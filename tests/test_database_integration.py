"""Migrate a fresh SQLite database and an explicitly configured disposable PostgreSQL schema."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from studio.api import create_app
from studio.storage import Base, Cursor, Delivery, Item

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["sqlite", "postgresql"])
def migrated_url(request, tmp_path, monkeypatch):
    admin_engine, schema = None, None
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path}/migrated.db"
    else:
        configured = os.getenv("STUDIO_TEST_POSTGRES_URL")
        if not configured:
            pytest.skip("Disposable PostgreSQL test service not configured")
        parsed = make_url(configured)
        if parsed.database != "studio_test" or parsed.host not in {"localhost", "127.0.0.1", "::1"}:
            pytest.fail("PostgreSQL tests require a loopback studio_test database")
        admin_engine = create_engine(parsed)
        schema = "studio_test_" + uuid.uuid4().hex
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(
            hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    try:
        command.upgrade(config, "0001")
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO source_items (platform, content_id, url, status) "
                "VALUES ('youtube', 'abcdefghijk', 'https://youtu.be/abcdefghijk', 'DISCOVERED')"
            )
        engine.dispose()
        command.upgrade(config, "0002")
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO telegram_outbox (key, chat_id, text, status, attempts, available_at) "
                "VALUES ('legacy', 123, 'legacy message', 'pending', 0, 0)"
            )
        engine.dispose()
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        yield url
    finally:
        if admin_engine:
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            admin_engine.dispose()


def test_migration_preserves_data_matches_models_and_serves_api(migrated_url):
    app = create_app(migrated_url, token="migration-test")
    try:
        with app.state.engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        with Session(app.state.engine) as session:
            assert session.get(Item, 1).version == 1
            assert session.get(Delivery, "legacy").reply_markup is None
            session.add(Cursor(name="telegram", offset=2**40))
            session.add(Delivery(key="migration", chat_id=2**40, text="آزمون"))
            session.commit()
        with TestClient(app, headers={"Authorization": "Bearer migration-test"}) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/items/1").json()["status"] == "DISCOVERED"
            response = client.post("/items/1/transition", json={"status": "REJECTED"},
                                   headers={"Idempotency-Key": "migration-command"})
            assert response.status_code == 200
            assert client.post("/items/1/transition", json={"status": "REJECTED"},
                               headers={"Idempotency-Key": "migration-command"}).status_code == 200
            assert client.get("/operations/telegram").json()["offset"] == 2**40
        with Session(app.state.engine) as session:
            assert len(list(session.scalars(select(Delivery)))) == 2
    finally:
        app.state.engine.dispose()


def test_quota_limit_is_atomic_on_migrated_database(migrated_url):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.orm import sessionmaker

    from studio.metadata import reserve_quota
    from studio.storage import Usage

    engine = create_engine(migrated_url)
    try:
        sessions = sessionmaker(engine)
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: reserve_quota(sessions, "2026-10-31", 3), range(10)))
        assert sum(results) == 3
        with sessions() as session:
            assert session.get(Usage, "youtube:2026-10-31").count == 3
    finally:
        engine.dispose()


def test_research_claim_and_budget_are_atomic_on_migrated_database(migrated_url):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone

    from sqlalchemy.orm import sessionmaker
    from test_scout_delivery import RESEARCH

    from studio.ai import AIConfig, OpenAIResearch, ResearchBlocked, ResearchQuotaExceeded
    from studio.research import Research
    from studio.storage import ResearchAttempt, Usage

    engine = create_engine(migrated_url)
    try:
        now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        instance = OpenAIResearch("fake-test-key", AIConfig("test-model", 1, budget_approved=True),
                                  sessionmaker(engine), clock=lambda: now)
        url = "https://www.youtube.com/watch?v=abcdefghijk"
        key = instance.fingerprint(instance.request("same transcript", url))
        def claim(_):
            try:
                return instance.claim(key, url) is None
            except ResearchBlocked:
                return False
        with ThreadPoolExecutor(max_workers=5) as pool:
            assert sum(pool.map(claim, range(10))) == 1
        other_key = instance.fingerprint(instance.request("different transcript", url))
        with pytest.raises(ResearchQuotaExceeded):
            instance.claim(other_key, url)
        with Session(engine) as session:
            assert session.get(Usage, "research:openai:2026-10-31").count == 1
            assert len(list(session.scalars(select(ResearchAttempt)))) == 1
        instance.finish(key, "completed", result=Research.model_validate(RESEARCH),
                        response={"id": "resp_test", "usage": {"input_tokens": 50, "output_tokens": 20}})
        assert instance.claim(key, url).title_fa == RESEARCH["title_fa"]
    finally:
        engine.dispose()

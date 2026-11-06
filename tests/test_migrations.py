from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_existing_data_upgrade_and_repeatability(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path}/migration.db"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_items (id, platform, content_id, url, status) VALUES (1, 'youtube', 'abcdefghijk', 'https://youtu.be/abcdefghijk', 'REJECTED')"
            )
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT status, version FROM source_items WHERE id=1")
        ).one() == ("REJECTED", 1)
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0008"
        )
    engine.dispose()

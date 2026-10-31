import pytest
from fastapi.testclient import TestClient

from studio.api import create_app
from studio.storage import Base


@pytest.fixture(autouse=True)
def isolated_external_configuration(monkeypatch):
    """Developer credentials must never opt ordinary tests into live integrations."""
    monkeypatch.setenv("STUDIO_FEEDS_ENABLED", "0")
    monkeypatch.setenv("STUDIO_AI_PROVIDER", "none")
    monkeypatch.setenv("STUDIO_AI_BUDGET_APPROVED", "0")
    monkeypatch.setenv("STUDIO_METADATA_PROVIDER", "none")
    monkeypatch.delenv("STUDIO_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STUDIO_YOUTUBE_API_KEY", raising=False)


@pytest.fixture
def app(tmp_path):
    application = create_app(f"sqlite:///{tmp_path}/scout.db", token="admin-test",
                             telegram_token="gateway-test", allowed_users={123})
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app, headers={"Authorization": "Bearer admin-test"}) as client:
        yield client


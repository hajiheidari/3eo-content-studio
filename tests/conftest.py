import pytest
from fastapi.testclient import TestClient

from studio.api import create_app
from studio.storage import Base


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


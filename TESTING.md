# Validation
Run `uv sync --frozen`, `uv run pytest -q`, `uv run ruff check src tests migrations`.
Tests use temporary SQLite and an in-process HTTP client; no paid services or actual video
are accessed. Current suite validates the foundation, not complete M1 or video production.
Run `uv run alembic upgrade head` twice to verify migration idempotence. Start the API using
README and make a local `/health` request. PostgreSQL, external provider integration, live
Telegram scheduling, media and full end-to-end export tests are pending implementation.

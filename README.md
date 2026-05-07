# Scrolis API

Backend for the Scrolis capstone project. Provides
authentication, social account connectivity (Twitter, Reddit), content
fetching and analysis pipelines, and a small cron job toolkit.

## Repository layout

- `api/` — FastAPI route handlers and request models
  - `routes/` — route modules: `auth.py`, `twitter.py`, `reddit.py`, `analysis.py`, `security.py`
  - `models/requests.py` — pydantic request bodies
- `service/` — integration services and DB helpers
  - `TwitterXAPIService.py`, `RedditService.py`, `AnalysisService.py`, `MongoDBService.py`, `db.py`
- `db/` — SQL bootstrap (`init.sql`) used to create the PostgreSQL schema
- `cron/` — scheduled/utility scripts (e.g., `cleanup_digests.py`)
- `tests/` — unit/integration tests (mini harness)
- `mongo-init/` — MongoDB initialization resources
- `main.py` — app entrypoint
- `config.py` — configuration loader (env-driven)
- `pyproject.toml` — dependencies and packaging

## Quick start (development)

Requirements: Python 3.10+, Poetry, Docker, Docker Compose, Postgres, MongoDB.

1. Install dependencies using Poetry:

```bash
poetry install
```

2. Set up and run services using Docker Compose:

```bash
docker-compose down -v
docker-compose up --build
```

This will start Postgres and MongoDB containers. The `-v` flag removes old volumes
to ensure a fresh database state.

3. Add required environment variables in a `.env` file or export them in your shell.

4. Start the development server in a new terminal:

```bash
poetry run uvicorn main:app --reload
```

Open the Swagger UI at `http://localhost:8000/docs` when running locally.

## Important environment variables

- `DATABASE_URL` — Postgres connection string (required)
- `MONGO_URI` — MongoDB connection string (optional, used for digests)
- `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`, `TWITTER_BEARER_TOKEN`, `TWITTER_REDIRECT_URI`
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_REDIRECT_URI`
- `OPENAI_API_KEY` — used by analysis service
- Other values are defined/loaded in `config.py`.

Keep secrets out of source control (use `.env` or your secret manager).

## Database schema notes

- The SQL bootstrap (`db/init.sql`) defines UUID primary keys for
  `users`, `social_credentials`, `refresh_tokens`, and `auth_providers`.
- The SQLAlchemy models in `service/models/authentication.py` should match
  the database DDL. If you change the model types, apply a migration or
  rebuild the database from `db/init.sql`.

If you hit insert/type errors (e.g. UUID vs integer), recreate the DB or run
a migration that aligns the SQL types with ORM definitions.

## Token handling

- OAuth tokens are stored in `social_credentials` and expiration times are
  saved as TIMESTAMP values (`twitter_token_expires_at`, `reddit_token_expires_at`).
- Route helpers `get_valid_x_access_token` and `get_valid_reddit_access_token`
  refresh tokens when expired and persist new tokens and expiry timestamps.

## Key API endpoints (overview)

- `POST /reddit/me` — exchange a Reddit access token, save refresh token and username
- `GET /reddit/auth/exchange` — build deep link/authorize URL for Reddit
- `GET /reddit/timeline` — fetch Reddit best posts (requires access token + username)
- `POST /twitter/auth/exchange` — exchange Twitter auth code and persist tokens
- `GET /twitter/me` — inspect Twitter-authenticated user
- `GET /analyze/topics` — run analysis pipeline using connected social accounts
- `POST /analyze/different-perspectives` — analysis for specified queries

Refer to the route modules in `api/routes/` for full parameter lists and
behavior.

## Running cron/maintenance tasks

- `cron/cleanup_digests.py` — housekeeping for stored digests (run daily).
- `cron/calculate_topics_preferences.py` — (placeholder) script to calculate user topic preferences
  based on historical data.

## Tests

- Run tests using Poetry:

```bash
poetry run pytest -q
```

Focus tests on pieces you modify: API routes, service wrappers (Twitter/Reddit),
and the AnalysisService.

## Troubleshooting

- If imports like `fastapi` or `sqlalchemy` are unresolved in your editor, ensure
  your virtualenv is activated and the interpreter is configured.
- Token exchange failures frequently show the raw OAuth response — check logs
  and verify client IDs/secrets and redirect URIs.

## Next steps / TODOs

- Add a migration script (Alembic) to manage schema evolution.
- Add automated tests for token refresh paths.
- Add CI steps to run tests and linting.

---

If you'd like, I can also:
- add a minimal `requirements.txt`/`pyproject` dev extras,
- scaffold an `alembic` migration setup,
- or open a PR with these docs and CI config.


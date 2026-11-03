# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Blurby is a small Flask app for sharing pastebin-style "secrets": a user posts text, it is stored in SQLite under a SHA-256 link, and it is automatically deleted after a TTL. The code is the `blurby` package in `src/blurby/`. The UI is Jinja templates based on the HTML5 UP "Massively" theme.

## Commands

```bash
uv sync    # create .venv from uv.lock (runtime + dev deps; installs blurby in editable mode)

# Run locally. The default DB path /blurby/data/sqlite.db won't exist outside Docker, so set it explicitly
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run blurby --debug   # Flask dev server on :5000
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run blurby           # waitress on :8080 (production mode; also `python -m blurby`)

# Tests (pytest, unittest-style tests in tests/, in-memory SQLite)
uv run pytest
uv run pytest tests/test_app.py::TestBase::test_viewing_a_shalink   # single test
uv run pytest --cov                                                 # with branch coverage report (as CI runs it)

# Lint and format (configured in pyproject.toml; CI runs check and format --check)
uv run ruff check .
uv run ruff format .

# Docker (serves on :8080, mounts ./data for the DB)
docker compose up --build
```

### Dependencies

Dependencies are managed with uv. Commit `pyproject.toml` and `uv.lock` together: CI and the Docker image both install with `uv sync --locked`, so a stale lockfile fails the build. CI and the Dockerfile pin uv to 0.13.1, and the build backend is `uv_build`.

Runtime dependencies are Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2 and waitress. Flask-SQLAlchemy 3 requires an application context for all database access. The lock forks SQLAlchemy: 2.1 needs Python 3.11+, so 3.9 and 3.10 get 2.0.

## Architecture

- **Modules.** `__init__.py` (`create_app`, `__version__`), `config.py` (env vars, `secret_ttl()`), `models.py` (`db`, the `Data` model), `views.py` (routes and the `current_username()` helper), `cleanup.py` (`CleanUpCrew`), and `main.py` (startup checks and `main()`). `setup_database.py` creates the schema by hand.
- **App factory.** `create_app(test_config=None)` builds the app. `db` (Flask-SQLAlchemy) is created unbound and attached with `init_app`, and the routes live on the `blurby` Blueprint, so `url_for` takes `.read` or `blurby.read`. Code that touches the DB outside a request (cleanup thread, startup checks, `setup_database`, tests) must push `app.app_context()`. Importing the module has no side effects.
- **Configuration.** `config.load_config(environ)` maps the `BLURBY_*` env vars to Flask config keys of the same name: `BLURBY_DB_FILE`, `BLURBY_TTL_HOURS`, `BLURBY_THREADS`, `BLURBY_HOST_IP`, and `BLURBY_CLEANUP_INTERVAL` (seconds between cleanup passes; not listed in the README). It also derives `SQLALCHEMY_DATABASE_URI`. Code reads these from `current_app.config`, and `secret_ttl()` returns the TTL as a `timedelta`. Tests override settings through `create_app({...})`.
- **Startup (`blurby.main:main`, the `blurby` console script).** `main()` configures logging (stdout plus a `FileHandler('./blurby.log')` in the current working directory) and creates the app. `check_preconditions(app)` exits the process if the DB file's directory doesn't exist or the path doesn't end in `.db`, and runs `db.create_all()` if the file is missing. Then `CleanUpCrew(app)` starts a daemon thread that deletes rows older than the TTL in a loop. `--debug` chooses the Flask dev server on port 5000; otherwise waitress serves on port 8080.
- **Links.** On `POST /`, `sha_link = sha256(data + str(time.time()))`, and the row's primary key is that hex digest. `/link/<sha>` reads a secret, `/delete/<sha>` deletes it (a plain GET), and `/find` checks that the input is 64 alphanumeric characters before redirecting to `/link/<sha>`.
- **Identity.** The app has no auth of its own. The "user" is whatever value the `username` request header carries (presumably set by an upstream auth proxy), falling back to `anonymous`. Every route passes `username` into its template, and it is saved as `Data.creator`.
- **Templates.** Every page extends `templates/base_structure.html` and fills the blocks `intro`, `header`, `main`, and `footer`. `msg.html` is the generic message/error page (`msg_title`, `msg`).
- **Static assets.** `static/sass/` holds the theme sources, but the repo has no Sass build step. The compiled `static/css/main.css` is committed and is what gets served. Templates and static files ship inside the wheel.

## Docker image

The image builds in `/build` and installs the locked runtime dependencies plus the non-editable `blurby` package into `/opt/venv`. It runs the `blurby` console script from `/blurby`, the runtime directory: the log file is written there and `/blurby/data` is the volume for the SQLite DB. Keep the deployment interface stable: port 8080, the `/blurby/data` volume, the `BLURBY_*` env vars, the link format, and the DB schema.

## Conventions

- Conventional Commits with an atomic commit style. Every commit should keep lint and tests passing. Bug fixes go in their own `fix:` commits, never bundled into refactors or dependency bumps.
- SemVer. The version is bumped in a dedicated release commit, not on every change.

## Versioning and CI

- `src/blurby/version.py` contains exactly `BLURBY_VERSION='...'`. The Docker workflow runs `source src/blurby/version.py` in bash, so the file must stay valid shell (no spaces around `=`), and it is excluded from `ruff format`. The version is also stored on every row (`Data.blurby_version`) and shown on `/about`.
- `pyproject.toml` has a `version` field because uv requires one. Keep it in sync with `src/blurby/version.py`.
- `.github/workflows/python-app.yml` (push/PR to `main`) runs `uv sync --locked`, `ruff check`, `ruff format --check`, and then `uv run pytest --cov` on Python 3.10.
- `.github/workflows/docker_build_push.yml` (push to `main`) builds the image and pushes it to Docker Hub as `joniturunen/blurby:<BLURBY_VERSION>` and `:latest`. The image uses Python 3.9.

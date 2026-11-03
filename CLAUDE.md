# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Blurby is a small Flask app for sharing pastebin-style "secrets": a user posts text, it is stored in SQLite under a SHA-256 link, and it is automatically deleted after a TTL. The whole backend is one module, `app/main.py`. The UI is Jinja templates based on the HTML5 UP "Massively" theme.

## Commands

All Python code imports siblings as top-level modules (`from main import ...`, `from version import ...`), so `app/` must be the import root. pytest handles this through `pythonpath` in `pyproject.toml`. For scripts, run them by path (`uv run python app/main.py`) or `cd app` first.

```bash
uv sync    # create .venv from uv.lock (runtime + dev dependencies)

# Run locally. The default DB path /blurby/data/sqlite.db won't exist outside Docker, so set it explicitly
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run python app/main.py --debug   # Flask dev server on :5000
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run python app/main.py           # waitress on :8080 (production mode)

# Tests (pytest runs the unittest-style tests in app/tests.py against in-memory SQLite)
uv run pytest
uv run pytest app/tests.py::TestBase::test_viewing_a_shalink   # single test
uv run pytest --cov                                            # with branch coverage report (as CI runs it)

# Lint and format (configured in pyproject.toml; CI runs check and format --check)
uv run ruff check .
uv run ruff format .

# Docker (serves on :8080, mounts ./data for the DB)
docker compose up --build
```

### Dependencies

Dependencies are managed with uv. Commit `pyproject.toml` and `uv.lock` together: CI and the Docker image both install with `uv sync --locked`, so a stale lockfile fails the build. CI and the Dockerfile pin uv to 0.13.1.

The upper bounds in `pyproject.toml` are deliberate. The code depends on Flask-SQLAlchemy 2.x behavior: model queries and `db.create_all()` run outside an application context (in `tests.py`, `check_preconditions()`, the cleanup thread, and `setup_database.py`). With Flask 3.x / Flask-SQLAlchemy 3.x every test fails with `RuntimeError: Working outside of application context`. Werkzeug 2.2 in turn uses `ast.Str`, which doesn't exist on Python 3.14, so `requires-python` is capped at `<3.14`.

Moving to Flask-SQLAlchemy 3 means wrapping those call sites in `app.app_context()`. The tests also override `SQLALCHEMY_DATABASE_URI` *after* importing `main`, which only works because 2.x creates the engine lazily.

## Architecture

- **Single-module app.** `app/main.py` holds the env-var config, the `Data` model, the routes, the startup checks, and the server entrypoint. There is no app factory (`create_app()` is on the README TODO list), so `app` and `db` are created when `main` is imported. That import also configures logging, including a `FileHandler('./blurby.log')` written to the current working directory.
- **Configuration** comes only from env vars read at import time: `BLURBY_DB_FILE`, `BLURBY_TTL_HOURS`, `BLURBY_THREADS`, `BLURBY_HOST_IP`, and `BLURBY_CLEANUP_INTERVAL` (seconds between cleanup passes; not listed in the README).
- **Startup (`__main__` only).** `check_preconditions()` exits the process if the DB file's directory doesn't exist or the path doesn't end in `.db`, and runs `db.create_all()` if the file is missing. Then `CleanUpCrew` starts a daemon thread that deletes rows older than the TTL in a loop. `--debug` chooses the Flask dev server on port 5000; otherwise waitress serves on port 8080. Importing `main` (as the tests do) runs neither step.
- **Links.** On `POST /`, `sha_link = sha256(data + str(time.time()))`, and the row's primary key is that hex digest. `/link/<sha>` reads a secret, `/delete/<sha>` deletes it (a plain GET), and `/find` checks that the input is 64 alphanumeric characters before redirecting to `/link/<sha>`.
- **Identity.** The app has no auth of its own. The "user" is whatever value the `username` request header carries (presumably set by an upstream auth proxy), falling back to `anonymous`. Every route passes `username` into its template, and it is saved as `Data.creator`.
- **Templates.** Every page extends `templates/base_structure.html` and fills the blocks `intro`, `header`, `main`, and `footer`. `msg.html` is the generic message/error page (`msg_title`, `msg`).
- **Static assets.** `static/sass/` holds the theme sources, but the repo has no Sass build step. The compiled `static/css/main.css` is committed and is what gets served.

## Versioning and CI

- `app/version.py` contains exactly `BLURBY_VERSION='x.y.z.w'`. Bump it with each change; past PRs do so. The Docker workflow runs `source app/version.py` in bash, so the file must stay valid shell (no spaces around `=`). The version is also stored on every row (`Data.blurby_version`) and shown on `/about`.
- `.github/workflows/python-app.yml` (push/PR to `main`) runs `uv sync --locked`, `ruff check`, `ruff format --check`, and then `uv run pytest --cov` on Python 3.10.
- `.github/workflows/docker_build_push.yml` (push to `main`) builds the image and pushes it to Docker Hub as `joniturunen/blurby:<BLURBY_VERSION>` and `:latest`. The image uses Python 3.9, installs the locked runtime dependencies into `/opt/venv`, and copies `app/` to `/blurby`.
- `pyproject.toml` has a `version` field because uv requires one. Keep it in sync with `app/version.py` until the version moves to `pyproject.toml` alone.

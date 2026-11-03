# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Blurby is a small Flask app for sharing pastebin-style "secrets": a user posts text, it is stored in SQLite under a SHA-256 link, and it is automatically deleted after a TTL. The whole backend is one module, `app/main.py`. The UI is Jinja templates based on the HTML5 UP "Massively" theme.

## Commands

All Python code imports siblings as top-level modules (`from main import ...`, `from version import ...`), so `app/` must be the import root. Either run scripts by path (`python app/tests.py`) or `cd app` first.

```bash
pip install -r requirements.txt

# Run locally. The default DB path /blurby/data/sqlite.db won't exist outside Docker, so set it explicitly
BLURBY_DB_FILE=$PWD/data/sqlite.db python app/main.py --debug   # Flask dev server on :5000
BLURBY_DB_FILE=$PWD/data/sqlite.db python app/main.py           # waitress on :8080 (production mode)

# Tests (unittest, in-memory SQLite)
python app/tests.py
cd app && python -m unittest tests.TestBase.test_viewing_a_shalink   # single test

# Lint (same as CI; only the first command fails the build)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Docker (serves on :8080, mounts ./data for the DB)
docker compose up --build
```

### Dependency versions matter

`requirements.txt` is unpinned, but the code depends on Flask-SQLAlchemy 2.x behavior: model queries and `db.create_all()` run outside an application context (in `tests.py`, `check_preconditions()`, the cleanup thread, and `setup_database.py`). With the current latest releases (Flask 3.x / Flask-SQLAlchemy 3.x), all tests fail with `RuntimeError: Working outside of application context`. Tests pass with:

```bash
pip install "flask<2.3" "werkzeug<2.3" "flask-sqlalchemy<3" "sqlalchemy<2" bleach waitress
```

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
- `.github/workflows/python-app.yml` (push/PR to `main`) runs flake8 and then `python app/tests.py` on Python 3.10.
- `.github/workflows/docker_build_push.yml` (push to `main`) builds the image and pushes it to Docker Hub as `joniturunen/blurby:<BLURBY_VERSION>` and `:latest`. The image uses Python 3.9 and copies `app/` to `/blurby`.

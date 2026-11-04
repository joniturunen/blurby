# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Blurby is a small Flask app for sharing pastebin-style "secrets": a user posts text, it is stored in SQLite under a random 64-hex-character link, and it is automatically deleted after a TTL. The code is the `blurby` package in `src/blurby/`. The UI is server-rendered Jinja templates styled with a vendored Pico CSS, plus two small vanilla JS files; every page also works without JavaScript.

## Commands

```bash
uv sync    # create .venv from uv.lock (runtime + dev deps; installs blurby in editable mode)

# Run locally. The default DB path /blurby/data/sqlite.db won't exist outside Docker, so set it explicitly
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run blurby --debug   # Flask dev server on :5000
BLURBY_DB_FILE=$PWD/data/sqlite.db uv run blurby           # waitress on :8080 (production mode; also `python -m blurby`)

# Tests (in-memory or temp-file SQLite)
uv run pytest
uv run pytest tests/test_app.py::TestBase::test_viewing_a_shalink   # single unittest-style test
uv run pytest tests/test_cleanup.py -k ttl                          # pytest-style tests by keyword
uv run pytest --cov                                                 # branch coverage, fails below 95% (as CI runs it)

# Lint and format (configured in pyproject.toml; CI runs check and format --check)
uv run ruff check .
uv run ruff format .

# Docker (serves on :8080, mounts ./data for the DB)
docker compose up --build
```

### Dependencies

Dependencies are managed with uv. Commit `pyproject.toml` and `uv.lock` together: CI and the Docker image both install with `uv sync --locked`, so a stale lockfile fails the build. CI and the Dockerfile pin uv to 0.13.1, and the build backend is `uv_build`.

Runtime dependencies are Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2 and waitress. Flask-SQLAlchemy 3 requires an application context for all database access. Blurby requires Python 3.14 (`.python-version` sets it for uv).

### Tests

`tests/test_app.py` holds the original unittest-style route tests (`TestBase`). The other test files are pytest-style and use fixtures from `tests/conftest.py`: `app` (in-memory DB, context pushed) and `make_file_app` (an on-disk SQLite file). pytest runs with `filterwarnings = ["error"]`, so dispose of the engine of any app a test creates (`db.engine.dispose()` in its context; the fixtures already do this). Otherwise Python's `ResourceWarning` for unclosed SQLite connections fails the suite. The same goes for a static-file response: `close()` it. To check a page's markup, use `elements(body, tag, **attrs)` from `tests/html_helpers.py`, which finds elements by their attributes, rather than matching exact HTML.

## Architecture

- **Modules.** `__init__.py` (`create_app`, `__version__`, the response headers), `config.py` (env vars, `secret_ttl()`, `ttl_choices()`), `models.py` (`db`, the `Data` model), `migrate.py` (`upgrade_schema()`), `views.py` (routes, the `current_username()` helper and the `hours` and `when` template filters), `cleanup.py` (`delete_expired()`, `clean_up_once()`, `CleanUpCrew`), and `main.py` (startup checks and `main()`). `setup_database.py` creates the schema by hand.
- **App factory.** `create_app(test_config=None)` builds the app. `db` (Flask-SQLAlchemy) is created unbound and attached with `init_app`, and the routes live on the `blurby` Blueprint, so `url_for` takes `.read` or `blurby.read`. Code that touches the DB outside a request (cleanup thread, startup checks, `setup_database`, tests) must push `app.app_context()`. Importing the module has no side effects.
- **Configuration.** `config.load_config(environ)` maps the `BLURBY_*` env vars to Flask config keys of the same name: `BLURBY_DB_FILE`, `BLURBY_TTL_HOURS` (the default TTL), `BLURBY_MAX_TTL_HOURS` (the longest TTL a creator can choose; defaults to, and is at least, `BLURBY_TTL_HOURS`, so an upgrade never lengthens retention), `BLURBY_THREADS`, `BLURBY_HOST_IP`, and `BLURBY_CLEANUP_INTERVAL` (seconds between cleanup passes). It also derives `SQLALCHEMY_DATABASE_URI` and sets `MAX_CONTENT_LENGTH`. Code reads these from `current_app.config`. `secret_ttl()` returns the default TTL as a `timedelta`, and `ttl_choices()` the hours a creator can choose: `TTL_PRESETS_HOURS` up to the cap, plus the default. Tests override settings through `create_app({...})`.
- **Startup (`blurby.main:main`, the `blurby` console script).** `main()` configures logging to stdout only (no log file; in Docker, `docker logs` keeps it) and creates the app. `check_preconditions(app)` exits the process if the DB file's directory doesn't exist or the path doesn't end in `.db`, and runs `db.create_all()` if the file is missing. It then runs `upgrade_schema()` (see Schema) and exits if that fails. Then `CleanUpCrew(app)` starts a daemon thread that calls `clean_up_once(app)` every interval. That function runs `delete_expired()` in an app context and logs any error rather than raising, so the thread can't die. `main()` then installs `stop_on_sigterm`, which turns SIGTERM into `KeyboardInterrupt`. In Docker Blurby is PID 1, which ignores signals it has no handler for, so without it `docker stop` would kill Blurby (exit 137) instead of letting waitress shut down. `--debug` chooses the Flask dev server on port 5000; otherwise waitress serves on port 8080, with `max_request_body_size` set to `MAX_CONTENT_LENGTH`.
- **Links.** On `POST /`, the link is `secrets.token_hex(32)` (64 hex chars), stored as the `Data.sha_link` primary key. The "sha" naming is historical. The form also posts `ttl_hours` (one of `ttl_choices()`, else 400; missing means the default) and `read_once`. `/link/<sha>` reads a secret and treats one past `Data.expiry` as not found, even before cleanup deletes it.
- **Burning.** `POST /burn/<sha>` (#26) and `POST /reveal/<sha>` (#27) burn a secret with one conditional `UPDATE … WHERE burnt_at IS NULL` (`burn_statement()`): `data` becomes `''`, and `burnt_at` and `burnt_by` (the `username` header, or NULL for anonymous) are set, so only the first burn counts. A burnt link shows `receipt.html` with 410 until its expiry. A read-once secret's `GET`/`HEAD` shows `reveal.html`, a notice with a Reveal form; only the reveal `POST` shows the text, and only if its burn succeeded. Both routes are POST-only (405 otherwise), because link previewers and scanners open links with `GET` or `HEAD`. `/delete/<sha>` still deletes without a trace, only on `POST`; a `GET` or `HEAD` shows `confirm_delete.html`. The read page offers Burn, not Delete. `/find` checks that the input is 64 alphanumeric characters before redirecting to `/link/<sha>`. The displayed link is built from the `Origin` header, falling back to `request.host_url` when it is missing or `null`.
- **Logs never contain secrets or links.** A link is the key to its secret, so it is as sensitive as the text. The engine runs with `hide_parameters=True`, so database errors don't print SQL parameters. `BlurbyFlask.log_exception` logs the route pattern (`/link/<string:sha_link>`) instead of the request path. `tests/test_log_privacy.py` checks both. Never log `request.path`, a `sha_link`, or form data. The Flask dev server under `--debug` still logs request paths.
- **Size limit.** A secret can be at most `config.MAX_SECRET_LENGTH` (16384) characters, the same as the form's textarea `maxlength`, and a test checks that they match. A line break counts as one character, as in the browser. Requests are capped at `MAX_REQUEST_BYTES` (150 KiB), because the URL-encoded form can take up to 9 bytes per character. Both limits return the 413 "Secret too long" page.
- **Schema.** `Data` has the original columns plus `expires_at`, `read_once`, `burnt_at` and `burnt_by` (0.4.0). `db.create_all()` doesn't add columns to an existing table, so `upgrade_schema()` adds missing ones with `ALTER TABLE ADD COLUMN` on every start. The schema only grows: never drop or change a column, and make new ones nullable or give them a `server_default`, so an older version still runs (and can insert) after a rollback. `Data.expiry` is `expires_at`, or for rows without one `timestamp + secret_ttl()`; the cleanup's DELETE uses the same rule. Times are naive server-local (UTC in Docker); the `when` filter shows them with the timezone.
- **Privacy headers.** `set_privacy_headers` (an `after_request` hook in `__init__.py`) sends `Referrer-Policy: same-origin` and `X-Content-Type-Options: nosniff` on every response, and `Cache-Control: no-store` and `CONTENT_SECURITY_POLICY` on HTML pages, so browsers don't keep pages with secrets or links, and don't send their URLs to other sites. Static files keep their caching. The CSP allows only Blurby's own scripts, styles and images (plus `data:` images, which Pico uses for form icons), and forbids framing; so templates must not use inline `<script>`, `on*=` handlers, `<style>` or `style=` attributes (`tests/test_pages.py` checks). Not `no-referrer`: under it, browsers send `Origin: null` with the page's own form posts, and the new link would start with `null/`.
- **Identity.** The app has no auth of its own. The "user" is whatever value the `username` request header carries (presumably set by an upstream auth proxy), falling back to `anonymous`. Every route passes `username` into its template, and it is saved as `Data.creator`.
- **Templates.** Every page extends `templates/base_structure.html` and fills the blocks `title` and `main` (usually one `<article>`). `msg.html` is the generic message/error page (`msg_title`, `msg`). Error pages return a matching status: 400 for an empty secret, an invalid TTL or an invalid `/find` link, 404 for an unknown or expired link, 405 for `GET` on `/burn` or `/reveal`, 410 for a burnt secret's receipt, 413 for a secret that is too long, and 500 for a database error.
- **Static assets.** No build step. `static/css/pico.orange.min.css` is Pico CSS 2.1.1 (the orange accent), vendored unmodified with `pico.LICENSE.md`; overrides go in `static/css/blurby.css`. `static/js/blurby.js` wires up `button[data-copy="#id"]` (copy a field; hidden until the script runs), `form[data-reveal]` (reveal in place with `fetch`) and `[data-shown-once]` (a `beforeunload` prompt). It also wires up the light/dark switch (`button[data-theme-switch]`), which saves the reader's choice in `localStorage` as `blurby-theme`, or forgets it when it matches the system's setting. `static/js/theme.js` is loaded in `<head>` without `defer` and applies a saved choice as `<html data-theme>` before the page is drawn; without one, Pico follows `prefers-color-scheme`. The server never sets `data-theme`. `static/images/hush.jpg` is the photo under the menu (krakenimages on Unsplash, credited on `/about` and in the README). Templates and static files ship inside the wheel. Pages load nothing from other sites (no web fonts, no CDNs): each request would tell that site who uses Blurby. `tests/test_third_party.py` checks the stylesheets and templates.

## Docker image

The image builds in `/build` and installs the locked runtime dependencies plus the non-editable `blurby` package into `/opt/venv`. It runs the `blurby` console script from `/blurby`, the runtime directory. `/blurby/data` is the only volume and holds the SQLite DB; logs go to stdout. Keep the deployment interface stable: port 8080, the `/blurby/data` volume, the `BLURBY_*` env vars, and the link format. The DB schema changes only additively (see Schema).

## Conventions

- Conventional Commits with an atomic commit style. Every commit should keep lint and tests passing. Bug fixes go in their own `fix:` commits, never bundled into refactors or dependency bumps.
- SemVer. The version is bumped in a dedicated release commit, not on every change.

## Versioning and CI

- The version lives only in `pyproject.toml`. `blurby.version.BLURBY_VERSION` reads it from the installed package metadata, so run `uv sync` after changing it. The Docker publish workflow reads it from `pyproject.toml` with `tomllib`. The version is also stored on every row (`Data.blurby_version`) and shown on `/about`.
- `.github/workflows/python-app.yml` (push/PR to `main`) runs `uv sync --locked`, `ruff check`, `ruff format --check`, and then `uv run pytest --cov` on Python 3.14.
- `.github/workflows/docker_build_push.yml` (push to `main`) builds the image and pushes it to Docker Hub as `joniturunen/blurby:<BLURBY_VERSION>` and `:latest`. The image is based on `python:3.14-slim-trixie`.

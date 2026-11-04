import logging
import signal
import sqlite3
import sys

import pytest
import sqlalchemy as sa
from flask import Flask

import blurby
from blurby.config import MAX_REQUEST_BYTES
from blurby.main import check_preconditions, main, stop_on_sigterm
from blurby.models import Data, db

# check_preconditions()


def test_exits_when_the_db_directory_does_not_exist(make_file_app, tmp_path):
    app = make_file_app(tmp_path / "missing" / "sqlite.db")

    with pytest.raises(SystemExit) as excinfo:
        check_preconditions(app)

    assert excinfo.value.code == 1


def test_explains_a_missing_db_directory_and_how_to_fix_it(
    make_file_app, tmp_path, caplog
):
    # Outside Docker the default /blurby/data doesn't exist, so this is the
    # first thing anyone running Blurby locally sees.
    missing_dir = tmp_path / "missing"
    app = make_file_app(missing_dir / "sqlite.db")

    with (
        caplog.at_level(logging.ERROR, logger="blurby.main"),
        pytest.raises(SystemExit),
    ):
        check_preconditions(app)

    assert f"directory {missing_dir} does not exist" in caplog.text
    assert "set BLURBY_DB_FILE" in caplog.text


def test_exits_when_the_db_file_does_not_end_in_db(make_file_app, tmp_path):
    app = make_file_app(tmp_path / "sqlite.sqlite3")

    with pytest.raises(SystemExit) as excinfo:
        check_preconditions(app)

    assert excinfo.value.code == 1


def test_creates_the_schema_when_the_db_file_is_missing(make_file_app, tmp_path):
    db_file = tmp_path / "sqlite.db"
    app = make_file_app(db_file)

    check_preconditions(app)

    assert db_file.exists()
    with app.app_context():
        assert sa.inspect(db.engine).has_table("data")


def test_keeps_an_existing_db_file(make_file_app, tmp_path):
    app = make_file_app(tmp_path / "sqlite.db")
    with app.app_context():
        db.create_all()
        db.session.add(Data(sha_link="kept", data="secret", creator="anonymous"))
        db.session.commit()

    check_preconditions(app)

    with app.app_context():
        assert db.session.get(Data, "kept") is not None


def test_upgrades_the_schema_of_an_existing_db_file(make_file_app, tmp_path):
    from test_migrate import SCHEMA_0_3

    db_file = tmp_path / "sqlite.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute(SCHEMA_0_3)
    conn.close()
    app = make_file_app(db_file)

    check_preconditions(app)

    with app.app_context():
        names = {column["name"] for column in sa.inspect(db.engine).get_columns("data")}
    assert {"expires_at", "read_once", "burnt_at", "burnt_by"} <= names


def test_exits_when_the_schema_cannot_be_upgraded(make_file_app, tmp_path, monkeypatch):
    app = make_file_app(tmp_path / "sqlite.db")

    def fail():
        raise sa.exc.OperationalError("ALTER TABLE", {}, Exception("read-only"))

    monkeypatch.setattr("blurby.main.upgrade_schema", fail)

    with pytest.raises(SystemExit) as excinfo:
        check_preconditions(app)

    assert excinfo.value.code == 1


def test_creates_a_relative_db_file_in_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("BLURBY_DB_FILE", "./data/sqlite.db")
    app = blurby.create_app()

    try:
        check_preconditions(app)
    finally:
        with app.app_context():
            db.engine.dispose()

    assert (tmp_path / "data" / "sqlite.db").exists()


def test_exits_when_the_db_cannot_be_created(make_file_app, tmp_path, monkeypatch):
    app = make_file_app(tmp_path / "sqlite.db")

    def fail(*args, **kwargs):
        raise sa.exc.OperationalError("CREATE TABLE", {}, Exception("read-only"))

    monkeypatch.setattr(db, "create_all", fail)

    with pytest.raises(SystemExit) as excinfo:
        check_preconditions(app)

    assert excinfo.value.code == 1


def test_reports_a_created_db_only_after_creating_it(
    make_file_app, tmp_path, monkeypatch, caplog
):
    app = make_file_app(tmp_path / "sqlite.db")

    def fail(*args, **kwargs):
        raise sa.exc.OperationalError("CREATE TABLE", {}, Exception("read-only"))

    monkeypatch.setattr(db, "create_all", fail)

    with (
        caplog.at_level(logging.INFO, logger="blurby.main"),
        pytest.raises(SystemExit),
    ):
        check_preconditions(app)

    assert "Created the DB file" not in caplog.text
    assert "Could not create database" in caplog.text


# main()


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Run main() against a temp DB, recording instead of starting servers/threads."""
    monkeypatch.chdir(tmp_path)  # catch any file main() might write
    monkeypatch.setenv("BLURBY_DB_FILE", str(tmp_path / "sqlite.db"))
    monkeypatch.setenv("BLURBY_HOST_IP", "127.0.0.1")
    monkeypatch.setenv("BLURBY_THREADS", "3")

    calls = {}
    crews = []
    monkeypatch.setattr("blurby.main.CleanUpCrew", crews.append)
    monkeypatch.setattr(
        "waitress.serve", lambda app, **kwargs: calls.update(serve=(app, kwargs))
    )
    monkeypatch.setattr(
        Flask, "run", lambda self, **kwargs: calls.update(run=(self, kwargs))
    )
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    # main() installs a SIGTERM handler; give pytest its own back afterwards.
    monkeypatch.setattr(signal, "signal", signal.signal)
    saved_sigterm = signal.getsignal(signal.SIGTERM)

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["blurby", *args])
        # Like a fresh process: an unconfigured root logger, so basicConfig()
        # installs (and we can close) its file and stream handlers.
        root.handlers = []
        try:
            main()
        finally:
            for handler in root.handlers:
                handler.close()
            root.handlers, root.level = saved_handlers, saved_level
        return calls, crews

    yield run

    signal.signal(signal.SIGTERM, saved_sigterm)
    for app in crews:
        with app.app_context():
            db.engine.dispose()


def test_main_serves_with_waitress_on_port_8080(run_main):
    calls, crews = run_main()

    app, kwargs = calls["serve"]
    assert kwargs == {
        "host": "127.0.0.1",
        "port": 8080,
        "threads": 3,
        # Without it, waitress buffers bodies up to 1 GiB to disk before Flask
        # can reject them.
        "max_request_body_size": MAX_REQUEST_BYTES,
    }
    assert crews == [app]
    assert "run" not in calls


def test_main_with_debug_runs_the_flask_debug_server_on_port_5000(run_main):
    calls, crews = run_main("--debug")

    app, kwargs = calls["run"]
    assert kwargs == {
        "host": "127.0.0.1",
        "port": 5000,
        "debug": True,
        "threaded": True,
    }
    assert crews == [app]
    assert "serve" not in calls


def test_main_creates_the_database_before_serving(run_main, tmp_path):
    run_main()

    assert (tmp_path / "sqlite.db").exists()


def test_main_logs_to_stdout_and_writes_no_log_file(run_main, tmp_path, capsys):
    # In Docker, `docker logs` already keeps stdout; a file in the container's
    # filesystem just grows (#24).
    run_main()

    assert "Starting Blurby" in capsys.readouterr().out
    assert not (tmp_path / "blurby.log").exists()


def test_main_stops_on_sigterm_like_on_ctrl_c(run_main):
    # In Docker, Blurby is PID 1, which ignores signals it has no handler for:
    # without one, `docker stop` waits and then kills it with exit code 137 (#31).
    run_main()

    assert signal.getsignal(signal.SIGTERM) is stop_on_sigterm


def test_the_sigterm_handler_raises_keyboard_interrupt():
    # Waitress's server loop catches KeyboardInterrupt and shuts down its
    # worker threads, and serve() then returns.
    with pytest.raises(KeyboardInterrupt):
        stop_on_sigterm(signal.SIGTERM, None)

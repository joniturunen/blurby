import pytest
import sqlalchemy as sa

import blurby
from blurby.models import db
from blurby.setup_database import setup_database


@pytest.fixture
def created_apps(monkeypatch):
    """Record the apps setup_database() creates, and dispose their engines."""
    apps = []

    def recording_create_app(*args, **kwargs):
        app = blurby.create_app(*args, **kwargs)
        apps.append(app)
        return app

    monkeypatch.setattr("blurby.setup_database.create_app", recording_create_app)
    yield apps
    for app in apps:
        with app.app_context():
            db.engine.dispose()


def test_creates_the_schema_in_the_configured_db_file(
    created_apps, monkeypatch, tmp_path, capsys
):
    db_file = tmp_path / "sqlite.db"
    monkeypatch.setenv("BLURBY_DB_FILE", str(db_file))

    setup_database()

    assert capsys.readouterr().out == "Database created!\n"
    with created_apps[0].app_context():
        assert sa.inspect(db.engine).has_table("data")


def test_reports_when_the_db_file_cannot_be_created(
    created_apps, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("BLURBY_DB_FILE", str(tmp_path / "missing" / "sqlite.db"))

    setup_database()

    assert "Can't create database" in capsys.readouterr().out

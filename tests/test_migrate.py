"""Databases from earlier versions get the new columns on startup, and earlier
versions keep working on an upgraded database."""

import logging
import sqlite3
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

from blurby.migrate import upgrade_schema
from blurby.models import Data, db

# The table as Blurby 0.3.x creates it.
SCHEMA_0_3 = """
CREATE TABLE data (
    sha_link VARCHAR(64) NOT NULL,
    data TEXT NOT NULL,
    timestamp DATETIME,
    creator VARCHAR(64) NOT NULL,
    event_history TEXT,
    blurby_version VARCHAR(64) NOT NULL,
    PRIMARY KEY (sha_link)
)
"""
NEW_COLUMNS = ["expires_at", "read_once", "burnt_at", "burnt_by"]
OLD_LINK = "0" * 63 + "3"
CREATED = datetime(2026, 11, 4, 9, 30)


@pytest.fixture
def old_db(tmp_path):
    """A database file written by 0.3.x, with one secret in it."""
    db_file = tmp_path / "sqlite.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute(SCHEMA_0_3)
        conn.execute(
            "INSERT INTO data VALUES (?, ?, ?, ?, NULL, ?)",
            (OLD_LINK, "from 0.3", CREATED.isoformat(" "), "alice", "0.3.1"),
        )
    conn.close()
    return db_file


def columns():
    return [column["name"] for column in sa.inspect(db.engine).get_columns("data")]


def test_upgrading_adds_the_missing_columns(make_file_app, old_db, caplog):
    app = make_file_app(old_db)

    with app.app_context(), caplog.at_level(logging.INFO, logger="blurby.migrate"):
        added = upgrade_schema()
        assert columns()[-4:] == NEW_COLUMNS

    assert added == NEW_COLUMNS
    for name in NEW_COLUMNS:
        assert f"Added the column {name}" in caplog.text


def test_an_old_secret_keeps_its_text_and_expiry(make_file_app, old_db):
    app = make_file_app(old_db)
    app.config["BLURBY_TTL_HOURS"] = 48

    with app.app_context():
        upgrade_schema()
        secret = db.session.get(Data, OLD_LINK)

        assert secret.data == "from 0.3"
        assert secret.read_once is False
        assert secret.burnt_at is None
        # No expires_at of its own: the server's TTL after its creation.
        assert secret.expiry == CREATED + timedelta(hours=48)


def test_upgrading_twice_changes_nothing(make_file_app, old_db):
    app = make_file_app(old_db)

    with app.app_context():
        upgrade_schema()
        assert upgrade_schema() == []
        assert columns()[-4:] == NEW_COLUMNS


def test_a_current_database_needs_no_upgrade(make_file_app, tmp_path):
    app = make_file_app(tmp_path / "sqlite.db")

    with app.app_context():
        db.create_all()
        assert upgrade_schema() == []


def test_a_database_without_the_table_gets_it(make_file_app, tmp_path):
    app = make_file_app(tmp_path / "sqlite.db")

    with app.app_context():
        assert upgrade_schema() == []
        assert columns()[-4:] == NEW_COLUMNS


def test_an_older_version_can_still_insert_after_the_upgrade(make_file_app, old_db):
    # After a rollback to 0.3.x, inserts name only the old columns.
    app = make_file_app(old_db)
    with app.app_context():
        upgrade_schema()
        db.engine.dispose()

    with sqlite3.connect(old_db) as conn:
        conn.execute(
            "INSERT INTO data (sha_link, data, timestamp, creator, blurby_version)"
            " VALUES (?, ?, ?, ?, ?)",
            ("1" * 64, "from a rollback", CREATED.isoformat(" "), "bob", "0.3.1"),
        )
    conn.close()

    with app.app_context():
        secret = db.session.get(Data, "1" * 64)
        assert secret.read_once is False
        assert secret.expires_at is None


def test_a_secret_with_its_own_expiry_uses_it(app):
    expires = CREATED + timedelta(days=5)
    secret = Data(sha_link="2" * 64, data="x", creator="a", timestamp=CREATED)
    secret.expires_at = expires

    assert secret.expiry == expires

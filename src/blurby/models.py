"""Database models."""

from datetime import datetime

import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy

from blurby.config import secret_ttl
from blurby.version import BLURBY_VERSION

db = SQLAlchemy()


class Data(db.Model):
    sha_link = db.Column(db.String(64), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    creator = db.Column(db.String(64), nullable=False)
    event_history = db.Column(db.Text)
    blurby_version = db.Column(db.String(64), nullable=False, default=BLURBY_VERSION)
    # Added in 0.4.0, by blurby.migrate.upgrade_schema() on existing databases.
    # Each is nullable or has a server default, so that an older version can
    # still insert rows after an upgrade (a rollback).
    expires_at = db.Column(db.DateTime)
    read_once = db.Column(
        db.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    burnt_at = db.Column(db.DateTime)
    burnt_by = db.Column(db.String(64))

    @property
    def expiry(self):
        """When the secret expires.

        Its own expires_at, or for a secret without one (written before 0.4.0,
        or by an older version after a rollback) the server's TTL after it was
        created.
        """
        return self.expires_at or self.timestamp + secret_ttl()

    def __repr__(self):
        return f"<Data {self.sha_link!r}>"

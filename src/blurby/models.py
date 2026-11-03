"""Database models."""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from blurby.version import BLURBY_VERSION

db = SQLAlchemy()


class Data(db.Model):
    sha_link = db.Column(db.String(64), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    creator = db.Column(db.String(64), nullable=False)
    event_history = db.Column(db.Text)
    blurby_version = db.Column(db.String(64), nullable=False, default=BLURBY_VERSION)

    def __repr__(self):
        return "<Data %r>" % self.sha_link

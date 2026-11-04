"""Application configuration, read from BLURBY_* environment variables."""

import os
from datetime import timedelta

from flask import current_app

DEFAULT_DB_FILE = "/blurby/data/sqlite.db"

# The longest secret, in characters; the form's textarea has the same maxlength.
MAX_SECRET_LENGTH = 16384
# The largest request body, in bytes. The form is URL-encoded, so a character
# can take up to 9 bytes (3 UTF-8 bytes, each sent as %XX): 16384 characters
# can be 147456 bytes.
MAX_REQUEST_BYTES = 150 * 1024


def load_config(environ):
    """Build the Flask config mapping from the given environment mapping."""
    db_file = environ.get("BLURBY_DB_FILE", DEFAULT_DB_FILE)
    return {
        "BLURBY_DB_FILE": db_file,
        "BLURBY_TTL_HOURS": int(environ.get("BLURBY_TTL_HOURS", "48")),
        "BLURBY_THREADS": int(environ.get("BLURBY_THREADS", "8")),
        "BLURBY_HOST_IP": environ.get("BLURBY_HOST_IP", "0.0.0.0"),
        "BLURBY_CLEANUP_INTERVAL": int(environ.get("BLURBY_CLEANUP_INTERVAL", "60")),
        # Absolute, because Flask-SQLAlchemy resolves a relative SQLite path
        # against the Flask instance folder instead of the working directory.
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{os.path.abspath(db_file)}",
        # Keep SQL parameters (a secret's text, its link) out of database error
        # messages, which end up in the logs.
        "SQLALCHEMY_ENGINE_OPTIONS": {"hide_parameters": True},
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        # Flask answers larger requests with 413 before reading them.
        "MAX_CONTENT_LENGTH": MAX_REQUEST_BYTES,
    }


def secret_ttl():
    """How long secrets are kept, from the app's BLURBY_TTL_HOURS setting."""
    return timedelta(hours=current_app.config["BLURBY_TTL_HOURS"])

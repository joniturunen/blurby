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
# The TTLs a creator can choose from, in hours, up to BLURBY_MAX_TTL_HOURS:
# an hour, a day, two days, five days, a week, two weeks.
TTL_PRESETS_HOURS = (1, 24, 48, 120, 168, 336)


def load_config(environ):
    """Build the Flask config mapping from the given environment mapping."""
    db_file = environ.get("BLURBY_DB_FILE", DEFAULT_DB_FILE)
    ttl_hours = int(environ.get("BLURBY_TTL_HOURS", "48"))
    # The longest TTL a creator can choose. It defaults to, and is at least,
    # the default TTL, so an upgrade never lengthens how long secrets are kept.
    max_ttl_hours = max(int(environ.get("BLURBY_MAX_TTL_HOURS", ttl_hours)), ttl_hours)
    return {
        "BLURBY_DB_FILE": db_file,
        "BLURBY_TTL_HOURS": ttl_hours,
        "BLURBY_MAX_TTL_HOURS": max_ttl_hours,
        "BLURBY_THREADS": int(environ.get("BLURBY_THREADS", "8")),
        "BLURBY_HOST_IP": environ.get("BLURBY_HOST_IP", "0.0.0.0"),
        "BLURBY_CLEANUP_INTERVAL": int(environ.get("BLURBY_CLEANUP_INTERVAL", "60")),
        # The request header that names the user, set by an auth proxy in front
        # of Blurby. Empty: Blurby ignores usernames, and everyone is anonymous.
        "BLURBY_USERNAME_HEADER": environ.get(
            "BLURBY_USERNAME_HEADER", "username"
        ).strip(),
        # The most secrets Blurby stores, so that its database can't fill the
        # disk; 0 means no limit.
        "BLURBY_MAX_SECRETS": max(int(environ.get("BLURBY_MAX_SECRETS", "10000")), 0),
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
    """The default TTL, from the app's BLURBY_TTL_HOURS setting.

    It applies when the creator doesn't choose one, and to secrets without an
    expiry of their own (from before 0.4.0).
    """
    return timedelta(hours=current_app.config["BLURBY_TTL_HOURS"])


def ttl_choices():
    """The TTLs, in hours, that a creator can choose from, shortest first.

    The presets up to BLURBY_MAX_TTL_HOURS, plus the default TTL.
    """
    cap = current_app.config["BLURBY_MAX_TTL_HOURS"]
    default = current_app.config["BLURBY_TTL_HOURS"]
    return sorted({hours for hours in TTL_PRESETS_HOURS if hours <= cap} | {default})

"""Application configuration, read from BLURBY_* environment variables."""

DEFAULT_DB_FILE = "/blurby/data/sqlite.db"


def load_config(environ):
    """Build the Flask config mapping from the given environment mapping."""
    db_file = environ.get("BLURBY_DB_FILE", DEFAULT_DB_FILE)
    return {
        "BLURBY_DB_FILE": db_file,
        "BLURBY_TTL_HOURS": int(environ.get("BLURBY_TTL_HOURS", "48")),
        "BLURBY_THREADS": int(environ.get("BLURBY_THREADS", "8")),
        "BLURBY_HOST_IP": environ.get("BLURBY_HOST_IP", "0.0.0.0"),
        "BLURBY_CLEANUP_INTERVAL": int(environ.get("BLURBY_CLEANUP_INTERVAL", "60")),
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    }

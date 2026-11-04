"""Command-line entry point: startup checks, cleanup thread and web server."""

import logging
import os
import signal
import sys

from blurby import __version__, create_app
from blurby.cleanup import CleanUpCrew
from blurby.migrate import upgrade_schema
from blurby.models import db

logger = logging.getLogger(__name__)


# Function to check preconditions for database file creation
def check_preconditions(app):
    db_file = app.config["BLURBY_DB_FILE"]
    # Check if database file exists
    logger.info(f"Checking if database file {db_file} exists...")
    # Check if filepath is valid path
    db_dir = os.path.dirname(db_file)
    if not os.path.isdir(db_dir):
        logger.error(
            f"Cannot use BLURBY_DB_FILE={db_file}: "
            f"the directory {db_dir} does not exist."
        )
        logger.error(
            "Create it, or set BLURBY_DB_FILE to a .db file in an existing "
            "directory, e.g. BLURBY_DB_FILE=./data/sqlite.db"
        )
        sys.exit(1)
    # Check if db_file variable includes a file extension at the end
    if not db_file.endswith(".db"):
        logger.error(f"{db_file} is not a valid database file!")
        sys.exit(1)
    if not os.path.isfile(db_file):
        # Folder exists and path valid but file not found
        # Try to create the database if failed log error and exit
        logger.info(f"Database file {db_file} not found, trying to create it...")
        try:
            with app.app_context():
                db.create_all()
            logger.info(f"Created the DB file {db_file}!")
        except Exception:
            logger.error(
                f"Could not create database URI {app.config['SQLALCHEMY_DATABASE_URI']}"
            )
            logger.warning(f"Please check if the database file {db_file} is writable!")
            sys.exit(1)
    else:
        # Write log entry
        logger.info(f"Database file: {db_file} found!")
    # Add the columns that a database from an earlier version lacks.
    try:
        with app.app_context():
            upgrade_schema()
    except Exception:
        logger.exception(f"Could not upgrade the schema of the database {db_file}")
        sys.exit(1)
    logger.info(
        f"\033[1mPreconditions check passed with following env values\033[0m:\033[1;32m \
                \n{' ' * 42}- BLURBY_TTL_HOURS = {app.config['BLURBY_TTL_HOURS']} \
                \n{' ' * 42}- BLURBY_MAX_TTL_HOURS = {app.config['BLURBY_MAX_TTL_HOURS']} \
                \n{' ' * 42}- BLURBY_THREADS = {app.config['BLURBY_THREADS']} \
                \n{' ' * 42}- BLURBY_DB_FILE = {db_file} \
                \n{' ' * 42}- BLURBY_CLEANUP_INTERVAL = {app.config['BLURBY_CLEANUP_INTERVAL']} \
                \n{' ' * 42}- BLURBY_USERNAME_HEADER = {app.config['BLURBY_USERNAME_HEADER']} \
                \n{' ' * 42}- BLURBY_MAX_SECRETS = {app.config['BLURBY_MAX_SECRETS']} \
                \033[0m"
    )


SECURITY_NOTES = "https://github.com/joniturunen/blurby#security"


def log_security_notes(app):
    """Log the risks that Blurby can't check for itself, and how to avoid them."""
    header = app.config["BLURBY_USERNAME_HEADER"]
    if header:
        logger.warning(
            f"Blurby shows the {header!r} request header as the user's name. The "
            "proxy in front of Blurby must set it, replacing any value a client "
            "sent, or remove it; otherwise anyone can claim any name. Set "
            "BLURBY_USERNAME_HEADER to the header your proxy sets, or to nothing "
            "to show everyone as anonymous."
        )
    else:
        logger.info("BLURBY_USERNAME_HEADER is empty: everyone is anonymous.")
    logger.warning(
        "Blurby speaks plain HTTP. Serve it over HTTPS, through a proxy that sends "
        "Strict-Transport-Security and rate-limits requests, and don't publish its "
        f"port to the internet. See {SECURITY_NOTES}"
    )
    if not app.config["BLURBY_MAX_SECRETS"]:
        logger.warning(
            "BLURBY_MAX_SECRETS is 0: Blurby stores any number of secrets, which "
            "can fill the disk."
        )
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        logger.warning(
            "Blurby runs as root. Run it as an unprivileged user; the Docker image "
            "uses UID 5678."
        )


def stop_on_sigterm(signum, frame):
    """Stop the server on SIGTERM (`docker stop`) the way Ctrl+C does.

    In Docker, Blurby is PID 1, and Linux ignores signals that PID 1 has no
    handler for, so without this `docker stop` waits and then kills Blurby.
    Waitress catches KeyboardInterrupt, shuts down its worker threads and
    returns from serve().
    """
    raise KeyboardInterrupt


def main():
    """Run Blurby: waitress on port 8080, or the Flask debug server with --debug."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        # stdout only: Docker keeps it (`docker logs`) and rotates it; a log file
        # inside the container would only grow.
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    app = create_app()
    host_ipaddr = app.config["BLURBY_HOST_IP"]
    # Echo the start of program to logger in color
    logger.info(f"\033[1;32m{'-' * 30}\033[0m")
    logger.info(f"\033[1m\033[1;32mStarting Blurby v{__version__}\033[0m")
    logger.info(f"\033[1;32m{'-' * 30}\033[0m")
    # Call check_preconditions function to check if database file exists
    check_preconditions(app)
    log_security_notes(app)
    # Start clean_up crew process in background
    CleanUpCrew(app)
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    # If commandline argument --debug is used, run the app in debug mode
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        # deepcode ignore RunWithDebugTrue: <please specify a reason of ignoring this>
        app.run(host=host_ipaddr, port=5000, debug=True, threaded=True)
    # Else run the app in production mode
    else:
        from waitress import serve

        serve(
            app,
            host=host_ipaddr,
            port=8080,
            threads=app.config["BLURBY_THREADS"],
            # Refuse larger bodies up front instead of buffering them to disk.
            max_request_body_size=app.config["MAX_CONTENT_LENGTH"],
        )


if __name__ == "__main__":
    main()

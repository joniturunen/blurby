"""Command-line entry point: startup checks, cleanup thread and web server."""

import logging
import os
import sys

from blurby import __version__, create_app
from blurby.cleanup import CleanUpCrew
from blurby.models import db

logger = logging.getLogger(" Blurby ")


# Function to check preconditions for database file creation
def check_preconditions(app):
    db_file = app.config["BLURBY_DB_FILE"]
    # Check if database file exists
    logger.info(f"Checking if database file {db_file} exists...")
    # Check if filepath is valid path
    if not os.path.isdir(os.path.dirname(db_file)):
        logger.error(f"{db_file} is not a valid path!")
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
            logger.info(f"Created the DB file {db_file}!")
            with app.app_context():
                db.create_all()
        except:
            logger.error(
                f"Could not create database URI {app.config['SQLALCHEMY_DATABASE_URI']}"
            )
            logger.warning(f"Please check if the database file {db_file} is writable!")
            sys.exit(1)
    else:
        # Write log entry
        logger.info(f"Database file: {db_file} found!")
    logger.info(
        f"\033[1mPreconditions check passed with following env values\033[0m:\033[1;32m \
                \n{' ' * 42}- BLURBY_TTL_HOURS = {app.config['BLURBY_TTL_HOURS']} \
                \n{' ' * 42}- BLURBY_THREADS = {app.config['BLURBY_THREADS']} \
                \n{' ' * 42}- BLURBY_DB_FILE = {db_file} \
                \n{' ' * 42}- BLURBY_CLEANUP_INTERVAL = {app.config['BLURBY_CLEANUP_INTERVAL']} \
                \033[0m"
    )


def main():
    """Run Blurby: waitress on port 8080, or the Flask debug server with --debug."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("./blurby.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    app = create_app()
    host_ipaddr = app.config["BLURBY_HOST_IP"]
    # Echo the start of program to logger in color
    logger.info(f"\033[1;32m{'-' * 30}\033[0m")
    logger.info(f"\033[1m\033[1;32mStarting Blurby v{__version__}\033[0m")
    logger.info(f"\033[1;32m{'-' * 30}\033[0m")
    # Call check_preconditions function to check if database file exists
    check_preconditions(app)
    # Start clean_up crew process in background
    CleanUpCrew(app)
    # If commandline argument --debug is used, run the app in debug mode
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        # deepcode ignore RunWithDebugTrue: <please specify a reason of ignoring this>
        app.run(host=host_ipaddr, port=5000, debug=True, threaded=True)
    # Else run the app in production mode
    else:
        from waitress import serve

        serve(app, host=host_ipaddr, port=8080, threads=app.config["BLURBY_THREADS"])


if __name__ == "__main__":
    main()

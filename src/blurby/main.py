from flask import (
    Blueprint,
    Flask,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from blurby.config import load_config
from blurby.version import BLURBY_VERSION
import hashlib, time, logging, threading, sys, os

# Define version and author
__version__ = BLURBY_VERSION
__author__ = "Joni Turunen"

db = SQLAlchemy()
bp = Blueprint("blurby", __name__)
logger = logging.getLogger(" Blurby ")


def create_app(test_config=None):
    """Create the Blurby app, configured from BLURBY_* environment variables.

    `test_config` entries override the environment-derived settings.
    """
    app = Flask(__name__)
    app.config.from_mapping(load_config(os.environ))
    if test_config is not None:
        app.config.from_mapping(test_config)
    db.init_app(app)
    app.register_blueprint(bp)
    return app


def secret_ttl():
    """How long secrets are kept, from the app's BLURBY_TTL_HOURS setting."""
    return timedelta(hours=current_app.config["BLURBY_TTL_HOURS"])


class Data(db.Model):
    sha_link = db.Column(db.String(64), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    creator = db.Column(db.String(64), nullable=False)
    event_history = db.Column(db.Text)
    blurby_version = db.Column(db.String(64), nullable=False, default=__version__)

    def __repr__(self):
        return "<Data %r>" % self.sha_link


class CleanUpCrew:
    """Background thread that removes data older than the TTL."""

    def __init__(self, app):
        self.app = app
        # Define the interval in seconds for the clean_up function
        self.interval = app.config["BLURBY_CLEANUP_INTERVAL"]
        thread = threading.Thread(target=self.clean_up, args=())
        thread.daemon = True
        thread.start()

    def clean_up(self):
        while True:
            with self.app.app_context():
                ttl = secret_ttl()
                logger.info(
                    f"Checking for older than \033[1m{datetime.now() - ttl}\033[0m data entries..."
                )
                # if there are entries in the database that are older than the TTL remove them
                if Data.query.filter(Data.timestamp < datetime.now() - ttl).all():
                    logger.info(
                        f"Found data entries that are older than \033[1m{datetime.now() - ttl}\033[0m, deleting..."
                    )
                    Data.query.filter(Data.timestamp < datetime.now() - ttl).delete()
                    db.session.commit()
                    # write log entry
                    logger.info(f"Cleaned up old data entries!")
            time.sleep(self.interval)


def current_username():
    """Return the user named by the `username` request header, or "anonymous"."""
    return request.headers.get("username") or "anonymous"


@bp.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        posted_data = request.form["data"]
        url = request.headers.get("Origin") + "/"
        salty_data = posted_data + str(time.time())
        sha = hashlib.sha256(salty_data.encode())
        sha_link = sha.hexdigest()
        creator = current_username()
        new_data = Data(data=posted_data, sha_link=sha_link, creator=creator)
        try:
            db.session.add(new_data)
            db.session.commit()
            logger.info(f"{current_username()} submitted a secret")
            return render_template(
                "link.html",
                username=current_username(),
                sha_link=sha_link,
                url=url,
            )
        except:
            # Write log entry and return error message from sqlalchemy
            logger.error(
                f"⚠ Error adding new data entry to database! Action called by {current_username()}"
            )
            logger.error(f"{sys.exc_info()[0]}")
            logger.error(f"{sys.exc_info()[1]}")
            logger.error(f"statement error: {sys.exc_info()[0].__dict__}")
            return render_template(
                "msg.html",
                username=current_username(),
                msg_title="⚠ There was an error!",
                msg="There was a problem connecting the database",
            )
    else:
        logger.info(f"{current_username()} requested the default page")
        return render_template(
            "main.html",
            username=current_username(),
        )


@bp.route("/link/<string:sha_link>")
def read(sha_link):
    data = db.session.get(Data, sha_link)
    if data:
        logger.info(f"{current_username()} requested a sha link")
        return render_template(
            "read_link.html",
            username=current_username(),
            retrieved_message=data.data,
            time=data.timestamp,
            sha_link=data.sha_link,
            ttl=data.timestamp + secret_ttl(),
            creator=data.creator,
            event_history=data.event_history,
        )
    else:
        # return 404
        logger.info(f"{current_username()} requested a non-existent sha link")
        return render_template(
            "msg.html",
            username=current_username(),
            msg_title="⚠ No message found!",
            msg="Message might be too old and deleted or it never existed. - Check your link.",
        ), 404


@bp.route("/delete/<string:sha_link>")
def delete(sha_link):
    data_to_delete = db.session.get(Data, sha_link)
    try:
        db.session.delete(data_to_delete)
        db.session.commit()
        logger.info(f"{current_username()} deleted a sha link")
        return render_template(
            "msg.html",
            username=current_username(),
            msg_title="👌 Message succesfully deleted!",
            msg="You can create a new secret!",
        )
    except:
        return render_template(
            "msg.html",
            username=current_username(),
            msg_titl="⚠ There was an error!",
            msg="Message was not found - maybe it was already deleted?",
        )


@bp.route("/find", methods=["POST", "GET"])
def find():
    logger.info(f"{current_username()} requested to find a secret")
    if request.method == "POST":
        sha_link = request.form["sha_link"]
        # Check if sha_link is valid and 'secure'
        if len(sha_link) == 64:
            if sha_link.isalnum():
                # url_for builds a same-site path and URL-quotes the value, so the
                # input can't turn this into an open redirect.
                return redirect(url_for(".read", sha_link=sha_link))
            else:
                return render_template(
                    "msg.html",
                    username=current_username(),
                    msg_title="⚠ Invalid link!",
                    msg="The link you entered is not valid, please try again.",
                )
        else:
            # Error message since the sha is not valid or not found
            return render_template(
                "msg.html",
                username=current_username(),
                msg_title="⚠ No message found!",
                msg="Message might be too old and deleted or it never existed. - Check your link.",
            ), 404
    elif request.method == "GET":
        return render_template(
            "find.html",
            username=current_username(),
        )


# Render About page
@bp.route("/about")
def about():
    logger.info(f"{current_username()} requested the about page")
    return render_template(
        "about.html",
        username=current_username(),
        ttl=secret_ttl(),
        version=__version__,
        author=__author__,
        db_conf=str(current_app.config["SQLALCHEMY_DATABASE_URI"]),
        request_headers=request.headers,
    )


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

"""HTTP routes, registered on the "blurby" blueprint."""

import logging
import secrets
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for

from blurby.config import MAX_SECRET_LENGTH, secret_ttl
from blurby.models import Data, db
from blurby.version import BLURBY_VERSION

bp = Blueprint("blurby", __name__)
logger = logging.getLogger(__name__)


def current_username():
    """Return the user named by the `username` request header, or "anonymous"."""
    return request.headers.get("username") or "anonymous"


@bp.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        posted_data = request.form["data"]
        # Browsers count a line break as one character but send it as "\r\n".
        if len(posted_data.replace("\r\n", "\n")) > MAX_SECRET_LENGTH:
            return secret_too_long()
        # Browsers send Origin with form posts; fall back to this host for
        # clients that don't (curl, scripts).
        origin = request.headers.get("Origin")
        url = f"{origin}/" if origin else request.host_url
        # 256 random bits, as 64 hex characters: the same format as before
        sha_link = secrets.token_hex(32)
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
        except Exception:
            # Log the error with its traceback and show a generic error page
            logger.exception(
                f"⚠ Error adding new data entry to database! Action called by {current_username()}"
            )
            return render_template(
                "msg.html",
                username=current_username(),
                msg_title="⚠ There was an error!",
                msg="There was a problem connecting the database",
            ), 500
    else:
        logger.info(f"{current_username()} requested the default page")
        return render_template(
            "main.html",
            username=current_username(),
        )


@bp.app_errorhandler(413)
def secret_too_long(error=None):
    """Reject a secret over the size limit, whether Flask or the view caught it."""
    logger.info(f"{current_username()} submitted a secret over the size limit")
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ Secret too long!",
        msg=f"A secret can be at most {MAX_SECRET_LENGTH} characters.",
    ), 413


@bp.route("/link/<string:sha_link>")
def read(sha_link):
    data = db.session.get(Data, sha_link)
    # Expired secrets stay in the DB until the next cleanup pass; don't show them.
    if data and datetime.now() < data.timestamp + secret_ttl():
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


@bp.route("/delete/<string:sha_link>", methods=["GET", "POST"])
def delete(sha_link):
    data_to_delete = db.session.get(Data, sha_link)
    if data_to_delete is None:
        logger.info(f"{current_username()} tried to delete a non-existent sha link")
        return render_template(
            "msg.html",
            username=current_username(),
            msg_title="⚠ There was an error!",
            msg="Message was not found - maybe it was already deleted?",
        ), 404
    # Opening a delete link (GET, or HEAD from link checkers and previewers)
    # only asks for confirmation; deleting takes a POST.
    if request.method != "POST":
        logger.info(f"{current_username()} opened a delete link")
        return render_template(
            "confirm_delete.html", username=current_username(), sha_link=sha_link
        )
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
    except Exception:
        logger.exception(
            f"⚠ Error deleting a secret from the database! Action called by {current_username()}"
        )
        return render_template(
            "msg.html",
            username=current_username(),
            msg_title="⚠ There was an error!",
            msg="There was a problem connecting the database",
        ), 500


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
    else:
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
        version=BLURBY_VERSION,
    )

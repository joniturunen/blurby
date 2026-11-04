"""HTTP routes, registered on the "blurby" blueprint."""

import logging
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from markupsafe import Markup

from blurby.config import MAX_SECRET_LENGTH, ttl_choices
from blurby.models import Data, db
from blurby.version import BLURBY_VERSION

bp = Blueprint("blurby", __name__)
logger = logging.getLogger(__name__)


def current_username():
    """Return the user named by the BLURBY_USERNAME_HEADER request header.

    The header is `username` by default. Without it, or with the setting
    empty, the user is "anonymous".
    """
    header = current_app.config["BLURBY_USERNAME_HEADER"]
    return (header and request.headers.get(header)) or "anonymous"


@bp.before_request
def refuse_posts_from_other_sites():
    """Refuse a form post that a page on another site sent (CSRF).

    Browsers tell where a request comes from in Sec-Fetch-Site: Blurby's own
    forms and its reveal fetch send "same-origin", and a page on another site
    sends "same-site" or "cross-site". Requests without the header (curl,
    scripts, browsers from before 2023) go through. Not a check of Origin
    against Host: behind a proxy, Host can name the proxy's upstream instead.
    """
    if request.method != "POST":
        return None
    if request.headers.get("Sec-Fetch-Site") not in ("same-site", "cross-site"):
        return None
    logger.info(f"{current_username()} sent a form from another site; refused it")
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ Request refused!",
        msg="Blurby only accepts forms sent from its own pages.",
    ), 403


@bp.app_template_filter("hours")
def describe_hours(hours):
    """A TTL in words: "1 hour", "2 days", "1 week"."""
    unit, count = "hour", hours
    for name, length in (("week", 168), ("day", 24)):
        if hours % length == 0:
            unit, count = name, hours // length
            break
    return f"{count} {unit}{'' if count == 1 else 's'}"


@bp.app_template_filter("when")
def show_time(value):
    """A <time> element for a stored time, with the server's timezone.

    Blurby stores naive local times: UTC in the Docker image.
    """
    local = value.astimezone()
    return Markup('<time datetime="{}">{}</time>').format(
        local.isoformat(timespec="minutes"), local.strftime("%Y-%m-%d %H:%M %Z")
    )


def not_found():
    logger.info(f"{current_username()} requested a non-existent sha link")
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ No message found!",
        msg="Message might be too old and deleted or it never existed. - Check your link.",
    ), 404


def database_error():
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ There was an error!",
        msg="There was a problem connecting the database",
    ), 500


def receipt(secret, just_burnt=False):
    """The read receipt of a burnt secret: 410 Gone, or 200 right after burning."""
    return render_template(
        "receipt.html",
        username=current_username(),
        secret=secret,
        just_burnt=just_burnt,
    ), 200 if just_burnt else 410


def invalid_ttl():
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ Invalid TTL!",
        msg="Choose how long to keep the secret from the list.",
    ), 400


def is_full():
    """Whether Blurby holds BLURBY_MAX_SECRETS secrets already (0: no limit).

    Burnt receipts count, and so do expired secrets until the next cleanup
    pass. Simultaneous posts can go a few over the limit.
    """
    limit = current_app.config["BLURBY_MAX_SECRETS"]
    stored = db.session.scalar(db.select(db.func.count()).select_from(Data))
    return bool(limit) and stored >= limit


def blurby_is_full():
    limit = current_app.config["BLURBY_MAX_SECRETS"]
    logger.warning(
        f"Refused a secret from {current_username()}: Blurby holds {limit} "
        "secrets, its BLURBY_MAX_SECRETS limit"
    )
    return render_template(
        "msg.html",
        username=current_username(),
        msg_title="⚠ Blurby is full!",
        msg="Blurby holds as many secrets as it may. Try again when older ones have expired.",
    ), 507


@bp.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        posted_data = request.form["data"]
        if not posted_data.strip():
            return render_template(
                "msg.html",
                username=current_username(),
                msg_title="⚠ Empty secret!",
                msg="Write the secret first, then generate its link.",
            ), 400
        # Browsers count a line break as one character but send it as "\r\n".
        if len(posted_data.replace("\r\n", "\n")) > MAX_SECRET_LENGTH:
            return secret_too_long()
        # Without a choice (curl, scripts), the default TTL applies.
        ttl_hours = request.form.get("ttl_hours")
        if ttl_hours is None:
            hours = current_app.config["BLURBY_TTL_HOURS"]
        elif ttl_hours.isdecimal() and int(ttl_hours) in ttl_choices():
            hours = int(ttl_hours)
        else:
            return invalid_ttl()
        # Browsers send Origin with form posts; fall back to this host for
        # clients that don't (curl, scripts) and for the "null" origin that
        # browsers send from privacy-sensitive contexts.
        origin = request.headers.get("Origin")
        url = f"{origin}/" if origin and origin != "null" else request.host_url
        # 256 random bits, as 64 hex characters: the same format as before
        sha_link = secrets.token_hex(32)
        creator = current_username()
        now = datetime.now()
        new_data = Data(
            data=posted_data,
            sha_link=sha_link,
            creator=creator,
            timestamp=now,
            expires_at=now + timedelta(hours=hours),
            read_once=bool(request.form.get("read_once")),
        )
        try:
            if is_full():
                return blurby_is_full()
            db.session.add(new_data)
            db.session.commit()
            logger.info(f"{current_username()} submitted a secret")
            return render_template(
                "link.html",
                username=current_username(),
                sha_link=sha_link,
                url=url,
                expires=new_data.expires_at,
                read_once=new_data.read_once,
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
            ttl_choices=ttl_choices(),
            default_ttl=current_app.config["BLURBY_TTL_HOURS"],
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
    if data is None or datetime.now() >= data.expiry:
        return not_found()
    if data.burnt_at:
        logger.info(f"{current_username()} opened the receipt of a burnt secret")
        return receipt(data)
    if data.read_once:
        # Opening the link (GET, or HEAD from previewers) never shows or burns
        # a read-once secret; only the Reveal button's POST does.
        logger.info(f"{current_username()} opened a read-once sha link")
        return render_template("reveal.html", username=current_username(), secret=data)
    logger.info(f"{current_username()} requested a sha link")
    return show_secret(data, data.data)


def show_secret(data, text, shown_once=False):
    return render_template(
        "read_link.html",
        username=current_username(),
        retrieved_message=text,
        time=data.timestamp,
        sha_link=data.sha_link,
        ttl=data.expiry,
        creator=data.creator,
        shown_once=shown_once,
    )


def burn_statement(sha_link, now, reader):
    """Burn the secret unless it's burnt already: the condition makes it atomic."""
    return (
        db.update(Data)
        .where(Data.sha_link == sha_link, Data.burnt_at.is_(None))
        .values(
            data="",
            burnt_at=now,
            burnt_by=None if reader == "anonymous" else reader,
        )
    )


@bp.route("/burn/<string:sha_link>", methods=["POST"])
def burn(sha_link):
    """Delete a secret's text for good, leaving a read receipt (#26).

    POST only: link previewers and scanners open links with GET or HEAD.
    """
    secret = db.session.get(Data, sha_link)
    now = datetime.now()
    if secret is None or now >= secret.expiry:
        return not_found()
    reader = current_username()
    # Only the first burn counts.
    try:
        burnt = db.session.execute(burn_statement(sha_link, now, reader)).rowcount == 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(f"⚠ Error burning a secret! Action called by {reader}")
        return database_error()
    db.session.refresh(secret)
    if burnt:
        logger.info(f"{reader} burnt a secret")
    return receipt(secret, just_burnt=burnt)


@bp.route("/reveal/<string:sha_link>", methods=["POST"])
def reveal(sha_link):
    """Show a read-once secret and burn it in the same step (#27).

    POST only: link previewers and scanners open links with GET or HEAD.
    """
    secret = db.session.get(Data, sha_link)
    now = datetime.now()
    if secret is None or now >= secret.expiry:
        return not_found()
    if not secret.read_once:
        return redirect(url_for(".read", sha_link=sha_link), 303)
    text = secret.data
    reader = current_username()
    # Of simultaneous reveals, only the one whose burn succeeds shows the text.
    try:
        burnt = db.session.execute(burn_statement(sha_link, now, reader)).rowcount == 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(f"⚠ Error revealing a secret! Action called by {reader}")
        return database_error()
    if not burnt:
        db.session.refresh(secret)
        return receipt(secret)
    logger.info(f"{reader} revealed a read-once secret, which burnt it")
    return show_secret(secret, text, shown_once=True)


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
                ), 400
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
        default_ttl=current_app.config["BLURBY_TTL_HOURS"],
        max_ttl=current_app.config["BLURBY_MAX_TTL_HOURS"],
        version=BLURBY_VERSION,
    )

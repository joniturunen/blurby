"""Blurby: share short-lived secrets via SHA-256 links."""

import os

from flask import Flask, request

from blurby.config import load_config
from blurby.models import db
from blurby.version import BLURBY_VERSION
from blurby.views import bp

__version__ = BLURBY_VERSION
__author__ = "Joni Turunen"


class BlurbyFlask(Flask):
    """Flask, except that failed requests are logged without their secret link."""

    def log_exception(self, exc_info):
        # Flask logs request.path, but a Blurby path such as /link/<link> holds
        # the key to a secret. Log the route pattern instead.
        rule = request.url_rule.rule if request.url_rule else "<no route>"
        self.logger.error(f"Exception on {rule} [{request.method}]", exc_info=exc_info)


# Pages may load only Blurby's own scripts, stylesheets and images: no inline
# scripts or styles, nothing from other sites. Pico CSS draws its form icons as
# data: SVGs. frame-ancestors keeps other sites from framing Blurby's buttons
# under a decoy (clickjacking).
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
    ]
)


def set_privacy_headers(response):
    """Keep pages out of caches and keep their URLs, which hold links, private."""
    # Send a Referer only to Blurby itself, never to other sites. Not
    # no-referrer: under it, browsers send `Origin: null` with the page's own
    # form posts, and Blurby builds the new secret's link from Origin.
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Pages can show a secret or its link; static files can be cached as before.
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


def create_app(test_config=None):
    """Create the Blurby app, configured from BLURBY_* environment variables.

    `test_config` entries override the environment-derived settings.
    """
    app = BlurbyFlask(__name__)
    app.config.from_mapping(load_config(os.environ))
    if test_config is not None:
        app.config.from_mapping(test_config)
    db.init_app(app)
    app.register_blueprint(bp)
    app.after_request(set_privacy_headers)
    return app

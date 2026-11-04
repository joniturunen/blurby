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
    return app

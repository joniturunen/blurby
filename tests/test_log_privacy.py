"""Logs must never contain a secret or its link: the link is the key to the secret."""

import logging
import re

import pytest

from blurby import create_app
from blurby.models import db

LINK = re.compile(r"[0-9a-f]{64}")


@pytest.fixture
def broken_app():
    """An app whose database has no tables, so every query fails."""
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_a_failed_save_logs_neither_the_secret_nor_its_link(broken_app, caplog):
    with caplog.at_level(logging.INFO):
        response = broken_app.test_client().post(
            "/", data={"data": "TOP-SECRET-VALUE"}, headers={"Origin": "http://x"}
        )

    assert b"There was a problem connecting the database" in response.data
    assert "Error adding new data entry" in caplog.text  # the error is still logged
    assert "TOP-SECRET-VALUE" not in caplog.text
    assert not LINK.search(caplog.text)


@pytest.mark.parametrize(
    ("path", "route"),
    [("/link/", "/link/<string:sha_link>"), ("/delete/", "/delete/<string:sha_link>")],
)
def test_a_failed_request_logs_its_route_but_not_the_link(
    broken_app, caplog, path, route
):
    with caplog.at_level(logging.INFO):
        response = broken_app.test_client().get(path + "c" * 64)

    assert response.status_code == 500
    assert f"Exception on {route} [GET]" in caplog.text
    assert not LINK.search(caplog.text)

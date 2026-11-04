"""The server enforces the same secret size limit as the browser form."""

import re

import pytest

from blurby.config import MAX_SECRET_LENGTH
from blurby.models import Data


def post_secret(app, secret):
    return app.test_client().post(
        "/", data={"data": secret}, headers={"Origin": "http://x"}
    )


def test_the_form_limit_matches_the_server_limit(app):
    body = app.test_client().get("/").get_data(as_text=True)

    assert re.search(r'name="data"[^>]*maxlength="(\d+)"', body)[1] == str(
        MAX_SECRET_LENGTH
    )


@pytest.mark.parametrize(
    "secret",
    [
        "a" * MAX_SECRET_LENGTH,
        # 3 UTF-8 bytes each, sent as %XX%XX%XX: the largest form a browser sends.
        "€" * MAX_SECRET_LENGTH,
        # Browsers count a line break as one character but send it as "\r\n".
        "a\r\n" * (MAX_SECRET_LENGTH // 2),
    ],
    ids=["ascii", "three-byte characters", "line breaks"],
)
def test_a_secret_the_browser_allows_is_stored(app, secret):
    response = post_secret(app, secret)

    assert response.status_code == 200
    assert Data.query.count() == 1


@pytest.mark.parametrize(
    "secret",
    ["a" * (MAX_SECRET_LENGTH + 1), "a" * 1_000_000],
    ids=["one character too long", "request body over the limit"],
)
def test_a_secret_over_the_limit_is_rejected_with_413(app, secret):
    response = post_secret(app, secret)

    assert response.status_code == 413
    assert "Secret too long" in response.get_data(as_text=True)
    assert Data.query.count() == 0

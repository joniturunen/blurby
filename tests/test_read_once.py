"""Read-once secrets (#27): opening the link shows a notice, and the secret is
shown only when the reader clicks Reveal, which burns it in the same step."""

from datetime import datetime, timedelta
from unittest import mock

import pytest
from html_helpers import elements
from sqlalchemy.exc import SQLAlchemyError

from blurby.models import Data, db

LINK = "a" * 63 + "1"
TEXT = "the launch code is 4-8-15"


@pytest.fixture
def client(app):
    now = datetime.now()
    db.session.add(
        Data(
            sha_link=LINK,
            data=TEXT,
            creator="alice",
            timestamp=now,
            expires_at=now + timedelta(hours=2),
            read_once=True,
        )
    )
    db.session.commit()
    return app.test_client()


def secret():
    db.session.expire_all()
    return db.session.get(Data, LINK)


# Creating


def test_the_form_offers_read_once_off_by_default(app):
    body = app.test_client().get("/").get_data(as_text=True)

    [checkbox] = elements(body, "input", type="checkbox", name="read_once")
    assert "checked" not in checkbox


@pytest.mark.parametrize(
    ("form", "read_once"), [({"read_once": "1"}, True), ({}, False)]
)
def test_creating_stores_the_choice(app, form, read_once):
    app.test_client().post(
        "/", data={"data": "secret", **form}, headers={"Origin": "http://x"}
    )

    assert Data.query.one().read_once is read_once


def test_the_link_page_says_opening_the_link_is_safe_until_reveal(app):
    body = (
        app.test_client()
        .post("/", data={"data": "s", "read_once": "1"}, headers={"Origin": "http://x"})
        .get_data(as_text=True)
    )

    assert "burns after reading" in body
    assert "Reveal" in body


# Opening the link


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_opening_the_link_shows_a_notice_and_burns_nothing(client, method):
    # Link previewers, email scanners and prefetching open links on their own.
    response = client.open(f"/link/{LINK}", method=method)

    assert response.status_code == 200
    assert secret().data == TEXT
    assert secret().burnt_at is None


def test_the_notice_has_a_reveal_button_but_not_the_secret(client):
    body = client.get(f"/link/{LINK}").get_data(as_text=True)

    assert TEXT not in body
    assert "shown only once" in body
    [form] = elements(body, "form", method="POST", action=f"/reveal/{LINK}")
    assert "data-reveal" in form


# Revealing


def test_revealing_shows_the_secret_once_and_burns_it(client):
    response = client.post(f"/reveal/{LINK}", headers={"username": "bob"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert TEXT in body
    # The page warns before the reader leaves it.
    assert [a for a in elements(body, "article") if "data-shown-once" in a]
    assert "won't be shown again" in body
    assert elements(body, "button", **{"data-copy": "#secret"})
    burnt = secret()
    assert burnt.data == ""
    assert burnt.burnt_at is not None
    assert burnt.burnt_by == "bob"


def test_a_second_reveal_gets_the_receipt(client):
    client.post(f"/reveal/{LINK}")

    response = client.post(f"/reveal/{LINK}")

    assert response.status_code == 410
    assert TEXT not in response.get_data(as_text=True)
    assert "Read and burnt" in response.get_data(as_text=True)


def test_opening_the_link_after_revealing_shows_the_receipt(client):
    client.post(f"/reveal/{LINK}")

    response = client.get(f"/link/{LINK}")

    assert response.status_code == 410
    assert TEXT not in response.get_data(as_text=True)


def test_revealing_a_normal_secret_redirects_to_it(client):
    db.session.add(
        Data(
            sha_link="9" * 64,
            data="normal",
            creator="a",
            expires_at=datetime.now() + timedelta(hours=1),
        )
    )
    db.session.commit()

    response = client.post("/reveal/" + "9" * 64)

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/link/" + "9" * 64)
    assert db.session.get(Data, "9" * 64).burnt_at is None


def test_revealing_an_unknown_or_expired_link_returns_404(client):
    assert client.post("/reveal/" + "0" * 64).status_code == 404

    expired = secret()
    expired.expires_at = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    assert client.post(f"/reveal/{LINK}").status_code == 404
    assert secret().data == TEXT


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_opening_a_reveal_link_does_not_reveal(client, method):
    response = client.open(f"/reveal/{LINK}", method=method)

    assert response.status_code == 405
    assert secret().data == TEXT


def test_a_database_error_while_revealing_shows_no_secret(client, caplog):
    failing_commit = mock.patch.object(
        db.session, "commit", side_effect=SQLAlchemyError("disk I/O error")
    )
    with failing_commit:
        response = client.post(f"/reveal/{LINK}")

    assert response.status_code == 500
    assert TEXT not in response.get_data(as_text=True)
    assert "Error revealing a secret" in caplog.text
    assert secret().data == TEXT

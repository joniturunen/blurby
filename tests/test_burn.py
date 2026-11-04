"""Burn after reading (#26): the reader deletes the secret's text, and its link
then shows a read receipt until the secret would have expired."""

from datetime import datetime, timedelta
from unittest import mock

import pytest
from html_helpers import elements
from sqlalchemy.exc import SQLAlchemyError

from blurby.cleanup import delete_expired
from blurby.models import Data, db

LINK = "b" * 64


@pytest.fixture
def client(app):
    now = datetime.now()
    db.session.add(
        Data(
            sha_link=LINK,
            data="burn me",
            creator="alice",
            timestamp=now,
            expires_at=now + timedelta(hours=2),
        )
    )
    db.session.commit()
    return app.test_client()


def secret():
    db.session.expire_all()
    return db.session.get(Data, LINK)


def test_the_read_page_burns_with_a_post(client):
    body = client.get(f"/link/{LINK}").get_data(as_text=True)

    assert elements(body, "form", method="POST", action=f"/burn/{LINK}")
    # Burn replaces Delete on the read page; /delete still works for scripts.
    assert not elements(body, "form", action=f"/delete/{LINK}")


def test_burning_deletes_the_text_and_records_when(client):
    before = datetime.now()

    response = client.post(f"/burn/{LINK}")

    assert response.status_code == 200
    assert "Burnt" in response.get_data(as_text=True)
    burnt = secret()
    assert burnt.data == ""
    assert before <= burnt.burnt_at <= datetime.now()
    assert burnt.burnt_by is None


def test_burning_records_who_burnt_it(client):
    client.post(f"/burn/{LINK}", headers={"username": "bob"})

    assert secret().burnt_by == "bob"


def test_a_burnt_link_shows_a_receipt_with_410(client):
    client.post(f"/burn/{LINK}", headers={"username": "bob"})

    response = client.get(f"/link/{LINK}")

    body = response.get_data(as_text=True)
    assert response.status_code == 410
    assert "burn me" not in body
    assert "Read and burnt" in body
    assert "by bob" in body
    # The burn time, with the server's timezone.
    burnt_at = secret().burnt_at.astimezone()
    assert elements(body, "time", datetime=burnt_at.isoformat(timespec="minutes"))
    assert burnt_at.strftime("%Z") in body


def test_an_anonymous_reader_is_not_named(client):
    client.post(f"/burn/{LINK}")

    body = client.get(f"/link/{LINK}").get_data(as_text=True)

    assert "Read and burnt" in body
    assert "by anonymous" not in body


def test_burning_twice_keeps_the_first_time(client):
    client.post(f"/burn/{LINK}", headers={"username": "bob"})
    first = secret().burnt_at

    response = client.post(f"/burn/{LINK}", headers={"username": "carol"})

    assert response.status_code == 410
    assert secret().burnt_at == first
    assert secret().burnt_by == "bob"


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_opening_a_burn_link_does_not_burn(client, method):
    # Link previewers and scanners open links with GET or HEAD.
    response = client.open(f"/burn/{LINK}", method=method)

    assert response.status_code == 405
    assert secret().data == "burn me"


def test_burning_an_unknown_link_returns_404(client):
    assert client.post("/burn/" + "0" * 64).status_code == 404


def test_an_expired_receipt_is_gone(client):
    client.post(f"/burn/{LINK}")
    receipt = secret()
    receipt.expires_at = datetime.now() - timedelta(minutes=1)
    db.session.commit()

    assert client.get(f"/link/{LINK}").status_code == 404
    assert client.post(f"/burn/{LINK}").status_code == 404
    assert delete_expired() == 1
    assert secret() is None


def test_a_database_error_while_burning_shows_an_error_page(client, caplog):
    failing_commit = mock.patch.object(
        db.session, "commit", side_effect=SQLAlchemyError("disk I/O error")
    )
    with failing_commit:
        response = client.post(f"/burn/{LINK}")

    assert response.status_code == 500
    assert "There was a problem connecting the database" in response.get_data(
        as_text=True
    )
    assert "Error burning a secret" in caplog.text

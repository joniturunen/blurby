"""Only a POST deletes a secret; opening a delete link asks first."""

import pytest

from blurby.models import Data, db

LINK = "d" * 64


@pytest.fixture
def client(app):
    db.session.add(Data(sha_link=LINK, data="secret", creator="anonymous"))
    db.session.commit()
    return app.test_client()


def secret_exists():
    return db.session.get(Data, LINK) is not None


def test_opening_a_delete_link_asks_for_confirmation(client):
    response = client.get(f"/delete/{LINK}")

    assert response.status_code == 200
    assert f'<form method="POST" action="/delete/{LINK}">' in response.get_data(
        as_text=True
    )
    assert secret_exists()


def test_a_head_request_does_not_delete(client):
    # Link checkers and previewers often send HEAD, which Flask answers like GET.
    response = client.head(f"/delete/{LINK}")

    assert response.status_code == 200
    assert secret_exists()


def test_posting_deletes_the_secret(client):
    response = client.post(f"/delete/{LINK}")

    assert response.status_code == 200
    assert "succesfully deleted" in response.get_data(as_text=True)
    assert not secret_exists()


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_an_unknown_link_returns_404(client, method):
    response = client.open("/delete/" + "0" * 64, method=method)

    assert response.status_code == 404
    assert "Message was not found" in response.get_data(as_text=True)


def test_the_read_page_deletes_with_a_post(client):
    body = client.get(f"/link/{LINK}").get_data(as_text=True)

    assert f'<form method="POST" action="/delete/{LINK}">' in body

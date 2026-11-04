"""Pages with a secret or its link must not be kept, and their URLs must not leak."""

import pytest

from blurby.models import Data, db

LINK = "a" * 64


@pytest.fixture
def client(app):
    db.session.add(Data(sha_link=LINK, data="secret", creator="anonymous"))
    db.session.commit()
    return app.test_client()


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", f"/link/{LINK}"), ("POST", "/"), ("GET", "/"), ("GET", "/about")],
)
def test_pages_are_not_stored_and_send_no_referrer(client, method, path):
    response = client.open(path, method=method, data={"data": "new secret"})

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    # Not no-referrer: under it, browsers send `Origin: null` with the page's
    # own form posts, and the new secret's link became null/link/<link>.
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_static_files_keep_their_caching(client):
    response = client.get("/static/css/blurby.css")

    assert "no-store" not in response.headers.get("Cache-Control", "")
    assert response.headers["Referrer-Policy"] == "same-origin"
    response.close()

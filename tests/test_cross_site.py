"""Blurby refuses form posts that a page on another site sent (cross-site
request forgery): such a page could otherwise create, burn, reveal or delete
secrets in the name of whoever visits it."""

import logging
import re

import pytest

from blurby.models import Data, db

LINK = "f" * 64
OTHER_SITES = ["cross-site", "same-site"]
OWN_PAGES = ["same-origin", "none", None]  # None: no header (curl, scripts)


@pytest.fixture
def secret(app):
    db.session.add(Data(sha_link=LINK, data="the secret", creator="anonymous"))
    db.session.add(
        Data(sha_link="r" * 64, data="read once", creator="anonymous", read_once=True)
    )
    db.session.commit()


def post(app, path, fetch_site, **data):
    headers = {"Sec-Fetch-Site": fetch_site} if fetch_site else {}
    return app.test_client().post(path, data=data, headers=headers)


def unchanged():
    db.session.expire_all()
    secret = db.session.get(Data, LINK)
    read_once = db.session.get(Data, "r" * 64)
    return (
        db.session.query(Data).count() == 2
        and secret.data == "the secret"
        and secret.burnt_at is None
        and read_once.burnt_at is None
    )


@pytest.mark.parametrize("fetch_site", OTHER_SITES)
@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/", {"data": "planted"}),
        (f"/burn/{LINK}", {}),
        (f"/reveal/{'r' * 64}", {}),
        (f"/delete/{LINK}", {}),
        ("/find", {"sha_link": LINK}),
    ],
)
def test_a_post_from_another_site_is_refused(app, secret, fetch_site, path, data):
    response = post(app, path, fetch_site, **data)

    assert response.status_code == 403
    assert b"Request refused" in response.data
    assert b"the secret" not in response.data
    assert b"read once" not in response.data
    assert unchanged()


@pytest.mark.parametrize("fetch_site", OWN_PAGES)
def test_a_post_from_blurby_or_a_script_creates_the_secret(app, fetch_site):
    response = post(app, "/", fetch_site, data="welcome")

    assert response.status_code == 200
    assert db.session.query(Data).one().data == "welcome"


@pytest.mark.parametrize("fetch_site", OWN_PAGES)
def test_a_post_from_blurby_or_a_script_burns_the_secret(app, secret, fetch_site):
    response = post(app, f"/burn/{LINK}", fetch_site)

    assert response.status_code == 200
    assert db.session.get(Data, LINK).burnt_at is not None


def test_a_post_from_blurby_reveals_the_secret(app, secret):
    response = post(app, f"/reveal/{'r' * 64}", "same-origin")

    assert response.status_code == 200
    assert b"read once" in response.data


@pytest.mark.parametrize("fetch_site", OTHER_SITES)
def test_links_from_other_sites_still_open(app, secret, fetch_site):
    response = app.test_client().get(
        f"/link/{LINK}", headers={"Sec-Fetch-Site": fetch_site}
    )

    assert response.status_code == 200
    assert b"the secret" in response.data


def test_a_refused_post_is_logged_without_its_link(app, secret, caplog):
    with caplog.at_level(logging.INFO):
        post(app, f"/burn/{LINK}", "cross-site")

    assert "refused" in caplog.text
    assert not re.search(r"[0-9a-f]{64}", caplog.text)

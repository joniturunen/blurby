"""Copy buttons (#17): a button with data-copy copies the field it names."""

import pytest
from html_helpers import elements

from blurby.models import Data, db

LINK = "f" * 64


@pytest.fixture
def client(app):
    db.session.add(Data(sha_link=LINK, data="copy me", creator="anonymous"))
    db.session.commit()
    return app.test_client()


def copy_buttons(body):
    return {
        button["data-copy"]: button
        for button in elements(body, "button")
        if "data-copy" in button
    }


def test_the_read_page_has_a_button_that_copies_the_secret(client):
    body = client.get(f"/link/{LINK}").get_data(as_text=True)

    button = copy_buttons(body)["#secret"]
    assert button["type"] == "button"
    assert elements(body, "textarea", id="secret")


def test_the_link_page_has_a_button_that_copies_the_link(client):
    body = client.post(
        "/", data={"data": "new"}, headers={"Origin": "http://x"}
    ).get_data(as_text=True)

    assert "#sha_link" in copy_buttons(body)
    assert elements(body, "input", id="sha_link")


@pytest.mark.parametrize("path", [f"/link/{LINK}"])
def test_copy_buttons_stay_hidden_until_the_script_shows_them(client, path):
    # Without JavaScript, a copy button would do nothing.
    body = client.get(path).get_data(as_text=True)

    assert all("hidden" in button for button in copy_buttons(body).values())

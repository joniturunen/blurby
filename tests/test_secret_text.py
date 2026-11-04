"""A page shows the secret exactly as it was typed, including the line breaks
and spaces at its start and end."""

import pytest
from html_helpers import textarea_value

from blurby.models import Data, db

LINK = "e" * 64
TEXTS = [
    "one line",
    "\nstarts with a line break",
    "\n\nstarts with two line breaks",
    "ends with a line break\n",
    "  starts and ends with spaces  ",
    "\r\nstarts with a Windows line break\r\nand has another",
]


def browser_text(text):
    """The browser shows every line break as "\\n"."""
    return text.replace("\r\n", "\n")


@pytest.mark.parametrize("text", TEXTS)
def test_the_read_page_shows_the_secret_as_typed(app, text):
    db.session.add(Data(sha_link=LINK, data=text, creator="anonymous"))
    db.session.commit()

    body = app.test_client().get(f"/link/{LINK}").get_data(as_text=True)

    assert textarea_value(body, "secret") == browser_text(text)


@pytest.mark.parametrize("text", TEXTS)
def test_a_revealed_secret_is_shown_as_typed(app, text):
    db.session.add(Data(sha_link=LINK, data=text, creator="anonymous", read_once=True))
    db.session.commit()

    body = app.test_client().post(f"/reveal/{LINK}").get_data(as_text=True)

    assert textarea_value(body, "secret") == browser_text(text)

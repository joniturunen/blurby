"""Secrets and links are shown in read-only fields: a disabled field's text
can't be selected, so it can't be copied by hand."""

from html_helpers import elements

from blurby.models import Data, db

LINK = "c" * 64


def test_the_secret_is_read_only_not_disabled(app):
    db.session.add(Data(sha_link=LINK, data="select me", creator="anonymous"))
    db.session.commit()

    body = app.test_client().get(f"/link/{LINK}").get_data(as_text=True)

    [secret] = elements(body, "textarea", id="secret")
    assert "readonly" in secret
    assert "disabled" not in secret


def test_a_new_link_is_read_only_not_disabled(app):
    response = app.test_client().post(
        "/", data={"data": "secret"}, headers={"Origin": "http://x"}
    )

    [link] = elements(response.get_data(as_text=True), "input", id="sha_link")
    assert link["value"].startswith("http://x/link/")
    assert "readonly" in link
    assert "disabled" not in link

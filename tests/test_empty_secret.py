import pytest
from html_helpers import elements

from blurby.models import Data


def post_secret(app, secret):
    return app.test_client().post(
        "/", data={"data": secret}, headers={"Origin": "http://x"}
    )


@pytest.mark.parametrize(
    "secret",
    ["", "   ", "\r\n\r\n", "\t \n"],
    ids=["empty", "spaces", "line breaks", "mixed"],
)
def test_an_empty_secret_is_rejected_with_400(app, secret):
    response = post_secret(app, secret)

    assert response.status_code == 400
    assert "Empty secret" in response.get_data(as_text=True)
    assert Data.query.count() == 0


def test_a_secret_keeps_its_surrounding_whitespace(app):
    response = post_secret(app, "  indented\n")

    assert response.status_code == 200
    assert Data.query.one().data == "  indented\n"


def test_the_form_requires_a_secret(app):
    body = app.test_client().get("/").get_data(as_text=True)

    [textarea] = elements(body, "textarea", name="data")
    assert "required" in textarea

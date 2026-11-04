"""Light and dark mode: pages follow the system's setting until the reader
chooses one with the switch in the menu, and a saved choice is applied before
the page is drawn. The switching itself is in theme.js and blurby.js."""

import pytest
from html_helpers import elements

PAGES = ["/", "/find", "/about", "/link/" + "0" * 64]


def page(app, path="/"):
    return app.test_client().get(path).get_data(as_text=True)


def test_the_server_leaves_the_mode_to_the_browser(app):
    body = page(app)

    # Without data-theme, Pico CSS follows the system's setting.
    [html] = elements(body, "html")
    assert "data-theme" not in html
    assert elements(body, "meta", name="color-scheme", content="light dark")


def test_a_saved_choice_is_applied_before_the_page_is_drawn(app):
    head = page(app).split("</head>")[0]

    # A deferred or async script would run after the page is first drawn.
    [script] = elements(head, "script", src="/static/js/theme.js")
    assert "defer" not in script
    assert "async" not in script
    assert head.index("js/theme.js") < head.index("pico.violet.min.css")


@pytest.mark.parametrize("path", PAGES)
def test_every_page_has_the_switch(app, path):
    body = page(app, path)

    [switch] = [b for b in elements(body, "button") if "data-theme-switch" in b]
    # It does nothing without JavaScript, so it's hidden until blurby.js runs.
    assert "hidden" in switch
    # A toggle button; type=button so that it could never submit a form.
    assert switch["type"] == "button"
    assert switch["aria-label"] == "Dark mode"
    assert switch["aria-pressed"] == "false"

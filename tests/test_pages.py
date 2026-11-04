"""Every page renders on the shared layout, and everything it loads is served."""

import re
from pathlib import Path

import pytest
from html_helpers import elements

import blurby
from blurby.models import Data, db

LINK = "e" * 64


@pytest.fixture
def client(app):
    db.session.add(Data(sha_link=LINK, data="secret", creator="anonymous"))
    db.session.commit()
    return app.test_client()


PAGES = [
    ("GET", "/"),
    ("POST", "/"),
    ("GET", "/find"),
    ("GET", "/about"),
    ("GET", f"/link/{LINK}"),
    ("GET", f"/delete/{LINK}"),
    ("GET", "/link/" + "0" * 64),
]


def assets(body):
    """The local files a page loads: stylesheets, icons and scripts."""
    links = [link["href"] for link in elements(body, "link")]
    scripts = [script["src"] for script in elements(body, "script")]
    return links + scripts


@pytest.mark.parametrize(("method", "path"), PAGES)
def test_every_file_a_page_loads_is_served(client, method, path):
    body = client.open(path, method=method, data={"data": "new"}).get_data(as_text=True)

    loaded = assets(body)
    assert any(href.endswith("/pico.violet.min.css") for href in loaded)
    for href in loaded:
        response = client.get(href)
        assert response.status_code == 200, href
        response.close()


TEMPLATES = sorted(
    (Path(blurby.__file__).parent / "templates").glob("*.html"), key=lambda p: p.name
)
# What the Content-Security-Policy blocks: inline scripts and event handlers,
# and inline styles.
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
EVENT_HANDLER = re.compile(r"<[^>]*\son[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE = re.compile(r"<style\b|<[^>]*\sstyle\s*=", re.IGNORECASE)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_templates_have_no_inline_scripts_or_styles(path):
    html = path.read_text(encoding="utf-8")

    assert not INLINE_SCRIPT.search(html)
    assert not EVENT_HANDLER.search(html)
    assert not INLINE_STYLE.search(html)


@pytest.mark.parametrize(("method", "path"), PAGES)
def test_every_page_has_a_title_and_the_menu(client, method, path):
    body = client.open(path, method=method, data={"data": "new"}).get_data(as_text=True)

    assert "· Blurby</title>" in body
    for href in ("/", "/find", "/about"):
        assert elements(body, "a", href=href)

"""Pages must not load anything from other sites: each request would tell that
site the visitor's IP address, and break Blurby where the internet is out of reach."""

import re
from pathlib import Path

import pytest

import blurby

PACKAGE = Path(blurby.__file__).parent
STYLESHEETS = sorted(PACKAGE.glob("static/**/*.css"))
TEMPLATES = sorted(PACKAGE.glob("templates/*.html"))

# A url(...) or @import in CSS, or a src/href on a tag that loads a resource,
# pointing at another host. Plain links (<a href>) are fine.
CSS_REMOTE = re.compile(r"""(?:@import\s+(?:url\()?|url\()\s*["']?(?:https?:)?//""")
HTML_REMOTE = re.compile(
    r"""<(?:script|link|img|iframe|source|video|audio)\b[^>]*\b(?:src|href)\s*=\s*["']?(?:https?:)?//""",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", STYLESHEETS, ids=lambda p: p.name)
def test_stylesheets_load_nothing_from_other_sites(path):
    assert not CSS_REMOTE.search(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_templates_load_nothing_from_other_sites(path):
    assert not HTML_REMOTE.search(path.read_text(encoding="utf-8"))

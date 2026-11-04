"""Find elements in a rendered page, for checks that don't depend on its exact markup."""

from html.parser import HTMLParser


class _Collector(HTMLParser):
    def __init__(self, tag):
        super().__init__(convert_charrefs=True)
        self.tag = tag
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag == self.tag:
            self.found.append(dict(attrs))

    handle_startendtag = handle_starttag


def elements(body, tag, **attrs):
    """Return the attributes of each <tag> in `body` that has all of `attrs`.

    A boolean attribute such as `readonly` maps to None: test it with `in`.
    """
    collector = _Collector(tag)
    collector.feed(body)
    collector.close()
    return [
        found
        for found in collector.found
        if all(found.get(name) == value for name, value in attrs.items())
    ]

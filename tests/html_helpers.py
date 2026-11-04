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


class _TextareaReader(HTMLParser):
    def __init__(self, id):
        super().__init__(convert_charrefs=True)
        self.id = id
        self.inside = False
        self.text = None

    def handle_starttag(self, tag, attrs):
        if tag == "textarea" and dict(attrs).get("id") == self.id:
            self.inside = True
            self.text = ""

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.text += data


def textarea_value(body, id):
    """Return the text a browser shows in the <textarea id=...> of `body`.

    Like a browser's HTML parser, it turns line breaks into "\\n" and drops a
    line break right after the start tag. Python's parser does neither.
    """
    reader = _TextareaReader(id)
    reader.feed(body)
    reader.close()
    text = reader.text.replace("\r\n", "\n").replace("\r", "\n")
    return text.removeprefix("\n")

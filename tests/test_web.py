"""Contracts for the static recorder UI, without starting a browser or server."""

from html.parser import HTMLParser
from urllib.parse import unquote_to_bytes
from xml.etree import ElementTree

from blackbox.cli import WEB


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.links.append(dict(attrs))


def test_favicon_is_a_self_contained_svg():
    page = Links()
    page.feed((WEB / "index.html").read_text())
    icons = [link for link in page.links if link.get("rel") == "icon"]
    assert len(icons) == 1
    icon = icons[0]
    assert icon["type"] == "image/svg+xml"
    kind, svg = icon["href"].split(",", 1)
    assert kind == "data:image/svg+xml"
    root = ElementTree.fromstring(unquote_to_bytes(svg))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 28 28"
    assert len(root) > 0
    # The icon needs no resource requests, including when demo data is absent.
    assert all("href" not in attr for el in root.iter() for attr in el.attrib)

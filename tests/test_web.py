"""Contracts for the static recorder UI, without starting a browser or server."""

from html.parser import HTMLParser
import json
import re
import subprocess
from urllib.parse import unquote_to_bytes
from xml.etree import ElementTree

import pytest

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


@pytest.mark.parametrize("run", sorted((WEB / "data").glob("*/explain.json")), ids=lambda p: p.parent.name)
def test_reel_initial_timestamp(run):
    # Evaluate the timestamp expression actually used by render(), with each
    # saved explanation. No browser, server, or substitute run data is needed.
    script = (WEB / "index.html").read_text().split("<script>", 1)[1].split("</script>", 1)[0]
    render = script.split("function render() {", 1)[1].split("function drawPencil()", 1)[0]
    initial = re.search(r"setTime\((.+), false\);", render).group(1)
    explanation = json.loads(run.read_text())
    result = subprocess.run(
        ["node", "-e", """
const [expression, fm] = JSON.parse(process.argv[1]);
process.stdout.write(JSON.stringify(eval(expression)));
""", json.dumps([initial, explanation["failure_moment"]])],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == 0

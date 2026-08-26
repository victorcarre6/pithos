"""Smoke checks for the localhost-only visualizer launcher."""

import sys
import threading
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from start_visualizer import create_server


class ElementCollector(HTMLParser):
    """Collect element identifiers and script sources from the static page."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"])


def test_server_binds_to_localhost_and_serves_the_app():
    server = create_server()
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}", timeout=2) as response:
            page = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert host == "127.0.0.1"
    assert "Pithos Visualizer" in page


def test_static_app_contains_controls_and_no_external_endpoint():
    web_root = PROJECT_ROOT / "web"
    page = (web_root / "index.html").read_text(encoding="utf-8")
    application = (web_root / "app.mjs").read_text(encoding="utf-8")
    parser = ElementCollector()
    parser.feed(page)

    assert {"start", "device", "theme", "fullscreen", "status"} <= parser.ids
    assert parser.scripts == ["./app.mjs"]
    assert "https://" not in page + application
    assert "http://" not in page + application

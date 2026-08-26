#!/usr/bin/env python3
"""Serve the visualizer locally and open it in the default browser."""

import argparse
import functools
import http.server
import threading
import webbrowser
from pathlib import Path


WEB_ROOT = Path(__file__).parent / "web"


def create_server(port=0):
    """Create a localhost-only static server for the bundled web app."""

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=WEB_ROOT)

    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def main():
    """Start the local server and keep it alive until interrupted."""

    parser = argparse.ArgumentParser(description="Launch the local Pithos audio visualizer")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    arguments = parser.parse_args()

    server = create_server(arguments.port)
    url = f"http://127.0.0.1:{server.server_port}"
    if not arguments.no_browser:
        threading.Timer(0.2, webbrowser.open, args=[url]).start()

    print(f"Pithos visualizer: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

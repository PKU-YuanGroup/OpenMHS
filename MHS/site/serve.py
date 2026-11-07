#!/usr/bin/env python3
"""Preview the generated OpenMHS site locally.

    python3 MHS/site/serve.py [port] [--site DIR]

Serves ``MHS/site/_site`` (or ``DIR``) on 127.0.0.1 only.
"""

from __future__ import annotations

import functools
import http.server
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent / "_site"


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".jsonl": "application/x-ndjson; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".svg": "image/svg+xml",
        ".xml": "application/xml; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".zip": "application/zip",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):  # noqa: D102 - quiet by default
        if "--verbose" in sys.argv:
            super().log_message(fmt, *args)


def main() -> int:
    port = 8080
    site = SITE
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        if arg.isdigit():
            port = int(arg)
        elif arg == "--site" and index + 1 < len(args):
            site = Path(args[index + 1]).expanduser().resolve()
        elif arg.startswith("--site="):
            site = Path(arg.split("=", 1)[1]).expanduser().resolve()
    if not site.is_dir():
        print("build the site first: python3 MHS/site/build.py [--out DIR]", file=sys.stderr)
        return 2
    handler = functools.partial(Handler, directory=str(site))
    # Threading matters: a browser opens several parallel connections for the
    # CSS, scripts, fonts and JSON data. A single-threaded server can deadlock
    # on a kept-alive socket and appears to hang after the first asset.
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"OpenMHS site preview of {site}: http://127.0.0.1:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

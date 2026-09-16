#!/usr/bin/env python3
"""Preview server for the GENIUS site.

    python3 serve.py            # http://localhost:4173/
    python3 serve.py 8080       # custom port

Serves the `site/` folder as the web root, exactly the folder you deploy, so
what you see locally is what ships. See DEPLOY.md.
"""

import functools
import http.server
import os
import socketserver
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4173


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # Send the same security headers production uses (from site/_headers), so a
    # CSP violation shows up in the browser console locally, not after deploy.
    _HEADERS = None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        if Handler._HEADERS is None:
            Handler._HEADERS = []
            try:
                for line in open(os.path.join(ROOT, "_headers")):
                    if line.startswith("  ") and ":" in line:
                        k, v = line.strip().split(":", 1)
                        Handler._HEADERS.append((k.strip(), v.strip()))
            except OSError:
                pass
        for k, v in Handler._HEADERS:
            self.send_header(k, v)
        super().end_headers()


if __name__ == "__main__":
    if not os.path.exists(os.path.join(ROOT, "console", "data.js")):
        print("note: site/console/data.js missing, run `python3 lab/run_demo.py` first\n")
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=ROOT)
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"GENIUS · serving {ROOT}")
        print(f"  site    → http://localhost:{PORT}/")
        print(f"  console → http://localhost:{PORT}/console/")
        httpd.serve_forever()

#!/usr/bin/env python3
"""
Sarvam Translator — local demo server.

Why this exists:
  Browsers frequently block direct calls from a page to https://api.sarvam.ai
  (CORS). This tiny server serves the translator UI AND proxies /api/translate
  to Sarvam, so the demo always works. The API key is read from the request
  header sent by the page, or from the SARVAM_API_KEY environment variable.

Run:
    export SARVAM_API_KEY="sk_..."      # optional; you can also paste it in the UI
    python server.py
    # then open http://localhost:8000

No third-party packages required (standard library only).
"""
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SARVAM_URL = "https://api.sarvam.ai/translate"
PORT = int(os.environ.get("PORT", "8000"))


class Handler(BaseHTTPRequestHandler):
    server_version = "SarvamTranslator/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, api-subscription-key")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/translator.html"):
            html_path = os.path.join(HERE, "translator.html")
            if not os.path.exists(html_path):
                self._send(500, "translator.html not found next to server.py", "text/plain")
                return
            with open(html_path, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._send(200, json.dumps({"ok": True}))
            return
        self._send(404, json.dumps({"error": {"message": "Not found", "code": "not_found"}}))

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/translate":
            self._send(404, json.dumps({"error": {"message": "Not found", "code": "not_found"}}))
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"

        key = (self.headers.get("api-subscription-key")
               or os.environ.get("SARVAM_API_KEY", "")).strip()
        if not key:
            self._send(400, json.dumps({"error": {
                "message": "No API key. Paste one in the UI or set SARVAM_API_KEY.",
                "code": "missing_key"}}))
            return

        req = urllib.request.Request(
            SARVAM_URL,
            data=raw,
            headers={"Content-Type": "application/json", "api-subscription-key": key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._send(resp.status, resp.read())
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read() or json.dumps({"error": {"message": str(e)}}))
        except urllib.error.URLError as e:
            self._send(502, json.dumps({"error": {
                "message": "Could not reach Sarvam API: %s" % e.reason,
                "code": "upstream_unreachable"}}))
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": {"message": str(e), "code": "server_error"}}))

    def log_message(self, fmt, *args):
        sys.stderr.write("[server] %s\n" % (fmt % args))


def main():
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("Sarvam Translator running at  http://localhost:%d" % PORT)
    print("Open that URL, pick 'Local proxy' in the top-right dropdown, then translate.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()

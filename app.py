"""Local JSON API and demo server. Run with python app.py."""

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from data import CITIES, LANGUAGES, SHIFTS, SKILLS, generate
from learning import train
from matching import WEIGHTS, recommend

NURSES, REQUESTS = generate()
RANKING_WEIGHTS = {"default": WEIGHTS, "learned": train(NURSES)}
REQUEST_BY_ID = {request["id"]: request for request in REQUESTS}
WEB = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=HTTPStatus.OK):
        self.send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def send_matches(self, request):
        modes = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get("ranking", ["default"])
        if len(modes) != 1 or modes[0] not in RANKING_WEIGHTS:
            self.send_json({"error": "ranking must be default or learned."}, HTTPStatus.BAD_REQUEST)
            return
        mode = modes[0]
        weights = RANKING_WEIGHTS[mode]
        result = recommend(request, NURSES, weights=weights)
        self.send_json({**result, "ranking": mode, "weights": weights})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ASSETS:
            filename, content_type = ASSETS[path]
            self.send_bytes(HTTPStatus.OK, (WEB / filename).read_bytes(), content_type)
        elif path == "/api/requests":
            self.send_json({"requests": REQUESTS, "nurse_count": len(NURSES)})
        elif path.startswith("/api/matches/"):
            request = REQUEST_BY_ID.get(path.removeprefix("/api/matches/"))
            if request is None:
                self.send_json({"error": "Unknown care request ID."}, HTTPStatus.NOT_FOUND)
                return
            self.send_matches(request)
        else:
            self.send_json({"error": "Route not found."}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/matches":
            self.send_json({"error": "Route not found."}, HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json({"error": "Send application/json."}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                self.close_connection = True
                self.send_json({"error": "Request body exceeds 4 KB."}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            if length < 1:
                raise ValueError("Request body is required.")
            payload = json.loads(self.rfile.read(length))
            request = validate(payload)
        except (ValueError, UnicodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_matches(request)


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object.")
    fields = {"city": CITIES, "skill": SKILLS, "language": LANGUAGES, "shift": SHIFTS}
    for name, options in fields.items():
        value = payload.get(name)
        if not isinstance(value, str) or value not in options:
            raise ValueError(f"{name} must be one of: {', '.join(options)}.")
    city_lat, city_lon = CITIES[payload["city"]]
    for name, center in (("lat", city_lat), ("lon", city_lon)):
        value = payload.get(name)
        if type(value) not in (int, float) or not center - .2 <= value <= center + .2:
            raise ValueError(f"{name} must be a numeric coordinate within 0.2 degrees of the city center.")
    previous = payload.get("previous_nurse_id")
    if previous is not None and previous not in [nurse["id"] for nurse in NURSES]:
        raise ValueError("previous_nurse_id must be a known nurse ID or null.")
    return {**{name: payload[name] for name in fields}, "lat": payload["lat"],
            "lon": payload["lon"], "previous_nurse_id": previous}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8015"))
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Care matching demo at http://127.0.0.1:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

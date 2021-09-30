import base64
import urllib
import hashlib
import datetime
import json
import os
import requests
from functools import wraps
from urllib.parse import urlparse
from pathlib import Path

from flask import abort, Flask, jsonify, Response, send_from_directory, request

from ip_television import IPTelevision
import m3u


M3U_URL = os.environ.get("M3U_URL")
CATEGORIES = os.environ.get("CATEGORIES")
PASSWORD = os.environ.get("PASSWORD")


def urlretrieve(url, output_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
    }
    r = requests.get(url, allow_redirects=True, headers=headers)
    open(output_path, "wb").write(r.content)


def authorize(f):
    @wraps(f)
    def decorated_function(*args, **kws):
        password = request.cookies.get("password")
        if PASSWORD and password != PASSWORD:
            abort(404)
        return f(*args, **kws)

    return decorated_function


def root_url(request):
    parsed = urlparse(request.base_url)
    protocol = request.headers.get("X-Forwarded-Proto", parsed.scheme)
    return f"{protocol}://{parsed.netloc}"


if __name__ == "__main__":
    print("Parsing M3U...")
    tv_channels = m3u.parse_m3u(M3U_URL)

    print("Starting server...")
    tv = IPTelevision(tv_channels)

    app = Flask(__name__, template_folder=".")
    app.use_x_sendfile = True

    @app.after_request
    def after_request(resp):
        x_sendfile = resp.headers.get("X-Sendfile")
        if x_sendfile:
            resp.headers["X-Accel-Redirect"] = "/nginx/" + x_sendfile
            del resp.headers["X-Sendfile"]
        resp.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
        return resp

    @app.route("/")
    def frontend():
        password = request.cookies.get("password")
        if not PASSWORD or password == PASSWORD:
            return send_from_directory(
                "/app/", "index.html", last_modified=datetime.datetime.now()
            )
        return send_from_directory(
            "/app/", "login.html", last_modified=datetime.datetime.now()
        )

    @app.route("/api", methods=["POST"])
    def login():
        password = request.form.get("password")
        if not password:
            abort(404)
        response = jsonify()
        if PASSWORD and password == PASSWORD:
            response.set_cookie("password", password)
        return response

    @app.route("/api/set_channel/", methods=["POST"])
    @authorize
    def set_channel():
        channel_id = request.json.get("channel_id")
        tv.change_channel(channel_id)
        return ""

    @app.route("/channels.json")
    def channels():
        cmap = json.loads(json.dumps(tv_channels))
        cmap.sort(key=lambda x: len(x.get("channels", [])), reverse=True)
        if CATEGORIES:
            cmap = [
                g
                for g in cmap
                if g.get("name").lower() in CATEGORIES.lower().split(",")
            ]
        for group in cmap:
            for channel in group["channels"]:
                if channel["logo"]:
                    hashed_logo = base64.b64encode(str.encode(channel["logo"])).decode(
                        "utf-8"
                    )
                    channel["logo"] = "/logo/" + hashed_logo + ".png"
                else:
                    channel["logo"] = root_url(request) + "/static/icon.png"
        return jsonify(cmap)

    @app.route("/status")
    def status():
        return dict(channel_id=tv.channel_id, loading=tv.loading)

    @app.route("/stream.m3u8")
    def channel():
        m3u8_source = f"/tmp/{tv.channel_id}.m3u8"
        if not os.path.isfile(m3u8_source):
            abort(404)

        txt = Path(m3u8_source).read_text()
        lines = txt.split()
        for i, line in enumerate(lines):
            if line.endswith(".ts"):
                lines[i] = root_url(request) + f"/hls/{line}"
        txt = "\n".join(lines)
        return Response(txt, content_type="application/vnd.apple.mpegURL")

    @app.route("/logo/<hashed_url>.png")
    def logo(hashed_url):
        url = base64.b64decode(hashed_url.encode("ascii")).decode("ascii")
        output_path = f"/tmp/logos/{hashed_url}.png"
        if not os.path.exists(output_path):
            os.makedirs("/tmp/logos/", exist_ok=True)
            try:
                urlretrieve(url, output_path)
            except Exception as e:
                print(e, flush=True)
                return send_from_directory("/app/static/", "icon.png")
        return send_from_directory("/tmp/logos/", hashed_url + ".png")

    app.run(host="0.0.0.0", port=5001, threaded=True)

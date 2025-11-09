from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import os, shutil

from providers import PROVIDERS, detect_provider

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
executor = ThreadPoolExecutor(max_workers=8)


def is_valid_mod_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        if not p.netloc:
            return False
        nl = p.netloc.lower()
        return "curseforge.com" in nl or "modrinth.com" in nl
    except Exception:
        return False


def fetch_mod_info(url: str) -> dict:
    provider_name = detect_provider(url)
    if not provider_name:
        return {"url": url, "error": "Unknown provider for URL"}

    get_mod_data = PROVIDERS.get(provider_name)
    if get_mod_data is None:
        return {"url": url, "error": f"No implementation for provider '{provider_name}'"}

    try:
        mod_info = get_mod_data(url)
        return {
            "name": mod_info.get("name"),
            "provider": mod_info.get("provider"),
            "id": mod_info.get("id"),
            "slug": mod_info.get("slug"),
            "versions": mod_info.get("versions", []),
            "url": mod_info.get("url") or url,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    valid_urls = []
    invalid = []
    for u in urls:
        if is_valid_mod_url(u):
            valid_urls.append(u)
        else:
            invalid.append(u)

    results = []
    for u in invalid:
        results.append({"url": u, "error": "Invalid or unsupported URL"})

    futures = {executor.submit(fetch_mod_info, u): u for u in valid_urls}
    for future in as_completed(futures):
        res = future.result()
        results.append(res)

    return jsonify(results)


@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    cache_root = os.path.join(os.path.dirname(__file__), "cache")
    try:
        if os.path.exists(cache_root):
            shutil.rmtree(cache_root)
            os.makedirs(cache_root, exist_ok=True)
        return jsonify({"status": "ok", "message": "Cache cleared."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, threaded=True)
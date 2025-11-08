from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from collections import Counter
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
    """
    Wrapper that calls the provider safely and returns a dict result.
    Always returns a dict (either data or error) so callers don't get exceptions.
    """
    provider_name = detect_provider(url)
    if not provider_name:
        return {"url": url, "error": "Unknown provider for URL"}

    get_mod_data = PROVIDERS.get(provider_name)
    if get_mod_data is None:
        return {"url": url, "error": f"No implementation for provider '{provider_name}'"}

    try:
        mod_info = get_mod_data(url)
        # include provider key and keep structure stable
        return {
            "name": mod_info.get("name"),
            "provider": mod_info.get("provider"),
            "mod_id": mod_info.get("mod_id"),
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

    # Validate & filter
    valid_urls = []
    invalid = []
    for u in urls:
        if is_valid_mod_url(u):
            valid_urls.append(u)
        else:
            invalid.append(u)

    results = []
    # Immediately add invalid URLs to results so frontend can see them
    for u in invalid:
        results.append({"url": u, "error": "Invalid or unsupported URL"})

    # Parallel fetch for valid ones
    futures = {executor.submit(fetch_mod_info, u): u for u in valid_urls}
    for future in as_completed(futures):
        res = future.result()
        results.append(res)

    return jsonify(results)

if __name__ == "__main__":
    # In production run via gunicorn/uvicorn; debug only when developing
    app.run(host="0.0.0.0", debug=True, threaded=True)

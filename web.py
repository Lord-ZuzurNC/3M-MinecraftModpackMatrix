from flask import Flask, request, jsonify, send_from_directory, render_template, render_template_string
from flask_cors import CORS
import os
from providers import PROVIDERS, detect_provider
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

executor = ThreadPoolExecutor(max_workers=8)  # tune depending on CPU/network

app = Flask(__name__, static_folder="static")
CORS(app)

def is_valid_mod_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
        if not any(domain in parsed.netloc for domain in ("curseforge.com", "modrinth.com")):
            return False
        return True
    except Exception:
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    # ✅ Validate URLs early
    valid_urls = []
    for u in urls:
        if is_valid_mod_url(u):
            valid_urls.append(u)
        else:
            print(f"[WARN] Skipping invalid URL: {u}")

    results = []
    futures = {executor.submit(fetch_mod_info, u): u for u in valid_urls}

    for future in as_completed(futures):
        url = futures[future]
        try:
            mod_info = future.result()
            results.append(mod_info)
        except Exception as e:
            results.append({"url": url, "error": str(e)})

    return jsonify(results)

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    import shutil
    try:
        for folder in os.listdir("cache"):
            path = os.path.join("cache", folder)
            if os.path.isdir(path):
                shutil.rmtree(path)
        return "All cache cleared.", 200
    except Exception as e:
        return f"Failed: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", threaded=True, debug=True)

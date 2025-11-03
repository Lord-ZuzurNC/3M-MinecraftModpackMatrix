import os
import time
import json
import requests
from datetime import datetime, timedelta
from dateutil.parser import parse
from re import sub
from providers import cache_path, safe_name

API_BASE = "https://api.curseforge.com/v1"
GAME_ID = 432  # Minecraft
CACHE_DIR = os.path.join("cache", "curseforge")
CACHE_TTL = timedelta(hours=24)

# Load CurseForge API key from .env
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("CF_API_KEY")

DEBUG = os.getenv("DEBUG")
if not API_KEY:
    raise EnvironmentError("Missing CF_API_KEY in environment (.env not loaded)")

def debug(msg):
    if os.getenv("DEBUG", "false").lower() == "true":
        print("[DEBUG] ", msg)

HEADERS = {
    "Accept": "application/json",
    "x-api-key": API_KEY,
}

# ---------- Helper: Safe request with retries ----------
def safe_request(url, params=None, retries=5, delay=1):
    for attempt in range(1, retries + 1):
        try:
            timeout = int(os.getenv("REQUEST_TIMEOUT", 10))
            response = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            debug(f"Request failed: {e}. Retrying ({attempt}/{retries})...")
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

# ---------- Helper: Cached fetch ----------
def cached_fetch(provider, mod_id, slug, page, url, params):
    cache_file = cache_path(provider, slug, mod_id, page)

    if os.path.exists(cache_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - mtime < CACHE_TTL:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    response = safe_request(url, params=params)
    data = response.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data

# ---------- Main provider function ----------
def get_mod_data(url: str):
    debug(f"Extracting mod slug from URL: {url}")
    slug = url.rstrip("/").split("/")[-1]

    # Step 1: Resolve mod slug → mod ID
    search_url = f"{API_BASE}/mods/search"
    params = {"gameId": GAME_ID, "slug": slug}
    debug(f"Searching for slug '{slug}' via {search_url} params={params}")
    resp = safe_request(search_url, params)
    mods = resp.json().get("data", [])
    if not mods:
        raise ValueError(f"Mod '{slug}' not found on CurseForge.")

    # Pick the most likely one (most recent / most downloaded)
    for m in mods:
        debug(f"Candidate mod: {m['name']} (ID={m['id']}, downloads={m['downloadCount']})")
    best_mod = max(mods, key=lambda m: (
        parse(m.get("dateReleased", "1970-01-01")),
        m.get("downloadCount", 0)
    ))
    mod_id = best_mod["id"]
    mod_name = best_mod["name"]
    debug(f"Found mod ID: {mod_id} for slug: {slug} ({mod_name}, {best_mod['downloadCount']} downloads)")

    # Step 2: Fetch all file pages (with cache)
    all_files = []
    page = 0
    page_size = 50
    consecutive_misses = 0  # stop when N empty pages in a row

    while True:
        files_url = f"{API_BASE}/mods/{mod_id}/files"
        params = {"index": page * page_size, "pageSize": page_size, "sortOrder": "asc"}

        debug(f"Fetching page {page} for mod {mod_id} (index={params['index']})")
        try:
            data = cached_fetch("curseforge", mod_id, slug, page, files_url, params)
        except Exception as e:
            debug(f"[WARN] Failed to fetch page {page}: {e}")
            consecutive_misses += 1
            if consecutive_misses >= 3:
                break
            page += 1
            continue

        files = data.get("data", [])
        if not files:
            debug(f"No files in page {page}, stopping.")
            break

        all_files.extend(files)

        if len(files) < page_size:
            debug(f"Last page reached at {page}.")
            break
        page += 1
        time.sleep(0.3)

    debug(f"Fetched {len(all_files)} files total for mod {mod_name}")

    # Step 3: Extract Minecraft version ↔ mod loader pairs
    version_loader_pairs = set()

    for f in all_files:
        game_versions = [v for v in f.get("gameVersions", []) if v.startswith("1.")]
        lower_versions = [v.lower() for v in f.get("gameVersions", [])]
        file_name = f.get("fileName", "").lower()

        # --- Detect all possible loaders ---
        detected_loaders = set()

        # Direct detection from gameVersions list
        for token in lower_versions:
            if "neoforge" in token or "neo-forge" in token:
                detected_loaders.add("NeoForge")
            elif "fabric" in token and not "fabrication" in token:
                detected_loaders.add("Fabric")
            elif "forge" in token:
                detected_loaders.add("Forge")
            elif "quilt" in token:
                detected_loaders.add("Quilt")

        # Filename-based hints (if still empty)
        if not detected_loaders:
            if "neoforge" in file_name or "neo-forge" in file_name:
                detected_loaders.add("NeoForge")
            elif "fabric" in file_name and not "fabrication" in file_name:
                detected_loaders.add("Fabric")
            elif "forge" in file_name:
                detected_loaders.add("Forge")
            elif "quilt" in file_name:
                detected_loaders.add("Quilt")

        # Default fallback
        if not detected_loaders:
            detected_loaders.add("Unknown")

        # --- Debug: detect multi-loader combinations ---
        if len(detected_loaders) > 1 and game_versions:
            debug(f"Multi-loader file detected: "
                  f"{game_versions} → {', '.join(sorted(detected_loaders))}")

        # --- Add all version/loader combinations ---
        for v in game_versions:
            for loader in detected_loaders:
                version_loader_pairs.add((v, loader))

    # Step 4: Return structured data
    sorted_pairs = sorted(version_loader_pairs, key=lambda x: (x[0], x[1]))

    return {
        "provider": "curseforge",
        "mod_id": mod_id,
        "name": mod_name + (" [c]" if cached else ""),
        "url": url,
        "versions": sorted_pairs
    }
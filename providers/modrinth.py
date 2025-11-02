import os
import time
import json
import requests
from datetime import datetime, timedelta

API_BASE = "https://api.modrinth.com/v2"
CACHE_DIR = os.path.join("cache", "modrinth")
CACHE_TTL = timedelta(hours=24)

os.makedirs(CACHE_DIR, exist_ok=True)

# ---------- Helper: Safe request with retries ----------
def safe_request(url, retries=5, delay=1):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"[DEBUG] Request failed: {e}. Retrying ({attempt}/{retries})...")
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

# ---------- Helper: Cached fetch ----------
def cached_fetch(slug, mod_id, name, url):
    """
    Fetch and cache CurseForge API page data.
    """
    mod_cache_dir = os.path.join(CACHE_DIR, mod_id)
    os.makedirs(mod_cache_dir, exist_ok=True)
    cache_path = os.path.join(mod_cache_dir, "versions.json")

    # Check for valid cache
    if os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - mtime < CACHE_TTL:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

    # Fetch and cache new data
    data = safe_request(url).json()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data

# ---------- Main provider function ----------
def get_mod_data(url: str):
    slug = url.rstrip("/").split("/")[-1]
    print(f"[DEBUG] Extracting Modrinth slug: {slug}")

    # Step 1: Resolve mod slug → mod ID
    project_url = f"{API_BASE}/project/{slug}"
    proj_data = safe_request(project_url).json()
    mod_name = proj_data.get("title", slug)
    mod_id = proj_data.get("id")

    # Step 2: Fetch all file pages (with cache)
    versions_url = f"{API_BASE}/project/{slug}/version"
    data = cached_fetch(slug, mod_name, versions_url, url)

    # Step 3: Extract Minecraft version ↔ mod loader pairs
    version_loader_pairs = set()
    for v in data:
        game_versions = v.get("game_versions", [])
        loaders = v.get("loaders", [])
        for gv in game_versions:
            for loader in loaders:
                if gv.startswith("1."):
                    version_loader_pairs.add((gv, loader.capitalize()))


    # Step 4: Return structured data
    sorted_pairs = sorted(version_loader_pairs, key=lambda x: (x[0], x[1]))

    print(f"[DEBUG] Fetched {len(sorted_pairs)} unique versions for {mod_name}")

    return {
        "provider": "modrinth",
        "mod_id": mod_id,
        "name": mod_name,
        "versions": sorted_pairs
    }

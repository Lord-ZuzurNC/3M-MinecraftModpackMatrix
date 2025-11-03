import os
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
from re import sub
from providers import cache_path, safe_name

load_dotenv()

API_BASE = "https://api.modrinth.com/v2"
CACHE_DIR = Path("cache") / "modrinth"
CACHE_TTL = timedelta(hours=24)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def debug(msg: str):
    if os.getenv("DEBUG", "false").lower() == "true":
        print("[DEBUG] ", msg)

def safe_request(url, retries=5, timeout=10):
    for attempt in range(1, retries + 1):
        try:
            timeout = int(os.getenv("REQUEST_TIMEOUT", 10))
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            # try parse JSON here; if it fails we'll raise with useful info
            try:
                _ = r.json()
            except ValueError:
                debug(f"Non-JSON response for {url}: {r.text[:200]!r}")
                raise RuntimeError(f"Non-JSON response from Modrinth API for {url}")
            return r
        except requests.RequestException as e:
            debug(f"Request failed: {e}. Retrying ({attempt}/{retries})...")
            time.sleep(1 * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

def slug_from_modrinth_url(url: str) -> str | None:
    # Accept many forms: https://modrinth.com/mods/sodium, /project/<id>, etc.
    if not url:
        return None
    url = url.strip().rstrip("/")
    # If URL contains /project/ or /mod/ or /mods/ or /modpack/
    m = re.search(r"/(project|mod|mods)/([^/?#]+)$", url)
    if m:
        return m.group(2)
    # fallback: last path segment
    parts = url.split("/")
    if parts:
        return parts[-1]
    return None

def cache_path_for(slug: str):
    safe_slug = sub(r'[^a-zA-Z0-9_-]', '_', slug)
    d = CACHE_DIR / safe_slug
    d.mkdir(parents=True, exist_ok=True)
    return d / "versions.json"

def cached_fetch_versions(provider, slug: str, mod_id: str, url: str):
    all_versions = []
    offset = 0
    page = 0
    while True:
        page_url = f"{url}?offset={offset}&limit=50"
        cache_file = cache_path(provider, slug, mod_id, page)
        if os.path.exists(cache_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - mtime < CACHE_TTL:
                data = json.loads(open(cache_file, encoding="utf-8").read())
                all_versions += data
                if len(data) < 50:
                    break
                page += 1
                offset += 50
                continue
        r = safe_request(page_url)
        data = r.json()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        all_versions += data
        if len(data) < 50:
            break
        offset += 50
        page += 1
    return all_versions

def get_mod_data(url: str) -> dict:
    slug = slug_from_modrinth_url(url)
    if not slug:
        raise ValueError(f"Could not extract Modrinth slug from URL: {url}")

    project_url = f"{API_BASE}/project/{slug}"
    debug(f"Fetching Modrinth project: {project_url}")
    try:
        proj = safe_request(project_url).json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Modrinth project for slug '{slug}': {e}")

    mod_name = proj.get("title") or proj.get("name") or slug
    mod_id = proj.get("id")

    versions_url = f"{API_BASE}/project/{slug}/version"
    try:
        versions = cached_fetch_versions(slug, versions_url, url)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Modrinth versions for '{slug}': {e}")

    pairs = set()
    for v in versions:
        game_versions = v.get("game_versions", [])
        loaders = v.get("loaders", [])
        for gv in game_versions:
            if not gv.startswith("1."):
                continue
            for loader in loaders:
                pairs.add((gv, loader.capitalize()))

    sorted_pairs = sorted(pairs, key=lambda x: (x[0], x[1]))

    return {
        "provider": "modrinth",
        "mod_id": mod_id,
        "name": mod_name + (" [c]" if cached else ""),
        "url": url,
        "versions": sorted_pairs
    }

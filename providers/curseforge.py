import os
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# -----------------------------
# Load environment
# -----------------------------
load_dotenv()

API_BASE = "https://api.curseforge.com/v1"
API_KEY = os.getenv("CF_API_KEY")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

HEADERS = {
    "Accept": "application/json",
    "x-api-key": API_KEY or "",
}

if not API_KEY:
    raise RuntimeError("CF_API_KEY missing in your .env file!")

CACHE_DIR = Path("cache")
CACHE_EXPIRY_HOURS = 24
SESSION = requests.Session()

# -----------------------------
# Debug helper
# -----------------------------
def debug(msg: str):
    if DEBUG:
        print(f"[DEBUG] {msg}")

# -----------------------------
# Safe requests with retry
# -----------------------------
def safe_request(url, headers=None, params=None, max_retries=5, timeout=20):
    retries = 0
    while retries < max_retries:
        try:
            r = SESSION.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.SSLError as e:
            debug(f"[SSL WARN] {e}. Retrying ({retries+1}/{max_retries})...")
        except requests.exceptions.RequestException as e:
            debug(f"[WARN] Request failed: {e}. Retrying ({retries+1}/{max_retries})...")
        retries += 1
        time.sleep(2 ** retries)  # exponential backoff
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries.")

# -----------------------------
# Cache helpers (multi-provider)
# -----------------------------
def get_cache_path(provider: str, mod_id: int, page: int) -> Path:
    dir_path = CACHE_DIR / provider / str(mod_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / f"page-{page}.json"

def load_cached_page(provider: str, mod_id: int, page: int) -> list | None:
    path = get_cache_path(provider, mod_id, page)
    if path.exists():
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_EXPIRY_HOURS):
            debug(f"Loading cached page {page} for mod {mod_id} (provider={provider})")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None

def save_cached_page(provider: str, mod_id: int, page: int, data: list):
    path = get_cache_path(provider, mod_id, page)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# -----------------------------
# URL / slug helpers
# -----------------------------
def extract_slug(url: str) -> str | None:
    parts = url.strip("/").split("/")
    if len(parts) >= 2 and parts[-2] == "mc-mods":
        return parts[-1]
    return None

def get_mod_id_from_slug(slug: str) -> int | None:
    search_url = f"{API_BASE}/mods/search"
    params = {"gameId": 432, "slug": slug}
    debug(f"Searching for slug '{slug}' via {search_url} params={params}")
    r = safe_request(search_url, headers=HEADERS, params=params)
    data = r.json().get("data", [])
    if data:
        return data[0]["id"]
    return None

# -----------------------------
# Fetch all files with pagination + cache
# -----------------------------
def fetch_all_files(mod_id: int, provider="curseforge") -> list:
    all_files = []
    page_size = 50
    page = 0

    while True:
        # Check cache first
        cached = load_cached_page(provider, mod_id, page)
        if cached is not None:
            debug(f"Using cached page {page} for mod {mod_id} (provider={provider})")
            all_files.extend(cached)
        else:
            url = f"{API_BASE}/mods/{mod_id}/files"
            params = {"index": page * page_size, "pageSize": page_size}
            debug(f"Fetching page {page} for mod {mod_id} (provider={provider})")
            try:
                r = safe_request(url, headers=HEADERS, params=params)
            except RuntimeError as e:
                debug(f"Failed to fetch page {page}, skipping rest: {e}")
                break
            data = r.json().get("data", [])
            if not data:
                break
            all_files.extend(data)
            save_cached_page(provider, mod_id, page, data)
            time.sleep(1)  # delay to reduce SSL/rate-limit issues

        # Stop if last page
        if len(all_files) < (page + 1) * page_size:
            break
        page += 1

    debug(f"Fetched {len(all_files)} total files for mod {mod_id} (provider={provider})")
    return all_files

# -----------------------------
# Main provider function
# -----------------------------
def get_mod_data(url: str, provider="curseforge") -> dict:
    slug = extract_slug(url)
    if not slug:
        raise ValueError(f"Invalid CurseForge mod URL: {url}")

    mod_id = get_mod_id_from_slug(slug)
    if not mod_id:
        raise ValueError(f"Could not extract mod ID from URL: {url}")

    debug(f"Found mod ID: {mod_id} for slug: {slug} (provider={provider})")
    files = fetch_all_files(mod_id, provider=provider)

    game_versions = set()
    mod_loaders = set()

    for f in files:
        for v in f.get("gameVersions", []):
            if v.startswith("1."):
                game_versions.add(v)
        loader = f.get("modLoader", None)
        if loader:
            mod_loaders.add(loader)
        
        loader = f.get("modLoader")
        if loader is None:
          # fallback based on filename
          filename = f.get("fileName", "").lower()
          if "forge" in filename:
            loader = "Forge"
          elif "fabric" in filename:
            loader = "Fabric"
          elif "neoforge" in filename:
            loader = "NeoForge"
          elif "quilt" in filename:
            loader = "Quilt"
          else:
            loader = "Unknown"
        mod_loaders.add(loader)


    return {
        "name": slug,
        "mod_id": mod_id,
        "url": url,
        "platform": provider,
        "versions": sorted(list(game_versions)),
        "loaders": sorted(list(mod_loaders)),
    }

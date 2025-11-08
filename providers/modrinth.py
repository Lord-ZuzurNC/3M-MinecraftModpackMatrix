import os, re, time, json, requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.modrinth.com/v2"
CACHE_TTL = timedelta(hours=24)
CACHE_ROOT = Path("cache") / "modrinth"
CACHE_ROOT.mkdir(parents=True, exist_ok=True)

def debug(msg: str):
    if os.getenv("DEBUG", "false").lower() == "true":
        print("[DEBUG]", msg)

def safe_request(url, retries=5, timeout=10):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
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
    if not url:
        return None
    url = url.strip().rstrip("/")
    m = re.search(r"/(project|mod|mods)/([^/?#]+)$", url)
    if m:
        return m.group(2)
    parts = url.split("/")
    if parts:
        return parts[-1]
    return None

from providers import cache_path

def cached_fetch_versions(provider, slug: str, mod_id: str, base_url: str):
    """
    Fetch Modrinth versions in pages of 50. Cache each page to:
    cache/{provider}/{slug}_{mod_id}/page-{page}.json
    Returns the combined list of version objects.
    """
    all_versions = []
    offset = 0
    page = 0
    page_size = 50

    while True:
        page_url = f"{base_url}?offset={offset}&limit={page_size}"
        cache_file = cache_path(provider, slug, mod_id, page)

        if os.path.exists(cache_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - mtime < CACHE_TTL:
                debug(f"Loading cached Modrinth page {page} for {slug}")
                data = json.loads(open(cache_file, encoding="utf-8").read())
                all_versions += data
                if len(data) < page_size:
                    break
                page += 1
                offset += page_size
                continue

        r = safe_request(page_url)
        data = r.json()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        all_versions += data
        if len(data) < page_size:
            break
        offset += page_size
        page += 1

    return all_versions

def version_key(v: str):
    # Extract numeric parts from version strings like '1.20.10'
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', v)]

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
        versions = cached_fetch_versions("modrinth", slug, str(mod_id), versions_url)
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

    sorted_pairs = sorted(pairs, key=version_key, reverse=True)

    return {
        "provider": "modrinth",
        "mod_id": str(mod_id),
        "name": mod_name,
        "url": url,
        "versions": sorted_pairs
    }

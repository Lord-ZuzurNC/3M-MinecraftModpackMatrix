import os, time, json, requests, urllib.parse, re
from datetime import timedelta
from dotenv import load_dotenv
from providers import cache_path, is_cache_expired

load_dotenv()
API_BASE = "https://api.curseforge.com/v1"
GAME_ID = 432
CACHE_TTL = timedelta(hours=24)

API_KEY = os.getenv("CF_API_KEY")
if not API_KEY:
    raise EnvironmentError("Missing CF_API_KEY in environment")

HEADERS = {"Accept": "application/json", "x-api-key": API_KEY}


def safe_request(url, params=None, retries=5, delay=1, timeout=10):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")


def cached_fetch(provider, slug, id, page, url, params):
    cache_file = cache_path(provider, slug, id, page)
    if os.path.exists(cache_file) and not is_cache_expired(cache_file, 24):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    r = safe_request(url, params=params)
    data = r.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def version_key(v):
    # ensure v is a string
    v = str(v)
    # split by ., -, +, _
    parts = re.split(r"[.\-+_]", v)
    key = []
    for p in parts:
        try:
            key.append(int(p))
        except ValueError:
            key.append(float('inf'))
    return tuple(key)


def normalize_slug(raw_slug: str) -> str:
    # Decode any percent-encoding
    slug = urllib.parse.unquote(raw_slug)
    # Remove emoji / non-ASCII chars
    slug = re.sub(r"[^\x00-\x7F]+", "", slug)
    # Trim whitespace / odd symbols
    return slug.strip(" /")

def get_mod_data(url: str) -> dict:
    raw_slug = url.rstrip("/").split("/")[-1]
    slug = normalize_slug(raw_slug)

    # resolve mod id via search
    search_url = f"{API_BASE}/mods/search"
    params = {"gameId": GAME_ID, "slug": slug}
    resp = safe_request(search_url, params=params)
    mods = resp.json().get("data", [])
    if not mods:
        raise ValueError(f"Mod '{slug}' not found on CurseForge.")

    best_mod = max(mods, key=lambda m: (m.get("downloadCount", 0), m.get("name", "")))
    id = str(best_mod["id"])
    mod_name = best_mod.get("name", slug)

    all_files = []
    page = 0
    page_size = 50

    while True:
        files_url = f"{API_BASE}/mods/{id}/files"
        params = {"index": page * page_size, "pageSize": page_size}
        data = cached_fetch("curseforge", slug, id, page, files_url, params)
        files = data.get("data", [])
        if not files:
            break
        all_files.extend(files)
        if len(files) < page_size:
            break
        page += 1
        time.sleep(0.2)

    pairs = set()
    for f in all_files:
        game_versions = [str(v) for v in f.get("gameVersions", []) if str(v).startswith("1.")]
        file_name = str(f.get("fileName", "")).lower()
        
        loaders = set()
        for token in map(str.lower, f.get("gameVersions", [])):
            if "fabric" in token:
                loaders.add("Fabric")
            if "neoforge" in token or "neo-forge" in token:
                loaders.add("NeoForge")
            if "quilt" in token:
                loaders.add("Quilt")
            if "forge" in token and "neoforge" not in token:
                loaders.add("Forge")
        if not loaders:
            ln = file_name
            if "fabric" in ln:
                loaders.add("Fabric")
            elif "neoforge" in ln or "neo-forge" in ln:
                loaders.add("NeoForge")
            elif "quilt" in ln:
                loaders.add("Quilt")
            elif "forge" in ln and "neoforge" not in ln:
                loaders.add("Forge")
            else:
                loaders.add("Unknown")
        
        for v in game_versions:
            for loader in loaders:
                pairs.add((str(v), loader))

    sorted_pairs = sorted(pairs, key=lambda x: (version_key(x[0]), x[1]), reverse=True)

    return {
        "name": mod_name,
        "id": id,
        "slug": slug,
        "provider": "curseforge",
        "versions": sorted_pairs,
        "url": url,
    }
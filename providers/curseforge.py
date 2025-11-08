import os, time, json, requests, re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

API_BASE = "https://api.curseforge.com/v1"
GAME_ID = 432  # Minecraft
CACHE_TTL = timedelta(hours=24)

API_KEY = os.getenv("CF_API_KEY")
DEBUG = os.getenv("DEBUG", "false").lower()

if not API_KEY:
    raise EnvironmentError("Missing CF_API_KEY in environment (.env not loaded)")

HEADERS = {
    "Accept": "application/json",
    "x-api-key": API_KEY,
}

def debug(msg: str):
    if DEBUG == "true":
        print("[DEBUG]", msg)

# safe_request same as you had
def safe_request(url, params=None, retries=5, delay=1, timeout=10):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            debug(f"Request failed: {e}. Retrying ({attempt}/{retries})...")
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

# Use shared cache_path helper
from providers import cache_path

def cached_fetch(provider, slug, mod_id, page, url, params):
    """
    Fetch and cache CurseForge API page data at:
    cache/{provider}/{slug}_{mod_id}/page-{page}.json
    """
    cache_file = cache_path(provider, slug, mod_id, page)

    # Check for valid cache
    if os.path.exists(cache_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - mtime < CACHE_TTL:
            debug(f"Loading cached CurseForge page {page} for {slug} ({mod_id})")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f), True

    # Fetch and cache new data
    response = safe_request(url, params=params)
    data = response.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data, False

def version_key(v: str):
    # Extract numeric parts from version strings like '1.20.10'
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', v)]

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

    # pick most likely one
    best_mod = max(mods, key=lambda m: (m.get("downloadCount", 0), m.get("name", "")))
    mod_id = best_mod["id"]
    mod_name = best_mod["name"]

    # Step 2: Fetch all file pages (with cache)
    all_files = []
    page = 0
    page_size = 50
    consecutive_misses = 0

    while True:
        files_url = f"{API_BASE}/mods/{mod_id}/files"
        params = {"index": page * page_size, "pageSize": page_size, "sortOrder": "asc"}
        debug(f"Fetching page {page} for mod {mod_id} (index={params['index']})")

        try:
            data, cached = cached_fetch("curseforge", slug, str(mod_id), page, files_url, params)
        except Exception as e:
            debug(f"[WARN] Failed to fetch page {page}: {e}")
            consecutive_misses += 1
            if consecutive_misses >= 3:
                break
            page += 1
            continue

        files = data.get("data", [])
        if not files:
            debug(f"[DEBUG] No files in page {page}, stopping.")
            break

        all_files.extend(files)

        if len(files) < page_size:
            debug(f"[DEBUG] Last page reached at {page}.")
            break
        page += 1
        time.sleep(0.2)

    debug(f"[DEBUG] Fetched {len(all_files)} files total for mod {mod_name}")

    # Step 3: Extract Minecraft version ↔ mod loader pairs
    pairs = set()
    for f in all_files:
        game_versions = [v for v in f.get("gameVersions", []) if v.startswith("1.")]
        lower_versions = [v.lower() for v in f.get("gameVersions", [])]
        file_name = f.get("fileName", "").lower()

        detected_loaders = set()
        for token in lower_versions:
            if "neoforge" in token or "neo-forge" in token:
                detected_loaders.add("NeoForge")
            elif "fabric" in token:
                detected_loaders.add("Fabric")
            elif "forge" in token:
                detected_loaders.add("Forge")
            elif "quilt" in token:
                detected_loaders.add("Quilt")

        if not detected_loaders:
            if "neoforge" in file_name or "neo-forge" in file_name:
                detected_loaders.add("NeoForge")
            elif "fabric" in file_name:
                detected_loaders.add("Fabric")
            elif "forge" in file_name:
                detected_loaders.add("Forge")
            elif "quilt" in file_name:
                detected_loaders.add("Quilt")

        if not detected_loaders:
            detected_loaders.add("Unknown")

        for v in game_versions:
            for loader in detected_loaders:
                pairs.add((v, loader))

    sorted_pairs = sorted(pairs, key=version_key, reverse=True)

    return {
        "provider": "curseforge",
        "mod_id": str(mod_id),
        "name": mod_name,
        "url": url,
        "versions": sorted_pairs
    }

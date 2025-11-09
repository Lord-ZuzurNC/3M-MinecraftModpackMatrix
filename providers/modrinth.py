import os, time, json, re, requests
from providers import cache_path, is_cache_expired

API_BASE = "https://api.modrinth.com/v2"
CACHE_TTL_HOURS = 24

def safe_request(url: str, retries: int = 5, delay: int = 1, timeout: int = 10):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException:
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")


def slug_from_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    url = url.strip().rstrip("/")
    m = re.search(r"/(project|mod|mods)/([^/?#]+)$", url)
    if m:
        return m.group(2)
    parts = url.split("/")
    return parts[-1] if parts else None


def cached_fetch(provider, slug, id, page, url):
    cache_file = cache_path(provider, slug, id, page)
    if os.path.exists(cache_file) and not is_cache_expired(cache_file, CACHE_TTL_HOURS):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    data = safe_request(url).json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def version_key(v: str):
    if not isinstance(v, str):
        v = str(v)

    parts = re.split(r"[.\-+_]", v)
    key = []
    for p in parts:
        if p.isdigit():
            key.append(int(p))
        else:
            key.append(float("inf"))
    return tuple(key)


def get_mod_data(url: str) -> dict:
    slug = slug_from_url(url)
    if not slug:
        raise ValueError(f"Invalid Modrinth URL: {url}")

    project_url = f"{API_BASE}/project/{slug}"
    proj = safe_request(project_url).json()
    mod_name = proj.get("title") or proj.get("name") or slug
    id = str(proj.get("id"))

    # Pagination (even though Modrinth usually returns all at once)
    all_versions = []
    page = 0
    page_size = 100

    while True:
        versions_url = f"{API_BASE}/project/{slug}/version?offset={page*page_size}&limit={page_size}"
        data = cached_fetch("modrinth", slug, id, page, versions_url)
        if isinstance(data, dict) and data.get("data"):
            items = data["data"]
        else:
            items = data
        if not items:
            break
        all_versions.extend(items)
        if len(items) < page_size:
            break
        page += 1

    pairs = set()
    for v in all_versions:
        game_versions = v.get("game_versions", []) if isinstance(v, dict) else []
        loaders = v.get("loaders", []) if isinstance(v, dict) else []
        for gv in game_versions:
            if not str(gv).startswith("1."):
                continue
            for loader in loaders:
                pairs.add((gv, str(loader).capitalize()))

    sorted_pairs = sorted(pairs, key=lambda x: version_key(x[0]), reverse=True)

    return {
        "name": mod_name,
        "id": id,
        "slug": slug,
        "provider": "modrinth",
        "versions": sorted_pairs,
        "url": url,
    }
import os
import re
import time
from typing import Optional

# --- safe name + cache path helpers (defined before importing providers) ---

def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))


def cache_path(provider: str, slug: str, mod_id: str, page: int | None = None) -> str:
    safe_provider = safe_name(provider)
    safe_slug = safe_name(slug)
    safe_mod_id = safe_name(mod_id)
    folder = os.path.join("cache", safe_provider, f"{safe_slug}_{safe_mod_id}")
    os.makedirs(folder, exist_ok=True)
    if page is None:
        return folder
    return os.path.join(folder, f"page-{page}.json")


def is_cache_expired(path: str, ttl_hours: int = 24) -> bool:
    if not os.path.exists(path):
        return True
    return (time.time() - os.path.getmtime(path)) > (ttl_hours * 3600)


# --- provider detection ---

def detect_provider(url: str) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    u = url.lower()
    if "curseforge.com" in u:
        return "curseforge"
    if "modrinth.com" in u:
        return "modrinth"
    return None


# --- import provider implementations (after helpers) ---
from .curseforge import get_mod_data as curseforge_get_mod_data
from .modrinth import get_mod_data as modrinth_get_mod_data

PROVIDERS = {
    "curseforge": curseforge_get_mod_data,
    "modrinth": modrinth_get_mod_data,
}
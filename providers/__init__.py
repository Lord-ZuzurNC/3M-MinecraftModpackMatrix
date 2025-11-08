import os, re
from typing import Optional

def detect_provider(url: str) -> Optional[str]:
    """
    Return provider key for a given URL, or None if unknown.
    """
    if not url:
        return None
    u = url.lower()
    if "curseforge.com" in u:
        return "curseforge"
    if "modrinth.com" in u:
        return "modrinth"
    return None

def safe_name(name: str) -> str:
    """
    Turn arbitrary strings into safe file/dir name fragments.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))

def cache_path(provider: str, slug: str, mod_id: str, page: int | None = None) -> str:
    """
    Build: cache/{safe_provider}/{safe_slug}_{safe_mod_id}/page-{page}.json
    If page is None return folder path.
    """
    safe_provider = safe_name(provider)
    safe_slug = safe_name(slug)
    safe_mod_id = safe_name(mod_id)
    folder = os.path.join("cache", safe_provider, f"{safe_slug}_{safe_mod_id}")
    os.makedirs(folder, exist_ok=True)
    if page is None:
        return folder
    return os.path.join(folder, f"page-{page}.json")

from .curseforge import get_mod_data as curseforge_get_mod_data
from .modrinth import get_mod_data as modrinth_get_mod_data

PROVIDERS = {
    "curseforge": curseforge_get_mod_data,
    "modrinth": modrinth_get_mod_data,
}
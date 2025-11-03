from .curseforge import get_mod_data as curseforge
from .modrinth import get_mod_data as modrinth
import re, os

def safe_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', str(name))

def cache_path(provider, slug, mod_id, page=None):
    safe_provider = safe_name(provider)
    safe_slug = safe_name(slug)
    safe_mod_id = safe_name(mod_id)
    folder = os.path.join("cache", safe_provider, f"{safe_slug}_{safe_mod_id}")
    os.makedirs(folder, exist_ok=True)
    if page is not None:
        return os.path.join(folder, f"page-{page}.json")
    return folder
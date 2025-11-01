from .curseforge import get_mod_data as curseforge_get

PROVIDERS = {
    "curseforge": curseforge_get,
    # "modrinth": modrinth_get,  # will be added later
}

def detect_provider(url: str) -> str:
    if "curseforge.com" in url:
        return "curseforge"
    elif "modrinth.com" in url:
        return "modrinth"
    else:
        raise ValueError(f"Unknown provider for URL: {url}")

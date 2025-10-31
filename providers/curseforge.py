import os
import re
import requests
from dotenv import load_dotenv

# Load .env file (contains CF_API_KEY)
load_dotenv()

API_KEY = os.getenv("CF_API_KEY")
BASE_URL = "https://api.curseforge.com/v1"

HEADERS = {
    "Accept": "application/json",
    "x-api-key": API_KEY
}


def extract_mod_id(url: str) -> int | None:
    """
    Extracts the mod ID from a CurseForge mod URL.
    Example: https://www.curseforge.com/minecraft/mc-mods/jei -> 238222
    """
    match = re.search(r'/mc-mods/(\d+)', url)
    if match:
        return int(match.group(1))

    # fallback: need to fetch from slug if the URL uses mod name instead of ID
    # e.g. https://www.curseforge.com/minecraft/mc-mods/just-enough-items-jei
    slug_match = re.search(r'/mc-mods/([a-zA-Z0-9\-_]+)', url)
    if slug_match:
        slug = slug_match.group(1)
        response = requests.get(f"{BASE_URL}/mods/search", headers=HEADERS, params={"gameId": 432, "slug": slug})
        if response.ok and response.json()["data"]:
            return response.json()["data"][0]["id"]

    return None


def get_mod_info(url: str) -> dict:
    """
    Fetches mod name, ID, supported versions and loaders from CurseForge.
    """
    mod_id = extract_mod_id(url)
    if not mod_id:
        raise ValueError(f"Could not extract mod ID from URL: {url}")

    # Basic mod info
    mod_response = requests.get(f"{BASE_URL}/mods/{mod_id}", headers=HEADERS)
    if not mod_response.ok:
        raise RuntimeError(f"Failed to fetch mod info (HTTP {mod_response.status_code})")

    mod_data = mod_response.json()["data"]
    mod_name = mod_data["name"]

    # Fetch file metadata (to extract versions + loaders)
    files_response = requests.get(f"{BASE_URL}/mods/{mod_id}/files", headers=HEADERS)
    if not files_response.ok:
        raise RuntimeError(f"Failed to fetch mod files (HTTP {files_response.status_code})")

    files = files_response.json()["data"]

    version_loader_pairs = set()
    for f in files:
        versions = f.get("gameVersions", [])
        loaders = []
        for v in versions:
            v_lower = v.lower()
            if v_lower in ("forge", "fabric", "neoforge", "quilt"):
                loaders.append(v.capitalize())
        mc_versions = [v for v in versions if re.match(r"\d+\.\d+(\.\d+)?", v)]

        for mc in mc_versions:
            for loader in (loaders or ["Unknown"]):
                version_loader_pairs.add((mc, loader))

    # Sort the results
    sorted_pairs = sorted(version_loader_pairs, key=lambda x: (x[0], x[1]))

    return {
        "mod_id": mod_id,
        "mod_name": mod_name,
        "versions": sorted_pairs
    }

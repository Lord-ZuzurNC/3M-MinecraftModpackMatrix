from providers import PROVIDERS, detect_provider
from tabulate import tabulate

def process_mod_url(url: str):
    provider_name = detect_provider(url)
    get_mod_data = PROVIDERS[provider_name]
    data = get_mod_data(url)
    return data


def main():
    url = input("Enter mod URL (CurseForge or Modrinth): ").strip()
    try:
        mod_info = process_mod_url(url)
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"\nFetching info for mod: {mod_info['name']} (ID {mod_info['mod_id']})\n")

    # Combine all versions with all loaders for display
    table = []
    for version in mod_info["versions"]:
       for loader in mod_info["loaders"] or ["Unknown"]:
          table.append([version, loader])

    print(tabulate(table, headers=["Version", "Mod Loader"], tablefmt="grid"))


if __name__ == "__main__":
    main()

from providers import PROVIDERS, detect_provider
from tabulate import tabulate


def main():
    print("Enter one or more mod URLs (one per line). Empty line to start:")
    urls = []
    while True:
        line = input().strip()
        if not line:
            break
        urls.append(line)


    all_rows = []
    for url in urls:
        provider_name = detect_provider(url)
        if not provider_name:
            print(f"[ERROR] Unknown provider for URL: {url}")
            continue


        get_mod_data = PROVIDERS.get(provider_name)
        if get_mod_data is None:
            print(f"[ERROR] No provider implementation for '{provider_name}' ({url})")
            continue


        try:
            mod_info = get_mod_data(url)
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            continue


        for version, loader in mod_info.get("versions", []):
            all_rows.append([mod_info.get("name"), version, loader])


    print("\n=== Summary ===")
    if all_rows:
        print(tabulate(all_rows, headers=["Mod Name", "MC Version", "Mod Loader"], tablefmt="grid"))
    else:
        print("No results.")


if __name__ == "__main__":
    main()
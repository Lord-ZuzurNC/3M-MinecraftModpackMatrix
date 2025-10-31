from providers.curseforge import get_mod_info
from tabulate import tabulate

def main():
    url = input("Enter CurseForge mod URL: ").strip()
    try:
        mod_info = get_mod_info(url)
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"\nFetching info for mod: {mod_info['mod_name']} (ID {mod_info['mod_id']})\n")

    table = [
        [mc, loader]
        for mc, loader in mod_info["versions"]
    ]
    print(tabulate(table, headers=["Game Version", "Mod Loader"], tablefmt="grid"))

if __name__ == "__main__":
    main()

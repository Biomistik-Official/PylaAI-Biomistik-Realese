import os
import sys
import time
import zipfile
import shutil
import tempfile
import subprocess

# URL to download the latest main branch zip from your GitHub repository
REPO_ZIP_URL = "https://github.com/Biomistik-Official/PylaAI-Biomistik-Realese/archive/refs/heads/main.zip"

# List of files to NEVER overwrite so user settings are preserved
PROTECTED_FILES = [
    "cfg/brawl_stars_api.toml",
    "cfg/telegram_config.toml",
    "cfg/discord_config.toml",
    "cfg/general_config.toml",
    "cfg/adaptive_state.json",
    "cfg/match_history.toml",
    "cfg/login.toml"
]


def _get_proxy_handler():
    """Reads proxy_url or use_eu_proxy from general_config.toml and returns a urllib ProxyHandler."""
    try:
        import urllib.request
        # Try to load config
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg", "general_config.toml")
        if not os.path.exists(cfg_path):
            return None

        try:
            import toml
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                cfg = toml.load(f)
        except Exception:
            return None

        # Check use_eu_proxy flag
        if not cfg.get("use_eu_proxy", False):
            return None

        # Use proxy_config module if available
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from common.proxy_config import get_proxy_url
            proxy_url = get_proxy_url()
            if proxy_url:
                return urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        except Exception:
            pass

        return None
    except Exception:
        return None


def _kill_adb():
    """Завершить ADB-сервер перед обновлением чтобы не было конфликтов."""
    adb_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adb.exe")
    if not os.path.exists(adb_exe):
        adb_exe = "adb"
    try:
        subprocess.run(
            [adb_exe, "kill-server"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        print("[*] ADB server stopped.")
    except Exception:
        pass


def download_and_update():
    import urllib.request

    print("=======================================")
    print(" PylaAi-Biomistik Auto Updater")
    print("=======================================")

    # Завершить ADB перед обновлением
    _kill_adb()

    print(f"[*] Downloading latest update from GitHub...")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = os.path.join(tmp_dir, "update.zip")

            # Настраиваем opener с прокси (если включён)
            proxy_handler = _get_proxy_handler()
            if proxy_handler:
                print("[*] Using EU proxy for download...")
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", "Mozilla/5.0")]
            urllib.request.install_opener(opener)

            # Download the zip file
            req = urllib.request.Request(REPO_ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as response, open(zip_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

            print("[*] Download complete. Extracting files...")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmp_dir)

            extracted_folders = [f for f in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, f))]

            if not extracted_folders:
                print("[!] Error: Unexpected zip structure.")
                return False

            root_extracted_folder = os.path.join(tmp_dir, extracted_folders[0])

            print("[*] Installing new files...")

            base_dir = os.path.abspath(".")

            for src_dir, dirs, files in os.walk(root_extracted_folder):
                rel_dir = os.path.relpath(src_dir, root_extracted_folder)
                dest_dir = os.path.join(base_dir, rel_dir) if rel_dir != "." else base_dir

                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)

                for file in files:
                    src_file = os.path.join(src_dir, file)
                    dest_file = os.path.join(dest_dir, file)
                    rel_file_path = os.path.relpath(dest_file, base_dir).replace("\\", "/")

                    if rel_file_path in PROTECTED_FILES and os.path.exists(dest_file):
                        print(f"[-] Skipping protected file: {rel_file_path}")
                        continue

                    try:
                        shutil.copy2(src_file, dest_file)
                    except Exception as e:
                        print(f"[!] Warning: Could not overwrite {rel_file_path}. Is it currently running?")

            print("[+] Update installed successfully!")
            return True

    except Exception as e:
        print(f"[!] Failed to update: {e}")
        return False

if __name__ == "__main__":
    if download_and_update():
        print("\nUpdate complete. You can now start the bot.")
    else:
        print("\nUpdate failed. Please check your internet connection or repository URL.")

    print("\nPress Enter to exit...")
    input()

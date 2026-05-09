import os
import sys
import time
import urllib.request
import zipfile
import shutil
import tempfile

# URL to download the latest main branch zip from your GitHub repository
# Make sure this URL matches your actual GitHub repository
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

def download_and_update():
    print("=======================================")
    print(" PylaAi-Biomistik Auto Updater")
    print("=======================================")
    print(f"[*] Downloading latest update from GitHub...")
    
    try:
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = os.path.join(tmp_dir, "update.zip")
            
            # Download the zip file
            req = urllib.request.Request(REPO_ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            print("[*] Download complete. Extracting files...")
            
            # Extract the zip file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # The extracted zip usually contains a root folder like "PylaAI-Biomistik-Realese-main"
            extracted_folders = [f for f in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, f))]
            
            if not extracted_folders:
                print("[!] Error: Unexpected zip structure.")
                return False
                
            root_extracted_folder = os.path.join(tmp_dir, extracted_folders[0])
            
            print("[*] Installing new files...")
            
            # Copy files from extracted folder to current directory
            base_dir = os.path.abspath(".")
            
            for src_dir, dirs, files in os.walk(root_extracted_folder):
                # Calculate relative path to the current directory
                rel_dir = os.path.relpath(src_dir, root_extracted_folder)
                dest_dir = os.path.join(base_dir, rel_dir) if rel_dir != "." else base_dir
                
                # Create directory if it doesn't exist
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                
                for file in files:
                    src_file = os.path.join(src_dir, file)
                    dest_file = os.path.join(dest_dir, file)
                    rel_file_path = os.path.relpath(dest_file, base_dir).replace("\\", "/")
                    
                    # Check if the file is protected
                    if rel_file_path in PROTECTED_FILES and os.path.exists(dest_file):
                        print(f"[-] Skipping protected file: {rel_file_path}")
                        continue
                    
                    # Overwrite file
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

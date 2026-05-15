import os
import shutil
import subprocess
import sys

def main():
    print("=== Starting PylaAI HARD COMPILE Build (Nuitka) ===")
    
    # Original source
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # User's requested output directory
    build_dir = r"C:\Users\Biomistik\Desktop\PylaAI-Closed"
    src_copy_dir = os.path.join(build_dir, "src")
    dist_dir = os.path.join(build_dir, "dist")
    
    # 1. Clean previous build
    print(f"1. Cleaning {build_dir} ...")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            print(f"Warning: could not delete {build_dir}: {e}")
            
    os.makedirs(src_copy_dir, exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)

    # 2. Copy source files
    print("2. Copying source files...")
    folders_to_copy = ['api', 'common', 'core', 'gui', 'remote', 'tools', 'vision']
    for folder in folders_to_copy:
        src_path = os.path.join(base_dir, folder)
        if os.path.exists(src_path):
            shutil.copytree(src_path, os.path.join(src_copy_dir, folder))
            
    files_to_copy = ['main.py', 'setup.py', 'PylaLauncher.py', 'updater.py', 'replace_script.py']
    for file in files_to_copy:
        src_path = os.path.join(base_dir, file)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(src_copy_dir, file))

    # 3. Copy assets
    print("3. Preparing assets...")
    assets_to_copy = ['cfg', 'models', 'images', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'adb.exe']
    for asset in assets_to_copy:
        src_path = os.path.join(base_dir, asset)
        dst_path = os.path.join(src_copy_dir, asset)
        if os.path.exists(src_path):
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)

    # 4. Run Nuitka
    print("4. Hard compiling with Nuitka... (This will take a while!)")
    
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        "--plugin-enable=numpy",
        "--plugin-enable=tk-inter",
        "--windows-console-mode=force",
        "--include-data-dir=cfg=cfg",
        "--include-data-dir=models=models",
        "--include-data-dir=images=images",
        "--include-data-dir=api=api",
        "--include-package-data=scrcpy",
        r"--include-data-file=C:\Users\Biomistik\AppData\Local\Programs\Python\Python311\Lib\site-packages\scrcpy\scrcpy-server.jar=scrcpy/scrcpy-server.jar",
        "--include-data-file=AdbWinApi.dll=AdbWinApi.dll",
        "--include-data-file=AdbWinUsbApi.dll=AdbWinUsbApi.dll",
        "--include-data-file=adb.exe=adb.exe",
        "--output-filename=TrophyFlow.exe",
        "--output-dir=" + dist_dir,
        os.path.join(src_copy_dir, "main.py")
    ]
    
    print(f"Running: {' '.join(nuitka_cmd)}")
    subprocess.run(nuitka_cmd, cwd=src_copy_dir, check=True)
    
    print(f"=== Nuitka Build Complete! Executable is in: {dist_dir} ===")

if __name__ == "__main__":
    main()

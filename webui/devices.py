"""ADB discovery only; importing this module never launches an emulator."""
import os
import re
import shutil
import subprocess


def emulator_name(port):
    if port in {16384, 16416, 16448, 16480, 7555}:
        return 'MuMu'
    if port >= 62001 and (port - 62001) % 24 == 0:
        return 'NoxPlayer'
    if port >= 5565 and (port - 5565) % 10 == 0:
        return 'BlueStacks'
    return 'LDPlayer'


def scan_devices(root):
    executable = str(root / 'adb.exe') if (root / 'adb.exe').exists() else shutil.which('adb')
    if not executable:
        raise ValueError('ADB was not found. Restore adb.exe or install Android platform tools.')
    try:
        output = subprocess.check_output([executable, 'devices'], timeout=8, text=True,
            encoding='utf-8', errors='replace', stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('ADB did not respond. Check that the emulator is running and ADB is enabled.') from None
    result = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1] != 'device':
            continue
        serial = parts[0]
        match = re.fullmatch(r'(?:127\.0\.0\.1:|localhost:|emulator-)([0-9]+)', serial)
        if match:
            port = int(match[1])
            if 1 <= port <= 65535 and port != 5037:
                result.append(dict(serial=serial, port=port, emulator=emulator_name(port)))
    return result

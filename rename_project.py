import os
import re

target_dir = r"C:\Users\Biomistik\Desktop\PylaAI-Closed"

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
    
    # Сначала заменяем самые длинные совпадения
    replacements = [
        ("PylaAI-Biomistik-Realese", "TrophyFlow"),
        ("PylaAI-Biomistik", "TrophyFlow"),
        ("Pyla-Biomistik", "TrophyFlow"),
        ("PylaAI", "TrophyFlow"),
        ("PylaAi", "TrophyFlow"),
        ("PylaLauncher", "TrophyFlowLauncher"),
        ("pyla_main", "trophyflow_main"),
        ("pyla_version", "trophyflow_version"),
        ("Pyla", "TrophyFlow"),
        ("pyla", "trophyflow")
    ]
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    # Заменяем Biomistik, игнорируя пути C:\Users\Biomistik
    # Регулярка проверяет, что перед Biomistik нет слова Users\\ или Users/
    new_content = re.sub(r'(?<!Users\\)(?<!Users\\\\)(?<!Users/)Biomistik', 'TrophyFlow', new_content, flags=re.IGNORECASE)
            
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched content in {filepath}")

for root, dirs, files in os.walk(target_dir):
    if 'dist' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith(('.py', '.toml', '.json', '.txt', '.md', '.bat')):
            replace_in_file(os.path.join(root, file))

# Переименование файлов
for root, dirs, files in os.walk(target_dir, topdown=False):
    if 'dist' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if "Pyla" in file or "pyla" in file:
            new_name = file.replace("Pyla", "TrophyFlow").replace("pyla", "trophyflow")
            old_path = os.path.join(root, file)
            new_path = os.path.join(root, new_name)
            os.rename(old_path, new_path)
            print(f"Renamed {old_path} to {new_path}")

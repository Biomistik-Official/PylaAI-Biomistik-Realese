import re
import glob

# Theme mapping
theme = {
    '#4A4A4A': '#141416',
    '#AA2A2A': '#ff204e',
    '#BB3A3A': '#d41940',
    '#333333': '#141416',
    '#555555': '#2a2a2f',
    '#c0392b': '#ff204e',
    '#e74c3c': '#d41940',
    '#888888': '#8e8e93',
}

files = glob.glob('gui/*.py')
for file in files:
    if 'select_brawler' in file:
        continue
    with open(file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Replace colors
    for old, new in theme.items():
        code = code.replace(old, new)
        code = code.replace(old.lower(), new)
        
    # Inject background color for main windows
    code = code.replace('self.app = ctk.CTk()', 'self.app = ctk.CTk()\n        self.app.configure(fg_color="#0a0a0b")')
    code = code.replace('top = ctk.CTkToplevel(self.app)', 'top = ctk.CTkToplevel(self.app)\n        top.configure(fg_color="#0a0a0b")')
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(code)
print('UI theme updated in all files.')

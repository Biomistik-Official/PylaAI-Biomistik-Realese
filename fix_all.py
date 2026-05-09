import re

with open('gui/hub.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the exact injected string that causes crashes in OptionMenu and CheckBox
code = code.replace('fg_color="transparent", border_color="#ff204e", border_width=1', 'fg_color="#ff204e"')

# In case some commas were missing or left
code = code.replace('fg_color="transparent", border_color="#ff204e", border_width=1,', 'fg_color="#ff204e",')

with open('gui/hub.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed everything")

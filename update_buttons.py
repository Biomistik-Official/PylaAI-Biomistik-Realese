import re
with open('gui/hub.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Make buttons modern outlines
code = re.sub(r'fg_color="#ff204e"', 'fg_color="transparent", border_color="#ff204e", border_width=1', code)
code = re.sub(r'hover_color="#d41940"', 'hover_color="#1a1a1c"', code)

with open('gui/hub.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Buttons outlined')

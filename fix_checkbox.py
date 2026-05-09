import re

with open('gui/hub.py', 'r', encoding='utf-8') as f:
    code = f.read()

# We need to revert the transparent outline styling for non-buttons.
# Let's target CTkCheckBox
code = re.sub(
    r'(CTkCheckBox\([^)]*)fg_color="transparent", border_color="#ff204e", border_width=1([^)]*\))',
    r'\1fg_color="#ff204e"\2',
    code,
    flags=re.MULTILINE
)

# And CTkSlider if any
code = re.sub(
    r'(CTkSlider\([^)]*)fg_color="transparent", border_color="#ff204e", border_width=1([^)]*\))',
    r'\1fg_color="#ff204e"\2',
    code,
    flags=re.MULTILINE
)

# And CTkSegmentedButton if any
code = re.sub(
    r'(CTkSegmentedButton\([^)]*)fg_color="transparent", border_color="#ff204e", border_width=1([^)]*\))',
    r'\1fg_color="#ff204e"\2',
    code,
    flags=re.MULTILINE
)

# Also CTkProgressBar
code = re.sub(
    r'(CTkProgressBar\([^)]*)fg_color="transparent", border_color="#ff204e", border_width=1([^)]*\))',
    r'\1fg_color="#ff204e"\2',
    code,
    flags=re.MULTILINE
)

with open('gui/hub.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed CTkCheckBox and other non-button kwargs")

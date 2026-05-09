import re

with open('gui/hub.py', 'r', encoding='utf-8') as f:
    code = f.read()

bad_str = 'fg_color="transparent", border_color="#ff204e", border_width=1,'

# For gpu_menu and any CTkOptionMenu that has it, we just replace it with fg_color="#141416"
# Let's target the exact blocks:

code = code.replace(
    '''        gpu_menu = ctk.CTkOptionMenu(
            container,
            values=gpu_values,
            command=on_gpu_change,
            variable=gpu_var,
            font=("Arial", S(16)),
            fg_color="transparent", border_color="#ff204e", border_width=1,
            button_color="#ff204e",
            button_hover_color="#1a1a1c",
            width=S(100),
            height=S(35)
        )''',
    '''        gpu_menu = ctk.CTkOptionMenu(
            container,
            values=gpu_values,
            command=on_gpu_change,
            variable=gpu_var,
            font=("Arial", S(16)),
            fg_color="#141416",
            button_color="#ff204e",
            button_hover_color="#d41940",
            width=S(100),
            height=S(35)
        )'''
)

# And language menu
code = code.replace(
    '''        language_menu = ctk.CTkOptionMenu(
            container,
            values=["English"],
            font=("Arial", S(16)),
            fg_color="transparent", border_color="#ff204e", border_width=1,
            button_color="#ff204e",
            button_hover_color="#1a1a1c",
            width=S(120),
            height=S(35)
        )''',
    '''        language_menu = ctk.CTkOptionMenu(
            container,
            values=["English"],
            font=("Arial", S(16)),
            fg_color="#141416",
            button_color="#ff204e",
            button_hover_color="#d41940",
            width=S(120),
            height=S(35)
        )'''
)

with open('gui/hub.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed CTkOptionMenu kwargs")

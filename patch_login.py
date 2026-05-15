import os

new_login_content = """import os
import sys
import subprocess
import uuid
import requests

import customtkinter as ctk
from common.utils import save_dict_as_toml

sys.path.append(os.path.abspath('../'))
from common.utils import load_toml_as_dict

def get_hwid():
    try:
        output = subprocess.check_output('wmic csproduct get uuid', shell=True).decode().split('\\n')[1].strip()
        if output and len(output) > 10:
            return output
    except Exception:
        pass
    return str(uuid.getnode())

def login(logged_in_setter):
    LICENSE_SERVER_URL = "http://localhost:8080/api/verify"

    def validate_api_key(api_key):
        hwid = get_hwid()
        try:
            response = requests.post(LICENSE_SERVER_URL, json={"key": api_key, "hwid": hwid}, timeout=5)
            data = response.json()
            if data.get("status") == "ok":
                return True, data.get("message", "Success")
            else:
                return False, data.get("message", "Invalid key")
        except requests.exceptions.RequestException:
            return False, "Could not connect to license server"

    def on_login_button_click():
        api_key = api_key_entry.get().strip()
        if not api_key:
            result_label.configure(text="Please enter a key", text_color="red")
            return
            
        result_label.configure(text="Verifying...", text_color="yellow")
        app.update()
        
        is_valid, message = validate_api_key(api_key)
        if is_valid:
            result_label.configure(text="Login Successful!", text_color="green")
            logged_in_setter(True)
            app.destroy()
            save_dict_as_toml({"key": api_key}, "./cfg/login.toml")
        else:
            result_label.configure(text=message, text_color="red")

    try:
        login_data = load_toml_as_dict('./cfg/login.toml')
        auth_key = login_data.get('key', '')
        if auth_key:
            is_valid, _ = validate_api_key(auth_key)
            if is_valid:
                logged_in_setter(True)
                return
    except Exception:
        pass

    app = ctk.CTk()
    app.title('PYLAAI LOGIN')
    app.geometry('600x400')
    app.resizable(False, False)
    ctk.set_appearance_mode("dark")
    app.configure(fg_color="#0a0a0b")

    card = ctk.CTkFrame(app, fg_color="#141416", corner_radius=15, width=450, height=300)
    card.place(relx=0.5, rely=0.5, anchor="center")
    card.pack_propagate(False)

    title_label = ctk.CTkLabel(card, text="Pyla-Biomistik", font=("Segoe UI", 32, "bold"), text_color="#ff204e")
    title_label.pack(pady=(30, 5))
    
    subtitle = ctk.CTkLabel(card, text="Enter your License Key to continue", font=("Segoe UI", 14), text_color="gray")
    subtitle.pack(pady=(0, 25))

    api_key_entry = ctk.CTkEntry(
        card, placeholder_text="XXXX-XXXX-XXXX-XXXX", font=("Segoe UI", 16), width=350, height=45,
        fg_color="#1a1a1c", border_color="#2a2a2f", corner_radius=8, text_color="white"
    )
    api_key_entry.pack(pady=(0, 20))

    login_button = ctk.CTkButton(
        card, text="LOGIN", command=on_login_button_click, font=("Segoe UI", 16, "bold"),
        width=350, height=45, corner_radius=8,
        fg_color="transparent", border_color="#ff204e", border_width=2, text_color="#ff204e",
        hover_color="#1a1a1c"
    )
    login_button.pack()

    def on_entry_focus(e):
        api_key_entry.configure(border_color="#ff204e")
    def on_entry_unfocus(e):
        api_key_entry.configure(border_color="#2a2a2f")
        
    api_key_entry.bind("<FocusIn>", on_entry_focus)
    api_key_entry.bind("<FocusOut>", on_entry_unfocus)

    result_label = ctk.CTkLabel(card, text="", font=("Segoe UI", 14))
    result_label.pack(pady=(15, 0))

    app.mainloop()
"""

target_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\src\gui\login.py"

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(new_login_content)

print(f"Patched {target_path}")

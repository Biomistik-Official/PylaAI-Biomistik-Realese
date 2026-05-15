import os
import sys

import customtkinter as ctk  # Import the customtkinter library
from gui.api import check_if_exists
from common.utils import api_base_url, save_dict_as_toml

sys.path.append(os.path.abspath('../'))
from common.utils import load_toml_as_dict


def login(logged_in_setter):

    if api_base_url == "localhost":
        logged_in_setter(True)
        return

    def validate_api_key(api_key):
        return check_if_exists(api_key)

    def on_login_button_click():
        api_key = api_key_entry.get()
        if validate_api_key(api_key):
            result_label.configure(text="Login Successful!", text_color="green")
            logged_in_setter(True)
            app.destroy()
            save_dict_as_toml({"key": api_key}, "./cfg/login.toml")
            return
        else:
            result_label.configure(text="Invalid API Key", text_color="red")

    login_data = load_toml_as_dict('./cfg/login.toml')
    auth_key = login_data['key']
    if auth_key:
        if validate_api_key(auth_key):
            logged_in_setter(True)
            return

    app = ctk.CTk()
    app.title('PYLAAI LOGIN')
    app.geometry('600x400')
    app.resizable(False, False)
    ctk.set_appearance_mode("dark")
    app.configure(fg_color="#0a0a0b")

    # Center Card
    card = ctk.CTkFrame(app, fg_color="#141416", corner_radius=15, width=450, height=300)
    card.place(relx=0.5, rely=0.5, anchor="center")
    card.pack_propagate(False)

    title_label = ctk.CTkLabel(card, text="Pyla-Biomistik", font=("Segoe UI", 32, "bold"), text_color="#ff204e")
    title_label.pack(pady=(30, 5))
    
    subtitle = ctk.CTkLabel(card, text="Enter your API Key to continue", font=("Segoe UI", 14), text_color="gray")
    subtitle.pack(pady=(0, 25))

    api_key_entry = ctk.CTkEntry(
        card, placeholder_text="API Key", font=("Segoe UI", 16), width=350, height=45,
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

    # Hover effect for entry
    def on_entry_focus(e):
        api_key_entry.configure(border_color="#ff204e")
    def on_entry_unfocus(e):
        api_key_entry.configure(border_color="#2a2a2f")
        
    api_key_entry.bind("<FocusIn>", on_entry_focus)
    api_key_entry.bind("<FocusOut>", on_entry_unfocus)

    result_label = ctk.CTkLabel(card, text="", font=("Segoe UI", 14))
    result_label.pack(pady=(15, 0))

    app.mainloop()

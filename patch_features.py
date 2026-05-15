import os

# Paths
utils_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\src\common\utils.py"
login_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\src\gui\login.py"
hub_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\src\gui\hub.py"

# --- 1. PATCH utils.py ---
with open(utils_path, 'r', encoding='utf-8') as f:
    utils_code = f.read()

# Make sure we don't patch twice
if "def resolve_instance_path(" in utils_code and "appdata_dir" not in utils_code:
    old_func = """def resolve_instance_path(path_str):
    if not isinstance(path_str, str):
        path_str = str(path_str)
    instance_id = os.environ.get("PYLAAI_INSTANCE", "")
    if instance_id and instance_id != "1":
        if path_str.startswith("cfg/"):
            return path_str.replace("cfg/", f"cfg_{instance_id}/", 1)
        elif path_str.startswith("./cfg/"):
            return path_str.replace("./cfg/", f"./cfg_{instance_id}/", 1)
    return path_str"""
    
    new_func = """def resolve_instance_path(path_str):
    import sys
    import shutil
    if not isinstance(path_str, str):
        path_str = str(path_str)
    
    base_path = path_str
    
    if getattr(sys, 'frozen', False):
        appdata_dir = os.path.join(os.environ.get("APPDATA", ""), "TrophyFlow")
        if path_str.startswith("cfg/") or path_str.startswith("./cfg/"):
            rel_path = path_str[2:] if path_str.startswith("./") else path_str
            new_path = os.path.join(appdata_dir, rel_path)
            
            if not os.path.exists(new_path):
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                embedded_path = os.path.join(sys._MEIPASS, rel_path)
                if os.path.exists(embedded_path):
                    shutil.copy2(embedded_path, new_path)
            base_path = new_path
            
    instance_id = os.environ.get("PYLAAI_INSTANCE", "")
    if instance_id and instance_id != "1":
        base_path = base_path.replace("cfg", f"cfg_{instance_id}", 1)
        
    return base_path"""
    
    # Actually, let's just use replace since it's a clean block
    if old_func in utils_code:
        utils_code = utils_code.replace(old_func, new_func)
    else:
        # manual replace
        start = utils_code.find("def resolve_instance_path(path_str):")
        end = utils_code.find("def load_toml_as_dict(file_path):")
        if start != -1 and end != -1:
            utils_code = utils_code[:start] + new_func + "\n\n" + utils_code[end:]
            
    with open(utils_path, 'w', encoding='utf-8') as f:
        f.write(utils_code)
    print("utils.py patched successfully.")

# --- 2. PATCH login.py ---
with open(login_path, 'r', encoding='utf-8') as f:
    login_code = f.read()

if "key_path" not in login_code:
    # Adding key loading
    entry_line = 'key_entry = ctk.CTkEntry(root, width=300, font=("Arial", 14), placeholder_text="Enter License Key")'
    new_entry_logic = """key_path = os.path.join(os.environ.get("APPDATA", ""), "TrophyFlow", "license.txt")
saved_key = ""
if os.path.exists(key_path):
    with open(key_path, "r", encoding="utf-8") as f:
        saved_key = f.read().strip()

key_entry = ctk.CTkEntry(root, width=300, font=("Arial", 14), placeholder_text="Enter License Key")
if saved_key:
    key_entry.insert(0, saved_key)"""
    
    login_code = login_code.replace(entry_line, new_entry_logic)
    
    # Adding key saving on success
    success_line = 'messagebox.showinfo("Success", "License Verified! Starting app...")'
    new_success_logic = """os.makedirs(os.path.dirname(key_path), exist_ok=True)
                with open(key_path, "w", encoding="utf-8") as f:
                    f.write(key)
                messagebox.showinfo("Success", "License Verified! Starting app...")"""
    
    login_code = login_code.replace(success_line, new_success_logic)
    
    with open(login_path, 'w', encoding='utf-8') as f:
        f.write(login_code)
    print("login.py patched successfully.")

# --- 3. PATCH hub.py ---
with open(hub_path, 'r', encoding='utf-8') as f:
    hub_code = f.read()

if "Dev Email (API)" not in hub_code:
    hook_str = 'row_idx += 1\n\n        lbl_play_again = ctk.CTkLabel(container, text="Play Again On Win:", font=("Arial", S(18)))'
    
    new_fields = """row_idx += 1

        # Brawl Stars API Credentials
        lbl_api_email = ctk.CTkLabel(container, text="Dev Email (API):", font=("Arial", S(18)))
        lbl_api_email.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        
        from common.utils import load_toml_as_dict, save_dict_as_toml, resolve_instance_path
        bs_cfg_path = resolve_instance_path("cfg/brawl_stars_api.toml")
        bs_cfg = load_toml_as_dict(bs_cfg_path)
        
        email_var = tk.StringVar(value=bs_cfg.get("developer_email", ""))
        def on_email_save(*_):
            bs_cfg["developer_email"] = email_var.get().strip()
            save_dict_as_toml(bs_cfg, bs_cfg_path)
            
        entry_email = ctk.CTkEntry(container, textvariable=email_var, width=S(150), font=("Arial", S(16)))
        entry_email.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        entry_email.bind("<FocusOut>", on_email_save)
        entry_email.bind("<Return>", on_email_save)
        self.attach_tooltip(entry_email, "Email for developer.brawlstars.com API")
        row_idx += 1
        
        lbl_api_pass = ctk.CTkLabel(container, text="Dev Password (API):", font=("Arial", S(18)))
        lbl_api_pass.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        
        pass_var = tk.StringVar(value=bs_cfg.get("developer_password", ""))
        def on_pass_save(*_):
            bs_cfg["developer_password"] = pass_var.get().strip()
            save_dict_as_toml(bs_cfg, bs_cfg_path)
            
        entry_pass = ctk.CTkEntry(container, textvariable=pass_var, width=S(150), font=("Arial", S(16)), show="*")
        entry_pass.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        entry_pass.bind("<FocusOut>", on_pass_save)
        entry_pass.bind("<Return>", on_pass_save)
        self.attach_tooltip(entry_pass, "Password for developer.brawlstars.com API")
        row_idx += 1

        lbl_play_again = ctk.CTkLabel(container, text="Play Again On Win:", font=("Arial", S(18)))"""
        
    hub_code = hub_code.replace(hook_str, new_fields)
    
    with open(hub_path, 'w', encoding='utf-8') as f:
        f.write(hub_code)
    print("hub.py patched successfully.")

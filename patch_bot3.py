import os

target_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\license_server\bot.py"

with open(target_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Патч для показа HWID в списке ключей
old_select = "c.execute(\"SELECT key_string, is_used, owned_by FROM keys ORDER BY id DESC LIMIT 15\")"
new_select = "c.execute(\"SELECT key_string, is_used, owned_by, hwid FROM keys ORDER BY id DESC LIMIT 15\")"

old_loop = """    for k, used, owner in rows:
        status = "🔴 Использован ПК" if used else "🟢 Свободен"
        owner_text = f"(TG ID: {owner})" if owner else ""
        text += f"`{k}` - {status} {owner_text}\\n\""""

new_loop = """    for k, used, owner, hwid in rows:
        status = "🔴 Активирован" if used else "🟢 Свободен"
        owner_text = f"👤 TG: {owner}" if owner else ""
        hwid_text = f"💻 HWID: {hwid[:8]}..." if hwid else ""
        text += f"`{k}` - {status} {owner_text} {hwid_text}\\n\""""

# Поскольку я мог немного не так скопировать старый луп, сделаем более надежную замену:
content = content.replace("SELECT key_string, is_used, owned_by FROM keys", "SELECT key_string, is_used, owned_by, hwid FROM keys")
content = content.replace("for k, used, owner in rows:", "for k, used, owner, hwid in rows:")
content = content.replace('status = "🔴 Использован ПК" if used else "🟢 Свободен"', 'status = "🔴 Акт." if used else "🟢 Св."')
content = content.replace('owner_text = f"(TG ID: {owner})" if owner else ""', 'owner_text = f"TG:{owner}" if owner else ""\n        hwid_text = f" HWID:{hwid[:8]}..." if hwid else ""')
content = content.replace('text += f"`{k}` - {status} {owner_text}\\n"', 'text += f"`{k}` - {status} {owner_text}{hwid_text}\\n"')

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("List keys patched successfully.")

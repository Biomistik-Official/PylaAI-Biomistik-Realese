import os

target_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\license_server\bot.py"
bat_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\license_server\start_bot.bat"

with open(target_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Патч для `message.from_user.id` и `callback.from_user.id`
content = content.replace("message.from_user.id", "(message.from_user.id if message.from_user else 0)")
content = content.replace("callback.from_user.id", "(callback.from_user.id if callback.from_user else 0)")

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(content)

# Создание bat файла
with open(bat_path, 'w', encoding='utf-8') as f:
    f.write("@echo off\n")
    f.write("echo Starting PylaAI License Bot...\n")
    f.write("python bot.py\n")
    f.write("pause\n")

print("Pylance warnings fixed and start_bot.bat created.")

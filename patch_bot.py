import os

target_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\license_server\bot.py"

with open(target_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Простой патч для всех `await callback.message.answer`
content = content.replace("await callback.message.answer", "if isinstance(callback.message, types.Message):\n        await callback.message.answer")

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Pylance warnings fixed.")

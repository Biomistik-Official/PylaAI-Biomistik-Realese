import sqlite3
import os

db_path = r"C:\Users\Biomistik\Desktop\PylaAI-Closed\license_server\keys.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE keys ADD COLUMN owned_by INTEGER DEFAULT NULL")
        print("Column 'owned_by' added successfully!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column already exists.")
        else:
            print("Error:", e)
    conn.commit()
    conn.close()
else:
    print("DB not found at", db_path)

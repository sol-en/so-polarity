import sqlite3
import os

db_path = "/home/vf/Downloads/Household/zhbk_app/zhbk_app.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Tariffs ---")
cursor.execute("SELECT name, value, is_active FROM tariffs")
for row in cursor.fetchall():
    print(row)

print("\n--- Residents Count (first 10) ---")
cursor.execute("SELECT number, residents_count, has_lift_exemption FROM apartments LIMIT 10")
for row in cursor.fetchall():
    print(row)

conn.close()

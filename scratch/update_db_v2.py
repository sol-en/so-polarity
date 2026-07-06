import sqlite3
import os

db_path = '/home/vf/Downloads/Household/zhbk_app/zhbk_app.db'
print(f"Checking DB at {db_path}, exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
c = conn.cursor()
try:
    c.execute("ALTER TABLE charges ADD COLUMN owner_name VARCHAR")
    print("Added owner_name")
except Exception as e:
    print(f"owner_name: {e}")
try:
    c.execute("ALTER TABLE charges ADD COLUMN area_m2 FLOAT DEFAULT 0.0")
    print("Added area_m2")
except Exception as e:
    print(f"area_m2: {e}")
conn.commit()
conn.close()
print("Done")

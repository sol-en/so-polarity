import sqlite3
conn = sqlite3.connect('/home/vf/Downloads/Household/zhbk_app/database.db')
c = conn.cursor()
try:
    c.execute("ALTER TABLE charges ADD COLUMN owner_name VARCHAR")
except Exception as e:
    print(f"owner_name: {e}")
try:
    c.execute("ALTER TABLE charges ADD COLUMN area_m2 FLOAT DEFAULT 0.0")
except Exception as e:
    print(f"area_m2: {e}")
conn.commit()
conn.close()
print("Done")

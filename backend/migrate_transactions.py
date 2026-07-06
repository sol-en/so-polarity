import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "zhbk_app.db")

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if comment column exists
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "comment" not in columns:
        print("Adding 'comment' column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN comment TEXT")
    
    if "counterparty" not in columns:
        print("Adding 'counterparty' column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN counterparty VARCHAR")
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

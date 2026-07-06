import csv
import os
import sqlite3
from datetime import datetime

# Database setup
DB_PATH = "zhbk_app.db"
CSV_PATH = "../Нарахування_Оплати - Нарахування.csv"

def clean_float(val):
    if not val: return 0.0
    val = val.replace(',', '.').replace('\xa0', '').replace(' ', '').strip()
    try:
        return float(val)
    except ValueError:
        return 0.0

def import_historical_2026():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data to avoid duplicates
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM charges")
    cursor.execute("DELETE FROM apartments")
    
    # 1. Ensure "Apartment Payments" category exists
    cursor.execute("SELECT id FROM categories WHERE name = 'Надходження від мешканців' AND type = 'income'")
    cat_res = cursor.fetchone()
    if cat_res:
        category_id = cat_res[0]
    else:
        cursor.execute("INSERT INTO categories (name, type) VALUES ('Надходження від мешканців', 'income')")
        category_id = cursor.lastrowid
        print(f"Created category: Надходження від мешканців (ID: {category_id})")

    # Clear existing 2026 data to avoid duplicates if re-running
    cursor.execute("DELETE FROM charges WHERE period LIKE '2026-%'")
    # We should be careful about transactions, maybe only delete those linked to apartments?
    # Actually, for now let's just add them.

    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        # Skip headers
        next(reader)
        next(reader)

        for row in reader:
            if not row or not row[0] or "Загалом" in row[0] or "Всього" in row[0]:
                continue
            
            apt_no = row[0].strip()
            owner = row[1].strip()
            area = clean_float(row[2])
            
            # Start balance 2026-01-01 (Index 463)
            # Note: in the CSV debt is positive, so balance should be negative initial_balance
            start_balance_2026 = clean_float(row[463])
            
            # Update apartment initial balance (as of 2026-01-01)
            cursor.execute("SELECT id FROM apartments WHERE number = ?", (apt_no,))
            apt_res = cursor.fetchone()
            if apt_res:
                apt_id = apt_res[0]
                cursor.execute("UPDATE apartments SET initial_balance = ? WHERE id = ?", (-start_balance_2026, apt_id))
            else:
                cursor.execute("INSERT INTO apartments (number, owner_name, area_m2, initial_balance) VALUES (?, ?, ?, ?)", 
                               (apt_no, owner, area, -start_balance_2026))
                apt_id = cursor.lastrowid

            # Months to import
            months = [
                {"period": "2026-01", "pay_date_idx": 461, "pay_amt_idx": 462, "charge_idx": 468, "maint_idx": 464, "lift_idx": 465, "gas_idx": 466, "adj_idx": 467},
                {"period": "2026-02", "pay_date_idx": 469, "pay_amt_idx": 470, "charge_idx": 476, "maint_idx": 472, "lift_idx": 473, "gas_idx": 474, "adj_idx": 475},
                {"period": "2026-03", "pay_date_idx": 477, "pay_amt_idx": 478, "charge_idx": 484, "maint_idx": 480, "lift_idx": 481, "gas_idx": 482, "adj_idx": 483},
                {"period": "2026-04", "pay_date_idx": 485, "pay_amt_idx": 486, "charge_idx": 492, "maint_idx": 488, "lift_idx": 489, "gas_idx": 490, "adj_idx": 491},
            ]

            for m in months:
                charge_amt = clean_float(row[m["charge_idx"]])
                maint_amt = clean_float(row[m["maint_idx"]])
                lift_amt = clean_float(row[m["lift_idx"]])
                gas_amt = clean_float(row[m["gas_idx"]])
                adj_amt = clean_float(row[m["adj_idx"]])
                
                pay_amt = clean_float(row[m["pay_amt_idx"]])
                pay_date_raw = row[m["pay_date_idx"]].strip()

                # Insert Charge
                cursor.execute("""
                    INSERT INTO charges (apartment_id, period, maintenance_fee, lift_fee, gas_fee, adjustment, total)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (apt_id, m["period"], maint_amt, lift_amt, gas_amt, adj_amt, charge_amt))

                # Insert Transaction if paid
                if pay_amt > 0:
                    # Parse date if possible, otherwise use start of month
                    try:
                        # Handle multiple dates or different formats
                        if "," in pay_date_raw:
                            pay_date_raw = pay_date_raw.split(",")[0].strip()
                        
                        # Some dates are DD.MM.YYYY, some DD.MM.YY
                        if len(pay_date_raw.split('.')[-1]) == 2:
                            dt = datetime.strptime(pay_date_raw, "%d.%m.%y")
                        else:
                            dt = datetime.strptime(pay_date_raw, "%d.%m.%Y")
                        date_str = dt.strftime("%Y-%m-%d")
                    except:
                        date_str = f"{m['period']}-15" # Default to mid-month
                    
                    cursor.execute("""
                        INSERT INTO transactions (date, amount, description, category_id, apartment_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (date_str, pay_amt, f"Оплата кв. {apt_no}", category_id, apt_id))

    conn.commit()
    conn.close()
    print("Historical import finished successfully.")

if __name__ == "__main__":
    import_historical_2026()

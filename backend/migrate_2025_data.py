import sqlite3
import csv
import docx
import os

db_path = '/home/vf/Downloads/Household/zhbk_app/zhbk_app.db'
csv_apt_debt_path = '/home/vf/Downloads/Household/Нарахування_Оплати - Аркуш14.csv'
docx_contractor_debt_path = '/home/vf/Downloads/Household/Copy of Акт ревізійної комісії.docx'

def main():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Delete all transactions, bank_payments, match_status_log, import_logs >= 2025-01-01
    print("Deleting records >= 2025...")
    c.execute("DELETE FROM match_status_log WHERE bank_payment_id IN (SELECT id FROM bank_payments WHERE operation_date >= '2025-01-01')")
    c.execute("DELETE FROM bank_payments WHERE operation_date >= '2025-01-01'")
    c.execute("DELETE FROM import_logs WHERE created_at >= '2025-01-01'")
    c.execute("DELETE FROM transactions WHERE date >= '2025-01-01'")
    print(f"Deleted {c.rowcount} transactions.")

    # 2. Add global initial balance
    print("Adding global initial balance...")
    cat_id = c.execute("SELECT id FROM categories WHERE \"group\"='Початковий залишок' OR name='Початковий залишок'").fetchone()
    if not cat_id:
        c.execute("INSERT INTO categories (name, type, \"group\") VALUES ('Початковий залишок', 'income', 'Початковий залишок')")
        cat_id = c.lastrowid
    else:
        cat_id = cat_id[0]

    c.execute("INSERT INTO transactions (date, amount, description, category_id, counterparty) VALUES ('2025-01-01', 48194.47, 'Вхідний залишок на 01.01.2025', ?, 'ЖБК')", (cat_id,))

    # 3. Read apartment debts and update initial balances
    print("Updating apartment initial balances...")
    with open(csv_apt_debt_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) # skip empty row if any
        next(reader) # skip header '№ кв.,Борг' (might need to handle carefully)
        for row in reader:
            if not row or not row[0].strip().isdigit(): continue
            apt_num = row[0].strip()
            debt_str = row[1].strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
            if debt_str == '' or debt_str == '-': debt_str = '0'
            debt = float(debt_str)
            
            # initial balance is negative debt
            c.execute("UPDATE apartments SET initial_balance=? WHERE number=?", (-debt, apt_num))

    # 4. Extract contractor debts and add initial balance transactions for them
    print("Extracting contractor debts...")
    doc = docx.Document(docx_contractor_debt_path)
    table = doc.tables[3] # Table 2
    for row in table.rows[2:]:
        cells = [cell.text.strip() for cell in row.cells]
        name = cells[0]
        if name == 'Разом': continue
        credit_str = cells[6].replace(',', '').replace(' ', '')
        
        if credit_str and credit_str != '0.00':
            debt = float(credit_str)
            # Find or create contractor, and set its initial_balance
            cont_id = c.execute("SELECT id FROM contractors WHERE name=?", (name,)).fetchone()
            if not cont_id:
                c.execute("INSERT INTO contractors (name, active, initial_balance) VALUES (?, 1, ?)", (name, -debt))
            else:
                c.execute("UPDATE contractors SET initial_balance=? WHERE id=?", (-debt, cont_id[0]))

    conn.commit()
    conn.close()
    print("Done!")

if __name__ == '__main__':
    main()

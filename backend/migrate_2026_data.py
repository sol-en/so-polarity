import csv
import os
import re
from datetime import datetime
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from . import models

def parse_float(val_str):
    if not val_str:
        return 0.0
    val_str = val_str.replace(',', '.').replace(' ', '').replace('\xa0', '').strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_date(date_str, fallback_period):
    date_str = date_str.strip()
    if not date_str:
        # If no date but there's a payment, we assign it to the 15th of the month
        return f"{fallback_period}-15"
    
    # Try parsing common formats
    try:
        # DD.MM.YYYY
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    try:
        # DD.MM.YY
        dt = datetime.strptime(date_str, "%d.%m.%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    # multiple dates like '05.07.2025, 10.07.2025'
    if ',' in date_str:
        parts = [p.strip() for p in date_str.split(',')]
        if parts:
            return parse_date(parts[-1], fallback_period) # take the last one

    return f"{fallback_period}-15"

def get_or_create_category(db: Session, name: str, type_str: str, group: str = None):
    cat = db.query(models.Category).filter(
        models.Category.name == name,
        models.Category.type == type_str
    ).first()
    if not cat:
        cat = models.Category(name=name, type=type_str, group=group)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    return cat

def run_migration():
    db = SessionLocal()
    
    try:
        print("Clearing test data...")
        db.query(models.Transaction).delete()
        db.query(models.Charge).delete()
        db.query(models.ApartmentLog).delete()
        db.commit()

        apt_file = "/home/vf/Downloads/Household/Нарахування_Оплати - Нарахування.csv"
        budget_file = "/home/vf/Downloads/Household/ЖБК Бюджет - Setup.csv"
        
        # Get category for apartment payments
        apt_payment_cat = get_or_create_category(db, "Надходження від мешканців", "income")

        print("Processing Нарахування file for 2026...")
        months_2026 = {
            '2026-01': 464, # січ., 2026
            '2026-02': 472, # лют., 2026
            '2026-03': 480, # бер., 2026
            '2026-04': 488, # квіт., 2026
            '2026-05': 496, # трав., 2026
        }

        with open(apt_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader) # header1
            next(reader) # header2
            
            for row in reader:
                if not row or not row[0].strip() or 'Всього' in row[0]:
                    continue
                
                apt_num = row[0].strip()
                owner_name = row[1].strip()
                area = parse_float(row[2])
                
                # Dec 2025 Debt is the initial balance for 2026
                # It is located at column 463
                initial_balance = parse_float(row[463]) if len(row) > 463 else 0.0
                # Debt is positive in CSV, meaning they owe. In DB, negative balance = debt
                initial_balance_db = -initial_balance
                
                apt = db.query(models.Apartment).filter(models.Apartment.number == apt_num).first()
                if apt:
                    apt.initial_balance = initial_balance_db
                    apt.area_m2 = area
                    if owner_name:
                        apt.owner_name = owner_name
                else:
                    apt = models.Apartment(
                        number=apt_num,
                        owner_name=owner_name,
                        area_m2=area,
                        initial_balance=initial_balance_db
                    )
                    db.add(apt)
                    db.flush()
                
                for period, start_col in months_2026.items():
                    if start_col + 7 >= len(row):
                        continue
                        
                    jbk = parse_float(row[start_col])
                    lift = parse_float(row[start_col+1])
                    gas = parse_float(row[start_col+2])
                    adj = parse_float(row[start_col+3])
                    total = parse_float(row[start_col+4])
                    
                    pay_date_str = row[start_col+5].strip()
                    paid_amt = parse_float(row[start_col+6])
                    
                    if total != 0 or jbk != 0 or lift != 0 or gas != 0 or adj != 0:
                        charge = models.Charge(
                            apartment_id=apt.id,
                            period=period,
                            owner_name=apt.owner_name,
                            area_m2=apt.area_m2,
                            maintenance_fee=jbk,
                            lift_fee=lift,
                            gas_fee=gas,
                            adjustment=adj,
                            total=total
                        )
                        db.add(charge)
                    
                    if paid_amt > 0:
                        tx_date = parse_date(pay_date_str, period)
                        tx = models.Transaction(
                            date=tx_date,
                            amount=paid_amt,
                            description=f"Оплата кв. {apt.number}",
                            category_id=apt_payment_cat.id,
                            apartment_id=apt.id
                        )
                        db.add(tx)

        db.commit()
        print("Processed apartments and payments.")

        print("Processing ЖБК Бюджет file for 2026...")
        with open(budget_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            for row in reader:
                if not row or not row[0].strip():
                    continue
                
                period_str = row[0].strip()
                if '2026' not in period_str:
                    continue
                    
                type_raw = row[1].strip()
                group = row[2].strip()
                purpose = row[3].strip()
                amount = parse_float(row[4])
                comment = row[5].strip() if len(row) > 5 else ''
                
                if amount == 0:
                    continue
                    
                # Skip 'Квартплата' as we imported per-apartment payments
                if group.lower() == 'квартплата' or purpose.lower() == 'квартплата':
                    continue
                    
                cat_type = 'expense' if 'Витрат' in type_raw else 'income'
                
                # Determine date from period "May, 2026"
                month_map = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
                month_str = period_str.split(',')[0].strip()
                month_num = month_map.get(month_str, '01')
                tx_date = f"2026-{month_num}-15" # Put middle of the month
                
                cat = get_or_create_category(db, purpose, cat_type, group)
                
                desc = purpose
                if comment:
                    desc += f" - {comment}"
                    
                tx = models.Transaction(
                    date=tx_date,
                    amount=amount, # in budget it is negative for expenses, positive for income
                    description=desc[:200], # limit length
                    category_id=cat.id
                )
                db.add(tx)
                
        db.commit()
        print("Data migration for 2026 completed successfully.")

    finally:
        db.close()

if __name__ == "__main__":
    run_migration()

import csv
import os
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from . import models

def import_apartments(file_path: str, db: Session):
    print(f"Importing apartments from {file_path}...")
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        # Skip header rows (usually first 2 rows based on snippet)
        next(reader)
        next(reader)
        
        for row in reader:
            if not row or not row[0] or "Всього" in row[0]: continue
            
            apt_no = row[0].strip()
            owner = row[1].strip()
            area_str = row[2].replace(',', '.').strip()
            try:
                area = float(area_str.replace('\xa0', '')) # handle non-breaking spaces
            except ValueError:
                area = 0.0
                
            # Initial debt - column 4 (index 3)
            debt_str = row[3].replace(',', '.').strip()
            try:
                debt = float(debt_str.replace('\xa0', ''))
            except ValueError:
                debt = 0.0
                
            apt = db.query(models.Apartment).filter(models.Apartment.number == apt_no).first()
            if not apt:
                apt = models.Apartment(
                    number=apt_no,
                    owner_name=owner,
                    area_m2=area,
                    initial_balance=-debt # Debt is negative balance for the owner
                )
                db.add(apt)
    db.commit()

def import_transactions_and_categories(file_path: str, db: Session):
    print(f"Importing transactions from {file_path}...")
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        # The file has a header like: ,Тип,Група,Призначення,Сума,Коментар
        reader = csv.DictReader(f)
        for row in reader:
            cat_name = row['Група'].strip()
            cat_type_raw = row['Тип'].strip()
            # In CSV: 'Витрати' or 'Надходження'
            cat_type = 'expense' if 'Витрат' in cat_type_raw else 'income'
            
            # Find or create category
            category = db.query(models.Category).filter(
                models.Category.name == cat_name,
                models.Category.type == cat_type
            ).first()
            
            if not category:
                category = models.Category(name=cat_name, type=cat_type)
                db.add(category)
                db.flush() # get ID
            
            # Amount: handle "-2 946.24" (space as thousands separator)
            amt_str = row['Сума'].replace(',', '.').replace(' ', '').strip()
            try:
                amt_str = amt_str.replace('\xa0', '')
                amount = float(amt_str)
            except ValueError:
                amount = 0.0
                
            # Period is in the first column (empty key in DictReader)
            date_str = row.get('', '').strip()
            
            tx = models.Transaction(
                date=date_str,
                amount=amount,
                description=f"{row['Призначення']} {row['Коментар']}".strip(),
                category_id=category.id
            )
            db.add(tx)
    db.commit()

if __name__ == "__main__":
    # Ensure tables are created
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Paths relative to the project root or absolute
        apt_file = "/home/vf/Downloads/Household/Нарахування_Оплати - Нарахування.csv"
        setup_file = "/home/vf/Downloads/Household/ЖБК Бюджет - Setup.csv"
        
        if os.path.exists(apt_file):
            import_apartments(apt_file, db)
        else:
            print(f"Warning: {apt_file} not found")
            
        if os.path.exists(setup_file):
            import_transactions_and_categories(setup_file, db)
        else:
            print(f"Warning: {setup_file} not found")
            
        print("Import completed successfully.")
    finally:
        db.close()

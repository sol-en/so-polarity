import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'zhbk_app'))
from backend.database import SessionLocal
from backend import models

db = SessionLocal()
try:
    tx_count = db.query(models.Transaction).filter(models.Transaction.apartment_id != None).count()
    print(f"Transactions with apartment_id: {tx_count}")
    
    if tx_count > 0:
        tx = db.query(models.Transaction).filter(models.Transaction.apartment_id != None).first()
        print(f"Sample transaction: date={tx.date}, amount={tx.amount}, apt_id={tx.apartment_id}")
    
    cat_names = db.query(models.Category.name).distinct().all()
    print(f"Categories: {[c[0] for c in cat_names]}")
    
    total_tx = db.query(models.Transaction).count()
    print(f"Total transactions: {total_tx}")
finally:
    db.close()

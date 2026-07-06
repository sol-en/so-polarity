import sqlite3
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend import models

engine = create_engine("sqlite:///zhbk_app.db")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    apartments = db.query(models.Apartment).all()
    print(f"Found {len(apartments)} apartments")
    for apt in apartments:
        total_charges = db.query(func.sum(models.Charge.total)).filter(models.Charge.apartment_id == apt.id).scalar() or 0.0
        total_payments = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.apartment_id == apt.id).scalar() or 0.0
        # Check for None values
        init_bal = apt.initial_balance if apt.initial_balance is not None else 0.0
        apt.current_balance = init_bal - total_charges + total_payments
        print(f"Apt {apt.number}: {apt.current_balance}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()

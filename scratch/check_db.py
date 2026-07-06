from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from backend.models import Base, Apartment, Charge, Transaction

engine = create_engine("sqlite:///zhbk_app.db")
Session = sessionmaker(bind=engine)
session = Session()

print(f"Apartments count: {session.query(Apartment).count()}")
print(f"Charges count: {session.query(Charge).count()}")
print(f"Transactions count: {session.query(Transaction).count()}")

first_apt = session.query(Apartment).first()
if first_apt:
    print(f"First apartment: {first_apt.number}, {first_apt.owner_name}, initial_balance: {first_apt.initial_balance}")

# Check charges periods
periods = session.query(Charge.period).distinct().all()
print(f"Periods in charges: {[p[0] for p in periods]}")

from backend.database import SessionLocal
from backend.models import Apartment

db = SessionLocal()
apts = db.query(Apartment).limit(10).all()
for a in apts:
    print(f"Apt {a.number}: lift_exemption={a.has_lift_exemption}")
db.close()

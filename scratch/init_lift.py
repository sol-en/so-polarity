from backend.database import SessionLocal
from backend.models import Apartment

db = SessionLocal()
apts = db.query(Apartment).all()
# TZ: 1st floor apartments (1-4) often don't have lift access
tz_exempt = ['1', '2', '3', '4'] 

for a in apts:
    if a.number in tz_exempt:
        a.has_lift_exemption = True
    else:
        a.has_lift_exemption = False

db.commit()
print(f"Updated {len(apts)} apartments. Exempted: {tz_exempt}")
db.close()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Apartment])
def get_apartments(db: Session = Depends(get_db)):
    apartments = db.query(models.Apartment).all()
    user_access_map = {ua.apartment_id: ua.email for ua in db.query(models.UserAccess).filter(models.UserAccess.role == 'resident').all()}
    for apt in apartments:
        total_charges = db.query(func.sum(models.Charge.total)).filter(models.Charge.apartment_id == apt.id).scalar() or 0.0
        total_payments = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.apartment_id == apt.id).scalar() or 0.0
        apt.current_balance = apt.initial_balance - total_charges + total_payments
        apt.email = user_access_map.get(apt.id)
    return apartments

@router.get("/{apt_id}", response_model=schemas.Apartment)
def get_apartment(apt_id: int, db: Session = Depends(get_db)):
    apt = db.query(models.Apartment).filter(models.Apartment.id == apt_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Apartment not found")
    
    total_charges = db.query(func.sum(models.Charge.total)).filter(models.Charge.apartment_id == apt.id).scalar() or 0.0
    total_payments = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.apartment_id == apt.id).scalar() or 0.0
    apt.current_balance = apt.initial_balance - total_charges + total_payments
    ua = db.query(models.UserAccess).filter(models.UserAccess.apartment_id == apt.id, models.UserAccess.role == 'resident').first()
    apt.email = ua.email if ua else None
    return apt

@router.post("/", response_model=schemas.Apartment)
def create_apartment(apt: schemas.ApartmentCreate, db: Session = Depends(get_db)):
    db_apt = models.Apartment(**apt.model_dump())
    db.add(db_apt)
    db.commit()
    db.refresh(db_apt)
    return db_apt

@router.get("/{apt_id}/logs", response_model=List[schemas.ApartmentLog])
def get_apartment_logs(apt_id: int, db: Session = Depends(get_db)):
    return db.query(models.ApartmentLog).filter(models.ApartmentLog.apartment_id == apt_id).order_by(models.ApartmentLog.date.desc()).all()

@router.post("/{apt_id}/logs", response_model=schemas.ApartmentLog)
def create_apartment_log(apt_id: int, log: schemas.ApartmentLogCreate, db: Session = Depends(get_db)):
    apt = db.query(models.Apartment).filter(models.Apartment.id == apt_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Apartment not found")
    
    # Handle state updates based on log type
    if log.type == 'owner_change':
        log.old_value = apt.owner_name
        apt.owner_name = log.new_value
    elif log.type == 'area_change':
        log.old_value = str(apt.area_m2)
        try:
            apt.area_m2 = float(log.new_value)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid area value")
    
    db_log = models.ApartmentLog(**log.model_dump())
    db_log.apartment_id = apt_id
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@router.post("/{apt_id}/toggle-lift")
def toggle_lift(apt_id: int, db: Session = Depends(get_db)):
    apt = db.query(models.Apartment).filter(models.Apartment.id == apt_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Apartment not found")
    apt.has_lift_exemption = not apt.has_lift_exemption
    db.commit()
    return {"has_lift": not apt.has_lift_exemption}

from pydantic import BaseModel
class EmailUpdate(BaseModel):
    email: str | None

@router.post("/{apt_id}/email")
def update_email(apt_id: int, req: EmailUpdate, db: Session = Depends(get_db)):
    apt = db.query(models.Apartment).filter(models.Apartment.id == apt_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Apartment not found")
    
    ua = db.query(models.UserAccess).filter(models.UserAccess.apartment_id == apt_id, models.UserAccess.role == 'resident').first()
    if req.email:
        if ua:
            ua.email = req.email
        else:
            new_ua = models.UserAccess(email=req.email, role='resident', apartment_id=apt_id)
            db.add(new_ua)
    else:
        if ua:
            db.delete(ua)
            
    db.commit()
    return {"status": "ok"}


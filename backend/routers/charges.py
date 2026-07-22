from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Charge])
def get_charges(period: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Charge)
    if period:
        query = query.filter(models.Charge.period == period)
    return query.all()


def calculate_charges_for_period(period: str, db: Session):
    """Calculate resident charges for a single period (YYYY-MM). Reusable by other modules."""
    tariffs = db.query(models.Tariff).filter(models.Tariff.is_active == True).all()
    t_map = {t.name: t for t in tariffs}
    
    maintenance_tariff = t_map.get("Maintenance", t_map.get("Утримання", None))
    lift_tariff = t_map.get("Lift", t_map.get("Ліфт", None))
    gas_tariff = t_map.get("Gas", t_map.get("Газ", None))
    
    if not maintenance_tariff:
        return  # Can't calculate without maintenance tariff
    
    apartments = db.query(models.Apartment).all()
    
    for apt in apartments:
        m_fee = round((apt.area_m2 or 0.0) * maintenance_tariff.value, 2)
        l_fee = 0.0
        if lift_tariff and not apt.has_lift_exemption:
            l_fee = round((apt.area_m2 or 0.0) * lift_tariff.value, 2)
            
        g_fee = 0.0
        if gas_tariff:
            g_fee = round((apt.area_m2 or 0.0) * gas_tariff.value, 2)
            
        adj_amount = db.query(func.sum(models.ApartmentLog.amount)).filter(
            models.ApartmentLog.apartment_id == apt.id,
            models.ApartmentLog.type == 'adjustment',
            models.ApartmentLog.period == period
        ).scalar() or 0.0
        
        total = round(m_fee + l_fee + g_fee + adj_amount, 2)
        
        db_charge = db.query(models.Charge).filter(
            models.Charge.apartment_id == apt.id,
            models.Charge.period == period
        ).first()
        
        if db_charge:
            db_charge.owner_name = apt.owner_name
            db_charge.area_m2 = apt.area_m2
            db_charge.maintenance_fee = m_fee
            db_charge.lift_fee = l_fee
            db_charge.gas_fee = g_fee
            db_charge.adjustment = adj_amount
            db_charge.total = total
        else:
            db_charge = models.Charge(
                apartment_id=apt.id,
                period=period,
                owner_name=apt.owner_name,
                area_m2=apt.area_m2,
                maintenance_fee=m_fee,
                lift_fee=l_fee,
                gas_fee=g_fee,
                adjustment=adj_amount,
                total=total
            )
            db.add(db_charge)
    
    db.commit()


@router.post("/calculate")
def calculate_charges(req: schemas.CalculationRequest, db: Session = Depends(get_db)):
    calculate_charges_for_period(req.period, db)
    apartments = db.query(models.Apartment).all()
    return {"message": f"Charges calculated for {len(apartments)} apartments for period {req.period}"}

from ..auth_utils import get_current_user, CurrentUser

@router.post("/report", response_model=List[schemas.ApartmentReport])
def get_charges_report(
    req: schemas.ReportRequest, 
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    print("DEBUG REPORT REQ:", req.start_period, req.end_period)
    if current_user.role == 'resident':
        apartments = db.query(models.Apartment).filter(models.Apartment.id == current_user.apartment_id).all()
    else:
        apartments = db.query(models.Apartment).all()

    
    results = []
    for apt in apartments:
        past_charges = db.query(func.sum(models.Charge.total)).filter(
            models.Charge.apartment_id == apt.id,
            models.Charge.period < req.start_period
        ).scalar() or 0.0
        
        past_payments = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.apartment_id == apt.id,
            models.Transaction.date < req.start_period
        ).scalar() or 0.0
        
        start_balance = (apt.initial_balance or 0.0) - past_charges + past_payments
        
        charges_in_range = db.query(models.Charge).filter(
            models.Charge.apartment_id == apt.id,
            models.Charge.period >= req.start_period,
            models.Charge.period <= req.end_period
        ).order_by(models.Charge.period).all()
        
        c_map = {c.period: c for c in charges_in_range}
        
        curr_year, curr_month = map(int, req.start_period.split("-"))
        end_year, end_month = map(int, req.end_period.split("-"))
        
        monthly_details = []
        total_charges = 0.0
        total_payments = 0.0
        
        while (curr_year < end_year) or (curr_year == end_year and curr_month <= end_month):
            p_str = f"{curr_year:04d}-{curr_month:02d}"
            ch = c_map.get(p_str)
            
            pmt = db.query(func.sum(models.Transaction.amount)).filter(
                models.Transaction.apartment_id == apt.id,
                models.Transaction.date.like(f"{p_str}%")
            ).scalar() or 0.0
            
            ch_val = ch.total if ch else 0.0
            adj_val = ch.adjustment if ch else 0.0
            
            monthly_details.append(schemas.MonthlyDetail(
                period=p_str,
                maintenance_fee=ch.maintenance_fee if ch else 0.0,
                lift_fee=ch.lift_fee if ch else 0.0,
                gas_fee=ch.gas_fee if ch else 0.0,
                charge=ch_val,
                payment=pmt,
                adjustment=adj_val
            ))
            
            total_charges += ch_val
            total_payments += pmt
            
            curr_month += 1
            if curr_month > 12:
                curr_month = 1
                curr_year += 1
            
        end_balance = start_balance - total_charges + total_payments
        
        results.append(schemas.ApartmentReport(
            apartment_id=apt.id,
            apartment_number=apt.number,
            owner_name=apt.owner_name,
            area_m2=apt.area_m2,
            email=None,
            start_balance=start_balance,
            end_balance=end_balance,
            total_charges=total_charges,
            total_payments=total_payments,
            monthly_details=monthly_details
        ))
        
    return results

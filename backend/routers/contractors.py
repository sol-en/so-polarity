from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Contractor])
def get_contractors(db: Session = Depends(get_db)):
    return db.query(models.Contractor).options(
        joinedload(models.Contractor.default_category),
        joinedload(models.Contractor.obligations)
    ).order_by(models.Contractor.name).all()

@router.post("/", response_model=schemas.Contractor)
def create_contractor(contractor: schemas.ContractorBase, db: Session = Depends(get_db)):
    existing = db.query(models.Contractor).filter(models.Contractor.name == contractor.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Контрагент з таким ім'ям вже існує")
    db_cont = models.Contractor(**contractor.model_dump())
    db.add(db_cont)
    db.commit()
    db.refresh(db_cont)
    return db_cont

@router.put("/{contractor_id}", response_model=schemas.Contractor)
def update_contractor(contractor_id: int, contractor: schemas.ContractorBase, db: Session = Depends(get_db)):
    db_cont = db.query(models.Contractor).filter(models.Contractor.id == contractor_id).first()
    if not db_cont:
        raise HTTPException(status_code=404, detail="Контрагента не знайдено")
    db_cont.name = contractor.name
    db_cont.default_category_id = contractor.default_category_id
    db_cont.active = contractor.active
    db_cont.initial_balance = contractor.initial_balance
    db_cont.initial_balance_date = contractor.initial_balance_date
    db.commit()
    db.refresh(db_cont)
    return db_cont

@router.delete("/{contractor_id}")
def delete_contractor(contractor_id: int, db: Session = Depends(get_db)):
    db_cont = db.query(models.Contractor).filter(models.Contractor.id == contractor_id).first()
    if not db_cont:
        raise HTTPException(status_code=404, detail="Контрагента не знайдено")
    db.delete(db_cont)
    db.commit()
    return {"ok": True}

# --- Obligations ---

@router.get("/{contractor_id}/obligations", response_model=List[schemas.ContractorObligationResponse])
def get_contractor_obligations(contractor_id: int, db: Session = Depends(get_db)):
    return db.query(models.ContractorObligation).filter(models.ContractorObligation.contractor_id == contractor_id).all()

@router.post("/{contractor_id}/obligations", response_model=schemas.ContractorObligationResponse)
def create_contractor_obligation(contractor_id: int, ob: schemas.ContractorObligationCreate, db: Session = Depends(get_db)):
    db_ob = models.ContractorObligation(**ob.model_dump())
    db_ob.contractor_id = contractor_id
    db.add(db_ob)
    db.commit()
    db.refresh(db_ob)
    return db_ob

@router.put("/{contractor_id}/obligations/{ob_id}", response_model=schemas.ContractorObligationResponse)
def update_contractor_obligation(contractor_id: int, ob_id: int, ob: schemas.ContractorObligationCreate, db: Session = Depends(get_db)):
    db_ob = db.query(models.ContractorObligation).filter(models.ContractorObligation.id == ob_id, models.ContractorObligation.contractor_id == contractor_id).first()
    if not db_ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    
    for k, v in ob.model_dump().items():
        setattr(db_ob, k, v)
        
    db.commit()
    db.refresh(db_ob)
    return db_ob

@router.delete("/{contractor_id}/obligations/{ob_id}")
def delete_contractor_obligation(contractor_id: int, ob_id: int, db: Session = Depends(get_db)):
    db_ob = db.query(models.ContractorObligation).filter(models.ContractorObligation.id == ob_id, models.ContractorObligation.contractor_id == contractor_id).first()
    if not db_ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    # Clean up associated charges
    db.query(models.ContractorCharge).filter(models.ContractorCharge.obligation_id == ob_id).delete()
    db.delete(db_ob)
    db.commit()
    return {"ok": True}

# --- Accruals Engine ---

import re
from datetime import datetime

def parse_period_from_desc(desc: str) -> str:
    if not desc:
        return None
    # match basic YYYY-MM
    m = re.search(r'(20\d{2})-(0[1-9]|1[0-2])', desc)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    
    months_ua = {
        'січен': '01', 'лют': '02', 'берез': '03', 'квіт': '04',
        'трав': '05', 'черв': '06', 'лип': '07', 'серп': '08',
        'верес': '09', 'жовт': '10', 'листоп': '11', 'груд': '12'
    }
    
    lower_desc = desc.lower()
    for ua_m, m_num in months_ua.items():
        if ua_m in lower_desc:
            year_match = re.search(r'(20\d{2})', desc)
            if year_match:
                return f"{year_match.group(1)}-{m_num}"
    
    return None

def ensure_accruals_up_to_period(period: str, db: Session):
    """Automatically run accruals for all months from the earliest obligation start up to the target period."""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    current_month = datetime.now().strftime("%Y-%m")
    target_period = min(period, current_month)
    
    # 1. Find the earliest valid_from date among all obligations
    earliest_ob = db.query(models.ContractorObligation).order_by(models.ContractorObligation.valid_from).first()
    if not earliest_ob:
        return
        
    start_month_str = earliest_ob.valid_from # e.g. "2025-01"
    
    # Parse dates
    try:
        start_date = datetime.strptime(start_month_str, "%Y-%m").date()
        target_date = datetime.strptime(target_period, "%Y-%m").date()
    except ValueError:
        return
        
    # Generate all months in between and run accruals
    curr = start_date
    while curr <= target_date:
        month_str = curr.strftime("%Y-%m")
        run_contractor_accruals(month_str, db)
        curr += relativedelta(months=1)


@router.get("/settlements")
def get_contractor_settlements(start_period: str = None, end_period: str = None, period: str = None, db: Session = Depends(get_db)):
    """Get settlement status for all contractors for a specific period range (YYYY-MM to YYYY-MM)."""
    # Backward compatibility
    if period:
        if not start_period:
            start_period = period
        if not end_period:
            end_period = period
            
    if not end_period:
        end_period = datetime.now().strftime("%Y-%m")
    if not start_period:
        start_period = end_period

    # Cap auto-accruals at the current month to avoid generating future planned accruals
    current_month = datetime.now().strftime("%Y-%m")
    accrual_target = min(end_period, current_month)
    
    ensure_accruals_up_to_period(accrual_target, db)
    
    contractors = db.query(models.Contractor).all()
    results = []
    
    # Calculate start period bounds for query
    start_year, start_month = map(int, start_period.split("-"))
    start_date_str = f"{start_period}-01"
    
    # Calculate end period bounds for query
    end_year, end_month = map(int, end_period.split("-"))
    if end_month == 12:
        next_year = end_year + 1
        next_month = 1
    else:
        next_year = end_year
        next_month = end_month + 1
    next_month_start = f"{next_year}-{next_month:02d}-01"
    
    from sqlalchemy import func
    
    for c in contractors:
        # 1. Debt before start_period (Initial balance + accrued before - paid before)
        accrued_before = db.query(func.sum(models.ContractorCharge.accrued_amount)).filter(
            models.ContractorCharge.contractor_id == c.id,
            models.ContractorCharge.period < start_period
        ).scalar() or 0.0
        
        paid_before = db.query(func.sum(func.abs(models.Transaction.amount))).filter(
            models.Transaction.contractor_id == c.id,
            models.Transaction.date < start_date_str
        ).scalar() or 0.0
        
        initial_balance = c.initial_balance or 0.0
        if c.initial_balance_date and c.initial_balance_date >= start_period:
            initial_balance = 0.0
            
        debt_before = initial_balance + accrued_before - paid_before
        
        # 2. Accrued in period (between start_period and end_period)
        accrued_in_period = db.query(func.sum(models.ContractorCharge.accrued_amount)).filter(
            models.ContractorCharge.contractor_id == c.id,
            models.ContractorCharge.period >= start_period,
            models.ContractorCharge.period <= end_period
        ).scalar() or 0.0
        
        # 3. Paid in period (between start_date and next_month_start)
        paid_in_period = db.query(func.sum(func.abs(models.Transaction.amount))).filter(
            models.Transaction.contractor_id == c.id,
            models.Transaction.date >= start_date_str,
            models.Transaction.date < next_month_start
        ).scalar() or 0.0
        
        # 4. Debt at the end of period
        debt_end = debt_before + accrued_in_period - paid_in_period
        
        # Get active obligations in end_period
        obs = db.query(models.ContractorObligation).filter(
            models.ContractorObligation.contractor_id == c.id,
            models.ContractorObligation.valid_from <= end_period
        ).all()
        active_obs = [ob for ob in obs if not ob.valid_to or ob.valid_to >= end_period]
        
        if not active_obs and accrued_in_period == 0 and debt_before == 0 and debt_end == 0:
            continue
            
        status = '✅'
        if debt_end > 0:
            # If end_period has accrued amount, compare debt against monthly accrued
            monthly_ref = accrued_in_period
            if monthly_ref <= 0 and active_obs:
                # Fallback to active obligation sum
                fixed_obs = [ob for ob in active_obs if ob.amount_type == 'fixed']
                monthly_ref = sum(ob.fixed_amount for ob in fixed_obs)
            if monthly_ref > 0 and debt_end > (monthly_ref * 0.1):
                status = '🔴'
            else:
                status = '🟡'
                
        is_income = False
        if c.default_category and c.default_category.type == 'income':
            is_income = True
            
        results.append({
            "contractor_id": c.id,
            "contractor_name": c.name,
            "is_income": is_income,
            "balance_start": round(debt_before, 2),
            "accrued": round(accrued_in_period, 2),
            "paid": round(paid_in_period, 2),
            "debt": round(debt_end, 2),
            "status": status
        })
        
    return results

@router.post("/accrue")
def run_contractor_accruals(period: str, db: Session = Depends(get_db)):
    """
    Run accruals for the given period YYYY-MM.
    """
    # Get ALL obligations (not just active ones for this period)
    all_obligations = db.query(models.ContractorObligation).all()
    
    for ob in all_obligations:
        is_active = ob.valid_from <= period and (not ob.valid_to or ob.valid_to >= period)
        
        existing = db.query(models.ContractorCharge).filter(
            models.ContractorCharge.obligation_id == ob.id,
            models.ContractorCharge.period == period
        ).first()
        
        if not is_active or ob.amount_type == 'calculated':
            # Obligation doesn't cover this period or is calculated (plan only) — remove any stale charge
            if existing:
                db.delete(existing)
            continue
            
        # Active obligation: create or update charge
        accrued = 0.0
        if ob.amount_type == 'fixed':
            accrued = ob.fixed_amount or 0.0
            
        if existing:
            existing.accrued_amount = accrued
        else:
            new_charge = models.ContractorCharge(
                contractor_id=ob.contractor_id,
                obligation_id=ob.id,
                period=period,
                accrued_amount=accrued,
                paid_amount=0.0
            )
            db.add(new_charge)
            
    db.commit() # Save all charges before reconciling
    
    # FIFO reconciliation per contractor
    contractor_ids = {ob.contractor_id for ob in all_obligations}
    for c_id in contractor_ids:
        # Get total paid (absolute amount to handle both income and expenses)
        from sqlalchemy import func
        total_paid = db.query(func.sum(func.abs(models.Transaction.amount))).filter(
            models.Transaction.contractor_id == c_id
        ).scalar() or 0.0
        
        # Get all charges in chronological order
        charges = db.query(models.ContractorCharge).filter(
            models.ContractorCharge.contractor_id == c_id
        ).order_by(models.ContractorCharge.period).all()
        
        for ch in charges:
            if total_paid >= ch.accrued_amount:
                ch.paid_amount = ch.accrued_amount
                total_paid -= ch.accrued_amount
            else:
                ch.paid_amount = round(total_paid, 2)
                total_paid = 0.0
                
    db.commit()
    return {"status": "ok", "message": "Accruals and FIFO reconciliation completed"}

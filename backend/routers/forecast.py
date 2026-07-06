from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime
from dateutil.relativedelta import relativedelta
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/activities", response_model=List[schemas.PlannedActivityResponse])
def get_planned_activities(db: Session = Depends(get_db)):
    return db.query(models.PlannedActivity).order_by(models.PlannedActivity.planned_month).all()

@router.post("/activities", response_model=schemas.PlannedActivityResponse)
def create_activity(act: schemas.PlannedActivityCreate, db: Session = Depends(get_db)):
    db_act = models.PlannedActivity(**act.model_dump())
    db.add(db_act)
    db.commit()
    db.refresh(db_act)
    return db_act

@router.delete("/activities/{act_id}")
def delete_activity(act_id: int, db: Session = Depends(get_db)):
    act = db.query(models.PlannedActivity).filter(models.PlannedActivity.id == act_id).first()
    if act:
        db.delete(act)
        db.commit()
    return {"ok": True}

@router.put("/activities/{act_id}", response_model=schemas.PlannedActivityResponse)
def update_activity(act_id: int, act_data: schemas.PlannedActivityUpdate, db: Session = Depends(get_db)):
    act = db.query(models.PlannedActivity).filter(models.PlannedActivity.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    if act_data.planned_amount is not None:
        act.planned_amount = act_data.planned_amount
    if act_data.planned_month is not None:
        act.planned_month = act_data.planned_month
    db.commit()
    db.refresh(act)
    return act

@router.get("/dashboard")
def get_forecast(start_month: str, end_month: str, db: Session = Depends(get_db)):
    """
    Generate cash flow forecast.
    start_month, end_month in YYYY-MM
    """
    # Parse dates
    try:
        start_date = datetime.strptime(start_month, "%Y-%m").date()
        end_date = datetime.strptime(end_month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM")

    # Generate months list
    months = []
    curr = start_date
    while curr <= end_date:
        months.append(curr.strftime("%Y-%m"))
        curr += relativedelta(months=1)

    # 1. Income Residents (Smart Forecast)
    # Simple version for now: sum of area * tariff * payment ratio
    tariffs = db.query(models.Tariff).filter(models.Tariff.is_active == True).all()
    t_map = {t.name: t for t in tariffs}
    maintenance_tariff = t_map.get("Maintenance", t_map.get("Утримання"))
    lift_tariff = t_map.get("Lift", t_map.get("Ліфт"))
    gas_tariff = t_map.get("Gas", t_map.get("Газ"))
    
    apartments = db.query(models.Apartment).all()
    
    # Calculate payment ratios (last 12 months)
    today = datetime.now()
    twelve_months_ago = (today - relativedelta(months=12)).strftime("%Y-%m")
    
    total_expected_residents_current = 0
    total_expected_residents_a = 0 # Scenario A (8.0)
    total_expected_residents_b = 0 # Scenario B (12.0)
    
    for apt in apartments:
        # Get payments count in last 12 months
        payments = db.query(models.Transaction).filter(
            models.Transaction.apartment_id == apt.id,
            models.Transaction.date >= twelve_months_ago,
            models.Transaction.amount > 0
        ).count()
        
        ratio = 0.0
        if payments >= 9:
            ratio = 1.0 # 🟢 regular
        elif payments >= 3:
            ratio = payments / 12.0 # 🟡 irregular
        else:
            ratio = 0.0 # 🔴 non_payer
            
        area = apt.area_m2 or 0.0
        
        # Current scenario
        m_fee = area * (maintenance_tariff.value if maintenance_tariff else 0)
        l_fee = 0 if apt.has_lift_exemption else (area * (lift_tariff.value if lift_tariff else 0))
        g_fee = area * (gas_tariff.value if gas_tariff else 0)
        total_monthly_charge = m_fee + l_fee + g_fee
        total_expected_residents_current += (total_monthly_charge * ratio)
        
        # Scenario A (8.0 for maintenance)
        total_expected_residents_a += ((area * 8.0 + l_fee + g_fee) * ratio)
        
        # Scenario B (12.0 for maintenance)
        total_expected_residents_b += ((area * 12.0 + l_fee + g_fee) * ratio)
        
    total_expected_residents_current = round(total_expected_residents_current, 2)
    total_expected_residents_a = round(total_expected_residents_a, 2)
    total_expected_residents_b = round(total_expected_residents_b, 2)

    # 2. Get active obligations
    obligations = db.query(models.ContractorObligation).filter(
        models.ContractorObligation.include_in_forecast == 1
    ).all()
    
    # 3. Get planned activities
    activities = db.query(models.PlannedActivity).filter(
        models.PlannedActivity.include_in_forecast == 1,
        models.PlannedActivity.planned_month >= start_month,
        models.PlannedActivity.planned_month <= end_month
    ).all()
    
    activities_by_month = {}
    for act in activities:
        activities_by_month[act.planned_month] = activities_by_month.get(act.planned_month, 0) + act.planned_amount

    # Get Contractor Debts (FIFO based unpaid)
    contractor_debts = {}
    contractor_charges = db.query(models.ContractorCharge).all()
    for ch in contractor_charges:
        debt = ch.accrued_amount - ch.paid_amount
        if debt > 0:
            contractor_debts[ch.contractor_id] = contractor_debts.get(ch.contractor_id, 0) + debt

    # Build forecast
    forecast = []
    
    # In month 1, we pay all debt
    is_first_month = True
    
    for month in months:
        income_contractors = 0
        expense_obligations = 0
        
        for ob in obligations:
            if ob.valid_from <= month and (not ob.valid_to or ob.valid_to >= month):
                # Is it income or expense? Check category
                is_income = False
                if ob.category and ob.category.type == 'income':
                    is_income = True
                
                amt = ob.fixed_amount or 0.0 # TODO seasonal
                if is_income:
                    income_contractors += amt
                else:
                    expense_obligations += amt
                    
        expense_debt_repayment = 0
        if is_first_month:
            is_first_month = False
            
        expense_activities = activities_by_month.get(month, 0.0)
        
        # We will return the base scenario in 'income_residents' and include scenarios inside
        item = {
            "month": month,
            "income_expected": round(total_expected_residents_current + income_contractors, 2),
            "income_residents": total_expected_residents_current,
            "income_contractors": round(income_contractors, 2),
            "expense_fixed": round(expense_obligations + expense_debt_repayment + expense_activities, 2),
            "expense_obligations": round(expense_obligations, 2),
            "expense_debt_repayment": round(expense_debt_repayment, 2),
            "expense_activities": round(expense_activities, 2),
            "net": round((total_expected_residents_current + income_contractors) - (expense_obligations + expense_debt_repayment + expense_activities), 2),
            # Scenarios
            "scenarios": {
                "base": total_expected_residents_current,
                "a": total_expected_residents_a,
                "b": total_expected_residents_b
            }
        }
        forecast.append(item)
        
    return forecast

@router.post("/custom")
def generate_custom_forecast(req: schemas.ForecastScenarioRequest, db: Session = Depends(get_db)):
    try:
        start_date = datetime.strptime(req.start_month, "%Y-%m").date()
        end_date = datetime.strptime(req.end_month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM")

    months = []
    curr = start_date
    while curr <= end_date:
        months.append(curr.strftime("%Y-%m"))
        curr += relativedelta(months=1)

    tariffs = db.query(models.Tariff).filter(models.Tariff.is_active == True).all()
    t_map = {t.name: t for t in tariffs}
    lift_tariff = t_map.get("Lift", t_map.get("Ліфт"))
    gas_tariff = t_map.get("Gas", t_map.get("Газ"))
    
    apartments = db.query(models.Apartment).all()
    total_expected_residents = 0
    
    for apt in apartments:
        area = apt.area_m2 or 0.0
        m_fee = area * req.resident_tariff
        l_fee = 0 if apt.has_lift_exemption else (area * (lift_tariff.value if lift_tariff else 0))
        g_fee = area * (gas_tariff.value if gas_tariff else 0)
        total_expected_residents += ((m_fee + l_fee + g_fee) * req.collection_rate)
        
    total_expected_residents = round(total_expected_residents, 2)

    obligations = db.query(models.ContractorObligation).filter(
        models.ContractorObligation.include_in_forecast == 1
    ).all()
    
    activities = db.query(models.PlannedActivity).filter(
        models.PlannedActivity.include_in_forecast == 1,
        models.PlannedActivity.planned_month >= req.start_month,
        models.PlannedActivity.planned_month <= req.end_month
    ).all()
    
    activities_by_month = {}
    for act in activities:
        activities_by_month[act.planned_month] = activities_by_month.get(act.planned_month, 0) + act.planned_amount

    forecast = []
    is_first_month = True
    cumulative = req.starting_balance
    
    for month in months:
        income_contractors = 0
        expense_obligations = 0
        
        for ob in obligations:
            if ob.valid_from <= month and (not ob.valid_to or ob.valid_to >= month):
                is_income = ob.category and ob.category.type == 'income'
                amt = ob.fixed_amount or 0.0 
                if is_income:
                    income_contractors += amt
                else:
                    expense_obligations += amt
                    
        expense_debt_repayment = 0
        if is_first_month:
            is_first_month = False
            
        expense_activities = activities_by_month.get(month, 0.0)
        
        total_income = total_expected_residents + income_contractors
        total_expense = expense_obligations + expense_debt_repayment + expense_activities
        net = total_income - total_expense
        cumulative += net
        
        item = {
            "month": month,
            "income_total": round(total_income, 2),
            "income_residents": total_expected_residents,
            "income_contractors": round(income_contractors, 2),
            "expense_total": round(total_expense, 2),
            "expense_obligations": round(expense_obligations, 2),
            "expense_debt_repayment": round(expense_debt_repayment, 2),
            "expense_activities": round(expense_activities, 2),
            "net": round(net, 2),
            "cumulative": round(cumulative, 2)
        }
        forecast.append(item)
        
    return forecast

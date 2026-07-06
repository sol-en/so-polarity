from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime
import calendar
from ..database import get_db
from .. import models, schemas

router = APIRouter()

def parse_date(date_str: str):
    """Parses various date formats used in the database."""
    if not date_str:
        return None
    
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        pass
    
    # Try "Month, Year" (e.g., "May, 2026")
    try:
        # Ukrainian/English months mapping might be needed if they are localized, 
        # but the CSV snippet showed English "May, 2026", "Apr, 2026"
        return datetime.strptime(date_str, "%b, %Y")
    except ValueError:
        pass
        
    return None

@router.get("/stats")
def get_dashboard_stats(start_date: str = '2026-01-01', end_date: str = '2026-12-31', db: Session = Depends(get_db)):
    # Auto-calculate resident charges for all months in the period (up to current month)
    from .charges import calculate_charges_for_period
    
    s_dt = datetime.strptime(start_date, "%Y-%m-%d")
    e_dt = datetime.strptime(end_date, "%Y-%m-%d")
    current_month = datetime.now().strftime("%Y-%m")
    
    # Generate months and auto-calculate charges
    calc_y, calc_m = s_dt.year, s_dt.month
    while (calc_y < e_dt.year) or (calc_y == e_dt.year and calc_m <= e_dt.month):
        period_str = f"{calc_y}-{calc_m:02d}"
        if period_str > current_month:
            break  # Don't calculate future months
        # Only calculate if no charges exist yet for this period
        existing_count = db.query(models.Charge).filter(models.Charge.period == period_str).count()
        if existing_count == 0:
            calculate_charges_for_period(period_str, db)
        calc_m += 1
        if calc_m > 12:
            calc_m = 1
            calc_y += 1

    # 1. Fetch all categories to identify income/expense and 'Квартплата'
    categories = db.query(models.Category).all()
    cat_map = {c.id: c for c in categories}
    kvartplata_cat_id = next((c.id for c in categories if c.name == 'Квартплата'), None)
    
    # 2. Fetch all transactions
    all_txs = db.query(models.Transaction).all()
    
    # 3. Fetch all apartments to calculate debt dynamics
    apartments = db.query(models.Apartment).all()
    
    # 4. Fetch all charges
    all_charges = db.query(models.Charge).all()
    
    # Generate months array based on start_date and end_date
    s_dt = datetime.strptime(start_date, "%Y-%m-%d")
    e_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    months = []
    curr_y = s_dt.year
    curr_m = s_dt.month
    while (curr_y < e_dt.year) or (curr_y == e_dt.year and curr_m <= e_dt.month):
        months.append(f"{curr_y}-{curr_m:02d}")
        curr_m += 1
        if curr_m > 12:
            curr_m = 1
            curr_y += 1
            
    if not months:
        months = [s_dt.strftime("%Y-%m")]
        
    inflow_data = {m: 0.0 for m in months}
    expenses_data = {m: 0.0 for m in months}
    
    # Process transactions
    for tx in all_txs:
        dt = parse_date(tx.date)
        if not dt: continue
        
        p_str = dt.strftime("%Y-%m")
        is_in_range = s_dt <= dt <= e_dt
        
        cat = cat_map.get(tx.category_id)
        if not cat: continue
        
        if is_in_range:
            if tx.apartment_id is not None:
                if p_str in inflow_data: inflow_data[p_str] += tx.amount
            elif cat.name != 'Квартплата' and cat.group != 'Початковий залишок':
                if cat.type == 'income':
                    if p_str in inflow_data: inflow_data[p_str] += tx.amount
                else:
                    if p_str in expenses_data: expenses_data[p_str] += abs(tx.amount)
    
    cumulative_balance = 0.0
    # Calculate starting balance (pre-period)
    for tx in all_txs:
        dt = parse_date(tx.date)
        if not dt: continue
        
        cat = cat_map.get(tx.category_id)
        if not cat: continue
        
        if dt < s_dt or cat.group == 'Початковий залишок':
            if tx.apartment_id is not None:
                cumulative_balance += tx.amount
            elif cat.name != 'Квартплата':
                if cat.type == 'income':
                    cumulative_balance += tx.amount
                else:
                    cumulative_balance -= abs(tx.amount)
                    
    start_balance = cumulative_balance
                
    balance_data = []
    for m in months:
        cumulative_balance += inflow_data[m] - expenses_data[m]
        balance_data.append(cumulative_balance)
        
    # Debt Dynamics
    debt_dynamics = []
    for m in months:
        total_debt = 0.0
        for apt in apartments:
            p_charges = sum(c.total for c in all_charges if c.apartment_id == apt.id and c.period <= m)
            p_payments = sum(tx.amount for tx in all_txs if tx.apartment_id == apt.id and parse_date(tx.date) and parse_date(tx.date).strftime("%Y-%m") <= m)
            
            balance = (apt.initial_balance or 0.0) - p_charges + p_payments
            if balance < 0:
                total_debt += abs(balance)
        debt_dynamics.append(total_debt)
        
    # Forecast
    now_p = datetime.now().strftime("%Y-%m")
    past_months = [m for m in months if m < now_p]
    if not past_months: past_months = months[:1]
    
    avg_inflow = sum(inflow_data[m] for m in past_months) / len(past_months) if past_months else 0
    avg_expenses = sum(expenses_data[m] for m in past_months) / len(past_months) if past_months else 0
    
    forecast_months = [m for m in months if m >= now_p]
    forecast_inflow = [avg_inflow] * len(forecast_months)
    forecast_expenses = [avg_expenses] * len(forecast_months)
    
    last_balance = balance_data[len(past_months)-1] if len(past_months) > 0 else start_balance
    forecast_balance = []
    curr_b = last_balance
    for i in range(len(forecast_months)):
        curr_b += avg_inflow - avg_expenses
        forecast_balance.append(curr_b)

    month_names_ua = ['Січ', 'Лют', 'Бер', 'Квіт', 'Трав', 'Черв', 'Лип', 'Серп', 'Вер', 'Жовт', 'Лист', 'Груд']
    labels = []
    for m in months:
        y, mo = m.split('-')
        labels.append(f"{month_names_ua[int(mo)-1]}-{y[2:]}")

    # ── Build Balance table (Inflow / Expenses / Balance per month) ────────
    balance_table = {
        "headers": ["Тип"] + labels + ["Всього"],
        "rows": [
            {"label": "Витрати", "values": [-expenses_data[m] for m in months] + [-sum(expenses_data.values())]},
            {"label": "Надходження", "values": [inflow_data[m] for m in months] + [sum(inflow_data.values())]},
        ],
        "grand_total": {
            "label": "Grand Total",
            "values": [inflow_data[m] - expenses_data[m] for m in months] + [sum(inflow_data.values()) - sum(expenses_data.values())]
        },
        "balance_row": {
            "label": "Баланс",
            "values": balance_data + [balance_data[-1] if balance_data else start_balance]
        }
    }

    # ── Build Expense breakdown (group → % + sum) ──────────────────────────
    expense_by_group = {}
    income_by_group = {}
    # detail: type → group → purpose → {months}
    detail_data = {}

    for tx in all_txs:
        dt = parse_date(tx.date)
        if not dt: continue
        is_in_range = s_dt <= dt <= e_dt
        if not is_in_range: continue
        p_str = dt.strftime("%Y-%m")
        cat = cat_map.get(tx.category_id)
        if not cat: continue
        if cat.group == 'Початковий залишок': continue
        if tx.apartment_id is not None:
            # apartment payment → income / Квартплата
            grp = 'Квартплата'
            purpose = 'Квартплата'
            ttype = 'Надходження'
            amt = tx.amount
            income_by_group[grp] = income_by_group.get(grp, 0) + amt
        elif cat.name == 'Квартплата':
            continue  # skip aggregate budget line
        else:
            grp = cat.group or cat.name
            purpose = cat.name
            if cat.type == 'income':
                ttype = 'Надходження'
                amt = tx.amount
                income_by_group[grp] = income_by_group.get(grp, 0) + amt
            else:
                ttype = 'Витрати'
                amt = -abs(tx.amount)
                expense_by_group[grp] = expense_by_group.get(grp, 0) + abs(tx.amount)

        # Populate detail pivot
        if ttype not in detail_data:
            detail_data[ttype] = {}
        if grp not in detail_data[ttype]:
            detail_data[ttype][grp] = {}
        if purpose not in detail_data[ttype][grp]:
            detail_data[ttype][grp][purpose] = {mm: 0 for mm in months}
            detail_data[ttype][grp][purpose]["_total"] = 0
        if p_str in detail_data[ttype][grp][purpose]:
            detail_data[ttype][grp][purpose][p_str] += amt
        detail_data[ttype][grp][purpose]["_total"] += amt

    total_exp = sum(expense_by_group.values()) if expense_by_group else 1
    expense_breakdown = []
    for grp, val in sorted(expense_by_group.items(), key=lambda x: -x[1]):
        expense_breakdown.append({
            "group": grp,
            "pct": round(val / total_exp * 100),
            "amount": -val
        })

    # ── Build detail pivot rows ────────────────────────────────────────────
    detail_rows = []
    grand_by_month = {mm: 0 for mm in months}
    grand_total = 0

    for ttype in ["Витрати", "Надходження"]:
        if ttype not in detail_data:
            continue
        type_by_month = {mm: 0 for mm in months}
        type_total = 0
        for grp, purposes in sorted(detail_data[ttype].items()):
            grp_by_month = {mm: 0 for mm in months}
            grp_total = 0
            for purpose, mvals in sorted(purposes.items()):
                row_values = []
                for mm in months:
                    v = mvals.get(mm, 0)
                    row_values.append(v)
                    grp_by_month[mm] += v
                    type_by_month[mm] += v
                    grand_by_month[mm] += v
                rt = mvals.get("_total", 0)
                grp_total += rt
                type_total += rt
                grand_total += rt
                detail_rows.append({"level": "item", "type": ttype, "group": grp, "purpose": purpose, "values": row_values + [rt]})
            # group subtotal
            # detail_rows.append({"level": "group_total", "type": ttype, "group": grp, "purpose": f"{grp} Total", "values": [grp_by_month[mm] for mm in months] + [grp_total]})
        # type total
        detail_rows.append({"level": "type_total", "type": ttype, "group": "", "purpose": f"{ttype} Total", "values": [type_by_month[mm] for mm in months] + [type_total]})

    detail_rows.append({"level": "grand_total", "type": "", "group": "", "purpose": "Grand Total", "values": [grand_by_month[mm] for mm in months] + [grand_total]})

    # ── Debtors list at end of period ─────────────────────────────────────────
    # Calculate as of last day of end_date's month
    end_period = e_dt.strftime("%Y-%m")
    last_day = calendar.monthrange(e_dt.year, e_dt.month)[1]
    end_date_full = f"{e_dt.year}-{e_dt.month:02d}-{last_day:02d}"

    debtors = []
    for apt in sorted(apartments, key=lambda a: a.number):
        # All charges up to end period
        apt_charges = sum(c.total for c in all_charges if c.apartment_id == apt.id and c.period <= end_period)
        # All payments up to last day of end month
        apt_payments = sum(
            tx.amount for tx in all_txs
            if tx.apartment_id == apt.id and parse_date(tx.date) and parse_date(tx.date).strftime("%Y-%m-%d") <= end_date_full
        )
        balance = (apt.initial_balance or 0.0) - apt_charges + apt_payments
        # Negative balance = debt
        if balance < -0.01:
            debtors.append({
                "apartment": apt.number,
                "owner": apt.owner_name or "",
                "debt": round(abs(balance), 2)
            })

    return {
        "year": s_dt.year,
        "labels": labels,
        "months": months,
        "inflow": [inflow_data[m] for m in months],
        "expenses": [-expenses_data[m] for m in months],
        "balance": balance_data,
        "debt_dynamics": debt_dynamics,
        "forecast": {
            "start_index": len(past_months),
            "inflow": forecast_inflow,
            "expenses": [-v for v in forecast_expenses],
            "balance": forecast_balance
        },
        "totals": {
            "start_balance": start_balance,
            "inflow": sum(inflow_data.values()),
            "expenses": sum(expenses_data.values()),
            "balance": balance_data[-1] if balance_data else start_balance
        },
        "balance_table": balance_table,
        "expense_breakdown": expense_breakdown,
        "detail_rows": detail_rows,
        "debtors": debtors,
        "debtors_date": end_date_full
    }


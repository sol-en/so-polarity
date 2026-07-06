from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
import pandas as pd
import io
import re
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Transaction])
def get_transactions(db: Session = Depends(get_db)):
    return db.query(models.Transaction).options(
        joinedload(models.Transaction.category),
        joinedload(models.Transaction.contractor),
        joinedload(models.Transaction.apartment)
    ).all()

@router.post("/", response_model=schemas.Transaction)
def create_transaction(tx: schemas.TransactionBase, db: Session = Depends(get_db)):
    db_tx = models.Transaction(**tx.model_dump())
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Транзакцію не знайдено")
    db.delete(tx)
    db.commit()
    return {"status": "ok"}

@router.post("/upload")
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="Формат файлу має бути XLS або XLSX")
    
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка читання файлу: {str(e)}")
    
    col_mapping = {}
    for col in df.columns:
        c_lower = str(col).lower()
        if 'дата' in c_lower:
            col_mapping['date'] = col
        elif 'сума' in c_lower and 'еквівалент' not in c_lower and 'валют' not in c_lower:
            col_mapping['amount'] = col
        elif 'призначення' in c_lower:
            col_mapping['description'] = col
        elif 'референс' in c_lower or 'id' in c_lower or 'номер' in c_lower:
            col_mapping['ref'] = col
        elif 'контрагент' in c_lower or 'назва' in c_lower or 'одержувач' in c_lower or 'відправник' in c_lower:
            col_mapping['counterparty'] = col

    # Get or create Uncategorized category
    uncategorized = db.query(models.Category).filter(models.Category.name == "Без категорії").first()
    if not uncategorized:
        uncategorized = models.Category(name="Без категорії", type="income", group="Інше")
        db.add(uncategorized)
        db.commit()
        db.refresh(uncategorized)

    apartments = db.query(models.Apartment).all()
    apt_map = {str(a.number).strip().lower(): a.id for a in apartments if a.number}

    new_count = 0
    dup_count = 0

    for index, row in df.iterrows():
        try:
            ref = str(row[col_mapping['ref']]) if 'ref' in col_mapping and pd.notna(row[col_mapping['ref']]) else None
            if not ref or ref.lower() == 'nan':
                continue
            
            exists = db.query(models.Transaction).filter(models.Transaction.bank_tx_id == ref).first()
            if exists:
                dup_count += 1
                continue
            
            raw_date = row[col_mapping['date']] if 'date' in col_mapping else None
            if pd.isna(raw_date): continue
            try:
                date_str = pd.to_datetime(raw_date, dayfirst=True).strftime('%Y-%m-%d')
            except:
                date_str = str(raw_date)[:10]
            
            amount = float(row[col_mapping['amount']]) if 'amount' in col_mapping else 0.0
            if pd.isna(amount): continue
            
            desc = str(row[col_mapping['description']]) if 'description' in col_mapping else ""
            if pd.isna(desc) or desc.lower() == 'nan': desc = ""

            counterparty = str(row[col_mapping['counterparty']]) if 'counterparty' in col_mapping else ""
            if pd.isna(counterparty) or counterparty.lower() == 'nan': counterparty = ""

            apt_id = None
            match = re.search(r'кв\.?\s*(\d+[а-яА-Яa-zA-Z]?)', desc, re.IGNORECASE)
            if match:
                apt_num = match.group(1).lower()
                apt_id = apt_map.get(apt_num)

            tx = models.Transaction(
                date=date_str,
                amount=amount,
                description=desc,
                counterparty=counterparty,
                bank_tx_id=ref,
                category_id=uncategorized.id,
                apartment_id=apt_id
            )
            db.add(tx)
            new_count += 1
        except Exception as e:
            print(f"Error parsing row {index}: {e}")
            continue

    db.commit()
    return {"status": "ok", "imported": new_count, "duplicates": dup_count}

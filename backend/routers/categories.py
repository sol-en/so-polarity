from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Category])
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).order_by(models.Category.type, models.Category.name).all()

@router.post("/", response_model=schemas.Category)
def create_category(category: schemas.CategoryBase, db: Session = Depends(get_db)):
    db_cat = models.Category(**category.model_dump())
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat

@router.put("/{category_id}", response_model=schemas.Category)
def update_category(category_id: int, category: schemas.CategoryBase, db: Session = Depends(get_db)):
    db_cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    db_cat.name = category.name
    db_cat.type = category.type
    db_cat.group = category.group
    db.commit()
    db.refresh(db_cat)
    return db_cat

@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    db_cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    # Check if there are transactions using this category
    tx_count = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).count()
    if tx_count > 0:
        raise HTTPException(status_code=400, detail=f"Неможливо видалити: є {tx_count} транзакцій з цією категорією")
    db.delete(db_cat)
    db.commit()
    return {"ok": True}

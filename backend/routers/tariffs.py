from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.Tariff])
def get_tariffs(db: Session = Depends(get_db)):
    return db.query(models.Tariff).all()

@router.post("/", response_model=schemas.Tariff)
def create_tariff(tariff: schemas.TariffBase, db: Session = Depends(get_db)):
    db_tariff = models.Tariff(**tariff.model_dump())
    db.add(db_tariff)
    db.commit()
    db.refresh(db_tariff)
    return db_tariff

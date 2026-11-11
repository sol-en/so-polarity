from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime

from ..database import get_db
from .. import models

router = APIRouter(tags=["reports"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "reports"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def seed_sample_reports_if_empty(db: Session):
    count = db.query(models.ReportDocument).count()
    if count == 0:
        sample1_path = os.path.join(UPLOAD_DIR, "financial_report_2025.pdf")
        if os.path.exists(sample1_path):
            size = os.path.getsize(sample1_path)
            doc1 = models.ReportDocument(
                title="Звіт про фінансово-господарську діяльність ЖБК за 2025 рік",
                year=2025,
                period="Річний звіт",
                filename="financial_report_2025.pdf",
                file_size=size,
                note="Затверджено загальними зборами співвласників"
            )
            db.add(doc1)
        
        sample2_path = os.path.join(UPLOAD_DIR, "debtors_report_2026.pdf")
        if os.path.exists(sample2_path):
            size = os.path.getsize(sample2_path)
            doc2 = models.ReportDocument(
                title="Акт ревізійної комісії та реєстр заборгованості за 2026 рік",
                year=2026,
                period="Акт ревізії",
                filename="debtors_report_2026.pdf",
                file_size=size,
                note="Звіт ревізійної комісії станом на 31.10.2026"
            )
            db.add(doc2)
        db.commit()

@router.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    seed_sample_reports_if_empty(db)
    docs = db.query(models.ReportDocument).order_by(models.ReportDocument.year.desc(), models.ReportDocument.id.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "year": d.year,
            "period": d.period,
            "filename": d.filename,
            "file_size": d.file_size,
            "created_at": d.created_at.strftime("%d.%m.%Y") if d.created_at else "",
            "note": d.note
        }
        for d in docs
    ]

@router.post("/documents/upload")
async def upload_document(
    title: str = Form(...),
    year: int = Form(...),
    period: Optional[str] = Form("Річний звіт"),
    note: Optional[str] = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Дозволено завантажувати тільки PDF файли")
    
    timestamp = int(datetime.utcnow().timestamp())
    safe_name = f"doc_{year}_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)
    
    doc = models.ReportDocument(
        title=title,
        year=year,
        period=period or "Річний звіт",
        filename=safe_name,
        file_size=file_size,
        note=note or ""
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    return {"ok": True, "id": doc.id, "title": doc.title}

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.ReportDocument).filter(models.ReportDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
        
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
            
    db.delete(doc)
    db.commit()
    return {"ok": True}

@router.get("/documents/{doc_id}/view")
def view_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.ReportDocument).filter(models.ReportDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
        
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл відсутній на диску")
        
    return FileResponse(file_path, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={doc.filename}"})

@router.get("/documents/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.ReportDocument).filter(models.ReportDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
        
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл відсутній на диску")
        
    return FileResponse(file_path, media_type="application/pdf", filename=doc.filename)

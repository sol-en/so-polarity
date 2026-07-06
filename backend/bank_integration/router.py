"""API router for bank data integration (PrivatBank CSV + Registry imports)."""

import os
import shutil
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from ..database import get_db
from .. import models
from ..bank_models import BankPayment, BankBalanceSummary, ImportLog, MappingKey, MatchStatusLog
from .csv_parser import parse_transactions_csv, parse_saldo_csv, detect_file_type
from .registry_parser import parse_registry_txt
from .matching import run_matching_pipeline, _log_change
from .gmail_fetcher import fetch_registry_emails, GMAIL_API_AVAILABLE

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class ManualMapRequest(BaseModel):
    apartment_id: int
    save_mapping: bool = False
    key_type: Optional[str] = None  # 'payer_name', 'address_substring', 'both'
    note: Optional[str] = None

class GmailFetchRequest(BaseModel):
    from_date: str  # YYYY-MM-DD
    to_date: str    # YYYY-MM-DD

class DateRangeRequest(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None

class MappingKeyCreate(BaseModel):
    key_type: str
    key_value: str
    key_value_secondary: Optional[str] = None
    apartment_id: int
    note: Optional[str] = None


# ── Import endpoints ─────────────────────────────────────────────────────────

@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a PrivatBank Autoclient CSV file."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    content = await file.read()
    file_type = detect_file_type(file.filename)

    encoding = os.getenv('CSV_ENCODING', 'cp1251')
    log_entry = ImportLog(
        source_identifier=file.filename,
        source_type=f'csv_{file_type or "unknown"}',
        status='processing'
    )

    try:
        if file_type == 'saldo':
            records, errors = parse_saldo_csv(content, file.filename, encoding)
            inserted = 0
            for rec in records:
                summary = BankBalanceSummary(**rec)
                db.add(summary)
                inserted += 1
            db.commit()
            log_entry.status = 'success'
            log_entry.total_parsed = len(records)
            log_entry.inserted = inserted
            log_entry.skipped = 0
            if errors:
                log_entry.error_message = '; '.join(errors[:5])
            db.add(log_entry)
            db.commit()
            return {
                "status": "ok", "type": "saldo",
                "inserted": inserted, "errors": errors[:5]
            }

        elif file_type in ('opers', 'lastday'):
            records, errors = parse_transactions_csv(content, file.filename, encoding)
            inserted, skipped = 0, 0
            new_payment_ids = []

            for rec in records:
                # Deduplication check
                exists = db.query(BankPayment).filter(
                    BankPayment.doc_number == rec['doc_number']
                ).first()
                if exists:
                    skipped += 1
                    continue

                bp = BankPayment(
                    doc_number=rec['doc_number'],
                    source_type=rec.get('source_type', 'csv_statement'),
                    source_file=rec.get('source_file'),
                    operation_date=rec.get('operation_date'),
                    document_date=rec.get('document_date'),
                    amount=rec.get('amount', 0.0),
                    debit=rec.get('debit', 0.0),
                    credit=rec.get('credit', 0.0),
                    currency=rec.get('currency', 'UAH'),
                    uah_equivalent=rec.get('uah_equivalent'),
                    correspondent_name=rec.get('correspondent_name'),
                    correspondent_iban=rec.get('correspondent_iban'),
                    correspondent_edrpou=rec.get('correspondent_edrpou'),
                    correspondent_mfo=rec.get('correspondent_mfo'),
                    correspondent_bank_name=rec.get('correspondent_bank_name'),
                    client_edrpou=rec.get('client_edrpou'),
                    client_mfo=rec.get('client_mfo'),
                    client_iban=rec.get('client_iban'),
                    purpose=rec.get('purpose'),
                    match_status='unrecognized',
                )
                db.add(bp)
                db.flush()
                new_payment_ids.append(bp.id)
                _log_change(db, bp.id, None, 'unrecognized', 'system')
                inserted += 1

            db.commit()

            # Run matching on new payments
            match_counts = {}
            if new_payment_ids:
                match_counts = run_matching_pipeline(db, payment_ids=new_payment_ids)

            log_entry.status = 'success'
            log_entry.total_parsed = len(records)
            log_entry.inserted = inserted
            log_entry.skipped = skipped
            if errors:
                log_entry.error_message = '; '.join(errors[:5])
            db.add(log_entry)
            db.commit()

            return {
                "status": "ok", "type": file_type,
                "total_parsed": len(records),
                "inserted": inserted, "skipped": skipped,
                "matching": match_counts,
                "errors": errors[:5]
            }
        else:
            raise HTTPException(400,
                f"Unrecognized file type. Expected *_opers.csv, *_lastday.csv, or *_saldo.csv. Got: {file.filename}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_entry.status = 'error'
        log_entry.error_message = str(e)
        try:
            db.add(log_entry)
            db.commit()
        except Exception:
            pass
        logger.exception("CSV import error")
        raise HTTPException(500, f"Import error: {e}")


@router.post("/import-registry")
async def import_registry(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a PrivatBank registry TXT file."""
    content = await file.read()
    encoding = 'cp1251'

    log_entry = ImportLog(
        source_identifier=file.filename or 'registry_upload',
        source_type='registry_email',
        status='processing'
    )

    try:
        header_info, records, errors = parse_registry_txt(
            content, encoding, source_identifier=file.filename or ''
        )

        inserted, skipped = 0, 0
        new_ids = []

        for rec in records:
            exists = db.query(BankPayment).filter(
                BankPayment.doc_number == rec['doc_number']
            ).first()
            if exists:
                skipped += 1
                continue

            bp = BankPayment(
                doc_number=rec['doc_number'],
                source_type='registry_email',
                source_file=rec.get('source_file'),
                operation_date=rec.get('operation_date'),
                amount=rec.get('amount', 0.0),
                credit=rec.get('amount', 0.0),
                payer_name=rec.get('payer_name'),
                payer_address=rec.get('payer_address'),
                payment_order_number=rec.get('payment_order_number'),
                payment_order_date=rec.get('payment_order_date'),
                match_status='unrecognized',
            )
            db.add(bp)
            db.flush()
            new_ids.append(bp.id)
            _log_change(db, bp.id, None, 'unrecognized', 'system')
            inserted += 1

        db.commit()

        match_counts = {}
        if new_ids:
            match_counts = run_matching_pipeline(db, payment_ids=new_ids)

        log_entry.status = 'success'
        log_entry.total_parsed = len(records)
        log_entry.inserted = inserted
        log_entry.skipped = skipped
        if errors:
            log_entry.error_message = '; '.join(errors[:5])
        db.add(log_entry)
        db.commit()

        return {
            "status": "ok",
            "header": header_info,
            "total_parsed": len(records),
            "inserted": inserted, "skipped": skipped,
            "matching": match_counts,
            "errors": errors[:5]
        }

    except Exception as e:
        db.rollback()
        log_entry.status = 'error'
        log_entry.error_message = str(e)
        try: db.add(log_entry); db.commit()
        except: pass
        logger.exception("Registry import error")
        raise HTTPException(500, f"Import error: {e}")

@router.post("/sync-gmail")
def sync_gmail(req: GmailFetchRequest, db: Session = Depends(get_db)):
    if not GMAIL_API_AVAILABLE:
        raise HTTPException(500, "Gmail API libraries not installed.")
    
    try:
        attachments = fetch_registry_emails(req.from_date, req.to_date)
    except Exception as e:
        logger.exception("Gmail fetch error")
        raise HTTPException(500, f"Gmail sync failed: {str(e)}")
        
    if not attachments:
        return {"status": "ok", "message": "No new registries found.", "inserted": 0, "skipped": 0, "matching": {}}

    total_inserted = 0
    total_skipped = 0
    new_ids = []
    
    attachment_index = 0
    for msg_id, file_data in attachments:
        attachment_index += 1
        unique_id = f"{msg_id}_{attachment_index}"
        
        # Check if already processed
        log_exists = db.query(ImportLog).filter(ImportLog.source_identifier == unique_id).first()
        if log_exists and log_exists.status == 'success':
            continue
            
        log_entry = ImportLog(
            source_identifier=unique_id,
            source_type='registry_email',
            status='processing'
        )
        db.add(log_entry)
        db.commit()
        
        header_info, records, errors = parse_registry_txt(file_data, 'cp1251', source_identifier=unique_id)
        
        inserted = 0
        skipped = 0
        for rec in records:
            exists = db.query(BankPayment).filter(BankPayment.doc_number == rec['doc_number']).first()
            if exists:
                skipped += 1
                continue
                
            bp = BankPayment(
                doc_number=rec['doc_number'],
                source_type='registry_email',
                source_file=msg_id,
                gmail_message_id=msg_id,
                operation_date=rec.get('operation_date'),
                amount=rec.get('amount', 0.0),
                credit=rec.get('amount', 0.0),
                payer_name=rec.get('payer_name'),
                payer_address=rec.get('payer_address'),
                payment_order_number=rec.get('payment_order_number'),
                payment_order_date=rec.get('payment_order_date'),
                match_status='unrecognized',
            )
            db.add(bp)
            db.flush()
            new_ids.append(bp.id)
            inserted += 1
            
        log_entry.status = 'success' if not errors else 'partial'
        log_entry.total_parsed = len(records)
        log_entry.inserted = inserted
        log_entry.skipped = skipped
        if errors:
            log_entry.error_message = '; '.join(errors[:5])
        
        total_inserted += inserted
        total_skipped += skipped
        
    db.commit()
    
    match_counts = {}
    if new_ids:
        match_counts = run_matching_pipeline(db, payment_ids=new_ids)
        
    return {
        "status": "ok",
        "inserted": total_inserted,
        "skipped": total_skipped,
        "matching": match_counts
    }


@router.post("/gmail-credentials")
async def upload_gmail_credentials(file: UploadFile = File(...)):
    """Upload Google Cloud credentials.json for Gmail API integration."""
    if not file.filename.endswith('.json'):
        raise HTTPException(400, "Expected a .json file")
    
    content = await file.read()
    creds_path = os.getenv('GMAIL_CREDENTIALS', 'credentials.json')
    
    try:
        with open(creds_path, 'wb') as f:
            f.write(content)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to save credentials")
        raise HTTPException(500, f"Error saving file: {e}")

@router.get("/gmail-status")
def get_gmail_status():
    """Check if credentials.json is present and valid."""
    creds_path = os.getenv('GMAIL_CREDENTIALS', 'credentials.json')
    token_path = os.getenv('GMAIL_TOKEN', 'token.json')
    return {
        "credentials_exist": os.path.exists(creds_path),
        "token_exists": os.path.exists(token_path)
    }

# ── Payment list & details ───────────────────────────────────────────────────

@router.get("/payments")
def get_payments(
    status: Optional[str] = None,
    posted: Optional[bool] = None,
    source_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List bank payments with optional filters."""
    q = db.query(BankPayment)

    if status:
        statuses = status.split(',')
        q = q.filter(BankPayment.match_status.in_(statuses))
    if posted is not None:
        q = q.filter(BankPayment.posted == posted)
    if source_type:
        q = q.filter(BankPayment.source_type == source_type)
    if search:
        s = f"%{search}%"
        q = q.filter(
            (BankPayment.payer_name.ilike(s)) |
            (BankPayment.correspondent_name.ilike(s)) |
            (BankPayment.payer_address.ilike(s)) |
            (BankPayment.purpose.ilike(s)) |
            (BankPayment.doc_number.ilike(s))
        )

    payments = q.order_by(BankPayment.operation_date.desc()).all()

    # Enrich with apartment info
    apt_ids = set()
    for p in payments:
        if p.apartment_id: apt_ids.add(p.apartment_id)
        if p.suggested_apartment_id: apt_ids.add(p.suggested_apartment_id)

    apts = {}
    if apt_ids:
        for a in db.query(models.Apartment).filter(models.Apartment.id.in_(apt_ids)).all():
            apts[a.id] = {"id": a.id, "number": a.number, "owner_name": a.owner_name}

    result = []
    for p in payments:
        d = {
            "id": p.id,
            "doc_number": p.doc_number,
            "source_type": p.source_type,
            "operation_date": p.operation_date,
            "amount": p.amount,
            "credit": p.credit,
            "debit": p.debit,
            "correspondent_name": p.correspondent_name,
            "payer_name": p.payer_name,
            "payer_address": p.payer_address,
            "purpose": p.purpose,
            "match_status": p.match_status,
            "match_score": p.match_score,
            "apartment_id": p.apartment_id,
            "suggested_apartment_id": p.suggested_apartment_id,
            "posted": p.posted,
            "created_at": str(p.created_at) if p.created_at else None,
            "apartment": apts.get(p.apartment_id),
            "suggested_apartment": apts.get(p.suggested_apartment_id),
            "source_file": p.source_file,
        }
        result.append(d)

    return result


@router.get("/payments/{payment_id}")
def get_payment_detail(payment_id: int, db: Session = Depends(get_db)):
    """Get full details of a single bank payment."""
    p = db.query(BankPayment).filter(BankPayment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")

    apt = None
    if p.apartment_id:
        a = db.query(models.Apartment).filter(models.Apartment.id == p.apartment_id).first()
        if a: apt = {"id": a.id, "number": a.number, "owner_name": a.owner_name}

    sug_apt = None
    if p.suggested_apartment_id:
        a = db.query(models.Apartment).filter(models.Apartment.id == p.suggested_apartment_id).first()
        if a: sug_apt = {"id": a.id, "number": a.number, "owner_name": a.owner_name}

    logs = db.query(MatchStatusLog).filter(
        MatchStatusLog.bank_payment_id == payment_id
    ).order_by(MatchStatusLog.timestamp.desc()).all()

    return {
        "id": p.id, "doc_number": p.doc_number, "source_type": p.source_type,
        "source_file": p.source_file, "operation_date": p.operation_date,
        "amount": p.amount, "credit": p.credit, "debit": p.debit,
        "currency": p.currency,
        "correspondent_name": p.correspondent_name,
        "correspondent_iban": p.correspondent_iban,
        "correspondent_edrpou": p.correspondent_edrpou,
        "payer_name": p.payer_name, "payer_address": p.payer_address,
        "purpose": p.purpose,
        "match_status": p.match_status, "match_score": p.match_score,
        "apartment_id": p.apartment_id,
        "suggested_apartment_id": p.suggested_apartment_id,
        "posted": p.posted,
        "apartment": apt, "suggested_apartment": sug_apt,
        "status_history": [
            {"old": l.old_status, "new": l.new_status, "actor": l.actor,
             "timestamp": str(l.timestamp)} for l in logs
        ]
    }


# ── Manual mapping ───────────────────────────────────────────────────────────

@router.post("/payments/{payment_id}/map")
def map_payment(payment_id: int, req: ManualMapRequest, db: Session = Depends(get_db)):
    """Manually map a payment to an apartment."""
    p = db.query(BankPayment).filter(BankPayment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")

    apt = db.query(models.Apartment).filter(models.Apartment.id == req.apartment_id).first()
    if not apt:
        raise HTTPException(404, "Apartment not found")

    old_status = p.match_status
    p.apartment_id = req.apartment_id
    p.match_status = 'mapped'
    p.match_score = 100.0
    p.suggested_apartment_id = None

    _log_change(db, p.id, old_status, 'mapped', 'admin')

    # Save mapping key if requested
    if req.save_mapping and req.key_type:
        key_value = (p.payer_name or p.correspondent_name or '').strip()
        key_secondary = None

        if req.key_type == 'address_substring':
            key_value = (p.payer_address or p.purpose or '').strip()
        elif req.key_type == 'both':
            key_secondary = (p.payer_address or p.purpose or '').strip()

        if key_value:
            existing = db.query(MappingKey).filter(
                MappingKey.key_type == req.key_type,
                MappingKey.key_value == key_value
            ).first()

            if not existing:
                mk = MappingKey(
                    key_type=req.key_type,
                    key_value=key_value,
                    key_value_secondary=key_secondary,
                    apartment_id=req.apartment_id,
                    created_by='admin',
                    note=req.note,
                )
                db.add(mk)

    db.commit()
    return {"status": "ok", "match_status": "mapped"}


@router.post("/payments/{payment_id}/confirm")
def confirm_payment(payment_id: int, db: Session = Depends(get_db)):
    """Confirm an unconfirmed payment match suggestion."""
    p = db.query(BankPayment).filter(BankPayment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")
    if p.match_status != 'unconfirmed':
        raise HTTPException(400, "Payment is not unconfirmed")
    if not p.suggested_apartment_id:
        raise HTTPException(400, "No suggested apartment")

    old_status = p.match_status
    p.apartment_id = p.suggested_apartment_id
    p.match_status = 'mapped'
    p.suggested_apartment_id = None
    _log_change(db, p.id, old_status, 'mapped', 'admin')
    db.commit()
    return {"status": "ok"}


@router.post("/payments/{payment_id}/reject")
def reject_suggestion(payment_id: int, db: Session = Depends(get_db)):
    """Reject an unconfirmed suggestion — set to unrecognized."""
    p = db.query(BankPayment).filter(BankPayment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")

    old_status = p.match_status
    p.match_status = 'unrecognized'
    p.suggested_apartment_id = None
    p.match_score = None
    _log_change(db, p.id, old_status, 'unrecognized', 'admin')
    db.commit()
    return {"status": "ok"}


# ── Re-match & posting ──────────────────────────────────────────────────────

@router.post("/re-match")
def re_match(db: Session = Depends(get_db)):
    """Re-run matching pipeline on all unresolved payments."""
    counts = run_matching_pipeline(db)
    return {"status": "ok", "results": counts}


@router.post("/post-matched")
def post_all_matched(db: Session = Depends(get_db)):
    """Post all matched/mapped unposted payments to the transactions ledger.
    
    Handles both income (apartment) and expense (contractor) payments.
    """
    # Fetch all matched unposted payments
    payments_to_post = db.query(BankPayment).filter(
        BankPayment.match_status.in_(['matched', 'mapped']),
        BankPayment.posted == False
    ).all()

    if not payments_to_post:
        return {"status": "ok", "posted": 0, "message": "No payments to post"}

    posted = 0
    for p in payments_to_post:
        try:
            existing = db.query(models.Transaction).filter(
                models.Transaction.bank_tx_id == p.doc_number
            ).first()
            if existing:
                p.posted = True
                p.transaction_id = existing.id
                continue

            is_expense = (p.amount or 0) < 0
            contractor_id = p.suggested_apartment_id

            if p.apartment_id:
                # 1. Income from an Apartment
                cat = db.query(models.Category).filter(models.Category.name == "Квартплата").first()
                if not cat:
                    cat = models.Category(name="Квартплата", type="income", group="Квартплата")
                    db.add(cat); db.commit(); db.refresh(cat)

                tx = models.Transaction(
                    date=p.operation_date or datetime.utcnow().strftime('%Y-%m-%d'),
                    amount=abs(p.amount) if p.amount else abs(p.credit or 0),
                    description=p.purpose or p.payer_name or p.correspondent_name or '',
                    counterparty=p.payer_name or p.correspondent_name or '',
                    category_id=cat.id,
                    apartment_id=p.apartment_id,
                    bank_tx_id=p.doc_number,
                )
            else:
                # 2. Payment from/to a Contractor (or unlinked expense)
                if not is_expense and not contractor_id:
                    logger.error("Income must be linked to an apartment or contractor for payment %s", p.doc_number)
                    continue

                cat = None
                if contractor_id:
                    contractor = db.query(models.Contractor).filter(models.Contractor.id == contractor_id).first()
                    if contractor and contractor.default_category_id:
                        temp_cat = db.query(models.Category).filter(models.Category.id == contractor.default_category_id).first()
                        expected_type = "expense" if is_expense else "income"
                        if temp_cat and temp_cat.type == expected_type:
                            cat = temp_cat
                            
                if not cat:
                    cat_name = "Витрати (банк)" if is_expense else "Надходження (банк)"
                    cat_type = "expense" if is_expense else "income"
                    cat = db.query(models.Category).filter(models.Category.name == cat_name, models.Category.type == cat_type).first()
                    if not cat:
                        cat = models.Category(name=cat_name, type=cat_type, group="Інше")
                        db.add(cat); db.commit(); db.refresh(cat)

                tx = models.Transaction(
                    date=p.operation_date or datetime.utcnow().strftime('%Y-%m-%d'),
                    amount=abs(p.amount) if p.amount else abs(p.credit or 0),
                    description=p.purpose or p.correspondent_name or p.payer_name or '',
                    counterparty=p.correspondent_name or p.payer_name or '',
                    category_id=cat.id,
                    contractor_id=contractor_id,
                    bank_tx_id=p.doc_number,
                )

            db.add(tx)
            db.flush()
            p.posted = True
            p.transaction_id = tx.id
            posted += 1
        except Exception as e:
            logger.error("Failed to post payment %s: %s", p.doc_number, e)

    db.commit()
    return {"status": "ok", "posted": posted}


@router.post("/payments/{payment_id}/post")
def post_single(payment_id: int, db: Session = Depends(get_db)):
    """Post a single matched payment to the ledger."""
    p = db.query(BankPayment).filter(BankPayment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")
    if p.match_status not in ('matched', 'mapped'):
        raise HTTPException(400, "Payment must be matched or mapped to post")
    if p.posted:
        raise HTTPException(400, "Already posted")

    # Determine what this payment is linked to
    is_expense = (p.amount or 0) < 0
    contractor_id = p.suggested_apartment_id

    if p.apartment_id:
        # 1. Income from an Apartment
        cat = db.query(models.Category).filter(models.Category.name == "Квартплата").first()
        if not cat:
            cat = models.Category(name="Квартплата", type="income", group="Квартплата")
            db.add(cat); db.commit(); db.refresh(cat)

        tx = models.Transaction(
            date=p.operation_date or datetime.utcnow().strftime('%Y-%m-%d'),
            amount=abs(p.amount) if p.amount else abs(p.credit or 0),
            description=p.purpose or p.payer_name or p.correspondent_name or '',
            counterparty=p.payer_name or p.correspondent_name or '',
            category_id=cat.id,
            apartment_id=p.apartment_id,
            bank_tx_id=p.doc_number,
        )
    else:
        # 2. Payment from/to a Contractor (or unlinked expense)
        if not is_expense and not contractor_id:
            raise HTTPException(400, "Income must be linked to an apartment or contractor")
            
        cat = None
        if contractor_id:
            contractor = db.query(models.Contractor).filter(models.Contractor.id == contractor_id).first()
            if contractor and contractor.default_category_id:
                temp_cat = db.query(models.Category).filter(models.Category.id == contractor.default_category_id).first()
                expected_type = "expense" if is_expense else "income"
                if temp_cat and temp_cat.type == expected_type:
                    cat = temp_cat
                
        if not cat:
            cat_name = "Витрати (банк)" if is_expense else "Надходження (банк)"
            cat_type = "expense" if is_expense else "income"
            cat = db.query(models.Category).filter(models.Category.name == cat_name, models.Category.type == cat_type).first()
            if not cat:
                cat = models.Category(name=cat_name, type=cat_type, group="Інше")
                db.add(cat); db.commit(); db.refresh(cat)

        tx = models.Transaction(
            date=p.operation_date or datetime.utcnow().strftime('%Y-%m-%d'),
            amount=abs(p.amount) if p.amount else abs(p.credit or 0),
            description=p.purpose or p.correspondent_name or p.payer_name or '',
            counterparty=p.correspondent_name or p.payer_name or '',
            category_id=cat.id,
            contractor_id=contractor_id,
            bank_tx_id=p.doc_number,
        )

    db.add(tx); db.flush()
    p.posted = True; p.transaction_id = tx.id
    db.commit()
    return {"status": "ok", "transaction_id": tx.id}


# ── Mapping keys management ─────────────────────────────────────────────────

@router.get("/mapping-keys")
def get_mapping_keys(db: Session = Depends(get_db)):
    keys = db.query(MappingKey).all()
    result = []
    apt_ids = {k.apartment_id for k in keys}
    apts = {}
    if apt_ids:
        for a in db.query(models.Apartment).filter(models.Apartment.id.in_(apt_ids)).all():
            apts[a.id] = {"id": a.id, "number": a.number, "owner_name": a.owner_name}
    for k in keys:
        result.append({
            "id": k.id, "key_type": k.key_type,
            "key_value": k.key_value, "key_value_secondary": k.key_value_secondary,
            "apartment_id": k.apartment_id,
            "apartment": apts.get(k.apartment_id),
            "created_by": k.created_by,
            "created_at": str(k.created_at) if k.created_at else None,
            "last_used_at": str(k.last_used_at) if k.last_used_at else None,
            "use_count": k.use_count, "note": k.note,
        })
    return result


@router.post("/mapping-keys")
def create_mapping_key(req: MappingKeyCreate, db: Session = Depends(get_db)):
    existing = db.query(MappingKey).filter(
        MappingKey.key_type == req.key_type,
        MappingKey.key_value == req.key_value
    ).first()
    if existing:
        raise HTTPException(400, "Mapping key already exists")

    mk = MappingKey(
        key_type=req.key_type, key_value=req.key_value,
        key_value_secondary=req.key_value_secondary,
        apartment_id=req.apartment_id, note=req.note,
    )
    db.add(mk); db.commit()
    return {"status": "ok", "id": mk.id}


@router.delete("/mapping-keys/{key_id}")
def delete_mapping_key(key_id: int, db: Session = Depends(get_db)):
    mk = db.query(MappingKey).filter(MappingKey.id == key_id).first()
    if not mk: raise HTTPException(404, "Key not found")
    db.delete(mk); db.commit()
    return {"status": "ok"}


# ── Import logs ──────────────────────────────────────────────────────────────

@router.get("/import-logs")
def get_import_logs(db: Session = Depends(get_db)):
    logs = db.query(ImportLog).order_by(ImportLog.created_at.desc()).limit(100).all()
    return [{
        "id": l.id, "source_identifier": l.source_identifier,
        "source_type": l.source_type, "status": l.status,
        "total_parsed": l.total_parsed, "inserted": l.inserted,
        "skipped": l.skipped, "error_message": l.error_message,
        "created_at": str(l.created_at) if l.created_at else None,
    } for l in logs]


# ── Stats summary ────────────────────────────────────────────────────────────

@router.get("/stats")
def get_bank_stats(db: Session = Depends(get_db)):
    """Get summary statistics for bank import dashboard."""
    total = db.query(BankPayment).count()
    matched = db.query(BankPayment).filter(BankPayment.match_status == 'matched').count()
    mapped = db.query(BankPayment).filter(BankPayment.match_status == 'mapped').count()
    unconfirmed = db.query(BankPayment).filter(BankPayment.match_status == 'unconfirmed').count()
    unrecognized = db.query(BankPayment).filter(BankPayment.match_status == 'unrecognized').count()
    posted = db.query(BankPayment).filter(BankPayment.posted == True).count()

    return {
        "total": total, "matched": matched, "mapped": mapped,
        "unconfirmed": unconfirmed, "unrecognized": unrecognized,
        "posted": posted, "unposted": total - posted,
    }


@router.get("/verify-registries")
def verify_registries(db: Session = Depends(get_db)):
    """Check for discrepancies between consolidated registry sums and imported detailed registries."""
    from collections import defaultdict
    
    # 1. Sum up 'registry_email' payments per day in DB
    db_registries = db.query(BankPayment).filter(BankPayment.source_type == 'registry_email').all()
    db_by_day = defaultdict(float)
    for bp in db_registries:
        if bp.operation_date:
            day = bp.operation_date[:10]
            db_by_day[day] += bp.amount

    # 2. Sum up 'оплата згiдно реєстру' payments from CSVs in DB
    # They should have source_type 'csv_statement' and purpose containing 'згiдно реєстру'
    csv_registries = db.query(BankPayment).filter(
        BankPayment.source_type == 'csv_statement',
        BankPayment.amount > 0,
        BankPayment.purpose.like('%оплата згiдно реєстру%')
    ).all()
    
    csv_by_day = defaultdict(float)
    for bp in csv_registries:
        if bp.operation_date:
            day = bp.operation_date[:10]
            csv_by_day[day] += bp.amount

    discrepancies = []
    all_days = sorted(set(db_by_day.keys()) | set(csv_by_day.keys()))
    
    for day in all_days:
        csv_sum = round(csv_by_day.get(day, 0.0), 2)
        db_sum = round(db_by_day.get(day, 0.0), 2)
        diff = round(csv_sum - db_sum, 2)
        
        if abs(diff) > 0.01:
            discrepancies.append({
                "date": day,
                "expected_from_csv": csv_sum,
                "actual_from_detailed": db_sum,
                "missing": diff
            })
            
    return {
        "status": "ok",
        "total_discrepancies": len(discrepancies),
        "details": discrepancies
    }

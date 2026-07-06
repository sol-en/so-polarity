"""Matching pipeline for linking bank payments to apartments and contractors."""

import re
import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

APT_NUMBER_RE = re.compile(r'кв\.?\s*(\d+[а-яА-Яa-zA-Z]?)', re.IGNORECASE)
FUZZY_AUTO = 92
FUZZY_UNCONFIRMED = 80


def _norm(text):
    if not text: return ''
    return re.sub(r'\s+', ' ', text.strip().lower())


def _log_change(db, bp_id, old_s, new_s, actor='system'):
    from ..bank_models import MatchStatusLog
    db.add(MatchStatusLog(bank_payment_id=bp_id, old_status=old_s, new_status=new_s, actor=actor))


def match_expense(db, payment, contractors=None):
    """Match an expense (amount < 0) to a contractor by correspondent_name.

    Returns:
        Tuple of (status, contractor_id, score)
    """
    from ..models import Contractor
    if contractors is None:
        contractors = db.query(Contractor).all()

    cn = _norm(payment.correspondent_name or '')
    purp = _norm(payment.purpose or '')
    if not cn and not purp:
        return ('unrecognized', None, None)

    # Signal 1: Exact match on contractor name
    if cn:
        for c in contractors:
            if _norm(c.name) == cn:
                return ('matched', c.id, 100.0)

    # Signal 1.5: Keyword-based mapping for taxes, bank commission, salary, etc.
    # 1. Salary
    if 'зарплат' in purp or 'заробiтн' in purp or 'зп ' in purp:
        c_salary = next((c for c in contractors if 'співробітники' in _norm(c.name) or 'спiвробiтники' in _norm(c.name)), None)
        if c_salary:
            return ('matched', c_salary.id, 95.0)
            
    # 2. Taxes
    if any(k in cn or k in purp for k in ['єсв', 'пдфо', 'військовий', 'вiйськовий', 'податк', 'гук у', 'гу дпс', 'дпсу', 'гудксу', 'казначей']):
        c_taxes = next((c for c in contractors if 'податки' in _norm(c.name)), None)
        if c_taxes:
            return ('matched', c_taxes.id, 95.0)

    # 3. Bank commissions
    if any(k in cn or k in purp for k in ['обсл. рахунку', 'дебетування рахунку', 'комісія', 'комiсiя']):
        c_bank = next((c for c in contractors if 'приватбанк' in _norm(c.name)), None)
        if c_bank:
            return ('matched', c_bank.id, 95.0)

    # 4. Electricity
    if 'ел.енерг' in purp or 'енергет' in cn:
        c_elec = next((c for c in contractors if 'енергетичн' in _norm(c.name)), None)
        if c_elec:
            return ('matched', c_elec.id, 95.0)

    # 5. CS K Ukraine (KEP)
    if 'цск україна' in cn:
        c_cep = next((c for c in contractors if 'цск україна' in _norm(c.name)), None)
        if c_cep:
            return ('matched', c_cep.id, 95.0)

    # 6. Emergency / Service Dnipro
    if 'аварiйн' in purp or 'сервiс-днiпро' in cn or 'сервіс-дніпро' in cn:
        c_emerg = next((c for c in contractors if 'сервiс-днiпро' in _norm(c.name) or 'сервіс-дніпро' in _norm(c.name)), None)
        if c_emerg:
            return ('matched', c_emerg.id, 95.0)

    # 7. Cleaning (Stepura)
    if 'степура' in cn:
        c_clean = next((c for c in contractors if 'степура' in _norm(c.name)), None)
        if c_clean:
            return ('matched', c_clean.id, 95.0)

    # 8. Water supply (Dniprovodokanal)
    if 'водоканал' in cn:
        c_water = next((c for c in contractors if 'водоканал' in _norm(c.name)), None)
        if c_water:
            return ('matched', c_water.id, 95.0)

    # Signal 2: Substring matching (strip parentheses from contractor name)
    if cn:
        for c in contractors:
            if not c.name: continue
            cleaned_c_name = re.sub(r'\(.*\)', '', c.name).strip()
            norm_c = _norm(cleaned_c_name)
            if len(norm_c) >= 4 and norm_c in cn:
                return ('matched', c.id, 90.0)

    # Signal 3: Fuzzy match
    if cn and RAPIDFUZZ_AVAILABLE and len(cn) >= 3:
        best_s, best_c = 0, None
        for c in contractors:
            if not c.name:
                continue
            s = fuzz.token_sort_ratio(_norm(c.name), cn)
            if s > best_s:
                best_s, best_c = s, c
        if best_s >= FUZZY_AUTO and best_c:
            return ('matched', best_c.id, best_s)
        if best_s >= FUZZY_UNCONFIRMED and best_c:
            return ('unconfirmed', best_c.id, best_s)

    return ('unrecognized', None, None)


def match_payment(db, payment, apartments=None, mapping_keys=None):
    """Match an income payment (amount >= 0) to an apartment."""
    from ..bank_models import MappingKey
    from ..models import Apartment
    if apartments is None: apartments = db.query(Apartment).all()
    if mapping_keys is None: mapping_keys = db.query(MappingKey).all()
    apt_by_num = {a.number.strip().lower(): a for a in apartments if a.number}

    # Signal 1: Saved mapping keys
    pn = _norm(payment.payer_name or '')
    addr = _norm(payment.payer_address or '')
    cn = _norm(payment.correspondent_name or '')
    purp = _norm(payment.purpose or '')
    for mk in mapping_keys:
        kv = _norm(mk.key_value)
        if mk.key_type == 'payer_name':
            if kv and (kv == pn or kv == cn):
                mk.last_used_at = datetime.utcnow(); mk.use_count = (mk.use_count or 0) + 1
                return ('matched', mk.apartment_id, None, 100.0)
        elif mk.key_type == 'address_substring':
            if kv and (kv in addr or kv in purp):
                mk.last_used_at = datetime.utcnow(); mk.use_count = (mk.use_count or 0) + 1
                return ('matched', mk.apartment_id, None, 100.0)
        elif mk.key_type == 'both':
            ks = _norm(mk.key_value_secondary or '')
            if kv and (kv == pn or kv == cn) and ks and (ks in addr or ks in purp):
                mk.last_used_at = datetime.utcnow(); mk.use_count = (mk.use_count or 0) + 1
                return ('matched', mk.apartment_id, None, 100.0)

    # Signal 2: Apartment number from address
    for field in [payment.payer_address or '', payment.purpose or '']:
        m = APT_NUMBER_RE.search(field)
        if m:
            apt = apt_by_num.get(m.group(1).strip().lower())
            if apt: return ('matched', apt.id, None, 95.0)

    # Signal 3: Fuzzy name match
    if RAPIDFUZZ_AVAILABLE:
        name = _norm(payment.payer_name or payment.correspondent_name or '')
        if len(name) >= 3:
            best_s, best_a = 0, None
            for a in apartments:
                if not a.owner_name: continue
                s = fuzz.token_sort_ratio(_norm(a.owner_name), name)
                if s > best_s: best_s, best_a = s, a
            if best_s >= FUZZY_AUTO and best_a:
                return ('matched', best_a.id, None, best_s)
            if best_s >= FUZZY_UNCONFIRMED and best_a:
                return ('unconfirmed', None, best_a.id, best_s)

    return ('unrecognized', None, None, None)


def run_matching_pipeline(db, payment_ids=None, statuses=None):
    from ..bank_models import BankPayment, MappingKey
    from ..models import Apartment, Contractor
    if statuses is None: statuses = ['unrecognized', 'unconfirmed']
    apartments = db.query(Apartment).all()
    contractors = db.query(Contractor).all()
    keys = db.query(MappingKey).all()
    q = db.query(BankPayment)
    if payment_ids: q = q.filter(BankPayment.id.in_(payment_ids))
    else: q = q.filter(BankPayment.match_status.in_(statuses))
    payments = q.all()
    counts = {'matched': 0, 'unconfirmed': 0, 'unrecognized': 0, 'total': len(payments)}
    for p in payments:
        try:
            old = p.match_status
            is_expense = (p.amount or 0) < 0
            
            # 1. Try to match to a contractor (for both expenses and incomes)
            status_c, contractor_id, score_c = match_expense(db, p, contractors)
            
            if contractor_id and status_c == 'matched':
                # Exact match with a contractor
                status = 'matched'
                p.suggested_apartment_id = contractor_id
                p.apartment_id = None
                p.match_score = score_c
            elif is_expense:
                # Expenses NEVER need manual matching. If no contractor, it's just 'matched' without link.
                status = 'matched'
                p.suggested_apartment_id = None
                p.apartment_id = None
                p.match_score = 100.0
            else:
                # 2. Income that didn't match a contractor EXACTLY. Match to an apartment.
                status_a, apt_id, sug_id, score_a = match_payment(db, p, apartments, keys)
                status = status_a
                p.apartment_id = apt_id
                p.suggested_apartment_id = sug_id
                p.match_score = score_a

            p.match_status = status

            if old != status: _log_change(db, p.id, old, status)
            counts[status] = counts.get(status, 0) + 1
        except Exception as e:
            logger.error("Match error %s: %s", p.doc_number, e)
            counts['unrecognized'] += 1
    db.commit()
    return counts

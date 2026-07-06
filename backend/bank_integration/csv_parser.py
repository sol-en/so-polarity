"""Parser for PrivatBank Autoclient CSV export files.

Handles three file types:
- *_opers.csv — current-day transactions
- *_lastday.csv — previous day's transactions
- *_saldo.csv — daily turnover and balance summary
"""

import csv
import io
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Column mappings for transaction files (*_opers.csv, *_lastday.csv, or stmts_*)
TRANSACTION_COLUMNS = {
    'Номер документа': 'doc_number',
    'Номер документу': 'doc_number',
    'Дата операції': 'operation_date',
    'Дата проведения': 'operation_date',
    'Дата документа': 'document_date',
    'Дебет': 'debit',
    'Кредит': 'credit',
    'Сума': 'amount',
    'Валюта': 'currency',
    'Найменування кореспондента': 'correspondent_name',
    'Кореспондент': 'correspondent_name',
    'Рахунок кореспондента': 'correspondent_iban',
    'Код ЄДРПОУ кореспондента': 'correspondent_edrpou',
    'ЄДРПОУ кореспондента': 'correspondent_edrpou',
    'МФО банку кореспондента': 'correspondent_mfo',
    'Найменування банку кореспондента': 'correspondent_bank_name',
    'Назва банку': 'correspondent_bank_name',
    'Код ЄДРПОУ клієнта': 'client_edrpou',
    'МФО банку клієнта': 'client_mfo',
    'Рахунок клієнта': 'client_iban',
    'Рахунок': 'client_iban',
    'Призначення платежу': 'purpose',
    'Гривневе покриття': 'uah_equivalent',
}

# Column mappings for saldo files (*_saldo.csv)
SALDO_COLUMNS = {
    'Дата обороту': 'report_date',
    'Рахунок': 'account_iban',
    'Валюта': 'currency',
    'Вхідний залишок': 'opening_balance',
    'Обороти ДТ': 'debit_turnover',
    'Обороти КТ': 'credit_turnover',
    'Вихідний залишок': 'closing_balance',
}


def detect_file_type(filename: str) -> Optional[str]:
    """Detect CSV file type from filename suffix.

    Returns:
        'opers', 'lastday', 'saldo', or None if unrecognized.
    """
    name_lower = filename.lower()
    if '_opers' in name_lower:
        return 'opers'
    if '_saldo' in name_lower:
        return 'saldo'
    return 'opers'  # Default to opers (transactions) if not specifically a saldo file


def _parse_date(date_str: str) -> Optional[str]:
    """Parse DD.MM.YYYY HH:MM:SS or DD.MM.YYYY into ISO format."""
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Try datetime format first
    for fmt in ['%d.%m.%Y %H:%M:%S', '%d.%m.%Y']:
        try:
            dt = datetime.strptime(date_str, fmt)
            if ' ' in date_str:
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    logger.warning("Could not parse date: %s", date_str)
    return date_str


def _parse_amount(val: str) -> float:
    """Parse amount string to float. Handles '.' as decimal separator and spaces as thousand separators."""
    if not val or not str(val).strip():
        return 0.0
    try:
        # Remove spaces, non-breaking spaces, and replace comma with dot
        clean_val = str(val).strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
        return float(clean_val)
    except (ValueError, TypeError):
        return 0.0


def _read_csv_content(content: bytes, encoding: str = 'cp1251') -> str:
    """Decode CSV bytes, trying the specified encoding then fallback to utf-8."""
    try:
        return content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return content.decode('utf-8', errors='replace')


def _build_column_index(headers: List[str], column_map: Dict[str, str]) -> Dict[str, int]:
    """Build a mapping from semantic field name to column index.

    Tries exact match first, then substring match for robustness.
    """
    index = {}
    clean_headers = [h.strip().strip('\ufeff') for h in headers]

    for csv_col, field_name in column_map.items():
        # Exact match
        for i, h in enumerate(clean_headers):
            if h == csv_col:
                index[field_name] = i
                break
        else:
            # Substring match as fallback
            csv_col_lower = csv_col.lower()
            for i, h in enumerate(clean_headers):
                if csv_col_lower in h.lower() or h.lower() in csv_col_lower:
                    if field_name not in index:
                        index[field_name] = i
                        break

    return index


def parse_transactions_csv(
    content: bytes,
    filename: str,
    encoding: str = 'cp1251'
) -> Tuple[List[Dict], List[str]]:
    """Parse *_opers.csv or *_lastday.csv transaction file.

    Args:
        content: Raw file bytes
        filename: Original filename
        encoding: Character encoding (default cp1251)

    Returns:
        Tuple of (list of parsed payment dicts, list of errors)
    """
    errors = []
    records = []

    try:
        text = _read_csv_content(content, encoding)
        reader = csv.reader(io.StringIO(text), delimiter=';')
        rows = list(reader)
    except Exception as e:
        errors.append(f"Failed to read CSV: {e}")
        return records, errors

    if len(rows) < 2:
        errors.append("CSV file has fewer than 2 rows (no data)")
        return records, errors

    # First row is headers
    col_index = _build_column_index(rows[0], TRANSACTION_COLUMNS)

    if 'doc_number' not in col_index:
        errors.append("Could not find 'Номер документа' column in CSV headers")
        return records, errors

    for row_num, row in enumerate(rows[1:], start=2):
        try:
            if not row or all(not cell.strip() for cell in row):
                continue

            doc_num_idx = col_index['doc_number']
            if doc_num_idx >= len(row):
                continue

            doc_number = row[doc_num_idx].strip()
            if not doc_number:
                import hashlib
                row_hash = hashlib.md5("".join(row).encode('utf-8')).hexdigest()[:10]
                doc_number = f"FAKE_{row_hash}"
            
            is_expense = False
            if 'amount' in col_index and col_index['amount'] < len(row):
                amt_str = row[col_index['amount']].strip().replace(',', '.').replace(' ', '')
                if amt_str and float(amt_str) < 0:
                    is_expense = True
            elif 'debit' in col_index and col_index['debit'] < len(row):
                deb_str = row[col_index['debit']].strip().replace(',', '.').replace(' ', '')
                if deb_str and float(deb_str) > 0:
                    is_expense = True
            
            if is_expense:
                import hashlib
                row_hash = hashlib.md5("".join(row).encode('utf-8')).hexdigest()[:8]
                doc_number = f"{doc_number}-EXPENSE-{row_hash}"

            record = {
                'doc_number': doc_number,
                'source_type': 'csv_statement',
                'source_file': filename,
            }

            # Extract all mapped fields
            for field_name, idx in col_index.items():
                if field_name == 'doc_number':
                    continue
                if idx < len(row):
                    val = row[idx].strip()
                    if field_name in ('debit', 'credit', 'amount', 'uah_equivalent'):
                        record[field_name] = _parse_amount(val)
                    elif field_name in ('operation_date', 'document_date'):
                        record[field_name] = _parse_date(val)
                    else:
                        record[field_name] = val

            # Calculate amount: credit is positive (incoming), debit is negative (outgoing)
            if 'amount' not in record:
                credit = record.get('credit', 0.0)
                debit = record.get('debit', 0.0)
                record['amount'] = credit - debit

            # Skip consolidated incoming registry payments from CSV because they are imported via Gmail detailed registries
            # We MUST KEEP outgoing registry payments (amount < 0) because they are Salary payments (Зарплатний проект)!
            purpose = record.get('purpose', '')
            if purpose and "оплата згiдно реєстру" in purpose.lower() and record.get('amount', 0) > 0:
                continue

            records.append(record)

        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return records, errors


def parse_saldo_csv(
    content: bytes,
    filename: str,
    encoding: str = 'cp1251'
) -> Tuple[List[Dict], List[str]]:
    """Parse *_saldo.csv balance summary file.

    Returns:
        Tuple of (list of saldo record dicts, list of errors)
    """
    errors = []
    records = []

    try:
        text = _read_csv_content(content, encoding)
        reader = csv.reader(io.StringIO(text), delimiter=';')
        rows = list(reader)
    except Exception as e:
        errors.append(f"Failed to read saldo CSV: {e}")
        return records, errors

    if len(rows) < 2:
        errors.append("Saldo CSV has fewer than 2 rows")
        return records, errors

    col_index = _build_column_index(rows[0], SALDO_COLUMNS)

    # For saldo, we also need UAH equivalent columns — they appear after each main column
    # We handle them positionally: the column after each balance/turnover column is its UAH equivalent
    uah_fields = {}
    for field_name, idx in col_index.items():
        if field_name in ('opening_balance', 'debit_turnover', 'credit_turnover', 'closing_balance'):
            uah_fields[field_name + '_uah'] = idx + 1

    for row_num, row in enumerate(rows[1:], start=2):
        try:
            if not row or all(not cell.strip() for cell in row):
                continue

            record = {'source_file': filename}

            for field_name, idx in col_index.items():
                if idx < len(row):
                    val = row[idx].strip()
                    if field_name == 'report_date':
                        record[field_name] = _parse_date(val)
                    elif field_name in ('opening_balance', 'debit_turnover', 'credit_turnover', 'closing_balance'):
                        record[field_name] = _parse_amount(val)
                    else:
                        record[field_name] = val

            # UAH equivalents
            for uah_field, idx in uah_fields.items():
                if idx < len(row):
                    record[uah_field] = _parse_amount(row[idx].strip())

            records.append(record)

        except Exception as e:
            errors.append(f"Saldo row {row_num}: {e}")

    return records, errors

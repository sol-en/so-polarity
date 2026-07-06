"""Parser for PrivatBank registry TXT attachments (fixed-width format).

These files are cp1251-encoded, contain payment breakdowns from grouped
registry transactions, and use fixed-width columns.
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex to detect start of a new payment record line
RECORD_START_RE = re.compile(r'^\s*(\d+(?:\.\d+){2,})')

# Regex to extract report creation date from header
REPORT_DATE_RE = re.compile(r'Дата створення звіту:\s*(\d{2}\.\d{2}\.\d{2,4})\s*(\d{2}:\d{2}:\d{2})?')

# Regex to extract payment order info from header
PAYMENT_ORDER_RE = re.compile(r'Платіжне доручення\s*№\s*(\S+)\s*від\s*(\d{2}\.\d{2}\.\d{4})')

# Stop parsing at this line
STOP_LINE = 'Разом по р/р'

# We will determine these dynamically from the header
# COL_DOC_NUMBER = (0, 18)
# COL_OPER_DAY = (18, 24)
# COL_PAYER_NAME = (24, 57)
# COL_ADDRESS = (68, 93)
# COL_AMOUNT = (122, 135)


def _normalize_text(text: str) -> str:
    """Collapse internal whitespace to single space; strip leading/trailing."""
    return re.sub(r'\s+', ' ', text).strip()


def _extract_fixed_field(line: str, start: int, end: int) -> str:
    """Extract a field from a fixed-width line, handling short lines gracefully."""
    if len(line) <= start:
        return ''
    actual_end = min(end, len(line))
    return line[start:actual_end]


def _parse_amount(amount_str: str) -> float:
    """Parse amount with comma as decimal separator."""
    cleaned = amount_str.strip().replace(',', '.').replace(' ', '')
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse amount: '%s'", amount_str)
        return 0.0


def parse_registry_txt(
    content: bytes,
    encoding: str = 'cp1251',
    source_identifier: str = ''
) -> Tuple[Dict, List[Dict], List[str]]:
    """Parse a PrivatBank registry TXT file.

    Args:
        content: Raw file bytes
        encoding: Character encoding (default cp1251)
        source_identifier: Gmail message ID or filename for logging

    Returns:
        Tuple of (header_info dict, list of payment records, list of errors)
    """
    errors = []
    records = []
    header_info = {
        'report_datetime': None,
        'report_year': None,
        'report_month': None,
        'payment_order_number': None,
        'payment_order_date': None,
    }

    try:
        text = content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('utf-8', errors='replace')
            errors.append(f"Encoding fallback used for {source_identifier}")

    lines = text.split('\n')

    # Phase 1: Parse header
    header_parsed = False
    first_record_line = 0
    cols = []

    for i, line in enumerate(lines):
        # Extract report date
        date_match = REPORT_DATE_RE.search(line)
        if date_match:
            date_str = date_match.group(1)
            time_str = date_match.group(2) or '00:00:00'
            try:
                if len(date_str.split('.')[-1]) == 2:
                    dt = datetime.strptime(f"{date_str} {time_str}", '%d.%m.%y %H:%M:%S')
                else:
                    dt = datetime.strptime(f"{date_str} {time_str}", '%d.%m.%Y %H:%M:%S')
                header_info['report_datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                header_info['report_year'] = dt.year
                header_info['report_month'] = dt.month
            except ValueError as e:
                errors.append(f"Could not parse report date '{date_str}': {e}")

        # Extract payment order info
        order_match = PAYMENT_ORDER_RE.search(line)
        if order_match:
            header_info['payment_order_number'] = order_match.group(1)
            header_info['payment_order_date'] = order_match.group(2)
            
        # Detect table header for dynamic column sizes
        if '|' in line and 'Опер' in line and 'П.І.Б.' in line:
            idx = [-1] + [pos for pos, c in enumerate(line) if c == '|'] + [1000]
            cols = [(idx[k]+1, idx[k+1]) for k in range(len(idx)-1)]

        # Check if this line starts a payment record
        if RECORD_START_RE.match(line):
            first_record_line = i
            header_parsed = True
            break

    if not header_parsed:
        errors.append("No payment records found in file")
        return header_info, records, errors
        
    if not cols or len(cols) < 8:
        errors.append("Could not determine table columns from header")
        return header_info, records, errors

    if header_info['report_year'] is None:
        errors.append("Could not determine report year from header")
        return header_info, records, errors

    # Phase 2: Parse payment records
    report_year = header_info['report_year']
    report_month = header_info['report_month']

    current_record = None
    payer_name_parts = []
    address_parts = []

    def _finalize_record():
        """Finalize the current record by concatenating multi-line fields."""
        nonlocal current_record, payer_name_parts, address_parts
        if current_record:
            current_record['payer_name'] = _normalize_text(' '.join(payer_name_parts))
            current_record['payer_address'] = _normalize_text(' '.join(address_parts))
            records.append(current_record)
            current_record = None
            payer_name_parts = []
            address_parts = []

    for i in range(first_record_line, len(lines)):
        line = lines[i]

        # Stop at footer
        if STOP_LINE in line:
            _finalize_record()
            break

        # Check if this is a new record start
        record_match = RECORD_START_RE.match(line)
        if record_match:
            # Finalize previous record
            _finalize_record()

            doc_number = record_match.group(1).strip()
            oper_day_str = _extract_fixed_field(line, *cols[1]).strip()
            payer_fragment = _extract_fixed_field(line, *cols[2])
            address_fragment = _extract_fixed_field(line, *cols[4])
            amount_str = _extract_fixed_field(line, *cols[7])

            # Infer date per user request: Use payment_order_date or report_date
            operation_date = None
            if header_info.get('payment_order_date'):
                try:
                    # payment_order_date is parsed as DD.MM.YYYY
                    d, m, y = header_info['payment_order_date'].split('.')
                    operation_date = f"{y}-{m}-{d}"
                except Exception:
                    pass
            
            if not operation_date and header_info.get('report_datetime'):
                operation_date = header_info['report_datetime'][:10] # YYYY-MM-DD
                
            # Fallback to row oper_day
            if not operation_date:
                oper_year = report_year
                if oper_day_str and '.' in oper_day_str:
                    try:
                        oper_parts = oper_day_str.split('.')
                        oper_month = int(oper_parts[1])
                        oper_day = int(oper_parts[0])
    
                        if oper_month > report_month:
                            oper_year = report_year - 1
    
                        operation_date = f"{oper_year}-{oper_month:02d}-{oper_day:02d}"
                    except (ValueError, IndexError):
                        pass

            current_record = {
                'doc_number': doc_number,
                'operation_date': operation_date,
                'amount': _parse_amount(amount_str),
                'source_type': 'registry_email',
                'source_file': source_identifier,
                'payment_order_number': header_info.get('payment_order_number'),
                'payment_order_date': header_info.get('payment_order_date'),
            }

            payer_name_parts = [payer_fragment]
            address_parts = [address_fragment]

        elif current_record:
            # Continuation line — append to payer_name and address fields
            payer_fragment = _extract_fixed_field(line, *cols[2])
            address_fragment = _extract_fixed_field(line, *cols[4])

            if payer_fragment.strip():
                payer_name_parts.append(payer_fragment)
            if address_fragment.strip():
                address_parts.append(address_fragment)

    # Finalize last record (if file doesn't end with STOP_LINE)
    _finalize_record()

    return header_info, records, errors

"""Database models for bank integration (PrivatBank CSV + Registry imports)."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class BankPayment(Base):
    """Raw imported bank payment record from either CSV statement or registry email."""
    __tablename__ = "bank_payments"

    id = Column(Integer, primary_key=True, index=True)

    # Deduplication key — bank document number (unique across both sources)
    doc_number = Column(String, unique=True, index=True, nullable=False)

    # Source identification
    source_type = Column(String, nullable=False)  # 'csv_statement' or 'registry_email'
    source_file = Column(String, nullable=True)  # filename for CSV; Gmail message ID for email
    gmail_message_id = Column(String, nullable=True, index=True)

    # Date fields
    operation_date = Column(String, nullable=True)  # ISO format date or datetime
    document_date = Column(String, nullable=True)

    # Amount fields
    amount = Column(Float, nullable=False, default=0.0)
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    currency = Column(String, default="UAH")
    uah_equivalent = Column(Float, nullable=True)

    # Correspondent info (from CSV)
    correspondent_name = Column(String, nullable=True)
    correspondent_iban = Column(String, nullable=True)
    correspondent_edrpou = Column(String, nullable=True)
    correspondent_mfo = Column(String, nullable=True)
    correspondent_bank_name = Column(String, nullable=True)

    # Client info (from CSV — our organization)
    client_edrpou = Column(String, nullable=True)
    client_mfo = Column(String, nullable=True)
    client_iban = Column(String, nullable=True)

    # Payer info (from registry TXT)
    payer_name = Column(String, nullable=True)
    payer_address = Column(String, nullable=True)

    # Payment purpose
    purpose = Column(Text, nullable=True)

    # Matching status
    match_status = Column(String, default="unrecognized", index=True)
    # 'matched', 'unconfirmed', 'unrecognized', 'mapped'

    # Linked apartment
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True)
    suggested_apartment_id = Column(Integer, nullable=True)
    match_score = Column(Float, nullable=True)  # fuzzy match score

    # Posted to ledger
    posted = Column(Boolean, default=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    # Registry-specific header data
    payment_order_number = Column(String, nullable=True)
    payment_order_date = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    apartment = relationship("Apartment", foreign_keys=[apartment_id])
    transaction = relationship("Transaction", foreign_keys=[transaction_id])

    status_logs = relationship("MatchStatusLog", back_populates="bank_payment")


class BankBalanceSummary(Base):
    """Daily balance/turnover summary from *_saldo.csv files."""
    __tablename__ = "bank_balance_summary"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(String, nullable=False)
    account_iban = Column(String, nullable=True)
    currency = Column(String, default="UAH")

    opening_balance = Column(Float, default=0.0)
    opening_balance_uah = Column(Float, default=0.0)
    debit_turnover = Column(Float, default=0.0)
    debit_turnover_uah = Column(Float, default=0.0)
    credit_turnover = Column(Float, default=0.0)
    credit_turnover_uah = Column(Float, default=0.0)
    closing_balance = Column(Float, default=0.0)
    closing_balance_uah = Column(Float, default=0.0)

    source_file = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ImportLog(Base):
    """Log entry for each import run."""
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_identifier = Column(String, nullable=False)  # filename or Gmail message ID
    source_type = Column(String, nullable=False)  # 'csv_opers', 'csv_lastday', 'csv_saldo', 'registry_email'
    status = Column(String, nullable=False)  # 'success', 'error', 'partial'
    total_parsed = Column(Integer, default=0)
    inserted = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MappingKey(Base):
    """Saved payer-to-apartment mapping key for automatic matching."""
    __tablename__ = "mapping_keys"

    id = Column(Integer, primary_key=True, index=True)

    key_type = Column(String, nullable=False)
    # 'payer_name', 'address_substring', 'both'

    key_value = Column(String, nullable=False)  # primary match value
    key_value_secondary = Column(String, nullable=True)  # secondary value for 'both' type

    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    created_by = Column(String, default="admin")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    use_count = Column(Integer, default=0)
    note = Column(Text, nullable=True)

    apartment = relationship("Apartment")

    __table_args__ = (
        UniqueConstraint('key_type', 'key_value', name='uq_mapping_key_type_value'),
    )


class MatchStatusLog(Base):
    """Audit trail for match status transitions on bank payments."""
    __tablename__ = "match_status_log"

    id = Column(Integer, primary_key=True, index=True)
    bank_payment_id = Column(Integer, ForeignKey("bank_payments.id"), nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    actor = Column(String, default="system")  # 'system' or 'admin'
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    bank_payment = relationship("BankPayment", back_populates="status_logs")

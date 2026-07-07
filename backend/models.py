from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class OrganizationDetail(Base):
    __tablename__ = "organization_details"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    edrpou = Column(String, nullable=True)
    iban = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    mfo = Column(String, nullable=True)

class Apartment(Base):
    __tablename__ = "apartments"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True, nullable=False)
    owner_name = Column(String, nullable=True)
    area_m2 = Column(Float, default=0.0)
    has_lift_exemption = Column(Boolean, default=False)
    residents_count = Column(Integer, default=0)
    initial_balance = Column(Float, default=0.0) # Balance at start of tracking

    logs = relationship("ApartmentLog", back_populates="apartment")
    charges = relationship("Charge", back_populates="apartment")
    transactions = relationship("Transaction", back_populates="apartment")

class ApartmentLog(Base):
    __tablename__ = "apartments_log"
    id = Column(Integer, primary_key=True, index=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"))
    date = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String) # 'owner_change', 'area_change', 'adjustment'
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    period = Column(String, nullable=True) # YYYY-MM, specifically for adjustments
    amount = Column(Float, nullable=True) # for adjustment types
    description = Column(String, nullable=True)

    apartment = relationship("Apartment", back_populates="logs")

class Tariff(Base):
    __tablename__ = "tariffs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) # e.g., 'Maintenance', 'Lift', 'Gas'
    value = Column(Float, nullable=False)
    unit = Column(String, default="m2") # 'm2', 'person', 'flat'
    is_active = Column(Boolean, default=True)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String) # 'income', 'expense'
    group = Column(String, nullable=True) # e.g., 'Utility', 'Administrative'

    transactions = relationship("Transaction", back_populates="category")

class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    default_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    active = Column(Boolean, default=True)
    initial_balance = Column(Float, default=0.0)
    initial_balance_date = Column(String, nullable=True)

    default_category = relationship("Category")
    transactions = relationship("Transaction", back_populates="contractor")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False) # ISO format
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True) # purpose
    comment = Column(Text, nullable=True)
    counterparty = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True)
    bank_tx_id = Column(String, unique=True, index=True, nullable=True)

    category = relationship("Category", back_populates="transactions")
    contractor = relationship("Contractor", back_populates="transactions")
    apartment = relationship("Apartment", back_populates="transactions")

class Charge(Base):
    __tablename__ = "charges"
    id = Column(Integer, primary_key=True, index=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"))
    period = Column(String, nullable=False) # YYYY-MM
    owner_name = Column(String, nullable=True)
    area_m2 = Column(Float, default=0.0)
    maintenance_fee = Column(Float, default=0.0)
    lift_fee = Column(Float, default=0.0)
    gas_fee = Column(Float, default=0.0)
    adjustment = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    apartment = relationship("Apartment", back_populates="charges")


class ContractorObligation(Base):
    __tablename__ = "contractor_obligations"
    id = Column(Integer, primary_key=True, index=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=False)
    name = Column(String, nullable=False)
    amount_type = Column(String, nullable=False) # 'fixed' | 'calculated'
    fixed_amount = Column(Float, nullable=True)
    calculation_basis = Column(String, nullable=True)
    season_adjust = Column(Integer, default=0)
    valid_from = Column(String, nullable=False) # YYYY-MM
    valid_to = Column(String, nullable=True)
    include_in_forecast = Column(Integer, default=1)
    initial_balance = Column(Float, default=0.0)
    initial_balance_date = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    note = Column(Text, nullable=True)
    
    contractor = relationship("Contractor", backref="obligations")
    category = relationship("Category")


class PlannedActivity(Base):
    __tablename__ = "planned_activities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    planned_amount = Column(Float, nullable=False)
    planned_month = Column(String, nullable=False) # YYYY-MM
    include_in_forecast = Column(Integer, default=1)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContractorCharge(Base):
    __tablename__ = "contractor_charges"
    id = Column(Integer, primary_key=True, index=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=False)
    obligation_id = Column(Integer, ForeignKey("contractor_obligations.id"), nullable=True)
    period = Column(String, nullable=False) # YYYY-MM
    accrued_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    contractor = relationship("Contractor", backref="charges")
    obligation = relationship("ContractorObligation")


class UserAccess(Base):
    __tablename__ = "user_access"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False, default="resident") # 'admin' or 'resident'
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True) # Linked apartment
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    apartment = relationship("Apartment")


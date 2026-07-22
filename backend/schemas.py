from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class ApartmentBase(BaseModel):
    number: str
    owner_name: Optional[str] = None
    area_m2: Optional[float] = 0.0
    has_lift_exemption: Optional[bool] = False
    residents_count: Optional[int] = 0
    initial_balance: Optional[float] = 0.0
    current_balance: Optional[float] = 0.0
    email: Optional[str] = None

class ApartmentCreate(ApartmentBase):
    pass

class Apartment(ApartmentBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ApartmentLogBase(BaseModel):
    apartment_id: int
    type: str # 'owner_change', 'area_change', 'adjustment'
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    period: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None

class ApartmentLogCreate(ApartmentLogBase):
    pass

class ApartmentLog(ApartmentLogBase):
    id: int
    apartment_id: int
    date: datetime
    model_config = ConfigDict(from_attributes=True)

class TariffBase(BaseModel):
    name: str
    value: float
    unit: str = "m2"
    is_active: bool = True

class Tariff(TariffBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    name: str
    type: str
    group: Optional[str] = None

class Category(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ContractorObligationBase(BaseModel):
    contractor_id: int
    name: str
    amount_type: str
    fixed_amount: Optional[float] = None
    calculation_basis: Optional[str] = None
    season_adjust: int = 0
    valid_from: str
    valid_to: Optional[str] = None
    include_in_forecast: int = 1
    initial_balance: float = 0.0
    initial_balance_date: Optional[str] = None
    category_id: Optional[int] = None
    note: Optional[str] = None

class ContractorObligationCreate(ContractorObligationBase):
    pass

class ContractorObligationResponse(ContractorObligationBase):
    id: int

    class Config:
        from_attributes = True

class ContractorBase(BaseModel):
    name: str
    default_category_id: Optional[int] = None
    active: Optional[bool] = True
    initial_balance: Optional[float] = 0.0
    initial_balance_date: Optional[str] = None

class Contractor(ContractorBase):
    id: int
    default_category: Optional[Category] = None
    obligations: List[ContractorObligationResponse] = []
    model_config = ConfigDict(from_attributes=True)

class TransactionBase(BaseModel):
    date: str
    amount: float
    description: Optional[str] = None
    comment: Optional[str] = None
    counterparty: Optional[str] = None
    category_id: int
    contractor_id: Optional[int] = None
    apartment_id: Optional[int] = None
    bank_tx_id: Optional[str] = None

class Transaction(TransactionBase):
    id: int
    category: Optional[Category] = None
    contractor: Optional[Contractor] = None
    apartment: Optional[Apartment] = None
    model_config = ConfigDict(from_attributes=True)

class ChargeBase(BaseModel):
    apartment_id: int
    period: str
    owner_name: Optional[str] = None
    area_m2: float = 0.0
    maintenance_fee: float = 0.0
    lift_fee: float = 0.0
    gas_fee: float = 0.0
    adjustment: float = 0.0
    total: float

class Charge(ChargeBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CalculationRequest(BaseModel):
    period: str # YYYY-MM

class ReportRequest(BaseModel):
    start_period: str # YYYY-MM
    end_period: str # YYYY-MM

class MonthlyDetail(BaseModel):
    period: str
    maintenance_fee: float = 0.0
    lift_fee: float = 0.0
    gas_fee: float = 0.0
    charge: float
    payment: float
    adjustment: float

class ApartmentReport(BaseModel):
    apartment_id: int
    apartment_number: str
    owner_name: Optional[str]
    area_m2: Optional[float] = None
    email: Optional[str] = None
    start_balance: float
    end_balance: float
    total_charges: float
    total_payments: float
    monthly_details: List[MonthlyDetail]


class PlannedActivityBase(BaseModel):
    name: str
    planned_amount: float
    planned_month: str
    include_in_forecast: int = 1
    note: Optional[str] = None

class PlannedActivityCreate(PlannedActivityBase):
    pass

class PlannedActivityUpdate(BaseModel):
    planned_amount: Optional[float] = None
    planned_month: Optional[str] = None

class PlannedActivityResponse(PlannedActivityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ContractorChargeBase(BaseModel):
    contractor_id: int
    obligation_id: Optional[int] = None
    period: str
    accrued_amount: float
    paid_amount: float = 0.0

class ContractorChargeResponse(ContractorChargeBase):
    id: int
    balance: float = 0.0 # Accrued - Paid
    created_at: datetime

    class Config:
        from_attributes = True

class ForecastScenarioRequest(BaseModel):
    start_month: str
    end_month: str
    starting_balance: float = 0.0
    starting_debt: float = 0.0
    resident_tariff: float
    collection_rate: float = 1.0

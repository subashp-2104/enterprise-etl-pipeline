from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

# --- Stripe Raw Input Models ---

class StripeCustomerRaw(BaseModel):
    id: str = Field(..., min_length=1)
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created: int  # Unix timestamp
    currency: Optional[str] = None
    delinquent: Optional[bool] = False

class StripeChargeRaw(BaseModel):
    id: str = Field(..., min_length=1)
    customer: str = Field(..., min_length=1)
    amount: int  # Amount in cents
    currency: str = Field(..., min_length=3, max_length=3)
    status: str
    created: int  # Unix timestamp
    paid: bool
    refunded: bool

# --- Salesforce Raw Input Models ---

class SalesforceAccountRaw(BaseModel):
    Id: str = Field(..., min_length=1)
    Name: str
    Email__c: Optional[str] = None
    Phone: Optional[str] = None
    CreatedDate: str  # ISO timestamp
    SystemModstamp: str  # ISO timestamp

class SalesforceOpportunityRaw(BaseModel):
    Id: str = Field(..., min_length=1)
    AccountId: str = Field(..., min_length=1)
    Name: str
    Amount: Optional[float] = 0.0
    CurrencyIsoCode: str = Field(..., min_length=3, max_length=3)
    StageName: str
    CloseDate: str  # YYYY-MM-DD
    CreatedDate: str  # ISO timestamp
    SystemModstamp: str  # ISO timestamp

# --- Unified Output Models (Data Warehouse Target) ---

class UnifiedCustomer(BaseModel):
    source_system: str
    source_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("source_system")
    @classmethod
    def validate_source_system(cls, v: str) -> str:
        v_low = v.lower()
        if v_low not in ["stripe", "salesforce"]:
            raise ValueError("source_system must be 'stripe' or 'salesforce'")
        return v_low

class UnifiedTransaction(BaseModel):
    source_system: str
    source_transaction_id: str
    customer_id: str  # References source_id in the unified customer table
    amount: float     # Standardized currency amount (not cents)
    currency: str     # Uppercased currency (e.g. USD)
    status: str       # Standardized status
    transaction_date: datetime
    updated_at: datetime

    @field_validator("source_system")
    @classmethod
    def validate_source_system(cls, v: str) -> str:
        v_low = v.lower()
        if v_low not in ["stripe", "salesforce"]:
            raise ValueError("source_system must be 'stripe' or 'salesforce'")
        return v_low

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()

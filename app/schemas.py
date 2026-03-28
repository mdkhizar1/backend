from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import re


# ── Auth Schemas ──────────────────────────────────────────────
class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v):
        if not re.match(r"^\+?[\d\s\-]{10,15}$", v):
            raise ValueError("Invalid phone number")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TransactionTokenRequest(BaseModel):
    password: str  # Re-auth required for fund transfer


class TransactionTokenResponse(BaseModel):
    transaction_token: str
    expires_in: int = 300  # 5 minutes


# ── User / Account Schemas ─────────────────────────────────────
class AccountOut(BaseModel):
    id: UUID
    account_number: str
    balance: float
    account_type: str
    ifsc_code: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str
    is_active: bool
    created_at: datetime
    account: Optional[AccountOut] = None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Must contain a digit")
        return v


# ── Transaction Schemas ────────────────────────────────────────
class FundTransferRequest(BaseModel):
    to_account_number: str
    amount: float
    description: Optional[str] = None
    transaction_token: str  # Required for every fund transfer

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        if v > 500000:
            raise ValueError("Single transfer limit is ₹5,00,000")
        return round(v, 2)


class TransactionOut(BaseModel):
    id: UUID
    amount: float
    transaction_type: str
    status: str
    description: Optional[str]
    reference_id: str
    created_at: datetime
    from_account_number: Optional[str] = None
    to_account_number: Optional[str] = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: List[TransactionOut]
    total: int
    page: int
    per_page: int


class DashboardResponse(BaseModel):
    user: UserOut
    account: AccountOut
    recent_transactions: List[TransactionOut]

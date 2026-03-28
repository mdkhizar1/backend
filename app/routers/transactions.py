from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User, Account, Transaction, TransactionType, TransactionStatus
from app.schemas import FundTransferRequest, TransactionOut, TransactionListResponse
from app.auth import get_current_user, verify_transaction_token
from datetime import datetime

router = APIRouter()


def serialize_transaction(txn: Transaction, account_id) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        amount=txn.amount,
        transaction_type=txn.transaction_type.value,
        status=txn.status.value,
        description=txn.description,
        reference_id=txn.reference_id,
        created_at=txn.created_at,
        from_account_number=txn.from_account.account_number if txn.from_account else None,
        to_account_number=txn.to_account.account_number if txn.to_account else None,
    )


# ── Fund Transfer ─────────────────────────────────────────────────
@router.post("/transfer", response_model=TransactionOut)
async def fund_transfer(
    payload: FundTransferRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Validate transaction token (re-auth check)
    if not verify_transaction_token(payload.transaction_token, str(current_user.id)):
        raise HTTPException(status_code=401, detail="Transaction token invalid or expired. Please re-authenticate.")

    # 2. Load sender account
    result = await db.execute(
        select(Account).where(Account.user_id == current_user.id, Account.is_active == True)
    )
    sender_account = result.scalar_one_or_none()
    if not sender_account:
        raise HTTPException(status_code=404, detail="Sender account not found")

    # 3. Load recipient account
    result = await db.execute(
        select(Account).where(
            Account.account_number == payload.to_account_number,
            Account.is_active == True,
        )
    )
    receiver_account = result.scalar_one_or_none()
    if not receiver_account:
        raise HTTPException(status_code=404, detail="Recipient account not found")

    if sender_account.id == receiver_account.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to your own account")

    # 4. Balance check
    if sender_account.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 5. Execute transfer
    sender_account.balance = round(sender_account.balance - payload.amount, 2)
    receiver_account.balance = round(receiver_account.balance + payload.amount, 2)

    txn = Transaction(
        from_account_id=sender_account.id,
        to_account_id=receiver_account.id,
        amount=payload.amount,
        transaction_type=TransactionType.TRANSFER,
        status=TransactionStatus.SUCCESS,
        description=payload.description or f"Transfer to {payload.to_account_number}",
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    # Eagerly load relationships for response
    await db.refresh(txn, ["from_account", "to_account"])

    return serialize_transaction(txn, sender_account.id)


# ── Transaction History ───────────────────────────────────────────
@router.get("/history", response_model=TransactionListResponse)
async def transaction_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Count total
    count_q = select(func.count(Transaction.id)).where(
        or_(
            Transaction.from_account_id == account.id,
            Transaction.to_account_id == account.id,
        )
    )
    total = (await db.execute(count_q)).scalar()

    # Paginated fetch with relationships
    txns_q = (
        select(Transaction)
        .options(selectinload(Transaction.from_account), selectinload(Transaction.to_account))
        .where(
            or_(
                Transaction.from_account_id == account.id,
                Transaction.to_account_id == account.id,
            )
        )
        .order_by(Transaction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    txns_result = await db.execute(txns_q)
    txns = txns_result.scalars().all()

    return TransactionListResponse(
        transactions=[serialize_transaction(t, account.id) for t in txns],
        total=total,
        page=page,
        per_page=per_page,
    )


# ── Dashboard (balance + recent 5 transactions) ───────────────────
@router.get("/dashboard-summary")
async def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    txns_q = (
        select(Transaction)
        .options(selectinload(Transaction.from_account), selectinload(Transaction.to_account))
        .where(
            or_(
                Transaction.from_account_id == account.id,
                Transaction.to_account_id == account.id,
            )
        )
        .order_by(Transaction.created_at.desc())
        .limit(5)
    )
    txns = (await db.execute(txns_q)).scalars().all()

    return {
        "balance": account.balance,
        "account_number": account.account_number,
        "account_type": account.account_type,
        "ifsc_code": account.ifsc_code,
        "recent_transactions": [serialize_transaction(t, account.id) for t in txns],
    }

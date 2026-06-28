"""
crud.py — All database read/write operations.
Routes call these functions and pass in an AsyncSession from get_db().
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import OTPRecord, User
from backend.utils.auth import hash_password, verify_password, OTP_EXPIRE_MINUTES


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def get_user_by_identifier(db: AsyncSession, identifier: str) -> Optional[User]:
    """
    Look up a user by email, mobile, or PAN.
    Identifier is matched case-insensitively.
    """
    ident = identifier.strip()
    result = await db.execute(
        select(User).where(
            or_(
                User.email == ident.lower(),
                User.mobile == ident,
                User.pan == ident.upper(),
            )
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    mobile: str,
    first_name: str,
    last_name: str,
    password: str,
    pan: str = "",
) -> User:
    user = User(
        email=email.lower(),
        mobile=mobile or None,
        pan=pan.upper() or None,
        first_name=first_name,
        last_name=last_name,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, identifier: str, password: str
) -> Optional[User]:
    user = await get_user_by_identifier(db, identifier)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ── OTP CRUD ──────────────────────────────────────────────────────────────────

async def store_otp(db: AsyncSession, contact: str, otp: str) -> None:
    """Hash the OTP and persist it. Invalidates previous OTPs for the same contact."""
    # Mark previous OTPs as used
    await db.execute(
        update(OTPRecord)
        .where(OTPRecord.contact == contact, OTPRecord.used == False)  # noqa: E712
        .values(used=True)
    )
    record = OTPRecord(
        contact=contact,
        otp_hash=hash_password(otp),  # store bcrypt hash, not plaintext
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(record)
    await db.commit()


async def verify_otp(db: AsyncSession, contact: str, otp: str) -> bool:
    """Returns True if a valid, unexpired, unused OTP matches. Marks it used."""
    result = await db.execute(
        select(OTPRecord).where(
            OTPRecord.contact == contact,
            OTPRecord.used == False,  # noqa: E712
            OTPRecord.expires_at > datetime.now(timezone.utc),
        ).order_by(OTPRecord.created_at.desc())
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    if not verify_password(otp, record.otp_hash):
        return False
    # Mark as used
    record.used = True
    await db.commit()
    return True

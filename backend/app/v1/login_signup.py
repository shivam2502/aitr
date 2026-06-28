"""
login_signup.py — Auth routes backed by PostgreSQL.
  POST /auth/signup        — create account
  POST /auth/login         — OAuth2 password flow → JWT
  POST /auth/otp/send      — generate & persist OTP
  POST /auth/otp/verify    — verify OTP → JWT
  GET  /auth/me            — protected: return current user
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.main import app
from backend.db.database import get_db
from backend.db import crud
from backend.utils.auth import (
    create_access_token,
    decode_access_token,
    generate_otp,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    mobile: str
    password: str
    pan: Optional[str] = ""

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("pan")
    @classmethod
    def pan_format(cls, v: str) -> str:
        if v and (
            len(v) != 10
            or not v[:5].isalpha()
            or not v[5:9].isdigit()
            or not v[9].isalpha()
        ):
            raise ValueError("Invalid PAN format (e.g. ABCDE1234F)")
        return v.upper() if v else v


class OTPSendRequest(BaseModel):
    contact: str           # email or mobile
    method: str = "email"  # "email" | "phone"


class OTPVerifyRequest(BaseModel):
    contact: str
    otp: str


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await crud.get_user_by_email(db, payload.get("sub", ""))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    if await crud.get_user_by_identifier(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if body.pan and await crud.get_user_by_identifier(db, body.pan):
        raise HTTPException(status_code=400, detail="PAN already registered")

    user = await crud.create_user(
        db,
        email=body.email,
        mobile=body.mobile,
        first_name=body.first_name,
        last_name=body.last_name,
        password=body.password,
        pan=body.pan or "",
    )
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.post("/auth/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Standard OAuth2 password flow. username = email | PAN | mobile."""
    user = await crud.authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.post("/auth/otp/send")
async def otp_send(body: OTPSendRequest, db: AsyncSession = Depends(get_db)):
    """Generate, hash, and store an OTP. In dev mode returns it in the response."""
    otp = generate_otp()
    await crud.store_otp(db, body.contact, otp)

    # TODO: plug in SendGrid (email) or Twilio (SMS) here
    print(f"[DEV] OTP for {body.contact}: {otp}")

    return {"message": f"OTP sent to {body.contact}", "dev_otp": otp}


@app.post("/auth/otp/verify")
async def otp_verify(body: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP against the DB record. Returns a JWT on success."""
    valid = await crud.verify_otp(db, body.contact, body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Find or create a stub user for first-time OTP logins
    user = await crud.get_user_by_identifier(db, body.contact)
    if not user:
        is_email = "@" in body.contact
        user = await crud.create_user(
            db,
            email=body.contact if is_email else f"{body.contact}@otp.taxease",
            mobile="" if is_email else body.contact,
            first_name="",
            last_name="",
            password=generate_otp(16),  # random unusable password
        )

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.get("/auth/me")
async def me(current_user=Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user.to_dict()

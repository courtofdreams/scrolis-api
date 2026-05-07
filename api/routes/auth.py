from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

from service.db import get_db
from service.models.authentication import RefreshToken, User, AuthProvider, SocialCredentials
from api.models.requests import SocialCredentialsRequest
from .security import create_access_token, create_refresh_token, require_login
from service.app_services import mongo_db_service
import logging

router = APIRouter()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
logger = logging.getLogger(__name__)

class RegisterRequest(BaseModel):
    full_name: str
    username: str
    email: EmailStr
    password: str
    
class LoginRequest(BaseModel):
    identifier: str | None = None
    email: EmailStr | None = None
    username: str | None = None
    password: str
    
class UpdateNeedToConnectedSocialRequest(BaseModel):
    value: bool    

def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters"
        )
    if len(password) > 128:
        raise HTTPException(
            status_code=400,
            detail="Password must be at most 128 characters"
        )

def hash_value(value: str) -> str:
    return pwd_context.hash(value)

def hash_password(password: str) -> str:
    validate_password(password)
    return pwd_context.hash(password)



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@router.post("/auth/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    field_errors = []
    existing_email = db.query(User).filter(User.email == data.email.lower()).first()
    
    if existing_email:
        field_errors.append({
            "field": "email",
            "message": "An account with this email already exists."
        })

    existing_username = db.query(User).filter(User.username == data.username).first()
    if existing_username:
        field_errors.append({
            "field": "username",
            "message": "This username already exists."
        })
    
    if field_errors:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Please fix the errors below.",
                "fields": field_errors,
            }
        )    

    user = User(
        full_name=data.full_name,
        username=data.username,
        email=data.email.lower()
    )
    db.add(user)
    db.flush()

    password_hash = hash_password(data.password)

    auth_provider = AuthProvider(
        user_id=user.id,
        provider="local",
        password_hash=password_hash
    )
    db.add(auth_provider)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()

    refresh_token_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_value(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(refresh_token_row)

    db.commit()
    db.refresh(user)
    
    logs = mongo_db_service.update_user_log(str(user.id))

    return {
        "message": "User created successfully",
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "need_to_connected_social": user.need_to_connected_social,
            "login_streak": logs.get("loginStreak", 0)
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.get("/auth/me")
def me(current_user: User = Depends(require_login)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "need_to_connected_social": current_user.need_to_connected_social,
    }    
    
@router.put("/user/need-to-connected-social")   
def update_need_to_connected_social(data: UpdateNeedToConnectedSocialRequest, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    current_user.need_to_connected_social = data.value
    db.commit()
    return {"message": "Need to connected social updated successfully"}


@router.put("/user/social-credentials")
def upsert_social_credentials(
    payload: SocialCredentialsRequest,
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    print(f"Received social credentials: {payload}")  # Debug print statement
    social_credentials = (
        db.query(SocialCredentials)
        .filter(SocialCredentials.user_id == current_user.id)
        .first()
    )

    if not social_credentials:
        social_credentials = SocialCredentials(user_id=current_user.id)

    social_credentials.twitter_access_token = payload.twitter_access_token
    social_credentials.twitter_user_id = payload.twitter_user_id
    social_credentials.reddit_access_token = payload.reddit_access_token
    social_credentials.reddit_username = payload.reddit_username

    current_user.need_to_connected_social = False

    db.add(social_credentials)
    db.commit()

    return {
        "message": "Social credentials saved successfully",
        "user_id": str(current_user.id),
    }


@router.get("/user/login-streak")
def get_login_streak(current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    logs = mongo_db_service.get_user_login_streak(str(current_user.id))
    return {"login_streak": logs}


@router.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    login_identifier = data.identifier
    if not login_identifier:
        raise HTTPException(
            status_code=400,
            detail="Provide either username or email to log in."
        )

    if data.email or (data.identifier and "@" in data.identifier):
        user = db.query(User).filter(User.email == data.email).first()
    else:
        user = db.query(User).filter(User.username == data.username).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username/email or password."
        )

    auth_provider = (
        db.query(AuthProvider)
        .filter(AuthProvider.user_id == user.id)
        .filter(AuthProvider.provider == "local")
        .first()
    )

    if not auth_provider or not auth_provider.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid username/email or password."
        )

    if not verify_password(data.password, auth_provider.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid username/email or password."
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()

    refresh_token_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_value(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(refresh_token_row)
    db.commit()
    
    logs = mongo_db_service.update_user_log(str(user.id))
    logger.info(f"User {user.id} logged in. Updated login streak.")

    return {
        "message": "Login successful",
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "need_to_connected_social": user.need_to_connected_social,
            "login_streak": logs.get("loginStreak", 0)
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
        
            
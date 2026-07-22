from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import os
from datetime import datetime, timedelta
import jwt

from google.oauth2 import id_token
from google.auth.transport import requests

from backend.database import get_db
from backend.models import UserAccess

router = APIRouter(tags=["auth"])

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

class TokenRequest(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    apartment_id: Optional[int]
    email: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login/google", response_model=TokenResponse)
def login_google(request: TokenRequest, db: Session = Depends(get_db)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
        
    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(
            request.token, requests.Request(), GOOGLE_CLIENT_ID
        )
        
        email = idinfo.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
            
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Google token: {str(e)}")
        
    from sqlalchemy import func
    # Check if the user is in our allowlist
    user = db.query(UserAccess).filter(func.lower(UserAccess.email) == email.lower()).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Ви успішно авторизувались як {email}, але у вас немає доступу до системи. Зверніться до адміністратора."
        )
        
    # Generate our own internal JWT token
    access_token = create_access_token(
        data={
            "sub": user.email, 
            "role": user.role, 
            "apartment_id": user.apartment_id
        }
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": user.role,
        "apartment_id": user.apartment_id,
        "email": user.email
    }

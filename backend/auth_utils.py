from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

from backend.database import get_db
from backend.models import UserAccess

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/google")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-in-production")
ALGORITHM = "HS256"

class CurrentUser(BaseModel):
    email: str
    role: str
    apartment_id: int | None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None or role is None:
            raise credentials_exception
        
        # We can optionally query the DB to ensure the user still exists and hasn't been revoked
        user = db.query(UserAccess).filter(UserAccess.email == email).first()
        if user is None:
            raise credentials_exception
            
        return CurrentUser(
            email=user.email,
            role=user.role,
            apartment_id=user.apartment_id
        )
    except jwt.PyJWTError:
        raise credentials_exception

def get_current_admin(current_user: CurrentUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrative privileges"
        )
    return current_user

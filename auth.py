from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import requests
import os
from dotenv import load_dotenv
from database import get_db
from sqlalchemy.orm import Session
from models import User
from schemas import GoogleToken, GoogleUserInfo, TokenData

# Загружаем переменные окружения
load_dotenv()

# Константы для JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Константы для Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Схема OAuth2 для получения токена
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создает JWT токен"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Получает текущего пользователя по JWT токену"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user

async def verify_google_token(token: str) -> GoogleUserInfo:
    """Проверяет Google ID токен и возвращает информацию о пользователе"""
    try:
        # Получаем информацию о пользователе от Google
        response = requests.get(
            f"https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        user_info = response.json()
        return GoogleUserInfo(**user_info)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}"
        )

def get_or_create_user(db: Session, google_user: GoogleUserInfo) -> User:
    """Получает существующего пользователя или создает нового"""
    # Ищем пользователя по Google ID
    user = db.query(User).filter(User.google_id == google_user.id).first()
    
    if not user:
        # Создаем нового пользователя
        user = User(
            email=google_user.email,
            google_id=google_user.id,
            name=google_user.name,
            picture=google_user.picture
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

def create_user_token(user: User) -> dict:
    """Создает JWT токен для пользователя"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    } 
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import uuid

# Базовые схемы
class UserBase(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None

class UserProfileBase(BaseModel):
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    target_weight: Optional[float] = None
    goal: Optional[str] = None
    activity_level: Optional[str] = None
    diet_type: Optional[str] = None
    water_goal: Optional[float] = None
    notifications_enabled: bool = True

# Схемы для создания
class UserCreate(UserBase):
    google_id: str

class UserProfileCreate(UserProfileBase):
    pass

# Схемы для ответов
class UserResponse(UserBase):
    id: str
    google_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserProfileResponse(UserProfileBase):
    id: str
    user_id: str
    bmi: Optional[float] = None
    daily_calories: Optional[int] = None

    class Config:
        orm_mode = True

class WeightHistoryResponse(BaseModel):
    id: str
    profile_id: str
    weight: float
    date: datetime

    class Config:
        orm_mode = True

class WaterHistoryResponse(BaseModel):
    id: str
    profile_id: str
    amount: float
    date: datetime

    class Config:
        orm_mode = True

# Схемы для обновления
class UserUpdate(BaseModel):
    name: Optional[str] = None
    picture: Optional[str] = None

class UserProfileUpdate(UserProfileBase):
    pass

# Схемы для Google OAuth
class GoogleToken(BaseModel):
    access_token: str
    id_token: str
    expires_in: int
    refresh_token: Optional[str] = None
    token_type: str
    scope: str

class GoogleUserInfo(BaseModel):
    id: str
    email: EmailStr
    verified_email: bool
    name: str
    given_name: str
    family_name: str
    picture: str
    locale: str

# Схемы для токенов
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[str] = None 
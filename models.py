from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    google_id = Column(String, unique=True, index=True)
    name = Column(String)
    picture = Column(String)  # URL к фото профиля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связь с профилем пользователя
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    
    # Связь с файлами
    files = relationship("File", back_populates="user")

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    
    # Основные данные
    gender = Column(String)  # male, female, other
    birth_date = Column(DateTime)
    height = Column(Float)  # в сантиметрах
    weight = Column(Float)  # в килограммах
    target_weight = Column(Float)  # в килограммах
    
    # Цели и настройки
    goal = Column(String)  # weight_loss, weight_gain, maintenance
    activity_level = Column(String)  # sedentary, light, moderate, active, very_active
    diet_type = Column(String)  # regular, vegetarian, vegan, etc.
    
    # Расчетные значения
    bmi = Column(Float)
    daily_calories = Column(Integer)
    
    # Дополнительные настройки
    water_goal = Column(Float)  # в миллилитрах
    notifications_enabled = Column(Boolean, default=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="profile")
    
    # История веса
    weight_history = relationship("WeightHistory", back_populates="profile")
    
    # История потребления воды
    water_history = relationship("WaterHistory", back_populates="profile")

class WeightHistory(Base):
    __tablename__ = "weight_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("user_profiles.id"))
    weight = Column(Float)
    date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с профилем
    profile = relationship("UserProfile", back_populates="weight_history")

class WaterHistory(Base):
    __tablename__ = "water_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("user_profiles.id"))
    amount = Column(Float)  # в миллилитрах
    date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с профилем
    profile = relationship("UserProfile", back_populates="water_history")

class File(Base):
    __tablename__ = "files"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    filename = Column(String)
    content_type = Column(String)
    s3_key = Column(String, unique=True)
    url = Column(String)
    size = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с пользователем
    user = relationship("User", back_populates="files") 
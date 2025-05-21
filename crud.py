from sqlalchemy.orm import Session
from models import User, UserProfile, WeightHistory, WaterHistory
from schemas import UserCreate, UserProfileCreate, UserProfileUpdate
from datetime import datetime
import uuid

# CRUD операции для пользователей
def get_user(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_google_id(db: Session, google_id: str):
    return db.query(User).filter(User.google_id == google_id).first()

def create_user(db: Session, user: UserCreate):
    db_user = User(
        id=str(uuid.uuid4()),
        email=user.email,
        google_id=user.google_id,
        name=user.name,
        picture=user.picture
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: str, user_data: dict):
    db_user = get_user(db, user_id)
    if db_user:
        for key, value in user_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user

# CRUD операции для профилей пользователей
def get_user_profile(db: Session, user_id: str):
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

def create_user_profile(db: Session, user_id: str, profile: UserProfileCreate):
    db_profile = UserProfile(
        id=str(uuid.uuid4()),
        user_id=user_id,
        **profile.dict(exclude_unset=True)
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_user_profile(db: Session, user_id: str, profile: UserProfileUpdate):
    db_profile = get_user_profile(db, user_id)
    if db_profile:
        for key, value in profile.dict(exclude_unset=True).items():
            setattr(db_profile, key, value)
        db.commit()
        db.refresh(db_profile)
    return db_profile

# CRUD операции для истории веса
def add_weight_record(db: Session, profile_id: str, weight: float):
    db_record = WeightHistory(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        weight=weight,
        date=datetime.utcnow()
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

def get_weight_history(db: Session, profile_id: str, limit: int = 30):
    return db.query(WeightHistory)\
        .filter(WeightHistory.profile_id == profile_id)\
        .order_by(WeightHistory.date.desc())\
        .limit(limit)\
        .all()

# CRUD операции для истории воды
def add_water_record(db: Session, profile_id: str, amount: float):
    db_record = WaterHistory(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        amount=amount,
        date=datetime.utcnow()
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

def get_water_history(db: Session, profile_id: str, limit: int = 30):
    return db.query(WaterHistory)\
        .filter(WaterHistory.profile_id == profile_id)\
        .order_by(WaterHistory.date.desc())\
        .limit(limit)\
        .all()

def get_today_water_amount(db: Session, profile_id: str):
    today = datetime.utcnow().date()
    records = db.query(WaterHistory)\
        .filter(
            WaterHistory.profile_id == profile_id,
            WaterHistory.date >= today
        ).all()
    return sum(record.amount for record in records) 
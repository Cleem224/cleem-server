from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import numpy as np
import json
import os
import time
import sys
import torch
import requests
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from fastapi.responses import JSONResponse
import base64
from sqlalchemy.orm import Session
from database import get_db, engine, Base
from models import User, UserProfile
from schemas import (
    UserResponse, UserProfileResponse, UserProfileCreate, UserProfileUpdate,
    GoogleToken, Token, WeightHistoryResponse, WaterHistoryResponse
)
from auth import (
    verify_google_token, get_current_user, create_user_token,
    get_or_create_user
)
from crud import (
    get_user_profile, create_user_profile, update_user_profile,
    add_weight_record, get_weight_history,
    add_water_record, get_water_history, get_today_water_amount
)
from datetime import datetime
import boto3  # Добавлено для работы с S3
from file_router import router as file_router  # Импортируем роутер для файлов

# Создаем таблицы в базе данных
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cleem API")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутер для файлов
app.include_router(file_router)

# Добавляем путь к YOLOv5 в Python path
yolov5_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yolov5')
sys.path.append(yolov5_path)

# Загружаем модели при старте сервера
models = {
    "model1": None,  # YOLOv5 модель
    "model2": None   # YOLOv5 модель (или YOLOv8 если применимо)
}

# Пути к моделям
MODEL_PATHS = {
    "model1": "/Users/faig/Downloads/best.pt",
    "model2": "/Users/faig/Downloads/best-2.pt"
}

# Типы моделей
MODEL_TYPES = {
    "model1": "YOLOv5",
    "model2": "YOLOv5"
}

# API ключи (реальные ключи из проекта)
EDAMAM_APP_ID = "866cd6b2"
EDAMAM_APP_KEY = "d731d4ccac5db314f017faa8968784a5"
GEMINI_API_KEY = "AIzaSyBKaHxMvfr2PJ4T5_sJNGd9pc9PfOXaURs"

# Классы для возвращаемых данных
class NutritionInfo(BaseModel):
    calories: float
    protein: float
    fat: float
    carbs: float
    serving_weight_grams: float
    
class DetectedObject(BaseModel):
    bbox: List[float]
    confidence: float
    class_id: int
    class_name: str
    
class NutritionDetectionResponse(BaseModel):
    message: str
    product_name: str
    count: int
    nutrition_per_item: Optional[NutritionInfo] = None
    total_nutrition: Optional[NutritionInfo] = None
    detections: List[DetectedObject]
    processing_time_sec: float

# Функция для ленивой загрузки моделей (только когда они нужны)
def get_model(model_name):
    if models[model_name] is None:
        if not os.path.exists(MODEL_PATHS[model_name]):
            raise HTTPException(status_code=404, detail=f"Модель {model_name} не найдена")
        
        # Загружаем модель
        try:
            print(f"Загружаем модель {model_name}...")
            
            if MODEL_TYPES[model_name] == "YOLOv5":
                # Загрузка YOLOv5 модели используя torch.hub
                models[model_name] = torch.hub.load(
                    yolov5_path, 
                    'custom', 
                    path=MODEL_PATHS[model_name],
                    source='local'  # Используем локальную версию, а не загрузку с GitHub
                )
            else:
                # Если это YOLOv8 модель, используем Ultralytics
                from ultralytics import YOLO
                models[model_name] = YOLO(MODEL_PATHS[model_name])
                
            print(f"Модель {model_name} успешно загружена!")
        except Exception as e:
            print(f"Ошибка при загрузке модели: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки модели: {str(e)}")
    
    return models[model_name]

def get_product_name_from_gemini(image_bytes, detections):
    """
    Получает название продукта с помощью Gemini API.
    """
    try:
        # Конвертируем изображение в Base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # URL для Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"
        
        # Подготовка текстового промпта
        prompt = """
        Определи, какой продукт изображен на фото, и дай его название на английском языке.
        Ответь одним словом или короткой фразой (например: "fried chicken", "shrimp tempura", "apple").
        """
        
        # Если есть детекции, добавляем информацию о них в промпт
        if detections:
            prompt += "\nНа изображении обнаружены объекты со следующими координатами:\n"
            for i, detection in enumerate(detections):
                prompt += f"Объект {i+1}: {detection['bbox']}, уверенность: {detection['confidence']:.2f}\n"
        
        # Формирование запроса для Gemini
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 100
            }
        }
        
        # Отправка запроса
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        # Проверка ответа
        if response.status_code != 200:
            print(f"Ошибка Gemini API: {response.status_code}, {response.text}")
            if detections:
                return detections[0]["class_name"]
            return "unknown_food"
        
        # Парсинг ответа
        result = response.json()
        
        # Извлечение текста из ответа
        if "candidates" in result and len(result["candidates"]) > 0:
            if "content" in result["candidates"][0] and "parts" in result["candidates"][0]["content"]:
                for part in result["candidates"][0]["content"]["parts"]:
                    if "text" in part:
                        # Очищаем и нормализуем ответ
                        food_name = part["text"].strip().lower()
                        # Удаляем кавычки, точки и другие знаки
                        food_name = food_name.replace('"', '').replace('.', '').replace(':', '')
                        return food_name
        
        # Если не удалось извлечь текст, используем класс из детекции
        if detections:
            return detections[0]["class_name"]
        return "unknown_food"
    
    except Exception as e:
        print(f"Ошибка при определении продукта через Gemini: {str(e)}")
        # Фолбэк: используем класс из первой детекции
        if detections:
            return detections[0]["class_name"]
        return "unknown_food"

def get_nutrition_from_edamam(product_name, count=1):
    """
    Получает информацию о питательной ценности из Edamam API.
    """
    try:
        # URL для Edamam API
        url = f"https://api.edamam.com/api/nutrition-data?app_id={EDAMAM_APP_ID}&app_key={EDAMAM_APP_KEY}&ingr={product_name}"
        
        # Отправка запроса
        response = requests.get(url)
        
        # Проверка ответа
        if response.status_code != 200:
            print(f"Ошибка Edamam API: {response.status_code}, {response.text}")
            # Используем заглушку
            return use_nutrition_fallback(product_name, count)
        
        # Парсинг ответа
        result = response.json()
        
        # Проверка, что есть данные о калориях
        if "calories" not in result or result["calories"] == 0:
            print(f"Edamam не вернул данные о калориях для {product_name}")
            return use_nutrition_fallback(product_name, count)
        
        # Извлечение данных о питательной ценности
        calories = result.get("calories", 0)
        
        # Извлечение массы порции
        weight = result.get("totalWeight", 100.0)
        
        # Извлечение основных нутриентов
        nutrients = result.get("totalNutrients", {})
        protein = nutrients.get("PROCNT", {}).get("quantity", 0.0) if "PROCNT" in nutrients else 0.0
        fat = nutrients.get("FAT", {}).get("quantity", 0.0) if "FAT" in nutrients else 0.0
        carbs = nutrients.get("CHOCDF", {}).get("quantity", 0.0) if "CHOCDF" in nutrients else 0.0
        
        # Создание объекта с информацией о питательной ценности для одного продукта
        nutrition_per_item = NutritionInfo(
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs,
            serving_weight_grams=weight
        )
        
        # Расчет общей питательной ценности для всех продуктов
        total_nutrition = NutritionInfo(
            calories=calories * count,
            protein=protein * count,
            fat=fat * count,
            carbs=carbs * count,
            serving_weight_grams=weight * count
        )
        
        return nutrition_per_item, total_nutrition
    
    except Exception as e:
        print(f"Ошибка при получении питательной ценности через Edamam: {str(e)}")
        # Фолбэк: используем заглушки
        return use_nutrition_fallback(product_name, count)

def use_nutrition_fallback(product_name, count=1):
    """
    Возвращает заглушки для питательной ценности, если API не работает.
    """
    # Заглушки для демонстрации
    sample_nutritions = {
        "fried_chicken": NutritionInfo(
            calories=250.0,
            protein=15.0,
            fat=16.0,
            carbs=12.0,
            serving_weight_grams=100.0
        ),
        "chicken": NutritionInfo(
            calories=250.0,
            protein=15.0,
            fat=16.0,
            carbs=12.0,
            serving_weight_grams=100.0
        ),
        "shrimp": NutritionInfo(
            calories=120.0,
            protein=20.0,
            fat=5.0,
            carbs=3.0,
            serving_weight_grams=30.0
        ),
        "shrimp tempura": NutritionInfo(
            calories=200.0,
            protein=12.0,
            fat=12.0,
            carbs=15.0,
            serving_weight_grams=45.0
        ),
        "fruit": NutritionInfo(
            calories=80.0,
            protein=1.0,
            fat=0.5,
            carbs=20.0,
            serving_weight_grams=120.0
        ),
        "apple": NutritionInfo(
            calories=52.0,
            protein=0.3,
            fat=0.2,
            carbs=14.0,
            serving_weight_grams=100.0
        ),
        "nuggets": NutritionInfo(
            calories=290.0,
            protein=13.0,
            fat=18.0,
            carbs=18.0,
            serving_weight_grams=85.0
        ),
    }
    
    # Ищем подходящую заглушку по ключевым словам в названии продукта
    product_name_lower = product_name.lower()
    
    for key, nutrition in sample_nutritions.items():
        if key in product_name_lower:
            # Нашли совпадение
            nutrition_per_item = nutrition
            
            # Рассчитываем общую питательную ценность
            total_nutrition = NutritionInfo(
                calories=nutrition.calories * count,
                protein=nutrition.protein * count,
                fat=nutrition.fat * count,
                carbs=nutrition.carbs * count,
                serving_weight_grams=nutrition.serving_weight_grams * count
            )
            
            return nutrition_per_item, total_nutrition
    
    # Если не нашли совпадений, используем общую заглушку
    default_nutrition = NutritionInfo(
        calories=100.0,
        protein=5.0,
        fat=3.0,
        carbs=10.0,
        serving_weight_grams=100.0
    )
    
    total_nutrition = NutritionInfo(
        calories=default_nutrition.calories * count,
        protein=default_nutrition.protein * count,
        fat=default_nutrition.fat * count,
        carbs=default_nutrition.carbs * count,
        serving_weight_grams=default_nutrition.serving_weight_grams * count
    )
    
    return default_nutrition, total_nutrition

@app.post("/analyze", response_model=Dict[str, Any])
async def analyze_image(
    file: UploadFile = File(..., description="Загрузите изображение"),
    model_name: str = Form("model1", description="model1 или model2"),
    conf_threshold: float = Form(0.1, description="Порог уверенности (0.01-1.0)")
):
    try:
        # Проверка порога уверенности
        if conf_threshold < 0.01 or conf_threshold > 1.0:
            return JSONResponse(
                status_code=400,
                content={"error": "Порог уверенности должен быть между 0.01 и 1.0"}
            )
        
        # Проверка, что модель существует
        if model_name not in ["model1", "model2"]:
            return JSONResponse(
                status_code=400,
                content={"error": f"Неизвестная модель: {model_name}. Доступные модели: model1, model2"}
            )
        
        start_time = time.time()
        
        # Чтение изображения
        image_bytes = await file.read()
        image_pil = Image.open(io.BytesIO(image_bytes))
        
        # Получение модели
        model = get_model(model_name)
        
        # Инференс
        detections = []
        if MODEL_TYPES[model_name] == "YOLOv5":
            # YOLOv5 инференс с пользовательским порогом уверенности
            # Не передаем conf в вызов, он не поддерживается
            results = model(image_pil)
            
            # Обработка результатов YOLOv5
            for pred in results.pred[0]:
                x1, y1, x2, y2, conf, cls = pred.tolist()
                # Применяем фильтрацию по порогу уверенности здесь
                if float(conf) >= conf_threshold:
                    class_name = results.names[int(cls)]
                    
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": float(conf),
                        "class_id": int(cls),
                        "class_name": class_name
                    })
        else:
            # YOLOv8 инференс с пользовательским порогом уверенности
            results = model(image_pil, conf=conf_threshold)
            
            # Обработка результатов YOLOv8
            if hasattr(results[0], 'boxes'):
                for box in results[0].boxes:
                    # Получаем координаты
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Получаем класс и уверенность
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = results[0].names[class_id]
                    
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": class_name
                    })
        
        # Определяем количество объектов
        count = len(detections)
        
        # Интегрируем с Gemini для определения названия продукта
        product_name = get_product_name_from_gemini(image_bytes, detections)
        print(f"Gemini определил продукт: {product_name}")
        
        # Получаем информацию о питательной ценности
        nutrition_per_item, total_nutrition = get_nutrition_from_edamam(product_name, count)
        print(f"Edamam вернул данные: калории на 1 шт: {nutrition_per_item.calories}, всего: {total_nutrition.calories}")
        
        # Преобразуем Pydantic модели в словари для ответа
        nutrition_item_dict = None
        if nutrition_per_item:
            nutrition_item_dict = {
                "calories": nutrition_per_item.calories,
                "protein": nutrition_per_item.protein,
                "fat": nutrition_per_item.fat,
                "carbs": nutrition_per_item.carbs,
                "serving_weight_grams": nutrition_per_item.serving_weight_grams
            }
        
        total_nutrition_dict = None
        if total_nutrition:
            total_nutrition_dict = {
                "calories": total_nutrition.calories,
                "protein": total_nutrition.protein,
                "fat": total_nutrition.fat,
                "carbs": total_nutrition.carbs,
                "serving_weight_grams": total_nutrition.serving_weight_grams
            }
        
        processing_time = time.time() - start_time
        
        return {
            "message": "Фото обработано успешно!",
            "model": model_name,
            "model_type": MODEL_TYPES[model_name],
            "product_name": product_name,
            "count": count,
            "nutrition_per_item": nutrition_item_dict,
            "total_nutrition": total_nutrition_dict,
            "num_detections": len(detections),
            "detections": detections,
            "processing_time_sec": processing_time
        }
    except Exception as e:
        print(f"Ошибка при обработке изображения: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке изображения: {str(e)}")

@app.get("/")
async def root():
    return {"message": "API детекции продуктов с подсчетом питательной ценности. Перейдите на /docs для документации."}

@app.get("/health")
async def health_check():
    """Endpoint для проверки работоспособности API."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "db_status": "connected" if engine else "disconnected"
    }

@app.get("/models")
async def list_models():
    # Проверяем наличие файлов моделей
    status = {}
    for name, path in MODEL_PATHS.items():
        status[name] = {
            "path": path,
            "exists": os.path.exists(path),
            "loaded": models[name] is not None,
            "type": MODEL_TYPES[name]
        }
    
    return {
        "available_models": status
    }

# Новые эндпоинты для аутентификации и работы с пользователями

@app.post("/auth/google", response_model=Token)
async def google_auth(token: GoogleToken, db: Session = Depends(get_db)):
    """Аутентификация через Google OAuth"""
    try:
        # Проверяем Google токен
        google_user = await verify_google_token(token.id_token)
        
        # Получаем или создаем пользователя
        user = get_or_create_user(db, google_user)
        
        # Создаем JWT токен
        return create_user_token(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return current_user

@app.get("/users/me/profile", response_model=UserProfileResponse)
async def read_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение профиля текущего пользователя"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile

@app.post("/users/me/profile", response_model=UserProfileResponse)
async def create_profile(
    profile: UserProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание профиля пользователя"""
    # Проверяем, существует ли уже профиль
    existing_profile = get_user_profile(db, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists"
        )
    
    # Создаем новый профиль
    return create_user_profile(db, current_user.id, profile)

@app.put("/users/me/profile", response_model=UserProfileResponse)
async def update_profile(
    profile: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление профиля пользователя"""
    updated_profile = update_user_profile(db, current_user.id, profile)
    if not updated_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return updated_profile

@app.post("/users/me/weight", response_model=WeightHistoryResponse)
async def add_weight(
    weight: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавление записи о весе"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return add_weight_record(db, profile.id, weight)

@app.get("/users/me/weight/history", response_model=List[WeightHistoryResponse])
async def get_weight_history_endpoint(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение истории веса"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return get_weight_history(db, profile.id, limit)

@app.post("/users/me/water", response_model=WaterHistoryResponse)
async def add_water(
    amount: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавление записи о потреблении воды"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return add_water_record(db, profile.id, amount)

@app.get("/users/me/water/history", response_model=List[WaterHistoryResponse])
async def get_water_history_endpoint(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение истории потребления воды"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return get_water_history(db, profile.id, limit)

@app.get("/users/me/water/today")
async def get_today_water(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение количества воды, выпитой сегодня"""
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    amount = get_today_water_amount(db, profile.id)
    return {"amount": amount}

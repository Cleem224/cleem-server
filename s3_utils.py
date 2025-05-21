import boto3
import os
import uuid
from typing import Optional, Tuple
from fastapi import UploadFile
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_S3_REGION = os.getenv("AWS_S3_REGION", "eu-central-1")

# Инициализируем S3 клиента
s3_client = boto3.client(
    "s3",
    region_name=AWS_S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def get_file_extension(filename: str) -> str:
    """Получает расширение файла из имени файла."""
    if not filename or "." not in filename:
        return ""
    return filename.split(".")[-1].lower()

def generate_unique_filename(original_filename: str) -> str:
    """Генерирует уникальное имя файла на основе оригинального имени."""
    ext = get_file_extension(original_filename)
    unique_name = f"{uuid.uuid4().hex}"
    if ext:
        unique_name = f"{unique_name}.{ext}"
    return unique_name

def get_content_type(filename: str) -> str:
    """Определяет content-type файла на основе его расширения."""
    ext = get_file_extension(filename)
    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "pdf": "application/pdf",
        "txt": "text/plain",
        "csv": "text/csv",
        "json": "application/json"
    }
    return content_types.get(ext, "application/octet-stream")

def upload_file_to_s3(file_path: str, s3_key: Optional[str] = None) -> str:
    """Загружает файл с диска в S3.
    
    Args:
        file_path: Путь к файлу на диске
        s3_key: Ключ (путь) в S3. Если не указан, используется имя файла
        
    Returns:
        URL файла в S3
    """
    if s3_key is None:
        s3_key = os.path.basename(file_path)
    
    s3_client.upload_file(
        file_path, 
        AWS_S3_BUCKET, 
        s3_key,
        ExtraArgs={'ContentType': get_content_type(file_path)}
    )
    
    url = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
    return url

async def upload_fileobj_to_s3(upload_file: UploadFile, folder: str = "uploads") -> Tuple[str, str]:
    """Загружает файл из FastAPI UploadFile в S3.
    
    Args:
        upload_file: FastAPI UploadFile объект
        folder: Папка в S3 куда загружать файл
        
    Returns:
        Tuple[url, key]: URL файла в S3 и ключ (путь) в S3
    """
    # Читаем содержимое файла
    file_content = await upload_file.read()
    
    # Генерируем уникальное имя файла
    unique_filename = generate_unique_filename(upload_file.filename)
    
    # Формируем ключ S3 (с папкой)
    s3_key = f"{folder}/{unique_filename}"
    
    # Определяем content-type
    content_type = get_content_type(upload_file.filename)
    
    # Загружаем в S3
    s3_client.put_object(
        Bucket=AWS_S3_BUCKET,
        Key=s3_key,
        Body=file_content,
        ContentType=content_type
    )
    
    # Сбрасываем позицию чтения файла для последующего использования
    await upload_file.seek(0)
    
    # Возвращаем URL и ключ
    url = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
    return url, s3_key

def delete_file_from_s3(s3_key: str) -> bool:
    """Удаляет файл из S3.
    
    Args:
        s3_key: Ключ (путь) в S3
        
    Returns:
        bool: True если удаление прошло успешно
    """
    try:
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        return True
    except Exception as e:
        print(f"Error deleting file from S3: {e}")
        return False

def get_file_url(s3_key: str) -> str:
    """Получает URL файла в S3.
    
    Args:
        s3_key: Ключ (путь) в S3
        
    Returns:
        str: URL файла
    """
    return f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}" 
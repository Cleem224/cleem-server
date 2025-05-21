from fastapi import APIRouter, UploadFile, File as FastAPIFile, Form, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import User, File
from s3_utils import upload_fileobj_to_s3, delete_file_from_s3, get_file_url
from auth import get_current_user
import uuid
import json
import os

# Создаем роутер
router = APIRouter(
    prefix="/files",
    tags=["Files"],
    responses={404: {"description": "Not found"}},
)

# Модели Pydantic
class FileResponse(BaseModel):
    id: str
    url: str
    filename: str
    content_type: str
    s3_key: str
    
    class Config:
        orm_mode = True

class FileListResponse(BaseModel):
    files: List[FileResponse]

# Роуты для работы с файлами
@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    folder: str = Form("uploads"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Загружает файл в S3 хранилище.
    
    Args:
        file: Файл для загрузки
        folder: Папка в S3 куда загружать файл (по умолчанию 'uploads')
        current_user: Текущий пользователь (авторизация)
        db: Сессия базы данных
        
    Returns:
        Информация о загруженном файле
    """
    try:
        # Загружаем файл в S3
        url, s3_key = await upload_fileobj_to_s3(file, folder)
        
        # Создаем запись в БД
        db_file = File(
            id=uuid.uuid4().hex,
            user_id=current_user.id,
            filename=file.filename,
            content_type=file.content_type,
            s3_key=s3_key,
            url=url,
            size=file.size if hasattr(file, 'size') else None
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        return db_file
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке файла: {str(e)}"
        )

@router.post("/upload-multiple", response_model=FileListResponse)
async def upload_multiple_files(
    files: List[UploadFile] = FastAPIFile(...),
    folder: str = Form("uploads"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Загружает несколько файлов в S3 хранилище.
    
    Args:
        files: Список файлов для загрузки
        folder: Папка в S3 куда загружать файлы (по умолчанию 'uploads')
        current_user: Текущий пользователь (авторизация)
        db: Сессия базы данных
        
    Returns:
        Список информации о загруженных файлах
    """
    try:
        db_files = []
        
        for file in files:
            url, s3_key = await upload_fileobj_to_s3(file, folder)
            
            # Создаем запись в БД
            db_file = File(
                id=uuid.uuid4().hex,
                user_id=current_user.id,
                filename=file.filename,
                content_type=file.content_type,
                s3_key=s3_key,
                url=url,
                size=file.size if hasattr(file, 'size') else None
            )
            
            db.add(db_file)
            db_files.append(db_file)
        
        db.commit()
        
        # Обновляем объекты из БД
        for db_file in db_files:
            db.refresh(db_file)
        
        return {"files": db_files}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке файлов: {str(e)}"
        )

@router.get("/user", response_model=FileListResponse)
async def get_user_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получает список файлов текущего пользователя.
    
    Args:
        current_user: Текущий пользователь (авторизация)
        db: Сессия базы данных
        
    Returns:
        Список файлов пользователя
    """
    files = db.query(File).filter(File.user_id == current_user.id).all()
    return {"files": files}

@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получает информацию о файле по ID.
    
    Args:
        file_id: ID файла
        current_user: Текущий пользователь (авторизация)
        db: Сессия базы данных
        
    Returns:
        Информация о файле
    """
    db_file = db.query(File).filter(File.id == file_id).first()
    
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден"
        )
    
    # Проверяем права доступа (файл принадлежит пользователю)
    if db_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    return db_file

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Удаляет файл из S3 хранилища и из БД.
    
    Args:
        file_id: ID файла
        current_user: Текущий пользователь (авторизация)
        db: Сессия базы данных
        
    Returns:
        Результат удаления
    """
    try:
        # Получаем файл из БД
        db_file = db.query(File).filter(File.id == file_id).first()
        
        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден"
            )
        
        # Проверяем права доступа (файл принадлежит пользователю)
        if db_file.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен"
            )
        
        # Удаляем файл из S3
        success = delete_file_from_s3(db_file.s3_key)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при удалении файла из S3"
            )
        
        # Удаляем запись из БД
        db.delete(db_file)
        db.commit()
        
        return {"message": "Файл успешно удален"}
    except HTTPException:
        # Пробрасываем HTTP исключения дальше
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении файла: {str(e)}"
        ) 
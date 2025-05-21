FROM python:3.11-slim

WORKDIR /app

# Переменные среды для Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Копирование приложения
COPY . .

# Создаем непривилегированного пользователя для запуска приложения
RUN addgroup --system app && adduser --system --group app \
    && chown -R app:app /app/logs

# Переключаемся на непривилегированного пользователя
USER app

# Открываем порт
EXPOSE 8080

# Запуск приложения
# В продакшн рекомендуем использовать gunicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"] 
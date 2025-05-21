#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Запуск Cleem API для локальной разработки${NC}"

# Проверка наличия обязательных утилит
if ! command -v docker-compose &> /dev/null; then
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        echo -e "${RED}Ошибка: docker compose не установлен!${NC}"
        echo -e "${YELLOW}Установите Docker и Docker Compose перед запуском.${NC}"
        exit 1
    fi
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Создаем файл .env если он не существует
if [ ! -f .env ]; then
    echo -e "${YELLOW}Файл .env не найден. Создаю его с локальными настройками...${NC}"
    
    cat > .env << EOF
# PostgreSQL (Локальный)
ENVIRONMENT=development
PORT=8080
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=cleem_db

# JWT
JWT_SECRET_KEY=cleemai-jwt-secret-key-change-this-in-production
JWT_EXPIRATION=10080

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8080/auth/google/callback

# API Keys
EDAMAM_APP_ID=your-edamam-app-id
EDAMAM_APP_KEY=your-edamam-app-key
GEMINI_API_KEY=your-gemini-api-key

# Security
ALLOWED_ORIGINS=*

# Docker options
COMPOSE_PROJECT_NAME=cleem-api
EOF

    echo -e "${GREEN}Файл .env создан с локальными настройками${NC}"
else
    echo -e "${GREEN}Файл .env уже существует${NC}"
fi

# Создаем необходимые директории
mkdir -p logs
mkdir -p nginx/ssl
mkdir -p nginx/logs

# Проверяем наличие SSL сертификатов для Nginx
if [ ! -f nginx/ssl/server.crt ] || [ ! -f nginx/ssl/server.key ]; then
    echo -e "${YELLOW}SSL сертификаты не найдены, создаю самоподписанные сертификаты...${NC}"
    
    # Генерация самоподписанных сертификатов
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout nginx/ssl/server.key -out nginx/ssl/server.crt \
      -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null || {
        echo -e "${YELLOW}Не удалось создать SSL сертификаты. Nginx может не запуститься.${NC}"
    }
fi

# Запуск Docker Compose
echo -e "${GREEN}Запускаю контейнеры...${NC}"
$DOCKER_COMPOSE_CMD down
$DOCKER_COMPOSE_CMD up -d

echo -e "${GREEN}Сервер запущен на http://localhost:8080${NC}"
echo -e "${GREEN}Документация API доступна по адресу: http://localhost:8080/docs${NC}"
echo -e "${YELLOW}Для просмотра логов выполните: $DOCKER_COMPOSE_CMD logs -f${NC}" 
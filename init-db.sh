#!/bin/bash
set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Инициализация базы данных для Cleem API${NC}"

# Определяем команду docker-compose
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

# Проверяем, запущены ли контейнеры
if ! $DOCKER_COMPOSE_CMD ps | grep -q "db"; then
    echo -e "${YELLOW}База данных не запущена. Запускаем контейнеры...${NC}"
    $DOCKER_COMPOSE_CMD up -d db
    
    # Ждем, пока база данных запустится
    echo -e "${YELLOW}Ожидаем запуска базы данных...${NC}"
    sleep 10
fi

# Применяем миграции
echo -e "${GREEN}Применяем миграции базы данных...${NC}"
$DOCKER_COMPOSE_CMD run --rm api alembic upgrade head

echo -e "${GREEN}Инициализация базы данных завершена!${NC}"
echo -e "${GREEN}Теперь вы можете запустить сервер: ./start.sh${NC}" 
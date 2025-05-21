#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Cleem API deployment...${NC}"

# Validate environment variables
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create an .env file with required environment variables.${NC}"
    echo -e "${YELLOW}You can use env.example as a template.${NC}"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

echo -e "${GREEN}Checking Docker and Docker Compose installation...${NC}"
# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed!${NC}"
    echo -e "${YELLOW}Please install Docker before running this script.${NC}"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed!${NC}"
    echo -e "${YELLOW}Please install Docker Compose before running this script.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${GREEN}Creating necessary directories...${NC}"
mkdir -p logs
mkdir -p nginx/ssl
mkdir -p nginx/logs

# Check for SSL certificates
if [ ! -f nginx/ssl/server.crt ] || [ ! -f nginx/ssl/server.key ]; then
    echo -e "${YELLOW}SSL certificates not found, generating self-signed certificates...${NC}"
    echo -e "${YELLOW}Warning: For production, replace these with real certificates!${NC}"
    
    # Generate self-signed SSL certificates
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout nginx/ssl/server.key -out nginx/ssl/server.crt \
      -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
fi

# Create .htpasswd file for metrics endpoint
if [ ! -f nginx/.htpasswd ]; then
    echo -e "${GREEN}Creating .htpasswd file for metrics endpoint...${NC}"
    
    # Generate random username and password if not provided
    METRICS_USER=${METRICS_USER:-"admin"}
    if [ -z "$METRICS_PASSWORD" ]; then
        METRICS_PASSWORD=$(openssl rand -base64 12)
        echo -e "${YELLOW}Generated random password for metrics: ${METRICS_PASSWORD}${NC}"
    fi
    
    # Create htpasswd file
    docker run --rm httpd:alpine htpasswd -bn "$METRICS_USER" "$METRICS_PASSWORD" > nginx/.htpasswd
fi

# Run database migrations
echo -e "${GREEN}Running database migrations...${NC}"
docker-compose run --rm api alembic upgrade head

# Pull latest images
echo -e "${GREEN}Pulling latest Docker images...${NC}"
docker-compose pull

# Build and start the services
echo -e "${GREEN}Building and starting services...${NC}"
docker-compose up -d --build

# Check if services are running
echo -e "${GREEN}Checking if services are running...${NC}"
sleep 10

if docker-compose ps | grep "Up"; then
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo -e "${GREEN}The API is now running at:${NC}"
    echo -e "${YELLOW}  - HTTP: http://localhost:80${NC}"
    echo -e "${YELLOW}  - HTTPS: https://localhost:443${NC}"
    echo -e "${GREEN}Health check URL: https://localhost/health${NC}"
    echo -e "${GREEN}API documentation: https://localhost/api/docs (if enabled)${NC}"
else
    echo -e "${RED}× Deployment failed!${NC}"
    echo -e "${YELLOW}Please check the logs for more information:${NC}"
    echo -e "${YELLOW}docker-compose logs${NC}"
    exit 1
fi

# Show logs
echo -e "${GREEN}Showing logs (Ctrl+C to exit)...${NC}"
docker-compose logs -f 
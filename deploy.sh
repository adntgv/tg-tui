#!/bin/bash

set -e

echo "🚀 Starting deployment..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check required environment variables
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_TOKEN is not set"
    exit 1
fi

if [ -z "$WEBAPP_URL" ]; then
    echo "❌ Error: WEBAPP_URL is not set"
    exit 1
fi

# Build and deploy with Docker Compose
echo "📦 Building Docker images..."
docker-compose -f docker-compose.prod.yml build

echo "🔄 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d

echo "✅ Deployment complete!"
echo "📊 Check status with: docker-compose -f docker-compose.prod.yml ps"
echo "📝 View logs with: docker-compose -f docker-compose.prod.yml logs -f"
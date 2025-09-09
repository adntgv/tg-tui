#!/bin/bash

# Coolify CLI Deployment Script for TG-TUI

set -e

echo "====================================="
echo "   Coolify CLI Deployment for TG-TUI"
echo "====================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if Coolify CLI is installed
if ! command -v coolify &> /dev/null; then
    echo -e "${YELLOW}Installing Coolify CLI...${NC}"
    npm install -g coolify
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.coolify .env
    echo -e "${RED}Please edit .env file with your actual values:${NC}"
    echo "  - TELEGRAM_TOKEN: Your bot token from @BotFather"
    echo "  - WEBAPP_URL: Your Coolify app URL"
    exit 1
fi

# Load environment variables
source .env

# Validate required variables
if [ -z "$TELEGRAM_TOKEN" ] || [ "$TELEGRAM_TOKEN" = "your_telegram_bot_token_here" ]; then
    echo -e "${RED}Error: TELEGRAM_TOKEN not set in .env file${NC}"
    exit 1
fi

# Function to check if instance is configured
check_instance() {
    if [ ! -f ~/.coolify/config.json ]; then
        echo -e "${YELLOW}No Coolify instance configured.${NC}"
        echo "Please run: coolify instances:add"
        echo ""
        echo "You'll need:"
        echo "1. Your Coolify URL (e.g., https://coolify.example.com)"
        echo "2. API Token (from Coolify Settings -> API Tokens)"
        return 1
    fi
    return 0
}

# Function to check if application exists
check_application() {
    if ! coolify status &>/dev/null; then
        echo -e "${YELLOW}Application not found in Coolify.${NC}"
        echo "Please run: coolify applications:add"
        echo ""
        echo "Select:"
        echo "1. Application name: tg-tui"
        echo "2. Repository: https://github.com/adntgv/tg-tui"
        echo "3. Branch: main"
        echo "4. Compose file: docker-compose.coolify.yml"
        return 1
    fi
    return 0
}

# Main deployment flow
main() {
    echo -e "${BLUE}Step 1: Checking Coolify instance...${NC}"
    if ! check_instance; then
        echo -e "${YELLOW}Run: coolify instances:add${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Instance configured${NC}"
    
    echo ""
    echo -e "${BLUE}Step 2: Checking application...${NC}"
    if ! check_application; then
        echo -e "${YELLOW}Run: coolify applications:add${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Application found${NC}"
    
    echo ""
    echo -e "${BLUE}Step 3: Deploying application...${NC}"
    
    # Deploy
    if coolify deploy; then
        echo -e "${GREEN}✓ Deployment started successfully!${NC}"
        echo ""
        
        # Show status
        echo -e "${BLUE}Application status:${NC}"
        coolify status
        
        echo ""
        echo -e "${GREEN}Deployment complete!${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Check logs: coolify execute -- logs -f"
        echo "2. Set webhook: curl -X POST \"https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook\" -d \"url=${WEBAPP_URL}/webhook\""
        echo "3. Test your bot in Telegram"
    else
        echo -e "${RED}Deployment failed!${NC}"
        echo "Check logs: coolify execute -- logs"
        exit 1
    fi
}

# Run main function
main
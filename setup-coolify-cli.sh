#!/bin/bash

echo "========================================="
echo "     Coolify CLI Setup for TG-TUI"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Coolify CLI is installed
if ! command -v coolify &> /dev/null; then
    echo -e "${RED}Coolify CLI is not installed!${NC}"
    echo "Installing Coolify CLI..."
    npm install -g coolify
fi

echo -e "${GREEN}Coolify CLI is installed${NC}"
echo ""

# Function to setup Coolify instance
setup_instance() {
    echo -e "${YELLOW}Setting up Coolify instance...${NC}"
    echo ""
    echo "You'll need:"
    echo "1. Your Coolify instance URL (e.g., https://coolify.yourdomain.com)"
    echo "2. API Token from Coolify (Settings -> API Tokens)"
    echo ""
    
    coolify instances:add
}

# Function to add application
add_application() {
    echo -e "${YELLOW}Adding TG-TUI application...${NC}"
    echo ""
    
    coolify applications:add
}

# Function to deploy application
deploy_app() {
    echo -e "${YELLOW}Deploying application...${NC}"
    echo ""
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        echo -e "${RED}.env file not found!${NC}"
        echo "Creating .env from template..."
        cp .env.coolify .env
        echo -e "${YELLOW}Please edit .env file with your values before deploying${NC}"
        exit 1
    fi
    
    # Deploy using Coolify CLI
    coolify deploy
}

# Main menu
while true; do
    echo ""
    echo "========================================="
    echo "        Coolify CLI Setup Menu"
    echo "========================================="
    echo "1. Setup Coolify Instance"
    echo "2. Add TG-TUI Application"
    echo "3. Deploy Application"
    echo "4. Check Application Status"
    echo "5. View Application Logs"
    echo "6. Restart Application"
    echo "7. Exit"
    echo ""
    read -p "Select an option (1-7): " choice
    
    case $choice in
        1)
            setup_instance
            ;;
        2)
            add_application
            ;;
        3)
            deploy_app
            ;;
        4)
            coolify status
            ;;
        5)
            coolify execute -- logs -f
            ;;
        6)
            coolify restart
            ;;
        7)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done
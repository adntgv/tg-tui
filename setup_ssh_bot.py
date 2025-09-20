#!/usr/bin/env python3
"""
Setup script for SSH Client Bot
Helps configure the bot and test the database
"""

import os
import sys
import secrets
from pathlib import Path

def generate_encryption_key():
    """Generate a secure encryption key"""
    return secrets.token_urlsafe(32)

def create_env_file():
    """Create .env file with user inputs"""
    print("\n🚀 SSH Client Bot Setup")
    print("=" * 40)
    
    # Check if .env exists
    if Path(".env").exists():
        response = input("\n⚠️  .env file already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return False
    
    # Get bot token
    print("\n1. Bot Configuration")
    print("-" * 20)
    bot_token = input("Enter your Telegram bot token: ").strip()
    if not bot_token:
        print("❌ Bot token is required!")
        return False
    
    # Get webapp URL (optional)
    print("\n2. Web Terminal (Optional)")
    print("-" * 20)
    webapp_url = input("Enter webapp URL (press Enter to skip): ").strip()
    
    # Database configuration
    print("\n3. Database Configuration")
    print("-" * 20)
    print("Default: SQLite (sqlite:///ssh_connections.db)")
    custom_db = input("Enter custom database URL (press Enter for default): ").strip()
    database_url = custom_db if custom_db else "sqlite:///ssh_connections.db"
    
    # Generate encryption key
    print("\n4. Security Configuration")
    print("-" * 20)
    print("Generating secure encryption key...")
    encryption_key = generate_encryption_key()
    print(f"✅ Encryption key generated")
    
    # SSH defaults
    print("\n5. SSH Defaults")
    print("-" * 20)
    ssh_port = input("Default SSH port (press Enter for 22): ").strip()
    ssh_user = input("Default SSH username (press Enter for 'root'): ").strip()
    
    # Admin users
    print("\n6. Admin Configuration (Optional)")
    print("-" * 20)
    admin_ids = input("Admin user IDs (comma-separated, press Enter to skip): ").strip()
    
    # Create .env content
    env_content = f"""# Telegram Bot Configuration
TELEGRAM_TOKEN={bot_token}

# Webapp Configuration
WEBAPP_URL={webapp_url}
WEBAPP_PORT=8000

# Database Configuration
DATABASE_URL={database_url}

# Security Configuration
ENCRYPTION_KEY={encryption_key}
ENABLE_AUDIT_LOG=true

# Session Configuration
MAX_SESSIONS_PER_USER=3
SESSION_TIMEOUT_MINUTES=30
POLL_INTERVAL=0.2

# SSH Defaults
DEFAULT_SSH_PORT={ssh_port or '22'}
DEFAULT_SSH_USER={ssh_user or 'root'}

# Feature Flags
ALLOW_QUICK_CONNECT=true
ALLOW_KEY_UPLOAD=true
ALLOW_MULTIPLE_SESSIONS=false

# Admin Users (comma-separated Telegram user IDs)
ADMIN_USER_IDS={admin_ids}

# Development
DEBUG=false
"""
    
    # Write .env file
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("\n✅ Configuration saved to .env")
    print("\n⚠️  IMPORTANT: Keep your .env file secure and never commit it to git!")
    
    return True

def test_database():
    """Test database connection"""
    print("\n🔧 Testing Database Connection")
    print("=" * 40)
    
    try:
        from database import DatabaseManager
        from security import EncryptionManager
        
        # Load config
        from dotenv import load_dotenv
        load_dotenv()
        
        # Initialize components
        db = DatabaseManager()
        encryption = EncryptionManager()
        
        print("✅ Database connection successful")
        
        # Create test user
        test_user = db.get_or_create_user(
            user_id=12345,
            username="test_user",
            first_name="Test"
        )
        print(f"✅ Test user created: {test_user}")
        
        # Test encryption
        test_data = "test_password_123"
        encrypted = encryption.encrypt(test_data, 12345)
        decrypted = encryption.decrypt(encrypted, 12345)
        
        if decrypted == test_data:
            print("✅ Encryption/decryption working")
        else:
            print("❌ Encryption test failed")
            return False
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def install_dependencies():
    """Check and install dependencies"""
    print("\n📦 Checking Dependencies")
    print("=" * 40)
    
    try:
        import telegram
        import sqlalchemy
        import cryptography
        print("✅ All dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nInstalling dependencies...")
        os.system("pip install -r requirements.txt")
        return True

def main():
    """Main setup function"""
    print("""
╔══════════════════════════════════════╗
║     SSH Client Bot Setup Wizard      ║
╚══════════════════════════════════════╝
    """)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ required")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Failed to install dependencies")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        sys.exit(1)
    
    # Test database
    if test_database():
        print("\n" + "=" * 40)
        print("🎉 Setup Complete!")
        print("=" * 40)
        print("\nYou can now run the bot with:")
        print("  python main_v2.py")
        print("\nFirst steps:")
        print("1. Start a chat with your bot")
        print("2. Send /start to register")
        print("3. Use /add to save your first SSH connection")
        print("\nFor more information, see README_SSH_CLIENT.md")
    else:
        print("\n⚠️  Setup completed with warnings")
        print("Please check your configuration")

if __name__ == "__main__":
    main()
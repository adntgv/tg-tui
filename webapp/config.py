"""
Configuration for the SSH Telegram Bot
"""
import os
from decouple import config

# Bot Configuration
TELEGRAM_TOKEN = config('TELEGRAM_TOKEN')
WEBAPP_URL = config('WEBAPP_URL', default=None)

# Database Configuration
DATABASE_URL = config('DATABASE_URL', default='sqlite:///ssh_connections.db')

# Encryption Configuration
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='change_this_to_a_secure_key!')

# Session Configuration
MAX_SESSIONS_PER_USER = config('MAX_SESSIONS_PER_USER', default=3, cast=int)
SESSION_TIMEOUT_MINUTES = config('SESSION_TIMEOUT_MINUTES', default=30, cast=int)
POLL_INTERVAL = config('POLL_INTERVAL', default=0.2, cast=float)

# SSH Defaults
DEFAULT_SSH_PORT = config('DEFAULT_SSH_PORT', default=22, cast=int)
DEFAULT_SSH_USER = config('DEFAULT_SSH_USER', default=os.environ.get("USER", "root"))

# Security Configuration
ENABLE_AUDIT_LOG = config('ENABLE_AUDIT_LOG', default=True, cast=bool)
RATE_LIMIT_COMMANDS = config('RATE_LIMIT_COMMANDS', default=10, cast=int)  # Per minute
MAX_CONNECTION_ATTEMPTS = config('MAX_CONNECTION_ATTEMPTS', default=3, cast=int)

# Telegram Limits
TG_MESSAGE_LIMIT = 4096

# Feature Flags
ALLOW_QUICK_CONNECT = config('ALLOW_QUICK_CONNECT', default=True, cast=bool)
ALLOW_KEY_UPLOAD = config('ALLOW_KEY_UPLOAD', default=True, cast=bool)
ALLOW_MULTIPLE_SESSIONS = config('ALLOW_MULTIPLE_SESSIONS', default=False, cast=bool)

# Admin Users (optional - for bot administration)
ADMIN_USER_IDS = config('ADMIN_USER_IDS', default='', cast=lambda x: set(map(int, filter(None, x.split(',')))))

# Development
DEBUG = config('DEBUG', default=False, cast=bool)
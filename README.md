# SSH Telegram Terminal Bot

A powerful multi-user Telegram bot that provides secure SSH terminal access to remote servers. Save multiple SSH connections with encrypted credentials and connect to your servers directly from Telegram.

## Features

### 🔐 Multi-User Connection Management

- **Save Multiple SSH Connections**: Store unlimited SSH servers with nicknames
- **Encrypted Credentials**: All passwords and SSH keys encrypted at rest
- **One-Click Connect**: Access saved servers instantly from inline menus
- **Default Connection**: Set your most-used server as default
- **Per-User Isolation**: Each user's connections are completely isolated
- **Audit Logging**: Track all connection activity (optional)

### 🤖 Three Connection Modes

1. **Saved Connections** (`/add`, `/connections`) - Primary workflow
   - Add connections with password or SSH key authentication
   - Browse and connect from inline keyboard
   - Auto-reconnect to default server
   - Connection wizard for easy setup

2. **Quick Connect** (`/quick`) - Temporary connections
   - Connect without saving: `/quick host [port] [username]`
   - Useful for one-time access
   - Supports password and key-based auth

3. **Web App Mode** (`/webapp`) - Full terminal in Telegram Mini App
   - Complete xterm.js terminal emulator
   - Real-time WebSocket communication
   - Full keyboard and mouse support
   - Mobile-optimized with virtual keyboard

### 🔒 Security Features

- End-to-end encryption for stored credentials (Fernet symmetric encryption)
- Per-user encryption keys (user_id + master key)
- Automatic user registration and session management
- SSH key and password authentication support
- Temporary SSH key files with restrictive permissions (0600)
- Session isolation per user
- Optional admin user controls

## Installation

### Prerequisites

- Python 3.8+
- Linux/Unix system (for PTY support)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- (Optional) Docker and Docker Compose for containerized deployment

### Quick Start with Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tg-tui.git
cd tg-tui
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env and set:
# - TELEGRAM_TOKEN (from @BotFather)
# - WEBAPP_URL (your domain or ngrok URL)
# - ENCRYPTION_KEY (generate with: openssl rand -hex 32)
```

3. Start with Docker Compose:
```bash
docker-compose up -d

# View logs
docker-compose logs -f
```

### Manual Setup (Development)

1. Clone and setup virtual environment:
```bash
git clone https://github.com/yourusername/tg-tui.git
cd tg-tui
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
# Bot dependencies
pip install -r requirements.txt

# Web app dependencies
cd webapp && pip install -r requirements.txt && cd ..
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env and set required variables
```

4. Run the bot:
```bash
# Terminal 1: Start the bot
python main.py

# Terminal 2: Start the web app (for webapp mode)
cd webapp && python app.py
```

### Production Deployment

For production deployment with Coolify, Traefik, or other platforms, see [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md) for detailed instructions.

## Usage

### Getting Started

1. **Start the bot**: Send `/start` to your bot in Telegram
2. **Add your first connection**: Use `/add` and follow the wizard
3. **Connect**: Use `/connections` and click on a saved server

### Managing Connections

#### Add a New Connection
```
/add
```
Follow the interactive wizard to:
- Set a nickname for the connection
- Enter host, port, and username
- Choose authentication method (password or SSH key)
- Enter credentials securely

#### List Saved Connections
```
/connections
```
Shows all your saved connections with inline buttons to connect instantly.

#### Connect to a Saved Server
```
/connect <connection_name>
```
Or click the connection from `/connections` menu.

#### Set Default Connection
```
/setdefault <connection_name>
```
Your default connection can be accessed quickly from the main menu.

#### Delete a Connection
```
/delete <connection_name>
```

### Quick Connect (Temporary)

For one-time connections without saving:
```
/quick example.com
/quick server.local 2222 admin
/quick 192.168.1.100
```

### Active Session Commands

Once connected to a server:

```
# Send commands directly (type message and send)
ls -la
pwd
top

# Check connection status
/status

# Disconnect from server
/disconnect
```

### Web App Terminal

For the best experience, especially on mobile:

```
/webapp
```

Features:
- Full xterm.js terminal emulator
- Complete keyboard support
- Copy/paste functionality
- Real-time WebSocket communication
- Mobile-optimized interface

## Architecture

### Project Structure

```
tg-tui/
├── main.py              # Main bot application with Telegram handlers
├── config.py            # Centralized configuration (env vars)
├── requirements.txt     # Bot dependencies
│
├── database/            # Database layer (SQLAlchemy ORM)
│   ├── manager.py       # DatabaseManager - all DB operations
│   └── models.py        # User, SSHConnection, ActiveSession, AuditLog
│
├── security/            # Encryption and security
│   └── encryption.py    # EncryptionManager - Fernet encryption
│
├── ssh/                 # SSH connection management
│   ├── connections.py   # ConnectionManager - CRUD for connections
│   └── session_manager.py # EnhancedSSHManager - active sessions (pexpect)
│
├── ui/                  # Telegram UI components
│   ├── keyboards.py     # KeyboardBuilder - inline keyboards
│   └── wizards.py       # ConnectionWizard - conversation flows
│
└── webapp/              # Web terminal (Telegram Mini App)
    ├── app.py           # FastAPI + WebSocket server
    ├── ssh_handler.py   # SSH handling for webapp
    ├── requirements.txt # Web app dependencies
    └── templates/       # xterm.js frontend
        └── terminal.html
```

### How It Works

**Bot Server** ([main.py](main.py)):
- Command handlers for connection management (`/add`, `/connect`, `/delete`)
- SSH session management using `pexpect` with full PTY support
- Inline keyboard menus for user interaction
- Optional TUI mode with `pyte` terminal emulator
- Auto-registration and per-user isolation

**Database Layer** ([database/](database/)):
- SQLAlchemy ORM with SQLite (PostgreSQL compatible)
- **User**: Auto-registered Telegram users
- **SSHConnection**: Saved connections with encrypted credentials
- **ActiveSession**: Tracks live SSH sessions
- **AuditLog**: Security event logging

**Security** ([security/encryption.py](security/encryption.py)):
- Fernet symmetric encryption (AES-128)
- Per-user encryption: `key = hash(ENCRYPTION_KEY + user_id)`
- Passwords and SSH keys encrypted at rest
- Temporary key files with 0600 permissions

**SSH Management** ([ssh/](ssh/)):
- `ConnectionManager`: Encrypts and stores credentials
- `EnhancedSSHManager`: Manages active `pexpect.spawn` sessions
- Supports password and key-based authentication
- PTY for interactive programs (vim, nano, top)

**Web App** ([webapp/app.py](webapp/app.py)):
- FastAPI with WebSocket endpoints
- Separate PTY per user session
- xterm.js terminal emulator on frontend
- Telegram Web App SDK integration
- Shares database with bot service

## Security Considerations

⚠️ **IMPORTANT**: This bot provides SSH access to remote servers!

### Best Practices

- **Encryption Key**: Generate a strong encryption key and keep it secret
  ```bash
  openssl rand -hex 32
  ```
  ⚠️ Changing the encryption key will invalidate all stored credentials!

- **Environment Variables**: Never commit `.env` file with sensitive data
- **SSH Keys**: Preferred over passwords for authentication
- **Audit Logs**: Enable `ENABLE_AUDIT_LOG=true` to track all connections
- **Admin Controls**: Use `ADMIN_USER_IDS` for administrative features
- **Session Limits**: Configure `MAX_SESSIONS_PER_USER` and `SESSION_TIMEOUT_MINUTES`

### What's Protected

✅ **Encrypted at Rest**: Passwords, SSH private keys, key passphrases
✅ **Per-User Isolation**: Each user's data is completely isolated
✅ **Secure Sessions**: Temporary SSH key files with 0600 permissions
✅ **Auto-Registration**: No manual user management needed

### What You Should Do

- Use strong Telegram bot token
- Regularly rotate encryption keys (requires credential re-entry)
- Monitor audit logs for suspicious activity
- Use HTTPS for webapp deployment (Let's Encrypt recommended)
- Consider VPN or IP restrictions for production deployments

## Configuration

All configuration is managed through environment variables (`.env` file):

### Required Variables

```bash
TELEGRAM_TOKEN=your_bot_token_here
ENCRYPTION_KEY=your_32_byte_hex_string
WEBAPP_URL=https://your-domain.com
```

### Optional Configuration

```bash
# Database
DATABASE_URL=sqlite:///ssh_connections.db  # Or PostgreSQL URL

# Session Management
MAX_SESSIONS_PER_USER=3
SESSION_TIMEOUT_MINUTES=30
POLL_INTERVAL=0.2

# SSH Defaults
DEFAULT_SSH_PORT=22
DEFAULT_SSH_USER=root

# Security
ENABLE_AUDIT_LOG=true
RATE_LIMIT_COMMANDS=10
MAX_CONNECTION_ATTEMPTS=3

# Feature Flags
ALLOW_QUICK_CONNECT=true
ALLOW_KEY_UPLOAD=true
ALLOW_MULTIPLE_SESSIONS=false

# Admin
ADMIN_USER_IDS=123456789,987654321  # Comma-separated

# Development
DEBUG=false
```

See [.env.example](.env.example) for complete configuration template.

## Development

### Adding New Features

1. **New Commands**: Add handlers in [main.py](main.py) and register them:
   ```python
   async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
       # Your logic here
       pass

   application.add_handler(CommandHandler("mycommand", my_command))
   ```

2. **New Database Models**: Extend [database/models.py](database/models.py) and add methods to [database/manager.py](database/manager.py)

3. **Keyboard Layouts**: Add builders to [ui/keyboards.py](ui/keyboards.py)

4. **Conversation Flows**: Create wizards in [ui/wizards.py](ui/wizards.py) using `ConversationHandler`

5. **Web App Enhancements**: Modify [webapp/templates/terminal.html](webapp/templates/terminal.html) or [webapp/app.py](webapp/app.py)

### Running Tests

```bash
# Currently no test suite - contributions welcome!
# Manual testing via Telegram bot
```

### Debugging

Enable debug logging in `.env`:
```bash
DEBUG=true
```

Or in code:
```python
logging.basicConfig(level=logging.DEBUG)
```

Monitor logs:
```bash
# Docker
docker-compose logs -f bot
docker-compose logs -f webapp

# Local
tail -f logs/bot.log
```

Database inspection:
```bash
sqlite3 ssh_connections.db
.tables
SELECT * FROM users;
SELECT * FROM ssh_connections;
```

## Troubleshooting

### Common Issues

1. **Connection fails with "Invalid credentials"**:
   - Verify your SSH credentials are correct
   - Test connection manually: `ssh username@host -p port`
   - Check if SSH key has passphrase (you'll need to provide it)
   - Ensure host is reachable from bot server

2. **"Database locked" errors**:
   - SQLite has limited concurrency
   - For production, use PostgreSQL: `DATABASE_URL=postgresql://user:pass@host/db`

3. **Web app not loading**:
   - Verify `WEBAPP_URL` is correct and accessible
   - Check webapp service is running: `docker-compose logs webapp`
   - Ensure port 8000 is exposed and reachable
   - Check browser console for WebSocket errors

4. **Encryption errors after key change**:
   - Changing `ENCRYPTION_KEY` invalidates all stored credentials
   - Users must re-add their connections with `/add`
   - This is by design for security

5. **Sessions timeout quickly**:
   - Increase `SESSION_TIMEOUT_MINUTES` in `.env`
   - Check `POLL_INTERVAL` isn't too high
   - Verify server doesn't have short SSH timeout

6. **Bot not responding**:
   - Check bot is running: `docker-compose ps`
   - Verify `TELEGRAM_TOKEN` is correct
   - Check logs: `docker-compose logs -f bot`
   - Test bot token: `https://api.telegram.org/bot<TOKEN>/getMe`

## Available Commands

Complete list of bot commands:

```
/start          - Welcome message and main menu
/help           - Show all available commands
/add            - Add new SSH connection (interactive wizard)
/connections    - List all saved connections
/connect <name> - Connect to a saved server
/quick <host>   - Quick connect without saving
/disconnect     - Close current SSH session
/status         - Show active session status
/delete <name>  - Delete a saved connection
/setdefault     - Set default connection
/webapp         - Open web terminal interface
/settings       - Bot settings (if available)
/about          - About this bot
```

## Deployment Options

### Local Development
```bash
python main.py
cd webapp && python app.py
```

### Docker Compose
```bash
docker-compose up -d
```

### Coolify (Recommended for Production)
See [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md) for complete guide.

### Other Platforms
- **VPS**: Use `docker-compose.prod.yml`
- **Cloudflare Tunnel**: See [cloudflare-setup.md](cloudflare-setup.md)
- **Kubernetes**: Adapt Docker Compose files to K8s manifests

## Contributing

Contributions are welcome! Areas for improvement:

- [ ] Add unit and integration tests
- [ ] Support for SFTP file transfers
- [ ] Session recording and playback
- [ ] Multi-server command execution
- [ ] PostgreSQL migration scripts (Alembic)
- [ ] Rate limiting per user
- [ ] Connection groups/tags
- [ ] Better mobile TUI mode

Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with clear commit messages
4. Test thoroughly (manual testing required)
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram bot framework
- [xterm.js](https://xtermjs.org/) - Terminal emulator for the web
- [pexpect](https://pexpect.readthedocs.io/) - PTY control and SSH automation
- [pyte](https://github.com/selectel/pyte) - Terminal emulator library for TUI mode
- [FastAPI](https://fastapi.tiangolo.com/) - Modern async web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [cryptography](https://cryptography.io/) - Encryption library (Fernet)

## Related Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide for Claude Code
- [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md) - Production deployment guide
- [README_SSH_CLIENT.md](README_SSH_CLIENT.md) - SSH client implementation details
- [cloudflare-setup.md](cloudflare-setup.md) - Cloudflare Tunnel configuration

---

⚠️ **Security Warning**: This bot provides SSH access to remote servers. Use strong encryption keys, enable audit logging, and deploy only in controlled environments with proper security measures.
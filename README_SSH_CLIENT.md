# 🔐 Telegram SSH Client Bot

A powerful multi-user SSH client bot for Telegram that allows users to securely manage and connect to multiple SSH servers directly from their Telegram app.

## ✨ Features

### Connection Management
- **Save Multiple Connections**: Store unlimited SSH server configurations
- **Encrypted Credentials**: All passwords and SSH keys are encrypted with user-specific keys
- **Quick Connect**: Connect to saved servers with one click
- **Connection Types**: Support for both password and SSH key authentication
- **Default Connection**: Set a default server for quick access

### Security
- **Per-User Isolation**: Each user's data is completely isolated
- **Encrypted Storage**: AES-256 encryption for all sensitive data  
- **Audit Logging**: Optional logging of all connection attempts
- **Session Management**: Automatic cleanup of idle sessions
- **No Hardcoded Access**: No special privileges or backdoors

### Terminal Features
- **Full PTY Support**: Run any interactive program (vim, top, htop, etc.)
- **TUI Mode**: Navigate with inline keyboard buttons
- **Web Terminal**: Full web-based terminal interface
- **Real-time Output**: Stream command output in real-time
- **Multiple Sessions**: Support for concurrent sessions (configurable)

## 🚀 Quick Start

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/tg-tui.git
cd tg-tui
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run the bot**:
```bash
python main_v2.py
```

### Docker Deployment

```bash
docker-compose up -d
```

## 📱 Usage

### First Time Setup

1. Start a chat with your bot
2. Send `/start` to register
3. Add your first connection with `/add`

### Managing Connections

#### Add a Connection
```
/add
```
The bot will guide you through:
- Connection name
- Host address  
- SSH port (default 22)
- Username
- Authentication type (password/key)
- Credentials

#### List Connections
```
/connections
```
Shows all saved connections with quick connect buttons.

#### Connect to Server
```
/connect <name>
```
Or use the inline keyboard from `/connections`.

#### Quick Connect (Without Saving)
```
/quick example.com 22 root
```

#### Delete Connection
```
/delete <name>
```

#### Set Default Connection
```
/setdefault <name>
```

### During SSH Session

- **Send Commands**: Just type and send
- **Special Keys**: Use `/key` command for special keys
- **TUI Mode**: `/tui` for keyboard navigation
- **Web Terminal**: `/webapp` for full terminal
- **Disconnect**: `/disconnect`
- **Status**: `/status`

## ⚙️ Configuration

### Required Environment Variables

```env
# Bot token from @BotFather
TELEGRAM_TOKEN=your_bot_token_here

# Database URL (SQLite by default)
DATABASE_URL=sqlite:///ssh_connections.db

# Encryption key (change this!)
ENCRYPTION_KEY=your_secure_encryption_key_here
```

### Optional Configuration

```env
# Session settings
MAX_SESSIONS_PER_USER=3
SESSION_TIMEOUT_MINUTES=30

# SSH defaults  
DEFAULT_SSH_PORT=22
DEFAULT_SSH_USER=root

# Features
ALLOW_QUICK_CONNECT=true
ALLOW_KEY_UPLOAD=true
ENABLE_AUDIT_LOG=true

# Web terminal URL (optional)
WEBAPP_URL=https://your-terminal-webapp.com
```

## 🔒 Security Considerations

### Encryption
- Each user has a unique encryption key derived from their Telegram ID
- All credentials are encrypted using AES-256 (Fernet)
- SSH keys are never stored in plain text

### Best Practices
1. **Change the default encryption key** in production
2. **Use strong passwords** for SSH connections
3. **Regularly update** dependencies
4. **Monitor audit logs** if enabled
5. **Use SSH keys** instead of passwords when possible
6. **Deploy with HTTPS** for the web terminal

### Data Privacy
- No telemetry or usage tracking
- All data stays in your database
- Users can only access their own connections
- No shared state between users

## 📊 Database Schema

The bot uses SQLite by default (can be changed to PostgreSQL):

- **users**: Telegram user information
- **ssh_connections**: Encrypted connection details
- **active_sessions**: Current SSH sessions
- **audit_log**: Optional security audit trail

## 🛠️ Advanced Features

### Admin Commands (Optional)

Set admin user IDs in `.env`:
```env
ADMIN_USER_IDS=123456789,987654321
```

Admin commands:
- `/admin_stats` - View usage statistics
- `/admin_users` - List all users
- `/admin_cleanup` - Clean old sessions

### Custom SSH Options

Modify SSH command options in `ssh/session_manager.py`:
```python
ssh_cmd = f"ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60"
```

### Connection Sharing

Future feature: Allow read-only access to connections for team collaboration.

## 🐛 Troubleshooting

### Common Issues

**Bot not responding**:
- Check bot token is correct
- Ensure bot is not blocked
- Verify network connectivity

**Connection fails**:
- Verify SSH credentials
- Check if SSH port is open
- Ensure host is reachable

**Authentication issues**:
- Re-enter credentials with `/delete` and `/add`
- Check SSH key format
- Verify key permissions

**Session timeout**:
- Adjust `SESSION_TIMEOUT_MINUTES`
- Check `ServerAliveInterval` in SSH options

### Debug Mode

Enable debug logging:
```env
DEBUG=true
```

## 📝 Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Start bot and show menu | `/start` |
| `/add` | Add new connection | `/add` |
| `/connections` | List all connections | `/connections` |
| `/connect <name>` | Connect to saved server | `/connect myserver` |
| `/quick <host>` | Quick connect | `/quick example.com` |
| `/disconnect` | Close SSH session | `/disconnect` |
| `/status` | Show connection status | `/status` |
| `/delete <name>` | Delete connection | `/delete oldserver` |
| `/setdefault <name>` | Set default connection | `/setdefault myserver` |
| `/send <text>` | Send raw text | `/send ls -la` |
| `/tui` | Start TUI mode | `/tui` |
| `/webapp` | Open web terminal | `/webapp` |
| `/help` | Show help | `/help` |

## 🚦 Roadmap

- [ ] Multiple concurrent sessions
- [ ] SFTP file transfer support  
- [ ] SSH tunnel management
- [ ] Connection templates
- [ ] Team sharing features
- [ ] 2FA authentication
- [ ] Session recording
- [ ] Mobile-optimized UI
- [ ] Connection health checks
- [ ] Bulk connection import/export

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This bot provides SSH access to remote servers. Users are responsible for:
- Securing their bot instance
- Managing their SSH credentials safely
- Complying with their organization's security policies
- Any actions performed through SSH connections

## 🆘 Support

For issues and feature requests, please open an issue on GitHub.

---

**Security Note**: Never share your bot token, encryption key, or SSH credentials. Always use this bot in a secure environment and regularly update dependencies.
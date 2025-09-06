# Telegram Terminal Bot

A powerful Telegram bot that provides full terminal access through multiple interfaces - from simple shell commands to a complete web-based terminal emulator.

## Features

### 🤖 Bot Modes

1. **Shell Mode** (`/startsh`) - Basic terminal in Telegram chat
   - Direct command execution
   - Interactive programs support (ssh, python REPL, etc.)
   - PTY emulation for proper terminal behavior

2. **TUI Mode** (`/tui start`) - Enhanced terminal with inline keyboard
   - Visual terminal display with ANSI color support
   - Inline keyboard with arrow keys, Ctrl combinations, and special keys
   - Mobile-optimized 60x24 terminal size
   - Persistent message that stays at bottom of chat

3. **Web App Mode** (`/webapp`) - Full terminal in Telegram Mini App
   - Complete xterm.js terminal emulator
   - Real-time WebSocket communication
   - Full keyboard and mouse support
   - Hide/show virtual keyboard button for maximized screen space

### 🔒 Security

- User authorization by Telegram ID whitelist
- Secure PTY handling
- Session isolation per user

## Installation

### Prerequisites

- Python 3.8+
- Linux/Unix system (for PTY support)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tg-terminal-bot.git
cd tg-terminal-bot
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
# Bot dependencies
pip install python-telegram-bot pexpect pyte nest-asyncio

# Web app dependencies (if using webapp mode)
cd webapp
pip install -r requirements.txt
cd ..
```

4. Configure the bot:
```bash
# Edit main.py and add your Telegram user ID to AUTHORIZED_USER_IDS
AUTHORIZED_USER_IDS = {
    123456789,  # Replace with your Telegram user ID
}
```

5. Set environment variables:
```bash
export TELEGRAM_TOKEN="your_bot_token_here"

# For web app mode (optional)
export WEBAPP_URL="https://your-domain.com"  # Or use ngrok for testing
```

## Running the Bot

### Start the main bot:
```bash
python main.py
```

### Start the web app server (optional):
```bash
cd webapp
python app.py
```

For testing, you can use ngrok to expose the web app:
```bash
ngrok http 8080
# Then set WEBAPP_URL to the ngrok URL
```

## Usage

### Basic Shell Mode

1. Start a shell session:
```
/startsh
```

2. Run commands:
```
ls -la
pwd
echo "Hello, World!"
```

3. Stop the session:
```
/stop
```

### TUI Mode (Terminal UI)

1. Start TUI mode:
```
/tui start
```

2. Use the inline keyboard for:
   - Arrow keys navigation
   - Ctrl combinations (Ctrl+C, Ctrl+D, etc.)
   - Special keys (Tab, Escape, Enter, Backspace)
   - Function keys and more

3. Switch keyboard layouts:
```
/key nav     # Navigation keys
/key ctrl    # Control combinations
/key special # Special characters
/key fn      # Function keys
```

### Web App Mode

1. Launch the web app:
```
/webapp
```

2. Click "🖥️ Open Terminal Web App"

3. Features:
   - Full terminal emulation
   - Copy/paste support
   - Touch-friendly interface
   - Toggle keyboard visibility with floating button

## Architecture

### Components

```
tg-tui/
├── main.py              # Main bot logic
├── webapp/
│   ├── app.py          # FastAPI WebSocket server
│   ├── requirements.txt # Web app dependencies
│   └── templates/
│       └── terminal.html # xterm.js frontend
└── README.md           # This file
```

### How It Works

1. **Bot Server** (`main.py`):
   - Handles Telegram messages and commands
   - Manages PTY sessions using `pexpect`
   - Renders terminal output using `pyte` for TUI mode
   - Provides inline keyboards for terminal control

2. **Web App Server** (`webapp/app.py`):
   - FastAPI server with WebSocket support
   - Creates PTY for each user session
   - Bidirectional communication between browser and terminal
   - Proper PTY handling with master/slave FD management

3. **Web Frontend** (`terminal.html`):
   - xterm.js for terminal rendering
   - WebSocket client for real-time communication
   - Telegram Web App SDK integration
   - Mobile-optimized UI with virtual keyboard

## Security Considerations

⚠️ **IMPORTANT**: This bot provides full terminal access to your system!

- **Always** restrict access using `AUTHORIZED_USER_IDS`
- Never share your bot token publicly
- Consider running in a container or restricted environment
- Be cautious with commands that modify system files
- Monitor bot usage through logs

## Development

### Adding New Features

1. **New Commands**: Add handlers in `main.py`:
```python
app.add_handler(CommandHandler("yourcommand", your_handler))
```

2. **Keyboard Layouts**: Extend `get_terminal_keyboard()` in `main.py`

3. **Web App Enhancements**: Modify `webapp/templates/terminal.html`

### Debugging

- Enable debug logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

- Monitor WebSocket connections:
```bash
tail -f webapp/app.log  # If logging is configured
```

## Troubleshooting

### Common Issues

1. **"Unauthorized" message**:
   - Add your Telegram ID to `AUTHORIZED_USER_IDS`
   - Get your ID from [@userinfobot](https://t.me/userinfobot)

2. **Terminal not responding in web app**:
   - Check WebSocket connection in browser console
   - Ensure webapp server is running
   - Verify WEBAPP_URL is correctly set

3. **Special keys not working**:
   - Use TUI mode with inline keyboard
   - Or use web app for full keyboard support

4. **Line wrapping issues**:
   - TUI mode uses 60-column width for mobile
   - Adjust terminal size with `stty cols 60 rows 24`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram bot framework
- [xterm.js](https://xtermjs.org/) - Terminal emulator for the web
- [pexpect](https://pexpect.readthedocs.io/) - PTY control library
- [pyte](https://github.com/selectel/pyte) - Terminal emulator library
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact via Telegram (if provided)

---

⚠️ **Security Warning**: This bot provides system-level access. Use with extreme caution and only in controlled environments.
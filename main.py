#!/usr/bin/env python3
"""
Multi-User SSH Terminal Telegram Bot
-------------------------------------
A Telegram bot that allows users to manage and connect to multiple SSH servers.
Each user can save their own SSH connections with encrypted credentials.

Features:
- Save multiple SSH connections with encrypted passwords/keys
- Connect to saved servers with one click
- Full PTY support for interactive programs
- TUI mode with keyboard navigation
- Web terminal interface
- Per-user isolation and security

Run with: python main_v2.py
"""

import asyncio
import os
import logging
import textwrap
import io
import re
from typing import Optional
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes, 
    filters
)

# Import our modules
import config
from database import DatabaseManager
from security import EncryptionManager
from ssh import EnhancedSSHManager, ConnectionManager
from ui import KeyboardBuilder, ConnectionWizard

# Import existing modules (TUI support)
try:
    import pyte
    HAS_PYTE = True
except ImportError:
    HAS_PYTE = False
    print("pyte not installed - TUI mode disabled")

# Import our virtual terminal emulator
from terminal_emulator import VirtualTerminal, TUIAppType, ScreenDiff

# Setup logging
logging.basicConfig(
    level=logging.INFO if not config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
db = DatabaseManager(config.DATABASE_URL)
encryption = EncryptionManager(config.ENCRYPTION_KEY)
ssh_manager = EnhancedSSHManager(db, encryption)
connection_mgr = ConnectionManager(db, encryption)
keyboard_builder = KeyboardBuilder()

# ------------------------- HELPERS -------------------------

def format_connection_info(conn: dict) -> str:
    """Format connection information for display"""
    info = f"**{conn['name']}**\n"
    info += f"Host: {conn['username']}@{conn['host']}:{conn['port']}\n"
    info += f"Auth: {conn['auth_type']}\n"
    if conn.get('last_used'):
        info += f"Last used: {conn['last_used']}"
    return info

def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown V2"""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text

# ------------------------- AUTHENTICATION -------------------------

async def ensure_registered(update: Update) -> bool:
    """Ensure user is registered in the database"""
    user = update.effective_user
    if not user:
        return False
    
    # Auto-register user
    db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    return True

# ------------------------- COMMAND HANDLERS -------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not await ensure_registered(update):
        return await update.message.reply_text("Failed to register. Please try again.")
    
    user = update.effective_user
    welcome_text = f"""
🚀 **Welcome to SSH Terminal Bot, {user.first_name}!**

This bot allows you to securely manage and connect to your SSH servers directly from Telegram.

**Features:**
• Save multiple SSH connections with encrypted credentials
• Connect to any saved server with one click  
• Full terminal emulation with PTY support
• Interactive TUI mode with keyboard navigation
• Web terminal for the best experience

**Quick Start:**
Use /add to save your first SSH connection
Use /connections to see saved connections
Use /help for all available commands

Your data is encrypted and isolated from other users.
    """
    
    keyboard = keyboard_builder.main_menu()
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
**SSH Terminal Bot Commands**

**Connection Management:**
/add - Add new SSH connection
/connections - List saved connections
/connect <name> - Connect to saved server
/delete <name> - Delete saved connection
/setdefault <name> - Set default connection

**Quick Actions:**
/quick <host> [port] [user] - Quick connect (not saved)
/disconnect - Close current SSH session
/status - Show connection status

**Session Commands:**
/send <text> - Send raw text to SSH session
/tui - Start TUI mode (keyboard navigation)
/webapp - Open web terminal
Regular messages - Send with newline

**Other:**
/help - Show this help
/about - About this bot
/settings - Bot settings

**Tips:**
• Save frequently used servers with /add
• Set a default connection for quick access
• Use web terminal for the best experience
• Your credentials are encrypted and secure
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )

# Note: add_connection_cmd is no longer needed since the ConversationHandler 
# in ConnectionWizard handles the /add command directly

async def connections_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connections command - List saved connections"""
    if not await ensure_registered(update):
        return
    
    user_id = update.effective_user.id
    connections = connection_mgr.list_connections(user_id)
    
    if not connections:
        await update.message.reply_text(
            "You don't have any saved connections yet.\n"
            "Use /add to add your first connection!"
        )
        return
    
    # Build connection list message
    message = "**Your SSH Connections:**\n\n"
    for conn in connections:
        if conn.get('is_default'):
            message += "⭐ "
        message += f"`{conn['name']}` - {conn['username']}@{conn['host']}:{conn['port']}\n"
    
    keyboard = keyboard_builder.connections_list(connections)
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

async def connect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connect command - Connect to saved server"""
    if not await ensure_registered(update):
        return
    
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /connect <connection_name>\n"
            "Use /connections to see available connections."
        )
        return
    
    connection_name = args[1]
    await connect_to_server(update, context, connection_name)

async def connect_to_server(update: Update, context: ContextTypes.DEFAULT_TYPE, connection_name: str):
    """Connect to a saved SSH server"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if connection exists
    connection = db.get_connection(user_id, connection_name)
    if not connection:
        await update.effective_message.reply_text(
            f"Connection '{connection_name}' not found.\n"
            "Use /connections to see available connections."
        )
        return
    
    # Try to connect
    await update.effective_message.reply_text(
        f"🔄 Connecting to {connection_name}..."
    )
    
    try:
        session = ssh_manager.connect_saved(user_id, chat_id, connection_name)
        
        if session.connected:
            await update.effective_message.reply_text(
                f"✅ Connected to **{connection_name}**\n"
                f"({connection.username}@{connection.host}:{connection.port})",
                parse_mode=ParseMode.MARKDOWN
            )

            # Start output streaming task - this will send the keyboard
            session.task = asyncio.create_task(tail_output(chat_id, context))
        else:
            await update.effective_message.reply_text(
                "⚠️ Connected but authentication may be required.\n"
                "Send your password if prompted."
            )
    
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        await update.effective_message.reply_text(
            f"❌ Connection failed: {str(e)}"
        )

async def quick_connect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /quick command - Quick connect without saving"""
    if not config.ALLOW_QUICK_CONNECT:
        await update.message.reply_text("Quick connect is disabled.")
        return
    
    if not await ensure_registered(update):
        return
    
    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /quick <host> [port] [username]\n"
            "Example: /quick example.com 22 root"
        )
        return
    
    host = args[1]
    port = int(args[2]) if len(args) > 2 and args[2].isdigit() else config.DEFAULT_SSH_PORT
    username = args[3] if len(args) > 3 else config.DEFAULT_SSH_USER
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(f"🔄 Connecting to {username}@{host}:{port}...")
    
    try:
        session = ssh_manager.connect_manual(chat_id, host, port, username)
        
        if not session.connected:
            await update.message.reply_text(
                "🔐 Authentication required. Please enter your password:"
            )
        else:
            await update.message.reply_text(f"✅ Connected to {username}@{host}:{port}")
        
        # Start output streaming
        session.task = asyncio.create_task(tail_output(chat_id, context))
        
    except Exception as e:
        await update.message.reply_text(f"❌ Connection failed: {str(e)}")

async def disconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /disconnect command"""
    if not await ensure_registered(update):
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    host = ssh_manager.disconnect(chat_id, user_id)
    
    if host:
        await update.message.reply_text(f"✅ Disconnected from {host}")
    else:
        await update.message.reply_text("No active SSH connection.")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    if not await ensure_registered(update):
        return
    
    chat_id = update.effective_chat.id
    session = ssh_manager.get(chat_id)
    
    if session and session.is_alive():
        status = f"🟢 Connected to {session.username}@{session.host}:{session.port}"
        if session.connection_id:
            conn = db.get_connection_by_id(update.effective_user.id, session.connection_id)
            if conn:
                status += f"\nConnection: {conn.name}"
    else:
        status = "🔴 No active SSH connection"
    
    await update.message.reply_text(status)

async def delete_connection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delete command"""
    if not await ensure_registered(update):
        return
    
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /delete <connection_name>"
        )
        return
    
    connection_name = args[1]
    user_id = update.effective_user.id
    
    keyboard = keyboard_builder.confirm_delete(connection_name)
    await update.message.reply_text(
        f"Are you sure you want to delete connection '{connection_name}'?",
        reply_markup=keyboard
    )

async def setdefault_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setdefault command"""
    if not await ensure_registered(update):
        return
    
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /setdefault <connection_name>"
        )
        return
    
    connection_name = args[1]
    user_id = update.effective_user.id
    
    if db.set_default_connection(user_id, connection_name):
        await update.message.reply_text(
            f"⭐ Connection '{connection_name}' is now your default."
        )
    else:
        await update.message.reply_text(
            f"Connection '{connection_name}' not found."
        )

# ------------------------- MESSAGE HANDLERS -------------------------

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages (send to SSH session)"""
    if not await ensure_registered(update):
        return
    
    chat_id = update.effective_chat.id
    session = ssh_manager.get(chat_id)
    
    if not session or not session.is_alive():
        # No active session - show menu
        keyboard = keyboard_builder.main_menu()
        await update.message.reply_text(
            "No active SSH connection.\nChoose an action:",
            reply_markup=keyboard
        )
        return
    
    # Send message to SSH session
    text = update.message.text
    
    # Check if this is a password for authentication
    if not session.connected:
        session.child.sendline(text)
        # Try to detect successful auth
        try:
            index = session.child.expect([r"\$", r"#", r">"], timeout=3)
            session.connected = True
            await update.message.reply_text("✅ Authentication successful!")
        except:
            await update.message.reply_text("🔐 Waiting for authentication...")
    else:
        # Normal command
        session.send(text + "\n")

# ------------------------- CALLBACK HANDLERS -------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    if not await ensure_registered(update):
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    data = query.data
    
    # Main menu callbacks
    if data == "menu_main":
        keyboard = keyboard_builder.main_menu()
        await query.edit_message_text(
            "Choose an action:",
            reply_markup=keyboard
        )
    
    elif data == "menu_add":
        await query.edit_message_text(
            "To add a new SSH connection, use the /add command.\n"
            "I'll guide you through the setup process step by step.\n\n"
            "Type /add to start."
        )
        return
    
    elif data == "menu_quick":
        await query.edit_message_text(
            "**Quick Connect** (without saving)\n\n"
            "Use: `/quick <host> [port] [username]`\n\n"
            "Examples:\n"
            "• `/quick example.com`\n"
            "• `/quick 192.168.1.100 22 root`\n"
            "• `/quick server.local 2222 admin`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif data == "menu_settings":
        user_id = update.effective_user.id
        user = db.get_user(user_id)
        settings_text = f"""
**⚙️ Settings**

**User ID:** `{user_id}`
**Registered:** {user.registered_at.strftime('%Y-%m-%d')}
**Connections:** {len(db.get_connections(user_id))}

**Features:**
• Quick Connect: {'✅' if config.ALLOW_QUICK_CONNECT else '❌'}
• Key Upload: {'✅' if config.ALLOW_KEY_UPLOAD else '❌'}
• Multi-Sessions: {'✅' if config.ALLOW_MULTIPLE_SESSIONS else '❌'}
        """
        await query.edit_message_text(
            settings_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_builder.main_menu()
        )
        return
    
    elif data == "menu_connect":
        connections = connection_mgr.list_connections(user_id)
        if not connections:
            await query.edit_message_text(
                "You don't have any saved connections yet.\n"
                "Use /add to add your first connection!"
            )
        else:
            keyboard = keyboard_builder.connections_list(connections, prefix="connect")
            await query.edit_message_text(
                "Select a connection:",
                reply_markup=keyboard
            )
    
    elif data.startswith("connect:"):
        connection_id = int(data.split(":")[1])
        connection = db.get_connection_by_id(user_id, connection_id)
        if connection:
            await query.edit_message_text(f"Connecting to {connection.name}...")
            await connect_to_server(update, context, connection.name)
    
    elif data == "menu_list":
        connections = connection_mgr.list_connections(user_id)
        if not connections:
            await query.edit_message_text(
                "You don't have any saved connections yet."
            )
        else:
            keyboard = keyboard_builder.connections_list(connections, prefix="manage")
            await query.edit_message_text(
                "Select a connection to manage:",
                reply_markup=keyboard
            )
    
    elif data.startswith("manage:"):
        connection_id = int(data.split(":")[1])
        connection = db.get_connection_by_id(user_id, connection_id)
        if connection:
            keyboard = keyboard_builder.connection_actions(connection.name)
            info = format_connection_info(connection.to_dict())
            await query.edit_message_text(
                info,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
    
    elif data.startswith("confirm_delete:"):
        connection_name = data.split(":")[1]
        if db.delete_connection(user_id, connection_name):
            await query.edit_message_text(
                f"✅ Connection '{connection_name}' deleted."
            )
        else:
            await query.edit_message_text(
                f"Failed to delete connection."
            )
    
    elif data == "session_controls":
        # Show session control options
        session = ssh_manager.get(chat_id)
        if session:
            await query.edit_message_text(
                "📋 **Session Controls**\n\n"
                "Choose an action:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard_builder.session_actions()
            )
        else:
            await query.edit_message_text("No active SSH connection.")

    elif data == "session_disconnect":
        host = ssh_manager.disconnect(chat_id, user_id)
        if host:
            await query.edit_message_text(f"✅ Disconnected from {host}")
        else:
            await query.edit_message_text("No active connection.")

    elif data == "session_tui":
        # Switch to TUI mode with control buttons
        session = ssh_manager.get(chat_id)
        if session:
            # TUI mode is already enabled by default
            # Just show a message that they're in TUI mode
            keyboard = keyboard_builder.session_actions()
            await query.edit_message_text(
                "🖥️ **Terminal Controls**\n\n"
                "Use the buttons below to navigate.\n"
                "Send text messages to type commands.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text("No active SSH connection.")
    
    elif data == "session_webapp" or data == "webapp:launch":
        # Launch web terminal
        if not config.WEBAPP_URL:
            await query.edit_message_text(
                "Web terminal is not configured.\n"
                "Please set WEBAPP_URL in your environment."
            )
        else:
            from telegram import WebAppInfo
            
            # Check if there's an active SSH session to include session_id
            session = ssh_manager.get(chat_id)
            if session and session.is_alive() and session.session_id:
                webapp_url = f"{config.WEBAPP_URL}?user_id={user_id}&session_id={session.session_id}"
            else:
                webapp_url = f"{config.WEBAPP_URL}?user_id={user_id}"
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🌐 Open Web Terminal",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ]])
            await query.edit_message_text(
                "Click below to open the web terminal:",
                reply_markup=keyboard
            )
    
    elif data.startswith("key:"):
        # Handle key presses
        key = data[4:]  # Remove "key:" prefix
        session = ssh_manager.get(chat_id)
        if session and session.is_alive():
            # Map special keys to terminal sequences
            key_map = {
                'up': '\x1b[A', 'down': '\x1b[B', 
                'right': '\x1b[C', 'left': '\x1b[D',
                'home': '\x1b[H', 'end': '\x1b[F',
                'pgup': '\x1b[5~', 'pgdn': '\x1b[6~',
                'tab': '\t', 'shift+tab': '\x1b[Z',
                'enter': '\r', 'esc': '\x1b',
                'backspace': '\x7f', 'delete': '\x1b[3~',
                'space': ' ',
                'ctrl+a': '\x01', 'ctrl+b': '\x02', 'ctrl+c': '\x03',
                'ctrl+d': '\x04', 'ctrl+e': '\x05', 'ctrl+f': '\x06',
                'ctrl+k': '\x0b', 'ctrl+l': '\x0c', 'ctrl+r': '\x12',
                'ctrl+u': '\x15', 'ctrl+w': '\x17', 'ctrl+z': '\x1a',
                'f1': '\x1bOP', 'f2': '\x1bOQ', 'f3': '\x1bOR', 'f4': '\x1bOS',
                'f5': '\x1b[15~', 'f6': '\x1b[17~', 'f7': '\x1b[18~', 'f8': '\x1b[19~',
                'f9': '\x1b[20~', 'f10': '\x1b[21~', 'f11': '\x1b[23~', 'f12': '\x1b[24~',
            }
            
            if key in key_map:
                session.child.send(key_map[key])
                await query.answer(f"Sent: {key}")
            elif key.startswith("ctrl+b,"):
                # Handle tmux command sequences (Ctrl+B followed by another key)
                tmux_key = key[7:]  # Remove "ctrl+b," prefix
                session.child.send('\x02')  # Send Ctrl+B first
                session.child.send(tmux_key)  # Then send the tmux command key
                await query.answer(f"Sent: Ctrl+B {tmux_key}")
            elif key.startswith(":"):
                # Handle vim command sequences
                vim_command = key + '\r'  # Add enter to execute command
                session.child.send(vim_command)
                await query.answer(f"Sent vim command: {key}")
            elif len(key) == 1:
                # Handle single character keys (letters, numbers, symbols)
                session.child.send(key)
                await query.answer(f"Sent: {key}")
            else:
                await query.answer(f"Unknown key: {key}")
        else:
            await query.answer("No active SSH connection", show_alert=True)
    
    elif data.startswith("kbd:"):
        # Switch keyboard layouts
        kbd_type = data[4:]  # Remove "kbd:" prefix
        session = ssh_manager.get(chat_id)
        if session:
            if kbd_type == "navigation":
                keyboard = keyboard_builder.session_actions()
                text = "🖥️ **Terminal Controls**"
            elif kbd_type == "ctrl":
                keyboard = keyboard_builder.tui_ctrl()
                text = "🎛️ **Ctrl Key Combinations**"
            elif kbd_type == "special":
                keyboard = keyboard_builder.tui_special()
                text = "⚡ **Special Keys**"
            elif kbd_type == "function":
                keyboard = keyboard_builder.tui_function()
                text = "🔧 **Function Keys**"
            else:
                keyboard = keyboard_builder.session_actions()
                text = "🖥️ **Terminal Controls**"
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            await query.answer("No active SSH connection", show_alert=True)
    
    elif data == "menu_help":
        help_text = """
**SSH Terminal Bot Commands**

**Connection Management:**
/add - Add new SSH connection
/connections - List saved connections
/connect <name> - Connect to saved server
/delete <name> - Delete saved connection
/setdefault <name> - Set default connection

**Quick Actions:**
/quick <host> [port] [user] - Quick connect (not saved)
/disconnect - Close current SSH session
/status - Show connection status

**Other:**
/help - Show this help
/start - Show main menu
        """
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_builder.main_menu()
        )

# ------------------------- OUTPUT STREAMING -------------------------

def _clean_ansi_sequences(text: str) -> str:
    """Aggressively clean all ANSI escape sequences from text"""
    # Remove ALL ANSI escape sequences
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)  # SGR sequences (colors/styles)
    text = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', text)  # CSI sequences
    text = re.sub(r'\x1b\].*?[\x07\x1b\\]', '', text)  # OSC sequences
    text = re.sub(r'\x1b[PX^_].*?\x1b\\', '', text)  # DCS/SOS/PM/APC
    text = re.sub(r'\x1b[()][AB012]', '', text)  # Character set selection
    text = re.sub(r'\x1b[NO]', '', text)  # SS2/SS3

    # Remove character set selection sequences that create (B
    text = re.sub(r'\x1b\([0-9A-Z]', '', text)  # ESC ( X patterns
    text = re.sub(r'\x1b\)[0-9A-Z]', '', text)  # ESC ) X patterns

    # Multiple passes to catch nested sequences
    text = re.sub(r'\(B', '', text)  # Specifically remove (B
    text = re.sub(r'\(0', '', text)  # Specifically remove (0
    text = re.sub(r'\(A', '', text)  # Specifically remove (A
    text = re.sub(r'\([B0AB]', '', text)  # Character set designators
    text = re.sub(r'\)[B0AB]', '', text)  # Alternative form

    # Remove control characters
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)

    # Final multiple passes to ensure no (B remains
    for _ in range(3):
        text = text.replace('(B', '')

    # Debug logging and last resort fix
    if '(B' in text:
        print(f"WARNING: (B still present after cleaning, applying character-level fix")
        # Character-level removal as absolute last resort
        result = []
        i = 0
        while i < len(text):
            if i < len(text) - 1 and text[i] == '(' and text[i+1] == 'B':
                i += 2  # Skip both characters
            else:
                result.append(text[i])
                i += 1
        text = ''.join(result)

    return text

async def tail_output(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Stream SSH output to Telegram chat"""
    session = ssh_manager.get(chat_id)
    if not session:
        return

    buffer = ""
    last_send_time = asyncio.get_event_loop().time()
    min_interval = 2.0  # Increased to avoid rate limits
    last_message_id = None  # Track the last output message
    keyboard_message_id = None  # Track the keyboard message
    accumulated_output = ""  # Keep all output for editing
    tui_mode = False  # Track if we're in TUI mode
    last_was_clear = False  # Track screen clear commands
    last_content_hash = ""  # Track content to avoid unnecessary updates

    # Don't send keyboard immediately - wait for first output to establish proper order

    while session and session.is_alive():
        try:
            # Check for output
            output = session.child.read_nonblocking(size=4096, timeout=0)
            if output:
                # Debug logging to track (B sequences
                if '(B' in output:
                    print(f"DEBUG: Raw output contains (B: {output[:100]}", flush=True)

                # Auto-detect TUI apps and enable virtual terminal
                if not session.tui_mode and any(pattern in output for pattern in [
                    '\x1b[?1049h', '\x1b[?47h', 'tmux', '\x1b[2J'
                ]):
                    session.tui_mode = True
                    print(f"DEBUG: Auto-enabled TUI mode", flush=True)

                # Always use virtual terminal since TUI mode is default
                if session.virtual_terminal:
                    try:
                        print(f"DEBUG: Using virtual terminal for TUI mode", flush=True)
                        # Feed data to virtual terminal
                        screen_diff = session.virtual_terminal.feed_data(output)

                        # Render for Telegram - reduced height as requested
                        rendered_output = session.virtual_terminal.render_for_telegram(
                            screen_diff, max_lines=12  # Reduced from 20 to 12
                        )

                        if rendered_output:
                            # ULTRA-AGGRESSIVE (B cleaning - multiple passes
                            cleaned_rendered = rendered_output

                            # Pass 1: Standard ANSI cleaning
                            cleaned_rendered = _clean_ansi_sequences(cleaned_rendered)

                            # Pass 2-6: Multiple (B removal passes
                            for i in range(5):
                                cleaned_rendered = cleaned_rendered.replace('(B', '')
                                cleaned_rendered = cleaned_rendered.replace('( B', '')
                                cleaned_rendered = cleaned_rendered.replace('(B)', '')
                                cleaned_rendered = re.sub(r'\([B0AB]', '', cleaned_rendered)

                            # Pass 7: Manual character-by-character (B removal
                            result = []
                            i = 0
                            while i < len(cleaned_rendered):
                                if i < len(cleaned_rendered) - 1 and cleaned_rendered[i] == '(' and cleaned_rendered[i+1] == 'B':
                                    i += 2  # Skip (B
                                else:
                                    result.append(cleaned_rendered[i])
                                    i += 1
                            cleaned_rendered = ''.join(result)

                            # Debug check
                            if '(B' in cleaned_rendered:
                                print(f"ERROR: (B STILL SURVIVED ALL CLEANING: {cleaned_rendered[:100]}", flush=True)

                            buffer += cleaned_rendered

                            # Show app-specific help and update keyboard on first detection
                            if (screen_diff.is_major_change and
                                session.virtual_terminal.current_app != TUIAppType.UNKNOWN and
                                not hasattr(session, 'app_help_shown')):

                                help_text = session.virtual_terminal.get_app_specific_help()
                                if help_text:
                                    buffer = f"{help_text}\n\n{buffer}"
                                    session.app_help_shown = True

                                # Update keyboard to app-specific layout
                                try:
                                    app_name = session.virtual_terminal.current_app.value
                                    new_keyboard = keyboard_builder.tui_navigation(app_name)

                                    if keyboard_message_id:
                                        await context.bot.edit_message_text(
                                            chat_id=chat_id,
                                            message_id=keyboard_message_id,
                                            text=f"🖥️ **{app_name.upper()} Controls**",
                                            parse_mode=ParseMode.MARKDOWN,
                                            reply_markup=new_keyboard
                                        )
                                except Exception as keyboard_error:
                                    print(f"Keyboard update error: {keyboard_error}")

                        # Update TUI mode flag
                        tui_mode = session.virtual_terminal.in_alt_screen
                        session.tui_mode = tui_mode

                    except Exception as e:
                        print(f"Virtual terminal error: {e}")
                        # Fall back to old processing with cleaning
                        cleaned_output = _clean_ansi_sequences(output)
                        buffer += cleaned_output
                else:
                    # Legacy processing for non-TUI mode
                    original_output = output

                    # Detect TUI mode by looking for specific patterns
                    if any(pattern in original_output for pattern in [
                        '\x1b[?1049h',  # Enter alternate screen (tmux, vim, etc)
                        '\x1b[?47h',     # Alternative screen buffer
                        '\x1b[2J',       # Clear entire screen
                        '\x1b[H',        # Cursor home
                        'tmux',          # Tmux signature
                        'GNU nano',      # Nano signature
                        'VIM - Vi',      # Vim signature
                    ]):
                        tui_mode = True
                        session.tui_mode = True

                    # Check for exit from TUI mode
                    if '\x1b[?1049l' in original_output or '\x1b[?47l' in original_output:
                        tui_mode = False
                        session.tui_mode = False
                        accumulated_output = ""

                    # Check for screen clear command
                    if '\x1b[2J' in original_output or '\x1b[H\x1b[2J' in original_output:
                        last_was_clear = True
                        accumulated_output = ""
                        buffer = ""

                    # Apply comprehensive ANSI filtering for all modes
                    # Remove ALL ANSI escape sequences for clean Telegram display
                    output = re.sub(r'\x1b\[[0-9;]*m', '', output)  # SGR sequences (colors/styles)
                    output = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', output)  # CSI sequences
                    output = re.sub(r'\x1b\].*?[\x07\x1b\\]', '', output)  # OSC sequences
                    output = re.sub(r'\x1b[PX^_].*?\x1b\\', '', output)  # DCS/SOS/PM/APC
                    output = re.sub(r'\x1b[()][AB012]', '', output)  # Character set selection
                    output = re.sub(r'\x1b[NO]', '', output)  # SS2/SS3
                    output = re.sub(r'\([B0AB]', '', output)  # Character set designators like (B
                    output = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', output)  # Control chars

                    if tui_mode:
                        # For TUI mode, convert some positioning to structure
                        output = re.sub(r'\x1b\[[0-9;]*H', '\n', output)  # Cursor positioning to newline
                        output = re.sub(r'\x1b\[[0-9]*J', '\n', output)  # Screen clear to newline

                        # Show TUI warning once
                        if not hasattr(session, 'tui_warning_shown'):
                            buffer = "📺 TUI Mode Detected (Fallback)\n💡 For better experience use /webapp\n\n"
                            session.tui_warning_shown = True

                    # Apply final cleaning to all output
                    cleaned_output = _clean_ansi_sequences(output)
                    buffer += cleaned_output
                
                # Send if buffer is large enough or enough time has passed
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - last_send_time
                
                # Only send if we have waited long enough and have content
                # Also send immediately if buffer ends with common prompt patterns
                prompt_patterns = ['\n$ ', '\n# ', '\n> ', '$ ', '# ', '> ']
                has_prompt = any(buffer.endswith(p) for p in prompt_patterns)
                
                # Different send conditions for TUI vs normal mode
                should_send = False
                if tui_mode:
                    # In TUI mode, send less frequently but when we have a complete screen update
                    should_send = (len(buffer) > 2000 or time_since_last > 3.0 or last_was_clear)
                else:
                    # Normal mode - existing logic
                    should_send = (len(buffer) > 3000 or time_since_last > min_interval or has_prompt)

                if buffer and should_send:
                    # Handle output accumulation differently for TUI mode
                    if tui_mode and last_was_clear:
                        # For TUI apps after screen clear, replace accumulated output entirely
                        # Clean buffer before accumulating
                        clean_buffer = _clean_ansi_sequences(buffer)
                        clean_buffer = clean_buffer.replace('(B', '')  # Extra safety
                        accumulated_output = clean_buffer
                        last_was_clear = False
                    else:
                        # Normal append behavior - clean before accumulating
                        clean_buffer = _clean_ansi_sequences(buffer)
                        clean_buffer = clean_buffer.replace('(B', '')  # Extra safety
                        accumulated_output += clean_buffer

                    # Keep only last N characters to avoid message getting too long
                    max_display = 3500 if not tui_mode else 1200  # Much smaller for TUI to reduce height
                    if len(accumulated_output) > max_display:
                        if tui_mode:
                            # For TUI, keep more recent content (likely current screen state)
                            accumulated_output = accumulated_output[-max_display:]
                        else:
                            # For normal mode, add ellipsis
                            accumulated_output = "...\n" + accumulated_output[-max_display:]

                    # Format the message with final cleaning
                    if tui_mode:
                        # Clean up extra newlines for TUI mode
                        clean_output = re.sub(r'\n{3,}', '\n\n', accumulated_output)
                        # Final aggressive cleaning before display
                        final_clean = _clean_ansi_sequences(clean_output)
                        # Absolute last resort: manually remove (B at string level
                        while '(B' in final_clean:
                            final_clean = final_clean.replace('(B', '')
                        display_text = f"```\n{final_clean}\n```"
                    else:
                        # Final aggressive cleaning before display
                        final_clean = _clean_ansi_sequences(accumulated_output)
                        # Absolute last resort: manually remove (B at string level
                        while '(B' in final_clean:
                            final_clean = final_clean.replace('(B', '')
                        display_text = f"```\n{final_clean}\n```"
                    
                    # Final debug check before sending
                    if '(B' in display_text:
                        print(f"ERROR: (B found in display_text right before sending!", flush=True)
                        # Emergency removal
                        display_text = display_text.replace('(B', '')

                    # Check if content has actually changed to avoid unnecessary updates
                    import hashlib
                    content_hash = hashlib.md5(display_text.encode()).hexdigest()
                    if content_hash == last_content_hash and last_message_id:
                        # Content hasn't changed, skip update
                        buffer = ""
                        last_send_time = current_time
                        continue
                    last_content_hash = content_hash

                    try:
                        if last_message_id:
                            # Try to edit existing message
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=last_message_id,
                                    text=display_text,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            except Exception as e:
                                # If edit fails, send new message
                                if "message is not modified" not in str(e).lower():
                                    # Delete old message first to maintain order
                                    try:
                                        await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
                                    except:
                                        pass

                                    # Try with markdown first, fallback to plain text
                                    try:
                                        msg = await context.bot.send_message(
                                            chat_id=chat_id,
                                            text=display_text,
                                            parse_mode=ParseMode.MARKDOWN
                                        )
                                    except Exception as md_error:
                                        # Markdown failed, try plain text
                                        msg = await context.bot.send_message(
                                            chat_id=chat_id,
                                            text=display_text
                                        )
                                    last_message_id = msg.message_id
                        else:
                            # First message - send new with fallback
                            try:
                                msg = await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=display_text,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            except Exception as md_error:
                                # Markdown failed, try plain text
                                msg = await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=display_text
                                )
                            last_message_id = msg.message_id

                            # Send keyboard AFTER first terminal output to maintain proper order
                            if not keyboard_message_id:
                                try:
                                    keyboard_msg = await context.bot.send_message(
                                        chat_id=chat_id,
                                        text="🖥️ **Terminal Controls**",
                                        parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=keyboard_builder.session_actions()
                                    )
                                    keyboard_message_id = keyboard_msg.message_id
                                except:
                                    pass
                    except Exception as e:
                        # If accumulated output is too long, save as file
                        if len(accumulated_output) > config.TG_MESSAGE_LIMIT:
                            output_file = io.BytesIO(accumulated_output.encode('utf-8'))
                            output_file.name = "terminal_output.txt"
                            output_file.seek(0)
                            
                            try:
                                await context.bot.send_document(
                                    chat_id=chat_id,
                                    document=output_file,
                                    caption="📄 Terminal output (saved to file)",
                                    filename=f"terminal_output_{datetime.now().strftime('%H%M%S')}.txt"
                                )
                                # Clear accumulated output after saving to file
                                accumulated_output = ""
                                last_message_id = None
                            except:
                                pass
                    
                    buffer = ""
                    last_send_time = current_time
        except:
            pass
        
        await asyncio.sleep(config.POLL_INTERVAL)
    
    # Send any remaining buffer
    if buffer:
        accumulated_output += buffer
        try:
            if last_message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_message_id,
                    text=f"```\n{accumulated_output}\n```",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"```\n{accumulated_output}\n```",
                    parse_mode=ParseMode.MARKDOWN
                )
        except:
            pass
    
    # Clean up keyboard
    if keyboard_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=keyboard_message_id)
        except:
            pass

    # Clean up database session when SSH connection ends
    session = ssh_manager.get(chat_id)
    if session and session.session_id:
        try:
            db_session = db.get_session_by_id(session.session_id)
            if db_session:
                db.delete_session(db_session.user_id)
        except Exception as e:
            logger.error(f"Error cleaning up database session: {e}")

# ------------------------- WEBAPP COMMAND -------------------------

async def webapp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Launch the terminal web app"""
    if not await ensure_registered(update):
        return
    
    if not config.WEBAPP_URL:
        await update.message.reply_text(
            "Web terminal is not configured.\n"
            "Please set WEBAPP_URL in your environment."
        )
        return
    
    # Create webapp button
    webapp_url = f"{config.WEBAPP_URL}?user_id={update.effective_user.id}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🌐 Open Web Terminal",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])
    
    await update.message.reply_text(
        "Click below to open the full terminal interface:",
        reply_markup=keyboard
    )

# ------------------------- MAIN -------------------------

def main():
    """Main function"""
    # Create application
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # Add connection wizard FIRST (higher priority)
    wizard = ConnectionWizard(db, encryption)
    application.add_handler(wizard.get_handler())
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    # Note: /add is handled by the ConversationHandler wizard above
    application.add_handler(CommandHandler("connections", connections_cmd))
    application.add_handler(CommandHandler("connect", connect_cmd))
    application.add_handler(CommandHandler("quick", quick_connect_cmd))
    application.add_handler(CommandHandler("disconnect", disconnect_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("delete", delete_connection_cmd))
    application.add_handler(CommandHandler("setdefault", setdefault_cmd))
    application.add_handler(CommandHandler("webapp", webapp_cmd))
    
    # Add callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Add message handler LAST (lowest priority)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    # Auto-reconnect to active sessions after restart
    async def auto_reconnect():
        """Automatically reconnect to active SSH sessions after bot restart"""
        try:
            active_sessions = db.get_all_active_sessions()
            logger.info(f"Found {len(active_sessions)} active sessions to restore")

            for db_session in active_sessions:
                if not db_session.chat_id or not db_session.connection_id:
                    continue

                try:
                    # Get connection details
                    connection = db.get_connection_by_id(db_session.user_id, db_session.connection_id)
                    if not connection:
                        logger.warning(f"Connection not found for session {db_session.session_id}")
                        continue

                    # Attempt to reconnect
                    logger.info(f"Auto-reconnecting to {connection.name} for user {db_session.user_id}")
                    session = ssh_manager.connect_saved(db_session.user_id, db_session.chat_id, connection.name)

                    if session.connected:
                        # Start output streaming
                        session.task = asyncio.create_task(tail_output(db_session.chat_id, application))

                        # Send notification
                        await application.bot.send_message(
                            chat_id=db_session.chat_id,
                            text=f"🔄 **Auto-reconnected to {connection.name}**\n"
                                f"Your session has been restored after bot restart.\n\n"
                                f"Connected to: {connection.username}@{connection.host}:{connection.port}",
                            parse_mode=ParseMode.MARKDOWN
                        )

                        logger.info(f"Successfully auto-reconnected session {db_session.session_id}")
                    else:
                        logger.warning(f"Failed to auto-reconnect session {db_session.session_id}")

                except Exception as e:
                    logger.error(f"Error auto-reconnecting session {db_session.session_id}: {e}")
                    # Clean up failed session
                    db.delete_session(db_session.user_id)

        except Exception as e:
            logger.error(f"Error during auto-reconnection: {e}")

    # Schedule auto-reconnect to run after bot starts
    application.job_queue.run_once(
        lambda context: asyncio.create_task(auto_reconnect()),
        when=2  # Wait 2 seconds after startup
    )

    # Start bot
    logger.info("Starting SSH Terminal Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
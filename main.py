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
            keyboard = keyboard_builder.session_actions()
            await update.effective_message.reply_text(
                f"✅ Connected to **{connection_name}**\n"
                f"({connection.username}@{connection.host}:{connection.port})",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
            # Start output streaming task
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
    host = ssh_manager.disconnect(chat_id)
    
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
    
    elif data == "session_disconnect":
        host = ssh_manager.disconnect(chat_id)
        if host:
            await query.edit_message_text(f"✅ Disconnected from {host}")
        else:
            await query.edit_message_text("No active connection.")
    
    elif data == "session_tui":
        # Switch to TUI mode with control buttons
        session = ssh_manager.get(chat_id)
        if session:
            keyboard = keyboard_builder.tui_navigation()
            await query.edit_message_text(
                "🖥️ **TUI Mode Active**\n\n"
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
                keyboard = keyboard_builder.tui_navigation()
                text = "🖥️ **TUI Navigation Mode**"
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
                keyboard = keyboard_builder.tui_navigation()
                text = "🖥️ **TUI Mode**"
            
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

async def tail_output(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Stream SSH output to Telegram chat"""
    session = ssh_manager.get(chat_id)
    if not session:
        return
    
    buffer = ""
    last_send_time = asyncio.get_event_loop().time()
    min_interval = 1.0  # Reduced interval for more responsive output
    last_message_id = None  # Track the last output message
    keyboard_message_id = None  # Track the keyboard message
    accumulated_output = ""  # Keep all output for editing
    
    # Send initial keyboard
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
    
    while session and session.is_alive():
        try:
            # Check for output
            output = session.child.read_nonblocking(size=4096, timeout=0)
            if output:
                # Filter out common ANSI escape sequences and control codes
                # Note: Complex TUI apps like tmux/vim work better in web terminal
                original_output = output
                
                # Comprehensive ANSI filtering
                # Remove all CSI sequences (the most common ANSI escape sequences)
                output = re.sub(r'\x1b\[[^m]*m', '', output)  # Remove all SGR sequences
                output = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', output)  # Remove all CSI sequences
                output = re.sub(r'\x1b\].*?\x07', '', output)  # OSC sequences (window title, etc)
                output = re.sub(r'\x1b[PX^_].*?\x1b\\', '', output)  # DCS/SOS/PM/APC sequences
                output = re.sub(r'\x1b\[[\?!][0-9;]*[a-zA-Z]', '', output)  # Private sequences
                output = re.sub(r'\x1b[NO]', '', output)  # SS2/SS3
                output = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', output)  # Control chars except \t, \n, \r
                
                # Detect if this looks like a TUI app (lots of escape codes)
                escape_ratio = len(original_output) - len(output)
                if escape_ratio > len(output) * 0.5 and not hasattr(session, 'tui_warning_shown'):
                    # Suggest web terminal for better experience (only once per session)
                    buffer += "\n💡 Tip: Complex TUI apps work better in the web terminal. Use /webapp command.\n"
                    session.tui_warning_shown = True
                
                buffer += output
                
                # Send if buffer is large enough or enough time has passed
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - last_send_time
                
                # Only send if we have waited long enough and have content
                # Also send immediately if buffer ends with common prompt patterns
                prompt_patterns = ['\n$ ', '\n# ', '\n> ', '$ ', '# ', '> ']
                has_prompt = any(buffer.endswith(p) for p in prompt_patterns)
                
                if buffer and (len(buffer) > 3000 or time_since_last > min_interval or has_prompt):
                    # Add to accumulated output
                    accumulated_output += buffer
                    
                    # Keep only last N characters to avoid message getting too long
                    max_display = 3500
                    if len(accumulated_output) > max_display:
                        # Keep the last portion and add ellipsis
                        accumulated_output = "...\n" + accumulated_output[-max_display:]
                    
                    # Format the message
                    display_text = f"```\n{accumulated_output}\n```"
                    
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
                                    msg = await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=display_text,
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                    last_message_id = msg.message_id
                        else:
                            # First message - send new
                            msg = await context.bot.send_message(
                                chat_id=chat_id,
                                text=display_text,
                                parse_mode=ParseMode.MARKDOWN
                            )
                            last_message_id = msg.message_id
                        
                        # Move keyboard to bottom if needed
                        if keyboard_message_id:
                            try:
                                await context.bot.delete_message(chat_id=chat_id, message_id=keyboard_message_id)
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
    
    # Start bot
    logger.info("Starting SSH Terminal Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
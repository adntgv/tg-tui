"""
Interactive Shell Telegram Bot
--------------------------------
A Telegram bot that can start an interactive shell (PTY) per chat and relay stdin/stdout
between Telegram and the shell. Supports true back-and-forth interaction with CLI tools.

⚠️ SECURITY: Running a shell via a bot is dangerous. Read the SECURITY section below and
restrict access before deploying.

Requires: python-telegram-bot >= 21, pexpect

pip install python-telegram-bot==21.6 pexpect

Run with:  TELEGRAM_TOKEN=... python bot.py
"""

import asyncio
import os
import textwrap
from dataclasses import dataclass, field
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import pexpect

# ------------------------- CONFIG -------------------------
# Allow only these Telegram user IDs to use the bot (REQUIRED!)
AUTHORIZED_USER_IDS = {
    # e.g. 123456789,
    289310951
}

# Optional: default shell and working directory
DEFAULT_SHELL = os.environ.get("SHELL", "/bin/bash")
DEFAULT_CWD = os.getcwd()

# Telegram message size hard limit
TG_LIMIT = 4096

# How often to poll the PTY for output (seconds)
POLL_INTERVAL = 0.2

# ------------------------- STATE -------------------------
@dataclass
class Session:
    child: pexpect.spawn
    buffer: str = ""
    task: Optional[asyncio.Task] = None

    def send(self, data: str):
        # Ensure one newline per message unless user explicitly sends raw
        self.child.send(data)

    def is_alive(self) -> bool:
        return self.child.isalive()


class ShellManager:
    def __init__(self):
        self.sessions: Dict[int, Session] = {}

    def get(self, chat_id: int) -> Optional[Session]:
        return self.sessions.get(chat_id)

    def start(self, chat_id: int, shell: str = DEFAULT_SHELL, cwd: str = DEFAULT_CWD) -> Session:
        if chat_id in self.sessions and self.sessions[chat_id].is_alive():
            raise RuntimeError("A shell is already running in this chat. Use /stop to terminate.")
        # Start an interactive PTY-managed process via pexpect
        child = pexpect.spawn(shell, encoding="utf-8", timeout=None, cwd=cwd)
        sess = Session(child=child)
        self.sessions[chat_id] = sess
        return sess

    def stop(self, chat_id: int):
        sess = self.sessions.get(chat_id)
        if not sess:
            return
        try:
            if sess.child.isalive():
                # Send exit politely, then force-kill if needed
                try:
                    sess.child.sendline("exit")
                    sess.child.expect(pexpect.EOF, timeout=1)
                except Exception:
                    sess.child.close(force=True)
        finally:
            # Cancel output task if running
            if sess.task and not sess.task.done():
                sess.task.cancel()
            self.sessions.pop(chat_id, None)


shells = ShellManager()

# ------------------------- HELPERS -------------------------
async def send_chunked(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE):
    # Telegram messages max ~4096 chars. Split on newline boundaries when possible.
    if not text:
        return
    start = 0
    while start < len(text):
        end = min(start + TG_LIMIT, len(text))
        # try to break at last newline
        nl = text.rfind("\n", start, end)
        if nl != -1 and nl > start:
            piece = text[start:nl]
            start = nl + 1
        else:
            piece = text[start:end]
            start = end
        await context.bot.send_message(chat_id=chat_id, text=f"```\n{piece}\n```", parse_mode=ParseMode.MARKDOWN_V2)


def escape_markdown_v2(s: str) -> str:
    # Minimal escaping for code blocks content handled separately
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        s = s.replace(ch, f"\\{ch}")
    return s


async def tail_output(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    sess = shells.get(chat_id)
    if not sess:
        return
    child = sess.child
    # Continuously read whatever is available without blocking.
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            if not child.isalive():
                await context.bot.send_message(chat_id=chat_id, text="Shell exited.")
                shells.stop(chat_id)
                return
            # Use non-blocking read by checking child.before after expect with short timeout
            if child.exitstatus is None:
                # Read all available without waiting
                try:
                    data = child.read_nonblocking(size=4096, timeout=0)
                except pexpect.exceptions.TIMEOUT:
                    data = ""
                except pexpect.exceptions.EOF:
                    data = child.before or ""
                if data:
                    await send_chunked(chat_id, data, context)
        except asyncio.CancelledError:
            return
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Output loop error: {escape_markdown_v2(str(e))}")
            return


# ------------------------- COMMANDS -------------------------
async def ensure_auth(update: Update) -> bool:
    user = update.effective_user
    return user and user.id in AUTHORIZED_USER_IDS


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized. Add your user id to AUTHORIZED_USER_IDS.")
    m = textwrap.dedent(
        f"""
        Hi {update.effective_user.first_name or ''}!\n\n"""
    ).strip()
    await update.effective_message.reply_text(m + HELP_TEXT)


HELP_TEXT = textwrap.dedent(
    """

Commands:
  /startsh            Start an interactive shell in this chat
  /tui start          Start TUI mode with inline keyboard
  /webapp             Open full terminal web app
  /stop               Stop the running shell
  /send <text>        Send raw text (no added newline) to the shell
  Type anything else  Sends the line to the shell with a newline

Notes:
- This opens a PTY, so interactive programs (ssh, python REPL, top, etc.) work.
- Full-screen TUIs (vim, top) may be hard to use over Telegram due to screen updates.
- For passwords/prompts, just type the input as a message.
- Web app provides the best terminal experience!
"""
)


async def startsh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized.")
    chat_id = update.effective_chat.id
    try:
        sess = shells.start(chat_id)
    except RuntimeError as e:
        return await update.effective_message.reply_text(str(e))

    await update.effective_message.reply_text(f"Started shell: {DEFAULT_SHELL} in {DEFAULT_CWD}")
    # Kick off a background task to stream output
    sess.task = asyncio.create_task(tail_output(chat_id, context))


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized.")
    chat_id = update.effective_chat.id
    
    # Stop TUI session if active
    tui_sess = tui_sessions.get(chat_id)
    if tui_sess:
        tui_sess.stop()
        tui_sessions.pop(chat_id, None)
        await update.effective_message.reply_text("Stopped TUI session.")
        return
    
    # Stop regular shell
    shells.stop(chat_id)
    await update.effective_message.reply_text("Stopped shell.")


async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized.")
    chat_id = update.effective_chat.id
    
    # Check if TUI mode is active first
    tui_sess = tui_sessions.get(chat_id)
    if tui_sess and tui_sess.child.isalive():
        raw = update.effective_message.text.partition(" ")[2]
        if raw == "":
            return await update.effective_message.reply_text("Usage: /send <text>")
        tui_sess.child.send(raw)
        # Recreate the TUI message to keep it at the bottom
        await tui_sess.recreate_message()
        return
    
    # Otherwise check regular shell
    sess = shells.get(chat_id)
    if not sess or not sess.is_alive():
        return await update.effective_message.reply_text("No shell is running. Use /startsh or /tui start.")
    # Raw send, no newline appended. Use with care for partial inputs.
    raw = update.effective_message.text.partition(" ")[2]
    if raw == "":
        return await update.effective_message.reply_text("Usage: /send <text>")
    sess.send(raw)


async def line_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Default path: send the message with a trailing newline to the shell
    if not await ensure_auth(update):
        return  # Ignore silently
    chat_id = update.effective_chat.id
    
    # Check if TUI mode is active first
    tui_sess = tui_sessions.get(chat_id)
    if tui_sess and tui_sess.child.isalive():
        # Send to TUI session
        line = update.effective_message.text
        tui_sess.child.send(line + "\n")
        # Recreate the TUI message to keep it at the bottom
        await tui_sess.recreate_message()
        return
    
    # Otherwise check regular shell
    sess = shells.get(chat_id)
    if not sess or not sess.is_alive():
        return await update.effective_message.reply_text("No shell is running. Use /startsh or /tui start.")
    line = update.effective_message.text
    # Append newline for typical CLI behavior
    sess.send(line + "\n")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        raise context.error
    except Exception as e:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {escape_markdown_v2(str(e))}")
        else:
            print("Unhandled error:", e)


# ------------------------- OPTIONAL: TUI SNAPSHOT MODE -------------------------
# This mode keeps a fixed-size terminal grid (cols x rows) in memory using a VT100
# emulator and periodically EDITS a single Telegram message to reflect the current
# screen. This makes TUIs like `top` usable as a live "image" of text.
#
# Install extra dep:  pip install pyte

import html
import re
try:
    import pyte  # type: ignore
    HAS_PYTE = True
except Exception:
    HAS_PYTE = False

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

def _html_pre(s: str) -> str:
    # Render inside <pre> to avoid Telegram MarkdownV2 escaping pain
    return f"<pre>{html.escape(s)}</pre>"

@dataclass
class TuiSession:
    child: pexpect.spawn
    screen: "pyte.Screen"
    stream: "pyte.Stream"
    msg_id: Optional[int] = None
    cols: int = 80
    rows: int = 30
    read_task: Optional[asyncio.Task] = None
    render_task: Optional[asyncio.Task] = None
    last_frame: str = ""
    context: Optional[ContextTypes.DEFAULT_TYPE] = None
    chat_id: Optional[int] = None
    keyboard_msg_id: Optional[int] = None
    recreating: bool = False
    keyboard_mode: str = "navigation"

    def stop(self):
        if self.read_task and not self.read_task.done():
            self.read_task.cancel()
        if self.render_task and not self.render_task.done():
            self.render_task.cancel()
        if self.child.isalive():
            try:
                self.child.close(force=True)
            except Exception:
                pass
    
    async def recreate_message(self):
        """Delete the old message and create a new one with current screen content"""
        # Prevent concurrent recreations
        if self.recreating:
            return
        
        if self.msg_id and self.context and self.chat_id:
            self.recreating = True
            try:
                # Delete old message
                try:
                    await self.context.bot.delete_message(chat_id=self.chat_id, message_id=self.msg_id)
                except Exception:
                    pass  # Message might already be deleted
                
                # Delete old keyboard if exists
                if self.keyboard_msg_id:
                    try:
                        await self.context.bot.delete_message(chat_id=self.chat_id, message_id=self.keyboard_msg_id)
                    except Exception:
                        pass
                
                # Get current screen content
                lines = list(self.screen.display)
                padded = [(ln + " " * self.cols)[:self.cols] for ln in lines[:self.rows]]
                while len(padded) < self.rows:
                    padded.append(" " * self.cols)
                frame = "\n".join(padded)
                
                # Create new terminal message
                try:
                    msg = await self.context.bot.send_message(
                        chat_id=self.chat_id,
                        text=_html_pre(frame),
                        parse_mode=ParseMode.HTML
                    )
                    self.msg_id = msg.message_id
                    self.last_frame = frame
                    
                    # Create new keyboard message with current mode
                    keyboard_msg = await self.context.bot.send_message(
                        chat_id=self.chat_id,
                        text="📱 Terminal Controls:",
                        reply_markup=get_terminal_keyboard(self.keyboard_mode)
                    )
                    self.keyboard_msg_id = keyboard_msg.message_id
                except Exception:
                    pass
            finally:
                self.recreating = False


tui_sessions: Dict[int, TuiSession] = {}


def _pick_safe_geometry(cols: int, rows: int) -> tuple[int, int]:
    # Telegram displays messages best with ~60-70 chars width on most devices
    # Mobile displays typically show ~50-60 chars comfortably
    # Desktop can handle more but we optimize for mobile
    
    # First, cap width for better display on all devices
    max_width_mobile = 60  # Optimal for mobile
    max_width_desktop = 72  # Still readable on desktop
    
    # Use a reasonable default that works well on both
    if cols > max_width_desktop:
        cols = max_width_mobile  # Default to mobile-friendly width
    
    # Keep message under ~3900 chars (Telegram hard limit ~4096). Each row has a newline.
    # Budget check: rows * (cols + 1) <= 3900
    while rows * (cols + 1) > 3900:
        if cols > 50:
            cols -= 2
        elif rows > 15:
            rows -= 1
        else:
            break
    
    # Ensure minimum usable size
    cols = max(40, cols)  # Minimum 40 chars wide
    rows = max(10, rows)  # Minimum 10 rows
    
    return cols, rows


async def tui_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized.")
    if not HAS_PYTE:
        return await update.effective_message.reply_text("Please install 'pyte' to use TUI snapshot mode: pip install pyte")

    args = (update.effective_message.text or "").split()
    sub = args[1] if len(args) > 1 else "help"

    if sub in {"help", "?"}:
        return await update.effective_message.reply_text(
            "Usage: /tui start [COLSxROWS] | /tui size COLSxROWS | /tui stop\n"
            "Examples: /tui start 80x40, /tui size 72x30\n"
            "Tips: Use /send for raw text (no newline) and /key for arrows/esc.")

    chat_id = update.effective_chat.id

    if sub == "start":
        # Parse geometry - default to mobile-friendly size
        cols, rows = 60, 24  # Good default for most devices
        if len(args) >= 3 and "x" in args[2].lower():
            try:
                c, r = args[2].lower().split("x", 1)
                cols, rows = int(c), int(r)
            except Exception:
                pass
        cols, rows = _pick_safe_geometry(cols, rows)

        # If already running, stop previous
        if chat_id in tui_sessions:
            tui_sessions[chat_id].stop()
            tui_sessions.pop(chat_id, None)

        # Spawn shell and set winsize
        child = pexpect.spawn(DEFAULT_SHELL, encoding="utf-8", timeout=None, cwd=DEFAULT_CWD)
        # Set PTY size
        try:
            child.setwinsize(rows, cols)
        except Exception:
            pass

        screen = pyte.Screen(cols, rows)
        stream = pyte.Stream(screen)
        sess = TuiSession(child=child, screen=screen, stream=stream, cols=cols, rows=rows, 
                         context=context, chat_id=chat_id)
        tui_sessions[chat_id] = sess

        # Post placeholder message
        msg = await update.effective_message.reply_html(_html_pre(f"TUI started {cols}x{rows}…"))
        sess.msg_id = msg.message_id
        
        # Send keyboard controls
        keyboard_msg = await update.effective_message.reply_text(
            "📱 Terminal Controls:",
            reply_markup=get_terminal_keyboard()
        )
        sess.keyboard_msg_id = keyboard_msg.message_id

        async def reader():
            # Continuously feed PTY output into the VT screen buffer
            while True:
                await asyncio.sleep(0.05)
                if not child.isalive():
                    break
                try:
                    data = child.read_nonblocking(65536, timeout=0)
                except pexpect.exceptions.TIMEOUT:
                    data = ""
                except pexpect.exceptions.EOF:
                    break
                if data:
                    try:
                        stream.feed(data)
                    except Exception:
                        # As a fallback, strip ANSI and write raw
                        stream.feed(ANSI.sub("", data))

        async def renderer():
            # Periodically render the screen buffer into one fixed-size frame
            while True:
                await asyncio.sleep(0.5)
                if not child.isalive():
                    break
                
                # Skip if currently recreating messages
                if sess.recreating:
                    continue
                
                # pyte.Screen.display already returns a list of visual lines
                lines = list(screen.display)
                # Ensure fixed geometry
                padded = [ (ln + " " * sess.cols)[:sess.cols] for ln in lines[:sess.rows] ]
                while len(padded) < sess.rows:
                    padded.append(" " * sess.cols)
                frame = "\n".join(padded)
                
                if frame != sess.last_frame and sess.msg_id is not None and not sess.recreating:
                    sess.last_frame = frame
                    try:
                        # Try to edit existing message first
                        await context.bot.edit_message_text(
                            chat_id=chat_id, 
                            message_id=sess.msg_id,
                            text=_html_pre(frame), 
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as e:
                        # Only create new if message was deleted, not for other errors
                        if "message to edit not found" in str(e).lower() or "message identifier is not specified" in str(e).lower():
                            if not sess.recreating:  # Double-check to prevent race condition
                                try:
                                    msg = await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=_html_pre(frame),
                                        parse_mode=ParseMode.HTML
                                    )
                                    sess.msg_id = msg.message_id
                                except Exception:
                                    pass

        sess.read_task = asyncio.create_task(reader())
        sess.render_task = asyncio.create_task(renderer())
        return

    if sub == "size":
        geom = args[2] if len(args) >= 3 else ""
        if chat_id not in tui_sessions:
            return await update.effective_message.reply_text("No TUI running. Use /tui start first.")
        try:
            c, r = geom.lower().split("x", 1)
            cols, rows = int(c), int(r)
        except Exception:
            return await update.effective_message.reply_text("Usage: /tui size COLSxROWS")
        cols, rows = _pick_safe_geometry(cols, rows)
        sess = tui_sessions[chat_id]
        sess.cols, sess.rows = cols, rows
        try:
            sess.child.setwinsize(rows, cols)
        except Exception:
            pass
        # Force re-render next tick
        sess.last_frame = ""
        return await update.effective_message.reply_text(f"Resized to {cols}x{rows}.")

    if sub == "stop":
        sess = tui_sessions.pop(chat_id, None)
        if not sess:
            return await update.effective_message.reply_text("No TUI running.")
        sess.stop()
        return await update.effective_message.reply_text("TUI stopped.")

    return await update.effective_message.reply_text("Unknown subcommand. Use /tui help")


# Virtual keys for TUIs - extended set for inline keyboard support
KEYMAP = {
    # Arrow keys
    "up": "\x1b[A", "down": "\x1b[B", "left": "\x1b[D", "right": "\x1b[C",
    # Special keys
    "esc": "\x1b", "tab": "\t", "shift+tab": "\x1b[Z", "enter": "\r", "backspace": "\x7f", "delete": "\x1b[3~",
    "space": " ",
    # Function keys
    "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS",
    "f5": "\x1b[15~", "f6": "\x1b[17~", "f7": "\x1b[18~", "f8": "\x1b[19~",
    # Common ctrl combos
    "ctrl+c": "\x03", "ctrl+z": "\x1a", "ctrl+d": "\x04", "ctrl+l": "\x0c",
    "ctrl+a": "\x01", "ctrl+e": "\x05", "ctrl+w": "\x17", "ctrl+u": "\x15",
    "ctrl+k": "\x0b", "ctrl+y": "\x19", "ctrl+r": "\x12", "ctrl+s": "\x13",
    # Page navigation
    "home": "\x1b[H", "end": "\x1b[F", "pgup": "\x1b[5~", "pgdn": "\x1b[6~",
}

def get_terminal_keyboard(mode="navigation"):
    """Generate inline keyboard for terminal control"""
    
    if mode == "navigation":
        keyboard = [
            [
                InlineKeyboardButton("⬆️", callback_data="key:up"),
                InlineKeyboardButton("Home", callback_data="key:home"),
                InlineKeyboardButton("PgUp", callback_data="key:pgup"),
            ],
            [
                InlineKeyboardButton("⬅️", callback_data="key:left"),
                InlineKeyboardButton("⬇️", callback_data="key:down"),
                InlineKeyboardButton("➡️", callback_data="key:right"),
            ],
            [
                InlineKeyboardButton("Tab →", callback_data="key:tab"),
                InlineKeyboardButton("⇧Tab ←", callback_data="key:shift+tab"),
                InlineKeyboardButton("Enter ⏎", callback_data="key:enter"),
            ],
            [
                InlineKeyboardButton("End", callback_data="key:end"),
                InlineKeyboardButton("PgDn", callback_data="key:pgdn"),
                InlineKeyboardButton("Esc", callback_data="key:esc"),
            ],
            [
                InlineKeyboardButton("🎛️ Ctrl", callback_data="kbd:ctrl"),
                InlineKeyboardButton("⚡ Special", callback_data="kbd:special"),
                InlineKeyboardButton("🔧 F-Keys", callback_data="kbd:function"),
            ],
            [
                InlineKeyboardButton("🖥️ Open Web Terminal", callback_data="webapp:launch"),
            ]
        ]
    
    elif mode == "ctrl":
        keyboard = [
            [
                InlineKeyboardButton("Ctrl+C (Cancel)", callback_data="key:ctrl+c"),
                InlineKeyboardButton("Ctrl+D (EOF)", callback_data="key:ctrl+d"),
            ],
            [
                InlineKeyboardButton("Ctrl+Z (Suspend)", callback_data="key:ctrl+z"),
                InlineKeyboardButton("Ctrl+L (Clear)", callback_data="key:ctrl+l"),
            ],
            [
                InlineKeyboardButton("Ctrl+A (Home)", callback_data="key:ctrl+a"),
                InlineKeyboardButton("Ctrl+E (End)", callback_data="key:ctrl+e"),
            ],
            [
                InlineKeyboardButton("Ctrl+W (Del Word)", callback_data="key:ctrl+w"),
                InlineKeyboardButton("Ctrl+U (Del Line)", callback_data="key:ctrl+u"),
            ],
            [
                InlineKeyboardButton("Ctrl+K (Kill Line)", callback_data="key:ctrl+k"),
                InlineKeyboardButton("Ctrl+R (Search)", callback_data="key:ctrl+r"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="kbd:navigation"),
            ],
            [
                InlineKeyboardButton("🖥️ Open Web Terminal", callback_data="webapp:launch"),
            ]
        ]
    
    elif mode == "special":
        keyboard = [
            [
                InlineKeyboardButton("Enter ⏎", callback_data="key:enter"),
                InlineKeyboardButton("Space", callback_data="key:space"),
                InlineKeyboardButton("Esc", callback_data="key:esc"),
            ],
            [
                InlineKeyboardButton("Backspace ⌫", callback_data="key:backspace"),
                InlineKeyboardButton("Delete", callback_data="key:delete"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="kbd:navigation"),
            ],
            [
                InlineKeyboardButton("🖥️ Open Web Terminal", callback_data="webapp:launch"),
            ]
        ]
    
    elif mode == "function":
        keyboard = [
            [
                InlineKeyboardButton("F1", callback_data="key:f1"),
                InlineKeyboardButton("F2", callback_data="key:f2"),
                InlineKeyboardButton("F3", callback_data="key:f3"),
                InlineKeyboardButton("F4", callback_data="key:f4"),
            ],
            [
                InlineKeyboardButton("F5", callback_data="key:f5"),
                InlineKeyboardButton("F6", callback_data="key:f6"),
                InlineKeyboardButton("F7", callback_data="key:f7"),
                InlineKeyboardButton("F8", callback_data="key:f8"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="kbd:navigation"),
            ],
            [
                InlineKeyboardButton("🖥️ Open Web Terminal", callback_data="webapp:launch"),
            ]
        ]
    
    return InlineKeyboardMarkup(keyboard)

async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_auth(update):
        return
    chat_id = update.effective_chat.id
    sess = tui_sessions.get(chat_id)
    if not sess or not sess.child.isalive():
        return await update.effective_message.reply_text("No TUI running.")
    args = (update.effective_message.text or "").split()
    if len(args) < 2:
        return await update.effective_message.reply_text("Usage: /key <up|down|left|right|esc|tab|enter|ctrl+x>")
    spec = args[1].lower()
    if spec.startswith("ctrl+") and len(spec) == 6:
        ch = spec[-1]
        code = chr(ord(ch) & 0x1f)
        sess.child.send(code)
        # Recreate the TUI message to keep it at the bottom
        await sess.recreate_message()
        return
    code = KEYMAP.get(spec)
    if not code:
        return await update.effective_message.reply_text("Unknown key.")
    sess.child.send(code)
    # Recreate the TUI message to keep it at the bottom
    await sess.recreate_message()


async def keyboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    data = query.data
    
    # Check TUI session exists
    sess = tui_sessions.get(chat_id)
    if not sess or not sess.child.isalive():
        await query.edit_message_text("No TUI session active. Use /tui start")
        return
    
    if data.startswith("key:"):
        # Send key to terminal
        key_name = data[4:]
        key_code = KEYMAP.get(key_name, "")
        
        if key_code:
            sess.child.send(key_code)
            # Don't recreate messages for keyboard input
            # Let the renderer handle terminal updates naturally
    
    elif data.startswith("kbd:"):
        # Switch keyboard layout
        mode = data[4:]
        sess.keyboard_mode = mode  # Save current mode
        try:
            await query.edit_message_reply_markup(
                reply_markup=get_terminal_keyboard(mode)
            )
        except Exception:
            # If message is too old to edit, send a new keyboard
            try:
                await query.message.delete()
                keyboard_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="📱 Terminal Controls:",
                    reply_markup=get_terminal_keyboard(mode)
                )
                sess.keyboard_msg_id = keyboard_msg.message_id
            except Exception:
                pass
    
    elif data == "webapp:launch":
        # Launch web app from inline button
        webapp_url = os.environ.get("WEBAPP_URL", "https://your-domain.com/webapp")
        
        keyboard = [[
            InlineKeyboardButton(
                text="🖥️ Open Terminal Web App",
                web_app=WebAppInfo(url=webapp_url)
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="Click the button below to open the terminal in a full-screen web app:\n\n"
                 "This provides a better terminal experience with:\n"
                 "• Full keyboard support\n"
                 "• Better copy/paste\n"
                 "• Proper terminal rendering\n"
                 "• Touch-friendly controls",
            reply_markup=reply_markup
        )


async def webapp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Launch the terminal web app"""
    if not await ensure_auth(update):
        return await update.effective_message.reply_text("Unauthorized.")
    
    # Web app URL - you'll need to host this somewhere accessible
    # For local testing, you can use ngrok or similar tunneling service
    webapp_url = os.environ.get("WEBAPP_URL", "https://your-domain.com/webapp")
    
    keyboard = [[
        InlineKeyboardButton(
            text="🖥️ Open Terminal Web App",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        "Click the button below to open the terminal in a full-screen web app:\n\n"
        "This provides a better terminal experience with:\n"
        "• Full keyboard support\n"
        "• Better copy/paste\n"
        "• Proper terminal rendering\n"
        "• Touch-friendly controls",
        reply_markup=reply_markup
    )


# ------------------------- MAIN -------------------------
async def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit("Please set TELEGRAM_TOKEN environment variable.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("startsh", startsh_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("send", send_cmd))

    # Any non-command text goes to the shell as a line
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), line_handler))

    # TUI snapshot mode handlers
    app.add_handler(CommandHandler("tui", tui_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    
    # Web app handler
    app.add_handler(CommandHandler("webapp", webapp_cmd))
    
    # Inline keyboard handler
    app.add_handler(CallbackQueryHandler(keyboard_callback))

    app.add_error_handler(error_handler)

    print("Bot up. Press Ctrl+C to stop.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Keep the bot running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

# ------------------------- SECURITY (READ ME) -------------------------
# 1) RESTRICT ACCESS: Populate AUTHORIZED_USER_IDS with your personal Telegram user ID(s).
#    You can get your user ID via @userinfobot or similar. Never deploy without this.
# 2) LEAST PRIVILEGE: Run the bot inside a Docker container or sandbox user with limited perms.
#    Example (rootless):
#      docker run --rm -it --name tgsh \
#        -e TELEGRAM_TOKEN=... \
#        --user 1000:1000 \
#        -v /safe/workdir:/work -w /work \
#        --pids-limit=200 --memory=512m --cpus=0.5 \
#        ghcr.io/yourimage/python:3.11-slim python bot.py
# 3) NETWORK & FS GUARDRAILS: Mount only what you need. Consider outbound firewall rules.
# 4) AUDIT LOGS: Telegram stores history; avoid handling secrets here.
# 5) FULL-SCREEN APPS: ncurses/TTY UIs spam updates; basic interaction works, but the UX is rough.
# 6) MULTI-SESSION: This sample uses one PTY per chat. Extend ShellManager for per-user or multi-PTY.


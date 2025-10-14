"""
Virtual Terminal Emulator for TUI applications in Telegram
Uses pyte for proper terminal emulation with screen buffer management
"""

import re
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum

try:
    import pyte
    HAS_PYTE = True
except ImportError:
    HAS_PYTE = False

class TUIAppType(Enum):
    UNKNOWN = "unknown"
    TMUX = "tmux"
    VIM = "vim"
    NANO = "nano"
    HTOP = "htop"
    TOP = "top"
    LESS = "less"
    MORE = "more"
    MAN = "man"

@dataclass
class ScreenDiff:
    """Represents changes between two screen states"""
    changed_lines: Dict[int, str]  # line_number -> new_content
    cursor_moved: bool
    cursor_pos: Tuple[int, int]  # (row, col)
    is_major_change: bool  # True for screen clears, app switches

class VirtualTerminal:
    """Virtual terminal emulator using pyte for proper TUI support"""

    def __init__(self, rows: int = 24, cols: int = 80):
        self.rows = rows
        self.cols = cols
        self.has_pyte = HAS_PYTE

        if self.has_pyte:
            self.screen = pyte.Screen(cols, rows)
            self.stream = pyte.Stream(self.screen)
            self.screen.reset()
        else:
            self.screen = None
            self.stream = None

        # State tracking
        self.last_screen_lines = []
        self.current_app = TUIAppType.UNKNOWN
        self.in_alt_screen = False
        self.last_cursor_pos = (0, 0)

        # Performance tracking
        self.update_count = 0
        self.last_major_change = 0

    def detect_application(self, data: str) -> TUIAppType:
        """Detect which TUI application is running based on output patterns"""
        data_lower = data.lower()

        # Specific application signatures
        if any(sig in data for sig in ['tmux', 'session', 'window', 'pane']):
            return TUIAppType.TMUX
        elif any(sig in data_lower for sig in ['vim', 'vi improved', 'nvim']):
            return TUIAppType.VIM
        elif 'gnu nano' in data_lower:
            return TUIAppType.NANO
        elif any(sig in data_lower for sig in ['htop', 'processes', 'cpu usage']):
            return TUIAppType.HTOP
        elif 'top -' in data_lower or 'load average:' in data_lower:
            return TUIAppType.TOP
        elif any(sig in data_lower for sig in ['(end)', 'lines ', '--more--']):
            return TUIAppType.LESS
        elif any(sig in data_lower for sig in ['manual page', 'man page']):
            return TUIAppType.MAN

        return TUIAppType.UNKNOWN

    def feed_data(self, data: str) -> ScreenDiff:
        """Feed terminal data and return screen differences"""
        if not self.has_pyte:
            return self._fallback_processing(data)

        # Detect application type
        detected_app = self.detect_application(data)
        if detected_app != TUIAppType.UNKNOWN:
            self.current_app = detected_app

        # Check for alternate screen buffer
        if '\x1b[?1049h' in data or '\x1b[?47h' in data:
            self.in_alt_screen = True
            self.last_major_change = self.update_count
        elif '\x1b[?1049l' in data or '\x1b[?47l' in data:
            self.in_alt_screen = False
            self.last_major_change = self.update_count

        # Process through pyte
        try:
            self.stream.feed(data)
            return self._compute_diff()
        except Exception as e:
            # Fallback on pyte errors
            print(f"Pyte processing error: {e}")
            return self._fallback_processing(data)

    def _compute_diff(self) -> ScreenDiff:
        """Compute differences between current and last screen state"""
        current_lines = []
        changed_lines = {}

        # Get current screen content
        for i in range(self.screen.lines):
            line_chars = []
            for j in range(self.screen.columns):
                char = self.screen.buffer[i][j]
                if hasattr(char, 'data'):
                    line_chars.append(char.data)
                else:
                    line_chars.append(' ')
            current_lines.append(''.join(line_chars).rstrip())

        # Compare with last screen state
        for i, (current_line, last_line) in enumerate(zip(current_lines, self.last_screen_lines)):
            if current_line != last_line:
                changed_lines[i] = current_line

        # Handle new lines (screen grew)
        for i in range(len(self.last_screen_lines), len(current_lines)):
            changed_lines[i] = current_lines[i]

        # Check cursor movement
        cursor_pos = (self.screen.cursor.y, self.screen.cursor.x)
        cursor_moved = cursor_pos != self.last_cursor_pos

        # Determine if this is a major change
        is_major_change = (
            len(changed_lines) > self.rows // 2 or  # More than half screen changed
            self.update_count - self.last_major_change < 5  # Recent app switch
        )

        # Update state
        self.last_screen_lines = current_lines.copy()
        self.last_cursor_pos = cursor_pos
        self.update_count += 1

        return ScreenDiff(
            changed_lines=changed_lines,
            cursor_moved=cursor_moved,
            cursor_pos=cursor_pos,
            is_major_change=is_major_change
        )

    def _fallback_processing(self, data: str) -> ScreenDiff:
        """Fallback processing when pyte is not available"""
        # Simple line-based processing
        lines = data.split('\n')
        changed_lines = {i: line for i, line in enumerate(lines) if line.strip()}

        return ScreenDiff(
            changed_lines=changed_lines,
            cursor_moved=False,
            cursor_pos=(0, 0),
            is_major_change=len(changed_lines) > 5
        )

    def render_for_telegram(self, diff: ScreenDiff, max_lines: int = 20) -> str:
        """Render screen differences optimized for Telegram display"""
        if not diff.changed_lines:
            return ""

        # For major changes, show full relevant screen
        if diff.is_major_change:
            return self._render_full_screen(max_lines)
        else:
            return self._render_differential(diff, max_lines)

    def _render_full_screen(self, max_lines: int) -> str:
        """Render the full current screen state"""
        if not self.has_pyte or not self.last_screen_lines:
            return ""

        # Get non-empty lines from the bottom up (like a terminal)
        relevant_lines = []
        for line in reversed(self.last_screen_lines):
            if line.strip() or len(relevant_lines) < 5:  # Keep some context
                relevant_lines.append(line)
            if len(relevant_lines) >= max_lines:
                break

        # Reverse back to correct order
        relevant_lines.reverse()

        # Clean up and format
        output = '\n'.join(relevant_lines)
        output = self._clean_output_for_telegram(output)

        # Add application-specific markers
        if self.current_app != TUIAppType.UNKNOWN:
            app_emoji = self._get_app_emoji(self.current_app)
            output = f"{app_emoji} {self.current_app.value.upper()}\n{output}"

        return output

    def _render_differential(self, diff: ScreenDiff, max_lines: int) -> str:
        """Render only the changed parts of the screen"""
        if not diff.changed_lines:
            return ""

        # Sort changed lines by line number
        sorted_changes = sorted(diff.changed_lines.items())

        # Group consecutive line changes
        groups = []
        current_group = []
        last_line_num = -2

        for line_num, content in sorted_changes:
            if line_num == last_line_num + 1:
                current_group.append((line_num, content))
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [(line_num, content)]
            last_line_num = line_num

        if current_group:
            groups.append(current_group)

        # Render groups
        output_parts = []
        for group in groups[:3]:  # Limit to 3 groups to avoid spam
            group_lines = [content for _, content in group]
            group_text = '\n'.join(group_lines)
            group_text = self._clean_output_for_telegram(group_text)
            if group_text.strip():
                output_parts.append(group_text)

        return '\n\n'.join(output_parts)

    def _clean_output_for_telegram(self, text: str) -> str:
        """Clean output for better display in Telegram"""
        # ULTRA-AGGRESSIVE CLEANING

        # First pass: explicit (B removal everywhere
        text = text.replace('(B', '')

        # Remove ALL remaining ANSI escape sequences
        # Remove SGR (color/style) sequences
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)

        # Remove CSI sequences (cursor control, etc.)
        text = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', text)

        # Remove OSC sequences (title, etc.)
        text = re.sub(r'\x1b\].*?[\x07\x1b\\]', '', text)

        # Remove DCS, SOS, PM, APC sequences
        text = re.sub(r'\x1b[PX^_].*?\x1b\\', '', text)

        # Remove other escape sequences
        text = re.sub(r'\x1b[()][AB012]', '', text)  # Character set selection like (B
        text = re.sub(r'\x1b[NO]', '', text)  # SS2/SS3

        # Remove VT100 character set sequences that show as (B
        text = re.sub(r'\([B0AB]', '', text)  # Character set designators
        text = re.sub(r'\x0E|\x0F', '', text)  # Shift In/Shift Out

        # Additional patterns that might produce (B
        text = re.sub(r'\x1b\(B', '', text)  # ESC ( B pattern
        text = re.sub(r'\x1b\)B', '', text)  # ESC ) B pattern
        text = re.sub(r'\(B\)', '', text)  # (B) pattern

        # Remove control characters but keep printable whitespace
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)

        # Final pass: remove any remaining (B that might have survived
        text = text.replace('(B', '')

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

        # Convert Unicode box drawing to ASCII for better mobile display
        replacements = {
            '─': '-', '│': '|', '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '├': '+', '┤': '+', '┬': '+', '┴': '+', '┼': '+',
            '═': '=', '║': '|', '╔': '+', '╗': '+', '╚': '+', '╝': '+',
            '┃': '|', '━': '-', '┏': '+', '┓': '+', '┗': '+', '┛': '+',
        }

        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)

        # Absolute final pass to guarantee no (B remains
        text = text.replace('(B', '')

        # Debug logging
        if '(B' in text:
            print(f"WARNING: (B STILL IN TERMINAL EMULATOR OUTPUT: {text[:100]}")

        return text

    def _get_app_emoji(self, app_type: TUIAppType) -> str:
        """Get emoji for specific TUI application"""
        emoji_map = {
            TUIAppType.TMUX: '🖥️',
            TUIAppType.VIM: '📝',
            TUIAppType.NANO: '✏️',
            TUIAppType.HTOP: '📊',
            TUIAppType.TOP: '⚡',
            TUIAppType.LESS: '📄',
            TUIAppType.MORE: '📖',
            TUIAppType.MAN: '📚',
            TUIAppType.UNKNOWN: '💻'
        }
        return emoji_map.get(app_type, '💻')

    def get_app_specific_help(self) -> Optional[str]:
        """Get help text specific to the current application"""
        help_map = {
            TUIAppType.TMUX: (
                "🖥️ **Tmux Controls:**\n"
                "• `Ctrl+B` then `C` - New window\n"
                "• `Ctrl+B` then `\"` - Split horizontal\n"
                "• `Ctrl+B` then `%` - Split vertical\n"
                "• `Ctrl+B` then arrow keys - Navigate panes\n"
                "• `Ctrl+B` then `D` - Detach session"
            ),
            TUIAppType.VIM: (
                "📝 **Vim Controls:**\n"
                "• `i` - Insert mode\n"
                "• `Esc` - Normal mode\n"
                "• `:w` - Save file\n"
                "• `:q` - Quit\n"
                "• `:wq` - Save and quit\n"
                "• `/text` - Search"
            ),
            TUIAppType.NANO: (
                "✏️ **Nano Controls:**\n"
                "• `Ctrl+O` - Save file\n"
                "• `Ctrl+X` - Exit\n"
                "• `Ctrl+W` - Search\n"
                "• `Ctrl+K` - Cut line\n"
                "• `Ctrl+U` - Paste"
            ),
            TUIAppType.HTOP: (
                "📊 **Htop Controls:**\n"
                "• `F9/k` - Kill process\n"
                "• `F5/t` - Tree view\n"
                "• `F6/</>` - Sort by column\n"
                "• `Space` - Tag process\n"
                "• `q` - Quit"
            )
        }
        return help_map.get(self.current_app)

    def resize(self, rows: int, cols: int):
        """Resize the virtual terminal"""
        if self.has_pyte and self.screen:
            self.screen.resize(rows, cols)
        self.rows = rows
        self.cols = cols

    def clear(self):
        """Clear the virtual terminal"""
        if self.has_pyte and self.screen:
            self.screen.reset()
        self.last_screen_lines = []
        self.current_app = TUIAppType.UNKNOWN
        self.in_alt_screen = False
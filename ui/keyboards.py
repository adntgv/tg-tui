"""
Inline keyboard builders for the bot
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional

class KeyboardBuilder:
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Build main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📡 Connect", callback_data="menu_connect"),
                InlineKeyboardButton("➕ Add Connection", callback_data="menu_add"),
            ],
            [
                InlineKeyboardButton("📋 My Connections", callback_data="menu_list"),
                InlineKeyboardButton("⚡ Quick Connect", callback_data="menu_quick"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
                InlineKeyboardButton("❓ Help", callback_data="menu_help"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def connections_list(connections: List[dict], prefix: str = "connect") -> InlineKeyboardMarkup:
        """Build connections list keyboard"""
        keyboard = []
        
        for conn in connections:
            # Show default marker
            name = conn['name']
            if conn.get('is_default'):
                name = f"⭐ {name}"
            
            # Format connection info
            info = f"{conn['username']}@{conn['host']}:{conn['port']}"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} ({info})",
                    callback_data=f"{prefix}:{conn['id']}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def connection_actions(connection_name: str) -> InlineKeyboardMarkup:
        """Build connection actions keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🔗 Connect", callback_data=f"connect_now:{connection_name}"),
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_conn:{connection_name}"),
            ],
            [
                InlineKeyboardButton("⭐ Set as Default", callback_data=f"set_default:{connection_name}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_conn:{connection_name}"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="menu_list")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def auth_type_selection() -> InlineKeyboardMarkup:
        """Build auth type selection keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🔑 Password", callback_data="auth_password"),
                InlineKeyboardButton("🔐 SSH Key", callback_data="auth_key"),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_delete(connection_name: str) -> InlineKeyboardMarkup:
        """Build delete confirmation keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete:{connection_name}"),
                InlineKeyboardButton("❌ Cancel", callback_data="menu_list"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_actions() -> InlineKeyboardMarkup:
        """Build session actions keyboard for active connection - now with direct TUI controls"""
        # TUI navigation controls are now top level, removed unnecessary buttons
        keyboard = [
            [
                InlineKeyboardButton("↑", callback_data="key:up"),
                InlineKeyboardButton("Tab →", callback_data="key:tab"),
                InlineKeyboardButton("Enter ⏎", callback_data="key:enter"),
            ],
            [
                InlineKeyboardButton("←", callback_data="key:left"),
                InlineKeyboardButton("↓", callback_data="key:down"),
                InlineKeyboardButton("→", callback_data="key:right"),
            ],
            [
                InlineKeyboardButton("Esc", callback_data="key:esc"),
                InlineKeyboardButton("Ctrl", callback_data="kbd:ctrl"),
                InlineKeyboardButton("Space", callback_data="key:space"),
            ],
            [
                InlineKeyboardButton("🔌 Disconnect", callback_data="session_disconnect"),
                InlineKeyboardButton("🌐 Web Terminal", callback_data="session_webapp"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_only() -> InlineKeyboardMarkup:
        """Build cancel-only keyboard"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tui_navigation(app_type: str = "general") -> InlineKeyboardMarkup:
        """Build TUI navigation keyboard with app-specific shortcuts"""
        # Simplified navigation keys - removed Home, End, PgUp, PgDn
        keyboard = [
            [
                InlineKeyboardButton("↑", callback_data="key:up"),
                InlineKeyboardButton("Tab →", callback_data="key:tab"),
                InlineKeyboardButton("Enter ⏎", callback_data="key:enter"),
            ],
            [
                InlineKeyboardButton("←", callback_data="key:left"),
                InlineKeyboardButton("↓", callback_data="key:down"),
                InlineKeyboardButton("→", callback_data="key:right"),
            ],
            [
                InlineKeyboardButton("Esc", callback_data="key:esc"),
                InlineKeyboardButton("⇧Tab ←", callback_data="key:shift+tab"),
                InlineKeyboardButton("Space", callback_data="key:space"),
            ]
        ]

        # Add app-specific shortcuts
        if app_type.lower() == "tmux":
            keyboard.extend([
                [
                    InlineKeyboardButton("^B C", callback_data="key:ctrl+b,c"),  # New window
                    InlineKeyboardButton("^B \"", callback_data="key:ctrl+b,\""),  # Split horizontal
                    InlineKeyboardButton("^B %", callback_data="key:ctrl+b,%"),  # Split vertical
                ],
                [
                    InlineKeyboardButton("^B D", callback_data="key:ctrl+b,d"),  # Detach
                    InlineKeyboardButton("^B ?", callback_data="key:ctrl+b,?"),  # Help
                ]
            ])
        elif app_type.lower() == "vim":
            keyboard.extend([
                [
                    InlineKeyboardButton("i", callback_data="key:i"),  # Insert mode
                    InlineKeyboardButton(":w", callback_data="key::w"),  # Save
                    InlineKeyboardButton(":q", callback_data="key::q"),  # Quit
                ],
                [
                    InlineKeyboardButton(":wq", callback_data="key::wq"),  # Save & quit
                    InlineKeyboardButton("/", callback_data="key:/"),  # Search
                ]
            ])
        elif app_type.lower() == "nano":
            keyboard.extend([
                [
                    InlineKeyboardButton("^O", callback_data="key:ctrl+o"),  # Save
                    InlineKeyboardButton("^X", callback_data="key:ctrl+x"),  # Exit
                    InlineKeyboardButton("^W", callback_data="key:ctrl+w"),  # Search
                ]
            ])
        elif app_type.lower() == "htop":
            keyboard.extend([
                [
                    InlineKeyboardButton("F9", callback_data="key:f9"),  # Kill
                    InlineKeyboardButton("F5", callback_data="key:f5"),  # Tree
                    InlineKeyboardButton("q", callback_data="key:q"),  # Quit
                ]
            ])
        else:
            # General TUI shortcuts - simplified
            keyboard.extend([
                [
                    InlineKeyboardButton("🎛️ Ctrl", callback_data="kbd:ctrl"),
                    InlineKeyboardButton("🔧 F-Keys", callback_data="kbd:function"),
                ]
            ])

        # Always add disconnect and webapp options
        keyboard.extend([
            [
                InlineKeyboardButton("🔌 Disconnect", callback_data="session_disconnect"),
                InlineKeyboardButton("🌐 Web Terminal", callback_data="webapp:launch"),
            ]
        ])

        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tui_ctrl() -> InlineKeyboardMarkup:
        """Build Ctrl key combinations keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("^A", callback_data="key:ctrl+a"),
                InlineKeyboardButton("^B", callback_data="key:ctrl+b"),
                InlineKeyboardButton("^C", callback_data="key:ctrl+c"),
            ],
            [
                InlineKeyboardButton("^D", callback_data="key:ctrl+d"),
                InlineKeyboardButton("^E", callback_data="key:ctrl+e"),
                InlineKeyboardButton("^F", callback_data="key:ctrl+f"),
            ],
            [
                InlineKeyboardButton("^K", callback_data="key:ctrl+k"),
                InlineKeyboardButton("^L", callback_data="key:ctrl+l"),
                InlineKeyboardButton("^R", callback_data="key:ctrl+r"),
            ],
            [
                InlineKeyboardButton("^U", callback_data="key:ctrl+u"),
                InlineKeyboardButton("^W", callback_data="key:ctrl+w"),
                InlineKeyboardButton("^Z", callback_data="key:ctrl+z"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="kbd:navigation"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tui_special() -> InlineKeyboardMarkup:
        """Build special keys keyboard"""
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
                InlineKeyboardButton("🌐 Web Terminal", callback_data="webapp:launch"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tui_function() -> InlineKeyboardMarkup:
        """Build function keys keyboard"""
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
                InlineKeyboardButton("F9", callback_data="key:f9"),
                InlineKeyboardButton("F10", callback_data="key:f10"),
                InlineKeyboardButton("F11", callback_data="key:f11"),
                InlineKeyboardButton("F12", callback_data="key:f12"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="kbd:navigation"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
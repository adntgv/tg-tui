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
        """Build session actions keyboard for active connection"""
        keyboard = [
            [
                InlineKeyboardButton("📝 Send Command", callback_data="session_send"),
                InlineKeyboardButton("🔄 Clear Screen", callback_data="session_clear"),
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data="session_status"),
                InlineKeyboardButton("🔌 Disconnect", callback_data="session_disconnect"),
            ],
            [
                InlineKeyboardButton("🖥️ TUI Mode", callback_data="session_tui"),
                InlineKeyboardButton("🌐 Web Terminal", callback_data="session_webapp"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_only() -> InlineKeyboardMarkup:
        """Build cancel-only keyboard"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]
        return InlineKeyboardMarkup(keyboard)
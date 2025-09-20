"""
Conversation wizards for multi-step processes
"""
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from database import DatabaseManager
from security import EncryptionManager
from ssh import ConnectionManager

# Conversation states
(NAME, HOST, PORT, USERNAME, AUTH_TYPE, 
 PASSWORD, SSH_KEY, KEY_PASSPHRASE, CONFIRM) = range(9)

class ConnectionWizard:
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager):
        self.db = db
        self.encryption = encryption
        self.connection_mgr = ConnectionManager(db, encryption)
    
    async def start_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the add connection wizard"""
        user = update.effective_user
        
        # Register user if needed
        self.db.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        await update.message.reply_text(
            "Let's add a new SSH connection!\n\n"
            "Please enter a name for this connection (e.g., 'My VPS', 'Work Server'):"
        )
        
        # Initialize user data
        context.user_data['connection'] = {}
        
        return NAME
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get connection name"""
        name = update.message.text.strip()
        
        if not name:
            await update.message.reply_text("Please enter a valid name:")
            return NAME
        
        # Check if name already exists
        existing = self.db.get_connection(update.effective_user.id, name)
        if existing:
            await update.message.reply_text(
                f"A connection named '{name}' already exists.\n"
                "Please choose a different name:"
            )
            return NAME
        
        context.user_data['connection']['name'] = name
        await update.message.reply_text(
            f"Great! Connection will be named: {name}\n\n"
            "Now enter the host address (domain or IP):"
        )
        
        return HOST
    
    async def get_host(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get host address"""
        host = update.message.text.strip()
        
        if not host:
            await update.message.reply_text("Please enter a valid host address:")
            return HOST
        
        context.user_data['connection']['host'] = host
        await update.message.reply_text(
            f"Host: {host}\n\n"
            f"Enter the SSH port (or press /skip for default 22):"
        )
        
        return PORT
    
    async def get_port(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get SSH port"""
        text = update.message.text.strip()
        
        if text == '/skip':
            port = 22
        else:
            try:
                port = int(text)
                if port < 1 or port > 65535:
                    raise ValueError()
            except ValueError:
                await update.message.reply_text(
                    "Please enter a valid port number (1-65535) or /skip for default:"
                )
                return PORT
        
        context.user_data['connection']['port'] = port
        await update.message.reply_text(
            f"Port: {port}\n\n"
            "Enter the SSH username:"
        )
        
        return USERNAME
    
    async def get_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get SSH username"""
        username = update.message.text.strip()
        
        if not username:
            await update.message.reply_text("Please enter a valid username:")
            return USERNAME
        
        context.user_data['connection']['username'] = username
        
        from ui.keyboards import KeyboardBuilder
        keyboard = KeyboardBuilder.auth_type_selection()
        
        await update.message.reply_text(
            f"Username: {username}\n\n"
            "Choose authentication type:",
            reply_markup=keyboard
        )
        
        return AUTH_TYPE
    
    async def get_auth_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get authentication type"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_add':
            await query.edit_message_text("Connection addition cancelled.")
            return ConversationHandler.END
        
        auth_type = 'password' if query.data == 'auth_password' else 'key'
        context.user_data['connection']['auth_type'] = auth_type
        
        if auth_type == 'password':
            await query.edit_message_text(
                "Please enter the SSH password:\n"
                "⚠️ The password will be encrypted and stored securely."
            )
            return PASSWORD
        else:
            await query.edit_message_text(
                "Please send the SSH private key as text or as a file:\n"
                "⚠️ The key will be encrypted and stored securely."
            )
            return SSH_KEY
    
    async def get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get SSH password"""
        password = update.message.text
        
        if not password:
            await update.message.reply_text("Please enter the password:")
            return PASSWORD
        
        context.user_data['connection']['password'] = password
        
        # Delete the password message for security
        try:
            await update.message.delete()
        except:
            pass
        
        await self.save_connection(update, context)
        return ConversationHandler.END
    
    async def get_ssh_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get SSH private key"""
        key_content = None
        
        # Check if it's a file
        if update.message.document:
            file = await update.message.document.get_file()
            key_content = (await file.download_as_bytearray()).decode('utf-8')
        elif update.message.text:
            key_content = update.message.text
        
        if not key_content:
            await update.message.reply_text("Please send the SSH key as text or file:")
            return SSH_KEY
        
        context.user_data['connection']['private_key'] = key_content
        
        # Delete the message with the key for security
        try:
            await update.message.delete()
        except:
            pass
        
        await update.message.reply_text(
            "Key received.\n\n"
            "Does this key require a passphrase? Send the passphrase or /skip:"
        )
        
        return KEY_PASSPHRASE
    
    async def get_key_passphrase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get key passphrase if needed"""
        text = update.message.text
        
        if text != '/skip':
            context.user_data['connection']['key_passphrase'] = text
            # Delete the passphrase message for security
            try:
                await update.message.delete()
            except:
                pass
        
        await self.save_connection(update, context)
        return ConversationHandler.END
    
    async def save_connection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save the connection to database"""
        user_id = update.effective_user.id
        conn = context.user_data['connection']
        
        try:
            saved = self.connection_mgr.add_connection(
                user_id=user_id,
                name=conn['name'],
                host=conn['host'],
                port=conn.get('port', 22),
                username=conn['username'],
                auth_type=conn['auth_type'],
                password=conn.get('password'),
                private_key=conn.get('private_key'),
                key_passphrase=conn.get('key_passphrase')
            )
            
            await update.effective_message.reply_text(
                f"✅ Connection '{conn['name']}' has been saved successfully!\n\n"
                f"You can now connect using: /connect {conn['name']}"
            )
        except Exception as e:
            await update.effective_message.reply_text(
                f"❌ Failed to save connection: {str(e)}"
            )
        
        # Clear user data
        context.user_data.clear()
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the wizard"""
        context.user_data.clear()
        await update.message.reply_text("Connection addition cancelled.")
        return ConversationHandler.END
    
    def get_handler(self) -> ConversationHandler:
        """Get the conversation handler for this wizard"""
        return ConversationHandler(
            entry_points=[CommandHandler('add_connection', self.start_add)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_name)],
                HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_host)],
                PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_port)],
                USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_username)],
                AUTH_TYPE: [CallbackQueryHandler(self.get_auth_type)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)],
                SSH_KEY: [
                    MessageHandler(filters.Document.ALL, self.get_ssh_key),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_ssh_key)
                ],
                KEY_PASSPHRASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_key_passphrase)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
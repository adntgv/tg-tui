"""
Encryption utilities for storing sensitive data
"""
import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class EncryptionManager:
    def __init__(self, base_key: str = None):
        """Initialize encryption manager with base key"""
        if base_key is None:
            base_key = os.environ.get('ENCRYPTION_KEY', 'default_key_change_me!')
        
        self.base_key = base_key.encode()
    
    def _generate_user_key(self, user_id: int) -> bytes:
        """Generate a unique encryption key for each user"""
        # Combine base key with user ID for unique key per user
        salt = f"telegram_ssh_{user_id}".encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.base_key))
        return key
    
    def encrypt(self, data: str, user_id: int) -> str:
        """Encrypt data for a specific user"""
        if not data:
            return None
        
        user_key = self._generate_user_key(user_id)
        fernet = Fernet(user_key)
        encrypted = fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str, user_id: int) -> Optional[str]:
        """Decrypt data for a specific user"""
        if not encrypted_data:
            return None
        
        try:
            user_key = self._generate_user_key(user_id)
            fernet = Fernet(user_key)
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    def encrypt_ssh_key(self, key_content: str, user_id: int) -> str:
        """Encrypt SSH private key"""
        # SSH keys can be large, so we handle them specially
        return self.encrypt(key_content, user_id)
    
    def decrypt_ssh_key(self, encrypted_key: str, user_id: int) -> Optional[str]:
        """Decrypt SSH private key"""
        return self.decrypt(encrypted_key, user_id)
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a random session ID"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')[:32]
"""
SSH connection management with database integration
"""
import os
import tempfile
from typing import Optional, Tuple
from database import DatabaseManager, SSHConnection
from security import EncryptionManager

class ConnectionManager:
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager):
        """Initialize connection manager"""
        self.db = db
        self.encryption = encryption
    
    def add_connection(self, user_id: int, name: str, host: str, port: int, 
                      username: str, auth_type: str, password: str = None, 
                      private_key: str = None, key_passphrase: str = None) -> SSHConnection:
        """Add a new SSH connection with encrypted credentials"""
        
        # Encrypt sensitive data
        encrypted_password = None
        encrypted_key = None
        encrypted_passphrase = None
        
        if auth_type == 'password' and password:
            encrypted_password = self.encryption.encrypt(password, user_id)
        elif auth_type == 'key' and private_key:
            encrypted_key = self.encryption.encrypt_ssh_key(private_key, user_id)
            if key_passphrase:
                encrypted_passphrase = self.encryption.encrypt(key_passphrase, user_id)
        
        # Save to database
        return self.db.add_connection(
            user_id=user_id,
            name=name,
            host=host,
            port=port,
            username=username,
            auth_type=auth_type,
            encrypted_password=encrypted_password,
            encrypted_private_key=encrypted_key,
            key_passphrase=encrypted_passphrase
        )
    
    def get_connection_credentials(self, user_id: int, connection_name: str) -> Optional[dict]:
        """Get decrypted connection credentials"""
        connection = self.db.get_connection(user_id, connection_name)
        if not connection:
            return None
        
        result = {
            'id': connection.id,
            'name': connection.name,
            'host': connection.host,
            'port': connection.port,
            'username': connection.username,
            'auth_type': connection.auth_type,
        }
        
        # Decrypt credentials based on auth type
        if connection.auth_type == 'password' and connection.encrypted_password:
            result['password'] = self.encryption.decrypt(connection.encrypted_password, user_id)
        elif connection.auth_type == 'key' and connection.encrypted_private_key:
            result['private_key'] = self.encryption.decrypt_ssh_key(connection.encrypted_private_key, user_id)
            if connection.key_passphrase:
                result['key_passphrase'] = self.encryption.decrypt(connection.key_passphrase, user_id)
        
        return result
    
    def prepare_ssh_key(self, user_id: int, connection_name: str) -> Optional[str]:
        """Prepare SSH key for use (write to temporary file)"""
        credentials = self.get_connection_credentials(user_id, connection_name)
        if not credentials or credentials['auth_type'] != 'key':
            return None
        
        private_key = credentials.get('private_key')
        if not private_key:
            return None
        
        # Create temporary file for SSH key
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(private_key)
            f.flush()
            os.chmod(f.name, 0o600)  # Set proper permissions
            return f.name
    
    def format_ssh_command(self, user_id: int, connection_name: str) -> Optional[Tuple[str, Optional[str]]]:
        """Format SSH command with credentials"""
        credentials = self.get_connection_credentials(user_id, connection_name)
        if not credentials:
            return None, None
        
        base_cmd = f"ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60"
        
        if credentials['auth_type'] == 'key':
            # Prepare key file
            key_file = self.prepare_ssh_key(user_id, connection_name)
            if key_file:
                cmd = f"{base_cmd} -i {key_file} -p {credentials['port']} {credentials['username']}@{credentials['host']}"
                return cmd, key_file
        else:
            # Password authentication
            cmd = f"{base_cmd} -p {credentials['port']} {credentials['username']}@{credentials['host']}"
            return cmd, None
        
        return None, None
    
    def list_connections(self, user_id: int) -> list:
        """List all connections for a user"""
        connections = self.db.get_connections(user_id)
        return [conn.to_dict() for conn in connections]
    
    def delete_connection(self, user_id: int, connection_name: str) -> bool:
        """Delete a connection"""
        return self.db.delete_connection(user_id, connection_name)
    
    def set_default(self, user_id: int, connection_name: str) -> bool:
        """Set a connection as default"""
        return self.db.set_default_connection(user_id, connection_name)
"""
Enhanced SSH session manager with database integration
"""
import os
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass, field
import pexpect
from database import DatabaseManager
from security import EncryptionManager
from .connections import ConnectionManager

@dataclass
class SSHSession:
    child: pexpect.spawn
    host: str
    port: int
    username: str
    connection_id: Optional[int] = None
    session_id: Optional[str] = None  # Database session ID
    buffer: str = ""
    task: Optional[asyncio.Task] = None
    connected: bool = False
    temp_key_file: Optional[str] = None  # For cleaning up temp SSH keys
    
    def send(self, data: str):
        self.child.send(data)
    
    def is_alive(self) -> bool:
        return self.child.isalive() and self.connected
    
    def cleanup(self):
        """Clean up resources"""
        if self.temp_key_file and os.path.exists(self.temp_key_file):
            try:
                os.remove(self.temp_key_file)
            except:
                pass

class EnhancedSSHManager:
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager):
        """Initialize enhanced SSH manager"""
        self.sessions: Dict[int, SSHSession] = {}
        self.db = db
        self.encryption = encryption
        self.connection_mgr = ConnectionManager(db, encryption)
    
    def get(self, chat_id: int) -> Optional[SSHSession]:
        """Get session for a chat"""
        return self.sessions.get(chat_id)
    
    def connect_saved(self, user_id: int, chat_id: int, connection_name: str) -> SSHSession:
        """Connect using saved connection"""
        if chat_id in self.sessions and self.sessions[chat_id].is_alive():
            raise RuntimeError("An SSH session is already active. Use /disconnect to close it.")
        
        # Get connection details
        connection = self.db.get_connection(user_id, connection_name)
        if not connection:
            raise RuntimeError(f"Connection '{connection_name}' not found")
        
        # Get SSH command
        ssh_cmd, temp_key_file = self.connection_mgr.format_ssh_command(user_id, connection_name)
        if not ssh_cmd:
            raise RuntimeError("Failed to prepare SSH command")
        
        # Start SSH process
        child = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=30)
        sess = SSHSession(
            child=child,
            host=connection.host,
            port=connection.port,
            username=connection.username,
            connection_id=connection.id,
            temp_key_file=temp_key_file
        )
        self.sessions[chat_id] = sess
        
        # Get credentials for authentication
        credentials = self.connection_mgr.get_connection_credentials(user_id, connection_name)
        
        # Handle initial connection
        try:
            index = child.expect([
                "password:",  # Password prompt
                "passphrase",  # SSH key passphrase
                r"\$",  # Shell prompt (successful key auth)
                r"#",   # Root shell prompt
                r">",   # Another possible prompt
                pexpect.EOF,
                pexpect.TIMEOUT
            ], timeout=10)
            
            if index == 0:  # Password needed
                if credentials['auth_type'] == 'password' and credentials.get('password'):
                    child.sendline(credentials['password'])
                    # Wait for prompt after password
                    child.expect([r"\$", r"#", r">"], timeout=10)
                    sess.connected = True
                else:
                    sess.connected = False
            elif index == 1:  # Key passphrase needed
                if credentials.get('key_passphrase'):
                    child.sendline(credentials['key_passphrase'])
                    child.expect([r"\$", r"#", r">"], timeout=10)
                    sess.connected = True
                else:
                    sess.connected = False
            elif index in [2, 3, 4]:  # Connected successfully
                sess.connected = True
            else:
                raise RuntimeError("SSH connection failed or timed out")
            
            # Update last used timestamp
            if sess.connected:
                self.db.update_connection_last_used(connection.id)
                
                # Create active session in database
                session_id = self.encryption.generate_session_id()
                sess.session_id = session_id
                self.db.create_session(user_id, session_id, connection.id, chat_id)
                
        except Exception as e:
            sess.cleanup()
            self.sessions.pop(chat_id, None)
            raise RuntimeError(f"Connection failed: {str(e)}")
        
        return sess
    
    def connect_manual(self, chat_id: int, host: str, port: int = 22, username: str = "root") -> SSHSession:
        """Connect manually (without saved credentials)"""
        if chat_id in self.sessions and self.sessions[chat_id].is_alive():
            raise RuntimeError("An SSH session is already active. Use /disconnect to close it.")
        
        ssh_cmd = f"ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60 -p {port} {username}@{host}"
        
        child = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=30)
        sess = SSHSession(child=child, host=host, port=port, username=username)
        self.sessions[chat_id] = sess
        
        # Handle initial connection
        try:
            index = child.expect([
                "password:",  # Password prompt
                "passphrase",  # SSH key passphrase
                r"\$",  # Shell prompt
                r"#",   # Root shell prompt
                r">",   # Another prompt
                pexpect.EOF,
                pexpect.TIMEOUT
            ], timeout=10)
            
            if index in [0, 1]:  # Auth needed
                sess.connected = False
            elif index in [2, 3, 4]:  # Connected
                sess.connected = True
            else:
                raise RuntimeError("SSH connection failed or timed out")
                
        except Exception as e:
            self.sessions.pop(chat_id, None)
            raise RuntimeError(f"Connection failed: {str(e)}")
        
        return sess
    
    def disconnect(self, chat_id: int) -> Optional[str]:
        """Disconnect SSH session"""
        sess = self.sessions.get(chat_id)
        if not sess:
            return None
        
        host = sess.host
        
        if sess.task:
            sess.task.cancel()
        
        sess.child.terminate()
        sess.cleanup()  # Clean up temp files
        
        self.sessions.pop(chat_id, None)
        
        # Remove from active sessions in database
        # Note: We need user_id here, which should be passed or stored
        # For now, we'll clean up based on connection_id
        # This is a simplified version
        
        return host
    
    def send_to_session(self, chat_id: int, data: str) -> bool:
        """Send data to an active session"""
        sess = self.get(chat_id)
        if sess and sess.is_alive():
            sess.send(data)
            return True
        return False
    
    def cleanup_user_sessions(self, user_id: int):
        """Clean up all sessions for a user"""
        # This would need to track user_id to chat_id mapping
        # For now, this is a placeholder
        pass
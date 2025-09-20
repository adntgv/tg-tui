"""
Database models for SSH connection management
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)  # Telegram user ID
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    connections = relationship("SSHConnection", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("ActiveSession", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class SSHConnection(Base):
    __tablename__ = 'ssh_connections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    name = Column(String(100), nullable=False)  # Connection nickname
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)
    auth_type = Column(String(20), nullable=False)  # 'password' or 'key'
    encrypted_password = Column(Text, nullable=True)  # Encrypted password
    encrypted_private_key = Column(Text, nullable=True)  # Encrypted SSH private key
    key_passphrase = Column(Text, nullable=True)  # Encrypted key passphrase
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_default = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="connections")
    
    def __repr__(self):
        return f"<SSHConnection(name={self.name}, host={self.host}, user={self.username})>"
    
    def to_dict(self):
        """Convert to dictionary for display (without sensitive data)"""
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'auth_type': self.auth_type,
            'is_default': self.is_default,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


class ActiveSession(Base):
    __tablename__ = 'active_sessions'
    
    session_id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    connection_id = Column(Integer, ForeignKey('ssh_connections.id'), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<ActiveSession(session_id={self.session_id}, user_id={self.user_id})>"


class AuditLog(Base):
    __tablename__ = 'audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AuditLog(user_id={self.user_id}, action={self.action}, timestamp={self.timestamp})>"
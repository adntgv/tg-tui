"""
Database manager for handling all database operations
"""
import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from .models import Base, User, SSHConnection, ActiveSession, AuditLog

class DatabaseManager:
    def __init__(self, database_url: str = None):
        """Initialize database connection"""
        if database_url is None:
            database_url = os.environ.get('DATABASE_URL', 'sqlite:///ssh_connections.db')
        
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    # User Management
    def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
        """Get existing user or create new one"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.commit()
                self.add_audit_log(user_id, "user_registered", f"New user registered: {username}")
            else:
                # Update last seen
                user.last_seen = datetime.utcnow()
                if username and user.username != username:
                    user.username = username
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                session.commit()
            
            return user
        finally:
            session.close()
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(user_id=user_id).first()
        finally:
            session.close()
    
    # Connection Management
    def add_connection(self, user_id: int, name: str, host: str, port: int, username: str, 
                      auth_type: str, encrypted_password: str = None, 
                      encrypted_private_key: str = None, key_passphrase: str = None) -> SSHConnection:
        """Add new SSH connection"""
        session = self.get_session()
        try:
            # Check if connection name already exists for user
            existing = session.query(SSHConnection).filter_by(
                user_id=user_id, name=name
            ).first()
            
            if existing:
                raise ValueError(f"Connection '{name}' already exists")
            
            connection = SSHConnection(
                user_id=user_id,
                name=name,
                host=host,
                port=port,
                username=username,
                auth_type=auth_type,
                encrypted_password=encrypted_password,
                encrypted_private_key=encrypted_private_key,
                key_passphrase=key_passphrase
            )
            
            # If this is the first connection, make it default
            user_connections = session.query(SSHConnection).filter_by(user_id=user_id).count()
            if user_connections == 0:
                connection.is_default = True
            
            session.add(connection)
            session.commit()
            
            self.add_audit_log(user_id, "connection_added", f"Added connection: {name} ({host})")
            return connection
        finally:
            session.close()
    
    def get_connections(self, user_id: int) -> List[SSHConnection]:
        """Get all connections for a user"""
        session = self.get_session()
        try:
            return session.query(SSHConnection).filter_by(user_id=user_id).all()
        finally:
            session.close()
    
    def get_connection(self, user_id: int, connection_name: str) -> Optional[SSHConnection]:
        """Get specific connection by name"""
        session = self.get_session()
        try:
            return session.query(SSHConnection).filter_by(
                user_id=user_id, name=connection_name
            ).first()
        finally:
            session.close()
    
    def get_connection_by_id(self, user_id: int, connection_id: int) -> Optional[SSHConnection]:
        """Get specific connection by ID"""
        session = self.get_session()
        try:
            return session.query(SSHConnection).filter_by(
                user_id=user_id, id=connection_id
            ).first()
        finally:
            session.close()
    
    def update_connection_last_used(self, connection_id: int):
        """Update last used timestamp for a connection"""
        session = self.get_session()
        try:
            connection = session.query(SSHConnection).filter_by(id=connection_id).first()
            if connection:
                connection.last_used = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def delete_connection(self, user_id: int, connection_name: str) -> bool:
        """Delete a connection"""
        session = self.get_session()
        try:
            connection = session.query(SSHConnection).filter_by(
                user_id=user_id, name=connection_name
            ).first()
            
            if connection:
                session.delete(connection)
                session.commit()
                self.add_audit_log(user_id, "connection_deleted", f"Deleted connection: {connection_name}")
                return True
            return False
        finally:
            session.close()
    
    def set_default_connection(self, user_id: int, connection_name: str) -> bool:
        """Set a connection as default"""
        session = self.get_session()
        try:
            # Remove default from all connections
            session.query(SSHConnection).filter_by(user_id=user_id).update(
                {'is_default': False}
            )
            
            # Set new default
            connection = session.query(SSHConnection).filter_by(
                user_id=user_id, name=connection_name
            ).first()
            
            if connection:
                connection.is_default = True
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    # Session Management
    def create_session(self, user_id: int, session_id: str, connection_id: int = None) -> ActiveSession:
        """Create new active session"""
        session = self.get_session()
        try:
            # Remove any existing sessions for this user
            session.query(ActiveSession).filter_by(user_id=user_id).delete()
            
            active_session = ActiveSession(
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id
            )
            session.add(active_session)
            session.commit()
            return active_session
        finally:
            session.close()
    
    def get_active_session(self, user_id: int) -> Optional[ActiveSession]:
        """Get active session for user"""
        session = self.get_session()
        try:
            return session.query(ActiveSession).filter_by(user_id=user_id).first()
        finally:
            session.close()
    
    def update_session_activity(self, session_id: str):
        """Update session last activity"""
        session = self.get_session()
        try:
            active_session = session.query(ActiveSession).filter_by(session_id=session_id).first()
            if active_session:
                active_session.last_activity = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def delete_session(self, user_id: int):
        """Delete active session"""
        session = self.get_session()
        try:
            session.query(ActiveSession).filter_by(user_id=user_id).delete()
            session.commit()
        finally:
            session.close()
    
    # Audit Logging
    def add_audit_log(self, user_id: int, action: str, details: str = None):
        """Add audit log entry"""
        session = self.get_session()
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                details=details
            )
            session.add(log)
            session.commit()
        except:
            pass  # Don't fail on audit log errors
        finally:
            session.close()
    
    def cleanup_old_sessions(self, timeout_minutes: int = 30):
        """Clean up old inactive sessions"""
        session = self.get_session()
        try:
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            old_sessions = session.query(ActiveSession).filter(
                ActiveSession.last_activity < cutoff_time
            ).all()
            
            for old_session in old_sessions:
                session.delete(old_session)
            
            session.commit()
            return len(old_sessions)
        finally:
            session.close()
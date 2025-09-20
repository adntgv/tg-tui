"""
SSH connection handler for webapp
Manages SSH connections based on session IDs from the bot
"""
import os
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)


def create_ssh_command(connection, credentials=None):
    """Create SSH command from connection details"""
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=60",
        "-p", str(connection.port),
        f"{connection.username}@{connection.host}"
    ]
    
    temp_key_file = None
    
    # Handle SSH key authentication
    if connection.auth_type == 'key' and credentials and credentials.get('private_key'):
        # Create temporary key file
        temp_key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
        temp_key_file.write(credentials['private_key'])
        temp_key_file.close()
        
        # Set proper permissions
        os.chmod(temp_key_file.name, 0o600)
        
        # Add key file to SSH command
        ssh_args.insert(1, "-i")
        ssh_args.insert(2, temp_key_file.name)
    
    return ssh_args, temp_key_file


def handle_ssh_authentication(master_fd, connection, credentials):
    """Handle SSH authentication prompts"""
    import select
    import time
    
    # Wait for initial output
    time.sleep(0.5)
    
    # Check for password/passphrase prompt
    r, _, _ = select.select([master_fd], [], [], 5)
    if r:
        output = os.read(master_fd, 4096)
        output_str = output.decode('utf-8', errors='replace').lower()
        
        if 'password:' in output_str and connection.auth_type == 'password':
            if credentials and credentials.get('password'):
                password = credentials['password'] + '\n'
                os.write(master_fd, password.encode())
                return True
        elif 'passphrase' in output_str and connection.auth_type == 'key':
            if credentials and credentials.get('key_passphrase'):
                passphrase = credentials['key_passphrase'] + '\n'
                os.write(master_fd, passphrase.encode())
                return True
    
    return False


def cleanup_temp_files(*files):
    """Clean up temporary files"""
    for file_obj in files:
        if file_obj and hasattr(file_obj, 'name'):
            try:
                os.unlink(file_obj.name)
            except:
                pass
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
        "-t",  # Force pseudo-terminal allocation for proper terminal support
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=60",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "PubkeyAuthentication=no",
        "-p", str(connection.port),
        f"{connection.username}@{connection.host}",
        "export TERM=xterm-256color && /bin/bash -l"  # Set terminal type and start login shell
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
    
    print(f"Starting authentication handler for {connection.username}@{connection.host}")
    
    # Wait for initial output
    time.sleep(0.5)
    
    # Check for password/passphrase prompt
    r, _, _ = select.select([master_fd], [], [], 5)
    if r:
        output = os.read(master_fd, 4096)
        output_str = output.decode('utf-8', errors='replace')
        print(f"SSH prompt received: {repr(output_str)}")
        
        output_lower = output_str.lower()
        
        if 'password:' in output_lower and connection.auth_type == 'password':
            if credentials and credentials.get('password'):
                password = credentials['password'] + '\n'
                print(f"Sending password for {connection.username}")
                written = os.write(master_fd, password.encode())
                print(f"Wrote {written} bytes for password")
                
                # Wait a bit and check for response
                time.sleep(0.5)
                r, _, _ = select.select([master_fd], [], [], 2)
                if r:
                    response = os.read(master_fd, 4096)
                    print(f"Post-auth response: {repr(response.decode('utf-8', errors='replace'))}")
                
                return True
        elif 'passphrase' in output_lower and connection.auth_type == 'key':
            if credentials and credentials.get('key_passphrase'):
                passphrase = credentials['key_passphrase'] + '\n'
                os.write(master_fd, passphrase.encode())
                return True
    else:
        print("No prompt received within timeout")
    
    return False


def cleanup_temp_files(*files):
    """Clean up temporary files"""
    for file_obj in files:
        if file_obj and hasattr(file_obj, 'name'):
            try:
                os.unlink(file_obj.name)
            except:
                pass
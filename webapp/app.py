#!/usr/bin/env python3
"""
Fixed Telegram Terminal Web App Server
Properly handles PTY creation and data flow
"""

import asyncio
import json
import os
import sys
import pty
import select
import struct
import fcntl
import termios
import signal
import subprocess
import tempfile
from typing import Dict, Optional
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request as FastAPIRequest, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles  # Not used currently
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import uvicorn
import logging

# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from database import DatabaseManager
from security import EncryptionManager
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AUTHORIZED_USER_IDS = {289310951}  # Same as main bot
DEFAULT_SHELL = os.environ.get("SHELL", "/bin/bash")
DEFAULT_CWD = os.getcwd()

# Initialize database and encryption
db = DatabaseManager(config.DATABASE_URL)
encryption = EncryptionManager(config.ENCRYPTION_KEY)

app = FastAPI()

# Initialize templates - with error handling
try:
    templates = Jinja2Templates(directory="templates")
    logger.info("Templates initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize templates: {e}")
    templates = None

# Track active sessions
@dataclass
class TerminalSession:
    process: Optional[subprocess.Popen] = None
    master_fd: Optional[int] = None
    websocket: Optional[WebSocket] = None
    read_task: Optional[asyncio.Task] = None
    session_id: Optional[str] = None
    connection_id: Optional[int] = None
    temp_key_file: Optional[str] = None

sessions: Dict[str, TerminalSession] = {}


@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("Starting Telegram Terminal Web App")
    logger.info(f"Port: {os.environ.get('PORT', '8000')}")
    logger.info(f"Default Shell: {DEFAULT_SHELL}")
    logger.info(f"Templates configured: {templates is not None}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "templates_loaded": templates is not None}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details by session ID"""
    active_session = db.get_session_by_id(session_id)
    if not active_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get connection details if available
    connection = None
    if active_session.connection_id:
        connection = db.get_connection_by_id(active_session.connection_id)
    
    return {
        "session": active_session.to_dict(),
        "connection": connection.to_dict() if connection else None
    }


@app.post("/webhook")
async def webhook(request: FastAPIRequest):
    """Telegram webhook endpoint - forwards to bot"""
    # This is just a placeholder - the actual bot handles webhooks
    return JSONResponse({"ok": True})


@app.get("/")
async def root(request: Request):
    """Serve the terminal HTML page"""
    if templates:
        return templates.TemplateResponse("terminal.html", {"request": request})
    else:
        return HTMLResponse(content="<h1>Terminal Web App</h1><p>Templates not configured</p>", status_code=500)


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for terminal communication"""
    await websocket.accept()
    print(f"WebSocket connected for user {user_id}")
    
    # Create session
    session = TerminalSession(websocket=websocket)
    sessions[user_id] = session
    
    master_fd = None
    slave_fd = None
    process = None
    
    try:
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        session.master_fd = master_fd
        
        print(f"Created PTY: master={master_fd}, slave={slave_fd}")
        
        # Make master non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Start shell process using subprocess.Popen for better control
        process = subprocess.Popen(
            [DEFAULT_SHELL],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=DEFAULT_CWD,
            preexec_fn=os.setsid,
            env=os.environ.copy()
        )
        session.process = process
        
        print(f"Started shell process: PID={process.pid}")
        
        # IMPORTANT: Close slave FD in parent process after starting child
        os.close(slave_fd)
        slave_fd = None
        print("Closed slave FD in parent")
        
        # Start output reader task
        async def read_output():
            """Read output from PTY and send to WebSocket"""
            print("Starting output reader task")
            loop = asyncio.get_event_loop()
            
            while process.poll() is None:  # While process is running
                try:
                    # Check if data is available to read
                    r, _, _ = select.select([master_fd], [], [], 0.01)
                    if r:
                        try:
                            # Read available data
                            output = os.read(master_fd, 4096)
                            if output:
                                # Send to WebSocket as text
                                text_output = output.decode('utf-8', errors='replace')
                                print(f"Read output: {repr(text_output[:50])}...")
                                await websocket.send_text(text_output)
                        except OSError as e:
                            if e.errno == 5:  # Input/output error - process might have exited
                                break
                            print(f"Read OSError: {e}")
                    
                except Exception as e:
                    print(f"Read error: {e}")
                    break
                    
                await asyncio.sleep(0.01)
            
            print("Output reader task ended")
        
        # Start the reader task
        session.read_task = asyncio.create_task(read_output())
        
        # Send initial prompt by sending a newline
        os.write(master_fd, b'\n')
        
        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data['type'] == 'input':
                    # Write input to PTY
                    input_data = data['data']
                    print(f"Received input: {repr(input_data)}")
                    written = os.write(master_fd, input_data.encode())
                    print(f"Wrote {written} bytes to PTY")
                    
                elif data['type'] == 'resize':
                    # Resize PTY
                    cols = data.get('cols', 80)
                    rows = data.get('rows', 24)
                    print(f"Resizing to {cols}x{rows}")
                    
                    # Set terminal size
                    winsize = struct.pack('HHHH', rows, cols, 0, 0)
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                    
                    # Send SIGWINCH to process
                    if process and process.pid:
                        os.kill(process.pid, signal.SIGWINCH)
                        
            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
                
    except Exception as e:
        print(f"Session error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("Cleaning up session")
        
        # Cancel read task
        if session.read_task:
            session.read_task.cancel()
            try:
                await session.read_task
            except asyncio.CancelledError:
                pass
        
        # Terminate process
        if process:
            try:
                process.terminate()
                process.wait(timeout=1)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        # Close file descriptors
        if master_fd is not None:
            try:
                os.close(master_fd)
            except:
                pass
                
        if slave_fd is not None:
            try:
                os.close(slave_fd)
            except:
                pass
        
        # Remove session
        sessions.pop(user_id, None)
        print(f"Session cleaned up for user {user_id}")


@app.websocket("/ws/session/{session_id}")
async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for SSH sessions initiated from Telegram bot"""
    await websocket.accept()
    print(f"WebSocket connected for session {session_id}")
    
    # Get session details from database
    active_session = db.get_session_by_id(session_id)
    if not active_session:
        await websocket.send_text(json.dumps({"error": "Session not found"}))
        await websocket.close()
        return
    
    # Get connection details
    connection = None
    if active_session.connection_id:
        connection = db.get_connection_by_id(connection_id=active_session.connection_id)
    
    if not connection:
        await websocket.send_text(json.dumps({"error": "Connection not found"}))
        await websocket.close()
        return
    
    # Create terminal session
    session = TerminalSession(
        websocket=websocket,
        session_id=session_id,
        connection_id=active_session.connection_id
    )
    sessions[f"session_{session_id}"] = session
    
    master_fd = None
    slave_fd = None
    process = None
    temp_key_file = None
    
    try:
        # Import SSH handler
        from ssh_handler import create_ssh_command, handle_ssh_authentication, cleanup_temp_files
        
        # Get connection credentials
        from ssh.connections import ConnectionManager
        conn_mgr = ConnectionManager(db, encryption)
        credentials = conn_mgr.get_connection_credentials(active_session.user_id, connection.name)
        
        # Create SSH command
        ssh_args, temp_key_file = create_ssh_command(connection, credentials)
        session.temp_key_file = temp_key_file
        
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        session.master_fd = master_fd
        
        print(f"Created PTY for SSH: master={master_fd}, slave={slave_fd}")
        
        # Make master non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Start SSH process
        process = subprocess.Popen(
            ssh_args,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            env=os.environ.copy()
        )
        session.process = process
        
        print(f"Started SSH process: PID={process.pid}, Command: {' '.join(ssh_args)}")
        
        # Close slave FD in parent
        os.close(slave_fd)
        slave_fd = None
        
        # Handle authentication if needed
        if connection.auth_type in ['password', 'key']:
            handle_ssh_authentication(master_fd, connection, credentials)
        
        # Update session activity in database
        db.update_session_activity(session_id)
        
        # Start output reader task
        async def read_output():
            """Read output from SSH PTY and send to WebSocket"""
            print("Starting SSH output reader task")
            loop = asyncio.get_event_loop()
            
            while process.poll() is None:  # While process is running
                try:
                    # Check if data is available to read
                    r, _, _ = select.select([master_fd], [], [], 0.01)
                    if r:
                        try:
                            # Read available data
                            output = os.read(master_fd, 4096)
                            if output:
                                # Send to WebSocket as text
                                text_output = output.decode('utf-8', errors='replace')
                                await websocket.send_text(text_output)
                        except OSError as e:
                            if e.errno == 5:  # Input/output error
                                break
                            print(f"Read OSError: {e}")
                    
                except Exception as e:
                    print(f"Read error: {e}")
                    break
                    
                await asyncio.sleep(0.01)
            
            print("SSH output reader task ended")
        
        # Start the reader task
        session.read_task = asyncio.create_task(read_output())
        
        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data['type'] == 'input':
                    # Write input to PTY
                    input_data = data['data']
                    os.write(master_fd, input_data.encode())
                    
                elif data['type'] == 'resize':
                    # Resize PTY
                    cols = data.get('cols', 80)
                    rows = data.get('rows', 24)
                    
                    # Set terminal size
                    winsize = struct.pack('HHHH', rows, cols, 0, 0)
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                    
                    # Send SIGWINCH to process
                    if process and process.pid:
                        os.kill(process.pid, signal.SIGWINCH)
                        
            except WebSocketDisconnect:
                print("SSH WebSocket disconnected")
                break
            except Exception as e:
                print(f"SSH WebSocket error: {e}")
                break
    
    finally:
        # Cleanup
        if session.read_task:
            session.read_task.cancel()
        
        # Terminate process
        if process:
            try:
                process.terminate()
                process.wait(timeout=1)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        # Close file descriptors
        if master_fd is not None:
            try:
                os.close(master_fd)
            except:
                pass
                
        if slave_fd is not None:
            try:
                os.close(slave_fd)
            except:
                pass
        
        # Clean up temporary key file
        if temp_key_file:
            cleanup_temp_files(temp_key_file)
        
        # Remove session
        sessions.pop(f"session_{session_id}", None)
        print(f"SSH session cleaned up: {session_id}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all sessions on shutdown"""
    for session in sessions.values():
        if session.process:
            try:
                session.process.terminate()
            except:
                pass


if __name__ == "__main__":
    # Run server
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
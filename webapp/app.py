#!/usr/bin/env python3
"""
Fixed Telegram Terminal Web App Server
Properly handles PTY creation and data flow
"""

import asyncio
import json
import os
import pty
import select
import struct
import fcntl
import termios
import signal
import subprocess
from typing import Dict, Optional
from dataclasses import dataclass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import uvicorn

# Configuration
AUTHORIZED_USER_IDS = {289310951}  # Same as main bot
DEFAULT_SHELL = os.environ.get("SHELL", "/bin/bash")
DEFAULT_CWD = os.getcwd()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Track active sessions
@dataclass
class TerminalSession:
    process: Optional[subprocess.Popen] = None
    master_fd: Optional[int] = None
    websocket: Optional[WebSocket] = None
    read_task: Optional[asyncio.Task] = None

sessions: Dict[str, TerminalSession] = {}


@app.get("/")
async def root(request: Request):
    """Serve the terminal HTML page"""
    return templates.TemplateResponse("terminal.html", {"request": request})


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
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
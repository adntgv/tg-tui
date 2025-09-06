#!/usr/bin/env python3
"""
Telegram Terminal Web App Server
Provides WebSocket interface for terminal access through Telegram Mini Apps
"""

import asyncio
import json
import os
import pty
import struct
import fcntl
import termios
import signal
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
    process: Optional[asyncio.subprocess.Process] = None
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
    
    # Create session
    session = TerminalSession(websocket=websocket)
    sessions[user_id] = session
    
    try:
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        session.master_fd = master_fd
        
        print(f"Created PTY: master={master_fd}, slave={slave_fd}")
        
        # Start shell process
        session.process = await asyncio.create_subprocess_exec(
            DEFAULT_SHELL,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=DEFAULT_CWD,
            preexec_fn=os.setsid
        )
        
        print(f"Started shell process: {DEFAULT_SHELL}")
        
        # Set non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Start output reader task
        async def read_output():
            """Read output from PTY and send to WebSocket"""
            loop = asyncio.get_event_loop()
            while True:
                try:
                    # Read from PTY
                    output = await loop.run_in_executor(None, os.read, master_fd, 4096)
                    if output:
                        # Send to WebSocket as text (decode bytes to string)
                        await websocket.send_text(output.decode('utf-8', errors='replace'))
                except OSError:
                    break
                except Exception as e:
                    print(f"Read error: {e}")
                    break
                await asyncio.sleep(0.01)
        
        session.read_task = asyncio.create_task(read_output())
        
        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data['type'] == 'input':
                    # Write input to PTY
                    input_data = data['data']
                    print(f"Received input: {repr(input_data)}")
                    os.write(master_fd, input_data.encode())
                    print(f"Wrote to PTY: {repr(input_data.encode())}")
                    
                elif data['type'] == 'resize':
                    # Resize PTY
                    cols = data.get('cols', 80)
                    rows = data.get('rows', 24)
                    
                    # Set terminal size
                    winsize = struct.pack('HHHH', rows, cols, 0, 0)
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                    
                    # Send SIGWINCH to process group
                    if session.process and session.process.pid:
                        os.killpg(os.getpgid(session.process.pid), signal.SIGWINCH)
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
                
    finally:
        # Cleanup
        if session.read_task:
            session.read_task.cancel()
            
        if session.process:
            try:
                session.process.terminate()
                await session.process.wait()
            except:
                pass
                
        if session.master_fd:
            try:
                os.close(session.master_fd)
            except:
                pass
                
        # Remove session
        sessions.pop(user_id, None)


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
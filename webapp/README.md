# Telegram Terminal Web App

This is a Telegram Mini App that provides a full terminal interface through a web browser.

## Features

- Full xterm.js terminal emulation
- WebSocket connection for real-time interaction
- Touch-friendly toolbar with common keys
- Responsive design that works on mobile and desktop
- Secure PTY access with session management

## Setup

### 1. Install Dependencies

```bash
cd webapp
pip install -r requirements.txt
```

### 2. Run the Web App Server

```bash
python app.py
```

The server will start on port 8080.

### 3. Make it Accessible

For Telegram Mini Apps to work, your web app must be accessible via HTTPS. Options:

#### Option A: Using ngrok (for testing)
```bash
ngrok http 8080
```

Copy the HTTPS URL provided by ngrok.

#### Option B: Deploy to a VPS
Deploy to a server with a domain and SSL certificate.

#### Option C: Use Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8080
```

### 4. Configure the Bot

Set the WEBAPP_URL environment variable when running the main bot:

```bash
WEBAPP_URL="https://your-domain.com" TELEGRAM_TOKEN=your_token python3 main.py
```

### 5. Use the Web App

In Telegram, use the `/webapp` command to get a button that launches the terminal web app.

## Security Considerations

1. **Authentication**: The web app should verify Telegram's init data to ensure only authorized users can access it.
2. **HTTPS Required**: Telegram Mini Apps only work over HTTPS.
3. **Session Management**: Each user gets their own isolated terminal session.
4. **Resource Limits**: Consider adding limits on CPU, memory, and session duration.

## Deployment with Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t tg-terminal-webapp .
docker run -p 8080:8080 tg-terminal-webapp
```

## Environment Variables

- `SHELL`: Shell to use (default: /bin/bash)
- `PORT`: Port to run the server on (default: 8080)

## Troubleshooting

1. **WebSocket connection fails**: Ensure your reverse proxy supports WebSocket upgrades.
2. **Terminal doesn't respond**: Check that the PTY is being created correctly.
3. **Authentication issues**: Verify the Telegram init data validation.

## Future Improvements

- [ ] Add Telegram init data validation
- [ ] Implement session persistence
- [ ] Add file upload/download support
- [ ] Support multiple terminal tabs
- [ ] Add terminal themes
- [ ] Implement clipboard integration
# Coolify Deployment Guide for TG-TUI

## Prerequisites
- Coolify instance running with Traefik proxy active (port 80/443)
- GitHub/GitLab repository with this code
- Telegram Bot Token from @BotFather
- Domain configured (e.g., tg-tui.adntgv.com)

## Deployment Steps

### 1. Create New Resource in Coolify
1. Go to your Coolify dashboard (https://coolify.adntgv.com:8000)
2. Click "New Resource" → "Docker Compose"
3. Select your server

### 2. Configure Source
1. Choose your Git provider (GitHub/GitLab)
2. Select repository containing this code
3. Set branch (usually `main`)

### 3. Configure Docker Compose
1. Set compose file path to: `docker-compose.coolify.yml`
2. Enable "Build on Server" option

### 4. Environment Variables
Add these in Coolify's environment variables section:

```bash
TELEGRAM_TOKEN=your_bot_token_here
WEBAPP_URL=https://tg-tui.adntgv.com
ENCRYPTION_KEY=generate_strong_32_byte_hex_string
WEBAPP_PORT=8000
DATABASE_URL=sqlite:////app/data/ssh_connections.db
```

Generate encryption key with:
```bash
openssl rand -hex 32
```

### 5. Network Configuration
1. The webapp service will be exposed automatically
2. Coolify will handle SSL certificates via Let's Encrypt
3. The bot service communicates internally with webapp

### 6. Deploy
1. Click "Deploy" button
2. Monitor logs in real-time
3. Wait for both services to be running

### 7. Configure Telegram Webhook
After deployment, set your bot's webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app.coolify-domain.com/webhook"}'
```

## Coolify-Specific Features

### Health Checks
Add to `docker-compose.coolify.yml` if needed:

```yaml
webapp:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Resource Limits
Configure in Coolify UI or add to compose:

```yaml
services:
  bot:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
  webapp:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
```

### Persistent Storage
If needed, add volumes:

```yaml
volumes:
  bot-data:
    driver: local

services:
  bot:
    volumes:
      - bot-data:/app/data
```

## Troubleshooting

### Common Issues

1. **Services not connecting**: Ensure they're on the same network
2. **Webhook not working**: Check WEBAPP_URL is correctly set
3. **Build failures**: Check Dockerfile paths and context
4. **Port conflicts**: Coolify handles port mapping automatically

### Logs
View logs in Coolify UI or SSH to server:

```bash
docker compose -f docker-compose.coolify.yml logs -f
```

## Updates
1. Push changes to your repository
2. Click "Redeploy" in Coolify
3. Coolify will rebuild and restart services

## Rollback
Coolify keeps previous deployments. Use "Rollback" button if needed.

## Advanced Configuration

### Custom Domain
1. Add domain in Coolify's domain settings
2. Update WEBAPP_URL environment variable
3. Coolify handles SSL automatically

### Scaling
For horizontal scaling, consider separating services:
- Deploy webapp as standalone Coolify application
- Deploy bot as separate service
- Use external Redis/database for session management
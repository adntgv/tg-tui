# Cloudflare Deployment Setup

## Option 1: Cloudflare Tunnel (Recommended)

1. Install cloudflared:
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin
```

2. Login to Cloudflare:
```bash
cloudflared tunnel login
```

3. Create a tunnel:
```bash
cloudflared tunnel create tg-tui-tunnel
```

4. Get the tunnel token:
```bash
cloudflared tunnel token tg-tui-tunnel
```

5. Configure the tunnel route:
```bash
cloudflared tunnel route dns tg-tui-tunnel your-domain.com
```

6. Update `.env` with your tunnel token and run:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Option 2: Cloudflare Workers

Deploy the webapp as a Cloudflare Worker:

1. Install Wrangler:
```bash
npm install -g wrangler
```

2. Use the provided `wrangler.toml` configuration

3. Deploy:
```bash
wrangler deploy
```

## Option 3: Cloudflare Pages

For static hosting with serverless functions:

1. Connect your GitHub repository to Cloudflare Pages
2. Set build command: `cd webapp && npm run build`
3. Set output directory: `webapp/dist`
4. Configure environment variables in Cloudflare dashboard
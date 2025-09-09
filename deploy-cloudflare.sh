#!/bin/bash

set -e

echo "☁️  Deploying to Cloudflare..."

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "Installing Wrangler CLI..."
    npm install -g wrangler
fi

# Deploy webapp to Cloudflare Workers
echo "📦 Building webapp..."
cd webapp

# Deploy to Cloudflare
echo "🚀 Deploying to Cloudflare Workers..."
wrangler deploy

cd ..

echo "✅ Cloudflare deployment complete!"
echo "🔗 Your app is now available at your Cloudflare Workers URL"
echo "📝 Don't forget to update WEBAPP_URL in your bot configuration"
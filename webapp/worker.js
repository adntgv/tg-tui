export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Handle WebSocket connections
    if (request.headers.get('Upgrade') === 'websocket') {
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      
      // Handle WebSocket messages
      server.accept();
      server.addEventListener('message', event => {
        // Process terminal commands
        const data = JSON.parse(event.data);
        // Forward to your backend or process here
        server.send(JSON.stringify({ 
          type: 'output', 
          data: `Received: ${data.command}` 
        }));
      });
      
      return new Response(null, {
        status: 101,
        webSocket: client,
      });
    }
    
    // Serve static files
    if (url.pathname === '/') {
      return new Response(getIndexHTML(), {
        headers: { 'Content-Type': 'text/html' },
      });
    }
    
    return new Response('Not Found', { status: 404 });
  },
};

function getIndexHTML() {
  // Return your index.html content
  return `<!DOCTYPE html>
<html>
<head>
    <title>Telegram Terminal UI</title>
</head>
<body>
    <div id="terminal"></div>
    <script src="/static/terminal.js"></script>
</body>
</html>`;
}
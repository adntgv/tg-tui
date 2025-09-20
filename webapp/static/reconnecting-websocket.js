/**
 * Reconnecting WebSocket with exponential backoff
 * Automatically reconnects on disconnection with configurable retry logic
 */
class ReconnectingWebSocket {
    constructor(url, protocols, options = {}) {
        this.url = url;
        this.protocols = protocols;

        // Configuration with defaults
        this.reconnectInterval = options.reconnectInterval || 1000; // Initial reconnect delay
        this.maxReconnectInterval = options.maxReconnectInterval || 30000; // Max delay between reconnects
        this.reconnectDecay = options.reconnectDecay || 1.5; // Exponential backoff factor
        this.timeoutInterval = options.timeoutInterval || 2000; // Connection timeout
        this.maxReconnectAttempts = options.maxReconnectAttempts || null; // null = infinite
        this.automaticOpen = options.automaticOpen !== false; // Auto connect on instantiation

        // State
        this.reconnectAttempts = 0;
        this.readyState = WebSocket.CONNECTING;
        this.forcedClose = false;
        this.timedOut = false;

        // Event handlers
        this.onopen = null;
        this.onclose = null;
        this.onmessage = null;
        this.onerror = null;
        this.onconnecting = null;
        this.onreconnect = null;

        // Message queue for disconnected state
        this.messageQueue = [];

        if (this.automaticOpen) {
            this.open(false);
        }
    }

    open(reconnectAttempt) {
        this.readyState = WebSocket.CONNECTING;

        if (this.onconnecting) {
            this.onconnecting(reconnectAttempt);
        }

        try {
            this.ws = new WebSocket(this.url, this.protocols);
        } catch (e) {
            console.error('WebSocket creation error:', e);
            this.scheduleReconnect();
            return;
        }

        // Connection timeout
        this.timeout = setTimeout(() => {
            console.log('Connection timeout');
            this.timedOut = true;
            this.ws.close();
            this.timedOut = false;
        }, this.timeoutInterval);

        this.ws.onopen = (event) => {
            clearTimeout(this.timeout);
            this.readyState = WebSocket.OPEN;
            this.reconnectAttempts = 0;

            // Process queued messages
            while (this.messageQueue.length > 0) {
                const message = this.messageQueue.shift();
                this.send(message);
            }

            if (reconnectAttempt && this.onreconnect) {
                this.onreconnect(event);
            }

            if (this.onopen) {
                this.onopen(event);
            }
        };

        this.ws.onclose = (event) => {
            clearTimeout(this.timeout);
            this.ws = null;

            if (this.forcedClose) {
                this.readyState = WebSocket.CLOSED;
                if (this.onclose) {
                    this.onclose(event);
                }
            } else {
                this.readyState = WebSocket.CONNECTING;
                if (!reconnectAttempt && !this.timedOut) {
                    if (this.onclose) {
                        this.onclose(event);
                    }
                }
                this.scheduleReconnect();
            }
        };

        this.ws.onmessage = (event) => {
            if (this.onmessage) {
                this.onmessage(event);
            }
        };

        this.ws.onerror = (event) => {
            if (this.onerror) {
                this.onerror(event);
            }
        };
    }

    scheduleReconnect() {
        if (this.maxReconnectAttempts && this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const timeout = Math.min(
            this.reconnectInterval * Math.pow(this.reconnectDecay, this.reconnectAttempts - 1),
            this.maxReconnectInterval
        );

        console.log(`Reconnecting in ${timeout}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.open(true);
        }, timeout);
    }

    send(data) {
        if (this.ws && this.readyState === WebSocket.OPEN) {
            return this.ws.send(data);
        } else {
            // Queue message if disconnected
            this.messageQueue.push(data);
            console.log('Message queued, will send when reconnected');
        }
    }

    close(code, reason) {
        this.forcedClose = true;
        if (this.ws) {
            this.ws.close(code, reason);
        }
    }

    refresh() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ReconnectingWebSocket;
}
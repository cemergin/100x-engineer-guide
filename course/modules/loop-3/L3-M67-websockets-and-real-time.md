# L3-M67: WebSockets & Real-Time

> **Loop 3 (Mastery)** | Section 3B: Real-Time & Advanced Features | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M10, L2-M31
>
> **Source:** Chapters 21, 10 of the 100x Engineer Guide

## What You'll Learn

- How the WebSocket protocol works: the HTTP upgrade handshake, binary framing, and full-duplex communication
- Building a WebSocket server for TicketPulse that broadcasts live seat availability
- Scaling WebSocket connections horizontally using Redis Pub/Sub
- Implementing heartbeats (ping/pong) and client-side reconnection with exponential backoff
- When to use WebSocket vs SSE vs polling

## Why This Matters

TicketPulse has a problem. A user is staring at the seat map for a popular concert. They see seat A-15 as available, click "Buy," and get an error: someone else bought it 30 seconds ago. The page was stale. The user is frustrated.

Real-time updates fix this. When someone buys a ticket, every other user watching that event sees the seat disappear instantly. No refresh, no stale data, no wasted clicks.

WebSocket is the protocol that makes this possible. Unlike HTTP's request-response model, WebSocket establishes a persistent, bidirectional connection between client and server. The server can push data to the client at any time, without the client asking for it.

Every major ticketing platform, chat application, collaborative editor, and trading platform uses WebSocket or a close cousin. Understanding this protocol is not optional for a backend engineer building real-time features.

---

## 1. The WebSocket Protocol

### The Handshake

WebSocket starts as a normal HTTP/1.1 request. The client sends an `Upgrade` header asking the server to switch protocols:

```http
GET /ws/events/evt_001 HTTP/1.1
Host: ticketpulse.local
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

If the server supports WebSocket, it responds with `101 Switching Protocols`:

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

The `Sec-WebSocket-Accept` value is a hash of the client's key concatenated with a magic GUID. This proves the server understands WebSocket, not just blindly proxying.

After the 101 response, the TCP connection stays open. Both sides communicate using WebSocket frames -- binary, text, ping, pong, close. No more HTTP.

### Why Not Just Use HTTP?

HTTP is request-response. The client asks, the server answers. If the server has new data, it has to wait until the client asks again. For a seat map with 50K watchers, that means either:

- **Polling**: 50K clients hitting `GET /api/events/evt_001/seats` every 2 seconds = 25K requests/second for stale data 90% of the time
- **Long polling**: slightly better, but each update requires a new HTTP connection with full headers
- **WebSocket**: one persistent connection per client. Server pushes only when something changes. A ticket sale triggers 50K pushes in milliseconds.

The overhead difference is dramatic. An HTTP request carries ~800 bytes of headers. A WebSocket frame carrying `{"type":"TICKET_SOLD","seatId":"A-15"}` is ~50 bytes total.

---

## 2. Build: WebSocket Server for TicketPulse

### The Goal

Clients connect to `ws://localhost:3000/ws/events/:eventId`. When a ticket is purchased for that event, every connected client receives a message like:

```json
{
  "type": "TICKET_SOLD",
  "seatId": "A-15",
  "remainingCount": 142,
  "timestamp": 1679012345678
}
```

### Stop and Design (5 minutes)

Before looking at the implementation, think through:

1. How will you track which clients are watching which event?
2. When a ticket is purchased via the REST API, how does the WebSocket server find out?
3. What happens when a client disconnects? How do you clean up?

Write down your approach, then continue.

---

### Reference Implementation

```javascript
// server.js
const { WebSocketServer } = require('ws');
const http = require('http');
const express = require('express');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });

// Track connections by eventId
// Map<eventId, Set<WebSocket>>
const eventRooms = new Map();

// Handle the HTTP upgrade to WebSocket
server.on('upgrade', (request, socket, head) => {
  // Parse the URL: /ws/events/:eventId
  const url = new URL(request.url, `http://${request.headers.host}`);
  const match = url.pathname.match(/^\/ws\/events\/(.+)$/);

  if (!match) {
    socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
    socket.destroy();
    return;
  }

  const eventId = match[1];

  // In production: validate JWT from query param or header here
  // const token = url.searchParams.get('token');
  // if (!verifyToken(token)) { socket.destroy(); return; }

  wss.handleUpgrade(request, socket, head, (ws) => {
    ws.eventId = eventId;
    wss.emit('connection', ws, request);
  });
});

wss.on('connection', (ws) => {
  const eventId = ws.eventId;

  // Add to event room
  if (!eventRooms.has(eventId)) {
    eventRooms.set(eventId, new Set());
  }
  eventRooms.get(eventId).add(ws);

  console.log(`Client joined event ${eventId}. Room size: ${eventRooms.get(eventId).size}`);

  // Send current state on connect
  ws.send(JSON.stringify({
    type: 'CONNECTED',
    eventId,
    message: 'Watching for ticket updates'
  }));

  // Handle client messages (for bidirectional communication)
  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data);
      // Handle ping from client
      if (msg.type === 'PING') {
        ws.send(JSON.stringify({ type: 'PONG', timestamp: Date.now() }));
      }
    } catch (e) {
      // Ignore malformed messages
    }
  });

  // Clean up on disconnect
  ws.on('close', () => {
    const room = eventRooms.get(eventId);
    if (room) {
      room.delete(ws);
      if (room.size === 0) {
        eventRooms.delete(eventId);
      }
    }
    console.log(`Client left event ${eventId}. Room size: ${eventRooms.get(eventId)?.size || 0}`);
  });
});

// Broadcast to all clients watching a specific event
function broadcastToEvent(eventId, message) {
  const room = eventRooms.get(eventId);
  if (!room) return;

  const payload = JSON.stringify(message);
  let sent = 0;

  for (const client of room) {
    if (client.readyState === 1) { // WebSocket.OPEN
      client.send(payload);
      sent++;
    }
  }

  console.log(`Broadcast to ${sent} clients for event ${eventId}`);
}

// REST endpoint: purchase a ticket
// When a ticket is purchased, broadcast to WebSocket clients
app.use(express.json());

app.post('/api/events/:eventId/purchase', async (req, res) => {
  const { eventId } = req.params;
  const { seatId } = req.body;

  // In production: actual purchase logic with database
  // For now, simulate
  const remainingCount = Math.floor(Math.random() * 200);

  // Broadcast the update to all watchers
  broadcastToEvent(eventId, {
    type: 'TICKET_SOLD',
    seatId,
    remainingCount,
    timestamp: Date.now()
  });

  res.json({ success: true, seatId, remainingCount });
});

server.listen(3000, () => {
  console.log('TicketPulse WebSocket server running on :3000');
});
```

### The Client

```html
<!-- client.html -->
<!DOCTYPE html>
<html>
<head><title>TicketPulse Live Seats</title></head>
<body>
  <h1>Event: <span id="eventId">evt_001</span></h1>
  <div id="status">Connecting...</div>
  <ul id="updates"></ul>

  <script>
    const eventId = 'evt_001';
    let ws;

    function connect() {
      ws = new WebSocket(`ws://localhost:3000/ws/events/${eventId}`);

      ws.onopen = () => {
        document.getElementById('status').textContent = 'Connected - watching for updates';
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const li = document.createElement('li');

        if (data.type === 'TICKET_SOLD') {
          li.textContent = `Seat ${data.seatId} sold! ${data.remainingCount} remaining`;
          li.style.color = 'red';
        } else {
          li.textContent = JSON.stringify(data);
        }

        document.getElementById('updates').prepend(li);
      };

      ws.onclose = () => {
        document.getElementById('status').textContent = 'Disconnected - reconnecting...';
        // Reconnect after delay (we will improve this later)
        setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
      };
    }

    connect();
  </script>
</body>
</html>
```

---

## 3. Try It: The Three-Tab Test

Open three browser tabs, all pointing to the client page (or three terminal sessions using `wscat`).

```bash
# Terminal approach using wscat (npm install -g wscat)
# Tab 1:
wscat -c ws://localhost:3000/ws/events/evt_001

# Tab 2:
wscat -c ws://localhost:3000/ws/events/evt_001

# Tab 3: Buy a ticket
curl -X POST http://localhost:3000/api/events/evt_001/purchase \
  -H "Content-Type: application/json" \
  -d '{"seatId": "A-15"}'
```

Watch Tabs 1 and 2. Both should instantly display:

```json
{"type":"TICKET_SOLD","seatId":"A-15","remainingCount":142,"timestamp":1679012345678}
```

Buy a few more tickets. Watch them appear in real time across all tabs.

This is the core value of WebSocket: one event (a ticket purchase) propagates to all interested clients without any of them polling.

---

## 4. Scaling WebSockets Horizontally

### The Problem

Your single WebSocket server handles 10K connections fine. But the popular concert is approaching and you expect 50K simultaneous watchers. You add a second server behind a load balancer.

Now Client A is connected to Server 1 and Client B is connected to Server 2. A ticket purchase processed by Server 1 broadcasts to Server 1's clients. Client B never sees the update.

This is the fundamental challenge of stateful protocols. Each server only knows about its own connections.

```
                      Load Balancer
                     /             \
               Server 1           Server 2
               /     \               |
          Client A  Client C     Client B
                                    ^
                                    |
                            Misses the update!
```

### The Solution: Redis Pub/Sub

Redis Pub/Sub acts as a broadcast backbone. Every WebSocket server subscribes to a Redis channel. When any server needs to broadcast, it publishes to Redis. All servers receive the message and broadcast to their local clients.

```
         Redis Pub/Sub
        /      |       \
   Server 1  Server 2  Server 3
    /   \       |        /   \
  A     C      B       D     E
```

### Build: Add Redis Pub/Sub

```javascript
// redis-broadcast.js
const Redis = require('ioredis');

// Two Redis connections: one for publishing, one for subscribing
// (Redis requires separate connections for pub/sub)
const redisPub = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const redisSub = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

// Subscribe to the ticket-updates channel
redisSub.subscribe('ticket-updates', (err) => {
  if (err) console.error('Redis subscribe error:', err);
  else console.log('Subscribed to ticket-updates channel');
});

// When a message arrives from Redis, broadcast to local WebSocket clients
redisSub.on('message', (channel, message) => {
  if (channel === 'ticket-updates') {
    const data = JSON.parse(message);
    broadcastToEvent(data.eventId, data);
  }
});

// Modified purchase handler: publish to Redis instead of broadcasting directly
app.post('/api/events/:eventId/purchase', async (req, res) => {
  const { eventId } = req.params;
  const { seatId } = req.body;

  // Database logic here...
  const remainingCount = Math.floor(Math.random() * 200);

  // Publish to Redis -- ALL servers will receive this and broadcast
  const update = {
    type: 'TICKET_SOLD',
    eventId,
    seatId,
    remainingCount,
    timestamp: Date.now()
  };

  await redisPub.publish('ticket-updates', JSON.stringify(update));

  res.json({ success: true, seatId, remainingCount });
});
```

Now it does not matter which server processes the purchase. The update flows through Redis to every server, and every server broadcasts to its connected clients.

### Channel Granularity

Publishing all updates to a single `ticket-updates` channel works but is wasteful. If 10K users watch Event A and 10 users watch Event B, every update for Event B reaches all 10K Event A servers unnecessarily.

Use per-event channels:

```javascript
// Subscribe when first client connects to an event
function subscribeToEvent(eventId) {
  const channel = `ticket-updates:${eventId}`;
  redisSub.subscribe(channel);
}

// Unsubscribe when last client disconnects from an event
function unsubscribeFromEvent(eventId) {
  const channel = `ticket-updates:${eventId}`;
  redisSub.unsubscribe(channel);
}

// Publish to the specific event channel
await redisPub.publish(`ticket-updates:${eventId}`, JSON.stringify(update));
```

---

## 5. Heartbeats: Detecting Dead Connections

TCP connections can die silently. A client's laptop goes to sleep, their WiFi drops, a NAT gateway times out. The server still thinks the connection is open.

WebSocket defines **ping** (opcode 0x9) and **pong** (opcode 0xA) control frames for this.

```javascript
// Server-side heartbeat
const HEARTBEAT_INTERVAL = 30_000; // 30 seconds
const HEARTBEAT_TIMEOUT = 10_000;  // 10 seconds to respond

function startHeartbeat(ws) {
  ws.isAlive = true;

  ws.on('pong', () => {
    ws.isAlive = true;
  });
}

// Sweep all connections periodically
const heartbeatTimer = setInterval(() => {
  for (const [eventId, room] of eventRooms) {
    for (const ws of room) {
      if (!ws.isAlive) {
        // Did not respond to last ping -- terminate
        console.log(`Terminating dead connection for event ${eventId}`);
        ws.terminate();
        room.delete(ws);
        continue;
      }

      ws.isAlive = false;
      ws.ping(); // Send ping frame
    }
  }
}, HEARTBEAT_INTERVAL);

// Clean up on server shutdown
process.on('SIGTERM', () => {
  clearInterval(heartbeatTimer);
  wss.close();
});
```

Why 30 seconds? Many load balancers (ALB, nginx) have idle timeouts of 60 seconds. Your heartbeat must be shorter than the idle timeout, or the load balancer kills the connection before your ping detects the issue.

```nginx
# nginx config for WebSocket proxy
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 120s;  # Longer than heartbeat interval
}
```

---

## 6. Reconnection with Exponential Backoff

WebSocket does not auto-reconnect. If the connection drops, the client must reconnect explicitly. A naive approach (reconnect immediately on close) creates a "thundering herd" -- if the server restarts, all 50K clients reconnect at the same instant, overwhelming it.

Exponential backoff with jitter solves this:

```javascript
function createReconnectingWebSocket(url) {
  let ws;
  let retryDelay = 1000; // Start at 1 second
  const MAX_DELAY = 30000; // Cap at 30 seconds
  let reconnectTimer = null;

  function connect() {
    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('Connected');
      retryDelay = 1000; // Reset on successful connection
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleUpdate(data);
    };

    ws.onclose = (event) => {
      console.log(`Disconnected (code: ${event.code}). Reconnecting in ${retryDelay}ms...`);

      // Add jitter: +/- 25% randomness
      const jitter = retryDelay * 0.25 * (Math.random() * 2 - 1);
      const delay = retryDelay + jitter;

      reconnectTimer = setTimeout(connect, delay);

      // Exponential backoff
      retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
    };

    ws.onerror = () => {
      ws.close(); // Trigger onclose for reconnection
    };
  }

  connect();

  return {
    send: (data) => ws?.readyState === 1 && ws.send(data),
    close: () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    }
  };
}
```

The jitter is critical. Without it, exponential backoff creates synchronized retry waves. With jitter, clients spread their reconnection attempts across the backoff window.

```
Without jitter:  [100 clients at 1s] → [100 clients at 2s] → [100 clients at 4s]
With jitter:     [scattered 0.75-1.25s] → [scattered 1.5-2.5s] → [scattered 3-5s]
```

---

## 7. WebSocket vs SSE: When to Use Which

| Aspect | WebSocket | SSE (Server-Sent Events) |
|--------|-----------|--------------------------|
| Direction | Bidirectional | Server to client only |
| Protocol | Custom binary framing | Plain HTTP |
| Auto-reconnect | No (you build it) | Yes (built in) |
| Browser support | All modern browsers | All modern (except IE) |
| Proxy/CDN friendly | Problematic | Yes (just HTTP) |
| Binary data | Yes | No (text only) |
| Connection limit | OS/server limit | 6 per domain (HTTP/1.1) |
| Complexity | Higher | Lower |

**Use WebSocket when:**
- You need bidirectional communication (chat, collaborative editing)
- You need very low latency server-to-client pushes (< 100ms)
- You need high-frequency updates (multiple per second)
- You are sending binary data

**Use SSE when:**
- You only need server-to-client streaming
- You want automatic reconnection for free
- You need to work through corporate proxies that block WebSocket
- Simplicity matters more than bidirectional capability

For TicketPulse's seat map, WebSocket is the right choice. The client does not need to send data to the server over the WebSocket -- purchases go through the REST API. But the real-time requirement (instant seat updates for 50K watchers) and the high-frequency nature of a ticket rush make WebSocket the better tool.

SSE would work for a simpler case: a notification feed where the server pushes new notifications and the client just listens.

---

## 8. Reflect: Capacity Planning

Take 5 minutes to think through this:

> TicketPulse has 50K users watching a popular event go on sale. How many WebSocket connections can one server handle?

Consider:
- Each WebSocket connection is a TCP connection. Each uses a file descriptor and some kernel memory.
- An idle WebSocket connection uses roughly 10-20 KB of memory (kernel buffers + application state).
- A modern Linux server can handle 1M+ file descriptors with tuning (`ulimit -n`).
- 50K connections x 20 KB = ~1 GB of memory just for connections.
- The bottleneck is usually not the number of connections but the broadcast fan-out: sending a message to 50K clients takes time.

**Practical limits:**
- A single Node.js process: 10K-50K connections (limited by single-threaded event loop for broadcast)
- A single Go/Rust server: 100K-500K connections (multi-threaded, lighter runtime)
- With Redis Pub/Sub across 5 servers: 250K+ total connections

For TicketPulse's 50K concurrent watchers: 2-3 Node.js servers behind a load balancer with Redis Pub/Sub is plenty.

For Ticketmaster-scale (millions of watchers): you would use a dedicated connection management service (Ably, Pusher, or a custom Go/Rust service) and treat WebSocket infrastructure as a separate scalability concern from your application servers.

---

## 9. Checkpoint

Before moving on, verify:

- [ ] Your WebSocket server accepts connections at `/ws/events/:eventId`
- [ ] Purchasing a ticket broadcasts the update to all connected clients for that event
- [ ] The three-tab test works: buy in one tab, see the update in the other two
- [ ] You understand why horizontal scaling requires a pub/sub backbone
- [ ] You can explain when to use WebSocket vs SSE vs polling

---

## Summary

WebSocket gives TicketPulse real-time superpowers. A single ticket purchase propagates to every watcher in milliseconds. But WebSocket connections are stateful, which complicates horizontal scaling. Redis Pub/Sub solves this by acting as a broadcast backbone across servers. Heartbeats detect dead connections, and exponential backoff with jitter prevents thundering herds on reconnection.

The pattern you built here -- event rooms, pub/sub backbone, heartbeat, reconnection -- is the foundation for every real-time feature: live chat, collaborative editing, real-time dashboards, multiplayer games. The protocol details change, but the architecture is the same.

Next module: we stress-test this system. What happens when 50K users all try to buy 500 tickets at the same instant?

## Key Terms

| Term | Definition |
|------|-----------|
| **WebSocket** | A protocol providing full-duplex, persistent communication channels over a single TCP connection. |
| **SSE** | Server-Sent Events; a standard for pushing real-time updates from server to client over HTTP. |
| **Pub/sub** | A messaging pattern where publishers send messages to topics and subscribers receive messages from topics they follow. |
| **Heartbeat** | A periodic signal sent between client and server to confirm the connection is still alive. |
| **Reconnection** | The logic that automatically re-establishes a dropped real-time connection, often with exponential backoff. |
| **Real-time** | A system characteristic where data is delivered to users within milliseconds of being produced. |

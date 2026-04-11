# L2-M36: API Gateway & BFF

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M35 (Database Per Service), L2-M31 (Strangler Fig)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

In M31, you added a simple nginx reverse proxy to route traffic between the monolith and the payment service. That was enough for two services. TicketPulse now has four services (monolith, payments, notifications, analytics) with more coming. The simple proxy is not enough.

An API gateway is the single entry point for all external clients. It handles the concerns that every service needs but no individual service should implement:
- **Routing:** Direct requests to the correct service
- **Authentication:** Validate JWT tokens once, not in every service
- **Rate limiting:** Protect services from abuse
- **Logging:** Attach correlation IDs that flow through every service
- **Aggregation:** Combine data from multiple services into a single response (BFF pattern)

By the end of this module, TicketPulse will have a proper API gateway with cross-cutting concerns, and you will have designed a BFF for mobile clients.

**You will have the gateway routing traffic with auth and rate limiting within ten minutes.**

---

> **Before you continue:** The nginx proxy from M31 does basic routing. What cross-cutting concerns (auth, logging, rate limiting) are currently duplicated across services that should be centralized in one place?


## 0. Why Not Just nginx? (5 minutes)

The nginx config from M31 does basic path-based routing. Here is what it cannot do:

```
What nginx does well:              What you also need:
✅ Route /api/payments → svc       ❌ Validate JWT and extract user info
✅ Load balance                     ❌ Rate limit per user (not per IP)
✅ SSL termination                  ❌ Inject correlation ID into every request
✅ Static file serving              ❌ Aggregate responses from multiple services
                                    ❌ Transform request/response shapes
                                    ❌ Circuit breaking per upstream service
```

You could add Lua scripting to nginx (OpenResty) or use a dedicated gateway like Kong, Envoy, or AWS API Gateway. For TicketPulse, we will build a lightweight Express gateway. This teaches you what a gateway does, not how to configure someone else's.

In production, use a battle-tested gateway (Kong, Envoy, Traefik). Building your own is for learning.

---

## 1. Build: The API Gateway (20 minutes)

### 🛠️ Create the Gateway Service

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what the gateway needs to do before forwarding: authenticate the user, attach a correlation ID, check rate limits. What order should these run in?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use Express middleware layers in order: strip headers, correlation ID, logging, auth, rate limiting. Use http-proxy-middleware for routing to backend services.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The BFF aggregates data from multiple internal services into a single mobile-optimized response. Use Promise.all for parallel fetches and transform the result to include only mobile-relevant fields.
</details>


```bash
mkdir -p services/gateway/src
```

```json
// services/gateway/package.json
{
  "name": "@ticketpulse/gateway",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "http-proxy-middleware": "^3.0.0",
    "jsonwebtoken": "^9.0.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "@types/express": "^4.17.0",
    "@types/jsonwebtoken": "^9.0.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.0",
    "typescript": "^5.3.0"
  }
}
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

### Middleware: Correlation ID

Every request gets a unique ID that flows through every service. When something fails in the payment service, you search logs for this ID and see the entire request path.

```typescript
// services/gateway/src/middleware/correlationId.ts

import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';

export function correlationId(req: Request, res: Response, next: NextFunction): void {
  // Use existing correlation ID if provided (e.g., from a load balancer)
  const id = (req.headers['x-correlation-id'] as string) || uuidv4();

  // Set it on the request for downstream middleware
  req.headers['x-correlation-id'] = id;

  // Set it on the response so the client can reference it in bug reports
  res.setHeader('x-correlation-id', id);

  next();
}
```

### Middleware: Request Logging

```typescript
// services/gateway/src/middleware/requestLogger.ts

import { Request, Response, NextFunction } from 'express';

export function requestLogger(req: Request, res: Response, next: NextFunction): void {
  const startTime = Date.now();
  const correlationId = req.headers['x-correlation-id'];

  // Log when request comes in
  console.log(JSON.stringify({
    level: 'info',
    type: 'request_start',
    correlationId,
    method: req.method,
    path: req.path,
    userAgent: req.headers['user-agent'],
    ip: req.ip,
    timestamp: new Date().toISOString(),
  }));

  // Log when response is sent
  res.on('finish', () => {
    const duration = Date.now() - startTime;
    console.log(JSON.stringify({
      level: 'info',
      type: 'request_end',
      correlationId,
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      durationMs: duration,
      timestamp: new Date().toISOString(),
    }));
  });

  next();
}
```

### Middleware: JWT Authentication

Validate the token once at the gateway. Pass the decoded user info to downstream services via headers.

```typescript
// services/gateway/src/middleware/auth.ts

import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key';

// Paths that do NOT require authentication
const PUBLIC_PATHS = [
  '/health',
  '/api/auth/login',
  '/api/auth/register',
  '/api/events',  // Public event listing
];

function isPublicPath(path: string): boolean {
  return PUBLIC_PATHS.some(p => path === p || path.startsWith(p + '/'));
}

export function authenticate(req: Request, res: Response, next: NextFunction): void {
  // Skip auth for public paths
  if (isPublicPath(req.path)) {
    return next();
  }

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({
      error: 'UNAUTHORIZED',
      message: 'Missing or invalid Authorization header',
      correlationId: req.headers['x-correlation-id'],
    });
    return;
  }

  const token = authHeader.substring(7);

  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { userId: string; email: string; role: string };

    // Pass user info to downstream services via headers
    // Services trust these headers because they come from the gateway
    req.headers['x-user-id'] = decoded.userId;
    req.headers['x-user-email'] = decoded.email;
    req.headers['x-user-role'] = decoded.role;

    next();
  } catch (err) {
    res.status(401).json({
      error: 'UNAUTHORIZED',
      message: 'Invalid or expired token',
      correlationId: req.headers['x-correlation-id'],
    });
  }
}
```

**Important security note:** Downstream services must only accept `x-user-id` headers from the gateway, not from external clients. The gateway strips any incoming `x-user-*` headers before processing.

### Middleware: Rate Limiting

```typescript
// services/gateway/src/middleware/rateLimiter.ts

import { Request, Response, NextFunction } from 'express';

// Simple in-memory rate limiter (in production: use Redis)
const windows: Map<string, { count: number; resetAt: number }> = new Map();

interface RateLimitConfig {
  windowMs: number;    // Time window in milliseconds
  maxRequests: number; // Max requests per window
}

const RATE_LIMITS: Record<string, RateLimitConfig> = {
  default: { windowMs: 60_000, maxRequests: 100 },     // 100 req/min
  purchase: { windowMs: 60_000, maxRequests: 10 },      // 10 purchases/min (stricter)
  auth: { windowMs: 300_000, maxRequests: 20 },          // 20 auth attempts/5min
};

function getLimit(path: string, method: string): RateLimitConfig {
  if (path.includes('/tickets') && method === 'POST') return RATE_LIMITS.purchase;
  if (path.includes('/auth')) return RATE_LIMITS.auth;
  return RATE_LIMITS.default;
}

export function rateLimiter(req: Request, res: Response, next: NextFunction): void {
  const userId = (req.headers['x-user-id'] as string) || req.ip || 'anonymous';
  const limit = getLimit(req.path, req.method);
  const key = `${userId}:${req.path}`;
  const now = Date.now();

  let window = windows.get(key);

  if (!window || now > window.resetAt) {
    window = { count: 0, resetAt: now + limit.windowMs };
    windows.set(key, window);
  }

  window.count++;

  // Set rate limit headers
  res.setHeader('X-RateLimit-Limit', limit.maxRequests);
  res.setHeader('X-RateLimit-Remaining', Math.max(0, limit.maxRequests - window.count));
  res.setHeader('X-RateLimit-Reset', new Date(window.resetAt).toISOString());

  if (window.count > limit.maxRequests) {
    console.log(JSON.stringify({
      level: 'warn',
      type: 'rate_limited',
      correlationId: req.headers['x-correlation-id'],
      userId,
      path: req.path,
    }));

    res.status(429).json({
      error: 'RATE_LIMITED',
      message: 'Too many requests. Please try again later.',
      retryAfter: Math.ceil((window.resetAt - now) / 1000),
      correlationId: req.headers['x-correlation-id'],
    });
    return;
  }

  next();
}
```

### The Gateway Server

```typescript
// services/gateway/src/server.ts

import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { correlationId } from './middleware/correlationId';
import { requestLogger } from './middleware/requestLogger';
import { authenticate } from './middleware/auth';
import { rateLimiter } from './middleware/rateLimiter';

const app = express();
const PORT = process.env.PORT || 8080;

// Service URLs
const MONOLITH_URL = process.env.MONOLITH_URL || 'http://localhost:3000';
const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://localhost:3001';
const EVENT_SERVICE_URL = process.env.EVENT_SERVICE_URL || MONOLITH_URL; // Still in monolith

// --- Cross-cutting middleware (order matters) ---

// 1. Strip any incoming x-user-* headers (security)
app.use((req, res, next) => {
  delete req.headers['x-user-id'];
  delete req.headers['x-user-email'];
  delete req.headers['x-user-role'];
  next();
});

// 2. Correlation ID
app.use(correlationId);

// 3. Request logging
app.use(requestLogger);

// 4. Authentication
app.use(authenticate);

// 5. Rate limiting (after auth, so we can rate limit per user)
app.use(rateLimiter);

// --- Health check ---
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'gateway',
    timestamp: new Date().toISOString(),
  });
});

// --- Route definitions ---

// Payment service routes
app.use('/api/payments', createProxyMiddleware({
  target: PAYMENT_SERVICE_URL,
  changeOrigin: true,
  timeout: 10000,
  proxyTimeout: 10000,
  on: {
    proxyReq: (proxyReq, req) => {
      // Forward correlation ID and user info
      const correlationId = (req as any).headers['x-correlation-id'];
      if (correlationId) proxyReq.setHeader('x-correlation-id', correlationId);

      const userId = (req as any).headers['x-user-id'];
      if (userId) proxyReq.setHeader('x-user-id', userId);
    },
    error: (err, req, res) => {
      console.error(JSON.stringify({
        level: 'error',
        type: 'proxy_error',
        target: 'payment-service',
        correlationId: (req as any).headers['x-correlation-id'],
        error: err.message,
      }));

      (res as any).status(502).json({
        error: 'SERVICE_UNAVAILABLE',
        message: 'Payment service is currently unavailable',
        correlationId: (req as any).headers['x-correlation-id'],
      });
    },
  },
}));

// Event routes (still in monolith for now)
app.use('/api/events', createProxyMiddleware({
  target: EVENT_SERVICE_URL,
  changeOrigin: true,
  timeout: 10000,
  on: {
    proxyReq: (proxyReq, req) => {
      const correlationId = (req as any).headers['x-correlation-id'];
      if (correlationId) proxyReq.setHeader('x-correlation-id', correlationId);

      const userId = (req as any).headers['x-user-id'];
      if (userId) proxyReq.setHeader('x-user-id', userId);
    },
  },
}));

// Order routes (still in monolith for now)
app.use('/api/orders', createProxyMiddleware({
  target: MONOLITH_URL,
  changeOrigin: true,
  timeout: 10000,
  on: {
    proxyReq: (proxyReq, req) => {
      const correlationId = (req as any).headers['x-correlation-id'];
      if (correlationId) proxyReq.setHeader('x-correlation-id', correlationId);

      const userId = (req as any).headers['x-user-id'];
      if (userId) proxyReq.setHeader('x-user-id', userId);
    },
  },
}));

// Auth routes
app.use('/api/auth', createProxyMiddleware({
  target: MONOLITH_URL,
  changeOrigin: true,
}));

// Catch-all: everything else goes to the monolith
app.use('/', createProxyMiddleware({
  target: MONOLITH_URL,
  changeOrigin: true,
}));

app.listen(PORT, () => {
  console.log(`[gateway] Running on http://localhost:${PORT}`);
  console.log(`[gateway] Routes:`);
  console.log(`  /api/payments  → ${PAYMENT_SERVICE_URL}`);
  console.log(`  /api/events    → ${EVENT_SERVICE_URL}`);
  console.log(`  /api/orders    → ${MONOLITH_URL}`);
  console.log(`  /*             → ${MONOLITH_URL}`);
});
```

### Dockerfile and Docker Compose

```dockerfile
# services/gateway/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY tsconfig.json ./
COPY src/ ./src/
RUN npm run build
RUN npm ci --production && npm cache clean --force
EXPOSE 8080
CMD ["node", "dist/server.js"]
```

```yaml
# docker-compose.yml — replace the nginx gateway

  gateway:
    build:
      context: ./services/gateway
      dockerfile: Dockerfile
    container_name: ticketpulse-gateway
    ports:
      - "8080:8080"
    environment:
      PORT: 8080
      MONOLITH_URL: http://monolith:3000
      PAYMENT_SERVICE_URL: http://payment-service:3001
      JWT_SECRET: your-secret-key
    depends_on:
      - monolith
      - payment-service
```


<details>
<summary>💡 Hint 1: Direction</summary>
The gateway is an Express server that applies middleware in a specific order: strip external headers, add correlation ID, log, authenticate, rate limit, then proxy.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `http-proxy-middleware` for proxying and `jsonwebtoken` for JWT validation. Create separate middleware files for each concern. The order of `app.use()` calls determines the processing pipeline.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Security critical: delete all incoming `x-user-*` headers first to prevent identity spoofing. After JWT validation, set `x-user-id` and `x-user-email` headers for downstream services. Use different rate limit configs for purchases (10/min) versus general reads (100/min).
</details>

---

## 2. Try It: Gateway in Action (10 minutes)

### 🔍 Deploy

```bash
docker compose up -d --build gateway
```

### Test Routing

```bash
# Health check
curl -s http://localhost:8080/health | jq .

# Public endpoint (no auth required) — routed to monolith
curl -s http://localhost:8080/api/events | jq .

# Protected endpoint without token — should get 401
curl -s http://localhost:8080/api/orders | jq .
# Expected: {"error": "UNAUTHORIZED", "message": "Missing or invalid Authorization header"}

# Get a token first
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "password"}' | jq -r '.token')

# Protected endpoint with token — routed to monolith
curl -s http://localhost:8080/api/orders \
  -H "Authorization: Bearer $TOKEN" | jq .

# Payment endpoint — routed to payment service
curl -s -X POST http://localhost:8080/api/payments \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"orderId": "test-1", "amountInCents": 15000, "paymentMethod": "tok_visa"}' | jq .
```

### Test Rate Limiting

```bash
# Hammer the purchase endpoint (limit: 10/min)
for i in $(seq 1 15); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8080/api/events/1/tickets \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"test${i}@example.com\", \"paymentMethod\": \"tok_visa\"}")
  echo "Request $i: HTTP $STATUS"
done
```

Requests 1-10 should return 201 (or the service's normal response). Requests 11-15 should return 429 (rate limited).

### 📊 Observe: Gateway Logs

```bash
docker compose logs -f gateway
```

You should see structured JSON logs for every request:

```json
{"level":"info","type":"request_start","correlationId":"abc-123","method":"POST","path":"/api/payments"}
{"level":"info","type":"request_end","correlationId":"abc-123","method":"POST","path":"/api/payments","statusCode":201,"durationMs":187}
```

Check that the correlation ID appears in both the gateway logs and the downstream service logs. This is how you trace a request across services.

```bash
# Check that the payment service received the correlation ID
docker compose logs payment-service | grep "abc-123"
```

---

## 3. Design: Backend for Frontend (BFF) (10 minutes)

### 📐 The Problem

<details>
<summary>💡 Hint 1: Direction</summary>
The web app downloads 5KB per event (full descriptions, artist bios, venue maps). The mobile app only needs ~500 bytes (title, date, venue city, lowest price, availability status, thumbnail). Both hit the same generic API.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create a `GET /api/mobile/events` endpoint in the gateway that fetches from the event service and availability service in parallel using `Promise.all()`, then transforms the combined data into a mobile-optimized shape.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Compute availability status from remaining percentage: >20% = "available", >0% = "few_left", 0% = "sold_out". Truncate descriptions to 200 chars. Append image size params for thumbnails: `?w=200&h=200&fit=crop`. Build a Map from the availability response for O(1) lookups.
</details>


TicketPulse has two clients:
- **Web app** — large screen, fast connection, needs detailed event pages with full descriptions, artist bios, venue maps, and reviews
- **Mobile app** — small screen, potentially slow connection, needs a compact event card with title, date, price, and availability

With the current API, both clients call the same endpoints. The mobile app downloads 5KB of event description text it never shows. The web app makes 4 separate calls (event, artists, venue, availability) that could be one.

### The BFF Pattern

Each client gets its own backend that serves exactly the data it needs.

```
                    ┌─────────────┐   ┌──────────────┐
                    │  Web App    │   │  Mobile App  │
                    └──────┬──────┘   └──────┬───────┘
                           │                  │
                    ┌──────▼──────┐   ┌──────▼───────┐
                    │  Web BFF    │   │  Mobile BFF  │
                    │  (detailed) │   │  (compact)   │
                    └──────┬──────┘   └──────┬───────┘
                           │                  │
                           └────────┬─────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Event Service   Payment Service   User Service
```

### 📐 Design Exercise: Mobile BFF for TicketPulse

The mobile app's home screen shows a list of upcoming events. Each card needs:
- Event title
- Event date and time
- Venue name and city
- Lowest ticket price
- Availability status (available, few left, sold out)
- Thumbnail image URL

**Design the mobile BFF endpoint.** Answer these questions before looking at the implementation:

1. What is the URL and HTTP method?
2. Which services does the BFF call internally?
3. What does the response look like?
4. How do you minimize latency (parallel calls)?


<details>
<summary>💡 Hint 1: Direction</summary>
Design backwards from the mobile UI. The home screen card needs: title, date, venue name/city, lowest price, availability status, and a thumbnail. That is far less data than the full API returns.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
The BFF endpoint should make parallel calls (Promise.all) to the event service and availability service, then transform the combined data into a mobile-optimized shape — no full descriptions, thumbnail URLs, and a simple availability enum.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
`GET /api/mobile/events` returns ~500 bytes per event instead of ~5KB. Build a Map from the availability response for O(1) lookups. Compute availability status from remaining percentage: >20% = "available", >0% = "few_left", 0% = "sold_out". Append image size params for thumbnails.
</details>

### 🤔 Pause: Write your design.

---

### One Possible Implementation

```typescript
// services/gateway/src/bff/mobile.ts
// (The BFF can live in the gateway or as a separate service)

import { Router, Request, Response } from 'express';

const router = Router();

const EVENT_SERVICE_URL = process.env.EVENT_SERVICE_URL || 'http://localhost:3000';

// Mobile home screen: upcoming events with compact data
router.get('/api/mobile/events', async (req: Request, res: Response) => {
  const correlationId = req.headers['x-correlation-id'];

  try {
    // Fetch events and availability in parallel
    const [eventsResponse, availabilityResponse] = await Promise.all([
      fetch(`${EVENT_SERVICE_URL}/api/events?status=published&limit=20`, {
        headers: { 'x-correlation-id': correlationId as string },
      }),
      fetch(`${EVENT_SERVICE_URL}/api/events/availability?limit=20`, {
        headers: { 'x-correlation-id': correlationId as string },
      }),
    ]);

    const events = await eventsResponse.json();
    const availability = await availabilityResponse.json();

    const availabilityMap = new Map(
      availability.data.map((a: any) => [a.eventId, a])
    );

    // Transform into mobile-friendly shape
    const mobileEvents = events.data.map((event: any) => {
      const avail = availabilityMap.get(event.id);
      const remainingPct = avail ? (avail.remaining / avail.capacity) * 100 : 100;

      return {
        id: event.id,
        title: event.title,
        // No description — mobile doesn't show it
        date: event.date,
        venue: {
          name: event.venue?.name,
          city: event.venue?.city,
          // No address, no full venue details
        },
        lowestPrice: avail?.lowestPriceInCents || null,
        availability: remainingPct > 20 ? 'available'
                    : remainingPct > 0 ? 'few_left'
                    : 'sold_out',
        thumbnailUrl: event.imageUrl
          ? `${event.imageUrl}?w=200&h=200&fit=crop`  // Mobile-optimized thumbnail
          : null,
      };
    });

    res.json({ data: mobileEvents });

  } catch (err) {
    console.error(`[mobile-bff] Error:`, (err as Error).message);
    res.status(502).json({
      error: 'SERVICE_ERROR',
      message: 'Unable to load events',
      correlationId,
    });
  }
});

// Mobile event detail: compact version
router.get('/api/mobile/events/:id', async (req: Request, res: Response) => {
  const correlationId = req.headers['x-correlation-id'];
  const eventId = req.params.id;

  try {
    // Parallel calls to event service and availability
    const [eventRes, availRes, pricesRes] = await Promise.all([
      fetch(`${EVENT_SERVICE_URL}/api/events/${eventId}`, {
        headers: { 'x-correlation-id': correlationId as string },
      }),
      fetch(`${EVENT_SERVICE_URL}/api/events/${eventId}/availability`, {
        headers: { 'x-correlation-id': correlationId as string },
      }),
      fetch(`${EVENT_SERVICE_URL}/api/events/${eventId}/prices`, {
        headers: { 'x-correlation-id': correlationId as string },
      }),
    ]);

    const event = await eventRes.json();
    const avail = await availRes.json();
    const prices = await pricesRes.json();

    // Aggregate into a single mobile-optimized response
    res.json({
      data: {
        id: event.data.id,
        title: event.data.title,
        description: event.data.description?.substring(0, 200), // Truncated for mobile
        date: event.data.date,
        venue: {
          name: event.data.venue?.name,
          city: event.data.venue?.city,
        },
        availability: avail.data,
        prices: prices.data.tiers.map((t: any) => ({
          tier: t.name,
          priceInCents: t.priceInCents,
          available: t.remaining > 0,
        })),
        imageUrl: event.data.imageUrl
          ? `${event.data.imageUrl}?w=400&h=300&fit=crop`
          : null,
      },
    });

  } catch (err) {
    console.error(`[mobile-bff] Error:`, (err as Error).message);
    res.status(502).json({
      error: 'SERVICE_ERROR',
      message: 'Unable to load event details',
      correlationId,
    });
  }
});

export default router;
```

### Mount the BFF in the Gateway

```typescript
// services/gateway/src/server.ts — add mobile BFF routes

import mobileBff from './bff/mobile';

// Mobile BFF routes (before the catch-all proxy)
app.use(mobileBff);
```

### The Key Differences: Web vs Mobile

| Aspect | Generic API | Mobile BFF |
|--------|-------------|------------|
| Event list response size | ~5KB per event | ~500 bytes per event |
| API calls per screen | 3-4 (events, venue, availability, prices) | 1 (aggregated) |
| Image URLs | Full resolution | Thumbnail (200x200) |
| Description | Full HTML/markdown | First 200 chars |
| Venue details | Full address, map coords, parking info | Name and city only |

The mobile app makes one call and gets everything it needs. The web app can use the full API or its own BFF with richer data.

---

## 4. Reflect (5 minutes)

### 🤔 Questions

1. **Where should the BFF live?** In the gateway? As a separate service? As part of the frontend deployment? What are the trade-offs?

2. **What happens when you have 5 frontend clients?** (Web, iOS, Android, smart TV, third-party widget) Do you build 5 BFFs? How do you prevent duplication?

3. **The gateway is now a single point of failure.** If it goes down, everything is down. How would you make it highly available?

4. **Should the gateway be "smart" or "dumb"?** Smart gateways (transforming data, aggregating responses) vs dumb gateways (pure proxy + cross-cutting concerns). Which fits TicketPulse today?

### Design Tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| **BFF in the gateway** | Simple, one deployment | Gateway gets complex, mixes concerns |
| **BFF as separate service** | Clean separation, independent scaling | Another service to deploy and monitor |
| **BFF in the frontend repo** | Frontend team owns it, fast iteration | Blurs the line between frontend and backend |
| **GraphQL instead of BFF** | One API, client specifies data needs | Complexity, N+1 resolver problem, caching harder |

---

> **What did you notice?** With the gateway handling auth and rate limiting, downstream services got simpler. But the gateway itself became a single point of failure. How would you make it resilient?

## 5. Checkpoint

After this module, TicketPulse should have:

- [ ] An Express-based API gateway replacing the nginx proxy
- [ ] Correlation ID middleware that attaches a unique ID to every request
- [ ] JWT authentication middleware that validates tokens and passes user info downstream
- [ ] Rate limiting middleware with per-endpoint configuration
- [ ] Structured JSON request logging with correlation IDs
- [ ] Routes configured: `/api/payments` -> payment service, `/api/events` -> event service, `/api/orders` -> monolith
- [ ] A mobile BFF endpoint that aggregates data from multiple services into mobile-optimized responses
- [ ] Downstream services receiving correlation IDs and user info via headers
- [ ] Understanding of BFF pattern and when to use it

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **API Gateway** | Single entry point for all external clients. Handles routing, auth, rate limiting, logging, and other cross-cutting concerns. |
| **Correlation ID** | A unique identifier attached to every request that flows through all services. Essential for distributed tracing and debugging. |
| **Gateway auth** | Validate authentication once at the gateway. Pass user info to downstream services via trusted headers. |
| **Rate limiting** | Protect services from abuse. Different limits for different endpoints (stricter for purchases, looser for reads). |
| **BFF (Backend for Frontend)** | A dedicated backend per client type. Each BFF serves exactly the data its client needs, aggregated from multiple services. |
| **Smart vs dumb gateway** | Dumb gateways proxy and add cross-cutting concerns. Smart gateways aggregate and transform. Start dumb, add intelligence only when needed. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **API Gateway** | A server that sits between clients and backend services. Routes requests, handles cross-cutting concerns (auth, rate limiting, logging). |
| **Reverse proxy** | A server that forwards client requests to backend servers. The client does not know which backend handled its request. |
| **Correlation ID** | A unique identifier assigned to a request at the gateway and propagated through all downstream service calls. Used for distributed tracing. |
| **Rate limiting** | Restricting the number of requests a client can make in a given time window. Protects services from abuse and overload. |
| **BFF (Backend for Frontend)** | A pattern where each type of frontend client (web, mobile, IoT) has its own dedicated backend that serves optimized responses. |
| **Cross-cutting concern** | A concern that affects multiple services: authentication, logging, rate limiting, error handling. Belongs in the gateway, not in every service. |
| **502 Bad Gateway** | HTTP status code indicating the gateway received an invalid response from an upstream service. |
| **429 Too Many Requests** | HTTP status code indicating the client has been rate limited. The response should include a Retry-After header. |

---

---

## What's Next

In **PostgreSQL Internals** (L2-M37), you'll look under the hood at how PostgreSQL actually works — MVCC, WAL, vacuum, and the machinery that keeps TicketPulse's data safe.

---

## Further Reading

- [Kong Gateway](https://docs.konghq.com/) — Production-grade API gateway with plugin ecosystem
- [Envoy Proxy](https://www.envoyproxy.io/) — High-performance proxy used in service meshes (Istio)
- Sam Newman, *Building Microservices*, Chapter 7 (API Gateway and BFF patterns)
- Chapter 3 of the 100x Engineer Guide: Section 3 (API Gateway Pattern, BFF)
- Chapter 25 of the 100x Engineer Guide: REST API Design (and Ch 25b: API Operations & DX)

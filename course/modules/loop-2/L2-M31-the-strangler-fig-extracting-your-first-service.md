# L2-M31: The Strangler Fig — Extracting Your First Service

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 75 min | 🟢 Core | Prerequisites: Loop 1 complete (TicketPulse monolith with Postgres, Redis, RabbitMQ, JWT auth, CI/CD, tests)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

TicketPulse is a working monolith. It has authentication, ticket purchasing, payment processing, notifications, search, and analytics — all in one codebase, one process, one deployment. It works. Customers are happy.

But the team is growing. Deployments take longer. A bug in the search indexer crashed the payment flow last week. The notifications code changes three times as often as the payment code, and every notification deploy requires re-testing payments. The monolith is becoming a liability.

You are not going to rewrite TicketPulse from scratch. Rewrites fail. Instead, you are going to use the **Strangler Fig pattern** — incrementally extracting pieces of the monolith into independent services while keeping everything running. The old monolith shrinks over time as the new services grow around it, like a strangler fig vine growing around a host tree.

By the end of this module, TicketPulse will have two running services — the original monolith (slightly smaller) and a new Payments service — both accessible through a single API gateway. From the client's perspective, nothing changed. From yours, everything did.

**You will have both services running and communicating within ten minutes.**

---

## 0. The Strangler Fig Pattern (5 minutes)

The pattern is simple:

```
Before:                              After:
┌─────────────────────┐             ┌──────────────┐
│     Monolith        │             │   Gateway    │
│                     │             └──┬───────┬───┘
│  Auth               │                │       │
│  Events             │                ▼       ▼
│  Tickets        ────────────→  ┌─────────┐ ┌──────────┐
│  Payments           │          │Monolith │ │ Payment  │
│  Notifications      │          │(smaller)│ │ Service  │
│  Search             │          │         │ │          │
│  Analytics          │          │ Auth    │ │ Charges  │
│                     │          │ Events  │ │ Refunds  │
└─────────────────────┘          │ Tickets │ │ Ledger   │
                                 │ Notif.  │ └──────────┘
                                 │ Search  │
                                 │ Analyt. │
                                 └─────────┘
```

The key rules:

1. **Never rewrite.** Extract one piece at a time.
2. **The client sees no change.** URLs, response shapes, authentication — all identical.
3. **Route at the edge.** A proxy or gateway decides which service handles each request.
4. **Both old and new code run simultaneously.** You can roll back by changing the routing.
5. **The monolith shrinks.** Once the new service is stable, delete the old code from the monolith.

Martin Fowler named this after the strangler fig tree, which grows around a host tree and eventually replaces it entirely. Your new services grow around the monolith until the monolith is gone.

---

## 1. Design: Which Service to Extract First? (10 minutes)

### 📐 Design Exercise

This is your first real architectural decision in Loop 2. No one is telling you the answer. You need to evaluate options and justify your choice.

Here are three candidates. For each, consider:
- **Complexity of extraction** — how many dependencies does this code have on the rest of the monolith?
- **Blast radius** — if the extraction goes wrong, what breaks?
- **Value of independence** — what do you gain by making this a separate service?
- **Data ownership** — how cleanly can you separate the data?

#### Candidate A: Notifications Service

```
Characteristics:
- Consumes events from RabbitMQ (already async from M22)
- No synchronous callers — nothing waits for a notification response
- Simple data: notification templates, delivery logs
- External dependency: email provider (SendGrid/SES)
- Change frequency: HIGH (marketing wants to change email templates weekly)
```

#### Candidate B: Payments Service

```
Characteristics:
- Called synchronously during ticket purchase
- Clear data boundary: payments, refunds, ledger entries
- External dependency: Stripe/payment processor
- Requires strong consistency (money cannot be lost)
- Change frequency: LOW (payment logic rarely changes)
- Compliance: PCI-DSS may require isolation
```

#### Candidate C: Search Service

```
Characteristics:
- Read-only — never writes to the core database
- Could use a different data store (Elasticsearch)
- No transactional coupling to other features
- Performance profile differs from CRUD operations
- Change frequency: MEDIUM
```

### 🤔 Pause and Decide

Before reading on, pick one. Write down your choice and two reasons why.

---

### The Analysis

All three are reasonable choices. Here is how experienced engineers evaluate them:

| Criteria | Notifications | Payments | Search |
|----------|--------------|----------|--------|
| Coupling to monolith | Very low (async) | Medium (sync call) | Low (read-only) |
| Data separation | Clean | Clean | Clean |
| Risk if extraction fails | Low (emails delayed) | High (purchases break) | Medium (search broken) |
| Value of independence | Medium | High (compliance, scaling) | Medium |
| Learning opportunity | Low | High | Medium |

**Notifications** is the easiest extraction — it is already async via RabbitMQ. But it teaches you the least about the hard problems of microservices (synchronous communication, failure handling, data consistency).

**Search** is a good candidate, but it is read-only, so you do not face the write-side challenges.

**Payments** is the most instructive choice. It forces you to deal with synchronous service-to-service communication, failure handling, and data consistency — the exact problems you will face in every future extraction. It also has a clear business justification: PCI compliance, independent scaling during ticket rushes, and isolated deployment.

We will extract Payments. If you chose Notifications, that is a perfectly valid production choice — just know that you would face the hard problems later.

---

## 2. Build: The Payments Service (20 minutes)

### 🛠️ Create the Service Directory

```bash
# From the TicketPulse root
mkdir -p services/payment-service/src
cd services/payment-service
```

### Initialize the Service

```json
// services/payment-service/package.json
{
  "name": "@ticketpulse/payment-service",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js",
    "test": "jest"
  },
  "dependencies": {
    "express": "^4.18.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "@types/express": "^4.17.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.0",
    "typescript": "^5.3.0",
    "jest": "^29.0.0",
    "@types/jest": "^29.0.0",
    "ts-jest": "^29.0.0"
  }
}
```

```json
// services/payment-service/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

### Move Payment Logic Out of the Monolith

Look at the payment-related code in your monolith. You need to identify:
- The payment processing function
- The refund logic
- The payment data models
- Any payment-specific validation

Here is the extracted service:

```typescript
// services/payment-service/src/server.ts

import express from 'express';
import { v4 as uuidv4 } from 'uuid';

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;

// In-memory store for now (will be its own DB in M35)
const payments: Map<string, Payment> = new Map();

interface Payment {
  id: string;
  orderId: string;
  amountInCents: number;
  currency: string;
  status: 'pending' | 'completed' | 'failed' | 'refunded';
  paymentMethod: string;
  createdAt: string;
  updatedAt: string;
}

// Health check — every service needs one
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'payment-service', timestamp: new Date().toISOString() });
});

// Process a payment
app.post('/api/payments', async (req, res) => {
  const { orderId, amountInCents, currency, paymentMethod } = req.body;

  console.log(`[payment-service] Processing payment for order ${orderId}: $${(amountInCents / 100).toFixed(2)}`);

  // Validate input
  if (!orderId || !amountInCents || !paymentMethod) {
    return res.status(400).json({
      error: 'INVALID_INPUT',
      message: 'orderId, amountInCents, and paymentMethod are required',
    });
  }

  // Idempotency check: if we already processed this order, return the existing payment
  const existing = Array.from(payments.values()).find(p => p.orderId === orderId);
  if (existing) {
    console.log(`[payment-service] Idempotent hit: order ${orderId} already processed`);
    return res.status(200).json({ data: existing });
  }

  // Simulate payment processing (in production: call Stripe, Adyen, etc.)
  const processingTime = 100 + Math.random() * 200;
  await new Promise(resolve => setTimeout(resolve, processingTime));

  // Simulate occasional failures (10% chance)
  if (Math.random() < 0.1) {
    console.log(`[payment-service] Payment failed for order ${orderId}`);
    return res.status(422).json({
      error: 'PAYMENT_FAILED',
      message: 'Payment processor declined the transaction',
    });
  }

  const payment: Payment = {
    id: `pay_${uuidv4()}`,
    orderId,
    amountInCents,
    currency: currency || 'USD',
    status: 'completed',
    paymentMethod,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  payments.set(payment.id, payment);

  console.log(`[payment-service] Payment ${payment.id} completed in ${processingTime.toFixed(0)}ms`);

  res.status(201).json({ data: payment });
});

// Get a payment by ID
app.get('/api/payments/:id', (req, res) => {
  const payment = payments.get(req.params.id);
  if (!payment) {
    return res.status(404).json({ error: 'NOT_FOUND', message: 'Payment not found' });
  }
  res.json({ data: payment });
});

// Refund a payment
app.post('/api/payments/:id/refund', async (req, res) => {
  const payment = payments.get(req.params.id);
  if (!payment) {
    return res.status(404).json({ error: 'NOT_FOUND', message: 'Payment not found' });
  }

  if (payment.status === 'refunded') {
    return res.status(200).json({ data: payment }); // Idempotent
  }

  if (payment.status !== 'completed') {
    return res.status(422).json({
      error: 'INVALID_STATE',
      message: `Cannot refund a payment in status: ${payment.status}`,
    });
  }

  // Simulate refund processing
  await new Promise(resolve => setTimeout(resolve, 150));

  payment.status = 'refunded';
  payment.updatedAt = new Date().toISOString();

  console.log(`[payment-service] Payment ${payment.id} refunded`);

  res.json({ data: payment });
});

app.listen(PORT, () => {
  console.log(`[payment-service] Running on http://localhost:${PORT}`);
});
```

### The Dockerfile

```dockerfile
# services/payment-service/Dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --production=false

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build

# Production: only install production deps
RUN npm ci --production && npm cache clean --force

EXPOSE 3001

CMD ["node", "dist/server.js"]
```

### Update the Monolith to Call the Payment Service

This is the critical step. The monolith's purchase endpoint currently calls its own `processPayment()` function. Now it needs to call the payment service over HTTP.

```typescript
// src/clients/paymentClient.ts (in the monolith)

const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://localhost:3001';

interface PaymentRequest {
  orderId: string;
  amountInCents: number;
  currency: string;
  paymentMethod: string;
}

interface PaymentResponse {
  id: string;
  orderId: string;
  amountInCents: number;
  status: string;
}

export async function processPayment(request: PaymentRequest): Promise<PaymentResponse> {
  const startTime = Date.now();

  try {
    const response = await fetch(`${PAYMENT_SERVICE_URL}/api/payments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    const duration = Date.now() - startTime;

    if (!response.ok) {
      const error = await response.json();
      console.error(`[payment-client] Failed in ${duration}ms:`, error);
      throw new Error(error.message || 'Payment processing failed');
    }

    const result = await response.json();
    console.log(`[payment-client] Payment ${result.data.id} completed in ${duration}ms`);
    return result.data;

  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      // Network error — payment service is unreachable
      throw new Error('Payment service is unavailable');
    }
    throw err;
  }
}
```

Now update the purchase endpoint to use the client:

```typescript
// src/routes/tickets.ts — updated purchase handler

import { processPayment } from '../clients/paymentClient';

async function purchaseTicket(req: Request, res: Response) {
  const ticket = await reserveTicket(req.params.eventId, req.body.email);

  // OLD: const payment = await processPaymentLocally(ticket, req.body.paymentMethod);
  // NEW: call the payment service over HTTP
  const payment = await processPayment({
    orderId: ticket.orderId,
    amountInCents: ticket.priceInCents,
    currency: 'USD',
    paymentMethod: req.body.paymentMethod,
  });

  const order = await createOrder(ticket, payment);

  // ... rest unchanged (publish to queue, etc.)
}
```

### Add the Payment Service to Docker Compose

```yaml
# docker-compose.yml — add the payment service

services:
  # ... existing services (postgres, redis, rabbitmq, monolith) ...

  payment-service:
    build:
      context: ./services/payment-service
      dockerfile: Dockerfile
    container_name: ticketpulse-payment-service
    ports:
      - "3001:3001"
    environment:
      PORT: 3001
      NODE_ENV: development
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3001/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Simple reverse proxy to route traffic
  gateway:
    image: nginx:alpine
    container_name: ticketpulse-gateway
    ports:
      - "8080:80"
    volumes:
      - ./gateway/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - monolith
      - payment-service
```

### The Gateway Configuration

```bash
mkdir -p gateway
```

```nginx
# gateway/nginx.conf

events {
  worker_connections 1024;
}

http {
  upstream monolith {
    server monolith:3000;
  }

  upstream payment_service {
    server payment-service:3001;
  }

  server {
    listen 80;

    # Payment routes go to the payment service
    location /api/payments {
      proxy_pass http://payment_service;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Request-ID $request_id;
    }

    # Everything else goes to the monolith
    location / {
      proxy_pass http://monolith;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Request-ID $request_id;
    }
  }
}
```

---

## 3. Try It: Both Services Running (10 minutes)

### 🔍 Deploy and Verify

```bash
# Build and start everything
docker compose up -d --build

# Wait for services to be healthy
docker compose ps
```

You should see:

```
NAME                           STATUS
ticketpulse-postgres           running
ticketpulse-redis              running
ticketpulse-rabbitmq           running
ticketpulse-monolith           running
ticketpulse-payment-service    running (healthy)
ticketpulse-gateway            running
```

### Test Through the Gateway

```bash
# Health check — payment service directly
curl -s http://localhost:3001/health | jq .

# Health check — through the gateway
curl -s http://localhost:8080/api/payments/health | jq .

# Purchase a ticket — goes through gateway → monolith → payment service
curl -s -X POST http://localhost:8080/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <your-jwt-token>' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}' | jq .
```

### Watch the Logs

Open a second terminal:

```bash
docker compose logs -f monolith payment-service gateway
```

When you purchase a ticket, you should see:

```
monolith           | [purchase] Reserving ticket for event 1
monolith           | [payment-client] Payment pay_abc123 completed in 187ms
monolith           | [purchase] Order created: ord_xyz789
monolith           | [purchase] Response sent in 245ms
payment-service    | [payment-service] Processing payment for order ord_xyz789: $150.00
payment-service    | [payment-service] Payment pay_abc123 completed in 142ms
gateway            | 172.18.0.1 - - "POST /api/events/1/tickets HTTP/1.1" 201
```

The request flows: Client -> Gateway -> Monolith -> Payment Service -> Monolith -> Client.

### 📊 Observe: The Architecture

```
Client
  │
  ▼
Gateway (:8080)
  │
  ├── /api/payments/* ──→ Payment Service (:3001)
  │
  └── /* ──────────────→ Monolith (:3000) ──→ Payment Service (:3001)
                                               (internal HTTP call)
```

Notice something important: the monolith still calls the payment service directly (not through the gateway). The gateway handles external routing. Internal service-to-service calls go direct. This is intentional — adding the gateway to internal calls would add unnecessary latency and a single point of failure.

---

## 4. Debug: New Failure Modes (15 minutes)

### 🐛 What Happens When the Payment Service Is Down?

```bash
# Stop the payment service
docker compose stop payment-service

# Try to buy a ticket
curl -s -X POST http://localhost:8080/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}' | jq .
```

What do you see? The monolith returns a 500 error because the payment service is unreachable. In the monolith logs:

```
monolith | [payment-client] Failed: Payment service is unavailable
monolith | [purchase] Error: Payment service is unavailable
```

This is a problem you **did not have before.** When payments were part of the monolith, a function call could not fail due to a network error. Now it can.

### 🐛 What Happens When the Payment Service Is Slow?

```bash
# Start the payment service again
docker compose start payment-service
```

Now simulate a slow payment service. Add an artificial delay:

```bash
# In services/payment-service/src/server.ts, temporarily add:
# const delay = parseInt(process.env.ARTIFICIAL_DELAY || '0');
# await new Promise(resolve => setTimeout(resolve, delay));

# Or set a higher processing time in docker-compose environment:
# ARTIFICIAL_DELAY: 5000
```

Try purchasing a ticket. The monolith's response time now includes the payment service latency. If the payment service takes 5 seconds, the purchase takes at least 5 seconds.

Before extraction, the payment processing was an in-memory function call taking microseconds to invoke (the actual Stripe call was still slow, but that was always the case). Now there is an additional network round trip: DNS resolution, TCP handshake, HTTP request/response, serialization/deserialization.

### What You Just Discovered

Extracting a service creates new failure modes:

| Failure Mode | Before (Monolith) | After (Microservice) |
|---|---|---|
| Service down | Impossible (same process) | Connection refused |
| Slow service | Impossible (in-memory call) | Timeout, cascading slowness |
| Network partition | Impossible | Both services up but cannot communicate |
| Serialization error | Impossible (typed function call) | JSON parsing failure |
| Version mismatch | Impossible (same deploy) | Service A expects field X, Service B removed it |

You will address these problems in the coming modules (circuit breakers in M49, retries, timeouts, and health checks).

### Quick Fix: Add a Timeout

At minimum, do not let the monolith wait forever:

```typescript
// src/clients/paymentClient.ts — add a timeout

export async function processPayment(request: PaymentRequest): Promise<PaymentResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000); // 5 second timeout

  try {
    const response = await fetch(`${PAYMENT_SERVICE_URL}/api/payments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    // ... rest of handler
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Payment service timed out after 5000ms');
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}
```

---

## 5. Write a Test for the Payment Service (5 minutes)

The payment service is independent — it should have its own tests.

```typescript
// services/payment-service/src/__tests__/payments.test.ts

describe('Payment Service', () => {
  // You decide: what are the critical test cases?
  // Hint: think about the API contract, not the implementation.

  test('should process a valid payment', async () => {
    const response = await fetch('http://localhost:3001/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orderId: 'test-order-1',
        amountInCents: 15000,
        currency: 'USD',
        paymentMethod: 'tok_visa',
      }),
    });

    expect(response.status).toBe(201);
    const body = await response.json();
    expect(body.data.status).toBe('completed');
    expect(body.data.amountInCents).toBe(15000);
  });

  test('should return existing payment for same orderId (idempotency)', async () => {
    // First call
    await fetch('http://localhost:3001/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orderId: 'idempotent-test',
        amountInCents: 5000,
        currency: 'USD',
        paymentMethod: 'tok_visa',
      }),
    });

    // Second call with same orderId
    const response = await fetch('http://localhost:3001/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orderId: 'idempotent-test',
        amountInCents: 5000,
        currency: 'USD',
        paymentMethod: 'tok_visa',
      }),
    });

    expect(response.status).toBe(200); // 200, not 201
  });

  test('should reject invalid input', async () => {
    const response = await fetch('http://localhost:3001/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(400);
  });
});
```

---

## 6. Reflect (5 minutes)

### 🤔 Was This Extraction Worth It?

Write down your answers:

1. **What did we gain?**
   - The payment service can be deployed independently
   - Payment code is isolated — a bug in search cannot crash payments
   - The payment service can scale independently during ticket rushes
   - PCI compliance scope is reduced to one service
   - A different team can own the payment service

2. **What new problems did we create?**
   - Network failures between monolith and payment service
   - Additional operational complexity (two services to deploy, monitor, debug)
   - Latency increased (network round trip for every payment)
   - Distributed debugging is harder (logs are in two places)
   - Version compatibility between services must be managed

3. **When would you NOT extract a service?**
   - When the team is too small to operate multiple services
   - When the code changes together with other code (high coupling)
   - When you do not have the infrastructure (CI/CD per service, centralized logging, health checks)

The honest answer: for a team of three, this extraction probably was not worth it yet. For a team of fifteen with clear domain boundaries, it is essential. Microservices are an organizational scaling strategy as much as a technical one.

---

## 7. Clean Up

```bash
# Leave everything running — you'll use this setup in M32
docker compose ps
```

Your TicketPulse now has two services. The monolith is slightly smaller. The payment service is independent. The gateway routes traffic. And you have a list of new problems to solve.

---

## 8. Checkpoint

After this module, TicketPulse should have:

- [ ] A `services/payment-service/` directory with its own `package.json`, `Dockerfile`, and `tsconfig.json`
- [ ] A running payment service on port 3001 with `/api/payments` endpoints
- [ ] The monolith calling the payment service over HTTP instead of a local function
- [ ] An nginx gateway on port 8080 routing `/api/payments` to the payment service and everything else to the monolith
- [ ] Both services visible in `docker compose ps`
- [ ] A payment client in the monolith with a timeout
- [ ] Understanding of new failure modes introduced by service extraction
- [ ] Tests for the payment service API

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Strangler Fig pattern** | Incrementally extract services from a monolith. Never rewrite. Route traffic at the edge. |
| **Service extraction** | Move code, create an HTTP API, update callers, route traffic. The client sees no change. |
| **Reverse proxy/gateway** | Routes external requests to the correct service. nginx, Traefik, or a custom Express gateway. |
| **New failure modes** | Service extraction introduces network failures, timeouts, serialization errors, and version mismatches. These did not exist in the monolith. |
| **Choosing what to extract** | Evaluate coupling, blast radius, value of independence, and data ownership. Start with something instructive, not just easy. |
| **Idempotency** | Payment endpoints must be idempotent. Duplicate requests return the same result. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Strangler Fig pattern** | A migration strategy where new services gradually replace parts of a monolith while both run simultaneously. Named after the strangler fig tree. |
| **Service extraction** | The process of moving a bounded piece of functionality from a monolith into its own independently deployable service. |
| **Reverse proxy** | A server that sits in front of backend services and forwards requests to the appropriate one based on the URL path or other rules. |
| **API gateway** | A reverse proxy with additional cross-cutting concerns: authentication, rate limiting, logging, request transformation. |
| **Blast radius** | The scope of impact if something goes wrong. A small blast radius means fewer things break. |
| **Idempotent** | An operation that produces the same result regardless of how many times it is called. Critical for payment operations. |

---

## Further Reading

- Martin Fowler, ["Strangler Fig Application"](https://martinfowler.com/bliki/StranglerFigApplication.html) — the original pattern description
- Sam Newman, *Building Microservices*, Chapter 3 (Splitting the Monolith)
- Chapter 3 of the 100x Engineer Guide: Section 6 (Monolith-to-Microservices)

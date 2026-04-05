# L2-M32: Service Communication — REST vs gRPC vs Events

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M31 (Strangler Fig — Extracting Your First Service)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

In M31, you extracted the payment service and connected it to the monolith with a REST call. REST was the obvious choice — you already know it, it works with curl, and browsers understand it. But is it the right choice for internal service-to-service communication?

This module explores three communication patterns through TicketPulse:

1. **REST** (what you have now) — JSON over HTTP/1.1
2. **gRPC** (what you will build) — Protocol Buffers over HTTP/2
3. **Events** (what you will build) — async messages through a broker

By the end, you will have all three patterns running in TicketPulse, real latency numbers comparing REST and gRPC, and a decision framework for choosing between them.

**You will see your first gRPC call succeed within five minutes.**

---

> **Before you continue:** For internal service-to-service calls, what disadvantages does REST have compared to a binary protocol? Think about serialization, type safety, and connection overhead.


## 0. The Problem with REST for Internal Calls (5 minutes)

Look at the payment client from M31:

```typescript
const response = await fetch(`${PAYMENT_SERVICE_URL}/api/payments`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request),
});
const result = await response.json();
```

This works. But consider what is happening under the hood:

1. **Serialization**: The request object is converted to a JSON string. `JSON.stringify()` is surprisingly slow for large objects.
2. **HTTP/1.1**: One request per connection (unless keep-alive is carefully managed). No multiplexing.
3. **Text-based**: JSON is human-readable, which means it is larger on the wire. `{"amountInCents":15000}` is 24 bytes. The same data in protobuf is 3 bytes.
4. **No schema enforcement**: The server could change its response shape and the client would not know until runtime.
5. **No streaming**: If you needed to stream partial results, you would need WebSockets or Server-Sent Events — a completely different protocol.

For external APIs (browsers, mobile apps, third-party developers), REST is the right default. For internal service-to-service calls, gRPC often wins.

---

## 1. Build: gRPC Payment Service (25 minutes)

### Install Dependencies

```bash
# In the payment service
cd services/payment-service
npm install @grpc/grpc-js @grpc/proto-loader

# In the monolith
cd ../../
npm install @grpc/grpc-js @grpc/proto-loader
```

### Define the Protobuf Schema

This is the contract between the monolith and the payment service. It is versioned, type-safe, and generates client/server code.

```bash
mkdir -p proto
```

```protobuf
// proto/payment.proto

syntax = "proto3";

package ticketpulse.payment;

service PaymentService {
  // Process a new payment
  rpc ProcessPayment (ProcessPaymentRequest) returns (ProcessPaymentResponse);

  // Get a payment by ID
  rpc GetPayment (GetPaymentRequest) returns (Payment);

  // Refund a payment
  rpc RefundPayment (RefundPaymentRequest) returns (Payment);
}

message ProcessPaymentRequest {
  string order_id = 1;
  int64 amount_in_cents = 2;
  string currency = 3;
  string payment_method = 4;
}

message ProcessPaymentResponse {
  Payment payment = 1;
}

message GetPaymentRequest {
  string payment_id = 1;
}

message RefundPaymentRequest {
  string payment_id = 1;
  string reason = 2;
}

message Payment {
  string id = 1;
  string order_id = 2;
  int64 amount_in_cents = 3;
  string currency = 4;
  PaymentStatus status = 5;
  string payment_method = 6;
  string created_at = 7;
  string updated_at = 8;
}

enum PaymentStatus {
  PAYMENT_STATUS_UNSPECIFIED = 0;
  PAYMENT_STATUS_PENDING = 1;
  PAYMENT_STATUS_COMPLETED = 2;
  PAYMENT_STATUS_FAILED = 3;
  PAYMENT_STATUS_REFUNDED = 4;
}
```

### 🤔 Pause: Read the Proto File

Before writing any code, notice what the `.proto` file gives you:

- **Explicit types**: `int64`, not "a number that might be a string sometimes"
- **Field numbers**: `= 1`, `= 2` — these are the wire identifiers, not the names. You can rename fields without breaking compatibility.
- **Enums**: Payment status is a closed set, not a magic string
- **Service definition**: The RPC methods, their inputs, and their outputs are all defined in one place

This is the contract. Both sides generate code from it. If either side breaks the contract, it fails at build time, not in production at 3am.

### Implement the gRPC Server

```typescript
// services/payment-service/src/grpcServer.ts

import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

const PROTO_PATH = path.resolve(__dirname, '../../../proto/payment.proto');
const GRPC_PORT = process.env.GRPC_PORT || '50051';

// Load the proto definition
const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,       // Convert snake_case to camelCase
  longs: String,         // Represent int64 as strings (JS numbers lose precision above 2^53)
  enums: String,         // Represent enums as strings
  defaults: true,
  oneofs: true,
});

const proto = grpc.loadPackageDefinition(packageDefinition) as any;

// In-memory store (shared with REST for now)
const payments: Map<string, any> = new Map();

// RPC implementations
function processPayment(
  call: grpc.ServerUnaryCall<any, any>,
  callback: grpc.sendUnaryData<any>
): void {
  const req = call.request;
  console.log(`[grpc] ProcessPayment for order ${req.orderId}: $${(Number(req.amountInCents) / 100).toFixed(2)}`);

  // Validate
  if (!req.orderId || !req.amountInCents || !req.paymentMethod) {
    return callback({
      code: grpc.status.INVALID_ARGUMENT,
      message: 'orderId, amountInCents, and paymentMethod are required',
    });
  }

  // Idempotency check
  const existing = Array.from(payments.values()).find((p: any) => p.orderId === req.orderId);
  if (existing) {
    console.log(`[grpc] Idempotent hit: order ${req.orderId}`);
    return callback(null, { payment: existing });
  }

  // Simulate processing
  const processingTime = 50 + Math.random() * 100;
  setTimeout(() => {
    const payment = {
      id: `pay_${uuidv4()}`,
      orderId: req.orderId,
      amountInCents: req.amountInCents,
      currency: req.currency || 'USD',
      status: 'PAYMENT_STATUS_COMPLETED',
      paymentMethod: req.paymentMethod,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    payments.set(payment.id, payment);
    console.log(`[grpc] Payment ${payment.id} completed in ${processingTime.toFixed(0)}ms`);

    callback(null, { payment });
  }, processingTime);
}

function getPayment(
  call: grpc.ServerUnaryCall<any, any>,
  callback: grpc.sendUnaryData<any>
): void {
  const payment = payments.get(call.request.paymentId);
  if (!payment) {
    return callback({
      code: grpc.status.NOT_FOUND,
      message: `Payment ${call.request.paymentId} not found`,
    });
  }
  callback(null, payment);
}

function refundPayment(
  call: grpc.ServerUnaryCall<any, any>,
  callback: grpc.sendUnaryData<any>
): void {
  const payment = payments.get(call.request.paymentId);
  if (!payment) {
    return callback({
      code: grpc.status.NOT_FOUND,
      message: `Payment ${call.request.paymentId} not found`,
    });
  }

  if (payment.status === 'PAYMENT_STATUS_REFUNDED') {
    return callback(null, payment); // Idempotent
  }

  payment.status = 'PAYMENT_STATUS_REFUNDED';
  payment.updatedAt = new Date().toISOString();

  console.log(`[grpc] Payment ${payment.id} refunded`);
  callback(null, payment);
}

// Start the gRPC server
export function startGrpcServer(): void {
  const server = new grpc.Server();

  server.addService(proto.ticketpulse.payment.PaymentService.service, {
    processPayment,
    getPayment,
    refundPayment,
  });

  server.bindAsync(
    `0.0.0.0:${GRPC_PORT}`,
    grpc.ServerCredentials.createInsecure(),
    (err, port) => {
      if (err) {
        console.error('[grpc] Failed to start:', err);
        return;
      }
      console.log(`[grpc] Payment service listening on port ${port}`);
    }
  );
}
```

Update the payment service entry point to run both REST and gRPC:

```typescript
// services/payment-service/src/server.ts — add at the bottom, before app.listen

import { startGrpcServer } from './grpcServer';

// Start gRPC server alongside REST
startGrpcServer();
```

Update the Dockerfile to expose the gRPC port:

```dockerfile
# services/payment-service/Dockerfile — add the gRPC port
EXPOSE 3001
EXPOSE 50051
```

### Implement the gRPC Client in the Monolith

```typescript
// src/clients/paymentGrpcClient.ts (in the monolith)

import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';

const PROTO_PATH = path.resolve(__dirname, '../../proto/payment.proto');
const PAYMENT_GRPC_URL = process.env.PAYMENT_GRPC_URL || 'localhost:50051';

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const proto = grpc.loadPackageDefinition(packageDefinition) as any;

// Create a persistent client (reuse the connection)
const client = new proto.ticketpulse.payment.PaymentService(
  PAYMENT_GRPC_URL,
  grpc.credentials.createInsecure(),
);

interface PaymentRequest {
  orderId: string;
  amountInCents: number;
  currency: string;
  paymentMethod: string;
}

export function processPaymentGrpc(request: PaymentRequest): Promise<any> {
  return new Promise((resolve, reject) => {
    const deadline = new Date();
    deadline.setSeconds(deadline.getSeconds() + 5); // 5 second timeout

    client.processPayment(
      {
        orderId: request.orderId,
        amountInCents: request.amountInCents,
        currency: request.currency,
        paymentMethod: request.paymentMethod,
      },
      { deadline },
      (err: grpc.ServiceError | null, response: any) => {
        if (err) {
          console.error(`[grpc-client] Error: ${err.code} - ${err.message}`);
          reject(new Error(`Payment gRPC call failed: ${err.message}`));
          return;
        }
        resolve(response.payment);
      }
    );
  });
}
```

---

## 2. Try It: Compare REST vs gRPC (10 minutes)

### 🔍 Deploy

```bash
docker compose up -d --build
```

Update `docker-compose.yml` to expose the gRPC port:

```yaml
  payment-service:
    # ... existing config ...
    ports:
      - "3001:3001"
      - "50051:50051"
    environment:
      PORT: 3001
      GRPC_PORT: 50051
```

### Test gRPC with grpcurl

```bash
# Install grpcurl (if not installed)
# macOS: brew install grpcurl
# Linux: go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest

# List available services
grpcurl -plaintext localhost:50051 list

# Describe the payment service
grpcurl -plaintext localhost:50051 describe ticketpulse.payment.PaymentService

# Process a payment via gRPC
grpcurl -plaintext -d '{
  "orderId": "grpc-test-001",
  "amountInCents": 15000,
  "currency": "USD",
  "paymentMethod": "tok_visa"
}' localhost:50051 ticketpulse.payment.PaymentService/ProcessPayment
```

### Benchmark: REST vs gRPC

```bash
# REST benchmark — 100 sequential requests
time for i in $(seq 1 100); do
  curl -s -X POST http://localhost:3001/api/payments \
    -H 'Content-Type: application/json' \
    -d "{\"orderId\": \"rest-bench-$i\", \"amountInCents\": 15000, \"currency\": \"USD\", \"paymentMethod\": \"tok_visa\"}" \
    > /dev/null
done

# gRPC benchmark — 100 sequential requests
time for i in $(seq 1 100); do
  grpcurl -plaintext -d "{
    \"orderId\": \"grpc-bench-$i\",
    \"amountInCents\": 15000,
    \"currency\": \"USD\",
    \"paymentMethod\": \"tok_visa\"
  }" localhost:50051 ticketpulse.payment.PaymentService/ProcessPayment \
    > /dev/null
done
```

For a more rigorous benchmark, use `ghz` (a gRPC benchmarking tool) and `wrk` (an HTTP benchmarking tool):

```bash
# Install ghz: brew install ghz (macOS)

# gRPC benchmark with ghz — 1000 requests, 10 concurrent
ghz --insecure \
  --proto proto/payment.proto \
  --call ticketpulse.payment.PaymentService.ProcessPayment \
  -d '{"orderId":"ghz-{{.RequestNumber}}","amountInCents":15000,"currency":"USD","paymentMethod":"tok_visa"}' \
  -n 1000 -c 10 \
  localhost:50051
```

### 📊 Observe: The Numbers

Typical results on a local machine:

| Metric | REST (JSON/HTTP1.1) | gRPC (Protobuf/HTTP2) |
|--------|--------------------|-----------------------|
| Avg latency | ~3-5ms | ~1-2ms |
| p99 latency | ~15ms | ~5ms |
| Payload size (request) | ~120 bytes | ~25 bytes |
| Payload size (response) | ~250 bytes | ~45 bytes |
| Connection reuse | Per-request (without keep-alive) | Multiplexed (single connection) |
| Serialization time | ~0.5ms | ~0.05ms |

The latency difference is modest for a single call. The real wins emerge at scale: smaller payloads mean less bandwidth, multiplexed connections mean fewer TCP handshakes, and binary serialization means less CPU.

---

> **Before you continue:** If the notification service does not serve HTTP requests, how should it learn about new ticket purchases? What communication pattern fits a "react to events" model?


## 3. Build: The Notification Service as an Event Consumer (15 minutes)

Not every service needs an HTTP API. The notification service does not serve requests — it reacts to events. Nobody calls "please send a notification." Instead, things happen (ticket purchased, event updated, order refunded) and notifications are a side effect.

### 🛠️ Build: A Service with No HTTP API

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


```bash
mkdir -p services/notification-service/src
```

```json
// services/notification-service/package.json
{
  "name": "@ticketpulse/notification-service",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node src/consumer.ts",
    "build": "tsc",
    "start": "node dist/consumer.js"
  },
  "dependencies": {
    "amqplib": "^0.10.0"
  },
  "devDependencies": {
    "@types/amqplib": "^0.10.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.0",
    "typescript": "^5.3.0"
  }
}
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```typescript
// services/notification-service/src/consumer.ts

import amqp, { ConsumeMessage } from 'amqplib';

const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://ticketpulse:ticketpulse@localhost:5672';

// This service listens to multiple event types
const BINDINGS = [
  { queue: 'notifications.ticket-purchased', sourceQueue: 'ticket.purchased' },
  { queue: 'notifications.event-updated', sourceQueue: 'event.updated' },
  { queue: 'notifications.order-refunded', sourceQueue: 'order.refunded' },
];

async function handleTicketPurchased(data: any): Promise<void> {
  console.log(`[notification] Sending purchase confirmation to ${data.customerEmail}`);
  console.log(`  Event: ${data.eventTitle}`);
  console.log(`  Amount: $${(data.amountInCents / 100).toFixed(2)}`);

  // In production: call SendGrid, SES, Twilio, Firebase Push, etc.
  await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 500));

  console.log(`[notification] Email sent to ${data.customerEmail}`);
}

async function handleEventUpdated(data: any): Promise<void> {
  console.log(`[notification] Event "${data.eventTitle}" was updated`);
  console.log(`  Notifying ${data.subscriberCount || 0} subscribers`);

  await new Promise(resolve => setTimeout(resolve, 200));
  console.log(`[notification] Subscriber notifications queued`);
}

async function handleOrderRefunded(data: any): Promise<void> {
  console.log(`[notification] Refund confirmation for order ${data.orderId}`);
  console.log(`  Refunding $${(data.amountInCents / 100).toFixed(2)} to ${data.customerEmail}`);

  await new Promise(resolve => setTimeout(resolve, 300));
  console.log(`[notification] Refund email sent`);
}

const handlers: Record<string, (data: any) => Promise<void>> = {
  'TicketPurchased': handleTicketPurchased,
  'EventUpdated': handleEventUpdated,
  'OrderRefunded': handleOrderRefunded,
};

async function start(): Promise<void> {
  console.log('[notification-service] Starting...');

  const connection = await amqp.connect(RABBITMQ_URL);
  const channel = await connection.createChannel();

  // Process one message at a time
  await channel.prefetch(1);

  // Declare our queues
  for (const binding of BINDINGS) {
    await channel.assertQueue(binding.queue, { durable: true });
  }

  // Consume from the main ticket.purchased queue
  // In a real system, you'd use a fanout exchange so multiple services
  // can independently consume the same events
  await channel.consume('ticket.purchased', async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    try {
      const event = JSON.parse(msg.content.toString());
      const handler = handlers[event.type];

      if (handler) {
        await handler(event.payload);
        channel.ack(msg);
      } else {
        console.warn(`[notification-service] Unknown event type: ${event.type}`);
        channel.ack(msg); // Ack unknown events — don't block the queue
      }
    } catch (err) {
      console.error('[notification-service] Error:', (err as Error).message);
      const requeue = !msg.fields.redelivered;
      channel.nack(msg, false, requeue);
    }
  });

  console.log('[notification-service] Waiting for events...');

  process.on('SIGTERM', async () => {
    console.log('[notification-service] Shutting down...');
    await channel.close();
    await connection.close();
    process.exit(0);
  });
}

start().catch(err => {
  console.error('[notification-service] Failed to start:', err);
  process.exit(1);
});
```

```dockerfile
# services/notification-service/Dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --production=false

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build
RUN npm ci --production && npm cache clean --force

CMD ["node", "dist/consumer.js"]
```

Add to docker compose:

```yaml
  notification-service:
    build:
      context: ./services/notification-service
      dockerfile: Dockerfile
    container_name: ticketpulse-notification-service
    environment:
      RABBITMQ_URL: amqp://ticketpulse:ticketpulse@rabbitmq:5672
    depends_on:
      - rabbitmq
    restart: unless-stopped
```


<details>
<summary>💡 Hint 1: Direction</summary>
The notification service has no HTTP API — it only consumes events from a message broker. Think of it as a background worker that reacts to things that happen elsewhere in the system.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `amqplib` to connect to RabbitMQ, set `prefetch(1)` to process one message at a time, and `ack` each message after successful handling. Map event types to handler functions with a Record lookup.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Parse the message JSON, look up a handler by `event.type`, call it, then `channel.ack(msg)`. On error, use `channel.nack(msg, false, !msg.fields.redelivered)` to requeue only on the first failure. Handle SIGTERM for graceful shutdown.
</details>

### 🔍 Try It

```bash
docker compose up -d --build notification-service

# Purchase a ticket
curl -s -X POST http://localhost:8080/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}'

# Watch the notification service logs
docker compose logs -f notification-service
```

You should see the notification service pick up the purchase event and "send" the email — all without anyone making an HTTP call to it.

---

## 4. The Decision Framework (10 minutes)

You now have three communication patterns running in TicketPulse. Here is when to use each:

### REST (JSON over HTTP/1.1)

```
Use when:
✅ External APIs (browsers, mobile apps, third parties)
✅ Public-facing endpoints
✅ Simplicity is more important than performance
✅ You need human-readable payloads for debugging
✅ Broad ecosystem support (every language, every tool)

Avoid when:
❌ High-throughput internal service calls
❌ Streaming data
❌ You need strict schema enforcement
```

**TicketPulse example:** The API that the web and mobile frontends call. External webhook callbacks.

### gRPC (Protobuf over HTTP/2)

```
Use when:
✅ Internal service-to-service communication
✅ High-throughput, low-latency requirements
✅ You need streaming (server, client, or bidirectional)
✅ Strict API contracts with code generation
✅ Polyglot environments (proto generates code for Go, Java, Python, TypeScript, etc.)

Avoid when:
❌ Browser clients (no native support without grpc-web proxy)
❌ Simple CRUD with low traffic
❌ Teams unfamiliar with protobuf tooling
```

**TicketPulse example:** Monolith-to-payment-service calls. Future service-to-service calls between order, inventory, and payment services.

### Events (Async messages through a broker)

```
Use when:
✅ Fire-and-forget operations (notifications, analytics, logging)
✅ Fan-out (one event → many consumers)
✅ Temporal decoupling (producer and consumer don't need to be running simultaneously)
✅ Load leveling (absorb traffic spikes)
✅ The consumer's failure should not affect the producer

Avoid when:
❌ The caller needs a response (request-response pattern)
❌ Ordering guarantees matter and are hard to achieve
❌ You need sub-millisecond latency
```

**TicketPulse example:** Notification service, analytics pipeline, search index updates.

### The Decision Matrix

| Scenario | Pattern | Why |
|----------|---------|-----|
| Mobile app fetches event list | REST | Browser-friendly, cacheable, simple |
| Monolith processes payment | gRPC | Internal, type-safe, low latency |
| Send purchase confirmation email | Event | Async, can fail independently, retry-safe |
| Real-time seat availability | gRPC (server streaming) | Low latency, streaming updates |
| Third-party webhook delivery | REST | External, standard, human-debuggable |
| Analytics event ingestion | Event | High volume, async, loss-tolerant |
| Service health check | REST | Simple, universal, works with load balancers |

### 📊 Observe: TicketPulse's Communication Map

```
                    ┌──────────────┐
                    │   Browser    │
                    └──────┬───────┘
                           │ REST (JSON/HTTP)
                           ▼
                    ┌──────────────┐
                    │   Gateway    │
                    └──┬───────┬───┘
                       │       │
              REST     │       │  REST
                       ▼       ▼
              ┌──────────┐  ┌──────────────┐
              │ Monolith │  │ Payment Svc  │
              │          │──│              │
              │          │  │  REST + gRPC │
              └────┬─────┘  └──────────────┘
                   │
                   │ Events (RabbitMQ)
                   ▼
          ┌────────────────────┐
          │ Notification Svc   │
          │ (event consumer)   │
          └────────────────────┘
```

---

## 5. Reflect (5 minutes)

### 🤔 Questions to Answer

1. **Why not use gRPC for everything?** What would happen if the mobile app needed to talk gRPC?

2. **Why not use events for everything?** What would happen if the payment processing was event-based instead of request-response?

3. **What pattern would you use for:** a real-time leaderboard of ticket sales? A bulk import of 10,000 events? A fraud detection check during purchase?

4. **If you could only pick one pattern for all internal communication, which would you pick and why?**

There are no right answers. The goal is to understand that each pattern exists because it solves a specific set of problems well, and creates a specific set of problems you have to manage.

---

## 6. Clean Up

```bash
# Leave everything running — you'll build on this in M33
docker compose ps
```

You now have three services: the monolith (REST + gRPC client), the payment service (REST + gRPC server), and the notification service (event consumer). Three communication patterns, each serving a different purpose.

---

> **What did you notice?** You now have three communication patterns running in TicketPulse. Which one felt the most natural? Which introduced the most complexity? Would you use a single pattern for everything if you could?

## 7. Checkpoint

After this module, TicketPulse should have:

- [ ] A `proto/payment.proto` defining the payment service contract
- [ ] A gRPC server in the payment service alongside the existing REST API
- [ ] A gRPC client in the monolith that can call the payment service
- [ ] Benchmark results comparing REST and gRPC latency
- [ ] A notification service that consumes events from RabbitMQ with no HTTP API
- [ ] `docker compose ps` showing monolith, payment-service, notification-service, gateway, and infrastructure
- [ ] A decision framework for when to use REST, gRPC, or events
- [ ] Understanding of the trade-offs of each communication pattern

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **REST** | Universal, human-readable, browser-friendly. Best for external APIs. Overhead from JSON serialization and HTTP/1.1 connection model. |
| **gRPC** | Binary (protobuf), HTTP/2, streaming, type-safe. Best for internal service-to-service. Not browser-native. |
| **Events** | Async, decoupled, durable. Best for fire-and-forget, fan-out, and temporal decoupling. Cannot do request-response. |
| **Protobuf** | Binary serialization format. Smaller, faster, and schema-enforced compared to JSON. Field numbers enable backward-compatible evolution. |
| **HTTP/2 multiplexing** | Multiple requests share a single TCP connection. Eliminates head-of-line blocking at the HTTP level. |
| **Communication pattern choice** | Match the pattern to the interaction. Synchronous request-response needs REST or gRPC. Asynchronous fire-and-forget needs events. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **gRPC** | A high-performance RPC framework from Google that uses Protocol Buffers for serialization and HTTP/2 for transport. |
| **Protocol Buffers (protobuf)** | A binary serialization format and interface definition language. Defines message types in `.proto` files and generates code for multiple languages. |
| **HTTP/2** | The second major version of HTTP. Supports multiplexing (multiple requests on one connection), header compression, and server push. |
| **Multiplexing** | Sending multiple requests and responses over a single TCP connection simultaneously, without waiting for each to complete. |
| **Unary RPC** | A gRPC call with one request and one response. Equivalent to a REST API call. |
| **Server streaming RPC** | A gRPC call where the server sends a stream of responses to a single request. |
| **Event consumer** | A service that reads and processes events from a message broker. It does not expose an HTTP API — it reacts to events. |
| **Fire-and-forget** | A communication pattern where the sender does not wait for or expect a response. The message is sent and the sender moves on. |

---

---

## What's Next

In **Kafka Deep Dive** (L2-M33), you'll replace RabbitMQ's simple task queue with Kafka's distributed event log, enabling multiple services to independently consume the same events.

---

## Further Reading

- [gRPC Official Documentation](https://grpc.io/docs/) — core concepts, tutorials, and language guides
- [Protocol Buffers Language Guide](https://protobuf.dev/programming-guides/proto3/) — proto3 syntax reference
- Chapter 21 of the 100x Engineer Guide: Section 6 (gRPC and Protocol Buffers)
- Chapter 3 of the 100x Engineer Guide: Section 2 (Communication Patterns)
- [grpcurl](https://github.com/fullstorydev/grpcurl) — command-line tool for interacting with gRPC servers (like curl for gRPC)

# L1-M22: Introduction to Message Queues

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M21 (Event-Driven Thinking)
>
> **Source:** Chapters 1, 3 of the 100x Engineer Guide

---

## The Goal

In M21, you built an in-process event emitter. It decoupled the code but not the process. If the server crashes, pending events are lost. If a listener fails, the event is gone forever. If the email service is slow, it consumes resources on the API server.

A message queue fixes all of this. Events are persisted to a queue. Consumers process events independently. If a consumer fails, the message stays in the queue and is retried. If the server crashes, messages survive. Consumers can run on separate machines with separate resources.

By the end of this module, TicketPulse's purchase flow will publish events to RabbitMQ, and a separate consumer process will handle email notifications. You will kill the consumer, buy tickets, and watch the messages queue up. Then you will start the consumer and watch it process them all.

**You will see your first message in the queue within five minutes.**

---

## 0. Quick Start: Add RabbitMQ (5 minutes)

Update your `docker-compose.yml`:

```yaml
# docker-compose.yml (add RabbitMQ service)

services:
  # ... existing services (postgres, redis) ...

  rabbitmq:
    image: rabbitmq:3-management
    container_name: ticketpulse-rabbitmq
    ports:
      - "5672:5672"     # AMQP protocol (for your application)
      - "15672:15672"   # Management UI (for you)
    environment:
      RABBITMQ_DEFAULT_USER: ticketpulse
      RABBITMQ_DEFAULT_PASS: ticketpulse
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

volumes:
  rabbitmq_data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

### 🚀 Deploy

```bash
docker compose up -d rabbitmq
```

Wait a few seconds for RabbitMQ to start, then open the management UI:

```bash
# Open in browser
open http://localhost:15672
# Login: ticketpulse / ticketpulse
```

You should see the RabbitMQ dashboard: empty queues, zero messages, zero consumers. That is about to change.

### Install the Client Library

```bash
cd ticketpulse
npm install amqplib
npm install -D @types/amqplib
```

---

## 1. Understand the Concepts (5 minutes)

Before writing code, understand the moving parts:

```
Producer                    RabbitMQ                     Consumer
(TicketPulse API)          (Message Broker)             (Worker Process)

┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│              │  publish   │              │  consume   │              │
│ Purchase     │──────────→│   Queue      │──────────→│ Email Worker │
│ Endpoint     │           │              │           │              │
│              │           │ [msg1]       │           │ Sends emails │
│              │           │ [msg2]       │           │              │
│              │           │ [msg3]       │           │              │
└──────────────┘           └──────────────┘           └──────────────┘
                                 │
                            Messages are
                            persisted until
                            acknowledged
```

**Producer:** The code that sends messages (your API endpoint).
**Queue:** A buffer that stores messages until a consumer processes them. Messages are persistent — they survive RabbitMQ restarts.
**Consumer:** A separate process that reads messages from the queue and acts on them.
**Acknowledge (ack):** The consumer tells RabbitMQ "I processed this message successfully, you can delete it." If the consumer crashes before acking, RabbitMQ re-delivers the message.

---

## 2. Build: The Message Publisher (15 minutes)

### 🛠️ Build: RabbitMQ Connection and Publisher

```typescript
// src/messaging/rabbitmq.ts

import amqp, { Connection, Channel } from 'amqplib';

const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://ticketpulse:ticketpulse@localhost:5672';

let connection: Connection | null = null;
let channel: Channel | null = null;

export async function connectRabbitMQ(): Promise<void> {
  try {
    connection = await amqp.connect(RABBITMQ_URL);
    channel = await connection.createChannel();

    // Declare the queues we'll use
    // durable: true — queue survives RabbitMQ restart
    await channel.assertQueue('ticket.purchased', {
      durable: true,
      arguments: {
        // Dead letter exchange: failed messages go here
        'x-dead-letter-exchange': '',
        'x-dead-letter-routing-key': 'ticket.purchased.dlq',
      },
    });

    // Dead letter queue for failed messages
    await channel.assertQueue('ticket.purchased.dlq', { durable: true });

    // Other queues
    await channel.assertQueue('event.created', { durable: true });
    await channel.assertQueue('user.registered', { durable: true });

    console.log('[rabbitmq] Connected and queues declared');

    // Handle connection errors
    connection.on('error', (err) => {
      console.error('[rabbitmq] Connection error:', err.message);
      connection = null;
      channel = null;
    });

    connection.on('close', () => {
      console.warn('[rabbitmq] Connection closed');
      connection = null;
      channel = null;
    });
  } catch (err) {
    console.error('[rabbitmq] Failed to connect:', (err as Error).message);
    // Don't crash the app — publishing will be skipped
    connection = null;
    channel = null;
  }
}

export async function publishMessage(
  queue: string,
  message: Record<string, unknown>,
): Promise<boolean> {
  if (!channel) {
    console.warn(`[rabbitmq] Cannot publish to ${queue}: not connected`);
    return false;
  }

  try {
    const buffer = Buffer.from(JSON.stringify(message));
    const sent = channel.sendToQueue(queue, buffer, {
      persistent: true,  // Message survives RabbitMQ restart
      contentType: 'application/json',
      timestamp: Date.now(),
    });

    if (sent) {
      console.log(`[rabbitmq] Published to ${queue}: ${message.type || 'unknown'}`);
    } else {
      console.warn(`[rabbitmq] Queue ${queue} is full, message buffered`);
    }

    return sent;
  } catch (err) {
    console.error(`[rabbitmq] Failed to publish to ${queue}:`, (err as Error).message);
    return false;
  }
}

export async function closeRabbitMQ(): Promise<void> {
  try {
    if (channel) await channel.close();
    if (connection) await connection.close();
    console.log('[rabbitmq] Connection closed cleanly');
  } catch (err) {
    console.error('[rabbitmq] Error closing connection:', (err as Error).message);
  }
}
```

### Wire Into the Purchase Endpoint

```typescript
// src/routes/tickets.ts — publish to queue after purchase

import { publishMessage } from '../messaging/rabbitmq';
import { eventBus } from '../events/eventBus';

async function purchaseTicket(req: Request, res: Response) {
  const startTime = Date.now();

  // Step 1: Reserve + Pay + Create order (synchronous — same as before)
  const ticket = await reserveTicket(req.params.eventId, req.body.email);
  const payment = await processPayment(ticket, req.body.paymentMethod);
  const order = await createOrder(ticket, payment);

  // Step 2: Publish event to message queue (async — non-blocking)
  const event = {
    type: 'TicketPurchased',
    occurredAt: new Date().toISOString(),
    payload: {
      orderId: order.id,
      ticketId: ticket.id,
      eventId: req.params.eventId,
      eventTitle: ticket.eventTitle,
      customerEmail: req.body.email,
      amountInCents: order.totalInCents,
      tier: req.body.tier || 'general',
    },
  };

  // Publish to queue (fire-and-forget — does not block the response)
  publishMessage('ticket.purchased', event);

  // Also emit in-process for logging (from M21)
  await eventBus.emit('TicketPurchased', event);

  const totalTime = Date.now() - startTime;
  console.log(`[purchase] Response sent in ${totalTime}ms`);

  return res.status(201).json({ data: order });
}
```

### Initialize on Startup

```typescript
// src/server.ts (add RabbitMQ initialization)

import { connectRabbitMQ, closeRabbitMQ } from './messaging/rabbitmq';

async function start() {
  // Connect to databases (existing)
  await connectPostgres();
  await connectRedis();

  // Connect to message queue (new)
  await connectRabbitMQ();

  app.listen(3000, () => {
    console.log('TicketPulse running on http://localhost:3000');
  });
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  await closeRabbitMQ();
  process.exit(0);
});

start();
```

### 🔍 Try It: Publish Your First Message

```bash
# Make sure RabbitMQ is running
docker compose up -d rabbitmq

# Start TicketPulse
npm run dev

# Purchase a ticket
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}'
```

Now check the RabbitMQ management UI:

```bash
open http://localhost:15672
# Navigate to Queues tab
```

You should see:
- **Queue: `ticket.purchased`** — Ready: 1, Consumers: 0

The message is sitting in the queue, waiting for a consumer. Nobody is reading from it yet. It will stay there until a consumer picks it up.

### 📊 Observe: The Management UI

The RabbitMQ management UI shows:

- **Queues tab:** List of queues with message counts
  - Ready: messages waiting to be consumed
  - Unacked: messages being processed (delivered but not yet acknowledged)
  - Total: ready + unacked
- **Message rate:** messages published/second, delivered/second, acknowledged/second
- **Consumers:** number of connected consumers per queue

Buy a few more tickets and watch the "Ready" count climb:

```bash
for i in {1..5}; do
  curl -s -X POST http://localhost:3000/api/events/1/tickets \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"buyer${i}@example.com\", \"paymentMethod\": \"tok_visa\"}"
  echo ""
done
```

The queue should now show: **Ready: 6** (1 from before + 5 new). No consumers are processing them. They are safe in the queue, waiting patiently.

---

## 3. Build: The Email Consumer (15 minutes)

The consumer is a **separate process.** It does not run inside the API server. It runs independently and can be scaled, restarted, or crashed without affecting the API.

### 🛠️ Build: Consumer Process

```typescript
// src/consumers/emailConsumer.ts

import amqp, { ConsumeMessage } from 'amqplib';

const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://ticketpulse:ticketpulse@localhost:5672';
const QUEUE = 'ticket.purchased';

interface TicketPurchasedPayload {
  orderId: string;
  ticketId: string;
  eventId: string;
  eventTitle: string;
  customerEmail: string;
  amountInCents: number;
  tier: string;
}

async function sendConfirmationEmail(data: TicketPurchasedPayload): Promise<void> {
  // In production, this calls SendGrid/SES/Postmark
  console.log(`[email-consumer] Sending confirmation to ${data.customerEmail}`);
  console.log(`  Order: ${data.orderId}`);
  console.log(`  Event: ${data.eventTitle}`);
  console.log(`  Amount: $${(data.amountInCents / 100).toFixed(2)}`);

  // Simulate email API call (1-2 seconds)
  await new Promise(resolve =>
    setTimeout(resolve, 1000 + Math.random() * 1000)
  );

  console.log(`[email-consumer] Email sent to ${data.customerEmail}`);
}

async function start(): Promise<void> {
  console.log('[email-consumer] Starting...');

  const connection = await amqp.connect(RABBITMQ_URL);
  const channel = await connection.createChannel();

  // Process one message at a time (prevents overloading the email API)
  await channel.prefetch(1);

  console.log(`[email-consumer] Waiting for messages on "${QUEUE}"...`);

  await channel.consume(QUEUE, async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    const startTime = Date.now();

    try {
      const event = JSON.parse(msg.content.toString());
      console.log(`[email-consumer] Received: ${event.type} at ${event.occurredAt}`);

      await sendConfirmationEmail(event.payload);

      // Acknowledge the message — tell RabbitMQ we're done
      channel.ack(msg);

      const duration = Date.now() - startTime;
      console.log(`[email-consumer] Processed in ${duration}ms`);

    } catch (err) {
      console.error('[email-consumer] Failed to process message:', (err as Error).message);

      // Reject the message
      // requeue: false — send to dead letter queue (if configured)
      // requeue: true — put it back in the queue for retry
      const requeue = !msg.fields.redelivered; // Retry once, then dead-letter
      channel.nack(msg, false, requeue);

      if (!requeue) {
        console.warn('[email-consumer] Message sent to dead letter queue');
      } else {
        console.warn('[email-consumer] Message requeued for retry');
      }
    }
  });

  // Handle shutdown gracefully
  process.on('SIGTERM', async () => {
    console.log('[email-consumer] Shutting down...');
    await channel.close();
    await connection.close();
    process.exit(0);
  });

  process.on('SIGINT', async () => {
    console.log('[email-consumer] Interrupted, shutting down...');
    await channel.close();
    await connection.close();
    process.exit(0);
  });
}

start().catch(err => {
  console.error('[email-consumer] Failed to start:', err);
  process.exit(1);
});
```

Add a script to run the consumer:

```json
// package.json (add to scripts)
{
  "scripts": {
    "dev": "ts-node src/server.ts",
    "consumer:email": "ts-node src/consumers/emailConsumer.ts"
  }
}
```

### 🔍 Try It: Watch the Consumer Process Messages

Open a new terminal and start the consumer:

```bash
cd ticketpulse
npm run consumer:email
```

Expected output:

```
[email-consumer] Starting...
[email-consumer] Waiting for messages on "ticket.purchased"...
[email-consumer] Received: TicketPurchased at 2026-03-24T10:00:00.000Z
[email-consumer] Sending confirmation to buyer@example.com
  Order: ord-1
  Event: Taylor Swift
  Amount: $150.00
[email-consumer] Email sent to buyer@example.com
[email-consumer] Processed in 1234ms
[email-consumer] Received: TicketPurchased at 2026-03-24T10:00:01.000Z
[email-consumer] Sending confirmation to buyer1@example.com
...
```

The consumer processes all 6 messages that were waiting in the queue, one by one.

Check the management UI again:
- **Ready: 0** (all messages consumed)
- **Consumers: 1** (your email consumer)

---

## 4. The Key Insight: Decoupled Performance (5 minutes)

Look at what just happened:

1. The API responded to each purchase in ~215ms (fast)
2. Messages queued up in RabbitMQ (persistent, durable)
3. The consumer processed messages at its own pace (~1.5 seconds each)
4. The API and consumer run on separate processes (separate resources)

The API never waited for the email. The email consumer never slowed down the API. They are fully decoupled.

### The Before and After

| | Before (M21 Sync) | After (M22 Queue) |
|---|---|---|
| Purchase response time | 3,810ms | 215ms |
| Email sending | Blocks the API | Separate process |
| If email service is slow | API is slow | Only consumer is slow |
| If email service crashes | Purchase fails | Messages queue up, retry later |
| If API crashes | Pending emails lost | Messages safe in queue |

---

## 5. Debug: Kill the Consumer, Queue Up Messages (10 minutes)

### 🐛 The Experiment

```bash
# Terminal 1: TicketPulse API is running
# Terminal 2: Kill the email consumer (Ctrl+C)
```

Now buy 5 tickets with no consumer running:

```bash
for i in {1..5}; do
  curl -s -X POST http://localhost:3000/api/events/1/tickets \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"queued${i}@example.com\", \"paymentMethod\": \"tok_visa\"}"
  echo " - Ticket $i purchased"
done
```

Check the management UI:
- **Queue: `ticket.purchased`** — Ready: **5**, Consumers: **0**

Five messages are sitting in the queue. Nobody is processing them. But they are safe — persisted to disk.

### Start the Consumer Again

```bash
npm run consumer:email
```

Watch it process all 5 messages:

```
[email-consumer] Starting...
[email-consumer] Waiting for messages on "ticket.purchased"...
[email-consumer] Received: TicketPurchased ...
[email-consumer] Sending confirmation to queued1@example.com...
[email-consumer] Email sent to queued1@example.com
[email-consumer] Received: TicketPurchased ...
[email-consumer] Sending confirmation to queued2@example.com...
...
[email-consumer] Sending confirmation to queued5@example.com...
[email-consumer] Email sent to queued5@example.com
```

All 5 emails are sent. No messages were lost. This is the power of a durable message queue — it acts as a buffer between the producer and consumer.

### 📊 Observe: Queue Draining

Watch the management UI as the consumer processes messages:

- Ready count goes from 5 → 4 → 3 → 2 → 1 → 0
- The "Message rates" chart shows the delivery rate
- Consumer utilization shows how busy the consumer is

---

## 6. Dead Letter Queues: When Messages Cannot Be Processed (10 minutes)

What happens when a message fails processing? It should not be lost, and it should not block the queue forever.

### The Problem

A malformed message, a bug in the consumer, or a permanently failing external service can cause a message to fail repeatedly. Without dead letter queues, the message bounces between the queue and the consumer forever (a "poison pill").

### How Our Consumer Handles Failures

Look at the error handling in `emailConsumer.ts`:

```typescript
} catch (err) {
  // Reject the message
  const requeue = !msg.fields.redelivered; // Retry once, then dead-letter
  channel.nack(msg, false, requeue);
}
```

The logic:
1. First failure: `requeue = true` — put the message back in the queue for one retry
2. Second failure (redelivered = true): `requeue = false` — send to dead letter queue

### 🔍 Try It: Trigger a Dead Letter

Temporarily break the consumer to force a failure:

```typescript
// Add this at the top of the consume callback (TEMPORARY)
if (event.payload.customerEmail.includes('poison')) {
  throw new Error('Cannot process this email address!');
}
```

Send a "poison" message:

```bash
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "poison@example.com", "paymentMethod": "tok_visa"}'
```

Watch the consumer:

```
[email-consumer] Received: TicketPurchased ...
[email-consumer] Failed to process message: Cannot process this email address!
[email-consumer] Message requeued for retry
[email-consumer] Received: TicketPurchased ...  ← redelivered
[email-consumer] Failed to process message: Cannot process this email address!
[email-consumer] Message sent to dead letter queue
```

Check the management UI:
- **Queue: `ticket.purchased`** — Ready: 0
- **Queue: `ticket.purchased.dlq`** — Ready: 1

The failed message is in the dead letter queue. You can inspect it, fix the bug, and reprocess it later. It was not lost, and it did not block the main queue.

### Inspecting Dead Letters

In the management UI:
1. Click on the `ticket.purchased.dlq` queue
2. Click "Get Messages"
3. You can see the full message content, headers (including the original queue and reason for dead-lettering)

In production, you would build a tool to:
- Alert on messages appearing in the DLQ
- Allow operators to inspect and reprocess messages
- Automatically retry after a delay

---

## 7. Reflect: What Else Should Use Queues? (5 minutes)

### 🤔 Exercise

Look at TicketPulse's side effects from M21. Which should move from the in-process event emitter to a message queue?

| Side Effect | In-Process Event | Message Queue | Why |
|------------|-----------------|---------------|-----|
| Log purchase | In-Process | | Logging should be instant and in-process |
| Send confirmation email | | Queue | Slow, can fail, needs retry |
| Update analytics | | Queue | Can be batched, non-critical |
| Generate PDF ticket | | Queue | CPU-intensive, should not run on API server |
| Notify event organizer | | Queue | Can be delayed, needs retry |
| Update search index | | Queue | Can tolerate slight delay |
| Fraud check | | Queue | Async by nature, separate concern |

### 🤔 What Should Stay Synchronous?

Not everything belongs in a queue. These should remain synchronous (in the request lifecycle):

- **Inventory reservation:** Must happen before the response. Cannot oversell.
- **Payment processing:** Must confirm before showing "purchase confirmed."
- **Order creation:** Must persist before returning the order ID.

The rule: if the user needs to see the result before the response, it is synchronous. If the user can wait, it goes in the queue.

---

## 8. Clean Up

```bash
# Leave RabbitMQ running — you'll use it in future modules
# Stop the email consumer: Ctrl+C in its terminal

# Clean up test data from the DLQ
# In RabbitMQ management UI: Queues → ticket.purchased.dlq → Purge
```

Remove the temporary "poison" check from the consumer code.

---

## 9. Checkpoint

After this module, TicketPulse should have:

- [ ] RabbitMQ running in docker compose with management UI accessible
- [ ] `rabbitmq.ts` module with connection management, publish, and queue declaration
- [ ] Purchase endpoint publishing `TicketPurchased` events to a queue
- [ ] A separate `emailConsumer.ts` process that reads from the queue and sends emails
- [ ] Demonstrated: kill consumer, buy tickets, start consumer, all messages processed
- [ ] Dead letter queue configured for failed messages
- [ ] Understanding of message acknowledgement (ack/nack)
- [ ] Understanding of when to use queues vs. in-process events vs. synchronous calls

**Your TicketPulse should have three processes: the API server, the email consumer, and the supporting infrastructure (Postgres, Redis, RabbitMQ).**

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Message queue** | A persistent buffer between producers and consumers. Messages survive crashes and are retried on failure. |
| **Producer** | The code that publishes messages. Your API endpoint. Fire-and-forget. |
| **Consumer** | A separate process that reads and processes messages. Runs independently from the API. |
| **Acknowledgement** | The consumer tells the broker "I'm done with this message." Until acked, the message stays in the queue. |
| **Persistent messages** | Messages written to disk. Survive broker restarts. Use `persistent: true`. |
| **Durable queues** | Queue definition survives broker restarts. Use `durable: true`. |
| **Prefetch** | Limits how many unacked messages a consumer receives at once. `prefetch(1)` = process one at a time. |
| **Dead letter queue** | A queue for messages that failed processing. Prevents poison pills from blocking the main queue. |
| **Decoupled performance** | API response time is independent of consumer processing time. The queue absorbs the difference. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Message queue** | A service that stores messages until consumers process them. Provides durability, ordering, and delivery guarantees. |
| **RabbitMQ** | An open-source message broker that implements AMQP. Supports queues, exchanges, routing, and management UI. |
| **AMQP** | Advanced Message Queuing Protocol. The standard protocol for message brokers. |
| **Producer** | An application that publishes messages to a queue. |
| **Consumer** | An application that reads and processes messages from a queue. |
| **Acknowledge (ack)** | A signal from the consumer to the broker that a message was successfully processed and can be removed. |
| **Negative acknowledge (nack)** | A signal that processing failed. The message can be requeued or dead-lettered. |
| **Dead letter queue (DLQ)** | A queue that receives messages that could not be processed. Used for inspection, alerting, and manual reprocessing. |
| **Prefetch count** | The maximum number of unacknowledged messages a consumer can receive. Controls back-pressure. |
| **Durable** | A queue or message that survives broker restarts by being persisted to disk. |
| **Poison pill** | A message that repeatedly fails processing, blocking the queue. Dead letter queues solve this. |
| **Back-pressure** | A mechanism to prevent a fast producer from overwhelming a slow consumer. Prefetch and queue limits provide this. |

---

## Further Reading

- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html) — Official step-by-step tutorials
- [RabbitMQ Best Practices](https://www.cloudamqp.com/blog/part1-rabbitmq-best-practice.html) — Production configuration guide
- Chapter 3 of the 100x Engineer Guide: Section 2 (Asynchronous Communication Patterns)
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 11 (Stream Processing)
- [Redis Streams](https://redis.io/docs/data-types/streams/) — An alternative to RabbitMQ using Redis (lighter weight, less feature-rich)

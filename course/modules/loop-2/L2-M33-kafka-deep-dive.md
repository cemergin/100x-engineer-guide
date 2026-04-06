# L2-M33: Kafka Deep Dive

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M32 (Service Communication), L1-M22 (Introduction to Message Queues)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

In M22, you added RabbitMQ to TicketPulse. It works well for task queues — one message, one consumer, done. But TicketPulse is growing. Multiple services need to react to the same events independently. The notification service, the analytics service, and the search indexer all need to know when a ticket is purchased. With RabbitMQ, you would need to configure exchanges and fanout bindings for every new consumer. With Kafka, every consumer reads independently from a shared, persistent log.

Kafka is not a replacement for RabbitMQ — it is a different tool for a different problem. RabbitMQ is a message broker (route messages to consumers). Kafka is a distributed log (append events, let anyone read them at their own pace).

**From the guide:** Chapter 13 explains why event-driven architecture is the backbone of modern distributed systems — not just for decoupling services, but because an immutable, replayable event log is a fundamentally more durable record of what happened than a synchronized state machine. The chapter's key insight is that events are facts: "a ticket was purchased" is something that happened and cannot be un-happened. Downstream systems can interpret that fact differently — the notification service sends an email, the analytics service increments a counter, the fraud service runs a risk score — without the purchase service needing to know any of them exist. Now you'll build exactly that. TicketPulse's ticket-purchases topic will become the single source of truth that multiple independent consumer groups read at their own pace. Kill one consumer, restart it, watch it replay from where it left off without missing a single event. That's the capability Chapter 13 described in theory.

By the end of this module, TicketPulse will have Kafka as its event backbone. You will create topics, produce messages, run multiple consumer groups, kill consumers and watch them catch up, and observe everything through Kafka UI.

**You will see your first Kafka message within five minutes.**

---

> **Before you continue:** With RabbitMQ, once a consumer processes a message, it is gone. What if a new analytics service needs to process all historical purchase events? How would you solve this with RabbitMQ? Keep this limitation in mind.


## 0. Deploy Kafka (5 minutes)

### 🚀 Add Kafka to Docker Compose

Kafka no longer requires Zookeeper in newer versions (KRaft mode). We will use KRaft for simplicity.

```yaml
# docker-compose.yml — add Kafka services

services:
  # ... existing services ...

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    container_name: ticketpulse-kafka
    ports:
      - "9092:9092"
      - "9093:9093"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_LOG_DIRS: /var/lib/kafka/data
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_CLUSTER_ID: "ticketpulse-cluster-001"
    volumes:
      - kafka_data:/var/lib/kafka/data

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: ticketpulse-kafka-ui
    ports:
      - "8090:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: ticketpulse
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
    depends_on:
      - kafka

volumes:
  kafka_data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```bash
docker compose up -d kafka kafka-ui

# Wait for Kafka to be ready (takes 10-20 seconds)
docker compose logs -f kafka 2>&1 | grep -m1 "Kafka Server started"

# Open Kafka UI
open http://localhost:8090
```

You should see Kafka UI with one cluster, zero topics. That is about to change.

---

## 1. Create Topics (5 minutes)

Kafka topics are not like RabbitMQ queues. A topic is a **partitioned, append-only log.** Messages are not deleted after consumption — they stay in the log for a configurable retention period.

### Create TicketPulse Topics

```bash
# Create topics using the Kafka CLI (inside the container)

# ticket-purchases: partitioned by event_id for ordering
docker compose exec kafka kafka-topics --create \
  --topic ticket-purchases \
  --bootstrap-server localhost:9092 \
  --partitions 6 \
  --replication-factor 1

# event-updates: changes to event details
docker compose exec kafka kafka-topics --create \
  --topic event-updates \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# user-notifications: notification delivery tracking
docker compose exec kafka kafka-topics --create \
  --topic user-notifications \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# List all topics
docker compose exec kafka kafka-topics --list \
  --bootstrap-server localhost:9092
```

### 🤔 Why 6 Partitions for ticket-purchases?

Partitions are Kafka's unit of parallelism. The number of partitions determines the maximum number of consumers in a consumer group that can process messages concurrently. Six partitions means up to six consumers can work in parallel.

```
ticket-purchases topic (6 partitions):

  Partition 0: [msg1] [msg4] [msg7] ...
  Partition 1: [msg2] [msg5] [msg8] ...
  Partition 2: [msg3] [msg6] [msg9] ...
  Partition 3: [msg10] [msg13] ...
  Partition 4: [msg11] [msg14] ...
  Partition 5: [msg12] [msg15] ...
```

Messages within a partition are **strictly ordered.** Messages across partitions have **no ordering guarantee.** This is why partitioning strategy matters.

Check Kafka UI — navigate to Topics. You should see three topics with their partition counts.

---

## 2. Understand the Key Concepts (10 minutes)

Before writing code, internalize the four concepts that make Kafka different from RabbitMQ:

### Concept 1: Topics and Partitions

```
RabbitMQ:                          Kafka:
Queue = a line of messages          Topic = a log split into partitions
Consumer takes message → gone       Consumer reads message → still there
One consumer per message            Many consumers, each at own offset

Queue: [A] [B] [C] [D]            Topic (3 partitions):
Consumer reads A → A is gone          P0: [A] [D] [G]
                                      P1: [B] [E] [H]
                                      P2: [C] [F] [I]
                                    Consumer reads A → A is still there
                                    Another consumer can also read A
```

### Concept 2: Consumer Groups

A consumer group is a set of consumers that cooperate to consume a topic. Each partition is assigned to exactly one consumer in the group. Two different consumer groups consume the same topic independently.

```
ticket-purchases (6 partitions)
          │
          ├── Consumer Group: "notification-service"
          │     Consumer 1 → reads P0, P1
          │     Consumer 2 → reads P2, P3
          │     Consumer 3 → reads P4, P5
          │
          └── Consumer Group: "analytics-service"
                Consumer 1 → reads P0, P1, P2, P3, P4, P5
                (only one consumer in this group, gets all partitions)
```

The notification service and analytics service both consume every message from `ticket-purchases`, but they track their positions independently.

### Concept 3: Offsets

Each consumer group tracks its **offset** per partition — the position of the last message it consumed. When a consumer restarts, it resumes from where it left off.

```
Partition 0: [msg0] [msg1] [msg2] [msg3] [msg4] [msg5]
                                     ↑
                          notification-service offset: 3
                          (has processed 0, 1, 2 — will read 3 next)

                               ↑
                    analytics-service offset: 1
                    (has processed 0 — will read 1 next)
```

### Concept 4: Partition Keys

When you produce a message, you can specify a **key.** Messages with the same key always go to the same partition. This guarantees ordering for related messages.

```
# All purchases for event 42 go to the same partition
key: "event-42" → hash → Partition 3

# All purchases for event 42 are ordered
Partition 3: [buy-event42-seat1] [buy-event42-seat2] [buy-event42-seat3]
```

For TicketPulse, keying `ticket-purchases` by `event_id` means all purchases for the same event are ordered. This prevents race conditions when checking remaining capacity.

---

> **Before you continue:** If you have 6 partitions and 8 consumers in the same group, what happens to the extra 2 consumers? Think about how Kafka distributes work.


## 3. Build: Kafka Producer (15 minutes)

### Install KafkaJS

```bash
# In the monolith
npm install kafkajs
```

### 🛠️ Build: The Kafka Producer

<details>
<summary>💡 Hint 1: Direction</summary>
The producer needs a persistent connection initialized once at startup. The critical decision is the partition key: using `event_id` means all purchases for the same event land in the same partition, guaranteeing order per event.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create a `connectKafkaProducer()` called at startup, and a `publishEvent(topic, key, event)` function. Use `producer.send({ topic, messages: [{ key, value: JSON.stringify(event), headers: {...} }] })`. Add headers for event-type and timestamp for debugging.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Wire `publishEvent('ticket-purchases', req.params.eventId, event)` into the purchase endpoint alongside the existing RabbitMQ publish. Both can coexist during migration. Handle the case where the producer is not connected (log a warning, do not crash the purchase).
</details>


```typescript
// src/messaging/kafkaProducer.ts

import { Kafka, Producer, Partitioners } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'ticketpulse-api',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
  retry: {
    initialRetryTime: 100,
    retries: 5,
  },
});

let producer: Producer | null = null;

export async function connectKafkaProducer(): Promise<void> {
  try {
    producer = kafka.producer({
      createPartitioner: Partitioners.DefaultPartitioner,
    });

    await producer.connect();
    console.log('[kafka-producer] Connected');
  } catch (err) {
    console.error('[kafka-producer] Failed to connect:', (err as Error).message);
    producer = null;
  }
}

export async function publishEvent(
  topic: string,
  key: string,
  event: Record<string, unknown>
): Promise<void> {
  if (!producer) {
    console.warn(`[kafka-producer] Not connected, cannot publish to ${topic}`);
    return;
  }

  try {
    await producer.send({
      topic,
      messages: [
        {
          key,    // Partition key — messages with the same key go to the same partition
          value: JSON.stringify(event),
          headers: {
            'event-type': event.type as string,
            'produced-at': new Date().toISOString(),
            'source': 'ticketpulse-api',
          },
        },
      ],
    });

    console.log(`[kafka-producer] Published to ${topic} (key: ${key}): ${event.type}`);
  } catch (err) {
    console.error(`[kafka-producer] Failed to publish to ${topic}:`, (err as Error).message);
  }
}

export async function disconnectKafkaProducer(): Promise<void> {
  if (producer) {
    await producer.disconnect();
    console.log('[kafka-producer] Disconnected');
  }
}
```

### Wire Into the Purchase Endpoint

```typescript
// src/routes/tickets.ts — add Kafka publishing alongside RabbitMQ

import { publishEvent } from '../messaging/kafkaProducer';

async function purchaseTicket(req: Request, res: Response) {
  const ticket = await reserveTicket(req.params.eventId, req.body.email);
  const payment = await processPayment({ /* ... */ });
  const order = await createOrder(ticket, payment);

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

  // Publish to Kafka — key is event_id for partition ordering
  await publishEvent('ticket-purchases', req.params.eventId, event);

  // Optionally keep RabbitMQ for the notification queue during migration
  // publishMessage('ticket.purchased', event);

  return res.status(201).json({ data: order });
}
```

### Initialize on Startup

```typescript
// src/server.ts — add Kafka initialization

import { connectKafkaProducer, disconnectKafkaProducer } from './messaging/kafkaProducer';

async function start() {
  await connectPostgres();
  await connectRedis();
  await connectRabbitMQ();
  await connectKafkaProducer(); // NEW

  app.listen(3000, () => {
    console.log('TicketPulse running on http://localhost:3000');
  });
}

process.on('SIGTERM', async () => {
  await disconnectKafkaProducer(); // NEW
  await closeRabbitMQ();
  process.exit(0);
});
```


<details>
<summary>💡 Hint 1: Direction</summary>
The Kafka producer needs a persistent connection initialized once on startup. The partition key controls message ordering — same key means same partition means guaranteed order.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create a `connectKafkaProducer()` function called at startup. The `publishEvent()` function takes a topic, key, and event object. Use `event_id` as the key so all purchases for the same event land in the same partition.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Call `producer.send({ topic, messages: [{ key, value: JSON.stringify(event), headers: {...} }] })`. Add headers for event-type and timestamp. Wire `publishEvent('ticket-purchases', req.params.eventId, event)` into the purchase endpoint alongside the existing RabbitMQ publish.
</details>

---

## 4. Build: Kafka Consumers (15 minutes)

### 🛠️ Build: Notification Consumer

<details>
<summary>💡 Hint 1: Direction</summary>
The notification consumer needs its own `groupId: 'notification-service'` so it tracks offsets independently from the analytics consumer. Use `fromBeginning: false` -- it only needs new events, not historical replay.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Subscribe to `['ticket-purchases', 'event-updates']`. In the `eachMessage` handler, parse `message.value` as JSON and switch on `event.type` to route to the correct handler (TicketPurchased, EventUpdated, etc.).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Handle graceful shutdown by disconnecting the consumer on SIGTERM/SIGINT. Log the topic, partition, and offset for each message so you can trace exactly where the consumer is in the log when debugging.
</details>


```typescript
// services/notification-service/src/kafkaConsumer.ts

import { Kafka, EachMessagePayload } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'notification-service',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
});

const consumer = kafka.consumer({
  groupId: 'notification-service',  // Consumer group name
  sessionTimeout: 30000,
  heartbeatInterval: 3000,
});

async function handleMessage({ topic, partition, message }: EachMessagePayload): Promise<void> {
  const event = JSON.parse(message.value!.toString());
  const key = message.key?.toString();

  console.log(`[notification] Received from ${topic}[${partition}] offset=${message.offset} key=${key}`);
  console.log(`[notification] Event: ${event.type}`);

  switch (event.type) {
    case 'TicketPurchased':
      console.log(`[notification] Sending confirmation to ${event.payload.customerEmail}`);
      console.log(`  Event: ${event.payload.eventTitle}`);
      console.log(`  Amount: $${(event.payload.amountInCents / 100).toFixed(2)}`);
      // Simulate email sending
      await new Promise(resolve => setTimeout(resolve, 500));
      console.log(`[notification] Email sent to ${event.payload.customerEmail}`);
      break;

    default:
      console.log(`[notification] Unhandled event type: ${event.type}`);
  }
}

async function start(): Promise<void> {
  console.log('[notification-service] Connecting to Kafka...');

  await consumer.connect();
  console.log('[notification-service] Connected');

  await consumer.subscribe({
    topics: ['ticket-purchases', 'event-updates'],
    fromBeginning: false,  // Only new messages
  });

  console.log('[notification-service] Subscribed to topics');

  await consumer.run({
    eachMessage: handleMessage,
  });

  console.log('[notification-service] Running...');
}

// Graceful shutdown
const shutdown = async () => {
  console.log('[notification-service] Shutting down...');
  await consumer.disconnect();
  process.exit(0);
};

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

start().catch(err => {
  console.error('[notification-service] Failed to start:', err);
  process.exit(1);
});
```


<details>
<summary>💡 Hint 1: Direction</summary>
Each Kafka consumer group independently tracks its position (offset) in the topic. The notification service and analytics service both read every message but at their own pace.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Set a unique `groupId` for each service. Use `subscribe({ topics: [...], fromBeginning: false })` for the notification service (only new messages) and `fromBeginning: true` for analytics (replay all history).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The consumer's `eachMessage` handler receives `{ topic, partition, message }`. Parse `message.value` as JSON, switch on `event.type`, and process accordingly. Handle graceful shutdown by disconnecting the consumer on SIGTERM/SIGINT.
</details>

### 🛠️ Build: Analytics Consumer

<details>
<summary>💡 Hint 1: Direction</summary>
The analytics consumer uses `groupId: 'analytics-service'` -- a different group from notifications, so both independently consume every message. The key difference: use `fromBeginning: true` to replay all historical events on first startup.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Maintain in-memory counters (totalPurchases, totalRevenue, purchasesByEvent Map). On each TicketPurchased event, increment the counters. In production you would write to a data warehouse instead.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
When you kill and restart this consumer, it resumes from its last committed offset -- not from the beginning (offsets are already committed). Only a brand-new consumer group with `fromBeginning: true` replays history. This is Kafka's superpower over RabbitMQ.
</details>


```typescript
// services/analytics-service/src/kafkaConsumer.ts
// (create services/analytics-service/ with the same structure)

import { Kafka, EachMessagePayload } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'analytics-service',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
});

const consumer = kafka.consumer({
  groupId: 'analytics-service',  // Different group — reads independently
});

// In-memory analytics (in production: write to a data warehouse)
const analytics = {
  totalPurchases: 0,
  totalRevenue: 0,
  purchasesByEvent: new Map<string, number>(),
};

async function handleMessage({ topic, partition, message }: EachMessagePayload): Promise<void> {
  const event = JSON.parse(message.value!.toString());

  if (event.type === 'TicketPurchased') {
    analytics.totalPurchases++;
    analytics.totalRevenue += event.payload.amountInCents;

    const eventId = event.payload.eventId;
    analytics.purchasesByEvent.set(
      eventId,
      (analytics.purchasesByEvent.get(eventId) || 0) + 1
    );

    console.log(`[analytics] Purchase #${analytics.totalPurchases}: $${(event.payload.amountInCents / 100).toFixed(2)}`);
    console.log(`[analytics] Total revenue: $${(analytics.totalRevenue / 100).toFixed(2)}`);
    console.log(`[analytics] Event ${eventId}: ${analytics.purchasesByEvent.get(eventId)} tickets sold`);
  }
}

async function start(): Promise<void> {
  console.log('[analytics-service] Connecting to Kafka...');

  await consumer.connect();
  await consumer.subscribe({ topics: ['ticket-purchases'], fromBeginning: true }); // fromBeginning: replay all history

  await consumer.run({ eachMessage: handleMessage });

  console.log('[analytics-service] Running...');
}

process.on('SIGTERM', async () => {
  await consumer.disconnect();
  process.exit(0);
});

start().catch(err => {
  console.error('[analytics-service] Failed to start:', err);
  process.exit(1);
});
```

Notice: the analytics service uses `fromBeginning: true`. On first startup, it replays every message in the topic from the beginning. This is Kafka's superpower — the log is persistent, so a new consumer can build its state by replaying history.

---

## 5. Try It: Watch Messages Flow (10 minutes)

### 🔍 Deploy Everything

```bash
docker compose up -d --build
```

### Buy 10 Tickets

```bash
for i in $(seq 1 10); do
  EVENT_ID=$((($i % 3) + 1))  # Spread across events 1, 2, 3
  curl -s -X POST http://localhost:8080/api/events/${EVENT_ID}/tickets \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"buyer${i}@example.com\", \"paymentMethod\": \"tok_visa\"}" \
    > /dev/null
  echo "Ticket $i purchased for event $EVENT_ID"
done
```

### 📊 Observe: Kafka UI

Open http://localhost:8090 and explore:

1. **Topics** — Click on `ticket-purchases`
   - You should see 10 messages
   - Click on individual partitions — messages are distributed by event_id key
   - Events with the same `event_id` are in the same partition

2. **Messages** — Click "Messages" tab on the topic
   - See the raw JSON payloads
   - Note the partition, offset, key, and headers for each message

3. **Consumer Groups** — Navigate to Consumer Groups
   - `notification-service`: see which partitions each consumer owns, and the current offset per partition
   - `analytics-service`: same view, different offsets (analytics may have replayed from the beginning)

4. **Consumer Lag** — The difference between the latest offset in a partition and the consumer's committed offset
   - If lag > 0, the consumer is behind
   - If lag grows over time, the consumer is too slow

### Watch the Logs

```bash
# In separate terminals or combined:
docker compose logs -f notification-service
docker compose logs -f analytics-service
```

Both services process all 10 messages independently:
- The notification service sends 10 emails
- The analytics service counts 10 purchases and calculates total revenue

---

## 6. Debug: Consumer Failure and Recovery (10 minutes)

### 🐛 Kill a Consumer, Buy More Tickets, Restart

<details>
<summary>💡 Hint 1: Direction</summary>
Stop the notification service with `docker compose stop notification-service`, then buy 5 more tickets. Check Kafka UI's Consumer Groups view -- the notification-service group should show consumer lag = 5.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Restart with `docker compose start notification-service` and watch the logs. The consumer resumes from its last committed offset and processes exactly the 5 missed messages. No messages were lost because Kafka retained them in the topic log.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Compare this to RabbitMQ: with RabbitMQ, once a consumer acks a message, it is gone. With Kafka, the message stays in the partition log for the configured retention period (default 7 days). Any consumer group can replay from any offset at any time.
</details>


```bash
# Step 1: Stop the notification service
docker compose stop notification-service

# Step 2: Buy 5 more tickets while it's down
for i in $(seq 11 15); do
  curl -s -X POST http://localhost:8080/api/events/1/tickets \
    -H 'Content-Type: application/json' \
    -d "{\"email\": \"buyer${i}@example.com\", \"paymentMethod\": \"tok_visa\"}" \
    > /dev/null
  echo "Ticket $i purchased"
done

# Step 3: Check Kafka UI
# Navigate to Consumer Groups → notification-service
# You should see consumer lag = 5 (5 unprocessed messages)
```

The analytics service is still running — it processes all 5 new messages. The notification service's messages are waiting in Kafka at the last committed offset.

```bash
# Step 4: Restart the notification service
docker compose start notification-service

# Watch it catch up
docker compose logs -f notification-service
```

You should see:

```
[notification-service] Connected
[notification-service] Subscribed to topics
[notification-service] Running...
[notification] Received from ticket-purchases[0] offset=5 key=1
[notification] Sending confirmation to buyer11@example.com
[notification] Email sent to buyer11@example.com
[notification] Received from ticket-purchases[0] offset=6 key=1
...
[notification] Email sent to buyer15@example.com
```

All 5 messages are processed. No messages were lost. The consumer resumed from its last committed offset.

### 📊 Observe: Consumer Lag

In Kafka UI, check the notification-service consumer group lag:
- Before restart: lag = 5
- After restart and catchup: lag = 0

---

## 7. Consumer Group Rebalancing (5 minutes)

What happens when you add a second instance of the notification service?

```bash
# Scale the notification service to 2 instances
docker compose up -d --scale notification-service=2
```

Watch the logs:

```
notification-service-1 | [notification-service] Rebalancing... Partitions revoked: [0, 1, 2, 3, 4, 5]
notification-service-1 | [notification-service] Rebalancing... Partitions assigned: [0, 1, 2]
notification-service-2 | [notification-service] Rebalancing... Partitions assigned: [3, 4, 5]
```

Kafka rebalanced the partitions across the two consumers:
- Instance 1 now reads partitions 0, 1, 2
- Instance 2 now reads partitions 3, 4, 5

Buy more tickets and watch both instances process messages in parallel.

```bash
# Scale back down
docker compose up -d --scale notification-service=1
```

Partitions are reassigned back to the single instance.

**Key insight:** If you have 6 partitions and 8 consumers in the same group, 2 consumers will be idle. The maximum parallelism equals the number of partitions. This is why partition count is a capacity planning decision.

---

## 8. Reflect (5 minutes)

### 🤔 When Would You Choose Kafka Over RabbitMQ?

| Criteria | RabbitMQ | Kafka |
|----------|----------|-------|
| Message pattern | Task queue (one consumer per message) | Event log (many consumers per message) |
| Message retention | Deleted after ack | Retained for configurable period |
| Replay | Not possible (message is gone) | Any consumer can replay from any offset |
| Ordering | Per-queue ordering | Per-partition ordering |
| Throughput | Thousands/sec (per queue) | Millions/sec (partitioned) |
| Consumer groups | Complex (exchange bindings) | Built-in (subscribe, get partitions) |
| Complexity | Moderate | High (partitions, offsets, rebalancing) |

**Choose RabbitMQ when:**
- You need a task queue (one consumer processes each message)
- Message routing logic is complex (topic exchanges, header routing)
- Messages should be deleted after processing
- You want simpler operations

**Choose Kafka when:**
- Multiple services need the same events independently
- You need to replay events (new service needs historical data)
- You need high throughput with ordering guarantees
- You are building an event-sourced system
- You need audit logs or event history

**What about SQS?**
- Managed RabbitMQ-like semantics (task queue, at-least-once, no replay)
- Zero ops overhead (no broker to manage)
- Choose SQS when you want a task queue without managing infrastructure

For TicketPulse: Kafka is the event backbone (ticket-purchases, event-updates). RabbitMQ can remain for specific task queues (email delivery retries, PDF generation). They serve different purposes and can coexist.

---

> **What did you notice?** When you killed the notification consumer and restarted it, all messages were still there. How does this compare to RabbitMQ's behavior? What makes Kafka's persistent log fundamentally different?

## 9. Checkpoint

After this module, TicketPulse should have:

- [ ] Kafka running in docker compose with KRaft (no Zookeeper)
- [ ] Kafka UI accessible at http://localhost:8090
- [ ] Three topics: `ticket-purchases` (6 partitions), `event-updates`, `user-notifications`
- [ ] A Kafka producer in the monolith publishing to `ticket-purchases` with event_id as the partition key
- [ ] A notification service consuming from Kafka as consumer group `notification-service`
- [ ] An analytics service consuming from Kafka as consumer group `analytics-service`
- [ ] Demonstrated: kill consumer, produce messages, restart consumer, messages processed from last offset
- [ ] Demonstrated: consumer group rebalancing when scaling consumers
- [ ] Understanding of topics, partitions, consumer groups, and offsets

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Kafka** | A distributed, append-only log. Messages are retained, not deleted after consumption. Multiple consumers read independently. |
| **Topic** | A named log split into partitions. Similar to a database table — a category of events. |
| **Partition** | A single ordered log within a topic. The unit of parallelism. Messages within a partition are strictly ordered. |
| **Partition key** | Determines which partition a message goes to. Same key = same partition = guaranteed ordering. |
| **Consumer group** | A set of consumers that cooperate to consume a topic. Each partition is assigned to exactly one consumer in the group. |
| **Offset** | A consumer's position in a partition. Consumers commit offsets to track progress. On restart, they resume from the last committed offset. |
| **Consumer lag** | The difference between the latest offset and the consumer's committed offset. Growing lag means the consumer is falling behind. |
| **Rebalancing** | When consumers join or leave a group, Kafka redistributes partition assignments. Brief interruption to processing. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Kafka** | A distributed event streaming platform that stores events as an ordered, immutable log. |
| **KRaft** | Kafka's built-in consensus protocol that replaces Zookeeper for metadata management. |
| **Broker** | A single Kafka server that stores data and serves client requests. A cluster has multiple brokers. |
| **Topic** | A named category of events in Kafka. Analogous to a database table. |
| **Partition** | A single ordered, append-only log within a topic. The unit of parallelism and ordering. |
| **Consumer group** | A group of consumers that split the work of consuming a topic. Each partition is processed by exactly one consumer in the group. |
| **Offset** | A sequential ID for each message within a partition. Consumers track offsets to know where they left off. |
| **Consumer lag** | The number of messages a consumer group has not yet processed. Lag = latest offset - consumer offset. |
| **Partition key** | A value used to determine which partition a message is written to. Same key = same partition. |
| **Retention** | How long Kafka keeps messages. Default is 7 days. Can be configured per topic. |
| **Rebalancing** | The process of reassigning partitions among consumers when the group membership changes. |

---

---

## What's Next

In **The Saga Pattern** (L2-M34), you'll tackle the hardest problem microservices create: coordinating transactions across services without a shared database.

---

## Further Reading

- [Kafka: The Definitive Guide](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/) — comprehensive book from Confluent
- [KafkaJS Documentation](https://kafka.js.org/) — the Node.js client used in this module
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 11 (Stream Processing)
- Jay Kreps, ["The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying) — the foundational essay behind Kafka

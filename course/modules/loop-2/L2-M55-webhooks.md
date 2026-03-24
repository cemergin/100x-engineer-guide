# L2-M55: Webhooks

> **Loop 2 (Applied)** | Section 2D: Advanced Patterns | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L2-M39 (Kubernetes Basics), L2-M49 (Circuit Breakers & Resilience)
>
> **What you'll build:** You will implement a complete webhook system for TicketPulse -- partner registration, HMAC-SHA256 signed delivery, a consumer that verifies signatures, retry with exponential backoff, a dead letter queue, idempotency, and delivery metrics.

---

## The Goal

TicketPulse partners -- venues, promoters, analytics platforms -- want to be notified when tickets are sold, events are updated, or orders are cancelled. Today, they poll the API every 30 seconds. 50 partners polling 3 endpoints = 150 requests every 30 seconds = 300 req/min of wasted work. Most polls return "no changes."

Webhooks flip the model: TicketPulse pushes events to partners when something happens. No polling. No wasted requests. Partners get notified in seconds instead of waiting up to 30 seconds.

**You will run code within the first two minutes.**

---

## 0. Quick Start: The Registration Model (3 minutes)

```sql
-- Webhook registrations
CREATE TABLE webhook_registrations (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  partner_id    TEXT NOT NULL,
  url           TEXT NOT NULL,
  secret        TEXT NOT NULL,     -- Shared secret for HMAC signing
  event_types   TEXT[] NOT NULL,   -- Which events to receive: ['ticket.purchased', 'event.updated']
  active        BOOLEAN DEFAULT true,
  failure_count INTEGER DEFAULT 0, -- Consecutive failures
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Delivery log (for debugging and replay)
CREATE TABLE webhook_deliveries (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  registration_id TEXT NOT NULL REFERENCES webhook_registrations(id),
  event_id        TEXT NOT NULL,   -- For idempotency
  event_type      TEXT NOT NULL,
  payload         JSONB NOT NULL,
  status          TEXT NOT NULL,   -- 'pending', 'delivered', 'failed', 'dead_letter'
  attempts        INTEGER DEFAULT 0,
  last_attempt_at TIMESTAMPTZ,
  response_status INTEGER,
  response_body   TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_deliveries_status ON webhook_deliveries(status);
CREATE INDEX idx_deliveries_event ON webhook_deliveries(event_id);
```

---

## 1. Build: Webhook Registration API (8 minutes)

```typescript
// src/routes/webhooks.routes.ts

import { Router, Request, Response } from 'express';
import crypto from 'crypto';
import { Pool } from 'pg';

const router = Router();
const db = new Pool({ connectionString: process.env.DATABASE_URL });

// Register a webhook
router.post('/webhooks', async (req: Request, res: Response) => {
  const { url, eventTypes } = req.body;
  const partnerId = (req as any).user.partnerId;

  // --- YOUR DECISION POINT ---
  // Should you validate the URL before registering?
  // Option A: Just store it (fast, but partners might register broken URLs)
  // Option B: Send a test request and require a 200 response
  // Option C: Send a verification challenge (like Slack does)
  //
  // Implement Option B for now:

  try {
    const testResponse = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'webhook.verification', challenge: crypto.randomUUID() }),
      signal: AbortSignal.timeout(5000),
    });

    if (!testResponse.ok) {
      return res.status(400).json({
        error: 'Webhook URL verification failed',
        message: `URL returned status ${testResponse.status}. The endpoint must return 2xx.`,
      });
    }
  } catch (error: any) {
    return res.status(400).json({
      error: 'Webhook URL unreachable',
      message: `Could not connect to ${url}: ${error.message}`,
    });
  }

  // Generate a shared secret for HMAC signing
  const secret = `whsec_${crypto.randomBytes(24).toString('hex')}`;

  const result = await db.query(
    `INSERT INTO webhook_registrations (partner_id, url, secret, event_types)
     VALUES ($1, $2, $3, $4)
     RETURNING id, url, event_types, created_at`,
    [partnerId, url, secret, eventTypes]
  );

  // Return the secret ONCE. Partners must store it.
  // It is never returned again (like an API key).
  res.status(201).json({
    ...result.rows[0],
    secret,  // Only returned at creation time
    message: 'Store the secret securely. It will not be shown again.',
  });
});

// List partner's webhooks
router.get('/webhooks', async (req: Request, res: Response) => {
  const partnerId = (req as any).user.partnerId;
  const result = await db.query(
    'SELECT id, url, event_types, active, failure_count, created_at FROM webhook_registrations WHERE partner_id = $1',
    [partnerId]
  );
  res.json(result.rows);
});

// Delete a webhook
router.delete('/webhooks/:id', async (req: Request, res: Response) => {
  const partnerId = (req as any).user.partnerId;
  await db.query(
    'DELETE FROM webhook_registrations WHERE id = $1 AND partner_id = $2',
    [req.params.id, partnerId]
  );
  res.status(204).send();
});

export default router;
```

---

## 2. Build: Webhook Delivery with HMAC Signing (12 minutes)

When a ticket is purchased, POST to all registered webhooks:

```typescript
// src/webhooks/webhook-sender.ts

import crypto from 'crypto';
import { Pool } from 'pg';

const db = new Pool({ connectionString: process.env.DATABASE_URL });

interface WebhookEvent {
  eventId: string;
  eventType: string;   // 'ticket.purchased', 'event.updated', 'order.cancelled'
  data: Record<string, any>;
  occurredAt: string;
}

export async function dispatchWebhook(event: WebhookEvent): Promise<void> {
  // Find all active registrations that subscribe to this event type
  const registrations = await db.query(
    `SELECT id, url, secret FROM webhook_registrations
     WHERE active = true AND $1 = ANY(event_types)`,
    [event.eventType]
  );

  console.log(`[webhook] Dispatching ${event.eventType} to ${registrations.rows.length} recipient(s)`);

  for (const registration of registrations.rows) {
    // Create a delivery record
    await db.query(
      `INSERT INTO webhook_deliveries (registration_id, event_id, event_type, payload, status)
       VALUES ($1, $2, $3, $4, 'pending')`,
      [registration.id, event.eventId, event.eventType, JSON.stringify(event)]
    );

    // Attempt delivery (fire and forget -- the retry processor handles failures)
    deliverWebhook(registration, event).catch(err => {
      console.error(`[webhook] Delivery failed for registration ${registration.id}:`, err.message);
    });
  }
}

async function deliverWebhook(
  registration: { id: string; url: string; secret: string },
  event: WebhookEvent
): Promise<void> {
  const payload = JSON.stringify(event);
  const timestamp = Math.floor(Date.now() / 1000);

  // HMAC-SHA256 signature
  const signedPayload = `${timestamp}.${payload}`;
  const signature = crypto
    .createHmac('sha256', registration.secret)
    .update(signedPayload)
    .digest('hex');

  const signatureHeader = `t=${timestamp},v1=${signature}`;

  try {
    const response = await fetch(registration.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Webhook-ID': event.eventId,
        'X-Webhook-Signature': signatureHeader,
        'X-Webhook-Timestamp': String(timestamp),
        'User-Agent': 'TicketPulse-Webhooks/1.0',
      },
      body: payload,
      signal: AbortSignal.timeout(10000),  // 10 second timeout
    });

    const responseBody = await response.text();

    // Record the delivery result
    await db.query(
      `UPDATE webhook_deliveries
       SET status = $1, attempts = attempts + 1, last_attempt_at = NOW(),
           response_status = $2, response_body = $3
       WHERE registration_id = $4 AND event_id = $5`,
      [
        response.ok ? 'delivered' : 'failed',
        response.status,
        responseBody.substring(0, 1000),  // Truncate to avoid storing huge responses
        registration.id,
        event.eventId,
      ]
    );

    if (response.ok) {
      // Reset failure count on success
      await db.query(
        'UPDATE webhook_registrations SET failure_count = 0 WHERE id = $1',
        [registration.id]
      );
      console.log(`[webhook] Delivered ${event.eventType} to ${registration.url} (${response.status})`);
    } else {
      await incrementFailureCount(registration.id);
      console.log(`[webhook] Failed delivery to ${registration.url}: ${response.status}`);
    }
  } catch (error: any) {
    await db.query(
      `UPDATE webhook_deliveries
       SET status = 'failed', attempts = attempts + 1, last_attempt_at = NOW(),
           response_body = $1
       WHERE registration_id = $2 AND event_id = $3`,
      [error.message, registration.id, event.eventId]
    );
    await incrementFailureCount(registration.id);
    console.log(`[webhook] Delivery error to ${registration.url}: ${error.message}`);
  }
}

async function incrementFailureCount(registrationId: string): Promise<void> {
  const result = await db.query(
    `UPDATE webhook_registrations
     SET failure_count = failure_count + 1, updated_at = NOW()
     WHERE id = $1
     RETURNING failure_count`,
    [registrationId]
  );

  const failureCount = result.rows[0]?.failure_count || 0;

  // After 50 consecutive failures, disable the webhook
  if (failureCount >= 50) {
    await db.query(
      'UPDATE webhook_registrations SET active = false WHERE id = $1',
      [registrationId]
    );
    console.log(`[webhook] Disabled registration ${registrationId} after ${failureCount} consecutive failures`);
    // In production: notify the partner via email
  }
}
```

Trigger it from the purchase flow:

```typescript
// src/services/order.service.ts (excerpt)

import { dispatchWebhook } from '../webhooks/webhook-sender';

async function completePurchase(order: Order): Promise<void> {
  // ... payment, ticket issuance ...

  // Dispatch webhook
  await dispatchWebhook({
    eventId: `evt_${crypto.randomUUID()}`,
    eventType: 'ticket.purchased',
    data: {
      orderId: order.id,
      eventId: order.eventId,
      ticketCount: order.quantity,
      totalCents: order.totalInCents,
      purchasedAt: new Date().toISOString(),
    },
    occurredAt: new Date().toISOString(),
  });
}
```

---

## 3. Build: The Consumer Side (8 minutes)

This is what a partner builds to receive webhooks:

```typescript
// partner-app/webhook-consumer.ts

import express from 'express';
import crypto from 'crypto';

const app = express();
// IMPORTANT: use raw body for signature verification
app.use('/webhooks', express.raw({ type: 'application/json' }));

const WEBHOOK_SECRET = process.env.TICKETPULSE_WEBHOOK_SECRET!;

app.post('/webhooks/ticketpulse', async (req, res) => {
  const rawBody = req.body.toString();
  const signatureHeader = req.headers['x-webhook-signature'] as string;
  const eventId = req.headers['x-webhook-id'] as string;

  // Step 1: Verify the signature
  try {
    verifySignature(WEBHOOK_SECRET, signatureHeader, rawBody);
  } catch (error: any) {
    console.error('[webhook] Signature verification failed:', error.message);
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const event = JSON.parse(rawBody);

  // Step 2: Idempotency check -- have we already processed this event?
  const alreadyProcessed = await db.query(
    'SELECT id FROM processed_webhook_events WHERE event_id = $1',
    [eventId]
  );
  if (alreadyProcessed.rows.length > 0) {
    console.log(`[webhook] Already processed event ${eventId}, acknowledging`);
    return res.status(200).json({ status: 'already_processed' });
  }

  // Step 3: Process the event
  try {
    console.log(`[webhook] Processing ${event.eventType}: ${JSON.stringify(event.data)}`);

    // Partner-specific logic
    if (event.eventType === 'ticket.purchased') {
      await handleTicketPurchased(event.data);
    }

    // Step 4: Record that we processed this event
    await db.query(
      'INSERT INTO processed_webhook_events (event_id, processed_at) VALUES ($1, NOW())',
      [eventId]
    );

    // Return 200 immediately -- TicketPulse will not retry
    res.status(200).json({ status: 'processed' });
  } catch (error: any) {
    console.error(`[webhook] Processing failed for ${eventId}:`, error);
    // Return 500 -- TicketPulse will retry
    res.status(500).json({ error: 'Processing failed' });
  }
});

function verifySignature(secret: string, signatureHeader: string, rawBody: string): void {
  const parts = Object.fromEntries(
    signatureHeader.split(',').map(p => {
      const [key, ...rest] = p.split('=');
      return [key, rest.join('=')];
    })
  );

  const timestamp = parseInt(parts.t);
  const receivedSignature = parts.v1;

  // Reject if timestamp is too old (prevent replay attacks)
  const fiveMinutesAgo = Math.floor(Date.now() / 1000) - 300;
  if (timestamp < fiveMinutesAgo) {
    throw new Error('Webhook timestamp too old -- possible replay attack');
  }

  const signedPayload = `${timestamp}.${rawBody}`;
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  // IMPORTANT: Use timing-safe comparison to prevent timing attacks
  if (!crypto.timingSafeEqual(
    Buffer.from(receivedSignature),
    Buffer.from(expectedSignature)
  )) {
    throw new Error('Invalid webhook signature');
  }
}

app.listen(4000, () => console.log('[partner-app] Listening on :4000'));
```

**Key security details:**
- `express.raw()` instead of `express.json()`: signature verification must use the raw body bytes, not a re-serialized JSON object (whitespace differences would break the signature)
- `crypto.timingSafeEqual`: constant-time comparison prevents attackers from guessing the signature byte-by-byte via timing analysis
- Timestamp check: prevents replay attacks where someone captures a valid webhook and replays it later

---

## 4. Build: Retry with Exponential Backoff (8 minutes)

Failed deliveries are retried with increasing delays:

```typescript
// src/webhooks/webhook-retry-processor.ts

import { Pool } from 'pg';

const db = new Pool({ connectionString: process.env.DATABASE_URL });

// Retry schedule: 1min, 5min, 30min, 2hr, 12hr
const RETRY_DELAYS_MS = [
  60_000,        // 1 minute
  300_000,       // 5 minutes
  1_800_000,     // 30 minutes
  7_200_000,     // 2 hours
  43_200_000,    // 12 hours
];

const MAX_ATTEMPTS = RETRY_DELAYS_MS.length + 1;  // Initial attempt + retries

export async function processRetries(): Promise<void> {
  // Find failed deliveries that are due for retry
  const result = await db.query(
    `SELECT d.id, d.registration_id, d.event_id, d.event_type, d.payload,
            d.attempts, d.last_attempt_at,
            r.url, r.secret, r.active
     FROM webhook_deliveries d
     JOIN webhook_registrations r ON d.registration_id = r.id
     WHERE d.status = 'failed'
       AND d.attempts < $1
       AND r.active = true
     ORDER BY d.last_attempt_at ASC
     LIMIT 100`,
    [MAX_ATTEMPTS]
  );

  for (const delivery of result.rows) {
    const retryIndex = delivery.attempts - 1;
    const retryDelay = RETRY_DELAYS_MS[retryIndex] || RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1];
    const nextRetryAt = new Date(delivery.last_attempt_at).getTime() + retryDelay;

    if (Date.now() < nextRetryAt) {
      continue; // Not time yet
    }

    console.log(`[retry] Retrying delivery ${delivery.id} (attempt ${delivery.attempts + 1}/${MAX_ATTEMPTS})`);

    try {
      // Re-attempt delivery (reuse the existing deliverWebhook function)
      await deliverWebhook(
        { id: delivery.registration_id, url: delivery.url, secret: delivery.secret },
        JSON.parse(delivery.payload)
      );
    } catch (error: any) {
      // If max attempts reached, move to dead letter
      if (delivery.attempts + 1 >= MAX_ATTEMPTS) {
        await db.query(
          `UPDATE webhook_deliveries SET status = 'dead_letter' WHERE id = $1`,
          [delivery.id]
        );
        console.log(`[retry] Delivery ${delivery.id} moved to dead letter queue after ${MAX_ATTEMPTS} attempts`);
      }
    }
  }
}

// Run every 30 seconds
setInterval(processRetries, 30_000);
```

---

## 5. Try It: End-to-End Webhook Flow (5 minutes)

```bash
# Terminal 1: Start the partner webhook consumer
npx ts-node partner-app/webhook-consumer.ts

# Terminal 2: Register a webhook
curl -X POST http://localhost:3000/api/webhooks \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <partner-token>' \
  -d '{
    "url": "http://localhost:4000/webhooks/ticketpulse",
    "eventTypes": ["ticket.purchased", "order.cancelled"]
  }'
# Save the returned secret

# Terminal 3: Buy a ticket
curl -X POST http://localhost:3000/api/orders \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <user-token>' \
  -d '{"eventId": "evt_1", "ticketType": "general", "quantity": 2}'

# Check Terminal 1 -- the webhook should arrive within seconds:
# [webhook] Processing ticket.purchased: {"orderId":"ord_abc","eventId":"evt_1",...}
```

Alternatively, use webhook.site for testing without running a local server:

```bash
curl -X POST http://localhost:3000/api/webhooks \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <partner-token>' \
  -d '{
    "url": "https://webhook.site/<your-uuid>",
    "eventTypes": ["ticket.purchased"]
  }'
```

---

## 6. Observe: Delivery Metrics (5 minutes)

```typescript
// src/webhooks/webhook-metrics.ts

import { Counter, Histogram, Gauge } from 'prom-client';

const webhookDeliveryTotal = new Counter({
  name: 'webhook_deliveries_total',
  help: 'Total webhook delivery attempts',
  labelNames: ['event_type', 'status'],  // status: 'success', 'failed', 'dead_letter'
});

const webhookDeliveryLatency = new Histogram({
  name: 'webhook_delivery_duration_seconds',
  help: 'Webhook delivery latency',
  labelNames: ['event_type'],
  buckets: [0.1, 0.5, 1, 2, 5, 10],
});

const webhookQueueSize = new Gauge({
  name: 'webhook_pending_deliveries',
  help: 'Number of pending webhook deliveries',
});
```

Grafana dashboard:

```
Panel 1 - Delivery Success Rate:
  rate(webhook_deliveries_total{status="success"}[5m]) /
  rate(webhook_deliveries_total[5m])
  Alert: if < 95% for 10 minutes

Panel 2 - Delivery Latency (p95):
  histogram_quantile(0.95, rate(webhook_delivery_duration_seconds_bucket[5m]))

Panel 3 - Dead Letter Queue Size:
  webhook_deliveries_total{status="dead_letter"}

Panel 4 - Pending Deliveries:
  webhook_pending_deliveries
  Alert: if > 1000 → "Webhook delivery backlog growing"
```

---

## 7. Idempotency (3 minutes)

Webhooks guarantee **at-least-once** delivery. The same event may be delivered multiple times because:
- Network issues cause ambiguous responses (the consumer processed it but TicketPulse did not receive the 200)
- Retry logic re-sends a previously successful delivery
- Infrastructure failures cause duplicate dispatches

The consumer MUST deduplicate by `event_id`. The implementation was shown in section 3: check `processed_webhook_events` before processing, insert after processing.

The producer includes the `event_id` in every delivery. The consumer is responsible for idempotency.

---

## Checkpoint

Before continuing, verify:

- [ ] Partners can register webhook URLs for specific event types
- [ ] URL verification prevents registering broken endpoints
- [ ] Deliveries include HMAC-SHA256 signature
- [ ] Consumer verifies signature with timing-safe comparison
- [ ] Timestamp check prevents replay attacks
- [ ] Failed deliveries are retried with exponential backoff
- [ ] After max retries, events go to dead letter queue
- [ ] After 50 consecutive failures, the webhook is disabled
- [ ] Consumer deduplicates by event_id

```bash
git add -A && git commit -m "feat: add webhook system with HMAC signing, retry, dead letter queue, and idempotency"
```

---

## Reflect

> A partner's webhook endpoint is down for 2 hours. How does TicketPulse handle the backlog?
>
> During the outage:
> - First few deliveries fail and enter the retry queue
> - After 50 consecutive failures, the webhook is disabled
> - No further delivery attempts are made (avoiding wasted resources)
> - TicketPulse notifies the partner that their webhook was disabled
>
> After the partner fixes their endpoint:
> - They re-enable the webhook via the admin API
> - They request a replay of missed events using the delivery log:
>   `POST /api/webhooks/:id/replay?since=2026-03-24T10:00:00Z`
> - TicketPulse re-sends all events from the specified time range
>
> The delivery log is the key. Without it, missed events are lost forever. With it, partners can recover from any outage.

---

## Further Reading

- Stripe Webhooks documentation -- the gold standard for webhook design (signature verification, retry policy, event replay)
- "API Design Patterns" by JJ Geewax, Chapter 14 -- webhooks and event-driven APIs
- Svix -- open-source webhook delivery service (if you do not want to build your own retry/delivery infrastructure)
- Standard Webhooks (standardwebhooks.com) -- an industry effort to standardize webhook signatures and delivery semantics

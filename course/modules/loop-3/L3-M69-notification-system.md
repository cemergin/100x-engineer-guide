# L3-M69: Notification System

> **Loop 3 (Mastery)** | Section 3B: Real-Time & Advanced Features | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M33, L1-M22
>
> **Source:** Chapters 23, 10 of the 100x Engineer Guide

## What You'll Learn

- Designing a multi-channel notification system for TicketPulse: push, email, SMS, in-app
- Implementing priority queues so payment confirmations always cut ahead of marketing emails
- Building deduplication to guarantee no user gets the same notification twice
- Tracking delivery status: sent, delivered, opened, clicked
- Handling user preferences, opt-outs, and quiet hours
- Designing notification templates with variable substitution
- Dealing with delivery failures: bounces, invalid tokens, retries

## Why This Matters

A user buys a ticket on TicketPulse. They should immediately receive: an email confirmation with the ticket details, a push notification on their phone, and an in-app notification in TicketPulse's notification center. If they opted in to SMS, they should get a text too.

This seems simple until you think about what else the notification system handles: event reminders 24 hours before the show, marketing emails about similar events, fraud alerts if someone tries to access their account, and system-wide announcements. Some of these are urgent (payment confirmation, fraud alert). Some can wait (event reminder). Some should be batched (marketing).

Slack sends 5B+ push notifications per month. Their system batches notifications to avoid waking users with 50 pings for 50 channel messages. Building a notification system that is reliable, respectful of user preferences, and does not send duplicates is harder than it looks.

---

## 1. Design: The TicketPulse Notification System (10 minutes)

Before reading the architecture, design it yourself. Here are the requirements:

### Notification Types

| Type | Priority | Channels | Timing |
|------|----------|----------|--------|
| Purchase confirmation | Critical | Email + Push + In-app | Immediate |
| Payment failure | Critical | Email + Push | Immediate |
| Event reminder | High | Push + Email | Scheduled (24h before) |
| Event cancellation | High | All opted-in channels | Immediate |
| Similar events recommendation | Low | Email | Batched weekly |
| System maintenance | Normal | In-app | Immediate |

### Questions to Answer

1. How do you ensure a purchase confirmation is sent before a marketing email?
2. If the email service is down, what happens to the purchase confirmation?
3. If a user opts out of push notifications, how does the system know?
4. How do you prevent sending the same "order shipped" notification twice if the upstream service retries?

Write down your design. Then continue.

---

## 2. Architecture Overview

```
  ┌──────────────┐  ┌──────────┐  ┌──────────┐
  │ Purchase     │  │ Event    │  │ Marketing│
  │ Service      │  │ Service  │  │ Engine   │
  └──────┬───────┘  └────┬─────┘  └────┬─────┘
         │               │              │
         └───────────────┼──────────────┘
                         │
                  ┌──────▼──────┐
                  │ Notification│
                  │   Gateway   │
                  │             │
                  │ - Validate  │
                  │ - Dedup     │
                  │ - Prefs     │
                  │ - Route     │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   Priority  │
                  │   Queues    │
                  │  (Kafka or  │
                  │   Redis)    │
                  └──────┬──────┘
                         │
         ┌───────┬───────┼───────┬────────┐
         │       │       │       │        │
    ┌────▼──┐ ┌──▼───┐ ┌▼────┐ ┌▼─────┐  │
    │ Push  │ │Email │ │SMS  │ │In-App│  │
    │Worker │ │Worker│ │Work.│ │Worker│  │
    └───┬───┘ └──┬───┘ └──┬──┘ └──┬───┘  │
        │        │        │       │       │
    ┌───▼───┐ ┌──▼──┐ ┌──▼───┐   │  ┌────▼────┐
    │APNs / │ │SES /│ │Twilio│   │  │  Redis  │
    │ FCM   │ │SMTP │ │      │   │  │ (dedup) │
    └───────┘ └─────┘ └──────┘   │  └─────────┘
                                 │
                          ┌──────▼──────┐
                          │ PostgreSQL  │
                          │(notif logs) │
                          └─────────────┘
```

The key insight: the **Notification Gateway** is a single entry point that handles all the cross-cutting concerns (deduplication, user preferences, priority routing) before any channel-specific worker touches the notification.

---

## 3. Build: Priority Queues

Not all notifications are equal. A 2FA code must be delivered in seconds. A marketing email can wait an hour.

### Using Redis Sorted Sets

```javascript
const Redis = require('ioredis');
const redis = new Redis();

// Priority levels (lower number = higher priority)
const PRIORITY = {
  CRITICAL: 0,  // 2FA codes, fraud alerts, payment confirmations
  HIGH: 1,      // Event reminders, cancellations
  NORMAL: 2,    // System notifications
  LOW: 3        // Marketing, recommendations
};

// Enqueue a notification with priority
async function enqueueNotification(notification) {
  const { id, priority, channel } = notification;

  // Score combines priority (major) and timestamp (minor within same priority)
  // Priority 0 at timestamp 1679000000 → score = 0 * 1e13 + 1679000000000
  // Priority 3 at timestamp 1679000000 → score = 3 * 1e13 + 1679000000000
  const score = priority * 1e13 + Date.now();

  await redis.zadd(
    `notifications:${channel}`,
    score,
    JSON.stringify(notification)
  );
}

// Dequeue the highest-priority notification for a channel
async function dequeueNotification(channel) {
  // ZPOPMIN returns the member with the lowest score
  // (lowest priority number + earliest timestamp = most urgent)
  const result = await redis.zpopmin(`notifications:${channel}`, 1);

  if (!result || result.length === 0) return null;

  return JSON.parse(result[0]);
}
```

### Using Kafka Topics (Production Scale)

For higher throughput, use separate Kafka topics per priority:

```javascript
// Kafka producer -- route to priority-specific topic
async function enqueueKafka(notification) {
  const topicMap = {
    [PRIORITY.CRITICAL]: 'notifications.critical',
    [PRIORITY.HIGH]:     'notifications.high',
    [PRIORITY.NORMAL]:   'notifications.normal',
    [PRIORITY.LOW]:      'notifications.low'
  };

  await producer.send({
    topic: topicMap[notification.priority],
    messages: [{
      key: notification.userId,      // Partition by user for ordering
      value: JSON.stringify(notification),
      headers: {
        channel: notification.channel,
        idempotencyKey: notification.idempotencyKey
      }
    }]
  });
}

// Consumer allocation:
// notifications.critical → 50 consumer instances, 0 lag tolerance
// notifications.high     → 30 consumer instances
// notifications.normal   → 20 consumer instances
// notifications.low      → 5 consumer instances, batch processing
```

Critical notifications get the most consumers and the tightest monitoring. Low-priority marketing emails get few consumers and batch hourly.

---

## 4. Build: Deduplication

The purchase service retries on timeout. The notification gateway receives the same "order confirmed" notification twice. Without deduplication, the user gets two identical emails.

### Two-Layer Dedup

```javascript
async function isDuplicate(idempotencyKey) {
  // Layer 1: Redis (fast path, covers 99% of cases)
  const exists = await redis.set(
    `dedup:${idempotencyKey}`,
    '1',
    'NX',  // Only set if key does not exist
    'EX',  // Expire
    86400  // 24 hours
  );

  // If set succeeded (returned 'OK'), this is NOT a duplicate
  if (exists === 'OK') return false;

  // Key already existed -- this IS a duplicate
  return true;
}

// In the notification gateway
async function processNotification(notification) {
  // Check dedup first
  if (await isDuplicate(notification.idempotencyKey)) {
    console.log(`Duplicate notification rejected: ${notification.idempotencyKey}`);
    return { status: 'duplicate' };
  }

  // Layer 2: Database constraint (catches any Redis failures)
  try {
    await db.query(
      `INSERT INTO notification_log (idempotency_key, user_id, template_id, channel, status)
       VALUES ($1, $2, $3, $4, 'queued')`,
      [notification.idempotencyKey, notification.userId, notification.templateId, notification.channel]
    );
  } catch (err) {
    if (err.code === '23505') { // Unique constraint violation
      return { status: 'duplicate' };
    }
    throw err;
  }

  // Not a duplicate -- proceed
  await enqueueNotification(notification);
  return { status: 'queued' };
}
```

### Idempotency Key Design

The caller must provide a meaningful idempotency key. Good examples:

```
"order_confirmed:ORD-456"         -- one confirmation per order
"event_reminder:evt_001:user_123" -- one reminder per event per user
"password_reset:user_123:1679000" -- one reset email per user per hour
```

Bad idempotency keys:

```
"abc123"                -- random, prevents nothing
""                      -- empty, no dedup at all
"notification_1679000"  -- timestamp-based, every retry gets a new key
```

---

## 5. Delivery Tracking

After sending, track what happens to each notification.

### State Machine

```
queued → sending → sent → delivered → opened → clicked
                        ↘ failed → retry_1 → retry_2 → retry_3 → dead_letter
                        ↘ bounced
```

```sql
CREATE TABLE notification_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(255) UNIQUE,
    user_id         BIGINT NOT NULL,
    template_id     VARCHAR(100) NOT NULL,
    channel         VARCHAR(10) NOT NULL,
    priority        SMALLINT DEFAULT 2,
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',
    payload         JSONB,
    sent_at         TIMESTAMP,
    delivered_at    TIMESTAMP,
    opened_at       TIMESTAMP,
    clicked_at      TIMESTAMP,
    failure_reason  TEXT,
    retry_count     SMALLINT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notif_user_created ON notification_log(user_id, created_at DESC);
CREATE INDEX idx_notif_status ON notification_log(status) WHERE status IN ('failed', 'sending');
```

### Tracking Email Opens and Clicks

**Open tracking** uses a tracking pixel -- a 1x1 transparent image embedded in the email:

```html
<!-- In the email template -->
<img src="https://track.ticketpulse.com/open/notif_abc123" width="1" height="1" />
```

When the email client loads the image, your server records the open:

```javascript
app.get('/open/:notificationId', (req, res) => {
  const { notificationId } = req.params;

  // Record the open asynchronously (don't block the response)
  recordOpen(notificationId).catch(console.error);

  // Return a 1x1 transparent GIF
  const pixel = Buffer.from(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
    'base64'
  );
  res.set('Content-Type', 'image/gif');
  res.set('Cache-Control', 'no-store');
  res.send(pixel);
});
```

**Click tracking** uses redirect URLs:

```html
<!-- In the email template, instead of direct links -->
<a href="https://track.ticketpulse.com/click/notif_abc123?url=https://ticketpulse.com/orders/ORD-456">
  View your order
</a>
```

```javascript
app.get('/click/:notificationId', (req, res) => {
  const { notificationId } = req.params;
  const { url } = req.query;

  // Record the click
  recordClick(notificationId).catch(console.error);

  // Redirect to the actual URL
  res.redirect(302, url);
});
```

Privacy note: many email clients now block tracking pixels by default (Apple Mail Privacy Protection, Hey.com). Open rates are increasingly unreliable. Click tracking is more trustworthy because the user actively chose to interact.

---

## 6. User Preferences

Users must control what they receive and how.

```javascript
// Notification preference check -- runs in the gateway before queueing
async function shouldSend(userId, notification) {
  const prefs = await getPreferences(userId);

  // Check channel opt-in
  if (notification.channel === 'push' && !prefs.pushEnabled) return false;
  if (notification.channel === 'email' && !prefs.emailEnabled) return false;
  if (notification.channel === 'sms' && !prefs.smsEnabled) return false;

  // Check category opt-in
  const categoryPref = prefs.categories?.[notification.category];
  if (categoryPref && categoryPref[notification.channel] === false) return false;

  // Check quiet hours (except for critical priority)
  if (notification.priority > PRIORITY.CRITICAL) {
    if (isQuietHours(prefs.quietHours)) {
      // Queue for delivery after quiet hours end
      notification.scheduledFor = getQuietHoursEnd(prefs.quietHours);
      return true; // Still send, but delayed
    }
  }

  // Check frequency caps (max 5 marketing emails per week)
  if (notification.category === 'marketing') {
    const recentCount = await getRecentNotificationCount(
      userId, 'marketing', 'email', 7 * 24 * 60 * 60 // 7 days
    );
    if (recentCount >= 5) return false;
  }

  return true;
}
```

### The Preference Schema

```javascript
// User preferences API
const defaultPreferences = {
  pushEnabled: true,
  emailEnabled: true,
  smsEnabled: false,     // Opt-in only (SMS costs money)
  quietHours: {
    enabled: false,
    start: '22:00',
    end: '07:00',
    timezone: 'UTC'
  },
  categories: {
    transactional: { push: true, email: true, sms: true },   // Cannot fully disable
    reminders:     { push: true, email: true, sms: false },
    marketing:     { push: false, email: true, sms: false },
    system:        { push: true, email: false, sms: false }
  }
};
```

Important: transactional notifications (purchase confirmations, password resets) should not be fully opt-outable. The user bought a ticket -- they need the confirmation. CAN-SPAM and similar regulations allow transactional emails without opt-in.

---

## 7. Template System

Hardcoding notification content is unmaintainable. Use templates:

```javascript
// templates/order_confirmed.json
{
  "id": "order_confirmed",
  "channels": {
    "email": {
      "subject": "Your TicketPulse order is confirmed!",
      "body": "Hi {{userName}},\n\nYour tickets for {{eventName}} on {{eventDate}} are confirmed.\n\nOrder: {{orderId}}\nSeats: {{seatList}}\nTotal: ${{totalAmount}}\n\nSee you there!"
    },
    "push": {
      "title": "Tickets confirmed!",
      "body": "Your {{ticketCount}} ticket(s) for {{eventName}} are ready."
    },
    "sms": {
      "body": "TicketPulse: Your tickets for {{eventName}} ({{eventDate}}) are confirmed. Order {{orderId}}."
    },
    "in_app": {
      "title": "Order confirmed",
      "body": "Your tickets for {{eventName}} are ready.",
      "action": { "type": "navigate", "target": "/orders/{{orderId}}" }
    }
  }
}

// Template rendering
function renderTemplate(template, channel, data) {
  let content = { ...template.channels[channel] };

  // Replace all {{variable}} placeholders
  for (const [key, value] of Object.entries(data)) {
    const placeholder = `{{${key}}}`;
    for (const field of Object.keys(content)) {
      if (typeof content[field] === 'string') {
        content[field] = content[field].replace(new RegExp(placeholder, 'g'), value);
      }
    }
  }

  return content;
}
```

---

## 8. Failure Handling

Notifications fail. Email addresses bounce. Push tokens expire. SMS delivery fails. Your system must handle each gracefully.

```javascript
async function handleDeliveryFailure(notification, error) {
  const { id, channel, retryCount } = notification;

  // Classify the failure
  if (isTransientError(error)) {
    // Temporary failure -- retry with backoff
    if (retryCount < 3) {
      const delays = [30_000, 300_000, 3600_000]; // 30s, 5m, 1h
      await scheduleRetry(notification, delays[retryCount]);
      await updateStatus(id, `retry_${retryCount + 1}`);
    } else {
      await updateStatus(id, 'dead_letter');
      await alertOps(notification, 'Max retries exceeded');
    }
  } else if (isPermanentError(error)) {
    // Permanent failure -- don't retry
    await updateStatus(id, 'failed', error.message);

    // Handle channel-specific permanent failures
    if (channel === 'push' && error.type === 'INVALID_TOKEN') {
      // Device uninstalled the app -- remove the push token
      await removePushToken(notification.userId, error.token);
    }
    if (channel === 'email' && error.type === 'HARD_BOUNCE') {
      // Email address is invalid -- disable email for this user
      await disableEmailForUser(notification.userId);
    }
  }
}

function isTransientError(error) {
  // Network timeouts, rate limits, temporary service outages
  return ['TIMEOUT', 'RATE_LIMITED', 'SERVICE_UNAVAILABLE'].includes(error.type);
}

function isPermanentError(error) {
  // Invalid tokens, hard bounces, unsubscribed
  return ['INVALID_TOKEN', 'HARD_BOUNCE', 'UNREGISTERED'].includes(error.type);
}
```

---

## 9. Reflect: The Full Flow

Think through this end-to-end:

> A user buys a ticket on TicketPulse. They should receive:
> 1. Email confirmation with ticket details
> 2. Push notification on their phone
> 3. SMS (if opted in)
> 4. In-app notification
>
> Design the flow from the purchase service to final delivery on all channels.

Your answer should cover:
- Who calls the notification gateway (the purchase service)
- What idempotency key is used (`order_confirmed:ORD-456`)
- How user preferences are checked
- How priority routing works (purchase confirmation = critical)
- What happens if the email service is temporarily down
- How the user's notification center gets populated

---

## 10. Checkpoint

Before moving on, verify:

- [ ] You can explain the role of the notification gateway as a single entry point
- [ ] Priority queues ensure critical notifications are processed first
- [ ] Deduplication uses two layers: Redis (fast) and database (correct)
- [ ] You understand how email open tracking (pixel) and click tracking (redirect) work
- [ ] User preferences are checked before queueing, not after
- [ ] Transient failures retry with backoff; permanent failures update user state
- [ ] Templates separate content from delivery logic

---

## Summary

A notification system is deceptively complex. The core is straightforward: receive a notification request, check preferences, queue by priority, deliver through the appropriate channel. The difficulty is in the edge cases: deduplication, retries, permanent failures, quiet hours, frequency caps, and tracking.

The key architectural decisions: a gateway that centralizes cross-cutting concerns, priority queues that ensure urgent notifications beat marketing emails, two-layer deduplication for correctness, and a state machine that tracks every notification from creation to delivery.

This pattern scales from TicketPulse (thousands of notifications per day) to Slack-scale (billions per month) by adjusting the queue infrastructure (Redis sorted sets to Kafka topics) and the number of channel workers.

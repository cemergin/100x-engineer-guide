# L3-M87: Mobile Backend Patterns

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 45 min | 🟡 Deep Dive | Prerequisites: L2-M36, L3-M67
>
> **Source:** Chapter 10 of the 100x Engineer Guide

## What You'll Learn

- Push notification architecture: FCM/APNs device registration, token management, and delivery guarantees
- Offline-first patterns: how the TicketPulse mobile app works on the subway with no network
- API optimization for mobile: minimizing round trips, compressing responses, cursor-based pagination
- Deep linking: making "share this event" open the app (or fall back to web)
- Battery and data awareness: reducing polling when backgrounded, batching deliveries

## Why This Matters

TicketPulse is launching a mobile app. The product team is excited. The backend team is nervous -- and they should be.

Mobile changes everything about how you design a backend. A web app has a reliable network connection, unlimited power, and you control when users get the latest version. A mobile app has intermittent connectivity, limited battery, users who refuse to update, and an operating system that will kill your background processes without warning.

The patterns that work for web do not translate directly. Polling every 2 seconds drains the battery. Large JSON responses consume mobile data plans. Requiring network connectivity means the app is useless on the subway. And your API versioning strategy matters more because you cannot force-update a mobile app the way you can deploy a new web frontend.

This module covers the backend patterns that make mobile apps work well: push notifications for real-time updates without polling, offline-first architecture for unreliable networks, API optimization for constrained clients, and deep linking for seamless sharing.

---

## 1. Push Notifications: FCM/APNs Architecture

### The Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────┐     ┌────────┐
│ TicketPulse │────▶│ FCM / APNs   │────▶│  Device  │────▶│  User  │
│ Backend     │     │ (Google/Apple)│     │  (Phone) │     │        │
└─────────────┘     └──────────────┘     └─────────┘     └────────┘
       ▲                                       │
       │         Device token registration     │
       └───────────────────────────────────────┘
```

1. The app starts, requests notification permission from the OS
2. The OS returns a **device token** (a unique identifier for this app on this device)
3. The app sends the token to TicketPulse's backend
4. The backend stores the token associated with the user
5. When something happens (ticket available from waitlist), the backend sends a push via FCM/APNs
6. FCM/APNs delivers the notification to the device

### Design: Device Token Management

```typescript
// Device token registration
interface DeviceToken {
  id: string;
  userId: string;
  token: string;             // The FCM/APNs token
  platform: 'ios' | 'android';
  appVersion: string;        // Track which version is installed
  lastActiveAt: Date;        // When the device last contacted the server
  createdAt: Date;
}
```

```sql
CREATE TABLE device_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token       TEXT NOT NULL,
  platform    VARCHAR(10) NOT NULL,
  app_version VARCHAR(20),
  last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(token)  -- A device token is globally unique
);

CREATE INDEX idx_device_tokens_user ON device_tokens (user_id);
```

**Key considerations:**

- **Stale tokens**: When a user uninstalls the app, you do not get notified. The token becomes stale. FCM/APNs will eventually tell you it is invalid (via error responses). Clean up stale tokens when delivery fails.
- **Multiple devices**: A user might have a phone and a tablet. Send to all active devices.
- **Token refresh**: Device tokens can change (app reinstall, OS update). Always upsert, not insert.

### Design: Notification Flow for TicketPulse

```typescript
// notification-service.ts

interface PushNotification {
  userId: string;
  title: string;
  body: string;
  data: Record<string, string>;  // Data payload for the app to process
  category?: string;              // Enables actionable notifications
}

async function sendPushNotification(notification: PushNotification): Promise<void> {
  // 1. Get all active device tokens for this user
  const tokens = await db.query(
    `SELECT token, platform FROM device_tokens
     WHERE user_id = $1 AND last_active_at > NOW() - INTERVAL '90 days'`,
    [notification.userId]
  );

  if (tokens.rows.length === 0) {
    console.log(`No active devices for user ${notification.userId}`);
    return;
  }

  // 2. Send to each device
  const results = await Promise.allSettled(
    tokens.rows.map(async (device) => {
      if (device.platform === 'android') {
        return sendViaFCM(device.token, notification);
      } else {
        return sendViaAPNs(device.token, notification);
      }
    })
  );

  // 3. Clean up invalid tokens
  for (let i = 0; i < results.length; i++) {
    if (results[i].status === 'rejected') {
      const error = (results[i] as PromiseRejectedResult).reason;
      if (error.code === 'INVALID_TOKEN' || error.code === 'UNREGISTERED') {
        await db.query(
          `DELETE FROM device_tokens WHERE token = $1`,
          [tokens.rows[i].token]
        );
      }
    }
  }
}
```

### The Critical Rule: Push Is Best-Effort

Push notifications are NOT guaranteed to be delivered. The device might be off, in airplane mode, or have notifications disabled. FCM/APNs might be experiencing an outage. The OS might silently drop the notification.

**Always have a fallback**: an in-app notification inbox that the app checks when it opens. Push is a "tap on the shoulder" -- the in-app inbox is the reliable source of truth.

```typescript
// Always write to in-app inbox AND send push
async function notifyUser(userId: string, notification: Notification): Promise<void> {
  // 1. Write to persistent in-app inbox (always reliable)
  await db.query(
    `INSERT INTO notifications (user_id, type, title, body, data, read)
     VALUES ($1, $2, $3, $4, $5, false)`,
    [userId, notification.type, notification.title, notification.body, notification.data]
  );

  // 2. Send push notification (best-effort)
  await sendPushNotification({
    userId,
    title: notification.title,
    body: notification.body,
    data: { notificationId: notification.id, type: notification.type },
  }).catch(err => {
    console.error('Push delivery failed (non-critical):', err);
  });
}
```

---

## 2. Offline-First Patterns

### The Problem

A TicketPulse user is on the subway, browsing events they saved earlier. They have no network connection. What should happen?

**Bad**: The app shows a spinner forever, then an error. The user closes the app.

**Good**: The app shows cached events, lets the user browse and even add items to a cart. When the user resurfaces and has connectivity, the app syncs.

### Design: What Works Offline?

| Feature | Offline Behavior |
|---------|-----------------|
| Browse saved events | Works (cached data) |
| View purchased tickets | Works (cached + QR code stored locally) |
| Join a waitlist | Queued, synced when online |
| Purchase tickets | Blocked (requires real-time availability + payment) |
| Search events | Limited to cached results |

Not everything can work offline. Purchasing requires real-time seat availability and payment processing. But viewing tickets (the most common action at event entry) MUST work offline -- the user standing at the venue door with no signal needs to show their QR code.

### The Outbox Pattern on Mobile

For mutations that can be queued (join waitlist, update preferences, RSVP):

```typescript
// Client-side (React Native / mobile app)

interface PendingMutation {
  id: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'DELETE';
  body: any;
  createdAt: number;
  retryCount: number;
}

class OfflineQueue {
  private queue: PendingMutation[] = [];

  async enqueue(mutation: Omit<PendingMutation, 'id' | 'createdAt' | 'retryCount'>): Promise<void> {
    this.queue.push({
      ...mutation,
      id: generateId(),
      createdAt: Date.now(),
      retryCount: 0,
    });
    await this.persistToStorage();
    this.attemptSync();
  }

  async attemptSync(): Promise<void> {
    if (!navigator.onLine) return;

    for (const mutation of [...this.queue]) {
      try {
        await fetch(mutation.endpoint, {
          method: mutation.method,
          body: JSON.stringify(mutation.body),
          headers: { 'Content-Type': 'application/json' },
        });
        // Success — remove from queue
        this.queue = this.queue.filter(m => m.id !== mutation.id);
      } catch (error) {
        mutation.retryCount++;
        if (mutation.retryCount > 5) {
          // Give up, notify user
          this.queue = this.queue.filter(m => m.id !== mutation.id);
          notifyUser('Failed to sync: ' + mutation.endpoint);
        }
      }
    }
    await this.persistToStorage();
  }
}
```

### Conflict Resolution

When the user's queued mutation conflicts with a change that happened while they were offline:

```
User goes offline at 3:00 PM
  - User RSVPs to Event A (queued locally)
At 3:05 PM, Event A is cancelled (on the server)
User comes online at 3:10 PM
  - Sync tries to submit RSVP for a cancelled event
```

**Server wins** (simplest): The server rejects the stale mutation and returns an error. The client shows "Event A was cancelled while you were offline."

**Merge** (complex): For certain operations (like updating preferences), merge the changes. This is where CRDTs shine but adds significant complexity.

For TicketPulse, **server wins** is the right default. Events and tickets have strong consistency requirements. Optimistic UI shows the change immediately, but the server is the authority.

---

## 3. API Optimization for Mobile

### Minimize Round Trips

A web app making 5 API calls on page load is acceptable. A mobile app on a 3G connection paying 200ms per round trip cannot afford 5 sequential calls (1 second of latency before any data appears).

**Use the BFF pattern** (from L2-M36): a single endpoint that aggregates what the mobile app needs for each screen.

```typescript
// /api/mobile/v1/home
// Returns everything the home screen needs in one call
{
  "featuredEvents": [...],      // Top 5 featured
  "nearbyEvents": [...],        // Based on user location
  "savedEvents": [...],         // User's saved events
  "upcomingTickets": [...],     // Tickets for upcoming events
  "unreadNotifications": 3
}
```

One round trip instead of five.

### Compress Responses

```typescript
// Express middleware: enable compression for mobile clients
import compression from 'compression';

app.use(compression({
  filter: (req, res) => {
    // Always compress for mobile clients
    if (req.headers['x-client-type'] === 'mobile') return true;
    return compression.filter(req, res);
  },
  threshold: 1024, // Only compress responses > 1KB
}));
```

### Cursor-Based Pagination

Offset pagination (`?page=3&limit=20`) breaks when new items are inserted. The user scrolling through events sees duplicates or missing items because the offset shifted.

Cursor pagination is stable:

```typescript
// GET /api/mobile/v1/events?cursor=evt_abc123&limit=20

app.get('/api/mobile/v1/events', async (req, res) => {
  const { cursor, limit = 20 } = req.query;

  const events = await prisma.event.findMany({
    where: cursor ? { id: { lt: cursor } } : {},
    orderBy: { id: 'desc' },
    take: Number(limit) + 1,  // Fetch one extra to determine hasMore
  });

  const hasMore = events.length > Number(limit);
  if (hasMore) events.pop();

  res.json({
    events,
    cursor: events.length > 0 ? events[events.length - 1].id : null,
    hasMore,
  });
});
```

### API Versioning: You Cannot Force-Update

Mobile apps in the wild run old versions. Some users never update. Your API must support older versions longer than web:

```
Web:  Deploy new frontend + new API at the same time. Done.
Mobile: Deploy new API, but millions of users are on app v2.1
        which calls the old endpoint format. You must support both.
```

Rule of thumb: support at least the last 3 major versions of the mobile API. Use explicit version prefixes (`/api/mobile/v1/`, `/api/mobile/v2/`) and deprecation headers.

---

## 4. Deep Linking

### The Problem

A user shares a TicketPulse event link: `https://ticketpulse.com/events/evt_123`. The recipient taps it on their phone. What should happen?

- If the app is installed: open the app directly to that event
- If the app is not installed: open the website (which might prompt them to install the app)

### Universal Links (iOS) / App Links (Android)

The backend serves a configuration file that tells the OS which URLs should open in the app:

```json
// .well-known/apple-app-site-association (iOS)
{
  "applinks": {
    "apps": [],
    "details": [
      {
        "appID": "TEAM_ID.com.ticketpulse.app",
        "paths": [
          "/events/*",
          "/tickets/*",
          "/checkout/*"
        ]
      }
    ]
  }
}
```

```json
// .well-known/assetlinks.json (Android)
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.ticketpulse.app",
    "sha256_cert_fingerprints": ["AB:CD:EF:..."]
  }
}]
```

The backend must serve these files at exact paths with correct MIME types. This is a common source of bugs -- if the file is not served correctly, deep linking silently fails and the user ends up in the browser.

---

## 5. Battery and Data Awareness

### Reduce Background Activity

When the app is backgrounded, reduce or stop polling:

```typescript
// Client-side pattern
const FOREGROUND_POLL_INTERVAL = 30_000;  // 30 seconds
const BACKGROUND_POLL_INTERVAL = 300_000; // 5 minutes (or don't poll at all)

let pollInterval = FOREGROUND_POLL_INTERVAL;

AppState.addEventListener('change', (state) => {
  if (state === 'active') {
    pollInterval = FOREGROUND_POLL_INTERVAL;
    syncImmediately(); // Catch up when returning to foreground
  } else {
    pollInterval = BACKGROUND_POLL_INTERVAL;
  }
});
```

Better yet, use push notifications to wake the app for important updates instead of polling at all. A silent push (no visible notification) can trigger a background data fetch.

### Batch Notification Deliveries

Instead of sending a push notification for every small update, batch them:

```
Bad:  "Ticket A-15 sold" → push
      "Ticket A-16 sold" → push
      "Ticket A-17 sold" → push

Good: "3 tickets sold for Summer Festival" → single push (batched over 30s window)
```

---

## 6. Push Notification Exercises

These exercises build on the architecture in Section 1. They cover the scenarios that trip up most engineers implementing push for the first time.

### Exercise 1: Implement Notification Batching

The naive implementation sends one push per event. An active user might get 30 notifications in a minute when a popular event sells out and their friends share it. Users turn off notifications entirely.

Implement a batching system that aggregates notifications within a 30-second window:

```typescript
// notification-batch.service.ts

interface PendingNotification {
  userId: string;
  type: string;
  payload: Record<string, any>;
  createdAt: Date;
}

class NotificationBatcher {
  private pending: Map<string, PendingNotification[]> = new Map();
  private timer: NodeJS.Timeout | null = null;
  private readonly BATCH_WINDOW_MS = 30_000;

  async add(notification: PendingNotification): Promise<void> {
    const key = `${notification.userId}:${notification.type}`;

    if (!this.pending.has(key)) {
      this.pending.set(key, []);
    }
    this.pending.get(key)!.push(notification);

    // Schedule a flush if not already scheduled
    if (!this.timer) {
      this.timer = setTimeout(() => this.flush(), this.BATCH_WINDOW_MS);
    }
  }

  private async flush(): Promise<void> {
    this.timer = null;
    const batches = new Map(this.pending);
    this.pending.clear();

    for (const [key, notifications] of batches) {
      await this.sendBatch(notifications);
    }
  }

  private async sendBatch(notifications: PendingNotification[]): Promise<void> {
    const { userId, type } = notifications[0];

    if (notifications.length === 1) {
      // Single notification — send as-is
      await sendPushNotification({
        userId,
        title: this.buildTitle(notifications[0]),
        body: this.buildBody([notifications[0]]),
        data: notifications[0].payload,
      });
    } else {
      // Multiple notifications — summarize
      await sendPushNotification({
        userId,
        title: `${notifications.length} updates for you`,
        body: this.buildBatchSummary(notifications),
        data: {
          notificationType: 'batch',
          count: notifications.length,
          types: [...new Set(notifications.map(n => n.type))],
        },
      });
    }
  }

  private buildBatchSummary(notifications: PendingNotification[]): string {
    // Exercise: implement this based on the notification types
    // Example: "Ticket available for Summer Festival + 2 more"
    throw new Error('Implement buildBatchSummary');
  }
}
```

**Your task**: Implement `buildBatchSummary`. It should:
- Name the most recent notification specifically
- Count the remainder
- Keep the summary under 60 characters (push notification body limit on iOS)

Test your implementation with these scenarios:
1. Three "ticket available" notifications for the same event → should say "Ticket available: Summer Festival" (no batching needed, same event)
2. Two "ticket available" notifications for different events → "Ticket available: Summer + 1 more event"
3. Five notifications of mixed types → "3 tickets available + 2 price drops"

### Exercise 2: Implement Delivery Confirmation Tracking

Push is best-effort, but you need to know which notifications were actually delivered for analytics and support purposes. Implement a delivery receipt system:

```typescript
// notification-delivery.service.ts

interface NotificationRecord {
  id: string;
  userId: string;
  type: string;
  sentAt: Date;
  deliveredAt: Date | null;
  openedAt: Date | null;
  platform: 'ios' | 'android';
  token: string;
}

// Step 1: Record every notification before sending
async function recordAndSend(notification: PushNotification): Promise<string> {
  const notificationId = generateId();

  await db.query(
    `INSERT INTO notification_log (id, user_id, type, sent_at, platform)
     VALUES ($1, $2, $3, NOW(), $4)`,
    [notificationId, notification.userId, notification.type, notification.platform]
  );

  // Include notification ID in the push data payload
  // The app will use this to call back and confirm delivery/open
  await sendPushNotification({
    ...notification,
    data: {
      ...notification.data,
      notificationId,  // ← app receives this
    },
  });

  return notificationId;
}

// Step 2: App calls this endpoint when notification is received
// POST /api/mobile/v1/notifications/:id/delivered
app.post('/api/mobile/v1/notifications/:id/delivered', auth, async (req, res) => {
  await db.query(
    `UPDATE notification_log
     SET delivered_at = NOW()
     WHERE id = $1 AND user_id = $2`,
    [req.params.id, req.user.id]
  );
  res.status(204).end();
});

// Step 3: App calls this when user taps the notification
// POST /api/mobile/v1/notifications/:id/opened
app.post('/api/mobile/v1/notifications/:id/opened', auth, async (req, res) => {
  await db.query(
    `UPDATE notification_log
     SET opened_at = NOW()
     WHERE id = $1 AND user_id = $2`,
    [req.params.id, req.user.id]
  );
  res.status(204).end();
});

// Step 4: Analytics query — delivery and open rates by type
const analyticsQuery = `
  SELECT
    type,
    COUNT(*) AS sent,
    COUNT(delivered_at) AS delivered,
    COUNT(opened_at) AS opened,
    ROUND(COUNT(delivered_at)::numeric / COUNT(*) * 100, 1) AS delivery_rate_pct,
    ROUND(COUNT(opened_at)::numeric / NULLIF(COUNT(delivered_at), 0) * 100, 1) AS open_rate_pct
  FROM notification_log
  WHERE sent_at > NOW() - INTERVAL '7 days'
  GROUP BY type
  ORDER BY sent DESC;
`;
```

**Discussion**: What delivery rate would you expect for push notifications? (Industry average: 60-70% on iOS, 80-90% on Android for apps with notification permissions enabled.) What would a delivery rate below 40% tell you?

### Exercise 3: Token Refresh Handling

Device tokens change. An app reinstall, an OS update, or an iOS migration generates a new token. If you send to the old token, FCM/APNs returns an error. Your system must detect this and update the stored token.

```typescript
// token-refresh.service.ts

interface FCMErrorResponse {
  error: {
    code: number;
    message: string;
    status: string;
    details?: Array<{ type: string; errorCode?: string }>;
  };
}

async function handleFCMError(
  token: string,
  error: FCMErrorResponse,
  userId: string
): Promise<void> {
  const status = error.error.status;

  if (status === 'UNREGISTERED') {
    // Token is permanently invalid — app was uninstalled
    await db.query(
      `DELETE FROM device_tokens WHERE token = $1`,
      [token]
    );
    console.log(`Removed unregistered token for user ${userId}`);
    return;
  }

  if (status === 'INVALID_ARGUMENT') {
    // Token is malformed (data corruption, bug in token storage)
    await db.query(
      `DELETE FROM device_tokens WHERE token = $1`,
      [token]
    );
    console.log(`Removed invalid token for user ${userId}`);
    return;
  }

  // For UNAVAILABLE or INTERNAL errors: retry with exponential backoff
  // (don't delete the token — FCM is temporarily having issues)
  if (status === 'UNAVAILABLE' || status === 'INTERNAL') {
    throw new RetryableError(`FCM temporarily unavailable: ${error.error.message}`);
  }
}

// FCM v1 API also returns a new token in some responses
// Always check and upsert when provided
async function upsertTokenIfRefreshed(
  oldToken: string,
  newToken: string | null,
  userId: string
): Promise<void> {
  if (!newToken || newToken === oldToken) return;

  await db.query(
    `UPDATE device_tokens
     SET token = $1, updated_at = NOW()
     WHERE token = $2 AND user_id = $3`,
    [newToken, oldToken, userId]
  );
  console.log(`Refreshed token for user ${userId}`);
}
```

**Your task**: Write a function `pruneStaleTokens()` that runs daily and removes tokens that have not delivered a notification in 90 days. Use the `notification_log` table from Exercise 2 to identify stale tokens. What is the risk of being too aggressive (30 days)? What is the risk of being too conservative (180 days)?

---

## 7. Offline-First Sync Scenarios

These scenarios describe specific offline sync problems you will encounter building TicketPulse's mobile app. Work through each one before looking at the guidance.

### Scenario 1: The Checkout Conflict

**Setup**: A user adds 2 tickets for the Summer Festival to their cart while online. They lose connectivity on the subway. They tap "Purchase" (the app optimistically shows "Processing..."). When connectivity returns, the app attempts to submit the purchase.

**Problem**: In the 8 minutes they were offline, the 2 remaining tickets for that section sold out. The backend rejects the purchase.

**Questions to answer before reading the guidance:**
1. What should the app show when connectivity returns and the purchase fails?
2. The user had tickets in their cart — should you show them as "reserved" while they're in the cart?
3. How do you communicate that the 15-minute cart reservation window expires?

**Guidance:**

```
Mobile cart reservation model for TicketPulse:

1. Cart reservation is server-side, not client-side.
   When the user adds tickets to the cart (online), the server
   reserves them for 15 minutes. The app shows the countdown timer.

2. If the user goes offline, the countdown continues.
   The app shows "Your cart expires in X:XX" even offline, because
   the expiration time is known from the server response.

3. When connectivity returns, the app first checks if the reservation
   is still valid (GET /api/orders/cart/{cartId}/status).
   - If valid: proceed to purchase
   - If expired: show "Your cart expired. Available tickets: [X]"

4. The purchase button is DISABLED when offline.
   This is the key design decision: purchasing requires real-time
   availability confirmation. Do not allow optimistic purchases.

The user experience trade-off: users cannot purchase offline.
The business trade-off: no oversells, no fraud via offline state manipulation.
```

### Scenario 2: The Stale Profile Update

**Setup**: A user updates their notification preferences while offline (they turned off "venue announcements"). The app queues the mutation. When they come back online, the backend syncs the change.

**Problem**: In the meantime, a team member updated the user's notification preferences in the admin panel (adding them to a marketing campaign). The admin change happened while the user was offline.

**The conflict**: user set `venue_announcements = false`, admin set `marketing_opt_in = true`. These are different fields — they do not conflict.

**But what if**: user set `email_notifications = false`, admin set `email_notifications = true`.

**Questions:**
1. Whose change wins?
2. How do you detect that this is the same field, modified by two different actors?
3. What should you show the user when their preference sync results in a conflict?

**Guidance:**

```
Conflict resolution strategy for preference syncs:

Use "last writer wins" with a version vector:

1. Every preference update includes:
   - The value being set
   - The client timestamp (when the user made the change)
   - The client version (the version of the preferences when the
     user last synced)

2. The server applies changes if:
   client_version >= server_version at the time of the user's change

3. If client_version < server_version at the time of the change:
   the server DOES NOT apply the change but returns the current state.
   The app shows: "Your preference was updated by another session.
   Current setting: [X]. Do you want to override it?"

4. For admin overrides specifically:
   Admin changes are marked with an admin flag.
   Client mutations cannot override admin flags without confirmation.
```

### Scenario 3: The Duplicate Mutation Problem

**Setup**: The user joins a waitlist while offline. The mutation is queued. When connectivity returns, the app retries the queued mutation — but the first retry succeeded and the user IS on the waitlist. The second retry hits the unique constraint (`UNIQUE(userId, eventId)`) and gets a 409.

**Questions:**
1. Is this a real error or expected behavior?
2. How should the app handle a 409 on a queued mutation?
3. How do you prevent the user from thinking the queue failed?

**Guidance:**

```
Idempotency keys for offline mutations:

1. When queuing a mutation, generate a client-side idempotency key.
   const key = `join-waitlist:${userId}:${eventId}:${sessionId}`;

2. Include the key in the request header:
   Idempotency-Key: join-waitlist:user_abc:event_xyz:sess_123

3. Server stores the key and result for 24 hours:
   If the same key arrives again, return the original result without
   re-executing.

4. From the app's perspective: any 2xx response (including a cached
   repeat response) means "success." A 409 with a different user
   error should surface; a 409 that is "you are already on the list"
   should be treated as success.

5. The app should not retry 4xx errors blindly.
   Distinguish between:
   - 409 ALREADY_EXISTS: success (idempotent)
   - 409 CONFLICT: failure (conflicting state, user needs to resolve)
   - 429 RATE_LIMIT: wait and retry
   - 5xx SERVER_ERROR: retry with backoff
```

---

## 8. Reflect: Web vs Mobile Backend

### Stop and Think (5 minutes)

What is the single biggest difference between building a backend for web vs mobile?

Consider:
- Network reliability assumptions
- Update deployment model
- Power and resource constraints
- Offline behavior expectations
- Push vs pull for real-time data

The fundamental shift is from **assumed connectivity** (web) to **intermittent connectivity** (mobile). Every design decision flows from this: cache more aggressively, queue mutations locally, use push instead of poll, support old API versions, and always have an offline fallback.

---

---

## Cross-References

- **Chapter 10** (Mobile Backend Patterns): Full treatment of the BFF pattern, device-aware APIs, and the push notification infrastructure covered in this module.
- **L2-M36** (API Gateway and BFF): The BFF pattern for mobile is a specialization of the general BFF pattern — read that module for the foundational concepts.
- **L3-M67** (Real-Time Systems with WebSockets): Push notifications and WebSockets serve different real-time use cases; this module contrasts them explicitly.

---

## Checkpoint: What You Built

You have:

- [x] Designed the push notification flow: device registration, token management, delivery with stale token cleanup
- [x] Implemented the in-app inbox as a reliable fallback for best-effort push
- [x] Built a notification batching system that prevents notification fatigue
- [x] Implemented delivery confirmation tracking with delivery and open rate analytics
- [x] Handled token refresh and invalidation for both FCM and APNs
- [x] Designed offline-first patterns with the outbox queue and server-wins conflict resolution
- [x] Worked through three offline sync conflict scenarios: checkout conflicts, preference conflicts, and duplicate mutations
- [x] Optimized APIs for mobile: BFF endpoints, compression, cursor pagination
- [x] Set up deep linking configuration for iOS and Android
- [x] Applied battery and data awareness patterns

**Key insight**: Mobile backend design starts from the assumption that the network is unreliable, the device is constrained, and you cannot control what version of the app is running. Every pattern in this module -- push notifications, offline queues, compressed responses, deep links -- flows from that fundamental difference.

---

**Next module**: L3-M88 -- The TicketPulse Architecture Review, where we step back and examine the complete system we have built across 88+ modules.

## Key Terms

| Term | Definition |
|------|-----------|
| **Push notification** | A server-initiated message delivered to a mobile device, even when the app is backgrounded. |
| **FCM** | Firebase Cloud Messaging; Google's service for sending push notifications to Android and iOS devices. |
| **APNs** | Apple Push Notification service; Apple's service for delivering push notifications to iOS, macOS, and other Apple devices. |
| **Offline-first** | An architecture where the app works without a network connection and syncs data when connectivity is restored. |
| **Deep link** | A URL that navigates a user directly to specific content or a screen within a mobile application. |
| **Idempotency key** | A client-generated unique identifier included in a request so the server can detect and deduplicate retries. |
| **Notification batching** | Aggregating multiple related notifications into a single push to reduce notification volume and prevent fatigue. |
| **Delivery receipt** | A confirmation sent from the app back to the server when a push notification is received or opened. |
| **Conflict resolution** | The strategy for handling simultaneous mutations to the same data from different clients or actors. |
---

## What's Next

In **The TicketPulse Architecture Review** (L3-M88), you'll build on what you learned here and take it further.

# L3-M68: The Ticket Rush Problem

> **Loop 3 (Mastery)** | Section 3B: Real-Time & Advanced Features | ⏱️ 90 min | 🔴 Expert | Prerequisites: L2-M50, L3-M67
>
> **Source:** Chapters 23, 10 of the 100x Engineer Guide

## What You'll Learn

- Designing a system that handles 50K simultaneous purchase attempts for 500 tickets
- Why the naive approach (check-then-reserve) fails catastrophically under concurrency
- Implementing optimistic locking with database-level constraints
- Building a virtual queue system that gives users real-time position updates
- Load testing a rush scenario and verifying exactly-once ticket assignment
- Debugging race conditions: the 51st ticket problem
- Fairness models for high-demand ticket sales

## Why This Matters

This is the defining challenge of a ticketing platform. A popular artist announces a concert. 500 tickets. 50K users hitting "buy" at the exact same instant.

Get this wrong and you sell 600 tickets for a 500-seat venue. Or you sell 400 because race conditions caused some tickets to get stuck in a "reserved" state nobody completed. Or your database locks up and nobody gets anything.

Every major ticketing platform has faced this. Ticketmaster handles 500M+ API hits during major on-sales. Their queue system processes 10K purchases per minute. Building a system that is both correct (never oversells) and fair (does not randomly favor some users) under extreme concurrency is one of the hardest problems in web engineering.

This module is where everything comes together: databases, concurrency, queues, WebSockets, and system design.

---

## 1. Design Before You Code (15 minutes)

Stop. Before reading any implementation, design the ticket rush system yourself.

### The Constraints

- 500 tickets for event `evt_001`
- 50K users hit the "buy" button within a 10-second window
- Each user can buy at most 2 tickets
- Requirements:
  - **Correctness**: exactly 500 tickets sold. Never 501.
  - **No duplicates**: no user gets charged twice for the same ticket
  - **Fairness**: users who clicked earlier should have priority
  - **Feedback**: users should know their status (queued, processing, success, sold out)
  - **Performance**: the system should not fall over under load

### Think Through These Questions

1. What happens if 50K users all run `SELECT count(*) FROM tickets WHERE status='available'` at the same instant?
2. How do you prevent two users from buying the same seat?
3. Where is the bottleneck: the application server, the database, or the network?
4. Should you process all 50K requests simultaneously, or queue them?

### 🤔 Prediction Prompt

Before reading the solutions, predict: will the bottleneck be the application server, the database, or something else entirely? What is the simplest mechanism that could prevent the 501st ticket from being sold?

Write down your design. Draw the data flow. Then continue.

---

## 2. The Naive Approach: Check-Then-Reserve

The most intuitive implementation:

```typescript
interface PurchaseResult {
  success?: boolean;
  ticketId?: string;
  error?: string;
}

async function purchaseTicket(userId: string, eventId: string, seatId: string): Promise<PurchaseResult> {
  // Step 1: Check availability
  const ticket = await db.query(
    'SELECT * FROM tickets WHERE event_id = $1 AND seat_id = $2 AND status = $3',
    [eventId, seatId, 'available']
  );

  if (!ticket) {
    return { error: 'Ticket not available' };
  }

  // Step 2: Reserve it
  await db.query(
    'UPDATE tickets SET status = $1, user_id = $2 WHERE id = $3',
    ['reserved', userId, ticket.id]
  );

  // Step 3: Process payment
  await processPayment(userId, ticket.price);

  // Step 4: Confirm
  await db.query(
    'UPDATE tickets SET status = $1 WHERE id = $2',
    ['confirmed', ticket.id]
  );

  return { success: true, ticketId: ticket.id };
}
```

### Why This Fails

The gap between Step 1 (check) and Step 2 (reserve) is a race condition window. When 50K users execute simultaneously:

```
Time 0ms:  User A: SELECT ... → ticket is available ✓
Time 0ms:  User B: SELECT ... → ticket is available ✓  (same ticket!)
Time 1ms:  User C: SELECT ... → ticket is available ✓  (same ticket!)
Time 5ms:  User A: UPDATE status = 'reserved'
Time 6ms:  User B: UPDATE status = 'reserved'  ← overwrites A's reservation!
Time 7ms:  User C: UPDATE status = 'reserved'  ← overwrites B's reservation!
```

All three users think they bought the ticket. Two of them will be charged for a seat they do not actually have. This is the **TOCTOU** (Time of Check, Time of Use) problem.

Under 50K concurrent requests, this is not a theoretical risk. It will happen. Constantly.

---

## 3. Solution 1: Optimistic Locking

Instead of separate check-and-update steps, combine them into a single atomic operation:

```sql
UPDATE tickets
SET status = 'reserved', user_id = $1, reserved_at = NOW()
WHERE event_id = $2
  AND seat_id = $3
  AND status = 'available'
RETURNING id, seat_id, price;
```

This is an atomic compare-and-swap at the database level. The `WHERE status = 'available'` clause means only the first `UPDATE` succeeds. All subsequent attempts find zero matching rows and return nothing.

```typescript
interface PurchaseSuccess {
  success: true;
  ticketId: string;
  seatId: string;
}

interface PurchaseError {
  error: string;
  details?: string;
}

type PurchaseOutcome = PurchaseSuccess | PurchaseError;

async function purchaseTicketOptimistic(userId: string, eventId: string, seatId: string | null): Promise<PurchaseOutcome> {
  // Single atomic operation -- no race window
  const result = await db.query(
    `UPDATE tickets
     SET status = 'reserved', user_id = $1, reserved_at = NOW()
     WHERE event_id = $2 AND seat_id = $3 AND status = 'available'
     RETURNING id, seat_id, price`,
    [userId, eventId, seatId]
  );

  if (result.rowCount === 0) {
    return { error: 'Ticket not available' };
  }

  const ticket = result.rows[0];

  try {
    // Process payment
    await processPayment(userId, ticket.price);

    // Confirm the ticket
    await db.query(
      `UPDATE tickets SET status = 'confirmed' WHERE id = $1`,
      [ticket.id]
    );

    return { success: true, ticketId: ticket.id, seatId: ticket.seat_id };
  } catch (paymentError: unknown) {
    // Payment failed -- release the reservation
    await db.query(
      `UPDATE tickets SET status = 'available', user_id = NULL, reserved_at = NULL WHERE id = $1`,
      [ticket.id]
    );
    const message = paymentError instanceof Error ? paymentError.message : 'Unknown error';
    return { error: 'Payment failed', details: message };
  }
}
```

### What About "Any Available Ticket"?

Most users during a rush do not pick a specific seat. They want "give me any ticket." This changes the query:

```sql
UPDATE tickets
SET status = 'reserved', user_id = $1, reserved_at = NOW()
WHERE event_id = $2
  AND status = 'available'
  AND id = (
    SELECT id FROM tickets
    WHERE event_id = $2 AND status = 'available'
    ORDER BY id
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
RETURNING id, seat_id, price;
```

`FOR UPDATE SKIP LOCKED` is critical. It tells PostgreSQL: "Lock a row, but if someone else already locked it, skip to the next one instead of waiting." Without `SKIP LOCKED`, all 50K queries would queue up on the same row, serializing entirely.

With `SKIP LOCKED`, concurrent requests each grab a different available ticket. Throughput scales with the number of available tickets.

### Optimistic Locking: Tradeoffs

**Pros:**
- Simple to implement
- Database handles all concurrency
- No external dependencies

**Cons:**
- Under extreme contention (50K requests), the database becomes the bottleneck
- `SKIP LOCKED` helps but still hammers the DB
- 49,500 users get an immediate "sold out" -- no queue, no waiting, just failure

---

## 4. Solution 2: The Virtual Queue

For a better user experience and more controlled load, put users in a queue instead of letting them all hit the database simultaneously.

### The Architecture

```
User clicks "Buy"
        │
        ▼
  API: Assign queue position
        │
        ▼
  Redis sorted set: { userId: timestamp }
        │
        ▼
  Queue processor: pop users one at a time
        │
        ▼
  Process purchase (optimistic locking)
        │
        ▼
  WebSocket: "You got the ticket!" / "Sold out"
```

### Build: The Virtual Queue

```typescript
import Redis from 'ioredis';

const redis = new Redis();

const QUEUE_KEY = (eventId: string): string => `queue:${eventId}`;
const PROCESSING_KEY = (eventId: string): string => `processing:${eventId}`;

interface QueueJoinResult {
  status: 'queued' | 'already_in_queue';
  position?: number;
  totalWaiting?: number;
  estimatedWaitSeconds?: number;
}

interface QueuePositionResult {
  status: 'waiting' | 'processing' | 'not_in_queue';
  position?: number;
  totalWaiting?: number;
}

// Step 1: User joins the queue
async function joinQueue(userId: string, eventId: string): Promise<QueueJoinResult> {
  const queueKey = QUEUE_KEY(eventId);

  // Score = timestamp (earlier = lower score = higher priority)
  const score = Date.now();

  // Only add if not already in queue (NX = don't update existing)
  const added = await redis.zadd(queueKey, 'NX', score, userId);

  if (!added) {
    return { status: 'already_in_queue' };
  }

  // Get position (0-indexed rank)
  const position = await redis.zrank(queueKey, userId);
  const totalWaiting = await redis.zcard(queueKey);

  return {
    status: 'queued',
    position: position! + 1,
    totalWaiting,
    estimatedWaitSeconds: Math.ceil((position! + 1) * 0.5) // ~2 purchases/sec
  };
}

// Step 2: Get current queue position (polled or pushed via WebSocket)
async function getQueuePosition(userId: string, eventId: string): Promise<QueuePositionResult> {
  const position = await redis.zrank(QUEUE_KEY(eventId), userId);

  if (position === null) {
    // Check if already being processed
    const processing = await redis.sismember(PROCESSING_KEY(eventId), userId);
    if (processing) return { status: 'processing' };
    return { status: 'not_in_queue' };
  }

  return {
    status: 'waiting',
    position: position + 1,
    totalWaiting: await redis.zcard(QUEUE_KEY(eventId))
  };
}
```

### Build: The Queue Processor

```typescript
interface UserNotification {
  status: string;
  ticketId?: string;
  seatId?: string;
  reason?: string;
}

// Processes users from the queue, one at a time
async function processQueue(eventId: string): Promise<void> {
  const queueKey = QUEUE_KEY(eventId);
  const processingKey = PROCESSING_KEY(eventId);

  while (true) {
    // Pop the next user from the queue (lowest score = earliest join)
    const result = await redis.zpopmin(queueKey, 1);

    if (!result || result.length === 0) {
      // Queue is empty, check again in 100ms
      await sleep(100);
      continue;
    }

    const userId: string = result[0];

    // Check if tickets are still available (fast check)
    const remaining = await getAvailableCount(eventId);
    if (remaining <= 0) {
      // Sold out -- notify this user and drain the rest
      await notifyUser(userId, eventId, { status: 'sold_out' });
      await drainQueueAsSoldOut(eventId);
      break;
    }

    // Mark as processing
    await redis.sadd(processingKey, userId);

    // Attempt the purchase
    try {
      const purchaseResult = await purchaseTicketOptimistic(userId, eventId, null);

      if ('success' in purchaseResult) {
        await notifyUser(userId, eventId, {
          status: 'purchased',
          ticketId: purchaseResult.ticketId,
          seatId: purchaseResult.seatId
        });

        // Broadcast availability update to all watchers
        await broadcastAvailability(eventId);
      } else {
        await notifyUser(userId, eventId, { status: 'failed', reason: purchaseResult.error });
      }
    } catch (err: unknown) {
      console.error(`Purchase failed for user ${userId}:`, err);
      await notifyUser(userId, eventId, { status: 'error', reason: 'Internal error' });
    } finally {
      await redis.srem(processingKey, userId);
    }
  }
}

// Notify user via WebSocket
async function notifyUser(userId: string, eventId: string, message: UserNotification): Promise<void> {
  await redisPub.publish(`user-updates:${userId}`, JSON.stringify({
    eventId,
    ...message,
    timestamp: Date.now()
  }));
}

// Tell all remaining queue members they are sold out
async function drainQueueAsSoldOut(eventId: string): Promise<void> {
  const queueKey = QUEUE_KEY(eventId);

  while (true) {
    const batch = await redis.zpopmin(queueKey, 100);
    if (!batch || batch.length === 0) break;

    for (let i = 0; i < batch.length; i += 2) {
      const userId: string = batch[i];
      await notifyUser(userId, eventId, { status: 'sold_out' });
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

### WebSocket Integration: Live Queue Position

```typescript
// On the WebSocket server, push position updates to queued users
setInterval(async () => {
  // For each active event with a queue
  for (const eventId of activeEvents) {
    const queueKey = QUEUE_KEY(eventId);
    const members: string[] = await redis.zrange(queueKey, 0, -1); // All queued users

    for (let i = 0; i < members.length; i++) {
      await notifyUser(members[i], eventId, {
        status: 'waiting',
        position: i + 1,
        totalWaiting: members.length
      });
    }
  }
}, 2000); // Update every 2 seconds
```

The user experience:

```
"You are #342 in queue..."
"You are #41 in queue..."
"You are #3 in queue..."
"It's your turn! Processing your purchase..."
"Success! You got seat B-22!"
```

---

## 5. Build: Load Test the Rush

Now stress-test the system. Can it handle 1000 concurrent purchase attempts for 50 tickets?

### Setup

```sql
-- Create 50 tickets for the test event
INSERT INTO tickets (event_id, seat_id, status, price)
SELECT
  'evt_rush_test',
  'S-' || generate_series(1, 50),
  'available',
  75.00;
```

### Load Test Script

```typescript
// load-test.ts
// Uses native fetch (Node 18+)

const EVENT_ID = 'evt_rush_test';
const CONCURRENT_USERS = 1000;
const API_URL = 'http://localhost:3000';

interface SimulationResult {
  userId: string;
  queuePosition?: number;
  status: string;
  error?: string;
  latencyMs: number;
}

interface EventStats {
  sold: number;
  available: number;
  reserved: number;
  uniqueBuyers: number;
}

async function simulateUser(userId: number): Promise<SimulationResult> {
  const start = Date.now();

  try {
    // Join queue
    const joinRes = await fetch(`${API_URL}/api/events/${EVENT_ID}/queue/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: `user_${userId}` })
    });
    const joinData = await joinRes.json() as { position: number; status: string };

    return {
      userId: `user_${userId}`,
      queuePosition: joinData.position,
      status: joinData.status,
      latencyMs: Date.now() - start
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return {
      userId: `user_${userId}`,
      status: 'error',
      error: message,
      latencyMs: Date.now() - start
    };
  }
}

async function runRush(): Promise<void> {
  console.log(`Starting rush: ${CONCURRENT_USERS} users, 50 tickets`);
  console.log('---');

  const start = Date.now();

  // Fire all requests simultaneously
  const promises = Array.from({ length: CONCURRENT_USERS }, (_, i) => simulateUser(i));
  const results = await Promise.all(promises);

  const elapsed = Date.now() - start;

  // Analyze results
  const queued = results.filter(r => r.status === 'queued').length;
  const alreadyQueued = results.filter(r => r.status === 'already_in_queue').length;
  const errors = results.filter(r => r.status === 'error').length;
  const latencies = results.map(r => r.latencyMs).sort((a, b) => a - b);

  console.log(`Results (${elapsed}ms total):`);
  console.log(`  Queued: ${queued}`);
  console.log(`  Already in queue: ${alreadyQueued}`);
  console.log(`  Errors: ${errors}`);
  console.log(`  Latency p50: ${latencies[Math.floor(latencies.length * 0.5)]}ms`);
  console.log(`  Latency p95: ${latencies[Math.floor(latencies.length * 0.95)]}ms`);
  console.log(`  Latency p99: ${latencies[Math.floor(latencies.length * 0.99)]}ms`);

  // Wait for queue processing, then check results
  console.log('\nWaiting for queue processing...');
  await sleep(30000); // Wait 30 seconds for processing

  // Check final state
  const checkRes = await fetch(`${API_URL}/api/events/${EVENT_ID}/stats`);
  const stats = await checkRes.json() as EventStats;

  console.log('\nFinal state:');
  console.log(`  Tickets sold: ${stats.sold}`);
  console.log(`  Tickets available: ${stats.available}`);
  console.log(`  Tickets reserved (stuck): ${stats.reserved}`);
  console.log(`  Unique buyers: ${stats.uniqueBuyers}`);

  // Verify correctness
  console.log('\nCorrectness checks:');
  console.log(`  Exactly 50 sold: ${stats.sold === 50 ? 'PASS' : 'FAIL'}`);
  console.log(`  No overselling: ${stats.sold <= 50 ? 'PASS' : 'FAIL'}`);
  console.log(`  No duplicates: ${stats.sold === stats.uniqueBuyers ? 'PASS' : 'FAIL'}`);
  console.log(`  No stuck reservations: ${stats.reserved === 0 ? 'PASS' : 'FAIL'}`);
}

runRush();
```

### Observe

Run the load test. Check: exactly 50 sold? No duplicates? No stuck reservations? If any check fails, the next section covers the most common bug.

---

## 6. Debug: The 51st Ticket

A race condition has allowed one extra sale. The database shows 51 confirmed tickets for a 50-ticket event. How?

### The Bug

The queue processor checks available count before attempting the purchase:

```typescript
const remaining = await getAvailableCount(eventId);
if (remaining <= 0) { /* sold out */ }
```

But between checking the count and executing the `UPDATE`, another queue processor instance (or a direct API call bypassing the queue) can sell the last ticket. The check says 1 remaining, two processors both proceed, and both succeed because they grab different tickets.

### The Fix: Database-Level Constraint

Never trust application-level counts for correctness. Add a database constraint:

```sql
-- Option 1: Trigger that enforces the cap
CREATE OR REPLACE FUNCTION check_ticket_cap()
RETURNS TRIGGER AS $$
DECLARE
  sold_count INTEGER;
  event_cap INTEGER;
BEGIN
  SELECT count(*) INTO sold_count
  FROM tickets
  WHERE event_id = NEW.event_id AND status IN ('reserved', 'confirmed');

  SELECT capacity INTO event_cap
  FROM events
  WHERE id = NEW.event_id;

  IF sold_count > event_cap THEN
    RAISE EXCEPTION 'Event capacity exceeded: % sold for capacity %', sold_count, event_cap;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_ticket_cap
  AFTER UPDATE ON tickets
  FOR EACH ROW
  WHEN (NEW.status IN ('reserved', 'confirmed') AND OLD.status = 'available')
  EXECUTE FUNCTION check_ticket_cap();
```

```sql
-- Option 2: Simpler -- use a counter with a check constraint
ALTER TABLE events ADD COLUMN tickets_sold INTEGER DEFAULT 0;
ALTER TABLE events ADD CONSTRAINT check_capacity CHECK (tickets_sold <= capacity);

-- In the purchase transaction:
BEGIN;
  UPDATE tickets SET status = 'reserved', user_id = $1 WHERE ...;
  UPDATE events SET tickets_sold = tickets_sold + 1 WHERE id = $2;
  -- If tickets_sold > capacity, the CHECK constraint raises an error
  -- and the entire transaction rolls back
COMMIT;
```

### Double-Purchase Prevention: Idempotency

What if the user clicks "buy" twice? Or the network retries the request?

```typescript
// Generate an idempotency key on the client
const idempotencyKey = `${userId}:${eventId}:${Date.now()}`;

// Server checks before processing
async function processWithIdempotency(
  idempotencyKey: string,
  userId: string,
  eventId: string
): Promise<{ error?: string }> {
  // Check Redis first (fast path)
  const exists = await redis.set(`idem:${idempotencyKey}`, '1', 'NX', 'EX', 3600);
  if (!exists) {
    return { error: 'Duplicate request' };
  }

  // Database constraint as backup
  try {
    await db.query(
      `INSERT INTO purchases (idempotency_key, user_id, event_id, status)
       VALUES ($1, $2, $3, 'processing')`,
      [idempotencyKey, userId, eventId]
    );
  } catch (err: unknown) {
    if (err instanceof Error && (err as NodeJS.ErrnoException & { code: string }).code === '23505') {
      // Unique violation
      return { error: 'Duplicate request' };
    }
    throw err;
  }

  // Proceed with purchase...
  return {};
}
```

Two layers of deduplication: Redis for speed, database unique constraint for correctness.

---

## 7. Distributed Locking with Redis

For seat-specific reservations (user picks a specific seat), you need a per-seat lock:

```typescript
import Redlock from 'redlock';

const redlock = new Redlock([redis], {
  retryCount: 3,
  retryDelay: 200,
});

async function reserveSeatWithLock(userId: string, eventId: string, seatId: string): Promise<PurchaseOutcome> {
  const lockKey = `lock:seat:${eventId}:${seatId}`;

  let lock: Awaited<ReturnType<typeof redlock.acquire>> | undefined;
  try {
    // Acquire a lock for this specific seat (10 second TTL)
    lock = await redlock.acquire([lockKey], 10_000);

    // We have exclusive access to this seat
    const result = await purchaseTicketOptimistic(userId, eventId, seatId);
    return result;

  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'LockError') {
      return { error: 'Seat is being reserved by another user, try again' };
    }
    throw err;
  } finally {
    if (lock) {
      await lock.release();
    }
  }
}
```

The lock TTL (10 seconds) is the reservation window. If payment processing takes longer than 10 seconds, the lock expires and someone else can grab the seat. Set it to match your maximum acceptable reservation time.

---

## 8. Fairness

Is first-come-first-served actually fair?

Think about it: when 50K users all click "buy" within a 10-second window, the difference between position #1 and position #500 is often milliseconds. The user with a faster internet connection, closer to the data center, or a less loaded browser wins. That is not really "first come, first served" in any meaningful sense.

### Alternative Models

**Random lottery**: Everyone who clicks "buy" within the first 60 seconds enters a lottery. Winners are selected randomly. More equitable but less exciting.

**Tiered access**: Fan club members get access at 10:00 AM. Presale code holders at 12:00 PM. General public at 2:00 PM. Each tier has its own allocation. This is what Ticketmaster and most major platforms do.

**Anti-bot measures**: CAPTCHAs, browser fingerprinting, rate limiting per IP, detecting automated purchase patterns. Bots can join a queue faster than any human, so any purely speed-based system favors automation.

**Verified fan programs**: Ticketmaster's "Verified Fan" requires registration before the on-sale. They use behavioral analysis to filter bots and allocate invite codes. The on-sale is effectively a smaller, curated group.

There is no perfect system. Every approach trades off between fairness, user experience, and engineering complexity.

---

## 9. Reflect

Consider the full picture:

> Your rush system handles 50K users for 500 tickets. The queue works, the database constraints prevent overselling, the WebSocket updates keep users informed.
>
> Now a user complains: "I was #45 in queue but didn't get a ticket. How is that possible when there were 500 tickets?"
>
> What happened? (Think: payment failures, reservation timeouts, users who abandoned the queue, the reservation-to-confirmation pipeline.)

---

## 10. Checkpoint

Before moving on, verify:

- [ ] You can explain why check-then-reserve fails under concurrency
- [ ] Optimistic locking with `WHERE status = 'available'` prevents double-booking
- [ ] `FOR UPDATE SKIP LOCKED` enables parallel ticket assignment
- [ ] Your virtual queue assigns positions and processes users sequentially
- [ ] WebSocket delivers real-time queue position updates
- [ ] The load test confirms exactly 50 tickets sold, no duplicates, no stuck reservations
- [ ] Database constraints (not application logic) enforce the ticket cap

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Summary

The ticket rush is a concurrency gauntlet. The naive approach fails immediately. Optimistic locking at the database level is the foundation of correctness -- never rely on application-level checks alone. A virtual queue transforms a chaotic stampede into an orderly line, with WebSocket providing real-time feedback. Database constraints are the final safety net: even if everything else has a bug, the database will refuse the 501st ticket.

### 🤔 Reflection Prompt

Compare your initial design from Section 1 with the final solution. What did you get right? What failure mode would have bitten you hardest in production?

This pattern -- queue + optimistic locking + idempotency + database constraints -- applies far beyond ticketing. Flash sales, limited-edition drops, reservation systems, auction closings: any time many users compete for scarce resources under time pressure.

## Key Terms

| Term | Definition |
|------|-----------|
| **Optimistic locking** | A concurrency control method that detects conflicts at commit time using version numbers rather than holding locks. |
| **Virtual queue** | A waiting-room mechanism that holds users in line before granting them access to a contested resource. |
| **Distributed lock** | A lock held across multiple processes or machines, ensuring only one can access a resource at a time. |
| **FOR UPDATE SKIP LOCKED** | A PostgreSQL clause that locks selected rows and skips any already locked by another transaction. |
| **Race condition** | A bug where the system's behavior depends on the unpredictable timing of concurrent operations. |

---

## What's Next

Next up: **[L3-M69: Notification System](L3-M69-notification-system.md)** -- you will design the multi-channel notification system that tells users their ticket was confirmed, their event is tomorrow, or their payment failed.

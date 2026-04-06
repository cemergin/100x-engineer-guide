# Exercise: Build the Ticket Rush System

## What We're Doing
You'll implement optimistic locking, build a Redis virtual queue, wire up WebSocket position updates, and load test the system to verify correctness under concurrency.

## Before You Start
- TicketPulse running with Postgres and Redis
- WebSocket support from L3-M67

## Steps

### Step 1: Implement Optimistic Locking

Replace the check-then-reserve with an atomic UPDATE...WHERE...RETURNING query. Use `FOR UPDATE SKIP LOCKED` for the "any available ticket" case.

### Step 2: Build the Virtual Queue

Create Redis-backed queue functions: `joinQueue(userId, eventId)` using sorted sets (score = timestamp), `getQueuePosition(userId, eventId)`, and a queue processor that pops users sequentially.

> **Before you continue:** Why a sorted set instead of a list? What property does timestamp-as-score give you?

### Step 3: Wire Up WebSocket Position Updates

Push queue position updates to connected clients every 2 seconds. The user experience: "You are #342... #41... #3... Processing... Success!"

### Step 4: Add Database Safety Constraint

```sql
ALTER TABLE events ADD COLUMN tickets_sold INTEGER DEFAULT 0;
ALTER TABLE events ADD CONSTRAINT check_capacity CHECK (tickets_sold <= capacity);
```

Increment `tickets_sold` inside the purchase transaction.

### Step 5: Load Test

Create 50 tickets, fire 1000 concurrent requests, verify: exactly 50 sold, no duplicates, no stuck reservations.

## What Just Happened?

You built a system that handles extreme concurrency correctly. The optimistic lock prevents double-booking, the queue provides orderly processing, and the database constraint is the final guarantee.

> **What did you notice?** What was the p95 latency? How did throughput change as tickets sold out? Where was the bottleneck?

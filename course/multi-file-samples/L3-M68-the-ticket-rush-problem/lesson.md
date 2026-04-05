# The Ticket Rush Problem

This is the defining challenge of a ticketing platform. A popular artist announces a concert. 500 tickets. 50K users hitting "buy" at the exact same instant.

Get this wrong and you sell 600 tickets for a 500-seat venue. Or your database locks up and nobody gets anything.

## The Naive Approach Fails

The intuitive implementation — check availability, then reserve — has a fatal race condition:

```
Time 0ms:  User A: SELECT ... → available ✓
Time 0ms:  User B: SELECT ... → available ✓  (same ticket!)
Time 5ms:  User A: UPDATE status = 'reserved'
Time 6ms:  User B: UPDATE status = 'reserved'  ← overwrites A!
```

This is TOCTOU (Time of Check, Time of Use). Under 50K concurrent requests, it's not theoretical — it happens constantly.

## Optimistic Locking: The Foundation

Combine check and update into a single atomic operation:

```sql
UPDATE tickets SET status = 'reserved', user_id = $1
WHERE event_id = $2 AND status = 'available'
RETURNING id, seat_id, price;
```

Only the first UPDATE succeeds. All others find zero matching rows.

For "any available ticket," add `FOR UPDATE SKIP LOCKED` — it tells PostgreSQL to skip already-locked rows instead of waiting, enabling parallel ticket assignment.

## The Virtual Queue: Better UX

Instead of 50K simultaneous database hits, put users in a Redis sorted set (score = join timestamp). A processor pops users one at a time and processes purchases sequentially. WebSocket pushes real-time position updates.

## Database Constraints: The Safety Net

Never trust application-level counts. Add a CHECK constraint:

```sql
ALTER TABLE events ADD CONSTRAINT check_capacity CHECK (tickets_sold <= capacity);
```

Even if everything else has a bug, the database refuses the 501st ticket.

## Fairness

First-come-first-served under 50K concurrent users really means "fastest internet connection wins." Alternatives: random lottery, tiered access (fan club → presale → general), verified fan programs. No perfect system — every approach trades fairness, UX, and complexity.

## Key Takeaways

- Never separate "check" and "update" for scarce resources under concurrency
- Database-level atomicity (optimistic locking) is the correctness foundation
- `FOR UPDATE SKIP LOCKED` enables parallel processing of competing requests
- Virtual queues transform chaos into orderly processing with real-time feedback
- Database constraints are the non-negotiable safety net
- This pattern applies beyond ticketing: flash sales, auctions, reservation systems

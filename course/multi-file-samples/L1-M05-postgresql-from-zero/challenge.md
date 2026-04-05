# Challenge: Design a Waitlist Feature

## The Scenario

TicketPulse events are selling out. The product team wants a waitlist: when sold out, users join a queue. When a ticket becomes available (cancellation/refund), the first person gets notified and has 15 minutes to claim it.

## Your Task

Design the database schema changes to support this. You need to:
1. Create a `waitlist_entries` table with proper columns, types, and constraints
2. Prevent duplicate entries (same user, same event)
3. Write a query to find the next person in line
4. Write a query to expire 15-minute-old notifications

## Success Criteria

- [ ] Table has appropriate columns and types
- [ ] Foreign key to `events` exists
- [ ] NOT NULL and CHECK constraints enforce integrity
- [ ] UNIQUE constraint prevents duplicate entries per event
- [ ] "Next person" query returns earliest non-expired, non-notified entry
- [ ] Expiry query correctly updates stale notifications

## Hints

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what uniquely identifies a waitlist entry. A UNIQUE constraint on (event_id, email) prevents duplicates. The status flow: waiting → notified → claimed or expired.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use joined_at TIMESTAMPTZ for position ordering. Add notified_at to track when the 15-minute window starts. A CHECK constraint on status limits it to valid values.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>

```sql
CREATE TABLE waitlist_entries (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES events(id),
  email VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'waiting'
    CHECK (status IN ('waiting', 'notified', 'claimed', 'expired')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notified_at TIMESTAMPTZ,
  UNIQUE (event_id, email)
);
```

Next person: `WHERE event_id = $1 AND status = 'waiting' ORDER BY joined_at LIMIT 1`
Expiry: `UPDATE ... SET status = 'expired' WHERE status = 'notified' AND notified_at < NOW() - INTERVAL '15 minutes'`
</details>

## Solution

<details>
<summary>View Solution</summary>

```sql
CREATE TABLE waitlist_entries (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES events(id),
  email VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'waiting'
    CHECK (status IN ('waiting', 'notified', 'claimed', 'expired', 'cancelled')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notified_at TIMESTAMPTZ,
  claimed_at TIMESTAMPTZ,
  UNIQUE (event_id, email)
);

CREATE INDEX idx_waitlist_event_status_joined
  ON waitlist_entries(event_id, status, joined_at);

-- Next person
SELECT id, email FROM waitlist_entries
WHERE event_id = $1 AND status = 'waiting'
ORDER BY joined_at LIMIT 1;

-- Notify them
UPDATE waitlist_entries SET status = 'notified', notified_at = NOW()
WHERE id = $1 AND status = 'waiting' RETURNING *;

-- Expire stale
UPDATE waitlist_entries SET status = 'expired'
WHERE status = 'notified' AND notified_at < NOW() - INTERVAL '15 minutes';

-- Claim
UPDATE waitlist_entries SET status = 'claimed', claimed_at = NOW()
WHERE id = $1 AND status = 'notified'
  AND notified_at >= NOW() - INTERVAL '15 minutes';
```

**Why:** UNIQUE prevents duplicates. CHECK enforces valid states. The composite index makes queue lookups fast. The 15-minute window is enforced in both the expiry job AND the claim query for safety.

**Trade-off:** This is FIFO. For high-demand events, a lottery might be fairer. For extreme volume, Redis queue with Postgres persistence would be faster.
</details>

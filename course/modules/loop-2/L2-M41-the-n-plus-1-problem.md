# L2-M41: The N+1 Problem

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 45 min | 🟢 Core | Prerequisites: L1-M07, L2-M37
>
> **Source:** Chapter 24 of the 100x Engineer Guide

## What You'll Learn
- How to detect N+1 queries by enabling query logging
- Why ORMs hide N+1 problems behind convenient syntax
- Three fix strategies: eager loading (JOIN), batch loading (DataLoader), ORM includes
- How to measure the performance impact (expect 10-20x improvements)
- How to prevent N+1 problems in development with query counting

## Why This Matters
The N+1 problem is the single most common performance bug in web applications. It happens silently — your code looks clean, your ORM hides the database calls, and everything works fine... until you have 100 items on a page and your API takes 800ms because it's firing 201 separate database queries. This module teaches you to detect it, fix it, and prevent it from happening again.

## Prereq Check

Ensure TicketPulse's event service is running with Postgres:

```bash
docker compose ps
# Verify event-service and postgres are running
```

---

> **Before you continue:** The events list endpoint loads 100 events with their venue name and ticket count. How many database queries do you think it makes? Write down a number before enabling query logging.

## Part 1: See the Problem (10 min)

### 🐛 Debug: Enable Query Logging

<details>
<summary>💡 Hint 1: Direction</summary>
Set log_statement='all' and log_min_duration_statement=0 in Postgres to see every query with its duration.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Hit the events list endpoint and watch the Postgres logs. Count the number of SELECT statements -- you should see 1 + N + N queries for N events.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Look for repetitive query patterns: the same query structure with different parameter values is the hallmark of N+1. For 100 events, expect 201 queries: 1 for events + 100 for venues + 100 for ticket counts.
</details>

First, let's see every query Postgres executes. Enable query logging:

```sql
-- Connect as superuser
docker exec -it ticketpulse-postgres psql -U postgres

-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 0;  -- Log ALL queries with their duration
SELECT pg_reload_conf();
```

Now every query hits the Postgres log. Watch it:

```bash
# In a separate terminal, follow the Postgres logs
docker compose logs -f postgres
```


<details>
<summary>💡 Hint 1: Direction</summary>
Enable `log_statement = 'all'` in Postgres to see every query. Then load the events page and count the individual SELECT statements in the log output.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
The pattern you are looking for: one SELECT for events, then one SELECT per event for the venue, then one SELECT per event for the ticket count. That is 1 + N + N = 2N + 1 queries.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
With 100 events, you should see 201 queries: 1 for the event list, 100 for venue lookups, 100 for ticket counts. The fix is to replace the loop with a JOIN or batch query that fetches all venues and counts in 1-2 queries total.
</details>

### 🐛 Debug: Load the Events Page

<details>
<summary>💡 Hint 1: Direction</summary>
Look at the query log pattern: if you see the same query shape repeated N times with different parameter values, that is the N+1 problem. The fix depends on context: JOIN, batch load, or ORM includes.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Collect all unique IDs first, then fetch ALL related data in one query using WHERE id = ANY($1). Build a Map for O(1) lookups when assembling the response.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The optimized version uses 3 queries total: one for the list, one batch fetch for related entity A, one batch fetch for related entity B. Assembly happens in application code using Maps.
</details>


Now hit the TicketPulse events list endpoint — the page that shows all events with their venue name and ticket count:

```bash
# Load the events page
curl http://localhost:3000/api/events
```

Watch the Postgres logs. You'll see something alarming:

```
LOG:  statement: SELECT * FROM events ORDER BY event_date LIMIT 100
LOG:  statement: SELECT name FROM venues WHERE id = 1
LOG:  statement: SELECT name FROM venues WHERE id = 2
LOG:  statement: SELECT name FROM venues WHERE id = 3
LOG:  statement: SELECT name FROM venues WHERE id = 1    -- duplicate!
LOG:  statement: SELECT name FROM venues WHERE id = 4
...
LOG:  statement: SELECT name FROM venues WHERE id = 2    -- duplicate!
LOG:  statement: SELECT COUNT(*) FROM tickets WHERE event_id = 1
LOG:  statement: SELECT COUNT(*) FROM tickets WHERE event_id = 2
LOG:  statement: SELECT COUNT(*) FROM tickets WHERE event_id = 3
...
```

### 🔍 Try It: Count the Queries

```sql
-- Reset stats
SELECT pg_stat_reset();

-- Make the request
-- (run curl in another terminal)

-- Count queries
SELECT calls, query
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 10;
```

Expected total: **1 + N + N = 2N + 1 queries**

For 100 events: 1 (events) + 100 (venues) + 100 (ticket counts) = **201 queries** for one page load.

### The Code That Causes This

Here's the typical pattern. It looks clean and reasonable:

```javascript
// This code looks fine but generates N+1 queries
async function getEvents() {
  // Query 1: Get all events
  const events = await db.query('SELECT * FROM events ORDER BY event_date LIMIT 100');

  // For each event, fetch its venue and ticket count
  const results = await Promise.all(events.rows.map(async (event) => {
    // N queries: one per event for venue
    const venue = await db.query('SELECT name FROM venues WHERE id = $1', [event.venue_id]);

    // N more queries: one per event for ticket count
    const tickets = await db.query(
      'SELECT COUNT(*) FROM tickets WHERE event_id = $1 AND status = $2',
      [event.id, 'available']
    );

    return {
      ...event,
      venue_name: venue.rows[0]?.name,
      available_tickets: parseInt(tickets.rows[0]?.count)
    };
  }));

  return results;
}
```

**The pattern**: fetch a list, then loop over it and fetch related data for each item. This is the N+1 problem.

### 📊 Observe: Measure the Damage

```bash
# Time the request
time curl -s http://localhost:3000/api/events > /dev/null

# With 100 events: expect 500-800ms
# Each query takes ~2-5ms, and you're making 201 of them
# Network round-trips add up fast
```

---

## Part 2: Fix 1 — Eager Loading with JOINs (10 min)

### The Idea

Instead of 201 queries, write ONE query that fetches everything at once:

### 🛠️ Build: Single Query with JOINs

<details>
<summary>💡 Hint 1: Direction</summary>
Replace the N+1 pattern with a single query that JOINs events, venues, and tickets with GROUP BY and COUNT FILTER.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use LEFT JOIN for tickets to handle events with no tickets. Apply FILTER (WHERE status = 'available') inside COUNT for available ticket counts.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The query: SELECT e.*, v.name AS venue_name, COUNT(t.id) FILTER (WHERE t.status = 'available') AS available_tickets FROM events e JOIN venues v ON e.venue_id = v.id LEFT JOIN tickets t ON t.event_id = e.id GROUP BY e.id, v.name ORDER BY e.event_date LIMIT 100.
</details>

```javascript
async function getEventsOptimized() {
  // ONE query that gets events + venues + ticket counts
  const result = await db.query(`
    SELECT
      e.id,
      e.name,
      e.event_date,
      e.category,
      v.name AS venue_name,
      v.city,
      COUNT(t.id) FILTER (WHERE t.status = 'available') AS available_tickets,
      COUNT(t.id) AS total_tickets
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    LEFT JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name, e.event_date, e.category, v.name, v.city
    ORDER BY e.event_date
    LIMIT 100
  `);

  return result.rows;
}
```


<details>
<summary>💡 Hint 1: Direction</summary>
Replace the N individual venue lookups with a single JOIN in the original events query. Add a subquery or LEFT JOIN for ticket counts.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `SELECT e.*, v.name as venue_name, COUNT(t.id) as ticket_count FROM events e JOIN venues v ON e.venue_id = v.id LEFT JOIN tickets t ON ...` to get everything in one query.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Be careful with the GROUP BY — when you JOIN tickets for the count, you need to group by all event and venue columns. Alternatively, use a correlated subquery: `(SELECT COUNT(*) FROM tickets WHERE event_id = e.id) as ticket_count` which avoids the GROUP BY complexity.
</details>

### 📊 Observe: Measure the Improvement

```bash
# Time the optimized request
time curl -s http://localhost:3000/api/events > /dev/null
```

**Before**: 201 queries, ~800ms
**After**: 1 query, ~50ms

That's a **16x improvement** from a single code change.

### Check the Query Log

Watch the Postgres logs now — you should see only ONE query instead of 201.

### Trade-offs of Eager Loading

| Pro | Con |
|-----|-----|
| Fewest round-trips (1 query) | JOIN can return redundant data (venue info repeated per event) |
| Database optimizes the entire query as one plan | Query gets complex with many joins |
| Simplest to understand and debug | If you don't always need the related data, you're over-fetching |

### When Eager Loading Works Best

- You **always** need the related data (events always show venue name and ticket count)
- The related data is small and doesn't multiply rows excessively
- The JOIN doesn't produce a cartesian product (many-to-many without careful handling)

---

## Part 3: Fix 2 — Batch Loading (DataLoader Pattern) (10 min)

### The Idea

Collect all the IDs you need, then make ONE query per table instead of one query per item:

```
Instead of:
  SELECT * FROM venues WHERE id = 1;
  SELECT * FROM venues WHERE id = 2;
  SELECT * FROM venues WHERE id = 3;  (N separate queries)

Do:
  SELECT * FROM venues WHERE id IN (1, 2, 3);  (1 query for all)
```

### 🛠️ Build: Batch Loading

<details>
<summary>💡 Hint 1: Direction</summary>
Look at the query log pattern: if you see the same query shape repeated N times with different parameter values, that is the N+1 problem. The fix depends on context: JOIN, batch load, or ORM includes.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Collect all unique IDs first, then fetch ALL related data in one query using WHERE id = ANY($1). Build a Map for O(1) lookups when assembling the response.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The optimized version uses 3 queries total: one for the list, one batch fetch for related entity A, one batch fetch for related entity B. Assembly happens in application code using Maps.
</details>


```javascript
async function getEventsWithBatchLoading() {
  // Query 1: Get all events
  const events = await db.query('SELECT * FROM events ORDER BY event_date LIMIT 100');

  // Collect unique venue IDs
  const venueIds = [...new Set(events.rows.map(e => e.venue_id))];

  // Query 2: Get ALL venues in one query
  const venues = await db.query(
    'SELECT id, name, city FROM venues WHERE id = ANY($1)',
    [venueIds]
  );
  const venueMap = new Map(venues.rows.map(v => [v.id, v]));

  // Collect event IDs
  const eventIds = events.rows.map(e => e.id);

  // Query 3: Get ALL ticket counts in one query
  const ticketCounts = await db.query(`
    SELECT event_id,
           COUNT(*) FILTER (WHERE status = 'available') AS available_tickets,
           COUNT(*) AS total_tickets
    FROM tickets
    WHERE event_id = ANY($1)
    GROUP BY event_id
  `, [eventIds]);
  const ticketMap = new Map(ticketCounts.rows.map(t => [t.event_id, t]));

  // Assemble the response (no additional queries!)
  return events.rows.map(event => ({
    ...event,
    venue_name: venueMap.get(event.venue_id)?.name,
    city: venueMap.get(event.venue_id)?.city,
    available_tickets: parseInt(ticketMap.get(event.id)?.available_tickets || 0),
    total_tickets: parseInt(ticketMap.get(event.id)?.total_tickets || 0)
  }));
}
```

Total queries: **3** (down from 201).

### The DataLoader Pattern (Facebook)

Facebook created the **DataLoader** pattern to solve N+1 in GraphQL. The idea: batch and cache individual lookups within a single request.

```javascript
// Using the dataloader library
const DataLoader = require('dataloader');

// Create loaders (one per request — do not share across requests)
const venueLoader = new DataLoader(async (ids) => {
  const venues = await db.query('SELECT * FROM venues WHERE id = ANY($1)', [ids]);
  // DataLoader requires results in the same order as the input IDs
  const map = new Map(venues.rows.map(v => [v.id, v]));
  return ids.map(id => map.get(id) || null);
});

// Usage — looks like individual loads, but DataLoader batches them
async function getEvents() {
  const events = await db.query('SELECT * FROM events LIMIT 100');

  return Promise.all(events.rows.map(async (event) => {
    // DataLoader collects these calls and batches them into one query
    const venue = await venueLoader.load(event.venue_id);
    return { ...event, venue_name: venue?.name };
  }));
}
```

DataLoader:
- **Batches**: Multiple `.load()` calls in the same tick are combined into one batch query
- **Caches**: If the same venue_id is loaded twice, the second call returns the cached result
- **Per-request**: Create a new DataLoader per request to avoid stale data across requests

### Trade-offs of Batch Loading

| Pro | Con |
|-----|-----|
| Simple mental model (load what you need) | More queries than a JOIN (3 vs 1) |
| No complex SQL (just IN queries) | Requires collecting IDs first |
| Works great with GraphQL resolvers | Slight overhead from DataLoader batching logic |
| Avoids over-fetching | Application-level join (assembling results in code) |


<details>
<summary>💡 Hint 1: Direction</summary>
Instead of fetching venues one by one, collect all unique venue IDs from the events and fetch them in a single `WHERE id IN (...)` query. This is the DataLoader pattern.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
After fetching events, extract `venueIds = [...new Set(events.map(e => e.venue_id))]`, then `SELECT * FROM venues WHERE id = ANY($1)` with the array. Build a Map for O(1) lookup when attaching venue data to events.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The DataLoader pattern batches and deduplicates: even if 50 events reference venue ID 1, it fetches venue 1 only once. In Node.js, use the `dataloader` package. For ORMs like Prisma, use `include` or `findMany` with relations to trigger eager loading.
</details>

---

## Part 4: Fix 3 — ORM-Level Solutions (5 min)

### If You Use an ORM

Most ORMs have built-in mechanisms to avoid N+1, but they're opt-in. You have to know they exist.

**Prisma:**
```typescript
// N+1 (default: lazy loading)
const events = await prisma.event.findMany();
for (const event of events) {
  const venue = await prisma.venue.findUnique({ where: { id: event.venueId } });
  // This fires a query per event!
}

// Fixed: use include
const events = await prisma.event.findMany({
  include: {
    venue: true,
    _count: {
      select: { tickets: { where: { status: 'available' } } }
    }
  }
});
// Prisma generates efficient queries automatically
```

**TypeORM:**
```typescript
// N+1 (lazy relations)
const events = await eventRepository.find();
for (const event of events) {
  console.log(event.venue.name); // Triggers lazy load query
}

// Fixed: eager load with relations
const events = await eventRepository.find({
  relations: ['venue'],
});

// Or use QueryBuilder for more control
const events = await eventRepository
  .createQueryBuilder('event')
  .leftJoinAndSelect('event.venue', 'venue')
  .getMany();
```

**Django ORM:**
```python
# N+1
events = Event.objects.all()
for event in events:
    print(event.venue.name)  # Triggers query per event

# Fixed: select_related (JOIN) or prefetch_related (batch)
events = Event.objects.select_related('venue').all()
```

### ⚠️ Common Mistake: ORMs Hide the Problem

The biggest danger of ORMs is that `event.venue.name` looks like a simple property access but actually fires a database query. Your code compiles, runs, passes tests, and looks clean. The N+1 problem only becomes visible under load or when you enable query logging.

---

## Part 5: Prevention — Never Let It Happen Again (10 min)

### Strategy 1: Query Counting in Development

Add middleware that counts queries per request and warns if it's too high:

```javascript
// middleware/query-counter.js
let queryCount = 0;

// Monkey-patch the pool.query to count queries
const originalQuery = pool.query.bind(pool);
pool.query = async (...args) => {
  queryCount++;
  return originalQuery(...args);
};

function queryCountMiddleware(req, res, next) {
  queryCount = 0;
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    if (queryCount > 10) {
      console.warn(
        `⚠️  N+1 ALERT: ${req.method} ${req.path} fired ${queryCount} queries in ${duration}ms`
      );
    } else {
      console.log(
        `${req.method} ${req.path}: ${queryCount} queries in ${duration}ms`
      );
    }
  });

  next();
}
```

### Strategy 2: Query Logging Always On in Development

```sql
-- In your docker compose postgres config:
ALTER SYSTEM SET log_min_duration_statement = 0;
```

Make it a habit to watch the query log while developing. If you see repetitive queries, you have an N+1.

### Strategy 3: Performance Tests

Add a test that asserts the query count for critical endpoints:

```javascript
// tests/performance/query-count.test.js
test('events list should not have N+1', async () => {
  const queryLog = [];
  // Intercept queries
  pool.on('query', (q) => queryLog.push(q));

  await request(app).get('/api/events');

  // Assert reasonable query count
  expect(queryLog.length).toBeLessThanOrEqual(5);
  // If this fails, you introduced an N+1
});
```

### The Rule of Thumb

> If you see more than 10 queries per request, investigate. If you see N queries where N correlates with the number of items returned, you have an N+1.

### 📊 Summary: Three Fixes Compared

| Approach | Queries (100 events) | Complexity | Best For |
|----------|---------------------|------------|----------|
| **N+1 (broken)** | 201 | Low (but buggy) | Never |
| **JOIN (eager load)** | 1 | Medium (SQL) | When you always need all related data |
| **Batch (DataLoader)** | 3 | Medium (code) | GraphQL, conditional loading, multiple data sources |
| **ORM includes** | 1-3 (ORM decides) | Low (config) | When using an ORM with good N+1 support |

---

> **What did you notice?** The N+1 fix reduced queries from 201 to 1 and response time by 16x. How easy was it to spot the problem before enabling query logging? What does this say about making query visibility a default part of your development workflow?

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **N+1 problem** | Fetching a list then querying per item. 201 queries for 100 items. |
| **Detection** | Enable query logging. Watch for repetitive queries. Count queries per request. |
| **Fix: JOIN** | One query with JOINs. Fewest round-trips. Best when you always need related data. |
| **Fix: Batch** | Collect IDs, then IN query. DataLoader batches automatically. Best for GraphQL. |
| **Fix: ORM** | Use `include`, `select_related`, `eager: true`. ORMs have this built-in — use it. |
| **Prevention** | Query counting middleware, always-on query logging in dev, performance tests. |

**The key insight**: N+1 is invisible if you don't look at the query log. Make query visibility a default part of your development workflow, not something you check only when things are slow.

## What's Next

In **L2-M42: Graph Databases**, you'll add social features to TicketPulse — "friends attending this event" and "artists similar to ones you've seen" — using Neo4j and Cypher.

## Key Terms

| Term | Definition |
|------|-----------|
| **N+1 problem** | A performance anti-pattern where one query fetches a list and N additional queries fetch related data for each item. |
| **Eager loading** | A strategy that loads related data in the same query or batch, avoiding extra round trips to the database. |
| **DataLoader** | A utility that batches and deduplicates data-fetching calls within a single execution tick. |
| **Batch loading** | The technique of combining multiple individual data requests into a single query to reduce database round trips. |
| **Query logging** | The practice of recording all SQL queries an application executes, used to detect N+1 and other performance issues. |

---

## Part 6: Real-World Walkthrough — The Attendee Dashboard (15 min)

### The Scenario

TicketPulse's new "My Events" page shows a user's upcoming tickets with: event name, venue, date, ticket section, and organizer name. The naive implementation causes a severe N+1.

### Step 1: Reproduce the Bug

Build the naive version first so you can feel the problem:

```javascript
// routes/attendee.routes.js (naive — do NOT ship this)
router.get('/api/attendee/:userId/upcoming', async (req, res) => {
  // Query 1: Get all tickets for the user
  const tickets = await db.query(`
    SELECT t.*, o.id AS order_id
    FROM tickets t
    JOIN order_items oi ON oi.ticket_id = t.id
    JOIN orders o ON oi.order_id = o.id
    WHERE o.user_id = $1 AND t.status = 'sold'
    ORDER BY t.created_at DESC
    LIMIT 50
  `, [req.params.userId]);

  // For each ticket, fetch related data — HERE IS THE N+1
  const enriched = await Promise.all(tickets.rows.map(async (ticket) => {
    // N queries: one per ticket for event
    const event = await db.query(
      'SELECT id, name, event_date, category FROM events WHERE id = $1',
      [ticket.event_id]
    );

    // N queries: one per ticket for venue
    const venue = await db.query(
      'SELECT id, name, city, address FROM venues WHERE id = $1',
      [event.rows[0].venue_id]
    );

    // N queries: one per ticket for organizer
    const organizer = await db.query(
      'SELECT id, name, email FROM organizers WHERE id = $1',
      [event.rows[0].organizer_id]
    );

    return {
      ticket_id: ticket.id,
      section: ticket.section,
      row: ticket.row,
      seat: ticket.seat,
      event: event.rows[0],
      venue: venue.rows[0],
      organizer: organizer.rows[0],
    };
  }));

  res.json(enriched);
});
```

For a user with 50 tickets: **1 + 50 + 50 + 50 = 151 queries**.

### Step 2: Enable Query Logging and Confirm

```bash
# Enable logging in Postgres
docker exec -it ticketpulse-postgres psql -U postgres -c \
  "ALTER SYSTEM SET log_min_duration_statement = 0; SELECT pg_reload_conf();"

# Follow the logs in a separate terminal
docker compose logs -f postgres | grep LOG

# Hit the endpoint
curl http://localhost:3000/api/attendee/user_123/upcoming
```

Count the logs. You'll see a pattern:
```
LOG: SELECT t.*, ... FROM tickets ...  (the main query)
LOG: SELECT ... FROM events WHERE id = 4
LOG: SELECT ... FROM venues WHERE id = 2
LOG: SELECT ... FROM organizers WHERE id = 1
LOG: SELECT ... FROM events WHERE id = 7
LOG: SELECT ... FROM venues WHERE id = 5   ← same venue? duplicate query!
...
```

Notice venue queries are often duplicated — the same venue hosts multiple events, but the naive code fetches it per ticket anyway.

### Step 3: Fix With a Single Optimized JOIN

```javascript
// routes/attendee.routes.js (fixed)
router.get('/api/attendee/:userId/upcoming', async (req, res) => {
  // ONE query that fetches everything
  const result = await db.query(`
    SELECT
      t.id         AS ticket_id,
      t.section,
      t.row,
      t.seat,
      t.price,
      e.id         AS event_id,
      e.name       AS event_name,
      e.event_date,
      e.category,
      v.id         AS venue_id,
      v.name       AS venue_name,
      v.city,
      v.address,
      org.id       AS organizer_id,
      org.name     AS organizer_name,
      org.email    AS organizer_email
    FROM tickets t
    JOIN order_items oi  ON oi.ticket_id    = t.id
    JOIN orders o        ON oi.order_id     = o.id
    JOIN events e        ON t.event_id      = e.id
    JOIN venues v        ON e.venue_id      = v.id
    JOIN organizers org  ON e.organizer_id  = org.id
    WHERE o.user_id = $1 AND t.status = 'sold'
    ORDER BY e.event_date
    LIMIT 50
  `, [req.params.userId]);

  // Shape the flat rows into nested objects (no extra queries needed)
  const enriched = result.rows.map(row => ({
    ticket_id:    row.ticket_id,
    section:      row.section,
    row:          row.row,
    seat:         row.seat,
    price:        row.price,
    event: {
      id:         row.event_id,
      name:       row.event_name,
      event_date: row.event_date,
      category:   row.category,
    },
    venue: {
      id:         row.venue_id,
      name:       row.venue_name,
      city:       row.city,
      address:    row.address,
    },
    organizer: {
      id:         row.organizer_id,
      name:       row.organizer_name,
      email:      row.organizer_email,
    },
  }));

  res.json(enriched);
});
```

**Result**: 151 queries → 1 query. On a loaded production DB this is the difference between 1.5 seconds and 30ms.

### Step 4: Add the Query Count Assert to CI

Now lock in the fix so it never regresses:

```javascript
// tests/performance/attendee-dashboard.test.js
const { pool } = require('../../src/db');

test('attendee upcoming tickets: max 3 queries (with pagination overhead)', async () => {
  const queries = [];
  const originalQuery = pool.query.bind(pool);

  pool.query = (...args) => {
    queries.push(typeof args[0] === 'string' ? args[0].trim().split('\n')[0] : 'prepared');
    return originalQuery(...args);
  };

  await request(app)
    .get('/api/attendee/user_test_1/upcoming')
    .expect(200);

  pool.query = originalQuery;  // restore

  expect(queries.length).toBeLessThanOrEqual(3);
  // If this fails, someone introduced an N+1. The query log in queries[] tells you which one.
  console.log('Queries fired:', queries);
});
```

---

## Part 7: Guided Reflection (5 min)

Work through these questions. Write your answers — they will sharpen your instincts.

### Question 1: When is batch loading (DataLoader) better than a JOIN?

Consider these two scenarios:

**Scenario A**: A GraphQL API where the `event` resolver, `venue` resolver, and `organizer` resolver are all wired independently by three different engineers. They each call `db.query(... WHERE id = $1)` for their own entity.

**Scenario B**: A REST endpoint that you own end-to-end and always needs all three related objects.

Which approach (JOIN vs DataLoader) makes more sense for each, and why?

> **Guided answer for Scenario A**: DataLoader wins. You cannot easily refactor three independent resolvers into a single JOIN. DataLoader lets each resolver stay simple while automatically batching under the hood. The alternative — forcing all three into a single resolver — breaks GraphQL's composability.

> **Guided answer for Scenario B**: JOIN wins. You own the endpoint, you always need all the data, and a single JOIN is simpler to understand, debug, and monitor than DataLoader wiring.

### Question 2: A team member says "I added 5 new resolvers but they each only add one extra query — that's fine." How do you respond?

Think about: what happens when those resolvers are called for a list of 100 items? Draw the math: 5 extra queries × 100 items = 500 extra queries per page load.

"One extra query per item" is exactly the N+1 problem dressed up in better clothes. The word "only" is the danger.

### Question 3: Your monitoring shows a slow endpoint (800ms p99). How do you decide whether N+1 is the culprit vs a slow individual query?

Procedure:
1. Enable Postgres query logging (or use `pg_stat_statements`).
2. Load the slow endpoint once.
3. If you see **many queries with identical shapes** (same structure, different bind values), it's N+1.
4. If you see **one or two queries with high `actual time`** in EXPLAIN ANALYZE, it's a missing index or inefficient query — not N+1.

---

> **Want the deep theory?** See Ch 24 of the 100x Engineer Guide: "Query Optimization & Execution Plans" — covers EXPLAIN ANALYZE in depth, query planner statistics, and multi-table JOIN strategies.

---

## 📚 Further Reading
- [DataLoader README](https://github.com/graphql/dataloader) — Facebook's original batching library
- Chapter 24 of the 100x Engineer Guide: Query Optimization
- [Prisma: Solving N+1](https://www.prisma.io/docs/orm/prisma-client/queries/query-optimization-performance)
- [Django: select_related and prefetch_related](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-related)

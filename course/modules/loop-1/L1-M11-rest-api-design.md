# L1-M11: REST API Design

> **Loop 1 (Foundation)** | Section 1C: Building the API | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M05 (SQL & Data Modeling)
>
> **Source:** Chapters 25, 5, 7, 8 of the 100x Engineer Guide

---

## The Goal

By the end of this module, TicketPulse will have a clean, consistent REST API. You will have designed the endpoint signatures from user stories, implemented them in Express, tested them with curl, and understood why every URL, method, status code, and query parameter is the way it is.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Make sure your TicketPulse monolith is running:

```bash
cd ticketpulse
docker compose up -d
```

Now hit the existing health endpoint to confirm the server is alive:

```bash
curl http://localhost:3000/health
# Expected: {"status":"ok","timestamp":"2026-03-24T..."}
```

Good. The server is running. Time to give it a real API.

---

## 1. Designing Before Coding

### The User Stories

TicketPulse needs to support these user stories:

1. **As a visitor**, I want to browse upcoming events so I can find concerts to attend.
2. **As a visitor**, I want to see the details of a specific event (lineup, venue, pricing).
3. **As an admin**, I want to create new events.
4. **As an admin**, I want to update event details (change venue, update description).
5. **As an admin**, I want to cancel an event (soft delete).
6. **As a user**, I want to see available tickets for an event.
7. **As a user**, I want to purchase a ticket for an event.

---

### Reflect: Design the Endpoints First

<details>
<summary>💡 Hint 1: HTTP Methods Map to CRUD</summary>
Each HTTP method has a standard meaning: GET = read, POST = create, PATCH = partial update, DELETE = remove. Map each user story to the appropriate method. Browsing events is a GET; creating an event is a POST.
</details>

<details>
<summary>💡 Hint 2: Resources Are Nouns, Nested by Ownership</summary>
URLs should be plural nouns: `/api/events`, not `/api/getEvents`. Tickets belong to events, so they nest as a sub-resource: `/api/events/:id/tickets`. Think about which resources "own" which.
</details>

<details>
<summary>💡 Hint 3: Status Codes Tell the Story</summary>
201 for successful creation (POST), 204 for successful deletion with no body (DELETE), 404 when the resource ID does not exist, 409 when a business rule blocks the action (e.g., sold out). Match each endpoint to the right success and error codes.
</details>

> **Before reading on**, take 5 minutes and design the endpoint signatures yourself.
>
> For each user story above, write down:
> - The HTTP method (GET, POST, PATCH, DELETE)
> - The URL path
> - What goes in the request body (if anything)
> - What the response looks like
>
> Write them on paper or in a scratch file. Then compare with the design below.

This is not a trick question. There is a standard way to do this. But the exercise of designing it yourself -- and noticing where your instincts differ from the conventions -- is where the learning happens.

---

### The TicketPulse API Contract

Here is the design we will implement:

```
GET    /api/events                    # List all events (with filtering, sorting, pagination)
POST   /api/events                    # Create a new event
GET    /api/events/:id                # Get a single event by ID
PATCH  /api/events/:id                # Update an event
DELETE /api/events/:id                # Cancel an event (soft delete)

GET    /api/events/:id/tickets        # List available tickets for an event
POST   /api/events/:id/tickets        # Purchase a ticket for an event
```

Notice what we did NOT do:

```
# BAD -- verbs in the URL
POST   /api/createEvent
GET    /api/getEvent?id=123
POST   /api/purchaseTicket
POST   /api/cancelEvent

# BAD -- inconsistent nesting
GET    /api/tickets?eventId=123       # tickets exist as sub-resource of events
```

**Resources are nouns. HTTP methods are the verbs.** This is the core principle of REST API design. `POST /api/events` means "create an event." `DELETE /api/events/:id` means "delete an event." The URL names the thing; the method names the action.

Tickets are a sub-resource of events because a ticket cannot exist without an event. That relationship is expressed in the URL: `/api/events/:id/tickets`.

---

## 2. Build: Set Up the Router

<details>
<summary>💡 Hint 1: Express Router Basics</summary>
Use `Router()` from Express. Each route handler takes `(req: Request, res: Response, next: NextFunction)`. The `next(err)` call passes errors to your error-handling middleware instead of crashing the server. Mount the router with `app.use('/api/events', eventsRouter)`.
</details>

<details>
<summary>💡 Hint 2: Parameterized Routes and Sub-resources</summary>
Express captures URL parameters with `:id` syntax -- access it via `req.params.id`. For the tickets sub-resource router, use `Router({ mergeParams: true })` so the nested router can read `:id` from the parent mount path `/api/events/:id/tickets`.
</details>

<details>
<summary>💡 Hint 3: Dynamic PATCH with Parameterized Queries</summary>
For PATCH, build the SQL SET clause dynamically -- only include fields the client actually sent. Use a `paramIndex` counter to generate `$1`, `$2`, etc. for each field, push values into an array, and join with commas: `SET title = $1, venue = $2 WHERE id = $3`.
</details>

Create the route file for events. We will use Express with TypeScript:

```typescript
// src/routes/events.ts

import { Router, Request, Response, NextFunction } from 'express';
import { pool } from '../db';

const router = Router();

// -------------------------------------------------------
// GET /api/events -- List events
// -------------------------------------------------------
router.get('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const result = await pool.query(
      `SELECT id, title, description, venue, city, date, created_at
       FROM events
       WHERE cancelled = false
       ORDER BY date ASC`
    );

    res.status(200).json({
      data: result.rows,
      meta: {
        count: result.rows.length,
      },
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// POST /api/events -- Create an event
// -------------------------------------------------------
router.post('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { title, description, venue, city, date, totalTickets, priceInCents } = req.body;

    // Basic validation (we will improve this in M12)
    if (!title || !venue || !date || !totalTickets || !priceInCents) {
      res.status(400).json({
        error: {
          code: 'MISSING_FIELDS',
          message: 'Required fields: title, venue, date, totalTickets, priceInCents',
        },
      });
      return;
    }

    const result = await pool.query(
      `INSERT INTO events (title, description, venue, city, date, total_tickets, available_tickets, price_in_cents)
       VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
       RETURNING id, title, description, venue, city, date, total_tickets, available_tickets, price_in_cents, created_at`,
      [title, description || '', venue, city || '', date, totalTickets, priceInCents]
    );

    const event = result.rows[0];

    res.status(201).json({
      data: formatEvent(event),
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// GET /api/events/:id -- Get a single event
// -------------------------------------------------------
router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { id } = req.params;

    const result = await pool.query(
      `SELECT id, title, description, venue, city, date, total_tickets, available_tickets, price_in_cents, cancelled, created_at
       FROM events
       WHERE id = $1`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({
        error: {
          code: 'NOT_FOUND',
          message: `Event with id '${id}' not found.`,
        },
      });
      return;
    }

    res.status(200).json({
      data: formatEvent(result.rows[0]),
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// PATCH /api/events/:id -- Update an event
// -------------------------------------------------------
router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { id } = req.params;
    const { title, description, venue, city, date } = req.body;

    // Build dynamic SET clause -- only update fields that were sent
    const updates: string[] = [];
    const values: any[] = [];
    let paramIndex = 1;

    if (title !== undefined) {
      updates.push(`title = $${paramIndex++}`);
      values.push(title);
    }
    if (description !== undefined) {
      updates.push(`description = $${paramIndex++}`);
      values.push(description);
    }
    if (venue !== undefined) {
      updates.push(`venue = $${paramIndex++}`);
      values.push(venue);
    }
    if (city !== undefined) {
      updates.push(`city = $${paramIndex++}`);
      values.push(city);
    }
    if (date !== undefined) {
      updates.push(`date = $${paramIndex++}`);
      values.push(date);
    }

    if (updates.length === 0) {
      res.status(400).json({
        error: {
          code: 'NO_UPDATES',
          message: 'No valid fields to update. Provide at least one of: title, description, venue, city, date.',
        },
      });
      return;
    }

    updates.push(`updated_at = NOW()`);
    values.push(id);

    const result = await pool.query(
      `UPDATE events SET ${updates.join(', ')} WHERE id = $${paramIndex} AND cancelled = false
       RETURNING id, title, description, venue, city, date, total_tickets, available_tickets, price_in_cents, created_at, updated_at`,
      values
    );

    if (result.rows.length === 0) {
      res.status(404).json({
        error: {
          code: 'NOT_FOUND',
          message: `Event with id '${id}' not found or is cancelled.`,
        },
      });
      return;
    }

    res.status(200).json({
      data: formatEvent(result.rows[0]),
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// DELETE /api/events/:id -- Cancel (soft delete) an event
// -------------------------------------------------------
router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { id } = req.params;

    const result = await pool.query(
      `UPDATE events SET cancelled = true, updated_at = NOW()
       WHERE id = $1 AND cancelled = false
       RETURNING id`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({
        error: {
          code: 'NOT_FOUND',
          message: `Event with id '${id}' not found or already cancelled.`,
        },
      });
      return;
    }

    // 204 No Content -- successful deletion, no body
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// Helper: format a database row into a camelCase response
// -------------------------------------------------------
function formatEvent(row: any) {
  return {
    id: row.id,
    title: row.title,
    description: row.description,
    venue: row.venue,
    city: row.city,
    date: row.date,
    totalTickets: row.total_tickets,
    availableTickets: row.available_tickets,
    priceInCents: row.price_in_cents,
    cancelled: row.cancelled || false,
    createdAt: row.created_at,
    updatedAt: row.updated_at || null,
  };
}

export default router;
```

And the tickets sub-resource:

```typescript
// src/routes/tickets.ts

import { Router, Request, Response, NextFunction } from 'express';
import { pool } from '../db';

const router = Router({ mergeParams: true }); // mergeParams gives us access to :id from parent route

// -------------------------------------------------------
// GET /api/events/:id/tickets -- List tickets for an event
// -------------------------------------------------------
router.get('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { id: eventId } = req.params;

    // First, verify the event exists
    const eventResult = await pool.query(
      'SELECT id, title, available_tickets, price_in_cents FROM events WHERE id = $1 AND cancelled = false',
      [eventId]
    );

    if (eventResult.rows.length === 0) {
      res.status(404).json({
        error: {
          code: 'NOT_FOUND',
          message: `Event with id '${eventId}' not found.`,
        },
      });
      return;
    }

    const tickets = await pool.query(
      `SELECT id, event_id, purchaser_email, tier, price_in_cents, purchased_at
       FROM tickets
       WHERE event_id = $1
       ORDER BY purchased_at DESC`,
      [eventId]
    );

    res.status(200).json({
      data: tickets.rows.map(formatTicket),
      meta: {
        eventId,
        availableTickets: eventResult.rows[0].available_tickets,
        count: tickets.rows.length,
      },
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// POST /api/events/:id/tickets -- Purchase a ticket
// -------------------------------------------------------
router.post('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { id: eventId } = req.params;
    const { email, tier } = req.body;

    if (!email) {
      res.status(400).json({
        error: {
          code: 'MISSING_FIELDS',
          message: 'Required field: email',
        },
      });
      return;
    }

    // Use a transaction to prevent overselling
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // Lock the event row to prevent race conditions
      const eventResult = await client.query(
        'SELECT id, title, available_tickets, price_in_cents FROM events WHERE id = $1 AND cancelled = false FOR UPDATE',
        [eventId]
      );

      if (eventResult.rows.length === 0) {
        await client.query('ROLLBACK');
        res.status(404).json({
          error: {
            code: 'NOT_FOUND',
            message: `Event with id '${eventId}' not found.`,
          },
        });
        return;
      }

      const event = eventResult.rows[0];

      if (event.available_tickets <= 0) {
        await client.query('ROLLBACK');
        res.status(409).json({
          error: {
            code: 'SOLD_OUT',
            message: `Event '${event.title}' is sold out. No tickets available.`,
          },
        });
        return;
      }

      // Create the ticket
      const ticketResult = await client.query(
        `INSERT INTO tickets (event_id, purchaser_email, tier, price_in_cents)
         VALUES ($1, $2, $3, $4)
         RETURNING id, event_id, purchaser_email, tier, price_in_cents, purchased_at`,
        [eventId, email, tier || 'general', event.price_in_cents]
      );

      // Decrement available tickets
      await client.query(
        'UPDATE events SET available_tickets = available_tickets - 1 WHERE id = $1',
        [eventId]
      );

      await client.query('COMMIT');

      res.status(201).json({
        data: formatTicket(ticketResult.rows[0]),
      });
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  } catch (err) {
    next(err);
  }
});

function formatTicket(row: any) {
  return {
    id: row.id,
    eventId: row.event_id,
    purchaserEmail: row.purchaser_email,
    tier: row.tier,
    priceInCents: row.price_in_cents,
    purchasedAt: row.purchased_at,
  };
}

export default router;
```

Wire these into the main app:

```typescript
// src/app.ts (add these lines)

import eventsRouter from './routes/events';
import ticketsRouter from './routes/tickets';

app.use(express.json());
app.use('/api/events', eventsRouter);
app.use('/api/events/:id/tickets', ticketsRouter);
```

---

## 3. Try It: Test Every Endpoint with curl

Restart your server if needed, then run through every endpoint:

### Create an event

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Radiohead @ Madison Square Garden",
    "description": "OK Computer 30th Anniversary Tour",
    "venue": "Madison Square Garden",
    "city": "NYC",
    "date": "2026-09-15T20:00:00Z",
    "totalTickets": 500,
    "priceInCents": 8500
  }' | jq .
```

Expected response (status 201):

```json
{
  "data": {
    "id": 1,
    "title": "Radiohead @ Madison Square Garden",
    "description": "OK Computer 30th Anniversary Tour",
    "venue": "Madison Square Garden",
    "city": "NYC",
    "date": "2026-09-15T20:00:00.000Z",
    "totalTickets": 500,
    "availableTickets": 500,
    "priceInCents": 8500,
    "cancelled": false,
    "createdAt": "2026-03-24T..."
  }
}
```

### List events

```bash
curl -s http://localhost:3000/api/events | jq .
```

### Get a single event

```bash
curl -s http://localhost:3000/api/events/1 | jq .
```

### Get a nonexistent event (expect 404)

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" http://localhost:3000/api/events/9999 | jq .
```

### Update an event (PATCH)

```bash
curl -s -X PATCH http://localhost:3000/api/events/1 \
  -H "Content-Type: application/json" \
  -d '{"description": "OK Computer 30th Anniversary Tour - UPDATED LINEUP"}' | jq .
```

Notice that we only sent `description`. The other fields remain unchanged. That is what PATCH means -- partial update. If we used PUT, we would need to send the entire event object.

### Purchase a ticket

```bash
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H "Content-Type: application/json" \
  -d '{"email": "fan@example.com", "tier": "general"}' | jq .
```

Expected: status 201 with the ticket object.

### List tickets for an event

```bash
curl -s http://localhost:3000/api/events/1/tickets | jq .
```

### Cancel an event

```bash
curl -s -X DELETE -w "\nHTTP Status: %{http_code}\n" http://localhost:3000/api/events/1
```

Expected: status 204, empty body.

---

## 4. Status Codes in Context

Every status code tells a story. Here is what each one means in TicketPulse:

| Status | Meaning | TicketPulse Example |
|--------|---------|-------------------|
| **200 OK** | Success, here is the data | GET /api/events returns the list |
| **201 Created** | New resource created | POST /api/events creates an event |
| **204 No Content** | Success, nothing to return | DELETE /api/events/:id cancels an event |
| **400 Bad Request** | Malformed request | POST /api/events with no title |
| **401 Unauthorized** | Not authenticated | Accessing a protected route without a token (coming in M13) |
| **404 Not Found** | Resource does not exist | GET /api/events/9999 |
| **409 Conflict** | State conflict | POST /api/events/:id/tickets when event is sold out |
| **500 Internal Server Error** | Bug in our code | Unhandled database error |

The most important distinction: **4xx means the client did something wrong. 5xx means we did something wrong.** If your API returns a 500 for invalid user input, that is a bug in your code, not a server error.

---

## 5. Request/Response Design

### JSON Structure Conventions

Every response follows the same shape:

```typescript
// Success (single resource)
{ "data": { ... } }

// Success (list)
{ "data": [ ... ], "meta": { "count": 10 } }

// Error
{ "error": { "code": "...", "message": "..." } }
```

This is not arbitrary. Wrapping the result in `data` means:
1. You can always add metadata (pagination, rate limit info) without changing the top-level shape.
2. Clients can check for `response.error` to detect errors, or `response.data` for success.
3. Every endpoint feels the same.

### Naming: camelCase in JSON

We use `camelCase` for JSON field names because our primary consumers are JavaScript/TypeScript clients:

```json
{
  "totalTickets": 500,
  "availableTickets": 498,
  "priceInCents": 8500,
  "createdAt": "2026-03-24T10:00:00Z"
}
```

The database uses `snake_case` (`total_tickets`, `available_tickets`). The `formatEvent` helper translates between them. This is a deliberate boundary -- the API contract is independent of the database schema.

---

## 6. Query Parameters: Filtering, Sorting, Pagination

<details>
<summary>💡 Hint 1: Parse and Clamp Pagination Inputs</summary>
Read `page` and `limit` from `req.query`, parse them with `parseInt()`, and clamp them to sane ranges: `page` minimum 1, `limit` between 1 and 100. Calculate the SQL OFFSET as `(page - 1) * limit`. Always run a COUNT query alongside the data query so you can return `totalPages`.
</details>

<details>
<summary>💡 Hint 2: Build WHERE Clauses Dynamically</summary>
Start with `conditions = ['cancelled = false']` and `values = []`. For each filter (city, venue, dateFrom, dateTo), push a parameterized condition like `city ILIKE $1` and push the value. Use ILIKE for case-insensitive partial matching: `%${req.query.city}%`.
</details>

<details>
<summary>💡 Hint 3: Sort Safely With an Allowlist</summary>
Never interpolate user input directly into ORDER BY -- that is a SQL injection vector. Define an allowlist of sortable columns (`date`, `title`, `price_in_cents`). Map camelCase query params to snake_case DB columns. Support a `-` prefix for descending: `?sort=-date` becomes `ORDER BY date DESC`.
</details>

Our `GET /api/events` endpoint currently returns everything. That does not scale. Let us add filtering, sorting, and pagination.

Update the list endpoint:

```typescript
// src/routes/events.ts -- updated GET / handler

router.get('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    // --- Pagination ---
    const page = Math.max(1, parseInt(req.query.page as string) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(req.query.limit as string) || 20));
    const offset = (page - 1) * limit;

    // --- Filtering ---
    const conditions: string[] = ['cancelled = false'];
    const values: any[] = [];
    let paramIndex = 1;

    if (req.query.city) {
      conditions.push(`city ILIKE $${paramIndex++}`);
      values.push(`%${req.query.city}%`);
    }

    if (req.query.venue) {
      conditions.push(`venue ILIKE $${paramIndex++}`);
      values.push(`%${req.query.venue}%`);
    }

    if (req.query.dateFrom) {
      conditions.push(`date >= $${paramIndex++}`);
      values.push(req.query.dateFrom);
    }

    if (req.query.dateTo) {
      conditions.push(`date <= $${paramIndex++}`);
      values.push(req.query.dateTo);
    }

    // --- Sorting ---
    const allowedSortFields = ['date', 'title', 'city', 'created_at', 'price_in_cents'];
    let orderBy = 'date ASC';

    if (req.query.sort) {
      const sortParam = req.query.sort as string;
      const descending = sortParam.startsWith('-');
      const field = descending ? sortParam.slice(1) : sortParam;

      // Map camelCase query params to snake_case DB columns
      const fieldMap: Record<string, string> = {
        date: 'date',
        title: 'title',
        city: 'city',
        createdAt: 'created_at',
        price: 'price_in_cents',
      };

      const dbField = fieldMap[field];
      if (dbField && allowedSortFields.includes(dbField)) {
        orderBy = `${dbField} ${descending ? 'DESC' : 'ASC'}`;
      }
    }

    // --- Build the query ---
    const whereClause = conditions.join(' AND ');

    const countResult = await pool.query(
      `SELECT COUNT(*) FROM events WHERE ${whereClause}`,
      values
    );
    const totalCount = parseInt(countResult.rows[0].count);

    const dataResult = await pool.query(
      `SELECT id, title, description, venue, city, date, total_tickets, available_tickets, price_in_cents, created_at
       FROM events
       WHERE ${whereClause}
       ORDER BY ${orderBy}
       LIMIT $${paramIndex++} OFFSET $${paramIndex++}`,
      [...values, limit, offset]
    );

    res.status(200).json({
      data: dataResult.rows.map(formatEvent),
      pagination: {
        page,
        limit,
        totalCount,
        totalPages: Math.ceil(totalCount / limit),
      },
    });
  } catch (err) {
    next(err);
  }
});
```

### Try It: Filtering and Pagination

```bash
# Filter by city
curl -s "http://localhost:3000/api/events?city=NYC" | jq .

# Sort by date descending (newest first)
curl -s "http://localhost:3000/api/events?sort=-date" | jq .

# Paginate: page 1 with 5 results per page
curl -s "http://localhost:3000/api/events?page=1&limit=5" | jq .

# Combine them: NYC events, newest first, 10 per page
curl -s "http://localhost:3000/api/events?city=NYC&sort=-date&page=1&limit=10" | jq .
```

The pagination response tells the client everything it needs to build page navigation:

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "totalCount": 47,
    "totalPages": 5
  }
}
```

---

## 7. Why These Conventions Matter

### Consistency is the Foundation

Every endpoint follows the same patterns:
- Success responses always have `data`
- Error responses always have `error` with `code` and `message`
- List endpoints always have `pagination`
- URLs are always plural nouns
- Field names are always camelCase in JSON, snake_case in the database

A developer who learns how `/api/events` works can predict exactly how `/api/users`, `/api/venues`, and every future resource will behave. That predictability is the most valuable property an API can have.

### The Stripe Standard

Stripe's API has not had a breaking change in over a decade. Their secret is ruthless consistency: every resource follows the same patterns, every error has the same shape, every list is paginated the same way. When you need a model for API design, Stripe is the gold standard.

---

## 8. Reflect: What Would You Add?

> Before moving on, think about these questions:
>
> 1. Our pagination uses offset-based (`page` and `limit`). What happens if someone inserts a new event while a user is paging through results? (Hint: items shift.)
>
> 2. We hardcoded the sort field allowlist. Why not allow sorting by any column? What is the security risk?
>
> 3. The ticket purchase endpoint uses `SELECT ... FOR UPDATE` to prevent overselling. What happens if two users try to buy the last ticket at the exact same time? Trace through the code.
>
> 4. We return `priceInCents` (integer) instead of `price` (float). Why? (Hint: try `0.1 + 0.2` in a JavaScript console.)

---

## 9. Checkpoint

After this module, your TicketPulse API should:

- [ ] `GET /api/events` -- list events with filtering, sorting, and pagination
- [ ] `POST /api/events` -- create a new event (returns 201)
- [ ] `GET /api/events/:id` -- get a single event (returns 404 if not found)
- [ ] `PATCH /api/events/:id` -- partially update an event
- [ ] `DELETE /api/events/:id` -- soft-delete an event (returns 204)
- [ ] `GET /api/events/:id/tickets` -- list tickets for an event
- [ ] `POST /api/events/:id/tickets` -- purchase a ticket (returns 409 if sold out)

Every response uses `{ data: ... }` or `{ error: { code, message } }`. Every list has pagination. Every 404 has a clear message.

**Next up:** L1-M12 where we make error handling truly excellent -- structured error codes, validation that reports ALL issues, and request ID tracing.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Resource** | A noun in your API -- events, tickets, users. The thing the URL points to. |
| **Sub-resource** | A resource nested under another -- `/events/:id/tickets`. Implies ownership. |
| **CRUD** | Create (POST), Read (GET), Update (PATCH/PUT), Delete (DELETE). |
| **Idempotent** | Calling it N times has the same effect as calling it once. GET, PUT, DELETE are idempotent. POST is not. |
| **Soft delete** | Marking a record as cancelled/deleted without removing it from the database. Preserves history. |
| **Offset pagination** | Using `page` and `limit` to paginate. Simple but degrades on large datasets. |
| **Cursor pagination** | Using an opaque token to mark your position. Stable and fast at any depth. |
---

## What's Next

In **Error Handling That Doesn't Suck** (L1-M12), you'll build on what you learned here and take it further.

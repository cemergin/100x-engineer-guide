# Exercise: Build the TicketPulse Database

## What We're Doing
You'll start PostgreSQL in Docker, create 7 tables for the TicketPulse schema, populate them with realistic concert data, and write JOIN queries to answer business questions.

## Before You Start
- Docker installed and running
- A terminal open
- The TicketPulse repo cloned (or just a terminal — we can run standalone)

## Steps

### Step 1: Start PostgreSQL

```bash
docker compose up -d postgres
```

Or standalone:

```bash
docker run -d \
  --name ticketpulse-postgres \
  -e POSTGRES_USER=ticketpulse \
  -e POSTGRES_PASSWORD=ticketpulse \
  -e POSTGRES_DB=ticketpulse \
  -p 5432:5432 \
  postgres:16
```

> **Pro tip:** Keep this container around. You'll use it for the next 5 modules.

### Step 2: Connect via psql

```bash
docker exec -it ticketpulse-postgres psql -U ticketpulse
```

You should see the `ticketpulse=#` prompt.

> **Before you continue:** What do you think happens if you try to connect before the container finishes initializing?

### Step 3: Verify the Connection

```sql
SELECT version();
\l
SELECT current_database();
```

> **Pro tip:** The `\` commands (`\l`, `\dt`, `\d`) are psql meta-commands — shortcuts built into the terminal client, not SQL.

### Step 4: Think About the Schema

Before writing any SQL, consider what TicketPulse needs: Venues, Artists, Events, Tickets, Orders, Order Items. Which entities need their own table? Where do foreign keys go? Sketch it.

### Step 5: Create the Tables

Try creating the tables yourself. Rules:
- `id BIGSERIAL PRIMARY KEY` on every table
- Appropriate types: `VARCHAR`, `TEXT`, `INTEGER`, `NUMERIC`, `TIMESTAMPTZ`
- `NOT NULL` where values must exist
- Foreign keys for relationships

Then compare with the solution in lesson.md.

### Step 6: Verify Your Schema

```sql
\dt
\d events
\d tickets
```

### Step 7: Insert Sample Data

Run the INSERT statements from the lesson. Verify:

```sql
SELECT 'venues' AS t, COUNT(*) FROM venues
UNION ALL SELECT 'artists', COUNT(*) FROM artists
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'tickets', COUNT(*) FROM tickets;
```

### Step 8: Your First JOIN

```sql
SELECT e.name AS event_name, v.name AS venue_name, v.city, e.event_date
FROM events e JOIN venues v ON e.venue_id = v.id
ORDER BY e.event_date;
```

> **Before you continue:** Predict how many rows. Do all events have a venue?

### Step 9: Multi-Table JOIN with Aggregation

```sql
SELECT e.name, COUNT(t.id) AS total_tickets,
       COUNT(t.id) FILTER (WHERE t.status = 'sold') AS sold,
       SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
FROM events e JOIN tickets t ON t.event_id = e.id
GROUP BY e.id, e.name;
```

### Step 10: LEFT JOIN vs INNER JOIN

Run both and compare which venues appear in each.

### Step 11: Practice Queries

Write queries for: (1) Artists at events with 5+ available tickets, (2) Orders with ticket counts, (3) Per-venue event counts and avg price.

## What Just Happened?

You designed a relational schema from business requirements, enforced integrity with constraints, and used JOINs to answer cross-table questions. This is what backend engineers do daily.

> **What did you notice?** Which part was hardest — designing the schema, writing the SQL, or understanding the JOINs? That's where to focus your practice.

## Try This

- `ALTER TABLE venues ADD COLUMN phone VARCHAR(20);`
- Insert a ticket with a fake event_id. What happens?
- Run `EXPLAIN` on a JOIN query. Don't decode it yet — that's Module 7.

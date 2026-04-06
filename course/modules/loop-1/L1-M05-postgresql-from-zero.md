# L1-M05: PostgreSQL From Zero

> **Loop 1 (Foundation)** | Section 1B: Data & Databases | ⏱️ 75 min | 🟢 Core | Prerequisites: Docker basics, terminal comfort
>
> **Source:** Chapters 2, 24 of the 100x Engineer Guide

## What You'll Learn
- How to run PostgreSQL in Docker and connect via `psql`
- Relational database fundamentals: tables, columns, types, constraints
- How to design a real schema from requirements (TicketPulse)
- JOINs, basic queries, and inserting data
- How to read a schema diagram and think in relations

## Why This Matters
Every production application you will ever work on stores data. PostgreSQL is the default choice for serious workloads — it powers Instagram, Stripe, Discord, and thousands of startups. If you understand Postgres deeply, you can work with any relational database. This module gets you from zero to a working schema with real data in 75 minutes.

## Prereq Check
Before starting, confirm you have Docker running:

```bash
docker --version
# Should output Docker version 24+ or similar
```

If Docker is not installed, visit https://docs.docker.com/get-docker/ and install it now. Everything in this module runs inside a container — no local Postgres install needed.

---

## Part 1: Start PostgreSQL (5 min)

TicketPulse is our running project — a ticket sales platform for events. It needs a database. Let's start one.

### 🔍 Try It Now

```bash
# Start PostgreSQL in a Docker container
docker compose up -d postgres
```

If you don't have the TicketPulse `docker-compose.yml` yet, use this standalone command:

```bash
docker run -d \
  --name ticketpulse-postgres \
  -e POSTGRES_USER=ticketpulse \
  -e POSTGRES_PASSWORD=ticketpulse \
  -e POSTGRES_DB=ticketpulse \
  -p 5432:5432 \
  postgres:16
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Wait a few seconds for it to initialize, then connect:

```bash
docker exec -it ticketpulse-postgres psql -U ticketpulse
```

You should see:

```
psql (16.x)
Type "help" for help.

ticketpulse=#
```

You are now inside the PostgreSQL interactive terminal. Every SQL command you type here runs directly against the database.

### 🔍 Try It Now

Run these commands to confirm everything works:

```sql
-- What version are we running?
SELECT version();

-- What databases exist?
\l

-- What's our current database?
SELECT current_database();
```

> **Pro tip:** The `\` commands (like `\l`, `\dt`, `\d`) are `psql` meta-commands — they are shortcuts built into the terminal client, not SQL. You'll use them constantly.

---

## Part 2: Understanding the Requirements (10 min)

Before writing any SQL, let's think about what TicketPulse needs to store. Here are the business requirements:

**TicketPulse is a ticket sales platform. It needs to track:**

1. **Venues** — places where events happen (name, city, state, capacity)
2. **Artists** — performers (name, genre, bio)
3. **Events** — shows at venues featuring artists (name, date, venue, description)
4. **Tickets** — individual tickets for events (section, row, seat, price, status)
5. **Orders** — purchases by customers (customer email, customer name, order date, total)
6. **Order Items** — which tickets are in which order (linking orders to tickets)

### 🤔 Reflect

Before looking at the solution, think about:
- Which entities need their own table?
- What are the relationships? (One-to-many? Many-to-many?)
- Where do foreign keys go?
- What columns should NOT allow NULL?

Sketch it on paper or in a text file. Spend 5 minutes on this before scrolling down.

---

### The Relationships

```
venues ──< events ──< tickets ──< order_items >── orders
                 \
                  ── event_artists ── artists
```

Reading this:
- A venue has many events (one-to-many)
- An event has many tickets (one-to-many)
- An event can have many artists, and an artist can play many events (many-to-many, needs a junction table)
- An order has many order items (one-to-many)
- Each order item links to one ticket (many-to-one)

---

## Part 3: Build the Schema (20 min)

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Your Turn

<details>
<summary>💡 Hint 1: Direction</summary>
Start with tables that have no foreign keys — venues and artists depend on nothing else. Then create events (which REFERENCES venues), then tickets (which REFERENCES events), and so on. If you try to create tickets before events exists, Postgres will error on the foreign key.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
For the many-to-many between events and artists, you need a junction table (event_artists) with a composite primary key: PRIMARY KEY (event_id, artist_id). Use BIGINT NOT NULL REFERENCES events(id) and BIGINT NOT NULL REFERENCES artists(id) for the two columns. No separate BIGSERIAL id needed here.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
For the money columns (ticket price, order total), use NUMERIC(10, 2) NOT NULL with a CHECK (price >= 0) constraint. For status columns, use a CHECK constraint with IN ('value1', 'value2', ...) to enforce valid values at the database level. Every table should end with created_at TIMESTAMPTZ NOT NULL DEFAULT NOW() and updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW().
</details>


Try creating the tables yourself first. Here are the rules:
- Every table needs an `id` column (use `BIGSERIAL PRIMARY KEY`)
- Use appropriate types: `VARCHAR`, `TEXT`, `INTEGER`, `NUMERIC`, `TIMESTAMPTZ`, `DATE`
- Add `NOT NULL` where a value must always exist
- Add foreign keys to enforce relationships
- Add `created_at` and `updated_at` timestamps to every table

Give it your best shot, then compare with the solution below.

---

### The Solution

```sql
-- ============================================================
-- TicketPulse Schema
-- ============================================================

-- Venues: where events happen
CREATE TABLE venues (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50) NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Artists: who performs
CREATE TABLE artists (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    genre VARCHAR(100),
    bio TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Events: a show at a venue on a date
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    venue_id BIGINT NOT NULL REFERENCES venues(id),
    event_date TIMESTAMPTZ NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'on_sale', 'sold_out', 'cancelled', 'completed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Junction table: many-to-many between events and artists
CREATE TABLE event_artists (
    event_id BIGINT NOT NULL REFERENCES events(id),
    artist_id BIGINT NOT NULL REFERENCES artists(id),
    is_headliner BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (event_id, artist_id)
);

-- Tickets: individual seats for an event
CREATE TABLE tickets (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id),
    section VARCHAR(50) NOT NULL,
    row VARCHAR(10),
    seat VARCHAR(10),
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'reserved', 'sold', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Orders: a customer's purchase
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    customer_email VARCHAR(255) NOT NULL,
    customer_name VARCHAR(200) NOT NULL,
    total NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'cancelled', 'refunded')),
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Order items: which tickets belong to which order
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    ticket_id BIGINT NOT NULL REFERENCES tickets(id),
    price_at_purchase NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 🔍 Try It Now

Copy and paste the entire schema into your `psql` session. Then verify:

```sql
-- List all tables we just created
\dt

-- Inspect a specific table's structure
\d events

-- See all foreign key constraints
\d tickets
```

You should see 7 tables: `venues`, `artists`, `events`, `event_artists`, `tickets`, `orders`, `order_items`.

> **Pro tip:** Design Decisions Explained

| Decision | Why |
|----------|-----|
| `BIGSERIAL` for IDs | Auto-incrementing, 64-bit. Handles billions of rows. Use this over `SERIAL` (32-bit) by default. |
| `NUMERIC(10,2)` for prices | Exact decimal arithmetic. Never use `FLOAT` or `DOUBLE` for money — they have rounding errors. |
| `TIMESTAMPTZ` not `TIMESTAMP` | Always store timestamps with timezone. `TIMESTAMP` without timezone is a footgun — it silently drops timezone info. |
| `CHECK` constraints | Database-level validation. Even if your app has a bug, invalid data cannot enter the database. |
| `price_at_purchase` in order_items | Captures the price at the time of sale. If ticket prices change later, historical orders stay accurate. |
| Junction table `event_artists` | Many-to-many relationships always need a junction table in relational databases. The composite primary key prevents duplicates. |

---

## Part 4: Insert Sample Data (15 min)

An empty database is useless for learning. Let's populate TicketPulse with realistic data.

### 🔍 Try It Now

```sql
-- ============================================================
-- Sample Data for TicketPulse
-- ============================================================

-- Venues
INSERT INTO venues (name, city, state, capacity, address) VALUES
('Madison Square Garden', 'New York', 'NY', 20000, '4 Pennsylvania Plaza, New York, NY 10001'),
('The Fillmore', 'San Francisco', 'CA', 1150, '1805 Geary Blvd, San Francisco, CA 94115'),
('Red Rocks Amphitheatre', 'Morrison', 'CO', 9525, '18300 W Alameda Pkwy, Morrison, CO 80465'),
('Ryman Auditorium', 'Nashville', 'TN', 2362, '116 5th Ave N, Nashville, TN 37219'),
('The Troubadour', 'Los Angeles', 'CA', 500, '9081 Santa Monica Blvd, West Hollywood, CA 90069');

-- Artists
INSERT INTO artists (name, genre, bio) VALUES
('Aurora Flux', 'Electronic', 'Berlin-based electronic producer known for immersive live shows'),
('The Midnight Riders', 'Rock', 'Nashville rock band blending southern and classic rock'),
('Jade Patel', 'Jazz', 'Grammy-nominated jazz pianist and composer'),
('Neon Collective', 'Indie', 'Brooklyn indie collective fusing lo-fi and experimental sounds'),
('Sierra Gold', 'Country', 'Rising country star with three platinum singles');

-- Events
INSERT INTO events (name, venue_id, event_date, description, status) VALUES
('Aurora Flux: Synthesis Tour', 1, '2026-06-15 20:00:00-04', 'The groundbreaking Synthesis Tour hits NYC', 'on_sale'),
('Midnight Riders Live at Red Rocks', 3, '2026-07-20 19:30:00-06', 'An unforgettable night under the stars', 'on_sale'),
('Jazz at the Fillmore: Jade Patel', 2, '2026-05-10 21:00:00-07', 'An intimate evening of jazz', 'on_sale'),
('Neon Collective + Aurora Flux', 5, '2026-08-01 20:00:00-07', 'A collaborative night of electronic and indie', 'scheduled'),
('Sierra Gold: Nashville Homecoming', 4, '2026-09-15 19:00:00-05', 'Sierra Gold returns to the Ryman', 'on_sale'),
('New Year''s Eve Extravaganza', 1, '2026-12-31 21:00:00-05', 'Ring in the new year at MSG', 'scheduled');

-- Event-Artist assignments
INSERT INTO event_artists (event_id, artist_id, is_headliner) VALUES
(1, 1, true),   -- Aurora Flux headlines at MSG
(2, 2, true),   -- Midnight Riders headline at Red Rocks
(3, 3, true),   -- Jade Patel headlines at Fillmore
(4, 4, true),   -- Neon Collective headlines at Troubadour
(4, 1, false),  -- Aurora Flux is support act
(5, 5, true),   -- Sierra Gold headlines at Ryman
(6, 1, true),   -- Aurora Flux headlines NYE
(6, 4, false),  -- Neon Collective support act at NYE
(6, 3, false);  -- Jade Patel support act at NYE

-- Generate tickets for events (simplified — 20 tickets per event)
INSERT INTO tickets (event_id, section, row, seat, price, status)
SELECT
    e.id,
    CASE (s % 3)
        WHEN 0 THEN 'Floor'
        WHEN 1 THEN 'Lower Bowl'
        WHEN 2 THEN 'Upper Bowl'
    END,
    'R' || ((s / 10) + 1),
    'S' || ((s % 10) + 1),
    CASE (s % 3)
        WHEN 0 THEN 150.00
        WHEN 1 THEN 95.00
        WHEN 2 THEN 55.00
    END,
    CASE
        WHEN s < 12 THEN 'sold'
        WHEN s < 15 THEN 'reserved'
        ELSE 'available'
    END
FROM events e
CROSS JOIN generate_series(0, 19) AS s;

-- Some orders
INSERT INTO orders (customer_email, customer_name, total, status, ordered_at) VALUES
('alice@example.com', 'Alice Johnson', 245.00, 'confirmed', '2026-04-01 14:30:00-04'),
('bob@example.com', 'Bob Smith', 150.00, 'confirmed', '2026-04-02 09:15:00-04'),
('carol@example.com', 'Carol Williams', 190.00, 'confirmed', '2026-04-03 16:45:00-04'),
('dave@example.com', 'Dave Brown', 55.00, 'pending', '2026-04-04 11:00:00-04'),
('eve@example.com', 'Eve Davis', 300.00, 'confirmed', '2026-04-05 20:00:00-04');

-- Order items (linking orders to specific sold tickets)
INSERT INTO order_items (order_id, ticket_id, price_at_purchase) VALUES
(1, 1, 150.00),   -- Alice bought a floor ticket to Aurora Flux at MSG
(1, 2, 95.00),    -- Alice bought a lower bowl ticket too
(2, 3, 150.00),   -- Bob bought a floor ticket to Aurora Flux at MSG
(3, 21, 95.00),   -- Carol bought a lower bowl ticket to Midnight Riders
(3, 22, 95.00),   -- Carol bought another lower bowl ticket
(4, 41, 55.00),   -- Dave bought an upper bowl ticket to Jazz at Fillmore
(5, 4, 150.00),   -- Eve bought floor tickets to Aurora Flux at MSG
(5, 5, 150.00);   -- Eve bought another floor ticket
```

Verify the data loaded:

```sql
-- Quick row counts
SELECT 'venues' AS table_name, COUNT(*) FROM venues
UNION ALL SELECT 'artists', COUNT(*) FROM artists
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'tickets', COUNT(*) FROM tickets
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items;
```

You should see: 5 venues, 5 artists, 6 events, 120 tickets, 5 orders, 8 order items.

---

## Part 5: Queries and JOINs (20 min)

Now the fun part. Let's query this data.

### Basic Queries

```sql
-- All events, ordered by date
SELECT name, event_date, status FROM events ORDER BY event_date;

-- Events that are on sale
SELECT name, event_date FROM events WHERE status = 'on_sale';

-- Venues in California
SELECT name, city FROM venues WHERE state = 'CA';

-- Tickets under $100
SELECT id, section, price, status FROM tickets WHERE price < 100 ORDER BY price;
```

### 🔍 Try It Now: Your First JOIN

A JOIN combines rows from two or more tables based on a related column. Here's the big one:

**"List all events with their venue names"**

```sql
SELECT e.name AS event_name,
       v.name AS venue_name,
       v.city,
       e.event_date
FROM events e
JOIN venues v ON e.venue_id = v.id
ORDER BY e.event_date;
```

The `JOIN ... ON` clause tells Postgres how the tables connect. The alias `e` for events and `v` for venues keeps things readable.

### Multi-Table JOINs

**"List all events at Madison Square Garden with ticket counts and revenue"**

```sql
SELECT e.name AS event_name,
       e.event_date,
       COUNT(t.id) AS total_tickets,
       COUNT(t.id) FILTER (WHERE t.status = 'sold') AS tickets_sold,
       COUNT(t.id) FILTER (WHERE t.status = 'available') AS tickets_available,
       SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
FROM events e
JOIN venues v ON e.venue_id = v.id
JOIN tickets t ON t.event_id = e.id
WHERE v.name = 'Madison Square Garden'
GROUP BY e.id, e.name, e.event_date
ORDER BY e.event_date;
```

### 🛠️ Your Turn

Write queries for these questions. Try each one before looking at the answer.

**Q1: "Which artists are playing at events with more than 5 available tickets?"**

<details>
<summary>💡 Hint 1: Direction</summary>
You need to walk the chain: artists -> event_artists -> events -> tickets. That means JOINing four tables. Start by writing the FROM clause with all the JOINs before thinking about filtering.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Filter tickets with WHERE t.status = 'available', then GROUP BY artist and event name. The "more than 5" part is a HAVING clause — HAVING COUNT(t.id) > 5 — because you are filtering on an aggregate, not on individual rows.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use DISTINCT on the artist name if an artist could appear multiple times. The JOIN path is: artists a JOIN event_artists ea ON a.id = ea.artist_id JOIN events e ON ea.event_id = e.id JOIN tickets t ON t.event_id = e.id.
</details>

<details>
<summary>Solution</summary>

```sql
SELECT DISTINCT a.name AS artist_name, e.name AS event_name
FROM artists a
JOIN event_artists ea ON a.id = ea.artist_id
JOIN events e ON ea.event_id = e.id
JOIN tickets t ON t.event_id = e.id
WHERE t.status = 'available'
GROUP BY a.name, e.name
HAVING COUNT(t.id) > 5;
```

</details>

**Q2: "List all orders with the customer name, number of tickets, and total paid"**

<details>
<summary>💡 Hint 1: Direction</summary>
You only need two tables here: orders and order_items. JOIN them on oi.order_id = o.id. The customer name lives in the orders table.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use COUNT(oi.id) for the number of tickets and SUM(oi.price_at_purchase) for the total paid. GROUP BY the order columns — o.id, o.customer_name, o.ordered_at, o.status.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Add ORDER BY o.ordered_at to show orders chronologically. Remember to include every non-aggregated column in your GROUP BY clause, or Postgres will complain.
</details>

<details>
<summary>Solution</summary>

```sql
SELECT o.customer_name,
       o.ordered_at,
       COUNT(oi.id) AS tickets_bought,
       SUM(oi.price_at_purchase) AS total_paid,
       o.status
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.customer_name, o.ordered_at, o.status
ORDER BY o.ordered_at;
```

</details>

**Q3: "For each venue, show the total number of events and the average ticket price"**

<details>
<summary>💡 Hint 1: Direction</summary>
Use LEFT JOIN (not INNER JOIN) from venues to events and then to tickets. A LEFT JOIN ensures venues with zero events still appear in the results instead of being silently dropped.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Count events with COUNT(DISTINCT e.id) — not COUNT(e.id) — because each event has many tickets, so e.id repeats. For average ticket price, use ROUND(AVG(t.price), 2) to get a clean two-decimal result.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
GROUP BY v.id, v.name, v.city and ORDER BY num_events DESC. Venues with no events will show 0 events and NULL for the average price — that is the correct behavior with LEFT JOIN.
</details>

<details>
<summary>Solution</summary>

```sql
SELECT v.name AS venue,
       v.city,
       COUNT(DISTINCT e.id) AS num_events,
       ROUND(AVG(t.price), 2) AS avg_ticket_price
FROM venues v
LEFT JOIN events e ON e.venue_id = v.id
LEFT JOIN tickets t ON t.event_id = e.id
GROUP BY v.id, v.name, v.city
ORDER BY num_events DESC;
```

Note the `LEFT JOIN` — this ensures venues with no events still appear (with 0 events and NULL avg price).

</details>

### LEFT JOIN vs INNER JOIN

```sql
-- INNER JOIN: only rows with matches in BOTH tables
SELECT v.name, e.name
FROM venues v
JOIN events e ON e.venue_id = v.id;
-- Result: only venues that have events

-- LEFT JOIN: all rows from left table, NULLs where no match
SELECT v.name, e.name
FROM venues v
LEFT JOIN events e ON e.venue_id = v.id;
-- Result: ALL venues, even those with no events (e.name will be NULL)
```

### 🤔 Reflect

When should you use LEFT JOIN vs INNER JOIN? Think about it:
- Use `INNER JOIN` when you only want rows where the relationship exists
- Use `LEFT JOIN` when you want all rows from the left table regardless

A common mistake is using `INNER JOIN` for a report and wondering why some rows are missing.

---

## Part 6: Schema Diagram (5 min)

Here's the complete TicketPulse schema as a text diagram:

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   venues     │     │     events       │     │   artists    │
├──────────────┤     ├──────────────────┤     ├──────────────┤
│ id        PK │◄────│ venue_id      FK │     │ id        PK │
│ name         │     │ id            PK │────►│              │
│ city         │     │ name             │     │ name         │
│ state        │     │ event_date       │     │ genre        │
│ capacity     │     │ description      │     │ bio          │
│ address      │     │ status           │     └──────────────┘
└──────────────┘     └──────────────────┘            │
                            │    │                    │
                            │    │         ┌──────────────────┐
                            │    │         │  event_artists   │
                            │    └────────►├──────────────────┤
                            │              │ event_id   PK,FK │
                            │              │ artist_id  PK,FK │
                            │              │ is_headliner     │
                            │              └──────────────────┘
                            │
                     ┌──────────────┐
                     │   tickets    │
                     ├──────────────┤
                     │ id        PK │
                     │ event_id  FK │
                     │ section      │
                     │ row          │
                     │ seat         │
                     │ price        │
                     │ status       │
                     └──────┬───────┘
                            │
                     ┌──────────────────┐     ┌──────────────┐
                     │  order_items     │     │   orders     │
                     ├──────────────────┤     ├──────────────┤
                     │ id            PK │     │ id        PK │
                     │ order_id      FK │────►│              │
                     │ ticket_id     FK │     │ customer_email│
                     │ price_at_purchase│     │ customer_name│
                     └──────────────────┘     │ total        │
                                              │ status       │
                                              │ ordered_at   │
                                              └──────────────┘
```

### 🔍 Try It: Browser-Based Practice

Want to practice these queries without Docker? Load the schema and data at **https://www.db-fiddle.com/**:

1. Go to db-fiddle.com
2. Select PostgreSQL 16 from the dropdown
3. Paste the CREATE TABLE statements in the left panel
4. Paste the INSERT statements in the left panel below the schema
5. Write queries in the right panel

This gives you a scratchpad to experiment with SQL freely.

---


> **What did you notice?** Look back at what you just built. What surprised you? What felt harder than expected? That's where the real learning happened.

## 🏁 Module Summary

In this module you:

- **Started PostgreSQL** in Docker and connected via `psql`
- **Designed a relational schema** from business requirements (7 tables with proper relationships)
- **Used appropriate data types** — `BIGSERIAL`, `NUMERIC` for money, `TIMESTAMPTZ` for dates, `CHECK` constraints for validation
- **Inserted realistic sample data** using `INSERT` and `generate_series`
- **Wrote JOIN queries** — INNER JOIN, LEFT JOIN, multi-table JOINs with GROUP BY and FILTER
- **Understood the TicketPulse data model** that we'll use for the rest of the course

Key commands to remember:
| Command | What it does |
|---------|-------------|
| `\dt` | List tables |
| `\d tablename` | Describe a table's structure |
| `\l` | List databases |
| `\q` | Quit psql |
| `\x` | Toggle expanded display (useful for wide rows) |

## What's Next

In **L1-M06: SQL That Actually Matters**, you'll learn the SQL patterns that senior engineers use daily — CTEs, window functions, and real analytics queries against the TicketPulse data you just created.

## Key Terms

| Term | Definition |
|------|-----------|
| **Schema** | A namespace within a PostgreSQL database that organizes tables, views, and other objects. |
| **Table** | A structured collection of rows and columns that stores data in a relational database. |
| **Column** | A named attribute of a table that holds values of a specific data type for each row. |
| **Primary key** | A column (or set of columns) that uniquely identifies each row in a table. |
| **Foreign key** | A column that references the primary key of another table, establishing a relationship between them. |
| **JOIN** | An SQL operation that combines rows from two or more tables based on a related column. |

## 📚 Further Reading
- [PostgreSQL Official Tutorial](https://www.postgresql.org/docs/current/tutorial.html)
- [Use The Index, Luke — SQL Indexing and Tuning](https://use-the-index-luke.com/)
- Chapter 2 of the 100x Engineer Guide: Data Engineering Paradigms
- Chapter 24 of the 100x Engineer Guide: Database Internals (Section 1 — PostgreSQL Internals)

# PostgreSQL From Zero

Every production application you will ever work on stores data. PostgreSQL is the default choice for serious workloads — it powers Instagram, Stripe, Discord, and thousands of startups. If you understand Postgres deeply, you can work with any relational database.

## What Is a Relational Database?

Think of a spreadsheet, but with superpowers. Each sheet is a **table**. Each column has a specific type (text, number, date). Each row is a record. The "relational" part means tables can reference each other — an event row points to a venue row, a ticket row points to an event row. These connections (foreign keys) are enforced by the database itself, so you can never have a ticket pointing to a venue that does not exist.

## Why PostgreSQL?

PostgreSQL is the Swiss Army knife of databases. It handles:
- Structured data with ACID transactions (your money is safe)
- JSON documents (when you need flexibility)
- Full-text search (when you need to find things)
- Geospatial queries (when location matters)
- Time-series data (when you need trends)

> **The bigger picture:** PostgreSQL is not the only game in town. MySQL is simpler and faster for basic workloads. SQLite is perfect for embedded/local use. CockroachDB and YugabyteDB add distributed capabilities on top of the Postgres wire protocol. We use Postgres because it is the most capable general-purpose database, and skills transfer directly to its derivatives.

## How Relational Schemas Work

A schema is a blueprint for your data. You define:

1. **Tables** — what entities exist (venues, events, tickets)
2. **Columns** — what attributes each entity has (name, date, price)
3. **Types** — what kind of data each column holds (VARCHAR, INTEGER, TIMESTAMPTZ)
4. **Constraints** — what rules the data must follow (NOT NULL, CHECK, UNIQUE)
5. **Relationships** — how tables connect (FOREIGN KEY)

### The TicketPulse Data Model

TicketPulse needs to track venues, artists, events, tickets, orders, and order items. The relationships:

```
venues ──< events ──< tickets ──< order_items >── orders
                 \
                  ── event_artists ── artists
```

- A venue has many events (one-to-many)
- An event has many tickets (one-to-many)
- An event can have many artists, and vice versa (many-to-many → junction table)
- An order has many order items (one-to-many)

### Design Decisions That Matter

| Decision | Why |
|----------|-----|
| `BIGSERIAL` for IDs | 64-bit auto-increment. Handles billions of rows. |
| `NUMERIC(10,2)` for prices | Exact decimal math. Never use FLOAT for money. |
| `TIMESTAMPTZ` not `TIMESTAMP` | Always store timezone. Without it, you'll get burned by DST. |
| `CHECK` constraints | Database-level validation. Even buggy app code cannot insert invalid data. |
| `price_at_purchase` in order_items | Captures the price at sale time. Historical orders stay accurate if prices change. |

## Key Takeaways

- PostgreSQL is the go-to relational database for production workloads
- Design your schema from business requirements before writing any SQL
- Use appropriate types (NUMERIC for money, TIMESTAMPTZ for dates, BIGSERIAL for IDs)
- Constraints (NOT NULL, CHECK, FOREIGN KEY) are your safety net against bad data
- Many-to-many relationships require a junction table
- `psql` meta-commands (`\dt`, `\d`, `\l`) are your best friends for exploring a database

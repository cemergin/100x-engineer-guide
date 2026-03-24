# L2-M38: Connection Pooling
> ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M37
> Source: Chapter 24 of the 100x Engineer Guide

## What You'll Learn
- Why each PostgreSQL connection is expensive (process model, memory overhead)
- How to reproduce and diagnose connection exhaustion
- How to deploy PgBouncer in front of TicketPulse's Postgres
- The difference between session, transaction, and statement pooling modes
- The connection pool sizing formula and why more connections is worse
- How to handle connection pooling in serverless environments

## Why This Matters
TicketPulse is now split into microservices — ticket service, order service, user service, event service. Each service opens its own database connections. Each connection to PostgreSQL spawns a dedicated OS process consuming ~5-10 MB of RAM. With 5 services, each running 4 replicas, each opening 20 connections... you're already at 400 connections. Postgres's default limit is 100. Your services crash with `FATAL: too many connections for role "ticketpulse"`, and no one can buy tickets.

## Prereq Check

Ensure your TicketPulse microservices stack is running:

```bash
docker compose ps
# You should see: ticket-service, order-service, event-service, user-service, postgres
```

---

## Part 1: The Problem — Connection Exhaustion (15 min)

### Why Postgres Connections Are Expensive

Unlike MySQL (which uses threads), PostgreSQL forks a **separate OS process** for every client connection. Each process:
- Consumes ~5-10 MB of RAM just for the connection overhead
- Has its own `work_mem` allocation for sorts and hashes
- Competes for CPU scheduling with every other connection process
- Holds file descriptors, locks, and shared memory references

### The Math

```
5 microservices × 4 replicas × 20 connections each = 400 connections

400 connections × 10 MB = 4 GB just for connection overhead
400 connections × 64 MB work_mem × 2 sorts per query = 51 GB worst-case memory for sorts!
```

And that's before counting the actual data in shared_buffers.

### 🐛 Debug: Reproduce Connection Exhaustion

Let's see this fail in real time. First, set a low connection limit:

```sql
-- Connect to Postgres as superuser
docker exec -it ticketpulse-postgres psql -U postgres

-- Check current setting
SHOW max_connections;
-- Default is 100

-- Set it low for demonstration
ALTER SYSTEM SET max_connections = 20;

-- Restart Postgres for the change to take effect
-- (In docker compose, restart the postgres container)
```

```bash
# Restart postgres container
docker compose restart postgres

# Wait for it to come up
docker compose logs postgres --tail 10
```

Now simulate load:

```bash
# Hit TicketPulse with 50 concurrent requests
# (Using a simple bash loop — in production you'd use k6, wrk, or similar)
for i in $(seq 1 50); do
    curl -s http://localhost:3000/api/events &
done
wait
```

Check the service logs:

```bash
docker compose logs ticket-service --tail 20
```

You should see errors like:
```
FATAL: too many connections for role "ticketpulse"
FATAL: sorry, too many clients already
Error: Connection terminated unexpectedly
```

### 📊 Observe: Current Connection Usage

```sql
-- Connect as superuser (reserved connections)
docker exec -it ticketpulse-postgres psql -U postgres

-- See all connections
SELECT datname, usename, application_name, state, count(*)
FROM pg_stat_activity
GROUP BY datname, usename, application_name, state
ORDER BY count(*) DESC;

-- How many connections are available?
SELECT max_conn, used, res_for_super,
       max_conn - used - res_for_super AS available
FROM
    (SELECT count(*) used FROM pg_stat_activity) t1,
    (SELECT setting::int max_conn FROM pg_settings WHERE name = 'max_connections') t2,
    (SELECT setting::int res_for_super FROM pg_settings WHERE name = 'superuser_reserved_connections') t3;
```

### The Insight

Most of those connections are **idle**. The service opened them but isn't actively using them. This is the core problem: services hoard connections "just in case," and Postgres has to maintain a process for each one, even when they're doing nothing.

---

## Part 2: PgBouncer to the Rescue (20 min)

### What PgBouncer Does

PgBouncer sits between your application and Postgres, multiplexing many client connections onto a small pool of actual database connections:

```
TicketPulse Services               PgBouncer              PostgreSQL
┌─────────────────┐           ┌──────────────┐      ┌─────────────┐
│ ticket-service   │──(50)──┐ │              │      │             │
│ order-service    │──(50)──┤ │  Pool of 20  │──20──│ max_conn=30 │
│ event-service    │──(50)──┤ │  connections  │      │             │
│ user-service     │──(50)──┘ │              │      │             │
└─────────────────┘           └──────────────┘      └─────────────┘
       200 clients                                     20 actual connections
```

### 🛠️ Build: Add PgBouncer to Docker Compose

Add PgBouncer to your `docker-compose.yml`:

```yaml
  pgbouncer:
    image: edoburu/pgbouncer:latest
    environment:
      DATABASE_URL: "postgres://ticketpulse:ticketpulse@postgres:5432/tickets"
      POOL_MODE: transaction
      DEFAULT_POOL_SIZE: 20
      MAX_CLIENT_CONN: 500
      RESERVE_POOL_SIZE: 5
      RESERVE_POOL_TIMEOUT: 3
      SERVER_RESET_QUERY: "DISCARD ALL"
      AUTH_TYPE: plain
    ports:
      - "6432:6432"
    depends_on:
      - postgres
```

Alternatively, create a dedicated PgBouncer config. Add a file `pgbouncer/pgbouncer.ini`:

```ini
[databases]
tickets = host=postgres port=5432 dbname=tickets
orders = host=postgres port=5432 dbname=orders
users = host=postgres port=5432 dbname=users
events = host=postgres port=5432 dbname=events

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = plain
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
default_pool_size = 20
max_client_conn = 500
reserve_pool_size = 5
reserve_pool_timeout = 3

# Clean up session state when returning connections to the pool
server_reset_query = DISCARD ALL

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1

# Timeouts
server_connect_timeout = 15
server_idle_timeout = 600
client_idle_timeout = 0
```

And `pgbouncer/userlist.txt`:
```
"ticketpulse" "ticketpulse"
```

### 🛠️ Build: Point Services at PgBouncer

Update your service environment variables to connect through PgBouncer instead of directly to Postgres:

```yaml
# Before (direct to Postgres):
  ticket-service:
    environment:
      DATABASE_URL: "postgres://ticketpulse:ticketpulse@postgres:5432/tickets"

# After (through PgBouncer):
  ticket-service:
    environment:
      DATABASE_URL: "postgres://ticketpulse:ticketpulse@pgbouncer:6432/tickets"
```

Do this for ALL services. Then restart:

```bash
docker compose up -d
```

### 🔍 Try It: Same Load Test, No Errors

```bash
# Reset max_connections back to 30 (low, but PgBouncer handles the multiplexing)
docker exec -it ticketpulse-postgres psql -U postgres -c "ALTER SYSTEM SET max_connections = 30;"
docker compose restart postgres

# Wait for it to come up, then hit it with 50 concurrent requests
for i in $(seq 1 50); do
    curl -s http://localhost:3000/api/events &
done
wait

# Check logs — no connection errors!
docker compose logs ticket-service --tail 20
```

### 📊 Observe: PgBouncer Stats

Connect to PgBouncer's admin console:

```bash
# PgBouncer's admin interface is accessible via psql
docker exec -it ticketpulse-pgbouncer psql -U ticketpulse -p 6432 pgbouncer
```

```sql
-- See pool status
SHOW POOLS;
-- Columns: database, user, cl_active, cl_waiting, sv_active, sv_idle, pool_mode
-- cl_active: client connections actively using a server connection
-- cl_waiting: clients waiting for a server connection
-- sv_active: server connections executing a query
-- sv_idle: server connections idle in the pool

-- See overall stats
SHOW STATS;
-- total_xact_count: total transactions processed
-- total_query_count: total queries processed
-- avg_xact_time: average transaction duration

-- See individual connections
SHOW CLIENTS;
SHOW SERVERS;
```

Watch the key ratio: you might see 50+ client connections but only 20 server connections. That's the multiplexing in action.

---

## Part 3: Pool Sizing and Pooling Modes (15 min)

### The Pool Sizing Formula

Counterintuitively, more database connections does NOT mean more throughput. The formula from the PostgreSQL wiki:

```
connections = (number_of_cores * 2) + number_of_spindle_disks
```

For an 8-core server with SSD: `(8 * 2) + 1 = 17` connections. Yes, 17.

Why? Beyond the optimal number:
- **CPU contention**: More connections = more context switching between processes
- **Lock contention**: More concurrent writers = more lock waits
- **Disk contention**: More concurrent queries = more random I/O if working set exceeds cache
- **Shared memory overhead**: Each connection holds buffers, locks, snapshot data

### 🔍 Try It: Prove That More Connections Isn't Better

If you have a load testing tool available (k6, wrk, pgbench):

```bash
# Test with 5 connections
pgbench -c 5 -j 2 -T 30 -h localhost -p 6432 -U ticketpulse tickets

# Test with 20 connections
pgbench -c 20 -j 4 -T 30 -h localhost -p 6432 -U ticketpulse tickets

# Test with 100 connections
pgbench -c 100 -j 8 -T 30 -h localhost -p 6432 -U ticketpulse tickets
```

You'll typically see: throughput (TPS) increases from 5 to 20 connections, then **plateaus or decreases** from 20 to 100. More connections past the sweet spot actually hurts performance.

### Pooling Modes: Which One?

| Mode | How It Works | Server Connection Returned... | Use Case |
|------|-------------|------|---------|
| **Session** | One client = one server connection for the entire session | When client disconnects | Long-lived connections, prepared statements |
| **Transaction** | Server connection assigned per transaction | After each COMMIT/ROLLBACK | Most web applications (recommended) |
| **Statement** | Server connection assigned per statement | After each statement | Autocommit-only workloads |

**For TicketPulse, use transaction pooling.** Here's why:

- A typical API request: BEGIN -> SELECT -> UPDATE -> COMMIT (takes 5ms)
- Between requests, the connection sits idle for 100ms-10s
- Transaction pooling lets other clients use the server connection during that idle time

### ⚠️ Common Mistake: Prepared Statements + Transaction Pooling

Prepared statements are **session-scoped** in PostgreSQL. When PgBouncer reassigns a server connection to a new client, that client's prepared statements don't exist on the new server connection.

```
Client A prepares "get_ticket" on server connection 1
Client A finishes transaction, server connection 1 returns to pool
Client B gets server connection 1
Client A starts new transaction, gets server connection 2
Client A tries to execute "get_ticket" — ERROR: prepared statement does not exist
```

Solutions:
1. **`server_reset_query = DISCARD ALL`** in PgBouncer config (runs on every connection return — slight overhead)
2. Use **PgBouncer 1.21+** which has transparent prepared statement support
3. Disable prepared statements in your ORM/driver:
   ```javascript
   // node-postgres
   const pool = new Pool({ ...config, statement_timeout: 0 });

   // Prisma
   // In connection string: ?pgbouncer=true
   datasource db {
     url = "postgres://...@pgbouncer:6432/tickets?pgbouncer=true"
   }
   ```

### Serverless Connection Challenges

TicketPulse might run on serverless (Lambda, Vercel Functions). Each invocation potentially opens a new connection:

```
100 concurrent Lambda invocations → 100 new Postgres connections → connection explosion
```

**Solutions (choose one):**

| Solution | Pros | Cons |
|----------|------|------|
| **AWS RDS Proxy** | Managed, handles failover, IAM auth | AWS-only, adds latency (~1ms), costs money |
| **Self-hosted PgBouncer** | Full control, cheap | You manage it, single point of failure |
| **Neon Serverless Driver** | HTTP-based, no persistent connections | Neon-only |
| **Supabase Supavisor** | Managed PgBouncer built into Supabase | Supabase-only |

For TicketPulse on AWS:
```
Lambda → RDS Proxy → PostgreSQL
```

For TicketPulse on Vercel:
```
Edge Function → PgBouncer (on a small VPS) → PostgreSQL
```

---

## Part 4: Monitoring and Troubleshooting (10 min)

### Key Metrics to Watch

```sql
-- PgBouncer: are clients waiting for connections?
SHOW POOLS;
-- If cl_waiting > 0 consistently, increase default_pool_size (but don't exceed the formula above)

-- Postgres: connection usage
SELECT count(*) AS total_connections,
       count(*) FILTER (WHERE state = 'active') AS active,
       count(*) FILTER (WHERE state = 'idle') AS idle,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn
FROM pg_stat_activity
WHERE backend_type = 'client backend';
```

### 🐛 Debug Checklist: "Too Many Connections"

When you see connection errors, work through this:

1. **Check `pg_stat_activity`** — who is consuming connections?
2. **Look for `idle in transaction`** — these hold connections without doing work. Set `idle_in_transaction_session_timeout`.
3. **Look for connection leaks** — application code that opens connections but doesn't close them.
4. **Check pool configuration** — is `default_pool_size` appropriate? Is `max_client_conn` too low?
5. **Check if services are pooling locally** — if your app already has a connection pool (e.g., HikariCP, node-pg pool), reduce its size. Let PgBouncer do the multiplexing.

### ⚠️ Common Mistake: Double Pooling

```
App pool (20 connections per instance)
    × 10 instances = 200 connections to PgBouncer
PgBouncer pool (20 connections)
    → 20 connections to Postgres
```

The app pool is wasteful — it's holding connections to PgBouncer (cheap) but preventing PgBouncer from efficiently sharing its server connections. Set the app pool to a **small number** (2-5 per instance) and let PgBouncer handle the rest.

---

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Postgres connections** | Each connection = an OS process. Default limit is 100. Memory-expensive. |
| **PgBouncer** | Multiplexes hundreds of client connections onto a small server pool. Essential for microservices. |
| **Transaction pooling** | Best mode for web apps. Connection returned after each COMMIT. |
| **Pool sizing** | `(cores * 2) + spindles`. More connections ≠ more throughput. |
| **Prepared statements** | Don't work with transaction pooling by default. Use `pgbouncer=true` in your connection string. |
| **Serverless** | Use RDS Proxy or a managed pooler. Every invocation opening a direct connection will fail at scale. |
| **Double pooling** | If you have PgBouncer, reduce your application-level pool size. |

## What's Next

In **L2-M39: Advanced SQL for Analytics**, you'll build a TicketPulse analytics dashboard using window functions, CTEs, LATERAL JOINs, and materialized views — SQL that separates juniors from seniors.

## 📚 Further Reading
- [PgBouncer Documentation](https://www.pgbouncer.org/config.html)
- Chapter 24 of the 100x Engineer Guide: Section 5 — Connection Management
- [Why More Database Connections = Slower](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [Supabase: Connection Pooling Explained](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pool)

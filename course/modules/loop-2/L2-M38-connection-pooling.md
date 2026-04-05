# L2-M38: Connection Pooling

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M37
>
> **Source:** Chapter 24 of the 100x Engineer Guide

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

## Part 5: PgBouncer Configuration Deep Dive (20 min)

Getting PgBouncer running is step one. Tuning it for production requires understanding what each configuration parameter does and how to measure whether your settings are correct.

### The Full Parameter Reference with Reasoning

```ini
[pgbouncer]
# ─── Networking ───────────────────────────────────────────────────────
listen_addr = 0.0.0.0
listen_port = 6432

# ─── Pool core ────────────────────────────────────────────────────────
pool_mode = transaction         # transaction | session | statement
                                # transaction: best for web apps
                                # session: required for prepared statements
                                # statement: for autocommit-only workloads

default_pool_size = 20          # Server connections PER USER PER DATABASE
                                # Formula: (DB_cores * 2) + spindles
                                # 4-core RDS: (4*2) + 1 = 9; round to 10
                                # 8-core RDS: (8*2) + 1 = 17; round to 20

max_client_conn = 1000          # Total client connections PgBouncer accepts
                                # Set high — client connections are cheap
                                # Rule of thumb: 10x your default_pool_size

min_pool_size = 0               # Server connections kept alive when idle
                                # Set to 2-5 to reduce first-query latency

reserve_pool_size = 5           # Extra server connections for when pool is full
                                # Clients wait up to reserve_pool_timeout seconds
reserve_pool_timeout = 3        # Seconds to wait before using reserve pool

max_db_connections = 0          # Hard cap across ALL users for a database
                                # 0 = no limit; useful in multi-tenant setups

# ─── Timeouts ─────────────────────────────────────────────────────────
server_connect_timeout = 15     # Max seconds to wait for a server connection
server_idle_timeout = 600       # Close idle server connections after 10 minutes
client_idle_timeout = 0         # Close idle client connections (0 = never)
query_timeout = 0               # Max query duration (0 = no limit)
                                # Set to 30s in production to kill runaway queries
transaction_timeout = 0         # Max transaction duration (0 = no limit)
                                # Set to 60s to prevent "idle in transaction" locks

# ─── Session management ────────────────────────────────────────────────
server_reset_query = DISCARD ALL  # Run when server connection is returned to pool
                                   # DISCARD ALL clears: prepared statements,
                                   # advisory locks, session-level GUC settings,
                                   # temp tables, and notification listeners
                                   # Adds ~1ms per checkout but prevents state leaks

# ─── Observability ────────────────────────────────────────────────────
log_connections = 1             # Log each client connect/disconnect
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60               # Log pool stats every 60 seconds
```

### The Four Configuration Exercises

**Exercise 1: Size the pool for TicketPulse's production database**

Given:
- RDS instance: `db.r6g.2xlarge` (8 vCPUs, SSD storage)
- 5 microservices, each with 4 replicas
- Peak transaction rate: 200 transactions/second
- Average transaction duration: 15ms

Calculate:
1. Optimal server-side pool size using the formula
2. Maximum client connections needed
3. `reserve_pool_size` setting

```
Step 1: Pool size
formula = (cores * 2) + spindles
        = (8 * 2) + 1
        = 17 → round to 20

Step 2: Client connection headroom
5 services × 4 replicas × app_pool_size_per_instance = total clients
If we set app pool to 5 per instance:
  5 × 4 × 5 = 100 max_client_conn

Step 3: Check: can 20 server connections handle 200 TPS at 15ms?
  Throughput = pool_size / avg_transaction_time
             = 20 / 0.015s
             = 1,333 TPS ← well above 200 TPS; pool is appropriately sized

Step 4: Reserve pool
  During peak, add 5 reserve connections
  reserve_pool_size = 5
  reserve_pool_timeout = 3
```

**Exercise 2: Diagnose a misconfigured pool**

You are seeing these numbers in `SHOW POOLS`:

```
database  | user         | cl_active | cl_waiting | sv_active | sv_idle
----------+--------------+-----------+------------+-----------+--------
tickets   | ticketpulse  | 15        | 12         | 20        | 0
```

What does `cl_waiting = 12` mean? What should you change?

```
Analysis:
- 15 clients actively executing queries
- 12 clients waiting for a server connection
- 20 server connections, all in use (sv_idle = 0)
- The pool is saturated

Possible causes:
  A) default_pool_size is too small for the workload
  B) Long-running transactions are holding connections (check sv_active duration)
  C) A traffic spike is temporarily exceeding capacity

Diagnosis steps:
1. Check if this is sustained or momentary:
   SHOW POOLS; -- run again in 10 seconds. Is cl_waiting still high?

2. Check for long-running transactions:
   SELECT pid, duration, state, query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC;

If sustained:
  → Increase default_pool_size (but do not exceed DB capacity)
  → OR reduce query duration (optimize slow queries)

If caused by long transactions:
  → Set transaction_timeout in PgBouncer
  → Investigate and fix the slow queries
```

**Exercise 3: Configure PgBouncer for a multi-database setup**

TicketPulse runs separate databases per service. Configure PgBouncer to route each service to its own database while using a shared server pool:

```ini
[databases]
; Route each logical database to the physical host
; Syntax: logical_name = host=... port=... dbname=... pool_size=...

tickets = host=postgres port=5432 dbname=tickets pool_size=20
orders  = host=postgres port=5432 dbname=orders  pool_size=15
users   = host=postgres port=5432 dbname=users   pool_size=10
events  = host=postgres port=5432 dbname=events  pool_size=20

; Read-only connection to replica (for analytics queries)
tickets_ro = host=postgres-replica port=5432 dbname=tickets pool_size=30

[pgbouncer]
pool_mode = transaction
max_client_conn = 500
default_pool_size = 20
; default_pool_size applies when pool_size is not specified per-database
```

Services connect by using the logical database name:
```
ticket-service: postgres://user:pass@pgbouncer:6432/tickets
order-service:  postgres://user:pass@pgbouncer:6432/orders
analytics:      postgres://user:pass@pgbouncer:6432/tickets_ro  ← read replica
```

This single PgBouncer instance routes all services, maintains separate pools per database, and directs analytics to the replica without any application code changes.

**Exercise 4: Tune timeouts to prevent "idle in transaction" leaks**

"Idle in transaction" is the silent killer of connection pools. A query starts a transaction, the application crashes or hangs, and the connection is held open indefinitely — blocking other queries on those rows.

```sql
-- Check for idle in transaction connections
SELECT pid, duration::interval, state, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY duration DESC;

-- Kill one (careful in production)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
AND duration > interval '5 minutes';
```

PgBouncer settings to prevent accumulation:

```ini
; Kill transactions that have been running for more than 60 seconds
transaction_timeout = 60

; Kill server connections idle in a transaction for more than 30 seconds
idle_transaction_timeout = 30

; Also set this in PostgreSQL itself (belt and suspenders)
; In postgresql.conf or via ALTER SYSTEM:
; idle_in_transaction_session_timeout = '30s'
```

Set these in PgBouncer AND in PostgreSQL. If PgBouncer restarts, the PostgreSQL-level timeout still protects you.

---

## Part 6: Pool Sizing Math: The Full Derivation

The formula `(cores * 2) + spindles` is a rule of thumb. Here is the reasoning behind it, and how to validate it with your actual workload.

### Why CPU Cores Drive the Limit

A database query consumes one CPU core while executing. If you have 8 cores and 9 simultaneous queries, one query waits. With 8 connections, the theoretical maximum is 8 fully-utilized cores.

But queries are not 100% CPU-bound. They wait for disk I/O, lock releases, and network responses. During those waits, the CPU is free. This is why `cores * 2` is better than `cores` — a second batch of queries can run on the CPU while the first batch waits for I/O.

For SSDs, adding 1 for disk I/O is a slight correction. For spinning disks, you add the number of disk spindles because parallel disk seeks matter more.

### Measuring Your Actual Optimal Pool Size

The rule of thumb is a starting point. Validate it with pgbench:

```bash
# Install pgbench (included with PostgreSQL client)
# Initialize a test database
pgbench -i -s 50 -h localhost -p 6432 -U ticketpulse tickets
# -s 50: scale factor 50 (~5M rows)

# Benchmark with increasing connection counts
for clients in 1 5 10 20 30 50 80 100; do
  echo -n "Clients=$clients: "
  pgbench -c $clients -j $((clients / 2 + 1)) -T 30 \
    -h localhost -p 6432 -U ticketpulse tickets 2>&1 \
    | grep "tps ="
done
```

Expected output pattern:
```
Clients=1:   tps = 320 (excluding connections establishing)
Clients=5:   tps = 1,450
Clients=10:  tps = 2,200
Clients=20:  tps = 2,850    ← peak (sweet spot for 8-core DB)
Clients=30:  tps = 2,710    ← slight drop (contention starting)
Clients=50:  tps = 2,400    ← clear drop
Clients=80:  tps = 2,100    ← significant drop
Clients=100: tps = 1,900    ← worse than 20 connections
```

The peak TPS is your optimal pool size. In this example, 20 connections beats 100 connections by 50%.

Run this benchmark against your actual database instance type (RDS r6g.2xlarge has different characteristics than a local MacBook). The formula gives you a starting point; the benchmark confirms it.

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

## Key Terms

| Term | Definition |
|------|-----------|
| **Connection pool** | A cache of reusable database connections that avoids the overhead of opening a new connection per request. |
| **PgBouncer** | A lightweight connection pooler for PostgreSQL that sits between clients and the database server. |
| **Transaction pooling** | A PgBouncer mode where connections are returned to the pool after each transaction completes. |
| **Max connections** | The PostgreSQL configuration parameter that limits the total number of concurrent client connections. |
| **Connection overhead** | The CPU, memory, and time cost of establishing and tearing down a database connection. |

---

## Cross-References

- **Chapter 24** (Database Internals): The PostgreSQL process model, `pg_stat_activity`, and query planning are covered in depth. Connection pooling sits on top of the fundamentals explained there.
- **L2-M39** (Advanced SQL for Analytics): Many analytics queries are long-running and can monopolize connection pool slots. The connection pool tuning here directly affects analytics workload isolation.
- **L3-M61** (Multi-Region Design): Running PgBouncer in a multi-region setup requires regional poolers close to each app deployment, covered in the global infrastructure module.

---

## 📚 Further Reading
- [PgBouncer Documentation](https://www.pgbouncer.org/config.html)
- Chapter 24 of the 100x Engineer Guide: Section 5 — Connection Management
- [Why More Database Connections = Slower](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [Supabase: Connection Pooling Explained](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pool)

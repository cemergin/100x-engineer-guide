#!/usr/bin/env python3
"""Second pass: Add Kolb prompts and hints to modules M37-M60."""

import re
import os

LOOP2_DIR = "/Users/cemergin/nelo/100x-engineer-guide/course/modules/loop-2"

# Kolb prompts for remaining modules
KOLB_DATA = {
    "L2-M37": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** When you run `UPDATE tickets SET status = \'sold\' WHERE id = 42`, does PostgreSQL modify the row in place? Or does something more interesting happen under the hood? Write down your mental model before reading on.'),
        ],
        "reflection": ('## 🏁 Module Summary', '> **What did you notice?** Every UPDATE creates a dead tuple. For TicketPulse\'s high-churn tickets table, what does that mean for disk usage and query performance over time? How aggressive should autovacuum be?'),
    },
    "L2-M38": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** TicketPulse has 5 microservices, each with 4 replicas, each opening 20 database connections. How many total connections is that? Postgres defaults to max 100. Do you see the problem coming?'),
        ],
        "reflection": ('## 🏁 Module Summary', '> **What did you notice?** With PgBouncer, 200 client connections are multiplexed onto 20 server connections and throughput actually improved. Why does fewer database connections lead to better performance? What does this tell you about the relationship between concurrency and throughput?'),
    },
    "L2-M39": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** The product team wants a rolling 30-day revenue total per venue. Could you compute this with GROUP BY alone? What SQL feature lets you compute aggregates across a set of rows without collapsing them into a single row?'),
        ],
        "reflection": ('## 🏁 Module Summary', '> **What did you notice?** Compare the cohort retention query (4 CTEs building on each other) with how you would compute the same thing in application code. Which approach is more maintainable? Which pushes more work to where it belongs?'),
    },
    "L2-M40": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** If you run `SELECT * FROM events WHERE name ILIKE \'%jazz%\'` on 1 million rows, what kind of scan does the database perform? Why can a B-tree index not help with leading wildcards?'),
        ],
        "reflection": ('## 🏁 Module Summary', '> **What did you notice?** An inverted index turns a full-table scan into an O(1) lookup. But you now have two data stores to keep in sync. When is the operational overhead of Elasticsearch worth it versus Postgres tsvector?'),
    },
    "L2-M41": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** Your events page loads 100 events, each with a venue name and ticket count. How many database queries do you think the current code fires? Take a guess before enabling query logging.'),
        ],
        "reflection": ('## What\'s Next', '> **What did you notice?** The N+1 problem was invisible in the code — the ORM made each query look like a simple property access. How many N+1 problems might be hiding in your own codebases right now? What would you add to your development workflow to catch them early?'),
    },
    "L2-M42": {
        "predictions": [
            ('## Prereq Check', '> **Before you continue:** "Find friends of Alice who are attending the Taylor Swift concert, and also friends-of-friends attending." How many SQL JOINs would this require? What happens to query complexity as you add more hops?'),
        ],
        "reflection": ('## What\'s Next', '> **What did you notice?** The same "friends attending this event" query took 7 JOINs in SQL but a single traversal pattern in Cypher. But you now have two databases to operate. When does the query expressiveness of a graph database justify the operational complexity?'),
    },
    "L2-M43": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Docker Compose worked great for local development. What happens when you need to run TicketPulse across multiple machines, automatically restart crashed containers, and scale services up and down? What is missing from Docker Compose for production?'),
        ],
        "reflection": None,
    },
    "L2-M44": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You have been creating infrastructure by clicking in dashboards or running CLI commands. What happens when a teammate needs to recreate the same environment? What if you need to tear it all down and rebuild it? How would you make infrastructure reproducible?'),
        ],
        "reflection": None,
    },
    "L2-M44a": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Your Terraform code creates resources, but does it create *secure* resources? What kind of mistakes might slip through code review that an automated scanner could catch?'),
        ],
        "reflection": None,
    },
    "L2-M44b": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Application code has version control, code review, and CI/CD. How do your database schema changes currently get deployed? If something goes wrong with a schema migration, how do you roll back?'),
        ],
        "reflection": None,
    },
    "L2-M45": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Your services are running but you cannot see inside them. If TicketPulse slows down right now, how would you know which service is the bottleneck? What metrics would help you answer that question?'),
        ],
        "reflection": None,
    },
    "L2-M46": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** A request to purchase a ticket flows through the gateway, monolith, payment service, and notification service. If total latency is 800ms, how do you figure out which service is responsible for most of that time? Correlation IDs help with log searching, but can they show you a timeline?'),
        ],
        "reflection": None,
    },
    "L2-M47": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You have monitoring dashboards with metrics and traces. But dashboards only help if someone is looking at them. How do you turn passive observation into active notification when something goes wrong at 3am?'),
        ],
        "reflection": None,
    },
    "L2-M48": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You built circuit breakers, retries, and health checks. But have you actually tested whether they work under real failure conditions? How would you prove that TicketPulse survives a database crash or a network partition?'),
        ],
        "reflection": None,
    },
    "L2-M49": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** In M31, you discovered that when the payment service goes down, the entire purchase flow fails. What if instead of failing immediately, the monolith could detect the failure, stop sending requests, and degrade gracefully? What pattern would enable this?'),
        ],
        "reflection": None,
    },
    "L2-M50": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** The API gateway has a simple rate limiter from M36. But what happens during a flash sale when 100,000 users hit the purchase endpoint simultaneously? How would you protect TicketPulse from being overwhelmed while still serving legitimate traffic fairly?'),
        ],
        "reflection": None,
    },
    "L2-M51": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** TicketPulse reads events for the homepage thousands of times per second but writes new events maybe once a day. Should the read path and write path use the same data model and infrastructure? What if you could optimize each independently?'),
        ],
        "reflection": None,
    },
    "L2-M51a": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** When you need to add new behavior to existing code, do you reach for class inheritance or function composition first? Think about a real example from your experience — which approach would have been simpler?'),
        ],
        "reflection": None,
    },
    "L2-M52": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** TicketPulse stores ticket sales in Postgres, search data in Elasticsearch, and events in Kafka. The analytics team wants all of this in a data warehouse for reporting. How would you move data from multiple operational systems into a single analytics store reliably?'),
        ],
        "reflection": None,
    },
    "L2-M53": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You have a risky new feature — a dynamic pricing algorithm for tickets. How would you deploy it to production without exposing it to all users at once? What if you wanted to test it with 5% of traffic first, then gradually increase?'),
        ],
        "reflection": None,
    },
    "L2-M54": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You need to rename a database column that three services depend on. If you deploy the schema change and the code change at the same time, there is a window where the old code runs against the new schema. How do you avoid that gap?'),
        ],
        "reflection": None,
    },
    "L2-M55": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** External partners want to be notified in real time when a TicketPulse event sells out. You could have them poll your API, but that is wasteful. What is the reverse pattern — where your system pushes data to theirs?'),
        ],
        "reflection": None,
    },
    "L2-M55a": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Your CI pipeline runs tests and deploys. But what if you needed to run tests across Node 18, 20, and 22? Or deploy to staging first, wait for approval, then deploy to production? How would you model that workflow?'),
        ],
        "reflection": None,
    },
    "L2-M56": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** TicketPulse uses JWT tokens from M31. But what if users want to log in with their Google account? Or what if an admin needs different permissions than a regular user? How would you extend the auth system to handle these requirements?'),
        ],
        "reflection": None,
    },
    "L2-M57": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Every HTTPS connection involves a "handshake" before any data is exchanged. What is being negotiated during that handshake? Why is it necessary? Try to sketch the steps before reading on.'),
        ],
        "reflection": None,
    },
    "L2-M58": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** A user reports that ticket purchases are intermittently slow. You cannot reproduce it locally. The service is running in production with real traffic. What tools and techniques do you have available to diagnose this without redeploying code?'),
        ],
        "reflection": None,
    },
    "L2-M59": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Think about the last design document or technical proposal you read. Was it easy to follow? Did it clearly state the problem, the proposed solution, and the alternatives considered? What made it effective or ineffective?'),
        ],
        "reflection": None,
    },
    "L2-M59a": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** Most APIs are built code-first: write the handler, then document it later (if ever). What if you wrote the API specification first and generated code, docs, and tests from it? What would that change about your development workflow?'),
        ],
        "reflection": None,
    },
    "L2-M60": {
        "predictions": [
            ('---\n\n## ', '> **Before you continue:** You have spent Loop 2 building microservices, databases, monitoring, resilience, and deployment infrastructure. Before starting this capstone, list the three areas where you feel most confident and the three where you feel least confident. This self-assessment will guide where you focus your effort.'),
        ],
        "reflection": None,
    },
}

# Hints for remaining modules with Build/Debug/Design exercises
HINTS_DATA = {
    "L2-M37": {
        "### 🛠️ Build: Create and Observe Bloat": """
<details>
<summary>💡 Hint 1: Direction</summary>
Check `pg_stat_user_tables` for `n_dead_tup` before and after a mass UPDATE. The dead tuple count should jump significantly.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run `UPDATE tickets SET updated_at = NOW() WHERE event_id BETWEEN 1 AND 10` to create dead tuples. Then query `n_live_tup` and `n_dead_tup` from `pg_stat_user_tables` to see the ratio.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Calculate `dead_pct` as `round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1)`. Also check `pg_total_relation_size('tickets')` — the table size grows with dead tuples even though the live data has not changed.
</details>""",
        "### 🛠️ Build: Run VACUUM and See the Difference": """
<details>
<summary>💡 Hint 1: Direction</summary>
Note the `n_dead_tup` count before running VACUUM. After `VACUUM tickets`, check again — it should drop to near zero.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
VACUUM marks dead tuple space as reusable in the Free Space Map but does NOT shrink the file on disk. To actually reclaim disk space, you would need `VACUUM FULL` (which locks the table).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
For TicketPulse's tickets table, tune autovacuum per-table: `ALTER TABLE tickets SET (autovacuum_vacuum_scale_factor = 0.01, autovacuum_vacuum_cost_delay = 0)`. This triggers vacuum at 1% dead tuples instead of the default 20%.
</details>""",
    },
    "L2-M38": {
        "### 🐛 Debug: Reproduce Connection Exhaustion": """
<details>
<summary>💡 Hint 1: Direction</summary>
Set `max_connections = 20` in Postgres, then fire 50 concurrent requests. Watch for `FATAL: too many connections` errors in the service logs.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Check `pg_stat_activity` to see all active connections grouped by `datname`, `usename`, and `state`. Most connections will be `idle` — hoarding connections they are not using.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The core insight: services hold connections "just in case" and Postgres maintains a process for each one. Query `pg_stat_activity` for the count of idle vs active connections. The ratio will show massive waste — most connections do nothing most of the time.
</details>""",
        "### 🛠️ Build: Add PgBouncer to Docker Compose": """
<details>
<summary>💡 Hint 1: Direction</summary>
PgBouncer sits between your services and Postgres, multiplexing many client connections onto a small pool. Key settings: `pool_mode = transaction`, `default_pool_size = 20`, `max_client_conn = 500`.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Add PgBouncer as a Docker Compose service with `DATABASE_URL` pointing to Postgres. Then change ALL service `DATABASE_URL` values to point to PgBouncer (port 6432) instead of Postgres (port 5432).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use `POOL_MODE: transaction` for web apps (connection returned after each COMMIT). Set `SERVER_RESET_QUERY: DISCARD ALL` to clean session state. After setup, run `SHOW POOLS` in PgBouncer's admin console to verify multiplexing is working.
</details>""",
        "### 🐛 Debug Checklist: \"Too Many Connections\"": """
<details>
<summary>💡 Hint 1: Direction</summary>
Start by checking `pg_stat_activity` to see who is consuming connections. Look specifically for `idle in transaction` states — these hold connections without doing work.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Check five things in order: (1) who is consuming connections, (2) idle-in-transaction sessions, (3) connection leaks in app code, (4) PgBouncer pool config, (5) app-level pool sizes (reduce to 2-5 per instance when using PgBouncer).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Set `idle_in_transaction_session_timeout = '5min'` in Postgres and `transaction_timeout = 60` in PgBouncer. Watch for "double pooling" — if your app has its own pool of 20 connections AND PgBouncer has a pool, the app pool is wasteful. Reduce app pool to 2-5 per instance.
</details>""",
    },
    "L2-M41": {
        "### 🐛 Debug: Enable Query Logging": """
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
</details>""",
        "### 🛠️ Build: Single Query with JOINs": """
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
</details>""",
        "### 🛠️ Build: Batch Loading": """
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
</details>""",
    },
    "L2-M42": {
        "### 🛠️ Build: Create the Graph Schema": """
<details>
<summary>💡 Hint 1: Direction</summary>
A graph schema defines node labels (User, Event, Artist) and relationship types (FRIENDS, ATTENDING, PERFORMED_AT). Nodes have properties; relationships can too.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create uniqueness constraints on node IDs first: `CREATE CONSTRAINT FOR (u:User) REQUIRE u.id IS UNIQUE`. This also creates an index for fast lookups.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use `MERGE` instead of `CREATE` when populating to avoid duplicates: `MERGE (u:User {id: 1}) SET u.name = 'Alice'`. Relationships use the same pattern: `MATCH (u1:User {id: 1}), (u2:User {id: 2}) MERGE (u1)-[:FRIENDS]-(u2)`.
</details>""",
        "### 📐 Design: TicketPulse's Hybrid Architecture": """
<details>
<summary>💡 Hint 1: Direction</summary>
Not everything belongs in the graph. CRUD operations (creating events, processing payments) stay in Postgres. Only relationship-heavy queries (recommendations, social features) use Neo4j.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Postgres is the source of truth. Neo4j is a read-optimized projection. Sync data from Postgres to Neo4j via Kafka CDC — when a user buys a ticket, a Kafka consumer creates the ATTENDING relationship in Neo4j.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The architecture is: Postgres (writes) -> Kafka CDC -> Neo4j consumer -> Neo4j (reads). The API checks Neo4j for "friends attending" and "recommendations" but calls Postgres for everything else. Accept eventual consistency — social features can be seconds behind.
</details>""",
    },
    "L2-M56": {
        "### 🛠️ Build: Implement the Full OAuth2 Flow": """
<details>
<summary>💡 Hint 1: Direction</summary>
OAuth2 authorization code flow has four steps: redirect to provider, user authorizes, provider redirects back with a code, your server exchanges the code for tokens.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create two endpoints: `GET /auth/google` (redirects to Google with client_id and redirect_uri) and `GET /auth/google/callback` (receives the authorization code, exchanges it for tokens, creates/finds the user, and issues your own JWT).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use the `state` parameter to prevent CSRF attacks — generate a random state, store it in the session, and verify it matches when the callback comes back. Exchange the code using a server-side POST to Google's token endpoint (never expose client_secret to the browser).
</details>""",
    },
    "L2-M57": {
        "### 🛠️ Build: Generate a Self-Signed Certificate": """
<details>
<summary>💡 Hint 1: Direction</summary>
Use `openssl` to generate a private key and a self-signed certificate. The key is the secret; the certificate is the public identity that clients verify.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run `openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes`. The `-nodes` flag means no password on the key (fine for development, never for production).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Inspect the certificate with `openssl x509 -in cert.pem -text -noout`. You should see the subject, issuer (same as subject for self-signed), validity dates, and the public key. Browsers will warn about self-signed certs — that is expected.
</details>""",
        "### 🛠️ Build: Configure HTTPS on the API Gateway": """
<details>
<summary>💡 Hint 1: Direction</summary>
The gateway terminates TLS — it decrypts HTTPS from clients and forwards plain HTTP to internal services. This is called TLS termination.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
In the Express gateway, use `https.createServer({ key: fs.readFileSync('key.pem'), cert: fs.readFileSync('cert.pem') }, app)`. Redirect HTTP to HTTPS with a middleware that checks `req.secure`.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Add security headers: `Strict-Transport-Security` (HSTS) tells browsers to always use HTTPS. Set `max-age=31536000; includeSubDomains`. In production, use Let's Encrypt with auto-renewal via certbot instead of self-signed certificates.
</details>""",
        "### 🛠️ Build: Set Up mTLS for TicketPulse Services": """
<details>
<summary>💡 Hint 1: Direction</summary>
Mutual TLS means both sides verify each other's certificate. The gateway verifies the service, AND the service verifies the gateway. This prevents unauthorized services from joining the mesh.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create a CA (Certificate Authority), then issue certificates for each service signed by that CA. Configure each service to require client certificates and verify them against the CA.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use `requestCert: true, rejectUnauthorized: true, ca: [caCert]` in the Node.js HTTPS server options. Each service presents its own cert and verifies the caller's cert was signed by the same CA. In production, a service mesh (Istio, Linkerd) handles mTLS automatically.
</details>""",
    },
    "L2-M58": {
        "### 🛠️ Build: Diagnose All Three Problems": """
<details>
<summary>💡 Hint 1: Direction</summary>
Use three different tools for three different problems: distributed tracing (Jaeger) for latency, log aggregation for errors, and metrics (Prometheus/Grafana) for resource exhaustion.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
For intermittent slowness, look at p99 latency in traces — the average may look fine while the 99th percentile is terrible. For errors, search logs by correlation ID to follow a request across services. For resource issues, check connection pool metrics and memory usage.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The three classic production problems: (1) a slow downstream dependency (visible in traces as one span taking 90% of total time), (2) a connection pool leak (visible in metrics as growing active connections that never decrease), (3) a memory leak (visible in metrics as monotonically increasing heap usage). Each requires a different tool to diagnose.
</details>""",
    },
    "L2-M59": {
        "### 🛠️ Build: Write an RFC for TicketPulse": """
<details>
<summary>💡 Hint 1: Direction</summary>
An RFC has a standard structure: problem statement, proposed solution, alternatives considered, and migration plan. Start with the problem — what is broken or missing, and why does it matter?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
The proposed solution should be specific enough to implement but not so detailed it reads like code. Include diagrams, API contracts, and data models. The "alternatives considered" section shows you thought broadly before narrowing.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The strongest RFCs have a clear "non-goals" section (what this proposal intentionally does NOT address), a rollback plan (how to undo it if it fails), and concrete success metrics (how will you know it worked). Write for a reader who has 15 minutes, not 2 hours.
</details>""",
        "### 🛠️ Build: Write the TicketPulse Purchase Failures Runbook": """
<details>
<summary>💡 Hint 1: Direction</summary>
A runbook is not documentation — it is a step-by-step procedure an on-call engineer follows at 3am when the alert fires. Every step must be copy-pasteable.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Structure: (1) symptoms and alert description, (2) immediate triage steps with exact commands, (3) common causes ranked by likelihood, (4) resolution steps for each cause, (5) escalation path if unresolved after 15 minutes.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Include exact shell commands, dashboard URLs, and log search queries. Never say "check the database" — say "run `SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction'` and if the result is > 10, run `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND duration > interval '5 minutes'`."
</details>""",
        "### 🛠️ Build: Write the Postmortem for the L2-M58 Incident": """
<details>
<summary>💡 Hint 1: Direction</summary>
A postmortem is blameless — it focuses on what happened, why, and how to prevent recurrence. Never name individuals as the cause.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Structure: (1) incident summary (one paragraph), (2) timeline with timestamps, (3) root cause analysis (the "5 whys"), (4) impact (users affected, revenue lost, SLA breached), (5) action items with owners and due dates.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The most valuable section is "what went well" alongside "what went wrong." Celebrate the things that worked (alerts fired correctly, runbook was followed, rollback was fast). Action items must be specific and assigned — "improve monitoring" is not an action item; "add alert for connection pool utilization > 80% (owner: Alice, due: March 15)" is.
</details>""",
    },
    "L2-M60": {
        "### 🐛 Debug: Find the First Bottleneck": """
<details>
<summary>💡 Hint 1: Direction</summary>
Start with the end-to-end latency measurement. Use distributed tracing to identify which service contributes the most time to the critical path.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run a load test with gradually increasing concurrency. Monitor response times, error rates, and resource utilization (CPU, memory, connections) across all services. The first service to degrade is your bottleneck.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Common bottlenecks in order of likelihood: (1) database connection pool exhaustion, (2) a slow SQL query that was not visible at low traffic, (3) a synchronous call to an external service without a timeout, (4) insufficient container CPU/memory limits in Kubernetes.
</details>""",
    },
}


def process_file(filepath):
    """Process a single file with Kolb prompts and hints."""
    filename = os.path.basename(filepath)
    match = re.match(r'(L2-M\d+[a-z]?)', filename)
    if not match:
        return
    module_id = match.group(1)

    with open(filepath, 'r') as f:
        content = f.read()

    original = content

    # Add Kolb prompts
    kolb = KOLB_DATA.get(module_id)
    if kolb:
        # Add predictions
        for marker, prompt in kolb.get("predictions", []):
            if prompt not in content and "Before you continue" not in content:
                idx = content.find(marker)
                if idx >= 0:
                    # For the generic pattern, insert before the matched section
                    content = content[:idx] + prompt + '\n\n' + content[idx:]

        # Add reflection
        if kolb.get("reflection"):
            marker, reflection_text = kolb["reflection"]
            if reflection_text not in content and "What did you notice" not in content:
                idx = content.find(marker)
                if idx >= 0:
                    content = content[:idx] + reflection_text + '\n\n' + content[idx:]

    # Add hints
    hints = HINTS_DATA.get(module_id, {})
    for marker, hint_text in hints.items():
        if marker in content and hint_text.strip() not in content:
            idx = content.find(marker)
            if idx >= 0:
                # Find end of this section (next ### heading or ## heading or ---)
                search_start = idx + len(marker)
                next_heading = re.search(r'\n(###?\s+(?:📐|🛠️|🐛|🔍|📊|🤔|\d+\.))', content[search_start:])
                next_section = re.search(r'\n## \d+\.', content[search_start:])
                next_hr = content.find('\n---\n', search_start)

                positions = []
                if next_heading:
                    positions.append(search_start + next_heading.start())
                if next_section:
                    positions.append(search_start + next_section.start())
                if next_hr >= 0:
                    positions.append(next_hr)

                if positions:
                    insert_at = min(positions)
                    content = content[:insert_at] + '\n' + hint_text + '\n' + content[insert_at:]

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  Updated: {filename}")
    else:
        print(f"  No changes needed: {filename}")


def main():
    files = sorted([
        f for f in os.listdir(LOOP2_DIR)
        if f.endswith('.md') and f.startswith('L2-M')
    ])

    print(f"Pass 2: Processing {len(files)} files for Kolb prompts and hints...")

    for filename in files:
        filepath = os.path.join(LOOP2_DIR, filename)
        process_file(filepath)

    print("\nPass 2 complete.")


if __name__ == '__main__':
    main()

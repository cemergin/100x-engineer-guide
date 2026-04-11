<!--
  CHAPTER: 24b
  TITLE: SQL Mastery & Graph Databases
  PART: I — Foundations
  PREREQS: Chapter 2, Chapter 24
  KEY_TOPICS: advanced SQL, CTEs, recursive CTEs, window functions, lateral joins, JSON operations, SQL anti-patterns, query recipes, graph databases, Cypher, Neo4j, property graphs
  DIFFICULTY: Advanced
  UPDATED: 2026-04-10
-->

# Chapter 24b: SQL Mastery & Graph Databases

> **Part I — Foundations** | Prerequisites: Chapter 2, Chapter 24 | Difficulty: Advanced

Chapter 24 opened up the database engine — MVCC, WAL, the query planner, vacuum, buffer management, all the machinery that runs beneath your queries. This chapter is about the queries themselves: the SQL patterns that separate senior engineers from everyone else, and the alternative database model you reach for when relational JOINs stop being the right tool.

The first half covers practical SQL that you will use weekly. Not textbook exercises — real patterns pulled from production codebases: recursive CTEs for hierarchical data, window functions for analytics, lateral joins for "top N per group," and the anti-patterns that silently destroy performance. The second half covers graph databases — when relationships *are* the data and traversals replace JOINs.

### In This Chapter
- Common Table Expressions (CTEs)
- Recursive CTEs
- Window Functions Deep Dive
- JSON Operations
- Advanced Query Patterns
- SQL Anti-Patterns
- Practical Query Recipes
- Performance Patterns
- Graph Databases

### Related Chapters
- **DATABASE spiral:** ← [Ch 24: Database Internals](../part-1-foundations/24-database-internals.md) | → [Ch 23: System Design Case Studies](../part-2-applied-engineering/23-system-design-case-studies.md)
- Ch 2 (database paradigms and data modeling)
- Ch 24 (database internals, optimization, and operations — the engine that runs these queries)
- Ch 18 (slow query debugging)
- Ch 22 (B-trees and LSM trees — the index structures behind query performance)

---

## 1. SQL Mastery

The queries that separate junior from senior database engineers. These are the patterns you'll reach for weekly.

### Common Table Expressions (CTEs)

```sql
-- Basic CTE: readable, named subqueries
WITH active_users AS (
    SELECT id, name, email, created_at
    FROM users
    WHERE status = 'active' AND last_login > NOW() - INTERVAL '30 days'
),
user_orders AS (
    SELECT user_id, COUNT(*) as order_count, SUM(total) as total_spent
    FROM orders
    WHERE created_at > NOW() - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT au.name, au.email, COALESCE(uo.order_count, 0) as orders,
       COALESCE(uo.total_spent, 0) as spent
FROM active_users au
LEFT JOIN user_orders uo ON au.id = uo.user_id
ORDER BY uo.total_spent DESC NULLS LAST;

-- WHY CTEs: readable, self-documenting, can reference multiple times
-- NOTE: In PostgreSQL, CTEs are optimization fences before v12.
-- In v12+, the planner can inline CTEs (use MATERIALIZED to force old behavior)
```

### Recursive CTEs

```sql
-- Organizational hierarchy (find all reports under a manager)
WITH RECURSIVE org_tree AS (
    -- Base case: the starting manager
    SELECT id, name, manager_id, 0 as depth
    FROM employees
    WHERE id = 42  -- starting manager

    UNION ALL

    -- Recursive case: find direct reports of current level
    SELECT e.id, e.name, e.manager_id, ot.depth + 1
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
    WHERE ot.depth < 10  -- safety limit to prevent infinite recursion
)
SELECT * FROM org_tree ORDER BY depth, name;

-- Category tree (e-commerce: Electronics > Phones > Smartphones)
-- Bill of materials (manufacturing: assembly contains sub-assemblies)
-- Graph traversal in SQL (shortest path, reachability)
```

### Window Functions

```sql
-- ROW_NUMBER: assign a unique number within each partition
SELECT name, department, salary,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
FROM employees;
-- Use case: "top N per group" → WHERE rank <= 3

-- RANK vs DENSE_RANK vs ROW_NUMBER
-- Salaries: 100, 90, 90, 80
-- ROW_NUMBER: 1, 2, 3, 4  (always unique)
-- RANK:       1, 2, 2, 4  (gaps after ties)
-- DENSE_RANK: 1, 2, 2, 3  (no gaps)

-- Running total
SELECT date, revenue,
    SUM(revenue) OVER (ORDER BY date) as running_total
FROM daily_revenue;

-- Moving average (7-day)
SELECT date, revenue,
    AVG(revenue) OVER (
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as avg_7day
FROM daily_revenue;

-- Percentage of total
SELECT department, salary,
    salary::numeric / SUM(salary) OVER () * 100 as pct_of_total
FROM employees;

-- LAG / LEAD (access previous/next row)
SELECT date, revenue,
    revenue - LAG(revenue) OVER (ORDER BY date) as day_over_day_change,
    LEAD(revenue) OVER (ORDER BY date) as next_day_revenue
FROM daily_revenue;

-- FIRST_VALUE / LAST_VALUE / NTH_VALUE
SELECT name, department, salary,
    FIRST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC) as highest_paid
FROM employees;

-- NTILE (divide rows into N buckets)
SELECT name, salary,
    NTILE(4) OVER (ORDER BY salary) as quartile
FROM employees;
```

### Window Functions Deep Dive

The examples above cover the basics, but window functions have subtleties that trip up even experienced engineers. This section covers the patterns that come up in real analytics work.

#### Frame Specifications: ROWS vs RANGE vs GROUPS

The frame clause controls which rows the window function considers. Getting this wrong produces silently incorrect results.

```sql
-- ROWS BETWEEN: physical row count — predictable, most common
SELECT date, revenue,
    SUM(revenue) OVER (
        ORDER BY date
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) as sum_3_rows
FROM daily_revenue;
-- Always exactly 3 rows (or fewer at the start). Simple. Predictable.

-- RANGE BETWEEN: logical value range — careful with duplicates
SELECT date, revenue,
    SUM(revenue) OVER (
        ORDER BY date
        RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
    ) as sum_7_days
FROM daily_revenue;
-- Includes ALL rows within 7 calendar days, even if there are gaps or duplicates.
-- If two rows share the same date, both are included (RANGE treats ties as a group).

-- GROUPS BETWEEN: groups of peer rows (PostgreSQL 11+)
SELECT date, revenue,
    SUM(revenue) OVER (
        ORDER BY date
        GROUPS BETWEEN 1 PRECEDING AND 1 FOLLOWING
    ) as sum_neighbor_groups
FROM daily_revenue;
-- "Peers" = rows with the same ORDER BY value. GROUPS counts groups, not rows.

-- DEFAULT FRAME (the trap):
-- SUM(...) OVER (ORDER BY date) actually means:
-- SUM(...) OVER (ORDER BY date RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
-- NOT ROWS — so duplicate dates get the same running total (they're peers).
-- This is a common source of subtle bugs.
```

#### Partition-Relative Calculations

```sql
-- Percentage rank within each department (0 to 1 scale)
SELECT name, department, salary,
    PERCENT_RANK() OVER (PARTITION BY department ORDER BY salary) as pct_rank,
    CUME_DIST() OVER (PARTITION BY department ORDER BY salary) as cumulative_dist
FROM employees;
-- PERCENT_RANK: (rank - 1) / (total_rows - 1) — where does this row stand?
-- CUME_DIST: fraction of rows <= current row — what percentile is this?

-- Difference from partition average
SELECT name, department, salary,
    salary - AVG(salary) OVER (PARTITION BY department) as diff_from_dept_avg,
    salary::numeric / AVG(salary) OVER (PARTITION BY department) as ratio_to_dept_avg
FROM employees;

-- Detect consecutive sequences (island detection)
-- Find streaks of days where a user was active
SELECT user_id, date,
    date - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY date))::int as island_id
FROM user_activity;
-- Rows in the same streak get the same island_id.
-- GROUP BY island_id to find streak start, end, and length.
```

#### Named Window Definitions

```sql
-- When you use the same window multiple times, name it (DRY principle)
SELECT name, department, salary,
    ROW_NUMBER() OVER w as row_num,
    RANK() OVER w as rank,
    SUM(salary) OVER w as running_salary_total,
    AVG(salary) OVER w as running_salary_avg
FROM employees
WINDOW w AS (PARTITION BY department ORDER BY salary DESC);
-- Cleaner, less error-prone than repeating the OVER clause four times.
```

### JSON Operations (PostgreSQL)

```sql
-- JSONB storage and querying (PostgreSQL)
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert
INSERT INTO events (data) VALUES ('{"type": "click", "page": "/home", "user_id": 123}');

-- Access fields
SELECT data->>'type' as event_type,          -- text extraction
       data->'user_id' as user_id_json,       -- JSON extraction
       data#>>'{nested,deep,field}' as deep   -- nested path extraction
FROM events;

-- Filter on JSON fields
SELECT * FROM events WHERE data->>'type' = 'click';
SELECT * FROM events WHERE data @> '{"type": "click"}';  -- containment (uses GIN index!)
SELECT * FROM events WHERE data ? 'user_id';              -- key exists

-- GIN index for JSONB (essential for performance)
CREATE INDEX idx_events_data ON events USING GIN (data);
-- Supports: @>, ?, ?|, ?& operators

-- JSONB aggregation
SELECT data->>'type' as event_type, COUNT(*)
FROM events
GROUP BY data->>'type';

-- Build JSON in queries
SELECT json_build_object(
    'user', json_build_object('id', u.id, 'name', u.name),
    'orders', json_agg(json_build_object('id', o.id, 'total', o.total))
) as result
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name;

-- jsonb_path_query (SQL/JSON path — PostgreSQL 12+)
SELECT * FROM events
WHERE jsonb_path_exists(data, '$.tags[*] ? (@ == "urgent")');
```

### Advanced Query Patterns

```sql
-- UPSERT (INSERT ... ON CONFLICT)
INSERT INTO user_settings (user_id, key, value)
VALUES (123, 'theme', 'dark')
ON CONFLICT (user_id, key)
DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

-- Batch upsert with UNNEST (PostgreSQL — much faster than individual inserts)
INSERT INTO metrics (name, value, recorded_at)
SELECT * FROM UNNEST(
    ARRAY['cpu', 'memory', 'disk'],
    ARRAY[45.2, 72.1, 55.0],
    ARRAY[NOW(), NOW(), NOW()]
)
ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value;

-- LATERAL JOIN (like a for-each loop in SQL)
-- "For each user, get their 3 most recent orders"
SELECT u.name, recent_orders.*
FROM users u
CROSS JOIN LATERAL (
    SELECT id, total, created_at
    FROM orders
    WHERE user_id = u.id
    ORDER BY created_at DESC
    LIMIT 3
) recent_orders;
-- WHY LATERAL: the subquery can reference columns from the outer query

-- FILTER clause (conditional aggregation — cleaner than CASE)
SELECT
    COUNT(*) as total_orders,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
    SUM(total) FILTER (WHERE status = 'completed') as completed_revenue
FROM orders
WHERE created_at > NOW() - INTERVAL '30 days';

-- GROUPING SETS / CUBE / ROLLUP (multiple aggregation levels in one query)
SELECT
    COALESCE(region, 'ALL') as region,
    COALESCE(product, 'ALL') as product,
    SUM(revenue) as total
FROM sales
GROUP BY GROUPING SETS (
    (region, product),  -- per region+product
    (region),           -- per region subtotal
    (product),          -- per product subtotal
    ()                  -- grand total
);

-- EXISTS vs IN vs JOIN for semi-joins
-- EXISTS is usually fastest for correlated checks:
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.total > 1000);
-- Better than: WHERE id IN (SELECT user_id FROM orders WHERE total > 1000)
-- Because EXISTS short-circuits on first match

-- Generate series (useful for filling gaps in time-series data)
SELECT date, COALESCE(daily.count, 0) as count
FROM generate_series(
    '2024-01-01'::date,
    '2024-01-31'::date,
    '1 day'::interval
) as date
LEFT JOIN (
    SELECT DATE(created_at) as day, COUNT(*) as count
    FROM events GROUP BY DATE(created_at)
) daily ON date = daily.day;
```

### SQL Anti-Patterns

These are the mistakes that silently destroy performance. You will encounter every one of these in production codebases — often written by experienced engineers who didn't realize the cost.

#### SELECT * (The Kitchen Sink)

```sql
-- BAD: fetches all columns, prevents covering index optimization
SELECT * FROM orders WHERE customer_id = 42;

-- GOOD: fetch only what you need
SELECT id, total, status, created_at FROM orders WHERE customer_id = 42;

-- WHY IT MATTERS:
-- 1. Transfers more data over the network (especially with TEXT/JSONB columns)
-- 2. Prevents "index-only scans" — Postgres can answer from the index alone
--    if every requested column is in the index. SELECT * always requires a
--    heap fetch (hitting the table data on disk)
-- 3. Breaks when columns are added/removed (fragile application code)
-- 4. In wide tables with TOAST columns, forces decompression of large values
```

#### The N+1 Query Problem

```sql
-- THE PROBLEM: ORM loads a list, then queries each item individually
-- Pseudocode:
--   users = db.query("SELECT * FROM users LIMIT 100")
--   for user in users:
--       orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)
-- Result: 1 query + 100 queries = 101 database round-trips

-- FIX 1: JOIN (single query)
SELECT u.id, u.name, o.id as order_id, o.total
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
ORDER BY u.id;

-- FIX 2: Batch IN query (two queries total)
-- Query 1: SELECT * FROM users LIMIT 100
-- Query 2: SELECT * FROM orders WHERE user_id IN (1, 2, 3, ..., 100)
-- Then join in application code

-- FIX 3: LATERAL (top-N per user, still one query)
SELECT u.id, u.name, recent.*
FROM users u
CROSS JOIN LATERAL (
    SELECT id, total FROM orders
    WHERE user_id = u.id ORDER BY created_at DESC LIMIT 5
) recent;

-- HOW TO DETECT: enable pg_stat_statements and look for queries with
-- extremely high 'calls' count relative to rows returned
```

#### Implicit Type Casting

```sql
-- BAD: column is integer, parameter is text — forces a cast on every row
SELECT * FROM orders WHERE id = '42';
-- Postgres may cast every row's id to text for comparison, preventing index use

-- BAD: comparing timestamp column with text
SELECT * FROM events WHERE created_at > '2024-01-01';
-- Works but relies on implicit parsing. Explicit is safer:
SELECT * FROM events WHERE created_at > '2024-01-01'::timestamptz;

-- BAD: joining on mismatched types
SELECT * FROM orders o JOIN products p ON o.product_id = p.id::text;
-- The cast prevents index use on one side. Fix the schema instead.

-- RULE: always match types exactly in WHERE and JOIN clauses.
-- When in doubt, run EXPLAIN and look for "Function Scan" or unexpected Seq Scans.
```

#### Unnecessary DISTINCT and ORDER BY

```sql
-- BAD: using DISTINCT to mask a bad JOIN that produces duplicates
SELECT DISTINCT u.id, u.name
FROM users u
JOIN orders o ON u.id = o.user_id;
-- If you need unique users, use EXISTS (which short-circuits):
SELECT u.id, u.name FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

-- BAD: ORDER BY inside a subquery that doesn't need it
SELECT * FROM (
    SELECT id, name FROM users ORDER BY name  -- pointless here
) sub
WHERE id < 100;
-- The outer query makes no ordering guarantee. The optimizer may ignore it,
-- or it may waste time sorting. Only ORDER BY at the outermost query level.
```

#### OFFSET Pagination at Depth

```sql
-- BAD: OFFSET grows linearly — page 500 scans and discards 10,000 rows
SELECT * FROM products ORDER BY created_at DESC LIMIT 20 OFFSET 10000;
-- Postgres must process 10,020 rows to return 20. Gets slower with every page.

-- GOOD: keyset pagination (covered in Performance Patterns below)
SELECT * FROM products
WHERE (created_at, id) < ('2024-06-15T10:00:00Z', 54321)
ORDER BY created_at DESC, id DESC LIMIT 20;
-- Uses index directly. O(1) regardless of "page" depth.
```

### Practical Query Recipes

Real queries for real problems. These come up constantly in production systems.

#### Time-Series Bucketing

```sql
-- Bucket events into 15-minute intervals
SELECT
    date_trunc('hour', created_at) +
        (EXTRACT(minute FROM created_at)::int / 15) * INTERVAL '15 minutes' as bucket,
    COUNT(*) as event_count,
    AVG(response_time_ms) as avg_response_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_ms
FROM api_requests
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1;

-- Simpler: use date_trunc for standard intervals
SELECT
    date_trunc('hour', created_at) as hour,
    COUNT(*) as requests,
    COUNT(*) FILTER (WHERE status_code >= 500) as errors,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status_code >= 500) / COUNT(*), 2) as error_rate
FROM api_requests
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1;
```

#### Running Totals and Cumulative Metrics

```sql
-- Monthly revenue with running total and month-over-month change
SELECT
    month,
    revenue,
    SUM(revenue) OVER (ORDER BY month) as cumulative_revenue,
    revenue - LAG(revenue) OVER (ORDER BY month) as mom_change,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
        / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) as mom_pct_change
FROM (
    SELECT date_trunc('month', created_at) as month, SUM(total) as revenue
    FROM orders
    WHERE status = 'completed'
    GROUP BY 1
) monthly
ORDER BY month;

-- Customer lifetime value running total
SELECT
    customer_id,
    order_date,
    order_total,
    SUM(order_total) OVER (PARTITION BY customer_id ORDER BY order_date) as lifetime_value,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) as order_number
FROM orders
ORDER BY customer_id, order_date;
```

#### Gap and Island Analysis

```sql
-- Find gaps in a sequence (e.g., missing invoice numbers)
WITH all_numbers AS (
    SELECT generate_series(
        (SELECT MIN(invoice_number) FROM invoices),
        (SELECT MAX(invoice_number) FROM invoices)
    ) as expected
)
SELECT expected as missing_invoice_number
FROM all_numbers a
LEFT JOIN invoices i ON a.expected = i.invoice_number
WHERE i.invoice_number IS NULL;

-- Find consecutive date ranges ("islands") per user
-- Use case: subscription active periods, login streaks, uptime windows
WITH ranked AS (
    SELECT
        user_id,
        active_date,
        active_date - (ROW_NUMBER() OVER (
            PARTITION BY user_id ORDER BY active_date
        ))::int as island_id
    FROM user_activity
)
SELECT
    user_id,
    MIN(active_date) as streak_start,
    MAX(active_date) as streak_end,
    COUNT(*) as streak_days
FROM ranked
GROUP BY user_id, island_id
HAVING COUNT(*) >= 3  -- only streaks of 3+ days
ORDER BY user_id, streak_start;
```

#### Top-N Per Group (A Pattern You Will Use Constantly)

```sql
-- Method 1: ROW_NUMBER (most common)
SELECT * FROM (
    SELECT
        product_id, review_text, rating, created_at,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY rating DESC, created_at DESC) as rn
    FROM reviews
) ranked
WHERE rn <= 3;

-- Method 2: LATERAL JOIN (often faster — uses index on each iteration)
SELECT p.id, p.name, top_reviews.*
FROM products p
CROSS JOIN LATERAL (
    SELECT review_text, rating, created_at
    FROM reviews
    WHERE product_id = p.id
    ORDER BY rating DESC, created_at DESC
    LIMIT 3
) top_reviews;

-- Method 3: DISTINCT ON (PostgreSQL-specific, elegant for top-1)
SELECT DISTINCT ON (department)
    department, name, salary
FROM employees
ORDER BY department, salary DESC;
-- Returns the highest-paid employee per department (one row each).
```

#### Cohort Retention Analysis

```sql
-- User retention by signup month: what % are still active N months later?
WITH cohorts AS (
    SELECT
        id as user_id,
        date_trunc('month', created_at) as cohort_month
    FROM users
),
activity AS (
    SELECT
        user_id,
        date_trunc('month', event_date) as activity_month
    FROM user_events
    GROUP BY 1, 2
)
SELECT
    c.cohort_month,
    EXTRACT(MONTH FROM AGE(a.activity_month, c.cohort_month))::int as months_since_signup,
    COUNT(DISTINCT a.user_id) as active_users,
    COUNT(DISTINCT c.user_id) as cohort_size,
    ROUND(100.0 * COUNT(DISTINCT a.user_id) / COUNT(DISTINCT c.user_id), 1) as retention_pct
FROM cohorts c
LEFT JOIN activity a ON c.user_id = a.user_id AND a.activity_month >= c.cohort_month
GROUP BY 1, 2
ORDER BY 1, 2;
```

### Performance Patterns

```sql
-- Keyset pagination (fast, stable — replaces OFFSET for deep pages)
-- First page:
SELECT id, name, created_at FROM users ORDER BY created_at DESC, id DESC LIMIT 20;
-- Next page (pass last row's values):
SELECT id, name, created_at FROM users
WHERE (created_at, id) < ('2024-01-15T10:00:00Z', 12345)
ORDER BY created_at DESC, id DESC LIMIT 20;
-- WHY: uses index directly, O(1) regardless of page depth
-- vs OFFSET 10000 which must scan and discard 10000 rows

-- Materialized view for expensive aggregations
CREATE MATERIALIZED VIEW monthly_revenue AS
SELECT DATE_TRUNC('month', created_at) as month,
       SUM(total) as revenue, COUNT(*) as order_count
FROM orders GROUP BY 1;
-- Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue;
-- Requires unique index for CONCURRENTLY

-- Advisory locks (application-level distributed locking in PostgreSQL)
SELECT pg_try_advisory_lock(hashtext('process-invoices'));
-- Returns true if lock acquired, false if already held
-- Use for: singleton job execution, preventing duplicate processing
SELECT pg_advisory_unlock(hashtext('process-invoices'));
```

---

## 2. Graph Databases

When relationships between entities are as important as the entities themselves — when the *connections* are the data — relational JOINs become unwieldy and graph databases shine.

### How Graph Databases Work

**The Property Graph Model** (used by Neo4j, Neptune, Memgraph):
- **Nodes** (vertices): entities with labels and properties. `(:User {name: "Alice", age: 30})`
- **Relationships** (edges): typed, directed connections with properties. `[:FOLLOWS {since: "2023-01-15"}]`
- **Both nodes and relationships can have arbitrary key-value properties**
- Relationships are first-class citizens — they are stored and indexed, not computed via JOINs

**How it differs from relational:**
```
RELATIONAL: To find "friends of friends of Alice"
  SELECT DISTINCT f3.name
  FROM users u
  JOIN friendships f1 ON u.id = f1.user_id
  JOIN friendships f2 ON f1.friend_id = f2.user_id
  JOIN friendships f3_rel ON f2.friend_id = f3_rel.user_id
  JOIN users f3 ON f3_rel.friend_id = f3.id
  WHERE u.name = 'Alice';
  -- Multiple self-JOINs, gets worse with each hop, performance degrades

GRAPH (Cypher):
  MATCH (alice:User {name: "Alice"})-[:FRIENDS*2..3]-(fof:User)
  RETURN DISTINCT fof.name
  -- Traversal, not JOIN. Performance depends on local neighborhood size, not table size.
```

**Key insight:** In a relational DB, the cost of a JOIN is proportional to the table sizes. In a graph DB, the cost of a traversal is proportional to the local neighborhood — it doesn't matter if you have 1 billion nodes if you're only traversing 3 hops from one node. This is the fundamental performance advantage of graph databases for relationship-heavy queries, and it's why social networks, fraud detection systems, and recommendation engines reach for them.

### Query Languages

**Cypher** (Neo4j, Memgraph — most popular):
```cypher
-- Create nodes and relationships
CREATE (alice:User {name: "Alice", email: "alice@example.com"})
CREATE (bob:User {name: "Bob"})
CREATE (alice)-[:FOLLOWS {since: date("2024-01-15")}]->(bob)

-- Pattern matching: find who Alice follows
MATCH (alice:User {name: "Alice"})-[:FOLLOWS]->(followed)
RETURN followed.name

-- Variable-length paths: friends within 1-3 hops
MATCH (alice:User {name: "Alice"})-[:FRIENDS*1..3]-(friend)
RETURN DISTINCT friend.name, length(shortestPath((alice)-[:FRIENDS*]-(friend))) as distance

-- Shortest path
MATCH path = shortestPath((a:User {name: "Alice"})-[:KNOWS*]-(b:User {name: "Dave"}))
RETURN nodes(path), length(path)

-- Aggregation: most connected users
MATCH (u:User)-[:FOLLOWS]->(other)
RETURN u.name, count(other) as following_count
ORDER BY following_count DESC LIMIT 10

-- Subgraph pattern: find triangles (mutual connections)
MATCH (a:User)-[:FRIENDS]-(b:User)-[:FRIENDS]-(c:User)-[:FRIENDS]-(a)
RETURN DISTINCT a.name, b.name, c.name

-- Recommend: products bought by people who bought what I bought
MATCH (me:User {id: 123})-[:PURCHASED]->(product)<-[:PURCHASED]-(other)-[:PURCHASED]->(rec)
WHERE NOT (me)-[:PURCHASED]->(rec)
RETURN rec.name, count(other) as score
ORDER BY score DESC LIMIT 10
```

**Gremlin** (Apache TinkerPop — used by Neptune, JanusGraph, CosmosDB):
```groovy
// Traversal-based, more verbose, more portable
g.V().has('User', 'name', 'Alice').out('FOLLOWS').values('name')

// Variable-length: 2-3 hops
g.V().has('User', 'name', 'Alice').repeat(both('FRIENDS')).times(3).dedup().values('name')
```

**SPARQL** (RDF/triple stores — used by knowledge graphs, W3C standard):
```sparql
SELECT ?friendName WHERE {
  :alice :knows ?friend .
  ?friend :name ?friendName .
}
```

### When to Use a Graph Database

| Use Case | Why Graph Excels | Example |
|----------|-----------------|---------|
| **Social networks** | Relationship traversal IS the query | "People you may know", mutual friends, influence scoring |
| **Fraud detection** | Detect patterns across entities | Shared phone/email/device across accounts = fraud ring |
| **Recommendation engines** | Collaborative filtering via graph | "Customers who bought X also bought Y" — natural graph traversal |
| **Knowledge graphs** | Rich entity relationships with inference | Google Knowledge Panel, enterprise data catalogs |
| **Identity resolution** | Match entities across datasets | Same person with different names/emails across systems |
| **Network/IT operations** | Dependency mapping | "If this server goes down, what services are affected?" |
| **Authorization (ReBAC)** | Permission via relationships | Google Zanzibar: "User X has role Y on resource Z" — traverse the graph |
| **Supply chain** | Multi-hop dependency tracking | "Which suppliers are affected if factory X shuts down?" |

### When NOT to Use a Graph Database

- **Simple CRUD** with no relationship queries — Postgres is better
- **Heavy aggregations** (SUM, AVG, GROUP BY) — graph DBs are weak at this
- **Time-series data** — use TimescaleDB/InfluxDB
- **Full-text search** — use Elasticsearch
- **Tabular reporting** — relational is built for this
- **If your queries are always "get entity by ID"** — key-value store is simpler

The data modeling guidance from Ch 2 applies here too: choose the database whose native data model matches your access patterns. If your access patterns are "traverse relationships," graph. If they're "aggregate columns," relational.

### Graph Database Options

| Database | Model | Hosting | Best For |
|----------|-------|---------|----------|
| **Neo4j** | Property graph | Self-hosted, Aura (cloud) | Most mature, best tooling, Cypher |
| **Amazon Neptune** | Property graph + RDF | AWS managed | AWS-native, Gremlin + SPARQL |
| **Memgraph** | Property graph | Self-hosted, cloud | Real-time streaming graphs, Cypher-compatible |
| **ArangoDB** | Multi-model (graph + document + KV) | Self-hosted, cloud | When you need graph + document in one DB |
| **TigerGraph** | Property graph | Self-hosted, cloud | Massive-scale analytics, parallel traversal |
| **Dgraph** | Property graph (GraphQL-native) | Self-hosted, cloud | GraphQL API directly on the graph |
| **JanusGraph** | Property graph | Self-hosted (on Cassandra/HBase) | Massive scale, TinkerPop/Gremlin |
| **PostgreSQL + Apache AGE** | Property graph (extension) | Self-hosted | Add graph queries to existing Postgres |

### Data Modeling for Graphs

**Principles:**
1. **Model verbs as relationships, nouns as nodes.** "Alice PURCHASED Product" not "Alice has purchase_id 123"
2. **Use specific relationship types.** `:PURCHASED`, `:REVIEWED`, `:RETURNED` — not generic `:RELATED_TO`
3. **Store properties on relationships.** A `:PURCHASED` relationship can have `{date, quantity, price}`
4. **Avoid super-nodes** (nodes with millions of relationships). They become bottlenecks. Strategies: partition by time (`[:FOLLOWS_2024]`), use intermediate nodes
5. **Denormalize for query patterns.** Like NoSQL, model for how you query, not for normalization

**Example: E-Commerce Graph Model:**
```
(:Customer)-[:PURCHASED {date, amount}]->(:Order)-[:CONTAINS {qty}]->(:Product)
(:Product)-[:IN_CATEGORY]->(:Category)-[:SUBCATEGORY_OF]->(:Category)
(:Customer)-[:REVIEWED {rating, text}]->(:Product)
(:Customer)-[:VIEWED {timestamp}]->(:Product)
(:Product)-[:SIMILAR_TO {score}]->(:Product)
```

### Performance & Scaling

**Index everything you query by:** Create indexes on node properties used in MATCH patterns.
```cypher
CREATE INDEX FOR (u:User) ON (u.email)
CREATE INDEX FOR (u:User) ON (u.id)
CREATE CONSTRAINT FOR (u:User) REQUIRE u.id IS UNIQUE
```

**Scaling challenges:**
- Graph databases are harder to shard than key-value or document stores — sharding cuts edges, requiring cross-partition traversals
- **Neo4j**: leader-follower replication (reads scale, writes don't) or Fabric (sharded subgraphs)
- **Neptune**: read replicas (up to 15), storage auto-scales
- **JanusGraph/TigerGraph**: designed for horizontal scaling from the start

**Performance tips:**
- Limit traversal depth (`*1..5` not `*` — unbounded traversals can explode exponentially)
- Use `PROFILE` or `EXPLAIN` to understand query plans
- Warm the page cache on startup for frequently accessed subgraphs
- Batch writes (especially for initial data load — Neo4j's `LOAD CSV` or `neo4j-admin import`)

### Graph + Relational: Hybrid Architecture

Many production systems use BOTH — and this is often the most practical path for an existing system:
```
PostgreSQL (OLTP)          Neo4j (Graph)
├── Users table            ├── (:User) nodes
├── Orders table           ├── (:Order) nodes
├── Products table         ├── Relationships
└── Transactions           └── Recommendations

Sync via CDC (Debezium) → Kafka → Neo4j consumer
```

- **Postgres** handles: CRUD, transactions, reporting, aggregations
- **Neo4j** handles: recommendations, fraud detection, social features, path finding
- **CDC keeps them in sync**: changes in Postgres are streamed to Neo4j

This is the most practical architecture for adding graph capabilities to an existing system — you don't replace your relational DB, you augment it. The systems play to their respective strengths, and CDC (Change Data Capture) keeps them in sync with minimal latency.

---

This chapter covered the SQL patterns that show up in real production work and the graph database model that handles relationship-heavy workloads. The SQL sections are not academic exercises — CTEs, window functions, lateral joins, and keyset pagination are tools you will reach for weekly. The anti-patterns section exists because every one of those mistakes is something you will encounter (or write) in a real codebase.

Graph databases are not a replacement for relational. They are a complement. When your access pattern is "traverse relationships," when the number of JOINs grows with the depth of the query, when the connections between entities matter as much as the entities themselves — that is when a graph database earns its place in your architecture. For everything else, the relational model and the SQL patterns in this chapter will serve you well.

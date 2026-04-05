# L2-M39: Advanced SQL for Analytics

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L1-M06, L1-M07, L2-M37
>
> **Source:** Chapter 24 of the 100x Engineer Guide

## What You'll Learn
- Window functions: ROW_NUMBER, LAG, NTILE, running totals, rolling averages
- CTEs and recursive CTEs for cohort analysis
- LATERAL JOINs for "top N per group" queries
- JSON aggregation to build API-ready nested responses in SQL
- Materialized views to precompute expensive dashboards
- pg_cron for automated refresh schedules

## Why This Matters
TicketPulse needs an analytics dashboard. The product team wants revenue by venue, day-over-day trends, conversion rates, cohort retention, and more. You could build this in application code — fetching raw data and computing in JavaScript. But that means transferring millions of rows over the network, burning CPU in your API servers, and writing fragile aggregation logic. Or you can write 6 SQL queries and let the database do what it was designed to do.

This module teaches the SQL patterns that separate junior engineers ("I'll just fetch all the data and loop over it") from senior engineers ("the database computed exactly what the dashboard needs in one query").

## Prereq Check

Connect to the TicketPulse database with a substantial dataset:

```bash
docker exec -it ticketpulse-postgres psql -U ticketpulse -d tickets
```

Ensure you have analytics-friendly data. If needed, generate it:

```sql
-- Create a comprehensive dataset for analytics
-- (Skip if you already have rich data from previous modules)

-- Ensure we have venues with cities
CREATE TABLE IF NOT EXISTS venues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    capacity INTEGER NOT NULL
);

INSERT INTO venues (name, city, capacity) VALUES
    ('Madison Square Garden', 'New York', 20000),
    ('The Forum', 'Los Angeles', 17500),
    ('United Center', 'Chicago', 23000),
    ('Red Rocks', 'Denver', 9500),
    ('Ryman Auditorium', 'Nashville', 2362)
ON CONFLICT DO NOTHING;

-- Ensure events have categories and venue references
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    venue_id INTEGER REFERENCES venues(id),
    category VARCHAR(50),
    event_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Populate events
INSERT INTO events (name, venue_id, category, event_date)
SELECT
    'Event ' || s,
    (s % 5) + 1,
    CASE (s % 6)
        WHEN 0 THEN 'rock'
        WHEN 1 THEN 'jazz'
        WHEN 2 THEN 'pop'
        WHEN 3 THEN 'hip-hop'
        WHEN 4 THEN 'country'
        WHEN 5 THEN 'classical'
    END,
    NOW() - (random() * INTERVAL '180 days')
FROM generate_series(1, 100) AS s
ON CONFLICT DO NOTHING;

-- Ensure tickets have realistic purchase timestamps
-- (Tickets from M37 should already exist; add purchased_at if missing)
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS purchased_at TIMESTAMPTZ;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_id INTEGER;

UPDATE tickets SET
    purchased_at = created_at + (random() * INTERVAL '30 days'),
    customer_id = (random() * 999 + 1)::int
WHERE status = 'sold' AND purchased_at IS NULL;

-- Create orders table for revenue analysis
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    event_id INTEGER REFERENCES events(id),
    amount NUMERIC(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Populate orders from ticket sales
INSERT INTO orders (customer_id, event_id, amount, status, ordered_at)
SELECT
    (random() * 999 + 1)::int,
    (s % 100) + 1,
    (random() * 200 + 25)::numeric(10,2),
    CASE WHEN random() < 0.9 THEN 'completed'
         WHEN random() < 0.95 THEN 'refunded'
         ELSE 'cancelled'
    END,
    NOW() - (random() * INTERVAL '180 days')
FROM generate_series(1, 50000) AS s;

ANALYZE;
```

---

## Part 1: Revenue by Venue — Window Functions (10 min)

### The Dashboard Requirement

"Show revenue by venue for each of the last 30 days, with a rolling 30-day total."

### 🛠️ Build: Query 1 — Revenue by Venue with Rolling Window

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
-- Revenue by venue with a 30-day rolling sum
WITH daily_venue_revenue AS (
    SELECT
        v.name AS venue_name,
        DATE_TRUNC('day', o.ordered_at)::date AS day,
        SUM(o.amount) AS daily_revenue
    FROM orders o
    JOIN events e ON o.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    WHERE o.status = 'completed'
      AND o.ordered_at > NOW() - INTERVAL '90 days'
    GROUP BY v.name, DATE_TRUNC('day', o.ordered_at)::date
)
SELECT
    venue_name,
    day,
    daily_revenue,
    SUM(daily_revenue) OVER (
        PARTITION BY venue_name
        ORDER BY day
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS rolling_30d_revenue,
    ROUND(AVG(daily_revenue) OVER (
        PARTITION BY venue_name
        ORDER BY day
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS avg_7d_revenue
FROM daily_venue_revenue
ORDER BY venue_name, day;
```

### How Window Functions Work

```sql
SUM(daily_revenue) OVER (
    PARTITION BY venue_name        -- "start a new window for each venue"
    ORDER BY day                   -- "rows are ordered by date within the window"
    ROWS BETWEEN 29 PRECEDING     -- "look back 29 rows (days) before current"
        AND CURRENT ROW            -- "up to and including today"
)
```

The window function computes the aggregate **without collapsing rows**. You still get one row per venue per day, but each row also carries the rolling aggregate. This is impossible with GROUP BY alone.

### 🔍 Try It

Run the query. You should see each venue's daily revenue alongside its 30-day rolling total. Notice how the rolling total "warms up" — the first row only sums itself, the second sums two days, etc.

---

> **Before you continue:** The product team wants a rolling 30-day revenue total per venue. Could you compute this with GROUP BY alone? What SQL feature lets you compute aggregates across rows without collapsing them?


## Part 2: Top Events by Conversion Rate — CTEs (8 min)

### The Dashboard Requirement

"Show the top 10 events by conversion rate (tickets sold / tickets available)."

### 🛠️ Build: Query 2 — Conversion Rate with CTE

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
WITH ticket_stats AS (
    SELECT
        event_id,
        COUNT(*) AS total_tickets,
        COUNT(*) FILTER (WHERE status = 'sold') AS sold_tickets,
        COUNT(*) FILTER (WHERE status = 'available') AS available_tickets
    FROM tickets
    GROUP BY event_id
),
conversion AS (
    SELECT
        e.name AS event_name,
        e.category,
        v.name AS venue_name,
        ts.total_tickets,
        ts.sold_tickets,
        ROUND(ts.sold_tickets::numeric / NULLIF(ts.total_tickets, 0) * 100, 1) AS conversion_rate
    FROM ticket_stats ts
    JOIN events e ON ts.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    WHERE ts.total_tickets > 10  -- filter out events with very few tickets
)
SELECT *
FROM conversion
ORDER BY conversion_rate DESC
LIMIT 10;
```

### Why CTEs?

CTEs make complex queries readable by naming intermediate results. Compare the CTE version above with the equivalent subquery mess:

```sql
-- Don't do this — harder to read, harder to debug
SELECT e.name, ...
FROM (SELECT event_id, COUNT(*) ... FROM tickets GROUP BY event_id) ts
JOIN events e ON ...
JOIN venues v ON ...
```

> **Ecosystem note:** In PostgreSQL 12+, the planner can inline CTEs (optimize them as subqueries). In older versions, CTEs are **optimization fences** — the CTE is materialized before the outer query runs. If you need the old behavior, use `WITH ticket_stats AS MATERIALIZED (...)`.

---

## Part 3: Day-over-Day Revenue Change — LAG (8 min)

### The Dashboard Requirement

"Show daily revenue with the day-over-day change and percentage change."

### 🛠️ Build: Query 3 — LAG for Trend Analysis

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
WITH daily_revenue AS (
    SELECT
        DATE_TRUNC('day', ordered_at)::date AS day,
        SUM(amount) AS revenue,
        COUNT(*) AS order_count
    FROM orders
    WHERE status = 'completed'
      AND ordered_at > NOW() - INTERVAL '60 days'
    GROUP BY DATE_TRUNC('day', ordered_at)::date
)
SELECT
    day,
    revenue,
    order_count,
    LAG(revenue) OVER (ORDER BY day) AS prev_day_revenue,
    revenue - LAG(revenue) OVER (ORDER BY day) AS revenue_change,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY day))::numeric /
        NULLIF(LAG(revenue) OVER (ORDER BY day), 0) * 100,
        1
    ) AS pct_change
FROM daily_revenue
ORDER BY day;
```

### How LAG Works

`LAG(revenue) OVER (ORDER BY day)` looks at the **previous row** in the ordered window and returns its `revenue` value. `LEAD()` does the opposite — it looks at the next row.

```
day        | revenue | LAG(revenue) | revenue - LAG(revenue)
2024-01-01 | 1000    | NULL         | NULL  (no previous day)
2024-01-02 | 1200    | 1000         | 200   (+20%)
2024-01-03 | 900     | 1200         | -300  (-25%)
```

The first row's LAG is NULL because there's no previous row. Handle this with `COALESCE(LAG(...), 0)` if needed.

---

## Part 4: Revenue Quartiles — NTILE (5 min)

### The Dashboard Requirement

"Categorize events into revenue quartiles by category."

### 🛠️ Build: Query 4 — NTILE for Distribution Analysis

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
WITH event_revenue AS (
    SELECT
        e.id,
        e.name AS event_name,
        e.category,
        COALESCE(SUM(o.amount), 0) AS total_revenue
    FROM events e
    LEFT JOIN orders o ON e.id = o.event_id AND o.status = 'completed'
    GROUP BY e.id, e.name, e.category
)
SELECT
    event_name,
    category,
    total_revenue,
    NTILE(4) OVER (
        PARTITION BY category
        ORDER BY total_revenue DESC
    ) AS revenue_quartile,
    CASE NTILE(4) OVER (PARTITION BY category ORDER BY total_revenue DESC)
        WHEN 1 THEN 'Top 25%'
        WHEN 2 THEN 'Above Average'
        WHEN 3 THEN 'Below Average'
        WHEN 4 THEN 'Bottom 25%'
    END AS quartile_label
FROM event_revenue
ORDER BY category, revenue_quartile, total_revenue DESC;
```

`NTILE(4)` divides the rows in each partition into 4 roughly equal groups. This is how you build distribution analysis — identifying which events are top performers, which are underperforming, and segmenting them for different business actions.

---

## Part 5: Cohort Retention — Recursive CTE (10 min)

### The Dashboard Requirement

"Of the customers who placed their first order in month X, what percentage placed another order in the following months?"

### 🛠️ Build: Query 5 — Cohort Retention Analysis

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
-- Step 1: Identify each customer's cohort (month of first purchase)
WITH customer_cohort AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(ordered_at))::date AS cohort_month
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),

-- Step 2: For each customer, find which months they were active
customer_activity AS (
    SELECT DISTINCT
        o.customer_id,
        cc.cohort_month,
        DATE_TRUNC('month', o.ordered_at)::date AS activity_month
    FROM orders o
    JOIN customer_cohort cc ON o.customer_id = cc.customer_id
    WHERE o.status = 'completed'
),

-- Step 3: Calculate months since cohort start
cohort_retention AS (
    SELECT
        cohort_month,
        EXTRACT(YEAR FROM age(activity_month, cohort_month)) * 12 +
        EXTRACT(MONTH FROM age(activity_month, cohort_month)) AS months_since_first,
        COUNT(DISTINCT customer_id) AS active_customers
    FROM customer_activity
    GROUP BY cohort_month, activity_month
),

-- Step 4: Get cohort sizes for percentage calculation
cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM customer_cohort
    GROUP BY cohort_month
)

-- Step 5: Bring it together
SELECT
    cr.cohort_month,
    cs.cohort_size,
    cr.months_since_first,
    cr.active_customers,
    ROUND(cr.active_customers::numeric / cs.cohort_size * 100, 1) AS retention_pct
FROM cohort_retention cr
JOIN cohort_sizes cs ON cr.cohort_month = cs.cohort_month
WHERE cr.months_since_first <= 6  -- show first 6 months
ORDER BY cr.cohort_month, cr.months_since_first;
```

### Reading the Output

```
cohort_month | cohort_size | months_since_first | active | retention_pct
2024-01-01   | 150         | 0                  | 150    | 100.0%
2024-01-01   | 150         | 1                  | 45     | 30.0%
2024-01-01   | 150         | 2                  | 32     | 21.3%
2024-02-01   | 180         | 0                  | 180    | 100.0%
2024-02-01   | 180         | 1                  | 62     | 34.4%
```

Month 0 is always 100% (that's when they joined). The drop-off in subsequent months tells you how "sticky" TicketPulse is. The product team will use this to measure the impact of features and campaigns.

---

## Part 6: JSON Aggregation — API-Ready Responses (7 min)

### The Dashboard Requirement

"Return a complete event summary as nested JSON — event details, venue, ticket counts by status, and recent orders — all in one query."

### 🛠️ Build: Query 6 — JSON Aggregation

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
SELECT json_build_object(
    'event', json_build_object(
        'id', e.id,
        'name', e.name,
        'category', e.category,
        'date', e.event_date
    ),
    'venue', json_build_object(
        'name', v.name,
        'city', v.city,
        'capacity', v.capacity
    ),
    'ticket_stats', (
        SELECT json_build_object(
            'total', COUNT(*),
            'available', COUNT(*) FILTER (WHERE t.status = 'available'),
            'sold', COUNT(*) FILTER (WHERE t.status = 'sold'),
            'reserved', COUNT(*) FILTER (WHERE t.status = 'reserved')
        )
        FROM tickets t
        WHERE t.event_id = e.id
    ),
    'recent_orders', (
        SELECT COALESCE(json_agg(
            json_build_object(
                'id', o.id,
                'amount', o.amount,
                'ordered_at', o.ordered_at
            ) ORDER BY o.ordered_at DESC
        ), '[]'::json)
        FROM (
            SELECT id, amount, ordered_at
            FROM orders
            WHERE event_id = e.id AND status = 'completed'
            ORDER BY ordered_at DESC
            LIMIT 5
        ) o
    )
) AS event_summary
FROM events e
JOIN venues v ON e.venue_id = v.id
WHERE e.id = 1;
```

This returns a single JSON object:

```json
{
  "event": {"id": 1, "name": "Event 1", "category": "rock", "date": "2024-03-15T20:00:00Z"},
  "venue": {"name": "Madison Square Garden", "city": "New York", "capacity": 20000},
  "ticket_stats": {"total": 5000, "available": 1200, "sold": 3500, "reserved": 300},
  "recent_orders": [
    {"id": 4523, "amount": 125.00, "ordered_at": "2024-03-14T18:30:00Z"},
    {"id": 4501, "amount": 95.00, "ordered_at": "2024-03-14T16:15:00Z"}
  ]
}
```

One query, zero application-level data assembly. Your API handler becomes a thin pass-through.

---

## Part 7: LATERAL JOIN — Top N Per Group (5 min)

### The Problem

"Show the top 3 highest-grossing events per venue." This is surprisingly hard with standard SQL. Window functions can rank them, but LATERAL JOIN is cleaner.

### 🛠️ Build: LATERAL JOIN

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
SELECT v.name AS venue_name, top_events.*
FROM venues v
CROSS JOIN LATERAL (
    SELECT
        e.name AS event_name,
        e.category,
        SUM(o.amount) AS total_revenue
    FROM events e
    JOIN orders o ON e.id = o.event_id
    WHERE e.venue_id = v.id
      AND o.status = 'completed'
    GROUP BY e.id, e.name, e.category
    ORDER BY total_revenue DESC
    LIMIT 3
) top_events
ORDER BY v.name, total_revenue DESC;
```

### How LATERAL Works

A LATERAL subquery can **reference columns from preceding tables** in the FROM clause. It's like a SQL for-each loop:

```
For each venue:
    Run this subquery (which filters by that venue's ID)
    Return the top 3 results
```

Without LATERAL, you'd need a window function approach:

```sql
-- Alternative: window function (more verbose, same result)
WITH ranked AS (
    SELECT v.name AS venue_name, e.name AS event_name,
           SUM(o.amount) AS revenue,
           ROW_NUMBER() OVER (PARTITION BY v.id ORDER BY SUM(o.amount) DESC) AS rn
    FROM venues v
    JOIN events e ON e.venue_id = v.id
    JOIN orders o ON e.id = o.event_id AND o.status = 'completed'
    GROUP BY v.id, v.name, e.id, e.name
)
SELECT * FROM ranked WHERE rn <= 3;
```

Both work. LATERAL is more intuitive for "top N per group" patterns and can be more efficient when N is small relative to the total.

---

## Part 8: Materialized Views — Precomputed Dashboard (7 min)

### The Problem

These analytics queries are expensive. Running them on every dashboard page load would kill your database under load.

### 🛠️ Build: Create a Materialized View

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
-- Create the materialized view (runs the query once, stores the result)
CREATE MATERIALIZED VIEW dashboard_daily_stats AS
WITH daily AS (
    SELECT
        DATE_TRUNC('day', o.ordered_at)::date AS day,
        v.name AS venue_name,
        e.category,
        SUM(o.amount) AS revenue,
        COUNT(DISTINCT o.customer_id) AS unique_customers,
        COUNT(*) AS order_count
    FROM orders o
    JOIN events e ON o.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    WHERE o.status = 'completed'
    GROUP BY DATE_TRUNC('day', o.ordered_at)::date, v.name, e.category
)
SELECT * FROM daily;

-- Create a unique index (required for CONCURRENTLY refresh)
CREATE UNIQUE INDEX idx_dashboard_stats_unique
    ON dashboard_daily_stats (day, venue_name, category);
```

### 📊 Observe: Query Time Before and After

```sql
\timing on

-- Query the raw tables (expensive)
SELECT DATE_TRUNC('day', o.ordered_at)::date AS day,
       v.name, SUM(o.amount) AS revenue
FROM orders o
JOIN events e ON o.event_id = e.id
JOIN venues v ON e.venue_id = v.id
WHERE o.status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Query the materialized view (fast — it's pre-computed)
SELECT day, venue_name, revenue
FROM dashboard_daily_stats
ORDER BY day, venue_name;
```

The materialized view query should be dramatically faster — it's reading from a pre-computed, indexed table instead of joining and aggregating millions of rows.

### 🛠️ Build: Automated Refresh with pg_cron

<details>
<summary>💡 Hint 1: Direction</summary>
Think about what this query needs to compute. What SQL pattern (window function, CTE, LATERAL, aggregation) fits the requirement?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the query into named steps using CTEs, then apply the appropriate window function or join pattern on top.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the code example that follows -- the query structure matches the pattern described above, with specific columns and filters for this use case.
</details>


```sql
-- Install pg_cron extension (must be in shared_preload_libraries)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Refresh the materialized view every 5 minutes
SELECT cron.schedule(
    'refresh-dashboard-stats',
    '*/5 * * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_daily_stats$$
);

-- Check scheduled jobs
SELECT * FROM cron.job;

-- Check job run history
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;
```

**`CONCURRENTLY`** is key — without it, the refresh takes an ACCESS EXCLUSIVE lock that blocks all reads. With CONCURRENTLY, the old data remains readable while the new data is being computed, and the swap is atomic. The tradeoff: CONCURRENTLY requires a unique index and is slightly slower.

### Trade-offs: When to Materialize

| Approach | When to Use |
|----------|------------|
| **Raw query** | Data freshness is critical (real-time), query is fast enough (<100ms), or data is small |
| **Materialized view** | Query is expensive (>1s), data can be 5-15 minutes stale, dashboard/reporting use case |
| **Application cache** | Need sub-millisecond reads, willing to manage cache invalidation |
| **Streaming aggregation** | Need real-time aggregates at high throughput (Kafka + materialized view via ksqlDB/Flink) |

For TicketPulse's analytics dashboard, a materialized view refreshed every 5 minutes is the right trade-off. The dashboard doesn't need real-time accuracy — seeing revenue from 5 minutes ago is fine.

---

> **What did you notice?** The cohort retention query uses four CTEs that build on each other like pipeline stages. Compare this to how you would have computed the same thing in application code. Which is more maintainable?

## 🏁 Module Summary

| Pattern | When to Use | TicketPulse Example |
|---------|------------|-------------------|
| **Window functions** | Running totals, rolling averages, rankings | Revenue trends by venue |
| **LAG/LEAD** | Row-to-row comparison (day-over-day, MoM) | Daily revenue change |
| **NTILE** | Distribution analysis, percentiles | Event revenue quartiles |
| **CTE** | Break complex queries into named steps | Cohort retention analysis |
| **LATERAL JOIN** | Top N per group | Top 3 events per venue |
| **JSON aggregation** | API-ready nested responses | Complete event summary |
| **Materialized views** | Precompute expensive queries | Analytics dashboard |
| **pg_cron** | Schedule recurring database tasks | Dashboard refresh |

**The mindset shift**: Don't fetch raw data and compute in your application. Push computation to the database. It has decades of optimization for exactly these operations.

## What's Next

In **L2-M40: Search Engineering**, you'll add Elasticsearch to TicketPulse so users can search for "jazz concerts in NYC this weekend" with full-text search, filters, and autocomplete.

## Key Terms

| Term | Definition |
|------|-----------|
| **Window function** | A function that performs a calculation across a set of rows related to the current row without collapsing them. |
| **CTE** | Common Table Expression; a named temporary result set defined with WITH that can be referenced in the same query. |
| **LATERAL JOIN** | A PostgreSQL join that allows a subquery to reference columns from preceding tables in the FROM clause. |
| **Materialized view** | A database object that stores the result of a query physically on disk and can be refreshed on demand. |
| **pg_cron** | A PostgreSQL extension that schedules recurring SQL jobs directly inside the database using cron syntax. |

## 📚 Further Reading
- [PostgreSQL Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html)
- [PostgreSQL LATERAL Queries](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-LATERAL)
- Chapter 24 of the 100x Engineer Guide: Section 9 — SQL Mastery
- [Modern SQL: LATERAL](https://modern-sql.com/feature/lateral)
- [pg_cron Documentation](https://github.com/citusdata/pg_cron)

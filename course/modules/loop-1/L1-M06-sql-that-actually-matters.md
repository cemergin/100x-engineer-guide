# L1-M06: SQL That Actually Matters

> **Loop 1 (Foundation)** | Section 1B: Data & Databases | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M05 (PostgreSQL From Zero)
>
> **Source:** Chapters 2, 24 of the 100x Engineer Guide

## What You'll Learn
- Common Table Expressions (CTEs) for readable, composable queries
- Window functions: ROW_NUMBER, running totals, rankings, LAG/LEAD
- Advanced aggregations with GROUP BY, HAVING, and FILTER
- How to build real analytics queries step by step
- The SQL patterns senior engineers use weekly

## Why This Matters
Most engineers learn SELECT, JOIN, and GROUP BY and stop there. They then write application code to do things SQL can handle natively — ranking, running totals, percentage calculations, time-series analysis. This is slower, harder to maintain, and scales worse. The patterns in this module eliminate 80% of the cases where you'd reach for application code.

💡 **Insight:** Window functions were added to the SQL standard in 2003, but most engineers never learn them. They are supported by every major database — Postgres, MySQL 8+, SQLite 3.25+, SQL Server, Oracle. Learn them once, use them everywhere.

## Prereq Check

You need the TicketPulse database from M05 running with sample data loaded.

```bash
# Connect to TicketPulse
docker exec -it ticketpulse-postgres psql -U ticketpulse
```

```sql
-- Verify data exists
SELECT COUNT(*) FROM events;
-- Should return 6
SELECT COUNT(*) FROM tickets;
-- Should return 120
```

If you get errors, go back to L1-M05 and run the schema + sample data scripts.

---

## Part 1: CTEs — Readable, Composable Queries (15 min)

A **Common Table Expression** (CTE) is a named temporary result set that exists for the duration of a single query. Think of it as a named subquery you can reference multiple times.

### Basic CTE Syntax

```sql
WITH cte_name AS (
    SELECT ...
)
SELECT ... FROM cte_name;
```

### Building a Real Query Step by Step

**Goal:** Find the top-selling events this week (well, in our sample data — let's use all time).

Without a CTE, you'd write one massive nested query. With CTEs, we build it in layers:

### 🔍 Try It Now

```sql
-- Step 1: Count sold tickets per event
WITH ticket_sales AS (
    SELECT event_id,
           COUNT(*) AS tickets_sold,
           SUM(price) AS revenue
    FROM tickets
    WHERE status = 'sold'
    GROUP BY event_id
)
SELECT * FROM ticket_sales ORDER BY revenue DESC;
```

Now layer on the event and venue details:

```sql
-- Step 2: Add event and venue info
WITH ticket_sales AS (
    SELECT event_id,
           COUNT(*) AS tickets_sold,
           SUM(price) AS revenue
    FROM tickets
    WHERE status = 'sold'
    GROUP BY event_id
),
event_details AS (
    SELECT e.id,
           e.name AS event_name,
           v.name AS venue_name,
           v.city,
           e.event_date,
           ts.tickets_sold,
           ts.revenue
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN ticket_sales ts ON ts.event_id = e.id
)
SELECT event_name, venue_name, city, event_date,
       tickets_sold, revenue
FROM event_details
ORDER BY revenue DESC;
```

### 🔍 Try It Now: Multiple CTEs

Add a third layer — include the headlining artist:

```sql
WITH ticket_sales AS (
    SELECT event_id,
           COUNT(*) AS tickets_sold,
           SUM(price) AS revenue
    FROM tickets
    WHERE status = 'sold'
    GROUP BY event_id
),
headliners AS (
    SELECT ea.event_id, a.name AS artist_name
    FROM event_artists ea
    JOIN artists a ON ea.artist_id = a.id
    WHERE ea.is_headliner = true
),
event_summary AS (
    SELECT e.name AS event_name,
           v.name AS venue_name,
           h.artist_name AS headliner,
           e.event_date,
           ts.tickets_sold,
           ts.revenue
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN ticket_sales ts ON ts.event_id = e.id
    LEFT JOIN headliners h ON h.event_id = e.id
)
SELECT * FROM event_summary ORDER BY revenue DESC;
```

**Why CTEs over subqueries:**
- Each step is named and self-documenting
- You can reference a CTE multiple times (subqueries get duplicated)
- Easier to debug — run each CTE independently
- In PostgreSQL 12+, the optimizer can inline CTEs (no performance penalty)

### ⚠️ Common Mistake: CTE Materialization

Before PostgreSQL 12, CTEs were always **materialized** — computed once and stored in a temp table, creating an optimization fence. The planner could not push predicates into them.

```sql
-- Pre-PG12: this CTE blocks the planner from using an index on status
WITH all_tickets AS (
    SELECT * FROM tickets
)
SELECT * FROM all_tickets WHERE status = 'available';

-- Post-PG12: the planner inlines the CTE and uses the index
-- To force materialization (old behavior), use:
WITH all_tickets AS MATERIALIZED (
    SELECT * FROM tickets
)
SELECT * FROM all_tickets WHERE status = 'available';
```

In PG 12+, you rarely need to worry about this. But if you see a CTE query performing poorly, check whether materialization is the cause.

---

## Part 2: Window Functions (25 min)

Window functions perform calculations across a set of rows that are related to the current row — without collapsing them into a single output row like GROUP BY does.

### The Core Idea

```sql
-- GROUP BY: 6 events → 6 rows (one per group)
SELECT event_id, COUNT(*) FROM tickets GROUP BY event_id;

-- Window function: 120 tickets → 120 rows (each with its group's count)
SELECT id, event_id, price,
       COUNT(*) OVER (PARTITION BY event_id) AS tickets_in_event
FROM tickets;
```

With GROUP BY, you lose the individual rows. With window functions, you keep every row AND get the aggregate.

### 🔍 Try It Now: ROW_NUMBER

**"Rank events by total revenue per venue"**

```sql
SELECT event_name, venue_name, revenue,
       ROW_NUMBER() OVER (PARTITION BY venue_name ORDER BY revenue DESC) AS rank_in_venue
FROM (
    SELECT e.name AS event_name,
           v.name AS venue_name,
           SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name, v.name
) event_revenue;
```

The `PARTITION BY venue_name` means: restart the numbering for each venue. The `ORDER BY revenue DESC` means: rank by highest revenue first.

### ROW_NUMBER vs RANK vs DENSE_RANK

```sql
-- Imagine these revenues: 500, 300, 300, 100
-- ROW_NUMBER: 1, 2, 3, 4  (always unique, arbitrary tiebreaker)
-- RANK:       1, 2, 2, 4  (ties get same rank, gaps after)
-- DENSE_RANK: 1, 2, 2, 3  (ties get same rank, no gaps)
```

### 🔍 Try It Now: Running Totals

**"Show daily revenue with a running total"**

First, let's create some daily revenue data from our orders:

```sql
WITH daily_revenue AS (
    SELECT DATE(o.ordered_at) AS order_date,
           SUM(oi.price_at_purchase) AS revenue,
           COUNT(DISTINCT o.id) AS num_orders
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE o.status = 'confirmed'
    GROUP BY DATE(o.ordered_at)
)
SELECT order_date,
       revenue,
       num_orders,
       SUM(revenue) OVER (ORDER BY order_date) AS running_total,
       SUM(num_orders) OVER (ORDER BY order_date) AS cumulative_orders
FROM daily_revenue
ORDER BY order_date;
```

The `SUM(...) OVER (ORDER BY order_date)` says: for each row, sum all values from the first row up to and including the current row. That's a running total.

### 🔍 Try It Now: LAG and LEAD

**"Show each order's revenue compared to the previous order"**

```sql
WITH daily_revenue AS (
    SELECT DATE(o.ordered_at) AS order_date,
           SUM(oi.price_at_purchase) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE o.status = 'confirmed'
    GROUP BY DATE(o.ordered_at)
)
SELECT order_date,
       revenue,
       LAG(revenue) OVER (ORDER BY order_date) AS prev_day_revenue,
       revenue - LAG(revenue) OVER (ORDER BY order_date) AS day_over_day_change
FROM daily_revenue
ORDER BY order_date;
```

`LAG(revenue)` looks at the previous row's revenue. `LEAD(revenue)` looks at the next row's. Both return NULL when there is no previous/next row.

### 🔍 Try It Now: Percentage of Total

**"What percentage of total revenue does each event represent?"**

```sql
SELECT e.name AS event_name,
       SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue,
       ROUND(
           SUM(t.price) FILTER (WHERE t.status = 'sold') * 100.0 /
           SUM(SUM(t.price) FILTER (WHERE t.status = 'sold')) OVER (),
           1
       ) AS pct_of_total
FROM events e
JOIN tickets t ON t.event_id = e.id
GROUP BY e.id, e.name
ORDER BY revenue DESC;
```

The `SUM(...) OVER ()` with no PARTITION BY and no ORDER BY means: sum across ALL rows. This gives you the grand total that you divide each event's revenue by.

### Window Function Frame Clause

The default frame for `SUM() OVER (ORDER BY ...)` is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — which means "from the start up to now." You can customize this:

```sql
-- 3-event moving average of revenue
SELECT event_name, revenue,
       ROUND(AVG(revenue) OVER (
           ORDER BY revenue DESC
           ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
       ), 2) AS moving_avg_3
FROM (
    SELECT e.name AS event_name,
           SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
    FROM events e
    JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name
) er;
```

| Frame | Meaning |
|-------|---------|
| `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` | All rows from start to here |
| `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` | Last 7 rows (7-day moving average) |
| `ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING` | Previous, current, and next row |
| `ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING` | Current row to end |

---

## Part 3: Advanced Aggregations (10 min)

### FILTER Clause

The `FILTER` clause is a PostgreSQL extension that replaces clunky `CASE WHEN` expressions in aggregations:

```sql
-- Old way (works everywhere but ugly)
SELECT event_id,
       COUNT(CASE WHEN status = 'sold' THEN 1 END) AS sold,
       COUNT(CASE WHEN status = 'available' THEN 1 END) AS available

-- PostgreSQL way (cleaner)
SELECT event_id,
       COUNT(*) FILTER (WHERE status = 'sold') AS sold,
       COUNT(*) FILTER (WHERE status = 'available') AS available
FROM tickets
GROUP BY event_id;
```

### 🔍 Try It Now: Event Dashboard

```sql
SELECT e.name,
       COUNT(*) AS total_tickets,
       COUNT(*) FILTER (WHERE t.status = 'sold') AS sold,
       COUNT(*) FILTER (WHERE t.status = 'available') AS available,
       COUNT(*) FILTER (WHERE t.status = 'reserved') AS reserved,
       SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue,
       ROUND(
           COUNT(*) FILTER (WHERE t.status = 'sold') * 100.0 / COUNT(*),
           1
       ) AS sell_through_pct
FROM events e
JOIN tickets t ON t.event_id = e.id
GROUP BY e.id, e.name
ORDER BY revenue DESC NULLS LAST;
```

### HAVING vs WHERE

```sql
-- WHERE filters individual rows BEFORE grouping
-- HAVING filters groups AFTER aggregation

-- "Events with more than 10 sold tickets"
SELECT e.name, COUNT(*) FILTER (WHERE t.status = 'sold') AS sold
FROM events e
JOIN tickets t ON t.event_id = e.id
GROUP BY e.id, e.name
HAVING COUNT(*) FILTER (WHERE t.status = 'sold') > 10;
```

### GROUPING SETS

When you need multiple levels of aggregation in one query:

```sql
-- Revenue by venue AND by status, plus totals
SELECT COALESCE(v.name, '** ALL VENUES **') AS venue,
       COALESCE(t.status, '** ALL **') AS ticket_status,
       COUNT(*) AS count,
       SUM(t.price) AS total_value
FROM tickets t
JOIN events e ON t.event_id = e.id
JOIN venues v ON e.venue_id = v.id
GROUP BY GROUPING SETS (
    (v.name, t.status),   -- per venue + status
    (v.name),             -- per venue subtotal
    ()                    -- grand total
)
ORDER BY venue NULLS LAST, ticket_status NULLS LAST;
```

---

## Part 4: Build 5 Analytics Queries (20 min)

Now it's your turn. Write these 5 queries against the TicketPulse database. Each one uses concepts from this module. Try writing them yourself before checking the solution.

### 🛠️ Your Turn

**Query 1: "Event Revenue Leaderboard"**
Show each event with its venue, headlining artist, tickets sold, total revenue, and rank by revenue (using ROW_NUMBER). Only include events with at least 1 sold ticket.

<details>
<summary>Solution</summary>

```sql
WITH event_revenue AS (
    SELECT e.id AS event_id,
           e.name AS event_name,
           v.name AS venue_name,
           COUNT(*) FILTER (WHERE t.status = 'sold') AS tickets_sold,
           SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name, v.name
    HAVING COUNT(*) FILTER (WHERE t.status = 'sold') > 0
),
headliners AS (
    SELECT ea.event_id, a.name AS headliner
    FROM event_artists ea
    JOIN artists a ON ea.artist_id = a.id
    WHERE ea.is_headliner = true
)
SELECT er.event_name,
       er.venue_name,
       h.headliner,
       er.tickets_sold,
       er.revenue,
       ROW_NUMBER() OVER (ORDER BY er.revenue DESC) AS rank
FROM event_revenue er
LEFT JOIN headliners h ON h.event_id = er.event_id
ORDER BY rank;
```

</details>

**Query 2: "Customer Spending Summary"**
For each customer, show their total spending, number of orders, average order value, and their rank among all customers by total spending. Use a window function for the rank.

<details>
<summary>Solution</summary>

```sql
WITH customer_spending AS (
    SELECT o.customer_name,
           o.customer_email,
           COUNT(DISTINCT o.id) AS num_orders,
           SUM(oi.price_at_purchase) AS total_spent,
           ROUND(AVG(oi.price_at_purchase), 2) AS avg_item_price
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE o.status = 'confirmed'
    GROUP BY o.customer_name, o.customer_email
)
SELECT customer_name,
       num_orders,
       total_spent,
       avg_item_price,
       RANK() OVER (ORDER BY total_spent DESC) AS spending_rank
FROM customer_spending
ORDER BY spending_rank;
```

</details>

**Query 3: "Venue Utilization Report"**
For each venue, show the number of events, total ticket capacity (tickets created), tickets sold, sell-through percentage, and total revenue. Rank venues by sell-through percentage.

<details>
<summary>Solution</summary>

```sql
SELECT v.name AS venue,
       v.city,
       v.capacity AS venue_capacity,
       COUNT(DISTINCT e.id) AS num_events,
       COUNT(t.id) AS total_tickets,
       COUNT(t.id) FILTER (WHERE t.status = 'sold') AS tickets_sold,
       ROUND(
           COUNT(t.id) FILTER (WHERE t.status = 'sold') * 100.0 /
           NULLIF(COUNT(t.id), 0),
           1
       ) AS sell_through_pct,
       COALESCE(SUM(t.price) FILTER (WHERE t.status = 'sold'), 0) AS revenue,
       DENSE_RANK() OVER (
           ORDER BY COUNT(t.id) FILTER (WHERE t.status = 'sold') * 100.0 /
                    NULLIF(COUNT(t.id), 0) DESC NULLS LAST
       ) AS utilization_rank
FROM venues v
LEFT JOIN events e ON e.venue_id = v.id
LEFT JOIN tickets t ON t.event_id = e.id
GROUP BY v.id, v.name, v.city, v.capacity
ORDER BY utilization_rank;
```

</details>

**Query 4: "Order Timeline with Running Revenue"**
Show all confirmed orders in chronological order, with a running total of revenue and the day-over-day change.

<details>
<summary>Solution</summary>

```sql
WITH order_revenue AS (
    SELECT o.id AS order_id,
           o.customer_name,
           DATE(o.ordered_at) AS order_date,
           SUM(oi.price_at_purchase) AS order_total
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE o.status = 'confirmed'
    GROUP BY o.id, o.customer_name, o.ordered_at
)
SELECT order_date,
       customer_name,
       order_total,
       SUM(order_total) OVER (ORDER BY order_date, order_id) AS running_revenue,
       order_total - LAG(order_total) OVER (ORDER BY order_date, order_id) AS change_from_prev
FROM order_revenue
ORDER BY order_date, order_id;
```

</details>

**Query 5: "Artist Popularity Dashboard"**
For each artist, show: number of events they play, how many are as headliner vs support, total tickets sold across all their events, and their percentage of all ticket sales platform-wide.

<details>
<summary>Solution</summary>

```sql
WITH artist_events AS (
    SELECT a.id AS artist_id,
           a.name AS artist_name,
           a.genre,
           COUNT(*) AS num_events,
           COUNT(*) FILTER (WHERE ea.is_headliner) AS headliner_count,
           COUNT(*) FILTER (WHERE NOT ea.is_headliner) AS support_count
    FROM artists a
    JOIN event_artists ea ON ea.artist_id = a.id
    GROUP BY a.id, a.name, a.genre
),
artist_ticket_sales AS (
    SELECT ea.artist_id,
           COUNT(*) FILTER (WHERE t.status = 'sold') AS tickets_sold,
           SUM(t.price) FILTER (WHERE t.status = 'sold') AS revenue
    FROM event_artists ea
    JOIN tickets t ON t.event_id = ea.event_id
    GROUP BY ea.artist_id
)
SELECT ae.artist_name,
       ae.genre,
       ae.num_events,
       ae.headliner_count,
       ae.support_count,
       COALESCE(ats.tickets_sold, 0) AS tickets_sold,
       COALESCE(ats.revenue, 0) AS revenue,
       ROUND(
           COALESCE(ats.revenue, 0) * 100.0 /
           NULLIF(SUM(COALESCE(ats.revenue, 0)) OVER (), 0),
           1
       ) AS pct_of_total_revenue
FROM artist_events ae
LEFT JOIN artist_ticket_sales ats ON ats.artist_id = ae.artist_id
ORDER BY revenue DESC;
```

</details>

---

## 🏁 Module Summary

You now know the SQL patterns that separate junior from senior engineers:

| Pattern | What It Does | When to Use |
|---------|-------------|-------------|
| **CTEs** | Named, composable query steps | Complex queries with multiple logical steps |
| **ROW_NUMBER** | Unique rank within a partition | Top-N per group, pagination |
| **RANK / DENSE_RANK** | Rank with tie handling | Leaderboards, percentile calculations |
| **Running totals** | `SUM() OVER (ORDER BY ...)` | Cumulative metrics, time series |
| **LAG / LEAD** | Access previous/next row | Day-over-day changes, trend detection |
| **FILTER** | Conditional aggregation | Pivot-style reports, dashboards |
| **HAVING** | Filter after grouping | "Show groups where count > N" |
| **GROUPING SETS** | Multiple aggregation levels | Reports needing subtotals and grand totals |

**Key takeaway:** If you find yourself fetching raw data and computing aggregations in Python/JavaScript/Go, stop and check whether a window function or CTE can do it in SQL. The database is almost always faster.

## What's Next

In **L1-M07: Indexing & Query Performance**, you'll learn why some of these queries are fast and others are slow — and how to make the slow ones 100x faster with the right indexes.

## Key Terms

| Term | Definition |
|------|-----------|
| **CTE** | Common Table Expression; a named temporary result set defined with WITH that can be referenced within a query. |
| **Window function** | A function that performs a calculation across a set of rows related to the current row without collapsing them. |
| **Aggregate** | A function (e.g., COUNT, SUM, AVG) that computes a single result from a set of input rows. |
| **GROUP BY** | An SQL clause that groups rows sharing a value so aggregate functions can be applied to each group. |
| **HAVING** | An SQL clause that filters groups produced by GROUP BY based on aggregate conditions. |

## 📚 Further Reading
- [PostgreSQL Window Functions Documentation](https://www.postgresql.org/docs/current/tutorial-window.html)
- [Modern SQL — Window Functions](https://modern-sql.com/feature/window-functions)
- Chapter 24 of the 100x Engineer Guide: Section 9 — SQL Mastery
- [Select Star SQL](https://selectstarsql.com/) — Free interactive SQL tutorial

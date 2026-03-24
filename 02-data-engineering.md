<!--
  CHAPTER: 2
  TITLE: Data Engineering Paradigms
  PART: I — Foundations
  PREREQS: Chapter 1
  KEY_TOPICS: database paradigms, SQL, NoSQL, NewSQL, data modeling, indexing, caching, ETL/ELT, CDC, data mesh, consistency patterns
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 2: Data Engineering Paradigms

> **Part I — Foundations** | Prerequisites: Chapter 1 | Difficulty: Intermediate to Advanced

How to choose, model, query, cache, and pipe data — the storage and retrieval layer that underpins every application.

### In This Chapter
- Database Paradigms
- Data Modeling
- Query Optimization
- Data Pipeline Architectures
- Caching Strategies
- Data Consistency Patterns

### Related Chapters
- [Ch 1: System Design Paradigms & Philosophies] — consistency models
- [Ch 3: Software Architecture Patterns] — CQRS/event sourcing bridges architecture and data
- [Ch 13: Cloud Databases] — cloud databases in practice

---

## 1. DATABASE PARADIGMS

### 1.1 Relational Databases (RDBMS)

**ACID Properties:**
- **Atomicity:** All-or-nothing transactions
- **Consistency:** Every transaction moves DB from one valid state to another
- **Isolation:** Concurrent transactions behave as serial (levels: Read Uncommitted → Read Committed → Repeatable Read → Serializable)
- **Durability:** Committed data survives crashes (via WAL)

**Normalization (1NF–5NF):** Reduce redundancy, prevent update anomalies.
**Denormalization:** Deliberate redundancy for read performance. Trade-off: write amplification and inconsistency risk.

**Examples:** PostgreSQL (dominant choice), MySQL/MariaDB, Oracle, SQL Server.

### 1.2 NoSQL Databases

| Type | Examples | Use Case | Trade-off |
|---|---|---|---|
| **Document** | MongoDB, Couchbase, Firestore | Heterogeneous schemas, content management | No joins; denormalization is the norm |
| **Key-Value** | Redis, DynamoDB, etcd | Session storage, caching, rate limiting | No secondary indexes natively |
| **Column-Family** | Cassandra, HBase, ScyllaDB | Time-series, write-heavy at massive scale | Limited query model; design tables around queries |
| **Graph** | Neo4j, Neptune, TigerGraph | Social networks, fraud detection, knowledge graphs | Scaling horizontally is harder |
| **Time-Series** | InfluxDB, TimescaleDB, ClickHouse | Metrics, IoT, financial tick data | Limited general-purpose queries |

### 1.3 NewSQL
ACID + horizontal scalability. Examples: CockroachDB, Google Spanner, YugabyteDB, TiDB.
**Trade-off:** Higher per-transaction latency than single-node RDBMS.

### 1.4 Multi-Model Databases
Single engine, multiple models. PostgreSQL with jsonb is the pragmatic choice.

---

## 2. DATA MODELING

### 2.1 Entity-Relationship Modeling
Entities → attributes → relationships → normalize to 3NF → selectively denormalize.

### 2.2 Star and Snowflake Schema
**Star:** Central fact table + denormalized dimensions. Default for OLAP.
**Snowflake:** Normalized dimensions. More joins, less storage.

### 2.3 Data Vault
Hubs (business keys) + Links (relationships) + Satellites (attributes with history). For auditable enterprise warehouses.

### 2.4 Event Sourcing
Store events, not state. Current state = replay of events.
**Trade-offs:** Complete audit trail, temporal queries, but eventual consistency, schema evolution complexity, GDPR challenges.

### 2.5 CQRS
Separate write model (commands) from read model (queries). Often paired with event sourcing.
**Trade-offs:** Independent scaling, but increased complexity and eventual consistency.

### 2.6 Polyglot Persistence
Different databases for different access patterns. Requires explicit coordination (Saga, outbox, CDC).

---

## 3. QUERY OPTIMIZATION

### 3.1 Indexing Strategies

| Index Type | Supports | Use Case |
|---|---|---|
| **B-Tree** | Equality, range, ORDER BY, prefix | Default; most queries |
| **Hash** | Equality only | High-cardinality equality lookups |
| **Bitmap** | Low-cardinality AND/OR | OLAP, data warehouses |
| **GIN** | Full-text, JSONB, arrays | Search, document queries |
| **GiST** | Geometric, range, nearest-neighbor | Geospatial (PostGIS), time ranges |

**Composite index key ordering matters:** Leftmost prefix rule.

### 3.2 The N+1 Problem
1 query for parents + N queries for children = N+1 total.
**Solutions:** JOIN, batch loading (IN clause), ORM eager loading, DataLoader pattern.

### 3.3 Materialized Views
Precomputed query results. Must be refreshed. Great for dashboards and reports.

### 3.4 Read Replicas
Scale read throughput. Watch for replication lag. Route reads-after-writes to primary.

### 3.5 Connection Pooling
PgBouncer, HikariCP. Transaction pooling is most common. Breaks session-level features.

---

## 4. DATA PIPELINE ARCHITECTURES

### 4.1 ETL vs ELT
- **ETL:** Transform before load. For sensitive data or limited warehouse compute.
- **ELT:** Load raw, transform in warehouse (dbt). For modern cloud warehouses (BigQuery, Snowflake).

### 4.2 Batch vs Stream Processing
- **Batch:** Spark, dbt, Airflow. Minutes-to-hours latency. Simpler.
- **Stream:** Kafka Streams, Flink. Sub-second latency. More complex (late data, ordering, state).

### 4.3 Lambda Architecture
Batch layer + speed layer + serving layer. Two codebases for same logic.

### 4.4 Kappa Architecture
Everything is a stream. Replay for reprocessing. Single codebase.

### 4.5 CDC (Change Data Capture)
Capture row-level changes from transaction logs. Tools: Debezium, AWS DMS.
**Use for:** Microservice sync, warehouse feeding, event-driven architectures.

### 4.6 Data Mesh
Domain-oriented ownership, data as a product, self-serve platform, federated governance.

### 4.7 Data Lakehouse
Data lake storage (S3/Parquet) + ACID transactions. Delta Lake, Apache Iceberg, Apache Hudi.

---

## 5. CACHING STRATEGIES

| Pattern | How It Works | When to Use |
|---|---|---|
| **Cache-Aside** | App checks cache, loads from DB on miss | General purpose, most common |
| **Write-Through** | Write to cache + DB synchronously | Read-after-write consistency critical |
| **Write-Behind** | Write to cache, async flush to DB | Write-heavy, batch DB writes |
| **Read-Through** | Cache loads from DB on miss (cache manages it) | Encapsulate cache-loading logic |

### Cache Invalidation Strategies
- **TTL:** Simplest. Set based on staleness tolerance.
- **Event-driven:** Publish events on data change. Near-real-time consistency.
- **Version-based:** Include version in cache key.
- **Tag-based:** Invalidate all entries with a given tag.

### Cache Stampede Prevention
- **Locking:** First miss acquires lock, others wait.
- **Probabilistic early expiration (XFetch):** Refresh before TTL with increasing probability.
- **Background refresh:** Pre-refresh hot keys.
- **Stale-while-revalidate:** Serve stale, refresh async.

### Multi-Tier Caching
L1 (in-process, μs) → L2 (distributed/Redis, sub-ms) → L3 (CDN/edge).

---

## 6. DATA CONSISTENCY PATTERNS

### The Dual Writes Problem
Writing to DB + message broker has no atomic guarantee. **Never do dual writes.**

### The Outbox Pattern
Write to DB + outbox table in same transaction. Relay process publishes from outbox.

### The Saga Pattern
Sequence of local transactions with compensating actions. Choreography or orchestration.

### Idempotent Consumers
Store processed event IDs. Natural idempotency. Conditional updates.

### Exactly-Once Semantics
True exactly-once is impossible. Use at-least-once + idempotent processing.

---

## Decision Heuristics

| Decision | Default | Alternative When |
|---|---|---|
| Database | PostgreSQL | Horizontal write scaling (CockroachDB), sub-ms lookups (Redis), graphs (Neo4j), time-series (TimescaleDB) |
| Modeling | 3NF for OLTP, Star for OLAP | Audit trail (Data Vault), event-driven (Event Sourcing) |
| Pipeline | ELT with dbt | Real-time (streaming), sensitive data (ETL) |
| Caching | Cache-aside with TTL | Write-heavy (write-behind), strict consistency (write-through) |
| Consistency | Outbox + idempotent consumers | Simple flows (choreography saga), complex flows (orchestration saga) |

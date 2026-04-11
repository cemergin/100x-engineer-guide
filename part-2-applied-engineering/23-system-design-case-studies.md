<!--
  CHAPTER: 23
  TITLE: System Design Case Studies
  PART: II — Applied Engineering
  PREREQS: Chapters 1, 2, 3
  KEY_TOPICS: URL shortener, rate limiter, chat system, notification system, news feed, search, distributed cache, payment system, video streaming, ride-sharing, web crawler
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 23: System Design Case Studies

> **Part II — Applied Engineering** | Prerequisites: Chapters 1, 2, 3 | Difficulty: Advanced

Okay. Let's design some systems together.

Not in the abstract, hand-wavy "just throw Kafka at it" way. In the real way — where you sit down with a blank whiteboard, someone says "build a URL shortener," and three minutes later you're arguing about whether to use a counter or a hash, whether 301 or 302 matters, and why the analytics pipeline can't touch the redirect path. That way.

Each case study in this chapter is a design session, not a lecture. You'll feel the moment where a "simple" system gets complicated. You'll see the tradeoffs emerge naturally. By the end, you won't just remember these designs — you'll understand *why* every decision was made, and you'll be able to adapt them when the requirements change on you.

Ten systems. Let's go.

### In This Chapter
- The System Design Framework
- Case Study: URL Shortener
- Case Study: Rate Limiter
- Case Study: Chat System
- Case Study: Notification System
- Case Study: News Feed / Timeline
- Case Study: Search Autocomplete
- Case Study: Distributed Cache
- Case Study: Payment System
- Case Study: Video Streaming Platform
- Case Study: Ride-Sharing Service

### Related Chapters
- **DATABASE spiral:** ← [Ch 24b: SQL Mastery](../part-1-foundations/24b-sql-mastery-graph-databases.md) | → [Ch 18: Debugging & Monitoring](../part-4-cloud-operations/18-debugging-profiling-monitoring.md)
- **ARCHITECTURE spiral:** ← [Ch 34: Specs, RFCs & ADRs](../part-3-tooling-practice/34-specs-rfcs-adrs.md) | → [Ch 1: System Design Paradigms](../part-1-foundations/01-system-design.md)
- Ch 1 (distributed systems theory — CAP theorem, consistency models)
- Ch 2 (database selection and modeling)
- Ch 3 (architecture patterns)
- Ch 13 (cloud integration)
- Ch 22 (algorithms behind these systems)

---

## 0. The System Design Framework

Before diving into case studies, let's agree on a framework. Every single design in this chapter follows the same seven-step structure. Internalize it and you can design any system under pressure — in an interview, in a production incident, or when your manager walks over and says "we need to build this by Friday."

The framework isn't a checklist you race through. It's a discipline that keeps you from jumping to solutions before you understand the problem.

### Step 1: Requirements Clarification

Before drawing a single box, ask questions. Split requirements into two buckets:

**Functional Requirements (FR):** What does the system *do*? User-facing features, core operations, edge cases.

**Non-Functional Requirements (NFR):** How does the system *behave*? Latency, availability, consistency, durability, scale.

> **Rule of thumb:** Spend 5 minutes on requirements in a 45-minute interview. In production, spend 5 days.

The most important question is almost always: "What consistency guarantees does this need?" (You covered this in Ch 1 with the CAP theorem — CP vs. AP is rarely obvious from the requirements, but it changes everything downstream.)

### Step 2: Capacity Estimation (Back-of-Envelope Math)

Derive these numbers from your requirements:

| Metric | Formula |
|--------|---------|
| **DAU** | Given or estimated |
| **QPS (avg)** | DAU x actions_per_user / 86,400 |
| **QPS (peak)** | QPS_avg x 2-5 (depends on traffic pattern) |
| **Storage/year** | objects_per_day x object_size x 365 |
| **Bandwidth** | QPS x avg_response_size |
| **Memory (cache)** | Follow the 80/20 rule — cache 20% of daily traffic |

Useful constants:
- 1 day = ~86,400 seconds (~10^5)
- 1 year = ~31.5 million seconds (~3 x 10^7)
- 1 million requests/day ~ 12 QPS
- 1 KB x 1 billion = 1 TB
- 1 char = 1 byte (ASCII), 2-4 bytes (UTF-8 extended)

Don't obsess over precision here. The goal is to catch order-of-magnitude mistakes — the difference between "fits in one Redis node" and "needs a 20-node cluster." That difference changes your entire architecture.

### Step 3: API Design

Define the external contract. For each endpoint:
- HTTP method + path
- Request parameters / body
- Response shape
- Authentication / rate limiting notes

### Step 4: Data Model

Choose the database(s) and define schemas. Justify why — and revisit Ch 2 if you're not sure. The database choice is one of the highest-leverage decisions in any design.

- **Relational (PostgreSQL):** Strong consistency, complex queries, transactions
- **Document (MongoDB):** Flexible schema, denormalized reads
- **Wide-column (Cassandra):** Write-heavy, time-series, massive scale
- **Key-value (Redis/DynamoDB):** Low-latency lookups, caching, counters
- **Search (Elasticsearch):** Full-text search, autocomplete
- **Graph (Neo4j):** Relationship-heavy queries

### Step 5: High-Level Architecture

Draw the boxes and arrows. Every architecture should show:
- Client layer
- Load balancer / API gateway
- Application servers
- Caches
- Databases (primary + replicas)
- Message queues (if async processing)
- Third-party services

### Step 6: Deep Dive

Pick 2-3 scaling bottlenecks and go deep:
- What breaks first as traffic grows 10x? 100x?
- How do you shard the data?
- Where do you add caching?
- What happens during a failure?
- How do you handle hot keys / thundering herd / split brain?

### Step 7: Monitoring & Alerting

A system you cannot observe is a system you cannot operate. Define:
- **Health checks:** Is the service alive?
- **Business metrics:** Conversion rate, success rate, latency percentiles
- **Infrastructure metrics:** CPU, memory, disk, queue depth
- **Alerts:** What thresholds trigger a page?

---

## 1. URL Shortener (like Bit.ly)

Okay, we need to build a URL shortener. Sounds simple, right? Take a long URL, give back a short one. How hard can it be?

Let me show you how fast it gets interesting.

The obvious first question: how do you generate the short code? You might think "just hash the URL." And that works — until two different URLs produce the same hash prefix. Now you need collision detection. And retry logic. And suddenly your "simple" write path has a retry loop. That's just the first problem.

Then there's analytics. Users want click counts. But if you increment a counter on every redirect, you're writing to the database on every read — and reads are 10x more frequent than writes. How do you track clicks without slowing down redirects? The answer changes your entire architecture.

And what about 301 vs. 302? That seemingly trivial HTTP decision has massive implications for CDN caching, analytics accuracy, and SEO. By the end of this design, you'll have a strong opinion about it.

> **The moment it gets hard:** Generating short codes at scale without collisions, across multiple servers, with no coordination bottleneck.

### Requirements

**Functional:**
- Given a long URL, generate a short unique alias (e.g., `sho.rt/abc123`)
- Redirecting a short URL to the original long URL (HTTP 301/302)
- Custom short links (optional)
- Link expiration (configurable TTL)
- Analytics: click count, referrer, geography

**Non-Functional:**
- 100M new URLs/month; 10:1 read-to-write ratio
- Redirect latency < 50 ms (p99)
- 99.99% availability (redirects must not fail)
- Short URLs should be as short as possible
- URLs are immutable once created

### Capacity Estimation

```
Writes:
  100M URLs/month = ~3.3M/day = ~40 writes/sec (avg)
  Peak: ~200 writes/sec

Reads (10:1 ratio):
  1B redirects/month = ~33M/day = ~400 reads/sec (avg)
  Peak: ~2,000 reads/sec

Storage (5-year horizon):
  Each record: short_url (7B) + long_url (200B avg) + metadata (100B) = ~300B
  100M/month x 12 x 5 = 6B records
  6B x 300B = 1.8 TB

Cache (80/20 rule):
  20% of daily reads: 33M x 0.2 = 6.6M entries
  6.6M x 300B = ~2 GB (fits in a single Redis node)

Bandwidth:
  Reads: 400 QPS x 300B = 120 KB/s (negligible)
```

Notice something: the reads are completely manageable. 400 QPS is not a lot. The challenge isn't volume — it's latency. Every redirect needs to be fast. That shapes everything.

### API Design

```
POST /api/v1/urls
  Headers: Authorization: Bearer <token>
  Body: { "long_url": "https://...", "custom_alias": "mylink", "ttl_days": 30 }
  Response: { "short_url": "https://sho.rt/abc123", "expires_at": "..." }
  Rate limit: 100 req/min per user

GET /{short_code}
  Response: HTTP 301 Location: <long_url>
  (No auth required)

GET /api/v1/urls/{short_code}/stats
  Headers: Authorization: Bearer <token>
  Response: { "clicks": 12345, "created_at": "...", "top_referrers": [...] }
```

Notice the read endpoint returns a plain HTTP redirect — no JSON, no body. The client never even touches our application layer for the content. It just follows the redirect. Speed is the whole point.

### Data Model

**Database: PostgreSQL** (strong consistency for writes) + **Redis** (cache for reads)

We choose PostgreSQL here because URL creation needs ACID guarantees — specifically, we need the `UNIQUE` constraint on `short_code` to prevent duplicates. As you saw in Ch 2, relational databases give you that for free.

```sql
-- URLs table
CREATE TABLE urls (
    id            BIGSERIAL PRIMARY KEY,
    short_code    VARCHAR(10) UNIQUE NOT NULL,
    long_url      TEXT NOT NULL,
    user_id       BIGINT REFERENCES users(id),
    created_at    TIMESTAMP DEFAULT NOW(),
    expires_at    TIMESTAMP,
    click_count   BIGINT DEFAULT 0
);
CREATE INDEX idx_short_code ON urls(short_code);

-- Click analytics (append-only, partitioned by month)
CREATE TABLE clicks (
    id            BIGSERIAL,
    short_code    VARCHAR(10) NOT NULL,
    clicked_at    TIMESTAMP DEFAULT NOW(),
    ip_address    INET,
    user_agent    TEXT,
    referrer      TEXT,
    country       VARCHAR(2)
) PARTITION BY RANGE (clicked_at);
```

The `clicks` table is intentionally separate from `urls`. Never update `click_count` on every redirect — that's a write on every read, and at 2,000 peak reads/sec it becomes a bottleneck. We'll handle counts asynchronously.

### High-Level Architecture

```
                         ┌─────────────┐
                         │   Clients   │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │  CloudFlare │
                         │     CDN     │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ API Gateway │
                         │ (rate limit)│
                         └──────┬──────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
          ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
          │  Write Svc  │ │ Read Svc │ │Analytics Svc│
          │  (create)   │ │(redirect)│ │  (stats)    │
          └──────┬──────┘ └────┬─────┘ └──────┬──────┘
                 │             │              │
                 │        ┌────▼─────┐        │
                 │        │  Redis   │        │
                 │        │  Cache   │        │
                 │        └────┬─────┘        │
                 │             │              │
                 └──────┬──────┘              │
                        │                     │
                 ┌──────▼──────┐       ┌──────▼──────┐
                 │ PostgreSQL  │       │   Kafka     │
                 │  (primary)  │       │ (click log) │
                 └──────┬──────┘       └──────┬──────┘
                        │                     │
                 ┌──────▼──────┐       ┌──────▼──────┐
                 │  Read       │       │ ClickHouse  │
                 │  Replicas   │       │ (analytics) │
                 └─────────────┘       └─────────────┘
```

Three separate services for three very different workloads. The read service (redirect) is purely latency-sensitive. The write service (create) needs correctness. The analytics service runs asynchronously and nobody cares if it's a few seconds behind.

### Deep Dive

**1. Short Code Generation: Hash vs. Counter**

Here's where it gets interesting. You have three real options:

| Approach | Pros | Cons |
|----------|------|------|
| **MD5/SHA256 hash + truncate** | No coordination needed | Collisions require retries; longer codes |
| **Base62 counter (auto-increment)** | No collisions, predictable length | Sequential = guessable; single point of coordination |
| **Pre-generated ID range** | No runtime collision; distributed | Requires a range allocator service |

The hash approach sounds elegant until you hit a collision at 100M+ entries — and then your write path needs retry logic, and that retry might loop. Not great.

The simple counter is tempting but sequential IDs are guessable: if someone gets `abc123`, they can try `abc124`. And you have a single coordinating database that all servers hammer.

**Chosen approach: Range-based counter.** A ZooKeeper/etcd coordinator assigns each app server a range (e.g., server A gets 1M-2M, server B gets 2M-3M). Each server increments locally and converts to Base62. No collisions, no runtime coordination, 7 chars supports 62^7 = 3.5 trillion URLs.

```
Base62 encoding: [0-9a-zA-Z]
ID 1000000 -> base62 -> "4c92"
ID 3521614606208 -> base62 -> "zzzzzz" (6 chars, ~3.5T IDs)
```

**2. Read Path Optimization**

The redirect is latency-critical. < 50 ms p99 means every millisecond counts. Think of the read path as layers:

1. **CDN caching:** Popular short URLs are cached at the edge. Set `Cache-Control: public, max-age=3600` for 301 redirects.
2. **Redis cache:** On cache miss from CDN, check Redis. 2 GB cache covers 20% of daily traffic (80/20 rule handles the rest).
3. **Database read replicas:** On Redis miss, query a read replica. Only the write path hits the primary.

This is the layered caching pattern you saw in Ch 3. The goal is that 80%+ of requests never reach the database at all.

Cache invalidation is simple here: URLs are immutable once created. Only expiration requires eviction — use Redis TTL and you're done.

**3. 301 vs. 302: The Redirect Decision**

This is a deceptively important choice.

- **301 (Permanent Redirect):** Browsers and CDNs cache it. Future visits go directly to the long URL without hitting your servers. Great for latency, terrible for analytics — you'll never see those cached hits.
- **302 (Temporary Redirect):** Not cached. Every click goes through your redirect server. Great for analytics, costs you the caching optimization.

If analytics matter, use 302. If you want maximum speed and CDN offloading, use 301. Most production URL shorteners use 302 because click data is the product.

**4. Analytics Pipeline**

Click tracking must not slow down redirects. Fire-and-forget approach:

1. Read service publishes a click event to Kafka (async, non-blocking).
2. A consumer writes aggregated counts to ClickHouse every 10 seconds.
3. `click_count` in PostgreSQL is updated via a periodic batch job (not on every click).

The redirect returns in < 50 ms. Kafka gets the event a few milliseconds later. ClickHouse processes it a few seconds after that. Eventually consistent analytics is completely fine — nobody needs real-time click counts.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Base62 counter over hash | Zero collisions, shorter codes | Need a range coordinator (added complexity) |
| 301 (permanent) redirect | CDN caching, lower latency | Cannot track every click (cached at CDN) |
| Async analytics | Redirect latency unaffected | Click counts are eventually consistent (seconds of delay) |
| PostgreSQL over NoSQL | ACID for URL creation | Vertical scaling limit (~50K writes/sec) |

---

## 2. Rate Limiter

You know what nobody thinks about until it's too late? Rate limiting.

Then one day a client's script goes haywire and fires 50,000 requests in a second. Or a competitor starts scraping your API. Or your own internal service has a retry bug that thunders against your database. And suddenly "we should add rate limiting" becomes a war room priority.

Here's the thing: rate limiting sounds like a solved problem. Just count requests per user and reject when they go over the limit. But distribute that across 10 API servers and it immediately gets complicated. If each server counts independently, a user can hit every server at the limit — effectively multiplying their allowed rate by the number of servers. That's not rate limiting, that's chaos.

The real problem is distributed counting with sub-5ms overhead and graceful degradation when the counting system itself fails.

> **The moment it gets hard:** Counting accurately across multiple API servers without adding latency to every request — and deciding what to do when your counting system goes down.

### Requirements

**Functional:**
- Limit API requests per client (by API key, IP, or user ID)
- Configurable rules: X requests per Y seconds per endpoint
- Return `429 Too Many Requests` with `Retry-After` header when limit exceeded
- Support multiple rate-limiting strategies (global, per-endpoint, per-user)

**Non-Functional:**
- Must add < 5 ms latency to each request
- Distributed: works across multiple API servers
- Highly available (if rate limiter fails, allow traffic through — fail open)
- 500K QPS across all API servers
- Accurate counting (minimal over/under-counting)

### Capacity Estimation

```
QPS: 500,000 across all servers
Unique clients: ~1M active API keys
Memory per client: key (50B) + counter (8B) + timestamp (8B) + window (8B) = ~74B
Total memory: 1M x 74B = ~74 MB (easily fits in one Redis node)
Network: 500K QPS x 2 Redis commands (GET+SET) = 1M Redis ops/sec
  -> Need Redis cluster (single node handles ~100K ops/sec)
```

The math is reassuring: the data fits easily in memory. The challenge is throughput — 1M Redis ops/sec is real work.

### API Design

The rate limiter is middleware, not a user-facing API. But it exposes headers — and those headers are the interface your clients depend on for backoff behavior:

```
-- On every response:
X-RateLimit-Limit: 1000          (max requests in window)
X-RateLimit-Remaining: 742       (requests left)
X-RateLimit-Reset: 1679012345    (UTC epoch when window resets)

-- On 429 response:
HTTP/1.1 429 Too Many Requests
Retry-After: 30                  (seconds to wait)
Content-Type: application/json
{ "error": "rate_limit_exceeded", "retry_after": 30 }
```

Good clients use `Retry-After` to implement exponential backoff. Bad clients ignore it and keep hammering. Design for both.

Internal configuration API:

```
PUT /internal/rate-limits/rules
Body: {
  "rule_id": "api_default",
  "limit": 1000,
  "window_seconds": 3600,
  "scope": "per_api_key",
  "endpoints": ["/api/v1/*"]
}
```

### Data Model

**Database: Redis** (in-memory, atomic operations, TTL support)

Redis is the obvious choice here. Fast, atomic operations, built-in TTL. As you saw in Ch 2, key-value stores are the right tool when you need sub-millisecond reads and simple data structures.

```
-- Sliding window log (precise but more memory)
Key:   rate:{client_id}:{endpoint}
Type:  Sorted Set
Score: timestamp (unix ms)
Value: unique request ID

-- Token bucket (simpler)
Key:   bucket:{client_id}
Type:  Hash
Fields:
  tokens:       INT (remaining tokens)
  last_refill:  TIMESTAMP (last refill time)
  max_tokens:   INT (bucket capacity)
  refill_rate:  INT (tokens per second)
```

### High-Level Architecture

```
                    ┌──────────┐
                    │  Client  │
                    └────┬─────┘
                         │
                    ┌────▼─────────────┐
                    │  Load Balancer   │
                    └────┬─────────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐
         │ API    │ │ API    │ │ API    │
         │Server 1│ │Server 2│ │Server 3│
         └───┬────┘ └───┬────┘ └───┬────┘
             │          │          │
             │   Rate Limiter Middleware
             │   (embedded in each server)
             │          │          │
             └──────────┼──────────┘
                        │
               ┌────────▼────────┐
               │  Redis Cluster  │
               │  (6 nodes,     │
               │   3 primary +  │
               │   3 replica)   │
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │  Rules Config   │
               │  Service        │
               │  (etcd/Consul)  │
               └─────────────────┘
```

The rate limiter is embedded middleware, not a separate proxy hop. That keeps latency down. Redis provides shared state across all servers. The rules config service lets you update limits without deploying code.

### Deep Dive

**1. Algorithm Comparison**

This is where most explanations skip the nuance. There are five real algorithms, and they have meaningfully different tradeoffs:

| Algorithm | Accuracy | Memory | Burst handling | Complexity |
|-----------|----------|--------|----------------|------------|
| **Fixed window counter** | Low (boundary burst) | Very low | Poor — 2x burst at boundary | Simple |
| **Sliding window log** | Perfect | High (stores every request) | Perfect | Moderate |
| **Sliding window counter** | Good (~0.003% error) | Low | Good | Moderate |
| **Token bucket** | Good | Very low | Allows controlled bursts | Simple |
| **Leaky bucket** | Good | Very low | No bursts (smooth output) | Simple |

The fixed window counter has a nasty failure mode: a user can send 1,000 requests at 11:59 PM and another 1,000 at 12:00 AM — 2,000 requests in 2 seconds, both within their "windows." That's a 2x burst that bypasses the rate limit.

**Chosen approach: Sliding window counter** for most rules (good accuracy, low memory). Token bucket for endpoints that should allow short bursts.

Sliding window counter formula:
```
count = (prev_window_count * overlap%) + current_window_count

Example: 100 req/min limit, we are 30s into current minute
  prev_window had 80 requests
  current_window has 25 requests
  estimated count = 80 * 0.5 + 25 = 65  (under limit, allow)
```

The 0.003% error is the approximation from using the previous window's count proportionally. In practice, it's negligible — you don't need perfect accuracy, you need good accuracy that's cheap to compute.

**2. Distributed Counting with Redis**

Race condition: two servers read the same counter, both see room, both increment. Classic TOCTOU (time-of-check to time-of-use) bug.

Solution: use Redis Lua scripts for atomic check-and-increment. Lua scripts in Redis are guaranteed to execute atomically — no other operations run between the check and the increment.

```lua
-- Atomic sliding window counter in Redis
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current entries
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
    redis.call('EXPIRE', key, window)
    return limit - count - 1  -- remaining
else
    return -1  -- rate limited
end
```

**3. Failure Modes**

This is the part that matters most in production. What happens when Redis goes down?

| Failure | Strategy |
|---------|----------|
| Redis node down | **Fail open** — allow all traffic. Degraded accuracy is better than total outage. Fall back to local in-memory counters. |
| Network partition | Each partition rate-limits independently. Effective limit may temporarily double. Acceptable trade-off. |
| Clock skew | Use Redis server time (`TIME` command), not app server time. |
| Hot key (single client doing millions of requests) | Hash to a specific Redis shard. If one client dominates, their key is isolated. |

The fail-open decision reflects a fundamental availability vs. consistency trade-off — exactly what Ch 1's CAP theorem formalizes. For most APIs, a few minutes of unlimited requests during a Redis outage is less catastrophic than blocking all traffic. For financial APIs or abuse-prone endpoints, you might choose to fail closed.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Sliding window counter over exact log | 10x less memory | ~0.003% counting error |
| Redis over local memory | Consistent limits across servers | +1-2 ms network latency per request |
| Fail-open on Redis failure | 100% availability | Temporarily no rate limiting |
| Lua scripts for atomicity | Race-condition-free counting | Slightly higher Redis CPU |

---

## 3. Chat System (like Slack/WhatsApp)

Chat is one of those systems where the requirements sound obvious ("users send messages to each other") but the implementation surface is enormous. Let's count the hard problems: real-time delivery, ordering guarantees, offline message buffering, 15 million simultaneous WebSocket connections, file sharing, presence indicators, group fan-out...

And those are just the ones that make it into the requirements doc.

Here's the real challenge: a message sent by User A needs to show up on User B's screen in under 200 milliseconds — and User B might be connected to a completely different server than User A. Your servers need to talk to each other in real-time, route messages across the cluster, persist them durably, and also send a push notification if User B is offline. All of this in parallel, without losing the message.

> **The moment it gets hard:** User A is on server 1. User B is on server 3. The message needs to go from server 1 to server 3 to User B's WebSocket in under 200 ms — and also be durably stored so User B can read it later if their phone crashes.

### Requirements

**Functional:**
- 1:1 messaging and group chat (up to 500 members)
- Online/offline presence indicators
- Read receipts and typing indicators
- Message history (persistent, searchable)
- File/image sharing (up to 50 MB)
- Offline message delivery (push notifications)

**Non-Functional:**
- 50M DAU, average 40 messages sent per user per day
- Message delivery latency < 200 ms (p95) for online users
- 99.99% message delivery guarantee (no lost messages)
- Message ordering: causal ordering within a conversation
- End-to-end encryption (optional, like WhatsApp)

### Capacity Estimation

```
Messages:
  50M DAU x 40 msgs/day = 2B messages/day
  QPS: 2B / 86,400 = ~23,000 msg/sec (avg)
  Peak: ~70,000 msg/sec

Storage:
  Avg message size: 200 bytes (text) + 100 bytes (metadata) = 300B
  2B msgs/day x 300B = 600 GB/day
  Per year: ~220 TB
  With media: assume 10% of messages have media (avg 500 KB)
  200M x 500 KB = 100 TB/day -> stored in object storage (S3)

Connections:
  50M DAU with ~30% concurrent online = 15M WebSocket connections
  Each connection: ~10 KB memory -> 150 GB total
  Need: ~150 servers at 100K connections each

Bandwidth:
  Messages: 23K QPS x 300B = ~7 MB/s (text, trivial)
  Media: significant, offloaded to CDN
```

That connection math is the real surprise. 15 million persistent WebSocket connections require about 150 dedicated servers just to hold the connections. Most of the system complexity comes from managing those stateful connections.

### API Design

```
-- WebSocket connection
WS /ws/chat?token=<jwt>

-- Send message (over WebSocket)
{
  "action": "send_message",
  "conversation_id": "conv_abc123",
  "content": "Hello!",
  "client_msg_id": "uuid-for-idempotency",
  "type": "text"
}

-- Server acknowledgment (over WebSocket)
{
  "action": "message_ack",
  "client_msg_id": "uuid",
  "server_msg_id": "msg_789",
  "timestamp": 1679012345678
}

-- REST fallback for offline / history
GET  /api/v1/conversations/{id}/messages?before={msg_id}&limit=50
POST /api/v1/conversations/{id}/messages   (for clients without WS)
POST /api/v1/media/upload                  (presigned URL for file upload)
GET  /api/v1/users/{id}/presence
```

The `client_msg_id` for idempotency is critical. The client sends a message and doesn't know if it arrived. The network might hiccup. With idempotency, the client can safely retry and the server won't create a duplicate.

### Data Model

**Database: Cassandra** (write-heavy, time-series messages, easy partitioning by conversation)
**Presence & routing: Redis**
**Media: S3 + CDN**

Cassandra for messages is the classic choice here. You're partitioning by `conversation_id`, which means all messages in a conversation live on the same node (fast reads). As you learned in Ch 2, wide-column stores like Cassandra shine when your access patterns are predictable and write throughput is high. 70,000 msg/sec would stress PostgreSQL — Cassandra handles it comfortably.

```sql
-- Cassandra: Messages table
CREATE TABLE messages (
    conversation_id  UUID,
    message_id       TIMEUUID,    -- time-sortable unique ID
    sender_id        UUID,
    content          TEXT,
    content_type     TEXT,        -- 'text', 'image', 'file'
    media_url        TEXT,
    created_at       TIMESTAMP,
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- Cassandra: Conversations per user (for inbox)
CREATE TABLE user_conversations (
    user_id           UUID,
    last_activity     TIMESTAMP,
    conversation_id   UUID,
    last_message      TEXT,
    unread_count      INT,
    PRIMARY KEY (user_id, last_activity, conversation_id)
) WITH CLUSTERING ORDER BY (last_activity DESC);

-- Redis: Presence and connection routing
SET   presence:{user_id}  "online"  EX 60    -- TTL heartbeat
HSET  routing:{user_id}   server_id  "ws-server-42"
```

The presence key has a 60-second TTL. If a client doesn't send a heartbeat for 60 seconds, they're considered offline. Simple and self-cleaning.

### High-Level Architecture

```
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ Mobile   │  │  Web     │  │ Desktop  │
  │ Client   │  │ Client   │  │ Client   │
  └────┬─────┘  └────┬─────┘  └────┬─────┘
       │              │              │
       │         WebSocket           │
       └──────────────┼──────────────┘
                      │
               ┌──────▼──────┐
               │   L7 Load   │
               │  Balancer   │
               │(sticky sess)│
               └──────┬──────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
   │  Chat   │  │  Chat   │  │  Chat   │
   │Server 1 │  │Server 2 │  │Server 3 │
   │ (WS)    │  │ (WS)    │  │ (WS)    │
   └────┬────┘  └────┬────┘  └────┬────┘
        │             │             │
        └──────┬──────┘             │
               │                    │
        ┌──────▼──────┐      ┌─────▼──────┐
        │  Redis      │      │  Message   │
        │  Pub/Sub    │◄────►│  Queue     │
        │ (routing +  │      │  (Kafka)   │
        │  presence)  │      └─────┬──────┘
        └─────────────┘            │
                              ┌────▼─────┐
                              │Cassandra │
                              │ Cluster  │
                              │(messages)│
                              └────┬─────┘
                                   │
        ┌──────────────┐     ┌─────▼──────┐
        │  Push Notif  │     │    S3      │
        │  Service     │     │  (media)   │
        │ (APNs/FCM)  │     └────────────┘
        └──────────────┘
```

### Deep Dive

**1. Message Delivery Flow**

The sequence that makes this work:

```
1. User A sends message via WebSocket to Chat Server 1
2. Chat Server 1:
   a. Validates and assigns server_msg_id (TIMEUUID)
   b. ACKs back to User A immediately
   c. Writes to Kafka topic: "messages.conv_abc123"
   d. Looks up User B's location in Redis routing table
3. If User B is on Chat Server 2:
   a. Publish via Redis Pub/Sub to Chat Server 2
   b. Chat Server 2 pushes message to User B via WebSocket
4. If User B is offline:
   a. Message stored in Cassandra (persistent)
   b. Increment unread_count in user_conversations
   c. Trigger push notification via APNs/FCM
5. Kafka consumer writes to Cassandra (async persistence)
```

The ACK in step 2b is crucial. User A gets confirmation that the server received the message — not that User B got it. That distinction matters. True delivery confirmation would require User B's client to ACK, which you can build on top of this.

**2. Ordering Guarantees**

Messages within a conversation must be ordered. Across conversations, ordering doesn't matter.

- Use **TIMEUUID** (Cassandra) — combines timestamp + node ID + sequence. Monotonically increasing per-node.
- Kafka topic partitioned by `conversation_id` — all messages for one conversation go to the same partition, preserving order.
- For conflict resolution (two users send at the same millisecond): TIMEUUID's built-in uniqueness resolves ties deterministically.

This is a practical application of the ordering guarantees discussed in Ch 1. You're not solving global ordering (that's the hard version) — you're solving per-conversation ordering, which is achievable.

**3. Group Chat Fan-out**

For a group of N members, sending a message means delivering to N-1 recipients. This is where chat systems scale differently from 1:1:

- **Small groups (< 50):** Fan-out on write. When a message arrives, look up all members, find their WebSocket servers, deliver immediately. Write once to Cassandra (single partition by conversation_id).
- **Large groups (50-500):** Same write-once storage, but fan-out delivery goes through a dedicated "group delivery" worker pool to avoid blocking the chat server.
- **Read receipts in groups:** Only track "last read message ID" per user per conversation. Do not send individual read receipts for every message in large groups — that's O(N^2) acknowledgments.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Cassandra over PostgreSQL | Horizontal write scaling, natural time-series partitioning | No cross-conversation transactions or JOINs |
| WebSocket over long-polling | True real-time, lower overhead | Stateful connections require sticky sessions |
| Redis Pub/Sub for cross-server delivery | Low-latency routing between servers | Messages lost if subscriber is temporarily disconnected (Kafka is the durable backup) |
| TIMEUUID over application-level clocks | No clock sync needed across servers | IDs are larger (16 bytes vs. 8 bytes for an integer) |

---

## 4. Notification System

Here's a system that looks like a simple message queue problem until you actually enumerate the requirements. Then it explodes.

"Send a notification to a user" sounds trivial. But now add: four different channels (push, email, SMS, in-app). User preferences (some users opt out of SMS, some only want email at certain hours). Priority levels (a 2FA code can't wait in line behind marketing emails). Deduplication (the same notification sent twice is bad UX, and for 2FA codes it's confusing). Delivery tracking with retry logic. 10x traffic spikes during sales events.

And the hardest constraint of all: the critical path (2FA codes, fraud alerts) cannot be delayed by any of the non-critical work. That forces you into a priority queue architecture.

> **The moment it gets hard:** Ensuring a 2FA code arrives in under 10 seconds even when your system is processing a million marketing emails from a sale event.

### Requirements

**Functional:**
- Multi-channel delivery: push (iOS/Android), email, SMS, in-app
- User notification preferences (opt-in/out per channel, per category)
- Priority levels: critical (immediate), high (< 1 min), normal (< 5 min), low (batched hourly)
- Deduplication (same notification should not be sent twice)
- Delivery tracking and retry on failure
- Template management for each channel

**Non-Functional:**
- 100M users, 500M notifications/day across all channels
- Critical notifications delivered in < 10 seconds
- At-least-once delivery guarantee
- 99.95% delivery success rate
- Handle sudden spikes (10x during events like sales, outages)

### Capacity Estimation

```
Notifications:
  500M/day = ~5,800/sec (avg)
  Peak (10x): ~58,000/sec

Breakdown by channel (typical):
  Push: 60% = 300M/day
  Email: 25% = 125M/day
  SMS:  10% = 50M/day
  In-app: 5% = 25M/day

Storage:
  Each notification log: ~500B (metadata, status, timestamps)
  500M x 500B = 250 GB/day
  Retain 90 days: 22.5 TB

Queue depth:
  Normal processing: ~5,800 msg/sec dequeued
  During spike: queue can grow to millions; need backpressure
```

That 10x spike is the design constraint. You can't overprovision 10x all the time — you'd go broke. You need a system that absorbs spikes gracefully, processes critical items first, and works through the backlog without dropping anything.

### API Design

```
-- Trigger a notification (internal service-to-service)
POST /api/v1/notifications/send
Body: {
  "user_id": "user_123",
  "template_id": "order_shipped",
  "channel": ["push", "email"],       -- or "auto" for preference-based
  "priority": "high",
  "data": {
    "order_id": "ORD-456",
    "tracking_url": "https://..."
  },
  "idempotency_key": "order_shipped:ORD-456"
}

-- Get user preferences
GET /api/v1/users/{id}/notification-preferences
Response: {
  "push_enabled": true,
  "email_enabled": true,
  "sms_enabled": false,
  "quiet_hours": { "start": "22:00", "end": "07:00", "timezone": "US/Pacific" },
  "categories": {
    "marketing": { "push": false, "email": true },
    "transactional": { "push": true, "email": true, "sms": true }
  }
}

-- Delivery status
GET /api/v1/notifications/{notification_id}/status
Response: {
  "status": "delivered",
  "channel": "push",
  "sent_at": "...",
  "delivered_at": "...",
  "opened_at": null
}
```

### Data Model

**Database: PostgreSQL** (notification logs, preferences) + **Redis** (dedup, rate limiting) + **Kafka** (queue)

```sql
-- Notification log
CREATE TABLE notifications (
    id              UUID PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    template_id     VARCHAR(100) NOT NULL,
    channel         VARCHAR(10) NOT NULL,  -- push, email, sms, in_app
    priority        SMALLINT DEFAULT 2,    -- 0=critical, 1=high, 2=normal, 3=low
    status          VARCHAR(20) NOT NULL,  -- queued, sent, delivered, failed, bounced
    idempotency_key VARCHAR(255) UNIQUE,
    payload         JSONB,
    sent_at         TIMESTAMP,
    delivered_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_notif_user ON notifications(user_id, created_at DESC);

-- User preferences
CREATE TABLE notification_preferences (
    user_id         BIGINT PRIMARY KEY,
    push_enabled    BOOLEAN DEFAULT TRUE,
    email_enabled   BOOLEAN DEFAULT TRUE,
    sms_enabled     BOOLEAN DEFAULT FALSE,
    quiet_hours     JSONB,
    category_prefs  JSONB,
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

### High-Level Architecture

```
 ┌──────────────┐  ┌──────────┐  ┌──────────┐
 │ Order Service│  │Auth Svc  │  │Marketing │
 │              │  │(2FA code)│  │ Service  │
 └──────┬───────┘  └────┬─────┘  └────┬─────┘
        │               │              │
        └───────────────┼──────────────┘
                        │
                 ┌──────▼──────┐
                 │ Notification│
                 │   Gateway   │
                 │ (validate,  │
                 │  dedup,     │
                 │  route)     │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │    Kafka    │
                 │  (4 topics  │
                 │  by priority│
                 └──────┬──────┘
                        │
        ┌───────┬───────┼───────┬────────┐
        │       │       │       │        │
   ┌────▼──┐ ┌─▼────┐ ┌▼────┐ ┌▼─────┐  │
   │ Push  │ │Email │ │SMS  │ │In-App│  │
   │Workers│ │Worker│ │Work.│ │Worker│  │
   └───┬───┘ └──┬───┘ └──┬──┘ └──┬───┘  │
       │        │        │       │       │
   ┌───▼───┐ ┌──▼──┐ ┌──▼───┐   │  ┌────▼────┐
   │APNs / │ │SES /│ │Twilio│   │  │  Redis  │
   │ FCM   │ │SMTP │ │      │   │  │ (dedup, │
   └───────┘ └─────┘ └──────┘   │  │  status) │
                                 │  └─────────┘
                          ┌──────▼──────┐
                          │ PostgreSQL  │
                          │(notif logs) │
                          └─────────────┘
```

### Deep Dive

**1. Priority-Based Processing**

Four Kafka topics, one per priority level. Workers consume from higher-priority topics first. This is the key architectural decision that makes 2FA codes fast during a marketing campaign:

```
Topic: notifications.critical  -> 50 consumer instances, 0 lag tolerance
Topic: notifications.high      -> 30 consumer instances
Topic: notifications.normal    -> 20 consumer instances
Topic: notifications.low       -> 5 consumer instances, batch every hour
```

Critical notifications (2FA codes, fraud alerts) bypass the normal queue entirely and are processed by a dedicated fast-path with its own APNs/FCM connections. Even if the marketing topic has 10M queued messages, the critical topic is never starved.

**2. Deduplication**

The `idempotency_key` prevents duplicate sends. This matters more than you'd think — retries, upstream bugs, and double-clicks all cause duplicate notification triggers. Two-layer check:

1. **Redis SET NX** with TTL: `SETNX dedup:{idempotency_key} 1 EX 86400` — if key exists, reject immediately.
2. **PostgreSQL UNIQUE constraint** on `idempotency_key` — catches any race conditions that slip past Redis.

The two-layer approach is a pattern you'll see throughout this chapter. Redis for speed, database constraint as the safety net. Neither alone is sufficient.

**3. Delivery Tracking and Retries**

```
State machine:
  queued -> sent -> delivered
                 -> failed -> retry_1 -> retry_2 -> retry_3 -> dead_letter

Retry policy:
  Attempt 1: immediate
  Attempt 2: after 30 seconds
  Attempt 3: after 5 minutes
  Attempt 4: after 1 hour
  After 4 failures: move to dead letter queue, alert ops
```

Push delivery confirmation comes from APNs/FCM callbacks. Email: track via SES webhooks (bounce, complaint, delivery). SMS: Twilio status callbacks. In-app: the client acknowledges when it displays the notification.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Kafka over simple queue (SQS) | Priority topics, replay capability, high throughput | Operational complexity of running Kafka |
| At-least-once over exactly-once delivery | Simpler, no 2PC needed | Users may get duplicate notifications (mitigated by dedup) |
| Separate workers per channel | Independent scaling, isolated failures | More services to deploy and monitor |
| 90-day log retention | Audit trail, debugging | 22.5 TB storage cost |

---

## 5. News Feed / Timeline (like Twitter)

The news feed is one of the most-discussed system design problems because the core tension is so clean: reads need to be fast, but writes create cascading work.

Here's the fundamental question you have to answer: when a user posts something, do you push that post to all their followers' feeds immediately (fan-out on write)? Or do you pull and merge when a follower opens their app (fan-out on read)?

Fan-out on write: fast reads, expensive writes.
Fan-out on read: fast writes, slow reads.

Pick one. Except — and here's where it gets really interesting — neither choice works for celebrities. A celebrity with 50 million followers can't do fan-out on write (that's 50 million write operations per post, taking minutes). And a user following 200 accounts can't do fan-out on read efficiently (that's 200 database queries per feed load).

The production answer is a hybrid, and understanding why reveals a lot about how real-world systems deal with non-uniform load.

> **The moment it gets hard:** Beyoncé posts a tweet. She has 50 million followers. How do you deliver that post without melting your infrastructure — and without adding 200 ms of latency to every other user's feed load?

### Requirements

**Functional:**
- Users publish posts (text, images, links)
- Home feed shows posts from followed users, ranked by relevance
- Support for celebrities with millions of followers
- Like, comment, retweet/share
- Infinite scroll pagination

**Non-Functional:**
- 300M DAU, average user checks feed 10 times/day
- Feed generation latency < 500 ms (p95)
- New posts appear in followers' feeds within 5 seconds
- 99.9% availability
- Average user follows 200 accounts; celebrities have up to 50M followers

### Capacity Estimation

```
Feed reads:
  300M DAU x 10 feed loads = 3B reads/day
  QPS: 3B / 86,400 = ~35,000 reads/sec
  Peak: ~100,000 reads/sec

Post writes:
  300M DAU x 2 posts/day (avg, most users post less) = 600M posts/day
  QPS: ~7,000 writes/sec

Fan-out (if fan-out-on-write):
  Average 200 followers per post = 600M x 200 = 120B fan-out writes/day
  That is 1.4M fan-out writes/sec -> infeasible for ALL users

Storage:
  Post: 500B (text + metadata) + avg 200KB media
  600M posts x 500B = 300 GB/day (text)
  600M x 10% with media x 200KB = 12 TB/day (media, in S3)

Feed cache:
  Cache top 200 posts per user
  300M users x 200 x 8B (post ID) = 480 GB in Redis
```

That fan-out math tells the story. 1.4M fan-out writes/sec is the number that breaks naive fan-out-on-write. And most of those writes are for non-celebrities — the solution needs to handle both cases.

### API Design

```
-- Publish a post
POST /api/v1/posts
Body: { "content": "Hello world", "media_ids": ["img_123"] }
Response: { "post_id": "post_abc", "created_at": "..." }

-- Get home feed
GET /api/v1/feed?cursor={post_id}&limit=20
Response: {
  "posts": [
    {
      "post_id": "post_abc",
      "author": { "id": "...", "name": "...", "avatar": "..." },
      "content": "...",
      "media": [...],
      "likes_count": 42,
      "comments_count": 7,
      "created_at": "...",
      "ranking_score": 0.95
    },
    ...
  ],
  "next_cursor": "post_xyz"
}

-- Like / Unlike
POST   /api/v1/posts/{id}/like
DELETE /api/v1/posts/{id}/like
```

### Data Model

**PostgreSQL:** Users, posts, social graph
**Redis:** Feed cache, counters
**S3 + CDN:** Media

```sql
-- Posts
CREATE TABLE posts (
    id          BIGSERIAL PRIMARY KEY,
    author_id   BIGINT NOT NULL REFERENCES users(id),
    content     TEXT,
    media_urls  TEXT[],
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Social graph (who follows whom)
CREATE TABLE follows (
    follower_id  BIGINT NOT NULL,
    followee_id  BIGINT NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (follower_id, followee_id)
);
CREATE INDEX idx_followers ON follows(followee_id);

-- Feed cache (Redis)
-- Key: feed:{user_id}
-- Type: Sorted Set
-- Score: ranking_score (combining recency + relevance)
-- Value: post_id
```

### High-Level Architecture

```
 ┌──────────┐
 │  Client  │
 └────┬─────┘
      │
 ┌────▼──────────┐
 │  API Gateway  │
 └────┬──────────┘
      │
      ├─────────────────────────────────┐
      │                                 │
 ┌────▼──────┐                   ┌──────▼──────┐
 │ Post Svc  │                   │  Feed Svc   │
 │ (write)   │                   │  (read)     │
 └────┬──────┘                   └──────┬──────┘
      │                                 │
      │                          ┌──────▼──────┐
      │                          │ Redis Feed  │
      │                          │   Cache     │
      │                          └──────┬──────┘
      │                                 │ (cache miss)
 ┌────▼──────┐                   ┌──────▼──────┐
 │   Kafka   │                   │ PostgreSQL  │
 │(new posts)│                   │  (posts,    │
 └────┬──────┘                   │   graph)    │
      │                          └─────────────┘
      │
 ┌────▼──────────────┐
 │  Fan-out Workers  │
 │  (write to feed   │
 │   cache for each  │
 │   follower)       │
 └────┬──────────────┘
      │
      │  ┌──────────────┐
      └──► Ranking Svc  │
         │ (ML model    │
         │  scoring)    │
         └──────────────┘
```

### Deep Dive

**1. Fan-out Strategy: The Celebrity Problem**

The core challenge: when a celebrity with 50M followers posts, fan-out-on-write means writing to 50M feed caches. That takes minutes. The user's post would appear in followers' feeds long after it's relevant.

**Hybrid approach — this is the real answer:**

| User type | Strategy | Why |
|-----------|----------|-----|
| Normal users (< 10K followers) | **Fan-out on write** | Pre-compute feeds. 200 writes per post is cheap. Reads are instant (just read cache). |
| Celebrities (> 10K followers) | **Fan-out on read** | Do NOT pre-write to 50M caches. When a user loads their feed, merge cached feed (from normal follows) with recent celebrity posts in real-time. |

```
Feed generation for User X:
1. Read pre-computed feed from Redis (posts from normal follows)
2. Get list of celebrities that User X follows (small list, ~5-20)
3. Fetch recent posts from each celebrity (cached in Redis by author_id)
4. Merge + rank all posts
5. Return top 20
```

Steps 2-4 add ~50-100 ms but avoid billions of fan-out writes. That's the tradeoff you're making: slightly more complex read path, dramatically simpler write path for celebrities.

**2. Feed Ranking**

Raw chronological feed is noisy — users miss content from accounts they care about because a high-volume account buried it. Apply a ranking model:

```
score = w1 * recency + w2 * affinity + w3 * engagement + w4 * content_type

Where:
  recency    = decay_function(now - post.created_at)
  affinity   = how often user interacts with this author
  engagement = (likes + comments + shares) / impressions
  content_type = boost for images/video vs plain text
```

The ranking service is a lightweight ML model (logistic regression or small neural net) that scores each candidate post. It runs at read time on the merged candidate set. The weights (w1-w4) are tuned by the product team based on engagement metrics.

**3. Pagination with Ranking**

You cannot use offset-based pagination (`LIMIT 20 OFFSET 40`) when results are ranked. Rankings change between page loads — you'd get duplicates and skips. Use cursor-based pagination:

- Cursor = `(score, post_id)` of the last item on the current page.
- Next page: `WHERE (score, post_id) < (cursor_score, cursor_post_id) ORDER BY score DESC, post_id DESC LIMIT 20`

The `post_id` is a tiebreaker — two posts with the same score are ordered by ID (older first). This gives you stable, consistent pagination even as new posts arrive.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Hybrid fan-out | Handles celebrities without melting infrastructure | More complex read path (merge step) |
| Pre-computed feed cache | < 100 ms read latency | 480 GB Redis for feed caches |
| ML ranking over chronological | Higher engagement, relevant content | Transparency — users do not understand why they see what they see |
| Cursor pagination over offset | Stable pagination, no duplicates/skips | Cannot "jump to page 50" |

---

## 6. Search Autocomplete

You've seen autocomplete a thousand times. You type "how to m" and the dropdown shows "how to make pancakes," "how to merge git branches," "how to meditate." It feels instant. It always has suggestions. It somehow knows what's trending.

Let's talk about how it actually works, because every piece of that experience is a deliberate engineering decision.

The first constraint hits you immediately: < 100 ms p99. That's not a lot of time. And you're doing this for 83,000 requests per second at average load. You can't hit a database on every keystroke for every user. You need a data structure purpose-built for prefix matching — and you need most requests to never reach your servers at all.

The second constraint is subtler: suggestions need to reflect trending searches within 15 minutes. That means you can't just precompute everything offline — the trie needs to update. But updating a trie that's being read at 83K QPS without downtime is a concurrency challenge.

> **The moment it gets hard:** Keeping the in-memory trie up to date with trending searches, at sub-100ms latency, across a fleet of stateful servers, without a single dropped request during the update.

### Requirements

**Functional:**
- As the user types, suggest top 5-10 completions
- Rank suggestions by popularity (search frequency)
- Support multi-language queries
- Update suggestions based on trending / recent searches
- Filter inappropriate suggestions

**Non-Functional:**
- 300M DAU, average 6 searches/day, 4 keystrokes per search = 7.2B autocomplete requests/day
- Response latency < 100 ms (p99)
- Suggestions update within 15 minutes of trending
- 99.99% availability

### Capacity Estimation

```
Autocomplete queries:
  7.2B/day = ~83,000 QPS (avg)
  Peak: ~250,000 QPS

Unique query prefixes:
  Estimate ~50M unique queries, avg length 15 chars
  All prefixes of length 1-15 for each: ~750M trie nodes (with sharing)
  But many prefixes overlap -> ~100M unique prefix nodes

Storage:
  Each trie node: prefix (20B avg) + top-5 suggestions (5 x 30B) + frequency (8B)
  = ~180B per node
  100M nodes x 180B = 18 GB (fits in memory!)

Bandwidth:
  83K QPS x 500B (5 suggestions) = ~40 MB/s
```

18 GB fits in memory. That's the key insight that drives the whole architecture. You can hold the entire autocomplete dataset in RAM on each server. No database calls on the hot path.

### API Design

```
GET /api/v1/autocomplete?q=how+to+m&lang=en&limit=5
Response: {
  "suggestions": [
    { "text": "how to make pancakes", "score": 95200 },
    { "text": "how to merge git branches", "score": 87100 },
    { "text": "how to meditate", "score": 73400 },
    { "text": "how to multiply fractions", "score": 62800 },
    { "text": "how to meal prep", "score": 51200 }
  ]
}
Headers:
  Cache-Control: public, max-age=300
```

### Data Model

**Primary: Trie in memory** (each autocomplete server holds the full trie)
**Source of truth: PostgreSQL** (query frequencies, used to rebuild trie)
**Cache: CDN** (most prefixes are cacheable)

```sql
-- Query frequency table (source of truth for trie building)
CREATE TABLE query_frequencies (
    query_text   VARCHAR(200) PRIMARY KEY,
    frequency    BIGINT DEFAULT 0,
    language     VARCHAR(5) DEFAULT 'en',
    is_blocked   BOOLEAN DEFAULT FALSE,
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- Trending queries (for real-time trie updates)
CREATE TABLE trending_queries (
    query_text   VARCHAR(200),
    frequency    BIGINT,
    window_start TIMESTAMP,
    PRIMARY KEY (window_start, query_text)
);
```

### High-Level Architecture

```
 ┌──────────┐
 │  Client  │
 └────┬─────┘
      │
 ┌────▼──────┐
 │   CDN     │  (cache autocomplete responses by prefix)
 └────┬──────┘
      │ (cache miss)
 ┌────▼──────────┐
 │ Load Balancer │
 └────┬──────────┘
      │
 ┌────▼──────────────────────────────┐
 │   Autocomplete Servers (stateful) │
 │   Each holds full trie in memory  │
 │                                   │
 │  ┌──────────────────────────┐     │
 │  │ Trie (in-memory, 18 GB) │     │
 │  │                          │     │
 │  │ "how" -> [how to make.., │     │
 │  │          how to merge..]│     │
 │  └──────────────────────────┘     │
 └────┬──────────────────────────────┘
      │
 ┌────▼──────────┐     ┌──────────────────┐
 │  Trie Builder │◄────│  Kafka (search   │
 │  Service      │     │  event stream)   │
 │  (rebuilds    │     └────────┬─────────┘
 │  every 15 min)│              │
 └────┬──────────┘     ┌────────▼─────────┐
      │                │  Search Service  │
 ┌────▼──────┐         │  (logs every     │
 │PostgreSQL │         │   user search)   │
 │(frequency)│         └──────────────────┘
 └───────────┘
```

### Deep Dive

**1. Trie Data Structure**

A trie (prefix tree) is purpose-built for this problem. Each node represents a character, and the path from root to node spells out a prefix. The magic is pre-computing the top-K suggestions at each node during the build phase:

```
Root
 ├── h
 │   ├── o
 │   │   └── w
 │   │       ├── [top-5: "how to make pancakes", "how to merge...", ...]
 │   │       └── (children for longer prefixes)
 │   └── e
 │       └── l
 │           └── [top-5: "hello world", "help me", ...]
 └── t
     └── h
         └── e
             └── [top-5: "the weather", "the office", ...]
```

Why pre-compute top-K at each node instead of traversing all leaves at query time? Because traversal would take O(n) where n is the number of descendants — far too slow for 100 ms latency. With pre-computed top-K, every autocomplete query is O(length of prefix) — basically instant.

**2. Trie Updates: Rebuild vs. Incremental**

| Approach | Latency | Complexity |
|----------|---------|------------|
| Full rebuild every 15 min | 15 min to reflect trends | Simple — build new trie, atomic swap |
| Incremental updates | Near real-time | Complex — concurrent reads/writes on trie, lock contention |

**Chosen approach:** Full rebuild with atomic pointer swap. Every 15 minutes:

1. Trie Builder aggregates query frequencies from Kafka stream + PostgreSQL
2. Builds a new trie in a separate memory region
3. Atomic pointer swap: `current_trie = new_trie`
4. Old trie is garbage collected

This is the blue-green deployment pattern applied to an in-memory data structure. The old trie serves requests while the new trie is built. The swap is atomic — no request ever sees a partial trie.

For truly real-time trending (e.g., during a breaking news event), a small "overlay" of trending queries is merged at query time. The overlay is just a hash map — tiny and fast to update.

**3. CDN Caching**

Most autocomplete requests are for common prefixes. Cache aggressively:

- Top 1000 prefixes (1-3 characters): cache at CDN with TTL=5min. This covers ~50% of all requests.
- All other prefixes: cache with TTL=1hr.
- Cache key: `autocomplete:{lang}:{prefix}`

At 250K peak QPS, if CDN absorbs 50%, autocomplete servers only see 125K QPS. The CDN does the heavy lifting for the most common, most cacheable prefixes.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Full trie in memory | < 10 ms lookup | 18 GB RAM per server, must fit in memory |
| Rebuild over incremental | Simple, no concurrency issues | 15-minute delay for new trends |
| Pre-computed top-K per node | O(1) query time | Larger trie, rebuild takes longer |
| CDN caching | 50% traffic reduction | Stale suggestions for up to 5 minutes |

---

## 7. Distributed Cache (like Memcached/Redis Cluster)

What happens when you need to design the thing that makes everything else fast? This case study is different from the others — you're not building a user-facing product, you're building infrastructure that user-facing products depend on.

The requirements sound deceptively simple: store key-value pairs, fast. But at 1M reads per second and 500 GB of data, "simple" disappears quickly. How do you distribute 500 GB across nodes without routing every key through a central coordinator? What happens when you add a node? What happens when a node dies?

And there's a failure mode specific to caches that you rarely think about until it destroys your database: the cache stampede. A hot key expires. A hundred servers simultaneously notice the cache miss. A hundred servers simultaneously query the database. The database — which the cache was protecting — collapses under the load. The cure for the disease caused the disease.

> **The moment it gets hard:** A hot key expires. Every server in your fleet misses the cache simultaneously. Your database gets hit 1,000 times in 50 milliseconds. How do you prevent this?

### Requirements

**Functional:**
- Key-value store with GET, SET, DELETE operations
- TTL (time-to-live) per key
- Support multiple data types (string, hash, list, set, sorted set)
- Atomic operations (increment, compare-and-swap)
- Cluster mode: distribute data across multiple nodes

**Non-Functional:**
- 1M QPS read, 200K QPS write across the cluster
- GET latency < 1 ms (p99) for cache hits
- 99.99% availability (cache downtime causes cascading DB failures)
- 500 GB total cache capacity
- Linear horizontal scalability (add nodes = add capacity)

### Capacity Estimation

```
Total QPS: 1.2M (1M read + 200K write)
Nodes needed (100K QPS per node): 12 data nodes minimum
With replication (1 primary + 1 replica): 24 nodes

Memory per node: 500 GB / 12 = ~42 GB per node
  Use 64 GB machines (leave headroom for fragmentation + OS)

Network:
  1.2M QPS x 1 KB avg value = 1.2 GB/s aggregate
  Per node: ~100 MB/s (well within 10 Gbps NIC)

Key count:
  500 GB / 1 KB avg = ~500M keys distributed across 12 nodes
```

### API Design

```
-- Core operations
SET key value [EX seconds] [NX|XX]
GET key
DEL key [key ...]
MGET key [key ...]       (multi-get, batched)
INCR key                 (atomic increment)
EXPIRE key seconds

-- Hash operations
HSET key field value
HGET key field
HGETALL key

-- Cluster operations (internal)
CLUSTER NODES            (list all nodes and their slots)
CLUSTER KEYSLOT key      (which slot owns this key)
CLUSTER FAILOVER         (manual failover for maintenance)
```

### Data Model

```
Internal data structures per node:

┌─────────────────────────────────────────┐
│            Hash Table (main)            │
│                                         │
│  Slot 0-1364:    Bucket[] -> Entry*     │
│  Each Entry:                            │
│    key:       char*                     │
│    value:     RedisObject*              │
│    ttl:       int64 (unix timestamp)    │
│    hash_next: Entry*                    │
│                                         │
│  RedisObject:                           │
│    type:     STRING | LIST | SET | ...  │
│    encoding: INT | EMBSTR | RAW | ...   │
│    data:     void*                      │
│    refcount: int                        │
│    lru_clock: uint24 (for eviction)     │
└─────────────────────────────────────────┘
```

### High-Level Architecture

```
                    ┌──────────────────────┐
                    │     Application      │
                    │     Servers          │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Cache Client Lib   │
                    │  (consistent hash,   │
                    │   connection pool,   │
                    │   retry logic)       │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          │                    │                     │
   ┌──────▼──────┐     ┌──────▼──────┐      ┌──────▼──────┐
   │  Node 1     │     │  Node 2     │      │  Node 3     │
   │ Primary     │     │ Primary     │      │ Primary     │
   │Slots 0-5460 │     │Slots 5461-  │      │Slots 10923- │
   │             │     │   10922     │      │   16383     │
   └──────┬──────┘     └──────┬──────┘      └──────┬──────┘
          │                    │                     │
   ┌──────▼──────┐     ┌──────▼──────┐      ┌──────▼──────┐
   │  Node 1     │     │  Node 2     │      │  Node 3     │
   │  Replica    │     │  Replica    │      │  Replica    │
   └─────────────┘     └─────────────┘      └─────────────┘
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Cluster Manager     │
                    │  (Sentinel / Gossip) │
                    │  - Failure detection │
                    │  - Automatic failover│
                    │  - Slot rebalancing  │
                    └──────────────────────┘
```

### Deep Dive

**1. Consistent Hashing and Slot Assignment**

The naive approach `hash(key) % N` has a catastrophic property: when N changes (add or remove a node), almost every key remaps to a different node. Every cache miss. Your database dies.

Redis solves this with hash slots:

```
1. Hash the key: slot = CRC16(key) % 16384
2. Each node owns a range of slots (16384 slots total)
3. Node 1: slots 0-5460, Node 2: slots 5461-10922, Node 3: slots 10923-16383
```

When adding a node: reassign some slots from existing nodes to the new node. Only keys in moved slots need to migrate — not all keys. Instead of invalidating your entire cache, you migrate a fraction of it.

**Virtual nodes** improve distribution: each physical node appears at multiple points on the hash ring, preventing hot spots when nodes have different capacities.

**2. Eviction Policies**

When memory is full, which keys to evict? This is a real design choice that affects your application's behavior:

| Policy | Description | Use case |
|--------|-------------|----------|
| **LRU** (Least Recently Used) | Evict key accessed longest ago | General-purpose caching |
| **LFU** (Least Frequently Used) | Evict key accessed fewest times | When popular keys should persist |
| **TTL-based** | Evict keys closest to expiration | When TTLs are well-calibrated |
| **Random** | Evict random key | When all keys are equally important |
| **volatile-lru** | LRU among keys with TTL set | Keep permanent keys, evict cached data |

Redis uses **approximated LRU** — samples N random keys and evicts the one with the oldest access time. This is O(1) vs. true LRU's O(n) for maintaining a linked list. The approximation error is small enough that it doesn't matter in practice.

**3. Cache Stampede Prevention**

When a popular key expires, hundreds of servers simultaneously cache-miss and hit the database. This is the thundering herd problem, and it can take down a database in seconds. Three solutions:

```
1. Probabilistic early expiration:
   remaining_ttl = key.ttl - now
   if (remaining_ttl < random(0, ttl * 0.1)):
       refresh_in_background()

2. Mutex lock (distributed):
   if cache_miss(key):
       if redis.SET("lock:" + key, 1, NX, EX, 5):
           value = db.query(key)
           redis.SET(key, value, EX, ttl)
           redis.DEL("lock:" + key)
       else:
           sleep(50ms)
           retry()

3. Cache warming on deploy:
   Pre-populate top 10K keys before routing traffic.
```

The probabilistic approach is elegant — a small random fraction of requests start refreshing the cache before it expires, so the expiration never hits cold. No locks, no coordination.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Hash slots (16384) over pure consistent hashing | Deterministic slot assignment, easy migration | Fixed upper bound on sharding granularity |
| Approximated LRU over true LRU | O(1) eviction, no memory overhead for LRU list | ~3% worse hit rate than true LRU |
| Async replication | Lower write latency | Small window of data loss on primary failure |
| Replica reads | 2x read throughput | Potentially stale data (eventual consistency) |

---

## 8. Payment System (like Stripe)

We've been building up to this one. Everything you've learned in the previous case studies — idempotency, distributed state, exactly-once semantics, audit trails — converges here, in the system where getting it wrong has direct financial consequences.

The non-functional requirements for payments are different from every other system. Most systems optimize for availability. Payments optimize for correctness. You'd rather have your payment system go down for 30 seconds than process the same charge twice. That's a fundamental difference from the AP (availability + partition-tolerance) systems we've been building — this is a CP (consistency + partition-tolerance) system.

That choice cascades through every design decision: PostgreSQL over distributed NoSQL, synchronous over async, single-primary over distributed writes. Every decision you make with "but what if we need to scale?" in mind might actually make payments less safe.

> **The moment it gets hard:** A merchant retries a payment request because they didn't get a response. The original request already went through. How do you prevent a double charge without adding a round-trip that makes payments slower?

### Requirements

**Functional:**
- Process payments (credit card, bank transfer, digital wallets)
- Refunds (full and partial)
- Recurring billing / subscriptions
- Multi-currency support
- Payment status tracking
- Merchant dashboard and reporting
- Webhook notifications to merchants

**Non-Functional:**
- 10,000 transactions per second at peak
- Exactly-once payment processing (no double charges)
- 99.999% availability for payment processing
- PCI DSS compliance (card data never stored in plaintext)
- All transactions must be auditable (immutable ledger)
- Strong consistency (eventual consistency = lost money)

### Capacity Estimation

```
Transactions:
  Peak: 10,000 TPS
  Daily: ~200M transactions
  Avg transaction record: 1 KB

Storage:
  200M x 1KB = 200 GB/day
  Per year: 73 TB (must retain 7+ years for compliance)

Ledger entries (double-entry, 2 rows per transaction):
  400M entries/day x 200B = 80 GB/day

Idempotency keys:
  200M/day x 64B = ~13 GB/day, retain 24 hours -> 13 GB in Redis
```

### API Design

```
-- Create a payment intent (reserves amount, not yet charged)
POST /api/v1/payment_intents
Headers: Authorization: Bearer sk_live_xxx
         Idempotency-Key: uuid-unique-per-request
Body: {
  "amount": 2999,             -- in cents
  "currency": "usd",
  "payment_method": "pm_card_visa",
  "merchant_id": "merch_123",
  "metadata": { "order_id": "ORD-456" }
}
Response: {
  "id": "pi_abc123",
  "status": "requires_confirmation",
  "amount": 2999,
  "currency": "usd"
}

-- Confirm (charge the payment)
POST /api/v1/payment_intents/{id}/confirm
Response: { "id": "pi_abc123", "status": "succeeded" }

-- Refund
POST /api/v1/refunds
Body: {
  "payment_intent_id": "pi_abc123",
  "amount": 1500,             -- partial refund
  "reason": "customer_request"
}
```

The two-step intent + confirm pattern isn't just an API design choice — it's a safeguard. The intent captures the amount and payment method without charging yet. The confirm step is what actually moves money. If the client crashes between the two steps, nobody gets charged.

### Data Model

**Database: PostgreSQL** (ACID transactions are non-negotiable for money)
**Redis:** Idempotency keys
**Kafka:** Event sourcing, webhook delivery

This is the clearest example in this chapter of Ch 2's principle: choose the database that matches your consistency requirements. Payments need ACID. Cassandra and DynamoDB (eventual consistency) are not options here.

```sql
-- Payment intents (state machine)
CREATE TABLE payment_intents (
    id                UUID PRIMARY KEY,
    merchant_id       UUID NOT NULL,
    amount            BIGINT NOT NULL,        -- in smallest currency unit (cents)
    currency          VARCHAR(3) NOT NULL,
    status            VARCHAR(30) NOT NULL,   -- requires_confirmation, processing,
                                              -- succeeded, failed, canceled
    payment_method_id UUID,
    idempotency_key   VARCHAR(255) UNIQUE,
    metadata          JSONB,
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW()
);

-- Ledger (immutable, append-only, double-entry bookkeeping)
CREATE TABLE ledger_entries (
    id                BIGSERIAL PRIMARY KEY,
    payment_intent_id UUID NOT NULL,
    account_id        UUID NOT NULL,          -- merchant, platform, or reserve account
    entry_type        VARCHAR(10) NOT NULL,   -- DEBIT or CREDIT
    amount            BIGINT NOT NULL,
    currency          VARCHAR(3) NOT NULL,
    balance_after     BIGINT NOT NULL,
    created_at        TIMESTAMP DEFAULT NOW()
);
-- Rule: SUM(debits) must always equal SUM(credits)

-- Idempotency store
CREATE TABLE idempotency_keys (
    key               VARCHAR(255) PRIMARY KEY,
    request_hash      BYTEA NOT NULL,         -- hash of request body
    response          JSONB,
    status_code       INT,
    created_at        TIMESTAMP DEFAULT NOW(),
    expires_at        TIMESTAMP NOT NULL       -- 24 hour TTL
);
```

### High-Level Architecture

```
 ┌──────────────┐
 │  Merchant    │
 │  Server      │
 └──────┬───────┘
        │ HTTPS + Idempotency-Key
 ┌──────▼───────────┐
 │   API Gateway    │
 │  (TLS termination│
 │   rate limiting) │
 └──────┬───────────┘
        │
 ┌──────▼───────────┐     ┌─────────────────┐
 │  Payment Service │────►│  Redis           │
 │  (orchestrator)  │     │  (idempotency    │
 └──────┬───────────┘     │   keys cache)    │
        │                 └─────────────────┘
        │
   ┌────┼──────────────────────────┐
   │    │                          │
   │  ┌─▼──────────────────┐       │
   │  │ PostgreSQL (primary)│       │
   │  │                    │       │
   │  │ BEGIN;             │       │
   │  │  INSERT payment    │       │
   │  │  INSERT ledger (D) │       │
   │  │  INSERT ledger (C) │       │
   │  │  UPDATE balance    │       │
   │  │ COMMIT;            │       │
   │  └────────┬───────────┘       │
   │           │                   │
   │  ┌────────▼───────────┐       │
   │  │  Read Replicas     │       │
   │  │  (reporting only)  │       │
   │  └────────────────────┘       │
   │                               │
   └───────────┬───────────────────┘
               │
        ┌──────▼──────┐        ┌─────────────┐
        │    Kafka    │───────►│  Webhook     │
        │  (events)   │        │  Delivery    │
        └──────┬──────┘        │  Service     │
               │               └─────────────┘
        ┌──────▼──────┐
        │Card Network │  (Visa, Mastercard via payment processor)
        │  Gateway    │
        └─────────────┘
```

### Deep Dive

**1. Exactly-Once Processing via Idempotency**

The most critical invariant: a payment must never be processed twice. Network timeouts, client retries, and connection failures all cause duplicate requests. The idempotency key system guarantees safety:

```
process_payment(request, idempotency_key):
    -- Step 1: Check if we already processed this
    existing = redis.GET("idemp:" + idempotency_key)
    if existing:
        if hash(request) != existing.request_hash:
            return 422 "Idempotency key reused with different params"
        return existing.response  -- replay cached response

    -- Step 2: Acquire lock (prevent concurrent retries)
    locked = redis.SET("lock:" + idempotency_key, 1, NX, EX, 30)
    if not locked:
        return 409 "Request in progress"

    -- Step 3: Process in a single DB transaction
    BEGIN TRANSACTION
        INSERT INTO payment_intents (...)
        INSERT INTO ledger_entries (debit)
        INSERT INTO ledger_entries (credit)
        INSERT INTO idempotency_keys (key, request_hash, response)
    COMMIT

    -- Step 4: Cache response in Redis
    redis.SET("idemp:" + idempotency_key, response, EX, 86400)
    redis.DEL("lock:" + idempotency_key)

    return response
```

The response is stored inside the database transaction. If the system crashes after COMMIT, the idempotency key is in the database and Redis can be repopulated on the next request. If the system crashes before COMMIT, the transaction is rolled back and the next retry processes it fresh.

**2. Double-Entry Ledger**

This is accounting 101, but it's also the most important data integrity tool in any financial system. Every money movement creates exactly two ledger entries that sum to zero:

```
Payment of $29.99 from customer to merchant:
  DEBIT  customer_funding_account   $29.99
  CREDIT merchant_settlement_account $29.99

Platform fee of $0.90:
  DEBIT  merchant_settlement_account $0.90
  CREDIT platform_revenue_account    $0.90

Invariant check (run every hour):
  SELECT SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END)
  FROM ledger_entries;
  -- Must ALWAYS equal 0
```

If that sum is ever non-zero, money is missing. Run this check every hour. Page someone if it fails. It should never fail, but when it does, you want to know immediately.

**3. Reconciliation**

Daily reconciliation catches discrepancies between internal ledger and external payment processor:

```
1. Export all transactions from payment processor (Visa/MC settlement files)
2. Compare with internal ledger entries
3. Flag mismatches:
   - Transaction in ledger but not in processor -> reversed/declined we missed
   - Transaction in processor but not in ledger -> system bug, immediate alert
4. Auto-resolve known patterns, escalate unknowns to ops team
```

Reconciliation is your safety net. Even with idempotency and ACID transactions, edge cases happen. The reconciliation job catches them before they become financial discrepancies.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| PostgreSQL (single primary) over distributed DB | True ACID, zero split-brain risk | Vertical scaling limit (~50K TPS); need sharding by merchant at scale |
| Idempotency key in both Redis + DB | Fast lookup + durable record | Slight complexity, 13 GB Redis |
| Double-entry ledger | Full auditability, invariant checking | 2x storage vs. single-entry |
| Synchronous card processing | Merchant gets immediate response | Higher latency (~500 ms for card network round-trip) |

---

## 9. Video Streaming Platform (like YouTube/Netflix)

Scale up the numbers, and suddenly the design space changes completely.

1 billion daily active users. 30 minutes of video per user per day. Do the math: that's about 13 terabytes per second of video delivered. Every second. The bandwidth alone would overwhelm any database, any web server cluster, any reasonable infrastructure. The only thing that makes this work is a global CDN, and the only thing that makes the CDN work is a transcoding pipeline that prepares content in every format, every resolution, ahead of time.

But there's a subtlety: you can't store video on traditional infrastructure. One video at 4K is multiple gigabytes. 500,000 new videos per day, each in 7 different resolutions and 2 codecs, is 3.5 petabytes of new storage every day. Object storage (S3/GCS) is the only answer — and once you're on object storage, your architecture looks completely different from the other case studies.

> **The moment it gets hard:** A creator uploads a 10 GB 4K video. Your system needs to transcode it into 7 resolutions x 2 codecs = 14 jobs, each taking 5-30 minutes. Meanwhile, 500,000 other creators did the same thing today. How do you manage 6 million transcoding jobs per day without burning your cloud bill?

### Requirements

**Functional:**
- Upload videos (up to 10 GB)
- Transcode to multiple resolutions and codecs
- Adaptive bitrate streaming (ABR)
- Search and browse catalog
- View count, likes, comments
- Personalized recommendation feed

**Non-Functional:**
- 1B DAU, average 30 minutes of video watched per day
- Upload: 500K new videos/day
- Playback start latency < 2 seconds
- 99.99% availability for playback
- Support 480p to 4K; multiple codecs (H.264, H.265, VP9, AV1)
- Global audience (multi-region CDN)

### Capacity Estimation

```
Video playback:
  1B DAU x 30 min = 30B minutes/day of video watched
  Avg bitrate (mix of resolutions): 5 Mbps
  30B min x 60 sec x 5 Mbps = 9 x 10^12 Mb/day = 1.125 PB/day bandwidth
  Egress: ~13 TB/s (avg), served 95%+ from CDN

Upload:
  500K videos/day, avg 500 MB = 250 TB/day raw uploads
  After transcoding (multiple resolutions): ~3x = 750 TB/day

Storage:
  Total video storage (growing): multi-exabyte (S3/GCS)

Transcoding:
  500K videos x 6 resolutions x 2 codecs = 6M transcoding jobs/day
  = ~70 jobs/sec; each takes 5-30 min
  Need: ~2,000-10,000 transcoding workers (burst to handle backlog)
```

13 TB/s of egress. That's not a number you serve from your own data centers — that's what CDNs are built for. Your architecture has to assume that video bytes are served by the CDN, not your application servers.

### API Design

```
-- Upload (two-phase: get presigned URL, then upload directly to S3)
POST /api/v1/videos/upload-url
Body: { "filename": "vacation.mp4", "size_bytes": 524288000 }
Response: {
  "upload_id": "upl_abc",
  "upload_url": "https://s3.../presigned?...",
  "expires_in": 3600
}

-- Confirm upload and start processing
POST /api/v1/videos
Body: {
  "upload_id": "upl_abc",
  "title": "My Vacation",
  "description": "...",
  "tags": ["travel", "beach"]
}
Response: { "video_id": "vid_xyz", "status": "processing" }

-- Get video for playback (returns ABR manifest)
GET /api/v1/videos/{id}/manifest
Response: {
  "video_id": "vid_xyz",
  "dash_url": "https://cdn.../vid_xyz/manifest.mpd",
  "hls_url": "https://cdn.../vid_xyz/master.m3u8",
  "thumbnails": [...]
}

-- Recommendations
GET /api/v1/feed/recommended?limit=20
```

### Data Model

**PostgreSQL:** Video metadata, users, comments
**Elasticsearch:** Video search
**S3/GCS:** Raw and transcoded video files
**Redis:** View counts, caching
**Cassandra:** User watch history (for recommendations)

```sql
-- Video metadata
CREATE TABLE videos (
    id              UUID PRIMARY KEY,
    uploader_id     BIGINT NOT NULL,
    title           VARCHAR(200),
    description     TEXT,
    status          VARCHAR(20),    -- uploading, processing, ready, failed
    duration_sec    INT,
    resolutions     JSONB,          -- ["480p","720p","1080p","4k"]
    storage_path    TEXT,           -- S3 prefix
    thumbnail_urls  TEXT[],
    view_count      BIGINT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Transcoding jobs
CREATE TABLE transcoding_jobs (
    id              UUID PRIMARY KEY,
    video_id        UUID NOT NULL,
    resolution      VARCHAR(10),    -- "1080p"
    codec           VARCHAR(10),    -- "h264", "vp9"
    status          VARCHAR(20),    -- queued, running, completed, failed
    output_path     TEXT,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP
);
```

### High-Level Architecture

```
                        ┌──────────────┐
                        │   Clients    │
                        │(web/mobile/TV)│
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────▼──────┐ ┌──────▼──────┐  ┌──────▼──────┐
       │  CDN Edge   │ │  CDN Edge   │  │  CDN Edge   │
       │  (US-East)  │ │  (EU-West)  │  │  (AP-South) │
       └──────┬──────┘ └──────┬──────┘  └──────┬──────┘
              │               │                │
              └───────────────┼────────────────┘
                              │ (cache miss)
                       ┌──────▼──────┐
                       │   Origin    │
                       │   Storage   │
                       │   (S3/GCS)  │
                       └──────┬──────┘
                              │
  ┌───────────────────────────┼───────────────────────┐
  │                           │                       │
  │  UPLOAD PATH              │  PLAYBACK PATH        │
  │                           │                       │
  │  ┌──────────┐      ┌─────▼─────┐   ┌──────────┐  │
  │  │ Upload   │      │ API       │   │ Search   │  │
  │  │ Service  │      │ Gateway   │   │ Service  │  │
  │  └────┬─────┘      └─────┬─────┘   │(Elastic) │  │
  │       │                  │          └──────────┘  │
  │  ┌────▼─────┐     ┌─────▼─────┐                  │
  │  │  S3 Raw  │     │  Video    │                  │
  │  │  Bucket  │     │  Metadata │                  │
  │  └────┬─────┘     │  Service  │                  │
  │       │           └───────────┘                  │
  │  ┌────▼──────────────┐                           │
  │  │  Message Queue    │                           │
  │  │  (SQS/Kafka)      │                           │
  │  └────┬──────────────┘                           │
  │       │                                          │
  │  ┌────▼──────────────────────┐                   │
  │  │  Transcoding Workers      │                   │
  │  │  (GPU instances, auto-    │                   │
  │  │   scaled, spot/preemptible│                   │
  │  │                           │                   │
  │  │  Raw -> 480p, 720p, 1080p,│                   │
  │  │        4K (H.264 + VP9)   │                   │
  │  └────┬──────────────────────┘                   │
  │       │                                          │
  │  ┌────▼─────┐                                    │
  │  │S3 Output │                                    │
  │  │+ Manifest│                                    │
  │  └──────────┘                                    │
  └──────────────────────────────────────────────────┘
```

### Deep Dive

**1. Upload and Transcoding Pipeline**

The upload flow is designed to bypass your application servers entirely for the heavy bytes:

```
Upload flow:
1. Client requests presigned S3 URL (direct upload, bypasses our servers)
2. Client uploads to S3 (supports multipart for large files)
3. S3 event triggers Lambda / message to SQS
4. Upload service validates: file type, size, virus scan
5. Creates transcoding jobs (one per resolution x codec):
   - 480p H.264, 720p H.264, 1080p H.264, 4K H.264
   - 720p VP9, 1080p VP9, 4K VP9
6. Each worker:
   a. Downloads raw from S3
   b. Transcodes using FFmpeg (GPU-accelerated)
   c. Segments output into 4-second chunks (for ABR)
   d. Uploads chunks + manifest to output S3 bucket
7. When all jobs complete: update video status to "ready"
```

Transcoding is the bottleneck. Use spot/preemptible GPU instances at 60-70% cost savings. Jobs are idempotent (you can restart a failed transcode from scratch) and can retry on preemption without losing progress.

**2. Adaptive Bitrate Streaming (ABR)**

This is how Netflix and YouTube handle variable network conditions. The video is pre-cut into 4-second segments at each quality level. The player picks which quality to use per segment based on measured bandwidth:

```
HLS Master Playlist (master.m3u8):
  #EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
  360p/playlist.m3u8
  #EXT-X-STREAM-INF:BANDWIDTH=2400000,RESOLUTION=1280x720
  720p/playlist.m3u8
  #EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
  1080p/playlist.m3u8

Each resolution playlist:
  #EXTINF:4.000,
  segment_001.ts
  #EXTINF:4.000,
  segment_002.ts
  ...
```

The player starts at a low resolution (fast start — no buffering), then upgrades as it measures bandwidth. If the network degrades, it switches back down. Each 4-second segment is an independent file on the CDN — the player can switch resolution at any segment boundary.

**3. CDN and Popularity Tiers**

Not all videos need the same storage treatment. Use tiered storage to optimize cost:

| Tier | Videos | Storage | Access pattern |
|------|--------|---------|----------------|
| **Hot** (< 1 week old or trending) | Top 1% by views | CDN edge (all regions) | Direct CDN serve |
| **Warm** (moderate views) | Next 10% | CDN origin (2-3 regions) | CDN pulls on first access |
| **Cold** (long tail) | Remaining 89% | S3 Standard | CDN pulls, higher latency |
| **Archive** (rarely watched) | Views < 10/year | S3 Glacier | Pull + transcode on demand |

The long tail of rarely-watched videos is the storage budget killer — millions of videos that get a few views per year. S3 Glacier and similar archival tiers cost a fraction of standard storage, with the tradeoff of seconds to minutes for the first byte. For a video that gets 5 views per year, that's acceptable.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Direct-to-S3 upload | No bandwidth through our servers | More complex client implementation |
| Spot/preemptible for transcoding | 60-70% cost savings | Jobs may be interrupted and restarted |
| 4-second segments | Quick quality switching | More files to manage (millions per video) |
| Multi-codec (H.264 + VP9) | Better compression (VP9), broader compatibility (H.264) | 2x transcoding cost and storage |

---

## 10. Ride-Sharing Service (like Uber)

We're finishing with my favorite case study, because it combines everything: real-time location tracking, geospatial indexing, matching algorithms, dynamic pricing, payments, and global scale. Every subsystem is interesting on its own, and they're all tightly coupled.

Here's the core problem: 5 million drivers are moving around in real-time. When a rider requests a pickup, you need to find the best available driver within 3 km in under 5 seconds — accounting for traffic, driver rating, and whether the driver's vehicle type matches the request. You're running a spatial query against 5 million moving points, thousands of times per second, with a hard latency budget.

And while you're doing that, every driver is sending a location update every 3 seconds. That's 1.67 million writes per second to your geospatial index. Any time a driver finishes a trip, accepts a request, or goes offline, the index has to update. This is a system that never stops moving.

> **The moment it gets hard:** 1.67 million location updates per second. Every write updates a geospatial index that's being read 230 times per second for driver matching. Standard databases can't keep up. What do you use instead?

### Requirements

**Functional:**
- Riders request rides by specifying pickup and destination
- Match riders with nearby available drivers
- Real-time GPS tracking during the trip
- Dynamic pricing (surge) based on demand/supply
- ETA calculation (pickup and trip)
- Payment processing at trip completion
- Rating system (rider and driver)

**Non-Functional:**
- 20M daily rides, 5M concurrent drivers
- Match latency < 5 seconds (from request to driver assignment)
- Location updates: every 3 seconds from active drivers
- ETA accuracy: within 2 minutes for trips under 30 minutes
- 99.95% availability
- Cover 500 cities worldwide

### Capacity Estimation

```
Ride requests:
  20M rides/day = ~230 rides/sec (avg)
  Peak (evening rush, global aggregate): ~1,500 rides/sec

Location updates:
  5M active drivers x 1 update/3 sec = 1.67M location updates/sec
  Each update: driver_id (8B) + lat (8B) + lng (8B) + timestamp (8B) + status (1B) = ~33B
  Bandwidth: 1.67M x 33B = ~55 MB/s

Geospatial index:
  5M driver locations, each in a geohash cell
  Index size: 5M x 50B = 250 MB (fits in memory)

Trip storage:
  20M trips/day x 2 KB = 40 GB/day
  Location trail: avg 20 min trip x 1 update/3 sec x 33B = ~13 KB per trip
  20M x 13 KB = 260 GB/day of location history
```

That 250 MB geospatial index is the key insight. It fits in RAM. You can keep the entire driver location index in memory and update it 1.67 million times per second without hitting disk.

### API Design

```
-- Request a ride
POST /api/v1/rides/request
Body: {
  "rider_id": "rider_123",
  "pickup": { "lat": 37.7749, "lng": -122.4194 },
  "destination": { "lat": 37.3382, "lng": -121.8863 },
  "ride_type": "standard"
}
Response: {
  "ride_id": "ride_abc",
  "status": "matching",
  "estimated_fare": { "min": 2500, "max": 3200, "currency": "usd" },
  "surge_multiplier": 1.3,
  "pickup_eta_seconds": 240
}

-- Driver location update (high frequency, sent via WebSocket or UDP)
PUT /api/v1/drivers/{id}/location
Body: { "lat": 37.7752, "lng": -122.4186, "heading": 45, "speed_mph": 25 }

-- Driver accepts/rejects ride
POST /api/v1/rides/{id}/accept
POST /api/v1/rides/{id}/reject

-- Get ride status (for rider, real-time)
WS /ws/rides/{id}/track
  Server pushes: { "driver_location": {...}, "eta_seconds": 180, "status": "en_route" }
```

### Data Model

**PostgreSQL:** Users, trips, payments
**Redis (with geospatial):** Real-time driver locations and availability
**Kafka:** Location stream, trip events, pricing events
**PostGIS/H3:** Geospatial indexing for matching

```sql
-- Trips
CREATE TABLE trips (
    id              UUID PRIMARY KEY,
    rider_id        BIGINT NOT NULL,
    driver_id       BIGINT,
    status          VARCHAR(20),     -- matching, accepted, en_route_pickup,
                                     -- in_progress, completed, canceled
    pickup_lat      DOUBLE PRECISION,
    pickup_lng      DOUBLE PRECISION,
    dest_lat        DOUBLE PRECISION,
    dest_lng        DOUBLE PRECISION,
    ride_type       VARCHAR(20),     -- standard, premium, pool
    surge_multi     DECIMAL(3,2),
    fare_cents      INT,
    distance_miles  DECIMAL(8,2),
    duration_sec    INT,
    requested_at    TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP
);

-- Redis geospatial (driver positions)
-- Using Redis GEOADD for real-time spatial queries
GEOADD drivers:available -122.4194 37.7749 "driver_456"
GEOADD drivers:available -122.4180 37.7755 "driver_789"

-- Find drivers within 3 km of a point
GEORADIUS drivers:available -122.4194 37.7749 3 km ASC COUNT 10
-- Returns: ["driver_789" (0.2 km), "driver_456" (0.5 km), ...]
```

### High-Level Architecture

```
 ┌──────────┐     ┌──────────┐
 │  Rider   │     │  Driver  │
 │   App    │     │   App    │
 └────┬─────┘     └────┬─────┘
      │                │
      │    WebSocket    │  Location updates (3s interval)
      │                │
 ┌────▼────────────────▼────┐
 │      API Gateway         │
 └────┬─────────────────┬───┘
      │                 │
 ┌────▼──────┐   ┌──────▼──────────┐
 │  Ride     │   │  Location       │
 │  Service  │   │  Service        │
 │           │   │  (ingests GPS)  │
 └────┬──────┘   └──────┬──────────┘
      │                 │
      │          ┌──────▼──────┐
      │          │   Redis     │
      │          │  GEO Index  │
      │          │(5M drivers) │
      │          └──────┬──────┘
      │                 │
 ┌────▼──────┐   ┌──────▼──────┐    ┌──────────────┐
 │  Matching │   │   ETA       │    │   Pricing    │
 │  Service  │◄──┤   Service   │    │   Service    │
 │ (dispatch)│   │ (routing +  │    │  (surge,     │
 └────┬──────┘   │  traffic)   │    │   fare est.) │
      │          └─────────────┘    └──────┬───────┘
      │                                    │
      │          ┌──────────────┐          │
      └─────────►│  Kafka       │◄─────────┘
                 │ (trip events,│
                 │  location    │
                 │  stream)     │
                 └──────┬───────┘
                        │
              ┌─────────┼──────────┐
              │         │          │
       ┌──────▼───┐ ┌───▼────┐ ┌──▼──────────┐
       │PostgreSQL│ │Payment │ │ Analytics   │
       │ (trips)  │ │Service │ │(supply/     │
       └──────────┘ └────────┘ │ demand heat │
                               │ maps)       │
                               └─────────────┘
```

### Deep Dive

**1. Driver Matching Algorithm**

When a ride request comes in, you have 5 seconds to find and assign a driver. Here's the algorithm:

```
match_driver(pickup_location, ride_type):
    -- Step 1: Find nearby available drivers (< 3 km)
    candidates = redis.GEORADIUS("drivers:available", lat, lng, 3, "km",
                                 ASC, COUNT, 20)

    -- Step 2: Filter by ride type eligibility
    candidates = [d for d in candidates if d.vehicle_type matches ride_type]

    -- Step 3: Score each candidate
    for driver in candidates:
        driver.score = (
            w1 * (1 / distance_to_pickup(driver))     -- closer is better
          + w2 * driver.rating                          -- higher rated preferred
          + w3 * driver.acceptance_rate                 -- reliable drivers preferred
          + w4 * (1 / eta_to_pickup(driver))           -- accounts for traffic
        )

    -- Step 4: Send request to top-scored driver
    best = max(candidates, key=score)
    send_ride_request(best, timeout=15_seconds)

    -- Step 5: If rejected/timeout, try next driver
    -- Up to 3 attempts, then expand search radius to 5 km
```

The algorithm favors proximity (faster for the rider) but also accounts for driver quality. A driver with a 4.9 rating and 95% acceptance rate is worth a small distance penalty over a 4.2-rated driver who's slightly closer.

**2. Geospatial Indexing with H3**

Redis GEORADIUS works well but has limits at very large scale. For production Uber-style matching at 5M drivers, use Uber's H3 hexagonal grid:

```
1. Divide the world into hexagonal cells (resolution 7: ~5 km^2 each)
2. Each driver belongs to one cell based on current location
3. When matching: find the cell of the pickup, then search that cell
   + its 6 neighbors (ring-1) for drivers
4. If not enough drivers, expand to ring-2 (18 more cells)

Advantages over rectangular grids:
  - All neighbors are equidistant (no corner problem)
  - Uniform coverage at any latitude
  - Hierarchical: zoom in/out by changing resolution
```

The corner problem with rectangular grids: a point at the corner of a cell is equidistant from 4 cells, but the grid only assigns it to one. With hexagonal grids, every cell has 6 neighbors and no corner case. Distance calculations are more uniform.

**3. Dynamic Pricing (Surge)**

Surge pricing is a balancing mechanism: when demand exceeds supply in an area, prices rise to attract more drivers and reduce rider demand until equilibrium is reached. The algorithm runs per geographic cell, every 2 minutes:

```
Every 2 minutes, per cell:
  demand = ride_requests_last_5_min
  supply = available_drivers_in_cell

  ratio = demand / max(supply, 1)

  surge_multiplier = case
    when ratio < 0.5  -> 1.0   (normal)
    when ratio < 1.0  -> 1.0 + (ratio - 0.5) * 0.5
    when ratio < 2.0  -> 1.25 + (ratio - 1.0) * 0.75
    when ratio < 4.0  -> 2.0 + (ratio - 2.0) * 0.5
    else              -> min(ratio, 5.0)  (cap at 5x)

  -- Smooth transitions: new_surge = 0.7 * old_surge + 0.3 * calculated_surge
```

The smoothing factor (0.7 old + 0.3 new) prevents rapid oscillations — without it, surge would jump to 2x, attract drivers, drop to 1x, lose drivers, jump again. The exponential smoothing creates stable convergence.

Surge is shown to riders before they confirm. It incentivizes drivers to move toward high-demand areas and gives riders the choice to wait for lower prices.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Redis GEO over PostGIS for real-time | Sub-millisecond spatial queries | Less sophisticated spatial operations (no polygon queries) |
| H3 hexagonal grid | Uniform neighbor distances, hierarchical zoom | Library dependency, learning curve |
| 3-second location updates | Smooth real-time tracking | 1.67M updates/sec ingestion load |
| Sequential driver offers (not broadcast) | No conflicts / "stolen rides" | Slower matching if first driver rejects |

---

## Appendix: Quick Reference Comparison

| System | Primary DB | Cache | Queue | Key Challenge |
|--------|-----------|-------|-------|---------------|
| **URL Shortener** | PostgreSQL | Redis | Kafka | Short code generation without collision |
| **Rate Limiter** | Redis | -- | -- | Distributed counting accuracy |
| **Chat System** | Cassandra | Redis | Kafka | Message ordering + real-time delivery |
| **Notification System** | PostgreSQL | Redis | Kafka | Priority processing + deduplication |
| **News Feed** | PostgreSQL | Redis | Kafka | Fan-out strategy for celebrities |
| **Search Autocomplete** | PostgreSQL | CDN + in-memory trie | Kafka | Sub-100ms prefix matching at scale |
| **Distributed Cache** | In-memory | -- | -- | Consistent hashing + eviction |
| **Payment System** | PostgreSQL | Redis | Kafka | Exactly-once processing + auditability |
| **Video Streaming** | PostgreSQL + S3 | CDN | SQS | Transcoding pipeline + global CDN |
| **Ride-Sharing** | PostgreSQL + Redis GEO | Redis | Kafka | Real-time geospatial matching |

### Common Patterns Across All Systems

Step back and look at the ten systems. A few patterns appear everywhere:

1. **Idempotency everywhere writes matter.** URL shortener, payment system, notification system — every system where a duplicate write causes user-visible harm uses idempotency keys. This isn't a payment-specific concern; it's a distributed systems fundamental (Ch 1).

2. **Async processing separates latency from throughput.** The redirect doesn't do analytics. The chat server doesn't wait for Cassandra. The payment API doesn't deliver the webhook. Fast paths stay fast by deferring heavy work to queues.

3. **Cache aggressively, invalidate carefully.** The 80/20 rule appears in every design. Cache the hot 20% of data, and most reads never reach the database. Cache invalidation is only hard when data is mutable — URL shortener avoids it by making URLs immutable, payment system avoids it by making the ledger append-only.

4. **Shard by natural key.** `conversation_id` for chat, `user_id` for feeds, `video_id` for streaming. The natural partition key is almost always obvious from the access pattern — and choosing correctly means you never need cross-shard transactions.

5. **Design for failure at every level.** Rate limiter fails open. Chat falls back to push notifications. Notification system retries with exponential backoff. Every external dependency will fail. The question isn't whether, but when — and whether your system fails gracefully or catastrophically.

6. **Monitor the business metric, not just the infrastructure.** "Messages delivered per second" matters more than "CPU at 60%." "Payments succeeded per second" matters more than "database response time." Infrastructure metrics tell you *how* the system is performing; business metrics tell you *whether* it's doing what it's supposed to do.

These patterns are not coincidences — they're solutions to the fundamental problems of distributed systems that Ch 1, Ch 2, and Ch 3 formalize. Every case study here is a specific application of those universal principles.

Now go build something.

---

*Next: [Chapter 24 — Production Readiness and Incident Response](24-production-readiness.md)*

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M76: System Design Interview Practice](../course/modules/loop-3/L3-M76-system-design-interview-practice.md)** — Work through full system design problems with the same structure as this chapter: requirements, capacity, components, trade-offs
- **[L3-M88: The TicketPulse Architecture Review](../course/modules/loop-3/L3-M88-architecture-review.md)** — Review the complete TicketPulse architecture you've built across all three loops and identify what you'd change now
- **[L3-M61: Multi-Region Design](../course/modules/loop-3/L3-M61-multi-region-design.md)** — Take one of the single-region designs from this chapter and extend it to survive a full region failure

### Quick Exercises

1. **Pick one case study from this chapter and redesign it for 100x the traffic: write down which components break first, what you'd change, and what new failure modes you'd introduce.**
2. **Draw a C4 Level 2 (Container) diagram of your current system — identify every process boundary, data store, and external dependency, then count how many you couldn't draw from memory.**
3. **Practice explaining your system's architecture in 5 minutes to someone who hasn't seen it — record yourself, then identify the moment where you started hand-waving instead of being precise.**

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

Step-by-step design of real-world systems — from requirements to capacity estimation to API design to schema to architecture. Each case study follows the same framework so you build a repeatable design muscle.

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
- Ch 1 (distributed systems theory)
- Ch 2 (database selection and modeling)
- Ch 3 (architecture patterns)
- Ch 13 (cloud integration)
- Ch 22 (algorithms behind these systems)

---

## 0. The System Design Framework

Every case study in this chapter follows the same seven-step framework. Internalize it and you can design any system under pressure.

### Step 1: Requirements Clarification

Before drawing a single box, ask questions. Split requirements into two buckets:

**Functional Requirements (FR):** What does the system *do*? User-facing features, core operations, edge cases.

**Non-Functional Requirements (NFR):** How does the system *behave*? Latency, availability, consistency, durability, scale.

> **Rule of thumb:** Spend 5 minutes on requirements in a 45-minute interview. In production, spend 5 days.

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

### Step 3: API Design

Define the external contract. For each endpoint:
- HTTP method + path
- Request parameters / body
- Response shape
- Authentication / rate limiting notes

### Step 4: Data Model

Choose the database(s) and define schemas. Justify why:
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

### Data Model

**Database: PostgreSQL** (strong consistency for writes) + **Redis** (cache for reads)

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

### Deep Dive

**1. Short Code Generation: Hash vs. Counter**

| Approach | Pros | Cons |
|----------|------|------|
| **MD5/SHA256 hash + truncate** | No coordination needed | Collisions require retries; longer codes |
| **Base62 counter (auto-increment)** | No collisions, predictable length | Sequential = guessable; single point of coordination |
| **Pre-generated ID range** | No runtime collision; distributed | Requires a range allocator service |

**Chosen approach: Range-based counter.** A ZooKeeper/etcd coordinator assigns each app server a range (e.g., server A gets 1M-2M, server B gets 2M-3M). Each server increments locally and converts to Base62. No collisions, no runtime coordination, 7 chars supports 62^7 = 3.5 trillion URLs.

```
Base62 encoding: [0-9a-zA-Z]
ID 1000000 -> base62 -> "4c92"
ID 3521614606208 -> base62 -> "zzzzzz" (6 chars, ~3.5T IDs)
```

**2. Read Path Optimization**

The read path (redirect) is latency-critical. Optimization layers:

1. **CDN caching:** Popular short URLs are cached at the edge. Set `Cache-Control: public, max-age=3600` for 301 redirects.
2. **Redis cache:** On cache miss from CDN, check Redis. 2 GB cache covers 20% of daily traffic (80/20 rule handles the rest).
3. **Database read replicas:** On Redis miss, query a read replica. Only the write path hits the primary.

Cache invalidation is simple: URLs are immutable. Only expiration requires eviction (use Redis TTL).

**3. Analytics Pipeline**

Click tracking must not slow down redirects. Fire-and-forget approach:

1. Read service publishes a click event to Kafka (async, non-blocking).
2. A consumer writes aggregated counts to ClickHouse every 10 seconds.
3. `click_count` in PostgreSQL is updated via a periodic batch job (not on every click).

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Base62 counter over hash | Zero collisions, shorter codes | Need a range coordinator (added complexity) |
| 301 (permanent) redirect | CDN caching, lower latency | Cannot track every click (cached at CDN) |
| Async analytics | Redirect latency unaffected | Click counts are eventually consistent (seconds of delay) |
| PostgreSQL over NoSQL | ACID for URL creation | Vertical scaling limit (~50K writes/sec) |

---

## 2. Rate Limiter

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

### API Design

The rate limiter is middleware, not a user-facing API. But it exposes headers:

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

### Deep Dive

**1. Algorithm Comparison**

| Algorithm | Accuracy | Memory | Burst handling | Complexity |
|-----------|----------|--------|----------------|------------|
| **Fixed window counter** | Low (boundary burst) | Very low | Poor — 2x burst at boundary | Simple |
| **Sliding window log** | Perfect | High (stores every request) | Perfect | Moderate |
| **Sliding window counter** | Good (~0.003% error) | Low | Good | Moderate |
| **Token bucket** | Good | Very low | Allows controlled bursts | Simple |
| **Leaky bucket** | Good | Very low | No bursts (smooth output) | Simple |

**Chosen approach: Sliding window counter** for most rules (good accuracy, low memory). Token bucket for endpoints that should allow short bursts.

Sliding window counter formula:
```
count = (prev_window_count * overlap%) + current_window_count

Example: 100 req/min limit, we are 30s into current minute
  prev_window had 80 requests
  current_window has 25 requests
  estimated count = 80 * 0.5 + 25 = 65  (under limit, allow)
```

**2. Distributed Counting with Redis**

Race condition: two servers read the same counter, both see room, both increment. Solution: use Redis Lua scripts for atomic check-and-increment:

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

| Failure | Strategy |
|---------|----------|
| Redis node down | **Fail open** — allow all traffic. Degraded accuracy is better than total outage. Fall back to local in-memory counters. |
| Network partition | Each partition rate-limits independently. Effective limit may temporarily double. Acceptable trade-off. |
| Clock skew | Use Redis server time (`TIME` command), not app server time. |
| Hot key (single client doing millions of requests) | Hash to a specific Redis shard. If one client dominates, their key is isolated. |

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Sliding window counter over exact log | 10x less memory | ~0.003% counting error |
| Redis over local memory | Consistent limits across servers | +1-2 ms network latency per request |
| Fail-open on Redis failure | 100% availability | Temporarily no rate limiting |
| Lua scripts for atomicity | Race-condition-free counting | Slightly higher Redis CPU |

---

## 3. Chat System (like Slack/WhatsApp)

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

### Data Model

**Database: Cassandra** (write-heavy, time-series messages, easy partitioning by conversation)
**Presence & routing: Redis**
**Media: S3 + CDN**

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

**2. Ordering Guarantees**

Messages within a conversation must be ordered. Across conversations, ordering does not matter.

- Use **TIMEUUID** (Cassandra) — combines timestamp + node ID + sequence. Monotonically increasing per-node.
- Kafka topic partitioned by `conversation_id` — all messages for one conversation go to the same partition, preserving order.
- For conflict resolution (two users send at the same millisecond): TIMEUUID's built-in uniqueness resolves ties deterministically.

**3. Group Chat Fan-out**

For a group of N members, sending a message means delivering to N-1 recipients:

- **Small groups (< 50):** Fan-out on write. When a message arrives, look up all members, find their WebSocket servers, deliver immediately. Write once to Cassandra (single partition by conversation_id).
- **Large groups (50-500):** Same write-once storage, but fan-out delivery goes through a dedicated "group delivery" worker pool to avoid blocking the chat server.
- **Read receipts in groups:** Only track "last read message ID" per user per conversation. Do not send individual read receipts for every message in large groups.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Cassandra over PostgreSQL | Horizontal write scaling, natural time-series partitioning | No cross-conversation transactions or JOINs |
| WebSocket over long-polling | True real-time, lower overhead | Stateful connections require sticky sessions |
| Redis Pub/Sub for cross-server delivery | Low-latency routing between servers | Messages lost if subscriber is temporarily disconnected (Kafka is the durable backup) |
| TIMEUUID over application-level clocks | No clock sync needed across servers | IDs are larger (16 bytes vs. 8 bytes for an integer) |

---

## 4. Notification System

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

Four Kafka topics, one per priority level. Workers consume from higher-priority topics first:

```
Topic: notifications.critical  -> 50 consumer instances, 0 lag tolerance
Topic: notifications.high      -> 30 consumer instances
Topic: notifications.normal    -> 20 consumer instances
Topic: notifications.low       -> 5 consumer instances, batch every hour
```

Critical notifications (2FA codes, fraud alerts) bypass the normal queue entirely and are processed by a dedicated fast-path with its own APNs/FCM connections.

**2. Deduplication**

The `idempotency_key` prevents duplicate sends. Two-layer check:

1. **Redis SET NX** with TTL: `SETNX dedup:{idempotency_key} 1 EX 86400` — if key exists, reject immediately.
2. **PostgreSQL UNIQUE constraint** on `idempotency_key` — catches any race conditions that slip past Redis.

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

Push delivery confirmation comes from APNs/FCM callbacks. Email: track via SES webhooks (bounce, complaint, delivery). SMS: Twilio status callbacks.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Kafka over simple queue (SQS) | Priority topics, replay capability, high throughput | Operational complexity of running Kafka |
| At-least-once over exactly-once delivery | Simpler, no 2PC needed | Users may get duplicate notifications (mitigated by dedup) |
| Separate workers per channel | Independent scaling, isolated failures | More services to deploy and monitor |
| 90-day log retention | Audit trail, debugging | 22.5 TB storage cost |

---

## 5. News Feed / Timeline (like Twitter)

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

The core challenge: when a celebrity with 50M followers posts, fan-out-on-write means writing to 50M feed caches. That takes minutes.

**Hybrid approach:**

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

Step 2-4 adds ~50-100 ms but avoids billions of fan-out writes.

**2. Feed Ranking**

Raw chronological feed is noisy. Apply a ranking model:

```
score = w1 * recency + w2 * affinity + w3 * engagement + w4 * content_type

Where:
  recency    = decay_function(now - post.created_at)
  affinity   = how often user interacts with this author
  engagement = (likes + comments + shares) / impressions
  content_type = boost for images/video vs plain text
```

The ranking service is a lightweight ML model (logistic regression or small neural net) that scores each candidate post. It runs at read time on the merged candidate set.

**3. Pagination with Ranking**

Cannot use simple offset pagination (rankings change between page loads). Use cursor-based pagination:

- Cursor = `(score, post_id)` of the last item on the current page.
- Next page: `WHERE (score, post_id) < (cursor_score, cursor_post_id) ORDER BY score DESC, post_id DESC LIMIT 20`

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Hybrid fan-out | Handles celebrities without melting infrastructure | More complex read path (merge step) |
| Pre-computed feed cache | < 100 ms read latency | 480 GB Redis for feed caches |
| ML ranking over chronological | Higher engagement, relevant content | Transparency — users do not understand why they see what they see |
| Cursor pagination over offset | Stable pagination, no duplicates/skips | Cannot "jump to page 50" |

---

## 6. Search Autocomplete

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

Each node stores a character and a pointer to children. At each node, we also store the top-K suggestions for that prefix (pre-computed).

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

Why pre-compute top-K at each node instead of traversing all leaves at query time? Because traversal would take O(n) where n is the number of descendants — far too slow for 100 ms latency.

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

For truly real-time trending (e.g., during a breaking news event), a small "overlay" of trending queries is merged at query time.

**3. CDN Caching**

Most autocomplete requests are for common prefixes. Cache aggressively:

- Top 1000 prefixes (1-3 characters): cache at CDN with TTL=5min. This covers ~50% of all requests.
- All other prefixes: cache with TTL=1hr.
- Cache key: `autocomplete:{lang}:{prefix}`

At 250K peak QPS, if CDN absorbs 50%, autocomplete servers only see 125K QPS.

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Full trie in memory | < 10 ms lookup | 18 GB RAM per server, must fit in memory |
| Rebuild over incremental | Simple, no concurrency issues | 15-minute delay for new trends |
| Pre-computed top-K per node | O(1) query time | Larger trie, rebuild takes longer |
| CDN caching | 50% traffic reduction | Stale suggestions for up to 5 minutes |

---

## 7. Distributed Cache (like Memcached/Redis Cluster)

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

Instead of `hash(key) % N` (which breaks when nodes change), use hash slots:

```
1. Hash the key: slot = CRC16(key) % 16384
2. Each node owns a range of slots (16384 slots total)
3. Node 1: slots 0-5460, Node 2: slots 5461-10922, Node 3: slots 10923-16383
```

When adding a node: reassign some slots from existing nodes to the new node. Only keys in moved slots need to migrate — not all keys.

**Virtual nodes** improve distribution: each physical node appears at multiple points on the hash ring, preventing hot spots when nodes have different capacities.

**2. Eviction Policies**

When memory is full, which keys to evict?

| Policy | Description | Use case |
|--------|-------------|----------|
| **LRU** (Least Recently Used) | Evict key accessed longest ago | General-purpose caching |
| **LFU** (Least Frequently Used) | Evict key accessed fewest times | When popular keys should persist |
| **TTL-based** | Evict keys closest to expiration | When TTLs are well-calibrated |
| **Random** | Evict random key | When all keys are equally important |
| **volatile-lru** | LRU among keys with TTL set | Keep permanent keys, evict cached data |

Redis uses **approximated LRU** — samples N random keys and evicts the one with the oldest access time. This is O(1) vs. true LRU's O(n) for maintaining a linked list.

**3. Cache Stampede Prevention**

When a popular key expires, hundreds of servers simultaneously cache-miss and hit the database. Solutions:

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

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Hash slots (16384) over pure consistent hashing | Deterministic slot assignment, easy migration | Fixed upper bound on sharding granularity |
| Approximated LRU over true LRU | O(1) eviction, no memory overhead for LRU list | ~3% worse hit rate than true LRU |
| Async replication | Lower write latency | Small window of data loss on primary failure |
| Replica reads | 2x read throughput | Potentially stale data (eventual consistency) |

---

## 8. Payment System (like Stripe)

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

### Data Model

**Database: PostgreSQL** (ACID transactions are non-negotiable for money)
**Redis:** Idempotency keys
**Kafka:** Event sourcing, webhook delivery

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

The most critical invariant: a payment must never be processed twice. The idempotency key system guarantees this:

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

**2. Double-Entry Ledger**

Every money movement creates exactly two ledger entries that sum to zero:

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

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| PostgreSQL (single primary) over distributed DB | True ACID, zero split-brain risk | Vertical scaling limit (~50K TPS); need sharding by merchant at scale |
| Idempotency key in both Redis + DB | Fast lookup + durable record | Slight complexity, 13 GB Redis |
| Double-entry ledger | Full auditability, invariant checking | 2x storage vs. single-entry |
| Synchronous card processing | Merchant gets immediate response | Higher latency (~500 ms for card network round-trip) |

---

## 9. Video Streaming Platform (like YouTube/Netflix)

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

Transcoding is the bottleneck. Use spot/preemptible GPU instances at 60-70% cost savings. Jobs are idempotent and can retry on preemption.

**2. Adaptive Bitrate Streaming (ABR)**

The video player dynamically switches quality based on network conditions:

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

The player starts at a low resolution (fast start), then upgrades as it measures bandwidth. Each 4-second segment is an independent file on the CDN — the player can switch resolution at any segment boundary.

**3. CDN and Popularity Tiers**

Not all videos are equal. Use tiered storage:

| Tier | Videos | Storage | Access pattern |
|------|--------|---------|----------------|
| **Hot** (< 1 week old or trending) | Top 1% by views | CDN edge (all regions) | Direct CDN serve |
| **Warm** (moderate views) | Next 10% | CDN origin (2-3 regions) | CDN pulls on first access |
| **Cold** (long tail) | Remaining 89% | S3 Standard | CDN pulls, higher latency |
| **Archive** (rarely watched) | Views < 10/year | S3 Glacier | Pull + transcode on demand |

### Trade-offs

| Decision | What we gained | What we sacrificed |
|----------|---------------|--------------------|
| Direct-to-S3 upload | No bandwidth through our servers | More complex client implementation |
| Spot/preemptible for transcoding | 60-70% cost savings | Jobs may be interrupted and restarted |
| 4-second segments | Quick quality switching | More files to manage (millions per video) |
| Multi-codec (H.264 + VP9) | Better compression (VP9), broader compatibility (H.264) | 2x transcoding cost and storage |

---

## 10. Ride-Sharing Service (like Uber)

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

When a ride request comes in, find the best driver:

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

**2. Geospatial Indexing with H3**

Redis GEORADIUS works but has limits at scale. For 5M drivers, use Uber's H3 hexagonal grid:

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

**3. Dynamic Pricing (Surge)**

Surge pricing balances supply and demand. For each H3 cell:

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

Surge is shown to riders BEFORE they confirm, and it incentivizes drivers to move toward high-demand areas.

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

1. **Idempotency:** Every write operation should be safe to retry (URL shortener, payment system, notification system).
2. **Async processing:** Separate the fast path (user response) from heavy work (transcoding, fan-out, analytics).
3. **Cache aggressively, invalidate carefully:** 80/20 rule applies everywhere. Cache the hot data, accept staleness for the rest.
4. **Shard by natural key:** conversation_id for chat, user_id for feeds, video_id for streaming.
5. **Design for failure:** Every external call will eventually fail. Use retries, circuit breakers, fallbacks, and dead letter queues.
6. **Monitor the business metric, not just the infrastructure:** "Messages delivered per second" matters more than "CPU at 60%."

---

*Next: [Chapter 24 — Production Readiness and Incident Response](24-production-readiness.md)*

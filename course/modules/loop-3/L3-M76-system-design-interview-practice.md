# L3-M76: System Design Interview Practice

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 90 min | 🟢 Core | Prerequisites: All Loop 2 modules (distributed systems, databases, messaging)
>
> **Source:** Chapter 32 of the 100x Engineer Guide

## What You'll Learn

- How to apply the 7-step system design framework under time pressure
- How to design three different systems from scratch: URL Shortener, Chat System, Notification Service
- The patterns that appear across all system designs (queues, caching, database choice, scaling)
- How to think out loud, discuss trade-offs, and structure your reasoning during an interview

## Why This Matters

System design interviews are the highest-signal interview format for senior engineering roles. They test whether you can reason about trade-offs, scope a problem, and communicate your thinking -- not whether you can memorize solutions.

The three systems in this module exercise different muscles: URL Shortener tests data modeling and scaling, Chat System tests real-time communication and ordering guarantees, Notification Service tests multi-channel delivery and reliability. Together, they cover the patterns you will encounter in 80% of system design interviews.

> 💡 **Insight**: "The best system design answers are not the most complex. They are the most clearly reasoned. An interviewer would rather hear 'I am choosing PostgreSQL because the access pattern is read-heavy with complex joins, and I am accepting the scaling limitation because our estimated QPS fits on a single primary with read replicas' than hear 'Let me use Cassandra, DynamoDB, and Redis for different parts of the system.'"

---

## The Framework (Review)

Every design follows 7 steps. Time-box each one.

```
SYSTEM DESIGN FRAMEWORK
════════════════════════

Step 1: Requirements (5 min)
  Functional: What does it DO?
  Non-Functional: How does it BEHAVE? (latency, availability, scale)

Step 2: Capacity Estimation (3 min)
  DAU, QPS, storage, bandwidth

Step 3: API Design (5 min)
  Endpoints, parameters, responses

Step 4: Data Model (5 min)
  Tables/collections, relationships, indexes

Step 5: High-Level Architecture (5 min)
  Boxes and arrows: clients, LB, services, DB, cache, queues

Step 6: Deep Dive (5 min)
  Pick 1-2 interesting problems and go deep

Step 7: Monitoring & Operations (2 min)
  How do you know it is working? How do you deploy safely?
```

---

## System 1: URL Shortener (30 minutes)

Set a 30-minute timer. Do not read ahead.

### Step 1: Requirements

**Functional:**
- Given a long URL, generate a short URL (e.g., `https://short.ly/abc123`)
- Given a short URL, redirect to the original long URL
- Users can optionally specify a custom short URL
- Short URLs expire after a configurable TTL (default: 5 years)

**Non-Functional:**
- Very low latency on redirect (< 50ms p99)
- High availability (redirects must work even if creation is down)
- Scale: 100M URLs created/month, 10B redirects/month

**Clarifying questions you should ask:**
- Do we need analytics? (clicks per URL, geographic distribution, referrers)
- Do we need rate limiting? (prevent abuse / spam)
- Do we support custom domains? (e.g., `brand.co/promo`)

### Step 2: Capacity Estimation

```
WRITES: 100M URLs/month
  = 100M / (30 * 86400) ≈ 40 URLs/second (avg)
  = 40 * 3 ≈ 120 URLs/second (peak)

READS: 10B redirects/month (100:1 read/write ratio)
  = 10B / (30 * 86400) ≈ 3,850 redirects/second (avg)
  = 3,850 * 3 ≈ 11,500 redirects/second (peak)

STORAGE:
  Average URL: 500 bytes (short URL + long URL + metadata)
  Per year: 100M * 12 * 500 bytes = 600 GB/year
  5-year retention: 3 TB

CACHE:
  80/20 rule: 20% of URLs get 80% of traffic
  Hot set: 100M * 12 * 20% = 240M URLs * 500 bytes ≈ 120 GB
  Use Redis cluster with ~128 GB capacity
```

### Step 3: API Design

```
POST /api/v1/urls
  Body: { "long_url": "https://...", "custom_alias": "promo", "ttl_days": 365 }
  Response: { "short_url": "https://short.ly/abc123", "expires_at": "..." }
  Auth: API key required

GET /{short_code}
  Response: 301 Redirect to long URL
  (No auth -- public access)

GET /api/v1/urls/{short_code}/stats
  Response: { "clicks": 1234, "created_at": "...", "last_clicked": "..." }
  Auth: API key required (owner only)
```

### Step 4: Data Model

```sql
-- Primary store: PostgreSQL (or DynamoDB for higher scale)
CREATE TABLE urls (
  id            BIGSERIAL PRIMARY KEY,
  short_code    VARCHAR(10) UNIQUE NOT NULL,
  long_url      TEXT NOT NULL,
  user_id       BIGINT,
  created_at    TIMESTAMP DEFAULT NOW(),
  expires_at    TIMESTAMP,
  click_count   BIGINT DEFAULT 0
);

CREATE INDEX idx_urls_short_code ON urls(short_code);
CREATE INDEX idx_urls_expires_at ON urls(expires_at) WHERE expires_at IS NOT NULL;
```

**Short code generation:**
- Option A: Base62 encoding of auto-increment ID (simple, sequential, predictable)
- Option B: Random 7-character Base62 string (non-sequential, collision check needed)
- Option C: Hash of long URL, take first 7 chars (deterministic, same URL = same short code)
- Recommended: **Option B** with collision retry. 62^7 = 3.5 trillion possible codes.

### Step 5: High-Level Architecture

```
                    ┌─────────────┐
                    │   Clients   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Load Balancer│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐    │     ┌──────▼──────┐
       │  URL Service │    │     │  URL Service │
       │  (write)     │    │     │  (read)      │
       └──────┬──────┘    │     └──────┬──────┘
              │            │            │
              │     ┌──────▼──────┐     │
              │     │    Redis    │◄────┘
              │     │   Cache     │
              │     └─────────────┘
              │            │
       ┌──────▼────────────▼──────┐
       │    PostgreSQL             │
       │  (primary + replicas)    │
       └──────────────────────────┘
```

**Read path (redirect):**
1. Check Redis cache for short_code → long_url
2. Cache hit: return redirect (< 5ms)
3. Cache miss: query read replica, populate cache, return redirect

**Write path (create):**
1. Generate short code
2. Write to PostgreSQL primary
3. Populate Redis cache
4. Return short URL

### Step 6: Deep Dive -- Analytics at Scale

If every redirect logs a click event, that is 3,850 events/second. Writing each click directly to PostgreSQL would overwhelm the database.

```
ANALYTICS PIPELINE
──────────────────

Redirect → Kafka (click events) → Consumer → TimescaleDB/ClickHouse

Click event: { short_code, timestamp, ip, user_agent, referrer, country }

- Kafka absorbs the write volume (3,850/sec is trivial for Kafka)
- Consumer batches writes to an analytics database
- Pre-aggregate popular metrics (clicks per hour per URL)
- The click_count on the urls table is updated async (every 60s)
```

### Step 7: What Did You Miss?

Compare your design against this checklist:

```
□ Analytics / click tracking
□ Rate limiting (prevent abuse)
□ Custom domains (multi-tenant)
□ URL expiration (TTL + cleanup job)
□ Spam/phishing detection (validate destination URLs)
□ 301 vs 302 redirect (301 is cached by browsers -- less analytics accuracy)
□ Handling URL encoding / unicode
□ Monitoring: redirect latency, cache hit rate, error rate
```

---

## System 2: Chat System (30 minutes)

Set a 30-minute timer.

### Step 1: Requirements

**Functional:**
- 1:1 messaging between users
- Group chat (up to 500 members)
- Online/offline presence indicators
- Read receipts (delivered, read)
- Message history (searchable, paginated)
- File/image sharing

**Non-Functional:**
- Message delivery latency < 500ms for online users
- Messages must not be lost (at-least-once delivery)
- Support 50M DAU, 500M messages/day
- Message ordering must be correct within a conversation

### Step 2: Capacity Estimation

```
MESSAGES: 500M/day
  = 500M / 86400 ≈ 5,800 messages/second (avg)
  = 5,800 * 5 ≈ 29,000 messages/second (peak)

CONNECTIONS: 50M DAU, ~30% concurrently online
  = 15M concurrent WebSocket connections

STORAGE:
  Average message: 200 bytes (text + metadata)
  Per day: 500M * 200 bytes = 100 GB/day
  Per year: 36.5 TB/year

BANDWIDTH:
  Each message delivered to avg 1.5 recipients (1:1 + group mix)
  = 5,800 * 1.5 * 200 bytes ≈ 1.7 MB/second outbound (manageable)
```

### Step 3: API Design

```
WebSocket: /ws/chat
  Client sends:
    { type: "message", conversation_id, content, media_url? }
    { type: "typing", conversation_id }
    { type: "read", conversation_id, message_id }

  Server sends:
    { type: "message", conversation_id, sender_id, content, timestamp, message_id }
    { type: "typing", conversation_id, sender_id }
    { type: "read", conversation_id, reader_id, message_id }
    { type: "presence", user_id, status: "online"|"offline" }

REST (for history, not real-time):
  GET /api/v1/conversations/{id}/messages?before={cursor}&limit=50
  POST /api/v1/conversations (create group)
  POST /api/v1/media/upload (file sharing)
```

### Step 4: Data Model

```sql
-- Conversations
CREATE TABLE conversations (
  id            UUID PRIMARY KEY,
  type          VARCHAR(10) NOT NULL, -- 'direct', 'group'
  name          VARCHAR(255),
  created_at    TIMESTAMP DEFAULT NOW()
);

-- Conversation membership
CREATE TABLE conversation_members (
  conversation_id  UUID REFERENCES conversations(id),
  user_id          BIGINT NOT NULL,
  joined_at        TIMESTAMP DEFAULT NOW(),
  last_read_at     TIMESTAMP,
  PRIMARY KEY (conversation_id, user_id)
);

-- Messages (partitioned by conversation for locality)
-- Consider Cassandra for write-heavy at extreme scale
CREATE TABLE messages (
  id               UUID PRIMARY KEY,
  conversation_id  UUID NOT NULL,
  sender_id        BIGINT NOT NULL,
  content          TEXT,
  media_url        TEXT,
  created_at       TIMESTAMP DEFAULT NOW(),
  -- Ordering: use created_at + id for tie-breaking
  INDEX idx_messages_conv_time (conversation_id, created_at DESC)
);
```

### Step 5: High-Level Architecture

```
┌──────────┐     WebSocket      ┌──────────────────┐
│  Client  │◄──────────────────►│ Chat Gateway     │
└──────────┘                    │ (connection mgmt)│
                                └────────┬─────────┘
                                         │
                                ┌────────▼─────────┐
                                │  Message Router   │
                                │  (which server    │
                                │   holds user X?)  │
                                └────────┬─────────┘
                                         │
                    ┌────────────────────┬┴──────────────────┐
                    │                    │                    │
             ┌──────▼──────┐    ┌───────▼──────┐    ┌───────▼──────┐
             │  Redis Pub   │    │  PostgreSQL  │    │  Object      │
             │  Sub (fanout)│    │  (messages)  │    │  Storage     │
             └─────────────┘    └──────────────┘    │  (media)     │
                                                    └──────────────┘
```

**Message delivery flow:**
1. Sender sends message over WebSocket to Chat Gateway
2. Chat Gateway writes to PostgreSQL (persistence first)
3. Chat Gateway publishes to Redis Pub/Sub channel for the conversation
4. All Chat Gateway instances subscribed to that channel receive the message
5. Each gateway checks if any of their connected users are in the conversation
6. Online recipients get the message over WebSocket immediately
7. Offline recipients get the message from history on next connection

**Presence:**
- Each Chat Gateway tracks its connected users
- Presence events published to Redis
- Users subscribe to presence of their contacts

### Step 6: Deep Dive -- Message Ordering in Groups

```
THE ORDERING PROBLEM
────────────────────

In a group chat, Alice and Bob both send a message at the "same time."
Alice's gateway receives her message at 14:00:00.001
Bob's gateway receives his message at 14:00:00.002

But Bob's message reaches the database FIRST (network jitter).
Database order: Bob, Alice
Intended order: Alice, Bob (Alice sent first)

Solutions:
1. Server timestamp at first gateway (not DB write time)
   - Each gateway stamps messages with its local clock
   - Clock skew between gateways can still cause issues

2. Logical clocks (Lamport timestamps)
   - Each conversation maintains a counter
   - Guarantees causal ordering within a conversation

3. Hybrid: server timestamp + message ID for tie-breaking
   - Good enough for chat (humans cannot perceive <100ms differences)
   - Simpler than logical clocks

Recommended: Option 3 for a chat app. Perfect ordering is
overkill when the tolerance is human perception speed.
```

### Step 7: What Did You Miss?

```
□ Offline message delivery (push notifications)
□ Message search (Elasticsearch index)
□ File sharing (upload to S3, CDN for delivery)
□ Message editing and deletion
□ Encryption (end-to-end for 1:1, server-side for groups)
□ Rate limiting (prevent spam, slow loris)
□ Typing indicators (ephemeral, do not persist)
□ Message reactions
□ Connection handling (reconnection, heartbeats, backoff)
□ Monitoring: connection count, message latency, delivery success rate
```

---

## System 3: Notification Service (30 minutes)

Set a 30-minute timer.

### Step 1: Requirements

**Functional:**
- Send notifications across multiple channels: push, email, SMS, in-app
- User preference management (opt in/out per channel, per notification type)
- Notification templates with variable substitution
- Priority levels (urgent, normal, low)
- Delivery tracking (sent, delivered, read, failed)
- Deduplication (same notification not sent twice)

**Non-Functional:**
- Urgent notifications delivered within 30 seconds
- Normal notifications delivered within 5 minutes
- At-least-once delivery (never lose a notification)
- Support 1B notifications/day across all channels
- 99.9% delivery success rate

### Step 2: Capacity Estimation

```
VOLUME: 1B notifications/day
  = 1B / 86400 ≈ 11,500/second (avg)
  = 11,500 * 5 ≈ 57,500/second (peak)

BREAKDOWN BY CHANNEL (estimated):
  Push: 500M/day (50%)
  Email: 300M/day (30%)
  In-app: 150M/day (15%)
  SMS: 50M/day (5%) -- most expensive, lowest volume

STORAGE:
  Notification record: 500 bytes (template ID, user, channel, status, timestamp)
  Per day: 1B * 500 bytes = 500 GB/day
  Retention: 90 days = 45 TB (need time-series optimized storage)
```

### Step 3: API Design

```
POST /api/v1/notifications
  Body: {
    "user_id": "123",
    "template_id": "ticket-confirmed",
    "variables": { "event_name": "...", "seat": "..." },
    "channels": ["push", "email"],  // optional: override user prefs
    "priority": "urgent",
    "idempotency_key": "order-456-confirmation"
  }
  Response: { "notification_id": "...", "status": "queued" }

POST /api/v1/notifications/batch
  Body: { "notifications": [...] }  // up to 1000

GET /api/v1/notifications/{id}/status
  Response: { "id": "...", "channels": { "push": "delivered", "email": "sent" } }

PUT /api/v1/users/{id}/preferences
  Body: { "marketing": { "push": true, "email": false, "sms": false } }

GET /api/v1/users/{id}/notifications?page=1&limit=20
  Response: { "notifications": [...], "unread_count": 5 }
```

### Step 4: Data Model

```sql
-- Templates
CREATE TABLE notification_templates (
  id            VARCHAR(100) PRIMARY KEY,  -- e.g., 'ticket-confirmed'
  channel       VARCHAR(20) NOT NULL,      -- 'push', 'email', 'sms', 'in_app'
  subject       TEXT,                       -- for email
  body_template TEXT NOT NULL,             -- with {{variable}} placeholders
  version       INTEGER DEFAULT 1
);

-- Notification records (high volume -- partition by date)
CREATE TABLE notifications (
  id              UUID PRIMARY KEY,
  user_id         BIGINT NOT NULL,
  template_id     VARCHAR(100) NOT NULL,
  channel         VARCHAR(20) NOT NULL,
  priority        VARCHAR(10) DEFAULT 'normal',
  status          VARCHAR(20) DEFAULT 'queued',
  -- queued → sending → sent → delivered → read | failed
  variables       JSONB,
  idempotency_key VARCHAR(255),
  created_at      TIMESTAMP DEFAULT NOW(),
  sent_at         TIMESTAMP,
  delivered_at    TIMESTAMP,
  read_at         TIMESTAMP,
  failure_reason  TEXT
) PARTITION BY RANGE (created_at);

CREATE UNIQUE INDEX idx_notifications_idempotency
  ON notifications(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- User preferences
CREATE TABLE user_notification_preferences (
  user_id           BIGINT NOT NULL,
  notification_type VARCHAR(50) NOT NULL,  -- 'marketing', 'transactional', 'social'
  channel           VARCHAR(20) NOT NULL,
  enabled           BOOLEAN DEFAULT true,
  PRIMARY KEY (user_id, notification_type, channel)
);
```

### Step 5: High-Level Architecture

```
┌──────────────────┐
│ Notification API │  (accepts requests, validates, enqueues)
└────────┬─────────┘
         │
    ┌────▼─────┐
    │  Kafka   │  (priority topics: urgent, normal, low)
    └────┬─────┘
         │
    ┌────▼─────────────────────────────────────────────┐
    │              Notification Workers                  │
    │                                                   │
    │  ┌──────────┐ ┌──────────┐ ┌─────┐ ┌──────────┐ │
    │  │  Push    │ │  Email   │ │ SMS │ │  In-App  │ │
    │  │  Worker  │ │  Worker  │ │ Wkr │ │  Worker  │ │
    │  └────┬─────┘ └────┬─────┘ └──┬──┘ └────┬─────┘ │
    └───────┼────────────┼──────────┼──────────┼───────┘
            │            │          │          │
      ┌─────▼───┐  ┌─────▼───┐ ┌───▼────┐ ┌──▼────────┐
      │  APNs / │  │SendGrid/│ │ Twilio │ │ WebSocket/ │
      │  FCM    │  │  SES    │ │        │ │ SSE        │
      └─────────┘  └─────────┘ └────────┘ └───────────┘
```

**Flow:**
1. API receives notification request
2. Check idempotency key (reject duplicates)
3. Look up user preferences (skip opted-out channels)
4. Render template with variables
5. Enqueue to appropriate Kafka topic based on priority
6. Workers consume from topics, send through channel-specific providers
7. Record delivery status (webhook callbacks from providers)

### Step 6: Deep Dive -- Priority Queues and Rate Limiting

```
PRIORITY QUEUE DESIGN
─────────────────────

Three Kafka topics:
  notifications.urgent   → consumed with max parallelism
  notifications.normal   → consumed with standard parallelism
  notifications.low      → consumed during off-peak only

Urgent: password reset, purchase confirmation, security alerts
Normal: friend activity, event reminders
Low: marketing, weekly digests, recommendations

RATE LIMITING (per channel):
  Push: 10/minute per user (prevent notification fatigue)
  Email: 5/day per user (avoid spam classification)
  SMS: 3/day per user (most expensive, most intrusive)

  If rate limit exceeded:
  - Urgent: send anyway (security > rate limit)
  - Normal: queue for next available slot
  - Low: drop silently
```

### Step 7: What Did You Miss?

```
□ Rate limiting per user per channel
□ Template versioning and A/B testing
□ Delivery confirmation webhooks (from push/email providers)
□ Retry logic with exponential backoff for failed deliveries
□ Unsubscribe handling (one-click unsubscribe for email -- required by law)
□ Notification grouping/batching ("You have 5 new messages" instead of 5 separate pushes)
□ Timezone-aware scheduling (do not send marketing at 3 AM user's local time)
□ Analytics: open rates, click-through rates, opt-out rates
□ Provider failover (if SendGrid is down, fall back to SES)
□ Cost optimization (SMS is expensive; prefer push where possible)
□ Monitoring: queue depth, delivery latency, failure rate by channel/provider
```

---

## Cross-Cutting Patterns

### 🤔 Reflect: What Appears in ALL Three Designs?

After completing all three designs, identify the recurring patterns:

```
UNIVERSAL PATTERNS
══════════════════

1. MESSAGE QUEUES
   URL Shortener: Kafka for click analytics
   Chat System: Redis Pub/Sub for message fanout
   Notification: Kafka for priority-based delivery
   → Nearly every system needs async processing

2. CACHING
   URL Shortener: Redis for hot URLs
   Chat System: Redis for presence, recent messages
   Notification: Redis for user preferences, rate limits
   → Read-heavy paths always benefit from caching

3. DATABASE CHOICE MATCHES ACCESS PATTERN
   URL Shortener: key-value lookup → could use DynamoDB
   Chat System: ordered messages per conversation → Cassandra or partitioned Postgres
   Notification: high-volume writes with time partitioning → TimescaleDB or Cassandra

4. IDEMPOTENCY
   URL Shortener: same long URL → same short code (optional)
   Chat System: message deduplication on retry
   Notification: idempotency key prevents duplicate sends
   → Distributed systems must handle duplicates

5. MONITORING THE SAME THINGS
   Latency (p50, p95, p99)
   Error rate
   Queue depth / consumer lag
   Cache hit ratio
```

---

## Interview Tips

```
SYSTEM DESIGN INTERVIEW DO's
─────────────────────────────
✓ Think out loud. Silence is the enemy.
✓ Ask clarifying questions before designing.
✓ Start with requirements, not architecture.
✓ State trade-offs explicitly: "I am choosing X over Y because..."
✓ Use back-of-envelope math to justify capacity decisions.
✓ Draw the architecture. Visuals communicate faster than words.
✓ Go deep on 1-2 interesting problems rather than shallow on everything.
✓ Mention monitoring and operations. It shows production experience.

SYSTEM DESIGN INTERVIEW DON'Ts
──────────────────────────────
✗ Do not jump to architecture without requirements.
✗ Do not use technologies you cannot explain.
✗ Do not over-engineer. Start simple, scale when needed.
✗ Do not ignore the interviewer's hints. They are steering you.
✗ Do not memorize solutions. Interviewers can tell.
✗ Do not say "it depends" without saying what it depends ON.
```

---

## 🤔 Final Reflections

1. **Which of the three systems was hardest to design? Why?** What made it harder -- the scale, the real-time requirements, the data model, or something else?

2. **If you had 45 minutes instead of 30, where would you spend the extra time?** On deeper requirements? More detailed data model? Scaling analysis?

3. **What is the most common mistake you made across all three designs?** Identify your pattern: do you tend to skip requirements? Over-engineer the data model? Forget about monitoring?

4. **How does designing these systems compare to building TicketPulse?** What is different about designing from scratch vs. evolving an existing system?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Capacity estimation** | The process of calculating the compute, storage, and bandwidth resources a system needs to handle projected load. |
| **Back-of-envelope** | A rough, order-of-magnitude calculation used to quickly validate whether a design is feasible. |
| **Trade-off** | A deliberate decision to favor one quality (e.g., consistency) at the expense of another (e.g., latency). |
| **Deep dive** | A detailed examination of one component of a system design, covering data models, APIs, and failure modes. |
| **Bottleneck** | The single component or resource that limits the overall throughput of a system under load. |

## Further Reading

- **Chapter 23**: Full system design case studies with detailed reference solutions
- **"System Design Interview" by Alex Xu**: the most comprehensive interview prep book
- **"Designing Data-Intensive Applications" by Martin Kleppmann**: the theory behind the patterns
- **highscalability.com**: real architecture breakdowns from companies like Instagram, Uber, Netflix

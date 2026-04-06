# L3-M77: Architecture Decision Records

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 60 min | 🟢 Core | Prerequisites: All Loop 2 modules (microservices, Kafka, databases, CQRS)
>
> **Source:** Chapter 9 of the 100x Engineer Guide

## What You'll Learn

- How to write ADRs that are useful 18 months from now, not just today
- The difference between decisions worth documenting and decisions that are not
- How to articulate trade-offs, consequences, and reversal conditions
- How ADRs prevent "why did we build it this way?" conversations from consuming engineering time

## Why This Matters

TicketPulse has made dozens of architectural decisions over the course of this project. Some were deliberate. Some were accidental. Some were the right call at the time but would be the wrong call today. The problem is that none of them are documented.

Six months from now, a new engineer joins the team. They look at the architecture and ask: "Why are we using Kafka instead of SQS? Why microservices? Why PostgreSQL?" Without ADRs, the answers live in the heads of engineers who may have moved on. The team re-debates decisions that were already made, or worse, accidentally reverses good decisions because nobody remembers the reasoning.

ADRs are cheap to write and expensive to lack.

> **Pro tip:** "At Spotify, ADRs are stored alongside code in the repo. When an engineer asks 'why do we use gRPC instead of REST for service X?', the answer is in docs/adr/0012-grpc-for-internal-services.md. This eliminates repeated debates and 'I was not here when that was decided' syndrome."

---

### 🤔 Prediction Prompt

Before reading the ADR format, think about the last architectural decision your team made. Could a new engineer joining 6 months from now reconstruct the reasoning? If not, what information is missing?

## The ADR Format

Every ADR follows the same structure. Keep it short -- 1 to 2 pages maximum.

```
# ADR-NNN: [Short Descriptive Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
What is the issue or decision we face? What forces are at play?
What constraints exist? What prompted this decision now?

## Decision
What did we decide? Be specific. Not "we will use a message queue"
but "we will use Apache Kafka for inter-service event streaming."

## Consequences
What becomes easier? What becomes harder? What are we giving up?
What new problems does this create? What would trigger us to
reconsider this decision?
```

### What Makes a Good ADR

```
GOOD ADR CHARACTERISTICS
────────────────────────
- Answers "why," not just "what"
- Lists alternatives that were considered and why they were rejected
- States the consequences honestly (including downsides)
- Includes a reversal condition: "We would reconsider if..."
- Is written BEFORE implementation, not after
- Is short enough to read in 5 minutes

BAD ADR CHARACTERISTICS
───────────────────────
- Rubber stamps a decision already implemented
- Lists only benefits, no downsides
- Uses vague language: "we felt that..." "it seemed like..."
- Is so long nobody reads it
- Documents trivial decisions (which linter rules to use)
```

### When to Write an ADR

```
WRITE AN ADR WHEN:
- The decision affects the structure of the system
- The decision would be hard to reverse
- Multiple reasonable alternatives exist
- Future engineers will ask "why?"
- The decision crosses team boundaries

DO NOT WRITE AN ADR WHEN:
- The choice is obvious and uncontroversial
- The decision is easily reversible (library version, config value)
- The scope is a single function or file
- Nobody will ever wonder about the decision
```

---

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

## 🛠️ Build: 5 ADRs for TicketPulse

<details>
<summary>💡 Hint 1: Direction</summary>
Follow the ADR template: Status, Context (forces at play), Decision (specific, not vague), Consequences (what becomes easier AND harder), and a reversal condition. The key is listing rejected alternatives with reasons -- that is the information future engineers actually need.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
For each ADR, force yourself to name at least two alternatives you considered and why you rejected them. If you cannot name alternatives, the decision may be too obvious for an ADR -- or you have not explored the design space enough.
</details>


Write each of these ADRs. Spend about 8-10 minutes on each. The goal is not perfection -- it is practice articulating decisions with structure and honesty.

### ADR-001: Use Kafka for Inter-Service Event Streaming

```markdown
# ADR-001: Use Kafka for Inter-Service Event Streaming

## Status
Accepted

## Context
TicketPulse's microservices need to communicate asynchronously.
When a ticket is purchased, the order service must notify the
payment service, inventory service, notification service, and
analytics pipeline. We evaluated three options:

1. **Apache Kafka**: Distributed event streaming platform
2. **RabbitMQ**: Traditional message broker with AMQP
3. **AWS SQS + SNS**: Managed messaging with fan-out

Key requirements:
- Event replay: we want the ability to reprocess historical events
  (e.g., rebuild a read model, backfill analytics)
- Ordering: events for the same entity must be processed in order
  (e.g., "ticket reserved" before "ticket purchased")
- Throughput: peak of ~5,000 events/second during major event launches
- Consumer groups: multiple independent consumers per event stream

## Decision
We will use Apache Kafka (self-managed on AWS MSK) for all
inter-service event streaming.

## Consequences

### What becomes easier:
- Event replay: Kafka retains events for a configurable period
  (we set 7 days). Any consumer can reprocess from any offset.
- Ordering: Kafka guarantees ordering within a partition.
  We partition by entity ID (e.g., order_id) so all events
  for the same order are processed in sequence.
- Adding new consumers: new services can consume existing topics
  without modifying producers.
- Audit trail: the event log IS the audit trail.

### What becomes harder:
- Operations: Kafka requires operational expertise. Broker
  management, partition rebalancing, and consumer group
  monitoring are non-trivial.
- Schema evolution: changing event schemas requires careful
  versioning. We mitigate this with a schema registry.
- Exactly-once semantics: Kafka provides at-least-once by
  default. Consumers must be idempotent.
- Local development: running Kafka locally is heavier than
  a simple in-memory queue. We use Docker Compose with a
  single-broker setup.

### Alternatives rejected:
- **RabbitMQ**: excellent for task queues and routing, but
  no built-in event replay. We would need to separately persist
  events for reprocessing, duplicating the messaging layer.
- **SQS + SNS**: fully managed (less ops burden), but no
  ordering guarantees in standard queues, and FIFO queues
  have a 300 msg/sec limit per group. No event replay.

### We would reconsider this decision if:
- Operational overhead of Kafka exceeds 20% of a platform
  engineer's time
- AWS MSK costs exceed 3x the equivalent SQS + SNS setup
- The team shrinks below 5 engineers (Kafka ops burden
  becomes disproportionate)
```

### ADR-002: Limit Microservice Decomposition to 3-5 Services

```markdown
# ADR-002: Limit Microservice Decomposition to 3-5 Services

## Status
Accepted

## Context
After migrating from a monolith, we need to decide how many
microservices to create. The current architecture has 3 services:
order-service, payment-service, and event-service.

Some team members advocate for finer decomposition: separate
services for inventory, user management, notifications,
analytics, search, and recommendations. That would be 9 services.

Team size: 8 engineers.

## Decision
We will maintain 3-5 services maximum until the team grows
beyond 15 engineers. New features will be added to existing
services unless there is a clear domain boundary AND a
dedicated team to own the new service.

## Consequences

### What becomes easier:
- Deployment: 3 services means 3 CI/CD pipelines, 3 sets of
  dashboards, 3 on-call rotations. Manageable for 8 engineers.
- Debugging: fewer network boundaries means fewer places for
  requests to fail. A trace has 3-5 spans, not 15.
- Development velocity: most features can be built within a
  single service without cross-team coordination.

### What becomes harder:
- Service boundaries get blurry: the order-service will
  accumulate responsibilities that arguably belong in separate
  services (inventory, notifications). We accept this.
- A large service is harder to understand than a small one.
  We mitigate with clear module boundaries within each service.
- When we eventually do split, the extraction will be more work
  than if we had started with separate services.

### Alternatives rejected:
- **9 services from the start**: each service is small and
  focused, but 8 engineers cannot own 9 services. Each service
  needs monitoring, CI/CD, dependency updates, on-call coverage.
  The operational overhead would consume more time than the
  architectural benefit saves.
- **Monolith**: simpler operations, but we already experienced
  the coupling and deployment bottlenecks that motivated the
  split. Going back is not an option.

### We would reconsider this decision if:
- Team grows to 15+ engineers (enough for dedicated service teams)
- Deployment conflicts between features become frequent
  (a sign that the service boundary is wrong)
- A single service exceeds 100K lines of code
```

### ADR-003: PostgreSQL as Primary Database

```markdown
# ADR-003: PostgreSQL as Primary Database

## Status
Accepted

## Context
TicketPulse needs a primary database for transactional data:
users, events, orders, payments, tickets. We evaluated:

1. **PostgreSQL**: relational, ACID, mature, rich query support
2. **DynamoDB**: NoSQL, serverless, auto-scaling, key-value/document
3. **CockroachDB**: distributed SQL, horizontal scaling, PostgreSQL-compatible

Key requirements:
- Complex queries: join orders with events, filter by date range,
  aggregate revenue by venue. This is fundamentally relational.
- Transactions: ticket purchase requires atomic reserve + charge +
  confirm across multiple tables.
- Team familiarity: 7 of 8 engineers have PostgreSQL experience.
  0 have DynamoDB experience. 1 has CockroachDB experience.

## Decision
We will use PostgreSQL (AWS RDS) as the primary database for
all transactional data.

## Consequences

### What becomes easier:
- Complex queries: JOINs, CTEs, window functions, full-text search
  are first-class citizens. No need to denormalize for query patterns.
- Transactions: ACID guarantees across tables. A purchase either
  fully succeeds or fully rolls back.
- Tooling: pgAdmin, psql, pg_stat_statements, EXPLAIN ANALYZE --
  the ecosystem is mature and well-documented.
- Hiring: PostgreSQL experience is common. New engineers ramp up quickly.

### What becomes harder:
- Horizontal scaling: PostgreSQL scales vertically (bigger instance)
  and via read replicas. Sharding is manual and complex.
- Write throughput: single primary means all writes go to one machine.
  At extreme scale (>50K writes/second), this becomes a bottleneck.
- Schema migrations: ALTER TABLE on large tables can lock or be slow.
  Requires careful migration practices.

### Alternatives rejected:
- **DynamoDB**: excellent scalability, but the access patterns
  require designing around partition keys. Complex queries
  (joins, aggregations) require GSIs or a separate analytics
  store. The team has no DynamoDB experience, and the learning
  curve for correct data modeling is steep.
- **CockroachDB**: distributed SQL that scales horizontally, but
  adds latency for distributed transactions. Operational complexity
  is higher than RDS. The team is too small to absorb the ops
  overhead for scaling we do not yet need.

### We would reconsider this decision if:
- Write volume exceeds what a single RDS instance can handle
  (db.r6g.2xlarge: ~20K writes/sec sustained)
- Read replicas cannot keep up with read volume despite caching
- We need multi-region active-active (PostgreSQL does not support
  this natively without extensions like Citus)
```

### ADR-004: CQRS for Event Data, Not User Data

```markdown
# ADR-004: CQRS for Event Data, Not User Data

## Status
Accepted

## Context
TicketPulse has asymmetric read/write patterns for event data:
- Writes: event organizers create/update events (low volume, ~100/day)
- Reads: users browse, search, and filter events (high volume, ~500K/day)

The read model needs full-text search, geo-filtering, category
facets, and sorting by date/popularity. The write model needs
ACID transactions and relational integrity.

User data has roughly symmetric read/write patterns and does not
need full-text search or complex filtering.

## Decision
We will implement CQRS (Command Query Responsibility Segregation)
for event data: PostgreSQL as the write store, Elasticsearch as
the read store. User data will remain in PostgreSQL only.

## Consequences

### What becomes easier:
- Event search is fast: Elasticsearch handles full-text search,
  geo queries, faceted filtering, and relevance scoring natively.
- Read and write models can evolve independently: adding a new
  search facet does not require a schema migration.
- Read model can be rebuilt: if the Elasticsearch index becomes
  corrupted, we replay events from Kafka to rebuild it.

### What becomes harder:
- Eventual consistency: after an organizer updates an event,
  there is a delay (typically <2 seconds) before the change
  appears in search results.
- Two data stores to maintain: schema changes require updating
  both PostgreSQL and the Elasticsearch mapping.
- Debugging: "why is this event not appearing in search?" now
  requires checking the write store, the event bus, the sync
  consumer, and the read store.
- Complexity cost: CQRS is a pattern that engineers must
  understand. It adds cognitive overhead.

### Why NOT for user data:
- User read/write ratio is approximately 3:1 (not 5000:1 like events)
- User queries are simple: lookup by ID, email, or username
- PostgreSQL handles user queries efficiently with standard indexes
- Adding CQRS for users would double the complexity for minimal benefit

### We would reconsider this decision if:
- User data develops a highly asymmetric read/write pattern
  (e.g., social features with profile browsing)
- Elasticsearch operational costs or complexity become excessive
  relative to the search quality improvement
- A simpler solution (PostgreSQL full-text search with pg_trgm)
  proves sufficient for event search needs
```

### ADR-005: TypeScript for API Services

```markdown
# ADR-005: TypeScript for API Services

## Status
Accepted

## Context
TicketPulse's API services need a programming language. We
evaluated three options based on the team's skills, the ecosystem,
and the operational requirements:

1. **TypeScript (Node.js)**: dynamic runtime, vast ecosystem, typed
2. **Go**: compiled, fast, excellent concurrency primitives
3. **Kotlin (Spring Boot)**: JVM, strong typing, mature ecosystem

Team composition: 6 engineers with strong JavaScript/TypeScript
experience, 2 with Python experience, 1 with Go side-project
experience. Nobody has production Go or Kotlin experience.

## Decision
We will use TypeScript (Node.js) with Express/Fastify for all
API services.

## Consequences

### What becomes easier:
- Hiring: TypeScript/JavaScript is the most popular language
  for web backend development. The candidate pool is large.
- Full-stack capability: front-end and back-end share the same
  language. Engineers can work across the stack.
- Ecosystem: npm has libraries for every third-party integration
  we need (Stripe, SendGrid, AWS SDK, Kafka clients).
- Type safety: TypeScript catches entire classes of bugs at
  compile time that JavaScript misses. Refactoring is safer.
- Rapid iteration: no compile step (transpilation is fast),
  quick feedback loop during development.

### What becomes harder:
- CPU-bound workloads: Node.js is single-threaded by default.
  CPU-intensive operations (image processing, heavy computation)
  block the event loop. We mitigate with worker threads or
  offloading to dedicated services.
- Memory management: V8's garbage collector can cause latency
  spikes under high memory pressure. Requires tuning for
  production workloads.
- Concurrency model: callback/async-await is productive but
  error-prone. Missing an "await" silently drops errors.
- Runtime performance: Node.js is slower than Go for raw
  throughput. For our QPS (~5K requests/second peak), this
  is not a bottleneck, but it would matter at 100K+ QPS.

### Alternatives rejected:
- **Go**: better raw performance and memory efficiency, but
  the team has no production Go experience. The learning curve
  (error handling, lack of generics until recently, different
  ecosystem conventions) would slow the team for 3-6 months.
  Go is the better choice for infrastructure tooling and
  very high-throughput services, but not for our API services
  where developer productivity matters more than raw speed.
- **Kotlin/Spring Boot**: mature, excellent for large enterprises,
  strong typing with null safety. But the JVM has high memory
  overhead (each service needs 512MB+ minimum), longer startup
  times (affects scaling), and the team has no JVM experience.

### We would reconsider this decision if:
- A service needs sustained >50K requests/second (Go would
  handle this with fewer instances)
- CPU-bound processing becomes a core requirement (Go or Rust
  would be better)
- The team composition shifts toward JVM expertise
- Memory pressure from Node.js becomes operationally significant
```

---

## ADR Writing Workshop

Writing an ADR is a skill that develops with practice. These workshop exercises cover the common failure modes — the things engineers get wrong when writing ADRs for the first time.

### Workshop Exercise 1: From Bad to Good

Below is a poorly-written ADR. Identify all the problems, then rewrite it.

**The Bad ADR:**

```markdown
# ADR-006: Use Redis

## Status
Accepted

## Context
We needed a cache.

## Decision
We decided to use Redis because it is fast and popular.

## Consequences
It will make things faster.
We have to manage Redis.
```

**Problems to identify:**

```
Write your list of problems before reading the guidance below:
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
4. _______________________________________________
5. _______________________________________________
```

**Guidance — the problems with this ADR:**

1. **"We needed a cache" is not a context.** What were the specific performance problems? Which queries were slow? How slow? What was the user impact?

2. **"Fast and popular" is not a decision rationale.** Why Redis over Memcached? Over an in-process cache? Over CDN-level caching? The alternatives considered are missing entirely.

3. **No specific use cases.** Redis as a session store, Redis as a rate limiter, Redis as a pub/sub broker, and Redis as a cache have completely different implications. Which?

4. **"Make things faster" is not a consequence.** Faster by how much? Which operations? What is slower (Redis requires network round trips vs in-process memory)?

5. **No reversal condition.** When would you remove Redis? When would you switch to Memcached or a different approach?

**Now rewrite it:**

```markdown
# ADR-006: Use Redis for Session Storage and Event Listing Cache

## Status
Accepted

## Context
TicketPulse's event listing endpoint queries 8 database tables and takes
450ms on average. During peak traffic (concert on-sale events), the
endpoint receives 2,000 requests per second. With 8 database connections
per request, this saturates the database at ~300 concurrent requests.

We need:
1. Session storage: JWT tokens work but we need server-side invalidation
   for security incidents (force-logout all sessions for a compromised user).
2. Event listing cache: Reduce database load from browsing traffic.
3. Rate limiter state: Store token bucket state across pods.

Options evaluated:
1. **Redis**: In-memory store, pub/sub, TTL support, well-supported client libraries
2. **Memcached**: Simpler, slightly faster for pure caching, no pub/sub, no persistence
3. **In-process cache**: Zero network latency, but not shared across pods (stale data
   on different pods), cannot invalidate globally
4. **PostgreSQL itself**: Existing infrastructure, but adds load to the primary DB

## Decision
We will use Redis 7.x for:
- Session invalidation registry (SET session_id, TTL=24h, DEL on logout)
- Event listing cache (SETEX event:list:{params} 30, TTL=30s)
- Rate limiter token buckets (INCRBY with EXPIRE)

Hosted on: AWS ElastiCache Redis (Multi-AZ, single shard, cache.r7g.large)

## Consequences

### What becomes easier:
- Global session invalidation: DEL session_id works across all pods instantly
- Event listing latency: cache hits reduce from 450ms to <10ms (Redis RTT)
- Rate limiter: token bucket state is consistent across all API pods
- Horizontal scaling: all pods share the same cache state

### What becomes harder:
- Cache invalidation: we need to invalidate event cache entries when events
  are updated. We use a pattern-based key (event:list:*) and SCAN to find
  affected keys. This adds complexity.
- Availability dependency: if Redis goes down, session invalidation stops,
  caching stops, rate limiting falls back to in-process (approximate).
  We mitigate with Multi-AZ failover (~30s recovery time).
- Cold start: fresh Redis instance has empty cache; the database absorbs
  full traffic for ~2 minutes until the cache warms up.
- Cost: ~$200/month for ElastiCache on top of existing RDS cost.

### We would reconsider this decision if:
- Redis operational cost (cost + maintenance) exceeds $1,000/month
- A Redis outage causes more than 5 minutes of degraded service in a quarter
- We move to a different cloud where ElastiCache is unavailable
  (would switch to GCP Memorystore)
```

### Workshop Exercise 2: The Pre-Decision ADR

Most ADRs are written after the decision is made — they document what was decided, not what was considered. The best ADRs are written BEFORE the decision, as a structured way to think through the trade-offs.

Write a pre-decision ADR for this situation:

**Context**: TicketPulse needs to add search functionality. Users want to find events by: event name, artist, venue, city, date range, genre, and price range. Currently there are 500,000 events in the database. The product team expects search to be one of the top 3 most-used features.

**Your task**: Write the ADR before choosing the implementation. Include at least three options (PostgreSQL full-text search, Elasticsearch, Algolia/Typesense). Do NOT include the decision section yet — mark it as `[PENDING]`. The act of writing the context and options without committing to a choice often reveals which option is actually better.

```markdown
# ADR-NNN: Event Search Implementation

## Status
Proposed — decision pending engineering review

## Context
[Write this section — what is the specific problem? What are the query patterns?
What are the constraints? What is the scale?]

## Options Considered

### Option 1: PostgreSQL Full-Text Search (pg_trgm + tsvector)
Pros:
- [list them]
Cons:
- [list them]

### Option 2: Elasticsearch (self-managed or AWS OpenSearch)
Pros:
- [list them]
Cons:
- [list them]

### Option 3: Algolia / Typesense (managed search SaaS)
Pros:
- [list them]
Cons:
- [list them]

## Decision
[PENDING — bring this to engineering review on [date]]

## Consequences
[Leave blank until decision is made]
```

After writing the options section, which option is leading? Does writing the pros/cons change your initial instinct?

### Workshop Exercise 3: The Decision Log for a Live System

For TicketPulse, or your current production system, create a retrospective decision log. This is different from an ADR — it captures decisions that were made implicitly and never documented.

Go through the codebase and find 3-5 places where you can see that a decision was made but was never written down. Use these signals to find undocumented decisions:

```bash
# In a git repo, find long-standing "temporary" code
git log --all --oneline --format="%as %s" | grep -i "temp\|hack\|fixme\|todo\|workaround" | head -20

# Find large files that have grown organically (signs of architectural drift)
find src/ -name "*.ts" -exec wc -l {} \; | sort -rn | head -10

# Find places where the same pattern is implemented multiple ways
# (signals of unresolved architectural debate)
grep -r "fetch(" src/ | wc -l
grep -r "axios(" src/ | wc -l
# If both exist: there was a decision about HTTP clients that was never resolved
```

For each undocumented decision you find, write a one-paragraph retrospective:

```
UNDOCUMENTED DECISION: [What the code does]
WHEN: [Approximate date from git blame]
PROBABLE RATIONALE: [Why was this probably done?]
CURRENT ASSESSMENT: [Is this still the right decision? Would you change it today?]
ADR NEEDED: [Yes/No — and why]
```

---

## ADR Hygiene

### Rules for Maintaining ADRs

```
ADR HYGIENE RULES
═════════════════

1. STORE IN THE REPO
   ADRs live in docs/adr/ in the repository they affect.
   Not in Confluence. Not in Google Docs. Not in Notion.
   The code and the decisions about the code travel together.

2. NEVER DELETE AN ADR
   If a decision is reversed, create a new ADR that supersedes
   the old one. The old ADR's status changes to:
   "Superseded by ADR-XXX"
   The history of WHY a decision was made and later reversed
   is valuable.

3. NUMBER SEQUENTIALLY
   ADR-001, ADR-002, ADR-003. The number is an ID, not a
   priority. Gaps are fine (if ADR-004 is deleted, do not
   renumber).

4. LINK FROM CODE
   When code exists because of an ADR, reference it:
   // See ADR-001 for why we use Kafka here
   This connects the "what" (code) to the "why" (ADR).

5. REVIEW DURING ONBOARDING
   New engineers read all active ADRs in their first week.
   This is the fastest way to understand why the system
   looks the way it does.

6. REVIEW ANNUALLY
   Once a year, review all active ADRs. Are the assumptions
   still valid? Have the reversal conditions been met?
   Update or supersede as needed.
```

### File Structure

```
ticketpulse/
  docs/
    adr/
      ADR-001-kafka-for-event-streaming.md
      ADR-002-limit-microservice-count.md
      ADR-003-postgresql-primary-database.md
      ADR-004-cqrs-for-events-not-users.md
      ADR-005-typescript-for-api-services.md
      INDEX.md  ← table with title, status, date for each ADR
```

---

## Decision Log Exercises

The ADRs you wrote capture major decisions. But major decisions happen rarely. Most decisions are smaller and more frequent — and those accumulate into architectural drift when left undocumented.

### Exercise 1: The Weekly Decision Log

For the next two weeks, keep a decision log entry for every technical decision you make that meets these criteria:

- Multiple options were available
- The decision will be visible in the codebase in 6 months
- A new engineer would reasonably ask "why?"

The entry does not need to be a full ADR. A paragraph is enough:

```
DATE: 2026-04-02
DECISION: Used cursor-based pagination for the event listing API instead of offset-based
RATIONALE: Offset pagination breaks when new events are inserted (users see duplicates
           or miss items). Cursor-based pagination is stable under concurrent writes.
TRADE-OFF: Cursor-based pagination cannot jump to arbitrary pages (no "page 5 of 20").
           The product team confirmed this is acceptable — infinite scroll is the UX.
ALTERNATIVES REJECTED: Offset pagination (breaks under writes), keyset pagination
                        (same as cursor, just different terminology)
WOULD REVISIT IF: Product team requests "jump to page N" functionality.
```

After two weeks, review your log. How many decisions did you make? Which of them would benefit from a full ADR?

### Exercise 2: The ADR Audit

For an existing system you work on (or TicketPulse as built through the course), conduct an ADR audit:

**Step 1: List the major architectural decisions in the system.**

Start with these categories:
- Language and runtime choice
- Primary database choice
- Message queue / event bus choice
- Authentication approach
- Deployment platform
- Service decomposition strategy
- Caching strategy
- API style (REST, GraphQL, gRPC)

**Step 2: For each decision, ask:**
- Is this documented in an ADR?
- If yes: is the ADR still accurate? Have the circumstances changed?
- If no: should it be?

**Step 3: Prioritize which decisions most need documentation.**

The highest-priority undocumented decisions are the ones where:
- People debate the decision regularly ("should we have used GraphQL?")
- New engineers ask about it frequently ("why do we use Kafka instead of SQS?")
- The decision is about to be revisited anyway

For each high-priority undocumented decision, write the ADR. The ADR will be retrospective, but it still adds value — it forces the team to agree on the rationale and the conditions under which they would reconsider.

### Exercise 3: The Superseding ADR

Write a superseding ADR — a decision that reverses a previous one. Use ADR-002 (Limit Microservice Decomposition to 3-5 Services) from the Build section as the decision being superseded.

**Scenario**: TicketPulse has grown. The team is now 20 engineers. The order service has become a monolith within a microservice — 80,000 lines of TypeScript handling orders, inventory, refunds, waitlists, and seat maps. Three teams own different parts of the order service and are constantly stepping on each other.

Write ADR-006 that supersedes ADR-002:

```markdown
# ADR-006: Expand Microservice Decomposition Beyond 3-5 Services

## Status
Accepted — supersedes ADR-002

## Context
ADR-002 was written when TicketPulse had 8 engineers. It capped services
at 3-5 to limit operational overhead.

Since then:
- Team has grown to 20 engineers across 3 teams
- [describe what changed about the order service]
- [describe the specific friction that is being experienced]
- [describe what the teams are asking for]

The reversal conditions in ADR-002 have been met:
- "Team grows beyond 15 engineers" ✓ (team is 20)
- "Deployment conflicts between features become frequent" ✓ ([describe incidents]

## Decision
[What is the new decomposition strategy?
Which service(s) will be split from the order service?
What are the new service boundaries?]

## Consequences
[What becomes easier?]
[What becomes harder?]
[New reversal conditions]
```

This exercise is valuable because it demonstrates that good ADRs anticipate their own reversal. ADR-002 explicitly stated "we would reconsider if the team grows to 15+ engineers." That foresight makes ADR-006 easy to write — the previous decision already told you when to revisit it.

---

## 🤔 Final Reflections

For each ADR you wrote, answer this question:

### Under What Circumstances Would You REVERSE This Decision?

```
ADR-001 (Kafka): Reverse if ___________________________________
  Hint: team shrinks, ops burden too high, SQS covers the use cases

ADR-002 (3-5 services): Reverse if _____________________________
  Hint: team grows, deployment conflicts increase, domain clarity improves

ADR-003 (PostgreSQL): Reverse if ________________________________
  Hint: write volume exceeds capacity, multi-region becomes critical

ADR-004 (CQRS for events): Reverse if __________________________
  Hint: Elasticsearch becomes too expensive/complex, pg_trgm suffices

ADR-005 (TypeScript): Reverse if ________________________________
  Hint: performance-critical service emerges, team composition changes
```

The best ADRs include their own expiration conditions. A decision that was right a year ago may be wrong today -- but only if you recorded why you made it.

---

---

## Cross-References

- **Chapter 9** (Engineering Leadership): ADRs are one of three core documentation practices covered in this chapter, alongside RFCs (for proposals) and design docs (for large features). The chapter covers how ADRs fit into the decision-making culture of high-performing teams.
- **L1-M19** (Architecture Patterns Overview): The architecture decision exercises in L1-M19 produce mini-ADRs. This module provides the full format and depth those exercises pointed toward.
- **L3-M89** (Career Engineering Plan): Writing ADRs builds the muscle for writing promotion evidence — both require articulating context, rationale, and consequences clearly and honestly.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **ADR** | Architecture Decision Record; a short document that captures a single architectural decision and its context. |
| **RFC** | Request for Comments; a design proposal shared with the team for feedback before a decision is finalized. |
| **Design doc** | A detailed document describing a proposed technical design, including alternatives considered and trade-offs. |
| **Decision record** | A log entry that captures the reasoning and outcome of a significant technical or process decision. |
| **Supersede** | The act of replacing a previous decision record with a new one when the context or choice changes. |
| **Pre-decision ADR** | An ADR written before the decision is finalized, used as a structured thinking tool rather than just documentation. |
| **Decision log** | A lightweight record of daily technical decisions that do not warrant full ADRs but should be traceable over time. |
| **ADR audit** | A periodic review of all active ADRs to verify their accuracy and identify decisions that need new ADRs. |
| **Reversal condition** | A stated circumstance under which the current decision should be revisited and potentially reversed. |

## Further Reading

- **Chapter 9**: Engineering Leadership -- ADRs, RFCs, DORA metrics, and technical decision-making
- **Michael Nygard's original ADR proposal**: "Documenting Architecture Decisions" (cognitect.com)
- **adr-tools**: CLI for managing ADR documents (github.com/npryce/adr-tools)
- **"Design Docs at Google"**: how Google documents design decisions at scale
- **Joel Parker Henderson's ADR collection**: github.com/joelparkerhenderson/architecture-decision-record

### 🤔 Reflection Prompt

After writing ADRs for TicketPulse, which decision was hardest to articulate? When the "consequences" section forced you to name trade-offs explicitly, did it change your confidence in the decision?

> **Going deeper:** **L3-M86a (AI-Native Spec-Driven Development)** extends ADRs into the AI era — CLAUDE.md as behavioral specification, the "spec stack" (CLAUDE.md + RFC + OpenAPI + Gherkin), and using specs as the interface between human intent and AI execution.
---

## What's Next

In **Package Principles & Architecture Fitness Functions** (L3-M77a), you'll build on what you learned here and take it further.

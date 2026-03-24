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

> 💡 **Insight**: "At Spotify, ADRs are stored alongside code in the repo. When an engineer asks 'why do we use gRPC instead of REST for service X?', the answer is in docs/adr/0012-grpc-for-internal-services.md. This eliminates repeated debates and 'I was not here when that was decided' syndrome."

---

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

## 🛠️ Build: 5 ADRs for TicketPulse

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

## Further Reading

- **Chapter 9**: Engineering Leadership -- ADRs, RFCs, DORA metrics, and technical decision-making
- **Michael Nygard's original ADR proposal**: "Documenting Architecture Decisions" (cognitect.com)
- **adr-tools**: CLI for managing ADR documents (github.com/npryce/adr-tools)
- **"Design Docs at Google"**: how Google documents design decisions at scale
- **Joel Parker Henderson's ADR collection**: github.com/joelparkerhenderson/architecture-decision-record

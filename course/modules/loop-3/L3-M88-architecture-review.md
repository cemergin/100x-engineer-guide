# L3-M88: The TicketPulse Architecture Review

> **Loop 3 (Mastery)** | Section 3E: The Final Sprint | ⏱️ 90 min | 🟢 Core | Prerequisites: All prior modules
>
> **Source:** Chapters 28, 3, 7 of the 100x Engineer Guide

## What You'll Learn

- Presenting a complete system architecture using the C4 model (4 levels of zoom)
- Articulating architectural decisions: what you chose, what you rejected, and what would make you reconsider
- Conducting a risk assessment: identifying the top operational risks and their mitigations
- Technical debt inventory: categorizing shortcuts and prioritizing what to fix
- Scaling analysis: understanding what breaks at 10x, 100x, and 1000x current traffic

## Why This Matters

You have built TicketPulse across 88+ modules. It started as a monolith in Module 1 and is now a globally distributed, event-driven, AI-powered platform with real-time features, payment processing, search, recommendations, and production-grade infrastructure.

But can you explain it? Can you stand in front of a whiteboard (or a review board) and walk someone through the entire system in 30 minutes? Can you answer "why did you choose Kafka over RabbitMQ?" or "what happens if your primary database goes down?" or "what is your biggest operational risk right now?"

This is the architecture review. It is the skill that separates engineers who build systems from engineers who build systems AND can communicate about them. Every Staff+ engineer interview includes a version of this. Every architectural decision at a company is defended in this format. Every post-mortem is, at its core, an architecture review of what went wrong.

This module is not building anything new. It is the culmination: synthesizing everything you have built into a coherent story that you can present, defend, and critique.

---

## 1. The C4 Model: Four Levels of Zoom

### Why C4?

C4 (Context, Container, Component, Code) gives you four levels of zoom for explaining a system. Start zoomed out, drill in only where needed. This prevents the common failure mode of architecture diagrams: showing everything at once and explaining nothing.

### Level 1: Context Diagram

The system and its relationships with users and external systems. No internal details.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CONTEXT DIAGRAM                             │
│                                                                     │
│    ┌──────────┐         ┌───────────────────┐       ┌────────────┐ │
│    │ Attendee │────────▶│                   │──────▶│  Stripe    │ │
│    │ (Web/App)│◀────────│   TicketPulse     │◀──────│  (Payment) │ │
│    └──────────┘         │                   │       └────────────┘ │
│                         │   Event ticketing │                       │
│    ┌──────────┐         │   platform with   │       ┌────────────┐ │
│    │ Organizer│────────▶│   real-time seats, │──────▶│ SendGrid   │ │
│    │ (Web)    │◀────────│   AI recs, search  │      │ (Email)    │ │
│    └──────────┘         │                   │       └────────────┘ │
│                         └───────────────────┘                       │
│    ┌──────────┐                │      │             ┌────────────┐ │
│    │  Admin   │────────────────┘      └────────────▶│ Cloudflare │ │
│    │ (Web)    │                                     │ (CDN)      │ │
│    └──────────┘                                     └────────────┘ │
│                                                                     │
│    ┌──────────┐                                     ┌────────────┐ │
│    │ Partner  │─────────── (Webhook API) ──────────▶│ FCM/APNs   │ │
│    │ Systems  │                                     │ (Push)     │ │
│    └──────────┘                                     └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**What to communicate at this level:**
- Who uses the system (attendees, organizers, admins, partner systems)
- What external services it depends on (payment, email, CDN, push notifications)
- The one-sentence description: "A globally distributed event ticketing platform"

### Level 2: Container Diagram

The high-level technology choices: every service, database, message broker, and cache.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CONTAINER DIAGRAM                              │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Web Frontend │  │  Mobile BFF  │  │  Admin Panel  │               │
│  │ (Next.js)    │  │  (Node.js)   │  │  (Next.js)    │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                        │
│         └────────┬────────┴──────────────────┘                       │
│                  ▼                                                    │
│         ┌───────────────┐                                            │
│         │  API Gateway  │                                            │
│         │  (Kong/Envoy) │                                            │
│         └───────┬───────┘                                            │
│                 │                                                     │
│    ┌────────────┼────────────┬────────────┬────────────┐            │
│    ▼            ▼            ▼            ▼            ▼             │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐          │
│ │ Order  │ │ Event  │ │ User   │ │Payment │ │ Search   │          │
│ │Service │ │Service │ │Service │ │Service │ │ Service  │          │
│ │(Node)  │ │(Node)  │ │(Node)  │ │(Node)  │ │(Node)    │          │
│ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘          │
│     │          │          │          │            │                  │
│     ▼          ▼          ▼          ▼            ▼                  │
│ ┌────────┐ ┌────────┐ ┌────────┐              ┌──────────┐         │
│ │Postgres│ │Postgres│ │Postgres│              │Elastic-  │         │
│ │(Orders)│ │(Events)│ │(Users) │              │search    │         │
│ └────────┘ └────────┘ └────────┘              └──────────┘         │
│                                                                      │
│     ┌──────────────────────────────────────┐                        │
│     │          Kafka (Event Bus)           │                        │
│     └──────────────────────────────────────┘                        │
│                                                                      │
│  ┌─────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Redis   │  │ Notification │  │ Rec Engine │  │  Workflow    │  │
│  │ (Cache)  │  │   Service    │  │ (ML/AI)    │  │  Engine      │  │
│  └─────────┘  └──────────────┘  └────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**What to communicate at this level:**
- Each service and its technology choice
- Data stores and which services own which data
- Communication patterns (sync via API gateway, async via Kafka)
- Supporting infrastructure (cache, search, workflow engine)

### Level 3: Component Diagram

Zoom into one service. For the architecture review, pick the most complex service -- the Order Service:

```
┌──────────────────────────────────────────────────────────────────┐
│                   ORDER SERVICE — COMPONENTS                      │
│                                                                  │
│  ┌────────────────┐                                              │
│  │  REST API Layer │  POST /orders, GET /orders/:id, etc.       │
│  │  (Express +     │  Input validation, auth middleware,         │
│  │   middleware)    │  rate limiting                              │
│  └───────┬─────────┘                                             │
│          │                                                        │
│  ┌───────▼─────────┐     ┌──────────────────┐                   │
│  │  Domain Logic    │────▶│  Event Publisher  │                   │
│  │  (Order          │     │  (Kafka Producer) │                   │
│  │   Aggregate,     │     └──────────────────┘                   │
│  │   business rules)│                                             │
│  └───────┬─────────┘     ┌──────────────────┐                   │
│          │               │  Kafka Consumer   │                   │
│  ┌───────▼─────────┐     │  (PaymentReceived,│                   │
│  │  Repository      │     │   TicketReleased) │                   │
│  │  (Prisma ORM,    │     └──────────────────┘                   │
│  │   event store)   │                                             │
│  └───────┬─────────┘                                             │
│          │                                                        │
│  ┌───────▼─────────┐                                             │
│  │  PostgreSQL      │  orders, events (event sourcing),          │
│  │  (Order DB)      │  waitlist_entries, snapshots                │
│  └─────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘
```

### Level 4: Code Diagram

Only for the part you are actively explaining. A class/module diagram for the order aggregate:

```
OrderAggregate
├── state: OrderState
├── pendingEvents: OrderEvent[]
├── load(id): Promise<void>
├── apply(event): void
├── confirmOrder(): void
├── cancelOrder(reason, by): void
├── save(): Promise<void>
└── getState(): OrderState

OrderState
├── id, userId, eventId
├── seats: string[]
├── totalAmount, currency
├── status: 'pending' | 'confirmed' | 'cancelled' | 'refunded'
├── paymentId: string | null
└── version: number
```

You do not need Level 4 for the entire system. Only zoom in this far when explaining a specific design decision or complex component.

---

## 2. Architectural Decision Records

For each major decision, document what you chose, what you rejected, and what would make you reconsider.

### Stop and Write (20 minutes)

Complete an ADR for at least 5 of these decisions. Use this template:

```
DECISION: [What you chose]
CONTEXT: [Why the decision was needed]
REJECTED: [What alternatives you considered and why you rejected them]
RECONSIDER IF: [What change in circumstances would make you revisit this]
```

### Example ADRs

**ADR 1: Kafka for Event Bus**

```
DECISION: Apache Kafka as the event bus for inter-service communication.

CONTEXT: Services need to communicate asynchronously. Events (OrderCreated,
PaymentReceived, etc.) must be processed reliably and in order per entity.

REJECTED:
- RabbitMQ: Better for task queues, but Kafka's log-based model gives us
  replay capability, higher throughput, and consumer group semantics.
- AWS SQS + SNS: Simpler, but vendor lock-in and no replay.
- Redis Streams: Lighter weight, but less mature ecosystem for production
  event streaming.

RECONSIDER IF:
- Scale drops below 100 events/second sustained (Kafka is overkill for
  small scale; Redis Streams would be simpler).
- We move entirely to a serverless architecture (managed alternatives
  like AWS EventBridge would reduce operational burden).
```

**ADR 2: Event Sourcing for Orders**

```
DECISION: Event sourcing for the order domain. CRUD for other domains.

CONTEXT: Orders require complete audit trails, temporal queries (support:
"what happened to this order at 3 PM?"), and financial reconciliation.

REJECTED:
- Event sourcing for everything: Too much complexity for domains that
  don't need audit trails (user profiles, event listings).
- CRUD with audit log table: Simpler, but the audit log becomes a
  second-class citizen that diverges from the actual state.

RECONSIDER IF:
- The order domain's event count grows past 10M events/day (may need
  a dedicated event store like EventStoreDB instead of Postgres).
- Other domains develop strong audit requirements (expand event sourcing
  to those domains).
```

**ADR 3: PostgreSQL Per Service (Database-per-Service)**

```
DECISION: Each service owns its own PostgreSQL database. No shared databases.

CONTEXT: Microservice independence requires data isolation. Services must
be deployable and scalable independently.

REJECTED:
- Shared database with schema-per-service: Simpler operationally, but
  creates coupling (schema migrations affect all services, connection
  pool exhaustion).
- NoSQL (MongoDB/DynamoDB) for some services: Considered for the event
  catalog, but PostgreSQL's flexibility (JSONB, full-text search, pgvector)
  made specialized databases unnecessary for our scale.

RECONSIDER IF:
- Operational cost of managing multiple databases exceeds the cost of
  the coupling a shared database creates.
- A service's data model diverges fundamentally from relational
  (e.g., a graph of social connections).
```

**ADR 4: WebSocket for Real-Time Seat Updates**

```
DECISION: WebSocket for real-time seat map updates (not SSE or polling).

CONTEXT: Users watching the seat map need sub-100ms updates when tickets
are sold. 50K concurrent watchers per popular event.

REJECTED:
- SSE (Server-Sent Events): Simpler, but one-directional. We need the
  client to send "subscribe to event X" and potentially "ping/pong"
  health checks. SSE would require a separate channel for client→server.
- Polling: At 50K clients polling every 2 seconds, that's 25K req/s of
  mostly-unchanged data. Wasteful.

RECONSIDER IF:
- Mobile battery impact of persistent WebSocket connections is significant
  (SSE with HTTP/2 might be lighter).
- We move to a serverless architecture where persistent connections
  are expensive or unsupported.
```

**ADR 5: Kubernetes over Serverless**

```
DECISION: Kubernetes (self-managed on EKS) for deployment.

CONTEXT: TicketPulse has multiple long-running services, WebSocket
connections, Kafka consumers, and background workers. Need fine-grained
control over networking, scaling, and resource allocation.

REJECTED:
- Serverless (Lambda + API Gateway): Cold starts are unacceptable for
  the real-time purchase flow. WebSocket support is limited. Kafka
  consumer patterns don't map cleanly to function invocations.
- Managed PaaS (Railway, Fly.io, Render): Simpler, but less control
  over networking (NetworkPolicies), custom metrics-based autoscaling,
  and multi-region deployment.

RECONSIDER IF:
- Team size shrinks (K8s operational cost is high for small teams).
- Serverless WebSocket and streaming support matures significantly.
- We adopt a platform engineering team that abstracts K8s complexity.
```

### Your Turn

Write ADRs for:
- Caching strategy (Redis vs in-memory vs CDN)
- Authentication approach (JWT + refresh tokens vs session-based)
- Search technology (Elasticsearch vs Postgres full-text search)
- Monitoring stack (Prometheus + Grafana vs Datadog vs custom)

---

## 3. Presenting the Architecture

### The 30-Minute Review Format

When presenting to a review board (or practicing for a Staff+ interview), structure the presentation:

```
Minutes 0-5:    Context diagram. What is TicketPulse? Who uses it?
                What external systems does it depend on?

Minutes 5-15:   Container diagram. Walk through each service, database,
                and communication pattern. Explain WHY each choice was made
                (reference your ADRs).

Minutes 15-20:  Deep dive into one complex area. Pick the order service
                or the real-time system. Show the component diagram.
                Explain the hardest engineering problem and how you solved it.

Minutes 20-25:  Risks, debt, and scaling analysis. Show self-awareness.

Minutes 25-30:  Q&A. The review board will probe your decisions.
```

### Handling Questions

The most common questions in architecture reviews (prepare for these):

- **"Why not X instead of Y?"** — Reference your ADR. Show you considered the alternative.
- **"What happens when Z fails?"** — Walk through the failure mode. Show you thought about resilience.
- **"How would this handle 10x traffic?"** — Reference your scaling analysis. Be honest about limitations.
- **"What would you do differently?"** — Have a real answer. Self-awareness is a signal of maturity.
- **"What is your biggest operational risk?"** — Do not say "nothing." Name a real risk and your mitigation.

The worst answer in an architecture review is "I did not think about that." The second worst is pretending you have an answer when you do not. It is perfectly acceptable to say "That is a good question. I have not evaluated that trade-off. Here is how I would approach investigating it."

---

## 4. Risk Assessment

### Top 5 Operational Risks

Identify the things most likely to cause a production incident and their mitigations:

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | Kafka cluster failure (all async communication stops) | Low | Critical | Multi-AZ deployment, monitoring consumer lag, fallback to sync calls for critical paths |
| 2 | Primary database failover during peak traffic | Medium | High | Read replicas, connection pooling (PgBouncer), tested failover runbook |
| 3 | Payment provider outage (Stripe down) | Medium | High | Circuit breaker, queue purchases for retry, communicate delay to users |
| 4 | Thundering herd on popular event launch | High | Medium | Rate limiting, queue-based purchase flow, pre-warming caches, CDN for static content |
| 5 | Cascading failure from one slow service | Medium | High | Circuit breakers, timeouts on all calls, bulkhead isolation, load shedding |

### Stop and Think (5 minutes)

What is missing from this list? What risk have you not thought about? Consider:
- Security incidents (data breach, credential leak)
- Human errors (deploying the wrong version, running a migration against production)
- Dependency supply chain attacks (compromised npm package)
- Cost spikes (unexpected traffic, runaway queries, forgotten cloud resources)

---

## 4. Technical Debt Inventory

### Categorize and Prioritize

Every system has shortcuts. The ones you acknowledged are less dangerous than the ones you forgot about.

| Debt Item | Category | Severity | Effort to Fix | Priority |
|-----------|----------|----------|---------------|----------|
| No integration tests for the purchase flow end-to-end | Testing | High | Medium | P1 |
| Hardcoded timeout values scattered across services | Configuration | Medium | Low | P1 |
| Event schema not validated at consumption time | Reliability | High | Medium | P1 |
| No automated runbook for database failover | Operations | High | Medium | P2 |
| Inconsistent error response format across services | Developer Experience | Low | Medium | P3 |
| Some services lack structured logging | Observability | Medium | Low | P2 |
| No load testing baseline for the current architecture | Performance | Medium | High | P2 |
| Mobile API shares endpoints with web (no BFF yet) | Architecture | Medium | High | P3 |

### The Debt Payoff Strategy

Not all debt needs to be paid immediately. The framework:

1. **P1 (Fix now)**: Debt that causes or hides production incidents
2. **P2 (Fix this quarter)**: Debt that slows down development or operations
3. **P3 (Fix when touching)**: Debt that is annoying but not urgent -- fix it when you are working in that area anyway

---

## 5. Scaling Analysis

### What Breaks at 10x, 100x, 1000x?

| Scale | Current Traffic | What Breaks | Solution |
|-------|----------------|-------------|----------|
| **Current** | 100 req/s, 1K concurrent users | Nothing (hopefully) | -- |
| **10x** | 1K req/s, 10K concurrent | Database connection limits, Redis memory, single Kafka partition hotspots | Connection pooling, Redis cluster, partition by event ID |
| **100x** | 10K req/s, 100K concurrent | Single-region latency for global users, Elasticsearch indexing lag, WebSocket connection limits per node | Multi-region deployment, search index sharding, WebSocket horizontal scaling with Redis pub/sub |
| **1000x** | 100K req/s, 1M concurrent | Everything. Database sharding needed, Kafka cluster expansion, CDN origin under load, cost becomes a primary concern | Sharding strategy, cell-based architecture, aggressive caching, FinOps discipline |

### Deep Dive: What 100x Actually Looks Like

At 100x (10K req/s, 100K concurrent users), the specific bottlenecks:

**Database connections**: PostgreSQL default max connections is 100. With 5 services each running 10 pods, you need 500+ connections. PgBouncer becomes mandatory, not optional. Connection pooling mode matters: transaction-level pooling for most services, session-level for services using LISTEN/NOTIFY or prepared statements.

**Kafka partitions**: A single partition can handle ~10K messages/second, but consumer lag builds if your consumer processing is slow. At 100x, you need to repartition hot topics (orders, ticket-updates) from 12 to 36+ partitions. This requires a careful migration since Kafka does not rebalance existing data.

**WebSocket state**: 100K concurrent WebSocket connections require ~10 servers (at 10K connections each). Each server holds in-memory connection state. Redis Pub/Sub broadcasts events to all servers, but the fan-out from Redis to 10 servers to 100K clients adds latency. At this scale, consider a dedicated WebSocket gateway (like Centrifugo or a custom solution with NATS).

**Search indexing lag**: Elasticsearch indexes at a certain rate. At 100x write throughput, the indexing delay between a new event being created and it appearing in search results grows from milliseconds to seconds. Accept eventual consistency for search, or invest in near-real-time indexing infrastructure.

### The Honest Answer

At 10x, TicketPulse works with tuning. At 100x, it requires significant architectural changes (multi-region, sharding). At 1000x, you are rebuilding core components.

This is normal. Every architecture has a scale ceiling. The mark of a good architecture is not that it handles infinite scale -- it is that you know where the ceiling is and what you need to do when you hit it.

### The Cost Dimension

Scaling is not just a technical problem. At 100x:

```
Current monthly infrastructure cost:    $2,000
At 10x (linear scaling):               $20,000
At 100x (with optimization):           $80,000-120,000
At 100x (without optimization):        $200,000+
```

The difference between $80K and $200K is engineering effort: caching, connection pooling, query optimization, right-sizing instances, spot instances for non-critical workloads, and aggressive CDN use. At scale, FinOps becomes a core engineering discipline, not an afterthought.

---

## 6. Reflect: If You Started Over

### Stop and Think (10 minutes)

If you had to rebuild TicketPulse from scratch with everything you know now, what would you do differently?

Consider:
- Would you start with microservices or a modular monolith?
- Would you choose different technologies for any component?
- What would you build first?
- What would you skip entirely?
- What would you invest more time in from the beginning?

There is no wrong answer. The point is to demonstrate that you can evaluate your own decisions critically -- which is the most important skill in architecture.

---

## Checkpoint: What You Presented

You have:

- [x] Created C4 diagrams at all four levels of zoom
- [x] Documented architectural decisions with rationale, rejected alternatives, and reconsideration criteria
- [x] Assessed the top operational risks and their mitigations
- [x] Inventoried technical debt with severity and priority
- [x] Analyzed scaling limits at 10x, 100x, and 1000x
- [x] Reflected on what you would do differently

**Key insight**: The architecture review is not about having perfect answers. It is about demonstrating that you understand the trade-offs in every decision, you know where the risks are, and you can communicate all of this clearly. This is the core skill of a Staff+ engineer.

---

## 7. The Live Architecture Review: Practice Walkthrough (30 min)

The architecture review is a skill you develop by doing it, not by reading about it. Run through this structured practice session.

### Setup: Record Yourself

Turn on your camera and screen recording. You are going to do a 25-minute verbal walkthrough of TicketPulse's architecture, as if presenting to a staff engineer panel. Speaking out loud — not just thinking — exposes gaps you do not notice when you only read your own notes.

```bash
# Open your C4 diagrams. Have these tabs ready:
# 1. Your Level 1 context diagram
# 2. Your Level 2 container diagram
# 3. Your ADR document
# 4. Your risk/debt tables
```

### The 25-Minute Script (Use This as a Prompt)

**Minutes 0-3: The Context (Do Not Overthink It)**

Start with one sentence: "TicketPulse is a globally distributed event ticketing platform used by attendees, organizers, and admins to manage and purchase event tickets." 

Then draw or show the Level 1 diagram while narrating:
- Who are the actors? (attendees, organizers, admins, partner systems)
- What external dependencies does it have? (Stripe, SendGrid, Cloudflare, FCM/APNs)
- What is the scale? (mention your peak traffic assumptions and current infra cost range)

**Pause here and ask yourself**: "Could a non-engineer understand what this system does from what I just said?" If not, simplify.

**Minutes 3-12: The Container Diagram (The Hard Part)**

Walk through each component of the Level 2 diagram. For each service, answer two questions:
1. What does this service own? (its data, its domain)
2. Why this technology choice? (reference your ADRs)

Do not just list services — explain the architecture as a story:

"The API gateway is the single entry point for all clients. We chose Kong because we needed request-level plugins for auth and rate limiting without baking that into every service. Traffic fans out to five domain services: Order, Event, User, Payment, and Search. Each service owns its own PostgreSQL database — no shared databases — because this gives us independent deployments and no query contention between services. They communicate asynchronously via Kafka because..."

**Minutes 12-18: The Deep Dive (Pick Your Most Interesting Problem)**

Choose ONE of these and explain it at the component level:
- How a ticket purchase flows through the system (saga pattern, event sourcing, payment coordination)
- How the real-time seat map works (WebSocket scaling, Redis pub/sub fan-out)
- How multi-region routing works (DNS latency-based routing, regional data ownership)

When you reach a design decision in the deep dive, pause and say: "We could have done X, but we chose Y because..." Use your ADR language.

**Minutes 18-22: Risks and Debt (Show Self-Awareness)**

Walk through your top 3 risks from the table above. For each: name it, say why it concerns you, explain your mitigation. Do not be defensive — reviewers respect engineers who see their own system's weaknesses.

Walk through your top 2 debt items. Explain the priority and why you have not fixed them yet (time, priority, dependencies). If you have a plan to address them, say so.

**Minutes 22-25: Scaling Analysis**

Pick the 10x scenario and explain what would break. Be specific: "At 10x traffic, the first bottleneck would be PostgreSQL max_connections. Each service runs 10 pods, 5 services = 50 pods × 5 connections each = 250 connections. PostgreSQL default max is 100. We need PgBouncer in transaction pooling mode immediately."

Specificity signals you have actually thought about this, not just recited generic answers.

---

### Hard Questions Practice

After the 25-minute walkthrough, answer each of these out loud (3-4 minutes total). Time yourself — fast, confident answers beat slow hedged ones.

**Q: "What would you have done differently if you had started with a serverless architecture?"**

> Work through the answer before reading this. Consider: Lambda cold starts on the real-time purchase flow, WebSocket limitations with API Gateway, Kafka consumer patterns with Lambda, and cost at scale. This is not "serverless is worse" — it is about specific trade-offs for TicketPulse's access patterns.

**Q: "Your CTO says cut infrastructure costs by 30% in 90 days without degrading user experience. Where do you start?"**

> First-pass audit: spot instances for non-critical background workers, right-size pods that are allocated but under-utilized, add aggressive CDN caching for static event data, review ElasticSearch cluster size (search indexing lag is acceptable if it saves $), move dev/staging to half-size clusters on a schedule. Do NOT touch the purchase flow or real-time WebSocket servers — user experience for revenue paths is non-negotiable.

**Q: "A single Kafka partition for the `orders` topic is the bottleneck at 2K messages/second. How do you fix it without data loss?"**

> This is a surgical operation. You cannot reduce partitions, but you can add them. Add new partitions to the topic. Update the producer to use the new partition count. The existing consumers will rebalance. The risk: messages already in old partitions keep their ordering; new messages are distributed across all partitions. If your order processor assumes strict ordering per user, you need to repartition by `user_id` hash to ensure all of a user's orders stay in the same partition.

---

## 8. Post-Review Improvement Sprint (15 min)

After every architecture review (real or practice), run this retrospective:

### The Three-Column Debrief

```
CLEAR (I explained this well)    FOGGY (I stumbled here)    GAP (I had no answer)
────────────────────────────     ───────────────────────     ─────────────────────
Kafka choice and rationale        Spanner vs CockroachDB      Exactly how TrueTime
Event sourcing for orders         when to choose               works at the hardware
Multi-region DNS routing          What happens to in-flight    level
                                  messages during Kafka        
                                  partition rebalancing        Cost of a Kafka node
                                                              in AP-Northeast
```

**For each item in the GAP column**: spend 15 minutes researching it right now and update your ADR or risk doc. Gaps in your knowledge are just future embarrassments that you can close today.

**For each item in the FOGGY column**: write a one-paragraph plain-English explanation. If you cannot write it, you do not understand it well enough to defend it.

### The Improvement Loop

```
1. Identify a gap from the review
2. Research → write a one-paragraph explanation
3. Find the relevant module or Chapter to deepen it (Ch 19 for distributed, Ch 28 for architecture patterns)
4. Update your C4 diagram or ADR to reflect the clarification
5. Practice explaining that specific topic out loud again (just 2 minutes)
```

Architecture clarity is a compounding skill. Every review cycle — even a practice one — makes the next one sharper.

---

> **Want the deep theory?** See Ch 28 of the 100x Engineer Guide: "System Design for Staff Engineers" — covers C4 in detail, how to run and receive architecture reviews, and the communication patterns that distinguish Staff from Senior engineers.

---

**Next module**: L3-M89 -- Your Career Engineering Plan, where we translate everything you have learned into concrete career action.

## Key Terms

| Term | Definition |
|------|-----------|
| **C4 diagram** | A hierarchical diagram model (Context, Container, Component, Code) for visualizing software architecture at multiple levels. |
| **Tech debt** | The implied cost of future rework caused by choosing a quick or easy solution over a better long-term approach. |
| **Risk assessment** | The process of identifying potential threats to a system and evaluating their likelihood and impact. |
| **Scaling plan** | A documented strategy for how the system will handle increased load, including horizontal and vertical scaling options. |
| **Fitness function** | An automated test that continuously validates whether a specific architectural quality attribute is maintained. |
---

## What's Next

In **Your Career Engineering Plan** (L3-M89), you'll build on what you learned here and take it further.

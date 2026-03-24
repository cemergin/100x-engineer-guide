# L3-M88: The TicketPulse Architecture Review

> ⏱️ 90 min | 🟢 Core | Prerequisites: All prior modules
> Source: Chapter 28 (C4 Model, Diagramming), Chapter 3 (Architecture Patterns), Chapter 7 (Production Checklist)

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

**Next module**: L3-M89 -- Your Career Engineering Plan, where we translate everything you have learned into concrete career action.

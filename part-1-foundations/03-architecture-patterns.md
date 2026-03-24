<!--
  CHAPTER: 3
  TITLE: Software Architecture Patterns
  PART: I — Foundations
  PREREQS: Chapters 1, 2
  KEY_TOPICS: monolith, microservices, hexagonal/clean/vertical slice, DDD, event-driven, CQRS, REST/gRPC/GraphQL, API design, saga pattern
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 3: Software Architecture Patterns

> **Part I — Foundations** | Prerequisites: Chapters 1, 2 | Difficulty: Intermediate to Advanced

The structural blueprints for software systems — from monoliths to microservices, from REST to event-driven, and the domain modeling that ties them together.

### In This Chapter
- Architectural Styles
- Communication Patterns
- API Design Philosophies
- Domain-Driven Design (DDD)
- Event-Driven Patterns
- Monolith-to-Microservices

### Related Chapters
- [Ch 1: System Design Paradigms & Philosophies] — distributed systems theory
- [Ch 2: Data Engineering Paradigms] — data modeling/CQRS
- [Ch 7: Deployment Strategies] — deploying these architectures
- [Ch 13: Cloud Databases] — how it all connects in practice

---

## 1. ARCHITECTURAL STYLES

### Monolithic Architecture
Single deployable unit. All components share one process and one database.

**When to use:** Early-stage startups, small teams (<10), unknown domain, time-to-market critical.
**Trade-offs:** Simple to develop/test/deploy, but scaling is all-or-nothing, long build cycles as codebase grows, tech lock-in.

### Modular Monolith
Monolith organized into well-defined modules with explicit boundaries. Deployed as one unit, structured for potential decomposition.

**Key techniques:** Separate modules by package/namespace, each module owns its schema, inter-module communication through public interfaces only, enforce boundaries with architecture fitness functions (ArchUnit, dependency-cruiser).

### Microservices Architecture
Small, independently deployable services, each owning its data. Services communicate over the network.

**Requires at minimum:** Centralized logging, distributed tracing, health checks, CI/CD per service, service discovery, clear ownership model.
**Anti-pattern:** Distributed Monolith — services are tightly coupled, requiring coordinated deployments.

### Service-Oriented Architecture (SOA)
Coarser-grained than microservices. Enterprise Service Bus (ESB) for integration. Smart pipes, dumb endpoints (opposite of microservices).

### Serverless Architecture
Event-triggered, ephemeral compute. Zero server management, pay-per-execution.
**Trade-offs:** Cold start latency, vendor lock-in, execution time limits, harder observability.

### Event-Driven Architecture (EDA)
Flow determined by events. Components communicate by emitting/responding to events.
**Trade-offs:** Extreme loose coupling, but eventual consistency, harder to reason about flow, requires distributed tracing.

### Hexagonal Architecture (Ports and Adapters)
Domain logic at center, isolated from external concerns. Ports (interfaces) + Adapters (implementations).
- **Driving ports (inbound):** How outside world talks to app (REST handler → app)
- **Driven ports (outbound):** How app talks to outside world (app → repository interface → Postgres adapter)

### Clean Architecture
Robert C. Martin. Concentric rings: Entities → Use Cases → Interface Adapters → Frameworks & Drivers. Dependencies always point inward.

### Onion Architecture
Similar to clean. Domain model at center, domain services wrap it, application services wrap those, infrastructure outermost.

### Vertical Slice Architecture
Organize by feature, not by layer. Each slice contains everything for one request/use case.
**Trade-offs:** High cohesion within features, potential duplication across slices. Works well with CQRS.

---

## 2. COMMUNICATION PATTERNS

### Synchronous

**REST:** Universal, cacheable, simple. Over-fetching/under-fetching problems.
**gRPC:** Binary (protobuf), HTTP/2, streaming. 10x faster than JSON. Not browser-friendly.
**GraphQL:** Client specifies exact data needed. Single endpoint. N+1 problem without DataLoader.

### Asynchronous

**Message Queues (Point-to-Point):** One producer → queue → one consumer. Load leveling. (RabbitMQ, SQS)
**Pub/Sub:** One producer → topic → many consumers. Fan-out. (Kafka, Google Pub/Sub)
**Event Streaming:** Persistent, ordered, replayable log. Consumers track their own offset. (Kafka, Kinesis)

### Choreography vs Orchestration

**Choreography:** No central coordinator. Services react to events. Great for simple flows, becomes "event spaghetti" for complex ones.
**Orchestration:** Central orchestrator controls flow. Clear visibility, easier debugging. Can become a "god service."
**Practical guidance:** Hybrid. Simple reactions use choreography; complex multi-step processes use orchestration (Temporal, Step Functions).

---

## 3. API DESIGN PHILOSOPHIES

### Richardson Maturity Model
Level 0 (single endpoint/RPC) → Level 1 (resources) → Level 2 (HTTP verbs + status codes) → Level 3 (HATEOAS/hypermedia).

### API Versioning Strategies
| Strategy | Pros | Cons |
|---|---|---|
| URI (`/v1/orders`) | Simple, explicit, cacheable | Duplicates routes |
| Header (`Accept: ...;version=2`) | Clean URIs | Hidden, harder to test |
| No versioning (evolution) | No version management | Requires discipline |

### Backward Compatibility Rules
Never remove a field. Never change a field's type. Never rename a field. New required input fields are breaking.

### API Gateway Pattern
Single entry point. Handles auth, rate limiting, routing, caching, SSL termination, monitoring.

### BFF (Backend for Frontend)
Dedicated backend per frontend type. Each gets exactly the API it needs.

---

## 4. DOMAIN-DRIVEN DESIGN (DDD)

### Strategic DDD

**Bounded Contexts:** Explicit boundary for a domain model. Same concept can have different representations in different contexts. Defines boundaries for microservices, teams, and data ownership.

**Ubiquitous Language:** Shared language between developers and domain experts, used in code and conversation.

**Context Mapping Patterns:**
| Pattern | Description |
|---|---|
| Shared Kernel | Two contexts share a subset of the model |
| Customer-Supplier | Upstream provides what downstream needs |
| Anti-Corruption Layer | Downstream translates upstream's model |
| Open Host Service | Upstream provides a well-defined protocol |
| Conformist | Downstream conforms to upstream as-is |

### Tactical DDD

**Entities:** Defined by identity, not attributes. Persist over time.
**Value Objects:** Defined by attributes. Immutable. Two with same attributes are equal. (`Money`, `EmailAddress`)
**Aggregates:** Cluster of entities/value objects as a single unit. One aggregate root. One transaction = one aggregate.
**Domain Events:** Records of significant happenings. Past tense. (`OrderPlaced`, `PaymentReceived`)

**Practical guidance:** Always invest in strategic DDD. Apply tactical DDD selectively to the core domain.

---

## 5. EVENT-DRIVEN PATTERNS

**Event Sourcing:** Store events, derive state. Complete audit trail, temporal queries.
**CQRS:** Separate read/write models. Independent scaling.
**Event Notification:** Thin events (just ID + type). Consumers call back for details.
**Event-Carried State Transfer:** Events carry full state. Consumers are autonomous.
**Saga Pattern:** Local transactions with compensating actions. Choreography or orchestration.

---

## 6. MONOLITH-TO-MICROSERVICES

### Strangler Fig Pattern
Incrementally replace monolith parts by routing specific requests to new services. Low risk, incremental.

### Branch by Abstraction
Introduce abstraction, build new implementation behind it, switch over. Keeps trunk deployable.

### Decomposition Strategies
- By business capability (most common)
- By subdomain (DDD)
- By change frequency (pragmatic)
- By team (Conway's Law)

### Data Ownership (The Hardest Part)
Database-per-service is the target. Use CDC, database views, and data sync as transitional patterns. Each piece of data has exactly one authoritative owner.

---

## Decision Framework

| Scenario | Start With |
|---|---|
| New startup, small team | Monolith or modular monolith |
| Growing team, clear boundaries | Modular monolith |
| Large org, multiple teams | Microservices |
| Complex domain logic | DDD + hexagonal/clean architecture |
| High-throughput events | Event-driven + Kafka |
| Full audit trail needed | Event sourcing + CQRS |
| Multiple client types | BFF + API gateway |
| Migrating from monolith | Strangler fig + branch by abstraction |

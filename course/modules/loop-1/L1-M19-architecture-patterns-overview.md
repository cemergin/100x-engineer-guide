# L1-M19: Architecture Patterns Overview

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M17 (How Distributed Systems Fail), L1-M18 (Consistency Models)
>
> **Source:** Chapters 1, 3 of the 100x Engineer Guide

---

## The Goal

TicketPulse is a monolith. Everything — events, tickets, users, payments — lives in one codebase, one process, one database. That is fine for now. But what happens when three teams need to work on it simultaneously? When the ticket purchase flow needs to scale independently from the event browsing page? When a bug in the notification system takes down the payment system?

This module is a tour of architectural styles — not as abstract theory, but as concrete options for TicketPulse's future. You will evaluate each one against the problems you have actually experienced in previous modules.

**No new infrastructure in this module. This is a thinking module — but a deeply structured one.**

---

## 1. What We Have: The Monolith (10 minutes)

### 🔍 Look At: TicketPulse's Current Structure

```
ticketpulse/
├── src/
│   ├── server.ts              # Entry point
│   ├── app.ts                 # Express app setup
│   ├── routes/
│   │   ├── events.ts          # Event CRUD + listing
│   │   ├── tickets.ts         # Purchase flow
│   │   ├── users.ts           # User registration, profiles
│   │   └── health.ts          # Health check
│   ├── services/
│   │   ├── pricing.ts         # Ticket pricing logic
│   │   ├── discounts.ts       # Discount codes
│   │   ├── emailService.ts    # Email sending
│   │   └── resilientCache.ts  # Redis wrapper (from M17)
│   ├── db/
│   │   ├── pool.ts            # Postgres connection pool
│   │   ├── dbRouter.ts        # Primary/replica routing (from M18)
│   │   └── migrations/        # Schema migrations
│   └── middleware/
│       ├── auth.ts            # Authentication
│       └── errorHandler.ts    # Error handling
├── docker-compose.yml
├── package.json
└── jest.config.ts
```

This is a **monolith.** Every feature shares:
- One process (one `node` process handles everything)
- One database (one Postgres instance with all tables)
- One deployment (deploy everything together)
- One codebase (one `git push` updates all features)

### What Works About This

List the advantages you have experienced:

1. **Simple to understand.** You can trace a request from route to database in one codebase.
2. **Simple to deploy.** One build, one Docker image, one `docker compose up`.
3. **Simple to test.** Integration tests hit real routes and a real database. No service-to-service mocking.
4. **Refactoring is easy.** Rename a function and the compiler catches all callers.
5. **No network boundaries.** A function call is nanoseconds. An HTTP call is milliseconds.

### What Hurts (or Will Hurt)

1. **Scaling is all-or-nothing.** The event listing page gets 100x more traffic than the admin panel. But you cannot scale them independently — you scale the entire monolith.
2. **One bug can take down everything.** A memory leak in the email service crashes the whole process, including ticket purchases.
3. **Build times grow.** As the codebase grows, build and test times increase for everyone.
4. **Team coupling.** If three teams work on the same codebase, merge conflicts and coordination overhead increase.

### 🤔 Reflect

Think about TicketPulse specifically:

- Which part of the codebase changes most frequently?
- Which part gets the most traffic?
- Which part is most critical (generates revenue)?
- Are these the same part? (Hint: usually not.)

---

## 2. The Modular Monolith (10 minutes)

Before jumping to microservices, there is a middle ground: enforce module boundaries within the monolith. Same deployment, same process, but with explicit walls between domains.

### What Changes

```
ticketpulse/
├── src/
│   ├── modules/
│   │   ├── events/               # Event Management module
│   │   │   ├── events.routes.ts
│   │   │   ├── events.service.ts
│   │   │   ├── events.repository.ts
│   │   │   ├── events.types.ts   # Public interface
│   │   │   └── index.ts          # Only exports public API
│   │   │
│   │   ├── ticketing/            # Ticketing module
│   │   │   ├── tickets.routes.ts
│   │   │   ├── tickets.service.ts
│   │   │   ├── purchase.service.ts
│   │   │   ├── tickets.repository.ts
│   │   │   ├── tickets.types.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── payments/             # Payments module
│   │   │   ├── payments.routes.ts
│   │   │   ├── payments.service.ts
│   │   │   ├── payments.repository.ts
│   │   │   ├── payments.types.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── users/                # Users module
│   │   │   ├── users.routes.ts
│   │   │   ├── users.service.ts
│   │   │   ├── users.repository.ts
│   │   │   ├── users.types.ts
│   │   │   └── index.ts
│   │   │
│   │   └── notifications/        # Notifications module
│   │       ├── notifications.service.ts
│   │       ├── email.adapter.ts
│   │       ├── notifications.types.ts
│   │       └── index.ts
│   │
│   ├── shared/                   # Shared kernel (minimal!)
│   │   ├── database.ts
│   │   ├── cache.ts
│   │   └── types.ts
│   │
│   ├── server.ts
│   └── app.ts
```

### The Rules

1. **Modules communicate through their public interface (`index.ts`) only.** The ticketing module cannot import `events.repository.ts` directly. It calls `eventsModule.getEventById(id)`.

2. **Each module owns its database tables.** The events module owns the `events` table. The ticketing module owns the `tickets` table. Cross-module queries go through the module's public API, not direct SQL JOINs.

3. **No circular dependencies.** If ticketing depends on events, events cannot depend on ticketing. Use events (domain events, not the module) to decouple.

### 🛠️ Exercise: Enforce Boundaries with a Lint Rule

You can enforce module boundaries at build time. With ESLint and `eslint-plugin-import`:

```javascript
// .eslintrc.js (module boundary rules)
module.exports = {
  rules: {
    'import/no-restricted-paths': ['error', {
      zones: [
        // Ticketing module cannot reach into Events internals
        {
          target: './src/modules/ticketing/**',
          from: './src/modules/events/!(index).ts',
          message: 'Use the Events module public API (import from events/index.ts)',
        },
        // Events module cannot reach into Ticketing internals
        {
          target: './src/modules/events/**',
          from: './src/modules/ticketing/!(index).ts',
          message: 'Use the Ticketing module public API (import from ticketing/index.ts)',
        },
        // No module can import from another module's repository
        {
          target: './src/modules/*/!(*.repository).ts',
          from: './src/modules/*/*.repository.ts',
          message: 'Repositories are private. Use the module public API.',
        },
      ],
    }],
  },
};
```

Run the linter and it catches boundary violations at build time. This is the cheap version of microservice boundaries — same benefits for team independence, without the operational complexity of network calls.

### 💡 Insight: Shopify's Modular Monolith

Shopify is one of the largest Ruby on Rails monoliths in the world. They did not break it into microservices. Instead, they created **component boundaries** within the monolith using a tool called Packwerk. Each component:
- Has a declared public API
- Cannot access another component's internals
- Can gradually be extracted into a service if needed

The result: 300+ developers working on one codebase with clear ownership and minimal conflicts. The modular monolith gave them 80% of the organizational benefits of microservices at 20% of the operational cost.

---

## 3. Microservices: What It Would Look Like (10 minutes)

If TicketPulse needed to split into microservices, here is what it would look like:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API        │     │   Event      │     │   Ticketing   │
│   Gateway    │────→│   Service    │     │   Service     │
│              │     │              │     │               │
│ Rate limit   │     │ Events CRUD  │     │ Purchase flow │
│ Auth         │     │ Search       │     │ Inventory     │
│ Routing      │     │              │     │ Seat maps     │
└──────┬───────┘     └──────┬───────┘     └──────┬────────┘
       │                    │                     │
       │              ┌─────┴──────┐        ┌─────┴──────┐
       │              │ Events DB  │        │ Tickets DB │
       │              │ (Postgres) │        │ (Postgres) │
       │              └────────────┘        └────────────┘
       │
       │             ┌──────────────┐     ┌──────────────┐
       └────────────→│   Payment    │     │ Notification │
                     │   Service    │     │   Service    │
                     │              │     │              │
                     │ Charges      │     │ Email        │
                     │ Refunds      │     │ Push         │
                     │ Ledger       │     │ SMS          │
                     └──────┬───────┘     └──────┬───────┘
                            │                     │
                      ┌─────┴──────┐        ┌─────┴──────┐
                      │ Payments DB│        │  Message    │
                      │ (Postgres) │        │  Queue      │
                      └────────────┘        └────────────┘
```

### What You Gain

- **Independent scaling.** The event listing gets 10x the traffic? Scale only the Event Service.
- **Independent deployment.** Fix a bug in notifications without redeploying the payment service.
- **Technology freedom.** The search feature could use Elasticsearch. The notification service could be written in Go.
- **Fault isolation.** The notification service crashes? Ticket purchases still work (messages queue up).

### What You Pay

Every benefit comes with a cost:

| Benefit | Cost |
|---------|------|
| Independent deployment | Need CI/CD per service (5 pipelines instead of 1) |
| Independent scaling | Need container orchestration (Kubernetes) |
| Fault isolation | Need distributed tracing to debug cross-service issues |
| Technology freedom | Need polyglot expertise on the team |
| Service independence | Need API versioning, contract testing, backward compatibility |
| Database per service | No more JOINs across domains. Need data sync or API calls. |

### The Hidden Costs That Kill Teams

1. **Network calls replace function calls.** A function call takes nanoseconds and never fails. An HTTP call takes milliseconds and can fail due to timeouts, DNS issues, serialization bugs, and network partitions.

2. **Distributed transactions.** Buying a ticket now spans the Ticketing Service, Payment Service, and Notification Service. If payment succeeds but the ticket reservation fails, what happens? You need sagas, compensating transactions, or two-phase commit (all complex).

3. **Testing complexity.** Integration tests now need multiple services running. Contract tests are needed to ensure services agree on API formats. End-to-end tests are slow and flaky.

4. **Operational overhead.** Logging, monitoring, tracing, deployment, secret management — all multiplied by the number of services.

### 🤔 Reflect: The Minimum Team Size

What is the smallest team that justifies microservices?

A common rule of thumb: if you have fewer than 3 full-time backend engineers, microservices will slow you down. The operational overhead exceeds the organizational benefits. A well-structured monolith (or modular monolith) is faster to build, debug, and deploy for small teams.

Amazon's famous "two-pizza teams" work because they have thousands of engineers. Two-pizza team size (6-10 people) per service means you need 30-50 engineers before microservices make organizational sense.

---

## 4. Serverless: What Parts of TicketPulse Suit Lambda? (5 minutes)

Not everything needs to run 24/7. Some operations are event-triggered and bursty:

| TicketPulse Feature | Serverless Fit | Why |
|---------------------|---------------|-----|
| Event listing API | Poor | Always-on traffic, needs connection pooling, cold starts hurt UX |
| Ticket purchase | Poor | Latency-sensitive, needs database transactions, cold starts unacceptable |
| Email notifications | Excellent | Triggered by events, tolerates latency, bursty |
| Image resizing (event posters) | Excellent | Triggered on upload, CPU-intensive, short-lived |
| Analytics aggregation | Good | Runs on schedule, processes batch data, no user-facing latency |
| PDF ticket generation | Excellent | Triggered on purchase, CPU-intensive, short-lived |
| Scheduled event reminders | Excellent | Cron-triggered, no standing traffic |

The pattern: **serverless excels for event-triggered, bursty, latency-tolerant workloads.** It is poor for steady-state, latency-sensitive, connection-heavy workloads.

---

## 5. The Architecture Spectrum (5 minutes)

Architecture is not a binary choice. It is a spectrum:

```
Monolith ──→ Modular Monolith ──→ Microservices
   │              │                     │
   │              │                     │
 Simple         Medium               Complex
 Fast to build  Clear boundaries     Independent scaling
 Hard to scale  Easy to reason about Hard to debug
 Team coupling  Enforceable ownership Network complexity
```

### The Journey, Not the Destination

Most successful companies follow this path:

1. **Start as a monolith.** Move fast, validate the business, discover the domain.
2. **Evolve into a modular monolith.** As the team grows, enforce module boundaries. Prevent spaghetti.
3. **Extract services only where needed.** When a specific module needs independent scaling or a different team owns it, extract it into a service.

The mistake companies make: jumping to microservices at step 1. They spend months building infrastructure (service mesh, container orchestration, distributed tracing) before they have validated the business. Many startups have died building microservices for a product nobody wanted.

### 💡 Insight: Segment's "Goodbye Microservices"

Segment (now part of Twilio) famously went from monolith to microservices and back again. They had 140+ microservices, each with its own deployment pipeline, database, and monitoring. The operational overhead was crushing their small team. They consolidated back into a modular architecture and their development velocity tripled.

The lesson: microservices are an organizational solution to an organizational problem (too many teams to coordinate). If you do not have that problem, microservices create problems you did not have.

---

## 6. Conway's Law (5 minutes)

> "Any organization that designs a system will produce a design whose structure is a copy of the organization's communication structure." — Melvin Conway, 1967

This means: your architecture will mirror your team structure, whether you plan for it or not.

### 🤔 Exercise: TicketPulse With Three Teams

Imagine TicketPulse grows and you have three teams:

- **Team A: Discovery** — event search, listings, recommendations
- **Team B: Commerce** — ticket purchase, payments, refunds
- **Team C: Engagement** — notifications, user profiles, reviews

How would you split the architecture?

```
Team A (Discovery)          Team B (Commerce)          Team C (Engagement)
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ Event Service    │       │ Ticketing Service│       │ User Service     │
│ Search Service   │       │ Payment Service  │       │ Notification Svc │
│ Recommendation   │       │ Order Service    │       │ Review Service   │
│                  │       │                  │       │                  │
│ Events DB        │       │ Orders DB        │       │ Users DB         │
│ Search Index     │       │ Payments DB      │       │ Notifications DB │
└──────────────────┘       └──────────────────┘       └──────────────────┘
```

Each team owns their services end-to-end: code, database, deployment, and on-call. They communicate through well-defined APIs and events. This is the "inverse Conway maneuver" — deliberately structuring teams to produce the architecture you want.

**If you have one team, you get a monolith — and that is the right architecture for one team.** Do not fight Conway's Law. Use it.

---

## 7. Design Exercise: TicketPulse at 100x Scale (10 minutes)

### 📐 Exercise

TicketPulse currently handles 100 requests per second. Imagine it needs to handle 10,000 requests per second (100x growth). The event is a Taylor Swift concert and tickets go on sale in 5 minutes.

Design the architecture. Consider:

1. **What is the hottest path?** (Hint: the ticket purchase endpoint during an on-sale event)
2. **What can be cached aggressively?** (Event details, venue info, artist profiles)
3. **What needs strong consistency?** (Inventory — cannot oversell)
4. **What can be async?** (Email confirmations, analytics, receipt generation)
5. **Where are the bottlenecks?** (Database write throughput for ticket purchases)

### A Possible Design

```
                    CDN (static assets, cached event pages)
                              │
                         Load Balancer
                              │
                    ┌─────────┼─────────┐
                    │         │         │
              ┌─────┴──┐ ┌───┴────┐ ┌──┴──────┐
              │ App    │ │ App    │ │ App     │
              │ Server │ │ Server │ │ Server  │   ← Horizontally scaled
              │ #1     │ │ #2     │ │ #3      │
              └────┬───┘ └───┬────┘ └────┬────┘
                   │         │           │
              ┌────┴─────────┴───────────┴────┐
              │           Redis Cluster        │  ← Cached event data
              │    (event listings, sessions)   │
              └────────────────┬───────────────┘
                               │ (cache miss only)
              ┌────────────────┴───────────────┐
              │        Postgres Primary         │  ← Writes (purchases)
              │   (ticket inventory, orders)     │
              └────────┬──────────┬────────────┘
                       │          │
              ┌────────┴──┐  ┌───┴──────────┐
              │ Replica 1 │  │ Replica 2    │    ← Reads (event listings)
              └───────────┘  └──────────────┘
                               │
              ┌────────────────┴───────────────┐
              │        Message Queue            │  ← Async processing
              │     (RabbitMQ / Redis Streams)  │
              └────┬──────────┬────────────────┘
                   │          │
              ┌────┴───┐  ┌──┴──────────┐
              │ Email  │  │ Analytics   │        ← Background workers
              │ Worker │  │ Worker      │
              └────────┘  └─────────────┘
```

Key decisions:
- **CDN for static content:** Event pages that do not change (descriptions, images) served from edge
- **Redis Cluster for hot data:** Event listings, availability counts (30-second TTL)
- **Read replicas for browse traffic:** 90% of reads go to replicas
- **Primary for purchases only:** Strong consistency where it matters
- **Message queue for async work:** Email, analytics, receipt generation do not block the purchase response

This is not microservices. It is a well-scaled monolith (or modular monolith) with read replicas, caching, and async processing. For 10,000 RPS, this is likely sufficient. You do not need microservices until organizational complexity demands it.

---

## 8. Checkpoint

After this module, you should understand:

- [ ] TicketPulse's current monolithic structure and its strengths
- [ ] How a modular monolith enforces boundaries without splitting services
- [ ] The costs and benefits of microservices (and when NOT to use them)
- [ ] Which parts of TicketPulse suit serverless
- [ ] The spectrum from monolith to microservices as a journey
- [ ] Conway's Law: architecture mirrors team structure
- [ ] A 100x scaling design for TicketPulse

**Key takeaway: do not choose microservices because they sound impressive. Choose the simplest architecture that solves your actual problems.**

---

## Glossary

| Term | Definition |
|------|-----------|
| **Monolith** | A single deployable unit containing all application features. One process, one database, one deployment. |
| **Modular monolith** | A monolith organized into modules with enforced boundaries. Deployed as one unit but structured for potential decomposition. |
| **Microservices** | Small, independently deployable services, each owning its data and communicating over the network. |
| **Serverless** | Event-triggered, ephemeral compute (e.g., AWS Lambda). No server management, pay-per-execution. |
| **API Gateway** | A single entry point that handles authentication, rate limiting, and routing to backend services. |
| **Conway's Law** | Organizations design systems that mirror their communication structure. Architecture follows team structure. |
| **Inverse Conway Maneuver** | Deliberately structuring teams to produce the desired architecture. |
| **Distributed monolith** | The worst outcome: microservices that are tightly coupled and require coordinated deployment. All the complexity, none of the benefits. |
| **Strangler Fig Pattern** | Incrementally replacing monolith parts by routing specific requests to new services. |

---

## Further Reading

- [Shopify's Modular Monolith with Packwerk](https://shopify.engineering/shopify-monolith) — How Shopify makes a massive monolith work
- [Segment: Goodbye Microservices](https://segment.com/blog/goodbye-microservices/) — Why Segment moved back from microservices
- [MonolithFirst by Martin Fowler](https://martinfowler.com/bliki/MonolithFirst.html) — Start monolith, split later
- Chapter 3 of the 100x Engineer Guide: Section 1 (Architectural Styles)
- Sam Newman, *Building Microservices*, Chapter 1 (What Are Microservices?)

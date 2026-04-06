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

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Exercise: Enforce Boundaries with a Lint Rule

<details>
<summary>💡 Hint 1: Use eslint-plugin-import restriction zones</summary>
The ESLint rule `import/no-restricted-paths` lets you define "zones" — pairs of (target, from) globs. If code in the target tries to import from the restricted `from` path, the linter fails. Each module's internals become off-limits to other modules.
</details>

<details>
<summary>💡 Hint 2: Only allow imports from index.ts</summary>
Each module exposes a public API via `index.ts`. The lint rule should block imports like `from '../events/events.repository'` but allow `from '../events'` (which resolves to `index.ts`). Use a glob like `!(index).ts` to match everything except the barrel file.
</details>

<details>
<summary>💡 Hint 3: Block cross-module repository access</summary>
Repositories contain direct SQL. No module should import another module's repository — that would bypass the public API and create hidden coupling. Add a zone that blocks any `*.repository.ts` import from outside its own module.
</details>


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

> **Pro tip:** Shopify's Modular Monolith

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

> **Pro tip:** Segment's "Goodbye Microservices"

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

<details>
<summary>💡 Hint 1: Identify the hottest path</summary>
During a Taylor Swift on-sale, the ticket purchase endpoint gets 100x the traffic of everything else. The event listing page is read-heavy and can be cached aggressively (CDN + Redis, 30-second TTL). The purchase endpoint needs strong consistency — that is your bottleneck to design around.
</details>

<details>
<summary>💡 Hint 2: Separate read and write scaling</summary>
Add Postgres read replicas for browse traffic (90% of reads). Keep the primary for purchases only. Put a Redis cluster in front for event listings. This means most requests never touch the primary database at all.
</details>

<details>
<summary>💡 Hint 3: Move non-critical work off the hot path</summary>
Email confirmations, analytics, receipt generation, and PDF tickets should go through a message queue (RabbitMQ or Redis Streams). The purchase response only needs to confirm the reservation and payment — everything else is async. This is the pattern you built in M21-M22.
</details>


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

## 8. Architecture Decision Exercises

These exercises develop the pattern-matching instincts that distinguish senior engineers from junior ones. The goal is not to find the "right" answer — it is to practice the reasoning process.

### Exercise 1: The Architectural Smell Test

Read each scenario and identify what is wrong with the architecture choice. Then describe what you would do instead.

**Scenario A**: A 4-engineer startup building a food delivery app has 12 microservices. Each has its own database, CI/CD pipeline, and Kubernetes deployment. They have spent 6 months on infrastructure and have not shipped the main product yet.

```
What is wrong:
_______________________________________________

What I would do instead:
_______________________________________________
```

**Guidance**: This is microservices premature optimization. At 4 engineers, the operational overhead (12 CI/CD pipelines, 12 deployment processes, 12 database schemas to maintain) overwhelms the organizational benefit. A monolith or modular monolith would let them ship in 2 months instead of 6. The microservices architecture is solving a team coordination problem they do not yet have.

---

**Scenario B**: A 200-engineer company's e-commerce platform is a single monolith. Three teams — catalog, checkout, and fulfillment — all work in the same codebase. PRs are blocked for 2 days because of merge conflicts. Deployments happen at 2 AM because any broken change takes everything down.

```
What is wrong:
_______________________________________________

What I would do instead:
_______________________________________________
```

**Guidance**: This is a case where the team size has exceeded what a monolith can support efficiently. Conway's Law is working against them — 200 engineers on one codebase means 200 engineers can break each other's work. The answer is not necessarily full microservices, but the modular monolith boundaries should map to team boundaries, and they should extract the highest-friction module (whichever team causes the most merge conflicts) into its own service first.

---

**Scenario C**: A product team decided to make "everything serverless." Their API is Lambda functions behind API Gateway. They have 47 Lambda functions, each a tiny handler for a single endpoint. Local development requires mocking 12 AWS services. Response times are 800ms for the first request of the day (cold start).

```
What is wrong:
_______________________________________________

What I would do instead:
_______________________________________________
```

**Guidance**: This is over-decomposition of a different kind — serverless granularity applied to everything. Lambda works well for event-triggered, bursty workloads. It is poor for always-on API traffic with latency requirements. The cold start problem (800ms) is fatal for user-facing APIs. A containerized service (ECS/Fargate or Cloud Run) would be always warm, simpler to develop locally, and nearly as operationally simple. Keep Lambda for truly async, bursty work (email sending, PDF generation, scheduled jobs) and use a proper API runtime for request/response endpoints.

### Exercise 2: Pattern Matching Drills

For each system description, identify the architectural pattern that best fits and explain why. Choose from: monolith, modular monolith, microservices, serverless, event-driven, CQRS, or a combination.

**System 1**: A company processes 50,000 insurance claims per day. Each claim goes through 15 sequential processing steps (intake → validation → underwriting → approval → payment). Steps can fail and need to be retried. The business needs a complete audit trail of every step for every claim for regulatory compliance.

```
Pattern: _______________________________________________
Why: ___________________________________________________
What this buys you: _____________________________________
```

*Answer hint: This is a textbook case for durable execution (saga pattern) + event sourcing. The step-by-step nature maps to a saga. The audit trail requirement maps to event sourcing. The retry requirement maps to durable execution (each step is persisted so retries pick up where they left off).*

---

**System 2**: A SaaS dashboard shows business analytics for 10,000 customers. Each customer sees their own data. The dashboard has 20 different chart types. Data is updated nightly by batch jobs. Reads are 100x more frequent than writes.

```
Pattern: _______________________________________________
Why: ___________________________________________________
What this buys you: _____________________________________
```

*Answer hint: CQRS. The read model (dashboards) is fundamentally different from the write model (nightly batch ingestion). You want to optimize the read side independently (pre-aggregated views, materialized query results) without coupling it to how data is written. This is not microservices — it is a read/write separation within a service.*

---

**System 3**: A gaming company runs online multiplayer matches. Each match has 10-100 players, lasts 10-30 minutes, and has no persistence requirements (the match data can be discarded after it ends). They need to spin up 50,000 matches simultaneously during a peak event.

```
Pattern: _______________________________________________
Why: ___________________________________________________
What this buys you: _____________________________________
```

*Answer hint: Serverless (Lambda/Cloud Run) per match instance, or stateful server pods with rapid scale-out. The bursty, short-lived, no-persistence nature maps perfectly to serverless. Each match is an independent function invocation that terminates when the match ends. The 50,000 simultaneous matches scale trivially with serverless — you never need to provision capacity for peak.*

### Exercise 3: Architecture Decision Record for TicketPulse

Write a mini-ADR (Architecture Decision Record) for a decision TicketPulse needs to make. Choose one of these and write the ADR:

**Option A**: Should TicketPulse's notification system be part of the order service or a separate notification service?

**Option B**: Should TicketPulse use a message queue (Kafka) for service communication, or direct HTTP calls between services?

**Option C**: Should TicketPulse's event search use PostgreSQL full-text search or Elasticsearch?

Use this format:

```markdown
# Architecture Decision: [Your chosen option]

## Context
What problem does this decision solve?
What are the current constraints (team size, timeline, scale)?

## Options Considered
Option 1: [name]
  Pros: ...
  Cons: ...

Option 2: [name]
  Pros: ...
  Cons: ...

## Decision
We will [chosen option] because [reason].

## Consequences
Easier: ...
Harder: ...
We would reconsider if: ...
```

Spend 15 minutes writing this ADR. Then compare your reasoning to the actual decisions documented in L3-M77 (Architecture Decision Records).

### Exercise 4: Conway's Law Applied to Your Team

Think about your current or most recent team. Answer these questions:

1. How many engineers are on the team?
2. How many independent code repositories (services, packages) are there?
3. Does the service boundary map to team boundaries? Or does one team own multiple services?
4. Where do the most integration bugs come from — within a team's service, or at the boundaries between services owned by different teams?

Now apply Conway's Law in reverse (the "Inverse Conway Maneuver"):

If you could redesign the team structure to produce better architecture, what would you change?

```
Current team structure:
_______________________________________________

Current architecture:
_______________________________________________

Mismatch (if any):
_______________________________________________

Proposed change:
_______________________________________________
```

This exercise is more valuable than any textbook example because it is about your actual system. The patterns you recognize in your own team are the ones that will stick.

---

## 9. Checkpoint

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

---

## Cross-References

- **Chapter 3** (Architectural Styles): The full taxonomy of architectural patterns with case studies. The monolith-to-microservices spectrum described in this module is drawn directly from Chapter 3.
- **L3-M77** (Architecture Decision Records): The ADR you wrote in Exercise 3 follows the format covered in depth there. ADRs are the primary mechanism for documenting and revisiting architectural decisions.
- **L2-M31** (Domain-Driven Design): Bounded contexts in DDD map directly to the module boundaries in a modular monolith and the service boundaries in microservices. The two disciplines reinforce each other.

---

## Further Reading

- [Shopify's Modular Monolith with Packwerk](https://shopify.engineering/shopify-monolith) — How Shopify makes a massive monolith work
- [Segment: Goodbye Microservices](https://segment.com/blog/goodbye-microservices/) — Why Segment moved back from microservices
- [MonolithFirst by Martin Fowler](https://martinfowler.com/bliki/MonolithFirst.html) — Start monolith, split later
- Chapter 3 of the 100x Engineer Guide: Section 1 (Architectural Styles)
- Sam Newman, *Building Microservices*, Chapter 1 (What Are Microservices?)
---

## What's Next

In **Domain-Driven Design Basics** (L1-M20), you'll build on what you learned here and take it further.

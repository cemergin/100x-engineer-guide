<!--
  CHAPTER: 34
  TITLE: Spec-Driven Development
  PART: III — Tooling & Practice
  PREREQS: Ch 27 (Technical Writing), Ch 25 (API Design), Ch 9 (Engineering Leadership)
  KEY_TOPICS: Specification-first development, RFCs, design documents, contract-first API design, OpenAPI, AsyncAPI, executable specifications, BDD, AI-native specs, CLAUDE.md as spec, agent-compatible specifications
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 34: Spec-Driven Development

> **Part III — Tooling & Practice** | Prerequisites: Ch 27 (Technical Writing), Ch 25 (API Design), Ch 9 (Engineering Leadership) | Difficulty: Intermediate → Advanced

Here is the most important thing you will learn in this entire guide: **the spec is where you do the hard thinking — before the code makes it expensive to change your mind.**

Specifications are the most leveraged artifact an engineer can produce. A single well-written spec aligns an entire team, prevents weeks of rework, enables parallel development, and — in the AI era — serves as the primary interface between human intent and machine execution. Engineers who master this skill are the ones who multiply teams, not just themselves. This chapter covers every form of specification, from lightweight RFCs to executable BDD specs, and shows you how to build a spec-driven culture that compounds engineering velocity over time.

### In This Chapter
- The Spec-First Thesis
- The RFC and Design Document
- Architecture Decision Records (ADRs)
- Contract-First API Design
- Executable Specifications
- Specification Languages and Formats
- AI-Native Spec-Driven Development
- The Spec-Driven Development Workflow
- Spec Anti-Patterns
- Measuring Spec Quality
- Spec-Driven Development in Practice
- Building a Spec Culture

### Related Chapters
- Ch 27 (Technical Writing & Documentation) — writing principles, ADR introduction, RFC basics
- Ch 25 (API Design) — REST, GraphQL, gRPC design patterns
- Ch 9 (Engineering Leadership) — communication, alignment, decision-making
- Ch 3 (Architecture Patterns) — system design patterns referenced in specs
- Ch 14 (AI-Powered Engineering) — AI workflows that consume specs
- Ch 17 (Claude Code Mastery) — CLAUDE.md, agent-compatible workflows

---

## 1. THE SPEC-FIRST THESIS

### 1.1 Specs Are the Highest-Leverage Engineering Artifact

Let me tell you about two engineers, both brilliant, both working on the same class of problem.

The first engineer opens their editor immediately. They are coding within five minutes. By the end of the day, they have shipped 400 lines. By the end of the week, they have a feature that sort of works. In code review, a senior engineer asks: "Why did you design it this way? This is going to conflict with what the auth team is building." Two weeks of work goes into rework. This engineer wonders why engineering feels so chaotic.

The second engineer spends two hours writing a one-pager. The one-pager surfaces the conflict with the auth team on day one, in a comment, before a single line of implementation exists. The rework cost is zero. The second engineer ships the feature in the same calendar time as the first — but with no rework, no production bugs from misaligned expectations, and a reviewable record of the decision.

The most senior engineers write specs, not code first. A principal engineer at Google might write 20% of the code they wrote as a junior — but their impact is 10x larger. The difference is alignment. One hour of spec writing saves 10 hours of rework. One well-written RFC prevents three teams from building incompatible systems.

The math is simple. Suppose you spend 4 hours writing a design doc for a feature that takes 3 engineers 2 weeks to build. That design doc:

- Prevents at least one false start (saves ~3 engineer-days)
- Enables parallel work between frontend and backend (saves ~2 days of sequential blocking)
- Surfaces an edge case that would have been a production bug (saves ~1 day of incident response)
- Gives the reviewer context, cutting code review time in half (saves ~1 day cumulative)

Total: 4 hours invested, ~7 engineer-days saved. That is a 14x return.

> "Weeks of coding can save you hours of planning." — common engineering wisdom

### 1.2 The Specification Spectrum

Specs exist on a spectrum from informal to formal. Each level has its place:

| Level | Format | Time to Write | When to Use |
|---|---|---|---|
| Napkin sketch | Whiteboard photo, Slack message | 5 minutes | Quick alignment in a conversation |
| One-pager | 1-page summary in a doc | 30 minutes | Any work >1 day, needs 1 approval |
| RFC / Design doc | Structured proposal, 2-6 pages | 2-8 hours | Work >2 days, affects >1 team, hard to reverse |
| Formal specification | OpenAPI, AsyncAPI, Protobuf | 4-16 hours | API contracts, service boundaries |
| Executable specification | Gherkin/BDD, property tests | 8-40 hours | Business-critical flows, regulated domains |
| Generated code | Code from spec | Automated | Server stubs, client SDKs, types |

The key insight: you should spend proportionally more time on spec as the blast radius of the work increases. A one-line bug fix needs no spec. A new microservice needs an RFC and an API contract. A platform migration needs all of the above.

This is also a leadership insight (see Ch 9 for the broader picture). The engineers who move up are not always the fastest coders — they are the ones who can identify when a situation calls for more rigor and escalate the specification effort accordingly.

### 1.3 Why Junior Engineers Skip Specs

Junior engineers think coding IS the work. They open their editor immediately because typing feels productive. They confuse motion with progress.

This is completely understandable. Writing a spec feels like delay. You are not shipping anything. You cannot demo a doc. Tickets do not get closed. But here is the uncomfortable truth: the most expensive code you will ever write is code built on top of a misunderstood requirement.

Senior engineers know that alignment IS the work. They have been burned enough times by:

- Building the wrong thing because the requirements were ambiguous
- Reworking an API because the consumer team had different expectations
- Discovering a fundamental design flaw during code review, after 2 weeks of implementation
- Shipping a feature that works but conflicts with another team's parallel effort

The pattern is always the same: the cost of not writing a spec shows up later, at 3-10x the cost of writing one.

I watched a team at a fintech startup spend six weeks rebuilding their notification service from scratch because two engineers, working in parallel, had built incompatible queue-handling abstractions. When they finally sat down in the same room and realized the conflict, they both said the same thing: "I thought you were building it differently." A two-page RFC would have caught this in an hour. Instead, they lost six weeks of combined engineering time plus two incident cycles where the bad integration shipped briefly to production.

### 1.4 The AI Inflection Point

Before 2024, specs had a high write cost and moderate execute cost. You spent hours writing the spec, then weeks implementing it. The ratio made specs feel expensive for smaller features.

AI changes this equation dramatically. Specs now have the same write cost but near-zero execute cost. An engineer can write a detailed spec in 2 hours and have an AI agent produce a working implementation in 30 minutes. This means:

- The ROI of spec writing has increased 5-10x
- Specs are now worth writing for smaller features (anything >4 hours of work)
- The spec IS the primary artifact — code is the generated output
- Engineers who can write precise specs are more valuable than engineers who can write fast code

The implication is profound: **specification writing is becoming the core engineering skill**, displacing raw coding ability as the primary differentiator between effective and ineffective engineers.

If you have worked through Ch 14 and Ch 17, you already know that AI agents are only as good as what you tell them. Every vague prompt is a vague spec. Every over-constrained prompt is an over-specified design. The skill of writing clear, complete, testable specifications translates directly into the skill of directing AI agents well — and vice versa. Investing in your spec-writing craft now is one of the highest-yield things you can do for your career in the next five years.

---

## 2. THE RFC AND DESIGN DOCUMENT

### 2.1 What an RFC Is

An RFC (Request for Comments) is a written proposal that invites structured disagreement. The name comes from the IETF tradition — the entire internet was built on RFCs. In a software organization, an RFC is a document that:

1. Proposes a specific technical change
2. Explains why the change is needed
3. Describes the design in enough detail to evaluate
4. Lists alternatives that were considered and why they were rejected
5. Identifies risks and open questions
6. Has an explicit status lifecycle

The power of an RFC is not the document itself — it is the structured disagreement it enables. Without an RFC, disagreements happen in code review (too late), in Slack threads (too scattered), or in meetings (too ephemeral). An RFC gives people a single place to raise concerns before implementation begins.

Think of the RFC as an asynchronous design review that happens at the exact moment when design changes are still cheap. Changing a sentence in an RFC costs you 30 seconds. Changing the corresponding database schema after launch costs you a migration, a coordination window, a rollback plan, and possibly a production incident. This is not a hypothetical — it is the daily reality of teams that skip the spec step.

The RFC also encodes something that code never can: **why a particular path was chosen over alternatives that looked equally valid**. Ch 9 covers how technical leadership is largely about making good decisions with incomplete information. The RFC is the artifact that captures that decision-making context before it evaporates from working memory.

### 2.2 Industry RFC Templates

**Google's Design Doc Template:**

Google's internal design doc is one of the most widely imitated formats in the industry. The core sections:

1. **Title and metadata** — Author, reviewers, status, last updated
2. **Context** — What is the current state? What problem exists?
3. **Goals and non-goals** — What are we trying to achieve? What are we explicitly NOT trying to achieve?
4. **Design** — The proposed solution, with enough detail to implement
5. **Alternatives considered** — Other approaches and why they were rejected
6. **Cross-cutting concerns** — Security, privacy, accessibility, observability
7. **Timeline and milestones** — Rough schedule with decision points

The goals/non-goals section is the most valuable part. Explicitly stating non-goals prevents scope creep and aligns the team on boundaries. Every time you add a non-goal, you are pre-empting a scope argument that would otherwise happen in the middle of implementation.

**Stripe's RFC Process:**

Stripe uses numbered RFCs with an explicit status lifecycle:

- **Draft** — Author is still writing, not ready for review
- **Review** — Open for comments, usually a 1-week review window
- **Accepted** — Approved for implementation
- **Implemented** — Code is shipped
- **Deprecated** — Superseded by a newer RFC

Each RFC gets a sequential number (RFC-001, RFC-002, etc.) and lives in a shared repository. This creates an auditable history of every significant technical decision. A common anti-pattern at fast-moving startups is losing institutional memory when people leave. Numbered, searchable RFCs are one of the most effective insurance policies against that knowledge drain.

**Uber's Design Doc Template:**

Uber's template emphasizes four sections:

1. **Motivation** — Why are we doing this? What is the business or technical driver?
2. **Proposed change** — The technical design, with diagrams
3. **Drawbacks** — Honest assessment of what could go wrong
4. **Alternatives** — Other approaches and trade-off analysis

The drawbacks section is what separates good design docs from bad ones. If your drawbacks section is empty, you have not thought hard enough. Real engineering decisions always involve trade-offs. A drawbacks section that says "none" is a signal that the author is either overconfident or trying to sell the idea rather than evaluate it. Reviewers will be skeptical. Your own future self will be better served by having documented the trade-offs you accepted.

**Meta's Diffs and Design Reviews:**

Meta uses a "diff" (their term for a PR) culture where significant changes require a design review before the diff is approved. For larger projects, an internal design doc is circulated. The key Meta pattern: every design doc must answer "What is the simplest version of this we could ship?"

That question is deceptively powerful. It forces scope discipline. It forces you to identify the core value before adding the bells and whistles. Ship the simplest version, learn, then iterate. The RFC captures that first-principles simplicity before enthusiasm inflates the design.

### 2.3 The NABC Framework

For shorter proposals or when you need a quick structure, use NABC:

- **Need** — What problem are we solving? Who is affected?
- **Approach** — What is the proposed solution?
- **Benefits** — What does the organization gain?
- **Competition/Alternatives** — What other approaches exist? Why is this one better?

NABC works well for one-pagers and for the executive summary at the top of a longer RFC. If you are presenting to a non-technical stakeholder (a product manager, an executive), NABC gives you a structure they can follow without a CS degree. The technical detail lives underneath — but the NABC gives them the hook to understand and engage with the decision.

### 2.4 When to Write an RFC

Write an RFC when any of these are true:

- The work takes more than 2 days
- The work affects more than 1 team
- The change is hard to reverse (data model changes, API contracts, infrastructure)
- The approach is non-obvious (multiple valid solutions exist)
- The work introduces a new dependency or technology
- There is meaningful disagreement about the approach

Do NOT write an RFC for:

- Bug fixes with obvious solutions
- Routine feature work that follows established patterns
- Dependency upgrades (unless they involve breaking changes)
- One-line configuration changes

The judgment call on "is this RFC-worthy?" is itself an important engineering skill. Ch 27 covers some of this in the context of documentation decisions. The heuristic I find most useful: if you would have a hard time explaining in a code review why you made the fundamental design choice, it deserved an RFC.

### 2.5 Complete RFC Template

```markdown
# RFC-[NUMBER]: [Title]

**Author:** [Name]
**Status:** Draft | Review | Accepted | Implemented | Deprecated
**Created:** [Date]
**Last Updated:** [Date]
**Reviewers:** [Names]
**Decision Deadline:** [Date — usually 1 week from review start]

## TL;DR

[2-3 sentences. A senior engineer should understand the proposal after reading
only this section.]

## Context

[What is the current state? What problem exists? Include metrics if available.
This section answers "Why now?"]

## Goals

- [Specific, measurable outcome 1]
- [Specific, measurable outcome 2]

## Non-Goals

- [What we explicitly will NOT do in this RFC]
- [Features or improvements deferred to future work]

## Design

### Overview

[High-level description. Include a diagram if the system has more than
2 components interacting.]

### Detailed Design

[The meat of the RFC. Cover:
 - Data model changes
 - API changes (request/response examples)
 - Key algorithms or business logic
 - Error handling strategy
 - Migration plan (if changing existing systems)]

### API Changes

[If applicable, show before/after API examples]

## Alternatives Considered

### Alternative 1: [Name]

[Description, pros, cons, reason for rejection]

### Alternative 2: [Name]

[Description, pros, cons, reason for rejection]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| [Risk 1] | Medium | High | [Mitigation strategy] |
| [Risk 2] | Low | Critical | [Mitigation strategy] |

## Security and Privacy

[How does this change affect security? Are there new attack surfaces?
Does it handle PII? GDPR/CCPA implications?]

## Observability

[What metrics, logs, and alerts will you add? How will you know the
change is working correctly in production?]

## Rollout Plan

[How will you deploy this? Feature flag? Percentage rollout?
What is the rollback plan?]

## Open Questions

- [Question 1 — who should answer it?]
- [Question 2 — what information is needed to answer it?]

## Timeline

| Milestone | Target Date | Description |
|-----------|-------------|-------------|
| RFC approved | [Date] | Begin implementation |
| MVP complete | [Date] | Core functionality working |
| Rollout start | [Date] | Begin production deployment |
| Rollout complete | [Date] | 100% traffic |
```

### 2.6 Example: TicketPulse RFC

Here is the RFC that kicked off TicketPulse's migration to event-driven architecture. Notice how every section earns its place — there is no boilerplate filler, and the alternatives section is genuinely honest about the trade-offs.

```markdown
# RFC-001: Migrate from REST to Event-Driven Ticket Reservation

**Author:** Jordan Chen
**Status:** Review
**Created:** 2026-03-10
**Last Updated:** 2026-03-17
**Reviewers:** Alex Rivera (Backend Lead), Sam Park (Infrastructure),
              Maria Gonzalez (Frontend Lead)
**Decision Deadline:** 2026-03-24

## TL;DR

Replace TicketPulse's synchronous REST-based ticket reservation flow with
an event-driven architecture using Apache Kafka. This eliminates the
cascading timeout failures we experience during high-demand events and
enables horizontal scaling of the reservation pipeline.

## Context

TicketPulse processes ticket reservations through a synchronous REST chain:

    Client → API Gateway → ReservationService → PaymentService
                                              → InventoryService
                                              → NotificationService

During the Taylor Swift Eras Tour on-sale (2026-02-14), this chain
experienced cascading failures:

- **ReservationService** timed out waiting for PaymentService (p99 latency
  spiked from 200ms to 12s)
- **InventoryService** connection pool exhausted (max 100 connections,
  burst of 8,400 concurrent requests)
- **Result:** 34% of reservation attempts failed with HTTP 503, estimated
  $2.1M in lost revenue over a 23-minute window

The synchronous chain cannot handle burst traffic because every component
must respond within the timeout window. Adding retries makes the problem
worse (retry storms).

## Goals

- **G1:** Survive 10x traffic spikes without cascading failures (target:
  <0.1% error rate at 50,000 concurrent reservations)
- **G2:** Reduce reservation confirmation latency from p99=12s to p99<3s
- **G3:** Enable independent scaling of payment, inventory, and notification
  processing
- **G4:** Maintain exactly-once reservation semantics (no double-booking,
  no lost reservations)

## Non-Goals

- **NG1:** Changing the client-facing REST API (frontend changes should be
  minimal — we keep the same POST /reservations endpoint)
- **NG2:** Replacing the PostgreSQL database (we keep existing data model)
- **NG3:** Real-time seat selection UI (deferred to Q3 2026)
- **NG4:** Multi-region deployment (deferred to separate RFC)

## Design

### Overview

```
Client → API Gateway → ReservationService
                              │
                              ▼
                        ┌─────────────┐
                        │    Kafka     │
                        │  Cluster    │
                        └──┬──┬──┬───┘
                           │  │  │
              ┌────────────┘  │  └────────────┐
              ▼               ▼               ▼
       PaymentWorker   InventoryWorker  NotificationWorker
              │               │               │
              ▼               ▼               ▼
         Stripe API      PostgreSQL     Email/SMS Provider
```

The ReservationService becomes an event producer. It validates the request,
writes a `reservation.created` event to Kafka, and returns HTTP 202
(Accepted) with a reservation ID. The client polls
`GET /reservations/:id/status` or subscribes to a WebSocket for updates.

### Kafka Topics

| Topic | Partitions | Retention | Key |
|-------|-----------|-----------|-----|
| `reservations.created` | 12 | 7 days | `event_id` |
| `reservations.payment.completed` | 12 | 7 days | `reservation_id` |
| `reservations.payment.failed` | 12 | 7 days | `reservation_id` |
| `reservations.confirmed` | 12 | 7 days | `reservation_id` |
| `reservations.cancelled` | 12 | 7 days | `reservation_id` |
| `reservations.dlq` | 3 | 30 days | `reservation_id` |

Partitioning by `event_id` ensures all reservations for the same event
are processed in order, preventing overselling.

### Reservation State Machine

```
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         │ payment.initiated
                    ┌────▼─────┐
              ┌─────│ PAYING   │─────┐
              │     └──────────┘     │
    payment.completed          payment.failed
              │                      │
         ┌────▼─────┐         ┌─────▼──────┐
         │ CONFIRMED │         │  FAILED    │
         └────┬─────┘         └────────────┘
              │ user.cancelled
         ┌────▼─────┐
         │ CANCELLED │
         └──────────┘
```

### Exactly-Once Semantics

We achieve exactly-once processing through:

1. **Idempotency keys:** Every reservation has a UUID generated client-side.
   The ReservationService deduplicates on this key before publishing.
2. **Kafka transactions:** PaymentWorker uses Kafka's transactional
   producer to atomically consume from `reservations.created` and produce
   to `reservations.payment.completed`.
3. **Outbox pattern:** Database writes and event publishing happen in the
   same transaction using the transactional outbox pattern (see Ch 3).

### API Changes

The client-facing API changes minimally:

**Before (synchronous):**
```http
POST /api/v1/reservations
Content-Type: application/json

{
  "event_id": "evt_abc123",
  "seat_ids": ["A1", "A2"],
  "idempotency_key": "idk_xyz789"
}

HTTP/1.1 201 Created
{
  "reservation_id": "res_def456",
  "status": "confirmed",
  "total_amount": 15000,
  "currency": "USD"
}
```

**After (asynchronous):**
```http
POST /api/v1/reservations
Content-Type: application/json

{
  "event_id": "evt_abc123",
  "seat_ids": ["A1", "A2"],
  "idempotency_key": "idk_xyz789"
}

HTTP/1.1 202 Accepted
{
  "reservation_id": "res_def456",
  "status": "pending",
  "status_url": "/api/v1/reservations/res_def456/status"
}
```

**New polling endpoint:**
```http
GET /api/v1/reservations/res_def456/status

HTTP/1.1 200 OK
{
  "reservation_id": "res_def456",
  "status": "confirmed",
  "total_amount": 15000,
  "currency": "USD",
  "updated_at": "2026-03-10T14:32:01Z"
}
```

## Alternatives Considered

### Alternative 1: Add a Queue (SQS/RabbitMQ) Without Full Event-Driven

Use a simple message queue between ReservationService and downstream
services.

**Pros:** Simpler, fewer infrastructure changes.
**Cons:** Doesn't solve the ordering problem (risk of overselling).
Doesn't enable independent scaling of consumers. No event replay
capability for debugging.

**Rejected because:** The ordering and replay guarantees of Kafka are
essential for our correctness requirements (G4).

### Alternative 2: Synchronous with Circuit Breakers

Keep REST but add circuit breakers (Hystrix/Resilience4j) to prevent
cascading failures.

**Pros:** No infrastructure changes. Familiar patterns.
**Cons:** Circuit breakers degrade gracefully but still fail under
sustained load. Users get errors instead of timeouts — better UX but
still lost revenue. Doesn't address the fundamental coupling.

**Rejected because:** Circuit breakers are a band-aid. They prevent
cascading failure but don't solve the throughput bottleneck.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Kafka cluster failure | Low | Critical | 3-broker cluster, 2 AZs, automated failover |
| Message ordering violation | Medium | High | Partition by event_id, single consumer per partition |
| Increased client complexity (polling) | High | Medium | Provide WebSocket option, SDK with built-in polling |
| Operational complexity increase | High | Medium | Runbooks, training, Kafka monitoring dashboard |

## Security and Privacy

- Kafka topics contain PII (user email in notification events).
  Enable at-rest encryption and TLS for inter-broker communication.
- ACLs restrict topic access: only ReservationService can produce to
  `reservations.created`.
- Payment tokens are never stored in Kafka messages — only reference IDs.

## Observability

- **Metrics:** Consumer lag per topic, reservation state transition
  latency, error rate by state transition, DLQ depth
- **Logs:** Structured JSON logs with correlation ID (reservation_id)
  across all services
- **Alerts:** Consumer lag >1000 messages (warning), >5000 (critical);
  DLQ depth >0 (warning)
- **Dashboard:** Grafana dashboard showing end-to-end reservation pipeline

## Rollout Plan

1. **Week 1-2:** Deploy Kafka cluster, create topics, deploy consumers
   in shadow mode (consume but don't act)
2. **Week 3:** Enable dual-write: ReservationService writes to both
   REST chain and Kafka. Compare results.
3. **Week 4:** Switch 5% of traffic to async path via feature flag.
   Monitor error rates and latency.
4. **Week 5:** Ramp to 25%, 50%, 100% over 3 days if metrics are clean.
5. **Week 6:** Remove synchronous REST chain.

**Rollback:** Feature flag reverts to synchronous path instantly.

## Open Questions

- Q1: Should we use Kafka Connect for the outbox pattern or build a
  custom outbox poller? (Assigned: Sam Park — investigate by 03/20)
- Q2: What is our Kafka cluster sizing? Need load test results.
  (Assigned: Jordan Chen — complete by 03/22)

## Timeline

| Milestone | Target Date | Description |
|-----------|-------------|-------------|
| RFC approved | 2026-03-24 | Begin implementation |
| Kafka cluster provisioned | 2026-03-31 | Infrastructure ready |
| Shadow mode deployment | 2026-04-07 | Consumers running, not acting |
| Dual-write comparison | 2026-04-14 | Validate event-driven path matches REST |
| Production rollout start | 2026-04-21 | 5% traffic |
| Full rollout | 2026-04-28 | 100% traffic |
| Synchronous path decommission | 2026-05-12 | Remove legacy code |
```

This RFC is 4 pages, took ~6 hours to write, and will guide 3 engineers for 6 weeks. That is the leverage of specs.

Notice what the RFC accomplished before a line of code was written: it surfaced the ordering requirement (which ruled out RabbitMQ), established the non-goal of changing the external API (which saved weeks of frontend negotiation), and produced a rollout plan with a clear rollback mechanism. Every one of those outcomes would have otherwise emerged painfully during implementation, at 10x the cost.

---

## 3. ARCHITECTURE DECISION RECORDS (ADRs)

### 3.1 ADRs vs. RFCs

RFCs and ADRs serve different purposes:

| Dimension | RFC | ADR |
|-----------|-----|-----|
| Purpose | Propose a change | Record a decision |
| Timing | Before implementation | During or after implementation |
| Length | 2-6 pages | 1-2 pages |
| Audience | Team deciding what to build | Future engineers understanding why |
| Lifecycle | Draft → Review → Accepted → Implemented | Proposed → Accepted → Deprecated → Superseded |
| Frequency | Per-project or per-feature | Per-decision (many per project) |

An RFC might result in 3-5 ADRs. The RFC proposes the migration to Kafka. The ADRs record specific decisions made during implementation: "ADR-0023: Use Avro for Kafka message serialization" and "ADR-0024: Partition reservation topics by event_id."

Ch 27 introduces ADRs as a documentation format. This section goes deeper into the decision-making framework and shows how ADRs integrate with the spec-driven workflow.

The ADR is, in many ways, the unsung hero of engineering documentation. RFCs get attention because they are written before the exciting work starts. ADRs quietly do the long-term work of preserving institutional memory. The question "why is this code this way?" is one of the most common questions in any engineering organization, and the answer should never be "I have no idea, that engineer left two years ago." ADRs are the answer.

### 3.2 The Nygard ADR Template

Michael Nygard's original ADR format is deliberately minimal:

```markdown
# ADR-[NUMBER]: [Short Title of Decision]

## Status

[Proposed | Accepted | Deprecated | Superseded by ADR-XXXX]

## Context

[What is the situation? What forces are at play? What constraints exist?
Describe the problem without prescribing a solution.]

## Decision

[What is the decision? State it clearly in active voice.
"We will use X" not "X was chosen."]

## Consequences

[What are the positive, negative, and neutral consequences of this
decision? Be honest about trade-offs.]
```

The beauty of this format is its brevity. An ADR should take 15-30 minutes to write. If it takes longer, you are writing an RFC, not an ADR.

The "active voice" note in the Decision section matters more than it seems. "X was chosen" is passive and disconnected. "We will use X" is a commitment with owners. When someone reads that ADR in two years and wonders whether the constraint still applies, the active framing reminds them that humans made this choice under specific conditions — and those conditions may have changed.

### 3.3 MADR (Markdown ADR) Format

The Markdown Architectural Decision Records (MADR) format extends Nygard's template with more structure:

```markdown
# ADR-[NUMBER]: [Short Title]

## Status

[Proposed | Accepted | Deprecated | Superseded by ADR-XXXX]

## Context and Problem Statement

[Describe the context and the problem or question that motivates
this decision.]

## Decision Drivers

- [Driver 1: e.g., performance requirement]
- [Driver 2: e.g., team familiarity]
- [Driver 3: e.g., operational cost]

## Considered Options

1. [Option 1]
2. [Option 2]
3. [Option 3]

## Decision Outcome

Chosen option: "[Option X]", because [justification].

### Positive Consequences

- [Benefit 1]
- [Benefit 2]

### Negative Consequences

- [Drawback 1]
- [Mitigation strategy]

## Pros and Cons of the Options

### [Option 1]

- Good, because [reason]
- Bad, because [reason]

### [Option 2]

- Good, because [reason]
- Bad, because [reason]
```

### 3.4 ADR as a Commit

ADRs should live in the codebase, not in a wiki. The recommended location is `docs/adr/`. Each ADR is a single Markdown file, numbered sequentially:

```
docs/
  adr/
    0001-use-postgresql-for-primary-datastore.md
    0002-adopt-event-sourcing-for-reservations.md
    0003-use-kafka-over-rabbitmq.md
    0004-implement-saga-pattern-for-distributed-transactions.md
    template.md
```

When you make an architectural decision, the ADR is committed alongside the code that implements it. This way, `git log docs/adr/` shows the chronological history of every architectural decision, and `git blame` shows who made each decision and when.

This co-location is critical. A wiki can go stale and disconnected. An ADR in the repo is versioned with the code it describes. If you ever need to understand what the team was thinking when they introduced the saga pattern, you can check out that commit and read the ADR alongside the code that instantiated it. That is documentation archaeology done right.

### 3.5 When to Write an ADR

Write an ADR when you make a decision about:

- **Technology choices** — choosing a database, message broker, or framework
- **Architectural patterns** — adopting event sourcing, CQRS, or microservices
- **Protocol changes** — switching from REST to gRPC, or from polling to WebSockets
- **Removing features** — deprecating an API, removing a service
- **Significant trade-offs** — choosing consistency over availability, or vice versa
- **Convention changes** — new coding standards, new testing requirements

Do NOT write an ADR for:

- Implementation details that can change without architectural impact
- Library version upgrades (unless they involve breaking API changes)
- Routine bug fixes

### 3.6 TicketPulse ADR Examples

**ADR-0001:**

```markdown
# ADR-0001: Use PostgreSQL as Primary Datastore

## Status

Accepted

## Context

TicketPulse needs a primary datastore for events, venues, users,
and reservations. Our team has 4 backend engineers. The data model is
relational (events belong to venues, reservations reference events
and users). Expected write volume is ~500 reservations/second during
peak on-sales, with ~50,000 concurrent read queries for event listings.

We evaluated three options:
1. PostgreSQL
2. MongoDB
3. Amazon DynamoDB

## Decision

We will use PostgreSQL (via Amazon RDS) as our primary datastore.

## Consequences

**Positive:**
- Strong consistency guarantees for reservation integrity (no double-booking)
- Team has deep PostgreSQL experience (3 of 4 engineers)
- Rich query capabilities for reporting and analytics
- Mature ecosystem of tools (pg_dump, pgAdmin, Datadog integration)
- ACID transactions simplify our reservation logic

**Negative:**
- Vertical scaling has limits; we will need read replicas above ~10,000
  reads/second
- Schema migrations require careful planning on a live system
- No built-in horizontal write scaling (unlike DynamoDB)

**Neutral:**
- We will use Amazon RDS managed service, trading some control for
  reduced operational burden
- Cost is predictable (instance-based) vs. DynamoDB's pay-per-request
```

**ADR-0003:**

```markdown
# ADR-0003: Use Kafka Over RabbitMQ for Event Streaming

## Status

Accepted (supersedes informal Slack discussion from 2026-01-15)

## Context and Problem Statement

RFC-001 proposes migrating to event-driven reservation processing.
We need a message broker that supports:
- Ordered processing per event (to prevent overselling)
- High throughput (target: 50,000 messages/second during peaks)
- Message replay (for debugging and reprocessing failed consumers)
- At-least-once delivery with idempotent consumers

## Decision Drivers

- Message ordering guarantees
- Throughput at peak load
- Replay capability for debugging
- Team operational experience
- Managed service availability on AWS

## Considered Options

1. Apache Kafka (via Amazon MSK)
2. RabbitMQ (self-managed on EC2)
3. Amazon SQS + SNS

## Decision Outcome

Chosen option: "Apache Kafka (via Amazon MSK)", because it provides
partition-level ordering, log-based replay, and throughput that exceeds
our requirements by 10x.

### Positive Consequences

- Partition-by-key ordering guarantees prevent reservation races
- Log retention enables replay of events for debugging or backfilling
  new consumers
- MSK managed service reduces operational burden
- Kafka Connect ecosystem for future integrations (CDC, S3 sink)

### Negative Consequences

- Higher operational complexity than SQS (topic management,
  partition rebalancing, consumer group monitoring)
- MSK cost is higher than SQS for low-throughput topics
  (~$400/month base cost vs. pay-per-message)
- Team has limited Kafka experience — need training investment
  (estimated: 2 days per engineer)

## Pros and Cons of the Options

### RabbitMQ

- Good, because team has operational experience
- Good, because simpler consumer model (push-based)
- Bad, because no built-in message ordering across consumers
- Bad, because no native replay capability
- Bad, because throughput ceiling is lower (~20,000 msg/s per node)

### Amazon SQS + SNS

- Good, because fully managed, zero operational overhead
- Good, because pay-per-message pricing is cost-effective at low volume
- Bad, because SQS FIFO queues have a 3,000 msg/s throughput limit
- Bad, because no replay — once consumed, messages are gone
- Bad, because fan-out via SNS adds latency and complexity
```

**ADR-0004:**

```markdown
# ADR-0004: Implement Saga Pattern for Distributed Transactions

## Status

Accepted

## Context

With the event-driven architecture (RFC-001), the reservation flow
spans multiple services: ReservationService, PaymentWorker, and
InventoryWorker. We need to maintain data consistency across these
services without distributed two-phase commit (which Kafka does not
support).

Two patterns exist for managing distributed transactions:
1. Choreography-based saga (events trigger next steps)
2. Orchestration-based saga (a central coordinator manages the flow)

## Decision

We will use a choreography-based saga for the reservation flow.

Each service reacts to events and publishes the result:

1. ReservationService publishes `reservation.created`
2. InventoryWorker consumes it, reserves seats, publishes
   `inventory.reserved`
3. PaymentWorker consumes it, charges the card, publishes
   `payment.completed` or `payment.failed`
4. ReservationService consumes the result and updates the final status

Compensating transactions handle failures:
- If payment fails → InventoryWorker releases the reserved seats
- If inventory reservation times out (>30s) → cancel the reservation

## Consequences

**Positive:**
- No single point of failure (no central orchestrator)
- Services remain loosely coupled
- Each service owns its own logic and can be deployed independently

**Negative:**
- Harder to reason about the complete flow (logic is spread across services)
- Debugging requires correlating events across multiple topics
- Adding new steps requires changes to multiple services

**Mitigation:** We will build a reservation flow dashboard that
visualizes the saga state by aggregating events with the same
reservation_id (see observability plan in RFC-001).
```

---

## 4. CONTRACT-FIRST API DESIGN

### 4.1 The Principle

Contract-first API design means you define the interface before writing a single line of server code. The contract (OpenAPI spec, Protobuf definition, GraphQL schema) is the source of truth. Implementation follows.

This inverts the common approach where developers build the server, then document the API after the fact. Contract-first has three major advantages:

1. **Parallel development.** Frontend and backend teams can work simultaneously. The frontend codes against the contract (using mock servers), while the backend implements it.
2. **Code generation.** Typed client SDKs, server stubs, and documentation are generated from the contract, eliminating an entire class of bugs (mismatched types, missing fields, wrong HTTP methods).
3. **Contract testing.** You can automatically verify that the implementation matches the contract, catching drift before it reaches production.

Here is a story I have seen play out more times than I can count. A backend team ships an endpoint. The frontend team integrates it. Two days later, someone notices that the response field the frontend relies on is named `user_id` in the contract and `userId` in the implementation. Both teams argue about who is "right." The spec was never authoritative. Now you have a production bug and a blame game.

Contract-first eliminates that entire class of argument. The contract is right, by definition. Implementations that deviate from it are wrong, and contract tests catch the deviation before it ships. Ch 25 covers API design patterns in depth — this section is about making that design stick through the power of a machine-readable, generated-from, tested-against contract.

### 4.2 OpenAPI for REST APIs

OpenAPI (formerly Swagger) is the standard for describing REST APIs. Here is a complete example for the TicketPulse event listing endpoint:

```yaml
openapi: 3.1.0
info:
  title: TicketPulse API
  version: 2.0.0
  description: |
    TicketPulse event discovery and ticket reservation API.
    All endpoints require Bearer token authentication unless
    marked as public.
  contact:
    name: TicketPulse Platform Team
    email: platform@ticketpulse.dev

servers:
  - url: https://api.ticketpulse.dev/v2
    description: Production
  - url: https://api.staging.ticketpulse.dev/v2
    description: Staging

security:
  - bearerAuth: []

paths:
  /events:
    get:
      operationId: listEvents
      summary: List upcoming events
      description: |
        Returns a paginated list of upcoming events. Results are ordered
        by event date ascending. Supports filtering by venue, category,
        date range, and price range.
      tags:
        - Events
      security: []  # Public endpoint — no auth required
      parameters:
        - name: venue_id
          in: query
          schema:
            type: string
            format: uuid
          description: Filter events by venue
          example: "550e8400-e29b-41d4-a716-446655440000"
        - name: category
          in: query
          schema:
            type: string
            enum:
              - concert
              - sports
              - theater
              - comedy
              - conference
          description: Filter by event category
        - name: date_from
          in: query
          schema:
            type: string
            format: date
          description: "Events on or after this date (ISO 8601: YYYY-MM-DD)"
          example: "2026-04-01"
        - name: date_to
          in: query
          schema:
            type: string
            format: date
          description: "Events on or before this date"
          example: "2026-06-30"
        - name: price_min
          in: query
          schema:
            type: integer
            minimum: 0
          description: "Minimum ticket price in cents"
        - name: price_max
          in: query
          schema:
            type: integer
            minimum: 0
          description: "Maximum ticket price in cents"
        - name: cursor
          in: query
          schema:
            type: string
          description: "Pagination cursor from previous response"
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: "Number of results per page"
      responses:
        "200":
          description: Successfully retrieved events
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EventListResponse"
              example:
                data:
                  - id: "evt_abc123"
                    title: "Arctic Monkeys — North American Tour"
                    slug: "arctic-monkeys-na-tour-2026"
                    category: "concert"
                    venue:
                      id: "ven_xyz789"
                      name: "Madison Square Garden"
                      city: "New York"
                      state: "NY"
                    date: "2026-05-15T20:00:00Z"
                    doors_open: "2026-05-15T18:30:00Z"
                    price_range:
                      min: 7500
                      max: 35000
                      currency: "USD"
                    availability: "available"
                    image_url: "https://cdn.ticketpulse.dev/events/evt_abc123/hero.jpg"
                pagination:
                  next_cursor: "eyJkYXRlIjoiMjAyNi0wNS0xNiJ9"
                  has_more: true
        "400":
          $ref: "#/components/responses/BadRequest"
        "429":
          $ref: "#/components/responses/RateLimited"
        "500":
          $ref: "#/components/responses/InternalError"

  /events/{event_id}:
    get:
      operationId: getEvent
      summary: Get event details
      tags:
        - Events
      security: []
      parameters:
        - name: event_id
          in: path
          required: true
          schema:
            type: string
          description: Event identifier
      responses:
        "200":
          description: Event details
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EventDetail"
        "404":
          $ref: "#/components/responses/NotFound"

  /reservations:
    post:
      operationId: createReservation
      summary: Reserve tickets for an event
      description: |
        Creates a ticket reservation. Returns 202 Accepted — the
        reservation is processed asynchronously. Poll the status
        endpoint or use WebSocket for real-time updates.
      tags:
        - Reservations
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateReservationRequest"
      responses:
        "202":
          description: Reservation accepted for processing
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ReservationAccepted"
        "400":
          $ref: "#/components/responses/BadRequest"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "409":
          description: Duplicate idempotency key
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "422":
          description: "Validation error (e.g., seats not available)"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Event:
      type: object
      required:
        - id
        - title
        - category
        - venue
        - date
        - price_range
        - availability
      properties:
        id:
          type: string
          description: Unique event identifier
        title:
          type: string
          maxLength: 200
        slug:
          type: string
          pattern: "^[a-z0-9-]+$"
        category:
          type: string
          enum: [concert, sports, theater, comedy, conference]
        venue:
          $ref: "#/components/schemas/VenueSummary"
        date:
          type: string
          format: date-time
        doors_open:
          type: string
          format: date-time
        price_range:
          $ref: "#/components/schemas/PriceRange"
        availability:
          type: string
          enum: [available, limited, sold_out]
        image_url:
          type: string
          format: uri

    EventDetail:
      allOf:
        - $ref: "#/components/schemas/Event"
        - type: object
          properties:
            description:
              type: string
              maxLength: 5000
            artists:
              type: array
              items:
                type: string
            sections:
              type: array
              items:
                $ref: "#/components/schemas/Section"
            policies:
              $ref: "#/components/schemas/EventPolicies"

    VenueSummary:
      type: object
      required: [id, name, city, state]
      properties:
        id:
          type: string
        name:
          type: string
        city:
          type: string
        state:
          type: string

    PriceRange:
      type: object
      required: [min, max, currency]
      properties:
        min:
          type: integer
          description: Minimum price in cents
        max:
          type: integer
          description: Maximum price in cents
        currency:
          type: string
          pattern: "^[A-Z]{3}$"
          description: ISO 4217 currency code

    Section:
      type: object
      required: [id, name, price, available_seats]
      properties:
        id:
          type: string
        name:
          type: string
        price:
          type: integer
          description: Price per seat in cents
        available_seats:
          type: integer
          minimum: 0

    EventPolicies:
      type: object
      properties:
        refund_policy:
          type: string
        age_restriction:
          type: string
        max_tickets_per_order:
          type: integer
          minimum: 1
          maximum: 8

    CreateReservationRequest:
      type: object
      required: [event_id, seat_ids, idempotency_key]
      properties:
        event_id:
          type: string
        seat_ids:
          type: array
          items:
            type: string
          minItems: 1
          maxItems: 8
        idempotency_key:
          type: string
          format: uuid
          description: |
            Client-generated UUID for idempotent reservation creation.
            If a reservation with this key already exists, the existing
            reservation is returned.

    ReservationAccepted:
      type: object
      required: [reservation_id, status, status_url]
      properties:
        reservation_id:
          type: string
        status:
          type: string
          enum: [pending]
        status_url:
          type: string
          format: uri

    EventListResponse:
      type: object
      required: [data, pagination]
      properties:
        data:
          type: array
          items:
            $ref: "#/components/schemas/Event"
        pagination:
          $ref: "#/components/schemas/Pagination"

    Pagination:
      type: object
      required: [has_more]
      properties:
        next_cursor:
          type: string
        has_more:
          type: boolean

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          description: Machine-readable error code
        message:
          type: string
          description: Human-readable error message
        details:
          type: object
          description: Additional error context

  responses:
    BadRequest:
      description: Invalid request parameters
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "invalid_parameter"
            message: "date_from must be a valid ISO 8601 date"
    Unauthorized:
      description: Missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    RateLimited:
      description: Too many requests
      headers:
        Retry-After:
          schema:
            type: integer
          description: Seconds until the rate limit resets
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    InternalError:
      description: Unexpected server error
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
```

Look at what this spec does for you: it defines every parameter with its type, constraints, and description. It covers all the error codes a consumer needs to handle. It includes concrete examples so that a frontend engineer can immediately understand what the response looks like. Compare this to "here is the endpoint, ask me what fields it returns" — which is how most APIs get consumed at teams without contract-first discipline. The OpenAPI spec is a gift to every engineer who will ever integrate with this API, including your future self.

### 4.3 AsyncAPI for Event-Driven APIs

AsyncAPI does for event-driven systems what OpenAPI does for REST. Here is the TicketPulse reservation events spec:

```yaml
asyncapi: 3.0.0
info:
  title: TicketPulse Reservation Events
  version: 1.0.0
  description: |
    Event-driven reservation pipeline. All messages use Avro
    serialization with Schema Registry.

servers:
  production:
    host: kafka.ticketpulse.internal:9092
    protocol: kafka
    description: Production Kafka cluster (MSK)

channels:
  reservationCreated:
    address: reservations.created
    messages:
      ReservationCreated:
        $ref: "#/components/messages/ReservationCreated"
    description: |
      Published when a user initiates a ticket reservation.
      Partitioned by event_id for ordered processing.

  paymentCompleted:
    address: reservations.payment.completed
    messages:
      PaymentCompleted:
        $ref: "#/components/messages/PaymentCompleted"
    description: Published when payment is successfully processed.

  paymentFailed:
    address: reservations.payment.failed
    messages:
      PaymentFailed:
        $ref: "#/components/messages/PaymentFailed"
    description: Published when payment processing fails.

  reservationConfirmed:
    address: reservations.confirmed
    messages:
      ReservationConfirmed:
        $ref: "#/components/messages/ReservationConfirmed"
    description: Published when the reservation is fully confirmed.

operations:
  publishReservationCreated:
    action: send
    channel:
      $ref: "#/channels/reservationCreated"
    summary: ReservationService publishes when a new reservation is initiated

  consumeReservationCreated:
    action: receive
    channel:
      $ref: "#/channels/reservationCreated"
    summary: PaymentWorker and InventoryWorker consume new reservations

  publishPaymentCompleted:
    action: send
    channel:
      $ref: "#/channels/paymentCompleted"
    summary: PaymentWorker publishes on successful payment

  consumePaymentCompleted:
    action: receive
    channel:
      $ref: "#/channels/paymentCompleted"
    summary: ReservationService consumes to update reservation status

components:
  messages:
    ReservationCreated:
      name: ReservationCreated
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - event_id
          - user_id
          - seat_ids
          - idempotency_key
          - created_at
        properties:
          reservation_id:
            type: string
            description: Unique reservation identifier
          event_id:
            type: string
            description: Event being reserved
          user_id:
            type: string
            description: User making the reservation
          seat_ids:
            type: array
            items:
              type: string
            description: Seats being reserved
          idempotency_key:
            type: string
            format: uuid
          total_amount_cents:
            type: integer
            description: Total price in cents
          currency:
            type: string
            default: USD
          created_at:
            type: string
            format: date-time

    PaymentCompleted:
      name: PaymentCompleted
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - payment_id
          - amount_cents
          - completed_at
        properties:
          reservation_id:
            type: string
          payment_id:
            type: string
            description: Stripe PaymentIntent ID
          amount_cents:
            type: integer
          completed_at:
            type: string
            format: date-time

    PaymentFailed:
      name: PaymentFailed
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - failure_reason
          - failed_at
        properties:
          reservation_id:
            type: string
          failure_reason:
            type: string
            enum:
              - insufficient_funds
              - card_declined
              - expired_card
              - processing_error
              - fraud_detected
          failure_code:
            type: string
            description: Provider-specific error code
          failed_at:
            type: string
            format: date-time

    ReservationConfirmed:
      name: ReservationConfirmed
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - event_id
          - user_id
          - confirmed_at
        properties:
          reservation_id:
            type: string
          event_id:
            type: string
          user_id:
            type: string
          seat_ids:
            type: array
            items:
              type: string
          confirmation_code:
            type: string
            description: Human-readable confirmation code (e.g., "TP-A3X9K2")
          confirmed_at:
            type: string
            format: date-time
```

### 4.4 Protocol Buffers for gRPC

For internal service-to-service communication where performance matters, Protocol Buffers define the contract:

```protobuf
syntax = "proto3";

package ticketpulse.inventory.v1;

import "google/protobuf/timestamp.proto";

option go_package = "github.com/ticketpulse/proto/inventory/v1";

// InventoryService manages seat availability and reservations.
// Internal service — not exposed to external clients.
service InventoryService {
  // ReserveSeats atomically reserves seats for a reservation.
  // Returns ALREADY_EXISTS if the idempotency_key was already used.
  // Returns RESOURCE_EXHAUSTED if any requested seat is unavailable.
  rpc ReserveSeats(ReserveSeatsRequest) returns (ReserveSeatsResponse);

  // ReleaseSeats releases previously reserved seats.
  // Used as a compensating transaction when payment fails.
  // Idempotent — releasing already-released seats is a no-op.
  rpc ReleaseSeats(ReleaseSeatsRequest) returns (ReleaseSeatsResponse);

  // GetAvailability returns real-time seat availability for an event.
  rpc GetAvailability(GetAvailabilityRequest) returns (GetAvailabilityResponse);

  // StreamAvailability provides real-time availability updates.
  rpc StreamAvailability(StreamAvailabilityRequest)
      returns (stream AvailabilityUpdate);
}

message ReserveSeatsRequest {
  string reservation_id = 1;
  string event_id = 2;
  repeated string seat_ids = 3;
  string idempotency_key = 4;
  // TTL for the reservation hold. If payment is not confirmed within
  // this duration, seats are automatically released.
  int32 hold_ttl_seconds = 5;  // Default: 600 (10 minutes)
}

message ReserveSeatsResponse {
  string reservation_id = 1;
  ReservationStatus status = 2;
  repeated SeatReservation seats = 3;
  google.protobuf.Timestamp expires_at = 4;
}

enum ReservationStatus {
  RESERVATION_STATUS_UNSPECIFIED = 0;
  RESERVATION_STATUS_HELD = 1;
  RESERVATION_STATUS_CONFIRMED = 2;
  RESERVATION_STATUS_RELEASED = 3;
  RESERVATION_STATUS_EXPIRED = 4;
}

message SeatReservation {
  string seat_id = 1;
  string section = 2;
  string row = 3;
  int32 number = 4;
  int32 price_cents = 5;
}

message ReleaseSeatsRequest {
  string reservation_id = 1;
  string event_id = 2;
  repeated string seat_ids = 3;
  string reason = 4;  // "payment_failed", "user_cancelled", "timeout"
}

message ReleaseSeatsResponse {
  int32 seats_released = 1;
}

message GetAvailabilityRequest {
  string event_id = 1;
  string section_id = 2;  // Optional — empty returns all sections
}

message GetAvailabilityResponse {
  string event_id = 1;
  repeated SectionAvailability sections = 2;
  google.protobuf.Timestamp as_of = 3;
}

message SectionAvailability {
  string section_id = 1;
  string name = 2;
  int32 total_seats = 3;
  int32 available_seats = 4;
  int32 price_cents = 5;
}

message StreamAvailabilityRequest {
  string event_id = 1;
}

message AvailabilityUpdate {
  string event_id = 1;
  string section_id = 2;
  int32 available_seats = 3;
  google.protobuf.Timestamp updated_at = 4;
}
```

### 4.5 The Code Generation Workflow

Once you have a contract, generate everything:

```bash
# From OpenAPI spec → TypeScript client SDK
npx @openapitools/openapi-generator-cli generate \
  -i specs/ticketpulse-api.yaml \
  -g typescript-fetch \
  -o generated/client-sdk \
  --additional-properties=supportsES6=true,typescriptThreePlus=true

# From OpenAPI spec → Go server stubs
npx @openapitools/openapi-generator-cli generate \
  -i specs/ticketpulse-api.yaml \
  -g go-server \
  -o generated/go-server

# From OpenAPI spec → TypeScript types only (lightweight)
npx openapi-typescript specs/ticketpulse-api.yaml \
  -o generated/types.ts

# From Protobuf → Go code
protoc --go_out=. --go-grpc_out=. \
  proto/inventory/v1/inventory.proto

# From Protobuf → TypeScript (for Node.js services)
npx grpc_tools_node_protoc \
  --ts_out=generated/ts \
  --grpc_out=generated/ts \
  proto/inventory/v1/inventory.proto
```

The generated TypeScript types from the OpenAPI spec look like this:

```typescript
// generated/types.ts — auto-generated, do not edit

export interface Event {
  id: string;
  title: string;
  slug?: string;
  category: "concert" | "sports" | "theater" | "comedy" | "conference";
  venue: VenueSummary;
  date: string;
  doors_open?: string;
  price_range: PriceRange;
  availability: "available" | "limited" | "sold_out";
  image_url?: string;
}

export interface CreateReservationRequest {
  event_id: string;
  seat_ids: string[];
  idempotency_key: string;
}

export interface ReservationAccepted {
  reservation_id: string;
  status: "pending";
  status_url: string;
}

// ... more types generated from every schema in the spec
```

Now the frontend team and backend team share the same types, generated from the same source of truth. If the spec changes, both sides regenerate and compilation errors tell you exactly what broke. That is the spec enforcing its own contract at compile time — one of the most powerful feedback loops in software engineering.

### 4.6 Contract Testing with Pact

Contract-first is only valuable if you verify that implementations match the contract. Pact is the standard tool for consumer-driven contract testing:

```typescript
// frontend/tests/contract/reservation.pact.ts
import { PactV4, MatchersV3 } from "@pact-foundation/pact";
const { like, eachLike, uuid } = MatchersV3;

const provider = new PactV4({
  consumer: "TicketPulse-WebApp",
  provider: "TicketPulse-API",
});

describe("Reservation API Contract", () => {
  it("creates a reservation and returns 202", async () => {
    await provider
      .addInteraction()
      .given("event evt_abc123 has available seats A1 and A2")
      .uponReceiving("a request to reserve seats")
      .withRequest("POST", "/api/v2/reservations", (builder) => {
        builder
          .headers({ "Content-Type": "application/json" })
          .jsonBody({
            event_id: "evt_abc123",
            seat_ids: ["A1", "A2"],
            idempotency_key: uuid(),
          });
      })
      .willRespondWith(202, (builder) => {
        builder.jsonBody({
          reservation_id: like("res_def456"),
          status: "pending",
          status_url: like("/api/v2/reservations/res_def456/status"),
        });
      })
      .executeTest(async (mockServer) => {
        const client = new TicketPulseClient(mockServer.url);
        const result = await client.createReservation({
          event_id: "evt_abc123",
          seat_ids: ["A1", "A2"],
        });

        expect(result.status).toBe("pending");
        expect(result.reservation_id).toBeDefined();
      });
  });
});
```

The Pact workflow:

1. **Consumer (frontend) writes a contract test** describing what it expects from the provider
2. **Pact generates a contract file** (JSON) from the test
3. **Provider (backend) verifies the contract** by replaying the consumer's expectations against the real implementation
4. **Pact Broker** (optional) stores contracts and tracks verification status across services

This closes the loop: the OpenAPI spec defines the contract, code generation produces types, and Pact verifies that the implementation matches. At no point can a backend engineer silently change a field name and break the frontend — the contract test will fail in CI, loudly, before the PR merges.

---

## 5. EXECUTABLE SPECIFICATIONS

### 5.1 BDD: Specs That Run as Tests

Behavior-Driven Development (BDD) closes the gap between specification and verification. Instead of writing requirements in one document and tests in another, you write specifications in a format that is both human-readable AND machine-executable.

This is the part where specs get genuinely exciting. You stop choosing between "document that's readable by stakeholders" and "tests that actually run." With Gherkin, you get both in one artifact.

Consider what this means in practice: your product manager can read your test suite. Your QA engineer can write test scenarios before implementation starts. Your compliance team can sign off on the exact scenarios that are verified in CI. A misunderstood requirement surfaces as a failing test before a single line of implementation code exists. That is the promise of BDD done well.

The Gherkin language is the standard:

```gherkin
Feature: Ticket Reservation
  As a TicketPulse user
  I want to reserve tickets for events
  So that I can attend live performances

  Background:
    Given the event "Arctic Monkeys — NA Tour" exists
    And the event has sections:
      | section    | price_cents | total_seats |
      | Floor      | 35000       | 200         |
      | Lower Bowl | 25000       | 500         |
      | Upper Bowl | 7500        | 1000        |
    And the user "alice@example.com" is authenticated

  Scenario: Successful reservation of available seats
    Given seats "F-A1" and "F-A2" in section "Floor" are available
    When Alice reserves seats "F-A1" and "F-A2"
    Then the reservation status should be "pending"
    And the reservation total should be 70000 cents
    And seats "F-A1" and "F-A2" should be held for 10 minutes

  Scenario: Reservation with unavailable seats
    Given seat "F-A1" is available
    And seat "F-A2" is already reserved by another user
    When Alice reserves seats "F-A1" and "F-A2"
    Then the reservation should fail with error "seats_unavailable"
    And seat "F-A1" should remain available
    And no payment should be initiated

  Scenario: Idempotent reservation creation
    Given Alice has already created a reservation with idempotency key "idk_123"
    When Alice creates another reservation with idempotency key "idk_123"
    Then the original reservation should be returned
    And no duplicate reservation should be created

  Scenario: Reservation hold expiration
    Given Alice has a pending reservation for seats "F-A1" and "F-A2"
    And the reservation hold TTL is 10 minutes
    When 11 minutes pass without payment confirmation
    Then the reservation status should be "expired"
    And seats "F-A1" and "F-A2" should be released
    And Alice should receive a "reservation_expired" notification

  Scenario: Concurrent reservation race condition
    Given seat "F-A1" is available
    And Alice and Bob both attempt to reserve seat "F-A1" simultaneously
    Then exactly one reservation should succeed
    And the other should fail with error "seats_unavailable"
    And the seat count should remain consistent

  Scenario Outline: Maximum tickets per order enforcement
    Given <available> seats are available in section "Floor"
    When Alice attempts to reserve <requested> seats
    Then the reservation should <result>

    Examples:
      | available | requested | result                                    |
      | 10        | 4         | succeed                                   |
      | 10        | 8         | succeed                                   |
      | 10        | 9         | fail with error "max_tickets_exceeded"    |
      | 2         | 4         | fail with error "insufficient_seats"      |
```

Notice the "Concurrent reservation race condition" scenario. That is not a unit test edge case — it is a business-critical correctness requirement expressed in plain English. When a new engineer joins the team, this file tells them, without ambiguity, that the system must handle concurrent reservation attempts correctly. When a refactor touches the reservation logic, these scenarios catch any regression immediately.

### 5.2 Implementing Gherkin Steps

The Gherkin spec becomes executable when you implement step definitions. Using Cucumber.js:

```typescript
// tests/steps/reservation.steps.ts
import { Given, When, Then, Before } from "@cucumber/cucumber";
import { expect } from "chai";
import { TestContext } from "../support/context";

let ctx: TestContext;

Before(async function () {
  ctx = new TestContext();
  await ctx.resetDatabase();
});

Given(
  "the event {string} exists",
  async function (eventTitle: string) {
    ctx.event = await ctx.createEvent({ title: eventTitle });
  }
);

Given(
  "the event has sections:",
  async function (dataTable) {
    const rows = dataTable.hashes();
    for (const row of rows) {
      await ctx.createSection({
        event_id: ctx.event.id,
        name: row.section,
        price_cents: parseInt(row.price_cents),
        total_seats: parseInt(row.total_seats),
      });
    }
  }
);

Given(
  "seats {string} and {string} in section {string} are available",
  async function (seat1: string, seat2: string, section: string) {
    const sectionRecord = await ctx.getSection(ctx.event.id, section);
    await ctx.ensureSeatsAvailable(sectionRecord.id, [seat1, seat2]);
  }
);

When(
  "Alice reserves seats {string} and {string}",
  async function (seat1: string, seat2: string) {
    ctx.reservationResult = await ctx.apiClient.createReservation({
      event_id: ctx.event.id,
      seat_ids: [seat1, seat2],
      idempotency_key: ctx.generateIdempotencyKey(),
    });
  }
);

Then(
  "the reservation status should be {string}",
  async function (expectedStatus: string) {
    expect(ctx.reservationResult.status).to.equal(expectedStatus);
  }
);

Then(
  "the reservation total should be {int} cents",
  async function (expectedTotal: number) {
    const details = await ctx.apiClient.getReservation(
      ctx.reservationResult.reservation_id
    );
    expect(details.total_amount_cents).to.equal(expectedTotal);
  }
);

Then(
  "seats {string} and {string} should be held for {int} minutes",
  async function (seat1: string, seat2: string, minutes: number) {
    const availability = await ctx.inventoryClient.getAvailability(
      ctx.event.id
    );
    const seat1Status = availability.seats.find((s) => s.id === seat1);
    const seat2Status = availability.seats.find((s) => s.id === seat2);

    expect(seat1Status?.status).to.equal("held");
    expect(seat2Status?.status).to.equal("held");

    const expectedExpiry = new Date(
      Date.now() + minutes * 60 * 1000
    );
    expect(new Date(seat1Status!.hold_expires_at)).to.be.closeTo(
      expectedExpiry,
      5000 // 5-second tolerance
    );
  }
);

Then(
  "the reservation should fail with error {string}",
  async function (errorCode: string) {
    expect(ctx.reservationResult.error?.code).to.equal(errorCode);
  }
);
```

### 5.3 When BDD Shines and When It Is Overkill

**BDD shines when:**

- Business stakeholders need to read and approve the test scenarios
- The domain is complex and edge cases are numerous (payments, compliance, reservations)
- Multiple teams need to agree on behavior before implementing
- Regulatory requirements demand human-readable test evidence
- The system has critical user-facing flows that must not regress

**BDD is overkill when:**

- The API is internal-only and the team is small
- The behavior is purely technical (connection pooling, caching logic)
- The feature is simple CRUD with no complex business rules
- You are prototyping and the requirements are still fluid

This calibration matters. BDD has a setup cost — writing step definitions, maintaining the test context, keeping the Gherkin in sync with implementation as requirements evolve. Apply it where it earns its keep. For a fintech payment flow or a healthcare authorization system, BDD is not optional — it is the spec that proves you built the right thing. For an internal admin dashboard that lists users? Overkill. Regular unit tests with clear names are sufficient.

### 5.4 Property-Based Testing as Specification

Property-based testing is another form of executable specification. Instead of specifying individual examples, you specify properties that should always hold:

```typescript
// tests/properties/reservation.property.ts
import * as fc from "fast-check";

describe("Reservation properties", () => {
  it("should never oversell seats", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 1000 }),   // total seats
        fc.integer({ min: 1, max: 100 }),     // concurrent requests
        fc.integer({ min: 1, max: 8 }),       // seats per request
        async (totalSeats, concurrentRequests, seatsPerRequest) => {
          const event = await createEventWithSeats(totalSeats);

          // Fire concurrent reservations
          const results = await Promise.allSettled(
            Array.from({ length: concurrentRequests }, () =>
              apiClient.createReservation({
                event_id: event.id,
                seat_count: seatsPerRequest,
              })
            )
          );

          const successfulReservations = results.filter(
            (r) => r.status === "fulfilled" && r.value.status !== "failed"
          );

          const totalReserved = successfulReservations.length * seatsPerRequest;

          // THE PROPERTY: total reserved seats must never exceed total seats
          expect(totalReserved).to.be.at.most(totalSeats);
        }
      ),
      { numRuns: 50 }  // Run 50 random combinations
    );
  });

  it("should produce consistent seat counts", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 500 }),
        async (totalSeats) => {
          const event = await createEventWithSeats(totalSeats);

          // Reserve some seats
          const reserved = Math.floor(Math.random() * totalSeats);
          await reserveNSeats(event.id, reserved);

          const availability = await apiClient.getAvailability(event.id);

          // THE PROPERTY: available + reserved + held = total
          const sum = availability.sections.reduce(
            (acc, s) => acc + s.available + s.reserved + s.held,
            0
          );
          expect(sum).to.equal(totalSeats);
        }
      )
    );
  });
});
```

Property-based tests encode invariants — rules that should hold for ALL possible inputs. They are particularly powerful for finding edge cases that example-based tests miss. "Never oversell seats" is not just a test case — it is a business rule expressed as an executable specification. When the property fails with a counter-example on some weird combination of inputs, you have found a real bug in your specification or implementation, not just a hypothetical.

---

## 6. SPECIFICATION LANGUAGES AND FORMATS

### 6.1 Comparison Table

| Format | Domain | Machine-Readable | Human-Readable | Generates Code | Best For |
|--------|--------|:---:|:---:|:---:|--------|
| OpenAPI | REST APIs | Yes | Yes (YAML) | Yes | External APIs, public docs |
| AsyncAPI | Event APIs | Yes | Yes (YAML) | Yes | Kafka, RabbitMQ, WebSocket |
| Protobuf | gRPC/RPC | Yes | Moderate | Yes | Internal service-to-service |
| JSON Schema | Data validation | Yes | Moderate | Yes | Request/response validation |
| GraphQL SDL | Graph APIs | Yes | Yes | Yes | Client-driven APIs |
| Gherkin | Business logic | Yes | Very | Tests only | Business-critical flows |
| ADR/RFC | Architecture | No | Very | No | Decision-making, alignment |
| CLAUDE.md | AI behavior | Moderate | Very | No (prompt) | AI agent configuration |

### 6.2 Decision Matrix

Use this to choose the right specification format:

**Is it a public-facing REST API?** → OpenAPI. No exceptions. The tooling ecosystem (Swagger UI, code generation, Postman import) is unmatched.

**Is it an event-driven system?** → AsyncAPI. It mirrors OpenAPI's structure for message-based systems, so if your team knows OpenAPI, the learning curve is minimal.

**Is it internal service-to-service over gRPC?** → Protobuf. The performance benefits of binary serialization and the type safety of generated code justify the reduced readability.

**Is it a client-driven API where different consumers need different data shapes?** → GraphQL SDL. The schema IS the specification.

**Is it a complex business process with stakeholder visibility requirements?** → Gherkin. The Given/When/Then format is readable by non-engineers and executable by CI.

**Is it a data format or configuration schema?** → JSON Schema. Supported by every language and used by OpenAPI internally.

**Is it an architectural decision?** → ADR. Short, committed to the repo alongside code.

**Is it a feature proposal affecting multiple teams?** → RFC. Longer, with alternatives and risk analysis.

The most common mistake is reaching for the most formal format for every situation. You do not need an OpenAPI spec for an internal helper script. You do not need a Gherkin scenario for a simple read endpoint. The right spec for the situation is the one that is actually going to get written, read, and maintained — not the theoretically most rigorous one.

---

## 7. AI-NATIVE SPEC-DRIVEN DEVELOPMENT

### 7.1 The New Paradigm

In the pre-AI era, specs were consumed by humans who wrote code. In the AI era, specs are consumed by AI agents that generate code. This changes what a good spec looks like.

Human-consumed specs can be somewhat ambiguous — a skilled developer fills in gaps with common sense and domain knowledge. AI-consumed specs must be precise, because AI agents will implement exactly what you specify (including your mistakes).

The shift: **the spec is no longer a communication tool between humans. It is a programming interface between human intent and machine execution.**

This is the most important consequence of the AI inflection point discussed in section 1.4. You are no longer writing specs to help teammates understand the design. You are writing specs to program a system that will produce implementations from them. The precision requirement goes up dramatically. The payoff — speed of execution — goes up even more dramatically.

If you have spent time with Ch 17 on Claude Code, you have felt this firsthand. Vague instructions produce vague code. Precise instructions — input types, output shapes, constraints, edge cases, file locations, naming conventions — produce code you can review and merge. The entire discipline of prompt engineering is, at its core, specification writing with a very small context budget.

### 7.2 CLAUDE.md as a Behavioral Specification

`CLAUDE.md` (introduced in Ch 17) is a specification file that defines how an AI agent should behave when working on your codebase. It is a behavioral spec, not a feature spec:

```markdown
# CLAUDE.md — TicketPulse Engineering Spec

## Project Context
TicketPulse is a ticket reservation platform built with:
- Backend: Node.js 22 + TypeScript 5.4 + Fastify 5
- Database: PostgreSQL 16 (via Drizzle ORM)
- Message broker: Apache Kafka (Amazon MSK)
- Frontend: Next.js 15 + React 19
- Infrastructure: AWS (ECS Fargate, RDS, MSK, CloudFront)

## Code Conventions
- All source files use TypeScript strict mode
- Use named exports, never default exports
- Errors are typed: throw new AppError("code", "message", statusCode)
- All API handlers follow the pattern in src/api/handlers/_template.ts
- Database queries go in src/repositories/, never in handlers
- Use Drizzle query builder, never raw SQL (exception: migrations)
- Test files live next to source: foo.ts → foo.test.ts

## Architecture Rules
- Services do not import from other services directly. Use events.
- The only synchronous cross-service call is to InventoryService via gRPC.
- All Kafka producers use the transactional outbox pattern (see src/lib/outbox.ts)
- Reservation state transitions must go through ReservationStateMachine
  (src/domain/reservation-state-machine.ts). Never update status directly.

## Testing Requirements
- Every new API endpoint needs: unit test, integration test, contract test
- Integration tests use testcontainers (PostgreSQL + Kafka)
- Run tests with: npm test (unit), npm run test:integration, npm run test:contract
- Minimum coverage: 80% line, 70% branch

## Common Gotchas
- Kafka consumer group IDs must be unique per service (format: svc-{name}-{topic})
- Drizzle migrations are in src/db/migrations/ — run with: npm run db:migrate
- The idempotency_key column has a unique constraint — handle ConflictError
- Price fields are always in cents (integer), never dollars (float)
```

This spec does not describe a feature — it describes the constraints and conventions an AI agent must follow when implementing ANY feature. It is the most leveraged file in the repository.

The "Common Gotchas" section is particularly valuable. Every item in that section represents a mistake that was made — probably multiple times — before someone thought to write it down. Each line is a concrete lesson encoded as a behavioral constraint. The "price fields are always in cents" rule exists because at some point a float comparison produced a subtle off-by-one error in a billing calculation. The gotchas are the distilled institutional knowledge of the team, packaged in a format that prevents the same mistakes from recurring.

Keep CLAUDE.md current. It is a living spec. When conventions change, update it before anyone uses the old conventions in new AI-generated code. The investment in maintaining it pays dividends across every AI-assisted development session the team runs.

### 7.3 Writing Specs That AI Can Execute

When writing a feature spec for AI implementation, follow these principles:

**1. Be precise about inputs and outputs:**

```markdown
## Bad (ambiguous)
Create an endpoint for searching events.

## Good (precise)
Create GET /api/v2/events/search that:
- Accepts query parameters: q (string, required, min 2 chars),
  category (enum: concert|sports|theater|comedy|conference, optional),
  date_from (ISO 8601 date, optional), date_to (ISO 8601 date, optional),
  limit (integer 1-100, default 20), cursor (string, optional)
- Returns 200 with { data: Event[], pagination: { next_cursor, has_more } }
- Uses PostgreSQL full-text search on events.title and events.description
- Results ordered by ts_rank descending, then by event date ascending
- Returns 400 if q is less than 2 characters
- Returns 400 if date_from > date_to
- Rate limited: 30 requests per minute per IP (public endpoint, no auth)
```

**2. Include acceptance criteria as testable assertions:**

```markdown
## Acceptance Criteria
- [ ] GET /api/v2/events/search?q=arctic returns events with "Arctic" in title
- [ ] GET /api/v2/events/search?q=ar returns 400 (min 2 chars is enforced on meaningful queries, but "ar" has exactly 2 chars — this should succeed)
- [ ] GET /api/v2/events/search?q=a returns 400
- [ ] Searching for "Monkeys" matches "Arctic Monkeys — NA Tour" (partial match)
- [ ] Results with higher relevance appear first
- [ ] Pagination works: first page returns next_cursor, second page uses it
- [ ] Category filter narrows results correctly
- [ ] Date range filter is inclusive on both ends
- [ ] Response time <100ms for queries matching <1000 events (add index)
```

**3. Specify constraints and non-goals explicitly:**

```markdown
## Constraints
- Must use existing Event schema from src/db/schema/events.ts
- Must follow handler pattern in src/api/handlers/_template.ts
- Must add OpenAPI spec to specs/ticketpulse-api.yaml
- Must not add new dependencies (use existing pg full-text search)

## Non-Goals
- Fuzzy matching / typo tolerance (defer to Elasticsearch migration, RFC-005)
- Search history / analytics (separate feature)
- Autocomplete / typeahead (separate endpoint)
```

**4. Provide examples of expected behavior:**

```markdown
## Example Interactions

### Search by title
Request:  GET /api/v2/events/search?q=arctic+monkeys&limit=2
Response: 200
{
  "data": [
    {
      "id": "evt_abc123",
      "title": "Arctic Monkeys — NA Tour",
      "category": "concert",
      "date": "2026-05-15T20:00:00Z",
      "relevance_score": 0.95
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false }
}

### Search with filters
Request:  GET /api/v2/events/search?q=tour&category=concert&date_from=2026-05-01
Response: 200
{
  "data": [...only concert events from May 2026 onwards matching "tour"...],
  "pagination": { "next_cursor": "eyJ...", "has_more": true }
}

### Invalid query
Request:  GET /api/v2/events/search?q=a
Response: 400
{
  "code": "invalid_parameter",
  "message": "Query parameter 'q' must be at least 2 characters"
}
```

### 7.4 The Design Doc to AI Implementation Workflow

Many companies now use this workflow:

1. **Engineer writes design doc / RFC** (human, 2-4 hours)
2. **Engineer writes feature spec with acceptance criteria** (human, 1-2 hours)
3. **AI agent implements the feature** (AI, 15-60 minutes)
4. **Engineer reviews the diff** (human, 30-60 minutes)
5. **AI agent fixes review comments** (AI, 5-15 minutes)
6. **Merge and deploy** (automated)

Total human time: 4-7 hours. Total wall-clock time: 1 day. Without AI: 1-3 weeks.

The spec is what makes step 3 possible. Without a spec, the AI agent guesses — and guessing produces code that looks right but is wrong in subtle ways. With a spec, the AI agent has clear constraints and the review in step 4 can focus on "does this match the spec?" rather than "does this make sense?"

This is the workflow that turns a 10-engineer team into one that ships at the pace of a 50-engineer team. But notice where the leverage actually sits: it is in the spec quality at steps 1 and 2. If those are vague, step 3 produces code that requires so much review and iteration that you lose the velocity advantage entirely. The spec is the multiplier.

### 7.5 Prompt Engineering IS Specification Writing

Every time you write a prompt for an AI agent, you are writing a micro-spec. The skills are identical:

| Spec-Writing Skill | Prompt-Engineering Equivalent |
|---|---|
| Define inputs and outputs | Describe expected request/response format |
| State constraints | List rules and restrictions |
| Provide examples | Include few-shot examples |
| Specify non-goals | Say what the AI should NOT do |
| Acceptance criteria | Describe how to verify correctness |
| Edge cases | List corner cases to handle |

Engineers who are good at writing specs are automatically good at prompt engineering. Engineers who skip specs also write vague prompts and get poor AI output. The skill is the same: precise communication of intent.

This is not a coincidence — it is the same cognitive activity. You are modeling what another actor (human or AI) needs to know to produce the output you want. The vocabulary differs. The discipline is identical.

### 7.6 The AI-First Development Loop

The emerging pattern for AI-native teams:

```
┌─────────────────────────────────────────────────┐
│                                                   │
│   ┌──────┐    ┌──────────┐    ┌──────┐          │
│   │ SPEC ├───→│ GENERATE ├───→│ TEST │          │
│   └──┬───┘    └──────────┘    └──┬───┘          │
│      │                            │               │
│      │         ┌──────────┐      │               │
│      └─────────│  REFINE  │←─────┘               │
│                │   SPEC   │                       │
│                └──────────┘                       │
│                                                   │
└─────────────────────────────────────────────────┘
```

1. **Spec** — Human writes the specification
2. **Generate** — AI agent produces implementation from spec
3. **Test** — Automated tests (generated from spec) validate the implementation
4. **Refine Spec** — If tests fail, the human refines the spec (not the code)

The critical insight: when tests fail, the first instinct should be to fix the spec, not the generated code. If you edit generated code directly, you lose the spec-to-code traceability. Fix the spec, regenerate, retest. This keeps the spec as the source of truth.

This takes discipline, especially at first. You will look at generated code, see a 2-line fix, and be tempted to just edit it. Resist. The moment you edit generated code directly, you create a divergence between spec and implementation. The next time you regenerate from the spec, your hand-edit disappears. Always fix the spec first.

---

## 8. THE SPEC-DRIVEN DEVELOPMENT WORKFLOW

### 8.1 Step-by-Step Workflow for a New Feature

Here is the complete workflow for building a new feature using spec-driven development:

**Step 1: Write the One-Pager (30-60 minutes)**

Answer three questions:
- What problem are we solving? (Include metrics if possible)
- What are the goals? (Specific, measurable)
- What are the non-goals? (Prevent scope creep)

This is a 1-page document. Send it to stakeholders asynchronously. The one-pager exists to surface alignment problems as cheaply as possible. If someone reads your one-pager and thinks you are solving the wrong problem, you want to know that now, before you spend eight hours on an RFC.

**Step 2: Get Alignment (30 minutes)**

Share the one-pager and collect feedback. This should be a 30-minute meeting or an async comment thread, not a 3-hour design session. The one-pager's job is to get a go/no-go decision and surface major concerns.

Common outcomes:
- "Looks good, proceed to RFC" — ideal
- "We need to adjust the scope" — update non-goals and re-share
- "This conflicts with Team X's work" — pause, coordinate, then proceed

**Step 3: Write the RFC (2-8 hours)**

Now write the full technical design using the RFC template from Section 2.5. Include:
- Detailed design with diagrams
- API changes (before/after examples)
- Data model changes
- Migration plan
- Risk analysis

Set a review deadline (usually 1 week). Assign 2-3 reviewers.

**Step 4: Define API Contracts (2-4 hours)**

Write the formal API specification:
- OpenAPI YAML for REST endpoints
- AsyncAPI YAML for event-driven interfaces
- Protobuf definitions for gRPC services
- JSON Schema for shared data structures

This is the contract that enables parallel work. The moment you publish the contract, both frontend and backend can start building. Without the contract, they must serialize — backend first, then frontend. Contract-first gives you weeks of calendar time back on every significant feature.

**Step 5: Write Acceptance Criteria as Executable Specs (2-4 hours)**

Translate the RFC's goals and design into testable specifications:
- Gherkin scenarios for business-critical flows
- Property-based test specs for invariants
- Contract test definitions for API boundaries

These specs will be used to validate the implementation, whether it is written by a human or generated by AI.

**Step 6: Implementation (variable)**

This is now the straightforward part. The spec constrains the solution space enough that implementation is largely mechanical:
- Human implementation: Follow the API contract, satisfy the acceptance criteria
- AI implementation: Feed the spec to an AI agent, review the output
- Hybrid: AI generates the scaffolding, human writes the complex business logic

Notice that step 6 is labeled "variable" — because the spec has already resolved all the hard questions. What used to be 70% of the work (figuring out what to build) is now done before the first line of code. What remains is execution, which is where AI assistance compounds most powerfully.

**Step 7: Record ADRs (15-30 minutes per decision)**

During implementation, decisions will arise that were not covered by the RFC. Record each one as an ADR:
- "We chose Avro serialization over JSON for Kafka messages because..."
- "We added a circuit breaker to the payment service call because..."
- "We decided against caching event availability because..."

**Step 8: Review Against Original Spec (1-2 hours)**

The final review checks the implementation against the spec:
- Does the API match the OpenAPI contract? (Contract tests should verify this)
- Do the acceptance criteria pass? (Executable specs should verify this)
- Does the implementation match the RFC's design? (Human review)
- Are there deviations from the spec? If so, update the spec to match reality.

### 8.2 Timeline Overlay

For a medium-complexity feature (2-week sprint):

| Day | Activity | Who |
|-----|----------|-----|
| Day 1 | One-pager + stakeholder alignment | Tech lead |
| Day 2-3 | RFC writing + API contract definition | Tech lead |
| Day 3-5 | RFC review period (async) | Team + stakeholders |
| Day 4-5 | Acceptance criteria / executable specs | QA + tech lead |
| Day 5 | RFC approved, implementation begins | Full team |
| Day 5-9 | Implementation (parallel: frontend + backend + tests) | Full team |
| Day 10 | Integration testing, review against spec, ADRs | Full team |

Notice that implementation does not start until Day 5 — half the sprint. This feels slow to managers who measure velocity in lines-of-code. But the implementation phase is dramatically more efficient because everyone knows exactly what to build, tests are already written, and the API contract enables parallel work.

If you get pushback on this — and you will — frame it in terms of outcomes, not process. "The last feature took 3 weeks because we reworked the API design twice after the frontend integrated. This time, we spent 4 days upfront and the integration should be straightforward." Ch 9 covers the leadership skills for making this case effectively.

### 8.3 The Two-Track Pattern

For larger projects, run specification and prototyping in parallel:

**Track 1 (Spec):** Write the RFC, define contracts, write acceptance criteria.

**Track 2 (Spike):** Build a quick prototype to validate technical feasibility and discover unknowns.

The spike's job is NOT to produce production code. Its job is to answer questions that the spec cannot:
- "Can PostgreSQL full-text search handle our query volume?" (Benchmark)
- "Does the Stripe API support our refund flow?" (Experiment)
- "Is the Kafka consumer lag acceptable at our throughput?" (Load test)

The spike results feed back into the RFC, making it more accurate. The spike code is thrown away. This is hard for junior engineers — they want to keep the spike code. Do not let them. Spike code has wrong abstractions, no tests, and technical debt baked in. The spec-driven implementation will be better.

I know how this sounds. "Throw away working code" sounds like waste. But the spike's value was the learning, not the code. The learning is now encoded in the spec, where it will guide a much cleaner implementation. Keep the spike code and you are building on a foundation of expedient choices made under uncertainty. Throw it away and you are building on deliberate choices made with full information.

---

## 9. SPEC ANTI-PATTERNS

This section is worth reading slowly. Most of the ways specs fail are more insidious than "nobody wrote a spec." They wrote a spec — it just had one of these problems.

### 9.1 Waterfall Specs

**The problem:** A 50-page specification document that nobody reads, written before any code exists, attempting to specify every detail upfront.

**Why it fails:** By the time implementation starts, requirements have changed. The spec is too long for anyone to review thoroughly. It creates a false sense of completeness.

**The fix:** Write living specs, not tomes. An RFC should be 2-6 pages. Update it as implementation reveals new information. A spec is a planning tool, not a contract with a client.

The 50-page spec is a psychological trap. The author spent weeks writing it and it feels authoritative. But length is not the same as quality. A 50-page spec that no one reads is less useful than a 3-page RFC that sparks real conversation. Optimize for engagement, not comprehensiveness.

### 9.2 Spec-and-Forget

**The problem:** Writing a spec, getting it approved, then never updating it as the implementation diverges.

**Why it fails:** Six months later, a new engineer reads the RFC and implements something based on the outdated design. The RFC has become actively harmful — worse than no spec at all.

**The fix:** When implementation deviates from the spec, update the spec immediately. Add a "Deviations from Original Design" section to the RFC. Mark superseded specs clearly.

This is one of the most common failures I see at growing startups. They have good spec discipline early on. The RFC process is solid. But nobody maintains the RFCs after they are approved. A year later, the RFC repository is full of documents that describe systems as they were designed, not as they exist. New engineers read them, trust them, and build on incorrect assumptions.

Assign RFC ownership. The RFC author is responsible for keeping it current through the implementation phase. After that, the tech lead is responsible for marking it superseded when the next relevant RFC is written.

### 9.3 Premature Specification

**The problem:** Specifying implementation details before you understand the problem space. Writing API contracts before you know what data the client needs. Defining message schemas before you know what events occur.

**Why it fails:** You end up specifying the wrong thing precisely. Changing a formal specification (especially one with generated code depending on it) is expensive.

**The fix:** Use the specification spectrum. Start with a one-pager, spike to validate assumptions, then formalize into an RFC and API contract only when you understand the problem well enough.

There is a meta-principle here: the right time to write a formal spec is when the cost of being wrong exceeds the cost of the spec. For a one-pager, that threshold is very low. For an OpenAPI spec with generated client code, the threshold is higher — you want to be confident about the API shape before investing in the generation toolchain. Spec at the right level of formality for your current level of understanding.

### 9.4 Missing Non-Goals

**The problem:** The spec says what you WILL build but not what you WON'T build. Stakeholders read the RFC and assume their favorite feature is included. Implementation scope creeps.

**Why it fails:** Without explicit non-goals, every reviewer adds "one more thing." The project grows 50% larger than planned.

**The fix:** Every RFC must have a non-goals section. For every goal, ask: "What related thing are we NOT doing?" State it explicitly. Examples:

- Goal: "Add search by event title" → Non-goal: "Fuzzy matching, typo tolerance"
- Goal: "Async reservation processing" → Non-goal: "Real-time seat selection UI"
- Goal: "Kafka for event streaming" → Non-goal: "Multi-region Kafka deployment"

Non-goals are not admissions of failure. They are deliberate scope decisions. Writing them down protects the team from scope creep and gives stakeholders a venue to debate priorities before implementation starts rather than during it.

### 9.5 Copy-Paste Specs

**The problem:** Using the RFC template as a form to fill out, copying boilerplate from previous RFCs without thinking about what sections are relevant.

**Why it fails:** The spec feels complete but is not useful. Sections exist because the template says they should, not because they contain meaningful content. Reviewers learn to skip sections, missing genuine concerns.

**The fix:** Every section should justify its existence. If a section does not apply, delete it. If the security section is "N/A — no security implications," ask yourself: are you sure? If yes, leave it out rather than filling in placeholder text.

Templates are starting points, not checklists. The TicketPulse RFC from Section 2.6 does not have a "Drawbacks" section labeled as such — because the drawbacks are woven throughout the alternatives and risks sections. That is fine. The template is a scaffold; the RFC is the building.

### 9.6 The Spec as CYA Document

**The problem:** Writing specs to prove you did your due diligence, not to actually clarify thinking. The spec is written defensively, covering every possible objection, so that if something goes wrong you can point to the spec and say "I documented that risk."

**Why it fails:** The spec optimizes for blame avoidance, not clarity. It becomes a legal document rather than an engineering tool. Reviewers stop engaging because the spec reads like a terms-of-service agreement.

**The fix:** Write specs for your teammates, not for an imaginary future audit. Optimize for clarity and brevity. A good spec is opinionated — it makes a clear recommendation and defends it.

You can tell a CYA spec immediately: it hedges every statement, qualifies every claim, and lists risks without recommending mitigations. It is writing designed to be technically accurate but never wrong. Real engineering specs are willing to be wrong — they commit to a direction and invite disagreement, because that is how better designs emerge.

### 9.7 Over-Specifying

**The problem:** Specifying every implementation detail — variable names, loop structures, data structure choices — leaving no room for the implementer's judgment.

**Why it fails:** The implementer (human or AI) has no room to find better solutions. The spec becomes a pseudocode document that takes as long to write as actual code. Changing any detail requires updating the spec.

**The fix:** Spec the what and the why, not the how. Specify the interface (inputs, outputs, constraints) and leave the implementation flexible. If a specific algorithm IS the point (e.g., "use Kafka's transactional producer for exactly-once semantics"), specify it. If it is an implementation detail (e.g., "use a HashMap vs. a TreeMap"), leave it out.

The over-specification problem becomes acute with AI-generated implementations. If you over-specify the implementation, you are essentially writing pseudocode and asking the AI to translate it. You lose the creative capability of the model — the ability to find an elegant solution you did not anticipate. Under-specify the mechanism; over-specify the behavior.

---

## 10. MEASURING SPEC QUALITY

A spec is a tool. Like any tool, you can measure whether it is working.

### 10.1 The Parallel Work Test

**Question:** Can frontend, backend, and QA start working simultaneously after reading this spec?

If the answer is no — if the frontend team needs to wait for the backend team to figure out the API shape — the spec is insufficient. A good spec defines interfaces clearly enough for parallel work.

This is my favorite quick test for spec quality. It is concrete. You can ask any of the three teams: "Can you start today?" If any of them say "I'm waiting on X," the spec did not do its job.

### 10.2 The New Team Member Test

**Question:** Can someone who joined the team last week understand the system from this spec alone?

If a new engineer reads your RFC and still has fundamental questions about "what are we building and why," the spec needs more context. If they have questions about implementation details, that is fine — those belong in the code.

Ch 9 discusses how senior engineers create leverage by enabling others to operate independently. A well-written spec is one of the primary mechanisms for that leverage — it encodes context that would otherwise require one-on-one meetings to transfer.

### 10.3 The Testability Test

**Question:** Are the acceptance criteria testable?

Bad acceptance criteria: "The system should be fast." Good acceptance criteria: "Event search returns results in <100ms for queries matching fewer than 1,000 events." Every acceptance criterion should be verifiable by an automated test or a specific manual check.

If you cannot write a test for an acceptance criterion, you do not actually know what you are trying to achieve. Go back and sharpen the requirement until it is testable.

### 10.4 The "Why" Test

**Question:** Does the spec explain WHY each trade-off was made?

A spec that says "We will use Kafka" is less useful than one that says "We will use Kafka because we need partition-level ordering for reservation processing and log-based replay for debugging failed consumers. We considered RabbitMQ but it does not provide ordering guarantees across consumers." The why survives longer than the what — when the next team re-evaluates this decision in 2 years, the rationale tells them whether the original constraints still apply.

The why is the most perishable information in software engineering. The code tells you what was built. The tests tell you what behavior was expected. Only the spec tells you why this approach was chosen over the alternatives. Protect it accordingly.

### 10.5 The Length Test

**Question:** Is the spec short enough that reviewers will actually read it?

An unread spec has zero value. The ideal RFC is 2-4 pages. If yours is longer, ask: can any section be cut? Can details move to an appendix? Is there a shorter way to express this?

Target lengths:
- One-pager: 1 page (obviously)
- RFC: 2-6 pages (4 is the sweet spot)
- ADR: 0.5-2 pages
- API contract: As long as needed (it is a reference, not a narrative)
- Gherkin spec: 20-50 scenarios per feature file

Ch 27 covers writing concisely at length. The core lesson applies directly here: ruthless editing is not laziness. It is respect for your reader's time. A 4-page RFC that a reviewer reads is worth infinitely more than a 12-page RFC they skim and say "LGTM."

### 10.6 The Discovery Ratio

**Metric:** Ratio of "requirements discovered during implementation" to "requirements in the spec."

If your spec captures 80% of requirements upfront and only 20% are discovered during implementation, the spec is doing its job. If 50% of requirements are discovered during implementation, the spec was too shallow — spend more time on the spec next time.

Track this informally: at the end of each feature, ask "What did we discover during implementation that should have been in the spec?" Use the answers to improve your spec process.

This retrospective question is powerful because it is specific and actionable. "The spec was good" tells you nothing. "We discovered the idempotency requirement mid-implementation because the spec didn't mention concurrent user submissions" tells you exactly what to add to your spec template.

---

## 11. SPEC-DRIVEN DEVELOPMENT IN PRACTICE

### 11.1 Google: Design Docs

Every significant project at Google starts with a design doc. The process:

1. Author writes a design doc using the internal template
2. Shares it with a mailing list of relevant stakeholders
3. Reviewers comment directly on the document (Google Docs)
4. Author addresses comments, iterates
5. Design doc is "approved" when reviewers are satisfied
6. Implementation begins

Key insight from Google's culture: design docs are not optional. Attempting to start a project without one will be blocked during code review. "Where is the design doc?" is a standard first comment on CLs (changelists) that introduce new systems.

This cultural norm is the enforcement mechanism that makes the whole system work. At Google, the social contract is clear: starting implementation without a design doc is a violation of team norms, and reviewers are expected to enforce it. The spec requirement is not a suggestion — it is a gate. If your team does not have this kind of social norm, building it is leadership work (see Ch 9). Someone has to go first: write great specs, reference them in code review, and make the connection visible between good specs and smooth implementations.

### 11.2 Stripe: Numbered RFCs

Stripe's RFC process is notable for its rigor:

- RFCs are numbered sequentially (RFC-001, RFC-002, ...)
- Each RFC has a clear status lifecycle
- The RFC author is responsible for driving it to a decision
- Review comments are threaded and must be resolved before acceptance
- Accepted RFCs are archived and searchable

Stripe's insight: RFCs are the institutional memory of the engineering organization. Years later, someone can search "why do we use protocol X?" and find the RFC that made the decision, including the alternatives that were considered and rejected.

This is especially valuable when revisiting decisions. When a new engineer argues that you should switch from Kafka to Pulsar, the RFC that explains why Kafka was chosen — including the specific requirements Pulsar would need to meet — is the starting point for that conversation. Without it, you are relitigating the decision from scratch.

### 11.3 Amazon: PR/FAQ

Amazon's unique approach: before building a new feature or product, you write a press release and FAQ as if the product already exists.

The press release forces you to:
- Articulate the customer benefit in plain language
- Define what "done" looks like
- Identify the most likely customer questions (FAQ)
- Think from the customer's perspective, not the engineer's

This is specification-by-outcome rather than specification-by-design. You specify what the customer will experience, then work backward to the technical design.

The PR/FAQ is a brilliant forcing function because it is hard to fake. You can write a vague technical RFC. You cannot write a convincing press release for a feature you do not understand. If the benefit is not clear enough to write a press release about, the feature is not well-enough understood to build.

### 11.4 Basecamp: Shape Up

Basecamp's Shape Up methodology uses "pitches" — a specification format with:

- **Problem** — the raw idea or customer request
- **Appetite** — how much time we are willing to spend (2 or 6 weeks)
- **Solution** — shaped at the right level of abstraction (not too concrete, not too abstract)
- **Rabbit holes** — known risks and complexities to avoid
- **No-gos** — things explicitly excluded from scope

The appetite is the key innovation. Instead of estimating how long a feature will take, you decide upfront how much time it is worth. If the team cannot ship within the appetite, they cut scope — they do not extend the deadline. This forces specs to be realistic about scope.

The "rabbit holes" section is similarly underrated. Documenting the known traps before implementation starts is exactly the kind of institutional knowledge transfer that prevents junior engineers from spending a week on a path that will never work. If you hit a rabbit hole during a spike, document it in the spec so no one else falls in.

### 11.5 Open Source: RFCs as Community Governance

Open source projects use RFCs as a governance mechanism:

- **Rust RFCs** — Any significant language change requires an RFC, reviewed by the core team and community. The Rust RFC repo has 3,000+ RFCs, each a permanent record of a language design decision.
- **Python PEPs** (Python Enhancement Proposals) — PEP 8 (style guide), PEP 484 (type hints), PEP 572 (walrus operator) are all specification documents that went through community review.
- **TC39 Proposals** (JavaScript/ECMAScript) — Every new JavaScript feature goes through a 5-stage process from "strawman" to "finished," with formal specifications at each stage.

The pattern: the larger and more distributed the team, the more important written specifications become. You cannot align 1,000 contributors with a Slack conversation.

This scales down, too. Even a team of five engineers benefits from written specs as the primary coordination mechanism. The alternative — verbal alignment through meetings and Slack — is fragile and undiscoverable. It disappears the moment the conversation ends. Written specs persist.

### 11.6 TicketPulse Recommendation

For TicketPulse (a team of ~10 engineers, 3 backend, 3 frontend, 2 infrastructure, 1 QA, 1 tech lead):

- **One-pagers:** Required for any work estimated at >3 days
- **RFCs:** Required for any work that changes APIs, data models, or infrastructure. Use the template from Section 2.5. Review window: 48 hours, 2 reviewers.
- **ADRs:** Required for technology choices and architecture patterns. Store in `docs/adr/`. One ADR per decision.
- **API contracts:** OpenAPI for all REST endpoints, AsyncAPI for Kafka topics, Protobuf for the gRPC InventoryService. Contracts must be approved before implementation starts.
- **Gherkin specs:** Required for the reservation flow, payment flow, and refund flow. Optional for CRUD endpoints.
- **CLAUDE.md:** Maintained by the tech lead. Updated when conventions change. Every AI-assisted development session should reference it.

This gives the team structure without bureaucracy. The total spec overhead is ~20% of development time, saving ~40% in avoided rework, parallel work enablement, and reduced review cycles.

---

## 12. BUILDING A SPEC CULTURE

Culture change is the hardest part of spec-driven development. The tools are straightforward; the habits are not. This section is about the human side of building a team that writes great specs consistently.

### 12.1 Start Small

Do not mandate specs for everything on day one. Start with a single rule:

> Any work that takes more than 3 days requires a one-page design doc before implementation begins.

This is low friction (a one-pager takes 30 minutes), demonstrates immediate value (stakeholder alignment, caught misunderstandings), and builds the habit. After a month, the team will ask for more structure because they have seen the benefit.

The most important thing is to start. Perfect spec culture is built incrementally. You do not need to implement everything in this chapter on day one. You need one small rule that gets enforced consistently. A single enforced rule produces more spec discipline than ten unenforced policies.

### 12.2 Templates Reduce Friction

Provide 2-3 templates, not 10. More templates means more decisions about which to use, which means more friction, which means people skip the spec entirely.

Recommended templates:

1. **One-pager** — Problem, Goals, Non-Goals, Proposed Approach (1 page)
2. **RFC** — Full template from Section 2.5 (for significant changes)
3. **ADR** — Nygard format from Section 3.2 (for decisions)

Store templates in the repo at `docs/templates/`. When someone needs to write a spec, they copy the template. No hunting for links, no asking "where is the template?"

Friction is the enemy of good habits. Every extra step between "I should write a spec" and "I am writing a spec" increases the probability that the spec never gets written. Reduce friction relentlessly.

### 12.3 Lightweight Review Process

Spec review should be fast and focused:

- **2 reviewers.** More than 2 creates diffusion of responsibility.
- **48-hour window.** If reviewers do not respond in 48 hours, the author can proceed. This prevents specs from blocking work indefinitely.
- **Async by default.** Comments on the document, not meetings. Schedule a 30-minute sync only if there is genuine disagreement.
- **Decision authority.** If reviewers disagree, the tech lead makes the call. Consensus is ideal but not required.

The 48-hour rule is critical. Nothing kills spec culture faster than specs that sit in review for a week and block work. Make the review window explicit and make it short. If a reviewer cannot engage in 48 hours, the author can proceed — and the reviewer has acknowledged that trade-off by not responding.

### 12.4 Spec Review Is Not Code Review

Spec review requires different skills than code review:

| Spec Review | Code Review |
|---|---|
| "Is this the right approach?" | "Is this the right implementation?" |
| "Are we solving the right problem?" | "Does this code work correctly?" |
| "What are we missing?" | "What are the bugs?" |
| "Will this scale?" | "Is this performant?" |
| "Is this aligned with our strategy?" | "Does this follow our conventions?" |

Spec reviewers should be senior engineers, tech leads, or architects — people who can evaluate strategic fit. Code reviewers should be engineers familiar with the codebase — people who can evaluate correctness.

A common failure mode is assigning spec reviews to the same engineers who do code reviews, with the same mental frame. Code review instincts ("this line could be cleaner," "this should be a named constant") do not transfer to spec review. Spec review needs system-thinking instincts: zooming out, questioning assumptions, spotting missing cases. Coach your reviewers explicitly on the difference.

### 12.5 Document Decisions, Not Just Proposals

Many teams write RFCs but not ADRs. They capture proposals but not the decisions made during implementation. Six months later, someone asks "why do we use Avro for Kafka messages?" and nobody remembers.

Make ADR writing a habit:

- At every sprint retrospective, ask: "Were any architectural decisions made this sprint that we should document?"
- When a code reviewer asks "why did you choose X over Y?" — the answer should become an ADR.
- When someone says "we should document that" in a meeting — that is an ADR.

The retrospective question is a low-effort, high-yield practice. Five minutes at the end of each sprint produces a steady stream of ADRs that collectively build an accurate picture of how the system evolved. After a year, that ADR archive is one of the most valuable assets the team has.

### 12.6 Celebrate Good Specs

Incentives shape behavior. If your team only celebrates shipped features, nobody will invest in specs. Create recognition for good specification work:

- **Monthly "Best RFC" recognition** — highlight an RFC that was particularly clear, thorough, or well-structured
- **Reference RFCs** — when a new engineer writes their first RFC, point them to 2-3 exemplary RFCs as models
- **Postmortem credit** — when an incident is avoided because a spec caught a risk early, mention it in the next team meeting

The postmortem credit is the most powerful. Nothing makes the case for spec investment more viscerally than a story that ends with "and we almost shipped this, but the RFC reviewer caught it." Make those stories visible. They are the social proof that spec discipline pays off.

### 12.7 Specs as Onboarding

New engineers should read recent RFCs as part of onboarding. A well-written RFC explains not just what the system does, but why it was built that way. This is more valuable than reading the code, because code shows you HOW but not WHY.

Recommended onboarding reading list:
1. `CLAUDE.md` — understand project conventions
2. The 3 most recent RFCs — understand current direction
3. All ADRs — understand historical decisions
4. The OpenAPI spec — understand the API surface

An engineer who reads these four sources will be productive faster than one who spends the same time reading source code.

This is a concrete, measurable claim. Track it. Ask new engineers after their first month: "What most helped you get up to speed?" If teams with strong spec cultures report faster onboarding, you have evidence for the investment. I have consistently seen that teams with good ADR and RFC coverage onboard engineers 20-30% faster — not because the specs replace learning, but because they eliminate the dead ends that slow learning.

---

## Summary: The Spec-Driven Checklist

Use this checklist when starting any significant feature:

| Step | Artifact | Time | Done? |
|------|----------|------|-------|
| Problem definition | One-pager | 30-60 min | |
| Stakeholder alignment | Meeting notes / Slack thread | 30 min | |
| Technical design | RFC | 2-8 hours | |
| API contract | OpenAPI / AsyncAPI / Protobuf | 2-4 hours | |
| Acceptance criteria | Gherkin / test specs | 2-4 hours | |
| Implementation | Code | Variable | |
| Decision records | ADRs | 15-30 min each | |
| Final review | Diff against spec | 1-2 hours | |

The total spec investment is 7-20 hours for a feature that takes 2-6 weeks to build. This is 5-15% of total development time. The return — in avoided rework, parallel work, reduced review cycles, and institutional knowledge — is 3-5x the investment.

---

**Key Takeaway:** In the AI era, the spec is the product and code is the build artifact. Engineers who master specification writing — who can precisely capture intent, constraints, and acceptance criteria in a format that humans can review and machines can execute — are the most valuable engineers on any team. This is not a soft skill. It is the core technical skill of the next decade. Write the spec first. Write it precisely. Let the implementation — human or AI — follow from it. The spec is where you do the hard thinking, before the code makes it expensive to change your mind.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L2-M59a: Spec-Driven Development](../course/modules/loop-2/L2-M59a-spec-driven-development.md)** — Write a full OpenAPI contract for a TicketPulse endpoint before touching implementation code, then validate against it with Spectral
- **[L3-M86a: AI-Native Spec-Driven Development](../course/modules/loop-3/L3-M86a-ai-native-spec-driven-development.md)** — Use specs as the interface between human intent and AI implementation, closing the loop with automated acceptance tests
- **[L3-M77: Architecture Decision Records](../course/modules/loop-3/L3-M77-architecture-decision-records.md)** — Document the non-obvious decisions in TicketPulse's architecture in a format that survives team turnover

### Quick Exercises

1. **Write an OpenAPI spec for one of your existing endpoints and validate it with Spectral** — describe the request, response, and error cases. Run it through Spectral with the default ruleset and fix every warning before touching the implementation.
2. **Write a Gherkin scenario for your most critical user flow** — describe it in Given/When/Then without writing any test code. Review it with a non-engineer and see if they can understand and verify the behaviour.
3. **Draft an RFC for your next feature before writing any code** — spend two hours on the problem statement, constraints, alternatives considered, and your proposed approach. Share it for review before you open your editor.

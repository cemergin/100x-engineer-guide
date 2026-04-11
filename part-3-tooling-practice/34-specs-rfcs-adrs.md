<!--
  CHAPTER: 34
  TITLE: Specs, RFCs & Architecture Decision Records
  PART: III — Tooling & Practice
  PREREQS: Ch 27 (Technical Writing), Ch 25 (API Design), Ch 9 (Engineering Leadership)
  KEY_TOPICS: Specification-first development, RFCs, design documents, Architecture Decision Records, ADR templates, spec-first thesis
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 34: Specs, RFCs & Architecture Decision Records

> **Part III — Tooling & Practice** | Prerequisites: Ch 27 (Technical Writing), Ch 25 (API Design), Ch 9 (Engineering Leadership) | Difficulty: Intermediate → Advanced

Here is the most important thing you will learn in this entire guide: **the spec is where you do the hard thinking — before the code makes it expensive to change your mind.**

Specifications are the most leveraged artifact an engineer can produce. A single well-written spec aligns an entire team, prevents weeks of rework, enables parallel development, and — in the AI era — serves as the primary interface between human intent and machine execution. Engineers who master this skill are the ones who multiply teams, not just themselves. This chapter covers the foundational spec formats — from lightweight RFCs to Architecture Decision Records — and shows you why the spec-first approach is the highest-leverage habit you can build.

### In This Chapter
- The Spec-First Thesis
- The RFC and Design Document
- Architecture Decision Records (ADRs)

### Related Chapters
- Ch 34b (Contract-First API & Executable Specs) — OpenAPI, AsyncAPI, Protobuf, BDD/Gherkin
- Ch 34c (AI-Native Specs & Spec Culture) — CLAUDE.md as spec, AI workflows, anti-patterns, measuring quality
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

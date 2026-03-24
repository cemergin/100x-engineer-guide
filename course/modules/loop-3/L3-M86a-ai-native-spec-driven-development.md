# L3-M86a: AI-Native Spec-Driven Development

> **Loop 3 (Mastery)** | Section 3D: AI & Intelligence | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M59 (Technical Writing), L3-M77 (Architecture Decision Records), L3-M86 (AI-Powered Engineering)
>
> **Source:** Chapter 34 of the 100x Engineer Guide

## What You'll Learn

- How to write a CLAUDE.md that turns your codebase into a self-documenting system for AI agents
- The difference between a spec a human can follow and a spec an AI agent can execute from
- A complete workflow from design doc to AI implementation to human review
- Why prompt engineering and specification writing are converging into the same discipline
- How to choose and layer specification formats (OpenAPI, Gherkin, AsyncAPI) for maximum AI leverage

## Why This Matters

You have spent the entire course learning to build TicketPulse -- designing systems, making architectural decisions, writing tests, shipping features. You have also used AI tools to accelerate your work. But there is an inflection point happening right now, and it changes the job description.

The inflection point is this: AI agents are no longer autocomplete. They can read a specification and produce a working implementation. Not a sketch. Not boilerplate. A working implementation with tests, error handling, and adherence to your project's patterns -- *if* the specification is good enough.

This changes what "engineering skill" means. The bottleneck is no longer typing code. The bottleneck is the quality of the specification you hand to the agent. Engineers who write precise, unambiguous, testable specs will get 10x more leverage from AI than engineers who write vague requirements and then spend hours fixing the output.

The spec is the product. The code is the artifact.

> 💡 **Insight**: "The best prompt is a spec. The best spec is a prompt. Once you internalize this, the entire AI-assisted development workflow clicks into place."

---

## Prereq Check

Before starting this module, confirm you can:

```
✅ Write an ADR with context, decision, consequences, and reversal conditions (L3-M77)
✅ Use AI pair programming tools to implement a feature (L3-M86)
✅ Write clear technical documentation that another engineer could follow (L2-M59)
✅ Describe TicketPulse's architecture: services, event bus, databases, API gateway
```

If any of these feel shaky, revisit the prerequisite module before continuing.

---

## Part 1: CLAUDE.md as a Behavioral Specification

### What Is CLAUDE.md?

CLAUDE.md is a file you place at the root of your repository. It tells AI agents how to work in your codebase. Not what your code does -- how to work within it. Think of it as the document you would give a senior engineer on their first day, compressed into something an AI agent can parse and follow.

It is not a README. A README tells users how to run your project. CLAUDE.md tells an AI agent how to contribute to your project without breaking anything.

The insight: CLAUDE.md is an ADR + style guide + onboarding doc compressed into an AI-readable format. Everything you would explain to a new teammate in their first week -- your conventions, your constraints, your architectural decisions, your testing philosophy -- goes into this file.

### TicketPulse's CLAUDE.md

Here is a complete CLAUDE.md for TicketPulse. Study it carefully -- every section exists for a reason.

```markdown
# CLAUDE.md -- TicketPulse

## Project Overview
TicketPulse is a concert ticketing platform. Users browse events, purchase
tickets, receive e-tickets, and get AI-powered recommendations. The system
handles high-concurrency scenarios (ticket rushes) and processes payments.

## Architecture
- **Monorepo**: All services live in /services, shared libs in /packages
- **Services**: api-gateway (Express), ticket-service, payment-service,
  user-service, recommendation-service, notification-service
- **Event bus**: Apache Kafka. All inter-service communication is async
  via events. No direct service-to-service HTTP calls except through
  the API gateway.
- **Databases**: PostgreSQL (primary), Redis (caching + session),
  Elasticsearch (search + recommendations)
- **Infrastructure**: Docker Compose for local dev, Kubernetes for prod
- **CI/CD**: GitHub Actions. All PRs require passing tests + review.

## Code Conventions
- **Language**: TypeScript everywhere. Strict mode enabled.
- **No `any`**: Use `unknown` and narrow with type guards. The only
  exception is third-party library type gaps, which must be wrapped
  in a typed adapter in /packages/adapters/.
- **Prefer composition over inheritance**: No class hierarchies deeper
  than one level. Use interfaces and factory functions.
- **Error handling**: All services use the Result pattern from
  /packages/shared/result.ts. Never throw exceptions for business logic.
  Exceptions are for programmer errors only.
- **Naming**: Services use kebab-case directories. Files use camelCase.
  Types use PascalCase. Constants use UPPER_SNAKE_CASE.

## Kafka Event Conventions
- Topic naming: `ticketpulse.<service>.<entity>.<event>`
  Example: `ticketpulse.ticket.order.completed`
- All events include: `eventId` (UUID), `timestamp` (ISO 8601),
  `version` (semver), `correlationId`, `payload`
- Events are immutable. Never modify a published event schema.
  Create a new version instead.
- Consumer groups follow: `<consuming-service>-<topic>-consumer`

## Testing Requirements
- All new features require integration tests. Unit tests alone are
  not sufficient for service-level features.
- Test files live next to source: `foo.ts` -> `foo.test.ts`
- Integration tests use testcontainers for Kafka and PostgreSQL.
- Minimum coverage for new code: 80% line, 70% branch.
- E2E tests for any user-facing flow change go in /tests/e2e/.

## Deployment Constraints
- Zero-downtime deployments only. Blue-green required for all services.
- Database migrations must be backward-compatible (no column drops
  without a two-release deprecation cycle).
- Feature flags via /packages/flags/ for any user-facing change.
- Rollback plan required in the PR description for any infra change.

## Architecture Decisions
- See /docs/adr/ for all ADRs. Key ones:
  - ADR-001: Kafka over SQS for event streaming
  - ADR-002: 3-5 microservices, not monolith or fine-grained
  - ADR-003: PostgreSQL as primary data store
  - ADR-004: CQRS for event queries, not user queries
  - ADR-005: TypeScript for all API services

## Common Patterns
- **New API endpoint**: Follow the pattern in services/api-gateway/src/routes/
  Every route has: validation (zod), handler, error mapping, response type.
- **New Kafka consumer**: Follow services/ticket-service/src/consumers/
  Every consumer has: schema validation, idempotency check, dead letter handling.
- **New database migration**: Use /packages/db/migrations/ with sequential
  numbering. Test both up and down migrations.
- **New service**: Copy the template in /services/_template/. It includes
  health checks, graceful shutdown, structured logging, and metrics.

## What NOT to Do
- Do not add npm dependencies without checking /packages/ for existing
  solutions first. We have wrappers for HTTP, logging, and validation.
- Do not use console.log. Use the structured logger from /packages/logger/.
- Do not write synchronous service-to-service calls. Use Kafka events.
- Do not skip the PR template. It exists for a reason.
```

### Why Each Section Matters

```
SECTION                  → WHAT IT PREVENTS
─────────────────────────────────────────────────────────
Project Overview         → AI inventing wrong assumptions about the domain
Architecture             → AI creating files in wrong locations, wrong patterns
Code Conventions         → AI using `any`, throwing exceptions, wrong naming
Kafka Conventions        → AI inventing topic names, missing event fields
Testing Requirements     → AI skipping integration tests, wrong test locations
Deployment Constraints   → AI generating breaking migrations, no feature flags
Architecture Decisions   → AI re-solving problems that already have ADRs
Common Patterns          → AI inventing new patterns instead of following yours
What NOT to Do           → AI introducing dependencies, console.log, sync calls
```

A good CLAUDE.md does not describe every file. It describes the principles and patterns. An AI agent that understands the principles will make correct decisions about files it has never seen.

---

## Part 2: Writing Specs AI Agents Can Execute

### Human-Readable vs AI-Executable

A human-readable spec says: *"Add venue capacity tracking so we know when venues are getting full."*

An AI-executable spec says exactly what to build, what the inputs and outputs look like, where the code should go, what patterns to follow, and how to verify correctness.

The difference is not length. It is precision.

### Five Principles of AI-Executable Specs

**Principle 1: Be Precise About Inputs and Outputs**

```
❌ VAGUE: "The API should return venue capacity information"

✅ PRECISE:
  GET /api/v1/venues/:venueId/capacity

  Response 200:
  {
    "venueId": string (UUID),
    "totalCapacity": number (integer, > 0),
    "currentOccupancy": number (integer, >= 0),
    "availableCapacity": number (integer, >= 0),
    "utilizationPercent": number (float, 0.0-100.0, 1 decimal),
    "status": "available" | "limited" | "sold_out",
    "lastUpdated": string (ISO 8601)
  }

  Status thresholds:
  - "available": utilizationPercent < 80
  - "limited": utilizationPercent >= 80 AND < 100
  - "sold_out": utilizationPercent === 100
```

Types, not descriptions. Exact field names, not vague concepts.

**Principle 2: Include Acceptance Criteria as Testable Assertions**

```
Acceptance Criteria:
- GIVEN a venue with capacity 10000 and 7500 tickets sold
  WHEN GET /api/v1/venues/:id/capacity
  THEN availableCapacity = 2500 AND status = "available"

- GIVEN a venue with capacity 10000 and 9500 tickets sold
  WHEN GET /api/v1/venues/:id/capacity
  THEN availableCapacity = 500 AND status = "limited"

- GIVEN a venue with capacity 10000 and 10000 tickets sold
  WHEN GET /api/v1/venues/:id/capacity
  THEN availableCapacity = 0 AND status = "sold_out"

- GIVEN a venue that does not exist
  WHEN GET /api/v1/venues/:id/capacity
  THEN 404 with error code "VENUE_NOT_FOUND"
```

Every acceptance criterion is a test case. An AI agent can generate the test file directly from these.

**Principle 3: Specify Constraints and Non-Goals Explicitly**

```
Constraints:
- Capacity data must be eventually consistent (max 5s stale)
- Do not lock the tickets table for capacity reads. Use a
  materialized counter in Redis.
- Do not add a new database table. Add columns to the existing
  venues table.

Non-Goals:
- Real-time WebSocket updates for capacity (future feature)
- Historical capacity tracking over time (future feature)
- Per-section capacity (treat venue as a single pool)
```

Without non-goals, the AI agent will over-build. It will add WebSocket support because it seems like a good idea. Non-goals are a fence around the work.

**Principle 4: Provide Examples of Expected Behavior**

```
Example Scenarios:

1. Normal purchase flow:
   - Venue starts: capacity=10000, occupancy=0
   - User buys 2 tickets → occupancy=2, available=9998
   - Kafka event: ticketpulse.ticket.order.completed
   - Capacity consumer updates Redis counter

2. Refund flow:
   - Venue: capacity=10000, occupancy=9000
   - User refunds 1 ticket → occupancy=8999, available=1001
   - Kafka event: ticketpulse.ticket.order.refunded
   - Capacity consumer decrements Redis counter

3. Race condition:
   - Two purchases complete simultaneously
   - Redis INCRBY is atomic, both increments apply
   - No lost updates
```

**Principle 5: Reference Existing Code Patterns**

```
Implementation Notes:
- API route: follow pattern in services/api-gateway/src/routes/events.ts
- Kafka consumer: follow pattern in services/ticket-service/src/consumers/orderConsumer.ts
- Redis counter: follow pattern in packages/cache/src/counter.ts
- Add zod schema to packages/shared/src/schemas/venue.ts
- Integration test: follow pattern in services/api-gateway/src/routes/__tests__/events.integration.test.ts
```

This is crucial. Without it, the AI agent invents its own patterns. With it, the AI agent produces code that looks like it was written by a team member.

### Complete Example: TicketPulse Venue Capacity Tracking Spec

```markdown
# Feature Spec: Venue Capacity Tracking

## Summary
Add real-time capacity tracking to venues so the API can report
available tickets, utilization percentage, and sell-out status.

## Data Model Changes
Add to existing `venues` table (services/ticket-service/src/db/):
- total_capacity: INTEGER NOT NULL DEFAULT 0
- Migration: /packages/db/migrations/024_add_venue_capacity.sql

Redis key for live counter:
- Key: `venue:capacity:{venueId}` (type: hash)
- Fields: `occupancy` (integer)
- TTL: none (persistent, rebuilt on service restart from DB)

## API Changes
GET /api/v1/venues/:venueId/capacity
- Auth: public (no token required)
- Rate limit: 100 req/min per IP
- Response: see schema above
- Cache: Redis, 5s TTL on computed response

## Kafka Events
Consume:
- `ticketpulse.ticket.order.completed` → increment occupancy
- `ticketpulse.ticket.order.refunded` → decrement occupancy
- `ticketpulse.ticket.order.cancelled` → decrement occupancy

Publish:
- `ticketpulse.venue.capacity.status_changed`
  Payload: { venueId, previousStatus, newStatus, timestamp }
  Trigger: when status crosses a threshold boundary

## Test Scenarios
1. Capacity calculation is correct after purchases and refunds
2. Status transitions at 80% and 100% thresholds
3. Concurrent purchases do not cause lost updates (Redis atomicity)
4. Unknown venue returns 404
5. Capacity never goes below 0 (refund on empty venue)
6. Kafka consumer is idempotent (replaying an event does not
   double-count)
7. Redis counter rebuilds correctly from DB on cold start

## Edge Cases
- Venue capacity is updated (venue expanded) mid-sales period
- Bulk purchase (100 tickets at once) in a single order
- Refund for an event that was already deleted
- Redis is temporarily unavailable (fallback to DB query)

## Files to Create/Modify
- CREATE: services/api-gateway/src/routes/venueCapacity.ts
- CREATE: services/ticket-service/src/consumers/capacityConsumer.ts
- MODIFY: packages/shared/src/schemas/venue.ts (add capacity schema)
- CREATE: packages/db/migrations/024_add_venue_capacity.sql
- CREATE: services/api-gateway/src/routes/__tests__/venueCapacity.integration.test.ts
- CREATE: services/ticket-service/src/consumers/__tests__/capacityConsumer.test.ts
```

An AI agent given this spec, plus the CLAUDE.md, can produce a complete implementation. Not because the spec tells it every line to write, but because the spec tells it exactly what to build and the CLAUDE.md tells it exactly how to build it.

---

## Part 3: The Design Doc to AI Implementation Workflow

### The Modern Workflow

The workflow that gets the best results from AI agents follows a specific sequence. Each step has a different author and a different purpose.

```
STEP  AUTHOR   TIME        ARTIFACT
──────────────────────────────────────────────────────
1     Human    30-60 min   RFC / Design doc
2     Human    One-time    CLAUDE.md (project context)
3     Human    30-45 min   Feature spec with acceptance criteria
4     AI       Minutes     Code implementation
5     Human    20-30 min   Review diff against spec
6     AI       Minutes     Tests from acceptance criteria
7     Human    10-15 min   Verify tests match intent
```

Notice the rhythm: human defines, AI executes, human verifies. The human never stops thinking. The human stops typing boilerplate.

### Step-by-Step Walkthrough: TicketPulse Waitlist Notification Preferences

Let us walk through the complete workflow for a real feature.

**Step 1: Human writes the RFC (30 minutes)**

The RFC is a thinking document. It captures the problem, explores alternatives, and proposes a solution. It is not for the AI -- it is for you and your team.

```
RFC: Waitlist Notification Preferences

Problem:
Users on the waitlist for sold-out events currently receive
notifications via email only. User research shows 40% of waitlist
notifications are missed because users do not check email quickly
enough, and the 15-minute purchase window expires.

Proposed Solution:
Allow users to configure notification preferences per waitlist entry:
email, SMS, push notification, or any combination. When a ticket
becomes available, notify through all selected channels simultaneously.

Alternatives Considered:
1. Always notify via all channels → too aggressive, users complain
2. Global notification preferences → users want different settings
   for different events (a casual show vs their favorite artist)
3. Extend the purchase window → does not solve the core problem
   of missed notifications

Decision: Per-waitlist-entry notification preferences.
```

**Step 2: CLAUDE.md exists (already done, one-time setup)**

If your CLAUDE.md is up to date, you skip this step. If the feature introduces new domain concepts (like "notification preferences"), consider adding a line to the Project Overview section.

**Step 3: Human writes the feature spec (30 minutes)**

Now translate the RFC into an AI-executable spec using the five principles from Part 2. This is where precision matters. The spec should include the API contract, data model changes, Kafka events, acceptance criteria, edge cases, and file references.

**Step 4: AI agent implements from spec**

You hand the spec to the AI agent along with the CLAUDE.md. The agent reads both, understands the project's conventions, and produces code that follows existing patterns.

```
Prompt to AI agent:

"Implement the feature described in docs/specs/waitlist-notifications.md.
Follow the conventions in CLAUDE.md. Reference existing patterns for
Kafka consumers and API routes. Create all files listed in the spec.
Do not add any functionality not described in the spec."
```

The last sentence is critical. Without it, the AI agent will add "helpful" features that were not requested.

**Step 5: Human reviews diff against spec**

This is not a normal code review. You are reviewing the AI's output against the spec you wrote. Your checklist:

```
REVIEW CHECKLIST (AI-generated code)
─────────────────────────────────────
□ Does every acceptance criterion have a corresponding implementation?
□ Does the code follow the patterns referenced in the spec?
□ Are the Kafka event names and schemas correct?
□ Are the API response types exactly as specified?
□ Did the AI add anything NOT in the spec? (Remove it)
□ Did the AI skip any edge cases? (Flag them)
□ Are there any hardcoded values that should be configurable?
□ Does the error handling follow the Result pattern?
```

**Step 6: AI writes tests from acceptance criteria**

```
Prompt to AI agent:

"Write integration tests for the waitlist notification preferences
feature. Use the acceptance criteria in docs/specs/waitlist-notifications.md
as test cases. Follow the test patterns in
services/api-gateway/src/routes/__tests__/. Use testcontainers for
Kafka and PostgreSQL."
```

**Step 7: Human verifies tests match intent**

Read every test. Does it actually test what the acceptance criterion says? AI-generated tests sometimes test the implementation rather than the behavior. The test should assert on observable outcomes, not internal state.

### When This Workflow Works Beautifully

```
WORKS WELL:
- Well-defined CRUD features with clear boundaries
- API endpoints with precise contracts
- Kafka consumers with known event schemas
- Database migrations with specific column definitions
- Features that follow existing patterns in the codebase
- Test generation from Gherkin-style acceptance criteria
```

### When This Workflow Breaks Down

```
BREAKS DOWN:
- Ambiguous requirements ("make the recommendations better")
- Novel algorithms (new ranking system, custom ML pipeline)
- Cross-cutting concerns (observability, security, performance)
- Architecture decisions (the AI should not choose your architecture)
- Subtle business logic with many unstated assumptions
- Performance optimization (the AI does not know your traffic patterns)
```

The pattern: AI agents excel at the *what* when you are precise about it. They struggle with the *why* and the *how much*.

> 💡 **Insight**: "The workflow does not replace engineering judgment. It relocates it. Instead of spending judgment on writing code, you spend it on writing specs and reviewing output. The total judgment required is the same. The total typing required drops dramatically."

---

## Part 4: Prompt Engineering IS Specification Writing

### The Convergence

If you have been reading this module carefully, you have already noticed something: a good AI prompt and a good specification are the same document. They have the same structure, the same requirements for precision, and the same failure modes when they are vague.

This is not a coincidence. A specification is an instruction to an implementer. A prompt is an instruction to an implementer. The only difference is whether the implementer is human or AI.

### The Anatomy of a Spec-Quality Prompt

Every effective prompt for code generation contains five elements:

```
1. CONTEXT     → What project, what existing patterns, what constraints
2. REQUIREMENT → What to build, with precise inputs and outputs
3. CONSTRAINTS → What NOT to do, performance budgets, scope limits
4. EXAMPLES    → Expected behavior as input/output pairs
5. VERIFICATION → How to know the implementation is correct
```

This is not a prompting trick. This is the structure of a good specification in any format.

### Side-by-Side: Vague Prompt vs Spec-Quality Prompt

**Vague prompt:**

```
Add a pricing endpoint to TicketPulse that returns ticket prices
for an event. Include dynamic pricing based on demand.
```

What the AI produces: a generic pricing endpoint with invented business logic, arbitrary pricing rules, new database tables you did not ask for, and no tests. You spend two hours fixing it.

**Spec-quality prompt:**

```
Add a pricing endpoint to TicketPulse.

Context:
- Project conventions are in CLAUDE.md at the repo root
- Follow the route pattern in services/api-gateway/src/routes/events.ts
- Use the Result pattern from packages/shared/result.ts

Requirement:
GET /api/v1/events/:eventId/pricing
Response 200:
{
  "eventId": string (UUID),
  "basePrice": number (cents, integer),
  "currentPrice": number (cents, integer),
  "demandMultiplier": number (float, 1.0-3.0),
  "tier": "early_bird" | "standard" | "high_demand" | "last_minute",
  "currency": "USD"
}

Pricing rules:
- early_bird: > 30 days before event, multiplier = 0.8
- standard: 7-30 days before event, multiplier = 1.0
- high_demand: < 7 days AND utilization > 80%, multiplier = 1.5
- last_minute: < 24 hours before event, multiplier = 2.0
- demandMultiplier is capped at 3.0 regardless of tier

Constraints:
- Do NOT create a new database table. Pricing is computed from
  existing event and venue data.
- Do NOT implement price history or price change notifications.
- Prices are always in cents (integer) to avoid floating point issues.

Examples:
- Event in 45 days, base price 5000 → currentPrice: 4000, tier: early_bird
- Event in 14 days, base price 5000 → currentPrice: 5000, tier: standard
- Event in 3 days, 90% sold, base price 5000 → currentPrice: 7500, tier: high_demand
- Event in 12 hours, base price 5000 → currentPrice: 10000, tier: last_minute

Verification:
- All examples above should pass as test cases
- Unknown event returns 404 with error code EVENT_NOT_FOUND
- Past events return 400 with error code EVENT_ALREADY_OCCURRED
- Response time < 50ms (computed, no external calls)
```

The spec-quality prompt produces code you can ship with minor adjustments. The vague prompt produces code you have to rewrite.

### The Dramatic Difference

```
VAGUE PROMPT OUTCOMES           SPEC-QUALITY PROMPT OUTCOMES
────────────────────────        ────────────────────────────
AI invents business rules       AI implements YOUR rules
AI creates new patterns         AI follows existing patterns
AI over-builds (3x scope)      AI builds exactly what you asked
Review takes 2 hours            Review takes 20 minutes
50% of code gets rewritten      10% of code needs adjustment
No tests generated              Tests generated from examples
```

The time investment shifts. You spend 30 minutes writing the prompt/spec instead of 5 minutes. But you save 2 hours on review and rewriting. The net savings grows with feature complexity.

---

## Part 5: Specification Formats for the AI Era

### Which Formats Work Best With AI Agents?

Not all specification formats are equally useful for AI-assisted development. The key factors are: can the AI parse it unambiguously, and can the AI generate working code from it?

| Format | AI Comprehension | Executability | Human Readability |
|--------|-----------------|---------------|-------------------|
| **CLAUDE.md** | Excellent | Behavioral guidance | Good |
| **OpenAPI (YAML)** | Excellent | Full API codegen | Good |
| **Gherkin / BDD** | Excellent | Test generation | Excellent |
| **RFC (prose)** | Good | Partial implementation | Excellent |
| **AsyncAPI** | Excellent | Full event codegen | Good |
| **Protobuf** | Excellent | Full type/client codegen | Moderate |
| **JSON Schema** | Excellent | Validation codegen | Moderate |
| **Diagrams / ASCII art** | Poor | None | Excellent |
| **Whiteboard photos** | Very poor | None | Context-dependent |

The pattern: structured, machine-parseable formats give AI agents the most leverage. Prose and visual formats are great for human understanding but lose information when an AI agent tries to implement from them.

### The Spec Stack

No single format captures everything an AI agent needs. The solution is a layered spec stack where each format serves a different purpose at a different stage of development.

```
THE SPEC STACK
══════════════════════════════════════════════════════

Layer 1: CLAUDE.md (Project Level)
  Purpose: "How we work here"
  Scope: Entire project, rarely changes
  Feeds: Every AI interaction with the codebase

Layer 2: RFC / Design Doc (Feature Level)
  Purpose: "Why we are building this and what we considered"
  Scope: One feature or architectural change
  Feeds: Human understanding, team alignment

Layer 3: OpenAPI / AsyncAPI (Contract Level)
  Purpose: "The exact API surface and event schemas"
  Scope: Endpoints, request/response types, events
  Feeds: Code generation, client generation, mock servers

Layer 4: Gherkin / BDD Scenarios (Behavior Level)
  Purpose: "How the system should behave in specific situations"
  Scope: User-facing behaviors and edge cases
  Feeds: Test generation, acceptance testing

══════════════════════════════════════════════════════
```

Each layer feeds a different stage of AI-assisted development:

```
LAYER          → AI STAGE
──────────────────────────────────
CLAUDE.md      → Every code generation session (context)
RFC            → Human planning (AI reads for background)
OpenAPI        → API route generation, client SDK generation
AsyncAPI       → Kafka consumer/producer generation
Gherkin        → Integration and E2E test generation
```

### How the Layers Work Together

When you want to add a feature to TicketPulse, you produce artifacts at multiple layers:

1. **Update CLAUDE.md** if the feature introduces new domain concepts
2. **Write the RFC** to capture the problem, solution, and alternatives
3. **Write the OpenAPI spec** for any new or modified endpoints
4. **Write AsyncAPI spec** for any new Kafka events
5. **Write Gherkin scenarios** for all acceptance criteria

Then you hand the AI agent the relevant layers for each task:
- Generating route handlers? CLAUDE.md + OpenAPI spec
- Generating Kafka consumers? CLAUDE.md + AsyncAPI spec
- Generating tests? CLAUDE.md + Gherkin scenarios
- Generating the whole feature? All layers

The AI agent does not need to see the RFC for code generation. The RFC is for humans. But the AI might read the RFC for context when something is ambiguous.

---

## Design Exercise: The Smart Pricing Spec Stack (30 minutes)

TicketPulse wants to add smart ticket pricing: dynamic prices that adjust based on demand, time to event, artist popularity, and historical sales data. This is a significant feature that touches multiple services.

Your task: write the complete spec stack for this feature.

### Part A: Update CLAUDE.md (5 minutes)

Add a section to TicketPulse's CLAUDE.md that covers the pricing domain:

```
Think about:
- What new domain concepts does pricing introduce?
- What pricing-specific conventions should the AI follow?
- What existing services does pricing interact with?
- What are the pricing-specific constraints (e.g., prices in cents)?
```

### Part B: Write the RFC (10 minutes)

Write a concise RFC covering:

```
- Problem: Why static pricing leaves money on the table and
  frustrates users who miss early deals
- Proposed solution: Demand-based dynamic pricing with four tiers
  and configurable multiplier caps
- Alternatives considered: (at least two, with reasons for rejection)
- Risks: Price gouging perception, regulatory concerns, complexity
- Reversal condition: Under what circumstances would you roll this back?
```

### Part C: Write the OpenAPI Spec (10 minutes)

Define the pricing endpoints:

```
Write OpenAPI (YAML or structured markdown) for:
- GET /api/v1/events/:eventId/pricing (current price)
- GET /api/v1/events/:eventId/pricing/history (price over time)
- PUT /api/v1/admin/events/:eventId/pricing/config (set pricing rules)

Include: request/response schemas, status codes, error responses
```

### Part D: Write Gherkin Scenarios (5 minutes)

Write at least five Gherkin scenarios:

```
Cover:
- Base case: standard pricing calculation
- Tier transitions: what happens at 80% utilization
- Edge case: event in the past
- Admin case: updating pricing configuration
- Constraint: price never exceeds 3x base price
```

### Evaluation

After completing the spec stack, ask yourself:

```
If you handed these four documents to an AI agent along with
CLAUDE.md, could it produce a working implementation?

- What questions would the AI agent still need answered?
- What ambiguities remain in your specs?
- What did you discover while writing the specs that you had
  not considered before?
```

The last question is the most important. Writing specs is a design activity. The specs are not just instructions for the AI -- they are a forcing function for your own thinking.

---

## Try It: Spec-Quality Prompt Challenge (15 minutes)

Take one of these TicketPulse features and write a spec-quality prompt (using the five-element structure from Part 4) that an AI agent could implement from:

```
OPTION A: Add a "similar events" recommendation widget to the
          event detail page

OPTION B: Add rate limiting to the ticket purchase API to prevent
          bot purchases during high-demand sales

OPTION C: Add an admin dashboard endpoint that returns real-time
          metrics (revenue, tickets sold, active users) for a
          given time range
```

After writing your prompt, evaluate it against this rubric:

```
RUBRIC                                          SCORE (1-5)
─────────────────────────────────────────────────────────
Inputs and outputs fully typed?                  ____
Acceptance criteria testable without ambiguity?  ____
Constraints and non-goals stated?                ____
At least 3 input/output examples provided?       ____
Existing code patterns referenced?               ____
Verification criteria included?                  ____

TOTAL: ____/30

25+  → Production-quality spec. Ship it.
18-24 → Good foundation, needs sharpening on weak areas.
<18  → Rewrite. The AI will produce something you have to rewrite.
```

---

## 🤔 Reflect

Take a few minutes to consider these questions. There are no right answers -- these are meant to sharpen your thinking about where the industry is heading.

### 1. How does spec quality correlate with AI output quality?

Think about your experience with AI tools in this course. When did the AI produce great results? When did it produce garbage? Was the difference in the AI model, or in the clarity of what you asked for?

### 2. Will AI eventually write the specs too?

If AI can implement from a spec, can it also write the spec from a product requirement? If so, what does the human engineer do? Is there an irreducible core of engineering judgment that cannot be automated?

### 3. How would you measure the ROI of investing in better specs?

Your team currently spends 10 minutes writing vague requirements and 3 hours fixing AI output. If you spent 45 minutes on a spec-quality prompt and 30 minutes reviewing, is that better? How would you prove it to a skeptical engineering manager?

### 4. In 5 years, what percentage of code will be written by AI agents working from human specs?

Is it 50%? 80%? 95%? What does this mean for what junior engineers should learn? What does this mean for what senior engineers should focus on?

---

## ✅ Checkpoint

Before moving on, confirm you have completed:

- [ ] CLAUDE.md written for TicketPulse with project context, conventions, and architecture decisions
- [ ] Feature spec written that an AI agent could implement from (using the five principles)
- [ ] Understand the seven-step design-doc to AI implementation to review workflow
- [ ] Can articulate the difference between a human-readable spec and an AI-executable spec
- [ ] Complete spec stack designed for the smart pricing feature (CLAUDE.md update + RFC + OpenAPI + Gherkin)
- [ ] At least one spec-quality prompt written and self-evaluated against the rubric

---

## Key Terms

| Term | Definition |
|------|-----------|
| **CLAUDE.md** | A project-root file that tells AI agents how to work within a codebase: conventions, patterns, constraints, and architectural context. |
| **AI-native specification** | A spec written with the assumption that an AI agent, not just a human, will implement from it. Emphasizes precision, types, and testable criteria. |
| **Prompt engineering** | The practice of structuring instructions to AI models for optimal output. Converging with specification writing as AI capabilities increase. |
| **Spec stack** | A layered set of specification documents (CLAUDE.md + RFC + OpenAPI + Gherkin) where each layer serves a different stage of AI-assisted development. |
| **Behavioral specification** | A spec that defines how a system should behave (inputs, outputs, side effects) rather than how it should be implemented internally. |
| **AI-executable spec** | A specification precise enough that an AI agent can produce a working implementation without asking clarifying questions. |
| **Design-doc-to-implementation workflow** | The seven-step process: RFC, CLAUDE.md, feature spec, AI implementation, human review, AI tests, human verification. |
| **Acceptance criteria** | Specific, testable conditions that define when a feature is complete. In AI-native specs, these map directly to test cases. |
| **Agent-compatible spec** | A specification formatted and structured so that an AI coding agent can parse it, understand scope, and generate code that adheres to it. |

---

## Further Reading

- **Chapter 34**: AI-Native Development Practices -- spec-driven workflows, prompt engineering, and the future of human-AI collaboration
- **Chapter 9**: Engineering Leadership -- ADRs, RFCs, and decision documentation (the foundation specs build on)
- **Chapter 17**: AI-Augmented Engineering -- practical AI tool usage, prompt strategies, and review processes
- **OpenAPI Specification**: swagger.io/specification/ -- the standard for REST API specifications
- **AsyncAPI Specification**: asyncapi.com -- the standard for event-driven API specifications
- **Gherkin Reference**: cucumber.io/docs/gherkin/reference/ -- behavior-driven development scenario syntax
- **"Specification by Example" by Gojko Adzic**: the book that predicted specs and tests would converge

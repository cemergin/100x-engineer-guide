<!--
  CHAPTER: 34c
  TITLE: AI-Native Specs & Spec Culture
  PART: III — Tooling & Practice
  PREREQS: Ch 34 (Specs, RFCs & ADRs), Ch 34b (Contract-First API & Executable Specs), Ch 17 (Claude Code Mastery), Ch 14 (AI-Powered Engineering)
  KEY_TOPICS: AI-native spec-driven development, CLAUDE.md as spec, AI-first development loop, spec anti-patterns, measuring spec quality, spec-driven workflow, building spec culture
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 34c: AI-Native Specs & Spec Culture

> **Part III — Tooling & Practice** | Prerequisites: Ch 34 (Specs, RFCs & ADRs), Ch 34b (Contract-First API & Executable Specs), Ch 17 (Claude Code Mastery), Ch 14 (AI-Powered Engineering) | Difficulty: Intermediate → Advanced

In the age of AI-assisted development, the spec is no longer just a communication tool between humans — it is a programming interface between human intent and machine execution. This chapter covers how to write specs that AI agents can execute, how to avoid the most common spec failures, how to measure whether your specs are working, and how to build a team culture where spec discipline compounds engineering velocity over time.

### In This Chapter
- AI-Native Spec-Driven Development
- The Spec-Driven Development Workflow
- Spec Anti-Patterns
- Measuring Spec Quality
- Spec-Driven Development in Practice
- Building a Spec Culture

### Related Chapters
- Ch 34 (Specs, RFCs & Architecture Decision Records) — the spec-first thesis, RFCs, ADRs
- Ch 34b (Contract-First API & Executable Specs) — OpenAPI, AsyncAPI, Protobuf, BDD/Gherkin
- Ch 27 (Technical Writing & Documentation) — writing principles, ADR introduction, RFC basics
- Ch 9 (Engineering Leadership) — communication, alignment, decision-making
- Ch 14 (AI-Powered Engineering) — AI workflows that consume specs
- Ch 17 (Claude Code Mastery) — CLAUDE.md, agent-compatible workflows

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

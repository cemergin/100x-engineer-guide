# L3-M86: AI-Powered Engineering Workflow

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 60 min | 🟢 Core | Prerequisites: All prior modules
>
> **Source:** Chapters 17, 10 of the 100x Engineer Guide

## What You'll Learn

- Using AI pair programming to plan, design, implement, and test a new TicketPulse feature end-to-end
- Evaluating AI output: what it gets right, what needs correction, and what it misses entirely
- The "70% problem": AI gets you most of the way, but the last stretch requires your expertise
- Effective prompting strategies: specificity, context, constraints, and iteration
- When AI accelerates you (boilerplate, tests, docs) vs when it slows you down (novel architecture, subtle bugs, security)
- How to review code that was primarily written by AI

## Why This Matters

AI coding tools are not a future trend. They are current infrastructure. Engineers who use them effectively ship faster than those who do not. But "effectively" is the key word. Using AI without understanding what it produces is worse than not using it at all -- you get code that looks correct, passes a quick glance, and breaks in production because nobody caught the subtle assumption the AI made.

This module is not about learning how to use a tool. You have been using Claude Code or similar tools throughout the course. This module is about developing judgment: knowing when to trust the output, when to be skeptical, and how to direct the AI to produce better results.

The engineers who get the most from AI are not the ones who type the cleverest prompts. They are the ones who understand the system deeply enough to evaluate, correct, and extend what the AI produces. The AI is a force multiplier -- but only for engineers who already have force to multiply.

---

## 1. The Feature: Waitlist When Events Sell Out

### Product Requirements

When an event sells out, users should be able to join a waitlist. If tickets become available (cancellations, refunds, additional capacity), waitlisted users are notified in order and given a time-limited opportunity to purchase.

**Requirements:**
- Users can join the waitlist for a sold-out event
- When tickets become available, the first N users on the waitlist are notified
- Each notified user has 15 minutes to complete the purchase
- If they do not purchase in time, the next user on the waitlist is notified
- A user can leave the waitlist at any time
- A user cannot join the waitlist if they already have tickets for the event

### Stop and Design (10 minutes)

Before using AI, spend 10 minutes designing this yourself:

1. What database tables/columns do you need?
2. What API endpoints?
3. What happens concurrently (two tickets released at the same time)?
4. How do you handle the 15-minute timeout?
5. What events would this publish to the event bus?

Write down your design. You will compare it to what the AI produces.

---

## 2. AI-Assisted Implementation

### Phase 1: Planning with AI

Give the AI your design context and ask it to plan:

```
Prompt: "TicketPulse is an event ticketing platform built with Node.js,
Express, PostgreSQL, and Redis. We use TypeScript, Prisma for ORM,
and a Kafka-based event bus for async communication.

Design a waitlist feature with these requirements:
[paste requirements above]

Existing patterns in the codebase:
- REST API endpoints follow /api/v1/{resource} pattern
- All mutations publish domain events to Kafka
- We use optimistic locking (version column) for concurrency
- Rate limiting exists on all public endpoints

Give me: database schema, API endpoints, and the key edge cases
to handle."
```

### Evaluating the Plan

The AI will likely produce a reasonable schema and endpoint design. Compare it to your own design from the "Stop and Design" exercise.

**What AI typically gets right:**
- Basic schema design (waitlist table with user_id, event_id, position, status)
- Standard CRUD endpoints (POST to join, DELETE to leave, GET to check position)
- Common edge cases (already on waitlist, already has tickets)

**What AI typically misses or gets wrong:**
- **Concurrency at the edges**: When two tickets are released simultaneously, the AI might not handle the race condition where both trigger notifications to the same user, or where position calculation has a gap.
- **Timeout implementation details**: The AI might suggest `setTimeout` (which does not survive process restarts) instead of a scheduled job or durable timer.
- **Integration with existing patterns**: The AI does not know about your specific event bus patterns, your error handling middleware, or your logging conventions unless you tell it.

### Phase 2: Schema and Migration

Ask the AI to generate the Prisma schema:

```
Prompt: "Generate the Prisma schema additions for the waitlist feature.
Follow the existing pattern in our schema where we use:
- UUID for primary keys
- camelCase for field names
- explicit relations with onDelete behavior
- version field for optimistic locking
- createdAt/updatedAt timestamps"
```

**Review the output carefully:**

```prisma
// What AI might generate:
model WaitlistEntry {
  id        String   @id @default(uuid())
  userId    String
  eventId   String
  position  Int
  status    String   @default("waiting") // waiting, notified, expired, converted
  notifiedAt DateTime?
  expiresAt  DateTime?
  version   Int      @default(0)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  user  User  @relation(fields: [userId], references: [id], onDelete: Cascade)
  event Event @relation(fields: [eventId], references: [id], onDelete: Cascade)

  @@unique([userId, eventId])
  @@index([eventId, status, position])
}
```

**What to check:**
- Does the `@@unique` constraint match your business rule? (One entry per user per event -- correct.)
- Is the index useful for the queries you will run? (Find next waiting user for an event -- yes.)
- Does `onDelete: Cascade` make sense? (If the event is deleted, removing waitlist entries is reasonable.)
- Is `position` the right approach? (What happens when someone leaves the waitlist -- do you renumber everyone, or accept gaps?)

### Phase 3: API Endpoints

Ask the AI to generate the endpoint implementations:

```
Prompt: "Implement the POST /api/v1/events/:eventId/waitlist endpoint.
It should:
1. Verify the event exists and is sold out
2. Verify the user does not already have tickets
3. Verify the user is not already on the waitlist
4. Add the user to the waitlist with the next available position
5. Publish a WaitlistJoined event to Kafka
6. Return 201 with the waitlist entry

Use our existing patterns:
- Wrap in try/catch, errors use our AppError class
- Auth middleware provides req.user with { id, email }
- Use Prisma transactions for multi-step writes"
```

**What to scrutinize:**

```typescript
// AI might generate this for position calculation:
const maxPosition = await prisma.waitlistEntry.aggregate({
  where: { eventId, status: 'waiting' },
  _max: { position: true },
});
const nextPosition = (maxPosition._max.position ?? 0) + 1;
```

**The concurrency bug**: If two users join simultaneously, both read `maxPosition = 5`, both get `nextPosition = 6`. The `@@unique([userId, eventId])` prevents duplicates per user, but two different users both get position 6.

**Fix**: Use a database sequence, or use the unique constraint plus a retry:

```typescript
// Better: use a serializable transaction or a sequence
const entry = await prisma.$transaction(async (tx) => {
  const maxPosition = await tx.waitlistEntry.aggregate({
    where: { eventId, status: 'waiting' },
    _max: { position: true },
  });

  return tx.waitlistEntry.create({
    data: {
      userId: req.user.id,
      eventId,
      position: (maxPosition._max.position ?? 0) + 1,
      status: 'waiting',
    },
  });
}, { isolationLevel: 'Serializable' });
```

This is the kind of fix AI will not suggest unless you specifically ask about concurrency.

### Phase 4: Test Generation

AI excels at generating tests. Use it:

```
Prompt: "Generate tests for the waitlist join endpoint. Include:
- Happy path: user joins waitlist successfully
- Already on waitlist: returns 409
- Already has tickets: returns 409
- Event not sold out: returns 400
- Event does not exist: returns 404
- Concurrent joins: positions do not collide

Use our test patterns: vitest, supertest, test database with transactions
rolled back after each test."
```

AI will generate thorough test suites quickly. The concurrency test is the one most likely to need your correction -- check that it actually tests concurrent behavior (parallel requests) rather than sequential calls that happen to test for collisions.

---

## 3. The 70% Problem

After using AI for planning, schema, implementation, and tests, evaluate the result:

### What AI Got Right (the 70%)

- Basic schema design and API structure
- Input validation and error handling boilerplate
- Standard CRUD operations
- Test scaffolding and happy-path tests
- TypeScript types and interfaces
- Prisma query construction

### What Needed Your Correction (the 30%)

- Concurrency handling for position assignment
- Timeout mechanism (suggesting a durable approach instead of setTimeout)
- Integration with your specific event bus patterns
- Edge case in notification: what if the user's email bounces?
- Security: rate limiting on the join endpoint to prevent waitlist spam
- Performance: will the position query be fast with 100K waitlist entries?

### The Pattern

AI is a drafting tool. It produces a first draft that is structurally sound but misses the nuances that come from understanding the system deeply. The value is in getting to the first draft in 15 minutes instead of 2 hours. Your expertise is in identifying and fixing the 30% the AI missed.

---

## 4. When AI Accelerates vs When It Slows Down

### AI Accelerates You

| Task | Why AI Helps |
|------|-------------|
| **Boilerplate** | CRUD endpoints, middleware setup, configuration files |
| **Test generation** | Given a function, AI writes thorough tests quickly |
| **Documentation** | JSDoc, README sections, API descriptions |
| **Exploring unfamiliar APIs** | "How do I use Prisma's createMany with conflict handling?" |
| **Refactoring** | "Convert this callback-based code to async/await" |
| **Code review prep** | "What could go wrong with this implementation?" |

### AI Slows You Down

| Task | Why AI Hurts |
|------|-------------|
| **Novel architecture decisions** | AI draws from patterns it has seen, not your specific constraints |
| **Subtle concurrency bugs** | AI does not reason about timing and race conditions well |
| **Security-sensitive code** | AI might miss authentication edge cases or produce vulnerable patterns |
| **Performance optimization** | AI does not know your data distribution, query patterns, or bottlenecks |
| **Debugging production issues** | AI cannot observe runtime behavior, logs, or metrics |

---

## 5. Effective Prompting: Getting Better Results

### The Specificity Spectrum

The quality of AI output is directly proportional to the specificity of your input.

**Vague prompt (poor results):**
```
"Add a waitlist feature to TicketPulse."
```

**Specific prompt (good results):**
```
"Implement POST /api/v1/events/:eventId/waitlist endpoint for TicketPulse.

Context:
- Node.js + Express + TypeScript
- Prisma ORM with PostgreSQL
- Auth middleware provides req.user with { id, email }
- Kafka event bus (publish WaitlistJoined event)
- Existing patterns: AppError class for errors, Prisma transactions for multi-step writes

Requirements:
- Verify event exists and is sold out (event.availableTickets === 0)
- Verify user doesn't already have tickets for this event
- Verify user isn't already on the waitlist
- Assign next position (handle concurrent position assignment)
- Return 201 with waitlist entry

Constraints:
- Must handle race conditions (two users joining simultaneously)
- Position must be monotonically increasing per event
- Include input validation with Zod"
```

The specific prompt gives the AI everything it needs: technology stack, existing patterns, requirements, AND constraints. The AI cannot infer your patterns from nothing.

### The Iteration Loop

Do not expect the first response to be final. Effective AI use is iterative:

```
1. Generate initial implementation
2. Review: "This doesn't handle the case where..."
3. AI corrects
4. Review: "The error handling should use our AppError class, like this: [example]"
5. AI adapts to your pattern
6. Review: "Looks good. Now generate tests."
7. AI generates tests
8. Review: "Add a test for concurrent position assignment"
9. Final review and manual adjustments
```

Each iteration narrows the gap between what you need and what the AI produced. The key skill is knowing what to ask for next -- which requires understanding the system.

### Context Management

AI tools have limited context windows. For large codebases:

```
DON'T: "Look at my entire codebase and add the waitlist feature"
       (AI tries to read everything, runs out of context, produces shallow results)

DO:    "Here are the specific files relevant to this feature:
       - src/routes/events.ts (existing event endpoints to follow the pattern)
       - src/services/ticket-service.ts (the service that tracks availability)
       - src/lib/errors.ts (our AppError class)
       - prisma/schema.prisma (current schema)
       Now implement the waitlist feature."
```

Point the AI at exactly what it needs. Less context, more relevant context, better results.

---

## 6. Reviewing AI-Generated Code

### How to Review a PR That Was Mostly Written by AI

When a teammate (or you) submits a PR where AI did most of the writing, apply extra scrutiny to:

1. **Concurrency and state**: Does the code handle concurrent access correctly? Race conditions are the number one thing AI misses.

2. **Error handling completeness**: AI generates try/catch blocks but often catches too broadly or swallows errors. Check that errors propagate correctly and are logged.

3. **Security boundaries**: Authentication, authorization, input validation. Does the code check permissions correctly? Are all inputs sanitized?

4. **Edge cases at boundaries**: Empty arrays, null values, maximum sizes, timezone issues, Unicode in strings. AI tests the happy path well but may miss boundary conditions.

5. **Integration correctness**: Does the code follow YOUR codebase's patterns? AI might use a different error handling pattern, a different logging format, or a different API style than your codebase.

6. **Dependencies**: Did the AI add new dependencies? Are they necessary? Are they well-maintained? Check the license.

---

## 6. Reflect: Your AI Workflow

### Stop and Think (10 minutes)

After building the waitlist feature with AI assistance:

1. **Time comparison**: How long would this have taken without AI? With AI? Where was the biggest time saving?

2. **Quality comparison**: Was the AI-generated code production-ready as-is? What percentage needed correction?

3. **Your role**: What did you contribute that AI could not? (System knowledge, concurrency reasoning, security awareness, taste in API design)

4. **Going forward**: Which of your daily tasks would benefit most from AI assistance? Which should you never delegate to AI?

The engineer who understands the system uses AI 10x more effectively than one who does not. AI does not replace understanding -- it amplifies it.

---

## Checkpoint: What You Built

You have:

- [x] Designed and implemented a waitlist feature using AI pair programming
- [x] Evaluated AI output: identified what was correct, what needed fixes, and what was missing
- [x] Fixed a concurrency bug that AI missed (position assignment race condition)
- [x] Generated comprehensive tests using AI and verified their correctness
- [x] Developed a framework for when to use AI vs when to rely on your own expertise

**Key insight**: AI is a force multiplier, not a replacement. The 70% it handles well (boilerplate, tests, documentation, exploration) saves you hours. The 30% it misses (concurrency, security, system-specific integration, novel design) is where your engineering judgment earns its keep.

---

**Next module**: L3-M87 -- Mobile Backend Patterns, where TicketPulse launches a mobile app and the backend requirements change fundamentally.

---

## 7. Prompt Engineering Drills

The fastest way to improve your AI output quality is deliberate practice. These drills are designed to be done sequentially, each one building on the previous.

### Drill 1: The Context Injection Drill (10 minutes)

Take a real task from your backlog. Write the same prompt three times with increasing levels of context:

**Version A — Bare minimum:**
```
"Add rate limiting to the waitlist endpoint."
```

**Version B — Stack context:**
```
"Add rate limiting to POST /api/v1/events/:eventId/waitlist.
Tech stack: Node.js, Express, TypeScript.
Use our existing RateLimiter from src/lib/rate-limiter.ts.
Limit: 5 requests per IP per 10 minutes."
```

**Version C — Full context with constraints:**
```
"Add rate limiting to POST /api/v1/events/:eventId/waitlist.

Context:
- Node.js + Express + TypeScript
- Rate limiter middleware: src/lib/rate-limiter.ts (uses Redis sliding window)
- Pattern in codebase: rateLimiter({ points: 5, duration: 600, prefix: 'rl:join:' })
- Auth middleware runs before rate limiter (req.user is populated)
- Error response format: { error: { code: 'RATE_LIMIT_EXCEEDED', message: '...' } }

Constraint: limit by user ID when authenticated, by IP when not.
Return 429 with Retry-After header.
Do not add new dependencies."
```

Generate output from each version. Compare the quality. Measure how many corrections the Version C output needs vs Version A. In most cases, Version C needs zero corrections, Version A needs five.

**The lesson:** writing the Version C prompt takes 3 extra minutes. Correcting a Version A output takes 15. You save time by investing in the prompt.

### Drill 2: The Skeptic Drill (5 minutes)

Take any AI-generated code snippet. Before running it, ask the AI to attack its own output:

```
"You just generated this code. Now act as an adversarial code reviewer.
Find every race condition, security hole, and edge case this code misses.
Be ruthless. Do not defend the code you wrote."
```

What comes back is often a list of 3-5 genuine problems. This is the fastest way to catch issues before they reach production. The AI knows what it generated and can reason about its own failure modes.

### Drill 3: The Pattern Extraction Drill (10 minutes)

Find a pattern in your codebase that you use repeatedly — maybe how you structure service classes, how you write Prisma transactions, or how you format error responses. Feed three examples to the AI:

```
"Here are three examples of how we structure service methods in TicketPulse:

Example 1: [paste getEvent service method]
Example 2: [paste createOrder service method]
Example 3: [paste cancelTicket service method]

Extract the pattern. Describe it precisely enough that you could generate new service methods that match it perfectly.

Then generate createWaitlistEntry using that exact pattern."
```

This trains the AI on YOUR patterns, not generic patterns. The output will match your codebase style without manual correction.

### Drill 4: The Constraint-First Drill (5 minutes)

Most engineers describe WHAT they want. Effective AI prompting starts with constraints — things the output must NOT do:

```
"Implement the waitlist notification cron job.

Hard constraints (these are non-negotiable):
- Must be idempotent: running it twice must produce the same result
- Must not use setTimeout or setInterval (these die when the process restarts)
- Must not send more than one notification per user per event per hour
- Must work with our existing Bull queue infrastructure

Soft preferences:
- Prefer simplicity over cleverness
- Prefer explicit over implicit
- Prefer small functions with clear names

Now implement it."
```

The constraint-first structure forces the AI to eliminate bad solutions before writing code. You get dramatically better results on the first try.

### Drill 5: The Incremental Refinement Drill (15 minutes)

Do not try to get the perfect implementation in one shot. Practice a 5-step refinement loop:

```
Step 1: "Give me a rough sketch of the waitlist notification flow. Pseudocode is fine."
         → Review the structure. Does the flow make sense?

Step 2: "Good. Now implement step 2 (find users to notify) in TypeScript using Prisma."
         → Review the query. Is it correct? Efficient?

Step 3: "This query could be slow with 100K waitlist entries. Optimize it."
         → Review the optimization. Does it still return correct data?

Step 4: "Add error handling using our AppError class. Show me the full function."
         → Review error paths. Are all failure modes covered?

Step 5: "Generate tests for this function. Cover: happy path, empty waitlist,
         database error, and concurrent execution."
         → Review tests. Do the concurrent tests actually test concurrency?
```

Each step is small enough that you can evaluate it completely. Errors in step 2 get caught before you build steps 3-5 on a broken foundation.

---

## 8. Advanced AI Workflow: AI for Architecture and Design

Most engineers use AI for implementation. The engineers who get the most leverage use it earlier — at the design and architecture stage.

### Using AI for Design Critique

Before writing code, use AI as an adversarial design partner:

```
"Here is my design for the waitlist notification system:
[paste your design]

Act as a Staff Engineer doing a design review. Your goal is to find problems with this design, not validate it. Focus on:
1. Concurrency and race conditions
2. Failure modes and how the system behaves when each component fails
3. Scalability — what breaks at 10x, 100x the current load?
4. Missing edge cases
5. Integration points that are likely to cause problems

Do not suggest improvements yet. Just identify problems."
```

This is more valuable than asking the AI to design something for you. You bring the domain knowledge and business constraints. The AI brings systematic skepticism.

### Using AI for Trade-off Analysis

When you are choosing between two approaches, AI can help you think through the trade-offs you have not considered:

```
"I am deciding between two approaches for the waitlist notification system:

Option A: Cron job that runs every 30 seconds, checks for available tickets, and sends notifications.
Option B: Event-driven — when a ticket is released, publish a WaitlistCheck event that triggers notification.

I have already identified these trade-offs:
- A is simpler, B is more responsive
- A has up to 30s delay, B is near-instant
- A is easier to reason about, B has more moving parts

What trade-offs have I missed? Particularly around: failure handling, idempotency, monitoring and debugging, and cost at scale."
```

The AI often identifies trade-offs you did not consider — like the fact that Option B requires your event bus to be reliable before you can trust notification delivery.

---

## 9. AI-Assisted Code Review: A Checklist

When reviewing a PR that was heavily AI-assisted, use this structured checklist. Each item targets a category of problems AI commonly misses.

### Pre-Review: Set Expectations

```
Before reviewing AI-generated code, remind yourself:
- AI does not know YOUR codebase conventions
- AI does not know YOUR data distribution and volume
- AI does not know which failure modes have burned YOU before
- AI was not in the room when the requirements were discussed
```

### The Checklist

**Concurrency (check every shared resource access):**
- [ ] Every read-modify-write sequence uses a transaction or lock
- [ ] Counter increments use atomic operations or serializable transactions
- [ ] Any "check then act" pattern is protected from TOCTOU races
- [ ] Background jobs are idempotent (safe to run twice)

**Error handling (check every try/catch block):**
- [ ] Errors propagate to the right level (not swallowed in service, thrown to route handler)
- [ ] All catch blocks either re-throw or log + handle
- [ ] Async errors are caught (unhandled promise rejections are silent)
- [ ] External service failures are handled (database down, Kafka unavailable)

**Security (check every external input):**
- [ ] All inputs are validated before use (Zod, Joi, or equivalent)
- [ ] SQL queries use parameterized queries, not string concatenation
- [ ] User-controlled data does not flow into system commands or file paths
- [ ] Authorization checks happen before data access, not after

**Performance (check data access patterns):**
- [ ] No queries inside loops (N+1 problem)
- [ ] Indexes exist for all WHERE and ORDER BY columns in new queries
- [ ] Large result sets are paginated, not loaded entirely into memory
- [ ] Expensive operations (crypto, serialization) are outside hot paths

**Integration (check codebase consistency):**
- [ ] Error responses use your AppError class / standard format
- [ ] Logging uses your existing logger with standard fields
- [ ] Events published to Kafka follow your schema registry format
- [ ] New files follow the project's naming and directory conventions

---

## 10. Reflect: Your AI Workflow

### Stop and Think (10 minutes)

After building the waitlist feature with AI assistance:

1. **Time comparison**: How long would this have taken without AI? With AI? Where was the biggest time saving?

2. **Quality comparison**: Was the AI-generated code production-ready as-is? What percentage needed correction?

3. **Your role**: What did you contribute that AI could not? (System knowledge, concurrency reasoning, security awareness, taste in API design)

4. **Going forward**: Which of your daily tasks would benefit most from AI assistance? Which should you never delegate to AI?

5. **The meta-skill**: AI tools change every few months. New models, new capabilities, new interfaces. What is the underlying skill that transfers across all of them? (Answer: knowing your system deeply enough to evaluate any output against it.)

The engineer who understands the system uses AI 10x more effectively than one who does not. AI does not replace understanding — it amplifies it.

---

## Cross-References

- **Chapter 14** (The AI-Augmented Engineer): The mental model for integrating AI into every phase of the engineering workflow, from requirements through post-mortems.
- **Chapter 17** (AI Pair Programming in Practice): Deep dive into prompt patterns, context management, and the economics of AI-assisted development across different task types.
- **L3-M90** (Final Capstone): Uses AI pair programming as one of the primary tools for the capstone architecture review.

---

## Checkpoint: What You Built

You have:

- [x] Designed and implemented a waitlist feature using AI pair programming
- [x] Evaluated AI output: identified what was correct, what needed fixes, and what was missing
- [x] Fixed a concurrency bug that AI missed (position assignment race condition)
- [x] Generated comprehensive tests using AI and verified their correctness
- [x] Practiced five prompt engineering drills that compound quality with specificity
- [x] Applied the adversarial review technique to your own AI-generated code
- [x] Developed a framework for when to use AI vs when to rely on your own expertise

**Key insight**: AI is a force multiplier, not a replacement. The 70% it handles well (boilerplate, tests, documentation, exploration) saves you hours. The 30% it misses (concurrency, security, system-specific integration, novel design) is where your engineering judgment earns its keep.

---

**Next module**: L3-M87 -- Mobile Backend Patterns, where TicketPulse launches a mobile app and the backend requirements change fundamentally.

## Key Terms

| Term | Definition |
|------|-----------|
| **AI pair programming** | Using an AI assistant alongside a developer in real time to write, review, and debug code. |
| **Claude Code** | Anthropic's CLI tool that integrates Claude into the development workflow for code generation and analysis. |
| **Prompt engineering** | The practice of crafting effective inputs to an LLM to elicit accurate, useful responses. |
| **Code review** | The process of examining code changes for correctness, style, security, and maintainability before merging. |
| **Context window** | The maximum amount of text (measured in tokens) that an LLM can process in a single request. |
| **Adversarial review** | A technique where the AI is asked to critique and attack its own output, simulating a skeptical reviewer. |
| **Constraint-first prompting** | A prompting style that specifies what the output must NOT do before describing what it should do. |
| **Incremental refinement** | An AI workflow pattern where complex output is built in small, verifiable steps rather than generated all at once. |

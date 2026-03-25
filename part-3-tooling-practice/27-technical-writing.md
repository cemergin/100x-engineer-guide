<!--
  CHAPTER: 27
  TITLE: Technical Writing & Documentation
  PART: III — Tooling & Practice
  PREREQS: None
  KEY_TOPICS: Diátaxis framework, READMEs, architecture docs, RFCs, postmortems, commit messages, PR descriptions, runbooks, API docs, writing clearly
  DIFFICULTY: Beginner → Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 27: Technical Writing & Documentation

> **Part III — Tooling & Practice** | Prerequisites: None | Difficulty: Beginner → Intermediate

Clear writing is a multiplier — a well-written RFC prevents weeks of misaligned work, a good runbook saves hours during an incident, and clear commit messages make debugging possible months later. This chapter covers every type of document an engineer writes.

### In This Chapter
- Writing Principles for Engineers
- The Diátaxis Framework
- READMEs That Actually Help
- Architecture Decision Records (ADRs)
- RFCs & Design Documents
- Commit Messages & PR Descriptions
- Runbooks & Operational Docs
- Postmortem Reports
- API Documentation
- Code Comments That Add Value

### Related Chapters
- Ch 9 (engineering leadership communication)
- Ch 15 (codebase organization)
- Ch 25 (API documentation)

---

## 1. Writing Principles for Engineers

Good engineering writing is not literary writing. It is closer to a user interface: the goal is to transfer information with minimal friction. These principles apply to every document type in this chapter.

### Lead with the Conclusion

Use the inverted pyramid structure. Put the most important information first. Readers are busy and may not finish your document.

**Bad:**
> We evaluated several caching strategies over the past quarter, considering factors such as consistency requirements, operational complexity, and cost. After careful deliberation across three team meetings and a review of industry literature, we concluded that we should adopt Redis Cluster for our session store.

**Good:**
> We are adopting Redis Cluster for our session store. It meets our consistency requirements, has lower operational complexity than the alternatives, and reduces session lookup latency from 120ms to 8ms.

The first version makes the reader wade through process before reaching the point. The second version gives the decision immediately, then justifies it.

### One Idea per Paragraph

Each paragraph should communicate a single concept. If you find a paragraph covering two distinct ideas, split it. This makes text scannable and easier to reference in discussions ("I disagree with your point in paragraph 3").

### Active Voice over Passive

Active voice is shorter, clearer, and assigns responsibility.

| Passive (avoid) | Active (prefer) |
|---|---|
| An error is returned by the service | The service returns an error |
| The database was migrated by the platform team | The platform team migrated the database |
| The request will be retried automatically | The client retries the request automatically |
| Tests should be written before implementation | Write tests before implementation |

Passive voice is acceptable when the actor is genuinely unknown or irrelevant ("The server was provisioned in 2019").

### Concrete over Abstract

Specifics are more useful than vague descriptions. Numbers, names, and examples beat adjectives.

| Abstract (avoid) | Concrete (prefer) |
|---|---|
| Performance degraded significantly | Latency increased from 50ms to 800ms at p99 |
| The service handles a large volume of requests | The service processes 14,000 requests per second |
| The deployment took a long time | The deployment took 47 minutes |
| There were some errors | 3.2% of requests returned HTTP 500 |

### Remove Filler Words

These words add length without adding meaning. Delete them on sight:

- **very** — "very important" → "critical"
- **basically** — "it basically works by" → "it works by"
- **actually** — "it actually turns out" → "it turns out"
- **just** — "you just need to" → "you need to"
- **really** — "this is really useful" → "this is useful"
- **quite** — "quite a few errors" → "many errors" or "2,400 errors"
- **simply** — "simply run the command" → "run the command"

### Use Lists and Tables for Structured Information

Do not bury structured data inside prose paragraphs. If information has parallel structure, use a list or table.

**Bad:**
> The service supports three authentication methods. The first is API keys, which are best for server-to-server communication. The second is OAuth2, which should be used for user-facing applications. The third is mutual TLS, which is required for inter-service communication in the production VPC.

**Good:**

| Method | Use Case |
|---|---|
| API keys | Server-to-server communication |
| OAuth2 | User-facing applications |
| Mutual TLS | Inter-service communication (production VPC) |

### Write for Scanning

Most readers scan before they read. Help them:

- Use descriptive headers (not "Overview" — say "How the billing pipeline works")
- **Bold key terms** when they first appear
- Put a TL;DR at the top of long documents
- Keep paragraphs short (3-5 sentences)
- Use code formatting for `function names`, `file paths`, and `commands`

### The "So What?" Test

After writing each sentence, ask: "Why does the reader care?" If you cannot answer that question, the sentence can be cut or rewritten.

**Fails the test:** "The system uses a microservices architecture."
**Passes the test:** "The system uses a microservices architecture, so each team can deploy independently without coordinating release schedules."

---

## 2. The Diátaxis Framework

The Diátaxis framework (from the Greek *dia* "across" + *taxis* "arrangement") organizes documentation into four types based on what the reader needs. Mixing types is the single most common documentation mistake.

### The Four Types

|  | Learning (acquiring skill) | Working (applying skill) |
|---|---|---|
| **Practical** | **Tutorial** | **How-To Guide** |
| **Theoretical** | **Explanation** | **Reference** |

#### Tutorials (Learning-Oriented)

**Purpose:** Get the reader to a working result through a guided experience.

**Characteristics:**
- Step-by-step instructions the reader follows exactly
- Assumes no prior knowledge of this specific system
- Focuses on *doing*, not *understanding*
- Every step produces a visible result
- Hand-holds through potential failure points

**Example opening:**
> In this tutorial, you will build a REST API that stores and retrieves user profiles. By the end, you will have a running service that handles CRUD operations with PostgreSQL. This takes about 30 minutes.

**Common mistake:** Stopping to explain why something works. In a tutorial, keep the reader moving. Save the "why" for Explanation docs.

#### How-To Guides (Task-Oriented)

**Purpose:** Help a practitioner accomplish a specific task.

**Characteristics:**
- Problem-focused ("How to deploy to production," "How to rotate API keys")
- Assumes the reader has working knowledge of the system
- Direct and efficient — no hand-holding
- May reference other docs for background

**Example opening:**
> This guide covers deploying a new version to production using blue-green deployment. You need kubectl access to the production cluster and membership in the `deployers` GitHub team.

**Common mistake:** Starting from scratch. A how-to guide is not a tutorial. If the reader needs fundamentals, link to the tutorial instead.

#### Reference (Information-Oriented)

**Purpose:** Provide complete, accurate, structured information for lookup.

**Characteristics:**
- Organized for fast lookup (alphabetical, by module, by endpoint)
- Exhaustive — covers every parameter, option, and return value
- Consistent format across entries
- Generated from code when possible (keeps it in sync)
- No opinions, no narrative — just facts

**Example:**
```
### POST /api/v2/users

Creates a new user account.

**Request Body:**
| Field    | Type   | Required | Description           |
|----------|--------|----------|-----------------------|
| email    | string | yes      | Must be unique        |
| name     | string | yes      | 1-200 characters      |
| role     | string | no       | Default: "member"     |

**Response:** 201 Created
**Errors:** 409 Conflict (email already exists), 422 Unprocessable Entity
```

**Common mistake:** Adding tutorial-style instructions inside a reference. Keep it pure.

#### Explanation (Understanding-Oriented)

**Purpose:** Deepen the reader's understanding of concepts, architecture, and decisions.

**Characteristics:**
- Answers "why" and "how does this work conceptually"
- Discusses trade-offs, alternatives, and context
- Can include history and rationale
- Written in a conversational, discursive style
- Not tied to specific tasks

**Example opening:**
> Our billing system uses event sourcing rather than traditional CRUD because billing data has strict auditability requirements. Every state change is captured as an immutable event, which means we can reconstruct the state of any account at any point in time.

**Common mistake:** Trying to be a tutorial and an explanation at the same time. If the reader needs to *do* something, write a tutorial. If they need to *understand* something, write an explanation.

### How to Identify What Type You Need

Ask: **"What is the reader trying to do right now?"**

| Reader's goal | Document type |
|---|---|
| "I'm new and want to learn this" | Tutorial |
| "I need to accomplish task X" | How-To Guide |
| "What are the parameters for function Y?" | Reference |
| "Why does the system work this way?" | Explanation |

---

## 3. READMEs That Actually Help

A README is the front door of your project. Apply the **30-second rule**: a new developer should understand what this project does, whether it is relevant to them, and how to get started within 30 seconds of opening the README.

### Essential Sections (In Order)

#### 1. One-Sentence Description

State what the project is and what problem it solves. Not what technologies it uses.

**Bad:** "A Node.js microservice using Express, PostgreSQL, and Redis."
**Good:** "Order Processing Service — validates, charges, and fulfills customer orders from the web storefront."

#### 2. Quick Start

Get the reader to a running system in under 5 minutes. Copy-paste commands only.

```bash
# Clone and start
git clone git@github.com:acme/order-service.git
cd order-service
cp .env.example .env
docker compose up -d
npm install
npm run dev

# Verify it works
curl http://localhost:3000/health
# → {"status":"ok","version":"2.4.1"}
```

#### 3. Prerequisites

List exact versions. Do not say "recent version of Node."

```
- Node.js >= 20.11
- Docker >= 24.0
- PostgreSQL 16 (runs in Docker by default)
- Redis 7+ (runs in Docker by default)
```

#### 4. Installation / Setup

Expand on quick start for edge cases: environment variables to configure, database seeds to run, external services to set up.

#### 5. Usage Examples

Show the 3-5 most common operations:

```bash
# Create an order
curl -X POST http://localhost:3000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"items": [{"sku": "WIDGET-01", "qty": 2}]}'

# Get order status
curl http://localhost:3000/api/orders/ord_abc123

# Run the test suite
npm test
```

#### 6. Configuration

Document every environment variable:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | PostgreSQL connection string |
| `REDIS_URL` | no | `redis://localhost:6379` | Redis connection for caching |
| `STRIPE_SECRET_KEY` | yes | — | Stripe API key for payments |
| `LOG_LEVEL` | no | `info` | One of: debug, info, warn, error |

#### 7. Architecture Overview

For non-trivial projects, a short paragraph or diagram showing the major components and how they connect.

#### 8. Contributing Guide

Link to CONTRIBUTING.md or provide inline instructions: branch naming, test expectations, PR process.

#### 9. License

State the license. For internal projects, state "Internal — proprietary."

### README Anti-Patterns

- **Wall of text** with no headers or formatting
- **Outdated instructions** that no longer work (test your README quarterly)
- **No quick start** — the reader has to read 500 lines before running anything
- **Auto-generated boilerplate** that was never customized (the default Create React App README, for example)
- **Badges as content** — twelve status badges but no description of what the project does
- **"See the wiki"** — the wiki is always out of date; keep essential info in the README

---

## 4. Architecture Decision Records (ADRs)

> For a deeper treatment of ADRs, RFCs, contract-first API design (OpenAPI/AsyncAPI), executable specs (BDD/Gherkin), and AI-native specifications, see **Chapter 34: Spec-Driven Development**.

An ADR captures a single architectural decision: what was decided, why, and what the consequences are. ADRs create a decision log that future engineers (including your future self) can reference.

### Template

```markdown
# ADR-0001: Use PostgreSQL for the Order Database

## Status
Accepted (2026-01-15)

## Context
The order service needs a persistent data store. We process ~5,000 orders
per day with complex queries for reporting (joins across orders, line items,
and fulfillment records). Our team has deep PostgreSQL expertise. We
considered DynamoDB and MySQL as alternatives.

## Decision
We will use PostgreSQL 16 hosted on Amazon RDS.

## Consequences

### Positive
- Strong support for complex queries and joins needed for reporting
- Team has 5+ years of operational experience with PostgreSQL
- JSONB columns allow flexible metadata without schema migrations
- Mature ecosystem of tools (pgAdmin, pg_dump, logical replication)

### Negative
- Vertical scaling limits — may need read replicas beyond ~50K orders/day
- RDS costs more than DynamoDB for simple key-value access patterns
- Requires managing connection pooling (PgBouncer) under high concurrency

### Neutral
- Migration path to Aurora PostgreSQL exists if we outgrow single-instance RDS
```

### Key Practices

- **Store alongside code:** `docs/adr/0001-use-postgresql.md`. ADRs that live in a wiki get lost.
- **Never delete ADRs.** If a decision is reversed, write a new ADR that supersedes the old one and update the original's status to "Superseded by ADR-0042."
- **Number sequentially.** The number is an ID, not a priority.
- **Keep them short.** One page is ideal. If you need more, you are writing an RFC.

### Bad ADR Example (Too Vague)

```markdown
# ADR-0002: Database Choice

## Status
Accepted

## Context
We need a database.

## Decision
We will use PostgreSQL.

## Consequences
This should work well for our use case.
```

This fails because it captures zero reasoning. Six months later, nobody knows why PostgreSQL was chosen over alternatives, what trade-offs were accepted, or what constraints led to this decision.

---

## 5. RFCs & Design Documents

An RFC (Request for Comments) is a proposal for a significant change. It forces the author to think through a problem before writing code and gives stakeholders a structured way to provide input.

### When to Write an RFC

Write an RFC when any of these apply:
- The work will take more than 2 engineer-weeks
- The change affects multiple teams or services
- The decision is difficult or expensive to reverse
- There are multiple viable approaches and the trade-offs are non-obvious

Do **not** write an RFC for routine work, small bug fixes, or changes contained within a single team's codebase.

### RFC Structure

```markdown
# RFC: Migrate User Authentication to OAuth2 PKCE

**Author:** Alice Chen
**Date:** 2026-03-10
**Status:** In Review
**Reviewers:** Bob (security), Carol (frontend), Dave (platform)

## TL;DR
Replace our custom session-based auth with OAuth2 PKCE using Auth0.
This eliminates three classes of security vulnerabilities and reduces
auth-related on-call pages by an estimated 60%.

## Problem
Our custom authentication system has three issues:
1. Session fixation vulnerabilities (two incidents in 2025)
2. No support for MFA without significant custom development
3. Auth-related on-call pages account for 34% of all pages (avg 6/month)

## Context
- 12,000 active users, 95% web-based
- Current system: custom session cookies, bcrypt password hashing
- Mobile app launching Q3 2026 needs token-based auth regardless
- Security audit in January flagged auth as highest-risk area

## Proposed Solution
Adopt Auth0 as our identity provider using the OAuth2 PKCE flow.

### Architecture
[Diagram showing browser → Auth0 → API with token validation]

### Migration Plan
1. **Phase 1 (2 weeks):** Deploy Auth0 tenant, configure PKCE flow
2. **Phase 2 (3 weeks):** Dual-auth period — support both old and new
3. **Phase 3 (1 week):** Migrate remaining users, disable old system
4. **Phase 4 (ongoing):** Monitor, remove old auth code

### API Changes
- All endpoints accept Bearer tokens instead of session cookies
- New `/auth/callback` endpoint for OAuth redirect
- Deprecate `/auth/login` and `/auth/logout` (remove in Phase 3)

## Alternatives Considered

### Build OAuth2 in-house
- Pro: Full control, no vendor dependency
- Con: 8-12 weeks of work, ongoing maintenance, higher security risk
- **Rejected because:** We do not have the security expertise to build
  this correctly, and maintaining it diverts engineering from product work.

### Use Firebase Auth
- Pro: Free tier covers our usage, good mobile SDK
- Con: Vendor lock-in to Google ecosystem, less flexibility in flows
- **Rejected because:** We need custom claims and organization-level
  scoping that Firebase does not support well.

## Open Questions
1. How do we handle users with active sessions during migration?
2. Should we require MFA immediately or make it opt-in for 90 days?
3. What is our fallback if Auth0 has an outage?

## Rollout Plan
- Week 1-2: Implementation in staging
- Week 3: Internal dogfooding (employees only)
- Week 4-5: Gradual rollout (10% → 50% → 100%)
- Week 6: Remove old auth code
```

### RFC Process

1. **Author writes the RFC** and identifies 3-5 reviewers (include at least one skeptic).
2. **Review period: 1 week.** Reviewers leave comments directly on the document.
3. **Author addresses all comments** — either by updating the RFC or explaining why the feedback was not incorporated.
4. **Author makes the decision.** An RFC is not a vote. The author owns the decision and is accountable for it.
5. **Status updated** to Accepted, Rejected, or Deferred.

### Design Doc vs. RFC

A design doc is more detailed and implementation-focused. Use an RFC for the "should we do this and how?" question. Use a design doc for the "here is exactly how we will build it" answer. In many organizations, these are the same document — the RFC gets extended with implementation details after approval.

---

## 6. Commit Messages & PR Descriptions

### Commit Messages

A commit message is a note to your future self and your teammates. The diff shows *what* changed; the message explains *why*.

#### Format: Conventional Commits

```
type(scope): subject line (≤50 chars)

Body explaining WHY, not WHAT. The diff shows the what.
Wrap at 72 characters per line.

Refs: #1234
```

**Types:**
| Type | Meaning |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Build, CI, tooling changes |

**Good examples:**

```
feat(auth): add OAuth2 PKCE flow for SPA clients

Our SPA clients were using the implicit grant, which is deprecated
and vulnerable to token interception. PKCE is the recommended flow
for public clients per RFC 7636.

Refs: #1847, SEC-2026-003
```

```
fix(api): prevent race condition in order creation

Two concurrent requests for the same user could create duplicate
orders because we checked inventory and decremented it in separate
transactions. Wrapped both operations in a serializable transaction.

Fixes: #2103
```

```
perf(db): add composite index for user search

User search queries were doing sequential scans on the users table
(~800ms at current data volume). Added a composite index on
(organization_id, lower(email)) which brings it to ~3ms.
```

**Bad examples:**

```
fix stuff
```
```
WIP
```
```
address review comments
```
```
update user service
```

These messages are useless for `git log`, `git blame`, and `git bisect`. Six months from now, "fix stuff" tells you nothing.

#### Rules

- **Subject line: 50 characters max.** This is a hard limit — longer lines get truncated in `git log --oneline`.
- **Blank line** between subject and body.
- **Body: wrap at 72 characters.** This ensures readability in terminals and `git log`.
- **Reference issue numbers.** Use `Fixes #123` (auto-closes the issue) or `Refs: #123`.
- **One logical change per commit.** Do not mix a bug fix with a refactor.

### PR Descriptions

A PR description is a communication tool. It helps reviewers understand what they are looking at, why it exists, and what to pay attention to.

#### Template

```markdown
## What
Add rate limiting to the public API endpoints.

## Why
We had two incidents in the past month where a single client sent 50K
requests/minute, degrading service for all users. Rate limiting was
identified as an action item in postmortem PM-2026-008.

## How
- Added a token bucket rate limiter using Redis (lua script for atomicity)
- Default limit: 1000 req/min per API key, configurable per client
- Returns HTTP 429 with Retry-After header when limit is exceeded
- Added rate limit headers to all responses (X-RateLimit-Remaining, etc.)

## Testing
- Unit tests for the token bucket algorithm (edge cases: burst, refill)
- Integration tests against Redis (TestContainers)
- Load tested with k6: confirmed 429 responses at threshold
- Tested clock skew scenarios

## Risks / Review Focus
- The Lua script in `rate_limiter.lua` is the critical path — please
  review carefully for correctness
- Redis failure mode: currently fails open (allows requests). This is
  intentional — availability over rate limiting. Open to discussion.

## Checklist
- [x] Tests pass
- [x] No new warnings
- [x] Documentation updated (API docs, runbook)
- [x] Backwards compatible
- [ ] Load test results reviewed by SRE team
```

#### PR Description Tips

- **Link to the ticket/issue** so reviewers have full context.
- **Call out risky changes** that deserve extra scrutiny.
- **Include before/after screenshots** for any UI change.
- **Mention what you did NOT do** and why, if scope was intentionally limited.
- **Keep the description updated** if you push additional commits during review.

---

## 7. Runbooks & Operational Docs

A runbook is a step-by-step guide for responding to a specific operational event. It is written for the on-call engineer at 3 AM who is tired, stressed, and may not be familiar with this specific system.

### Runbook Structure

```markdown
# Runbook: High Error Rate on Order Service

## When to Use This Runbook
You received an alert: "order-service error rate > 5% for 5 minutes"
(PagerDuty alert: ORDER-ERR-RATE)

## Prerequisites
- Access to the `production` Kubernetes cluster (kubectl)
- Access to Grafana (https://grafana.internal.acme.com)
- Membership in #incident-response Slack channel

## Steps

### 1. Assess the Impact
Check the Grafana dashboard for current error rate and affected endpoints:
https://grafana.internal.acme.com/d/order-svc/overview

Look for: Which endpoints are erroring? Is it all traffic or a subset?

### 2. Check Recent Deployments
```bash
kubectl -n production rollout history deployment/order-service
```
If a deployment happened in the last 30 minutes, it is likely the cause.
Go to Step 5 (Rollback).

### 3. Check Database Connectivity
```bash
kubectl -n production exec -it deployment/order-service -- \
  pg_isready -h $DATABASE_HOST -p 5432
```
**If the database is unreachable:** Escalate to the Database team
(#db-oncall in Slack). This is not an application issue.

### 4. Check Application Logs
```bash
kubectl -n production logs deployment/order-service \
  --since=10m --tail=200 | grep ERROR
```
Look for: connection timeouts, OOM kills, panic/fatal messages.

### 5. Rollback (If Caused by Deployment)
```bash
kubectl -n production rollout undo deployment/order-service
```
**Verify rollback succeeded:**
```bash
kubectl -n production rollout status deployment/order-service
```
Wait 2 minutes, then check the error rate dashboard from Step 1.

### 6. Verification
Confirm the error rate has dropped below 1% on the Grafana dashboard.
Check that no new errors are appearing in the logs (Step 4).

## If Nothing Works / Escalation
- Page the Order Service tech lead: @alice (PagerDuty)
- Post in #incident-response with what you have tried
- If customer-facing impact > 15 minutes, initiate incident process
  (see: Incident Management Handbook)

## Rollback Plan
If the rollback in Step 5 makes things worse, re-deploy the previous
known-good version:
```bash
kubectl -n production set image deployment/order-service \
  order-service=acme/order-service:v2.3.7
```
(v2.3.7 is the last version confirmed stable as of 2026-03-01)
```

### Runbook Principles

- **Write for 3 AM.** Assume the reader is exhausted, stressed, and unfamiliar with this system. Use short sentences. Give exact commands.
- **Include exact commands,** not "run the deployment script." Copy-paste should work.
- **Every step has verification.** After each action, tell the reader how to confirm it worked.
- **Include escalation paths.** Who to contact if the runbook does not solve the problem.
- **Test runbooks regularly.** Run through them during game days. Stale runbooks are dangerous.
- **Store where people can find them.** Link from PagerDuty alerts directly to the relevant runbook. If the on-call engineer has to search for the runbook, you have already lost minutes.

---

## 8. Postmortem Reports

A postmortem (also called an incident review) documents what happened during an incident, why it happened, and what will be done to prevent recurrence. The primary purpose is organizational learning.

### Template

```markdown
# Postmortem: Order Processing Outage (2026-03-15)

## Summary
Order processing was unavailable for 73 minutes due to a database
connection pool exhaustion caused by a leaked connection in the
new bulk-import feature.

## Impact
- **Duration:** 14:22 UTC to 15:35 UTC (73 minutes)
- **Users affected:** ~2,400 users could not place orders
- **Revenue impact:** Estimated $18,000 in delayed orders
  (most completed after resolution, ~$3,200 lost)
- **Severity:** SEV-2

## Timeline (UTC)
| Time | Event |
|---|---|
| 13:45 | Bulk import feature deployed to production |
| 14:15 | Connection pool usage begins climbing (not yet alerting) |
| 14:22 | Alert fires: order-service error rate > 5% |
| 14:25 | On-call engineer Alice acknowledges the page |
| 14:30 | Alice identifies database connection errors in logs |
| 14:38 | Alice suspects the 13:45 deployment, begins rollback |
| 14:42 | Rollback complete, but connection pool still exhausted |
| 14:50 | Alice restarts order-service pods to reset connection pool |
| 14:55 | Connections recovering, error rate dropping |
| 15:05 | Error rate below 1%, orders processing normally |
| 15:35 | All queued orders processed, incident resolved |

## Root Cause
The bulk-import endpoint opened a database connection for each row
in the import file but did not release connections when a row failed
validation. A 10,000-row import with 3% validation failures leaked
~300 connections, exhausting the pool (max: 100, but cascading
retries amplified the problem).

The specific bug: the `importRow()` function used a `try` block
without a `finally` clause to release the connection. On validation
error, the function threw an exception and the connection was never
returned to the pool.

## Contributing Factors
- The bulk-import feature was not load-tested with invalid data
- Connection pool exhaustion alert threshold was set to 95%,
  which left insufficient time to react
- The connection pool had no per-query timeout, so leaked
  connections persisted indefinitely

## What Went Well
- Alert fired within 7 minutes of the problem starting
- On-call response was fast (3 minutes to acknowledge)
- Rollback process worked correctly
- Customer support was notified within 15 minutes

## What Went Wrong
- Rollback did not fix the issue because leaked connections
  persisted (required pod restart)
- No runbook for connection pool exhaustion — Alice had to
  diagnose from scratch
- The staging environment does not have connection pool limits,
  so the bug was not caught in testing

## Action Items
| Action | Owner | Deadline |
|---|---|---|
| Add `finally` block to release connections in importRow() | Bob | Done |
| Add connection pool exhaustion runbook | Alice | 2026-03-22 |
| Add per-query timeout (30s) to connection pool config | Carol | 2026-03-25 |
| Set up staging with production-equivalent pool limits | Dave | 2026-04-01 |
| Add load test for bulk import with invalid data | Bob | 2026-04-01 |
| Lower connection pool alert threshold to 80% | Alice | 2026-03-18 |

## Lessons Learned
1. Any feature that opens database connections in a loop needs
   explicit connection management review during code review.
2. Rollback does not fix stateful problems (leaked connections,
   corrupted data). Runbooks should include "restart" as a step
   after rollback when the service holds state.
3. Staging environments that differ from production in resource
   limits give false confidence.
```

### Postmortem Principles

- **Blameless.** Focus on systems, processes, and tools — not people. "Alice did not catch the bug" becomes "Our code review checklist does not include connection management." Blame prevents people from sharing information.
- **Publish broadly.** Share postmortems with the entire engineering organization. Transparency builds trust, and other teams learn from your incidents.
- **Follow up on action items.** Track them in your issue tracker. Review completion in team meetings. An action item that never gets done means you will have the same incident again.
- **Write the postmortem within 48 hours** while memories are fresh.

---

## 9. API Documentation

API documentation serves two audiences: developers evaluating whether to use your API, and developers actively building against it. Address both.

### Quick Start Section

Get a reader to a successful API call in 60 seconds:

```markdown
## Quick Start

### 1. Get an API key
Sign up at https://dashboard.acme.com and copy your API key
from Settings → API Keys.

### 2. Make your first request
```bash
curl https://api.acme.com/v2/orders \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 3. Response
```json
{
  "data": [
    {
      "id": "ord_abc123",
      "status": "fulfilled",
      "total_cents": 4999,
      "created_at": "2026-03-15T10:30:00Z"
    }
  ],
  "has_more": true,
  "next_cursor": "eyJpZCI6Im9yZF9hYmMxMjMifQ=="
}
```
```

### Endpoint Documentation

Every endpoint needs:

```markdown
### Create Order

`POST /v2/orders`

Creates a new order. The order will be in `pending` status until
payment is confirmed.

**Authentication:** Bearer token (API key or OAuth2 access token)

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array | yes | Line items (see below) |
| `currency` | string | no | ISO 4217 code. Default: `USD` |
| `metadata` | object | no | Arbitrary key-value pairs (max 50 keys) |

**Line Item:**
| Field | Type | Required | Description |
|---|---|---|---|
| `sku` | string | yes | Product SKU |
| `quantity` | integer | yes | Must be ≥ 1 |
| `price_cents` | integer | yes | Unit price in cents |

**Example Request:**
```bash
curl -X POST https://api.acme.com/v2/orders \
  -H "Authorization: Bearer sk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"sku": "WIDGET-01", "quantity": 2, "price_cents": 1999}
    ],
    "currency": "USD"
  }'
```

**Success Response:** `201 Created`
```json
{
  "id": "ord_xyz789",
  "status": "pending",
  "items": [...],
  "total_cents": 3998,
  "created_at": "2026-03-15T14:22:00Z"
}
```

**Error Responses:**
| Status | Code | Description |
|---|---|---|
| 400 | `invalid_request` | Missing required field or invalid format |
| 401 | `unauthorized` | Invalid or missing API key |
| 409 | `duplicate_order` | Idempotency key already used |
| 422 | `insufficient_inventory` | One or more items out of stock |
```

### Auto-Generation

Generate reference docs from code when possible:

- **OpenAPI/Swagger:** Define your API spec in `openapi.yaml`, generate docs with Swagger UI or Redoc.
- **GraphQL:** Schema introspection generates documentation automatically.
- **gRPC:** Protobuf definitions serve as the reference.

Auto-generation keeps documentation in sync with code. But auto-generated docs still need a hand-written quick start, authentication guide, and error reference.

### Error Reference

Document every error code your API returns, with cause and resolution:

| Error Code | HTTP Status | Cause | Resolution |
|---|---|---|---|
| `invalid_request` | 400 | Malformed JSON or missing field | Check request body against the schema |
| `unauthorized` | 401 | Bad or expired API key | Regenerate your key at dashboard.acme.com |
| `rate_limited` | 429 | Too many requests | Wait for the duration in `Retry-After` header |
| `internal_error` | 500 | Server-side failure | Retry with exponential backoff; contact support if persistent |

### Changelog

Document every breaking and notable change:

```markdown
## Changelog

### 2026-03-15
- **Breaking:** `GET /v2/orders` now requires `organization_id` parameter
- Added `metadata` field to order creation endpoint

### 2026-02-28
- Added `GET /v2/orders/:id/events` endpoint for order event history
- `status` field now includes `partially_fulfilled` value
```

---

## 10. Code Comments That Add Value

The best code is self-documenting through clear naming and structure. Comments should explain things the code *cannot* express: intent, context, trade-offs, and non-obvious behavior.

### Comment the WHY, Not the WHAT

The code shows what is happening. The comment should explain why.

**Bad — restates the code:**
```python
# Increment retry count by 1
retry_count += 1
```

**Bad — describes obvious logic:**
```python
# Check if user is admin
if user.role == "admin":
```

**Good — explains intent:**
```python
# Use insertion sort for small arrays — faster than quicksort under 16 elements
# due to lower constant factors and cache locality.
if len(arr) < 16:
    insertion_sort(arr)
```

**Good — explains a non-obvious constraint:**
```python
# Sleep 100ms between API calls to respect Stripe's rate limit of 100 req/sec.
# See: https://stripe.com/docs/rate-limits
time.sleep(0.1)
```

**Good — explains a workaround:**
```javascript
// HACK: Chrome 120 has a bug where ResizeObserver fires twice on initial
// render. Debounce with requestAnimationFrame to avoid double layout.
// Remove when Chrome 122+ is our minimum supported version.
// See: https://crbug.com/1234567
```

### TODO Comments

Include a ticket number and an owner. A TODO without a ticket is a wish, not a plan.

```python
# TODO(alice): #1234 Handle the case where the user has multiple orgs.
# Currently we assume one org per user, which is true for 99.8% of users
# but will break when we launch the enterprise tier in Q2.
```

A bare `// TODO: fix this later` is almost never fixed later. Attach a ticket so it shows up in sprint planning.

### Doc Comments for Public APIs

Every public function, class, and module should have a doc comment. This is the primary documentation most developers see.

**Python:**
```python
def calculate_shipping(
    items: list[OrderItem],
    destination: Address,
    method: ShippingMethod = ShippingMethod.STANDARD,
) -> ShippingQuote:
    """Calculate shipping cost for a list of items to a destination.

    Uses the carrier's rate API for real-time quotes. Falls back to
    flat-rate pricing if the carrier API is unavailable (see SHIPPING_FALLBACK
    in config).

    Args:
        items: Order items with weight and dimensions.
        destination: Shipping address. Must include postal code.
        method: Shipping speed. Default: STANDARD (5-7 business days).

    Returns:
        ShippingQuote with cost_cents, estimated_delivery, and carrier.

    Raises:
        InvalidAddressError: If the postal code is not recognized.
        OversizeItemError: If any item exceeds carrier dimension limits.
    """
```

**TypeScript:**
```typescript
/**
 * Retry an async operation with exponential backoff.
 *
 * @param fn - The async function to retry. Called with the attempt number (0-indexed).
 * @param options.maxAttempts - Maximum number of attempts (default: 3).
 * @param options.baseDelayMs - Initial delay in milliseconds (default: 1000).
 *   Doubles after each attempt: 1000, 2000, 4000...
 * @param options.shouldRetry - Predicate to determine if an error is retryable.
 *   Default: retries on all errors.
 * @returns The result of the first successful call to `fn`.
 * @throws The last error if all attempts fail.
 *
 * @example
 * const user = await retry(
 *   () => fetchUser(userId),
 *   { maxAttempts: 3, shouldRetry: (err) => err.status === 503 }
 * );
 */
```

### Architecture Comments

At the top of complex files or modules, explain the big picture:

```python
"""
Order State Machine

Orders move through these states:
  pending → confirmed → processing → shipped → delivered
                ↘ cancelled

State transitions are enforced by this module. No other code should
modify order.status directly. Each transition fires a domain event
(see events.py) consumed by the notification and analytics services.

Why a state machine instead of simple status updates:
- Prevents invalid transitions (e.g., shipped → pending)
- Centralizes business rules for each transition
- Domain events ensure downstream systems stay in sync

See ADR-0014 for the full decision record.
"""
```

### What Not to Comment

- **Commented-out code.** Delete it. Git remembers everything. Commented-out code rots, confuses readers, and creates merge conflicts.

```python
# Bad — delete this
# def old_calculate_tax(amount):
#     return amount * 0.08

# Good — just delete it. If you need it, `git log -p --all -S 'old_calculate_tax'` will find it.
```

- **Obvious code.** If a variable is named `user_email`, you do not need a comment saying "the user's email."
- **Changelog-style comments** ("Modified by Alice on 2026-01-15 to add validation"). That is what `git blame` is for.
- **Closing brace comments** (`} // end if`, `} // end for`). If your code is so nested that you need these, the code needs refactoring, not comments.

---

## Summary: The Documentation Checklist

Use this checklist when starting or joining a project:

| Document | Exists? | Up to Date? |
|---|---|---|
| README with quick start | | |
| Architecture overview (or ADRs) | | |
| API reference (auto-generated) | | |
| Runbooks for critical alerts | | |
| Onboarding guide for new developers | | |
| RFC/design doc for recent major decisions | | |
| Postmortem template in use | | |
| Contributing guide | | |

Documentation is not a separate activity from engineering — it is part of shipping. Code without documentation is a liability. Code with clear documentation is an asset that compounds over time.

---

**Key Takeaway:** Write the document you wish existed when you were the new person, the on-call engineer at 3 AM, or the developer trying to understand a decision made two years ago. Your future colleagues — and your future self — will thank you.
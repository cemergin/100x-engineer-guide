# L2-M59: Technical Writing for Engineers

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M58 (Debugging in Production)
>
> **Source:** Chapter 27 of the 100x Engineer Guide

## What You'll Learn

- How to write an RFC that gets approved without endless back-and-forth
- How to write a runbook that works at 3 AM
- How to write a blameless postmortem that prevents recurrence
- The Diataxis framework: four types of documentation, each for a different purpose
- Concrete templates you will fill in for TicketPulse

## Why This Matters

Code is how you talk to machines. Documentation is how you talk to other engineers -- including your future self. A well-written RFC prevents weeks of misaligned work. A good runbook saves hours during an incident. A clear postmortem prevents the same failure from happening twice.

Most engineers underinvest in writing because they think their job is writing code. But look at how senior engineers spend their time: RFC reviews, architecture discussions, incident reports, onboarding docs. The ability to write clearly and concisely is a career multiplier.

This module is not theoretical. You are going to write three real documents for TicketPulse.

## Prereq Check

You should have completed L2-M58 (Debugging in Production). You will write a postmortem based on the incident you debugged in that module.

Have a text editor ready. These exercises produce real documents, not code.

---

## Part 1: The RFC

### What an RFC Is (and Is Not)

An RFC (Request for Comments) is a proposal for a significant change. It forces you to think through a problem before writing code and gives others a structured way to provide input.

Write an RFC when:
- The work will take more than 2 engineer-weeks
- The change affects multiple services or teams
- The decision is difficult or expensive to reverse
- There are multiple viable approaches and the trade-offs are non-obvious

Do NOT write an RFC for routine bug fixes, small features, or changes contained within a single service.

### The Template

```markdown
# RFC: [Title]

**Author:** [Your name]
**Date:** [Today]
**Status:** Draft / In Review / Accepted / Rejected / Deferred
**Reviewers:** [Names and areas of expertise]

## TL;DR
[2-3 sentences. What are you proposing and why? A busy reader should
understand the proposal from this paragraph alone.]

## Problem
[What is broken, missing, or suboptimal? Use concrete evidence:
error rates, user complaints, performance numbers, operational burden.
Do not describe the solution here -- just the problem.]

## Context
[Relevant background. Current system state, constraints, related work.
What does the reader need to know to evaluate the proposal?]

## Proposed Solution
[Your recommended approach. Include architecture diagrams, API changes,
data model changes. Be specific enough that someone could implement
this without asking you questions.]

### Migration Plan
[If this changes existing behavior: how do you get from here to there?
Phases, backward compatibility, rollback plan.]

## Alternatives Considered
[At least 2 alternatives. For each: what it is, pros, cons, and why
you rejected it. This section is what reviewers scrutinize most.
If you cannot articulate why the alternatives are worse, you have
not thought deeply enough about the problem.]

## Open Questions
[What you have not figured out yet. Being explicit about unknowns
builds trust and focuses the review discussion.]

## Rollout Plan
[Timelines, milestones, how you will validate each phase.]
```

### 🛠️ Build: Write an RFC for TicketPulse

**Feature: Add a Waitlist When Events Sell Out**

Currently, when a TicketPulse event sells out, users see "Sold Out" and have no recourse. The feature request: let users join a waitlist. If tickets become available (cancellations, additional inventory), waitlisted users are notified in order.

Write a one-page RFC. Here is the problem statement to get you started:

```markdown
## Problem
When popular events sell out, TicketPulse loses potential revenue and
frustrates users. Our support team receives ~200 emails per month asking
"can you notify me if tickets become available?" We have no mechanism
for this. Competitors (Eventbrite, Ticketmaster) offer waitlist
functionality.

Based on event data from the past 6 months:
- 34% of events sell out
- Of sold-out events, 12% release additional inventory later
- Average time between sellout and new inventory: 3.2 days
```

Your RFC should address:

1. **Where does the waitlist data live?** New table? New service? Redis sorted set?
2. **How are users notified?** Email? Push notification? Both? How quickly?
3. **What happens when tickets become available?** First-come-first-served? Time-limited hold?
4. **How does this interact with the existing purchase flow?** Does the waitlist user get a reserved ticket, or do they compete with regular buyers?
5. **Scale considerations:** A popular artist could have 50,000 people on the waitlist. How does that affect notification delivery?

**Alternatives to consider:**
- Build waitlist into the existing purchase service vs. create a new waitlist service
- Notify all waitlisted users simultaneously vs. notify in batches (first in line first)
- Guarantee a ticket to notified users vs. give them a time-limited purchase window

### 🤔 Reflect: Pre-Address Reviewer Concerns

Before submitting your RFC, put on the reviewer's hat. What would a skeptical senior engineer push back on?

Common pushback patterns:
- "Why not use the simpler approach?" -- If you chose a complex solution, justify the complexity.
- "What happens if X fails?" -- Address failure modes explicitly.
- "How does this affect existing SLOs?" -- New features should not degrade existing performance.
- "What is the rollback plan?" -- If the feature causes problems, how do you turn it off?

Add a sentence or two to your RFC addressing the most likely pushback.

---

## Part 2: The Runbook

### What Makes a Good Runbook

A runbook is written for the on-call engineer at 3 AM. They are tired. They are stressed. They may not be familiar with this specific service. Your runbook must be:

- **Unambiguous.** Not "check the database" -- the exact `psql` command.
- **Step-by-step.** Each step has a clear action and a clear verification.
- **Copy-pasteable.** Every command should work when copied directly into a terminal.
- **Branching.** "If X, go to step Y. If not X, go to step Z."
- **Escalation-aware.** When should the reader stop and page someone else?

### The Template

```markdown
# Runbook: [Alert Name or Scenario]

## When to Use This Runbook
[Which alert triggers this? What symptoms does the reader observe?]

## Prerequisites
[Access needed: kubectl, database, Grafana, Slack channels]

## Steps

### 1. [First Action]
[Exact command or action]
```bash
[copy-pasteable command]
```
**Expected output:** [what success looks like]
**If this fails:** [what to do instead]

### 2. [Second Action]
...

## Escalation
[Who to page if the runbook does not resolve the issue.
Include names, PagerDuty schedules, Slack channels.]

## Rollback Plan
[If the fix makes things worse, how to undo it.]
```

### 🛠️ Build: Write the TicketPulse Purchase Failures Runbook

Write a runbook for the scenario from L2-M58: "TicketPulse purchase failures -- elevated error rate."

Your runbook should cover:

**Step 1: Assess Impact**
```markdown
### 1. Assess Impact
Open the Grafana purchases dashboard:
https://grafana.ticketpulse.dev/d/purchases/overview

Check the error rate panel. Note:
- Current error rate: ___% (normal: < 0.5%)
- Which endpoints are affected
- When the spike started (hover over the graph to find the inflection point)

**If error rate > 50%:** This is a major outage. Skip to Escalation immediately.
**If error rate 5-50%:** Continue to Step 2.
**If error rate < 5%:** Monitor for 10 minutes. If it stays below 5%, close the alert.
```

**Step 2: Check Recent Deployments**
```markdown
### 2. Check Recent Deployments
```bash
kubectl -n ticketpulse rollout history deployment/purchase-service
kubectl -n ticketpulse rollout history deployment/event-service
kubectl -n ticketpulse rollout history deployment/payment-service
```

**If a deployment happened in the last 60 minutes:**
```bash
# Roll back the most recently deployed service
kubectl -n ticketpulse rollout undo deployment/<service-name>

# Verify rollback completed
kubectl -n ticketpulse rollout status deployment/<service-name>
```
Wait 3 minutes, then re-check the error rate dashboard (Step 1).

**If no recent deployments:** Continue to Step 3.
```

Continue the runbook with steps for:

3. **Check Database Connectivity** -- exact commands to verify each database
4. **Check Application Logs** -- exact `kubectl logs` commands with `jq` filters
5. **Check Kafka Consumer Lag** -- exact commands to check consumer group status
6. **Check Connection Pool Status** -- Grafana panel or SQL query
7. **Verification** -- how to confirm the issue is resolved

Include the Escalation section:

```markdown
## Escalation
If the runbook does not resolve the issue within 30 minutes:
- Page the Purchase Service tech lead: @alice-chen (PagerDuty)
- Post in #ticketpulse-incidents with:
  - Current error rate
  - What you have tried (copy your incident timeline)
  - Which services are affected
- If customer-facing impact exceeds 30 minutes, notify customer support:
  #cs-urgent in Slack
```

**Key test:** Could a new hire who has never seen TicketPulse follow your runbook at 3 AM and resolve the incident? If not, add more detail.

### Runbook Anti-Patterns

Watch out for these mistakes in your runbook:

| Anti-Pattern | Example | Why It's Bad |
|---|---|---|
| **Vague commands** | "Check the database" | Which database? What query? What are you looking for? |
| **Missing verification** | "Restart the service" (no follow-up) | How do you know it worked? |
| **No branching** | Linear steps only | Real diagnosis requires if/then decisions |
| **Assuming knowledge** | "Use the usual monitoring" | The reader may be a new hire or from another team |
| **Missing escalation** | Steps end without a "what if none of this works?" | The reader is stuck with no next step |
| **Stale commands** | `kubectl` commands for old resource names | Test your runbook quarterly. Stale runbooks are dangerous |

### Runbook Testing

Runbooks rot faster than code. Schedule quarterly runbook reviews:

1. **Read-through**: Does every command still work? Have service names, endpoints, or dashboard URLs changed?
2. **Dry run**: Walk through the runbook on a staging environment. Time yourself. If it takes more than 30 minutes, the runbook needs simplification.
3. **Game day**: Inject a real failure and have someone unfamiliar with the system follow the runbook. Every place they get stuck reveals a gap.

```bash
# Add a reminder to your team's calendar:
# "Quarterly Runbook Review - TicketPulse"
# Assign a different team member each quarter
```

---

## Part 3: The Postmortem

### Blameless Postmortems

A postmortem documents what happened, why, and how to prevent recurrence. The most important word is **blameless**.

Blameless means:
- "Alice deployed the bad code" becomes "The code passed all CI checks and was deployed through the normal process. The CI pipeline did not include query plan analysis."
- "Bob should have caught the bug in review" becomes "The code review checklist does not include database query performance verification."
- Focus on **systems and processes**, not people. People make mistakes; the system should catch those mistakes.

Why blameless? If people fear blame, they will hide information. If the on-call engineer worries about being blamed for an outage, they will not share the full timeline. You need complete honesty to find the real root cause.

### The Template

```markdown
# Postmortem: [Incident Title] ([Date])

## Summary
[2-3 sentences. What happened, how long, what was the impact.]

## Impact
- **Duration:** [start time to resolution time]
- **Users affected:** [number and description]
- **Revenue impact:** [estimate if applicable]
- **Severity:** [SEV-1/2/3/4]

## Timeline (UTC)
| Time | Event |
|---|---|
| HH:MM | [Event description] |
| HH:MM | [Event description] |
| ... | ... |

## Root Cause
[Technical explanation of what went wrong. Be specific: which code,
which query, which configuration. Include enough detail that another
engineer could reproduce the issue.]

## Contributing Factors
[What made the root cause possible or made the incident worse?
Missing tests, insufficient monitoring, configuration drift, etc.]

## What Went Well
[What worked as expected during the incident? Fast detection?
Effective communication? Working runbooks?]

## What Went Wrong
[What failed or was missing? Gaps in monitoring, unclear runbooks,
slow escalation?]

## Action Items
| Action | Owner | Deadline | Status |
|---|---|---|---|
| [Specific, actionable item] | [Name] | [Date] | Open |
| ... | ... | ... | ... |
```

### 🛠️ Build: Write the Postmortem for the L2-M58 Incident

Using the incident timeline you built in L2-M58, write a full postmortem. This is the same incident: purchase failures caused by three layered problems (slow DB queries, stuck Kafka consumer, connection pool exhaustion).

Your postmortem should include:

**Summary:**
```markdown
## Summary
Ticket purchases were intermittently failing for approximately 43 minutes
due to a database query regression introduced in purchase-service v2.8.1.
The slow query caused cascading connection pool exhaustion. A concurrent
but independent issue (stuck Kafka consumer) delayed post-purchase
processing. 8.3% of purchase attempts failed during the incident window.
```

**Timeline:** Use your actual timeline from L2-M58.

**Root Cause:** Explain the missing index and why it only affected events with >1000 tickets.

**Contributing Factors:** Write at least three:
- The CI pipeline does not include query plan analysis
- Load tests use small event sizes (< 100 tickets)
- The Kafka consumer has no dead-letter queue for poison messages

**What Went Well:** Write at least three things.

**What Went Wrong:** Write at least three things.

**Action Items:** Write exactly five, with owners and deadlines:

```markdown
## Action Items
| Action | Owner | Deadline | Status |
|---|---|---|---|
| Add composite index on tickets(event_id, status) | [You] | [Today] | Done |
| Add EXPLAIN ANALYZE check to CI for migration files | [You] | [+1 week] | Open |
| Add DLQ for purchase-events Kafka consumer | [You] | [+1 week] | Open |
| Update load tests to include events with 10K+ tickets | [You] | [+2 weeks] | Open |
| Add slow query alert: queries > 500ms on event-service DB | [You] | [+3 days] | Open |
```

Each action item must be:
- **Specific**: not "improve monitoring" but "add alert for queries > 500ms"
- **Assigned**: one owner, not "the team"
- **Dated**: a concrete deadline
- **Tracked**: in your issue tracker, not just in the postmortem document

---

## Part 4: The Diataxis Framework

### Four Types of Documentation

The Diataxis framework organizes documentation into four types based on what the reader needs. Mixing types is the most common documentation mistake.

```
                 LEARNING                    WORKING
              (acquiring skill)          (applying skill)

PRACTICAL      Tutorial                  How-To Guide
               "Follow these steps       "Here's how to
                to learn X"               accomplish task Y"

THEORETICAL    Explanation               Reference
               "Here's why X             "Here are the exact
                works this way"           parameters for Y"
```

| Type | Reader's Goal | Example for TicketPulse |
|---|---|---|
| **Tutorial** | "I'm new and want to learn this" | "Getting started with TicketPulse development" |
| **How-To Guide** | "I need to accomplish task X" | "How to add a new Kafka consumer" |
| **Reference** | "What are the parameters for Y?" | "Purchase API endpoint reference" |
| **Explanation** | "Why does the system work this way?" | "Why TicketPulse uses CQRS for event listings" |

### Common Mistakes

**Mistake 1: Tutorial that stops to explain**

```markdown
# BAD: Tutorial with embedded explanation
Step 3: Run the migration.
```bash
npm run migrate
```
This works because migrations use a transaction log that tracks which
migrations have been applied. The migration runner reads the
`schema_migrations` table and compares it against the migration files
in the `migrations/` directory. It applies only the unapplied ones
in order. This is important because... [500 words of explanation]

Step 4: Start the server.
```

The reader is trying to get to a working system. They do not need to understand the migration engine right now. Save the explanation for an Explanation document. In the tutorial, just say:

```markdown
# GOOD: Tutorial stays focused on doing
Step 3: Run the migration.
```bash
npm run migrate
```
You should see output like: "Applied 3 migrations." If you see errors,
check that PostgreSQL is running (`docker ps`).

Step 4: Start the server.
```

**Mistake 2: Reference that tries to be a how-to**

```markdown
# BAD: Reference mixed with how-to
### POST /api/purchases

Creates a new ticket purchase.

First, make sure the user is authenticated (see the auth guide).
Then, check that the event has available tickets by calling
GET /api/events/:id first. Once you've confirmed availability...
```

Reference documentation should be terse and complete. The how-to for "purchasing a ticket" is a separate document.

```markdown
# GOOD: Pure reference
### POST /api/purchases

Creates a new ticket purchase.

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| eventId | string (UUID) | yes | Event to purchase tickets for |
| quantity | integer | yes | Number of tickets (1-10) |
| paymentMethodId | string | yes | Stripe payment method ID |

**Response:** 201 Created
**Errors:** 400 (validation), 402 (payment failed), 409 (insufficient tickets)
```

### 🤔 Reflect: What Documents Does TicketPulse Need?

Look at TicketPulse v2's documentation gaps. Prioritize the top three documents you would write next.

Consider:
- Does a new developer know how to set up the development environment? (Tutorial)
- Does an on-call engineer know how to respond to every alert? (How-To / Runbook)
- Are all API endpoints documented? (Reference)
- Does anyone know why CQRS was chosen for event listings? (Explanation / ADR)
- Is there a guide for adding a new microservice to the platform? (How-To)
- Are the Kafka topic schemas documented? (Reference)

Here is one way to prioritize:

| Document | Type | Priority | Reasoning |
|---|---|---|---|
| Dev environment setup | Tutorial | P0 | New engineers cannot contribute without this |
| Purchase failure runbook | How-To | P0 | On-call cannot respond to the most common incident |
| API endpoint reference | Reference | P1 | External consumers and frontend team need this |
| ADR: Why CQRS? | Explanation | P2 | Useful for understanding, but not blocking anyone |
| Adding a new service guide | How-To | P1 | Team will build more services; do not reinvent setup each time |
| Kafka topic schema reference | Reference | P1 | Consumers need to know the message format |

Prioritize ruthlessly. Write the P0 documents first. P2 documents are valuable but not urgent.

### Applying Diataxis to Existing Documents

Look at a document you have already written (an old README, a design doc, internal wiki page). Can you identify which Diataxis type it is? Does it mix types?

If it mixes types, consider splitting it. A README that starts as a tutorial, pivots into an explanation of the architecture, and ends with an API reference is hard to use because the reader has to search for the information they need. Three focused documents beat one unfocused one.

---

## Part 5: Writing Principles

### Lead with the Conclusion

Busy readers (your coworkers) may not finish your document. Put the most important information first.

**Bad:**
> We evaluated several approaches to the waitlist feature over the past two weeks, considering factors such as notification latency, database design, and integration with the existing purchase flow. After careful analysis and a review of competitor implementations, we concluded that we should build a dedicated waitlist service.

**Good:**
> We are building a dedicated waitlist service. It will notify users within 30 seconds of ticket availability, handle 50K waitlist entries per event, and integrate with the existing Kafka event stream.

### Concrete Over Abstract

Numbers, names, and examples beat adjectives.

| Abstract (avoid) | Concrete (prefer) |
|---|---|
| Performance degraded significantly | Latency increased from 50ms to 800ms at p99 |
| The service handles a large volume | The service processes 14,000 requests per second |
| There were some errors | 3.2% of requests returned HTTP 500 |
| The deployment took a long time | The deployment took 47 minutes |

### Write for 3 AM

For operational documents (runbooks, incident playbooks):
- Short sentences
- Exact commands (copy-pasteable)
- Clear branching ("if X, do Y; otherwise, do Z")
- Verification after every step
- Escalation paths when the runbook does not work

### The "So What?" Test

After writing each sentence, ask: "Why does the reader care?" If you cannot answer, cut or rewrite the sentence.

**Fails:** "The system uses a microservices architecture."
**Passes:** "The system uses a microservices architecture, so each team can deploy independently without coordinating release schedules."

---

## 🤔 Reflect

Answer these questions:

1. **Look at your RFC. Could a reviewer approve it based solely on what is written?** Or would they need to ask you clarifying questions? Every question they would ask is a gap in your RFC.
2. **Test your runbook.** Read it aloud, step by step. At each step, do you know exactly what to do? Is there any step where you would pause and think? That step needs more detail.
3. **Read your postmortem's action items.** Are they specific enough that someone could start working on them without asking you what you meant? "Improve monitoring" is not actionable. "Add alert for event-service DB queries > 500ms" is.
4. **Which type of Diataxis document do you find hardest to write?** Why?

---

## Checkpoint

Before moving on, verify:

- [ ] You wrote an RFC for the TicketPulse waitlist feature (problem, solution, alternatives, open questions, rollout plan)
- [ ] You wrote a runbook for purchase failures (step-by-step, exact commands, branching, escalation)
- [ ] You wrote a postmortem for the L2-M58 incident (timeline, root cause, contributing factors, 5 action items with owners and deadlines)
- [ ] You can identify which Diataxis type a document should be (tutorial, how-to, reference, explanation)
- [ ] Your documents follow the writing principles: lead with conclusion, concrete over abstract, active voice

---

## Key Terms

| Term | Definition |
|------|-----------|
| **RFC** | Request for Comments; a document proposing a technical design or change for team review before implementation. |
| **Runbook** | A step-by-step guide for handling a specific operational procedure or incident scenario. |
| **Postmortem** | A structured review conducted after an incident to document what happened, why, and how to prevent recurrence. |
| **Diataxis** | A documentation framework that classifies content into tutorials, how-to guides, explanations, and reference. |
| **Blameless** | An incident review culture that focuses on systemic improvements rather than assigning personal fault. |
| **Action item** | A concrete, assigned follow-up task resulting from a postmortem or review that prevents recurrence. |

## Further Reading

- Chapter 27 of the 100x Engineer Guide (Technical Writing & Documentation) for the full treatment
- [Diataxis Framework](https://diataxis.fr/) -- the original framework documentation
- [Google SRE Book: Chapter 15 - Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- [RFC 7322: RFC Style Guide](https://tools.ietf.org/html/rfc7322) -- how the internet's own RFCs are written

> **Going deeper:** **L2-M59a (Spec-Driven Development)** builds on everything here with contract-first API design (OpenAPI), event schema specs (AsyncAPI), and executable BDD specifications (Gherkin) — writing specs that machines can validate and AI agents can implement from.
>
> **Next up:** L2-M60 is the Loop 2 Capstone. You have gone from a monolith to a production-grade microservices platform. Time to prove it.

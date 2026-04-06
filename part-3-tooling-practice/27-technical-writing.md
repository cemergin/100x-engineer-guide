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

Here is the thing nobody tells you early enough: the best code in the world is useless if nobody understands it.

You can write the most elegant, performant, beautifully architected service your team has ever shipped — and it will still rot if the next engineer cannot figure out what it does, why it was built that way, or how to run it at 3 AM when things are on fire. Code without documentation is not an asset. It is a liability you are deferring to your future colleagues, your future self, and the poor on-call engineer who is about to have a very bad night.

This is not a soft skill. This is an engineering superpower.

The engineers who accelerate their careers fastest are not always the ones who write the cleanest code. They are the ones who can take a complex decision and explain it clearly in writing, who draft an RFC that aligns a team in days instead of weeks of meetings, who write a runbook so good that a junior engineer can resolve a production incident without waking anyone up. That is leverage. That is what it means to multiply your impact beyond your own working hours.

Think about the last time a clear document saved you an hour. Now think about how many times in a week you waste time because something was not documented at all. Documentation is one of the highest-ROI activities in software engineering, and most engineers treat it as an afterthought.

This chapter changes that. Every document type you need to write as an engineer — from a three-line commit message to a full RFC — has a craft to it. You will learn it here.

> **Career note:** This chapter connects directly to Ch 9 (engineering leadership) and Ch 29 (career engineering). Staff+ engineers are expected to drive alignment through writing. The ability to turn ambiguity into a clear, shared document is how you demonstrate you are operating at the next level.

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
- Ch 29 (career engineering and visibility)

---

## 1. Writing Principles for Engineers

Good engineering writing is not literary writing. It has nothing in common with a novel, an essay, or a blog post that wants to entertain you. Engineering writing is closer to a user interface: the goal is to transfer information from your head into the reader's head with the minimum possible friction.

Every principle below serves that one goal.

### Lead with the Conclusion

Engineers are trained to show their work — to walk through the problem, the analysis, the alternatives considered, and then arrive at the answer at the end. That is the right order for *thinking*. It is the wrong order for *writing*.

Readers are busy. They scan. They may not read past the second paragraph. If you bury your conclusion at the end, most of your audience will never reach it. Use the inverted pyramid: put the most important information first, then provide context and justification for those who need it.

**Terrible:**
> We evaluated several caching strategies over the past quarter, considering factors such as consistency requirements, operational complexity, and cost. After careful deliberation across three team meetings and a review of industry literature, we concluded that we should adopt Redis Cluster for our session store.

**Good:**
> We are adopting Redis Cluster for our session store. It meets our consistency requirements, has lower operational complexity than the alternatives, and reduces session lookup latency from 120ms to 8ms.

The first version makes you read a paragraph of process before you learn what decision was made. The second version tells you the decision in the first sentence, then justifies it. If you already agree, you can stop. If you want to understand the reasoning, it is right there. Nobody's time is wasted.

Apply this everywhere. In Slack messages. In email. In postmortems. In ADRs. Lead with the conclusion.

### One Idea per Paragraph

Each paragraph should communicate a single concept. If you find a paragraph doing two things — explaining a problem and proposing a solution — split it into two paragraphs. This discipline makes text scannable. It makes discussions precise ("I disagree with the point in your third paragraph"). It makes editing faster.

Here is a reliable test: can you summarize each paragraph in a single sentence? If you need two sentences to summarize one paragraph, the paragraph needs to be split.

### Active Voice over Passive

Active voice is shorter. It is clearer. It assigns responsibility. Passive voice hides the actor, which creates ambiguity exactly where you need precision.

| Passive (avoid) | Active (prefer) |
|---|---|
| An error is returned by the service | The service returns an error |
| The database was migrated by the platform team | The platform team migrated the database |
| The request will be retried automatically | The client retries the request automatically |
| Tests should be written before implementation | Write tests before implementation |

Passive voice is acceptable when the actor is genuinely unknown or irrelevant: "The server was provisioned in 2019." But when you know who did what, say so.

### Concrete over Abstract

Vague claims erode trust. Specific claims transfer information. Numbers, names, and examples beat adjectives every single time.

| Abstract (avoid) | Concrete (prefer) |
|---|---|
| Performance degraded significantly | Latency increased from 50ms to 800ms at p99 |
| The service handles a large volume of requests | The service processes 14,000 requests per second |
| The deployment took a long time | The deployment took 47 minutes |
| There were some errors | 3.2% of requests returned HTTP 500 |

The abstract versions create questions. The concrete versions create understanding. When you write "performance degraded significantly," every reader forms a different mental model of what that means. When you write "latency increased from 50ms to 800ms at p99," everyone is working from the same reality.

### Remove Filler Words

Filler words are words that take up space without contributing meaning. They are habits of speech that sneak into writing. Delete them:

- **very** — "very important" → "critical"
- **basically** — "it basically works by" → "it works by"
- **actually** — "it actually turns out" → "it turns out"
- **just** — "you just need to" → "you need to"
- **really** — "this is really useful" → "this is useful"
- **quite** — "quite a few errors" → "many errors" or "2,400 errors"
- **simply** — "simply run the command" → "run the command"

"Simply" deserves special attention. When you write "simply run the command" or "just set the environment variable," you are writing from the perspective of someone who already knows what they are doing. The reader who is struggling does not feel like it is simple. You create unnecessary friction. Delete the word.

### Use Lists and Tables for Structured Information

Do not bury parallel structured data inside prose paragraphs. Readers cannot extract it efficiently, and you make them do unnecessary cognitive work.

**Painful to read:**
> The service supports three authentication methods. The first is API keys, which are best for server-to-server communication. The second is OAuth2, which should be used for user-facing applications. The third is mutual TLS, which is required for inter-service communication in the production VPC.

**Good:**

| Method | Use Case |
|---|---|
| API keys | Server-to-server communication |
| OAuth2 | User-facing applications |
| Mutual TLS | Inter-service communication (production VPC) |

The table is faster to scan, easier to compare, and easier to update when you add a fourth method. Prose is great for narrative reasoning. Tables and lists are better for structured information.

### Write for Scanning

Most readers scan before they read. Your job is to make scanning productive: give readers enough information in headers and bold text that they can decide where to slow down and actually read.

- Use descriptive headers. Not "Overview" — say "How the billing pipeline works." Not "Details" — say "Why we chose PostgreSQL over DynamoDB."
- **Bold key terms** when they first appear.
- Put a TL;DR at the top of long documents.
- Keep paragraphs short (3-5 sentences). Dense paragraphs get skipped.
- Use code formatting for `function names`, `file paths`, and `commands`.

A document where every section header is a verb phrase telling you what you'll learn is infinitely more useful than one with abstract noun headers that tell you nothing until you read the content.

### The "So What?" Test

After writing each sentence or paragraph, ask: "Why does the reader care?" If you cannot answer that question immediately, the content needs revision.

**Fails the test:** "The system uses a microservices architecture."

So what? That sentence is a fact with no context. Why should the reader care?

**Passes the test:** "The system uses a microservices architecture, so each team can deploy independently without coordinating release schedules."

Now the reader knows the *consequence*. They understand why it matters. They can connect it to decisions they will need to make.

Apply this test ruthlessly. The engineering writing that survives it is writing that actually transfers knowledge.

---

## 2. The Diátaxis Framework

Here is the single most common documentation mistake teams make: they mix documentation types.

A developer opens the README looking for quick setup instructions and instead finds a thousand-word explanation of the system's design philosophy. A new hire tries to understand the architecture and ends up in a step-by-step tutorial. Someone needs the API parameters for a function and has to wade through a conceptual overview to find them.

The Diátaxis framework, developed by Daniele Procida, solves this by giving each type of documentation a clear purpose and telling you to keep them separate. The name comes from the Greek *dia* ("across") + *taxis* ("arrangement") — it is a map for organizing knowledge.

The framework divides documentation into four types based on a simple 2x2:

|  | Learning (acquiring skill) | Working (applying skill) |
|---|---|---|
| **Practical** | **Tutorial** | **How-To Guide** |
| **Theoretical** | **Explanation** | **Reference** |

This is not a bureaucratic taxonomy. It is a practical tool. Once you internalize it, you will immediately spot mixed-type documentation — and you will understand exactly why it is frustrating to read.

### Tutorials (Learning-Oriented)

**Purpose:** Get the reader to a working result through a guided, hands-on experience.

**What it is:** A tutorial is like a cooking class, not a recipe book. You are leading someone through a complete experience, step by step. You are responsible for their success. Every step should produce a visible result. The reader should feel accomplishment, not confusion.

**Characteristics:**
- Step-by-step instructions the reader follows exactly
- Assumes no prior knowledge of this specific system
- Focuses on *doing*, not *understanding* — save the why for Explanation docs
- Every step produces a visible, verifiable result
- Hand-holds through potential failure points explicitly

**Example opening:**
> In this tutorial, you will build a REST API that stores and retrieves user profiles. By the end, you will have a running service that handles CRUD operations with PostgreSQL. This takes about 30 minutes. You will need Node.js 20+ and Docker installed.

**The critical difference from a how-to guide:** Tutorials hold the reader's hand. They do not assume working knowledge. They check in: "You should see output like this." They explain what to do if something goes wrong.

**The most common mistake:** Stopping to explain why something works. In a tutorial, keep the reader moving. "Run this command" is fine. "Run this command — here is a 400-word explanation of what it does under the hood" breaks the momentum and overwhelms a beginner. Save the conceptual depth for an Explanation document. Link to it at the end.

---

**Great tutorial opening (concrete example):**

```markdown
# Tutorial: Your First API with Express and PostgreSQL

By the end of this tutorial, you will have a running API that stores
and retrieves users from a PostgreSQL database. We'll write three
endpoints, and you'll make your first successful request to each one.

Time: ~30 minutes
Prerequisites: Node.js 20+, Docker

## Step 1: Create the project

mkdir user-api && cd user-api
npm init -y
npm install express pg

You should see:
added 57 packages in 2.3s

✓ If you see this, you're ready for step 2.
✗ If npm fails, check that Node 20+ is installed: node --version
```

**Terrible tutorial opening (real example of what not to do):**

```markdown
# Getting Started with Our Authentication Service

Our authentication service is built on OAuth2, a widely-adopted
open standard for access delegation. OAuth2 was designed to address
the limitations of earlier authentication approaches by separating
the authorization server from the resource server. There are four
grant types: Authorization Code, Client Credentials, Resource Owner
Password, and Implicit (now deprecated). We use Authorization Code
with PKCE, which was introduced in RFC 7636...
```

Three paragraphs in and the reader has not done anything. They are already exhausted and may not even understand why the history of OAuth matters to them. A tutorial that opens with theory is not a tutorial.

### How-To Guides (Task-Oriented)

**Purpose:** Help a practitioner accomplish a specific task efficiently.

**What it is:** A how-to guide is a recipe. It assumes you already know how to cook. It does not explain what an oven is. It tells you what to do, in order, to get from where you are to where you want to be.

**Characteristics:**
- Problem-focused title: "How to deploy to production," "How to rotate API keys," "How to set up a local development environment"
- Assumes the reader has working knowledge of the system
- Direct and efficient — no hand-holding, no history, no theory
- May reference other docs for background, but does not reproduce them

**Example opening:**
> This guide covers deploying a new version to production using blue-green deployment. You need kubectl access to the production cluster and membership in the `deployers` GitHub team. If you do not have these, request access in #platform-ops.

Notice what is not there: no explanation of what blue-green deployment is, no history of how the process evolved, no tutorial on kubectl. If the reader needs those things, they should read the appropriate background material first. This guide is for someone who knows what they are doing and needs to do it right now.

**The most common mistake:** Turning a how-to guide into a tutorial by starting from scratch. If a reader needs fundamentals, link to the tutorial instead of reproducing it. Mixing tutorial content into a how-to guide makes both worse.

### Reference (Information-Oriented)

**Purpose:** Provide complete, accurate, structured information for lookup.

**What it is:** Reference documentation is like a dictionary or a map. Nobody reads it cover to cover. You go to exactly the entry you need, get the information, and leave.

**Characteristics:**
- Organized for fast lookup (alphabetical, by module, by endpoint)
- Exhaustive — covers every parameter, option, return value, and error code
- Consistent format across every entry (if one endpoint has a table, they all do)
- Generated from code when possible — this keeps it in sync automatically
- No opinions, no narrative, no "here is why we designed it this way" — just facts

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

Clean. Consistent. No narrative. If there is an `email` field, you know everything about it from this entry. You do not need to read anything else.

**The most common mistake:** Adding tutorial-style instructions or design rationale inside reference documentation. Keep it pure. The moment you start writing "here is how you would typically use this endpoint," you have left reference territory. That content belongs in a how-to guide or tutorial.

### Explanation (Understanding-Oriented)

**Purpose:** Deepen the reader's understanding of concepts, architecture, and decisions.

**What it is:** Explanation documents are for when someone wants to understand, not do. They answer "why does this exist?" and "how does this work conceptually?" They can include history, trade-offs, and context. They are allowed to be opinionated because they are about understanding, not action.

**Characteristics:**
- Answers "why" and "how does this work at a conceptual level"
- Discusses trade-offs, alternatives considered, and historical context
- Can explore multiple perspectives on a design question
- Written in a discursive, narrative style (this is the one type that resembles essay writing)
- Not tied to specific tasks — reading this should not make you feel like you missed the steps

**Example opening:**
> Our billing system uses event sourcing rather than traditional CRUD because billing data has strict auditability requirements. Every state change is captured as an immutable event, which means we can reconstruct the state of any account at any point in time. This was the key requirement from our finance team after the 2024 audit found inconsistencies in our balance calculations.

This is not a tutorial — no steps. Not a how-to — no task. Not reference — no table of parameters. It is pure understanding: why does this exist, and what does it mean for the reader's mental model?

**The most common mistake:** Trying to be both a tutorial and an explanation in the same document. If the reader needs to *do* something, write a tutorial. If they need to *understand* something, write an explanation. When you try to do both, you produce something that teaches neither.

### How to Identify What Type You Need

The simplest diagnostic: **"What is the reader trying to do right now?"**

| Reader's goal | Document type |
|---|---|
| "I'm new and want to learn this" | Tutorial |
| "I need to accomplish task X" | How-To Guide |
| "What are the parameters for function Y?" | Reference |
| "Why does the system work this way?" | Explanation |

When you write documentation, answer this question first. Write one type of document at a time. The Diátaxis framework's power is not in the taxonomy itself — it is in forcing you to be clear about what the reader needs before you write a single word.

> **Pro tip:** When a document tries to be all four types at once, it becomes the most common failure mode in engineering documentation: the "comprehensive overview" that nobody reads, everyone links to, and nobody finds useful. If you encounter one of these, the fix is to split it into four focused documents, each doing one job well.

---

## 3. READMEs That Actually Help

The README is the front door of your project. It is the first thing every new engineer, every potential contributor, and every future you will see when they land on your repository.

Apply the **30-second rule**: a new developer should be able to answer three questions within 30 seconds of opening your README:
1. What does this project do?
2. Is it relevant to what I need?
3. How do I get started?

If your README fails this test, you are creating friction for every single person who ever works with this project. Multiply that friction by the hundreds of times people will encounter this repository over its lifetime.

Here is what a README that passes the test looks like, section by section.

### Essential Sections (In Order)

#### 1. One-Sentence Description

State what the project is and what problem it solves. Not the technologies it uses. Not its history. What problem. What solution.

**Bad — leads with tech stack:**
> "A Node.js microservice using Express, PostgreSQL, and Redis."

This tells a developer what the project is built with. It does not tell them what it does or whether they should care.

**Good — leads with purpose:**
> "Order Processing Service — validates, charges, and fulfills customer orders from the web storefront."

In one sentence, you know what this service does, what business function it owns, and what system it connects to. A new engineer can immediately decide if this is the service they need.

#### 2. Quick Start

Get the reader to a running system in under 5 minutes. Copy-paste commands only. No explanation, no options, no "you might also want to" — those go in later sections. The quick start is about removing every obstacle between the reader and their first successful run.

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

The verification step at the end is not optional. Tell the reader exactly what success looks like. If they see something different, they know something went wrong. Without a verification step, engineers spend twenty minutes assuming everything is fine when the service never actually started.

#### 3. Prerequisites

List exact versions. "Recent version of Node" is not a prerequisite — it is a source of undetermined future pain.

```
- Node.js >= 20.11
- Docker >= 24.0
- PostgreSQL 16 (runs in Docker by default)
- Redis 7+ (runs in Docker by default)
```

If something can be handled automatically (like PostgreSQL running in Docker), say so. Remove anxiety. Engineers should not have to guess what "built with PostgreSQL" means for their local setup.

#### 4. Installation / Setup

Expand on quick start for edge cases: which environment variables need to be set and what they do, database seeds or migrations to run, external services that need to exist (like a Stripe account for payment testing), and platform-specific setup (Mac vs. Linux vs. Windows differences).

#### 5. Usage Examples

Show the three to five most common operations. These are the things that 80% of users will want to do 80% of the time. Pick those, not the exhaustive list.

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

Each example should work as written. Test them when you write them. Test them again when you change the API.

#### 6. Configuration

Document every environment variable. Every single one. The developer who needs to deploy this in a new environment should not have to search through the source code to discover what configuration is needed.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | PostgreSQL connection string |
| `REDIS_URL` | no | `redis://localhost:6379` | Redis connection for caching |
| `STRIPE_SECRET_KEY` | yes | — | Stripe API key for payments |
| `LOG_LEVEL` | no | `info` | One of: debug, info, warn, error |

Required vs. optional. Default values. What the variable does. The developer who hits a missing configuration error at 10 PM on a Friday will be extremely grateful for this table.

#### 7. Architecture Overview

For non-trivial projects, add a short paragraph or a diagram showing the major components and how they connect. This is the Explanation-type documentation from the Diátaxis framework: not a tutorial, not reference — just enough context that a new engineer understands what they are working with before they dive in.

#### 8. Contributing Guide

Link to `CONTRIBUTING.md` or provide inline instructions: branch naming conventions, test requirements, PR process, and anything a first-time contributor needs to know before they open a PR. Reduce the friction for contributions.

#### 9. License

State the license. For internal projects, state "Internal — proprietary." For open source, use a standard SPDX identifier. For projects with multiple licenses (code vs. documentation, for example), explain each.

### README Anti-Patterns

- **Wall of text with no headers or formatting.** No one reads this. Not even you, three months from now.
- **Outdated instructions that no longer work.** This is worse than no documentation — it wastes the reader's time and destroys trust. Test your README quarterly. Set a calendar reminder.
- **No quick start.** The reader has to read 500 lines before they can run anything. They will not. They will either ask someone or give up.
- **Auto-generated boilerplate that was never customized.** The default Create React App README. The default GitHub repository template. These tell the reader you do not care about their experience.
- **Badges as content.** Twelve status badges and a build-passing indicator, but no description of what the project does. Badges are decoration. They do not replace information.
- **"See the wiki."** The wiki is always out of date. It is a graveyard of documentation that was accurate in 2023. Keep essential information in the README, version-controlled alongside the code.

### The README as a Living Document

A README that nobody maintains is worse than a README that does not exist, because it actively misleads people. Assign README maintenance as part of your team's definition of done for significant features. When you change an API, update the README. When you add a new environment variable, add it to the configuration table. When the setup process changes, update the quick start.

The best teams treat the README as code: reviewed in PRs, tested in CI (you can lint markdown and even run the quick start commands in a CI job), and kept in sync with the system it describes.

---

## 4. Architecture Decision Records (ADRs)

> **Deeper coverage:** For a more detailed treatment of ADRs alongside RFCs, contract-first API design (OpenAPI/AsyncAPI), executable specs (BDD/Gherkin), and AI-native specifications, see **Chapter 34: Spec-Driven Development**.

Let me tell you about a failure mode that happens in almost every engineering team.

A team debates a technology choice for two weeks. They consider three options, read benchmarks, argue about operational complexity, and finally converge on PostgreSQL. The decision is made. Everyone moves on.

Eighteen months later, a new engineer joins. They read a blog post about MongoDB's horizontal scaling capabilities. They bring it up in a planning meeting. And the whole debate happens again — same arguments, same data, same conclusion. Two engineer-days of experienced people's time, wasted. Then it happens again two years after that.

This is not a hypothetical. This happens constantly in software teams. The exact same debates, recycled endlessly, because nobody wrote down why the decision was made the first time.

An **Architecture Decision Record** (ADR) is the fix. An ADR is a short document — one or two pages — that captures a single architectural decision: what was decided, why, and what the consequences are. The format was formalized by Michael Nygard, and it has spread through the industry because it solves a real and painful problem.

As Ch 9 explains, the purpose of decision documentation is not bureaucracy. It is to let your team think forward instead of in circles. When you can point a new engineer to ADR-0023 and say "read this to understand why we use PostgreSQL and what we would need to change for that decision to be revisited," you save both the debate and the relationship.

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

The "Consequences — Negative" section is the most important part. When you write down what gets harder as a result of your decision, you build honesty into the process. You are not selling a choice — you are documenting it with its full reality. That honesty is what makes ADRs useful six months or two years later: a future engineer can read it, see the constraints that led to the decision, and evaluate whether those constraints have changed.

### Key Practices

- **Store alongside code, not in a wiki.** Put them in `docs/adr/0001-use-postgresql.md`. ADRs that live in Confluence or a wiki get lost, go stale, and accumulate the smell of abandoned documentation. Keeping them in the repository means they get reviewed in PRs, they change when the code changes, and they never silently drift from reality.
- **Never delete ADRs.** If a decision is reversed, write a new ADR that supersedes the old one and update the original's status to "Superseded by ADR-0042." The history of your decisions is as valuable as the decisions themselves.
- **Number sequentially.** The number is an identifier, not a priority ranking. ADR-0001 is not more important than ADR-0047.
- **Keep them short.** One page is ideal. If you need more, you are writing an RFC (see the next section). An ADR that is five pages long will not be read.
- **Write them before the decision is made.** The forcing function of writing down the context and consequences often reveals weaknesses in decisions that seemed obvious in a whiteboard session. An ADR draft is a useful review artifact — share it with skeptics.

### The ADR That Is Too Vague to Be Useful

Here is what a bad ADR looks like:

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

This ADR captures a decision without capturing any of the reasoning that made the decision meaningful. Six months later, nobody knows why PostgreSQL was chosen over DynamoDB or MySQL. Nobody knows what the query patterns were. Nobody knows whether the "5+ years of team expertise" rationale still applies after two team transitions. The ADR exists, but it has preserved nothing worth knowing.

The test for a good ADR: could a thoughtful engineer who was not in the room read this document and understand *why* this decision made sense at the time, and what it would take to revisit it? If yes, you have written a good ADR.

### ADRs as Career Leverage

Here is the thing most engineers miss: writing ADRs is also how you demonstrate Staff-level thinking. When you write a clear ADR — one that articulates the problem space, lays out alternatives with honest trade-offs, and explains the decision with its consequences — you show that you understand the system at an architectural level and that you can think clearly in writing.

> **Cross-reference Ch 29:** Staff and Principal engineers are expected to leave a trail of good decisions that the organization can learn from. ADRs are that trail. If your team does not use ADRs, introducing them is itself a Staff-level contribution.

---

## 5. RFCs & Design Documents

An RFC (Request for Comments) is a proposal for a significant change. The original RFC format was used to design the internet — literally, the protocols that define how computers communicate were designed through RFCs. The engineering industry borrowed the format because it solves a universal problem: how do you build consensus on a complex technical decision before writing a lot of code?

The answer is: you write it down first.

An RFC forces the author to think through a problem before writing code. It gives stakeholders a structured opportunity to provide input. It surfaces concerns early — before the cost of changing course is high. A well-written RFC can prevent weeks of misaligned implementation work and months of technical debt.

Here is a concrete way to think about the value: an RFC takes an engineer a day or two to write. If it surfaces a fundamental design problem that would have taken two engineers three weeks to discover in code review, the RFC had a 30x ROI. That is not unusual.

### When to Write an RFC

Write an RFC when any of these apply:
- The work will take more than 2 engineer-weeks
- The change affects multiple teams or services
- The decision is difficult or expensive to reverse
- There are multiple viable approaches and the trade-offs are non-obvious

Do **not** write an RFC for routine work, small bug fixes, or changes contained within a single team's codebase that will not affect downstream consumers. An RFC is a tool for large, consequential decisions — treating every change as RFC-worthy creates process overhead that kills team velocity.

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

Notice what the "Alternatives Considered" section does. It does not just list alternatives — it explains why each was rejected, in specific terms. This prevents your review period from being derailed by someone suggesting an alternative you already considered. It demonstrates that you have done the research. And it gives future engineers the same information you have when they revisit the decision.

### RFC Process

1. **Author writes the RFC** and identifies 3-5 reviewers. Include at least one skeptic — the most valuable reviewer is the one most likely to find the problems you missed.
2. **Review period: 1 week.** Reviewers leave comments directly on the document. Async by default.
3. **Author addresses all comments** — either by updating the RFC or explaining in writing why the feedback was not incorporated. Every comment deserves a response.
4. **Author makes the decision.** An RFC is not a vote. The author owns the decision and is accountable for the outcome. Consensus is great when it happens naturally. But waiting for perfect consensus on a complex decision is how teams never ship.
5. **Status updated** to Accepted, Rejected, or Deferred, with a brief explanation.

### Design Doc vs. RFC

A design doc is more detailed and implementation-focused. Think of the RFC as answering "should we do this, and at a high level, how?" and the design doc as answering "here is exactly how we will build it."

In practice, many organizations use these as a single document: the RFC gets accepted, and then the author extends it with implementation details. The "In Review" version is the RFC. The "Accepted + extended" version is the design doc. Use whatever format works for your team — the key is that the document exists before the implementation begins, not after.

### RFCs as Communication Superpowers

An RFC does something remarkable: it turns a technical decision from a whiteboard conversation into a written record that the whole team can engage with asynchronously. Engineers who were in meetings can leave detailed feedback. Engineers in other timezones can participate. Engineers who were not invited to the whiteboard session can catch problems before they are baked into code.

> **Cross-reference Ch 9:** Engineering leadership is largely about writing. The ability to write an RFC that builds alignment on a complex technical question — without requiring a two-hour meeting — is one of the highest-leverage skills a senior or staff engineer can develop. If your organization does not use RFCs, proposing and leading the introduction of the practice is itself a demonstration of technical leadership.

---

## 6. Commit Messages & PR Descriptions

### Commit Messages

A commit message is a note to your future self and your teammates. The diff shows *what* changed. The message explains *why*.

This distinction matters more than it might seem. You can always recover the "what" from the diff — git stores it forever. But the "why" — the reasoning behind the change, the bug it was fixing, the context that made this approach the right one — that lives only in the commit message. Lose it there and it is lost forever.

Think about how you actually use `git log` in practice. You are looking at a file that was behaving correctly six months ago and is now broken. You run `git blame`. You find the commit. You read the message. If that message says "fix stuff," you learn nothing. If it says "fix: prevent race condition in order creation — see #2103," you have a thread to pull.

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

#### Good Commit Messages (Study These)

```
feat(auth): add OAuth2 PKCE flow for SPA clients

Our SPA clients were using the implicit grant, which is deprecated
and vulnerable to token interception. PKCE is the recommended flow
for public clients per RFC 7636.

Refs: #1847, SEC-2026-003
```

This message tells you: what changed (PKCE flow), why (security vulnerability with implicit grant), and where to learn more (RFC 7636, ticket 1847, security issue SEC-2026-003). Six months from now, an engineer who hits a question about the auth flow has everything they need.

```
fix(api): prevent race condition in order creation

Two concurrent requests for the same user could create duplicate
orders because we checked inventory and decremented it in separate
transactions. Wrapped both operations in a serializable transaction.

Fixes: #2103
```

The body explains the bug, why it happened (separate transactions), and what the fix was (serializable transaction). No diff-reading required to understand the change.

```
perf(db): add composite index for user search

User search queries were doing sequential scans on the users table
(~800ms at current data volume). Added a composite index on
(organization_id, lower(email)) which brings it to ~3ms.
```

Numbers. Before and after. The "why" is in the numbers: 800ms → 3ms is self-evidently worth a composite index. No explanation needed beyond the data.

#### Bad Commit Messages (Do Not Write These)

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
```
asdf
```

These messages are useless for `git log`, `git blame`, and `git bisect`. They are especially damaging in `git bisect`, where you are trying to find which commit introduced a bug: "fix stuff" tells you nothing about whether this commit is a candidate. "fix(auth): prevent session fixation on login" tells you it is probably not relevant to a database bug.

Six months from now, "fix stuff" tells you nothing. The three extra minutes required to write a real commit message will save hours of future archaeology.

#### Rules

- **Subject line: 50 characters max.** This is a hard limit — longer lines get truncated in `git log --oneline` and in GitHub's commit list. Count them.
- **Blank line** between subject and body. Without it, many git tools treat everything as the subject.
- **Body: wrap at 72 characters.** This ensures readability in terminals and `git log`. Most editors have a ruler for this.
- **Reference issue numbers.** Use `Fixes #123` (auto-closes the issue on merge) or `Refs: #123` (links without closing).
- **One logical change per commit.** Do not mix a bug fix with a refactor. Atomic commits make `git bisect` useful and make PR reviews easier.

### PR Descriptions

A PR description is a communication tool. It is not a formality. It helps reviewers understand what they are looking at, why it exists, and what deserves the most scrutiny. A well-written PR description is a gift to your reviewers — it reduces the cognitive overhead of the review and often catches problems the author missed, because writing the description forces you to explain your reasoning.

The best PR descriptions I have read are ones where the author says "here is the thing I am not sure about, please look carefully here." That honesty gets better reviews and ships better code.

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

- **Link to the ticket/issue** so reviewers have full context without searching. One line: "Fixes #1234" or "Implements the RFC: [link]."
- **Call out risky changes** that deserve extra scrutiny. If you are not sure about a section, say so. Your reviewer will not know you are worried about it unless you tell them.
- **Include before/after screenshots** for any UI change. Even for small visual changes — "looks the same" is a useful verification.
- **Mention what you did NOT do** and why, if scope was intentionally limited. "I did not add caching in this PR because it requires coordination with the platform team — tracked in #1456."
- **Keep the description updated** if you push additional commits during review. If the approach changed significantly, rewrite the description.

The habit of writing thorough PR descriptions also makes you a better engineer. It forces you to articulate what you built and why. If you cannot explain the PR clearly in writing, there is a reasonable chance you do not fully understand it yet.

---

## 7. Runbooks & Operational Docs

A runbook is a step-by-step guide for responding to a specific operational event.

Here is the context you need to write a good one: picture an on-call engineer at 3 AM. They have just been paged out of sleep. They are tired, stressed, and they may not be the engineer who owns this service. They have no whiteboard. They may not have a rubber duck. They have a laptop, a pager, and a growing pressure to fix this before it affects more users.

That is your reader. Write for them.

Every decision you make while writing a runbook should be filtered through this lens: "Will this be clear and actionable for someone who is exhausted, stressed, and unfamiliar with this specific service?" If the answer is no, rewrite it.

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

### What Makes This Runbook Work

Notice the things this runbook does that so many runbooks do not:

**Every step includes a verification.** After each action, the runbook tells the on-call engineer how to confirm it worked. Without this, the engineer might move to step 3 while the outcome of step 2 is still unknown. That creates cascading uncertainty that makes incidents longer.

**Branching logic is explicit.** "If a deployment happened in the last 30 minutes, go to Step 5." The on-call engineer does not have to reason through the decision tree at 3 AM. It is already reasoned for them.

**Escalation paths are named.** Not "contact the database team" — "#db-oncall in Slack." Not "get help" — "Page @alice on PagerDuty." The on-call engineer should never have to figure out who to call.

**The fallback version is specified.** "v2.3.7 is the last version confirmed stable as of 2026-03-01." When the rollback does not fix it and you need to deploy a known-good version, you have the version number right there.

### Runbook Principles

- **Write for 3 AM.** Assume the reader is exhausted, stressed, and unfamiliar with this system. Use short sentences. Give exact commands.
- **Include exact commands,** not "run the deployment script." Commands should be copy-paste ready. Every variable that needs to be substituted should be explicitly marked.
- **Every step has verification.** After each action, tell the reader exactly what success looks like.
- **Include escalation paths.** Who to contact, how to contact them, and when to escalate. Do not make a stressed engineer search for this.
- **Test runbooks regularly.** Run through them during game days and chaos engineering exercises. A runbook that has never been tested under realistic conditions is an untested hypothesis.
- **Store where people can find them.** Link from PagerDuty alerts directly to the relevant runbook. If the on-call engineer has to search for the runbook during an incident, you have already burned minutes that matter.

### The Runbook You Write After Every Incident

Here is a practice that turns incidents into organizational capability: after every significant incident, if you had to do anything that is not covered by a runbook, write a new one. If you had to diagnose something in a way the existing runbook did not cover, update it.

Over time, your runbooks become the accumulated knowledge of every incident your team has ever resolved. A new on-call engineer in year three of a service has the benefit of every hard-won lesson from the previous three years. That is compounding value.

---

## 8. Postmortem Reports

A postmortem (also called an incident review or post-incident analysis) documents what happened during an incident, why it happened, and what the team will do to prevent recurrence.

Here is the critical thing to understand about postmortems: their primary purpose is not to document the incident. It is to create organizational learning. A postmortem that accurately documents what happened but produces no action items is interesting history. A postmortem that produces three clear action items that prevent the next incident is an engineering investment with measurable return.

Write postmortems as if they are letters to your future self and your future teammates, explaining what broke, what was hard about fixing it, and what you changed so that it does not happen the same way again.

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

### What Makes This Postmortem Work

The timeline is the most underrated section. A precise timeline — in UTC, to the minute — does several things: it makes the sequence of events unambiguous, it reveals gaps (why did it take 8 minutes to suspect the deployment after the rollback was complete?), and it gives future engineers a template for incident timelines.

The "Contributing Factors" section is not root cause analysis. It is asking: even if the immediate cause is fixed, what conditions allowed this to happen? Fixing the `finally` clause prevents *this* bug. Setting up staging with production-equivalent limits prevents a whole category of future bugs. The action items should address both.

The "What Went Well" section is not feel-good padding. It is diagnostic information. It tells you what parts of your incident response process are working and should be preserved. If the alert fired quickly and response time was fast, that is worth acknowledging explicitly — so you do not accidentally "improve" the alerting system in a way that breaks what is already working.

### Postmortem Principles

- **Blameless.** Focus on systems, processes, and tools — not people. "Alice did not catch the bug" becomes "Our code review checklist does not include connection management." Blame prevents honesty. Honesty is the only thing that produces learning. If the people involved in an incident are worried about being blamed for it, they will be careful about what they share in the postmortem — and you will lose the most important information.
- **Publish broadly.** Share postmortems with the entire engineering organization. Not just the team that was involved. Other teams are running similar systems and will recognize the same failure modes. Broad transparency builds trust and multiplies the learning.
- **Follow up on action items.** Track them in your issue tracker. Review completion in team meetings. An action item without a deadline and an owner is not an action item — it is a wish. An action item that never gets done means the next incident is more likely to happen the same way.
- **Write the postmortem within 48 hours** while memories are fresh. Every day that passes, details blur and humans naturally construct more favorable narratives about their own decisions under pressure. Write it fast, write it accurately.

### The Blameless Culture Dividend

Teams that write genuinely blameless postmortems — where the goal is learning, not accountability — build a culture where engineers report problems quickly, share information during incidents, and propose systemic improvements without fear of career consequences. Teams that use postmortems as accountability mechanisms build a culture where people hide problems, cover for each other, and speak carefully in incident reviews.

The engineering output of the two cultures is dramatically different. Blamelessness is not softness — it is engineering pragmatism.

---

## 9. API Documentation

API documentation serves two distinct audiences at once: developers evaluating whether to use your API, and developers actively building against it. These audiences have different needs, and good API documentation serves both.

The developer evaluating your API asks: "Does this do what I need? Is it easy to use? Can I trust it?" Answer these questions in your overview, quick start, and error reference.

The developer building against your API asks: "What are the exact parameters? What does this error mean? What does the response look like?" Answer these questions in your endpoint reference.

### Quick Start Section

Get a reader to a successful API call in under 60 seconds:

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

The 60-second quick start is not about comprehensiveness. It is about giving the evaluating developer a real response in their terminal so they know the API works and can feel how it behaves. Everything after this can be reference material — but the quick start is the hook.

### Endpoint Documentation

Every endpoint needs all of this. Every one. Inconsistency in API documentation is a failure mode — developers start guessing about the endpoints that are less complete.

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

The example request is not optional. It is the most useful part. Developers read the table of parameters and then look at the example to see how they fit together. The example is where abstract documentation becomes concrete understanding.

### Auto-Generation

Generate reference docs from code when possible:

- **OpenAPI/Swagger:** Define your API spec in `openapi.yaml`, generate docs with Swagger UI or Redoc. Changes to the spec immediately reflect in the documentation.
- **GraphQL:** Schema introspection generates documentation automatically. Tools like GraphiQL make the schema explorable.
- **gRPC:** Protobuf definitions serve as the reference, and tools like `protoc-gen-doc` generate readable documentation.

Auto-generation keeps documentation in sync with code. When the API changes and the documentation is generated from the same source, the documentation cannot be out of date. But auto-generated docs still need human-written sections: a quick start, an authentication guide, an error reference with resolution guidance, and conceptual overviews of how the API is designed to be used. The generation handles the exhaustive detail; the human writing handles the understanding.

### Error Reference

Every error code your API can return, documented with its cause and how to resolve it. Developers spend a disproportionate amount of time dealing with errors. A good error reference turns hours of debugging into minutes.

| Error Code | HTTP Status | Cause | Resolution |
|---|---|---|---|
| `invalid_request` | 400 | Malformed JSON or missing field | Check request body against the schema |
| `unauthorized` | 401 | Bad or expired API key | Regenerate your key at dashboard.acme.com |
| `rate_limited` | 429 | Too many requests | Wait for the duration in `Retry-After` header |
| `internal_error` | 500 | Server-side failure | Retry with exponential backoff; contact support if persistent |

The Resolution column is what separates useful error documentation from the default behavior: a 401 that says "Invalid or missing API key" tells the developer what went wrong. One that says "Regenerate your key at dashboard.acme.com" tells the developer what to do about it. That sentence prevents a support ticket.

### Changelog

Document every breaking and notable change. API users need to know what changed so they can plan updates.

```markdown
## Changelog

### 2026-03-15
- **Breaking:** `GET /v2/orders` now requires `organization_id` parameter
- Added `metadata` field to order creation endpoint

### 2026-02-28
- Added `GET /v2/orders/:id/events` endpoint for order event history
- `status` field now includes `partially_fulfilled` value
```

Mark breaking changes clearly. Breaking changes without explicit marking are how you end up with angry enterprise customers whose integrations silently broke after an upgrade.

---

## 10. Code Comments That Add Value

The best code is self-documenting through clear naming and structure. Good variable names, clear function names, and sensible organization eliminate the need for most comments. When code is clear, comments add noise — they are things the reader has to read to discover they already knew.

But some things cannot be expressed in code. The context of a decision. The reason for a non-obvious approach. The constraint that made the obvious approach wrong. These are things that comments must carry — and failing to document them creates exactly the kind of archaeological nightmare that wastes engineering hours and confuses future readers.

The rule: **Comments should explain what the code cannot express.** Intent, context, trade-offs, and non-obvious behavior.

### Comment the WHY, Not the WHAT

The code shows what is happening. The comment should explain why.

**Comments that restate the code (useless):**
```python
# Increment retry count by 1
retry_count += 1
```

```python
# Check if user is admin
if user.role == "admin":
```

These comments make the code longer without making it clearer. Anyone who can read the code can see what it does. The comment provides no additional information.

**Comments that explain intent (valuable):**
```python
# Use insertion sort for small arrays — faster than quicksort under 16 elements
# due to lower constant factors and cache locality.
if len(arr) < 16:
    insertion_sort(arr)
```

The code says "if the array is small, use insertion sort." The comment explains *why* the threshold is 16 and what property of insertion sort makes this trade-off correct. A reader who does not know this could reasonably wonder "why not quicksort always?" The comment answers before the question forms.

**Comments that explain non-obvious constraints (valuable):**
```python
# Sleep 100ms between API calls to respect Stripe's rate limit of 100 req/sec.
# See: https://stripe.com/docs/rate-limits
time.sleep(0.1)
```

Without this comment, the next engineer looks at `time.sleep(0.1)` and wonders if it was a performance optimization, a bug, or a temporary hack. With the comment, they know exactly what this is and can verify the constraint if it ever needs to change.

**Comments that explain workarounds (valuable):**
```javascript
// HACK: Chrome 120 has a bug where ResizeObserver fires twice on initial
// render. Debounce with requestAnimationFrame to avoid double layout.
// Remove when Chrome 122+ is our minimum supported version.
// See: https://crbug.com/1234567
```

This comment does everything right: it explains the reason for the hack (Chrome bug), the specific symptom it fixes (double fire on initial render), the specific fix applied (requestAnimationFrame debounce), and most importantly, the condition under which this code should be removed. Without it, this is mysterious code that will live forever because nobody knows what it does or whether it still matters.

### TODO Comments

Include a ticket number and an owner. A TODO without either is a wish, not a plan.

```python
# TODO(alice): #1234 Handle the case where the user has multiple orgs.
# Currently we assume one org per user, which is true for 99.8% of users
# but will break when we launch the enterprise tier in Q2.
```

A bare `// TODO: fix this later` will not be fixed later. There is no ticket. There is no owner. It will rot in the codebase for years, slightly radioactive, neither removed nor acted upon. Attach a ticket number and it shows up in sprint planning. Attach an owner and someone is responsible for it.

The best TODOs also explain the *nature* of the gap: "Currently we assume one org per user." A new engineer reading this code now knows the assumption and knows it will need to change. That context is worth more than the ticket number.

### Doc Comments for Public APIs

Every public function, class, and module should have a doc comment. This is the primary documentation most developers encounter — it surfaces in IDEs as hover text, in generated API documentation, and in code navigation. It is the most-read documentation you will write, so write it well.

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

Notice the fallback behavior in the description: "Falls back to flat-rate pricing if the carrier API is unavailable." This is non-obvious behavior that callers need to know about. Without it, they would be surprised when their local test environment (which probably cannot reach the carrier API) returns a flat rate.

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

The `@example` tag is often skipped. Do not skip it. An example in the doc comment surfaces in IDEs as hover text — a developer can see exactly how to call this function without leaving their editor. That is the highest-leverage documentation you can write.

### Architecture Comments

At the top of complex files or modules, explain the big picture. New engineers reading the file for the first time need to understand the design intent before they can interpret any of the code.

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

This comment does something that the code cannot: it explains the design intent (no other code should modify status directly), the consequences of violation, and where to find more information (ADR-0014). A new engineer who reads this before diving into the code will understand the module at an architectural level. One who does not will wonder why there is a state machine and may attempt to work around it.

### What Not to Comment

- **Commented-out code.** Delete it. Git remembers everything. Commented-out code rots, confuses readers, triggers merge conflicts, and creates uncertainty: was this removed intentionally? Is it safe to delete? If you need it again, `git log -p --all -S 'old_calculate_tax'` will find it.

```python
# Bad — delete this
# def old_calculate_tax(amount):
#     return amount * 0.08
```

- **Obvious code.** If a variable is named `user_email`, you do not need a comment that says "the user's email."

- **Changelog-style comments** in source files: "Modified by Alice on 2026-01-15 to add validation." That is what `git blame` is for. These comments go stale, become inaccurate as the code changes further, and create visual noise that obscures the code.

- **Closing brace comments** (`} // end if`, `} // end for`). If your code is nested enough that you need these to orient yourself, the code needs refactoring — not annotations. Extract a function. Flatten the nesting.

---

## Summary: The Documentation Checklist

Every project has documentation needs. Here is a practical checklist for when you start or join a project:

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

When you find gaps in this checklist, filling them is among the highest-leverage things you can do. It does not require new features. It does not require coordination with product management. It requires writing — something you now know how to do.

### Documentation is Engineering

A prevailing misconception in software engineering is that documentation is separate from the engineering work — something you do after the real work is done, a checkbox before the PR is merged, a task that gets deferred when things are busy.

This is backwards. Documentation is engineering. Writing an RFC is engineering the decision-making process. Writing a runbook is engineering the incident response capability. Writing a postmortem is engineering organizational resilience. Writing a good README is engineering the onboarding experience for every future colleague.

Code without documentation is not finished. It is code with hidden costs deferred to the future: the hours a new engineer spends orienting themselves, the incident that takes longer to resolve because there is no runbook, the debate that happens for the fifth time because nobody wrote down the ADR.

> **Career note:** Documentation is also how you become visible at scope. Code that only you understand is local knowledge. Code that is well-documented is institutional knowledge. The engineers who advance fastest are the ones whose work is understandable, teachable, and durable. As Ch 29 explains, staff-level impact is about operating at a wider scope — and documentation is how you extend your thinking beyond your own working hours. See also Ch 9 for how communication patterns define engineering leadership.

Code with clear documentation is an asset that compounds over time. Every time someone understands your system faster, solves an incident without waking you up, or makes a good architectural decision because they had the context from your ADR — that is a return on your investment.

---

**Key Takeaway:** Write the document you wish existed when you were the new person, the on-call engineer at 3 AM, or the developer trying to understand a decision made two years ago. Technical writing is not overhead — it is the work. Your future colleagues, your future self, and your career will all thank you for taking it seriously.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M77: Architecture Decision Records](../course/modules/loop-3/L3-M77-architecture-decision-records.md)** — Write the ADRs for TicketPulse's three most consequential architecture choices using the format from this chapter
- **[L3-M89: Your Career Engineering Plan](../course/modules/loop-3/L3-M89-career-engineering-plan.md)** — Apply technical writing skills to build a brag doc and career narrative that makes your impact legible to others

### Quick Exercises

1. **Rewrite one confusing paragraph in your project's README: find the section that generates the most Slack questions from new developers, rewrite it assuming zero context, and ask one person to read both versions.**
2. **Write an ADR for a recent technical decision your team made: use the Context / Decision / Consequences format, and include the alternatives you considered and why you rejected them.**
3. **Draft a runbook for your team's most common on-call scenario: write it so that someone woken up at 3 AM with no prior context could follow it to resolution without pinging you.**

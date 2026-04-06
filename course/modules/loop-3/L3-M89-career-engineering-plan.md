# L3-M89: Your Career Engineering Plan

> **Loop 3 (Mastery)** | Section 3E: The Final Sprint | ⏱️ 60 min | 🟢 Core | Prerequisites: All prior modules
>
> **Source:** Chapter 29 of the 100x Engineer Guide

## What You'll Learn

- Building your brag document: quantifying everything you have built and learned across 90+ modules
- Staff+ archetype self-assessment: identifying whether you are a Tech Lead, Architect, Solver, or Right Hand
- Gap analysis: your 3 strongest and 3 weakest areas, with an actionable plan
- Negotiation preparation: researching market rates and building your case
- Influence plan: increasing your impact without changing your title

## Why This Matters

You have spent months (maybe a year) working through this course. You have built a globally distributed platform, learned distributed systems, databases, architecture, security, testing, DevOps, monitoring, and more. But technical knowledge without career strategy is potential without trajectory.

The engineers who advance fastest are not always the most technically brilliant. They are the ones who can articulate their impact, position themselves for the right opportunities, and negotiate effectively. They treat their career with the same rigor they apply to system design.

This module is not about gaming a system. It is about ensuring that the real work you have done gets recognized, that you invest your learning time wisely going forward, and that you have a plan for the next 12 months that is as deliberate as an architecture roadmap.

---

### 🤔 Prediction Prompt

Before starting the brag document, try to list your top 5 accomplishments from the last 6 months from memory. How many can you actually recall? That gap between what you did and what you remember is why the brag document exists.

## 1. Build: Your Brag Document

### What It Is

The brag document (a term popularized by Julia Evans) is a running record of your accomplishments. You will forget 80% of what you did by the time performance reviews come around. The brag document remembers for you.

### Stop and Write (20 minutes)

Go through the modules you have completed. For each major thing you built or learned, write a brag document entry. Be specific and quantify where possible.

**Template for each entry:**

```
WHAT: [What you built or did]
HOW:  [The technical approach — be specific]
WHY:  [What problem it solved]
IMPACT: [Quantified where possible]
SKILLS: [What you demonstrated]
```

### Example Entries from the Course

Here are examples of how to translate course work into brag document entries. Adapt these to your actual experience:

```
WHAT: Designed and implemented event-sourced order system
HOW:  Append-only event store with PostgreSQL, aggregate pattern for
      state reconstruction, projections for read models, snapshots
      for performance, crypto-shredding for GDPR compliance.
WHY:  Traditional CRUD orders lost state change history, making support
      investigations and financial reconciliation impossible.
IMPACT: Complete audit trail for all order state changes. Support
        investigations reduced from "check multiple systems" to
        "query the event log." GDPR-compliant PII handling.
SKILLS: Event sourcing, CQRS, domain modeling, data compliance.
```

```
WHAT: Production-hardened Kubernetes deployment with defense in depth
HOW:  Default-deny NetworkPolicies, per-service RBAC with least privilege,
      PodSecurityContext (non-root, read-only rootfs, dropped capabilities),
      PodDisruptionBudgets, HPA with custom Kafka consumer lag metrics.
WHY:  Default K8s configuration is permissive — any compromised pod can
      reach any other pod and any database.
IMPACT: Zero-trust network model. Pod compromise blast radius reduced
        from entire cluster to single service. Guaranteed availability
        during cluster maintenance.
SKILLS: Kubernetes security, network policy design, RBAC, capacity planning.
```

```
WHAT: Implemented durable purchase workflow surviving process crashes
HOW:  Built workflow engine with persisted step execution, deterministic
      replay for crash recovery, human-in-the-loop approval gates.
WHY:  Original saga orchestrator held state in memory — process crash
      between payment and confirmation caused money taken but no tickets.
IMPACT: Eliminated the class of bugs where crashes cause inconsistent
        order states. Zero manual interventions needed for mid-saga crashes.
SKILLS: Durable execution, distributed transactions, fault tolerance.
```

```
WHAT: Built real-time seat availability with WebSockets at scale
HOW:  WebSocket server with per-event rooms, Redis Pub/Sub for
      horizontal scaling, heartbeat-based connection health,
      client-side reconnection with exponential backoff + jitter.
WHY:  Users were purchasing already-sold seats because seat maps
      were stale (polling every 30s).
IMPACT: Seat availability updates delivered to all watchers in <100ms.
        Eliminated stale-seat purchase errors.
SKILLS: WebSocket protocol, real-time systems, horizontal scaling.
```

### Write Your Full Brag Document

Cover at minimum:

- **Architecture and system design**: Monolith to microservices, API gateway, event-driven communication, CQRS/event sourcing
- **Data and databases**: PostgreSQL optimization, Redis caching, Elasticsearch, data modeling, migrations
- **Reliability and operations**: Circuit breakers, rate limiting, monitoring, alerting, incident response, chaos engineering
- **Security**: Authentication, authorization, OWASP protections, Kubernetes hardening, crypto-shredding
- **Performance**: Load testing, optimization, caching strategies, connection pooling
- **DevOps and infrastructure**: Docker, Kubernetes, CI/CD, Nix, IaC
- **Real-time and messaging**: WebSockets, Kafka, event bus, push notifications
- **AI and emerging tech**: AI-powered features, durable execution, event sourcing
- **Testing**: Unit, integration, end-to-end, contract testing, property-based testing
- **Open source and communication**: Preparing a project for release, documentation, technical writing

This document is your promotion evidence, your interview prep, and your confidence builder. Update it after every significant project for the rest of your career.

---

## 2. Staff+ Archetype Assessment

### The Four Archetypes

From Will Larson's framework (covered in Chapter 29):

| Archetype | Core Activity | Day-to-Day |
|-----------|--------------|-----------|
| **Tech Lead** | Drive one team's technical direction | Code reviews, design discussions, mentoring, still coding regularly |
| **Architect** | Define cross-team technical vision | Architecture reviews, design docs, technology evaluation, alignment meetings |
| **Solver** | Parachute into the hardest problems | Deep investigation, prototyping, working across unfamiliar codebases |
| **Right Hand** | Extend VP/Director capacity | Variable — whatever the org needs most right now |

### Self-Assessment

Answer these honestly:

**1. Which modules energized you most?**

| If you loved... | You might be a... |
|-----------------|-------------------|
| Design exercises (C4 diagrams, ADRs, API design) | Architect |
| Debugging and performance optimization | Solver |
| Team workflow modules (CI/CD, code review, monitoring) | Tech Lead |
| Cross-cutting modules (career, open source, communication) | Right Hand |

**2. When you have unstructured time, what do you gravitate toward?**

- Writing code and reviewing PRs → Tech Lead or Solver
- Drawing diagrams and writing design docs → Architect
- Fixing organizational problems and processes → Right Hand

**3. How do you feel about working on the same team for years?**

- Energized by depth and continuity → Tech Lead
- Restless, want new challenges → Solver
- Indifferent, care more about the work → Architect or Right Hand

**4. What is your relationship with ambiguity?**

- You want to reduce it for your team → Tech Lead
- You want to resolve it through design → Architect
- You seek it out — that is where interesting problems live → Solver or Right Hand

### Stop and Reflect (5 minutes)

Write down your top archetype and your secondary archetype. There is no wrong answer. Most Staff+ roles are a blend. The goal is self-awareness about where you naturally perform best, so you can seek roles that match.

---

## 3. Gap Analysis

### Your Strongest and Weakest Areas

Rate yourself (1-5) in each area based on your experience through the course:

| Area | Rating (1-5) | Evidence |
|------|-------------|---------|
| Distributed systems design | | |
| Database internals and optimization | | |
| API design and communication patterns | | |
| Reliability engineering (circuit breakers, resilience) | | |
| Security (auth, hardening, compliance) | | |
| Performance and optimization | | |
| DevOps and infrastructure | | |
| Testing strategies | | |
| Monitoring and observability | | |
| Real-time systems | | |
| AI/ML integration | | |
| Technical communication (writing, presenting) | | |
| Career management and influence | | |

### Identify Your Top 3 and Bottom 3

Your top 3 are your brand. These are the areas where you will be known as the expert. Lean into them.

Your bottom 3 are your gaps. You do not need to become an expert in all of them -- but you need to be competent enough that they do not limit you.

### Design: Your 6-Month Learning Roadmap

<details>
<summary>💡 Hint 1: Pick the gap that blocks your next role, not the one that is most interesting</summary>
Look at your self-assessment. If you are aiming for Staff and your weakest area is system design communication, prioritize that over learning another database -- the bottleneck to promotion is almost never more technical depth, it is the ability to articulate and defend decisions.
</details>

For each of your bottom 3 gaps, define a concrete plan:

```
GAP: [Area]
CURRENT LEVEL: [1-5]
TARGET LEVEL: [1-5]
ACTIONS:
  Month 1-2: [Specific learning — book, course, project]
  Month 3-4: [Apply it — build something, contribute to a project]
  Month 5-6: [Teach it — write a blog post, give a talk, mentor someone]
MEASURE OF SUCCESS: [How will you know you have improved?]
```

**Example:**

```
GAP: Security (auth, hardening, compliance)
CURRENT LEVEL: 2
TARGET LEVEL: 4
ACTIONS:
  Month 1-2: Read "Web Application Security" by Andrew Hoffman.
             Complete OWASP Top 10 exercises.
  Month 3-4: Conduct a security audit of a personal project.
             Implement OAuth 2.0 + OIDC from scratch (not a library).
  Month 5-6: Write a blog post "Security Checklist for Node.js APIs."
             Review security-related PRs at work.
MEASURE OF SUCCESS: Can explain OWASP Top 10 in an interview.
                    Can conduct a basic security review of a new service.
```

---

## 4. Building Visibility: The Work That Gets Noticed

### The Visibility Trap

Many engineers believe that great work speaks for itself. It does not. Great work that nobody knows about is invisible work. Invisible work does not lead to promotions, opportunities, or influence.

This is not about self-promotion or politics. It is about making sure the right people understand what you have done and why it matters.

### Concrete Visibility Actions

**Write technical design docs and RFCs.** Every time you make a significant technical decision, write it down. The document itself becomes evidence of Staff-level thinking. It also invites feedback, builds consensus, and creates a record.

```
RFC: Migrating Order Service to Event Sourcing

Author: [Your name]
Status: Proposed
Date: 2026-03-15

## Problem
Support investigations for order issues take 30+ minutes because we
have no history of state changes. Financial reconciliation requires
cross-referencing three different databases.

## Proposal
Event-source the order domain...

## Alternatives Considered
1. Audit log table alongside CRUD...
2. CDC (Change Data Capture) from PostgreSQL WAL...

## Decision Criteria
...
```

**Share learnings after incidents.** Post-mortems are career-building documents. They demonstrate that you can diagnose complex problems, communicate them clearly, and drive preventive action.

**Demo your work.** If your team has demo days, use them. A 5-minute demo of the durable purchase workflow ("watch me kill the process and see it resume") is worth more visibility than a month of commits.

**Answer questions in Slack/Discord/team channels.** When someone asks a question you know the answer to, answer it thoroughly. Over time, this builds your reputation as the person who knows things.

### The Principle

Make the work legible. If you built something complex, write about it. If you solved a hard problem, document the solution. If you made an architectural decision, record the reasoning. Every written artifact is evidence that compounds over time.

---

## 4b. Brag Document Writing Workshop

Most engineers write brag documents that are too vague to be useful. "Improved system performance" is not a brag document entry. "Reduced 99th percentile API latency from 1.2s to 340ms by adding a read replica routing layer, eliminating 60% of queries from the primary" is a brag document entry.

This workshop takes you through the transformation from vague to specific for the entries you wrote in Section 1.

### The Five-Layer Deepening Method

For each brag document entry, apply these five questions in order. Each question adds a layer of specificity that makes the entry more credible and more useful in reviews, interviews, and negotiations.

**Layer 1: The What (you already have this)**
```
"Improved API performance"
```

**Layer 2: The How**
```
"Added Redis caching layer for event listing queries"
```

**Layer 3: The Numbers**
```
"Reduced average response time from 450ms to 38ms (88% improvement)
 for the top 3 most-trafficked endpoints"
```

**Layer 4: The Business Context**
```
"Event listing is the entry point for 73% of ticket purchases.
 The speed improvement increased mobile session completion rates by 12%."
```

**Layer 5: The Difficulty**
```
"The challenge was cache invalidation: events update frequently (seat
 availability changes every minute). Designed a targeted invalidation
 strategy using Redis pub/sub to notify caching nodes when specific
 events change, achieving freshness within 2 seconds without wholesale
 cache busts."
```

Layer 5 is where your entry becomes a promotion packet exhibit, not just a resume bullet. The difficulty is what demonstrates Staff-level thinking: you understood the problem deeply enough to navigate a non-obvious trade-off.

### Workshop Exercise (20 minutes)

Take your three weakest brag document entries — the ones that are most vague — and apply all five layers. Start at your current layer and add the next one.

Use this template for each entry:

```
ENTRY: [your current entry text]

Layer 1 (What): ___________________________________
Layer 2 (How):  ___________________________________
Layer 3 (Numbers): ________________________________
Layer 4 (Business context): _______________________
Layer 5 (Difficulty / insight): ___________________

REVISED ENTRY:
[rewrite the entry incorporating all five layers in 3-5 sentences]
```

### Quantifying Qualitative Work

Some of your most important contributions are qualitative — mentoring, process improvements, technical design reviews. These can be quantified too:

```
VAGUE: "Mentored junior engineers"
QUANTIFIED: "Mentored 2 engineers from L3 to L4 in 12 months.
             Both now independently own features with zero incidents
             in the past 6 months. One presented at the company all-hands."

VAGUE: "Improved the code review process"
QUANTIFIED: "Reduced average PR review turnaround from 3.5 days to 18 hours
             by introducing async review guidelines and a tiered review depth
             checklist. Measured via linear PR age metrics over 90 days."

VAGUE: "Wrote technical documentation"
QUANTIFIED: "Authored the runbook that reduced P1 incident MTTR from 42 minutes
             to 11 minutes across 4 incidents. The runbook has been used in
             every production incident for the past 6 months."
```

The pattern: count things, name names, cite time periods, reference outcomes.

---

## 5. Negotiation Preparation

### Research Market Rates

```
Resources:
- levels.fyi         — compensation data by company and level
- Glassdoor          — salary ranges and interview experiences
- Blind              — anonymous compensation discussions
- Hired              — marketplace that reveals salary ranges
- Your network       — the most accurate data comes from people you know
```

### Build Your Narrative

Negotiation is not about demanding more. It is about presenting evidence that your contribution justifies a specific compensation.

**The structure:**

```
1. MARKET DATA: "Based on [source], the market range for [level] at
   [type of company] in [location] is [range]."

2. YOUR CONTRIBUTION: "In the past [period], I [accomplishments from
   brag document]. These contributions are at [target level] scope."

3. THE ASK: "Given the market data and my contributions, I believe
   [specific number or range] is appropriate."

4. FLEXIBILITY: "I am also open to discussing [equity, title, role
   scope, team choice, learning budget] as part of the package."
```

### Common Mistakes

- **Not negotiating at all**: The most expensive mistake. Companies expect negotiation. Not negotiating leaves money on the table.
- **Negotiating without data**: "I want more" is weak. "The market rate for this role is X, and here is why I am at the top of that range" is strong.
- **Making it adversarial**: Negotiation is collaborative. You are both trying to find a number that reflects your value.
- **Accepting the first offer immediately**: Even if the offer is good, asking for 24-48 hours to consider is normal and expected.

---

## 5b. Negotiation Role-Play Workshop

Reading about negotiation is not enough. You need to practice the words out loud, including the awkward silences and the phrases that feel presumptuous until you have said them a few dozen times.

This workshop runs three role-play scenarios. For each one, read both sides of the dialogue, then practice your side with a partner or by writing your responses.

### Scenario 1: The Initial Offer

**Context**: You applied through a recruiter. The hiring manager emails: "Great news — we want to extend an offer. We're thinking $165K base. Can you confirm that works for you?"

**The trap**: Confirming immediately. Even if $165K is above your current salary, you are leaving money on the table. The first offer is a starting position, not a final one.

**Your response (practice saying this out loud):**
```
"Thank you — I am genuinely excited about this role and the team.
 I would like to take 48 hours to review the full package details
 before responding. Could you send me the complete offer in writing
 including base, equity, bonus structure, and benefits?"

[After receiving the full offer]

"I have reviewed the offer carefully and I appreciate it.
 The role is a great fit, and I want to make this work.
 My research shows that the market rate for this level at a company
 of this stage is in the $185K-$205K range. Based on my experience
 with [specific relevant skill] and [specific relevant accomplishment],
 I believe $195K would be appropriate. Is there flexibility there?"
```

**What makes this effective:**
- You do not panic or apologize
- You anchor to market data, not personal needs ("I need more" is weak; "the market says" is strong)
- You are specific ($195K, not "a bit more")
- You leave the door open ("is there flexibility" — not "I won't accept less")

### Scenario 2: The Counter

**Context**: The recruiter comes back: "We hear you on the data. We can go to $175K — that's our maximum for this level. Is that something you can work with?"

**The trap**: Accepting immediately because they moved. $175K is still $20K below your anchor.

**Your response:**
```
"I appreciate you going to bat for me — $175K is meaningful progress.
 I understand you may have a band constraint. Can we look at whether
 there are other levers? For example: a signing bonus, an accelerated
 first review at 6 months instead of 12, or additional equity?
 I want to find a package that works for both of us."
```

**What this accomplishes:**
- You acknowledge their movement without caving
- You open other dimensions (equity, signing bonus, timeline) that they may have more flexibility on
- You keep the conversation collaborative, not adversarial

### Scenario 3: The Internal Promotion Conversation

**Context**: You have been working hard for 18 months and you believe you are performing at the next level. Your manager has not brought up promotion. You need to start that conversation.

**The wrong approach**: "I think I deserve a promotion."

**The right approach — requesting a structured conversation:**
```
"I want to talk about my career development. I have been thinking
 about what the L5 level looks like and whether I am on track for
 a promotion cycle. Can we schedule 30 minutes to walk through
 where I stand and what I should focus on?

 I have put together a summary of my contributions over the past
 18 months that I would like to share."
```

**In the meeting:**
```
"Here is what I have been working on [walk through top 3-4 brag doc entries].
 I think these demonstrate [specific competency] and [specific competency].

 Based on what you know about the L5 expectations, where do you see gaps?
 And what would a realistic timeline look like if I close those gaps?"
```

**What makes this effective:**
- You come prepared with evidence (your brag document)
- You frame it as a partnership (you want to close gaps, not just receive a promotion)
- You ask for specifics ("realistic timeline" forces a concrete answer, not a vague "maybe next cycle")

### Reflection Questions (5 minutes)

After the role-play exercises:

1. Which scenario was most uncomfortable? Why?
2. What phrase felt most foreign to say out loud?
3. What is your actual walk-away number (below which you would decline an offer)? Write it down before your next negotiation.
4. Who do you know at your target company or compensation level who could give you real data on their package?

---

## 6. Switching Jobs Strategically

### When to Stay vs When to Leave

Not every career problem is solved by switching companies. But sometimes it is the right move.

**Consider staying when:**
- You have a clear path to the next level and your manager supports it
- You are learning and growing in your current role
- Your compensation is fair for your market and level
- You have influence and a track record (hard to rebuild at a new company)

**Consider leaving when:**
- You have been at the same level for 2+ years despite strong performance
- The company's technical trajectory does not align with your growth goals
- Your compensation is significantly below market (20%+ gap)
- You have stopped learning and every day feels like the same day
- The team or culture has deteriorated and is unlikely to improve

**The compounding effect of tenure:** Switching companies resets your internal reputation. At your current company, people know your track record. At a new company, you start from zero. The first 6 months are spent building credibility. This is not a reason to stay forever, but it is a cost to factor in.

**The compounding effect of switching:** Each company teaches you different architectures, team structures, engineering cultures, and problem domains. Engineers who have worked at 3-4 companies over 10 years tend to have broader perspective. The sweet spot is typically 2-4 years per company.

### The Interview Advantage You Now Have

Having completed this course, you can:
- **System design interviews**: Present TicketPulse as your example system. You have a deep, practiced answer ready for any system design question.
- **Behavioral interviews**: Your brag document is your preparation. Every "tell me about a time..." question has an answer.
- **Technical interviews**: You have breadth across the entire backend stack. Even if a question is outside your deepest expertise, you can speak intelligently about it.
- **Architecture discussions**: You can whiteboard a complete system, defend your decisions, and discuss trade-offs.

---

## 7. Influence Plan

### Increase Your Impact Without Changing Your Title

You do not need a promotion to have more impact. Identify 3 ways to increase your influence in the next 6 months:

| Action | Impact | Effort |
|--------|--------|--------|
| Write an RFC proposing a technical improvement | High (shapes team direction) | Medium |
| Mentor a junior engineer through their first quarter | High (multiplier effect) | Low |
| Improve a team process (deploy pipeline, on-call rotation, code review) | Medium (reduces friction for everyone) | Low |
| Open-source a tool your team built | Medium (builds profile, attracts talent) | Medium |
| Give a talk at a meetup or internal tech talk | Medium (builds reputation, clarifies your thinking) | Medium |
| Start a weekly "architecture reading group" | Medium (elevates the whole team) | Low |

### The Multiplier Mindset

The definition of Staff+ impact is not "I built more things." It is "I made the team more effective." Every influence action above multiplies the output of others:

- An RFC that shapes the right technical direction saves the team from building the wrong thing.
- Mentoring a junior engineer turns one productive person into two.
- Improving the deploy pipeline saves every engineer 10 minutes per deploy, every day.

This is what "100x engineer" actually means. Not doing everything yourself. Making everyone around you faster, more effective, and more capable.

---

## 8. Reflect: The One Thing

### Stop and Think (5 minutes)

What is the ONE thing that would most accelerate your career in the next 12 months?

Not three things. Not five things. One thing.

Is it:
- Deepening a technical skill?
- Building your public profile (writing, speaking, open source)?
- Improving your communication (design docs, presentations, influence)?
- Moving to a different team or company?
- Finding a mentor who has the career you want?
- Shipping a project that demonstrates next-level impact?

Write it down. Make it specific. Make it measurable. Make it the thing you actually do.

---

## Checkpoint: What You Built

You have:

- [x] Written a comprehensive brag document covering 90+ modules of work
- [x] Identified your Staff+ archetype and secondary archetype
- [x] Assessed your strengths and gaps with a concrete 6-month learning plan
- [x] Prepared negotiation material with market data and a personal narrative
- [x] Created an influence plan with 3 specific actions for the next 6 months
- [x] Identified the single most important thing for your career in the next year

**Key insight**: Your career is a system you can engineer. The brag document is your monitoring. The gap analysis is your capacity planning. The influence plan is your scaling strategy. Apply the same rigor to your career that you apply to production systems.

---

**Next module**: L3-M90 -- The Final Capstone. The last module of the entire course. A retrospective on everything you have learned, a showcase of what you have built, and a plan for what comes next.

---

## Cross-References

- **Chapter 29** (Career Engineering): The full framework for treating your career as a system — metrics, capacity planning, and strategic investment in the areas that compound fastest.
- **L3-M77** (Architecture Decision Records): The skill of writing clear, structured arguments for technical decisions transfers directly to writing promotion narratives and negotiation cases.
- **L3-M90** (Final Capstone): Incorporates the brag document and career plan into your end-of-course retrospective.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Brag document** | A running record of your accomplishments, impact, and key contributions maintained for performance reviews. |
| **Promotion packet** | A compiled collection of evidence demonstrating readiness for the next career level. |
| **Staff+ archetype** | A recognized pattern of senior engineering impact such as Tech Lead, Architect, Solver, or Right Hand. |
| **Negotiation** | The process of discussing and reaching agreement on compensation, role, or scope with an employer. |
| **Sponsorship** | Active advocacy by a senior leader who creates opportunities and visibility for your career advancement. |
| **Five-layer deepening** | A method for transforming vague brag document entries into specific, quantified, context-rich narratives. |
| **Anchor** | In negotiation, the first specific number stated, which disproportionately shapes the final outcome. |
| **Walk-away number** | Your minimum acceptable outcome in a negotiation, determined before the conversation begins. |

### 🤔 Reflection Prompt

After completing the gap analysis, which weakness surprised you most? Where is the gap between "I understand the concept" and "I could build it under pressure in production"?

---

## What's Next

In **The 100x Engineer Retrospective** (L3-M90), you'll build on what you learned here and take it further.

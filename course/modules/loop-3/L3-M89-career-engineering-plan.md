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

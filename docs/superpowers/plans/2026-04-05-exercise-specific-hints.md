# Exercise-Specific Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all generic hint text in course module exercises with exercise-specific, contextually useful hints that scaffold learner thinking progressively.

**Architecture:** A Python script reads each module, identifies exercises with generic hints (pattern-matched), reads the surrounding exercise context, and generates a replacement hints file. A human or agent then reviews and applies the replacements. This two-pass approach (generate → review → apply) prevents bad hints from shipping.

**Tech Stack:** Python 3, regex for pattern matching, Edit tool for applying changes.

---

## Scope

### Current State
- **51 modules** have `<details>` hint blocks (our script added them)
- **57 modules** have NO hint blocks at all (no qualifying exercises or script missed them)
- Of the 51 with hints, **all use generic text** from the batch script:
  - Loop 1: "Think about the overall approach before diving into implementation details."
  - Loop 2: "Consider the trade-offs between different approaches before choosing one."
  - Loop 3: "What constraints matter most here? Start from the requirements, not the implementation."
- **3 modules** (L1-M05, L1-M06, L1-M07) had pre-existing `<summary>Solution</summary>` blocks — those are fine and should be left alone.

### Exercise Counts (hint-eligible: 🛠️ Build, 🐛 Debug, 📐 Design)
| Loop | 🛠️ Build | 🐛 Debug | 📐 Design | Total |
|------|---------|---------|----------|-------|
| Loop 1 | 18 | 3 | 5 | 26 |
| Loop 2 | 46 | 11 | 6 | 63 |
| Loop 3 | 42 | 2 | 41 | 85 |
| **Total** | **106** | **16** | **52** | **174** |

### Work Breakdown
- **Phase 1:** 57 modules missing hints entirely → add exercise-specific hints
- **Phase 2:** 51 modules with generic hints → replace with exercise-specific hints
- **Total:** ~174 exercises across 108 modules needing specific hint text

### Hint Quality Standard

Each hint block must:
1. **Reference the specific exercise** — mention the actual technology, table, command, or concept
2. **Progress from vague to specific** — Hint 1 is a direction, Hint 3 is nearly the answer
3. **Match the loop's scaffolding level:**
   - Loop 1: 3 generous hints, Hint 3 gives the approach + key code/command
   - Loop 2: 3 hints behind `<details>`, Hint 3 gives the approach but not full code
   - Loop 3: 1-2 hints only, peer-level tone ("Have you considered X?")

**Example of a GOOD specific hint (L1-M07, indexing):**
```markdown
<details>
<summary>💡 Hint 1: Direction</summary>
Think about which columns appear in your WHERE clauses most often. Those are your index candidates.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run EXPLAIN ANALYZE on the "find events by date range" query first. Look for "Seq Scan" — that's the signal you need an index. A B-tree index on the `date` column is the natural fit.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
CREATE INDEX idx_events_date ON events(date); — then re-run EXPLAIN ANALYZE and compare the cost and execution time. You should see "Index Scan" replace "Seq Scan".
</details>
```

**Example of a BAD generic hint (what we have now):**
```markdown
<details>
<summary>💡 Hint 1: Direction</summary>
Think about the overall approach before diving into implementation details.
</details>
```

---

## Parallelization Strategy

This work is **perfectly parallelizable by module**. Each module's hints are independent. The recommended approach is to dispatch one subagent per batch of 5-6 modules (grouped by topic for context efficiency), resulting in ~18-20 parallel tasks.

---

## Task 1: Loop 1, Section 1A — Tooling & Setup (M01-M04)

**Files:**
- Modify: `course/modules/loop-1/L1-M01-course-setup-ticketpulse-kickoff.md`
- Modify: `course/modules/loop-1/L1-M02-your-dev-environment.md`
- Modify: `course/modules/loop-1/L1-M03-git-beyond-the-basics.md`
- Modify: `course/modules/loop-1/L1-M04-how-the-internet-actually-works.md`

**Approach:** These modules are mostly 🔍 Explore exercises (no hints needed). Scan for any 🛠️ Build or 🐛 Debug exercises and add specific hints.

- [ ] **Step 1: Read L1-M01 through L1-M04**

Read each file. Identify all 🛠️ Build, 🐛 Debug, and 📐 Design exercises. Note the specific task each asks the learner to do.

- [ ] **Step 2: Write specific hints for each qualifying exercise**

For each exercise found, write 3 hints that reference the specific technology and task. Example for L1-M03's git bisect exercise:

```markdown
<details>
<summary>💡 Hint 1: Direction</summary>
git bisect needs two things: a "bad" commit (where the bug exists) and a "good" commit (where it doesn't). Start with HEAD as bad and the initial commit as good.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run `git bisect start`, then `git bisect bad` (current commit has the bug), then `git bisect good <earliest-commit-hash>`. Git will check out a middle commit — test it and tell git if it's good or bad.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
At each step, run the test suite (or check the specific behavior). Tell git: `git bisect good` or `git bisect bad`. After ~4-5 steps, git will identify the exact commit. Run `git bisect reset` when done.
</details>
```

- [ ] **Step 3: Apply hints using Edit tool**

Insert hint blocks after each qualifying exercise description. If a generic hint block already exists, replace it.

- [ ] **Step 4: Verify changes**

Read each modified file and confirm hints are contextually specific and properly formatted.

- [ ] **Step 5: Commit**

```bash
git add course/modules/loop-1/L1-M0{1,2,3,4}*.md
git commit -m "feat(course): add specific hints for L1-M01 through L1-M04"
```

---

## Task 2: Loop 1, Section 1B — Data Foundations (M05-M10)

**Files:**
- Modify: `course/modules/loop-1/L1-M05-postgresql-from-zero.md`
- Modify: `course/modules/loop-1/L1-M06-sql-that-actually-matters.md`
- Modify: `course/modules/loop-1/L1-M07-indexing-and-query-performance.md`
- Modify: `course/modules/loop-1/L1-M08-data-modeling-decisions.md`
- Modify: `course/modules/loop-1/L1-M09-nosql-when-and-why.md`
- Modify: `course/modules/loop-1/L1-M10-caching-strategies.md`

**Approach:** These are data-heavy modules with many 🛠️ Build exercises. L1-M05 through M07 already have `<summary>Solution</summary>` blocks — leave those, but replace any generic `💡 Hint` blocks. Hints should reference specific SQL, Redis commands, or caching patterns.

- [ ] **Step 1: Read M05-M10, identify all hint-eligible exercises**
- [ ] **Step 2: Write specific hints** (e.g., for M07 indexing: reference EXPLAIN ANALYZE, B-tree vs GIN, specific TicketPulse columns)
- [ ] **Step 3: Replace generic hints with specific ones using Edit tool**
- [ ] **Step 4: Verify — hints reference actual SQL, commands, or TicketPulse schema**
- [ ] **Step 5: Commit**

```bash
git add course/modules/loop-1/L1-M0{5,6,7,8,9}*.md course/modules/loop-1/L1-M10*.md
git commit -m "feat(course): add specific hints for L1-M05 through L1-M10 (data foundations)"
```

---

## Task 3: Loop 1, Section 1C — API & Deployment (M11-M16d)

**Files:**
- Modify: `course/modules/loop-1/L1-M11-rest-api-design.md`
- Modify: `course/modules/loop-1/L1-M12-error-handling.md`
- Modify: `course/modules/loop-1/L1-M13-authentication-authorization.md`
- Modify: `course/modules/loop-1/L1-M14-first-deployment.md`
- Modify: `course/modules/loop-1/L1-M15-ci-cd-pipeline.md`
- Modify: `course/modules/loop-1/L1-M16-testing-fundamentals.md`
- Modify: `course/modules/loop-1/L1-M16a-solid-principles-in-practice.md`
- Modify: `course/modules/loop-1/L1-M16b-clean-code-and-design-principles.md`
- Modify: `course/modules/loop-1/L1-M16c-design-patterns-that-matter.md`
- Modify: `course/modules/loop-1/L1-M16d-coupling-cohesion-modularity.md`

**Approach:** Hints should reference Express routes, JWT tokens, Docker, GitHub Actions, Jest test patterns, SOLID principles, and specific design patterns. These modules have no hint blocks currently.

- [ ] **Step 1: Read M11-M16d, identify all hint-eligible exercises**
- [ ] **Step 2: Write specific hints** (e.g., for M13 auth: reference JWT structure, bcrypt, middleware pattern; for M16 testing: reference Jest matchers, test isolation, the TicketPulse pricing function)
- [ ] **Step 3: Insert hint blocks after each qualifying exercise using Edit tool**
- [ ] **Step 4: Verify**
- [ ] **Step 5: Commit**

```bash
git add course/modules/loop-1/L1-M1{1,2,3,4,5,6}*.md
git commit -m "feat(course): add specific hints for L1-M11 through L1-M16d (API, deploy, testing)"
```

---

## Task 4: Loop 1, Section 1D — Systems & Architecture (M17-M22)

**Files:**
- Modify: `course/modules/loop-1/L1-M17-how-distributed-systems-fail.md`
- Modify: `course/modules/loop-1/L1-M18-consistency-models-in-practice.md`
- Modify: `course/modules/loop-1/L1-M19-architecture-patterns-overview.md`
- Modify: `course/modules/loop-1/L1-M20-domain-driven-design-basics.md`
- Modify: `course/modules/loop-1/L1-M21-event-driven-thinking.md`
- Modify: `course/modules/loop-1/L1-M22-introduction-to-message-queues.md`

**Approach:** Hints should reference CAP theorem, consistency trade-offs in TicketPulse (e.g., ticket availability vs purchase confirmation), RabbitMQ, bounded contexts.

- [ ] **Step 1-5:** Same pattern — read, write specific hints, apply, verify, commit.

```bash
git commit -m "feat(course): add specific hints for L1-M17 through L1-M22 (systems, architecture)"
```

---

## Task 5: Loop 1, Section 1E — Security, Observability, Languages (M23-M30)

**Files:**
- Modify: `course/modules/loop-1/L1-M23-owasp-top-10-finding-vulnerabilities.md`
- Modify: `course/modules/loop-1/L1-M24-secrets-management.md`
- Modify: `course/modules/loop-1/L1-M25-logging-and-observability-101.md`
- Modify: `course/modules/loop-1/L1-M26-slos-and-error-budgets.md`
- Modify: `course/modules/loop-1/L1-M27-dependency-and-environment-management.md`
- Modify: `course/modules/loop-1/L1-M28-the-language-landscape.md`
- Modify: `course/modules/loop-1/L1-M29-concurrency-models.md`
- Modify: `course/modules/loop-1/L1-M30-loop-1-capstone.md`

**Approach:** Hints should reference OWASP-specific vulnerabilities (SQL injection in TicketPulse), .env files, structured logging with pino/winston, SLO calculations, nvm/volta, and the capstone integration.

- [ ] **Step 1-5:** Same pattern.

```bash
git commit -m "feat(course): add specific hints for L1-M23 through L1-M30 (security, observability, capstone)"
```

---

## Task 6: Loop 2, Section 2A — Microservices (M31-M36)

**Files:**
- Modify: `course/modules/loop-2/L2-M31-the-strangler-fig-extracting-your-first-service.md`
- Modify: `course/modules/loop-2/L2-M32-service-communication-rest-vs-grpc-vs-events.md`
- Modify: `course/modules/loop-2/L2-M33-kafka-deep-dive.md`
- Modify: `course/modules/loop-2/L2-M34-the-saga-pattern.md`
- Modify: `course/modules/loop-2/L2-M35-database-per-service.md`
- Modify: `course/modules/loop-2/L2-M36-api-gateway-and-bff.md`

**Approach:** Hints should reference TicketPulse's service extraction (Payments service), Kafka topics, saga compensating actions, schema ownership, and nginx/Express gateway routing.

- [ ] **Step 1-5:** Same pattern.

```bash
git commit -m "feat(course): add specific hints for L2-M31 through L2-M36 (microservices)"
```

---

## Task 7: Loop 2, Section 2B — Advanced Data (M37-M42)

**Files:**
- Modify: `course/modules/loop-2/L2-M37-postgresql-internals.md`
- Modify: `course/modules/loop-2/L2-M38-connection-pooling.md`
- Modify: `course/modules/loop-2/L2-M39-advanced-sql-for-analytics.md`
- Modify: `course/modules/loop-2/L2-M40-search-engineering.md`
- Modify: `course/modules/loop-2/L2-M41-the-n-plus-1-problem.md`
- Modify: `course/modules/loop-2/L2-M42-graph-databases.md`

**Approach:** Hints should reference pg_stat_activity, PgBouncer config, window functions on TicketPulse data, Elasticsearch mapping, DataLoader pattern, and Neo4j Cypher queries.

- [ ] **Step 1-5:** Same pattern.

```bash
git commit -m "feat(course): add specific hints for L2-M37 through L2-M42 (advanced data)"
```

---

## Task 8: Loop 2, Section 2C — Infrastructure & Observability (M43-M50)

**Files:**
- Modify: `course/modules/loop-2/L2-M43-kubernetes-fundamentals.md`
- Modify: `course/modules/loop-2/L2-M44-terraform-and-iac.md`
- Modify: `course/modules/loop-2/L2-M44a-policy-and-iac-scanning.md`
- Modify: `course/modules/loop-2/L2-M44b-database-migrations-as-code.md`
- Modify: `course/modules/loop-2/L2-M45-monitoring-prometheus-grafana.md`
- Modify: `course/modules/loop-2/L2-M46-distributed-tracing-opentelemetry.md`
- Modify: `course/modules/loop-2/L2-M47-alerting-and-on-call.md`
- Modify: `course/modules/loop-2/L2-M48-chaos-engineering.md`
- Modify: `course/modules/loop-2/L2-M49-circuit-breakers-and-resilience.md`
- Modify: `course/modules/loop-2/L2-M50-rate-limiting.md`

**Approach:** Hints should reference kubectl commands, HCL resources, Prometheus PromQL, OpenTelemetry spans, PagerDuty config, Chaos Toolkit experiments, Resilience4j patterns, and token bucket algorithms.

- [ ] **Step 1-5:** Same pattern.

```bash
git commit -m "feat(course): add specific hints for L2-M43 through L2-M50 (infra, observability)"
```

---

## Task 9: Loop 2, Section 2D — Patterns & Practices (M51-M60)

**Files:**
- Modify: `course/modules/loop-2/L2-M51-cqrs-in-practice.md`
- Modify: `course/modules/loop-2/L2-M51a-composition-over-inheritance-fp-vs-oop.md`
- Modify: `course/modules/loop-2/L2-M52-data-pipelines.md`
- Modify: `course/modules/loop-2/L2-M53-feature-flags.md`
- Modify: `course/modules/loop-2/L2-M54-zero-downtime-migrations.md`
- Modify: `course/modules/loop-2/L2-M55-webhooks.md`
- Modify: `course/modules/loop-2/L2-M55a-github-actions-mastery.md`
- Modify: `course/modules/loop-2/L2-M56-advanced-authentication.md`
- Modify: `course/modules/loop-2/L2-M57-tls-encryption-deep-dive.md`
- Modify: `course/modules/loop-2/L2-M58-debugging-in-production.md`
- Modify: `course/modules/loop-2/L2-M59-technical-writing.md`
- Modify: `course/modules/loop-2/L2-M59a-spec-driven-development.md`
- Modify: `course/modules/loop-2/L2-M60-loop-2-capstone.md`

**Approach:** Hints should reference CQRS read/write models in TicketPulse, LaunchDarkly/Unleash config, expand-contract migration pattern, webhook signature verification, OAuth 2.0 PKCE flow, TLS certificate chain, production debugging with strace/tcpdump, and the capstone integration.

- [ ] **Step 1-5:** Same pattern.

```bash
git commit -m "feat(course): add specific hints for L2-M51 through L2-M60 (patterns, capstone)"
```

---

## Task 10: Loop 3, Section 3A — Global Scale (M61-M66)

**Files:**
- Modify: `course/modules/loop-3/L3-M61-multi-region-design.md`
- Modify: `course/modules/loop-3/L3-M62-cloud-provider-deep-dive.md`
- Modify: `course/modules/loop-3/L3-M63-database-at-scale.md`
- Modify: `course/modules/loop-3/L3-M64-cdn-and-edge-computing.md`
- Modify: `course/modules/loop-3/L3-M65-consistent-hashing-and-distributed-cache.md`
- Modify: `course/modules/loop-3/L3-M66-the-payment-system.md`

**Approach:** Loop 3 hints are 1-2 only, peer-level tone. Reference multi-region latency tables, CockroachDB vs Aurora, CloudFront behaviors, consistent hashing ring, Stripe idempotency keys.

- [ ] **Step 1-5:** Same pattern. Only 1-2 hints per exercise (mastery scaffolding).

```bash
git commit -m "feat(course): add specific hints for L3-M61 through L3-M66 (global scale)"
```

---

## Task 11: Loop 3, Section 3B — Real-Time & AI (M67-M72)

**Files:**
- Modify: `course/modules/loop-3/L3-M67-websockets-and-real-time.md`
- Modify: `course/modules/loop-3/L3-M68-the-ticket-rush-problem.md`
- Modify: `course/modules/loop-3/L3-M69-notification-system.md`
- Modify: `course/modules/loop-3/L3-M70-recommendation-engine.md`
- Modify: `course/modules/loop-3/L3-M71-ai-powered-features.md`
- Modify: `course/modules/loop-3/L3-M72-graphql-api.md`

**Approach:** Hints should reference WebSocket heartbeats, FOR UPDATE SKIP LOCKED, notification fan-out patterns, collaborative filtering, embedding models, and GraphQL DataLoader.

- [ ] **Step 1-5:** Same pattern. 1-2 hints.

```bash
git commit -m "feat(course): add specific hints for L3-M67 through L3-M72 (real-time, AI)"
```

---

## Task 12: Loop 3, Section 3C — Operations & Leadership (M73-M80a)

**Files:**
- Modify: `course/modules/loop-3/L3-M73-incident-response-simulation.md`
- Modify: `course/modules/loop-3/L3-M74-war-stories-analysis.md`
- Modify: `course/modules/loop-3/L3-M75-cost-optimization.md`
- Modify: `course/modules/loop-3/L3-M76-system-design-interview-practice.md`
- Modify: `course/modules/loop-3/L3-M77-architecture-decision-records.md`
- Modify: `course/modules/loop-3/L3-M77a-package-principles-architecture-fitness.md`
- Modify: `course/modules/loop-3/L3-M78-dora-metrics-team-performance.md`
- Modify: `course/modules/loop-3/L3-M79-data-privacy-gdpr.md`
- Modify: `course/modules/loop-3/L3-M80-building-your-platform.md`
- Modify: `course/modules/loop-3/L3-M80a-github-actions-at-scale.md`

**Approach:** Hints should reference incident commander roles, postmortem templates, AWS/GCP cost explorer, system design interview framework (requirements → estimation → design → deep dive), ADR templates, DORA metrics collection, GDPR Article 17, and platform team API patterns.

- [ ] **Step 1-5:** Same pattern. 1-2 hints.

```bash
git commit -m "feat(course): add specific hints for L3-M73 through L3-M80a (operations, leadership)"
```

---

## Task 13: Loop 3, Section 3D — Advanced & Capstone (M81-M91c)

**Files:**
- Modify: `course/modules/loop-3/L3-M81-durable-execution.md`
- Modify: `course/modules/loop-3/L3-M82-event-sourcing-at-scale.md`
- Modify: `course/modules/loop-3/L3-M83-advanced-kubernetes.md`
- Modify: `course/modules/loop-3/L3-M83a-observability-and-gitops-as-code.md`
- Modify: `course/modules/loop-3/L3-M83b-platform-engineering-crossplane.md`
- Modify: `course/modules/loop-3/L3-M84-nix-reproducible-builds.md`
- Modify: `course/modules/loop-3/L3-M85-open-source-your-work.md`
- Modify: `course/modules/loop-3/L3-M86-ai-powered-engineering.md`
- Modify: `course/modules/loop-3/L3-M86a-ai-native-spec-driven-development.md`
- Modify: `course/modules/loop-3/L3-M87-mobile-backend-patterns.md`
- Modify: `course/modules/loop-3/L3-M88-architecture-review.md`
- Modify: `course/modules/loop-3/L3-M89-career-engineering-plan.md`
- Modify: `course/modules/loop-3/L3-M90-final-capstone.md`
- Modify: `course/modules/loop-3/L3-M91-beast-mode-access-and-system-mapping.md`
- Modify: `course/modules/loop-3/L3-M91a-beast-mode-observability-wiring.md`
- Modify: `course/modules/loop-3/L3-M91b-beast-mode-incident-dry-run.md`
- Modify: `course/modules/loop-3/L3-M91c-beast-mode-tribal-knowledge.md`

**Approach:** Hints should reference Temporal/Inngest workflow steps, event store projections, K8s NetworkPolicy YAML, ArgoCD ApplicationSets, Crossplane XRDs, Nix flake.nix, CHANGELOG conventions, Claude API tool_use, BFF for mobile, architecture fitness functions, and the Beast Mode access matrix.

- [ ] **Step 1-5:** Same pattern. 1-2 hints.

```bash
git commit -m "feat(course): add specific hints for L3-M81 through L3-M91c (advanced, capstone, beast mode)"
```

---

## Task 14: Final Cleanup

**Files:**
- Remove: `course/apply-improvements.py` (one-time script, no longer needed)
- Remove: `course/modules/loop-2/process_pass2.py` (stray agent artifact, if still present)

- [ ] **Step 1: Remove utility scripts**

```bash
git rm course/apply-improvements.py
git rm -f course/modules/loop-2/process_pass2.py 2>/dev/null
```

- [ ] **Step 2: Spot-check 10 random modules**

Pick 2-3 modules from each loop and read the hints. Verify they are specific, contextual, and follow the scaffolding level for their loop.

- [ ] **Step 3: Run a count to verify no generic hints remain**

```bash
grep -r "Think about the overall approach" course/modules/ | wc -l
# Expected: 0
grep -r "Consider the trade-offs between" course/modules/ | wc -l
# Expected: 0
grep -r "What constraints matter most" course/modules/ | wc -l
# Expected: 0
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore(course): remove utility scripts, finalize hint pass"
git push
```

---

## Execution Notes

### Parallelization
Tasks 1-13 are fully independent. With subagent-driven development, dispatch all 13 in parallel — each reads its own module files, writes specific hints, and commits. No cross-task dependencies.

### Per-Task Time Estimate
Each task involves reading 5-10 module files and writing 3-15 hint blocks. At ~2 minutes per hint block (read context, write 3 hints), each task is roughly 10-30 minutes of agent work.

### Quality Gate
After all tasks complete, Task 14's spot-check catches any low-quality hints. If a hint is too generic or wrong, fix it inline.

# L3-M77a: Package Principles & Architecture Fitness Functions

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 75 min | 🔴 Expert | Prerequisites: L3-M77 (ADRs), L2-M31-35 (Microservices), all Loop 1 foundations
>
> **Source:** Chapter 32 of the 100x Engineer Guide

## What You'll Learn

- Martin's 6 package principles and how they apply to a real monorepo
- How to visualize and analyze dependency graphs for structural problems
- How to set up dependency-cruiser rules that enforce architectural boundaries in CI
- What architecture fitness functions are and why Netflix, Uber, and Airbnb use them
- The trade-off between enforcement overhead and architectural drift

## Why This Matters

TicketPulse's monorepo has grown. What started as 3 well-separated packages now has 12, and the dependency graph is getting tangled. The event-service imports a utility from the payment package. The shared library depends on a feature-specific type. A "quick fix" introduced a circular dependency between order and inventory modules.

None of these are bugs. The tests pass. The app works. But the architecture is quietly eroding. Each shortcut makes the next shortcut easier to justify. In 6 months, no one can change the order module without also touching payment, inventory, and shared. The codebase becomes a monolith again -- but worse, because it has the operational overhead of microservices with the coupling of a monolith.

Package principles and fitness functions are the guardrails that prevent this erosion.

> **Pro tip:** "Robert C. Martin defined the package principles in 2002, but they did not become widely practiced until monorepos became popular. In a monorepo, bad dependencies compile and run fine -- the boundary violations only show up as pain during refactoring, deployment, and scaling."

---

### 🤔 Prediction Prompt

Before reading the principles, think about your own monorepo or project. Can you change one module without worrying about breaking another? If not, where are the hidden couplings?

## Part 1: The 6 Package Principles

Robert C. Martin defined 6 principles for organizing packages, split into two groups: **cohesion** (what goes together) and **coupling** (how packages relate).

### Cohesion Principles: What Goes Together

```
REP — Reuse-Release Equivalence Principle
─────────────────────────────────────────
"The unit of reuse is the unit of release."

If you version and release code together, it should be cohesive.
A package containing a date formatter, a payment gateway, and
an image resizer is not reusable -- consumers depend on all three
even if they need only one.

TICKETPULSE CHECK:
  Does @ticketpulse/shared contain unrelated utilities?
  Would a consumer of the date formatter also need the Kafka helpers?


CCP — Common Closure Principle
──────────────────────────────
"Classes that change together belong together."

This is SRP applied to packages. If a regulatory change requires
updating TaxCalculator, TaxRules, and TaxReport, they should be
in the same package.

TICKETPULSE CHECK:
  When the payment provider changes their API, how many packages
  need to change? If the answer is more than 1, those packages
  should be merged or reorganized.


CRP — Common Reuse Principle
────────────────────────────
"Classes used together belong together. Do not force users to
depend on things they do not need."

This is ISP applied to packages. If a consumer uses HttpClient
but not WebSocketClient, they should not be forced to install
a package containing both.

TICKETPULSE CHECK:
  Does importing @ticketpulse/shared pull in Kafka dependencies
  even when the consumer only needs type definitions?
```

**The tension:** CCP says "group things that change together" (larger packages). CRP says "do not force unnecessary dependencies" (smaller packages). Early on, favor CCP. For stable, widely-reused code, favor CRP.

### Coupling Principles: How Packages Relate

These are the principles you will enforce in CI.

```
ADP — Acyclic Dependencies Principle
─────────────────────────────────────
"The dependency graph must have no cycles."

If package A depends on B, B depends on C, and C depends on A,
you have a cycle. Cycles mean you cannot build, test, or release
packages independently.

BEFORE (cycle):       A → B → C → A
AFTER (acyclic):      A → B → C
                      A → IShared ← C

Breaking cycles: extract an interface/type into a new package
that both sides depend on. This is dependency inversion at the
package level.


SDP — Stable Dependencies Principle
────────────────────────────────────
"Depend in the direction of stability."

A STABLE package has many dependents and few dependencies.
It is hard to change because changes break many consumers.

An UNSTABLE package has few dependents and many dependencies.
It is easy to change because few things depend on it.

Unstable packages should depend on stable packages.
If a stable package depends on a volatile one, every change
to the volatile package destabilizes the foundation.

Instability metric: I = Ce / (Ca + Ce)
  Ca = afferent couplings (packages that depend on this one)
  Ce = efferent couplings (packages this one depends on)
  I = 0: maximally stable (many dependents, no dependencies)
  I = 1: maximally unstable (no dependents, many dependencies)


SAP — Stable Abstractions Principle
────────────────────────────────────
"Stable packages should be abstract. Unstable packages should
be concrete."

A stable package full of concrete implementations is rigid --
it is hard to change AND hard to extend. Stable packages should
contain abstractions (interfaces, types, domain events) that
concrete packages implement.

Abstractness metric: A = abstract classes / total classes
  A = 0: fully concrete
  A = 1: fully abstract
```

### 📊 Observe: TicketPulse's Package Landscape

Map TicketPulse's packages to stability and abstractness:

```
TICKETPULSE PACKAGES (analyze each)
════════════════════════════════════

Package                     │ Dependents │ Dependencies │ I    │ Abstract?
────────────────────────────┼────────────┼──────────────┼──────┼──────────
@ticketpulse/domain-types   │     8      │      0       │ 0.00 │ Yes (interfaces, types)
@ticketpulse/shared-utils   │     6      │      2       │ 0.25 │ Mixed
@ticketpulse/event-schemas  │     5      │      1       │ 0.17 │ Yes (event types)
@ticketpulse/order-service  │     0      │      5       │ 1.00 │ No (concrete)
@ticketpulse/payment-service│     0      │      4       │ 1.00 │ No (concrete)
@ticketpulse/event-service  │     0      │      4       │ 1.00 │ No (concrete)
@ticketpulse/persistence    │     3      │      2       │ 0.40 │ Mixed ⚠️
@ticketpulse/kafka-client   │     4      │      1       │ 0.20 │ Mixed ⚠️

HEALTHY PATTERN:
  Services (I=1.0, concrete) → Shared libs (I≈0.2, mixed) → Domain (I=0.0, abstract)

VIOLATIONS TO CHECK:
  Does @ticketpulse/persistence depend on any service package? (SDP violation)
  Does @ticketpulse/shared-utils contain concrete implementations? (SAP concern)
  Are there cycles? (ADP violation)
```

---

## Part 2: Visualize the Dependency Graph

### 🔍 Analyze: Finding Cycles and Violations

```bash
# Install dependency-cruiser
npm install -g dependency-cruiser

# Generate a visual dependency graph
npx depcruise --include-only "^src" --output-type dot src \
  | dot -T svg > dependency-graph.svg

# Generate a text report of violations
npx depcruise --include-only "^src" --output-type err src
```

A healthy dependency graph looks like a tree (directed acyclic graph). An unhealthy one looks like a web.

```
HEALTHY (acyclic, layered):

  order-service ──→ domain-types
  order-service ──→ kafka-client ──→ event-schemas
  payment-service → domain-types
  event-service ──→ domain-types
  event-service ──→ persistence ──→ domain-types


UNHEALTHY (cycles, cross-feature imports):

  order-service ──→ payment-service ──→ order-service  ← CYCLE
  event-service ──→ shared-utils ──→ kafka-client ──→ event-service  ← CYCLE
  persistence ────→ order-service  ← SDP VIOLATION (stable depends on unstable)
```

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Breaking a Cycle

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


If you find a cycle between order-service and payment-service:

```
BEFORE (cycle):
  order-service imports PaymentResult from payment-service
  payment-service imports OrderStatus from order-service

AFTER (acyclic):
  Extract shared types into @ticketpulse/domain-types:
    - PaymentResult interface
    - OrderStatus enum

  order-service imports PaymentResult from domain-types
  payment-service imports OrderStatus from domain-types
  No direct dependency between order and payment
```

---

## Part 3: Enforce with dependency-cruiser

### 🛠️ Build: CI Rules

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Create a `.dependency-cruiser.cjs` configuration that encodes the architectural rules:

```javascript
// .dependency-cruiser.cjs
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    // RULE 1: No circular dependencies (ADP)
    {
      name: "no-circular",
      severity: "error",
      comment: "Circular dependencies make packages impossible to build/test independently.",
      from: {},
      to: {
        circular: true,
      },
    },

    // RULE 2: Shared packages cannot import from feature packages (SDP)
    {
      name: "no-shared-to-feature",
      severity: "error",
      comment: "Stable shared packages must not depend on volatile feature packages.",
      from: {
        path: "^packages/shared",
      },
      to: {
        path: "^packages/features",
      },
    },

    // RULE 3: Feature packages cannot import from each other directly
    {
      name: "no-cross-feature-imports",
      severity: "error",
      comment:
        "Features must communicate through events or shared interfaces, not direct imports.",
      from: {
        path: "^packages/features/([^/]+)",
      },
      to: {
        path: "^packages/features/(?!\\1)", // different feature package
      },
    },

    // RULE 4: Domain types cannot depend on infrastructure
    {
      name: "no-domain-to-infra",
      severity: "error",
      comment: "Domain types must be pure -- no database, HTTP, or messaging dependencies.",
      from: {
        path: "^packages/domain",
      },
      to: {
        path: "(pg|redis|kafka|express|fastify|axios)",
        pathNot: "node_modules/@types",
      },
    },

    // RULE 5: No importing from node_modules not in package.json
    {
      name: "no-undeclared-deps",
      severity: "warn",
      comment: "All dependencies must be declared in the package's own package.json.",
      from: {},
      to: {
        dependencyTypes: ["npm-no-pkg", "npm-unknown"],
      },
    },
  ],

  options: {
    doNotFollow: {
      path: "node_modules",
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: "tsconfig.json",
    },
    reporterOptions: {
      dot: {
        collapsePattern: "node_modules/(@[^/]+/[^/]+|[^/]+)",
      },
    },
  },
};
```

### Add to CI Pipeline

```yaml
# In your CI configuration (GitHub Actions, etc.)
architecture-check:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
    - run: npm ci
    - name: Check architecture rules
      run: npx depcruise --config .dependency-cruiser.cjs --output-type err src
    - name: Generate dependency graph
      run: |
        npx depcruise --config .dependency-cruiser.cjs --output-type dot src \
          | dot -T svg > dependency-graph.svg
    - uses: actions/upload-artifact@v4
      with:
        name: dependency-graph
        path: dependency-graph.svg
```

### 📊 Observe: Run the Rules

When you run the rules against a codebase with violations:

```
ERROR: no-circular
  packages/features/orders/src/orderService.ts →
  packages/features/payments/src/paymentClient.ts →
  packages/features/orders/src/types.ts

ERROR: no-shared-to-feature
  packages/shared/utils/src/formatting.ts →
  packages/features/events/src/eventTypes.ts

WARN: no-undeclared-deps
  packages/features/orders/src/db.ts →
  pg (not in packages/features/orders/package.json)

3 errors, 1 warning. Build FAILED.
```

Each violation is a conversation. Not every violation needs to be fixed immediately, but every violation should be understood.

---

## Part 4: Architecture Fitness Functions

### Beyond Dependency Rules

Dependency-cruiser enforces structural rules. But architecture fitness functions are a broader concept: **any automated check that validates an architectural characteristic.**

```
ARCHITECTURE FITNESS FUNCTIONS
══════════════════════════════

Structural:
  - No circular dependencies (dependency-cruiser)
  - Layer boundaries respected (shared ← features)
  - No cross-feature imports

Performance:
  - API response time p99 < 200ms (load test in CI)
  - Database query time < 50ms for critical paths
  - Bundle size < 500KB (for any client-facing packages)

Security:
  - No secrets in code (git-secrets, truffleHog)
  - All dependencies scanned for vulnerabilities (npm audit)
  - No direct database access from API handlers (must go through repository layer)

Operational:
  - Every service has a health check endpoint
  - Every service emits structured logs
  - Every service has Prometheus metrics
  - Docker images < 200MB

Resilience:
  - Every external call has a timeout configured
  - Every external call has a circuit breaker
  - Retry logic uses exponential backoff (not fixed delay)
```

### 🛠️ Build: ESLint Rules for Architecture Boundaries

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


For boundaries that dependency-cruiser cannot enforce (intra-package structure):

```javascript
// .eslintrc.cjs -- custom architecture rules
module.exports = {
  rules: {
    // Prevent API handlers from importing database modules directly
    "no-restricted-imports": [
      "error",
      {
        patterns: [
          {
            group: ["**/repositories/*", "**/db/*", "pg", "knex"],
            message:
              "API handlers must not import database modules directly. Use the service layer.",
            // Only applies to files in routes/ or handlers/
          },
        ],
      },
    ],
  },

  overrides: [
    {
      // Only enforce the DB restriction in handler files
      files: ["**/routes/**", "**/handlers/**", "**/controllers/**"],
      rules: {
        "no-restricted-imports": [
          "error",
          {
            patterns: [
              {
                group: ["**/repositories/*", "**/db/*"],
                message:
                  "Handlers must use the service layer, not repositories directly.",
              },
            ],
          },
        ],
      },
    },
  ],
};
```

---

## Part 5: The Overhead Question

### 🤔 Reflect: When Is Enforcement Worth It?

```
THE OVERHEAD SPECTRUM
═════════════════════

Team of 3, single service:
  Fitness functions: probably overkill
  Dependency rules: unnecessary (everyone knows the codebase)
  Cost of violation: low (easy to refactor)
  → Rely on code review and shared understanding

Team of 8, 3-5 services, monorepo:
  Fitness functions: worth it for critical boundaries
  Dependency rules: enforce ADP (no cycles) and SDP (layer direction)
  Cost of violation: medium (takes a sprint to untangle)
  → This is TicketPulse. The sweet spot for automated rules.

Team of 30+, many services, monorepo:
  Fitness functions: essential
  Dependency rules: comprehensive, enforced in CI
  Cost of violation: high (can take quarters to fix)
  → Netflix, Uber, Airbnb territory. Build fails on architecture violations.
```

The cost-benefit calculation:

```
COST OF ENFORCEMENT:
  - Time to set up rules: 2-4 hours
  - Time to maintain rules: ~1 hour/month
  - Developer friction: occasional false positives
  - Workaround pressure: "can we just disable this rule for now?"

COST OF NOT ENFORCING:
  - Gradual architectural erosion (invisible until painful)
  - "Big bang" refactoring every 12-18 months
  - Deployment coupling (changing A requires deploying B)
  - Slower onboarding (new engineers cannot understand boundaries)
  - Knowledge trapped in individuals ("ask Sarah, she knows how this connects")
```

---

## 🤔 Final Reflections

1. **These rules create overhead. When is that overhead worth it? When does it slow you down more than it helps?** Think about team size, codebase age, and rate of change.

2. **What is the difference between enforcing boundaries in CI versus enforcing them in code review?** Which is more reliable? Which catches problems earlier? Which allows for exceptions?

3. **If you could enforce only ONE rule in CI, which would it be?** No circular dependencies? No cross-feature imports? Something else?

4. **How do you handle a legitimate need to violate an architectural boundary?** Does the rule have an escape hatch? Does the violation trigger an ADR?

5. **Martin defined these principles in 2002. Why did they take 20 years to become widely practiced?** What changed about how we build software that made them relevant?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **ADR** | Architecture Decision Record; a short document that captures a single architectural decision and its context. |
| **RFC** | Request for Comments; a design proposal shared with the team for feedback before a decision is finalized. |
| **Design doc** | A detailed document describing a proposed technical design, including alternatives considered and trade-offs. |
| **Decision record** | A log entry that captures the reasoning and outcome of a significant technical or process decision. |
| **Supersede** | The act of replacing a previous decision record with a new one when the context or choice changes. |

---

## Part 6: Hands-On — Apply the Rules to TicketPulse's Monorepo (25 min)

Reading about package principles is one thing. Actually running the tools against TicketPulse's codebase and fixing violations is another. This walkthrough takes you through the full cycle.

### Step 1: Install and Initialize dependency-cruiser

```bash
cd /path/to/ticketpulse

# Install dependency-cruiser as a dev dependency
npm install --save-dev dependency-cruiser

# Initialize a configuration
npx dependency-cruiser --init
# When prompted, choose: TypeScript, yes to tsconfig, no to webpack
```

### Step 2: Generate Your First Dependency Graph

```bash
# Generate an SVG of the full dependency graph
npx depcruise \
  --include-only "^packages" \
  --output-type dot \
  packages \
  | dot -T svg > dep-graph-before.svg

# Open it
open dep-graph-before.svg   # macOS
# or: xdg-open dep-graph-before.svg  # Linux
```

What you are looking for in the graph:
- **Arrows that go "upward"** (from a stable package to an unstable one) — SDP violations
- **Cycles** (circular arrows or patterns where you can follow arrows in a loop back to the start)
- **Cross-feature imports** (arrows between `features/orders` and `features/payments`)
- **Thick fan-in on shared packages** (many arrows pointing at one package = high coupling = change will be painful)

### Step 3: Run the Violation Report

```bash
# Run with the forbidden rules from Part 3
npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type err-long \
  packages \
  2>&1 | tee violations-report.txt

cat violations-report.txt
```

For each violation found, record it in this table:

```
| Rule Violated        | Source File                          | Target File                    | Why It Happened (guess) |
|----------------------|--------------------------------------|--------------------------------|-------------------------|
| no-circular          | features/orders/orderService.ts      | features/payments/client.ts    | Direct import for type  |
| no-shared-to-feature | shared/utils/formatting.ts           | features/events/eventTypes.ts  | Convenience import      |
| ...                  | ...                                  | ...                            | ...                     |
```

### Step 4: Fix One Circular Dependency From End to End

Pick the first circular dependency from your violations report. Here is the guided process:

```bash
# First, understand what the circular chain looks like
npx depcruise \
  --include-only "^packages/features/(orders|payments)" \
  --output-type dot \
  packages \
  | dot -T svg > cycle-detail.svg

open cycle-detail.svg
```

Typical circular dependency in TicketPulse:

```
orders/src/orderService.ts
  → imports PaymentResult from payments/src/paymentTypes.ts
  
payments/src/paymentService.ts
  → imports OrderStatus from orders/src/orderTypes.ts
```

**The fix (dependency inversion)**:

```bash
# Step 1: Create a new shared types package
mkdir -p packages/shared/domain-events/src
cat > packages/shared/domain-events/package.json << 'EOF'
{
  "name": "@ticketpulse/domain-events",
  "version": "1.0.0",
  "main": "dist/index.js",
  "types": "dist/index.d.ts"
}
EOF

# Step 2: Move the shared types here
cat > packages/shared/domain-events/src/index.ts << 'EOF'
// Types that both orders and payments depend on
// Neither orders nor payments owns these — the domain does

export enum OrderStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  CANCELLED = 'cancelled',
  REFUNDED = 'refunded',
}

export interface PaymentResult {
  success: boolean;
  transactionId: string;
  amountCharged: number;
  currency: string;
  failureReason?: string;
}

export interface OrderPaymentEvent {
  orderId: string;
  userId: string;
  result: PaymentResult;
  processedAt: Date;
}
EOF
```

```typescript
// packages/features/orders/src/orderTypes.ts
// BEFORE (causes the cycle):
import { PaymentResult } from '../../payments/src/paymentTypes';

// AFTER (no cycle — both depend on shared):
import { PaymentResult } from '@ticketpulse/domain-events';
```

```typescript
// packages/features/payments/src/paymentService.ts
// BEFORE (causes the cycle):
import { OrderStatus } from '../../orders/src/orderTypes';

// AFTER (no cycle):
import { OrderStatus } from '@ticketpulse/domain-events';
```

After the fix, run the violation report again:

```bash
npx depcruise --config .dependency-cruiser.cjs --output-type err packages
# The no-circular violation should be gone
```

### Step 5: Add the Architecture Check to CI

```bash
# .github/workflows/architecture.yml
cat > .github/workflows/architecture.yml << 'EOF'
name: Architecture Check

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  check-architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - run: npm ci
      
      - name: Validate architecture rules
        run: |
          npx depcruise \
            --config .dependency-cruiser.cjs \
            --output-type err \
            packages
        
      - name: Generate dependency graph
        if: always()  # Generate even if violations found
        run: |
          npm install -g graphviz || apt-get install -y graphviz
          npx depcruise \
            --config .dependency-cruiser.cjs \
            --output-type dot \
            packages \
            | dot -T svg > dependency-graph.svg
        
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: dependency-graph
          path: dependency-graph.svg
EOF
```

Now every pull request automatically validates architecture rules. Violations block the merge. The dependency graph artifact lets reviewers see the structure without running the tool locally.

---

## Part 7: Extended Reflection — The Hard Cases (15 min)

Package principles are clear in theory and messy in practice. Work through these real situations.

### Hard Case 1: The "Just This Once" Exception

A product manager asks for a hotfix that requires the `order-service` to read a pricing rule directly from the `pricing-service` database. Your dependency rules forbid cross-feature imports.

You could:
a) Add a `dependency-cruiser-ignore` comment to bypass the rule
b) Create a proper API endpoint in pricing-service and call it over HTTP
c) Temporarily add the exception to the rule config with an explanatory comment and a TODO

Which do you choose? Under what time pressure does your answer change?

> **Guided thinking**: Option (b) is architecturally correct but takes longer. For a true production emergency, option (c) is defensible — add the exception in the config with `// HOTFIX: remove by <date>, tracked in JIRA-1234`. The key: the exception is visible, documented, and time-bounded. Option (a) buries the exception in source code where it is invisible to future maintainers.

### Hard Case 2: The Performance Exception

Profiling shows that calling the `event-service` API from the `order-service` (correct architecture) adds 8ms of latency per order. Directly importing the event lookup function (wrong architecture) would reduce that to 0.3ms.

The order flow is latency-sensitive: users see checkout slowness above 400ms. You are currently at 390ms.

How do you resolve this tension?

> **Guided thinking**: Before violating the architectural boundary, exhaust the correct-architecture options:
> - Cache the event data in `order-service` (Redis, short TTL) — eliminates most of the 8ms
> - Use a local read replica of the events data (database-level, not code-level coupling)
> - Move the checkout to a co-located service that has fast access to both
> 
> If none of these work and the 8ms genuinely cannot be removed, document it as an ADR: "We accepted a cross-feature dependency for the order-checkout critical path due to latency constraints. We will revisit when we implement a service mesh with connection pooling."

### Hard Case 3: The New Engineer Problem

A new engineer joins the team. On their first PR, they add an import from `features/analytics` inside `features/orders`. Your CI rule catches it. Their response: "This is the most natural way to do what I needed. Why does this rule exist?"

How do you explain it in a way that builds understanding rather than frustration?

> **Guided thinking**: Start with what would go wrong, not the rule itself:
> "If orders depends on analytics, then deploying analytics requires also deploying orders (or at least verifying it still works). Now you cannot deploy an analytics fix independently. Over time, you would end up with a dependency chain where changing any one component requires coordinating a dozen deployments. The rule exists to keep our deployments independent."
> 
> Then: "What were you trying to do? Let us find a way to do it that respects the boundary — maybe through an event emitted by orders that analytics consumes, or by extracting the shared logic into a shared package."

---

### 🤔 Reflection Prompt

After running dependency-cruiser on TicketPulse, what surprised you about the actual dependency graph vs what you expected? How many boundary violations existed before you added enforcement rules?

> **Want the deep theory?** See Ch 32 of the 100x Engineer Guide: "Package & Module Design Principles" — the full theoretical foundation including coupling metrics, zone of pain/uselessness, and the Main Sequence.

---

## Further Reading

- **Chapter 32, Section 10**: Package & Module Design Principles -- the full theoretical foundation
- **"Agile Software Development: Principles, Patterns, and Practices"** by Robert C. Martin, Part IV -- the original package principles
- **dependency-cruiser documentation**: github.com/sverweij/dependency-cruiser
- **"Building Evolutionary Architectures"** by Neal Ford, Rebecca Parsons, Patrick Kua -- the book that coined "architecture fitness functions"
- **Nx module boundaries**: nx.dev -- monorepo tooling with built-in boundary enforcement
- **ArchUnit** (Java/Kotlin): archunit.org -- architecture testing for JVM projects
---

## What's Next

In **DORA Metrics & Team Performance** (L3-M78), you'll build on what you learned here and take it further.

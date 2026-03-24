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

> 💡 **Insight**: "Robert C. Martin defined the package principles in 2002, but they did not become widely practiced until monorepos became popular. In a monorepo, bad dependencies compile and run fine -- the boundary violations only show up as pain during refactoring, deployment, and scaling."

---

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

### 🛠️ Build: Breaking a Cycle

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

## Further Reading

- **Chapter 32, Section 10**: Package & Module Design Principles -- the full theoretical foundation
- **"Agile Software Development: Principles, Patterns, and Practices"** by Robert C. Martin, Part IV -- the original package principles
- **dependency-cruiser documentation**: github.com/sverweij/dependency-cruiser
- **"Building Evolutionary Architectures"** by Neal Ford, Rebecca Parsons, Patrick Kua -- the book that coined "architecture fitness functions"
- **Nx module boundaries**: nx.dev -- monorepo tooling with built-in boundary enforcement
- **ArchUnit** (Java/Kotlin): archunit.org -- architecture testing for JVM projects

<!--
  CHAPTER: 8
  TITLE: Testing & Quality Engineering
  PART: II — Applied Engineering
  PREREQS: None
  KEY_TOPICS: TDD, BDD, property-based testing, mutation testing, unit/integration/E2E, contract testing, performance testing, code quality, refactoring
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 8: Testing & Quality Engineering

> **Part II — Applied Engineering** | Prerequisites: None | Difficulty: Intermediate

The discipline of proving your code works — testing philosophies, test types for every situation, and the code quality practices that prevent bugs from being written in the first place.

### In This Chapter
- Testing Philosophy
- Test Types
- Testing Distributed Systems
- Performance Testing
- Testing Strategies
- Code Quality

### Related Chapters
- Chapter 15 (linting/CI enforcement)
- Chapter 18 (debugging when tests miss bugs)
- Chapter 4 (performance testing)

---

## 1. TESTING PHILOSOPHY

### Testing Models

**Testing Pyramid (Cohn):** Many unit tests → some integration → few E2E. Best for backend/libraries.
**Testing Trophy (Dodds):** Static analysis base → thin unit → thick integration → few E2E. Best for frontends.
**Testing Diamond (Spotify):** Few unit → thick integration → few E2E. Best for microservices.

### Methodologies

**TDD (Red-Green-Refactor):** Write failing test → minimum code to pass → refactor. Design tool, not just testing tool.
**BDD (Given-When-Then):** Gherkin syntax for non-technical stakeholders. Overhead if stakeholders don't actually read specs.
**Property-Based Testing:** Define invariants, framework generates random inputs. Finds edge cases humans miss. Tools: fast-check (JS), Hypothesis (Python).
**Mutation Testing:** Mutate source code, check if tests catch it. Gold standard for test quality. Tools: Stryker (JS), PIT (Java).

---

## 2. TEST TYPES

### Unit Testing
- **Sociable (Detroit school):** Real collaborators, mock only external deps. Catches integration issues.
- **Solitary (London school):** Mock everything. Precise failure localization.
- **Test Doubles:** Dummy (unused), Stub (canned answers), Spy (records calls), Mock (pre-programmed expectations), Fake (working but simplified implementation).

### Integration Testing
- **Narrow:** Your code + one external system (e.g., repository + real Postgres via Testcontainers).
- **Broad:** Multiple components through a significant slice. Slower, catches cross-cutting issues.

### Contract Testing (Pact)
Consumer writes expectations → shared via Pact Broker → provider verifies. No need to deploy both simultaneously.

### End-to-End Testing
Real browser, real deployment. Slow, expensive, flaky. Keep to 5-15 critical paths. Tools: Playwright, Cypress.

### Snapshot Testing
Capture output, compare to stored snapshot. Easy to "update all" without reviewing. Best with small, focused snapshots.

---

## 3. TESTING DISTRIBUTED SYSTEMS

- **Service Virtualization:** Simulate dependencies (WireMock, Mountebank). Combine with contract tests.
- **Testcontainers:** Real databases/brokers in Docker for integration tests.
- **Async Workflows:** "Eventually" assertions with timeout and polling interval.
- **Eventual Consistency:** Test convergence, not immediate correctness.
- **Idempotency:** Send same request N times, assert side effect occurs once.
- **Circuit Breakers:** Inject failures, verify state transitions (closed → open → half-open → closed).
- **Retries:** Counter-based stubs. Test both success-after-retry and all-retries-exhausted paths.

---

## 4. PERFORMANCE TESTING

| Type | Purpose |
|---|---|
| **Load** | Verify SLOs under expected traffic |
| **Stress** | Find the breaking point |
| **Soak/Endurance** | Find memory leaks, resource exhaustion over hours |
| **Spike** | Test auto-scaling response to sudden surges |
| **Capacity** | Determine maximum capacity of current infrastructure |

**Tools:** k6 (JS scripting), Gatling (Scala), Locust (Python), Artillery (Node.js).

**Profiling:** CPU flame graphs (`perf`, `py-spy`), heap snapshots, slow query logs, distributed tracing (Jaeger, OpenTelemetry).

---

## 5. TESTING STRATEGIES

### Test Data Management
- **Factories/Builders:** Programmatic with defaults (Factory Bot, Fishery, Faker)
- **Fixtures:** Static, brittle
- **Production subsets:** Realistic but requires anonymization

### Flaky Test Management
Detect → Quarantine → Fix within 2 weeks or delete. Prevention: no `sleep()`, fresh state per test, unique resource names.

### Test Coverage Philosophy
- **Line coverage:** Useful negative indicator (low = under-tested), poor positive indicator
- **Branch coverage:** More meaningful, catches untested error paths
- **Mutation coverage:** Gold standard, expensive to compute
- Target 80%+ line as hygiene. Never chase 100%.

### Testing in Production
- **Feature Flags:** Deploy behind flag, enable gradually
- **Dark Launches:** Run new + old code, return old result, compare offline (GitHub's Scientist library)
- **Traffic Mirroring:** Copy production traffic to new version, discard responses

---

## 6. CODE QUALITY

### Static Analysis
Type checking, security scanning (SAST), complexity analysis, dependency analysis.
Tools: TypeScript, ESLint, SonarQube, Semgrep, CodeQL.

### Refactoring Patterns (Fowler)
Extract Function, Inline Function, Extract Variable, Rename, Replace Conditional with Polymorphism, Introduce Parameter Object, Move Function.

### Code Smells
| Smell | Refactoring |
|---|---|
| Long Method (>20 lines) | Extract Function |
| Large Class | Extract Class |
| Feature Envy | Move Function |
| Data Clumps | Parameter Object |
| Primitive Obsession | Value Objects (`EmailAddress` not `string`) |
| Shotgun Surgery | Move related logic together |
| Dead Code | Delete it. Git remembers. |

### Code Review Best Practices
- Small PRs (<400 lines). Review within 4 hours.
- Focus on: correctness, error handling, security, performance, observability.
- Approve with minor comments. Don't create round-trips for trivialities.

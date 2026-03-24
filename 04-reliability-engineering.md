<!--
  CHAPTER: 4
  TITLE: Reliability Engineering & Operations
  PART: I — Foundations
  PREREQS: Chapters 1, 3
  KEY_TOPICS: SRE, SLOs/SLIs, error budgets, observability, circuit breaker, bulkhead, retry, incident management, chaos engineering, performance engineering
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 4: Reliability Engineering & Operations

> **Part I — Foundations** | Prerequisites: Chapters 1, 3 | Difficulty: Intermediate to Advanced

Keeping systems alive — how to measure reliability, build resilience into systems, respond to incidents, and engineer for performance.

### In This Chapter
- Site Reliability Engineering (SRE)
- Observability
- Resilience Patterns
- Incident Management
- Chaos Engineering
- Performance Engineering

### Related Chapters
- [Ch 1: System Design Paradigms & Philosophies] — failure modes in distributed systems
- [Ch 18: Debugging & Monitoring Tools] — debugging/monitoring tools
- [Ch 7: Deployment Strategies] — deployment strategies for reliability

---

## 1. SITE RELIABILITY ENGINEERING (SRE)

### Core Concepts

**SLIs (Service Level Indicators):** Quantitative measures from the user's perspective.
- Request-based: availability, latency, quality
- Pipeline-based: freshness, correctness
- Storage-based: durability, throughput

**SLOs (Service Level Objectives):** Target values for SLIs over a rolling window.
Example: "99.9% of HTTP requests complete successfully within 300ms over 30 days."

**SLAs (Service Level Agreements):** Contractual commitments with business consequences. Always looser than SLOs.

**Error Budgets:** Inverse of SLO. 99.9% SLO = 0.1% error budget ≈ 43.2 minutes/month. When exhausted, prioritize reliability over features.

**Toil Elimination:** Manual, repetitive, automatable work. Target <50% of engineer time.

**Reliability Hierarchy:** Monitoring → Incident response → Postmortem → Testing/release → Capacity planning → Development → Product

**Blameless Postmortem Culture:** Focus on what/why, not who. Systems must tolerate human error.

---

## 2. OBSERVABILITY

### Three Pillars

**Logs:** Discrete event records. Use structured logging (JSON). Include correlation IDs.

**Metrics:**
- **Counters:** Monotonically increasing (total requests). Derive rates.
- **Gauges:** Point-in-time values (memory usage, queue depth).
- **Histograms:** Distribution across buckets. Enable percentile calculations.
- RED method (Rate, Errors, Duration) for request-driven services.
- USE method (Utilization, Saturation, Errors) for resources.

**Traces:** Follow a request across services. Spans with start time, duration, metadata. **OpenTelemetry** is the vendor-neutral standard.

### Alerting Philosophy
- Alert on symptoms (user-facing impact), not causes
- Every alert must be actionable
- Multi-window, multi-burn-rate alerting on SLOs
- Page only for active emergencies; everything else goes to ticket queue

### Dashboard Layers
1. Executive: uptime, SLA compliance, error budget
2. Service: SLIs, saturation signals
3. Debug: per-instance metrics, span waterfalls
4. Infrastructure: node health, network I/O

---

## 3. RESILIENCE PATTERNS

### Circuit Breaker
**Closed** (normal) → failures exceed threshold → **Open** (fail fast) → timeout → **Half-Open** (probe) → success → **Closed**

### Bulkhead Isolation
Separate thread pools, connection pools, or process groups per dependency. Failure in one cannot exhaust resources for others.

### Timeout Strategies
- Connection timeout (1-5s), read timeout (varies), overall timeout
- **Deadline propagation:** Pass remaining budget downstream

### Retry Policies
- Exponential backoff with jitter: `sleep = random(0, base * 2^attempt)`
- Retry budget: cap at 10% of original requests
- Only retry idempotent operations on transient errors

### Rate Limiting
- **Token bucket:** Allows bursts up to bucket size
- **Leaky bucket:** Smooths bursts into steady flow
- **Sliding window:** Most precise

### Back-Pressure
Signal upstream to slow down. HTTP 429 + Retry-After, TCP flow control, reactive streams.

### Load Shedding
Drop low-priority requests to preserve capacity for high-priority ones.

---

## 4. INCIDENT MANAGEMENT

### Lifecycle
Detection → Triage → Mobilization → Investigation → Mitigation → Resolution → Postmortem

### Severity Levels
| Level | Criteria | Response |
|---|---|---|
| SEV1 | Complete outage, data loss, security breach | All hands, 15-min updates |
| SEV2 | Major feature degraded | On-call + experts, 30-min updates |
| SEV3 | Minor degradation | On-call, next business day |
| SEV4 | Cosmetic | Ticket queue |

### On-Call Best Practices
- 1-week rotations with handoff docs
- Target <2 pages per 12-hour shift
- Runbooks for every alert
- Shadow on-call for new team members

---

## 5. CHAOS ENGINEERING

### Principles
1. Define steady state (SLIs)
2. Hypothesize steady state continues
3. Introduce real-world events (kill instances, inject latency, fill disks)
4. Try to disprove hypothesis
5. Minimize blast radius

### Game Days
Scheduled chaos experiments. Build muscle memory for incident response AND reveal monitoring gaps.

---

## 6. PERFORMANCE ENGINEERING

### Latency Percentiles
- **p50 (median):** Typical experience
- **p95:** The "unlucky" user (1 in 20)
- **p99:** Tail latency (often 3-10x median)
- Never use averages. Percentiles reveal truth.
- **Tail latency amplification:** Fan-out to 100 services with p99=10ms → 63.4% chance at least one exceeds 10ms.

### Key Laws
**Amdahl's Law:** Speedup limited by serial portion. If 5% serial, max speedup = 20x.
**Little's Law:** `L = λ * W` (items in system = arrival rate × time per item). Fundamental for capacity planning.
**Queueing Theory:** At 80% utilization, wait time = 4x service time. At 90%, 9x. Keep steady-state below 70-80%.

### Load Testing Types
- **Smoke:** Minimal load, verify system works
- **Load:** Expected traffic, validate SLOs
- **Stress:** Beyond peak, find breaking point
- **Soak:** Sustained hours/days, find memory leaks
- **Spike:** Sudden surge, test auto-scaling

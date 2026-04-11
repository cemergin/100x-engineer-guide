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
- **OBSERVABILITY spiral:** → [Ch 18: Debugging & Monitoring](../part-4-cloud-operations/18-debugging-profiling-monitoring.md)
- [Ch 1: System Design Paradigms & Philosophies] — failure modes in distributed systems
- [Ch 18: Debugging & Monitoring Tools] — debugging/monitoring tools
- [Ch 7: Deployment Strategies] — deployment strategies for reliability

---

## 1. SITE RELIABILITY ENGINEERING (SRE)

### 1.1 The Problem SRE Solves

Here's a tension that plays out at every growing tech company: your product team wants to ship features faster. Your operations team wants the system to stop changing so it stops breaking. Left unchecked, this ends one of two ways — either you slow to a crawl of change-control theater, or you move fast and periodically break things in spectacular, customer-visible ways.

SRE is Google's answer to this tension. The core insight, articulated in the first Google SRE book, is that **reliability is a feature** — one that competes with other features for engineering time. And if you treat it that way, you can reason about the trade-off mathematically instead of emotionally.

The mechanism that makes this work is the error budget.

But before you can have an error budget, you need to know what "reliable" means for your specific service. That's where SLIs and SLOs come in.

### 1.2 SLIs — Measuring What Users Actually Experience

**SLIs (Service Level Indicators)** are quantitative measures of service behavior, chosen specifically from the user's perspective. The key word is *user's perspective*. CPU utilization is not an SLI. Error rate is. Disk I/O wait is not an SLI. How long users wait for their page to load is.

**Why this matters:** It's shockingly easy to build beautiful dashboards full of infrastructure metrics that look healthy while users are having a terrible time. You can have 10% CPU usage, 2% memory pressure, and zero disk errors — while your database connection pool is exhausted and every user is getting a 500 after a 30-second timeout. Metrics that aren't anchored to user experience are distractions.

The three main families of SLIs:

**Request-based SLIs** (the most common):
- **Availability:** What fraction of requests succeeded? Usually measured as `(valid requests - errors) / valid requests`. The "valid" qualifier matters — you don't want 400s (client errors) to count against your availability.
- **Latency:** What fraction of requests completed within a threshold? Note: this is framed as a *proportion*, not a raw percentile. "95% of requests complete within 200ms over the past 30 days" — that's an SLI.
- **Quality:** For services that degrade gracefully, what fraction of requests received a full-quality response vs. a degraded one?

**Pipeline-based SLIs** (for batch and streaming systems):
- **Freshness:** How old is the data being served? If your reporting pipeline is processing yesterday's data, that's a freshness violation.
- **Correctness:** What fraction of pipeline outputs have the right answer? Hard to measure, but critical for data-serving systems.

**Storage-based SLIs:**
- **Durability:** What fraction of written records can later be retrieved? This is typically 99.999999% for storage systems and hard to observe directly — you measure it via synthetic monitoring.
- **Throughput:** Is the storage system keeping up with write load?

**Choosing good SLIs takes judgment.** The temptation is to pick whatever metrics you already collect. Resist that. Work backwards from user journeys. A user posting a photo to your social media app has a journey: (1) photo upload succeeds, (2) photo is processed and available within a reasonable time, (3) photo appears in their feed. Those stages map to SLIs.

One useful framing: write down the top five ways your users would say your service is broken. Now figure out how to measure each one. Those are your SLIs.

### 1.3 SLOs — Your Reliability Contract with Yourself

**SLOs (Service Level Objectives)** are target values for SLIs over a rolling window. They're the line in the sand that answers the question: "how good does 'good enough' need to be?"

A well-formed SLO looks like: *"99.9% of HTTP requests to /api/search complete within 500ms over any rolling 30-day window."*

Let's decompress that:
- **99.9%** — the target. Not 100%, never 100%.
- **HTTP requests to /api/search** — scoped to a specific request type or service.
- **within 500ms** — the threshold that distinguishes "good" from "bad."
- **over any rolling 30-day window** — the measurement window.

**Why rolling windows?** Because a fixed calendar month creates perverse incentives. If you exhausted your error budget on March 15th, you might be very risk-averse until April 1st, then very risk-tolerant on April 2nd. A rolling window keeps the pressure constant.

**Why 99.9% and not 100%?** Because 100% is impossible, and pursuing it is expensive and counterproductive. Perfect availability requires never deploying, never changing hardware, never upgrading dependencies. The exact right answer depends on your users' actual needs and your system's architecture.

**The art of SLO calibration:**

*Set the SLO too tight* and you spend all your time firefighting. Every deploy causes an alert. Engineers get burned out. The SLO becomes meaningless because everyone knows it's always red.

*Set the SLO too loose* and users are suffering but your dashboards are green. You get false confidence. You discover you have a reliability problem when users start leaving, not from your monitoring.

*The sweet spot* is an SLO that's just tighter than what your users actually need. Not tighter than that — there's no benefit to being more reliable than users require, and it costs engineering time that could go toward features.

A good way to calibrate: look at your historical data. Where are you today? Is that acceptable to users? Survey users or look at support tickets. Then set an SLO slightly above where you are, giving you a path to improve rather than an unreachable goal.

**SLOs vs. SLAs:**

**SLAs (Service Level Agreements)** are contractual commitments with business consequences — refunds, penalties, contract termination. They're always *looser* than your SLOs. If your SLO is 99.9%, your SLA might be 99.5%. The gap is a buffer. You want to know you're violating your SLO before you're violating your SLA, so you have time to react before there are business consequences.

The SLA is the floor. The SLO is the target you actually manage to. Never let your SLO be your SLA — if they're the same, you have no warning time.

### 1.4 Error Budgets — The Strategic Heart of SRE

Here's where it gets interesting. Your SLO is 99.9%. That means your **error budget** is 0.1%. In a 30-day month with roughly 43,200 minutes, that's 43.2 minutes of downtime (or equivalent badness) you're allowed before you've violated your SLO.

That number — 43.2 minutes — is not a punishment. It's a resource. It's the budget you have to spend on risky things: deployments, infrastructure migrations, experiments, new features. Every time you deploy and there's a brief degradation, you're spending error budget. Every time a dependency flakes, you spend error budget. Every time you turn on a feature flag and the new code has a bug, you spend error budget.

**The game-changing implication:** when your error budget is healthy (you've used less than your allotment), you can move fast. Deploy more. Take risks. Ship features. When your error budget is exhausted, you slow down. Freeze deployments. Focus on reliability improvements. The error budget is the *automatic* mechanism that balances velocity against reliability.

This shifts the conversation between product and engineering from "are we too slow?" or "did we break production again?" to "how's our error budget?" It's quantitative, non-personal, and tied directly to user impact.

In the TicketPulse course (L1-M26), you'll calculate TicketPulse's first real error budgets from scratch — define the SLOs, pull historical request counts from Prometheus, and wire the resulting budget to a deployment gate in GitHub Actions. When you see the gate actually block a merge because the monthly budget is 73% consumed and there are 8 days left, the abstraction becomes a physical reality you'll never forget.

**What happens when you run out:**

The policy consequences of an exhausted error budget are something your organization has to decide in advance, ideally before any specific incident. Common policies:
- No new feature deployments until the budget is replenished (the full-stop approach)
- Deployments require sign-off from SRE leadership
- The team shifts a fixed percentage (e.g., 50%) of engineering capacity to reliability work until the budget recovers

The policy needs teeth. If the error budget runs out and nothing changes, it's just a number on a dashboard.

**How error budgets change the product-engineering conversation:**

Before error budgets, the conversation went like this: the product manager wants to ship a new feature. The engineer says "we need to stabilize first." The product manager says "but we committed to this feature." Everyone is arguing from opinion and political leverage, not data.

After error budgets, the conversation sounds different. "Our error budget is at 72% consumed with 18 days left in the month. At this burn rate, we'll exhaust it in 11 days. What's the plan?" Now both sides are looking at the same number. Shipping a new feature that carries risk means burning more budget. Whether to do that is a business decision — but it's a data-driven one. The engineer isn't being obstructionist; they're flagging that the budget is the constraint. The product manager isn't being reckless; they're making an explicit trade-off.

This change in conversation quality is underrated. Teams that adopt error budgets report that reliability stops being an emotional topic at sprint planning and becomes an operational input, like capacity or headcount.

**Worked example: Calculating SLOs and error budgets**

Let's say you're running an e-commerce checkout service with an availability SLO of 99.9% over a 30-day rolling window.

Step 1 — Compute the total request budget. Over 30 days your service handles roughly 4 million requests (based on historical data). Your SLO allows 0.1% to fail:

```
Error budget (requests) = 4,000,000 * 0.001 = 4,000 failed requests
```

Step 2 — Translate to time. If your average request rate is 1,543 req/s and you experience a complete outage, you burn:

```
Time budget = 4,000 / 1,543 req/s ≈ 2.6 seconds of complete outage per 4,000 failed requests
```

More usefully in minutes: 30 days = 43,200 minutes. 0.1% of that is 43.2 minutes.

Step 3 — Track what you've spent. Suppose this month you've had:
- Deploy on the 8th with 3-minute degraded state (about 277,000 requests in that window, 5% error rate): consumed ≈ 13,850 failed requests
- Wait — that alone exceeds the budget of 4,000 failed requests.

That's the point. A single messy deploy can consume the entire monthly budget in minutes. When you make this visible, teams immediately see why careful release practices matter. It's not abstract "quality" talk — it's a finite resource they can actually see depleting.

**Multi-burn-rate alerting:**

One nuance that the original Google SRE workbook introduced: you need to alert when you're *burning* error budget too fast, not just when you've exhausted it. If you're burning your monthly error budget in a single day, that's a crisis — you should be paged immediately. If you're burning it slowly over several days, that's still bad but less urgent.

This leads to multi-window, multi-burn-rate alerting (covered more in Section 2), where you have different alert thresholds for different burn rates:
- Fast burn (e.g., 14x normal rate): page the on-call immediately
- Slow burn (e.g., 5x normal rate): create a ticket, investigate within a day
- Near-exhaustion: longer-horizon warning to prompt conversation

**Worked example: Multi-window burn rate calculations**

Continuing the checkout example (99.9% SLO, 30-day window):

```
Monthly error budget = 0.1% of all requests
Normal hourly burn rate = 0.1% / (30 * 24) = 0.000139% per hour

Fast-burn threshold (14x): 14 * 0.000139% = 0.00194% per hour
  → "Alert if hourly error rate exceeds 0.00194%"
  → At this rate, budget exhausts in: 30 days / 14 = ~2.1 days

Slow-burn threshold (5x): 5 * 0.000139% = 0.000694% per hour
  → "Ticket if hourly error rate exceeds 0.000694%"
  → At this rate, budget exhausts in: 30 days / 5 = 6 days
```

In Prometheus/Alertmanager, this looks like:

```yaml
# Fast burn — page immediately
- alert: ErrorBudgetBurnRateFast
  expr: |
    (
      rate(http_requests_errors_total[1h]) / rate(http_requests_total[1h])
    ) > (14 * 0.001)
  for: 2m
  labels:
    severity: page
  annotations:
    summary: "Error budget burning at 14x rate — exhaustion in ~2 days"

# Slow burn — create ticket
- alert: ErrorBudgetBurnRateSlow
  expr: |
    (
      rate(http_requests_errors_total[6h]) / rate(http_requests_total[6h])
    ) > (5 * 0.001)
  for: 30m
  labels:
    severity: ticket
  annotations:
    summary: "Error budget burning at 5x rate — exhaustion in ~6 days"
```

The two-window approach (1h and 6h) prevents false positives: a single spike triggers the 1h window, but a sustained slow degradation triggers the 6h window. Together they give you both speed and signal quality.

### 1.5 Toil — The Other Resource Drain

**Toil** is the manual, repetitive, automatable work tied to running a service. Handling a deployment manually. Restarting a crashed service. Cleaning up old logs. Responding to alerts that don't require human judgment.

Toil is distinct from overhead (meetings, planning) and engineering work (building new things, improving reliability). The Google guideline is that on-call engineers should spend less than 50% of their time on toil. If more than half your engineering time is toil, you're essentially running a manual system that happens to have code attached.

Why does this matter so much? Because toil is the silent killer of engineering organizations. It doesn't show up as a P0 incident. It doesn't get escalated. It just slowly fills engineers' days until there's no capacity left for actual improvement work. The system becomes unable to improve because everyone is too busy operating it.

The measure of a good SRE team is not how well they handle incidents — it's how much the operation of their services has been automated away.

### 1.6 The Reliability Hierarchy

When you're building reliability practices from scratch, it's tempting to go straight to the interesting stuff — chaos engineering, SLO frameworks, blameless postmortems. But there's a natural order to reliability investments, and violating it doesn't work.

The hierarchy, from foundation to peak:

1. **Monitoring** — You cannot improve what you cannot measure. Get logs, metrics, and alerts in place first. Even bad monitoring beats no monitoring.
2. **Incident response** — Have a process for when things break. On-call rotation, runbooks, escalation paths. Before this exists, incidents are chaotic and inconsistent.
3. **Postmortem culture** — After incidents are contained, build the habit of learning from them. This is where systematic improvement comes from.
4. **Testing and release** — Invest in automated testing and safer deployment practices (canary, blue-green). This is the first lever that reduces incident frequency rather than improving response.
5. **Capacity planning** — Understand your growth trajectory. Scale proactively rather than reactively.
6. **Development** — SRE principles feeding back into how the service is developed: design reviews, reliability requirements, SLO-driven feature trade-offs.
7. **Product** — The product roadmap incorporates reliability as a first-class concern, alongside feature work.

You have to do them roughly in this order because each layer depends on the ones below it. You can't do blameless postmortems if your incident response is chaos. You can't do meaningful capacity planning if you don't have monitoring. The hierarchy is a dependency graph.

### 1.7 Blameless Postmortem Culture

The postmortem is one of the most powerful tools in reliability engineering, and also one of the most frequently broken.

The blameless postmortem comes from a deceptively simple insight: **systems must be designed to tolerate human error.** People will make mistakes. Always. If your response to a mistake is to punish the person who made it, two things happen: (1) people hide mistakes, so you lose signal, and (2) you don't fix the system, so the mistake happens again with someone else's name attached.

A blameless postmortem asks: *what* happened, and *why* did the system allow it to happen? Not *who* did it.

**What a good postmortem contains:**
- **Timeline:** Minute-by-minute reconstruction of the incident. What was observed, by whom, at what time. What actions were taken, when, and what effect they had.
- **Root cause analysis:** Usually via Five Whys or a cause-and-effect diagram. Keep asking "why" until you hit something you can actually fix.
- **Contributing factors:** The root cause is rarely a single thing. List everything that made the incident worse or harder to resolve.
- **Impact:** Actual user impact, error budget consumed, SLO status.
- **Action items:** Specific, assigned, time-bounded. Not "improve monitoring" but "add alert for database connection pool exhaustion by [date] [owner]."

**The cultural piece:** Postmortems only work if they're genuinely blameless. Leadership sets this tone. If you ever see a postmortem where the action item is "engineer X should be more careful," the culture is broken. The action item should be "add validation to prevent that category of mistake."

---

## 2. OBSERVABILITY

### 2.1 Why "Monitoring" Isn't Enough

Traditional monitoring answers a specific question you thought to ask in advance. Is CPU over 80%? Is the site reachable? Is the queue depth above threshold? You have to know what might break and instrument for it.

**Observability** is the property of a system that lets you understand its internal state from its external outputs — including questions you didn't think to ask in advance. It's the difference between a system you can only monitor vs. a system you can debug.

The distinction matters at scale. In a monolith with five services, you can instrument for every failure mode you can imagine and probably cover it. In a microservices architecture with hundreds of services, the failure modes are a combinatorial explosion. You cannot anticipate all of them. You need to be able to investigate novel failures with the data you already have.

Observability is made up of three pillars, each giving you a different lens on the same system.

### 2.2 The Three Pillars

The three pillars of observability are logs, metrics, and traces. They're complementary, not redundant — each answers different questions and has different cost/query tradeoffs. Think of them as three lenses on the same system.

**Pillar 1: Logs**

Logs are discrete event records — a timestamped description of something that happened. They're the oldest and most widespread form of observability data.

The transition from unstructured to **structured logging** (using JSON or a similar format) is one of the highest-ROI observability investments you can make. Unstructured logs are readable by humans in isolation but opaque to machines. Structured logs are queryable, filterable, and joinable — you can ask "show me all events where user_id=12345 and status_code=500 in the last hour" and get an answer instantly.

Compare:

```
# Unstructured (hard to query programmatically)
2026-03-15 14:23:11 ERROR PaymentProcessor: charge failed for user 12345, amount $49.99, reason: card_declined

# Structured (queryable, filterable, joinable)
{
  "timestamp": "2026-03-15T14:23:11.234Z",
  "level": "error",
  "service": "payment-processor",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "user_id": 12345,
  "amount_cents": 4999,
  "currency": "USD",
  "event": "charge_failed",
  "reason": "card_declined",
  "duration_ms": 342,
  "payment_gateway": "stripe",
  "attempt": 1
}
```

With the structured version, you can query: "all card_declined events in the last hour, grouped by payment_gateway" — and get a table instantly. With the unstructured version, you're running regex over text.

**Correlation IDs** are the other critical practice. Every request that enters your system gets assigned a unique ID at the edge (API gateway, load balancer, or first service in the chain). That ID propagates through every subsequent call — logged at every service boundary, database query, and event emission. When something goes wrong, you can trace the full execution path of a single request across dozens of services by filtering on one ID. Without correlation IDs, debugging distributed systems is like solving a jigsaw puzzle with pieces from different boxes.

Implementing correlation IDs in a Python/FastAPI service:

```python
import uuid
from fastapi import FastAPI, Request
from contextvars import ContextVar

app = FastAPI()
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    # Use incoming trace-id if present (from upstream caller), else generate
    trace_id = (
        request.headers.get("X-Trace-Id") or
        request.headers.get("traceparent") or  # W3C TraceContext
        str(uuid.uuid4())
    )
    trace_id_var.set(trace_id)

    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response

# In any function, access the current trace ID for logging:
import logging
import structlog

log = structlog.get_logger()

def process_payment(user_id: int, amount: int):
    log.info("payment.started",
             user_id=user_id,
             amount_cents=amount,
             trace_id=trace_id_var.get())  # correlation ID flows through
    # ...
```

What to log:
- Request start and end (with duration)
- Every external call (DB queries, HTTP calls to dependencies, cache reads/writes)
- State transitions (order moved from PENDING to PROCESSING)
- Errors with full stack traces and relevant context
- Security events (auth attempts, privilege escalations)

What not to log:
- PII or sensitive data without explicit need and masking
- High-frequency, low-information events (individual packet receipts, tight loop iterations)
- Duplication of what metrics already capture well

**Log aggregation and querying:** Raw logs on individual instances are nearly useless at scale. You need a centralized log aggregation system. The standard stack is: Fluent Bit (log collector, runs as DaemonSet on Kubernetes) → Elasticsearch or OpenSearch (storage and indexing) → Kibana or Grafana (querying and visualization). Alternatives: Datadog Logs, Splunk, Google Cloud Logging, Loki (Grafana's purpose-built log aggregation, cheaper than Elasticsearch for many use cases).

**Log levels matter:** Don't log everything at ERROR. Reserve ERROR for things that require human attention. Use WARN for degraded states that are self-healing. Use INFO for significant business events. Use DEBUG for detailed diagnostic output (disabled by default in production). When everything is ERROR, nothing is.

**Pillar 2: Metrics**

Metrics are numeric measurements, typically aggregated over time. Unlike logs (one record per event), metrics are sampled or aggregated into time series. They're cheap to store and fast to query, which makes them ideal for alerting.

The three fundamental metric types:

**Counters** are monotonically increasing. They only go up — total requests received, total errors, total bytes sent. You never directly graph a counter; you derive its *rate* (requests per second, errors per minute). Counters reset to zero on service restart, so your monitoring tool needs to handle that gracefully.

**Gauges** capture a point-in-time value that can go up or down. Current memory usage, current queue depth, number of active connections, current goroutine count. Gauge values at a point in time are meaningful on their own.

**Histograms** record the distribution of values across configurable buckets. Request duration in the bucket 0-10ms: 500 requests. 10-50ms: 1200 requests. 50-100ms: 300 requests. 100ms+: 12 requests. From histograms you can calculate percentiles (p50, p95, p99) and spot the shape of your latency distribution — whether you have a bimodal distribution, heavy tail, or bounded spread.

**Practical instrumentation with Prometheus (Python):**

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ACTIVE_CONNECTIONS = Gauge(
    'db_connections_active',
    'Active database connections'
)

# Use in request handler
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response
```

And the Prometheus queries to build your RED dashboard:

```promql
# Rate: requests per second (5-minute window)
rate(http_requests_total[5m])

# Errors: fraction of requests that are 5xx
rate(http_requests_total{status_code=~"5.."}[5m])
  / rate(http_requests_total[5m])

# Duration: p50, p95, p99 latency
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**Two essential monitoring frameworks:**

The **RED method** (Brendan Gregg / Tom Wilkie) is designed for request-driven services:
- **Rate** — how many requests per second is the service handling?
- **Errors** — what fraction of those requests are failing?
- **Duration** — how long do requests take (distribution, not average)?

For every service you own, you should have a dashboard with these three signals. If you have these three, you can answer "is this service healthy?" in seconds.

The **USE method** is designed for resource utilization:
- **Utilization** — what fraction of the time is the resource busy?
- **Saturation** — how much extra work is queued waiting for the resource?
- **Errors** — are there errors from this resource?

Apply USE to: CPU, memory, disk, network interfaces, thread pools, connection pools. These are typically the bottlenecks in performance investigations.

A practical investigation flow: SLO alert fires (symptom) → check RED metrics to confirm the service is sick → switch to USE metrics for each resource to find the bottleneck → use logs and traces to find the specific request or code path that's causing it.

**Pillar 3: Traces**

Traces follow a single request through all the systems it touches. A trace is composed of **spans** — one span per logical unit of work. Each span has: a service name, an operation name, a start time, a duration, status (success/error), and arbitrary metadata key-value pairs.

The magic is in the parent-child relationships. When Service A calls Service B, Service B creates a child span of A's span. When you visualize this, you get a waterfall diagram: the entire request tree laid out on a time axis, showing you exactly where time was spent, which services called which, and where errors occurred.

**A trace visualized:**

```
checkout-service [280ms total]
├── auth-service.validate_token [12ms] ✓
├── inventory-service.check_availability [45ms] ✓
│   └── postgres.SELECT items [38ms] ✓
├── pricing-service.calculate_total [8ms] ✓
├── payment-service.charge [198ms] ✓  ← most of the time
│   ├── fraud-service.check_risk [22ms] ✓
│   └── stripe.create_charge [169ms] ✓  ← root bottleneck
└── notification-service.send_confirmation [17ms] ✓
```

Without this trace, you'd know the checkout was slow (280ms) but you'd have no idea it was Stripe's API accounting for 60% of the latency. The trace makes it immediately obvious.

Traces make two previously hard problems easy:
1. **Latency attribution** — "the request took 2 seconds, but where?" With traces, you can see that 1.8 seconds was spent in a single downstream database call.
2. **Service dependency mapping** — by aggregating traces, you can automatically discover your actual service topology (which often diverges from your architecture diagrams).

**Implementing tracing with OpenTelemetry:**

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configure tracer
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Auto-instrument: FastAPI, HTTPX, SQLAlchemy all get spans automatically
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument(engine=engine)

# Manual span for custom business logic
tracer = trace.get_tracer(__name__)

async def process_checkout(order_id: str, user_id: int):
    with tracer.start_as_current_span("checkout.process") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("user.id", user_id)

        # This nested span is automatically a child of the parent
        with tracer.start_as_current_span("checkout.validate_inventory"):
            inventory_ok = await check_inventory(order_id)
            span.set_attribute("inventory.available", inventory_ok)

        if not inventory_ok:
            span.set_status(trace.StatusCode.ERROR, "inventory_unavailable")
            raise InsufficientInventoryError(order_id)
```

**OpenTelemetry** (OTel) is now the vendor-neutral standard for instrumentation. You instrument your code once with the OTel SDK, and then route the telemetry to whatever backend you want: Jaeger, Zipkin, Honeycomb, Datadog, Grafana Tempo. This avoids vendor lock-in at the instrumentation layer — switching from Datadog to Honeycomb doesn't require re-instrumenting all your code.

The OTel SDK also handles trace context propagation automatically — injecting the trace ID into HTTP headers (W3C TraceContext standard), Kafka message headers, etc., so that traces flow across service boundaries without manual work.

**The three pillars together in practice:**

Here's how they work as a system during a real investigation:

1. **Alert fires** (metrics): SLO burn rate alert. Error rate at 8% for the past 15 minutes.
2. **Check the RED dashboard** (metrics): Rate is normal (no traffic spike), Errors are elevated, Duration has spiked to p99=4.2s (was 0.8s). The service is sick, not overwhelmed.
3. **Sample some failed traces** (traces): Filter traces by `error=true`. The waterfall shows that 95% of failed requests are failing in the `payment-service` span, specifically on the `stripe.create_charge` child span, with status `connection_timeout`.
4. **Drill into logs** (logs): Filter logs by `service=payment-service AND event=stripe_timeout`. The logs show: `stripe.api_timeout: connection timed out after 3000ms, attempt 1 of 3`. Stripe's API is responding slowly.
5. **Confirm with metrics** (metrics): Check the `external_api_duration_seconds` metric for Stripe specifically. p99 has gone from 800ms to 3200ms in the last 20 minutes.

Conclusion: Stripe is having an incident. Check Stripe's status page, activate the circuit breaker for Stripe to start failing fast, notify users that payment processing is degraded. This entire investigation took under 8 minutes because each pillar pointed to the next.

Without traces: you'd know requests are failing, but you'd spend 20+ minutes trying to figure out which service is responsible.

Without structured logs: you'd know the payment service is involved (from traces), but you'd be grepping text to find the timeout details.

Without metrics: you'd have no alert until users reported it, and no way to confirm recovery.

### 2.3 Alerting Philosophy

Alerting is where a lot of teams get observability wrong. The failure mode is almost always the same: alert fatigue. Too many alerts, most of them not actionable, pages firing at 3am for things that aren't real emergencies. On-call engineers start ignoring alerts. Real incidents get missed.

The fix is a clear alerting philosophy:

**Alert on symptoms, not causes.** An alert should represent user-visible impact. "Error rate is 5%" is a symptom alert. "Database replication lag is 30 seconds" is a cause alert. Cause alerts are sometimes useful as diagnostic aids, but they should never page someone — they should go into a ticket queue or be visible only in dashboards. The on-call engineer is paged when users are affected, not when internal machinery is misbehaving in ways that may or may not matter.

*Why?* Because there are hundreds of potential causes for any given symptom. If you alert on causes, you'll have hundreds of alerts that fire constantly for causes that happen to have no impact on users right now. You'll also page for the same underlying problem dozens of times as different causes trigger. One symptom alert covers all the causes.

**Every alert must be actionable.** If there is no action the on-call engineer can take when they receive an alert, it should not be an alert. It should be a metric in a dashboard. "Memory usage is 75%" — is there an action? If memory usage at 75% requires no immediate action, it shouldn't page. If it means "scale horizontally now," document that in the runbook and page.

**Multi-window, multi-burn-rate alerting on SLOs.** Align your alerting with your error budget. Rather than alerting on the absolute error rate, alert when your error budget is being consumed too fast:

- **Fast burn (page immediately):** You're consuming your monthly error budget at 14x the normal rate. At this rate, you'll exhaust the budget in 2 hours. This warrants waking someone up.
- **Slow burn (ticket + investigate):** You're consuming your monthly error budget at 5x the normal rate. At this rate, you'll exhaust the budget in about 6 days. This needs attention today, not at 3am.

This approach has a beautiful property: it's automatically calibrated to your SLO. A service with a 99.9% SLO and a service with a 99.99% SLO have the same alerting framework — they just have different burn rates because their error budgets are different sizes.

**Page for active emergencies only.** Everything else goes to a ticket queue that gets reviewed during business hours. Protect the on-call engineer's sleep. A paged engineer who's been woken up three nights in a row is not an effective engineer on day four. High on-call burden is both a people problem and a reliability problem.

### 2.4 Dashboard Layers

Dashboards serve different audiences with different questions. A well-structured dashboard hierarchy has four layers:

**Layer 1: Executive dashboard.** Answers "are we meeting our commitments?" Uptime percentage (rolling 30-day), SLA compliance status (green/yellow/red), error budget remaining as a percentage and time. Audience: leadership, product managers, customer-facing teams. Should be interpretable without technical knowledge.

**Layer 2: Service dashboard.** Answers "is this service healthy?" SLIs for each defined SLO (error rate, latency percentiles), saturation signals (connection pool usage, queue depth, memory and CPU), recent deployment markers, active alert status. Audience: on-call engineers, service owners. This is the first place you go when an alert fires.

**Layer 3: Debug dashboard.** Answers "what's wrong with this specific thing?" Per-instance metrics, span waterfalls from distributed traces, slow query logs, error detail counts broken down by error code or endpoint. Audience: engineers actively debugging an incident. You navigate here from the service dashboard when you've identified a suspicious component.

**Layer 4: Infrastructure dashboard.** Answers "how is the underlying platform?" Node health, network I/O, disk usage, cluster-level resource consumption. Audience: infrastructure/platform teams. Useful for capacity planning and infrastructure-level debugging.

The layers form an investigation funnel. An alert fires → you check Layer 2 to confirm the service is unhealthy and which SLI is burning → you dive to Layer 3 to identify the culprit → you may check Layer 4 if you suspect infrastructure is involved.

---

## 3. RESILIENCE PATTERNS

### 3.1 Why Distributed Systems Need Explicit Resilience

In a monolith, a function call either returns or throws. It doesn't time out indefinitely. It doesn't fail 1% of the time with a network error. It doesn't suddenly take 10 seconds because a mutex is contested.

In a distributed system, every network call is an opportunity for a cascade. Your service calls a database. The database is slow. Your service accumulates threads waiting for the database. Your thread pool fills up. New requests to your service start failing — not because your service has a bug, but because a database you depend on is slow. That failure propagates to your callers. Their thread pools fill up. The cascade ripples outward.

Resilience patterns are the engineering practices that contain these cascades. Each one is a specific mechanism addressing a specific failure mode. Together, they let you build a service that degrades gracefully under partial failures instead of failing catastrophically.

### 3.2 Circuit Breaker

The circuit breaker pattern (named by Michael Nygard in *Release It!*) is designed to prevent cascading failures and give struggling dependencies time to recover.

The circuit breaker wraps calls to an external dependency and tracks the failure rate. It has three states:

**Closed (normal operation):** Calls pass through to the dependency. The circuit breaker monitors failure rate. If failures stay below threshold, it stays closed. This is normal operation.

**Open (fail fast):** When failures exceed the threshold (e.g., 50% of calls in the last 60 seconds), the circuit breaker opens. Subsequent calls *do not go to the dependency at all* — they immediately fail with an error. This is the key insight: fast failures are better than slow failures. A thread that fails immediately frees up in microseconds; a thread waiting for a 30-second timeout ties up a resource for 30 seconds.

**Half-Open (probing):** After a configurable timeout (say, 30 seconds), the circuit breaker allows a small number of probe requests through to the dependency. If those succeed, the circuit resets to Closed. If they fail, it goes back to Open and resets the timeout.

**State machine diagram:**

```
                    failure rate > threshold
    ┌─────────────────────────────────────────┐
    │                                         ▼
┌───┴────┐    probe success              ┌─────────┐
│ CLOSED │◄──────────────────────────────┤  OPEN   │
└───┬────┘                               └────┬────┘
    │                                         │
    │ pass-through calls                      │ all calls fail fast
    │                                    after timeout
    │                                         │
    │                                    ┌────▼──────┐
    │              probe failure         │ HALF-OPEN │
    └────────────────────────────────────┤           │
                                        │ allow N   │
                                        │ probe reqs │
                                        └───────────┘
```

**Code example (Python, using the `circuitbreaker` library pattern):**

```python
import time
from enum import Enum
from threading import Lock
from dataclasses import dataclass, field
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5      # failures before opening
    recovery_timeout: float = 30.0  # seconds before entering HALF_OPEN
    probe_count: int = 3            # requests allowed in HALF_OPEN

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _probe_successes: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        with self._lock:
            state = self._get_state()

        if state == CircuitState.OPEN:
            raise Exception("Circuit is OPEN — failing fast")

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._on_success()
            return result
        except Exception as e:
            with self._lock:
                self._on_failure()
            raise

    def _get_state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._probe_successes = 0
        return self._state

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._probe_successes += 1
            if self._probe_successes >= self.probe_count:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

# Usage
payment_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

def process_payment(order_id: str, amount: float):
    try:
        return payment_circuit.call(payment_service.charge, order_id, amount)
    except Exception:
        # Return degraded response instead of propagating failure
        return {"status": "pending", "message": "Payment queued for retry"}
```

In production, prefer a battle-tested library: `resilience4j` (Java/Kotlin), `polly` (.NET), `pybreaker` (Python), or build on top of service mesh circuit breaking (Istio, Linkerd) for language-agnostic protection.

**The practical benefit:** When your payment service is struggling, the circuit breaker in your checkout service doesn't let checkout requests accumulate in a queue waiting for payment service responses. They fail fast. The checkout service stays healthy. Users get an error message rather than a timeout. The payment service isn't overwhelmed by a backlog of requests it can't serve. When the payment service recovers, the circuit resets and traffic flows normally.

**Configuration matters a lot.** Too-sensitive circuit breakers trip during normal traffic spikes and make transient errors into prolonged outages. Too-insensitive ones let cascades happen anyway. Tune the error rate threshold, the minimum number of requests before the circuit can trip (so a single failed request at startup doesn't open the circuit), and the probe timeout to fit your specific dependency's behavior.

### 3.3 Bulkhead Isolation

The term comes from ship construction: bulkheads are watertight compartments. If one compartment floods, the others stay dry. The ship sinks slower, or not at all.

In services, bulkheads mean: **separate resource pools per dependency.** If your service calls three downstream APIs, each gets its own thread pool (or connection pool, or semaphore). When Dependency A is slow and exhausts its thread pool, Dependency B and C are unaffected — they have their own pools.

Without bulkheads, a single slow dependency can exhaust your entire thread pool. Every thread in your application is stuck waiting for that one slow service. Requests that would have succeeded (and didn't even touch that dependency) start failing because there are no threads available to serve them.

The implementation varies by runtime:
- **JVM (Hystrix, Resilience4j):** Separate thread pools per downstream service. Calls run on the pool for that service, not the caller's thread.
- **Go:** Goroutine pools or semaphores per dependency (goroutines are cheap, but you still want bounded concurrency).
- **Node.js:** Connection pools per external service, with concurrency limits via semaphores (e.g., `p-limit`).

The tradeoff: bulkheads add complexity (more config, more monitoring) and don't come for free (thread context switching has overhead). For services with a small number of critical dependencies, the protection is usually worth it. For a service calling twenty microservices, you'd be selective about which ones get their own bulkhead.

### 3.4 Timeout Strategies

Every call to an external dependency needs a timeout. Without one, you're trusting that the dependency will always respond in reasonable time — which it won't.

**Three layers of timeouts:**

- **Connection timeout (1-5 seconds):** How long to wait when establishing a TCP connection. If you can't connect in this time, the host is probably unreachable or the port isn't listening. Should be short.
- **Read timeout (varies widely):** How long to wait for data from an established connection. Highly workload-dependent. A fast key-value lookup might have a 50ms read timeout. A report generation API might need 10 seconds.
- **Overall/wall-clock timeout:** A cap on the entire operation including retries. Ensures that even with multiple retries, the total time is bounded.

**Deadline propagation** is the practice of passing the remaining time budget downstream. If an incoming request has a 2-second overall budget and your service spends 200ms on processing before calling a dependency, you pass 1.8 seconds as the deadline for that downstream call. If the dependency can't respond in 1.8 seconds, there's no point waiting — the upstream caller will have already timed out.

In gRPC, deadline propagation is built into the protocol. In HTTP-based services, you implement it yourself, typically via a request header (e.g., `X-Request-Deadline: <absolute-timestamp>`) and checking it before initiating downstream calls.

The effect of deadline propagation: no more wasted work. A request that's already timed out from the user's perspective shouldn't be triggering expensive database queries and downstream API calls. Propagating deadlines cancels those work items as soon as the upstream deadline has passed.

### 3.5 Retry Policies

Retries are the right response to transient failures — a brief network hiccup, a momentary database overload, a flapping connection. Without retries, transient failures become permanent from the user's perspective.

But naive retries cause their own disasters. The classic failure mode: a service is struggling under load. Clients start timing out. Clients retry. The service is now receiving 2x the traffic (original requests + retries). It gets worse, not better. Clients get frustrated and retry again. 3x traffic. The service is now completely overwhelmed and unable to recover. This is a **retry storm**.

**Exponential backoff with jitter** is the standard solution:

```
sleep_duration = random(0, base_delay * 2^attempt)
```

After the first failure, wait 0-100ms. After the second, wait 0-200ms. After the third, 0-400ms. And so on, up to some maximum (e.g., 30 seconds). The randomness (jitter) ensures that if 1000 clients all hit the same error at the same moment, they don't all retry simultaneously — they spread out over a window, reducing thundering herd effects.

**Retry budgets:** Cap retries at roughly 10% of original requests. If your service receives 10,000 requests per second, you should be generating at most 1,000 retry requests per second. This prevents retry storms even if your base clients are aggressive retriers.

**Only retry the right things:**
- Only retry **idempotent** operations. An idempotent operation produces the same result whether executed once or ten times. GET requests are idempotent. Read-only operations are idempotent. Creating an order is typically *not* idempotent (retrying might create two orders) unless you're using idempotency keys.
- Only retry on **transient errors** (network timeouts, 503 Service Unavailable, 429 Too Many Requests). Never retry on 400 Bad Request, 404 Not Found, or 422 Unprocessable Entity — those aren't transient, and retrying won't help.

### 3.6 Rate Limiting

Rate limiting protects your service from overload — whether from misbehaving clients, traffic spikes, or intentional abuse. It's also the mechanism for enforcing usage quotas in multi-tenant systems.

**Token bucket:** The bucket holds up to N tokens. Tokens replenish at a fixed rate (e.g., 100 tokens per second). Each request consumes one token. If the bucket is empty, the request is rejected (or queued). The key property: the bucket allows **bursts** up to its size. A client that's been idle for 10 seconds (and accumulated 1000 tokens in a 100/s bucket) can burst 1000 requests immediately.

**Leaky bucket:** Requests enter the top of the bucket and are processed at a fixed rate from the bottom. If the bucket is full, new requests are dropped. Unlike token bucket, leaky bucket **smooths bursts** into a steady flow. Useful when you need to protect a backend that can't handle bursty traffic.

**Sliding window:** Counts requests in a rolling time window (e.g., the last 60 seconds). More precise than fixed-window approaches (which can allow up to 2x the rate at window boundaries) but more complex to implement and store. Used when you need accurate per-user rate limits at scale.

In practice, token bucket is the most common algorithm for request rate limiting. It maps naturally to how APIs want to behave: steady-state throughput with allowance for brief bursts.

### 3.7 Back-Pressure

Back-pressure is the mechanism by which a downstream component signals upstream components to slow down. It's the complement to load shedding — instead of dropping requests, you communicate capacity constraints so callers can adjust their rate.

**HTTP 429 (Too Many Requests)** with a `Retry-After` header is the most common back-pressure signal in REST APIs. It tells the client "slow down, wait this many seconds before trying again." Well-implemented clients honor this; badly implemented clients ignore it and retry immediately (a design failure).

**TCP flow control** is back-pressure built into the TCP protocol itself. When a receiver's buffer fills up, it advertises a zero window size, causing the sender to pause transmission. This is automatic and invisible — it's one reason TCP is more forgiving than UDP in overload scenarios.

**Reactive streams** (RxJava, Project Reactor, Akka Streams) implement back-pressure as a first-class protocol abstraction. Downstream consumers declare how many items they're ready to process (demand); upstream producers emit only that many items. This prevents fast producers from overwhelming slow consumers in streaming pipelines.

### 3.8 Load Shedding

When your service is at capacity and can't handle all incoming requests, what do you do? You have two options: slow down for everyone (latency creep), or reject some requests so others can be served well. Load shedding chooses the latter.

The core insight: **a degraded experience for some users is better than a terrible experience for all users.** When a checkout service is overloaded, you might reject requests to the product recommendation endpoint (low priority) while continuing to serve requests to the actual checkout flow (high priority).

Load shedding implementation:

1. **Classify requests by priority** at the edge (API gateway or service boundary). Priority can be based on endpoint criticality, user tier, request type.
2. **Monitor utilization** (CPU, active thread count, queue depth).
3. **When utilization exceeds threshold** (e.g., 90% thread pool capacity), start shedding low-priority requests with HTTP 503 + `Retry-After`.
4. **As utilization increases**, progressively shed higher-priority requests.

The alternative — not shedding load — results in latency for every request creeping up until the service becomes effectively unavailable for everyone. At that point you've shed load in the worst possible way (randomly, via timeout, without giving clients good information about when to retry).

---

## 4. INCIDENT MANAGEMENT

### 4.1 Incidents as Information

Every incident is expensive: on-call engineers lose sleep, users experience degradation, engineers drop what they're doing to respond, and trust erodes. But incidents are also the highest-quality signal you'll ever get about your system's real behavior under real conditions. Treated correctly, they're invaluable.

The goal of incident management is not just to resolve the current incident as fast as possible. It's to resolve it fast *and* capture enough information to prevent its recurrence. Both matter.

### 4.2 The Incident Lifecycle

Let's walk through a realistic incident to make these stages concrete. Imagine it's 2:17am and your checkout service's error rate just spiked to 23%.

**Detection:** The system tells you something is wrong, or a user tells you. Ideally the system tells you before users do — if users are filing support tickets before your alerts fire, your monitoring has a gap. Detection latency (time from problem start to alert fire) is a key metric for your monitoring system's health.

In our scenario, the fast-burn SLO alert fires at 2:17am. The on-call engineer, Sarah, is paged. She's the first to know. The alert includes: service name, current error rate, SLO budget consumed, a link to the runbook, and a link to the service dashboard. She has context before she's even opened her laptop.

*Detection best practice:* Measure your Mean Time to Detect (MTTD). If users are consistently reporting problems before your monitoring catches them, MTTD is too high. The goal is MTTD under 5 minutes for SEV1-level problems.

**Triage:** You've been paged. Is this real? How bad is it? What's the scope? Triage is the fast assessment that determines how to mobilize. The goal is a severity determination within minutes of detection.

Sarah looks at the service dashboard. 23% error rate, all errors are HTTP 500s, pattern started 12 minutes ago. She checks the traffic volume — requests are at normal levels, so it's not a load spike. She checks recent deployments — there was a deploy at 1:58am, 31 minutes ago. She declares SEV2 (major feature degraded, significant user impact) and opens an incident channel in Slack.

*Triage best practice:* Timebox triage to 5 minutes. If you can't determine severity in 5 minutes, declare the highest plausible severity, mobilize accordingly, and adjust down if warranted.

**Mobilization:** Based on severity, pull in the right people. For a SEV1, you might need the on-call, a service expert, and a communications lead. For a SEV3, maybe just the on-call is enough. Mobilization without a structure wastes time — you want clear roles defined before any specific incident.

For this SEV2, Sarah pings the deployment engineer who did the 1:58am push and the checkout service lead. Three roles are now filled: on-call (Sarah, incident commander), subject matter expert (deployment engineer), and escalation path (checkout lead). Sarah posts the first status update in the incident channel with a timeline template:

```
INCIDENT: SEV2 — Checkout 23% error rate
Start time: ~02:05 UTC (error start) / 02:17 UTC (detected)
IC: Sarah
Current status: Investigating
Current hypothesis: Deploy at 01:58 UTC is suspect
Next update: 02:45 UTC
Affected users: All checkout users (~18% of active users)
```

*Mobilization best practice:* Separate the incident commander (IC) role from the person doing technical investigation. The IC manages communication, tracks time, and ensures the team has what they need. The investigators investigate. When the same person tries to do both, communication gaps happen.

**Investigation:** What's causing this? The ideal investigation is methodical even under pressure: form a hypothesis, test it, confirm or reject, repeat. The temptation is to jump straight to a fix the moment you have a theory. Resist it — you need to confirm the cause before applying a fix, or you risk applying a fix that does nothing (or makes things worse) and losing time.

The deployment engineer pulls up the diff for the 1:58am deploy. It's a change to the payment processing integration — specifically, a new retry configuration. They look at the error logs: `NullPointerException in PaymentProcessor.charge()` — a field that the new code expects is null in existing objects. The error started 7 minutes after the deploy, which matches the timing of the first requests that would have touched the new code path for users with existing cart sessions (they had old session objects in cache that don't have the new field).

Hypothesis formed: the deploy introduced a null pointer exception for users with cached cart sessions from before the deploy.

They test it: spin up a staging environment, load a pre-deploy cart session, run through checkout. Confirmed crash.

*Investigation best practice:* Write every hypothesis, test, and result in the incident channel as you go, timestamped. During postmortem reconstruction, this log is invaluable. It also helps other responders avoid duplicating your work.

**Mitigation:** Stop the bleeding. This is often different from the root cause fix. If a bad deploy caused a memory leak, the mitigation might be "roll back the deploy." The root cause fix might be "fix the memory leak in the code." Mitigation is the fastest path to restoring service; root cause fix comes later.

Options discussed:
1. Roll back the deploy (estimated 4 minutes, low risk, solves immediately)
2. Push a hotfix (estimated 20 minutes, higher risk, new code)
3. Flush affected cache entries (estimated 8 minutes, medium risk)

They choose rollback — it's fastest and safest. At 2:41am, the rollback completes. Error rate drops from 23% to 0.1% within 90 seconds.

*Mitigation best practice:* Prefer rollback over hotfix when possible. Rollbacks are reversions to a known good state; hotfixes are new code under pressure. Hotfixes fail frequently. A successful rollback followed by a careful hotfix the next morning beats a rushed 3am hotfix that causes a second incident.

**Resolution:** The service is restored, users are no longer affected, all responders are stood down. Write the timeline while it's fresh.

At 2:45am, Sarah confirms: error rate stable at 0.1%, SLO burn rate back to normal. She updates the incident channel:

```
INCIDENT RESOLVED — 02:45 UTC
Duration: ~40 minutes
Mitigation: Rolled back deploy at 01:58 UTC
Root cause: (preliminary) Null pointer exception in PaymentProcessor.charge()
  for users with cached cart sessions from before deploy
Error budget consumed: ~0.12% of monthly budget
Postmortem: scheduled Friday 10am, owner: Sarah
Action items pending: Fix before re-deploy
```

She pages down the deployment engineer and checkout lead. Everyone goes back to sleep.

**Postmortem:** The learning phase. Detailed timeline reconstruction, root cause analysis, contributing factors, action items with owners and due dates.

The postmortem (held Friday, not at 3am) produces: a timeline, five contributing factors (insufficient staging coverage of cache compatibility, no canary deploy, insufficient pre-deploy null-safety checks, missing alert for NullPointerException spikes, 7-minute detection lag), and action items for each. The fix is shipped the following Monday with a canary deploy to 5% of traffic first.

*Postmortem best practice:* Schedule the postmortem within 48 hours while memory is fresh, but not in the immediate aftermath when people are tired and emotional. 24-48 hours after resolution is the sweet spot.

### 4.2a Incident Roles and Communication Templates

Clear role definitions prevent the two most common failure modes in incidents: too many cooks (everyone is talking, no one is deciding) and not enough visibility (people are working in silos, information isn't flowing).

**Core incident roles:**

| Role | Responsibility | Who fills it |
|------|---------------|-------------|
| Incident Commander (IC) | Overall coordination, communication cadence, declares severity | On-call or senior engineer |
| Technical Lead | Drives investigation and mitigation | Subject matter expert |
| Communications Lead | External and internal status updates | Product manager or senior IC |
| Scribe | Real-time timeline in incident channel | Anyone |

For SEV3, the on-call often fills all roles. For SEV1, each role needs its own person.

**Status update template (every 30 minutes during active incident):**

```
[HH:MM UTC] STATUS UPDATE
Current status: [Investigating / Mitigating / Monitoring / Resolved]
Error rate: X% (was Y% last update)
Affected users: estimated Z% of active users
Current hypothesis: [what you think is causing it]
Actions in progress: [what you're currently doing]
Next update: [time]
Help needed: [yes/no, what kind]
```

The regularity of updates matters as much as the content. During a major incident, stakeholders outside the technical responders (leadership, support team, customer success) need to know something is happening and there are people working on it. Regular updates — even if the update is "still investigating, no change" — reduce the pressure on the technical team from a stream of "what's the status?" pings.

### 4.3 Severity Levels

A clear severity system is important because it tells everyone — responders, leadership, communications — what to expect in terms of urgency and response scale.

| Level | Criteria | Response |
|---|---|---|
| SEV1 | Complete service outage, data loss, security breach, major revenue impact | All hands, leadership notified, 15-minute update cadence, communications to users |
| SEV2 | Major feature degraded, significant portion of users affected | On-call + domain experts, 30-minute updates, executive awareness |
| SEV3 | Minor degradation, small percentage of users affected, workaround available | On-call handles, investigate within 4 hours, next business day if off-hours |
| SEV4 | Cosmetic issue, no user impact, no SLO impact | Ticket queue, normal sprint prioritization |

The severity level should be set at detection time based on observable user impact, not based on your theory about what's wrong. A database problem that somehow isn't affecting users yet is SEV4 until it affects users. A flapping alert that IS affecting users is SEV2. User impact is the criterion.

Severity levels should have explicit criteria for escalation (if the SEV3 you investigated has gotten worse, upgrade it) and de-escalation (if you've mitigated the main impact of a SEV1, you might downgrade to SEV2 while finishing cleanup).

### 4.4 On-Call Best Practices

On-call is a cultural and operational investment, not just a staffing exercise. How you design your on-call directly affects whether good engineers want to stay at your company.

**1-week rotations with handoff docs.** Weekly is long enough that you don't spend most of your time ramping up, and short enough that no one is stuck on-call for extended periods. The handoff document captures: incidents that occurred during the week, issues that are still open, anything unusual the next person should know about.

**Target fewer than 2 pages per 12-hour shift.** This is the Google SRE guideline, and it's worth taking seriously. More than 2 pages per shift means your on-call engineer can't get real work done or real sleep done. They're in a constant state of partial attention that's bad for both reliability work and personal wellbeing. If you're consistently above this threshold, you have a monitoring problem or a reliability problem (or both).

**Runbooks for every alert.** Every actionable alert should have a runbook — a document that explains what the alert means, what the usual causes are, and what to do. A new engineer on their first on-call shift should be able to handle most alerts by following runbooks. Runbooks also force the question: if there's no documented action, should this be an alert at all?

**Shadow on-call for new team members.** The first week, a new engineer shadows an experienced on-call without being responsible for the response. The second week, they're on-call with an experienced engineer available to escalate to. This gradual ramp-up prevents the sink-or-swim experience that burns out new engineers and creates reliability risks.

**On-call load balancing.** Not everyone on a team has equal on-call burden. Senior engineers who have deep knowledge often get more escalations. Track the distribution and compensate — either through reduced on-call frequency, or through explicit investment in spreading knowledge (runbooks, knowledge transfer sessions, cross-training).

---

## 5. CHAOS ENGINEERING

### 5.1 From Testing to Hypothesis

Traditional testing verifies that your system does what you think it does under conditions you specify. Chaos engineering is different: it tests whether your system *behaves correctly under adversity* — conditions that are harder to anticipate in advance.

**The Netflix origin story:**

In 2008, Netflix suffered a major database corruption incident that took down their DVD shipping service for three days and affected millions of customers. It was a watershed moment. The engineering team made a decision: they would move entirely to AWS and build a cloud-native architecture that could tolerate infrastructure failures by design.

The problem was that designing for failure and actually tolerating failure are different things. You can architect for high availability on paper, add redundancy, write runbooks — and still discover on a random Tuesday night that a single Availability Zone failure takes down your entire service because of an assumption someone made two years ago in a config file no one remembers.

In 2010, Netflix engineer Cory Bennett and Ariel Tseitlin created Chaos Monkey: a tool that randomly terminated EC2 instances in their production environment, during business hours. The name was deliberately provocative — the monkey wanders through your data center randomly breaking things. The theory: if your engineers know that any instance might die at any moment during the workday, they'll build the system to handle it. You can't opt out. You adapt or you get paged.

The results were instructive. Chaos Monkey exposed dozens of single points of failure that no one had identified through architecture reviews. Services that were supposed to fail over automatically didn't. Services that were supposed to degrade gracefully crashed entirely. Assumptions baked into config files turned out to be wrong.

But here's the crucial piece: they ran it during business hours intentionally. When the monkey terminated an instance and something broke, the team was awake, alert, and in the office. They could respond, fix, learn. Contrast this with the alternative: the same failure happening at 2am, discovered by an exhausted on-call engineer, with no root cause context.

Netflix went further and built the Simian Army: Chaos Monkey (random instance termination), Chaos Gorilla (simulates loss of an entire Availability Zone), Latency Monkey (introduces artificial network latency), Conformity Monkey (checks for instances that don't follow best practices), Doctor Monkey (checks for unhealthy instances), Janitor Monkey (removes unused cloud resources). Each one targeted a different failure mode.

By 2012, Netflix had open-sourced Chaos Monkey, and the discipline had a name: chaos engineering.

The insight: **weaknesses in your system don't care whether you're testing or not.** They exist in production right now. The question is whether you discover them on your terms (controlled experiment, during business hours, with your team at full attention) or on the system's terms (random 3am production incident with your on-call engineer half-asleep).

This is exactly the learning you'll live through in L2-M48, where you'll break TicketPulse on purpose — killing the payment service mid-purchase, injecting 500ms of latency into the database connection, and severing the Kafka consumer. Some of those experiments will surface genuine bugs in the circuit breaker configuration. The "aha" moment is when you realize your staging system didn't catch them because staging never ran at production traffic volume.

### 5.2 The Five Principles of Chaos Engineering

The principles, articulated at Principlesofchaos.org:

**1. Define steady state.** Before you can test resilience, you need to define what "working correctly" looks like. This is your SLIs — request success rate, latency percentiles, specific business metrics. If you can't measure steady state, you can't tell whether your chaos experiment caused a problem.

**2. Hypothesize that steady state will continue.** Your experiment hypothesis is: "When I inject this failure, steady state will be maintained." You're expecting the system to absorb the failure. If you're expecting the system to break, that's not an experiment — that's debugging a known problem.

**3. Introduce real-world events.** The experiments that matter are the failures that could actually happen. Relevant chaos experiments:
   - Kill a random instance or pod (hardware failure simulation)
   - Inject latency into service-to-service calls (slow network or degraded dependency)
   - Fill a disk to capacity (storage failure)
   - Drop packets between specific services (partial network partition)
   - Kill a database replica (failover testing)
   - Exhaust a connection pool (resource exhaustion)
   - Simulate a dependency returning HTTP 500s or 503s

**4. Run experiments in production (or production-equivalent).** Staging environments diverge from production in ways that matter. Traffic patterns are different. Data distributions are different. Some failure modes only manifest under real production load. This is the most controversial principle. "Minimum blast radius" is the counterbalance.

**5. Minimize blast radius.** Start with experiments that have limited potential impact. Run in a single availability zone before all availability zones. Start with low traffic periods. Have automated stop conditions — if your error rate exceeds a threshold, automatically halt the experiment. Build confidence incrementally.

### 5.3 How to Start: Practical Chaos Engineering

The biggest barrier to starting chaos engineering is fear. "We can't inject failures into production — what if something breaks?" This is exactly backwards. If injecting a small, controlled failure breaks production in an unexpected way, you've just learned something invaluable *on your terms*, not at 3am.

But you should start small. Here's a practical progression:

**Stage 1: Verify your existing safety mechanisms (weeks 1-2)**

Before injecting failures, audit what safety you already have. Run these experiments in staging first:

```bash
# Experiment 1: Kill a single replica and watch failover
kubectl delete pod my-service-7d9f8b-xyz

# Watch: Does traffic reroute automatically?
# Watch: Do you get alerts?
# Watch: Does the service recover without manual intervention?
# Expected time to recovery: < 30 seconds

# Experiment 2: Simulate a slow dependency
# Using tc (traffic control) to add 2s latency to a single pod's egress
kubectl exec -it my-service-pod -- tc qdisc add dev eth0 root netem delay 2000ms

# Watch: Does the circuit breaker open?
# Watch: Does latency spike cascade to callers?
# Watch: Does load shedding kick in?
```

If any of these experiments reveals an unexpected failure mode, you've found a bug. Fix it before you run the experiment in production.

**Stage 2: Automate chaos in staging (weeks 3-6)**

Tools for this stage:
- **Chaos Monkey for Kubernetes (kube-monkey):** Randomly deletes pods on a schedule
- **Litmus Chaos:** Rich experiment library for Kubernetes (network faults, disk pressure, CPU hog, pod kill)
- **Gremlin:** Commercial SaaS platform for chaos experiments with good blast radius controls
- **AWS Fault Injection Simulator (FIS):** Native AWS chaos for EC2, ECS, EKS, RDS

A minimal Litmus experiment that kills a random pod every business day:

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: checkout-pod-kill
  namespace: production
spec:
  appinfo:
    appns: "production"
    applabel: "app=checkout-service"
    appkind: "deployment"
  chaosServiceAccount: litmus-admin
  experiments:
  - name: pod-delete
    spec:
      components:
        env:
        - name: TOTAL_CHAOS_DURATION
          value: "60"          # Run for 60 seconds
        - name: CHAOS_INTERVAL
          value: "10"          # Kill a pod every 10 seconds
        - name: FORCE
          value: "false"       # Graceful termination
      probe:
      - name: "check-availability"
        type: "httpProbe"
        httpProbe/inputs:
          url: "http://checkout-service/health"
          responseTimeout: 2000
          method:
            get:
              criteria: "==" 
              responseCode: "200"
        runProperties:
          probeTimeout: 5
          interval: 5
          attempt: 5
        mode: "Continuous"     # Run throughout chaos duration
```

The `probe` section is key: it continuously checks your service's health endpoint during the experiment. If availability drops, the experiment auto-halts and marks itself as failed — your automatic stop condition.

**Stage 3: Introduce to production (cautiously)**

When staging experiments consistently pass without unexpected failures, graduate to production:

1. **Start with low-traffic hours** (not 3am, but 2pm on a Tuesday rather than 9am on a Monday)
2. **Start with stateless services** — you can always restart them; state-bearing services have harder failure modes
3. **Have an escape hatch** — a single command that halts all chaos experiments and restores normal state
4. **Run with someone watching** — not automated-and-forget. A team member should be observing metrics in real time

**Automating your stop conditions:**

```python
# Simple chaos experiment runner with automatic halt
import time
import requests

class ChaosExperiment:
    def __init__(self, target_service_url: str, error_rate_threshold: float = 0.05):
        self.target_url = target_service_url
        self.threshold = error_rate_threshold
        self.running = False

    def run(self, inject_failure, duration_seconds: int):
        """Run chaos experiment with automatic stop on error rate threshold."""
        self.running = True
        inject_failure()  # Start the failure injection

        start_time = time.time()
        while time.time() - start_time < duration_seconds and self.running:
            error_rate = self._measure_error_rate()
            if error_rate > self.threshold:
                print(f"HALT: Error rate {error_rate:.1%} exceeded threshold {self.threshold:.1%}")
                self._halt_chaos()
                return False
            time.sleep(5)

        self._halt_chaos()
        return True

    def _measure_error_rate(self) -> float:
        # Query Prometheus for error rate
        query = 'rate(http_requests_errors_total[1m]) / rate(http_requests_total[1m])'
        response = requests.get(
            'http://prometheus:9090/api/v1/query',
            params={'query': query}
        )
        result = response.json()['data']['result']
        return float(result[0]['value'][1]) if result else 0.0

    def _halt_chaos(self):
        self.running = False
        # Signal chaos tool to stop (tool-specific)
        print("Chaos experiment halted.")
```

**Stage 4: Build a chaos calendar**

Once you have reliable experiments, run them on a schedule rather than ad-hoc. A monthly chaos calendar might look like:

| Week | Experiment | Target | Expected behavior |
|------|-----------|--------|-------------------|
| Week 1 | Pod kill (random) | All services | Failover in < 30s, no user impact |
| Week 2 | Network latency injection (500ms) | Payment service dependency | Circuit breaker opens, graceful degradation |
| Week 3 | Database failover | Primary RDS | Read traffic shifts to replica, < 60s degraded state |
| Week 4 | AZ failure simulation | Entire AZ | Cross-AZ traffic redistribution |

The calendar approach normalizes chaos as part of engineering routine rather than a special scary event.

### 5.4 Game Days

A game day is a scheduled chaos exercise — a planned event where you run specific experiments and treat the response like a real incident. The purposes:

**Build muscle memory for incident response.** Real incidents happen infrequently (if your reliability practices are working). This is good for users but bad for on-call engineers who need to keep their incident response skills sharp. Game days are deliberate practice.

**Reveal monitoring gaps.** Almost every game day reveals at least one alert that didn't fire when it should have, or one metric that wasn't being tracked. Finding these gaps in a controlled exercise is dramatically better than finding them during a real incident.

**Test runbook accuracy.** Runbooks written during calm periods often don't survive contact with reality. Game days test whether the runbook actually guides the responder to resolution, or whether it's out of date or underspecified.

**Build organizational confidence.** Leadership is often nervous about chaos engineering because it sounds like deliberately breaking production. A series of successful game days — where experiments ran, systems absorbed the failures, and runbooks worked — builds the organizational trust needed to do more aggressive experiments.

A good game day format: define the experiment and hypothesis in advance, run it with the on-call team as if it's a real incident (without telling them the specifics of what will be injected), record the timeline, run a postmortem afterward even if nothing bad happened.

---

## 6. PERFORMANCE ENGINEERING

### 6.1 Why Performance is a Reliability Concern

Performance is not separate from reliability. Slowness *is* an outage — just a gradual one. A service that's slow enough becomes effectively unavailable. Your SLOs capture this: the latency component of your SLI defines what "too slow" means in measurable terms.

But performance engineering is also tricky because performance problems are often non-linear and non-obvious. Your service might handle 1000 RPS perfectly and fall apart at 1200 RPS, not because of any single component failing but because of queueing theory — the interaction between arrival rates and service times when utilization exceeds a threshold.

Understanding a small amount of theory goes a long way here.

### 6.2 Latency Percentiles

If you take one piece of advice from this section, let it be this: **never use averages to describe latency.** Averages hide the distribution. A service that handles 99% of requests in 10ms and 1% in 10 seconds has an "average" latency of about 110ms. That 110ms average tells you nothing useful. The p99 of 10 seconds tells you everything important.

The relevant percentiles:

**p50 (median):** The experience of the typical user — the user who is right in the middle of the distribution. Half of requests are faster, half are slower.

**p95:** The experience of the "unlucky" user — 1 in 20. This is where you start seeing users who are having a noticeably worse experience than average. Watch this closely; it often reveals systemic issues masked by the median.

**p99:** Tail latency — 1 in 100 requests. In a system handling 10,000 requests per second, that's 100 users per second having this experience. At large scale, tail latency is not a tail — it's a significant number of real users. p99 is typically 3-10x the median.

**p99.9 (sometimes p999):** For very high-traffic systems or SLO-critical paths, you may track the 1-in-1000 experience. At Netflix or Google scale, 1 in 1000 is still millions of users.

**Tail latency amplification** is a critical concept for distributed systems. If a single service call has p99 latency of 10ms, a fan-out to 100 services (each independently with p99=10ms) results in the maximum latency being the maximum across all 100 — and the probability that *at least one* of those 100 exceeds the p99 threshold is:

```
1 - (0.99)^100 = 63.4%
```

So what looks like a p99 problem in one service becomes a p63 problem for the user of a system that fans out broadly. This is why tail latency matters disproportionately in microservices architectures and why hedged requests (sending the same request to two replicas and taking whichever responds first) are sometimes used for critical read paths.

### 6.3 The Laws That Govern Performance

**Amdahl's Law** quantifies the limits of parallelism. If a fraction `p` of your task can be parallelized and the remaining `(1-p)` fraction is inherently serial, the maximum speedup from N processors is:

```
Speedup = 1 / ((1-p) + p/N)
```

As N approaches infinity, the maximum speedup approaches `1/(1-p)`. If 5% of your processing is serial, the maximum possible speedup — regardless of how many cores you add — is 20x. This means optimization effort is best spent on the serial portion.

*Practical implication:* Before investing in horizontal scaling, profile your application. If you have a single-threaded bottleneck (say, a global lock on a connection pool), adding more instances won't help — you need to fix the serial bottleneck first.

**Little's Law** is the most useful formula in capacity planning:

```
L = λ * W
```

Where L is the average number of items in the system, λ is the average arrival rate, and W is the average time each item spends in the system. This applies to any stable system — your web server, a database connection pool, a message queue, a bank teller line.

*Example:* If your API endpoint receives 500 requests per second (λ) and each request takes 40ms on average (W), the average number of in-flight requests (L) is 500 * 0.04 = 20. If you have a thread pool of 20 threads, you're right at capacity on average — any increase in arrival rate or processing time will cause queuing.

*Why this matters:* Little's Law lets you set thread pool sizes based on traffic forecasts. It also lets you sanity-check observations: if you're seeing 50 in-flight requests but your arrival rate is 500/s, something has gotten very slow.

**Queueing Theory** describes how wait time grows with utilization. For a simple M/M/1 queue (Poisson arrivals, exponential service times, single server):

```
Wait time = service_time * (utilization / (1 - utilization))
```

At 50% utilization: wait time ≈ 1x service time.
At 80% utilization: wait time = 4x service time.
At 90% utilization: wait time = 9x service time.
At 95% utilization: wait time = 19x service time.

The shape of this curve is the key insight: **as utilization approaches 100%, wait time approaches infinity.** Even at 80%, you're at 4x overhead. This is why the recommendation is to keep steady-state utilization below 70-80% — you need headroom for variance, traffic spikes, and slow operations.

*Real-world implication:* If your service is running at 85% CPU and you're wondering why latency is high, this is your answer. You don't need to fix the algorithm or the database query — you need more capacity. The math says wait times are guaranteed to be high at that utilization level.

### 6.4 Load Testing Types

Each load test type answers a different question:

**Smoke test:** Run the absolute minimum load — a single user, or a handful of requests. Purpose: verify the system works at all. Run before every load test as a sanity check.

**Load test:** Target traffic at your expected production level or near it. Purpose: validate that your service meets SLOs under expected conditions. This is the baseline. If it fails here, you have a definite problem before you even consider scale.

**Stress test:** Ramp traffic beyond peak production load. Purpose: find the breaking point. At what traffic level does latency degrade? At what level do errors start? What's the failure mode — graceful degradation or catastrophic failure? Answers where you need capacity headroom and what failure looks like at the limit.

**Soak test (endurance test):** Run at production-level traffic for an extended period — hours or days. Purpose: find resource leaks. Memory leaks, file handle leaks, connection pool exhaustion over time. These problems don't show up in short tests. A service that handles load fine for an hour but degrades over 12 hours has a soak problem.

**Spike test:** Sudden, dramatic increase in traffic (e.g., 10x normal in 30 seconds), then rapid reduction. Purpose: test auto-scaling and traffic surge behavior. Does your auto-scaling kick in fast enough? Do connection pools and caches handle the sudden surge? Does the system recover cleanly after the spike, or does it stay in a degraded state?

Load testing should be part of your regular engineering workflow — run before major releases, regularly in staging, and occasionally in production (with circuit breakers and kill switches in place). The alternative is discovering your system's breaking point during a real traffic spike, which is universally a worse experience.

---

## Summary: Building a Culture of Reliability

The concepts in this chapter — SLOs, error budgets, observability, resilience patterns, incident management, chaos engineering, performance engineering — are individually powerful. Together, they form a coherent system.

Error budgets give you the language to talk about velocity vs. reliability trade-offs without it becoming political. Observability gives you the data to know when your error budget is burning, why, and where. Resilience patterns limit how bad any single failure can get. Incident management turns failures into learning. Chaos engineering builds the confidence to make changes in a complex system. Performance engineering keeps the system fast enough that slowness doesn't become the next reliability problem.

The goal isn't a perfectly reliable system — that doesn't exist, and pursuing it would require you to stop changing the system entirely. The goal is a system that fails predictably, recovers quickly, gives you clear signal about what's wrong, and gets better over time.

That's what it means to engineer for reliability.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M26: SLOs and Error Budgets](../course/modules/loop-1/L1-M26-slos-and-error-budgets.md)** — Define TicketPulse's first SLOs, calculate error budgets, and wire them to the deployment policy
- **[L2-M47: Alerting and On-Call](../course/modules/loop-2/L2-M47-alerting-and-on-call.md)** — Build an alerting stack from scratch and design a sustainable on-call rotation for TicketPulse
- **[L2-M48: Chaos Engineering](../course/modules/loop-2/L2-M48-chaos-engineering.md)** — Run controlled failure experiments on TicketPulse using Chaos Monkey principles and validate your resilience patterns
- **[L3-M73: Incident Response Simulation](../course/modules/loop-3/L3-M73-incident-response-simulation.md)** — Work through a realistic production incident end-to-end: detection, response, mitigation, and postmortem

### Quick Exercises

1. **Define one SLO for your most critical user-facing endpoint** — pick the endpoint users care about most, choose a latency or availability target, write it down precisely (e.g., "99.5% of requests complete under 300ms, measured over a 30-day window").
2. **Calculate your current error budget** — take your target availability SLO and compute how many minutes of downtime you have left this month. Is it already burned? Is the team aware?
3. **Identify one alert that should exist but doesn't** — look at the last production incident your team had. Was there a signal in the data before users reported it? Define the alert that would have caught it.

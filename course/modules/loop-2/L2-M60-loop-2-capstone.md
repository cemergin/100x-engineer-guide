# L2-M60: Loop 2 Capstone

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 90 min | 🟢 Core | Prerequisites: All previous modules (L2-M31 through L2-M59)
>
> **Source:** Chapters 5, 21, 18, 27 of the 100x Engineer Guide

---

## The Goal

Thirty modules. You started with a monolith and ended with a production-grade microservices platform: multiple services communicating over gRPC and Kafka, deployed on Kubernetes, monitored with Prometheus and Grafana, traced with OpenTelemetry and Jaeger, resilient with circuit breakers and rate limiters, secured with OAuth2 and TLS, managed with Terraform and feature flags.

That is not a tutorial project. That is a real architecture. Companies run systems like this to serve millions of users.

This capstone has four parts:

1. **Architecture Review** -- draw the full system, see how far it has come
2. **The Stress Test** -- find where TicketPulse v2 breaks under load
3. **The Incident Drill** -- simulate a real incident and practice the response workflow
4. **Self-Assessment** -- evaluate every skill from Loop 2 and plan for Loop 3

This is not a test. This is an engineering exercise: analyze the system you built, push it to its limits, respond to failure, and reflect on what you have learned.

---

## Part 1: Architecture Review (25 minutes)

### 1.1 Draw the Architecture

Open a diagramming tool (draw.io, Excalidraw, paper) and draw TicketPulse v2's complete architecture. Include everything:

```
                                    ┌─────────────────────────────────────────────────────────────┐
                                    │                        Kubernetes Cluster                    │
                                    │                                                             │
   Users ──── HTTPS ────>  ┌───────┴───────┐                                                     │
                           │  API Gateway   │─── gRPC ──> ┌──────────────┐     ┌──────────────┐  │
                           │  (rate limit,  │              │ Event Service│     │ User Service  │  │
                           │   auth, TLS)   │              │              │     │              │  │
                           └───────┬────────┘              │  PostgreSQL  │     │  PostgreSQL  │  │
                                   │                       └──────┬───────┘     └──────────────┘  │
                                   │                              │                               │
                                   │── gRPC ──> ┌────────────────┴─┐                              │
                                   │            │ Purchase Service  │─── Kafka ──> purchase-events │
                                   │            │                   │                    │         │
                                   │            │   PostgreSQL      │                    ▼         │
                                   │            └────────┬──────────┘         ┌──────────────────┐│
                                   │                     │                    │ Purchase Processor││
                                   │                     │── HTTP ──>         │ (Kafka consumer)  ││
                                   │            ┌────────┴──────────┐         └──────────────────┘│
                                   │            │ Payment Service   │                              │
                                   │            │ (circuit breaker) │                              │
                                   │            └───────────────────┘                              │
                                   │                                                              │
                                   │── gRPC ──> ┌───────────────────┐                              │
                                   │            │  Search Service   │                              │
                                   │            │  (Elasticsearch)  │                              │
                                   │            └───────────────────┘                              │
                                   │                                                              │
                                   │── gRPC ──> ┌───────────────────┐                              │
                                   │            │ Recommendation Svc│                              │
                                   │            │     (Neo4j)       │                              │
                                   │            └───────────────────┘                              │
                                   │                                                              │
                ┌──────────────────┴──────────────────────────────────────┐                        │
                │                 Observability Stack                      │                        │
                │  Prometheus ──> Grafana    Jaeger (traces)              │                        │
                │  AlertManager             OpenTelemetry Collector        │                        │
                └─────────────────────────────────────────────────────────┘                        │
                                                                                                  │
                ┌──────────────────────────────────────────────────────────────────────────────────┘
                │  Infrastructure: Terraform, Kafka cluster, Feature flags (LaunchDarkly/Flagsmith)
                └──────────────────────────────────────────────────────────────────────────────────
```

Your diagram should include:

- **All services**: API gateway, event service, purchase service, payment service, search service, recommendation service, user service
- **All data stores**: PostgreSQL (per service), Elasticsearch, Neo4j, Redis (caching)
- **Kafka topics**: purchase-events, notification-events, analytics-events
- **Monitoring**: Prometheus scrape targets, Grafana dashboards, Jaeger traces, AlertManager alerts
- **Infrastructure**: Kubernetes pods/deployments, Terraform-managed resources, feature flag system
- **External dependencies**: Payment provider (Stripe mock), email service

### 1.2 Trace the Purchase Flow

On your diagram, trace the complete data flow for a ticket purchase:

**Synchronous path (user waits for response):**
```
1. User → API Gateway: POST /api/purchases
2. API Gateway: validate JWT, check rate limit
3. API Gateway → Event Service (gRPC): check ticket availability
4. API Gateway → Purchase Service (gRPC): create purchase
5. Purchase Service → Payment Service (HTTP): charge card
6. Payment Service: circuit breaker wraps Stripe API call
7. Purchase Service → PostgreSQL: INSERT purchase record
8. Purchase Service → Kafka: produce purchase-completed event
9. Purchase Service → API Gateway: return purchase confirmation
10. API Gateway → User: 201 Created
```

**Asynchronous path (happens after response):**
```
11. Kafka → Purchase Processor: consume purchase-completed
12. Purchase Processor → Notification Service: send confirmation email
13. Purchase Processor → Analytics: update purchase metrics
14. Purchase Processor → Search Service: update event availability in Elasticsearch
15. Kafka → Recommendation Service: update purchase graph in Neo4j
```

**Observability path (happens on every request):**
```
- OpenTelemetry: trace spans created at each service boundary
- Prometheus: request count, latency histogram, error count incremented
- Structured logs: JSON log line at each service with trace_id correlation
```

### 1.3 Compare with Loop 1

Pull out your Loop 1 capstone architecture diagram. Set it next to the Loop 2 diagram.

| Dimension | Loop 1 (TicketPulse v1) | Loop 2 (TicketPulse v2) |
|---|---|---|
| **Services** | 1 monolith | 6+ microservices |
| **Communication** | Internal function calls | gRPC + Kafka |
| **Database** | 1 shared PostgreSQL | Database per service |
| **Caching** | Redis (single instance) | Redis + Elasticsearch + CDN-ready |
| **Messaging** | RabbitMQ (simple queue) | Kafka (distributed log, partitions) |
| **Deployment** | Docker Compose | Kubernetes + Terraform |
| **Monitoring** | Structured logs + basic SLIs | Prometheus + Grafana + Jaeger + OpenTelemetry |
| **Resilience** | None | Circuit breakers, rate limiting, retries, DLQs |
| **Security** | JWT + OWASP hardening | OAuth2/OIDC + mTLS + TLS everywhere |
| **Data patterns** | CRUD | CQRS + Event Sourcing + Saga |

What improved? Write down three things that are genuinely better in v2.

What got more complex? Write down three things that are harder to operate in v2.

> **The key question:** Is the added complexity justified? For TicketPulse's scale and team size, which v2 features are worth the operational cost, and which are premature?

---

## Part 2: The Stress Test (25 minutes)

### 2.1 Set Up the Load Test

Install k6 if you have not already:

```bash
brew install k6
```

Create the load test script:

```javascript
// ticketpulse-stress-test.js
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// Custom metrics
const purchaseErrors = new Counter('purchase_errors');
const purchaseDuration = new Trend('purchase_duration', true);

export const options = {
  stages: [
    { duration: '30s', target: 10 },     // Warm up
    { duration: '30s', target: 100 },    // Ramp to 100
    { duration: '30s', target: 500 },    // Ramp to 500
    { duration: '60s', target: 1000 },   // Sustained 1000 -- the "ticket rush"
    { duration: '30s', target: 0 },      // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<2000'],  // SLOs
    http_req_failed: ['rate<0.01'],                     // 99% success
    purchase_errors: ['count<50'],                      // Less than 50 purchase failures
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const EVENT_ID = __ENV.EVENT_ID || '1';

export default function () {
  group('Browse Events', () => {
    // 80% of traffic: browsing (read-heavy)
    const listRes = http.get(`${BASE_URL}/api/events`);
    check(listRes, {
      'event list: status 200': (r) => r.status === 200,
      'event list: has events': (r) => JSON.parse(r.body).length > 0,
    });

    const detailRes = http.get(`${BASE_URL}/api/events/${EVENT_ID}`);
    check(detailRes, {
      'event detail: status 200': (r) => r.status === 200,
    });
  });

  sleep(Math.random() * 2);

  // 20% of traffic: purchasing (write-heavy)
  if (Math.random() < 0.2) {
    group('Purchase Ticket', () => {
      const start = Date.now();

      const purchaseRes = http.post(
        `${BASE_URL}/api/purchases`,
        JSON.stringify({
          eventId: EVENT_ID,
          quantity: 1,
          paymentMethodId: 'pm_test_mock',
        }),
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getTestToken()}`,
          },
        }
      );

      purchaseDuration.add(Date.now() - start);

      const success = check(purchaseRes, {
        'purchase: status 201 or 409': (r) => r.status === 201 || r.status === 409,
        'purchase: response time < 2s': (r) => r.timings.duration < 2000,
      });

      if (!success) {
        purchaseErrors.add(1);
        console.log(`Purchase failed: ${purchaseRes.status} - ${purchaseRes.body}`);
      }
    });
  }

  sleep(Math.random());
}

function getTestToken() {
  // Use a pre-generated test token or implement token caching
  return __ENV.TEST_TOKEN || 'test-token-for-load-testing';
}
```

### 2.2 Run the Stress Test

```bash
# Generate a test token first (adjust for your auth setup)
export TEST_TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"loadtest@ticketpulse.dev","password":"LoadTest123!"}' \
  | jq -r '.token')

# Run the stress test
k6 run \
  -e BASE_URL=http://localhost:3000 \
  -e EVENT_ID=1 \
  -e TEST_TOKEN=$TEST_TOKEN \
  ticketpulse-stress-test.js
```

### 2.3 Watch Everything While It Runs

This is the critical part. While the load test runs, you should have these open:

**Terminal 1: k6 output**
Watch the real-time metrics: request rate, error rate, latency percentiles.

**Terminal 2: Kubernetes resource usage**
```bash
watch -n 2 kubectl top pods -n ticketpulse
```

**Browser Tab 1: Grafana**
Open these dashboards:
- Request rate and error rate per service
- p50/p95/p99 latency per service
- Database connection pool utilization
- CPU and memory per pod

**Browser Tab 2: Jaeger**
Search for traces with duration > 2s. As the load increases, watch trace durations grow.

**Browser Tab 3: Kafka UI**
Watch consumer group lag. As throughput increases, lag should stay near zero. If it starts growing, the consumer cannot keep up.

### 2.4 Record Your Results

| Concurrent Users | Req/sec | p95 Latency | p99 Latency | Error Rate | First Problem |
|---|---|---|---|---|---|
| 10 | | | | | |
| 100 | | | | | |
| 500 | | | | | |
| 1000 | | | | | |

### 2.5 Where Does It Break?

Document the breaking sequence. Common findings for a TicketPulse-like system:

```
1. ~200 concurrent users: Latency starts increasing (DB connections filling up)
2. ~400 concurrent users: p99 latency exceeds 1s (connection pool queuing)
3. ~600 concurrent users: Payment service circuit breaker opens
   (payment provider rate-limited or purchase service timeouts cascade)
4. ~800 concurrent users: Kafka consumer lag grows
   (consumers cannot keep up with purchase event volume)
5. ~1000 concurrent users: Errors spike
   (timeouts, connection refused, OOMKills on resource-constrained pods)
```

Your numbers will differ. The important thing is identifying the sequence and understanding why each failure happens.

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🐛 Debug: Find the First Bottleneck

<details>
<summary>💡 Hint 1</summary>
Run `k6 run ticketpulse-stress-test.js` while watching `kubectl top pods -n ticketpulse` in a second terminal. The first pod to hit its CPU or memory limit is your primary bottleneck. Common first failure: the event-service database connection pool fills up around 200 concurrent users because each purchase checks ticket availability, and the connection pool defaults to 20 connections.
</details>

<details>
<summary>💡 Hint 2</summary>
In Grafana, correlate three panels simultaneously: (1) `rate(http_requests_total{status=~"5.."}[1m])` for error rate, (2) `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[1m]))` for p99 latency, (3) `pg_stat_activity_count{datname="events"}` for database connections. The metric that degrades FIRST is the root bottleneck -- everything else is a cascade.
</details>

<details>
<summary>💡 Hint 3</summary>
To double capacity from the current ceiling, identify the cheapest fix: if the bottleneck is database connections, increase `max_connections` in Postgres and the pool size in the application (cheapest). If it is CPU on a service pod, increase the resource limit or add replicas via HPA (medium cost). If it is a slow synchronous call to the payment provider, add a circuit breaker with a shorter timeout and a retry queue (highest effort but biggest payoff).
</details>


Using the observability skills from L2-M58, identify:

1. **What component fails first?** (Database connections? CPU? Memory? External dependency?)
2. **At what load level?** (This is your current capacity ceiling.)
3. **What would you change to increase capacity by 2x?** (The cheapest fix for the tightest bottleneck.)


<details>
<summary>💡 Hint 1</summary>
Open Jaeger and search for traces with `minDuration=1s` during the load test. The waterfall view shows which service span dominates the critical path. If `event-service: GET /availability` takes 800ms out of a 1200ms total trace, that is your 67% contributor. Focus optimization there first -- improving a 50ms span by 50% saves 25ms, but improving an 800ms span by 50% saves 400ms.
</details>

<details>
<summary>💡 Hint 2</summary>
Check Kafka consumer lag during the stress test: `kafka-consumer-groups.sh --describe --group purchase-processor`. If lag grows linearly while traffic is constant, the consumer is processing slower than the production rate. Solutions in order of effort: (1) increase consumer `max.poll.records` to process batches, (2) add consumer replicas with more Kafka partitions, (3) switch to an async consumer with a connection pool instead of single-threaded processing.
</details>

<details>
<summary>💡 Hint 3</summary>
Fill in the results table from section 2.4 with your actual numbers. The "First Problem" column is the most valuable -- it tells you the order of cascade. Typical pattern: DB connection pool exhaustion (200 users) -> purchase service timeouts (400 users) -> circuit breaker opens on payment service (600 users) -> Kafka consumer lag grows (800 users) -> pod OOMKills (1000 users). Your optimization plan should address these in order.
</details>

---

## Part 3: The Incident Drill (25 minutes)

### 3.1 Simulate an Incident

While the load test is running at moderate load (~500 concurrent users), simulate a production incident:

```bash
# Kill the payment service
kubectl -n ticketpulse scale deployment/payment-service --replicas=0
```

The payment service is now gone. Purchases that require payment will fail. This is your incident.

### 3.2 Practice the Incident Response Workflow

Work through each step of the incident response, as if this were real.

**Step 1: Detect (< 2 minutes)**

Which alert fires first? Check:
- Grafana: error rate dashboard should spike
- AlertManager: a purchase error rate alert should fire
- Jaeger: traces for purchases should show errors at the payment-service span

Write it down:
```
[TIME] - DETECTED: [Which alert / what you observed]
```

**Step 2: Triage (< 5 minutes)**

Assess the impact:
- Are ALL purchases failing, or only some?
- Are other features (browsing events, searching) still working?
- What is the error rate?

```
[TIME] - TRIAGE: [Impact assessment]
         Purchases: failing / degraded / intermittent
         Browsing: working / degraded / failing
         Error rate: ___%
```

**Step 3: Mitigate (< 10 minutes)**

Does the circuit breaker help? Check:
- Are purchase requests failing fast (circuit open) or timing out (circuit closed)?
- Is Kafka buffering purchase attempts for later processing?
- Is the API gateway returning a useful error to users?

```bash
# Check circuit breaker state (look in purchase-service logs)
kubectl -n ticketpulse logs deployment/purchase-service --since=5m \
  | grep -i "circuit"

# Check Kafka for buffered messages
kubectl -n ticketpulse exec -it kafka-0 -- \
  kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic purchase-events --from-beginning --max-messages 5 --timeout-ms 5000
```

**Step 4: Communicate**

Write a status page update. This is what users would see:

```markdown
**[INVESTIGATING] Ticket Purchases Temporarily Unavailable**

We are aware that some users are experiencing errors when purchasing
tickets. Event browsing and search are not affected.

Our engineering team is investigating the issue. We will provide
an update within 15 minutes.

Posted at: [TIME]
```

**Step 5: Resolve**

Bring the payment service back:

```bash
kubectl -n ticketpulse scale deployment/payment-service --replicas=2
```

Watch the recovery:
- How quickly does the error rate drop?
- Are queued purchases (if any) processed?
- Does the circuit breaker close and allow traffic through?

```
[TIME] - RESOLVED: Payment service restored.
         Error rate returning to normal.
         Queued purchases processing.
```

Update the status page:

```markdown
**[RESOLVED] Ticket Purchases Restored**

The issue with ticket purchases has been resolved. All services
are operating normally. Purchases that were queued during the
incident are being processed.

If you experienced an error during this window, please try again.

Duration: [X] minutes
Posted at: [TIME]
```

**Step 6: Postmortem Preparation**

Write three action items that would prevent or reduce the impact of this incident:

```
Action Item 1: _______________________________________________
  (e.g., Add a retry queue for failed payment attempts)

Action Item 2: _______________________________________________
  (e.g., Configure circuit breaker to return cached/pending status
   instead of error)

Action Item 3: _______________________________________________
  (e.g., Add a graceful degradation mode: allow users to "reserve"
   tickets and complete payment later)
```

---

## Part 4: Self-Assessment (15 minutes)

### 4.1 The Full Map

Here is every concept from Loop 2. Go through each one and mark it:

- **Got it** -- you could explain this to a junior engineer and debug issues related to it
- **Need more practice** -- you understand the concept but want more hands-on time
- **Still fuzzy** -- you need to revisit this before moving on

**Section 2A: Distributed Systems Fundamentals**

| Module | Topic | Status |
|---|---|---|
| M31 | Microservices decomposition: bounded contexts, service boundaries | |
| M32 | gRPC & Protocol Buffers: service-to-service communication | |
| M33 | Kafka fundamentals: topics, partitions, consumer groups | |
| M34 | Saga pattern: distributed transactions across services | |
| M35 | CQRS: separating read and write models | |
| M36 | Event sourcing: immutable event log as source of truth | |

**Section 2B: Data at Scale**

| Module | Topic | Status |
|---|---|---|
| M37 | PostgreSQL internals: MVCC, WAL, vacuum, transaction IDs | |
| M38 | Database migrations: zero-downtime schema changes | |
| M39 | Elasticsearch: full-text search, indexing, analyzers | |
| M40 | Neo4j: graph databases, Cypher queries, recommendations | |
| M41 | Redis advanced: data structures, pub/sub, Lua scripting | |
| M42 | Data consistency patterns: eventual consistency, CRDTs | |

**Section 2C: Infrastructure & Deployment**

| Module | Topic | Status |
|---|---|---|
| M43 | Kubernetes fundamentals: pods, deployments, services | |
| M44 | Kubernetes advanced: HPA, PDB, resource limits, health checks | |
| M45 | Terraform: infrastructure as code, state management, modules | |
| M46 | CI/CD advanced: multi-service pipelines, canary deployments | |
| M47 | Feature flags: progressive rollouts, kill switches, experimentation | |

**Section 2D: Observability & Resilience**

| Module | Topic | Status |
|---|---|---|
| M48 | Prometheus: metrics collection, PromQL, alerting rules | |
| M49 | Grafana: dashboards, RED metrics, SLO tracking | |
| M50 | OpenTelemetry & Jaeger: distributed tracing across services | |
| M51 | Circuit breakers: failure isolation, fallback strategies | |
| M52 | Rate limiting: token bucket, sliding window, distributed rate limits | |
| M53 | Chaos engineering: failure injection, game days, resilience testing | |
| M54 | Webhooks: designing reliable webhook delivery systems | |
| M55 | Zero-downtime deployments: blue-green, canary, rolling updates | |

**Section 2E: Security & Quality**

| Module | Topic | Status |
|---|---|---|
| M56 | OAuth2/OIDC: authorization code + PKCE, client credentials | |
| M57 | TLS deep dive: TLS 1.3 handshake, mTLS, certificate management | |
| M58 | Debugging in production: systematic playbook, layered failures | |
| M59 | Technical writing: RFCs, runbooks, postmortems, Diataxis | |

### 4.2 Your Top Three Strengths

Which three areas from Loop 2 do you feel most confident in? These are the skills you will leverage in Loop 3.

```
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
```

### 4.3 Your Top Three Gaps

Which three areas need the most practice? Be honest. These become your focused learning areas.

```
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
```

### 4.4 The Competence Check

Answer honestly:

> **If you joined a new company tomorrow and they had a system like TicketPulse v2, could you:**
>
> - [ ] **Operate it?** Deploy a new version, monitor dashboards, respond to alerts, scale up/down.
> - [ ] **Debug it?** Investigate a production incident using only observability tools, find the root cause, write a postmortem.
> - [ ] **Improve it?** Identify bottlenecks, propose architectural changes, write an RFC, implement the improvement.
> - [ ] **Extend it?** Add a new service, integrate it with Kafka and gRPC, configure monitoring and alerting.
>
> **What would you need to learn first?** Write it down.

---

## What You Have Built

Take a moment to look at the full scope of what exists now.

TicketPulse v2 is a complete microservices platform:

- **6+ services** communicating over gRPC and Kafka, each with its own database
- **Kubernetes orchestration** with autoscaling, health checks, and rolling deployments
- **Infrastructure as code** with Terraform managing the infrastructure layer
- **Full observability** with Prometheus metrics, Grafana dashboards, distributed tracing, and structured logging
- **Resilience patterns** including circuit breakers, rate limiters, retries, dead-letter queues, and feature flags
- **Security** with OAuth2/OIDC authentication, TLS/mTLS encryption, and role-based authorization
- **Advanced data patterns** including CQRS, event sourcing, saga orchestration, and graph-based recommendations
- **Operational maturity** with runbooks, postmortem processes, chaos engineering practices, and incident response procedures

You did not just read about these things. You built them, tested them, broke them, and fixed them.

Compare where you started in Loop 1 -- a single Express server with a PostgreSQL database -- to where you are now. That progression is the same journey that takes most engineers 2-3 years of on-the-job experience. You have compressed it into a structured learning path.

---

## What Comes Next: Loop 3 Preview

Loop 3 takes TicketPulse global, real-time, and intelligent. You will be **designing**, not just building.

**TicketPulse Goes Multi-Region**
- Deploy across AWS us-east-1 and eu-west-1
- Data replication strategies: active-active vs active-passive
- Latency-based routing and regional failover
- Conflict resolution for concurrent writes in different regions

**TicketPulse Goes Real-Time**
- WebSocket connections for live ticket availability
- Server-Sent Events for purchase notifications
- Real-time dashboards showing live event capacity
- Handling 100K concurrent WebSocket connections

**TicketPulse Gets Intelligent**
- AI-powered event recommendations (beyond graph-based)
- Dynamic pricing based on demand signals
- Fraud detection for ticket purchases
- Search ranking optimization with ML

**You Become the Architect**
- System design exercises: design Twitter, design Uber, design Stripe
- Capacity planning: estimate compute, storage, and bandwidth requirements
- Cost modeling: calculate AWS bills for different architectures
- Technical leadership: writing architecture reviews, mentoring junior engineers

The difference between Loop 2 and Loop 3: in Loop 2, you followed patterns and implemented solutions. In Loop 3, you will choose the patterns and design the solutions. The constraints get harder, the trade-offs get more nuanced, and the right answer depends on context you have to gather yourself.

---

> **What did you notice?** Looking back at the full TicketPulse architecture, which decisions had the highest impact? Which would you make differently with what you know now? This self-awareness is the real output of Loop 2.

## Final Checkpoint

Before closing Loop 2, verify:

- [ ] You drew TicketPulse v2's complete architecture (all services, data stores, Kafka topics, monitoring)
- [ ] You traced the full purchase data flow (synchronous + asynchronous + observability)
- [ ] You compared the Loop 1 and Loop 2 architectures and identified what improved and what got more complex
- [ ] You ran the stress test and found where TicketPulse v2 breaks
- [ ] You completed the incident drill (detect, triage, mitigate, communicate, resolve, action items)
- [ ] You completed the self-assessment for all 30 Loop 2 modules
- [ ] You identified your top 3 strengths and top 3 gaps
- [ ] You answered the competence check honestly

---

## Congratulations

You finished Loop 2.

In Loop 1, you learned to build a backend system. In Loop 2, you learned to build a **production-grade distributed system**. The distance between those two things is enormous. Most engineers work for years before they are comfortable with the full stack you just worked through: Kubernetes, distributed tracing, saga patterns, chaos engineering, CQRS, TLS, OAuth2, and production debugging.

More importantly, you now have a framework for thinking about distributed systems: how to decompose them, how to make them reliable, how to observe them, how to secure them, and how to respond when they break.

The skills from Loop 2 will not change with the next framework or the next cloud provider. Distributed systems fundamentals -- consensus, consistency, observability, resilience -- are the same whether you are running on AWS, GCP, Azure, or bare metal. The patterns you learned (circuit breakers, sagas, CQRS, event sourcing) have been refined over decades and will be relevant for decades more.

What changes in Loop 3 is the scale of the decisions. You have the tools. Now you will learn when to use them and when not to. That judgment -- knowing which tool fits which problem at which scale -- is what makes a senior engineer.

See you in Loop 3.

## Key Terms

| Term | Definition |
|------|-----------|
| **Stress test** | A test that pushes a system beyond normal operating capacity to find its breaking point. |
| **Incident drill** | A simulated incident used to practice the team's response procedures and identify gaps. |
| **Architecture review** | A structured evaluation of a system's design to identify risks, bottlenecks, and improvement opportunities. |
| **Postmortem** | A blameless review conducted after an incident to document findings and prevent recurrence. |
| **Service mesh** | An infrastructure layer that manages service-to-service communication with built-in observability and resilience features. |

---

## What's Next

You've completed Loop 2. In **Loop 3**, you'll scale TicketPulse to handle millions of users with advanced patterns like multi-region deployment, ML-powered recommendations, and platform engineering.

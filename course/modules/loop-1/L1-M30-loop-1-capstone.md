# L1-M30: Loop 1 Capstone

> **Loop 1 (Foundation)** | Section 1F: Language Exposure + Capstone | ⏱️ 90 min | 🟢 Core | Prerequisites: All previous modules (L1-M01 through L1-M29)
>
> **Source:** Chapters 11, 6 of the 100x Engineer Guide

---

## The Goal

This is the big one. Thirty modules. Hundreds of hours. You built a real system from scratch: a REST API, a database layer, caching, authentication, message queues, CI/CD, tests, security hardening, structured logging, SLOs, and multi-language comparisons.

Now it is time to step back and see the whole picture.

This capstone has four parts:

1. **Architecture Review** -- draw the full system, identify strengths and weaknesses
2. **The Load Test** -- find where TicketPulse breaks under pressure
3. **The Improvement Plan** -- design TicketPulse v2 for 10x and 100x scale
4. **Reflection** -- assess what you know, what needs practice, and what is next

This is not a test. There are no wrong answers. This is an engineering exercise: analyze a system you built, find its limits, and plan what comes next.

---

## Part 1: Architecture Review (30 minutes)

### 1.1 Draw the Architecture

Open a diagramming tool (draw.io, Excalidraw, paper and pen -- whatever works) and draw TicketPulse v1's complete architecture.

Include every component:

```
Clients (curl, browser, mobile)
    │
    ▼
┌─────────────────────────────────────────────┐
│              Express API Server              │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Routes  │ │Middleware │ │  Services    │  │
│  │ /events │ │ - auth   │ │ - pricing    │  │
│  │ /tickets│ │ - csrf   │ │ - tickets    │  │
│  │ /auth   │ │ - reqId  │ │ - events     │  │
│  │ /search │ │ - logger │ │ - cache      │  │
│  │ /health │ │ - sli    │ │ - email(mock)│  │
│  └─────────┘ └──────────┘ └──────────────┘  │
└──────────┬────────────┬────────────┬─────────┘
           │            │            │
           ▼            ▼            ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │PostgreSQL│  │  Redis   │  │ RabbitMQ │
    │          │  │  Cache   │  │  Queue   │
    │ - events │  │ - events │  │ - emails │
    │ - tickets│  │ - sessions│ │ - notifs │
    │ - users  │  │          │  │          │
    │ - reviews│  │          │  │          │
    └──────────┘  └──────────┘  └──────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   Consumer   │
                              │ (background) │
                              │ - send email │
                              │ - send notif │
                              └──────────────┘
```

Also include:

- Docker Compose orchestration (which containers, how they connect)
- CI/CD pipeline (GitHub Actions: lint, typecheck, test, build)
- Environment configuration flow (.env, .env.example, startup validation)
- Logging pipeline (structured JSON logs with request IDs)

### 1.2 Identify Strengths

What is good about this architecture? Write down at least five things:

<details>
<summary>Suggested strengths (do not peek until you have written your own)</summary>

1. **Clear separation of concerns.** Routes, middleware, services, and data access are in separate files. A new developer can navigate the codebase.
2. **Proper authentication and authorization.** JWT-based auth with role checking. Secrets are in environment variables, not code.
3. **Caching layer.** Redis reduces database load for frequently accessed data (event listings).
4. **Async processing.** RabbitMQ decouples email/notification sending from the request path. A slow email provider does not slow down ticket purchases.
5. **Observability.** Structured JSON logging with request IDs means you can trace any request through the system. SLIs are being measured.
6. **Security hardened.** SQL injection, XSS, CSRF, broken auth, and SSRF are all addressed.
7. **Reproducible environment.** Pinned Node version, lockfile discipline, direnv auto-activation, `make setup` for onboarding.
8. **CI/CD pipeline.** Every push is linted, type-checked, and tested automatically.

</details>

### 1.3 Identify Weaknesses

What would break first? What is fragile? Write down at least five weaknesses:

<details>
<summary>Suggested weaknesses (do not peek until you have written your own)</summary>

1. **Single instance.** One Express server handles all traffic. If it crashes, the entire service is down. No redundancy.
2. **No horizontal scaling.** There is no load balancer. Adding a second server instance would require shared session storage (already in Redis, which is good) but there is no orchestration for multiple instances.
3. **Database is a single point of failure.** One PostgreSQL instance. No replication. If the database goes down, everything goes down.
4. **No connection pooling limits.** Under heavy load, the app will open too many database connections and exhaust PostgreSQL's `max_connections` (default: 100).
5. **No rate limiting.** An attacker (or a buggy client) can flood the API with requests. There is no protection against this.
6. **Synchronous ticket purchase.** The ticket purchase flow hits the database synchronously. Under load, this becomes a bottleneck with lock contention.
7. **No database read replicas.** All reads and writes go to the same database instance. Read-heavy workloads (browsing events) compete with write-heavy workloads (buying tickets).
8. **No CDN.** Static assets and event data that rarely changes are served directly from the Express server.
9. **No health check dependencies.** The `/health` endpoint returns 200 even if the database or Redis is down. It should check downstream dependencies.
10. **In-memory SLI metrics.** The SLI collector stores metrics in memory. If the server restarts, all metrics are lost. In a multi-instance deployment, each instance has its own metrics.

</details>

### 1.4 The Architecture Scorecard

Rate TicketPulse v1 on each dimension (1-5):

| Dimension | Score | Notes |
|---|---|---|
| **Correctness** | /5 | Does it do what it should? |
| **Reliability** | /5 | What happens when things fail? |
| **Scalability** | /5 | Can it handle 10x traffic? |
| **Security** | /5 | Is it hardened against common attacks? |
| **Observability** | /5 | Can you see what is happening? |
| **Operability** | /5 | How easy is it to deploy and maintain? |
| **Developer Experience** | /5 | How easy is it to develop and test? |

A realistic score for TicketPulse v1 is probably: Correctness 4, Reliability 2, Scalability 2, Security 4, Observability 3, Operability 3, Developer Experience 4.

The weak spots are reliability and scalability. That is expected for a v1 built by a small team. Those are exactly what Loop 2 will address.

---

## Part 2: The Load Test (20 minutes)

### 2.1 Install a Load Testing Tool

We will use `wrk` (which you already have from M28) or `k6` for more sophisticated tests:

```bash
# If you want k6 (recommended for the ramp-up test):
brew install k6

# wrk is fine too:
brew install wrk
```

### 2.2 Baseline: What Can TicketPulse Handle?

Start with a gentle load and ramp up:

**Using wrk:**

```bash
echo "=== 10 concurrent connections ==="
wrk -t1 -c10 -d10s http://localhost:3000/api/events
echo ""

echo "=== 100 concurrent connections ==="
wrk -t2 -c100 -d10s http://localhost:3000/api/events
echo ""

echo "=== 500 concurrent connections ==="
wrk -t4 -c500 -d10s http://localhost:3000/api/events
echo ""

echo "=== 1000 concurrent connections ==="
wrk -t4 -c1000 -d10s http://localhost:3000/api/events
echo ""
```

**Using k6 (more realistic ramp-up):**

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },    // Ramp up to 10 users
    { duration: '30s', target: 100 },   // Ramp up to 100 users
    { duration: '30s', target: 500 },   // Ramp up to 500 users
    { duration: '30s', target: 1000 },  // Ramp up to 1000 users
    { duration: '30s', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<1000'],  // Our SLOs from M26
    http_req_failed: ['rate<0.001'],                   // 99.9% success rate
  },
};

export default function () {
  // Mix of read and write operations
  const eventRes = http.get('http://localhost:3000/api/events');
  check(eventRes, {
    'events status is 200': (r) => r.status === 200,
    'events response time < 200ms': (r) => r.timings.duration < 200,
  });

  sleep(Math.random() * 2);  // Think time between requests

  // Occasionally try to buy a ticket
  if (Math.random() < 0.1) {
    const ticketRes = http.post(
      'http://localhost:3000/api/events/1/tickets',
      JSON.stringify({ email: `user${__VU}@example.com`, quantity: 1 }),
      { headers: { 'Content-Type': 'application/json' } }
    );
    check(ticketRes, {
      'ticket purchase succeeded': (r) => r.status === 201 || r.status === 409,
    });
  }
}
```

```bash
k6 run load-test.js
```

### 2.3 Record Your Results

| Concurrent Users | Requests/sec | p95 Latency | p99 Latency | Error Rate | Notes |
|---|---|---|---|---|---|
| 10 | | | | | |
| 100 | | | | | |
| 500 | | | | | |
| 1000 | | | | | |

### 2.4 Watch the System While Under Load

While the load test runs, open another terminal and watch resource usage:

```bash
# Docker resource usage (CPU, memory, network)
docker stats

# PostgreSQL connection count
docker exec ticketpulse-postgres-1 psql -U ticketpulse -c "SELECT count(*) FROM pg_stat_activity;"

# Redis connection count and memory
docker exec ticketpulse-redis-1 redis-cli -a "$REDIS_PASSWORD" info clients
docker exec ticketpulse-redis-1 redis-cli -a "$REDIS_PASSWORD" info memory
```

### 2.5 Find the First Bottleneck

At what point does TicketPulse degrade? What degrades first?

Common findings:

**Database connections (most likely first bottleneck):**

```bash
# Check if connections are exhausted
docker exec ticketpulse-postgres-1 psql -U ticketpulse -c \
  "SELECT count(*) as active, max_conn FROM pg_stat_activity, (SELECT setting::int as max_conn FROM pg_settings WHERE name='max_connections') mc GROUP BY max_conn;"
```

If active connections approach `max_connections` (default 100), new requests will fail with "too many connections." This is the most common first bottleneck in any Node.js + PostgreSQL application.

**Event loop saturation:**

```bash
# Check if the Node.js event loop is blocked
# Add this to your app temporarily:
```

```typescript
// src/middleware/event-loop-monitor.ts
setInterval(() => {
  const start = Date.now();
  setImmediate(() => {
    const lag = Date.now() - start;
    if (lag > 50) {
      logger.warn('Event loop lag detected', { lagMs: lag });
    }
  });
}, 1000);
```

If lag exceeds 50ms, the event loop is saturated. CPU-bound work (JSON serialization, request parsing) is blocking other requests.

**Memory:**

```bash
docker stats --format "{{.Name}}: {{.MemUsage}}"
```

If the Node.js container is approaching its memory limit, you may see slowdowns from garbage collection pressure.

### 2.6 Debug: Diagnose the Bottleneck

Based on what you observed, answer:

1. What was the first thing to degrade? (Response time? Error rate? Memory?)
2. At what load level did it start degrading?
3. What component caused it? (Database? App server? Redis? Network?)
4. What is the theoretical maximum throughput of TicketPulse v1?

> **Write your findings down.** These become the input for Part 3.

---

## Part 3: The Improvement Plan (30 minutes)

### 3.1 Design: TicketPulse v2

Based on your load test findings, write a one-page improvement plan. Address two scenarios:

**Scenario A: 10x More Users**

Current: handles ~500 concurrent users comfortably.
Target: handle ~5,000 concurrent users.

What changes are needed?

<details>
<summary>Suggested improvements for 10x (do not peek until you have written your own)</summary>

1. **Connection pooling.** Configure the PostgreSQL pool properly: min 5, max 20 connections per app instance, with connection timeout and idle timeout.

2. **Horizontal scaling.** Run 3-5 instances of the Express app behind a load balancer (nginx or an application load balancer). Redis already handles shared sessions.

3. **Database read replicas.** Add one PostgreSQL read replica. Route all read queries (event listings, search) to the replica. Writes go to the primary.

4. **Rate limiting.** Add rate limiting middleware: 100 requests/minute per IP for anonymous users, 1000/minute for authenticated users.

5. **Improved caching.** Cache event listings in Redis with a 30-second TTL. Cache individual events with a 5-minute TTL. This eliminates most database reads.

6. **Connection pooling for Redis.** Use ioredis with a connection pool instead of a single connection.

7. **Health check with dependencies.** The health endpoint should check PostgreSQL and Redis connectivity, not just return 200.

</details>

**Scenario B: 100x More Users**

Current: handles ~500 concurrent users.
Target: handle ~50,000 concurrent users.

What changes are needed?

<details>
<summary>Suggested improvements for 100x (do not peek until you have written your own)</summary>

1. **CDN for static content.** Put CloudFront or Cloudflare in front of the API. Cache event listings at the edge (TTL: 30 seconds). This eliminates 80%+ of requests from reaching the origin.

2. **Database sharding or partitioning.** Partition the tickets table by event ID. Hot events (concerts going on sale) do not contend with the rest of the database.

3. **CQRS (Command Query Responsibility Segregation).** Separate the read path (browsing events) from the write path (buying tickets). The read path can be served from a denormalized read store (Elasticsearch or a materialized view) that is eventually consistent. The write path hits the transactional database.

4. **Queue-based ticket purchases.** Instead of synchronous database writes during purchase, put purchase requests into a queue. A dedicated consumer processes purchases sequentially, eliminating race conditions and reducing database contention. The client gets a "purchase in progress" response and polls for completion.

5. **Autoscaling.** Deploy on Kubernetes or ECS with horizontal pod autoscaling. Scale from 3 to 50 instances based on CPU/request rate.

6. **Database connection pooling with PgBouncer.** Put PgBouncer between the app instances and PostgreSQL. PgBouncer multiplexes hundreds of app connections onto a smaller number of database connections.

7. **Search engine.** Move event search to Elasticsearch. Full-text search, filtering, and faceted navigation become fast and scalable without loading the primary database.

8. **Distributed caching.** Redis Cluster instead of a single Redis instance. Replicated across availability zones.

9. **Microservices (maybe).** Split the auth service, the event catalog service, and the ticket purchase service into separate deployments. Each can scale independently. But only if the team is large enough to support the operational complexity.

</details>

### 3.2 Decision Matrix

For each potential improvement, evaluate:

| Improvement | Impact | Effort | Risk | Priority |
|---|---|---|---|---|
| Connection pooling | High | Low | Low | P0 |
| Horizontal scaling + LB | High | Medium | Low | P0 |
| Read replicas | High | Medium | Medium | P1 |
| Rate limiting | Medium | Low | Low | P0 |
| CDN | High | Low | Low | P1 |
| CQRS | High | High | High | P2 |
| Database sharding | High | High | High | P2 |
| Queue-based purchases | High | Medium | Medium | P1 |
| Elasticsearch | Medium | Medium | Medium | P2 |
| Microservices | Variable | Very High | Very High | P3 |

The priority framework:
- **P0:** Do immediately. High impact, low effort, low risk.
- **P1:** Do soon. High impact, moderate effort.
- **P2:** Plan for next quarter. High impact, high effort.
- **P3:** Evaluate when needed. Variable impact, very high effort and risk.

> **The key insight:** The best improvements are boring. Connection pooling, caching, and a load balancer will get you to 10x. You do not need microservices or CQRS until you are much, much bigger than you think.

### 3.3 The Architecture Evolution

Write out how TicketPulse's architecture changes at each scale level:

**Current (~500 users):**

```
Client → Express → PostgreSQL
                 → Redis
                 → RabbitMQ → Consumer
```

Single everything. Simple. Works.

**10x (~5,000 users):**

```
Client → Load Balancer → Express (x3) → PgBouncer → PostgreSQL (primary)
                                       → Redis            ↓
                                       → RabbitMQ    PostgreSQL (replica)
                                            ↓
                                         Consumer (x2)
```

Multiple app instances, connection pooler, read replica, multiple consumers. The architecture is the same shape, just with redundancy.

**100x (~50,000 users):**

```
Client → CDN (CloudFront) → Load Balancer → API instances (autoscaled)
                                                ↓           ↓
                                           Read path    Write path
                                               ↓           ↓
                                          Elasticsearch  PostgreSQL (sharded)
                                          (event search)  + PgBouncer
                                               ↓           ↓
                                          Redis Cluster  Queue → Consumers
```

The architecture changes shape. Read and write paths separate. Specialized data stores appear (Elasticsearch for search). The database is sharded. Caching moves to the edge (CDN).

**The pattern:** at 1x, optimize the code. At 10x, add instances. At 100x, change the architecture. Most teams try to change the architecture at 10x, which is premature and expensive. Most teams try to add instances at 100x, which does not work because the bottleneck is architectural.

### 3.4 Write Your One-Page Plan

Take 10 minutes and write a concrete plan. Use this template:

```markdown
# TicketPulse v2 Improvement Plan

## Current State
- Max concurrent users: ___
- First bottleneck: ___
- Current SLO compliance: ___

## Phase 1: Quick Wins (1-2 weeks)
- [ ] ___
- [ ] ___
- [ ] ___

## Phase 2: 10x Scale (1-2 months)
- [ ] ___
- [ ] ___
- [ ] ___

## Phase 3: 100x Scale (3-6 months)
- [ ] ___
- [ ] ___
- [ ] ___

## Decisions Deferred (do not need these yet)
- ___
- ___
```

The "Decisions Deferred" section is as important as the action items. Knowing what NOT to do yet is engineering maturity.

---

## Part 4: Reflection (10 minutes)

### 4.1 The Full Map

Here is everything you have built and learned across 30 modules. Go through each item and mark it:

- Got it -- you could explain this to a junior engineer
- Need more practice -- you understand the concept but want more hands-on time
- Still fuzzy -- you need to revisit this

**Section 1A: Dev Environment & Foundations**

| Module | Topic | Status |
|---|---|---|
| M01 | Project setup, Docker Compose, exploring a codebase | |
| M02 | Terminal, shell, editor configuration | |
| M03 | Git: branching, merging, rebasing, conflict resolution | |
| M04 | HTTP, DNS, TCP/IP, TLS, how requests travel the internet | |

**Section 1B: Data Layer**

| Module | Topic | Status |
|---|---|---|
| M05 | PostgreSQL: setup, basic queries, data types | |
| M06 | SQL: JOINs, aggregations, subqueries, window functions | |
| M07 | Indexing: B-trees, composite indexes, EXPLAIN ANALYZE | |
| M08 | Data modeling: normalization, denormalization, trade-offs | |
| M09 | NoSQL: Redis data structures, when to use key-value vs relational | |
| M10 | Caching: strategies (aside, through, behind), TTL, invalidation | |

**Section 1C: Building the API**

| Module | Topic | Status |
|---|---|---|
| M11 | REST API design: resources, verbs, status codes, pagination | |
| M12 | Error handling: error types, error responses, graceful degradation | |
| M13 | Authentication: JWT, bcrypt, role-based authorization | |
| M14 | Docker: multi-stage builds, Dockerfile, container orchestration | |
| M15 | CI/CD: GitHub Actions pipeline, lint/test/build automation | |
| M16 | Testing: unit tests, integration tests, TDD, test doubles | |

**Section 1D: Async & Messaging**

| Module | Topic | Status |
|---|---|---|
| M17-M22 | Message queues, async processing, consumers, event-driven patterns | |

**Section 1E: Security & Reliability**

| Module | Topic | Status |
|---|---|---|
| M23 | OWASP Top 10: SQL injection, XSS, CSRF, broken auth, SSRF | |
| M24 | Secrets management: .env, startup validation, direnv | |
| M25 | Logging: structured JSON, request IDs, log levels, jq | |
| M26 | SLOs: availability, latency, error budgets, burn rate | |
| M27 | Dependencies: version pinning, lockfiles, reproducible environments | |

**Section 1F: Language Exposure + Capstone**

| Module | Topic | Status |
|---|---|---|
| M28 | Language comparison: Go, Python, TypeScript, Rust side by side | |
| M29 | Concurrency: goroutines, event loop, asyncio, tokio, threads vs async | |
| M30 | Capstone: architecture review, load testing, improvement planning | |

### 4.2 Your Top Three Strengths

What three areas do you feel most confident in? These are your foundation -- the skills you will build on in Loop 2.

```
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
```

### 4.3 Your Top Three Growth Areas

What three areas need the most practice? These become your focused learning areas in Loop 2.

```
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
```

### 4.4 What Surprised You?

Write one thing that surprised you during Loop 1. Maybe it was how simple SQL injection is. Maybe it was how much overhead Docker adds. Maybe it was how similar the concurrency models actually are across languages.

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## What You Have Built

Step back and look at what exists now:

- **A running application** with API, database, cache, and message queue
- **Authentication and authorization** with JWTs and role-based access
- **Security hardening** against the five most common web vulnerabilities
- **Structured observability** with JSON logs, request tracing, and SLI measurement
- **Automated CI/CD** that lints, type-checks, tests, and builds on every push
- **A reproducible environment** that any developer can set up in under 15 minutes
- **A test suite** with unit tests, integration tests, and TDD methodology
- **Benchmarks** across four languages showing real performance characteristics
- **An architecture review** with a clear improvement roadmap
- **Defined SLOs** with error budgets and measurement infrastructure

That is not a toy. That is a real system with real engineering practices. Most working engineers do not have all of these in their production systems.

---

## What Comes Next: Loop 2 Preview

Loop 2 takes everything you built and makes it production-grade:

- **Distributed systems:** What happens when you have multiple instances? Consensus, leader election, distributed transactions.
- **Advanced database patterns:** Sharding, replication, connection pooling with PgBouncer, query optimization at scale.
- **Kubernetes:** Orchestration, autoscaling, rolling deployments, service mesh.
- **Advanced observability:** Distributed tracing (OpenTelemetry), metrics (Prometheus), dashboards (Grafana), alerting.
- **System design:** Design interviews, capacity planning, trade-off analysis for real-world architectures.
- **Performance engineering:** Profiling, flame graphs, memory analysis, optimization techniques.

The foundation is solid. Loop 2 is where you learn to build systems that serve millions.

---

## Final Checkpoint

Before closing Loop 1, verify:

- [ ] You drew the TicketPulse architecture diagram (all components, all data flows)
- [ ] You identified at least 5 strengths and 5 weaknesses of the current architecture
- [ ] You ran a load test and found the first bottleneck
- [ ] You wrote an improvement plan for 10x and 100x scale
- [ ] You completed the self-assessment for all 30 modules
- [ ] You identified your top 3 strengths and top 3 growth areas

---

## Congratulations

You finished Loop 1. You did not just read about backend engineering -- you built a real system, broke it, fixed it, secured it, measured it, and planned its evolution.

Most importantly, you now have a mental framework for thinking about systems: how they work, how they fail, how they scale, and how to make decisions about improving them.

That framework is worth more than any single technology. Technologies change. The ability to analyze a system, find its limits, and design improvements does not.

See you in Loop 2.

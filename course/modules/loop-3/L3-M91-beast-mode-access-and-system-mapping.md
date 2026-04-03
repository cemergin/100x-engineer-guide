# L3-M91: Beast Mode — Access & System Mapping

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M47 (Alerting & On-Call), L1-M01 (Course Setup)
>
> **Source:** Chapter 36 of the 100x Engineer Guide

## What You'll Learn

- How to systematically verify your access to every layer of the stack
- Drawing a system mental model from infrastructure-as-code and deployment configs
- Tracing a user request end-to-end through a distributed system
- Identifying single points of failure and blast radius boundaries
- The "metrics and infra don't lie" principle — why observable truth beats documentation

## Why This Matters

The Nick Hook principle: your studio is pre-wired before the session starts. A recording engineer does not sit down and wonder where the patch bay is, whether the console is powered on, or if the monitor speakers work. Everything is verified before the artist arrives. The first hour of studio time is never spent searching for cables.

You have been building TicketPulse for months. You know where things are. But now, pretend you do not. Pretend today is your first day on the team. Someone hands you a laptop and says "the purchase flow is broken, figure it out." This module simulates that experience — the disorientation of joining a new team, the systematic process of becoming operational, and the discovery that infrastructure code reveals truths that documentation hides.

This matters because you will change teams. You will switch companies. You will inherit systems built by engineers who left before you arrived. The speed at which you become dangerous — not dangerous in a reckless sense, but dangerous in the sense that you can find problems, trace failures, and ship fixes — determines your first-month impact. Engineers who take three weeks to "ramp up" are not slower learners; they lack a systematic approach.

> 💡 **Insight**: "The best engineers I've ever hired were productive within 48 hours. Not because they were geniuses, but because they had a repeatable process for understanding a new system — verify access, read the infrastructure, trace the critical path. They didn't wait for someone to explain the architecture; they read the code that defines it."

---

## The Scenario

**You have just "joined" the TicketPulse team.** Forget everything you know about the system. Open a fresh terminal. Pretend the only thing you have been told is:

> "TicketPulse is a concert ticketing platform. The repo is at `ticketpulse/`. Users buy tickets. Sometimes things break. Good luck."

Your goal over the next 75 minutes: become operational. Not an expert. Operational — meaning you could respond to a page at 2 AM and have a reasonable chance of diagnosing the problem.

---

## Phase 1: Access Verification Sweep (~25 min)

### 🛠️ Build: Your Access Checklist

Before you can debug anything, you need to confirm you can reach everything. An engineer who cannot access the monitoring dashboard during an incident is useless. An engineer who discovers their VPN is broken while the CEO is asking for a status update is worse than useless.

Work through this checklist systematically. For each item, record whether you have access, the URL or command, and any blockers.

```
ACCESS VERIFICATION CHECKLIST
═══════════════════════════════════════════════════════════════
Layer                  │ Check Command / URL         │ Status
═══════════════════════╪═════════════════════════════╪═══════
Source code            │ git clone / git pull        │ [ ]
Local build            │ docker-compose up --build   │ [ ]
Test suite             │ npm test / go test ./...    │ [ ]
CI/CD pipelines        │ GitHub Actions tab          │ [ ]
Container registry     │ docker pull <image>         │ [ ]
Monitoring (Grafana)   │ http://localhost:3000       │ [ ]
Metrics (Prometheus)   │ http://localhost:9090       │ [ ]
Alerting (Alertmanager)│ http://localhost:9093       │ [ ]
Log aggregation        │ kubectl logs / Loki         │ [ ]
Database (read access) │ psql / mongosh              │ [ ]
Message queue          │ Kafka UI / rabbitmqctl      │ [ ]
Secrets / env config   │ .env files / vault          │ [ ]
Cloud console          │ AWS/GCP console login       │ [ ]
Incident channel       │ Slack #ticketpulse-incidents│ [ ]
On-call schedule       │ PagerDuty / Opsgenie        │ [ ]
═══════════════════════╧═════════════════════════════╧═══════
```

**Step 1 — Clone and build.** Start at the foundation. Can you get the code and run it?

```bash
# Clone the repo (or just cd into your existing checkout)
cd ticketpulse/

# Build everything from scratch
docker-compose build --no-cache

# Start the full stack
docker-compose up -d

# Verify services are running
docker-compose ps
```

If any service fails to start, note it. Do not debug it yet — just record the failure and move on. You are mapping, not fixing.

**Step 2 — Run the test suite.** Can tests pass on a clean checkout?

```bash
# Run unit tests
npm test          # or: go test ./... / pytest / etc.

# Run integration tests (if they exist)
npm run test:integration
```

Record the result: all passing, some failing, or unable to run. If tests fail, note which ones — this is signal about the system's current state.

**Step 3 — Access the monitoring stack.** Open each dashboard from L2-M45.

```bash
# Grafana — should be running from docker-compose
open http://localhost:3000
# Default credentials: admin / admin (or check .env)

# Prometheus — query interface
open http://localhost:9090
# Run a test query: up
# You should see all scraped targets

# Alertmanager
open http://localhost:9093
```

**Step 4 — Check CI/CD.** Can you see the pipeline history?

```bash
# If using GitHub Actions:
gh run list --limit 5

# Check the most recent run
gh run view $(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
```

**Step 5 — Find the secrets.** Where are environment variables stored? This is one of the most important things to locate early.

```bash
# Check for .env files
find . -name ".env*" -not -path "./node_modules/*"

# Check for docker-compose environment references
grep -r "env_file\|environment:" docker-compose.yml

# Check for secret references in CI/CD
grep -r "secrets\." .github/workflows/
```

### 🤔 Reflect

> Which layer was hardest to verify? In a real onboarding, what would you do if access to a critical system (say, production database read access) was blocked? How long would you wait before escalating?

---

## Phase 2: Architecture from Infrastructure (~25 min)

### 📐 Design: Draw the System from Code

Here is the rule: **you are not allowed to read any documentation, README, or architecture diagram.** You will reverse-engineer TicketPulse's architecture from the infrastructure code alone. This simulates what happens when documentation is outdated (it usually is).

**Step 1 — Read `docker-compose.yml`.** This is the single most information-dense file in many projects.

```bash
cat docker-compose.yml
```

For every service defined, answer these questions:

```
SERVICE INVENTORY (from docker-compose.yml)
═══════════════════════════════════════════════════════════════
Service Name    │ Image/Build  │ Ports     │ Depends On  │ Role
════════════════╪══════════════╪═══════════╪═════════════╪═════
                │              │           │             │
                │              │           │             │
                │              │           │             │
                │              │           │             │
                │              │           │             │
═══════════════════════════════════════════════════════════════
```

Guided questions while reading:
- How many distinct services are there? Which ones are custom code vs. off-the-shelf (Postgres, Redis, Kafka)?
- Which services expose ports to the host? Those are the entry points.
- What do the `depends_on` relationships tell you about service startup order and dependencies?
- Are there any volume mounts that hint at persistent state?
- Are there environment variables referencing other services? Those reveal runtime connections.

**Step 2 — Read Terraform / K8s manifests.** If the project has infrastructure-as-code, it tells you what exists in production.

```bash
# Find infrastructure definitions
find . -name "*.tf" -o -name "*.yaml" -path "*/k8s/*" -o -name "Dockerfile" | head -20

# Read Terraform files (if they exist)
cat infrastructure/*.tf 2>/dev/null

# Read Kubernetes manifests (if they exist)
cat k8s/*.yaml 2>/dev/null
```

For each resource you find, record:
- What type of resource is it? (Database, load balancer, cache, queue, storage bucket)
- What region/zone is it deployed to?
- What size/tier is it? (This tells you about expected load)
- What other resources does it reference?

**Step 3 — Read CI/CD config.** The pipeline reveals what gets built and where it goes.

```bash
cat .github/workflows/*.yml
```

Questions to answer:
- What triggers a deployment? (push to main? tag? manual?)
- What environments exist? (staging, production, canary?)
- What steps run before deployment? (tests, linting, security scans?)
- Where do artifacts get pushed? (Docker registry, S3, CDN?)

**Step 4 — Draw the architecture.** Using only what you have learned from files, draw TicketPulse's architecture. Use ASCII or a whiteboard. Include every service, database, queue, cache, and external dependency.

```
TICKETPULSE ARCHITECTURE (drawn from infra code)
══════════════════════════════════════════════════

    [Internet]
        │
        ▼
   ┌─────────┐
   │  Nginx   │ :80/:443
   │ (proxy)  │
   └────┬─────┘
        │
   ┌────┴─────────────────────────────┐
   │              │                   │
   ▼              ▼                   ▼
┌───────┐   ┌──────────┐      ┌──────────┐
│  ???  │   │   ???    │      │   ???    │
│       │   │          │      │          │
└───┬───┘   └────┬─────┘      └────┬─────┘
    │            │                  │
    ▼            ▼                  ▼
  [???]        [???]             [???]

(Fill in service names, databases, queues,
 and connections from what you found)
```

**Step 5 — Compare to what you already know.** Now — and only now — compare your infrastructure-derived diagram to the architecture you know from building TicketPulse over the past months.

```
ARCHITECTURE COMPARISON
═══════════════════════════════════════════════════
What infra code revealed         │ What was missing
═════════════════════════════════╪═════════════════
                                 │
                                 │
                                 │
═══════════════════════════════════════════════════
What infra code got wrong        │ Why it was wrong
═════════════════════════════════╪═════════════════
                                 │
                                 │
═══════════════════════════════════════════════════
```

### 🤔 Reflect

> What did the infrastructure code reveal that you had forgotten or never explicitly thought about? Were there services or dependencies that surprised you? What would a new engineer miss if they only read the README?

---

## Phase 3: Trace the Critical Path (~25 min)

### 🔍 Explore: Follow a Ticket Purchase End-to-End

TicketPulse's most important user action is purchasing a ticket. If this breaks, revenue stops. Trace it from the user's browser click to the confirmation email.

**Step 1 — Map every hop.** Start at the user's browser and follow the request through every service it touches.

```
CRITICAL PATH TRACE: Ticket Purchase
══════════════════════════════════════════════════════════════════
Hop │ From           │ To              │ Protocol │ What Can Fail
════╪════════════════╪═════════════════╪══════════╪══════════════
 1  │ Browser        │ Nginx/LB        │ HTTPS    │ DNS, TLS cert
 2  │ Nginx/LB       │ API Gateway     │ HTTP     │ Proxy config
 3  │ API Gateway    │ Order Service   │ HTTP/gRPC│ Auth, routing
 4  │ Order Service  │ Database        │ TCP/SQL  │ Connection pool
 5  │ Order Service  │ Payment Service │ HTTP     │ Timeout, 3rd party
 6  │ Payment Service│ Stripe/Provider │ HTTPS    │ Rate limit, outage
 7  │ Payment Service│ Order Service   │ HTTP/CB  │ Circuit breaker
 8  │ Order Service  │ Kafka           │ TCP      │ Broker down
 9  │ Kafka          │ Notification Svc│ TCP      │ Consumer lag
 10 │ Notification   │ Email Provider  │ HTTPS    │ Deliverability
════╧════════════════╧═════════════════╧══════════╧══════════════
```

This template is a starting point. Your TicketPulse setup may differ. Trace the actual path by reading the code:

```bash
# Find the purchase endpoint
grep -r "purchase\|checkout\|order" --include="*.ts" --include="*.go" --include="*.py" -l

# Read the handler — follow the function calls
# Look for: HTTP calls to other services, database queries,
# queue publishes, external API calls
```

For each hop, answer:
- What data is passed? (request body, headers, IDs)
- What is the expected latency? (< 50ms for DB, < 2s for payment)
- What happens if this hop fails? (retry? fallback? user error?)
- Is there a timeout configured? What is it?

**Step 2 — Identify single points of failure.**

A single point of failure (SPOF) is any component where, if it goes down, the entire purchase flow breaks with no fallback.

```
SINGLE POINTS OF FAILURE ANALYSIS
═══════════════════════════════════════════════════
Component        │ SPOF? │ Why / Mitigation
═════════════════╪═══════╪═════════════════════════
Database         │       │
Payment provider │       │
Kafka cluster    │       │
Order service    │       │
API Gateway      │       │
DNS              │       │
═════════════════╧═══════╧═════════════════════════
```

**Step 3 — The "What Can Kill Us" Top 3.** Based on your trace, identify the three failure scenarios that would cause the most damage. Consider both likelihood and blast radius.

```
TOP 3 FAILURE SCENARIOS
═══════════════════════════════════════════════════════════════
Rank │ Scenario                │ Blast Radius    │ Likelihood
═════╪═════════════════════════╪═════════════════╪════════════
  1  │                         │                 │
  2  │                         │                 │
  3  │                         │                 │
═════╧═════════════════════════╧═════════════════╧════════════
```

Think about:
- Database goes down — who is affected? Just purchases, or everything?
- Payment provider has a 30-second outage — do requests queue or fail?
- Kafka loses a broker — do orders get lost or do they retry?
- A bad deploy goes out at 5 PM on Friday — how fast can you roll back?

### 📊 Observe: Validate with Live Metrics

If your monitoring stack is running, validate your trace with real data. Make a test purchase and watch it flow through the system.

```bash
# In one terminal, watch order service logs
docker-compose logs -f order-service

# In another terminal, watch payment service logs
docker-compose logs -f payment-service

# In a third terminal, trigger a purchase
curl -X POST http://localhost:8080/api/purchases \
  -H "Content-Type: application/json" \
  -d '{"eventId": "test-event-1", "quantity": 1}'
```

Watch the logs. Does the request follow the path you mapped? Did it touch services you did not expect? Did it skip a service you thought it would hit?

### 🤔 Reflect

> What surprised you during the trace? Was the actual path simpler or more complex than you expected? If you were paged at 2 AM and told "purchases are failing," which hop would you check first, and why?

---

## Wrap-Up: Your Operational Readiness Score

You have completed three things that every engineer should do in their first 48 hours on a new team:

1. **Access verified** — you know what you can reach and what is blocked
2. **Architecture mapped** — you have a mental model derived from truth (code), not hope (documentation)
3. **Critical path traced** — you know the most important user flow and where it can break

```
SELF-ASSESSMENT
═══════════════════════════════════════════════
Area                          │ Confidence (1-5)
══════════════════════════════╪════════════════
I can access every layer      │
I can draw the architecture   │
I can trace a purchase e2e    │
I know the top 3 failure modes│
I could respond to a 2AM page │
══════════════════════════════╧════════════════
```

### 🤔 Final Reflection

> What did the infrastructure and code reveal that you would not have learned from reading documentation alone? If you had to onboard a new engineer to TicketPulse tomorrow, what would you tell them to do first — and what would you tell them to skip?

---

## Further Reading

- Chapter 36: "Beast Mode" — the full philosophy behind operational readiness
- L2-M47: Alerting & On-Call — the monitoring stack you verified in Phase 1
- L3-M73: Incident Response Simulation — what happens when the system you just mapped breaks
- L3-M83a: Observability & GitOps as Code — why the infra code you read is version-controlled

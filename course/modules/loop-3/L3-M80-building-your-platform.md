# L3-M80: Building Your Platform

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: All Loop 3 modules (operations, architecture, leadership)
>
> **Source:** Chapters 7, 30 of the 100x Engineer Guide

## What You'll Learn

- How to evaluate developer experience as a measurable engineering output
- How to build a "golden path" for new services that eliminates setup friction
- What self-service infrastructure looks like and why it matters at 20+ engineers
- How to design a minimal internal developer platform without over-engineering
- The trade-off between standardization and flexibility at different team sizes

## Why This Matters

TicketPulse's team has grown to 20 engineers. The architecture is sound. The observability is excellent. The CI/CD pipeline works. But a new problem has emerged: the internal developer experience is becoming a bottleneck.

A new engineer joins the team. They spend 2 days getting the local environment running. They ask in Slack: "How do I create a new service?" The answer is: "Copy the order-service, delete the business logic, and update the Dockerfile. Oh, and you need to manually create the Kafka topics, update the K8s manifests, add the Prometheus scrape config, and register the service in the API gateway." That is 3 days of infrastructure ceremony before writing a single line of business logic.

At 5 engineers, this was fine. Everyone knew how everything worked. At 20, it does not scale. At 50, it would be fatal.

> **Pro tip:** "Spotify built Backstage because they had 2,000+ microservices and engineers spent 40% of their time on infrastructure. After Backstage, it dropped to below 10%. You do not need 2,000 microservices to feel this pain -- it starts around 10 services and 15 engineers."

---

## Part 1: Measuring Developer Experience

### 📊 Observe: The Developer Experience Audit

Before building anything, measure where the friction is. Five key metrics:

```
DEVELOPER EXPERIENCE METRICS
═════════════════════════════

1. TIME TO FIRST COMMIT
   How long from "engineer accepts offer" to "first PR merged"?

   TicketPulse current state:
   Clone repo:                    5 min
   Install dependencies:         10 min
   Set up local environment:     45 min (Docker, env vars, databases)
   Get all services running:     30 min (if no issues)
   Understand the codebase:     480 min (multiple days)
   Make first change:            30 min
   Run tests:                    15 min
   Open PR:                       5 min
   ────────────────────────────────────
   Total:                        ~10 hours (spread over 2-3 days)

   Target: < 4 hours


2. CI PIPELINE DURATION
   From push to green/red signal.

   TicketPulse current state:
   Lint + type check:     2 min
   Unit tests:            4 min
   Integration tests:     8 min
   Docker build:          3 min
   Deploy to staging:     5 min
   Smoke tests:           3 min
   ──────────────────────────
   Total:                25 min

   Target: < 10 min (parallelize, cache, selective testing)


3. SERVICE CREATION TIME
   From "I need a new service" to "it is deployed and monitored."

   TicketPulse current state:
   Copy existing service:        30 min
   Strip business logic:         15 min
   Update configs:               45 min
   Create Kafka topics:          15 min (requires platform team)
   Create database:              20 min (requires DBA approval)
   Update K8s manifests:         30 min
   Add Prometheus config:        15 min
   Add Grafana dashboard:        30 min
   Register in API gateway:      10 min
   ──────────────────────────────────
   Total:                        ~4 hours + 1-2 days waiting for approvals

   Target: < 30 minutes (self-service)


4. DOCUMENTATION FINDABILITY
   "Where is the docs for X?"

   TicketPulse current state:
   Architecture docs:     README.md (outdated)
   API docs:              Swagger (sometimes generated)
   Runbooks:              Notion (3 of 8 services documented)
   ADRs:                  Started in M77 (new)
   Onboarding guide:      Does not exist

   Target: centralized, searchable, linked from code


5. INNER LOOP SPEED
   From code change to seeing the result locally.

   TicketPulse current state:
   Save file → TypeScript compile:  2 sec
   Hot reload picks up change:      1 sec
   Run affected test:               4 sec
   See change in browser:           3 sec
   ──────────────────────────────────
   Total:                           ~10 sec

   This is actually good. Protect this at all costs.
```

---

## Part 2: The Golden Path

### What Is a Golden Path?

A golden path is the **recommended, pre-paved, supported way** to do something. Not the only way -- engineers can deviate -- but the way that gets you from zero to production fastest with the least friction.

```
GOLDEN PATH vs. PAVED ROAD vs. GUARDRAILS
──────────────────────────────────────────

Golden Path: "Here is how we recommend building a new service.
  This template includes logging, tracing, health checks,
  Dockerfile, CI pipeline, and K8s manifests. Use it."

Paved Road: "We support these tools and patterns. If you stay
  on the road, the platform team will help you. If you go
  off-road, you are on your own."

Guardrails: "You must use these tools. The CI pipeline will
  reject alternatives." (Strongest enforcement)

For a team of 20: golden path + light guardrails.
For a team of 100: paved road + strong guardrails.
For a team of 500+: full internal platform with self-service.
```

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Service Template

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Create a service template that a new service can be scaffolded from in 30 seconds.

```
ticketpulse-service-template/
├── src/
│   ├── index.ts                 # Entry point with graceful shutdown
│   ├── server.ts                # HTTP server setup (Fastify)
│   ├── routes/
│   │   ├── health.ts            # GET /health (readiness + liveness)
│   │   └── index.ts             # Route registration
│   ├── services/                # Business logic goes here
│   ├── repositories/            # Database access goes here
│   ├── middleware/
│   │   ├── logging.ts           # Request logging (structured JSON)
│   │   ├── tracing.ts           # OpenTelemetry span creation
│   │   ├── error-handler.ts     # Global error handler
│   │   └── auth.ts              # JWT verification
│   └── config.ts                # Environment variable validation
├── test/
│   ├── unit/                    # Unit tests (vitest)
│   ├── integration/             # Integration tests (testcontainers)
│   └── setup.ts                 # Test helpers
├── Dockerfile                   # Multi-stage build, non-root user
├── docker-compose.yml           # Local dev: DB + Redis + Kafka
├── .env.example                 # Required env vars with descriptions
├── k8s/
│   ├── deployment.yaml          # K8s deployment with probes
│   ├── service.yaml             # K8s service
│   ├── hpa.yaml                 # Horizontal pod autoscaler
│   └── configmap.yaml           # Non-secret configuration
├── .github/
│   └── workflows/
│       └── ci.yaml              # Full CI pipeline
├── grafana/
│   └── dashboard.json           # Pre-built Grafana dashboard
├── prometheus/
│   └── alerts.yaml              # Default alerting rules
├── tsconfig.json
├── package.json
└── README.md                    # Auto-generated from template
```

### 🛠️ Build: The create-service Script

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


```bash
#!/bin/bash
# create-service.sh -- scaffold a new TicketPulse service

set -euo pipefail

SERVICE_NAME=$1
if [ -z "$SERVICE_NAME" ]; then
  echo "Usage: ./create-service.sh <service-name>"
  echo "Example: ./create-service.sh recommendation-service"
  exit 1
fi

TEMPLATE_DIR="tools/service-template"
TARGET_DIR="services/$SERVICE_NAME"

echo "Creating service: $SERVICE_NAME"
echo "================================"

# 1. Copy template
cp -r "$TEMPLATE_DIR" "$TARGET_DIR"

# 2. Replace placeholders
find "$TARGET_DIR" -type f -exec sed -i '' \
  "s/{{SERVICE_NAME}}/$SERVICE_NAME/g" {} +
find "$TARGET_DIR" -type f -exec sed -i '' \
  "s/{{SERVICE_PORT}}/$(shuf -i 3010-3099 -n 1)/g" {} +

# 3. Initialize package.json
cd "$TARGET_DIR"
cat > package.json <<EOF
{
  "name": "@ticketpulse/$SERVICE_NAME",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "test": "vitest",
    "test:integration": "vitest --config vitest.integration.config.ts",
    "lint": "eslint src/"
  }
}
EOF

# 4. Install dependencies
npm install

# 5. Create Kafka topics (if needed)
echo ""
echo "Do you need Kafka topics? (y/n)"
read -r NEEDS_KAFKA
if [ "$NEEDS_KAFKA" = "y" ]; then
  echo "Creating Kafka topics..."
  kafka-topics --create --topic "$SERVICE_NAME-events" \
    --partitions 6 --replication-factor 3 \
    --bootstrap-server kafka:9092 2>/dev/null || true
fi

# 6. Summary
echo ""
echo "Service created: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "  1. cd $TARGET_DIR"
echo "  2. cp .env.example .env  (fill in values)"
echo "  3. docker-compose up -d  (start local dependencies)"
echo "  4. npm run dev            (start the service)"
echo "  5. curl http://localhost:PORT/health"
echo ""
echo "CI pipeline: .github/workflows/ci.yaml (already configured)"
echo "Dashboard:   grafana/dashboard.json (import to Grafana)"
echo "Alerts:      prometheus/alerts.yaml (apply to Prometheus)"
```

### What the Template Gives You for Free

```
OUT OF THE BOX (zero config)
════════════════════════════

✅ Structured JSON logging (correlation IDs, request context)
✅ OpenTelemetry tracing (auto-instrumented HTTP + DB + Kafka)
✅ Prometheus metrics (/metrics endpoint)
   - Request count, latency histogram, error rate
   - Active connections, memory usage
✅ Health check (GET /health)
   - Readiness: can this instance serve traffic?
   - Liveness: is this instance still running?
✅ Graceful shutdown (drain connections, finish in-flight requests)
✅ Dockerfile (multi-stage, non-root, <150MB image)
✅ CI pipeline (lint → test → build → push → deploy)
✅ K8s manifests (deployment, service, HPA, probes)
✅ Grafana dashboard (request rate, latency, errors, resources)
✅ Prometheus alerts (high error rate, high latency, pod restarts)

NOT included (add as needed):
⬜ Database (choose: Postgres, Redis, both)
⬜ Kafka consumers/producers (add via shared library)
⬜ Authentication middleware (add if public-facing)
⬜ Rate limiting (add if public-facing)
```

---

## Part 3: Self-Service Infrastructure

### The Ticket Problem

```
THE TICKET PROBLEM
══════════════════

Without self-service:
  Engineer needs a database →
  Files a ticket with platform team →
  Platform team triages (1 day) →
  Platform team provisions (1 day) →
  Engineer gets credentials (1 day) →
  Total: 3 days of waiting

With self-service:
  Engineer runs: create-database --name inventory --size small →
  Database provisioned automatically (5 minutes) →
  Credentials stored in secrets manager →
  Engineer starts building immediately

The productivity difference is not 3 days.
It is 3 days + the context switch cost + the motivation cost
of being blocked + the temptation to "just use the shared
database instead" (which creates coupling).
```

### 📐 Design: Self-Service Capabilities

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


What can engineers provision without filing a ticket?

```
SELF-SERVICE MENU (team of 20)
══════════════════════════════

Tier 1: Fully Self-Service (no approval needed)
  □ Create a new service (from template)
  □ Create a dev/staging database (size-limited)
  □ Create Kafka topics (with naming convention enforcement)
  □ Add a feature flag
  □ Create a staging environment
  □ View any service's logs, metrics, traces

Tier 2: Auto-Approved (automated review, deployed within 1 hour)
  □ Create a production database (triggers cost alert)
  □ Add a new domain/subdomain
  □ Increase resource limits (CPU, memory)
  □ Add a new CI/CD pipeline

Tier 3: Requires Approval (human review, 1 business day SLA)
  □ Create a new AWS account or VPC
  □ Modify network security groups
  □ Add a new third-party integration
  □ Increase spend beyond budget threshold
```

---

## Part 4: The Internal Developer Platform

### 📐 Design: What Would TicketPulse's Platform Look Like?

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


At 20 engineers, you do not need Backstage. But you need the kernel of what Backstage provides.

```
MINIMUM VIABLE PLATFORM (20 engineers)
═══════════════════════════════════════

1. SERVICE CATALOG
   What services exist? Who owns them? Where are they?

   Implementation: a YAML file in the repo root
   ───────────────────────────────────────────
   services:
     - name: order-service
       owner: backend-team
       repo: ticketpulse/order-service
       production_url: https://orders.ticketpulse.com
       dashboard: https://grafana.../d/orders
       runbook: docs/runbooks/order-service.md
       on_call: backend-rotation
       dependencies:
         - payment-service
         - kafka
         - postgres-orders

     - name: payment-service
       owner: backend-team
       ...

   This YAML file is your service catalog. It is not Backstage.
   It is a file that answers 80% of the questions.


2. TEMPLATE LIBRARY
   How do I create a new X?

   Implementation: the create-service script from Part 2
   Plus: create-database, create-kafka-topic, create-feature-flag
   All documented in a single page.


3. DOCUMENTATION HUB
   Where are the docs?

   Implementation: a docs/ directory in the monorepo
   ───────────────────────────────────────────
   docs/
     adr/              ← Architecture Decision Records (M77)
     runbooks/         ← Operational runbooks per service
     onboarding/       ← New engineer setup guide
     api/              ← Auto-generated OpenAPI docs
     architecture.md   ← High-level system diagram
     glossary.md       ← Domain terms defined


4. OBSERVABILITY PORTAL
   How do I see what is happening?

   Implementation: Grafana home dashboard with links
   - Service health overview (all services, green/yellow/red)
   - Link to each service's detailed dashboard
   - Link to Jaeger for distributed tracing
   - Link to log search
   - Recent incidents list
```

### What to Add at 50 Engineers

```
AT 50 ENGINEERS, ADD:
─────────────────────

□ Backstage (or Cortex, Port, OpsLevel)
  - Service catalog becomes a web UI, not a YAML file
  - Software templates replace shell scripts
  - TechDocs renders markdown from repos into a searchable portal

□ Internal CLI
  - `tp create service <name>` (replaces shell script)
  - `tp deploy <service> <env>` (unified deploy command)
  - `tp logs <service>` (unified log access)
  - `tp status` (all services health)

□ Cost Dashboard
  - Per-service cloud cost (from tagging, M75)
  - Budget alerts per team
  - Optimization recommendations

□ Security Scanner
  - Automated dependency vulnerability scanning
  - Secret detection in PRs
  - Compliance checks (GDPR readiness per service)
```

### What to Add at 100 Engineers

```
AT 100 ENGINEERS, ADD:
──────────────────────

□ Full self-service infrastructure
  - Terraform modules with PR-based provisioning
  - Database creation, Kafka topic creation, DNS -- all automated

□ Developer portal
  - Searchable documentation across all services
  - API catalog with interactive testing
  - Dependency graph visualization

□ Platform team (dedicated)
  - 3-5 engineers whose full-time job is developer experience
  - SLOs on platform services (CI < 10 min, deploy < 5 min)
  - Internal "customer" interviews with product engineers
```

---

## Part 5: Measuring Platform Success

### How Do You Know the Platform Is Working?

```
PLATFORM METRICS
════════════════

Metric                              │ Before │ Target │ After
────────────────────────────────────┼────────┼────────┼───────
Time to first commit (new engineer) │ 10 hrs │ 4 hrs  │
Time to create a new service        │ 4 hrs  │ 30 min │
CI pipeline duration                │ 25 min │ 10 min │
% of time on infrastructure         │  35%   │ 15%    │
Services with complete dashboards   │ 3/8    │ 8/8    │
Services with runbooks              │ 3/8    │ 8/8    │
Average PR review turnaround        │ 6 hrs  │ 2 hrs  │
```

The ultimate test: **ask engineers.** A quarterly developer experience survey with 3 questions:

```
1. "On a 1-10 scale, how productive do you feel in our codebase?"
2. "What is the single biggest source of friction in your daily work?"
3. "If you could change one thing about our engineering infrastructure,
    what would it be?"
```

The answers drive the roadmap. Not the tools you think are cool. Not what other companies are building. What YOUR engineers need.

---

## 🤔 Final Reflections

1. **What is the minimum viable platform for a team of 20?** What would you add at 50? At 100? Where is the line between "helpful" and "premature optimization"?

2. **The golden path is a recommendation, not a mandate.** What happens when an engineer wants to deviate? Do you support them, discourage them, or block them? How does this change as the team grows?

3. **Developer experience is invisible work.** It does not ship features. It does not fix bugs users see. How do you justify platform investment to a CEO who asks "why are 3 engineers working on internal tools instead of customer features?"

4. **Spotify built Backstage at 2,000 microservices. TicketPulse has 3.** At what point does investing in a developer platform pay for itself? What is the trigger?

5. **The best platform is one engineers actually use.** How do you ensure adoption without mandating it? What makes an internal tool succeed where others fail?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Developer platform** | An internal platform that provides self-service tools, templates, and services to accelerate development teams. |
| **Golden path** | A recommended, well-supported default workflow or template that embodies organizational best practices. |
| **Self-service** | The ability for developers to provision resources, create services, or perform operations without filing tickets. |
| **Service catalog** | A registry of available internal services and components, including documentation and ownership information. |
| **DevEx** | Developer Experience; the overall satisfaction and productivity developers feel when using internal tools and platforms. |

## Further Reading

- **Backstage by Spotify**: backstage.io -- the open-source developer portal
- **Chapter 9**: Engineering Leadership -- knowledge management, developer effectiveness
- **Chapter 15**: Codebase Organization at Scale -- monorepo tooling, module boundaries
- **"Team Topologies" by Matthew Skelton & Manuel Pais**: platform teams, stream-aligned teams, and the interaction modes between them
- **Humanitec Platform Maturity Model**: a framework for evaluating where your platform is on the maturity curve
- **"An Elegant Puzzle" by Will Larson**: engineering management, including platform team sizing and investment
---

## What's Next

In **GitHub Actions at Scale** (L3-M80a), you'll build on what you learned here and take it further.

<!--
  CHAPTER: 36
  TITLE: Beast Mode — Operational Readiness from Day One
  PART: II — Applied Engineering
  PREREQS: None (Ch 12/12b, 18 helpful)
  KEY_TOPICS: operational readiness, onboarding, codebase navigation, observability setup, incident readiness, system mental models, dashboard quicklinks, tribal knowledge extraction
  DIFFICULTY: All levels
  UPDATED: 2026-04-03
-->

# Chapter 36: Beast Mode — Operational Readiness from Day One

> **Part II — Applied Engineering** | Prerequisites: None (Ch 12/12b, 18 helpful) | Difficulty: All levels

> *"You need to be ready — your setup, synths, drum machines, sounds, presets. So when you show up at someone's studio you are ready to throw down."* — Nick Hook

The engineering equivalent: your AWS console is bookmarked, your Datadog dashboards are favorited, your mental model of the system is loaded, and when the pager fires you're not googling "how do I SSH into prod" — you're already reading the logs. This chapter gives you a repeatable system for getting combat-ready on unfamiliar territory fast — whether you're joining a new company, switching teams, or preparing for on-call.

### In This Chapter
- Priority Triage — the "2 hours, 5 things" quick-hit
- Access & Toolchain — source code, cloud consoles, observability, CI/CD, secrets, communication, end-to-end verification
- System Mental Model — 5-min architecture sketch, data flow tracing, dependency mapping, "what can kill us" list, reading the IaC
- Observability Setup — dashboards, alerts, log queries, and the "golden signals" bookmark bar
- Codebase Navigation — repo structure, hot paths, test suites, and tribal knowledge extraction
- Incident Readiness — runbooks, escalation paths, communication templates, and dry runs
- Tribal Knowledge Extraction — the questions nobody thinks to document
- Closing: The Beast Mode Checklist

### Related Chapters
- **OBSERVABILITY spiral:** ← [Ch 18: Debugging & Monitoring](../part-4-cloud-operations/18-debugging-profiling-monitoring.md) | → [Ch 26: Incident War Stories](../part-4-cloud-operations/26-incident-war-stories.md)
- Chapter 4 (SRE fundamentals — error budgets, SLOs, the theoretical foundation for operational readiness)
- Chapter 7 (DevOps & Infrastructure — the tools and pipelines you need access to)
- Chapter 12/12b (Developer Tooling — Linux, shell, editors, Git, Docker)
- Chapter 18 (Debugging, Profiling & Monitoring — the observability tools you will set up here)
- Chapter 33/33b (GitHub Actions — CI/CD pipelines you will need to understand)
- Chapter 35 (Everything as Code — IaC as the source of truth for your mental model)

---

## 0. PRIORITY TRIAGE — THE "2 HOURS, 5 THINGS" QUICK-HIT

You just joined the team. Maybe it's day one at a new company. Maybe you rotated onto a new squad this morning. Maybe you volunteered for on-call on a system you've never touched. You don't have two weeks to ramp up. You have two hours before the next standup. Here's how you spend them.

### The 5-Thing Rule

In your first two hours, you need exactly five things:

| # | Thing | Time | Why |
|---|-------|------|-----|
| 1 | **One working local build** | 30 min | If you cannot build it, you cannot reason about it. Clone, install, run. If it doesn't work in 30 minutes, file the issue — that's already a contribution. |
| 2 | **One successful deployment path** | 20 min | Find the CI/CD pipeline. Read the last 5 green runs. Understand what "deploy" means here — is it a merge to `main`? A manual approval? An ArgoCD sync? |
| 3 | **One dashboard that shows system health** | 15 min | Find the primary monitoring dashboard. Bookmark it. Understand what "healthy" looks like so you can recognize "unhealthy" later. |
| 4 | **One on-call runbook or incident doc** | 15 min | Find the most recent incident postmortem or on-call runbook. Read it. This tells you what actually breaks, not what theoretically could break. |
| 5 | **One human who will answer questions** | 10 min | Identify your "phone-a-friend." Send them a message now. Don't wait until you're stuck at 2 AM. |

**Total: ~90 minutes.** The remaining 30 minutes are buffer for yak-shaving (VPN issues, MFA setup, waiting for access approvals).

### The Anti-Pattern: "I'll Read All the Docs First"

Do NOT spend your first two hours reading a 50-page architecture document. Here's why:

- Architecture docs are frequently outdated. The system evolved; the docs didn't.
- Reading without context is low-retention. You'll forget 80% by tomorrow.
- You learn systems by touching them, not by reading about them.

The docs are valuable — but read them *after* you have a running build and a mental model. They'll make ten times more sense.

### Quick-Hit Checklist

```markdown
## Day-One Quick-Hit (copy this into your notes)

- [ ] Cloned the primary repo and ran it locally
- [ ] Located the CI/CD pipeline and read last 5 runs
- [ ] Bookmarked the main health dashboard
- [ ] Read one recent incident doc or postmortem
- [ ] Identified my go-to person for questions
- [ ] Noted the 3 biggest "I don't understand this yet" items
```

That last item — the "I don't understand this yet" list — is critical. It becomes your learning roadmap for the next two weeks. Write it down now while everything is unfamiliar. In a week you'll have normalized the confusion and forgotten what you didn't know.

### Speed Matters, But Not for the Reason You Think

Getting combat-ready fast isn't about impressing your new team. It's about **reducing your mean-time-to-usefulness.** Every hour you spend unable to build the project, unable to find the logs, unable to understand the deploy pipeline — that's an hour where you can't help when something goes wrong. And something will go wrong. Murphy's law doesn't wait for your onboarding to finish.

The fastest way to earn trust on a new team is to be the person who, during the first incident after you join, can say "I see the error in the logs" instead of "how do I access the logs?"

---

## 1. ACCESS & TOOLCHAIN

Access is the single biggest blocker for new engineers. You can be the best debugger in the world, but if you can't reach the logs, you're useless. Treat access acquisition as a project, not an afterthought.

### The Access Matrix

Build this table on day one. Fill in every cell. Empty cells are action items.

| System | URL / Entry Point | Access Level | Status | Ticket/Contact |
|--------|-------------------|-------------|--------|----------------|
| Source code (GitHub/GitLab) | `github.com/org/...` | Write | Granted | — |
| CI/CD (GitHub Actions, Jenkins, etc.) | `github.com/org/.../actions` | Read | Granted | — |
| Cloud console (AWS/GCP/Azure) | `console.aws.amazon.com` | ReadOnly | Pending | JIRA-1234 |
| Observability (Datadog/Grafana/etc.) | `app.datadoghq.com` | Read | Pending | Ask @alice |
| Error tracking (Sentry/Bugsnag) | `sentry.io/org/...` | Read | Not requested | — |
| Secrets manager (Vault/AWS SSM) | `vault.internal.co` | App-specific | Not requested | — |
| On-call (PagerDuty/Opsgenie) | `pagerduty.com` | Responder | Not requested | — |
| Communication (Slack channels) | `#team-backend`, `#incidents` | Member | Granted | — |
| Wiki/Docs (Notion/Confluence) | `notion.so/team/...` | Read | Granted | — |
| Database (prod read replica) | `replica.db.internal:5432` | ReadOnly | Not requested | — |
| Feature flags (LaunchDarkly/etc.) | `app.launchdarkly.com` | Read | Not requested | — |
| CDN/Edge (CloudFront/Fastly) | `console.aws.amazon.com/cloudfront` | Read | Pending | JIRA-1234 |

**Pro tip:** Copy this table into a personal doc. Update it as access comes through. When the next person joins your team, hand it to them. You just saved them a day.

### Source Code

The repo is where everything starts. But "clone the repo" is step zero — here's what actually matters:

```bash
# Clone and get oriented
git clone git@github.com:org/main-service.git
cd main-service

# What's the build system?
ls -la | head -20
cat package.json 2>/dev/null || cat Makefile 2>/dev/null || cat Dockerfile

# Can you build it?
make build 2>&1 | tail -20    # or: npm install && npm run build
                                # or: ./gradlew build
                                # or: cargo build

# Can you run it locally?
make run 2>&1 | tail -20       # or: docker-compose up
                                # or: npm run dev

# Can you run the tests?
make test 2>&1 | tail -20      # or: npm test
                                # or: pytest
```

**If the build fails:** Don't spend more than 30 minutes debugging it solo. File an issue or ask your phone-a-friend. A broken local build setup is a team problem, not a you problem. And congratulations — you found your first contribution opportunity.

**Multi-repo environments:** If the system spans multiple repositories, identify the "main" one first. Ask: "If I could only look at one repo, which one?" Start there. Map the others later.

```bash
# Quick way to find all repos you have access to
gh repo list org --limit 100 --json name,description \
  | jq -r '.[] | "\(.name)\t\(.description)"' \
  | sort
```

### Cloud Consoles

Bookmark these immediately. Don't rely on typing URLs from memory at 3 AM during an incident.

**AWS essentials to bookmark (adjust for your cloud provider):**

```
# Create a browser bookmark folder: "Work — AWS"
https://console.aws.amazon.com/ecs/v2/clusters          # ECS clusters
https://console.aws.amazon.com/lambda/home               # Lambda functions
https://console.aws.amazon.com/rds/home                  # RDS databases
https://console.aws.amazon.com/cloudwatch/home            # CloudWatch logs & metrics
https://console.aws.amazon.com/ec2/home#LoadBalancers     # Load balancers
https://console.aws.amazon.com/route53/v2/hostedzones     # DNS
https://console.aws.amazon.com/s3/home                    # S3 buckets
https://console.aws.amazon.com/sqs/v3/home                # SQS queues
https://console.aws.amazon.com/secretsmanager/home        # Secrets Manager
```

**GCP essentials:**

```
https://console.cloud.google.com/kubernetes/list          # GKE clusters
https://console.cloud.google.com/run                      # Cloud Run
https://console.cloud.google.com/logs/query               # Cloud Logging
https://console.cloud.google.com/sql/instances             # Cloud SQL
https://console.cloud.google.com/monitoring                # Cloud Monitoring
```

**Key insight:** Learn the URL patterns. Cloud consoles have predictable URL structures. If you know the pattern, you can jump directly to any resource:

```
# AWS — jump to a specific Lambda function
https://console.aws.amazon.com/lambda/home#/functions/my-function-name

# AWS — jump to CloudWatch logs for a specific log group
https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups/log-group/
  /aws/ecs/my-service

# Datadog — jump to a specific dashboard
https://app.datadoghq.com/dashboard/abc-def-ghi
```

### Observability

This is where truth lives. Code can be deceptive — multiple generations of engineers, different periods of a company's life, legacy still being supported. But metrics say "this is what actually happens." Dashboards don't lie.

**Day-one observability setup:**

1. **Find the primary dashboard.** Ask your team: "What dashboard do you look at when you think something is wrong?" Bookmark it.
2. **Find the log search.** Whether it's Datadog Logs, CloudWatch Logs Insights, Kibana, or Grafana Loki — find it and run one query:

```
# Datadog Log Search — last 15 minutes, errors only
service:my-service status:error

# CloudWatch Logs Insights
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 50

# Kibana (KQL)
service.name: "my-service" AND level: "error"

# Grafana Loki (LogQL)
{service="my-service"} |= "ERROR" | logfmt
```

3. **Find the alerting channel.** Where do alerts fire? Slack channel? PagerDuty? Email? Join that channel now.
4. **Understand the golden signals.** For your primary service, can you answer these four questions right now?

| Signal | Question | Where to find it |
|--------|----------|-------------------|
| **Latency** | What's the p50/p95/p99 response time? | APM dashboard, load balancer metrics |
| **Traffic** | How many requests per second? | APM dashboard, load balancer metrics |
| **Errors** | What's the error rate? | APM dashboard, error tracking tool |
| **Saturation** | How close are we to capacity? | CPU/memory metrics, queue depth |

If you can't answer those four questions for your primary service, that's your next action item.

### CI/CD

Understand the deployment pipeline before you need to use it under pressure.

```bash
# GitHub Actions — find the workflows
ls .github/workflows/

# Read the main deploy workflow
cat .github/workflows/deploy.yml

# Check recent workflow runs
gh run list --limit 10 --json status,conclusion,name,createdAt \
  | jq -r '.[] | "\(.createdAt)\t\(.status)\t\(.conclusion)\t\(.name)"'

# Watch a run in progress
gh run watch
```

**Key questions to answer:**

- What triggers a deploy? Push to `main`? Tag? Manual approval?
- How long does a deploy take? (Check the last 5 runs.)
- How do you roll back? `git revert` + re-deploy? Blue/green switch? Feature flag?
- Is there a staging environment? How do you deploy to it?
- Are there any manual steps? Database migrations? Cache invalidation?

**If using ArgoCD or Flux (GitOps):**

```bash
# ArgoCD — check application status
argocd app list
argocd app get my-service

# Check sync status
argocd app get my-service -o json | jq '.status.sync.status'

# Flux — check kustomizations
flux get kustomizations
flux get helmreleases
```

### Secrets & Configuration

You need to know how secrets work before you accidentally commit one.

```bash
# AWS Secrets Manager — list secrets you can see
aws secretsmanager list-secrets --query 'SecretList[].Name' --output table

# AWS SSM Parameter Store — list parameters
aws ssm describe-parameters --query 'Parameters[].Name' --output table

# HashiCorp Vault — list secrets at a path
vault kv list secret/my-service/

# Check if the project uses .env files
ls -la .env* 2>/dev/null
cat .env.example 2>/dev/null
```

**Critical rule:** Never copy production secrets to your local machine unless absolutely necessary, and never commit them. If the project uses `.env` files, make sure `.env` is in `.gitignore`. Check now:

```bash
grep '\.env' .gitignore || echo "WARNING: .env not in .gitignore!"
```

### Communication Channels

Join these Slack channels (or your team's equivalent) immediately:

| Channel | Purpose |
|---------|---------|
| `#team-<your-team>` | Day-to-day team communication |
| `#incidents` or `#ops` | Active incident coordination |
| `#deploys` or `#releases` | Deployment notifications |
| `#alerts` | Automated alert notifications |
| `#engineering` or `#dev` | Org-wide engineering discussion |
| `#ask-<your-team>` | Inbound questions from other teams |

**Mute strategically.** Join everything, but mute the noisy channels (like `#deploys`) — check them when you need them, not when they notify you.

### End-to-End Verification

Once you have access to everything, verify the full chain works. This is your "can I actually do my job" smoke test:

```bash
# 1. Can you read the code?
git log --oneline -5

# 2. Can you build it?
make build  # or equivalent

# 3. Can you run it?
make run    # hit localhost, verify response

# 4. Can you see the logs?
# Open your observability tool, search for your local test request

# 5. Can you see a deploy?
gh run list --limit 3

# 6. Can you see production metrics?
# Open the main dashboard, verify data is flowing

# 7. Can you access the database (read-only)?
psql -h replica.db.internal -U readonly -d mydb -c "SELECT 1;"

# 8. Can you see the infrastructure?
aws ecs describe-services --cluster prod --services my-service \
  --query 'services[0].{status:status,desired:desiredCount,running:runningCount}'
```

If all 8 pass, you are tooled up. If any fail, you now have a specific list of access gaps to close.

---

## 2. SYSTEM MENTAL MODEL

You have access. You can build and run the code. Now you need to understand what you're looking at. The goal is not to understand every line of code — it's to build a **working mental model** good enough to reason about failures, trace requests, and know where to look when something breaks.

In L3-M91 (Beast Mode — Access & System Mapping), you'll run through this exact process against TicketPulse under a simulated "day one" constraint — pretend you've never seen the codebase before and get operational from scratch. The constraint isn't artificial. It trains the habit of treating *your* codebase the same way, because the engineer who truly understands their own system's blast radius is the one who treats it like an adversary, not like a familiar friend.

### The Core Principle: Metrics and Infra Don't Lie

Code can be deceptive. Multiple generations of engineers wrote it, in different periods of the company's life, under different constraints. Comments rot. READMEs drift. That function named `processOrder` might also send emails, update analytics, and trigger a webhook — because three different engineers extended it over two years.

But infrastructure config says "this is what actually runs." And metrics say "this is what actually happens."

```
Truth hierarchy:
  1. Production metrics     — what IS happening right now
  2. Infrastructure config  — what IS deployed right now
  3. CI/CD pipeline         — what WILL be deployed next
  4. Application code       — what SHOULD happen (in theory)
  5. Documentation          — what someone INTENDED to happen (once upon a time)
```

When the docs and the metrics disagree, the metrics are right. When the README says "we use Redis for caching" but the Terraform shows no Redis instance, trust the Terraform. Start from the top of this hierarchy and work down.

### The 5-Minute Architecture Sketch

Grab a piece of paper (or a whiteboard, or Excalidraw, or the back of a napkin). You're going to draw the system in 5 minutes. Not a perfect diagram — a thinking tool.

**Step 1: Identify the entry points (2 minutes)**

Where does traffic come in?

```
Questions to answer:
- Is there a load balancer? What kind? (ALB, NLB, CloudFront, Nginx)
- Is there an API gateway? (Kong, API Gateway, Envoy)
- Are there multiple entry points? (Web app, mobile API, admin panel, webhook receiver)
- Is there a CDN in front? (CloudFront, Fastly, Cloudflare)
```

Find this information fast:

```bash
# AWS — find load balancers
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[].{Name:LoadBalancerName,DNS:DNSName,Type:Type}' \
  --output table

# AWS — find CloudFront distributions
aws cloudfront list-distributions \
  --query 'DistributionList.Items[].{Id:Id,Domain:DomainName,Origin:Origins.Items[0].DomainName}' \
  --output table

# Kubernetes — find ingress resources
kubectl get ingress --all-namespaces

# Check DNS — where does the domain actually point?
dig api.mycompany.com +short
dig www.mycompany.com +short
```

**Step 2: Identify the compute (1 minute)**

What actually runs the code?

```bash
# AWS ECS
aws ecs list-services --cluster prod --query 'serviceArns[*]' --output table

# AWS Lambda
aws lambda list-functions --query 'Functions[].FunctionName' --output table

# Kubernetes
kubectl get deployments --all-namespaces -o wide

# EC2 instances (if applicable)
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,Name:Tags[?Key==`Name`].Value|[0]}' \
  --output table
```

**Step 3: Identify the data stores (1 minute)**

Where does state live?

```bash
# AWS RDS
aws rds describe-db-instances \
  --query 'DBInstances[].{Id:DBInstanceIdentifier,Engine:Engine,Size:DBInstanceClass}' \
  --output table

# AWS ElastiCache (Redis/Memcached)
aws elasticache describe-cache-clusters \
  --query 'CacheClusters[].{Id:CacheClusterId,Engine:Engine,Type:CacheNodeType}' \
  --output table

# AWS DynamoDB
aws dynamodb list-tables

# AWS S3 buckets (the interesting ones)
aws s3 ls | grep -v 'log\|backup\|trail'

# Kubernetes — persistent volumes
kubectl get pv
```

**Step 4: Identify the async components (1 minute)**

What happens outside the request-response cycle?

```bash
# AWS SQS queues
aws sqs list-queues --query 'QueueUrls[*]' --output table

# AWS SNS topics
aws sns list-topics --query 'Topics[*].TopicArn' --output table

# AWS EventBridge rules
aws events list-rules --query 'Rules[].{Name:Name,State:State,Schedule:ScheduleExpression}' \
  --output table

# Kafka topics (if applicable)
kafka-topics.sh --bootstrap-server kafka:9092 --list

# Kubernetes — CronJobs
kubectl get cronjobs --all-namespaces
```

Now draw it. Boxes for services, cylinders for databases, arrows for data flow. It doesn't have to be pretty. It has to be **yours** — because you built it, you'll remember it.

```
Example sketch (ASCII):

  [CloudFront] --> [ALB] --> [API Service (ECS)]
                                  |         |
                                  v         v
                              [Postgres]  [Redis]
                                  |
                                  v
                             [SQS Queue]
                                  |
                                  v
                          [Worker Service (ECS)]
                                  |
                                  v
                              [S3 Bucket]
                                  |
                                  v
                          [SNS Notification]
```

### Data Flow Tracing

The architecture sketch tells you what exists. Data flow tracing tells you how it works. Pick the most important user action (e.g., "user places an order") and trace it end-to-end.

**Method 1: Follow a request through the logs**

```bash
# Generate a test request with a unique identifier
curl -H "X-Request-Id: trace-$(date +%s)" https://api.staging.mycompany.com/health

# Search for that request ID in the logs
# Datadog
@http.request_id:trace-1712345678

# CloudWatch Logs Insights
fields @timestamp, @message
| filter @message like /trace-1712345678/
| sort @timestamp asc
```

**Method 2: Read the code path (for the primary flow)**

```bash
# Find the entry point — usually the route handler
grep -r "POST.*order" --include="*.ts" --include="*.py" --include="*.go" -l
# or
grep -r "@app.route\|@router\|app.post\|router.post" --include="*.ts" --include="*.py" -l

# Then trace the call chain from there
```

**Method 3: Use distributed tracing (if available)**

If the team uses Datadog APM, Jaeger, Zipkin, or AWS X-Ray, this is the fastest path:

```
Datadog APM: Search for a trace by operation name
  → See the full service map for that request
  → See latency breakdown per service
  → See database queries, cache hits, external calls

AWS X-Ray: Search by trace ID or annotation
  → Service map shows call graph
  → Segments show timing for each hop
```

**What to capture from the trace:**

| Hop | Service | Action | Latency | Notes |
|-----|---------|--------|---------|-------|
| 1 | ALB | Route to API | 1ms | Health check path: `/health` |
| 2 | API Service | Validate + process | 45ms | Calls auth middleware first |
| 3 | Postgres | INSERT order | 12ms | Uses connection pool |
| 4 | Redis | Cache user prefs | 2ms | TTL: 300s |
| 5 | SQS | Enqueue notification | 5ms | Async — fire and forget |
| 6 | Worker | Process notification | — | Separate service, ~30s delay |

### Dependency Mapping

Every system has dependencies. Some are obvious (the database). Some are hidden (a third-party geocoding API called inside a utility function). You need to find them all because **any dependency is a potential failure point.**

**Internal dependencies — find them in the IaC:**

```bash
# Terraform — what does this service connect to?
grep -r "aws_security_group_rule\|ingress\|egress" terraform/ \
  | grep -i "my-service"

# Docker Compose — what does this service depend on?
grep -A 5 "depends_on" docker-compose.yml

# Kubernetes — what environment variables reference other services?
kubectl get deployment my-service -o json \
  | jq '.spec.template.spec.containers[0].env[] | select(.value | test("http|amqp|redis|postgres|mysql|mongo"))'
```

**External dependencies — the ones that can ruin your day:**

```bash
# Search the codebase for outbound HTTP calls
grep -rn "https://\|http://" --include="*.ts" --include="*.py" --include="*.go" \
  | grep -v "localhost\|127.0.0.1\|node_modules\|vendor\|test" \
  | sort -u

# Search for SDK clients (AWS, Stripe, Twilio, etc.)
grep -rn "new.*Client\|create_client\|Client(" --include="*.ts" --include="*.py" \
  | grep -v "node_modules\|vendor\|test"
```

**Build a dependency table:**

| Dependency | Type | Criticality | Failure Mode | Fallback |
|------------|------|-------------|--------------|----------|
| Postgres (RDS) | Internal | Critical | Service down | None — hard dependency |
| Redis (ElastiCache) | Internal | High | Degraded perf, cache misses | Falls back to DB queries |
| Stripe API | External | Critical | Payments fail | Queue + retry |
| SendGrid | External | Medium | Emails delayed | Queue + retry, user not blocked |
| Google Maps API | External | Low | Geocoding fails | Cached results, graceful degradation |
| Auth0 | External | Critical | Login fails | Short JWT TTL, cached sessions |

### The "What Can Kill Us" List

This is the most important artifact you'll produce in your first week. It's a ranked list of things that can take the system down, how you'd know, and what you'd do.

**How to build it:**

1. **Read the last 5 incident postmortems.** What actually broke? That's your empirical data.
2. **Look at the dependency table.** Every "Critical" dependency with no fallback is a kill vector.
3. **Check the alerts.** What's currently alerting? What has alerted in the last 30 days?
4. **Ask the team:** "What keeps you up at night?" Engineers love answering this question.

```bash
# PagerDuty — recent incidents (last 30 days)
curl -s -H "Authorization: Token token=YOUR_TOKEN" \
  "https://api.pagerduty.com/incidents?since=$(date -v-30d +%Y-%m-%d)&until=$(date +%Y-%m-%d)" \
  | jq '.incidents[] | {title: .title, urgency: .urgency, created: .created_at}'

# Datadog — monitors in alert or warn state
curl -s -H "DD-API-KEY: $DD_API_KEY" -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  "https://api.datadoghq.com/api/v1/monitor?monitor_tags=team:my-team" \
  | jq '.[] | select(.overall_state != "OK") | {name: .name, state: .overall_state}'
```

**Example "What Can Kill Us" list:**

| # | Kill Vector | Probability | Impact | Detection | Response Time |
|---|-------------|-------------|--------|-----------|---------------|
| 1 | Database disk full | Medium | Total outage | CloudWatch alarm: disk > 80% | 15 min (auto-scale) |
| 2 | Stripe API outage | Low | Payments stop | Health check + Stripe status page | Manual: switch to queue mode |
| 3 | Memory leak in API service | Medium | Gradual degradation → OOM | ECS memory metric > 85% | Auto: ECS task restart |
| 4 | DDoS / traffic spike | Low | Latency spike → timeouts | ALB 5xx rate > 5% | Auto: WAF rules + scaling |
| 5 | Bad deploy (regression) | High | Partial feature failure | Error rate spike in APM | Manual: rollback deploy |
| 6 | Certificate expiry | Low | Total outage for HTTPS | ACM auto-renewal (but verify) | Manual: re-issue cert |

**The list is never done.** Update it after every incident. Share it in your team wiki. It's the most valuable page your team has.

### Read the IaC

Infrastructure as Code is the most underrated onboarding document. While README files drift and architecture diagrams become fantasies, the IaC describes what's actually deployed right now. If you want to understand the system, read the Terraform (or CDK, or Pulumi, or CloudFormation).

**What to look for in the IaC:**

```bash
# Find the IaC files
find . -name "*.tf" -o -name "*.tfvars" | head -20
# or for CDK:
find . -name "*.ts" -path "*/cdk/*" -o -name "*.ts" -path "*/infra/*" | head -20

# Terraform — what resources exist?
grep -r "^resource " terraform/ | awk '{print $2}' | sort | uniq -c | sort -rn

# Sample output:
#   12 "aws_iam_role"
#    8 "aws_security_group_rule"
#    6 "aws_ecs_task_definition"
#    4 "aws_sqs_queue"
#    3 "aws_rds_cluster"
#    2 "aws_elasticache_cluster"
#    2 "aws_cloudwatch_metric_alarm"
#    1 "aws_cloudfront_distribution"
```

**The IaC tells you things that no other source does:**

| IaC Element | What It Reveals |
|-------------|-----------------|
| `aws_ecs_task_definition` | Exact CPU/memory allocation, container image, env vars |
| `aws_rds_cluster` | Database engine, version, instance size, multi-AZ status |
| `aws_security_group_rule` | What can talk to what — the actual network topology |
| `aws_cloudwatch_metric_alarm` | What the team considers worth alerting on |
| `aws_autoscaling_policy` | Scaling triggers and limits — where the team expects load |
| `aws_sqs_queue` with `redrive_policy` | Dead-letter queue config — what the team expects to fail |
| `aws_waf_web_acl` | Security rules — what attacks they've seen before |

**Read the variables and outputs too:**

```bash
# Terraform variables — what's configurable?
grep -r "^variable " terraform/ | awk '{print $2}' | tr -d '"'

# Terraform outputs — what does this module expose to others?
grep -r "^output " terraform/ | awk '{print $2}' | tr -d '"'
```

**If there is no IaC:** That itself is a finding. It means infrastructure was created manually through the console, which means there's no reproducible way to recreate it. Flag this to your team. It's a risk, and fixing it (Ch 7, Ch 35) is a high-value contribution.

### Putting It All Together: Your Mental Model Document

After completing sections 0-2, you should have enough to write a one-page mental model document. This is for you, not for the team wiki (though sharing it is a great move).

```markdown
## System Mental Model — [Service Name]
### Date: [today]

**What it does:** [One sentence]

**Entry points:**
- Public API: api.company.com → ALB → ECS (API service)
- Admin UI: admin.company.com → CloudFront → S3 (static) → ALB → ECS (admin API)
- Webhooks: api.company.com/webhooks/* → ALB → ECS (API service) → SQS

**Compute:**
- API Service: ECS Fargate, 4 tasks, 1 vCPU / 2GB each
- Worker Service: ECS Fargate, 2 tasks, 0.5 vCPU / 1GB each
- Cron: EventBridge → Lambda (3 functions)

**Data stores:**
- Primary DB: RDS Postgres 14, db.r6g.xlarge, Multi-AZ
- Cache: ElastiCache Redis 7, cache.r6g.large, single node
- Object store: S3 (uploads, exports)
- Queues: SQS (notifications, export-jobs)

**External dependencies:**
- Stripe (payments) — CRITICAL
- SendGrid (email) — MEDIUM
- Auth0 (authentication) — CRITICAL

**What can kill us (top 3):**
1. Database failover (last incident: 2 months ago)
2. Bad deploy with undetected regression
3. Stripe outage (no fallback for payment processing)

**Key dashboards:**
- Health: [URL]
- APM: [URL]
- Logs: [URL]

**On-call runbook:** [URL]
**Recent postmortem:** [URL]
**Phone-a-friend:** @alice (backend), @bob (infra)
```

This document should take you 30 minutes to write after completing the exercises above. It will save you hours the first time something breaks. Print it. Pin it to your monitor. Refer to it at 3 AM. Update it as you learn more.

You are now loaded. Sections 3-7 will cover observability setup, codebase navigation, incident readiness, and tribal knowledge extraction — but with sections 0-2 complete, you can already answer the question "what is this system and how do I operate it?" That's beast mode.

---

## 3. OBSERVABILITY & DASHBOARDS — YOUR EYES AND EARS

> *"You can't fix what you can't see."*

This is the single biggest force multiplier for a new engineer. An engineer with dashboard access who knows what to look at will outperform a 10-year veteran who's flying blind. Section 1 had you bookmark the primary dashboard. Now you're going to build real situational awareness — pre-loading your brain so that when something goes wrong, you already know what "normal" looks like and can spot the anomaly in seconds.

**Why this matters more than reading code:** Code can be deceptive. Comments lie. READMEs go stale. But metrics and infra don't lie. A dashboard showing 200 RPS tells you more truth about a service than a README claiming "handles 1000 RPS." Observable reality beats documented intention, every single time.

### 3.1 Find the Golden Signals Dashboard

The four golden signals — from Google's SRE book — are the foundation of all service monitoring. Every healthy production system should have a dashboard covering these:

| Signal | What It Measures | Why It Matters | Example Threshold |
|--------|-----------------|----------------|-------------------|
| **Latency** | Time to serve a request | Directly impacts user experience | p99 < 500ms |
| **Error Rate** | Percentage of failed requests | Broken functionality, data loss | < 0.1% of total |
| **Traffic** | Requests per second (throughput) | Capacity planning, anomaly detection | Varies by service |
| **Saturation** | How full your resources are | Predicts outages before they happen | CPU < 70%, memory < 80% |

**How to find it:** Ask your team lead: "Where's our golden signals dashboard?" If the answer is "we don't have one" — that's simultaneously a red flag and a golden opportunity. Building one is a high-value first contribution.

**Example Datadog queries for each signal:**

```
# Latency — p50, p95, p99 by endpoint
avg:trace.http.request.duration{service:my-service} by {resource_name}.percentile(50,95,99)

# Error rate — 5xx responses as percentage
(sum:trace.http.request.errors{service:my-service}.as_count() /
 sum:trace.http.request.hits{service:my-service}.as_count()) * 100

# Traffic — requests per second
sum:trace.http.request.hits{service:my-service}.as_rate()

# Saturation — CPU and memory utilization
avg:container.cpu.usage{service:my-service}
avg:container.memory.usage{service:my-service} / avg:container.memory.limit{service:my-service} * 100
```

**Example Grafana/Prometheus queries:**

```promql
# Latency — p99 over 5 minutes
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="my-service"}[5m])) by (le))

# Error rate — 5xx as percentage
sum(rate(http_requests_total{service="my-service", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="my-service"}[5m])) * 100

# Traffic — RPS by endpoint
sum(rate(http_requests_total{service="my-service"}[5m])) by (handler)

# Saturation — CPU utilization
rate(container_cpu_usage_seconds_total{pod=~"my-service.*"}[5m])
/
container_spec_cpu_quota{pod=~"my-service.*"} * 100
```

**If your team doesn't have a golden signals dashboard**, here's your move: create one. Use the queries above as starting points. It takes an hour and immediately earns you credibility while giving yourself (and the team) permanent visibility.

### 3.2 Learn What "Normal" Looks Like

You cannot spot anomalies without knowing the baseline. This is non-negotiable.

**The 15-minute baseline exercise:** During a calm period (not during an incident, not during a deploy), sit in front of the primary dashboard for 15 minutes and capture these numbers:

| Metric | Baseline Value | Time Observed | Notes |
|--------|---------------|---------------|-------|
| Request rate (RPS) | _____ | _____ | e.g., "~350 RPS at 2 PM EST" |
| p50 latency | _____ ms | _____ | |
| p95 latency | _____ ms | _____ | |
| p99 latency | _____ ms | _____ | |
| Error rate | _____% | _____ | |
| CPU utilization | _____% | _____ | |
| Memory utilization | _____% | _____ | |
| Active DB connections | _____ | _____ | |
| Queue depth | _____ | _____ | |
| Cache hit ratio | _____% | _____ | |

**What to look for:**

- **Daily traffic pattern:** Most services have a predictable curve — low traffic overnight, ramp-up in the morning, peak mid-afternoon, taper off in the evening. Learn your curve.
- **Spike timing:** Does traffic spike at the top of the hour? (Cron jobs hitting the API.) Does it spike at 9 AM? (Users logging in.) Does it spike on Mondays? (Weekly batch jobs.)
- **The "normal" error rate:** Zero errors is unusual. Most services have a background error rate of 0.01-0.1%. Know yours so you can tell when it doubles.
- **Latency bands:** p50 tells you the typical experience. p99 tells you the worst 1% — and p99 is where the pain hides.

**Real-world example:** A new engineer joins the team. Two weeks in, she glances at the dashboard during lunch and says, "Hey, our p99 is at 800ms — isn't it usually around 200?" Nobody else noticed because it had been creeping up over three days. She caught a slow query introduced by a migration two deploys ago. That's what baseline knowledge does.

### 3.3 The Hotlinks List

Build a personal quick-access bookmark bar for your operational tools. When something breaks at 2 AM, you don't want to be searching Confluence for the Datadog URL.

**Your Beast Mode Hotlinks Template:**

| Category | Tool | URL Pattern | What to Look For |
|----------|------|-------------|------------------|
| **Service health** | Datadog / Grafana | `app.datadoghq.com/dashboard/xxx` | Golden signals, overall health |
| **Error tracking** | Sentry / Datadog APM | `sentry.io/organizations/xxx/issues/` | New errors, error spikes, regressions |
| **Logs** | Datadog / CloudWatch / Kibana | `app.datadoghq.com/logs?query=service:my-svc` | Filtered to your team's services |
| **Deployments** | GitHub Actions / ArgoCD | `github.com/org/repo/actions` | Recent deploys, success/failure |
| **Database** | RDS Console / Grafana | `console.aws.amazon.com/rds/` | Connection count, query latency, replication lag |
| **Queues** | SQS Console / Kafka UI | `console.aws.amazon.com/sqs/` | Queue depth — the early warning signal |
| **Cost** | AWS Cost Explorer / Datadog Cost | `console.aws.amazon.com/cost-management/` | Unexpected spikes, budget alerts |
| **On-call** | PagerDuty / OpsGenie | `app.pagerduty.com/schedules` | Current on-call, escalation policies |
| **Status page** | Statuspage / internal | `status.company.com` | External dependency status |
| **Runbooks** | Notion / Confluence / GitHub Wiki | varies | Incident response procedures |

```bash
# Quick way to populate your hotlinks — ask git for CI/CD URLs
git remote get-url origin
# → https://github.com/acme/my-service.git
# → Dashboard: https://github.com/acme/my-service/actions

# Find Datadog dashboard links in the codebase (teams often embed them)
grep -ri "datadoghq.com\|grafana.*dashboard\|app.datadoghq" README.md docs/ *.md 2>/dev/null

# Check Terraform for monitoring resources that contain dashboard URLs
grep -r "datadog_dashboard\|grafana_dashboard\|aws_cloudwatch_dashboard" terraform/ 2>/dev/null
```

**Pro tip:** Put these in a browser bookmark folder called "Ops — [Service Name]" and set it to open all bookmarks at once. One click gives you full situational awareness. Some engineers use a browser extension like OneTab or create a custom start page.

**Queue depth deserves special attention.** Queue depth (Kafka consumer lag, SQS `ApproximateNumberOfMessagesVisible`) is the canary in the coal mine. A growing queue means your consumers can't keep up — and that's often the first sign of a cascading failure. If you watch one metric obsessively, make it this one.

```bash
# AWS CLI — check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789/my-queue \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Kafka — check consumer group lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group my-consumer-group
```

### 3.4 Alerts — Who Gets Paged and For What

Before you join the on-call rotation (and you will), you need to understand the alerting topology.

**Questions to answer:**

| Question | Where to Find the Answer |
|----------|-------------------------|
| What conditions trigger alerts? | PagerDuty / OpsGenie / Datadog Monitors |
| What are the thresholds? | Monitor definitions — are they static or dynamic? |
| Who gets paged first? | Escalation policy — primary, secondary, manager |
| How fast does it escalate? | Escalation timeout — 5 min? 15 min? 30 min? |
| Where do alerts fire? | Slack channel? SMS? Phone call? All three? |
| What's the acknowledgment SLA? | How long before unacked alerts escalate? |
| Are there maintenance windows? | Scheduled downtime that suppresses alerts |

```bash
# PagerDuty CLI — list services and escalation policies
pd service list
pd escalation-policy list

# Datadog — list monitors for your service
curl -s "https://api.datadoghq.com/api/v1/monitor?tags=service:my-service" \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  | jq '.[] | {name, type, query, message}'
```

**The alerting layers you should know:**

1. **Infrastructure alerts:** CPU > 80%, memory > 90%, disk > 85%. These are blunt instruments but catch resource exhaustion.
2. **Application alerts:** Error rate > 1%, p99 latency > 2s, health check failures. These are more nuanced and service-specific.
3. **Business alerts:** Payment failures > threshold, signup rate drops, zero orders in 10 minutes. These catch problems that metrics miss.
4. **Synthetic alerts:** Scheduled health checks from external services (Pingdom, Datadog Synthetics) that verify the system works end-to-end from a user's perspective.

**Real-world example:** New engineer gets paged at 3 AM. The alert says "High CPU on my-service." She doesn't know if this means "the service is about to crash" or "this happens every night at 3 AM when the batch job runs." If she'd reviewed the alerting topology earlier, she'd know the batch job triggers this alert regularly and it resolves in 20 minutes. Instead, she spends an hour investigating, wakes up the on-call secondary, and everyone loses sleep. Learn the alerts before you're in the rotation.

### 3.5 The "Metrics Don't Lie" Principle

This is the philosophical backbone of beast mode observability.

**The problem:** Code is a living document written by many hands over many years. Comments get stale. READMEs diverge from reality. Wiki pages describe the system as it was designed, not as it runs today. Institutional knowledge lives in people's heads, and people leave.

**The solution:** Observable reality is the single source of truth.

| What the Docs Say | What the Metrics Show | Who's Right? |
|--------------------|-----------------------|--------------|
| "Service handles 1000 RPS" | Dashboard shows 200 RPS peak | The dashboard |
| "3 instances in the auto-scaling group" | Terraform shows `min_size = 5` | Terraform |
| "Redis cache TTL is 1 hour" | Cache hit ratio is 12% | Something is wrong — investigate |
| "Deploys take 5 minutes" | Last 10 deploys averaged 22 minutes | The deploy logs |
| "99.9% uptime SLA" | Error budget burned 40% in week 1 | The error budget |

**How to apply this:**

1. When someone tells you how the system works, **verify it against the dashboard.** Not because they're lying, but because systems drift.
2. When you read architecture docs, **cross-reference against actual infrastructure.** Terraform state and cloud console are the ground truth.
3. When you're debugging, **start with metrics, not code.** The metrics tell you *where* the problem is. The code tells you *why*.

```bash
# Verify claims against reality — Terraform edition
# "We have 3 instances" — let's check
terraform state list | grep aws_ecs_service
terraform state show aws_ecs_service.my_service | grep desired_count

# "We use t3.medium" — let's check
terraform state show aws_instance.my_server | grep instance_type

# AWS CLI — what's actually running?
aws ecs describe-services --cluster my-cluster --services my-service \
  --query 'services[0].{desired: desiredCount, running: runningCount, pending: pendingCount}'

aws ec2 describe-instances --filters "Name=tag:Service,Values=my-service" \
  --query 'Reservations[].Instances[].{id: InstanceId, type: InstanceType, state: State.Name}'
```

**The mental model:** Treat every piece of documentation and tribal knowledge as a *hypothesis* until confirmed by observable data. This isn't cynicism — it's engineering rigor. And it's exactly the mindset that lets a week-two engineer catch problems that a two-year veteran has gone blind to.

---

## 4. CODEBASE NAVIGATION — READING THE TERRAIN, NOT EVERY LEAF

> *"You don't need to read the whole map. You need to know which direction is north."*

This is NOT "understand the entire codebase" — that's Chapter 28 (Codebase Archeology). This is *navigational intuition*: someone reports a bug in feature X, and within two minutes you're looking at the right file. You don't need to understand every module. You need to know how to find the one that matters right now.

### 4.1 Entrypoint Mapping

Every request enters the system somewhere. These entry points are your anchor points — everything fans out from them.

**The four types of entrypoints:**

| Type | What It Is | How to Find It |
|------|-----------|----------------|
| **HTTP route handlers** | API endpoints, web pages | Route files, controller files, decorator patterns |
| **Event consumers** | Queue processors, webhook handlers | Consumer configs, event handler registrations |
| **Cron jobs** | Scheduled tasks | Crontab, CloudWatch Events, Kubernetes CronJobs |
| **CLI commands** | Developer/admin tools | CLI entrypoint files, management command directories |

**Finding entrypoints in common frameworks:**

```bash
# Express.js — find route definitions
grep -rn "router\.\(get\|post\|put\|delete\|patch\)" src/ --include="*.ts" --include="*.js"
grep -rn "app\.\(get\|post\|put\|delete\|patch\)" src/ --include="*.ts" --include="*.js"

# Django — find URL patterns
grep -rn "path(\|re_path(" */urls.py
# Or find view classes
grep -rn "class.*View\|class.*ViewSet" */views.py

# Spring Boot — find request mappings
grep -rn "@\(GetMapping\|PostMapping\|PutMapping\|DeleteMapping\|RequestMapping\)" \
  --include="*.java" src/

# FastAPI — find route decorators
grep -rn "@app\.\(get\|post\|put\|delete\)\|@router\.\(get\|post\|put\|delete\)" \
  --include="*.py" src/

# Rails — the routes file is the map
cat config/routes.rb
rails routes  # if you can run the app

# Go (net/http or Gin)
grep -rn "HandleFunc\|Handle\|GET\|POST\|PUT\|DELETE" --include="*.go" .
```

**Finding event consumers:**

```bash
# SQS consumers — look for queue URL references or SDK calls
grep -rn "sqs\.\(receive\|ReceiveMessage\|Consumer\)" --include="*.ts" --include="*.py" src/
grep -rn "SQS_QUEUE_URL\|queue_url\|QueueUrl" src/

# Kafka consumers — look for topic subscriptions
grep -rn "subscribe\|consumer\|@KafkaListener\|ConsumerGroup" src/

# Cron jobs — scheduled tasks
cat crontab 2>/dev/null
grep -rn "schedule\|cron\|@Scheduled\|periodic_task" src/
ls -la .github/workflows/ | grep -i cron
grep -rn "schedule:" .github/workflows/
```

**Build a quick entrypoint map:**

```markdown
## Entrypoints — [Service Name]

### HTTP (port 8080)
- POST /api/v1/users      → src/controllers/user.controller.ts → createUser()
- GET  /api/v1/users/:id   → src/controllers/user.controller.ts → getUser()
- POST /api/v1/payments    → src/controllers/payment.controller.ts → processPayment()

### Event Consumers
- SQS: notification-queue  → src/consumers/notification.consumer.ts
- SQS: export-jobs-queue   → src/consumers/export.consumer.ts

### Cron
- Daily 2 AM UTC           → src/jobs/cleanup.job.ts (delete expired sessions)
- Hourly                    → src/jobs/sync.job.ts (sync external data)

### CLI
- npm run migrate           → src/cli/migrate.ts
- npm run seed              → src/cli/seed.ts
```

This map takes 20 minutes to build and saves you hours of grep-ing later. Pin it next to your mental model document from Section 2.

### 4.2 The "Grep Your Way In" Technique

Do NOT try to understand the codebase top-down. Start from an **observable artifact** — an API endpoint, an error message, a log line — and grep backwards into the code.

**The technique:**

1. **Start with something you can see.** An error message in Sentry. A log line in Datadog. An API path from the docs.
2. **Search for that exact string in the codebase.** Error messages are unique strings — they lead straight to the handler.
3. **Follow the call chain.** From the handler, trace the function calls to understand the flow.

```bash
# Technique 1: Start from an error message
# You see "Payment processing failed: insufficient funds" in Sentry
rg "insufficient funds" --type ts
# → src/services/payment.service.ts:142

# Technique 2: Start from an API path
# You know the endpoint is POST /api/v1/orders
rg "/api/v1/orders" --type ts
# → src/routes/order.routes.ts:15
# → src/controllers/order.controller.ts:28

# Technique 3: Start from a log line
# You see "[OrderService] Processing order ORD-12345" in logs
rg "Processing order" --type ts
# → src/services/order.service.ts:67

# Technique 4: Start from a config key
# You see an environment variable PAYMENT_GATEWAY_URL in the config
rg "PAYMENT_GATEWAY_URL" --type ts
# → src/config/index.ts:23
# → src/services/payment.service.ts:8

# Technique 5: Start from a database table name
# You see slow queries on the "orders" table
rg "orders" --type ts -g "*model*" -g "*entity*" -g "*schema*"
# → src/models/order.model.ts
```

**Power moves with ripgrep:**

```bash
# Find where a function is defined (not just called)
rg "function processPayment|processPayment\s*=" --type ts

# Find where a class is instantiated
rg "new PaymentService" --type ts

# Find all files that import a module
rg "from.*payment.service" --type ts

# Find all TODO/FIXME/HACK comments
rg "TODO|FIXME|HACK|XXX" --type ts

# Find all environment variables used in the codebase
rg "process\.env\." --type ts | sort -t: -k2 | uniq

# Contextual search — show 5 lines around the match
rg -C 5 "handlePayment" --type ts
```

**Why this beats reading top-down:** A typical service has 500+ files. Reading them sequentially takes days and most of the knowledge decays before you need it. Grepping from a specific artifact gets you to the relevant code in under 60 seconds, and the context is immediately useful because you're looking at it in response to a real question.

### 4.3 Identify the Architectural Layers

You don't need to love the architecture. You need to know where things live.

**Common patterns and where to find things:**

| Pattern | Where to Find Business Logic | Where to Find Data Access | Where to Find API Definitions |
|---------|-----------------------------|--------------------------|-----------------------------|
| **MVC** | `controllers/`, `services/` | `models/`, `repositories/` | `routes/`, `controllers/` |
| **Hexagonal** | `domain/`, `application/` | `infrastructure/adapters/` | `infrastructure/http/` |
| **Vertical Slices** | `features/payments/`, `features/orders/` | Same directory as feature | Same directory as feature |
| **Big Ball of Mud** | Everywhere and nowhere | Mixed in with everything | Good luck |

```bash
# Quick architecture detection — look at the top-level directory structure
ls -la src/
# If you see: controllers/ models/ services/ routes/     → MVC
# If you see: domain/ application/ infrastructure/        → Hexagonal / Clean Architecture
# If you see: features/ or modules/ with self-contained dirs → Vertical Slices
# If you see: a flat list of 200 files                    → Big Ball of Mud

# Check for a monorepo structure
ls packages/ 2>/dev/null || ls apps/ 2>/dev/null || ls services/ 2>/dev/null

# Look at the dependency injection setup — reveals architecture philosophy
rg "inject\|@Injectable\|@Module\|container\.\(register\|bind\)" src/ --type ts -l

# Check for middleware layers
rg "middleware\|interceptor\|guard\|filter\|pipe" src/ --type ts -l | head -20
```

**What to document for yourself:**

```markdown
## Architecture Notes — [Service Name]

**Pattern:** MVC-ish (controllers → services → repositories)
**Business logic lives in:** src/services/
**Data access lives in:** src/repositories/
**API routes defined in:** src/routes/
**Shared utilities:** src/common/ and src/utils/
**Config loading:** src/config/index.ts (reads from environment)
**Middleware chain:** auth → rate-limit → validate → controller → error-handler
```

### 4.4 Spot the Load-Bearing Code

Every codebase has a handful of files that everything depends on. These are the load-bearing walls — touch them carefully, test them thoroughly, and know them well.

**How to find them:**

```bash
# Most frequently changed files (hot spots) — high churn = high importance
git log --pretty=format: --name-only --since="6 months ago" | \
  sort | uniq -c | sort -rn | head -20

# Most authors per file (many people touch it = shared dependency)
for f in $(git ls-files "*.ts" | head -50); do
  authors=$(git log --format='%ae' -- "$f" | sort -u | wc -l)
  echo "$authors $f"
done | sort -rn | head -20

# Largest files (complexity tends to accumulate in large files)
find src/ -name "*.ts" -exec wc -l {} + | sort -rn | head -20

# Most imported module (everything depends on it)
rg "from ['\"]" --type ts -o | \
  sed "s/.*from ['\"]//; s/['\"]//g" | \
  sort | uniq -c | sort -rn | head -20

# Files changed in the most PRs (high coupling to features)
git log --pretty=format: --name-only --merges --since="3 months ago" | \
  sort | uniq -c | sort -rn | head -20
```

**What load-bearing code looks like:**

- **The base model / entity class** — every other model inherits from it
- **The authentication middleware** — every request passes through it
- **The database connection manager** — everything that reads or writes data depends on it
- **The config loader** — imported by nearly every module
- **The error handler** — determines how every failure is reported
- **The main router / app setup** — the spine of the application

**Real-world example:** An engineer runs the most-changed-files command and discovers that `src/utils/helpers.ts` has been modified 340 times in 6 months by 12 different authors. It's a 2,000-line grab bag of utility functions. Everything imports from it. This is the most dangerous file in the codebase — any change here could break anything. Knowing this on day one means she'll treat changes to this file with extra caution, write extra tests, and maybe advocate for splitting it up.

### 4.5 The Archaeology Layer

Every codebase has layers of sediment — old patterns, deprecated dependencies, abandoned experiments. You need to know the boundary between "actively maintained" and "don't touch unless it breaks."

**How to identify legacy code:**

```bash
# Files not modified in over a year — potential legacy
git log --pretty=format:'%ai' --diff-filter=M -- src/ | \
  sort | head -5
# Better: find files with no recent commits
for f in $(git ls-files src/ | head -100); do
  last_modified=$(git log -1 --format='%ai' -- "$f" 2>/dev/null)
  echo "$last_modified $f"
done | sort | head -20

# Deprecated dependencies — check for known deprecated packages
npm outdated 2>/dev/null | head -20       # Node.js
pip list --outdated 2>/dev/null | head -20  # Python
bundle outdated 2>/dev/null | head -20      # Ruby

# TODO/FIXME archaeology — how old are the TODOs?
rg "TODO|FIXME" --type ts -n | while read -r line; do
  file=$(echo "$line" | cut -d: -f1)
  lineno=$(echo "$line" | cut -d: -f2)
  date=$(git log -1 --format='%as' -L "$lineno,$lineno:$file" 2>/dev/null)
  echo "$date $line"
done | sort | head -20

# Simpler: find old TODOs by blaming the file
rg -l "TODO|FIXME" --type ts | while read -r f; do
  git log -1 --format="%as %H" -- "$f"
done | sort | head -10

# Framework version mismatches — multiple versions of the same concept
rg "require\(|import.*from" --type ts | grep -i "express\|fastify\|koa" | sort -u

# Dead code candidates — exported functions never imported elsewhere
# (This is a rough heuristic)
for func in $(rg "export (function|const|class) (\w+)" --type ts -o -r '$2' src/ | sort -u); do
  count=$(rg "$func" --type ts src/ | wc -l)
  if [ "$count" -le 1 ]; then
    echo "possibly dead: $func"
  fi
done 2>/dev/null | head -20
```

**Signs of legacy code:**

| Indicator | What It Suggests |
|-----------|-----------------|
| Framework version 2 major versions behind | Nobody wants to touch the upgrade |
| `// TODO: temporary fix (2019-03-15)` | "Temporary" means permanent in most codebases |
| Commented-out code blocks | Someone was afraid to delete it |
| Inconsistent patterns in the same directory | Multiple generations of engineers, no style enforcement |
| `_old`, `_backup`, `_deprecated` in filenames | Self-documenting neglect |
| Test files with most tests skipped | The code works "well enough" but nobody trusts it |
| Orphaned config files for tools no longer used | `.babelrc` in a project that migrated to SWC two years ago |

**What to do with this knowledge:**

1. **Draw the boundary.** In your notes, mark which directories/modules are "legacy" vs "active." This prevents you from accidentally adopting old patterns when writing new code.
2. **Don't refactor legacy code on week one.** Understand it, document the boundary, and move on. Refactoring legacy code requires deep context you don't have yet.
3. **Know the migration paths.** Ask your team: "Are there any ongoing migrations I should be aware of?" (e.g., JavaScript to TypeScript, REST to GraphQL, monolith to microservices). This tells you which patterns are going toward and which are going away.

```markdown
## Archaeology Notes — [Service Name]

**Active code (follow these patterns):**
- src/services/ — TypeScript, async/await, clean error handling
- src/controllers/v2/ — new API endpoints with validation middleware

**Legacy code (don't touch unless breaks):**
- src/controllers/v1/ — old API, no input validation, callback-based
- src/legacy/ — original prototype code, still handles ~5% of traffic
- src/utils/helpers.ts — the junk drawer, add to it only as last resort

**In-progress migrations:**
- JavaScript → TypeScript (80% complete, new code must be .ts)
- Express callbacks → async/await (60% complete)
- Monolith → microservices (orders service extracted, payments next)
```

**The archaeology mindset:** Legacy code isn't bad code. It's code that solved real problems for real users and has been running in production — possibly for years. Respect it. Understand it. Know its boundaries. And when you do eventually work on it, approach it like an archaeologist: carefully, with a brush, not a bulldozer.

### Putting It All Together: Your Day-One Navigation Cheat Sheet

After completing sections 3 and 4, you should be able to fill out this cheat sheet:

```markdown
## Navigation Cheat Sheet — [Service Name]
### Date: [today]

**Hotlinks (bookmarked):**
- [ ] Golden signals dashboard: [URL]
- [ ] Error tracker: [URL]
- [ ] Logs (filtered to service): [URL]
- [ ] Deployment pipeline: [URL]
- [ ] On-call schedule: [URL]

**Baselines captured:**
- Request rate: _____ RPS (peak at _____)
- p99 latency: _____ ms
- Error rate: _____% 
- Queue depth: _____ (normal), _____ (concerning)

**Alerting:**
- Primary on-call: _____ → escalates to: _____
- Key alerts I should know about: _____

**Entrypoints mapped:**
- [ ] HTTP routes documented
- [ ] Event consumers identified
- [ ] Cron jobs listed

**Architecture:**
- Pattern: _____
- Business logic in: _____
- Data access in: _____

**Load-bearing files (handle with care):**
1. _____
2. _____
3. _____

**Legacy boundary:**
- Active patterns to follow: _____
- Old patterns to avoid: _____
- Migrations in progress: _____
```

With sections 0-4 complete, you can now answer two critical questions: "What is this system?" (sections 0-2) and "How do I see what it's doing and find my way around?" (sections 3-4). You have the map, the compass, and night vision. Sections 5-7 will cover incident readiness, tribal knowledge extraction, and the final beast mode checklist — the skills that turn operational awareness into operational excellence.

---

## 5. INCIDENT READINESS — THE FIRE DRILL YOU RUN BEFORE THE FIRE

The whole chapter builds to this moment: the pager goes off during your first week. Your heart rate spikes. Slack is lighting up. Someone typed "SEV-1" and suddenly the room feels different.

You have two options. You can freeze, scroll aimlessly through dashboards you barely understand, and silently pray someone else fixes it. Or you can execute a mental script — a rehearsed, deliberate sequence of actions that lets you *be useful* even when you don't yet understand the system deeply enough to fix the problem yourself.

This section gives you that script. You might not be the one who writes the fix. But you won't make things worse, and you'll contribute in ways that experienced engineers genuinely appreciate.

L3-M91b (Beast Mode — Incident Dry Run) is designed to be run immediately after you complete the access and system-mapping work from L3-M91. It throws a cascading failure at TicketPulse — starting with a Kafka consumer falling behind, triggering a payment timeout, triggering a circuit breaker opening, triggering cascading 503s — while deliberately degrading some of your usual debugging tools. The exercise is uncomfortable by design. That discomfort is the point: your real first incident will also be uncomfortable, and having already felt that specific pressure means you'll react with method instead of panic. L3-M91a (Observability Wiring) runs before the dry run to ensure your dashboards and log queries are all working before the pressure starts.

### 5.1 The First 5 Minutes Script

When the pager fires and you're new, you need a literal step-by-step. Not "use good judgment" — a checklist. Good judgment comes later. Right now, you need a sequence.

**Step 1: Check the alert details.**
Read the actual alert. What service? What metric? What threshold was crossed? When did it fire? Is this a warning or a critical? Don't skip this — half of all incident confusion starts with someone reacting to an alert they didn't actually read.

**Step 2: Open the primary dashboard.**
This is why you bookmarked it on day one (section 3). Open it. Look at the golden signals: latency, traffic, errors, saturation. Are they normal or abnormal?

**Step 3: Check recent deployments.**
Open the CI/CD pipeline or deployment history. Was anything deployed in the last 30 minutes? The last hour? If yes, that's your leading hypothesis.

**Step 4: Check the error rate.**
Is the error rate elevated? Is it a new error type or a spike in an existing one? Open the error tracker (Sentry, Bugsnag, Datadog Error Tracking) and sort by "first seen" or "last seen."

**Step 5: Open the logs.**
Run your bookmarked error log query (from section 3). Filter to the last 15 minutes. Scan for patterns — stack traces, timeout messages, connection refused errors, OOM kills.

**Step 6: Look for the obvious.**
You're looking for one of four shapes:
- **Spike** — a sudden jump in errors, latency, or traffic
- **Flatline** — a metric that dropped to zero (usually means something stopped)
- **Error storm** — a wall of identical error messages
- **Gradual climb** — a slow increase that just crossed a threshold (memory leak, queue backup)

**The cardinal rule: Don't touch anything yet. Observe before you act.**

You are gathering information, not making changes. The worst thing a new engineer can do during an incident is make a change without understanding the current state. Observe, note, communicate. The decision tree below gives you a framework:

```
PAGED → Open primary dashboard
        ├── Metrics normal? → Check if alert is stale/resolved
        └── Metrics abnormal?
            ├── Check recent deployments
            │   └── Deploy in last 30 min? → Candidate for rollback
            ├── Check error logs
            │   └── New error type? → Likely code change
            ├── Check traffic
            │   └── Spike? → Likely load issue
            └── Check dependencies
                └── External service down? → Likely upstream
```

**Print this decision tree.** Stick it next to your monitor. When the pager fires and your brain is flooded with adrenaline, you won't remember the clever mental model you read in a book. You'll remember the piece of paper taped to your desk.

Here's the checklist version you can copy into your notes:

```markdown
## First 5 Minutes — Incident Response Checklist

- [ ] Read alert: service=_____ metric=_____ threshold=_____ fired_at=_____
- [ ] Open primary dashboard — golden signals normal? Y / N
- [ ] Check deployment history — deploy in last 30 min? Y / N
  - If yes: SHA=_____ deployed_by=_____ deployed_at=_____
- [ ] Check error tracker — new error type? Y / N
  - If yes: error=_____ first_seen=_____ count=_____
- [ ] Open logs — pattern observed: (spike / flatline / error storm / gradual climb / none)
- [ ] Check dependency status pages — external service down? Y / N
- [ ] Initial assessment: _____________________________________
- [ ] Communicated to incident channel: Y / N
```

### 5.2 The "What Changed?" Reflex

Here's the single most important mental habit for incident response:

> **Ask "what changed?" before you ask "what's broken?"**

This isn't just a good heuristic — it's backed by data. Roughly **90% of production incidents are caused by a change**. A deploy. A config update. A traffic spike. A dependency upgrade. A feature flag toggle. A database migration. A certificate expiration.

Systems that were working yesterday and are broken today didn't spontaneously combust. Something changed. Your job is to find what.

**The Change Checklist:**

| Change Type | Where to Check | Typical Signal |
|---|---|---|
| **Code deploy** | CI/CD pipeline, deployment history | Errors correlate with deploy timestamp |
| **Config change** | Config management (Consul, Parameter Store, env vars) | Behavior change without new code |
| **Traffic spike** | Load balancer metrics, CDN analytics | Latency increase, resource saturation |
| **Dependency update** | Package lockfiles, Docker image history | New error types from third-party code |
| **Feature flag** | LaunchDarkly, Split, Unleash audit log | Errors only for affected user segment |
| **Infrastructure change** | Terraform apply history, CloudFormation events | Connectivity issues, permission errors |
| **Database migration** | Migration logs, schema change history | Query errors, timeout increases |
| **Certificate/secret rotation** | Secret manager audit log, cert expiry dates | TLS errors, auth failures |

Train yourself to run through this checklist reflexively. When someone says "the API is returning 500s," your first question should not be "what endpoint?" — it should be "what deployed in the last hour?"

### 5.3 Rollback Muscle Memory

Here's a scenario: it's 2 AM, the site is down, the deploy from 45 minutes ago is the obvious culprit, and you're the only one awake. You know you need to rollback. Do you know *how*?

**You need to know how to rollback before you need to rollback.**

This means:
- **Know the command.** Not "I'll figure it out" — the actual command, typed out, saved in your notes.
- **Know the pipeline.** Does rollback go through CI/CD? Is there an approval gate? Can you skip it in emergencies?
- **Know the blast radius.** Does rolling back also roll back database migrations? (Hint: it usually doesn't, and that's a problem.)
- **Practice it.** Roll back in staging. Do it once when nothing is on fire, so you're not learning the UI during an incident.

**Rollback Cheat Sheet:**

| Deployment Method | Rollback Command | Time to Effect |
|---|---|---|
| Git + CI/CD | `git revert <sha> && git push` | ~5 min (pipeline) |
| Feature flags | Kill switch in LaunchDarkly/Split | ~30 sec |
| Container (ECS/K8s) | Redeploy previous image tag | ~2 min |
| Serverless (Lambda) | Point alias to previous version | ~30 sec |
| Kubernetes (kubectl) | `kubectl rollout undo deployment/<name>` | ~1 min |
| ArgoCD | Sync to previous commit in Git | ~2 min |

**Important nuances:**
- **Database migrations are usually not reversible via rollback.** If the deploy included a migration that dropped a column, reverting the code won't bring the column back. This is why good teams separate schema changes from code deploys.
- **Feature flags are the fastest rollback.** If the new behavior is behind a flag, you can kill it in seconds without touching the deployment pipeline. This is why feature flags exist.
- **Know who can approve an emergency rollback.** Some organizations require approval even for rollbacks. Know the escalation path *before* the incident.

```bash
# Save these in your personal runbook — fill in for your specific environment

# Git revert (CI/CD rollback)
git log --oneline -10                    # find the bad commit
git revert <sha> --no-edit               # create revert commit
git push origin main                     # trigger pipeline

# Kubernetes rollback
kubectl rollout history deployment/my-service  # see revision history
kubectl rollout undo deployment/my-service     # rollback to previous

# AWS ECS — force new deployment with previous task definition
aws ecs update-service \
  --cluster my-cluster \
  --service my-service \
  --task-definition my-service:PREVIOUS_REVISION \
  --force-new-deployment

# AWS Lambda — point alias to previous version
aws lambda update-alias \
  --function-name my-function \
  --name live \
  --function-version PREVIOUS_VERSION

# Feature flag kill switch (LaunchDarkly CLI)
ldcli flags --flag my-new-feature --env production --off
```

### 5.4 Communication During Incidents

When you're new and an incident is happening, your instinct might be to stay quiet — don't bother the experts, don't ask dumb questions, don't get in the way. This instinct is wrong.

**Your job during an incident isn't to be the hero. It's to be useful.**

Here's what "useful" looks like for a new engineer:

**1. Update the incident channel with what you observe.**
Don't diagnose — describe. "Error rate on the orders-api dashboard jumped from 0.1% to 12% starting at 14:32 UTC" is far more useful than silence.

**2. Ask clarifying questions.**
"Should I check if the payment service is also affected?" is not a dumb question — it's initiative.

**3. Run commands others request.**
The senior engineer is heads-down in code and asks "can someone check the ECS task count?" You can do that. You're unblocking them.

**4. Take timeline notes.**
This is the single highest-value thing a new engineer can do during an incident. Keep a running timeline:

```markdown
## Incident Timeline — [Date]

| Time (UTC) | Event | Source |
|---|---|---|
| 14:30 | Alert fired: orders-api error rate > 5% | PagerDuty |
| 14:32 | Confirmed: error rate at 12% on dashboard | Datadog |
| 14:33 | Last deploy: SHA abc1234 by @jane at 14:15 | GitHub Actions |
| 14:35 | @jane confirms deploy included payment retry logic | Slack |
| 14:38 | Decision: rollback deploy | Incident commander |
| 14:40 | Rollback initiated: revert commit pushed | @jane |
| 14:45 | Pipeline complete, new deployment rolling out | GitHub Actions |
| 14:48 | Error rate dropping: 12% → 3% | Datadog |
| 14:52 | Error rate back to baseline: 0.1% | Datadog |
| 14:55 | Incident resolved, monitoring for 15 min | Team |
```

The engineer who keeps a clean timeline during an incident is worth their weight in gold. Every postmortem starts with "what happened and when?" — and if you wrote it down in real time, you just saved the team hours of reconstructing events from log timestamps.

**Communication Templates:**

When you first join the incident channel:
```
Joining incident. I'm [name], [role]. Reading alert details and checking dashboards now.
I'll keep timeline notes unless someone else is already doing that.
```

When you observe something:
```
Observation: [metric/log/behavior] shows [what you see] starting at [time].
Dashboard link: [URL]
```

When you're unsure:
```
Question: Should we also check [thing]? I can look into it if helpful.
```

When you've completed a task someone requested:
```
Done: [what you checked]. Result: [what you found].
[paste relevant output or screenshot]
```

### 5.5 The Shadow On-Call

Before you're added to the on-call rotation, you should shadow a shift. This is non-negotiable if your team supports it. Here's how:

**What shadow on-call means:**
- You're *not* the primary on-call — someone experienced is
- You receive the same alerts (add yourself to the notification channel)
- You follow the same process — check dashboards, read alerts, diagnose
- You tell the primary what you would do *before* they act
- You watch what they actually do and note the differences

**What to observe during your shadow shift:**

1. **What does the on-call engineer check first?** Not what the runbook says they should check — what they *actually* check. There's usually a difference.
2. **Which dashboards do they open?** In what order? Do they have a personal bookmark bar that's different from the team's official list?
3. **What's their decision tree?** When they see an alert, how do they decide whether to act, escalate, or snooze?
4. **What do they ignore?** Experienced on-call engineers have learned which alerts are noisy and which are real. This knowledge is pure gold and is almost never documented.
5. **What do they mutter under their breath?** Seriously. When the senior engineer looks at a dashboard and says "oh, it's *that* thing again," ask what *that thing* is. That's tribal knowledge leaking out.

**After your shadow shift, write down:**
- The 3 most common alerts and their usual resolution
- Any "known noisy" alerts the team ignores
- The actual (not documented) escalation path
- Tools or commands the on-call engineer used that you didn't know about
- Gaps between the runbook and reality

### 5.6 Build Your Personal Runbook

After your shadow shift and your first real incident, you have raw experience. Capture it before it fades.

**Your personal runbook is not the team runbook.** The team runbook says "check the dashboard." Your personal runbook says "open Datadog, click on the orders-api dashboard (bookmarked in Chrome folder 'On-Call'), look at the top-left graph for error rate, compare to the number in the top-right which is the p99 latency. If error rate > 5% AND p99 > 2000ms, it's a real incident, not a blip."

Your personal runbook captures *your* workflow with *your* bookmarks and *your* level of context.

**Personal runbook template:**

```markdown
## My On-Call Runbook — [Service Name]
### Last updated: [date]

**When paged:**
1. Open: [specific dashboard URL]
2. Check: [specific metric, specific location on dashboard]
3. Normal range: [what I expect to see]
4. If abnormal: [my next 3 steps]

**Common alerts I've seen:**
1. [Alert name]: Usually caused by [X]. Fix: [Y]. Time to resolve: ~[Z] min.
2. [Alert name]: Usually a false positive when [condition]. Snooze if [check].
3. [Alert name]: Escalate immediately to [person/team]. Don't try to fix alone.

**Rollback steps for this service:**
1. [Step 1 with exact command]
2. [Step 2]
3. [Step 3]
4. Verify: [how to confirm rollback worked]

**Contacts:**
- Primary escalation: [name] ([contact])
- Database issues: [name] ([contact])
- Infrastructure issues: [name] ([contact])
- Third-party service issues: [vendor support link]

**Things I learned the hard way:**
- [Lesson 1]
- [Lesson 2]
- [Lesson 3]
```

This document compounds over time. After 3 months of on-call, your personal runbook becomes one of the most valuable documents on the team — and you should eventually merge the good parts back into the team runbook.

---

## 6. TEAM & TRIBAL KNOWLEDGE — THE STUFF THAT ISN'T WRITTEN DOWN

Every system has an oral history. Architecture decisions that never made it into an ADR. The unwritten rule that you don't deploy on Fridays. The reason the `UserService` has two implementations and nobody deletes the old one. The engineer who built the authentication system from scratch, left two years ago, and took all the context with them.

L3-M91c (Beast Mode — Tribal Knowledge) is built specifically around this problem. You'll run the three conversations from section 6.1 against simulated TicketPulse "team members" (provided prompts and personas), surface the undocumented decisions baked into the system, and write them into a newcomer FAQ. The finished artifact from that module is something you'll reuse verbatim when you join any new team.

This knowledge exists in the heads of your teammates, in the chat history of old Slack threads, in the commit messages of three-year-old PRs. It's the difference between the system as documented and the system as it actually is. And if you don't deliberately extract it, you'll discover it the hard way — usually during an incident.

### 6.1 The Three Conversations

In your first two weeks, you need to have three specific conversations with three specific people. Not casual "hey, how's it going" chats — deliberate, prepared conversations with specific questions.

**Conversation 1: The Tech Lead**
*Purpose: Strategic view — where are we, where are we going*

Ask these questions:

```markdown
## Tech Lead Conversation Template

1. "Can you draw the system architecture on a whiteboard in 5 minutes?"
   → Forces the simplified mental model. What they include and exclude tells you what matters.

2. "What are we building in the next quarter?"
   → Tells you where to focus your learning. No point going deep on a component
     that's being replaced.

3. "What's the biggest technical risk right now?"
   → Tells you what keeps the tech lead up at night. Might be your chance to
     contribute early.

4. "If you had a week with no meetings, what would you fix?"
   → Reveals the tech debt they're aware of but can't prioritize.

5. "What should I definitely NOT do without checking with someone first?"
   → Reveals the landmines. Every codebase has them.
```

**Conversation 2: The Longest-Tenured Engineer**
*Purpose: Historical truth — the skeletons, the scars, the stories*

```markdown
## Longest-Tenured Engineer Conversation Template

1. "What's the oldest code in the system, and why hasn't it been rewritten?"
   → Reveals the thing that's too scary, too critical, or too poorly understood
     to touch.

2. "What breaks most often?"
   → The answer is almost never what you'd guess from reading the code.

3. "Is there a component everyone's afraid to modify?"
   → This is the "haunted graveyard" — the code surrounded by warning comments
     and anxiety. You need to know where it is.

4. "What's a decision you'd make differently if you were starting over?"
   → Reveals architectural regret — useful for understanding why things are the
     way they are.

5. "Who should I talk to about [specific component]?"
   → Maps the informal knowledge graph. Not the org chart — the actual
     "who knows what" network.
```

**Conversation 3: The On-Call Engineer**
*Purpose: Operational truth — what actually hurts*

```markdown
## On-Call Engineer Conversation Template

1. "What pages most often?"
   → The top 3 alerts by frequency tell you more about system health than any
     dashboard.

2. "What's the usual fix for the most common page?"
   → If the answer is "restart the service," that's a huge signal about
     underlying issues.

3. "What's the scariest alert — the one that makes your stomach drop?"
   → This is the "if this fires, something is really wrong" alert. You need to
     know what it is and what it means.

4. "What's the most annoying false positive?"
   → Tells you what to ignore and what the team has been too busy to fix.

5. "What's missing from the runbook?"
   → Every on-call engineer knows what the runbook doesn't cover. This question
     surfaces it.
```

**Why these three and not others?** Because they give you three orthogonal views of the same system:
- The tech lead sees the **intended** architecture
- The long-tenured engineer sees the **actual** architecture
- The on-call engineer sees the **failing** architecture

The gap between these three views is where the real system lives.

### 6.2 Meeting Archaeology

Before you schedule those three conversations, do your homework. Read the last month of:

**Team meeting notes:**
- What topics keep recurring? That's what the team actually cares about (or is stuck on).
- What was decided? What's still open? Don't re-ask questions that were settled last week.

**Retrospective action items:**
- What did the team commit to improving? Did they follow through?
- Unresolved retro items tell you where the team's processes are weakest.

**Incident postmortems:**
- What broke, why, and what was the remediation?
- Postmortems are the most honest documents in an engineering organization. Teams don't sugarcoat them (usually).
- Pay attention to the "action items" section — the ones marked "done" show you what the team prioritizes. The ones still "open" from three months ago show you what they don't.

**PR review comments:**
- What patterns do reviewers flag? What do they approve without comment?
- This tells you the team's actual coding standards, not the ones in the style guide.

```markdown
## Meeting Archaeology Checklist

- [ ] Read last 4 weekly team meeting notes
  - Recurring topics: _____
  - Recent decisions: _____
  - Open questions: _____

- [ ] Read last 3 retrospective notes
  - Top complaints: _____
  - Action items completed: _____
  - Action items still open: _____

- [ ] Read last 3 incident postmortems
  - Common failure modes: _____
  - Remediation patterns: _____
  - Outstanding action items: _____

- [ ] Skim last 10 merged PRs
  - Common review feedback: _____
  - Patterns that get approved quickly: _____
  - Patterns that get pushback: _____
```

This takes about 2-3 hours and is one of the highest-leverage onboarding activities you can do. You'll walk into your 1:1s with context that most new hires don't have for months.

### 6.3 The Team's "Known Unknowns"

Every team has a list of things they know are problems but haven't fixed. These are not secrets — ask about them and people will tell you freely. They just don't volunteer the information because they've normalized it.

**Common categories of known unknowns:**

| Category | Example | Why It Matters to You |
|---|---|---|
| **Tech debt** | "The billing service still uses the old ORM and we keep meaning to migrate" | Don't build new features on the old pattern |
| **Flaky tests** | "The integration test suite fails ~10% of the time, just re-run it" | Don't spend hours debugging a known flake |
| **Mystery service** | "Nobody really understands what the reconciler does anymore" | Don't touch it without finding the last person who worked on it |
| **Scaling cliff** | "If we hit 10K concurrent users, the WebSocket server will fall over" | Know the limits before you hit them |
| **Manual processes** | "Every month someone has to manually run the report generation script" | Automation opportunity — high-impact early contribution |
| **Documentation rot** | "The wiki says we use Redis but we switched to DynamoDB last year" | Don't trust the docs without verifying |

**How to surface known unknowns:**

Ask these questions in casual conversation, not in a formal meeting:
- "What's the thing you wish you had time to fix?"
- "If you could mass-delete one service, which would it be?"
- "What's the 'everybody knows' thing that a new person wouldn't know?"
- "What workaround do you use so often you've forgotten it's a workaround?"

**Why this matters for you specifically:**

Known unknowns are landmines *and* opportunities:
- **Landmine:** You accidentally build on the broken pattern because nobody warned you
- **Opportunity:** Fixing a known unknown is one of the highest-impact things a new engineer can do, because the team has been staring at it so long they've stopped seeing it

### 6.4 Document What You Learn

You have a superpower that expires quickly: **fresh eyes.**

Everything that's confusing to you right now is something that was confusing to the person before you, and will be confusing to the person after you. But the current team can't see it anymore — they've habituated to the complexity, the inconsistency, the missing documentation.

**Your job is to write it down before you habituate too.**

Here's what to document:

**1. Setup instructions that don't work.**
If the README says "run `docker-compose up`" and you had to do 4 extra things to make it actually work — update the README. This is the single most valuable documentation contribution a new engineer can make.

**2. Architectural decisions that aren't recorded.**
When the tech lead explains *why* the system is designed a certain way, write an ADR (Architecture Decision Record). Even a simple one:

```markdown
# ADR-023: Why we use SQS instead of direct HTTP calls between services

## Status: Accepted (retroactive documentation)
## Date: [today — documenting existing decision]
## Context
The orders service needs to notify the shipping service when an order is placed.
Direct HTTP calls created coupling and cascading failures during shipping service
deployments.

## Decision
Use SQS as a buffer between orders and shipping. Orders publishes an event,
shipping consumes it asynchronously.

## Consequences
- Shipping can be deployed independently without affecting orders
- Events can be replayed if shipping fails
- Adds ~2 second latency to order→shipment flow
- Requires Dead Letter Queue monitoring
```

**3. Tribal knowledge that should be team knowledge.**
When someone tells you "don't deploy on Fridays" or "always check the cache TTL before changing the product catalog" — that's tribal knowledge. Put it in the wiki. Make it searchable.

**4. The "newcomer FAQ."**
Keep a running document of questions you had and answers you found. After a month, publish it. This becomes the single most-used onboarding document for the next new hire.

```markdown
## Newcomer FAQ — [Team Name]
### Started collecting: [date]

**Q: How do I run the test suite locally?**
A: `make test-local` — but you need to start the Docker dependencies first with
`make deps-up`. The README doesn't mention this. (I've submitted a PR to fix it.)

**Q: Why are there two user tables in the database?**
A: The old one (`users`) is from the monolith era. The new one (`accounts`) is
used by the auth service. We're migrating but both are still active. New code
should use `accounts`.

**Q: What's the deal with the `legacy-gateway` service?**
A: It's a reverse proxy that translates old API formats to new ones. About 15%
of traffic still comes through it. It's owned by the platform team, not us, but
our alerts fire when it's slow.

**Q: Why does the CI pipeline take 20 minutes?**
A: The integration tests spin up real AWS resources via LocalStack. There's a
ticket to parallelize them (JIRA-4521) but it hasn't been prioritized.
```

**The ROI of documentation:**

| Action | Time Cost | Impact |
|---|---|---|
| Fix broken README | 30 min | Saves every future new hire 2+ hours |
| Write a retroactive ADR | 20 min | Prevents repeated architecture debates |
| Document a tribal knowledge item | 10 min | Eliminates one "gotcha" permanently |
| Publish newcomer FAQ | Ongoing | Becomes the team's most-referenced doc |

You'll notice a pattern: documentation has *compounding* returns. The 30 minutes you spend fixing the README saves 2 hours for every person who joins after you. Over a year, that's dozens of hours. Over the life of the team, it's weeks.

**The fresh-eyes window is about 3 months.** After that, you'll have habituated to the quirks and stopped noticing them. Document aggressively in your first 90 days. It's the highest-leverage onboarding contribution you can make — and it signals to your team that you're not just ramping up, you're making the ramp easier for everyone who follows.

---

With sections 5 and 6 complete, you now have the full operational toolkit: you can respond to incidents with a script instead of panic (section 5), and you can extract the unwritten knowledge that makes the difference between surviving on a team and thriving on it (section 6). Section 7 will bring it all together with the Beast Mode Checklist — a single-page summary you can print out and execute on day one of any new role.

---

## 7. THE BEAST MODE CHECKLIST

Everything in sections 1 through 6, distilled into a single checklist. Print this out. Tape it to your monitor. Bookmark it on your phone. This is the one page you execute against in your first week at any new role. You don't need to go in order — some items depend on access that takes days to arrive, others you can knock out in your first hour. The point is to have *nothing* slip through the cracks.

### Access & Toolchain

- [ ] Repo cloned, builds locally, tests pass
- [ ] Cloud console access verified (logged in, can see resources)
- [ ] Observability tool access confirmed (ran at least one query)
- [ ] CI/CD pipeline understood (found a recent deployment, read its logs)
- [ ] Secrets management system identified (know where secrets live, how to request new ones)
- [ ] Communication channels joined (team channel, incident channel, deploy notifications)
- [ ] Pushed a trivial change through the full pipeline to production

### System Mental Model

- [ ] 5-minute architecture sketch drawn (boxes, arrows, data flow)
- [ ] Critical user path traced end-to-end (request through every service it touches)
- [ ] Dependencies mapped — external (third-party APIs, managed services) and internal (other team services)
- [ ] "What can kill us" list identified (single points of failure, known fragile areas)
- [ ] IaC files read and cross-referenced with actual running infrastructure
- [ ] Mental model document written and shared with team for validation

### Observability & Dashboards

- [ ] Golden signals dashboard found and bookmarked
- [ ] Baseline metrics noted (normal request rate, p99 latency, error rate, saturation)
- [ ] Hotlinks page created and bookmarked (dashboards, logs, traces, runbooks — one click away)
- [ ] Alerting rules reviewed (know what fires alerts and at what thresholds)
- [ ] At least one log query that works saved (can pull logs for the critical path)
- [ ] Know who gets paged, when, and the escalation path

### Codebase Navigation

- [ ] Entrypoints mapped (HTTP routes, message consumers, cron jobs, event handlers)
- [ ] Grep-your-way-in technique practiced (can trace from user-facing string to handler code)
- [ ] Architectural layers identified (API layer, business logic, data access, infrastructure)
- [ ] Load-bearing files identified via git history (files with most churn, most authors)
- [ ] Legacy and archaeology boundaries noted (know where old code ends and new code begins)

### Incident Readiness

- [ ] First 5 minutes script written or memorized (the exact steps you take when an alert fires)
- [ ] Rollback procedure practiced on each deploy method (know how to revert in under 2 minutes)
- [ ] Communication templates saved (incident channel update format, stakeholder notification)
- [ ] Shadow on-call shift completed (sat with the on-call engineer through at least one rotation)
- [ ] Personal runbook started (your own notes on what to check, in what order, for what symptoms)
- [ ] "What changed?" checklist known (recent deploys, config changes, dependency updates, traffic shifts)

### Team & Tribal Knowledge

- [ ] Three key conversations completed (tech lead for architecture, veteran for history, on-call for war stories)
- [ ] Meeting archaeology done (read last 3 months of retros, postmortems, and planning docs)
- [ ] Known unknowns list collected (things the team knows they don't understand well)
- [ ] At least one documentation gap fixed (README, runbook, or onboarding doc improved)
- [ ] Phone-a-friend contacts identified (know who to call for database issues, infrastructure, security, frontend)

---

Not everything on this checklist needs to happen sequentially, and not everything will be possible on day one. Some items — like shadowing on-call — might take a week or two to schedule. Others — like cloning the repo and running the build — should happen in your first hour. The checklist is a *compass*, not a *railroad track*. Use it to make sure you're covering all six domains, not to stress about the order. By the end of your second week, every box should be checked. If it's not, you know exactly what's left.

---

## CLOSING: IT'S YOUR FIRST WEEK AND THERE'S AN OUTAGE

It's Thursday afternoon. Day four at the new job.

You're sitting at your desk — well, your kitchen table, or that corner of the open office you've claimed with a monitor and a coffee mug. Your Beast Mode checklist is taped to the wall next to your screen. Most of the boxes are checked. Not all of them. You haven't shadowed on-call yet (that's scheduled for next Tuesday), and you're still waiting on production database read access. But you've done the work. You have your hotlinks page bookmarked. You have your architecture sketch pinned. You know the golden signals and what "normal" looks like.

You're in the middle of reading through the order service's test suite when a notification pops up in Slack.

```
#incidents
🔴 Alert: order-service p99 latency > 5s (threshold: 2s)
Triggered at 2:47 PM
```

Your stomach drops. Four days in. You barely know anyone's name. Surely this is someone else's problem.

But you open the incident channel anyway. You see two messages:

```
@channel Latency alert firing on order-service. Looking into it.
```

That was from the bot. No human has responded yet. It's 2:48 PM on a Thursday and people are in meetings, or deep in focus mode, or simply haven't seen it yet.

You remember section 5. *The first five minutes matter more than the next five hours.* You remember the script you wrote for yourself on day two.

**Minute 0-1: Look at the dashboard.**

You click your hotlinks page — the one you built on Tuesday. Three clicks and you're on the golden signals dashboard. You see it immediately:

- **Request rate:** Normal. No traffic spike.
- **Error rate:** Climbing. Was 0.2%, now at 4.7% and rising.
- **Latency (p99):** 8.2 seconds. Your baseline notes say normal is 400ms.
- **Saturation:** CPU normal. Memory normal. *Database connections: 98% utilized.*

That last number grabs you. Database connection pool is nearly exhausted.

**Minute 1-2: What changed?**

You pull up the "what changed?" checklist you wrote on day three. Deployments first. You open the deploy tracker — it's a Slack channel that the CI bot posts to, you bookmarked it on Monday.

```
#deploys
✅ order-service v2.14.0 deployed to production
   Deployed by: @marcus | Pipeline: #4521
   Time: 2:38 PM
```

Nine minutes before the alert. A deploy of the exact service that's alerting.

**Minute 2-3: Check the logs.**

You open the log query you saved — the one from section 3 that filters for the order service's error logs. You adjust the time range to the last 15 minutes and run it.

```
2:39:14 ERROR [order-service] Failed to acquire database connection:
  pool exhausted (active: 50/50, waiting: 312)
  at ConnectionPool.acquire (db/pool.js:142)
  at OrderRepository.findById (repositories/order.js:28)

2:39:14 ERROR [order-service] Failed to acquire database connection:
  pool exhausted (active: 50/50, waiting: 318)

2:39:15 ERROR [order-service] Failed to acquire database connection:
  pool exhausted (active: 50/50, waiting: 327)
```

The same error, repeating hundreds of times. Database connection pool exhaustion. Started at 2:39, one minute after the deploy. The connection pool max is 50, and the waiting queue is growing fast.

**Minute 3-4: Correlate and communicate.**

You have enough. You switch to the incident channel and type:

```
I'm seeing order-service p99 at 8.2s (normal baseline is 400ms per
my onboarding notes). Purchase success rate dropping — error rate at
4.7% and climbing. Saturation dashboard shows database connection pool
at 98%.

Timeline:
- 2:38 PM: order-service v2.14.0 deployed by @marcus
- 2:39 PM: First database connection pool exhaustion errors in logs
- 2:47 PM: Latency alert fired

Error logs show pool exhausted (active: 50/50) with 300+ requests
queued. This started 1 minute after the v2.14.0 deploy.

Checking if rollback is appropriate.
```

You hit send. Fifteen seconds later:

```
@marcus: Good catch. That deploy changed the connection pool config —
we were trying to reduce idle connections. Looks like we set max too
low. Can you rollback while I look at the config?
```

**Minute 4-5: Rollback.**

You practiced this on Wednesday. You know the rollback procedure for this team's deploy pipeline because you walked through it with the deploy docs and ran a dry-run in staging. You open the CI dashboard, find the previous successful deploy of order-service (v2.13.2), and hit the "Redeploy" button. You know this team uses blue-green deploys, so the rollback is just a traffic shift — no new build required.

```
#deploys
🔄 order-service v2.13.2 redeployed to production
   Deployed by: @you | Pipeline: #4523 (rollback)
   Time: 2:52 PM
```

You switch back to the dashboard and watch. The database connection utilization starts dropping. 98%... 84%... 61%... 23%. The waiting queue drains. p99 latency falls from 8.2 seconds to 1.1 seconds, then back down to 430ms. Error rate drops from 4.7% to 0.3%, then back to the 0.2% baseline.

```
#incidents
You: Rollback complete. order-service v2.13.2 is live. Metrics
recovering:
- p99 latency: 430ms (baseline: 400ms) ✅
- Error rate: 0.2% (baseline: 0.2%) ✅
- DB connection pool: 23% (baseline: ~20%) ✅

Total impact window: ~14 minutes (2:38 PM - 2:52 PM).
Will take timeline notes for postmortem.
```

Marcus responds:

```
@marcus: Nice work. I found the issue — the new config set
maxConnections to 10 instead of 50. Typo in the env var override.
I'll fix and redeploy after we write the postmortem. Thanks for
catching this so fast.
```

Your tech lead, who's been lurking:

```
@sarah: Really solid incident response for day 4. Clear comms,
good data, clean rollback. 👏
```

---

The next morning, Friday, there's a postmortem meeting. You bring your timeline notes — the ones you took minute by minute as the incident unfolded. You can tell the room exactly when the deploy happened, when the first error appeared, when the alert fired, and when the rollback resolved it. You even have the specific error message and the connection pool numbers.

The postmortem document gets written. Your timeline becomes the "Timeline" section. The root cause is clear: a configuration change reduced the database connection pool from 50 to 10, causing connection exhaustion under normal load. The action items are straightforward: add a config validation check to the deploy pipeline, set a minimum threshold for connection pool size, and add a dashboard alert specifically for connection pool saturation.

You contributed. On day five. Not because you're a genius. Not because you had years of context. But because you spent your first four days building the operational scaffolding that let you respond when it mattered.

---

Think about what you had that a typical day-four engineer wouldn't:

- **A bookmarked dashboard** with the golden signals, so you didn't waste time searching for it.
- **Baseline numbers** written down, so you could immediately say "8.2 seconds vs. normal 400ms" instead of "this seems slow, maybe?"
- **A hotlinks page** that got you to the deploy tracker and log query in seconds, not minutes.
- **A "what changed?" checklist** that pointed you straight at the recent deployment.
- **A saved log query** that you could run immediately instead of fumbling with the query syntax.
- **A practiced rollback procedure** so you could execute it confidently instead of asking "how do I roll back?" during a live incident.
- **An incident communication template** so your message was structured, data-rich, and actionable — not "something seems wrong with orders."

None of this required deep system knowledge. You didn't debug the connection pool code. You didn't read the configuration diff. You didn't know the history of why the pool was set to 50 in the first place. Marcus knew that. Sarah knew that. What *you* knew was where to look, what to check first, and how to communicate what you found.

That's the difference between showing up and being *operationally ready*. Between being new and being *useful*. Between hoping someone else handles it and stepping up because you built the scaffolding to step up.

---

You didn't know everything. You didn't need to.

You knew where to look. You knew what to check first. You knew how to communicate what you found.

That's Beast Mode.

It's not about being the smartest person in the room. It's not about having five years of context on the system. It's about doing the work *before* the moment arrives, so that when the moment arrives — and it always does — you're ready.

Nick Hook didn't tell junior engineers to "move fast and break things." He told them to be *operationally excellent from day one*. To treat their first week not as a passive orientation but as an active mission to build the infrastructure of competence. The dashboards, the mental models, the checklists, the relationships, the muscle memory.

The engineers who do this don't just survive their first month. They change the culture of their team. They raise the bar for what "onboarding" means. They prove that operational readiness isn't a function of tenure — it's a function of intentionality.

Your first week isn't a grace period. It's a launchpad.

> **"The best engineers I've worked with weren't the ones who knew the most on day one. They were the ones who knew *how to become dangerous* the fastest. They didn't wait for permission or orientation or a buddy system. They built their own scaffolding, asked the hard questions early, and were ready when the system needed them. That's not experience. That's a decision."**
>
> — The Beast Mode philosophy

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M91: Beast Mode — Access & System Mapping](../course/modules/loop-3/L3-M91-beast-mode-access-and-system-mapping.md)** — Build your personal access matrix for TicketPulse: every system, every credential, every runbook, verified to actually work before you need it
- **[L3-M91a: Beast Mode — Observability & Dashboard Wiring](../course/modules/loop-3/L3-M91a-beast-mode-observability-wiring.md)** — Wire up the dashboards, traces, and log queries you will reach for during an incident and validate them against a simulated failure
- **[L3-M91b: Beast Mode — Incident Response Dry Run](../course/modules/loop-3/L3-M91b-beast-mode-incident-dry-run.md)** — Run a full incident simulation on TicketPulse: detection, triage, communication, mitigation, and postmortem under realistic time pressure
- **[L3-M91c: Beast Mode — Tribal Knowledge & the Newcomer Superpower](../course/modules/loop-3/L3-M91c-beast-mode-tribal-knowledge.md)** — Document the undocumented: surface the institutional knowledge that lives only in people's heads and convert it into searchable, durable reference material

### Quick Exercises

> **No codebase handy?** Try the self-contained version in [Appendix B: Exercise Sandbox](../appendices/appendix-exercise-sandbox.md) — the [incident simulation exercise](../appendices/appendix-exercise-sandbox.md#exercise-10-incident-simulation--break-it-triage-it-fix-it) gives you a Docker Compose app you can deliberately break and then triage using only logs and metrics.

1. **Build your personal access matrix for your current team's systems** — list every system you might need to touch during an incident, verify you have working credentials for each, and note the escalation path for anything you cannot access directly.
2. **Create a hotlinks bookmark folder with your top 5 dashboards** — open each one right now and verify it loads with current data. Fix any broken panel before an incident forces you to debug your observability tooling while the system is on fire.
3. **Shadow the next on-call shift and take notes** — you do not need to be the primary responder. Sit with whoever is on call, watch how they work, and write down every tool, every shortcut, and every piece of tribal knowledge you observe.

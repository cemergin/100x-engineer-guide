<!--
  CHAPTER: 36
  TITLE: Beast Mode — Operational Readiness from Day One
  PART: II — Applied Engineering
  PREREQS: None (Ch 12, 18 helpful)
  KEY_TOPICS: operational readiness, onboarding, codebase navigation, observability setup, incident readiness, system mental models, dashboard quicklinks, tribal knowledge extraction
  DIFFICULTY: All levels
  UPDATED: 2026-04-03
-->

# Chapter 36: Beast Mode — Operational Readiness from Day One

> **Part II — Applied Engineering** | Prerequisites: None (Ch 12, 18 helpful) | Difficulty: All levels

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
- Chapter 4 (SRE fundamentals — error budgets, SLOs, the theoretical foundation for operational readiness)
- Chapter 7 (DevOps & Infrastructure — the tools and pipelines you need access to)
- Chapter 12 (Software Architecture — understanding system structure)
- Chapter 18 (Debugging, Profiling & Monitoring — the observability tools you will set up here)
- Chapter 33 (GitHub Actions — CI/CD pipelines you will need to understand)
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

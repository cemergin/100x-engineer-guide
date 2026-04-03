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

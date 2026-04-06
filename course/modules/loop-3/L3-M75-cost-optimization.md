# L3-M75: Cost Optimization

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M44 (AWS Architecture), L2-M45 (Docker), L2-M46 (Kubernetes)
>
> **Source:** Chapters 4, 9, 19 of the 100x Engineer Guide

## What You'll Learn

- How to analyze a cloud bill and identify the highest-impact optimization opportunities
- The specific techniques for reducing compute, database, cache, and search costs
- How to do reserved instance math and decide when to commit
- How to build a cost optimization plan with estimated savings and trade-offs
- Why tagging strategy is the foundation of cost accountability
- The relationship between cost optimization and reliability — where cutting costs is dangerous

## Why This Matters

TicketPulse's cloud bill just arrived: **$15,000/month**. The CTO has called a meeting. The message is clear: "Cut it by 40% or we need to have a different conversation about this architecture."

$15,000/month is $180,000/year. For a startup, that is an engineer's salary. For a scale-up, it is still significant margin. The ability to look at a cloud bill and find $6,000/month in waste — without degrading the product — is a skill that directly impacts whether the business survives.

Most companies are 30-50% over-provisioned. Not because engineers are careless, but because the default is to over-provision for safety. Nobody gets fired for provisioning too much. They do get fired for an outage caused by under-provisioning. The result is systemic waste.

> **Ecosystem note:** Chapter 19 of the 100x Engineer Guide covers AWS architecture holistically — instance types, managed services, and the cost models behind them. This module is the applied companion: you will read the theory, then do real cost math against TicketPulse's actual bill.
>
> Airbnb's cost optimization team saved $60M/year by right-sizing their AWS instances. They found that the average EC2 instance was using 12% of its allocated CPU. The other 88% was paying for peace of mind.

---

### 🤔 Prediction Prompt

Before reading the bill breakdown, estimate: what percentage of a typical cloud bill do you think is waste from over-provisioning? Where do you expect the biggest surprise cost to be hiding?

## Part 1: Understanding the Bill

### 📊 Observe: TicketPulse Cost Breakdown

Here is TicketPulse's monthly cloud bill, broken down by service:

```
TICKETPULSE MONTHLY CLOUD COST: $15,000
════════════════════════════════════════

Service                      │ Monthly │  %  │ Notes
─────────────────────────────┼─────────┼─────┼─────────────────────
Compute (ECS/K8s)            │ $5,000  │ 33% │ 12 instances across 3 services
Database (RDS PostgreSQL)    │ $3,000  │ 20% │ Primary + 2 read replicas
Search (Elasticsearch)       │ $2,000  │ 13% │ 3-node cluster
Network / Bandwidth          │ $1,500  │ 10% │ Cross-AZ + egress
Cache (ElastiCache Redis)    │ $1,000  │  7% │ 2 nodes, r6g.large
Monitoring (Datadog/NR)      │ $1,000  │  7% │ APM + logs + metrics
Messaging (Kafka/MSK)        │   $500  │  3% │ 3-broker cluster
Other (DNS, Secrets, S3)     │ $1,000  │  7% │ Various small services
─────────────────────────────┼─────────┼─────┼─────────────────────
TOTAL                        │$15,000  │100% │
```

### Reading the Bill: Where to Look First

```
COST OPTIMIZATION PRINCIPLE: Optimize the biggest line items first.

$5,000 in compute: even a 20% reduction saves $1,000/month
$500 in messaging: even a 50% reduction saves only $250/month

Always start at the top of the bill.
```

### The Utilization Problem

Pull the actual utilization metrics for each service:

```
SERVICE UTILIZATION (average over 30 days)
──────────────────────────────────────────

Service              │ CPU Avg │ CPU Peak │ Memory Avg │ Memory Peak
─────────────────────┼─────────┼──────────┼────────────┼────────────
order-service (x4)   │   18%   │   62%    │    35%     │    58%
payment-service (x4) │   12%   │   45%    │    28%     │    42%
event-service (x4)   │    8%   │   30%    │    22%     │    35%
─────────────────────┼─────────┼──────────┼────────────┼────────────
PostgreSQL primary   │   25%   │   78%    │    60%     │    85%
PostgreSQL replica 1 │   15%   │   42%    │    55%     │    72%
PostgreSQL replica 2 │    5%   │   12%    │    40%     │    48%
─────────────────────┼─────────┼──────────┼────────────┼────────────
Redis node 1         │   10%   │   35%    │    45%     │    62%
Redis node 2         │    8%   │   28%    │    40%     │    55%
─────────────────────┼─────────┼──────────┼────────────┼────────────
Elasticsearch node 1 │   22%   │   55%    │    70%     │    88%
Elasticsearch node 2 │   20%   │   50%    │    68%     │    85%
Elasticsearch node 3 │   18%   │   48%    │    65%     │    82%
```

### 🤔 Reflect

Before reading the optimization section, study the utilization table. What jumps out at you? Which services are clearly over-provisioned? Which are close to their limits?

Write your observations before reading on. The services that scream for optimization usually have:
- CPU average well below 20% with peaks below 50%
- Multiple identical instances where one or two are essentially idle

---

## Part 2: The Top 5 Optimization Opportunities

### Opportunity 1: Right-Size Compute Instances

**Current state:** 12 instances across 3 services, all the same size.
**Problem:** The event-service uses 8% CPU average and 22% memory. It does not need the same instance type as the order-service.

```
RIGHT-SIZING ANALYSIS
─────────────────────

Service          │ Current      │ Proposed     │ Savings
─────────────────┼──────────────┼──────────────┼─────────
order-service    │ 4x m5.large  │ 3x m5.large  │ $104/mo
                 │ ($417/mo ea) │              │ (drop 1 instance; 62% peak
                 │              │              │  is fine with 3 + autoscaling)
─────────────────┼──────────────┼──────────────┼─────────
payment-service  │ 4x m5.large  │ 4x t3.large  │ $268/mo
                 │ ($417/mo ea) │ ($350/mo ea) │ (burstable is fine for 45%
                 │              │              │  peak; t3 unlimited if needed)
─────────────────┼──────────────┼──────────────┼─────────
event-service    │ 4x m5.large  │ 2x t3.medium │ $1,497/mo
                 │ ($417/mo ea) │ ($85/mo ea)  │ (30% peak CPU, 35% memory
                 │              │              │  -- massively over-provisioned)
─────────────────┼──────────────┼──────────────┼─────────
                                  TOTAL SAVINGS: ~$1,870/mo
```

**The catch:** Right-sizing requires load testing to validate. Do not just resize and hope. Run the new instance sizes against production-equivalent load for 48 hours before committing.

**The right-sizing process:**

```bash
# Step 1: Get 30-day P99 CPU and memory from CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=ticketpulse-prod \
  --start-time 2026-03-01T00:00:00Z \
  --end-time 2026-03-31T00:00:00Z \
  --period 86400 \
  --statistics Maximum

# Step 2: Apply the right-sizing formula
# Safe target: P99 peak <= 60% of instance capacity
# Your peak CPU: 62% on order-service
# That's already at the boundary -- don't downsize the instance type, just reduce count

# Step 3: Simulate load on the new size before committing
# Use k6 or Locust to replay production traffic patterns
# against a staging environment running the new instance sizes
```

### Opportunity 2: Reserved Instances — The Math

**Current state:** All instances are on-demand pricing.
**The problem:** TicketPulse has been running for 8 months with predictable baseline capacity. On-demand is the most expensive way to run a predictable workload.

Let us do the actual reserved instance math:

```
RESERVED INSTANCE MATH: AWS EC2
════════════════════════════════

Instance: m5.large (2 vCPU, 8GB RAM) in us-east-1

Pricing:
  On-Demand:              $0.096/hour × 730 hr/month = $70.08/month
  1-year, no upfront:     $0.062/hour × 730 hr/month = $45.26/month  → 35% savings
  1-year, partial upfront: $570 upfront + $0.038/hr  = $47.50/month avg → 32% savings
  1-year, all upfront:    $504 upfront / 12 months   = $42.00/month avg → 40% savings
  3-year, all upfront:    $816 upfront / 36 months   = $22.67/month avg → 68% savings

TicketPulse baseline (after right-sizing): 9 m5.large instances
  On-Demand total:        9 × $70.08 = $630.72/month
  Reserved (1yr, none):   9 × $45.26 = $407.34/month
  SAVINGS:                $223.38/month from compute alone
```

```
RESERVED INSTANCE MATH: RDS PostgreSQL
═══════════════════════════════════════

Instance: db.r6g.xlarge (4 vCPU, 32GB RAM) in us-east-1

Pricing:
  On-Demand:              $0.384/hour = $280.32/month
  1-year, no upfront:     $0.239/hour = $174.47/month  → 38% savings
  1-year, all upfront:    $2,024 / 12 = $168.67/month  → 40% savings

TicketPulse DB: Primary (db.r6g.2xlarge) + 1 Replica (db.r6g.xlarge)
  Estimate on-demand:  ~$3,000/month
  After 1-yr reserved: ~$1,860/month
  SAVINGS: ~$1,140/month
```

**When to reserve — the decision matrix:**

```
RESERVE WHEN:
  ✓ Workload has been running > 6 months (predictable baseline)
  ✓ You are confident the instance type is right (post right-sizing)
  ✓ The service will run for > 12 more months
  ✓ Cost savings > switching cost (time to evaluate, risk of commitment)

DO NOT RESERVE WHEN:
  ✗ You are still experimenting with instance types
  ✗ The workload is seasonal (consider Savings Plans instead)
  ✗ You might shut the service down within 12 months
  ✗ You have not right-sized first (reserving the wrong size wastes money)

ALTERNATIVES TO RESERVATIONS:
  - AWS Savings Plans: flexible (applies to any EC2 regardless of type),
    commit to $/hour spend rather than specific instances
    → Best if you are not sure which instance types you will use
  - Spot Instances: 70-90% discount, but can be interrupted with 2-min notice
    → Best for batch processing, fault-tolerant workers, ML training
```

### Opportunity 3: Eliminate the Second Read Replica

**Current state:** Primary + 2 read replicas ($3,000/month total).
**Problem:** Replica 2 uses 5% CPU average. It was added during a traffic spike 3 months ago and never removed.

```
DATABASE OPTIMIZATION
─────────────────────

Option A: Remove replica 2 entirely
  Savings: $750/month
  Risk: Less read capacity during spikes
  Mitigation: Use connection pooling (PgBouncer) to handle
              more connections with fewer replicas

Option B: Downsize replica 2 to a smaller instance
  Savings: $375/month
  Risk: Lower, but still paying for an underused instance

Option C: Switch to Aurora Serverless for replica 2
  Savings: Variable -- only pay for actual usage
  Risk: Cold start latency on first query after idle period

Recommendation: Option A with PgBouncer.
  The primary + 1 replica handles 78% peak CPU comfortably.
  PgBouncer multiplexes connections, reducing replica load.
```

**The infrastructure TTL principle:** When you add a resource during a spike, add a calendar reminder to re-evaluate it 30 days later. Call it an "infrastructure TTL." If the spike was a one-time event and the resource is still idle at TTL, remove it.

```bash
# Add to your Makefile or ops runbook:
# After adding any resource during an incident, run:

add-resource-ttl() {
  local RESOURCE=$1
  local DAYS=${2:-30}
  local REMINDER_DATE=$(date -d "+${DAYS} days" +%Y-%m-%d)
  
  echo "[$REMINDER_DATE] Review and remove if still idle: $RESOURCE" \
    >> ops/resource-ttls.txt
  
  echo "TTL reminder added for $RESOURCE on $REMINDER_DATE"
}

# Example:
# add-resource-ttl "RDS replica-2 in us-east-1" 30
```

### Opportunity 4: Optimize Elasticsearch

**Current state:** 3-node cluster, all nodes are data + master + ingest.
**Problem:** Memory utilization is 70-88%, but most of that is index caching for data that is rarely searched.

```
ELASTICSEARCH OPTIMIZATION
──────────────────────────

Action 1: Implement index lifecycle management (ILM)
  - Hot indices (last 7 days): keep on current nodes
  - Warm indices (8-30 days): move to cheaper storage
  - Cold indices (30+ days): compress + move to S3-backed
  Savings: ~$400/month (reduced storage needs)

Action 2: Reduce replica count for non-critical indices
  - Event search index: 1 replica → 0 replicas in dev/staging
  - Analytics indices: 1 replica → 0 replicas (rebuild from source)
  Savings: ~$200/month (reduced storage + memory)

Action 3: Right-size the cluster
  - Current: 3x r5.large ($450/mo each)
  - Proposed: 2x r5.large + 1x r5.medium ($300/mo)
  - The third node carries less load (ingest-only)
  Savings: ~$150/month

TOTAL ES SAVINGS: ~$750/month
```

### Opportunity 5: Reduce Network Costs

**Current state:** $1,500/month in network costs.
**Problem:** Cross-AZ traffic is expensive ($0.01/GB per direction), and TicketPulse's services communicate across AZs freely.

```
NETWORK COST BREAKDOWN
──────────────────────

Cross-AZ traffic:     $800/month
Internet egress:      $500/month
NAT Gateway:          $200/month

Cross-AZ reduction:
  - Enable topology-aware routing in K8s (prefer same-AZ pods)
  - Move Redis to the same AZ as the heaviest consumer
  Savings: ~$300/month

Egress reduction:
  - Add CloudFront for static assets and API responses
  - Enable gzip/brotli compression on all responses
  Savings: ~$200/month

TOTAL NETWORK SAVINGS: ~$500/month
```

**Topology-aware routing in Kubernetes:**

```yaml
# In your Service definition, add topology hints
apiVersion: v1
kind: Service
metadata:
  name: redis
  annotations:
    service.kubernetes.io/topology-mode: "Auto"
spec:
  selector:
    app: redis
  ports:
    - port: 6379
```

This tells Kubernetes to prefer routing traffic to pods in the same availability zone, reducing cross-AZ charges automatically.

---

## Part 3: The Cost Calculation Exercise

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Your Own Cost Model

<details>
<summary>💡 Hint 1: Direction</summary>
Start with AWS Cost Explorer grouped by service tag. For right-sizing, the key formula is: target P99 peak CPU at 60% of instance capacity. Below that, you are over-provisioned.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
For the event-service (8% avg CPU, 30% peak), a t3.large at $170/mo handles burst workloads via CPU credits. Two instances with autoscaling (2-4) replaces four m5.large at $417/mo each. Do the math: $340 vs $1,668.
</details>


Before reading the final plan, do this exercise yourself. Using the utilization table from Part 1:

**Exercise A: Right-sizing the event-service**

The event-service runs 4x m5.large at $417/month each = $1,668/month.
CPU average is 8%, peak is 30%. Memory average is 22%, peak is 35%.

A t3.medium has 2 vCPU, 4GB RAM and costs $85/month.
A t3.large has 2 vCPU, 8GB RAM and costs $170/month.

Questions:
1. Which instance type can handle 30% peak CPU without throttling? (Hint: t3 instances burst — check AWS burst credits)
2. How many instances do you need to handle the current peak safely? (Assume you want P99 peak < 60% per instance)
3. What is the new monthly cost and total savings?

**Reference answer:** t3.large can handle 30% peak without bursting its CPU credits heavily. 2 instances with autoscaling between 2 and 4 instances handles the load. Cost: 2 × $170 = $340/month vs $1,668. Savings: ~$1,328/month. (The original estimate used t3.medium for slightly more savings — validate with load testing before committing.)

**Exercise B: Reserved instance break-even**

You are considering reserving 3x m5.large instances for the order-service.

- On-Demand: $70.08/month per instance
- 1-year reserved (all upfront): $504 per instance

Questions:
1. How many months does it take to break even on the upfront payment?
2. What are the total savings over 12 months?
3. What is the risk if you need to change instance types in 6 months?

**Reference answer:**
- Break-even: $504 upfront / ($70.08 - $42.00) = $504 / $28.08 ≈ 17.9 months. Hmm — that suggests "all upfront" actually takes longer to break even than the 12-month term. Better choice: 1-year no-upfront at $45.26/month. Break-even is immediate (you save from day 1 with no upfront). Total savings: 12 × ($70.08 - $45.26) = 12 × $24.82 = $297.84 per instance × 3 = $893.52 over the year.

This exercise illustrates why you should model the math before committing. The "all upfront" sounds like maximum savings, but the break-even point can be longer than the commitment term for some instance types.

---

## Part 4: The Optimization Plan

### 🛠️ Build: Cost Optimization Plan

<details>
<summary>💡 Hint 1: Direction</summary>
Prioritize by savings-per-effort. Right-sizing the event-service saves $1,497/mo with low effort; reserved instances save $900+/mo with zero effort (just a purchase commitment). Attack the biggest line items first.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use Spot instances only for stateless, fault-tolerant workloads (batch processing, the event-service read path). Never Spot for the payment-service -- an interrupted transaction mid-charge is worse than paying full price. For reserved instances, model the break-even before committing: 1-year no-upfront saves from day 1 with zero risk.
</details>


Compile all opportunities into a prioritized plan:

```
TICKETPULSE COST OPTIMIZATION PLAN
═══════════════════════════════════

Target: Reduce from $15,000/month to $9,000/month (40% reduction)

 # │ Action                        │ Savings  │ Effort │ Risk  │ Timeline
───┼───────────────────────────────┼──────────┼────────┼───────┼──────────
 1 │ Right-size event-service      │ $1,497   │ Low    │ Low   │ Week 1
 2 │ Right-size payment-service    │   $268   │ Low    │ Low   │ Week 1
 3 │ Remove unused read replica    │   $750   │ Low    │ Med   │ Week 2
 4 │ Reserved instances (compute)  │   $940   │ None   │ Low   │ Week 2
 5 │ Reserved instances (database) │   $900   │ None   │ Low   │ Week 2
 6 │ Elasticsearch ILM + resize    │   $750   │ Med    │ Low   │ Week 3
 7 │ Network: topology routing     │   $300   │ Med    │ Low   │ Week 3
 8 │ Drop 1 order-service instance │   $104   │ Low    │ Med   │ Week 4
 9 │ Network: CloudFront + gzip    │   $200   │ Med    │ Low   │ Week 4
───┼───────────────────────────────┼──────────┼────────┼───────┼──────────
   │ TOTAL PROJECTED SAVINGS       │ $5,709   │        │       │
   │ NEW MONTHLY COST              │ $9,291   │        │       │
   │ REDUCTION                     │  38.1%   │        │       │
```

Close to the 40% target. The remaining 2% could come from:
- Monitoring cost optimization (log sampling, reducing trace volume)
- Spot instances for batch processing
- Scheduled scaling (scale down during low-traffic hours)

---

## Part 5: Tagging Strategy

### Why Tags Matter

Without tags, you cannot answer basic questions:
- "How much does the order service cost?" — no idea.
- "How much do we spend on staging vs production?" — no idea.
- "Which team is responsible for this $800/month Elasticsearch cluster?" — no idea.

```
TAGGING STRATEGY
════════════════

Required tags for EVERY resource:

Tag Key        │ Example Values       │ Purpose
───────────────┼──────────────────────┼─────────────────────
service        │ order, payment, event│ Cost per service
environment    │ prod, staging, dev   │ Cost per environment
team           │ platform, backend    │ Cost per team
cost-center    │ engineering, infra   │ Finance allocation
managed-by     │ terraform, manual    │ Drift detection

Enforcement:
- Terraform: require tags in module variables (fail plan without them)
- AWS: SCP (Service Control Policy) that denies resource creation
  without required tags
- CI check: scan IaC files for tag compliance before merge
```

### 🛠️ Build: Tag Compliance Check

<details>
<summary>💡 Hint 1: Direction</summary>
Without tags, you cannot answer "how much does the order-service cost?" Enforce required tags (service, environment, team, cost-center) via an SCP or a Terraform CI check that fails the plan without them.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use `aws ce get-cost-and-usage` with `--group-by Type=TAG,Key=service` to generate a per-service cost report. The tag compliance check in CI is a simple grep: for each Terraform resource, verify the required tag keys exist.
</details>


```bash
# Simple tag compliance check for Terraform
# Add to CI pipeline

check_tags() {
  local required_tags=("service" "environment" "team" "cost-center")
  local missing=0

  for tag in "${required_tags[@]}"; do
    if ! grep -q "\"$tag\"" "$1"; then
      echo "MISSING TAG: $tag in $1"
      missing=$((missing + 1))
    fi
  done

  return $missing
}

# Run against all Terraform files
for tf_file in $(find . -name "*.tf" -path "*/resources/*"); do
  check_tags "$tf_file"
done
```

**The tag-based cost report:**

Once tags are applied consistently, use AWS Cost Explorer to build a monthly report:

```bash
# AWS CLI: Get cost by service tag for last 30 days
aws ce get-cost-and-usage \
  --time-period Start=2026-03-01,End=2026-03-31 \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --group-by Type=TAG,Key=service \
  --query 'ResultsByTime[0].Groups[*].{Service: Keys[0], Cost: Metrics.UnblendedCost.Amount}' \
  --output table
```

This turns "the cloud bill" from a mystery into a per-service cost dashboard. When the payment service cost spikes, you know immediately — and you know which team owns it.

---

## Part 6: The Cost-Reliability Trade-off

### Where You Should NOT Cut Costs

```
NEVER CUT THESE
────────────────

1. MONITORING
   Saving $500/month on monitoring is meaningless if an
   undetected outage costs $50,000 in lost revenue.
   Monitoring is insurance. You optimize it; you do not cut it.

2. BACKUPS
   "We can save $200/month by reducing backup frequency
   from hourly to daily." Until you need the backup.

3. MULTI-AZ FOR DATABASES
   Single-AZ saves ~40% on database costs. It also means
   a single hardware failure takes down your database.
   For production: always multi-AZ.

4. SECURITY TOOLING
   WAF, DDoS protection, secrets management -- these are
   not cost centers. They are survival mechanisms.
```

### The Decision Framework

```
FOR EACH OPTIMIZATION, ASK:

1. What is the blast radius if this goes wrong?
   - Right-sizing compute: service might be slow under spike → recoverable
   - Removing a replica: reads might be slow → recoverable
   - Removing monitoring: you might not know something is wrong → dangerous

2. How quickly can we reverse it?
   - Reserved instances: locked for 1 year → high commitment
   - Instance resize: 5 minutes to resize back → low commitment
   - Removing a replica: 30 minutes to add back → medium commitment

3. What is the probability of needing the capacity?
   - Event-service at 8% CPU: extremely unlikely to need 4x m5.large
   - Database at 78% peak: already tight, do not reduce further
```

### 📐 Exercise: Risky vs Safe Cuts

<details>
<summary>💡 Hint 1: Direction</summary>
For each cut, assess blast radius (what breaks if this goes wrong?), reversibility (how fast can you undo it?), and probability of needing the capacity. Disabling RDS backups is "Never" -- the $150/mo savings is meaningless against a data loss event.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Spot instances for the event-service (stateless, read-heavy) = Safe. Spot for the payment-service (stateful transactions) = Never. Reducing Kafka from 3 to 2 brokers = Risky -- you lose fault tolerance for one broker failure. Single-AZ RDS = Never for production.
</details>


For each of these potential optimizations, classify it as "Safe," "Risky," or "Never" and explain why:

1. Remove the second Redis node (current: 8% CPU average, 40% memory average)
2. Disable automated RDS backups to save $150/month
3. Switch from Multi-AZ RDS to Single-AZ to save $1,200/month
4. Reduce Datadog log retention from 15 days to 3 days
5. Use Spot Instances for the event-service (read-heavy, stateless)
6. Use Spot Instances for the payment-service (stateful transactions)
7. Right-size the Kafka cluster from 3 to 2 brokers (current: 25% CPU, 40% storage used)

**Discussion:** Not all of these have clean answers. The Redis and Kafka reductions depend on your SLO for latency during node failures. The Datadog log retention cut depends on your compliance requirements. Work through the blast radius and reversibility for each before deciding.

---

## 📐 Design: The Monthly Cost Review

<details>
<summary>💡 Hint 1: Direction</summary>
The most expensive mistake is the "temporary" resource that becomes permanent. Every incident adds resources; the monthly review is where you check which are still justified. Add infrastructure TTLs (calendar reminders) for every resource added during a spike.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Structure the 30-minute review: (1) bill vs last month, (2) utilization dashboards for services under 20% or over 70% CPU, (3) reserved instance coverage, (4) recent architecture changes, (5) action items. Use AWS Cost Explorer grouped by service tag to make this data-driven, not anecdotal.
</details>


Cost optimization is not a one-time project. It is a recurring practice.

```
MONTHLY COST REVIEW AGENDA (30 minutes)
────────────────────────────────────────

1. Review the bill vs. last month (5 min)
   - What increased? Why?
   - Any unexpected charges?
   - Any resource TTLs that expired?

2. Check utilization dashboards (10 min)
   - Any services consistently under 20% CPU?
   - Any services consistently over 70% CPU?
   - Cache hit ratio still above 90%?
   - Any new services added without tags?

3. Check reserved instance coverage (5 min)
   - Are we using our reservations?
   - Any new baseline workloads that should be reserved?
   - Any reservations about to expire?

4. Review recent architecture changes (5 min)
   - New services added? What is their cost projection?
   - Services removed? Did we also remove the infrastructure?
   - Any experiments that were supposed to be temporary?

5. Action items for next month (5 min)
```

The most expensive mistake in cloud cost management is the "temporary" resource that becomes permanent. Every incident response adds resources. The monthly review is where you check which of those resources are still justified.

---

## 🤔 Final Reflections

1. **What is the trade-off between cost and reliability?** For each optimization in the plan, what could go wrong? Which trade-offs are acceptable?

2. **Why are most companies 30-50% over-provisioned?** What incentive structures lead to this? How would you change the incentives?

3. **Is $9,000/month the right target?** How do you decide what "enough" optimization looks like? When does further optimization become counterproductive?

4. **The second read replica was added during a traffic spike and never removed.** What process would prevent this from happening? (Hint: think about infrastructure TTLs and expiration alerts.)

5. **If TicketPulse's traffic doubles next quarter, which of these optimizations would you reverse first?** In what order would you scale back up?

6. **You reserved 9 m5.large instances for a year. Two months later, the architecture changes and you need m5.xlarge instead.** What are your options? What does this teach you about the timing of reserved instance commitments?

### 🤔 Reflection Prompt

Compare your initial estimate of waste percentage with the actual findings. Were you surprised by where the biggest savings were? How does this change your approach to provisioning new infrastructure?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Right-sizing** | Adjusting the resources (CPU, memory, instance type) allocated to a service to match its actual usage. |
| **Reserved instance** | A cloud pricing model offering a discount in exchange for committing to a specific instance type for a term. |
| **Savings Plans** | A flexible AWS pricing model that offers discounts in exchange for committing to a consistent hourly spend, without locking to specific instance types. |
| **Spot instance** | A cloud compute instance available at a steep discount but subject to interruption when demand rises. |
| **FinOps** | A practice that brings financial accountability to cloud spending through collaboration between engineering and finance. |
| **Cost allocation** | Tagging and attributing cloud costs to specific teams, services, or projects for visibility and accountability. |
| **Infrastructure TTL** | A time-to-live reminder to evaluate whether a temporarily added resource is still needed and remove it if not. |
| **Topology-aware routing** | Kubernetes traffic routing that prefers pods in the same availability zone, reducing cross-AZ data transfer costs. |

## Further Reading

- **AWS Well-Architected Framework, Cost Optimization Pillar**: the canonical guide to cloud cost management
- **The Frugal Architect** (Werner Vogels, 2023): cost as a first-class architectural concern
- **Chapter 19 of the 100x Engineer Guide**: AWS architecture and cost management patterns
- **AWS Cost Explorer and Compute Optimizer**: built-in tools for identifying right-sizing opportunities
- **CloudZero, Vantage, or Infracost**: third-party tools for continuous cost monitoring and optimization
- Kelsey Hightower: "The cloud is not expensive. Your architecture is expensive."

---

## What's Next

Next up: **[L3-M76: System Design Interview Practice](L3-M76-system-design-interview-practice.md)** -- you will apply everything from this course to three system design problems under interview time pressure, building the skill of structured reasoning under constraints.

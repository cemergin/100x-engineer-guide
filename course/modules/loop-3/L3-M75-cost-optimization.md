# L3-M75: Cost Optimization

> ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M44 (AWS Architecture), L2-M45 (Docker), L2-M46 (Kubernetes)
> Source: Chapter 19, Chapter 4 of the 100x Engineer Guide

## What You'll Learn

- How to analyze a cloud bill and identify the highest-impact optimization opportunities
- The specific techniques for reducing compute, database, cache, and search costs
- How to build a cost optimization plan with estimated savings and trade-offs
- Why tagging strategy is the foundation of cost accountability
- The relationship between cost optimization and reliability -- where cutting costs is dangerous

## Why This Matters

TicketPulse's cloud bill just arrived: **$15,000/month**. The CTO has called a meeting. The message is clear: "Cut it by 40% or we need to have a different conversation about this architecture."

$15,000/month is $180,000/year. For a startup, that is an engineer's salary. For a scale-up, it is still significant margin. The ability to look at a cloud bill and find $6,000/month in waste -- without degrading the product -- is a skill that directly impacts whether the business survives.

Most companies are 30-50% over-provisioned. Not because engineers are careless, but because the default is to over-provision for safety. Nobody gets fired for provisioning too much. They do get fired for an outage caused by under-provisioning. The result is systemic waste.

> 💡 **Insight**: "Airbnb's cost optimization team saved $60M/year by right-sizing their AWS instances. They found that the average EC2 instance was using 12% of its allocated CPU. The other 88% was paying for peace of mind."

---

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

> Before reading the optimization section, study the utilization table. What jumps out at you? Which services are clearly over-provisioned? Which are close to their limits?

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

### Opportunity 2: Reserved Instances for Baseline Capacity

**Current state:** All instances are on-demand pricing.
**Problem:** On-demand is the most expensive pricing model. TicketPulse has been running for 8 months -- the baseline is predictable.

```
RESERVED INSTANCE SAVINGS
─────────────────────────

Commitment        │ Discount │ Risk
──────────────────┼──────────┼──────────────────────
1-year, no upfront│   ~30%   │ Locked in for 1 year
1-year, partial   │   ~36%   │ Some upfront payment
1-year, all upfront│  ~40%   │ Full upfront payment
3-year, all upfront│  ~60%   │ Locked in for 3 years

For a startup: 1-year, no upfront is the safe bet.
For stable workloads: 1-year, partial upfront maximizes savings.
```

**Apply to TicketPulse's baseline:**

```
After right-sizing, baseline compute: ~$3,130/month
Reserved (1-year, no upfront): ~$2,190/month
Savings: ~$940/month

Database (RDS reserved): $3,000 → $2,100/month
Savings: ~$900/month

TOTAL RI SAVINGS: ~$1,840/month
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

---

## Part 3: The Optimization Plan

### 🛠️ Build: Cost Optimization Plan

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

## Part 4: Tagging Strategy

### Why Tags Matter

Without tags, you cannot answer basic questions:
- "How much does the order service cost?" -- no idea.
- "How much do we spend on staging vs production?" -- no idea.
- "Which team is responsible for this $800/month Elasticsearch cluster?" -- no idea.

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

---

## Part 5: The Cost-Reliability Trade-off

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

---

## 📐 Design: The Monthly Cost Review

Cost optimization is not a one-time project. It is a recurring practice.

```
MONTHLY COST REVIEW AGENDA (30 minutes)
────────────────────────────────────────

1. Review the bill vs. last month (5 min)
   - What increased? Why?
   - Any unexpected charges?

2. Check utilization dashboards (10 min)
   - Any services consistently under 20% CPU?
   - Any services consistently over 70% CPU?
   - Cache hit ratio still above 90%?

3. Check reserved instance coverage (5 min)
   - Are we using our reservations?
   - Any new baseline workloads that should be reserved?

4. Review recent architecture changes (5 min)
   - New services added? What is their cost projection?
   - Services removed? Did we also remove the infrastructure?

5. Action items for next month (5 min)
```

---

## 🤔 Final Reflections

1. **What is the trade-off between cost and reliability?** For each optimization in the plan, what could go wrong? Which trade-offs are acceptable?

2. **Why are most companies 30-50% over-provisioned?** What incentive structures lead to this? How would you change the incentives?

3. **Is $9,000/month the right target?** How do you decide what "enough" optimization looks like? When does further optimization become counterproductive?

4. **The second read replica was added during a traffic spike and never removed.** What process would prevent this from happening? (Hint: think about infrastructure TTLs and expiration alerts.)

5. **If TicketPulse's traffic doubles next quarter, which of these optimizations would you reverse first?**

---

## Further Reading

- **AWS Well-Architected Framework, Cost Optimization Pillar**: the canonical guide to cloud cost management
- **The Frugal Architect** (Werner Vogels, 2023): cost as a first-class architectural concern
- **Chapter 19**: AWS architecture and cost management patterns
- **Kelsey Hightower on "Cloud Costs"**: "The cloud is not expensive. Your architecture is expensive."
- **CloudZero, Vantage, or Infracost**: tools for continuous cost monitoring and optimization

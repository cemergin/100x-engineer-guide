# L3-M62: Cloud Provider Deep Dive

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 90 min | 🟢 Core | Prerequisites: L3-M61 (Multi-Region Design), L2-M44 (Terraform & IaC), L2-M43 (Kubernetes Fundamentals)
>
> **Source:** Chapters 1, 19, 31, 22, 23 of the 100x Engineer Guide

---

## The Goal

You have been running TicketPulse on Docker Compose on your laptop. That is not production. Production means TLS certificates, load balancers, managed databases with automatic backups, message queues that do not lose data when a process crashes, and monitoring dashboards that page you at 3am.

This module gives you two paths: AWS or GCP. Pick one (or do both if you have time). The goal is not to become a cloud certification expert. The goal is to deploy a real service, hit it from the internet, and understand the cost and operational reality of each platform.

**You will have a live, internet-accessible TicketPulse endpoint within 30 minutes.**

---

## 0. Choose Your Path (5 minutes)

### AWS Path

You will use:
- **ECS on Fargate** — serverless containers (no EC2 instances to manage)
- **RDS (PostgreSQL)** — managed database with automated backups
- **ElastiCache (Redis)** — managed cache
- **SQS** — managed message queue
- **ALB** — application load balancer with TLS termination

### GCP Path

You will use:
- **Cloud Run** — serverless containers (scale to zero)
- **Cloud SQL (PostgreSQL)** — managed database
- **Memorystore (Redis)** — managed cache
- **Pub/Sub** — managed message queue
- **Global HTTP(S) Load Balancer** — global load balancing with CDN

### Which Should You Choose?

| Factor | AWS | GCP |
|---|---|---|
| Market share | ~32% (largest) | ~12% (third) |
| Service catalog | 200+ services (exhaustive) | ~100 services (focused) |
| Developer experience | Configuration-heavy | Simpler defaults |
| Container story | ECS/Fargate (good), EKS (complex) | Cloud Run (excellent), GKE (the best K8s) |
| Free tier | 12 months + always-free tier | 90-day $300 credit + always-free tier |
| If your employer uses it | Pick this one | Pick this one |

**If in doubt:** GCP's Cloud Run path is faster to get a deployed service. AWS's ECS/Fargate path teaches you more about production networking. Both are valuable.

---

## 1. AWS Path: Deploy TicketPulse to ECS/Fargate (35 minutes)

### Prerequisites

```bash
# Install AWS CLI (if not already installed)
# https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)

# Verify
aws sts get-caller-identity
```

### Step 1: Push Your Container Image to ECR

```bash
# Create an ECR repository
aws ecr create-repository --repository-name ticketpulse-api

# Get the login command and authenticate Docker
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push your existing TicketPulse image
docker tag ticketpulse-api:latest \
  <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ticketpulse-api:latest

docker push \
  <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ticketpulse-api:latest
```

### Step 2: Create the Infrastructure

For a real deployment, you need: a VPC, subnets, security groups, an ALB, an ECS cluster, a task definition, and a service. This is a lot of configuration.

**Option A: Use the AWS Console (visual, good for learning)**

Walk through the ECS "Getting Started" wizard. It creates a Fargate cluster, task definition, and service with an ALB. This is the fastest way to get a running service.

**Option B: Use CloudFormation/CDK (repeatable, production-ready)**

📐 **Design Exercise:** Before using any wizard or template, write down the resources you think you need. Draw the network diagram. Then compare with what the wizard creates.

**The minimum viable architecture:**

```
Internet
    │
┌───▼────────────┐
│     ALB        │  (public subnets, port 443)
│  (HTTPS→HTTP)  │
└───┬────────────┘
    │ port 8080
┌───▼────────────┐
│  ECS Service   │  (private subnets)
│  (Fargate)     │
│  3 tasks       │
└───┬────────────┘
    │
┌───▼────────────┐  ┌──────────────┐
│  RDS PostgreSQL│  │  ElastiCache  │  (private subnets, no public access)
│  (Multi-AZ)    │  │  (Redis)      │
└────────────────┘  └──────────────┘
```

### Step 3: Create a Simplified Task Definition

```json
{
  "family": "ticketpulse-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ticketpulse-api:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        { "name": "NODE_ENV", "value": "production" },
        { "name": "PORT", "value": "8080" },
        { "name": "DATABASE_URL", "value": "postgresql://user:pass@rds-endpoint:5432/ticketpulse" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ticketpulse-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 🔍 Try It: Hit Your Live Endpoint

```bash
# Get the ALB DNS name
aws elbv2 describe-load-balancers --names ticketpulse-alb \
  --query 'LoadBalancers[0].DNSName' --output text

# Hit it
curl -s https://<ALB_DNS_NAME>/health | jq .
# Expected: {"status": "ok", "region": "us-east-1"}

# Try the events endpoint
curl -s https://<ALB_DNS_NAME>/api/events | jq .
```

### 📊 Observe: AWS Console Dashboards

Open the AWS Console and explore:
- **ECS → Clusters → your cluster:** See running tasks, CPU/memory utilization.
- **CloudWatch → Log groups → /ecs/ticketpulse-api:** See application logs from all tasks.
- **EC2 → Load Balancers → your ALB:** See request count, latency, HTTP error rates.
- **RDS → your instance:** See connections, IOPS, CPU, storage.

---

## 2. GCP Path: Deploy TicketPulse to Cloud Run (35 minutes)

### Prerequisites

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Initialize and authenticate
gcloud init
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  pubsub.googleapis.com \
  artifactregistry.googleapis.com
```

### Step 1: Push Your Container Image

```bash
# Create an Artifact Registry repository
gcloud artifacts repositories create ticketpulse \
  --repository-format=docker \
  --location=us-central1

# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Tag and push
docker tag ticketpulse-api:latest \
  us-central1-docker.pkg.dev/YOUR_PROJECT/ticketpulse/api:latest

docker push \
  us-central1-docker.pkg.dev/YOUR_PROJECT/ticketpulse/api:latest
```

### Step 2: Deploy to Cloud Run

```bash
# Deploy (this is the entire deployment command)
gcloud run deploy ticketpulse-api \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/ticketpulse/api:latest \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=80 \
  --port=8080 \
  --set-env-vars="NODE_ENV=production"
```

That is it. Cloud Run gives you:
- A public HTTPS URL with a managed TLS certificate.
- Auto-scaling from 0 to 10 instances based on traffic.
- Built-in load balancing and health checks.
- Request logging in Cloud Logging.

Compare this with the AWS path. The ECS deployment required a VPC, subnets, security groups, an ALB, a target group, a task definition, and a service. Cloud Run abstracts all of that away.

### Step 3: Set Up Cloud SQL

```bash
# Create a Cloud SQL PostgreSQL instance
gcloud sql instances create ticketpulse-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create the database
gcloud sql databases create ticketpulse \
  --instance=ticketpulse-db

# Set the password
gcloud sql users set-password postgres \
  --instance=ticketpulse-db \
  --password=YOUR_SECURE_PASSWORD

# Connect Cloud Run to Cloud SQL
gcloud run services update ticketpulse-api \
  --add-cloudsql-instances=YOUR_PROJECT:us-central1:ticketpulse-db \
  --set-env-vars="DATABASE_URL=postgresql://postgres:YOUR_SECURE_PASSWORD@/ticketpulse?host=/cloudsql/YOUR_PROJECT:us-central1:ticketpulse-db"
```

### 🔍 Try It: Hit Your Live Endpoint

```bash
# Get the Cloud Run URL
gcloud run services describe ticketpulse-api \
  --region=us-central1 \
  --format='value(status.url)'

# Hit it
curl -s https://ticketpulse-api-xxxxx-uc.a.run.app/health | jq .

# Try the events endpoint
curl -s https://ticketpulse-api-xxxxx-uc.a.run.app/api/events | jq .
```

### 📊 Observe: GCP Console Dashboards

Open the Google Cloud Console:
- **Cloud Run → ticketpulse-api:** See request count, latency percentiles, container instance count, memory usage.
- **Cloud Logging → Logs Explorer:** Filter by `resource.type="cloud_run_revision"` to see application logs.
- **Cloud SQL → ticketpulse-db:** See connections, CPU, storage, query insights.

---

## 3. Compare the Platforms (10 minutes)

### 📐 Design Exercise: Side-by-Side Comparison

Now that you have deployed (or walked through deploying) on at least one platform, fill in this comparison based on your experience:

| Dimension | AWS (ECS/Fargate) | GCP (Cloud Run) |
|---|---|---|
| **Time to first deploy** | ??? | ??? |
| **Number of resources created** | ??? | ??? |
| **Networking complexity** | ??? | ??? |
| **Console experience** | ??? | ??? |
| **Log access** | ??? | ??? |
| **What surprised you** | ??? | ??? |
| **What annoyed you** | ??? | ??? |

### Reference Comparison

| Dimension | AWS (ECS/Fargate) | GCP (Cloud Run) |
|---|---|---|
| **Time to first deploy** | 30-60 min (VPC, ALB, ECS setup) | 5-10 min (single deploy command) |
| **Resources created** | ~15 (VPC, subnets, IGW, NAT, SGs, ALB, TG, ECS cluster, task def, service, IAM roles, log groups) | ~3 (Cloud Run service, Artifact Registry image, IAM) |
| **Networking** | You build the VPC, subnets, and routing. Full control, full responsibility. | Abstracted. VPC connector for private resources. |
| **Scale to zero** | No. Fargate minimum is 1 task. | Yes. Zero cost when no traffic. |
| **Concurrency model** | 1 container = configurable concurrency (you set it in your app) | 1 instance handles up to 1000 concurrent requests |
| **Custom domains + TLS** | You configure ACM certificate + ALB listener | Automatic with `gcloud run domain-mappings` |
| **Price transparency** | Complex (Fargate vCPU-hr + memory-hr + ALB + NAT Gateway + data transfer) | Simpler (per request + CPU time + memory time) |

### 🤔 Reflect

"AWS has more services. GCP is often simpler. Which matters more for your team?"

There is no universal answer. AWS's breadth means you can find a managed service for almost anything. GCP's simplicity means you spend less time on infrastructure and more on your application. Large enterprises with complex compliance requirements often choose AWS. Startups optimizing for developer velocity often choose GCP.

The best cloud is the one your team knows. Switching costs are enormous.

---

## 4. Cost Estimation (15 minutes)

### 📐 Design Exercise: What Would TicketPulse Cost at 1M Users/Month?

Estimate the monthly AWS cost for TicketPulse with these assumptions:
- 1M monthly active users
- 100M API requests/month (~40 requests/second average, ~200 peak)
- 50GB database (PostgreSQL)
- 5GB cache (Redis)
- 10M messages/month through the queue
- 100GB data transfer out/month

**Work through each category before looking at the reference estimate.**

### Reference Cost Estimate (AWS, us-east-1)

| Service | Configuration | Monthly Cost |
|---|---|---|
| **ECS Fargate** | 3 tasks x 0.5 vCPU x 1GB, running 24/7 | ~$110 |
| **ALB** | 1 ALB + 100M requests | ~$30 |
| **RDS PostgreSQL** | db.t3.medium, Multi-AZ, 50GB | ~$140 |
| **ElastiCache Redis** | cache.t3.small, 1 node | ~$50 |
| **SQS** | 10M messages | ~$4 |
| **NAT Gateway** | 1 gateway + 100GB data processed | ~$50 |
| **Data Transfer** | 100GB out to internet | ~$9 |
| **CloudWatch** | Logs + metrics + alarms | ~$20 |
| **ECR** | Image storage | ~$1 |
| **Route 53** | 1 hosted zone + queries | ~$2 |
| **Total** | | **~$416/month** |

### Reference Cost Estimate (GCP, us-central1)

| Service | Configuration | Monthly Cost |
|---|---|---|
| **Cloud Run** | 100M requests, avg 200ms CPU time, 512MB memory | ~$60 |
| **Cloud SQL** | db-custom-2-4096, 50GB SSD | ~$100 |
| **Memorystore Redis** | M1, 1GB | ~$55 |
| **Pub/Sub** | 10M messages | ~$4 |
| **Cloud Load Balancing** | 1 forwarding rule + 100M requests | ~$25 |
| **Data Transfer** | 100GB out to internet | ~$12 |
| **Cloud Logging** | Logs ingestion | ~$10 |
| **Artifact Registry** | Image storage | ~$1 |
| **Total** | | **~$267/month** |

### Key Observations

- GCP is cheaper at this scale primarily because Cloud Run scales to zero and has no NAT Gateway cost.
- AWS's NAT Gateway ($0.045/GB + $0.045/hr) is a notorious hidden cost. Many teams are surprised by their first NAT Gateway bill.
- At higher scale (steady-state traffic, reserved instances), AWS pricing improves significantly. Reserved RDS and Fargate Savings Plans can cut costs 30-60%.
- These estimates exclude: domain registration, SSL certificate (free on both), developer time, and the cost of learning the platform.

### ⚠️ Common Mistake: Leaving Resources Running

Cloud resources cost money every hour they run, whether you are using them or not. After this exercise:

```bash
# AWS: Delete everything
aws ecs update-service --cluster ticketpulse --service ticketpulse-api --desired-count 0
aws ecs delete-service --cluster ticketpulse --service ticketpulse-api
aws rds delete-db-instance --db-instance-identifier ticketpulse-db --skip-final-snapshot
# ... and the VPC, ALB, NAT Gateway, ElastiCache, etc.

# GCP: Delete everything
gcloud run services delete ticketpulse-api --region=us-central1
gcloud sql instances delete ticketpulse-db
# Cloud Run at zero instances costs nothing, but Cloud SQL always costs money
```

**Set a budget alert.** Both platforms support budget alerts that email you when spending exceeds a threshold. Set one at $10 so you are not surprised.

```bash
# AWS: Create a budget (via console is easier, but CLI works)
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget '{"BudgetName":"TicketPulse-Lab","BudgetLimit":{"Amount":"10","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}'

# GCP: Create a budget
# Use the console: Billing → Budgets & alerts → Create budget
```

---

## 4b. Multi-Cloud Comparison Exercises

These exercises build on the AWS and GCP deployments you ran in Sections 1 and 2. They develop the judgment needed to evaluate cloud providers as an architectural decision rather than a vendor preference.

### Exercise 1: Service Equivalence Mapping

Every cloud provider has equivalents for common services, but the behavior differences matter. Fill in the equivalents and note the key behavioral difference for each:

| Capability | AWS | GCP | Azure | Key Behavioral Difference |
|------------|-----|-----|-------|--------------------------|
| Managed Kubernetes | EKS | GKE | AKS | GKE has the most mature managed K8s; EKS gives more VPC control |
| Serverless containers | Fargate | Cloud Run | Container Apps | Cloud Run scales to zero; Fargate minimum is 1 task |
| Managed PostgreSQL | RDS | Cloud SQL | Azure Database for PostgreSQL | RDS supports most instance types; Cloud SQL has better GCP integration |
| Object storage | S3 | Cloud Storage | Blob Storage | S3 is the original; all others are API-compatible |
| Global CDN | CloudFront | Cloud CDN | Azure CDN / Front Door | CloudFront has the most PoPs; Cloud CDN is simpler |
| Message queue | SQS | Pub/Sub | Service Bus | SQS is pull-based; Pub/Sub is push with delivery guarantees |
| Streaming (Kafka) | MSK | Dataflow/Pub/Sub | Event Hubs | MSK is managed Kafka; others are proprietary |
| Secret management | Secrets Manager | Secret Manager | Key Vault | Pricing varies significantly at scale |
| Container registry | ECR | Artifact Registry | Container Registry | Artifact Registry supports more artifact types beyond containers |

**Why this matters**: When a colleague recommends "using Lambda" for something, you need to know whether Cloud Run, Container Apps, or Cloud Functions would be equivalent — or whether the behavioral differences matter for your use case.

### Exercise 2: The Abstraction Ladder

Cloud services exist at different levels of abstraction. Choosing the right level is an architectural decision, not just a configuration choice.

For a PostgreSQL database in TicketPulse, map the options from least to most managed:

```
LEVEL 1: Self-managed
  EC2 instance + PostgreSQL installed manually
  GCP VM + PostgreSQL installed manually

  Control: Full (you manage everything)
  Operational burden: Highest (OS patches, backups, failover, monitoring)
  Cost: Lowest per vCPU
  Best for: Specific PostgreSQL configurations, compliance requirements

LEVEL 2: Managed VMs with data disk
  EC2 + EBS volume (you install PostgreSQL, AWS manages VM)
  GCP Compute Engine + Persistent Disk

  Control: High (you manage PostgreSQL, OS)
  Operational burden: High (but VM maintenance automated)
  Cost: Low
  Best for: Unusual PostgreSQL extensions, custom configs

LEVEL 3: Managed database service
  AWS RDS for PostgreSQL
  GCP Cloud SQL for PostgreSQL
  Azure Database for PostgreSQL

  Control: Medium (you manage schema, queries, connection pooling)
  Operational burden: Low (backups, patching, failover managed)
  Cost: Medium
  Best for: Most production workloads — this is the right default

LEVEL 4: Serverless database
  AWS Aurora Serverless v2
  GCP AlloyDB
  PlanetScale (MySQL-compatible, serverless)
  Neon (PostgreSQL, serverless)

  Control: Low (you manage schema, service manages capacity)
  Operational burden: Minimal
  Cost: Pay per use (can be cheaper for variable loads, expensive for steady state)
  Best for: Variable or unpredictable workloads, development environments

LEVEL 5: Managed distributed database
  AWS Aurora Global Database
  GCP Spanner
  CockroachDB Serverless

  Control: Low (provider manages distribution)
  Operational burden: Minimal
  Cost: Highest per query
  Best for: Multi-region active-active, globally distributed writes
```

**The exercise**: For each of these TicketPulse use cases, choose the right abstraction level and justify it:

1. The main transactional database (orders, tickets) — expected 5,000 writes/minute peak
2. The analytics read store (aggregate reports, business metrics) — expected 10 heavy queries per minute
3. The development/staging environment — used 8 hours/day, idle overnight
4. The global seat availability cache (needs sub-10ms reads from 5 regions)

### Exercise 3: Total Cost of Ownership Comparison

The monthly bill is not the total cost. Calculate the true TCO for TicketPulse across providers, including hidden costs:

```
TCO CATEGORIES:
═══════════════

1. Compute costs (what the calculator shows)
   AWS ECS/Fargate vs GCP Cloud Run vs Azure Container Apps
   → Run the cost calculator with your traffic profile

2. Networking costs (often invisible until the bill arrives)
   - AWS NAT Gateway: $0.045/hr + $0.045/GB processed
     For 100GB/month: ~$33 just for NAT gateway
   - GCP: Egress pricing from Cloud Run to internet
   - Cross-AZ data transfer (AWS charges, GCP mostly does not)

3. Operational costs (engineer-hours)
   - AWS: More complex configurations → more engineer time
   - GCP Cloud Run: Less configuration → less engineer time
   - Estimate: 2h/month vs 6h/month × $75/hr = $150 vs $450
   
4. Incident costs (unreliable platforms cost more)
   - Both AWS and GCP have SLAs of 99.9% or better
   - Difference is usually the operational complexity, not platform reliability

5. Switching costs (if you change your mind)
   - Container images: portable across clouds
   - Managed services (RDS, CloudSQL): data migration required
   - Proprietary services (Pub/Sub, SQS): code changes required
   - IAM, networking: complete re-architecture
   
Rule of thumb: switching cloud providers costs 3-6 months of a platform engineer's time
for a mid-sized system. Factor this into the "GCP is cheaper" calculation.
```

**Your task**: For TicketPulse at 1M users/month, calculate the total 3-year cost for:
- Staying on AWS (current)
- Migrating to GCP (one-time migration cost + ongoing savings)
- Using a multi-cloud setup (managed Kubernetes on your own, cloud-agnostic services)

Which option wins? (Answer: depends on your team's GCP expertise and the migration cost. At small scale, the monthly savings from GCP often do not justify the migration cost. At large scale, they do.)

### Exercise 4: The Multi-Cloud Reality Check

Multi-cloud is often proposed as a strategy. Let's examine it honestly.

**The theoretical benefits of multi-cloud:**
- Avoid vendor lock-in
- Negotiate better pricing (play providers against each other)
- Use the best service from each provider
- Survive a cloud provider outage

**The practical costs of multi-cloud:**
```
1. Operational complexity
   - Two security models to maintain (IAM on AWS AND IAM on GCP)
   - Two monitoring platforms (CloudWatch AND Cloud Monitoring)
   - Two networking models (VPC + peering on AWS, VPC on GCP)
   - Two deployment pipelines
   
2. No managed service harmony
   - Cannot use AWS-specific services (Lambda@Edge, SQS FIFO) if GCP must also work
   - Must use cloud-agnostic tools (Terraform, Kubernetes, open-source Kafka)
   - Cloud-agnostic = you give up the best features of each cloud

3. The "cloud outage" argument
   - Major cloud outages are extremely rare (<1 per year for each provider)
   - When they happen, your multi-cloud setup probably fails too
     (because most outages affect multiple services, not one region)
   - True redundancy requires multi-region within one cloud, not multi-cloud

4. Vendor negotiation
   - Realistic for companies spending $1M+/month
   - Not relevant for most startups
```

**The verdict for TicketPulse:**
- Primary cloud: choose one and commit (AWS or GCP)
- Run Kubernetes so your application layer is portable
- Use Terraform for infrastructure so the configuration is understandable
- Revisit multi-cloud only if spending exceeds $500K/month and you have dedicated platform engineers

### Exercise 5: The Emergency Migration Drill

Your company decided to move from AWS to GCP. You have 90 days. Work through the migration plan:

```
WEEK 1-2: Assessment
  - Inventory all AWS services in use (list them all)
  - Identify which have direct GCP equivalents
  - Identify which are proprietary (will require code changes)
  - Estimate effort for each

WEEK 3-4: GCP Foundation
  - Set up GCP project with billing alerts
  - Configure VPC, subnets, and firewall rules
  - Set up Cloud Run, Cloud SQL, Memorystore, Pub/Sub
  - Configure IAM (mirror AWS IAM structure)

WEEK 5-8: Service Migration
  - Migrate stateless services first (they are easy — just update the container registry and environment variables)
  - Migrate databases last (they are the risky part — data migration required)
  - Run AWS and GCP in parallel for overlap period

WEEK 9-10: Data Migration
  - pg_dump from RDS → restore to Cloud SQL
  - Verify data integrity (row counts, checksums)
  - Test application against GCP database

WEEK 11-12: Cutover
  - DNS cutover from ALB → Cloud Load Balancer
  - Monitor error rates for 48 hours
  - Keep AWS running for 1 week (rollback window)
  - Terminate AWS resources after successful cutover
```

**Key insight**: The containerized application layer (TicketPulse services as Docker images) migrates in a day. The infrastructure configuration (VPC, IAM, networking) takes 2-3 weeks. The data migration is the highest-risk step and takes the longest to verify.

---

## 5. Reflect (5 minutes)

### 🤔 Questions

1. **You need to deploy TicketPulse to production next week. You have never used either cloud platform. Which do you choose and why?**

2. **Your company already runs 50 services on AWS. A new team wants to use GCP because Cloud Run is simpler. What are the arguments for and against?**

3. **The cost estimate shows ~$400/month for 1M users. That is $0.0004 per user per month. At what scale does cloud cost become a significant concern?** (Hint: think about the 10M and 100M user tiers.)

4. **What is missing from our deployment that a production system would need?** (Think: secrets management, CI/CD pipeline, monitoring alerts, database migrations, rollback strategy.)

---

## 6. Checkpoint

After this module, you should have:

- [ ] At least one TicketPulse service deployed to a real cloud provider
- [ ] Successfully hit your live endpoint from the internet (curl or browser)
- [ ] Explored the cloud console dashboards (logs, metrics, resource status)
- [ ] A cost estimate for TicketPulse at 1M users/month on your chosen platform
- [ ] Understanding of the key differences between AWS and GCP for container workloads
- [ ] Budget alert configured (or resources deleted) to avoid surprise charges
- [ ] Answers to all reflect questions

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **AWS ECS/Fargate** | Full control over networking and infrastructure. More configuration, more flexibility. NAT Gateway is a hidden cost trap. |
| **GCP Cloud Run** | Simplest path from container to production. Scale to zero. Less configuration, less control. |
| **Cost at scale** | ~$300-400/month for 1M users. Cloud costs are negligible at small scale, significant at large scale. Reserved pricing changes the math. |
| **Platform choice** | Pick the platform your team knows. Switching costs dominate all other factors. |
| **Budget alerts** | Always set them. Cloud billing surprises are a rite of passage, but they do not have to be. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Fargate** | AWS serverless compute engine for containers. No EC2 instances to manage. Pay per vCPU and memory per second. |
| **Cloud Run** | GCP serverless container platform. Runs any container, scales to zero, pay per request. |
| **ALB** | Application Load Balancer. Routes HTTP/HTTPS traffic to backend targets. Operates at Layer 7. |
| **ECR / Artifact Registry** | Container image registries for AWS (ECR) and GCP (Artifact Registry). |
| **NAT Gateway** | A managed service that allows resources in private subnets to access the internet. Notorious for unexpected costs on AWS. |
| **Cloud SQL** | GCP's managed relational database service supporting PostgreSQL, MySQL, and SQL Server. |
| **ElastiCache** | AWS managed caching service supporting Redis and Memcached. |

---

---

## Cross-References

- **Chapter 19** (AWS Deep Dive): Covers ECS, EKS, RDS, ElastiCache, SQS, CloudWatch, and the IAM permission model in depth beyond what this module covers.
- **Chapter 31** (GCP Deep Dive): Covers Cloud Run, GKE, Cloud SQL, Pub/Sub, and the GCP resource hierarchy and IAM model.
- **L3-M61** (Multi-Region Design): Deploying across multiple cloud regions requires understanding the global networking primitives (CloudFront, Cloud Load Balancing) that this module introduces.

---

## Further Reading

- Chapter 19 of the 100x Engineer Guide: AWS Deep Dive
- Chapter 31 of the 100x Engineer Guide: GCP Deep Dive
- [AWS Free Tier](https://aws.amazon.com/free/) — 12-month and always-free tier details
- [GCP Free Tier](https://cloud.google.com/free) — $300 credit and always-free products
- Corey Quinn, [Last Week in AWS](https://www.lastweekinaws.com/) — entertaining and educational AWS cost analysis

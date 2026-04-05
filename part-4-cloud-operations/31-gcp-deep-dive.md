<!--
  CHAPTER: 31
  TITLE: Google Cloud Platform Deep Dive
  PART: IV — Cloud & Operations
  PREREQS: Chapter 7 (infrastructure concepts), Chapter 13 (system integration)
  KEY_TOPICS: Compute Engine, Cloud Run, GKE, Cloud Functions, VPC, Cloud SQL, Firestore, Spanner, BigQuery, Pub/Sub, Cloud Storage, IAM, Cloud Monitoring, cost optimization
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 31: Google Cloud Platform Deep Dive

> **Part IV — Cloud & Operations** | Prerequisites: Chapter 7, 13 | Difficulty: Intermediate → Advanced

Let's get one thing straight: GCP is not "the other cloud." It's the cloud you reach for when you need the best data warehouse on the planet, the best managed Kubernetes, a database that is simultaneously global and strongly consistent, and a developer experience that treats you like an adult who doesn't want to configure 47 IAM policy documents just to read from S3.

If you've come from AWS (covered in Chapter 19), you'll find GCP refreshingly opinionated. If you've been wrestling with cloud integration patterns from Chapter 13, you'll appreciate how GCP's services were designed to talk to each other without three layers of glue.

GCP's superpowers: BigQuery as the data warehouse that just works, Cloud Run as the thing Heroku should have been, GKE as what happens when the team that invented Kubernetes runs your Kubernetes, and Cloud Spanner as the database that does the theoretically impossible. Google built the most important internal infrastructure in tech — Bigtable, MapReduce, Borg, Dremel — and GCP is what happens when they productize that institutional knowledge for the rest of us.

### In This Chapter
- GCP Core Services Map
- Compute
- Networking
- Storage & Databases
- Messaging & Event-Driven
- Data & Analytics
- Security & IAM
- Developer & Operations Tools
- Cost Optimization
- Architecture Patterns
- GCP vs AWS Comparison

### Related Chapters
- Ch 19 (AWS & Firebase — comparison)
- Ch 7 (infrastructure concepts)
- Ch 13 (cloud system integration)

---

## 1. GCP CORE SERVICES MAP

### 1.1 The 15-20 Services That Matter Most

GCP has ~100+ services, but here's the honest truth: the same 20 services cover 95% of what you'll run in production. Everything else is either niche, legacy, or an alias for something on this list.

| Category | GCP Service | AWS Equivalent | What It Does |
|---|---|---|---|
| **Compute** | Compute Engine | EC2 | Virtual machines |
| | Cloud Run | Fargate + Lambda | Serverless containers (GCP's star) |
| | GKE | EKS | Managed Kubernetes (the best) |
| | Cloud Functions | Lambda | Event-driven functions |
| | App Engine | Elastic Beanstalk | Original PaaS |
| **Networking** | VPC / Cloud Load Balancing | VPC / ALB+NLB | Networking and traffic routing |
| | Cloud CDN / Cloud DNS | CloudFront / Route 53 | CDN and DNS |
| | Cloud Armor | AWS WAF | WAF and DDoS protection |
| **Storage** | Cloud Storage | S3 | Object storage |
| **Databases** | Cloud SQL | RDS | Managed relational databases |
| | AlloyDB | Aurora | High-performance PostgreSQL |
| | Cloud Spanner | DynamoDB Global Tables | Globally consistent relational DB |
| | Firestore | DynamoDB | Document database |
| | Bigtable | — (HBase-like) | Wide-column store for massive scale |
| | Memorystore | ElastiCache | Managed Redis / Memcached |
| **Messaging** | Pub/Sub | SQS + SNS | Message queue / pub-sub |
| | Eventarc | EventBridge | Event routing |
| | Cloud Tasks | SQS (with rate limiting) | Task queues |
| **Data** | BigQuery | Redshift | Serverless data warehouse (GCP's crown jewel) |
| | Dataflow | Kinesis + Glue | Stream and batch processing (Apache Beam) |
| **Security** | IAM / Secret Manager | IAM / Secrets Manager | Identity, secrets |
| **Observability** | Cloud Monitoring / Logging | CloudWatch | Metrics, logs, alerting |
| **CI/CD** | Cloud Build | CodePipeline | Build and deploy |

A note on the AWS equivalents: they're approximations. Cloud Run is not Fargate — it's significantly simpler. BigQuery is not Redshift — it's in a different league for ad-hoc analytics. Cloud Spanner has no real AWS equivalent; DynamoDB Global Tables gets lumped in, but they're solving different problems. Keep that nuance in mind as you read.

### 1.2 How They Connect

```
                         Cloud DNS
                             |
                     Cloud Load Balancing + Cloud CDN
                             |
                    +--------+--------+
                    |                 |
               Cloud Run          GKE / Compute Engine
                    |                 |
            +-------+-------+   +----+----+
            |       |       |   |         |
         Firestore Pub/Sub  Cloud  Cloud SQL / Memorystore
                    |       Storage  AlloyDB / Spanner
                    |
              Cloud Run / Cloud Functions (consumer)
                    |
              Eventarc (fan-out)
                    |
                BigQuery (analytics sink)
```

This diagram captures a pattern you'll use constantly on GCP: Cloud Run at the center, Cloud SQL or Spanner for persistence, Pub/Sub for async decoupling, and BigQuery as the analytics sink where everything eventually ends up. Compare this with the AWS architecture patterns in Chapter 13 — the shape is similar, but GCP's managed services handle a lot more of the glue automatically.

### 1.3 GCP Naming Conventions

GCP naming is more consistent than AWS (no more guessing whether it's "Lambda" or "Functions" or "Lambdas"). Here's the pattern:

- **"Cloud"** prefix = GCP-managed service: Cloud Run, Cloud SQL, Cloud Storage, Cloud Functions
- **"Google Kubernetes Engine"** = GKE (always abbreviated, because saying "Google Kubernetes Engine" every time is exhausting)
- **Products without "Cloud"** = standalone brands: BigQuery, Spanner, Bigtable, Firestore, Pub/Sub — these are famous enough to stand alone
- **"Vertex AI"** = the ML/AI platform (covers training, prediction, MLOps, and the kitchen sink)
- **"AlloyDB"** = PostgreSQL-compatible, high-performance DB — GCP's Aurora equivalent, and arguably better for HTAP workloads

The "Cloud" prefix thing trips up newcomers because Cloud Run and Cloud Functions sound similar. Remember: Cloud Run = containers, Cloud Functions = source code. Once you know that, most GCP naming clicks into place.

---

## 2. COMPUTE

### 2.1 Compute Engine (Virtual Machines)

The equivalent of EC2, but with one feature that made me stop and blink the first time I saw it: **custom machine types**. Instead of picking from fixed instance sizes (t3.medium, m5.xlarge, etc.), you specify the exact number of vCPUs and GBs of RAM you need. Need 6 vCPUs and 20 GB? Done. AWS will sell you 8 vCPUs and 32 GB and tell you to be grateful.

This sounds like a minor convenience but it's actually meaningful for cost optimization. Right-sizing on AWS means choosing from a menu. Right-sizing on GCP means telling it exactly what you need.

**Machine families:**

| Family | Use Case | Example |
|---|---|---|
| **General-purpose (E2, N2, N2D, N4)** | Web servers, small-to-medium DBs, dev/test | `e2-medium` (2 vCPU, 4 GB) |
| **Compute-optimized (C2, C2D, C3, H3)** | Batch processing, HPC, game servers | `c2-standard-8` (8 vCPU, 32 GB) |
| **Memory-optimized (M1, M2, M3)** | In-memory databases, SAP HANA | `m2-ultramem-416` (416 vCPU, 12 TB) |
| **Accelerator-optimized (A2, A3, G2)** | ML training/inference, GPU workloads | `a2-highgpu-1g` (1 A100 GPU) |
| **Custom machine types** | Anything in between | You pick: 6 vCPU + 24 GB RAM |

For most web workloads, start with E2 — it's the cheapest and performs surprisingly well. Graduate to N2 or C2 when you need more predictable performance or raw CPU power.

**Preemptible / Spot VMs:**

```bash
# Create a spot VM (up to 91% discount, can be reclaimed with 30s notice)
gcloud compute instances create my-worker \
  --zone=us-central1-a \
  --machine-type=e2-standard-4 \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP

# List current spot prices (there are no fixed prices — it's capacity-based)
# Spot VMs are typically 60-91% cheaper than on-demand
```

Spot VMs are the equivalent of AWS Spot Instances but with a different model — GCP doesn't have bidding, it's purely capacity-based. In practice, preemption rates are low for most regions and instance types during off-peak hours. For fault-tolerant batch workloads (ML training, data processing), these are basically free money.

**Committed Use Discounts (CUDs):**
- 1-year commitment: ~37% discount
- 3-year commitment: ~55% discount
- Resource-based (vCPU + memory) or machine-type-based
- Unlike AWS Reserved Instances, GCP CUDs are more flexible — they apply to any machine type in the same family, not a specific instance type in a specific region

That flexibility is real. On AWS, if you buy an m5.xlarge RI and decide you need an m5.2xlarge, you're stuck. GCP CUDs commit to compute resources, not specific machine types, so you can resize without losing your discount.

**Managed Instance Groups (MIGs):**

```bash
# Create an instance template
gcloud compute instance-templates create web-template \
  --machine-type=e2-medium \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --tags=http-server

# Create a managed instance group with autoscaling
gcloud compute instance-groups managed create web-mig \
  --zone=us-central1-a \
  --template=web-template \
  --size=2

gcloud compute instance-groups managed set-autoscaling web-mig \
  --zone=us-central1-a \
  --min-num-replicas=2 \
  --max-num-replicas=10 \
  --target-cpu-utilization=0.6
```

MIGs are Compute Engine's Auto Scaling Groups (ASGs). They're fine, but if you're building something new, consider Cloud Run first. You'll write a lot less infrastructure code.

### 2.2 Cloud Run (The Thing Heroku Should Have Been)

Cloud Run is GCP's most compelling compute service, full stop. I'll admit some bias here: the first time I `gcloud run deploy`'d a container and had a public HTTPS URL in 90 seconds with automatic TLS, zero-config autoscaling from zero to thousands, and a billing model that charges me nothing when nobody's using it — I understood why people choose GCP.

It runs any container, any language, scales to zero, and you pay only when handling requests. It's what Lambda would be if Lambda could run arbitrary containers — and what Heroku would be if Heroku had survived into the age of Kubernetes.

**Why Cloud Run is special:**
- **Any container, any language** — no runtime restrictions like Lambda (which still doesn't support arbitrary binaries without workarounds)
- **Scale to zero** — no cost when idle (unlike ECS/Fargate which always bills for minimum tasks)
- **Scale to thousands** — handles traffic spikes automatically with no provisioning
- **Pay per request** — billed per 100ms of CPU time actually used
- **No infrastructure to manage** — no clusters, no nodes, no patches, no capacity planning
- **Concurrency** — each instance handles up to 1000 concurrent requests (vs Lambda's 1 per instance — a huge difference for bursty traffic)

```bash
# Deploy a container to Cloud Run (this is the entire deployment)
gcloud run deploy my-service \
  --image=gcr.io/my-project/my-app:latest \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=100 \
  --concurrency=80

# Deploy from source code (Cloud Run builds it for you using Buildpacks)
gcloud run deploy my-service \
  --source=. \
  --region=us-central1

# Set environment variables
gcloud run services update my-service \
  --set-env-vars="DB_HOST=10.0.0.1,REDIS_URL=redis://10.0.0.2:6379"

# Connect to a VPC (for accessing Cloud SQL, Memorystore, etc.)
gcloud run services update my-service \
  --vpc-connector=my-connector \
  --vpc-egress=private-ranges-only

# Map a custom domain
gcloud run domain-mappings create \
  --service=my-service \
  --domain=api.example.com \
  --region=us-central1
```

That `--source=.` flag deserves special mention. Cloud Run uses Buildpacks (Google's open-source build system) to automatically detect your language, install dependencies, and package your app into a container. No Dockerfile required. You can go from "code on my laptop" to "running in production" with a single command and no Docker knowledge. That's a powerful onramp.

**When to use Cloud Run vs GKE vs Cloud Functions:**

| Factor | Cloud Run | GKE | Cloud Functions |
|---|---|---|---|
| **Best for** | APIs, web apps, microservices | Complex multi-service systems | Event handlers, glue code |
| **Container** | Any Docker container | Any K8s pod | Source code only |
| **Scale to zero** | Yes | No (unless using Knative) | Yes |
| **Max request duration** | 60 min | Unlimited | 9 min (1st gen) / 60 min (2nd gen) |
| **Concurrency** | Up to 1000 per instance | Unlimited (you control pods) | 1 per instance (1st gen) / configurable (2nd gen) |
| **Networking** | VPC connector | Full VPC native | VPC connector |
| **Cost model** | Per request + CPU time | Per node (always on) | Per invocation + CPU time |
| **Complexity** | Low | High | Low |
| **Choose when** | Default choice for most workloads | Need K8s features, stateful sets, service mesh | Simple event triggers, lightweight |

**Rule of thumb:** Start with Cloud Run. Move to GKE only if you need Kubernetes-specific features (StatefulSets, DaemonSets, service mesh, complex scheduling). Use Cloud Functions for simple event-driven glue. You can always migrate from Cloud Run to GKE later — it's just containers — but you'll find that most workloads never need to make that jump.

**GCP vs AWS honest take:** Cloud Run beats Fargate for simplicity by a wide margin. Fargate still requires you to define task definitions, services, clusters, and a load balancer separately. Cloud Run is genuinely one command. If your AWS instinct is to reach for Lambda for everything, Cloud Run is the GCP answer — but better for long-running requests, higher concurrency, and arbitrary containers.

### 2.3 GKE (Google Kubernetes Engine)

GKE is widely considered the best managed Kubernetes service, and it's not a close race. Google literally invented Kubernetes (it's a productization of their internal Borg system), and the institutional knowledge shows up in ways that matter: tighter integration with the autoscaler, more stable upgrades, and — the real differentiator — **Autopilot mode**.

Autopilot eliminates node management entirely. You tell GKE what pods you need; Google figures out the nodes. You never think about VM sizes, node pool capacity, or cluster autoscaler configuration. You just deploy workloads and pay per pod.

**Autopilot vs Standard mode:**

| Feature | Autopilot | Standard |
|---|---|---|
| **Node management** | Google manages nodes | You manage node pools |
| **Pricing** | Per pod (vCPU + memory + ephemeral storage) | Per node (VM pricing) |
| **Security** | Hardened by default (no SSH, no privileged containers) | You configure |
| **Scaling** | Automatic pod + node scaling | You configure node autoscaler |
| **GPU support** | Yes | Yes |
| **Best for** | Most workloads (recommended default) | Custom kernel modules, specific node configs |

```bash
# Create a GKE Autopilot cluster (recommended)
gcloud container clusters create-auto my-cluster \
  --region=us-central1 \
  --release-channel=regular

# Create a GKE Standard cluster
gcloud container clusters create my-cluster \
  --region=us-central1 \
  --num-nodes=3 \
  --machine-type=e2-standard-4 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10

# Get credentials for kubectl
gcloud container clusters get-credentials my-cluster \
  --region=us-central1

# Deploy a workload
kubectl apply -f deployment.yaml

# Use spot pods for batch workloads (GKE Standard)
# In your node pool:
gcloud container node-pools create spot-pool \
  --cluster=my-cluster \
  --region=us-central1 \
  --spot \
  --machine-type=e2-standard-4 \
  --num-nodes=0 \
  --enable-autoscaling \
  --min-nodes=0 \
  --max-nodes=20
```

**Why GKE beats EKS:**
- **Autopilot** removes node management entirely — EKS has no equivalent (Fargate for EKS is close but more constrained)
- **Node auto-provisioning** in Standard mode automatically selects machine types based on your pod requirements
- **Cluster autoscaler** is deeply integrated, not a separate add-on you configure and hope works
- **Binary Authorization** enforces deploy-time security policies (only signed images from your registry)
- **GKE multi-cluster** with fleet management (Anthos) for organizations running multiple clusters
- **Cost optimization** with spot pods, autoscaling, and right-sizing recommendations baked in
- **Upgrades** are automatic and zero-downtime — EKS upgrades are a semi-annual adventure

If you're running Kubernetes and not on GKE, you're carrying costs and operational burden you don't need to carry.

### 2.4 Cloud Functions (2nd Gen)

Cloud Functions 2nd gen is built on Cloud Run under the hood. That means it inherits Cloud Run's superpower set: longer timeouts, higher concurrency, traffic splitting, and support for container images. The main thing Cloud Functions adds over raw Cloud Run is trigger-based invocation wired directly to GCP services with zero configuration.

**Triggers:**

```bash
# HTTP trigger
gcloud functions deploy hello-http \
  --gen2 \
  --runtime=nodejs20 \
  --trigger-http \
  --allow-unauthenticated \
  --region=us-central1 \
  --source=. \
  --entry-point=helloHttp

# Pub/Sub trigger
gcloud functions deploy process-message \
  --gen2 \
  --runtime=python312 \
  --trigger-topic=my-topic \
  --region=us-central1 \
  --source=. \
  --entry-point=process_message

# Cloud Storage trigger (file upload)
gcloud functions deploy process-upload \
  --gen2 \
  --runtime=go122 \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=my-bucket" \
  --region=us-central1 \
  --source=. \
  --entry-point=ProcessUpload

# Firestore trigger (document change)
gcloud functions deploy on-user-create \
  --gen2 \
  --runtime=nodejs20 \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=(default)" \
  --trigger-event-filters-path-pattern="document=users/{userId}" \
  --region=us-central1 \
  --source=. \
  --entry-point=onUserCreate
```

**Cloud Functions vs AWS Lambda:**

| Feature | Cloud Functions (2nd gen) | AWS Lambda |
|---|---|---|
| **Max timeout** | 60 minutes | 15 minutes |
| **Concurrency** | Configurable (up to 1000) | 1 per instance |
| **Min instances** | Yes (keep warm) | Yes (provisioned concurrency) |
| **Container images** | Yes (via Cloud Run) | Yes |
| **Traffic splitting** | Yes (canary deploys) | Weighted aliases |
| **VPC access** | VPC connector | VPC config |

The 60-minute timeout vs Lambda's 15 minutes matters more than it sounds. Long-running data processing, ML inference pipelines, and video processing workflows regularly hit Lambda's ceiling and require awkward chunking workarounds. Cloud Functions 2nd gen just... handles it.

### 2.5 App Engine

The original PaaS — predates Lambda, Cloud Run, and most modern serverless. Two environments:

- **Standard** — sandbox with auto-scaling to zero, limited runtimes (Python, Java, Node.js, Go, PHP, Ruby). Fast cold starts. Best for simple web apps.
- **Flexible** — runs Docker containers on VMs. Does not scale to zero. Largely superseded by Cloud Run.

**When App Engine still makes sense:** Legacy apps already running on it, or very simple apps where you want zero-config deployment with `gcloud app deploy`. For anything new, Cloud Run is almost always the better choice — more flexible, cheaper, and simpler to reason about.

```bash
# Deploy an App Engine app
gcloud app deploy app.yaml --project=my-project

# app.yaml (Standard environment)
# runtime: python312
# instance_class: F2
# automatic_scaling:
#   min_instances: 0
#   max_instances: 10
#   target_cpu_utilization: 0.65
```

If you're starting fresh and considering App Engine Standard for its "simplicity," redirect that energy toward Cloud Run. The learning curve is almost identical, and Cloud Run is more capable in every dimension that matters for production.

---

## 3. NETWORKING

### 3.1 VPC (Virtual Private Cloud)

Here's where GCP's design philosophy diverges sharply from AWS, and it's a pleasant divergence: **GCP VPCs are global by default**. One VPC spans every region. Subnets are regional. This means multi-region architectures don't require VPC peering, Transit Gateways, or any of the infrastructure gymnastics that multi-region AWS setups demand.

On AWS, if you want a VM in us-east-1 and another in eu-west-1 to talk privately, you need VPC peering or Transit Gateway between two separate VPCs. On GCP, they're already in the same VPC — you just create subnets in each region. It sounds like a small thing until you're architecting a global app and you realize you've eliminated an entire category of networking complexity.

```bash
# Create a VPC with custom subnets
gcloud compute networks create my-vpc \
  --subnet-mode=custom

# Create subnets in different regions — same VPC, naturally
gcloud compute networks subnets create us-subnet \
  --network=my-vpc \
  --region=us-central1 \
  --range=10.0.1.0/24

gcloud compute networks subnets create eu-subnet \
  --network=my-vpc \
  --region=europe-west1 \
  --range=10.0.2.0/24

# Firewall rules (GCP uses network-level firewall rules, not per-instance security groups)
gcloud compute firewall-rules create allow-http \
  --network=my-vpc \
  --allow=tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=http-server

gcloud compute firewall-rules create allow-internal \
  --network=my-vpc \
  --allow=tcp,udp,icmp \
  --source-ranges=10.0.0.0/16
```

**Key networking concepts:**

- **Shared VPC** — one VPC shared across multiple projects in an organization. The host project owns the network, service projects deploy resources into it. This is the recommended pattern for enterprise GCP and maps conceptually to AWS Organizations with RAM (Resource Access Manager), but is cleaner to implement.
- **VPC Peering** — connects two VPCs (even across organizations). Non-transitive — which is a known pain point, but less of an issue when you're using Shared VPC properly.
- **Private Google Access** — allows VMs without external IPs to reach Google APIs (Cloud Storage, BigQuery, etc.) over the internal network. No NAT gateway needed. This is a meaningful cost and security win.

### 3.2 Cloud Load Balancing

AWS has ALB, NLB, and CLB — three separate products with different feature sets, pricing, and configuration models. Choosing the wrong one is a common mistake with consequences. GCP simplifies this: there's one load balancing product with different configurations.

| Type | Scope | Protocol | Use Case |
|---|---|---|---|
| **External HTTP(S)** | Global | HTTP/HTTPS | Web apps, APIs (integrates with Cloud CDN) |
| **External TCP/UDP** | Regional or Global | TCP/UDP | Non-HTTP traffic, gaming |
| **Internal HTTP(S)** | Regional | HTTP/HTTPS | Internal microservices |
| **Internal TCP/UDP** | Regional | TCP/UDP | Internal non-HTTP traffic |

```bash
# The global HTTP(S) load balancer is the most common
# It provides: global anycast IP, SSL termination, Cloud CDN, Cloud Armor integration

# For Cloud Run services, you get a load balancer automatically
# For custom setups:
gcloud compute backend-services create my-backend \
  --global \
  --protocol=HTTP \
  --health-checks=my-health-check

gcloud compute url-maps create my-lb \
  --default-service=my-backend

gcloud compute target-https-proxies create my-proxy \
  --url-map=my-lb \
  --ssl-certificates=my-cert

gcloud compute forwarding-rules create my-frontend \
  --global \
  --target-https-proxy=my-proxy \
  --ports=443
```

The global anycast IP is worth calling out: users anywhere in the world connect to the same IP, but their traffic is routed to the nearest Google point of presence. This is the same infrastructure that serves Google Search and YouTube. Your app gets that network as a first-class customer.

### 3.3 Other Networking Services

- **Cloud CDN** — integrated with the HTTP(S) load balancer. One checkbox to enable. Caches at Google's edge network — the same network that serves YouTube and Google Search. Not as many edge locations as CloudFront (AWS wins on raw PoP count), but the network quality is exceptional.
- **Cloud DNS** — managed DNS. Supports DNSSEC, private zones (internal DNS for your VPC). Comparable to Route 53, but Route 53 has more routing policies (latency-based, health-checked failover, geolocation).
- **Cloud Armor** — WAF and DDoS protection. Attach security policies to the load balancer. Supports IP allowlisting/blocklisting, geo-based rules, rate limiting, pre-configured WAF rules (OWASP Top 10). On par with AWS WAF feature-for-feature.
- **Cloud NAT** — managed NAT gateway for VMs without external IPs. No EC2 instance running as a NAT gateway — it's a fully managed, autoscaling service.
- **Private Service Connect** — like AWS PrivateLink. Private endpoints to Google services or your own services without traversing the public internet.
- **Cloud Interconnect** — dedicated physical connection to Google's network (10/100 Gbps). For enterprises with on-prem datacenters who need predictable bandwidth and latency.
- **Cloud VPN** — IPsec VPN tunnels to connect on-prem or other clouds. HA VPN provides 99.99% SLA with two redundant tunnels.

```bash
# Cloud Armor: create a security policy
gcloud compute security-policies create my-policy

# Block a country
gcloud compute security-policies rules create 1000 \
  --security-policy=my-policy \
  --expression="origin.region_code == 'XX'" \
  --action=deny-403

# Rate limiting
gcloud compute security-policies rules create 2000 \
  --security-policy=my-policy \
  --expression="true" \
  --action=throttle \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow \
  --exceed-action=deny-429

# Attach to a backend service
gcloud compute backend-services update my-backend \
  --security-policy=my-policy \
  --global
```

---

## 4. STORAGE & DATABASES

### 4.1 Cloud Storage (Object Storage)

The equivalent of S3. Stores objects (files) in buckets with four storage classes. The API, the mental model, and the use cases are essentially identical to S3 — which is either comforting or boring depending on your perspective. What GCP does differently is the pricing model for retrieval: Nearline, Coldline, and Archive are genuinely cheaper than S3 Glacier equivalents, and the minimum storage duration requirements are cleaner to reason about.

| Class | Access Pattern | Min Storage Duration | Price (us-central1, per GB/mo) | Use Case |
|---|---|---|---|---|
| **Standard** | Frequent | None | ~$0.020 | Hot data, serving assets |
| **Nearline** | Monthly | 30 days | ~$0.010 | Backups accessed monthly |
| **Coldline** | Quarterly | 90 days | ~$0.004 | Disaster recovery |
| **Archive** | Yearly | 365 days | ~$0.0012 | Compliance, long-term archive |

```bash
# Create a bucket
gcloud storage buckets create gs://my-bucket \
  --location=us-central1 \
  --default-storage-class=standard

# Upload files
gcloud storage cp local-file.txt gs://my-bucket/
gcloud storage cp -r local-dir/ gs://my-bucket/dir/

# Set lifecycle policy (move to Nearline after 30 days, delete after 365)
cat > lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
      "condition": {"age": 30, "matchesStorageClass": ["STANDARD"]}
    },
    {
      "action": {"type": "Delete"},
      "condition": {"age": 365}
    }
  ]
}
EOF
gcloud storage buckets update gs://my-bucket --lifecycle-file=lifecycle.json

# Generate a signed URL (temporary access without authentication)
gcloud storage sign-url gs://my-bucket/private-file.pdf \
  --duration=1h \
  --private-key-file=service-account-key.json
```

One practical advantage over S3: Cloud Storage is natively integrated with BigQuery. You can query files directly in Cloud Storage using BigQuery without loading them first. That `SELECT * FROM gs://my-bucket/data/*.parquet` capability makes Cloud Storage the natural landing zone for a GCP data platform.

### 4.2 Cloud SQL

Managed PostgreSQL, MySQL, and SQL Server. Comparable to AWS RDS — and this is one category where the comparison is genuinely close. Both are solid. Cloud SQL has excellent Cloud Run integration (more on that in a moment) and IAM-based authentication that AWS RDS only added much more recently.

```bash
# Create a PostgreSQL instance
gcloud sql instances create my-db \
  --database-version=POSTGRES_16 \
  --tier=db-custom-2-8192 \
  --region=us-central1 \
  --availability-type=REGIONAL \
  --storage-size=100GB \
  --storage-auto-increase

# Create a database
gcloud sql databases create myapp --instance=my-db

# Create a user
gcloud sql users create myuser \
  --instance=my-db \
  --password=supersecret

# Connect via Cloud SQL Auth Proxy (recommended — no public IP needed)
# Install: https://cloud.google.com/sql/docs/postgres/sql-proxy
cloud-sql-proxy my-project:us-central1:my-db &
psql "host=127.0.0.1 port=5432 user=myuser dbname=myapp"

# Create a read replica
gcloud sql instances create my-db-replica \
  --master-instance-name=my-db \
  --region=us-central1

# Enable IAM database authentication (passwordless, uses service account)
gcloud sql instances patch my-db \
  --database-flags=cloudsql.iam_authentication=on
```

**Cloud SQL + Cloud Run (common pattern):**

Cloud Run has native Cloud SQL integration — no VPC connector needed, just a flag. This is one of those GCP design decisions that saves you real time:

```bash
gcloud run deploy my-api \
  --image=gcr.io/my-project/my-api:latest \
  --add-cloudsql-instances=my-project:us-central1:my-db \
  --set-env-vars="DB_HOST=/cloudsql/my-project:us-central1:my-db,DB_USER=myuser,DB_NAME=myapp"
```

The Auth Proxy runs as a sidecar automatically. No VPN, no public IP on the database, no security group configuration. Compare this to the AWS equivalent: RDS in a private subnet, Lambda VPC config, security groups, subnet routing... it's not complicated, but it's a lot of steps.

### 4.3 AlloyDB

GCP's answer to Amazon Aurora. PostgreSQL-compatible and genuinely impressive for mixed workloads:
- Up to 4x better performance than standard Cloud SQL PostgreSQL on OLTP workloads
- **Columnar engine** for analytics queries (OLAP) on the same database handling OLTP — true HTAP without maintaining a separate analytical database
- AI/ML integrations (vector embeddings, model inference inside SQL via pgvector extensions)
- 99.99% SLA with regional HA

**When to choose AlloyDB over Cloud SQL:**
- High-performance OLTP workloads (high-throughput writes, many concurrent connections)
- Mixed OLTP + analytics (HTAP) — the columnar engine handles analytics without a separate warehouse for smaller datasets
- Need for vector search (pgvector on steroids — AlloyDB's vector support is first-class)
- When you'd reach for Aurora on AWS

**GCP vs AWS honest take:** AlloyDB vs Aurora is a genuine competition. Aurora is more mature and has a larger ecosystem. AlloyDB's HTAP story (columnar engine in the same DB) is more compelling than Aurora's, and the pgvector performance on AlloyDB is measurably better for ML workloads.

```bash
# Create an AlloyDB cluster
gcloud alloydb clusters create my-cluster \
  --region=us-central1 \
  --password=supersecret

# Create the primary instance
gcloud alloydb instances create my-primary \
  --cluster=my-cluster \
  --region=us-central1 \
  --instance-type=PRIMARY \
  --cpu-count=4
```

### 4.4 Cloud Spanner

Let me be direct about what Spanner is: it's the database that does the thing the CAP theorem says you can't do. It's globally distributed, strongly consistent, and fully relational (with JOINs, secondary indexes, foreign keys, and ACID transactions). This is not marketing — it's the result of TrueTime (atomic clocks and GPS receivers in every Google datacenter) providing external consistency across the planet.

No other cloud database offers this combination. DynamoDB Global Tables offers eventual consistency for global replication. Cosmos DB offers configurable consistency but not the relational model. Spanner is unique.

**When to use Spanner:**
- Global applications needing consistent reads/writes across regions (financial systems, inventory management, gaming leaderboards where you cannot afford stale reads)
- When you need relational semantics (JOINs, secondary indexes, schema enforcement) at global scale — something you cannot get from DynamoDB
- When eventual consistency is unacceptable and your data is inherently global

**When NOT to use Spanner:**
- Single-region applications (Cloud SQL or AlloyDB is far cheaper — and Spanner's overhead isn't worth it)
- Simple key-value lookups (Firestore or Bigtable is cheaper and simpler)
- Analytics (BigQuery is far better suited and much cheaper)
- Cost-sensitive projects — Spanner starts at ~$0.90/node/hr (minimum 1 node = ~$650/month), so it's not a dev database

**Schema design (critical for performance — get this wrong and you'll be sorry):**

```sql
-- BAD: auto-incrementing primary key causes hotspots
-- All writes go to the same node (the one owning the highest key range)
CREATE TABLE Orders (
  OrderId INT64 NOT NULL,  -- Sequential = hotspot!
  ...
) PRIMARY KEY (OrderId);

-- GOOD: UUIDs or hash-prefixed keys distribute writes evenly
CREATE TABLE Orders (
  OrderId STRING(36) NOT NULL,  -- UUID
  CustomerId STRING(36) NOT NULL,
  OrderDate TIMESTAMP NOT NULL,
  ...
) PRIMARY KEY (OrderId);

-- GOOD: Interleaved tables (co-locate parent + child rows for fast JOINs)
CREATE TABLE Customers (
  CustomerId STRING(36) NOT NULL,
  Name STRING(100),
  ...
) PRIMARY KEY (CustomerId);

CREATE TABLE Orders (
  CustomerId STRING(36) NOT NULL,
  OrderId STRING(36) NOT NULL,
  OrderDate TIMESTAMP NOT NULL,
  ...
) PRIMARY KEY (CustomerId, OrderId),
  INTERLEAVE IN PARENT Customers ON DELETE CASCADE;
-- Now Customer + their Orders are stored together on the same node
-- JOINs between them don't cross node boundaries
```

The interleaving concept is Spanner-specific and powerful. In a normal distributed database, a JOIN between Customers and Orders might cross nodes, adding network latency. Interleaving ensures that a customer's data and all their orders are stored together, making those JOINs fast.

```bash
# Create a Spanner instance
gcloud spanner instances create my-instance \
  --config=regional-us-central1 \
  --nodes=1 \
  --description="Production Spanner"

# Multi-region config (global consistency)
gcloud spanner instances create my-global-instance \
  --config=nam-eur-asia1 \
  --nodes=3 \
  --description="Global Spanner"

# Create a database
gcloud spanner databases create my-db \
  --instance=my-instance \
  --ddl='CREATE TABLE Users (UserId STRING(36) NOT NULL, Name STRING(100)) PRIMARY KEY (UserId)'
```

### 4.5 Firestore

Covered in detail in Chapter 19 (Firebase section). Brief recap for the GCP context:

- **Document database** — collections and documents, real-time listeners, offline support for mobile apps
- **Native mode** (recommended) — full Firestore with real-time sync and sub-millisecond reads
- **Datastore mode** — backward-compatible with the old Cloud Datastore API, no real-time, better for server-side-only workloads with simpler queries
- Scales automatically to millions of concurrent connections without any provisioning
- Strong consistency for all reads (upgraded from eventual consistency in 2021)
- **Pricing** — per document read/write/delete + storage. Can get expensive at scale if your access patterns aren't designed carefully — don't do full collection scans.

```bash
# Firestore operations via gcloud
gcloud firestore databases create --location=us-central1

# Most Firestore work is done via SDKs, not CLI
# Node.js example:
# const doc = await db.collection('users').doc('user123').get();
```

Firestore vs DynamoDB is the most direct database comparison across the two clouds. Firestore wins on developer experience and real-time capabilities. DynamoDB wins on predictability at massive scale and a more mature set of operational controls. For mobile apps, Firestore is the default. For high-throughput backend services, DynamoDB's single-table design patterns are worth learning.

### 4.6 Bigtable

Wide-column NoSQL database for massive-scale, low-latency workloads (millions of rows/sec). This is managed HBase — the technology that Google invented and published as a paper before the rest of the industry built HBase from it.

**Use cases:** Time-series data (IoT telemetry, metrics), financial tick data, analytics raw storage, large-scale ML feature stores. The common thread is huge amounts of data with consistent low-latency reads and writes, where you can define your access patterns upfront.

**Key design principle:** Row key design determines everything about Bigtable performance. Bigtable stores data sorted by row key and shards by row key ranges. Bad row key = hot nodes = degraded performance for everyone.

```
# Good row key patterns:
# Time-series: reverse timestamp + device_id  →  "9999999999-device42"
# User data: user_id#metric#reverse_timestamp  →  "user42#cpu#9999999999"

# Bad row key patterns:
# Sequential IDs (hotspot on last node)
# Timestamps alone (all recent writes go to one node)
# Domain names as-is (use reversed: com.example.www)
```

```bash
# Create a Bigtable instance
gcloud bigtable instances create my-bigtable \
  --cluster-config=id=my-cluster,zone=us-central1-a,nodes=3 \
  --display-name="Production Bigtable"

# Create a table with column family
cbt createtable my-table
cbt createfamily my-table metrics
```

AWS has no direct Bigtable equivalent — Amazon Keyspaces (managed Cassandra) is the closest, but Bigtable's performance characteristics at scale are in a different class.

### 4.7 Memorystore

Managed Redis and Memcached. Use for caching, session storage, rate limiting, leaderboards — the standard in-memory data structure use cases. Comparable to AWS ElastiCache, with similar feature parity and pricing.

```bash
# Create a Redis instance
gcloud redis instances create my-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0 \
  --network=my-vpc

# Get the IP to connect from Cloud Run / GKE
gcloud redis instances describe my-cache --region=us-central1 --format="value(host)"
```

No strong preference between Memorystore and ElastiCache — both are reliable, both require VPC connectivity, and both support Redis Cluster for horizontal scaling. Choose based on which cloud you're already on.

---

## 5. MESSAGING & EVENT-DRIVEN

### 5.1 Pub/Sub

GCP's fully managed message queue and pub-sub system. Here's the elegant design decision: Pub/Sub combines the roles of SQS + SNS + a lite version of Kafka in a single service. On AWS, routing a message to multiple consumers requires SNS → SQS fan-out wiring that you set up manually. On GCP, you create one topic, create multiple subscriptions, and each subscription receives every message automatically.

**Core concepts:**
- **Topic** — a named channel for messages
- **Subscription** — a named consumer of a topic (pull or push)
- **One topic, many subscriptions** — each subscription gets every message (fan-out built in)
- **At-least-once delivery** by default (idempotent consumers are your responsibility — see Chapter 13 for patterns)
- **Exactly-once delivery** available with ordering keys enabled
- **Dead-letter topics** for messages that fail processing repeatedly

```bash
# Create a topic
gcloud pubsub topics create orders

# Create a pull subscription
gcloud pubsub subscriptions create orders-processor \
  --topic=orders \
  --ack-deadline=60 \
  --dead-letter-topic=orders-dlq \
  --max-delivery-attempts=5

# Create a push subscription (pushes to an HTTPS endpoint)
gcloud pubsub subscriptions create orders-webhook \
  --topic=orders \
  --push-endpoint=https://my-service-xyz.run.app/webhook

# Publish a message
gcloud pubsub topics publish orders \
  --message='{"orderId": "123", "amount": 99.99}' \
  --attribute=type=new_order

# Pull messages (for testing)
gcloud pubsub subscriptions pull orders-processor --auto-ack --limit=10

# Ordering (messages with the same key are delivered in order)
gcloud pubsub topics publish orders \
  --message='{"orderId": "123", "status": "paid"}' \
  --ordering-key=order-123
```

**Pub/Sub vs SQS+SNS vs Kafka:**

| Feature | Pub/Sub | SQS + SNS | Kafka (MSK) |
|---|---|---|---|
| **Model** | Topics + subscriptions | Queues (SQS) + Topics (SNS) | Topics + consumer groups |
| **Fan-out** | Built-in (multiple subs) | SNS → SQS (manual wiring) | Built-in (consumer groups) |
| **Ordering** | Per ordering key | FIFO queues | Per partition |
| **Exactly-once** | Yes (with ordering) | FIFO queues | Yes (idempotent producer) |
| **Retention** | 7 days (configurable up to 31) | 14 days | Configurable (unlimited) |
| **Throughput** | Auto-scales | Auto-scales | Manual (partition count) |
| **Managed** | Fully serverless | Fully serverless | You manage brokers |
| **Cost** | Per message + data | Per request + data | Per broker hour + storage |

**Honest take:** Pub/Sub beats SQS+SNS for simplicity. One service instead of two, built-in fan-out, and a cleaner mental model. If you need Kafka semantics (long retention, consumer group offsets, exactly-once end-to-end), neither Pub/Sub nor SQS gives you that — you need MSK or a self-managed Kafka cluster.

### 5.2 Eventarc

Routes events from GCP services (Cloud Storage, Firestore, BigQuery, Pub/Sub, Cloud Audit Logs, and 100+ sources) to Cloud Run, Cloud Functions, or Workflows. Think of it as EventBridge but with tighter GCP service integration — triggering off Audit Logs is particularly powerful because it means any API call in your GCP project can trigger a workflow.

```bash
# Trigger Cloud Run when a file is uploaded to Cloud Storage
gcloud eventarc triggers create storage-trigger \
  --location=us-central1 \
  --destination-run-service=my-processor \
  --destination-run-region=us-central1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=my-bucket" \
  --service-account=my-sa@my-project.iam.gserviceaccount.com

# Trigger on any GCP API call (via Audit Logs)
gcloud eventarc triggers create audit-trigger \
  --location=us-central1 \
  --destination-run-service=my-auditor \
  --event-filters="type=google.cloud.audit.log.v1.written" \
  --event-filters="serviceName=bigquery.googleapis.com" \
  --event-filters="methodName=google.cloud.bigquery.v2.JobService.InsertJob"
```

The audit log trigger pattern is especially useful for governance and compliance — any BigQuery job someone runs can trigger a validation workflow. On AWS, this requires CloudTrail → EventBridge → Lambda, which is the same pattern but with more pieces to wire together.

EventBridge is more mature than Eventarc and has a larger partner event catalog. If you need events from third-party SaaS systems, EventBridge wins. For internal GCP service-to-service eventing, Eventarc is more native.

### 5.3 Cloud Tasks

Task queues for asynchronous work with rate limiting, scheduled execution, and retry policies. This is what differentiates it from Pub/Sub — Cloud Tasks gives you explicit control over dispatch rate, which is critical for tasks that call external APIs with rate limits (payment processors, email services, etc.).

```bash
# Create a queue with rate limiting
gcloud tasks queues create email-queue \
  --max-dispatches-per-second=10 \
  --max-concurrent-dispatches=5 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s

# Enqueue a task (HTTP target)
gcloud tasks create-http-task \
  --queue=email-queue \
  --url=https://my-service.run.app/send-email \
  --method=POST \
  --body-content='{"to":"user@example.com","template":"welcome"}' \
  --schedule-time="2026-03-25T10:00:00Z"
```

The `--schedule-time` flag is useful: you can enqueue tasks for future execution without a separate scheduler. Cloud Tasks is also the right tool for chunking long-running operations into smaller units — each chunk is a separate task with its own retry policy.

### 5.4 Workflows

Serverless workflow orchestration — GCP's equivalent of AWS Step Functions. Define workflows in YAML, chain together Cloud Run services, Cloud Functions, APIs, and GCP services. The syntax is more YAML-native than Step Functions' JSON state machines, which is either a feature or a bug depending on your preferences.

```yaml
# workflow.yaml
main:
  steps:
    - validate_order:
        call: http.post
        args:
          url: https://validate-service.run.app/validate
          body:
            orderId: ${args.orderId}
        result: validation
    - check_result:
        switch:
          - condition: ${validation.body.valid == true}
            next: process_payment
          - condition: ${validation.body.valid == false}
            next: reject_order
    - process_payment:
        call: http.post
        args:
          url: https://payment-service.run.app/charge
          body:
            orderId: ${args.orderId}
            amount: ${validation.body.amount}
        result: payment
    - notify:
        call: googleapis.pubsub.v1.projects.topics.publish
        args:
          topic: projects/my-project/topics/order-events
          body:
            messages:
              - data: ${base64.encode(json.encode(payment.body))}
        next: end
    - reject_order:
        call: http.post
        args:
          url: https://notify-service.run.app/reject
          body:
            orderId: ${args.orderId}
            reason: ${validation.body.reason}
```

```bash
# Deploy a workflow
gcloud workflows deploy order-workflow \
  --source=workflow.yaml \
  --location=us-central1

# Execute a workflow
gcloud workflows execute order-workflow \
  --data='{"orderId": "12345"}' \
  --location=us-central1
```

Step Functions is more mature than Workflows and has better debugging tooling (the visual state machine diagram is genuinely useful). Workflows is simpler to write and reads more naturally as code. Both are good choices for orchestrating multi-step processes; prefer Workflows if you're already GCP-native.

---

## 6. DATA & ANALYTICS (GCP's Crown Jewel)

### 6.1 BigQuery — The Data Warehouse That Just Works

Here it is. The service that makes data engineers switch to GCP and never look back.

BigQuery is a serverless, petabyte-scale data warehouse where you write SQL and Google handles everything else. No clusters to provision. No indexes to build. No VACUUM to run. No capacity planning. No query optimization passes before you can query your data. You upload data, write SQL, and get results. That's it.

The "serverless" part is not marketing. You don't pick an instance size. You don't configure parallelism. BigQuery automatically scales its query execution — scanning a 1 TB table and a 1 PB table use the same interface; the latter just costs more and takes longer. The underlying Dremel execution engine (which Google published as a research paper in 2010) distributes your query across thousands of workers automatically.

Redshift is a good data warehouse. BigQuery is a great data warehouse that requires almost no operational knowledge to use effectively. That difference matters enormously for small teams.

**Why BigQuery is special:**
- **Serverless** — no infrastructure to manage, ever, not even a connection string to a cluster
- **Separated storage and compute** — pay for storage and queries independently; your data doesn't cost money unless you're querying it
- **Columnar storage** — reads only the columns your query references (query one column of a 100-column table? Pays for one column's data scan)
- **Automatic scaling** — scans terabytes in seconds with no provisioning
- **Standard SQL** — no proprietary query language, no dialects to learn
- **Nested/repeated fields** — first-class support for STRUCT and ARRAY types (model JSON natively without flattening into a dozen relational tables)
- **Streaming inserts** — real-time data ingestion at scale
- **ML in SQL** — train and deploy ML models without leaving BigQuery (BigQuery ML)

**Core concepts:**

```sql
-- Projects > Datasets > Tables
-- project-id.dataset_name.table_name

-- Query example (scans only the columns referenced)
SELECT
  user_id,
  COUNT(*) as order_count,
  SUM(total_amount) as total_spent
FROM `my-project.analytics.orders`
WHERE order_date >= '2026-01-01'
GROUP BY user_id
ORDER BY total_spent DESC
LIMIT 100;

-- Nested/repeated fields (STRUCT and ARRAY)
-- No need to normalize into separate tables
CREATE TABLE `my-project.analytics.events` (
  event_id STRING,
  timestamp TIMESTAMP,
  user STRUCT<
    id STRING,
    name STRING,
    email STRING
  >,
  items ARRAY<STRUCT<
    product_id STRING,
    quantity INT64,
    price FLOAT64
  >>
)
PARTITION BY DATE(timestamp)
CLUSTER BY user.id;

-- Query nested fields naturally
SELECT
  user.name,
  item.product_id,
  item.quantity
FROM `my-project.analytics.events`,
  UNNEST(items) AS item
WHERE DATE(timestamp) = '2026-03-24';
```

**Partitioning and clustering (critical for cost and performance — read this carefully):**

```sql
-- Partitioned table (queries only scan relevant partitions)
CREATE TABLE `analytics.events`
PARTITION BY DATE(timestamp)        -- Time partitioning
CLUSTER BY user_id, event_type      -- Clustering (sort order within partitions)
AS SELECT * FROM `staging.raw_events`;

-- Integer range partitioning
CREATE TABLE `analytics.users`
PARTITION BY RANGE_BUCKET(age, GENERATE_ARRAY(0, 100, 10))
AS SELECT * FROM `staging.raw_users`;

-- Materialized views (pre-computed, auto-refreshed)
CREATE MATERIALIZED VIEW `analytics.daily_revenue`
AS SELECT
  DATE(order_date) as day,
  SUM(total_amount) as revenue,
  COUNT(*) as order_count
FROM `analytics.orders`
GROUP BY day;
```

**Pricing:**

| Model | Cost | Best For |
|---|---|---|
| **On-demand** | $6.25/TB scanned | Exploratory queries, variable workloads |
| **Capacity (editions)** | Slots (compute units), starting ~$0.04/slot/hr | Predictable workloads, cost control |
| **Storage** | $0.02/GB/month (active), $0.01/GB/month (long-term, >90 days untouched) | — |
| **Streaming inserts** | $0.01/200 MB | Real-time ingestion |

**Cost optimization (this is where people waste money):**

```sql
-- 1. ALWAYS select only the columns you need
-- BAD (scans all columns — expensive):
SELECT * FROM `analytics.events` WHERE DATE(timestamp) = '2026-03-24';

-- GOOD (scans only 3 columns):
SELECT event_id, user.id, timestamp
FROM `analytics.events`
WHERE DATE(timestamp) = '2026-03-24';

-- 2. Use partitioned tables and filter on the partition column
-- This query scans only one day's partition instead of the entire table:
SELECT * FROM `analytics.events`
WHERE DATE(timestamp) = '2026-03-24';  -- Partition pruning

-- 3. Preview query cost before running
-- In the BigQuery console, the top-right shows "This query will process X GB"
-- Via CLI:
-- bq query --dry_run 'SELECT ...'

-- 4. Use LIMIT with caution — it does NOT reduce data scanned
-- This scans the FULL table, then returns 10 rows:
SELECT * FROM `analytics.events` LIMIT 10;

-- 5. Use materialized views for repeated expensive queries
-- 6. Cluster tables by commonly filtered columns
-- 7. Set up custom cost controls (per-user quotas)
```

```bash
# Estimate query cost
bq query --dry_run --use_legacy_sql=false \
  'SELECT user_id, COUNT(*) FROM `my-project.analytics.events` GROUP BY user_id'

# Load data from Cloud Storage
bq load --source_format=NEWLINE_DELIMITED_JSON \
  my-project:analytics.events \
  gs://my-bucket/data/*.json \
  schema.json

# Export query results to Cloud Storage
bq extract --destination_format=CSV \
  my-project:analytics.daily_summary \
  gs://my-bucket/exports/summary_*.csv

# Set custom cost controls
bq update --default_table_expiration=7776000 my-project:temp_dataset  # 90 days
```

**BigQuery ML (train models with SQL):**

```sql
-- Train a model
CREATE MODEL `analytics.churn_model`
OPTIONS(model_type='LOGISTIC_REG', input_label_cols=['churned']) AS
SELECT
  total_orders,
  avg_order_value,
  days_since_last_order,
  churned
FROM `analytics.user_features`;

-- Make predictions
SELECT * FROM ML.PREDICT(MODEL `analytics.churn_model`,
  (SELECT total_orders, avg_order_value, days_since_last_order
   FROM `analytics.current_users`));
```

**BI Engine:** In-memory acceleration layer that sits on top of BigQuery. Makes dashboards (Looker, Data Studio) interactive-speed on large datasets. You enable it for a project and pay for reserved memory — dashboards that used to take 5 seconds respond in under a second. No code changes needed.

**GCP vs AWS honest take:** BigQuery vs Redshift isn't a close call for most teams. Redshift requires cluster management, VACUUM/ANALYZE maintenance, and cluster sizing decisions. BigQuery requires none of that. The query cost model is different — Redshift charges per hour of cluster time, BigQuery charges per TB scanned — but for teams without dedicated data engineering, BigQuery's operational simplicity is a massive productivity advantage. If BigQuery were the only GCP service that existed, it would still be worth using for the right workloads.

### 6.2 Dataflow (Apache Beam)

Managed Apache Beam runner for unified batch and stream processing. The key word is "unified" — you write one pipeline in Apache Beam's API, then run it in batch mode (against historical data) or streaming mode (against live Pub/Sub data) without code changes. This is a genuinely different mental model from Kinesis + Glue, where batch and streaming are separate services.

```python
# Simple Dataflow pipeline (Python / Apache Beam)
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

options = PipelineOptions([
    '--project=my-project',
    '--runner=DataflowRunner',
    '--region=us-central1',
    '--temp_location=gs://my-bucket/temp',
])

with beam.Pipeline(options=options) as p:
    (p
     | 'Read' >> beam.io.ReadFromPubSub(topic='projects/my-project/topics/events')
     | 'Parse' >> beam.Map(lambda msg: json.loads(msg))
     | 'Filter' >> beam.Filter(lambda event: event['type'] == 'purchase')
     | 'Window' >> beam.WindowInto(beam.window.FixedWindows(60))  # 1-minute windows
     | 'Sum' >> beam.CombineGlobally(beam.combiners.CountCombineFn())
     | 'Write' >> beam.io.WriteToBigQuery('my-project:analytics.purchase_counts'))
```

Dataflow is more powerful than Kinesis for complex stream processing. It supports windowing, late data handling, watermarks, and complex aggregations that Kinesis Data Analytics can approximate but doesn't match in expressiveness. The tradeoff: Dataflow has a steeper learning curve. Apache Beam is not a simple API.

### 6.3 Dataproc

Managed Apache Spark and Hadoop. For teams with existing Spark jobs or when Dataflow's programming model is not the right fit. The key advantage over self-managed Spark is fast cluster startup (~90 seconds) — you can spin up a cluster, run a job, and tear it down, paying only for job time.

```bash
# Create a Dataproc cluster
gcloud dataproc clusters create my-spark \
  --region=us-central1 \
  --num-workers=3 \
  --worker-machine-type=n2-standard-4

# Submit a Spark job
gcloud dataproc jobs submit spark \
  --cluster=my-spark \
  --region=us-central1 \
  --class=com.example.MyJob \
  --jars=gs://my-bucket/jars/my-job.jar

# Use Dataproc Serverless (no cluster management)
gcloud dataproc batches submit spark \
  --region=us-central1 \
  --jars=gs://my-bucket/jars/my-job.jar \
  --class=com.example.MyJob
```

Dataproc Serverless is the modern choice — no cluster to manage, you just submit jobs. If you have existing Spark code and want the lowest-friction migration path to managed Spark, Dataproc Serverless is the answer.

### 6.4 Looker and Looker Studio

- **Looker** — enterprise BI platform with LookML (a semantic modeling layer that sits between your SQL and your dashboards). Powerful for organizations that want a single source of truth for business metrics. Expensive (Google acquired Looker for $2.6B in 2019). Worth it if your company has a dedicated data team.
- **Looker Studio** (formerly Data Studio) — free, drag-and-drop dashboards. Connects directly to BigQuery, Cloud SQL, Sheets, and 800+ connectors. Not as sophisticated as Looker or Tableau, but "free and connects to BigQuery" covers a lot of use cases. Start here.

### 6.5 Data Fusion

Visual ETL/ELT tool built on CDAP (open source). Drag-and-drop pipeline builder for non-engineering users — think AWS Glue visual editor, but with more built-in connectors. Good for simple transformations; use Dataflow for complex pipelines where you need real programming constructs.

---

## 7. SECURITY & IAM

### 7.1 GCP IAM Model

GCP IAM is genuinely simpler than AWS IAM, and I say this not as a preference but as an objective observation about the number of concepts you need to hold in your head. The core model fits in one line:

```
WHO (member)  +  WHAT (role)  +  WHERE (resource)
```

That's it. A member (a user, service account, or group) gets a role (a collection of permissions) on a resource (a project, a bucket, a specific Cloud Run service). No JSON policy documents. No policy evaluation order. No resource-based policies vs identity-based policies distinction.

- **Members:** users (user@gmail.com), service accounts (sa@project.iam.gserviceaccount.com), groups, domains
- **Roles:** collections of permissions (predefined by Google, or custom ones you create)
- **Resources:** projects, folders, organizations, individual resources (a specific bucket, a specific Cloud Run service)

```bash
# Grant a role on a project
gcloud projects add-iam-policy-binding my-project \
  --member="user:dev@example.com" \
  --role="roles/editor"

# Grant a role on a specific resource (e.g., a Cloud Storage bucket)
gcloud storage buckets add-iam-policy-binding gs://my-bucket \
  --member="serviceAccount:my-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# List roles on a project
gcloud projects get-iam-policy my-project
```

**Role types:**

| Type | Example | When to Use |
|---|---|---|
| **Basic** | `roles/viewer`, `roles/editor`, `roles/owner` | Development only. Too broad for production. |
| **Predefined** | `roles/storage.objectViewer`, `roles/run.invoker` | Most common. Google-maintained, scoped to a service. |
| **Custom** | `roles/myCustomRole` | When predefined roles are too broad or too narrow. |

**GCP IAM vs AWS IAM:**

| Aspect | GCP IAM | AWS IAM |
|---|---|---|
| **Model** | Role bindings on resources | Policy documents attached to identities |
| **Policy format** | Who + Role + Resource (simple) | JSON policy documents (complex, with Effect/Action/Resource/Condition) |
| **Hierarchy** | Org → Folder → Project → Resource (inherits down cleanly) | Account → Resource (flat; cross-account is a maze) |
| **Deny policies** | Supported (relatively new feature) | Always supported |
| **Conditions** | IAM Conditions (time-based, resource attribute-based) | Policy conditions (extensive but verbose) |
| **Verdict** | Easier to learn, harder to misconfigure | More flexible, easier to accidentally grant too much access |

If you've ever spent an afternoon debugging why an AWS Lambda can't access an S3 bucket despite having the right role (spoiler: resource-based bucket policy trumped identity-based role), you'll appreciate GCP's unified model.

### 7.2 Service Accounts

Service accounts are GCP's way of giving identities to services (instead of humans). They're the GCP equivalent of AWS IAM roles for EC2/Lambda, but with a cleaner model: a service account is just another member that can be granted roles.

Best practices that your future self will thank you for:

```bash
# Create a service account (one per service)
gcloud iam service-accounts create my-api-sa \
  --display-name="My API Service Account"

# Grant minimum required roles
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:my-api-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:my-api-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Attach to a Cloud Run service (no keys needed!)
gcloud run services update my-api \
  --service-account=my-api-sa@my-project.iam.gserviceaccount.com

# GKE: Use Workload Identity (maps K8s service account to GCP service account)
gcloud iam service-accounts add-iam-policy-binding \
  my-api-sa@my-project.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:my-project.svc.id.goog[my-namespace/my-k8s-sa]"
```

**Golden rules for service accounts:**
1. **One service account per service** — never share service accounts between services (blast radius control)
2. **No service account keys** — use Workload Identity (GKE), built-in identity (Cloud Run), or Workload Identity Federation (external). Keys are a security liability: they don't expire, they can be copied, and they're frequently leaked in source code
3. **Minimum roles** — grant only what the service needs; use predefined roles scoped to specific services
4. **Disable unused service accounts** — `gcloud iam service-accounts disable` is free insurance

### 7.3 Workload Identity Federation

Lets external systems (AWS, Azure, GitHub Actions, any OIDC provider) authenticate to GCP without service account keys. This is the pattern you want for CI/CD pipelines — your GitHub Actions workflow gets a GCP token by presenting its OIDC token, with no secret to manage or rotate.

```bash
# Create a workload identity pool
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions Pool"

# Add GitHub as a provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"

# Grant the external identity access to a service account
gcloud iam service-accounts add-iam-policy-binding \
  deploy-sa@my-project.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/my-org/my-repo"
```

This is the GCP equivalent of AWS OIDC federation for GitHub Actions — both eliminate the need for long-lived secrets in your CI system. Set this up on day one. Rotating compromised service account keys at 2 AM is not a good use of your time.

### 7.4 Secret Manager

Versioned secrets with automatic rotation support. Similar to AWS Secrets Manager — both store secrets, both support versioning, both integrate with their cloud's compute services. The pricing is comparable. Neither is dramatically better than the other.

```bash
# Create a secret
echo -n "my-database-password" | gcloud secrets create db-password \
  --data-file=- \
  --replication-policy=automatic

# Access a secret
gcloud secrets versions access latest --secret=db-password

# Access from code (e.g., Cloud Run reads at startup)
# Node.js:
# const {SecretManagerServiceClient} = require('@google-cloud/secret-manager');
# const client = new SecretManagerServiceClient();
# const [version] = await client.accessSecretVersion({
#   name: 'projects/my-project/secrets/db-password/versions/latest'
# });
# const password = version.payload.data.toString();

# Add a new version (rotated password)
echo -n "new-password" | gcloud secrets versions add db-password --data-file=-

# Grant a service account access to a secret
gcloud secrets add-iam-policy-binding db-password \
  --member="serviceAccount:my-api-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

One nice GCP integration: Cloud Run natively supports mounting secrets as environment variables or volume mounts, with automatic refresh on rotation. No restart required.

### 7.5 VPC Service Controls

Creates a security perimeter around GCP services to prevent data exfiltration. Even if an attacker compromises a service account, they cannot copy data out of the perimeter. This is the enterprise security feature that AWS has no direct equivalent of — the closest is S3 block public access + service control policies, but VPC Service Controls operates at a different level of granularity.

```bash
# Create an access policy (org-level)
gcloud access-context-manager policies create --organization=ORG_ID --title="My Policy"

# Create a service perimeter
gcloud access-context-manager perimeters create my-perimeter \
  --policy=POLICY_ID \
  --title="Production Perimeter" \
  --resources="projects/PROJECT_NUMBER" \
  --restricted-services="bigquery.googleapis.com,storage.googleapis.com" \
  --perimeter-type=regular
```

If you're in a regulated industry (finance, healthcare, government), VPC Service Controls is worth understanding. It provides guarantees about data movement that are difficult to enforce with traditional IAM alone.

### 7.6 Security Command Center

GCP's central security dashboard. This is what you'd build yourself out of multiple AWS services (Security Hub + GuardDuty + Inspector + Config + Macie) — on GCP it's a single pane of glass:

- Vulnerability scanning (web apps, container images)
- Threat detection (anomalous IAM activity, crypto mining, malware on Compute Engine)
- Compliance monitoring (CIS benchmarks, PCI DSS, ISO 27001)
- Security findings from multiple sources (Cloud Armor, IAM recommender, etc.)

The Standard tier is free. Premium adds more threat detection and compliance reporting.

---

## 8. DEVELOPER & OPERATIONS TOOLS

### 8.1 Cloud Monitoring (formerly Stackdriver)

Cloud Monitoring is comparable to CloudWatch — both provide metrics, dashboards, alerts, and uptime checks. The key difference: Cloud Monitoring comes with richer pre-built dashboards for GCP services and bundles more in the free tier. CloudWatch is more mature and has better log insights (CloudWatch Insights is excellent).

```bash
# Create an alerting policy (CPU > 80% for 5 minutes)
gcloud monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="High CPU Alert" \
  --condition-display-name="CPU utilization > 80%" \
  --condition-filter='resource.type="gce_instance" AND metric.type="compute.googleapis.com/instance/cpu/utilization"' \
  --condition-threshold-value=0.8 \
  --condition-threshold-duration=300s \
  --condition-threshold-comparison=COMPARISON_GT

# Create an uptime check
gcloud monitoring uptime create my-uptime-check \
  --display-name="API Health Check" \
  --resource-type=uptime-url \
  --monitored-resource-labels="host=api.example.com" \
  --check-interval=60s \
  --timeout=10s \
  --path=/health
```

**Key capabilities:**
- Metrics from 100+ GCP services — automatic, no agent required for managed services
- Custom metrics via OpenTelemetry or Cloud Monitoring API (OpenTelemetry is the way to go — vendor-neutral, future-proof)
- Dashboards (pre-built for GKE, Cloud Run, Cloud SQL, etc. — genuinely useful out of the box)
- Alerting with notification channels (email, Slack, PagerDuty, webhooks)
- Uptime checks (HTTP, HTTPS, TCP) from global probes
- SLO monitoring (define SLIs and SLOs, track error budgets) — built into the product, not an afterthought

### 8.2 Cloud Logging

```bash
# View logs for a Cloud Run service
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="my-service"' \
  --limit=50 \
  --format=json

# View logs for a GKE workload
gcloud logging read 'resource.type="k8s_container" AND resource.labels.cluster_name="my-cluster" AND resource.labels.namespace_name="production"' \
  --limit=50

# Create a log-based metric (count of 5xx errors)
gcloud logging metrics create server-errors \
  --description="Count of 5xx errors" \
  --log-filter='resource.type="cloud_run_revision" AND httpRequest.status>=500'

# Create a log sink (export logs to BigQuery for analysis)
gcloud logging sinks create bigquery-sink \
  bigquery.googleapis.com/projects/my-project/datasets/logs \
  --log-filter='resource.type="cloud_run_revision"'

# Create a log sink (export to Cloud Storage for archival)
gcloud logging sinks create storage-sink \
  storage.googleapis.com/my-logs-bucket \
  --log-filter='resource.type="cloud_run_revision"'
```

The BigQuery log sink pattern is worth highlighting: export your logs to BigQuery, then query them with SQL. "Give me all 500 errors in the last 30 days grouped by endpoint" becomes a simple SQL query on your full log history, not a fight with a log management tool's query language.

**Structured logging best practice:**

```javascript
// Cloud Run / Cloud Functions — structured logging to stdout
// GCP automatically parses JSON log lines and enriches them with request context

// Instead of:
console.log('User created');

// Do this:
console.log(JSON.stringify({
  severity: 'INFO',
  message: 'User created',
  userId: user.id,
  email: user.email,
  'logging.googleapis.com/trace': traceHeader, // correlates with Cloud Trace
}));
```

Structured logging lets you filter logs in the console by any field, build log-based metrics on specific values, and correlate logs with traces. It takes 30 seconds to set up and pays dividends every time you're debugging a production issue.

### 8.3 Cloud Trace

Distributed tracing compatible with OpenTelemetry. Automatically traces requests through Cloud Run, Cloud Functions, GKE, App Engine, and Pub/Sub — for managed services, tracing just works without instrumentation.

```bash
# View traces
gcloud trace list --project=my-project --limit=10

# For custom tracing, use OpenTelemetry SDK with the GCP exporter
# npm install @google-cloud/opentelemetry-cloud-trace-exporter
```

For custom instrumentation, use OpenTelemetry rather than the GCP-specific SDK. The OpenTelemetry SDK works with Cloud Trace today and can be redirected to any other backend (Jaeger, Zipkin, Datadog) without code changes.

### 8.4 Error Reporting

Automatic error grouping and notification — genuinely useful and genuinely automatic. Cloud Logging scans for exceptions and stack traces, groups them by root cause, and alerts on new errors or regressions.

Works out of the box with Cloud Run, Cloud Functions, GKE, and App Engine — no configuration required, just log errors with stack traces. Error Reporting is the kind of feature that sounds unremarkable until you're woken up at 3 AM by a new exception type and realize it found it before your users reported it.

### 8.5 Cloud Build

CI/CD service that runs builds in containers. Similar to GitHub Actions but GCP-native. Honest take: most teams use GitHub Actions (or CircleCI, or similar) and only use Cloud Build for specific GCP integration points. Both work. Cloud Build has tighter integration with Artifact Registry and Cloud Run, which can simplify deployment steps.

```yaml
# cloudbuild.yaml
steps:
  # Run tests
  - name: 'node:20'
    entrypoint: 'npm'
    args: ['ci']
  - name: 'node:20'
    entrypoint: 'npm'
    args: ['test']

  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA', '.']

  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA']

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'my-app'
      - '--image=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '--region=us-central1'

images:
  - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
```

```bash
# Create a build trigger (runs on push to main)
gcloud builds triggers create github \
  --repo-name=my-repo \
  --repo-owner=my-org \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml

# Run a build manually
gcloud builds submit --config=cloudbuild.yaml .
```

### 8.6 Artifact Registry

Container images and language packages (npm, Maven, Python, Go, etc.). Replaces the older Container Registry (gcr.io). The main advantage over public Docker Hub is private storage within your GCP project with IAM access control — no separate registry credentials to manage.

```bash
# Create a Docker repository
gcloud artifacts repositories create my-repo \
  --repository-format=docker \
  --location=us-central1

# Authenticate Docker
gcloud auth configure-docker us-central1-docker.pkg.dev

# Push an image
docker tag my-app us-central1-docker.pkg.dev/my-project/my-repo/my-app:latest
docker push us-central1-docker.pkg.dev/my-project/my-repo/my-app:latest

# Create an npm repository
gcloud artifacts repositories create my-npm \
  --repository-format=npm \
  --location=us-central1
```

### 8.7 Terraform on GCP

Terraform is the standard IaC tool for GCP — more so than on AWS, where CDK (TypeScript infrastructure code) has gained significant adoption. GCP's Terraform provider is mature, well-maintained, and covers virtually all GCP services. For patterns covered in Chapter 7's infrastructure concepts, Terraform on GCP looks like this:

```hcl
# main.tf — common GCP Terraform pattern
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "my-terraform-state"
    prefix = "prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Cloud Run service
resource "google_cloud_run_v2_service" "api" {
  name     = "my-api"
  location = var.region

  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/my-repo/my-api:latest"
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }
    service_account = google_service_account.api.email
  }
}

# Cloud SQL instance
resource "google_sql_database_instance" "main" {
  name             = "main-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-custom-2-8192"
    availability_type = "REGIONAL"
    disk_size         = 100
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
  }
}

# Service account with minimum permissions
resource "google_service_account" "api" {
  account_id   = "my-api-sa"
  display_name = "My API Service Account"
}

resource "google_project_iam_member" "api_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}
```

**Note:** Use the `google-beta` provider for newer GCP features not yet in the stable provider. Many Cloud Run v2 features, GKE Autopilot configurations, and AlloyDB resources live in beta temporarily before graduating to stable.

### 8.8 gcloud CLI Essentials

The `gcloud` CLI is the primary interface for everything GCP. It's well-designed — commands follow a consistent structure (`gcloud [service] [resource] [action]`), help is genuinely useful (`gcloud run deploy --help` gives you exactly what you need), and the `--format` flag is a superpower for scripting.

```bash
# Authentication
gcloud auth login                              # Interactive login
gcloud auth application-default login          # For local development (ADC)
gcloud auth activate-service-account --key-file=key.json  # CI/CD

# Project management
gcloud config set project my-project           # Set default project
gcloud config set compute/region us-central1   # Set default region
gcloud projects list                           # List all projects

# Configurations (switch between projects/accounts quickly)
gcloud config configurations create staging
gcloud config configurations activate staging
gcloud config set project my-staging-project
gcloud config configurations activate default  # Switch back

# Common operations
gcloud compute instances list                  # List VMs
gcloud run services list                       # List Cloud Run services
gcloud sql instances list                      # List Cloud SQL instances
gcloud container clusters list                 # List GKE clusters
gcloud functions list                          # List Cloud Functions
gcloud pubsub topics list                      # List Pub/Sub topics

# Logs
gcloud logging read --limit=20                 # Recent logs
gcloud logging read 'severity>=ERROR' --limit=20  # Errors only

# IAM
gcloud iam service-accounts list               # List service accounts
gcloud projects get-iam-policy my-project      # View all IAM bindings

# Useful flags (apply to most commands)
# --format=json        JSON output
# --format="table(name, status)"  Custom table columns
# --filter="name:prod" Client-side filtering
# --project=my-project Override default project
# --quiet              No prompts
```

The configuration profiles (`gcloud config configurations`) are essential if you work with multiple GCP projects. Create one per environment (dev, staging, prod) and switch with a single command. Beats the AWS profile system in ergonomics.

---

## 9. COST OPTIMIZATION

### 9.1 Pricing Models

| Model | Discount | Commitment | Applies To |
|---|---|---|---|
| **On-demand** | None (baseline) | None | All services |
| **Sustained Use Discounts** | Up to 30% | **None (automatic!)** | Compute Engine, GKE Standard nodes |
| **Committed Use Discounts (CUDs)** | 37% (1yr) / 55% (3yr) | 1 or 3 years | Compute Engine, Cloud SQL, GKE |
| **Preemptible / Spot VMs** | 60-91% | None (can be reclaimed) | Compute Engine, GKE node pools |

**GCP-unique advantage: Sustained Use Discounts (SUDs)**

This is the GCP feature that genuinely has no AWS equivalent, and it's worth understanding. If a VM runs for more than 25% of the month, GCP automatically starts discounting its price. At 100% uptime, you get ~30% off with zero commitment. You don't have to buy Reserved Instances a year in advance, you don't have to predict your capacity needs, you just run workloads and get cheaper the more you run them.

```
Usage    | Effective discount
0-25%    | 0% (full price)
25-50%   | ~10%
50-75%   | ~20%
75-100%  | ~30%
```

On AWS, that 30% savings requires buying a 1-year Reserved Instance. On GCP, it's automatic. For workloads you're running anyway, this is free money.

### 9.2 Service-Specific Cost Optimization

**BigQuery:**

| Strategy | Savings |
|---|---|
| Use partitioned tables + filter on partition column | 10-1000x reduction in data scanned |
| SELECT only needed columns (never SELECT *) | 2-100x reduction |
| Use clustered tables for frequent filters | 2-10x reduction |
| Materialized views for repeated queries | Cost of one query instead of N |
| Slot reservations for predictable workloads | Up to 60% compared to on-demand |
| Set per-user/per-project query quotas | Prevents runaway costs from rogue queries |

The SELECT * antipattern deserves extra emphasis. In BigQuery, `SELECT * FROM analytics.events` on a 10 TB table scans 10 TB and costs ~$62.50 — every time you run it. `SELECT event_id, user_id FROM analytics.events` on the same table might scan 200 GB and cost $1.25. Get in the habit of selecting columns deliberately.

**Cloud Run:**

Cloud Run can be extremely cheap for variable-traffic workloads because you pay only for actual request handling time. A service handling 1M requests/month at 200ms each costs approximately $1-5 (depending on CPU/memory configuration). That's not a typo.

Tips:
- Set `--min-instances=0` for non-critical services (scale to zero, zero cost when idle)
- Set `--min-instances=1` only for latency-sensitive services where cold start latency matters
- Set `--cpu-throttling` (default behavior) to reduce cost when not actively processing requests
- Right-size memory (512Mi is enough for most APIs; most people over-provision to 1-2 GB unnecessarily)

**Compute Engine / GKE:**

- Use E2 machine types for general workloads (cheapest, good performance for most use cases)
- Use custom machine types instead of the nearest larger standard type (pay for exactly what you need)
- Spot VMs for fault-tolerant batch workloads (60-91% savings)
- Right-size with Recommender — GCP automatically detects over-provisioned VMs and suggests downgrades
- GKE Autopilot eliminates the node pool sizing problem: pay per pod, not per node

### 9.3 Common Cost Traps

| Trap | What Happens | Fix |
|---|---|---|
| Always-on Compute Engine with no CUDs | Paying full on-demand price 24/7 | Buy CUDs or migrate to Cloud Run |
| BigQuery `SELECT *` on large tables | Scans terabytes, costs hundreds per run | Select specific columns, add partitions |
| Unused persistent disks | Paying for storage nobody uses | Audit with `gcloud compute disks list` |
| Over-provisioned GKE node pools | Nodes sitting at 15% CPU | Use Autopilot or enable cluster autoscaler |
| Idle Cloud SQL instances | Dev/staging DBs running 24/7 at full cost | Schedule start/stop, or use serverless options |
| Undeleted snapshots and images | Storage costs accumulate silently | Set up lifecycle policies on snapshot schedules |
| Cross-region data transfer | $0.01-0.08/GB | Co-locate services in the same region |

Cross-region data transfer is the hidden cost that catches people off guard. Cloud Run in us-central1 calling Cloud SQL in us-east1 generates egress charges on every database call. Keep your services in the same region and this goes away.

### 9.4 Cost Management Tools

```bash
# View billing account
gcloud billing accounts list

# Link a project to a billing account
gcloud billing projects link my-project --billing-account=ACCOUNT_ID

# Export billing data to BigQuery (enables custom cost analysis with SQL)
# Set up in Console: Billing → Billing Export → BigQuery Export

# Set a budget alert
gcloud billing budgets create \
  --billing-account=ACCOUNT_ID \
  --display-name="Monthly Budget" \
  --budget-amount=1000USD \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0

# Recommendations (GCP proactively suggests cost savings)
gcloud recommender recommendations list \
  --project=my-project \
  --location=us-central1-a \
  --recommender=google.compute.instance.MachineTypeRecommender
```

Exporting billing to BigQuery is particularly powerful — you get a complete cost dataset that you can query with SQL. "What's my BigQuery spend by dataset and user for the last 90 days?" becomes a simple query instead of a painful billing console exercise.

---

## 10. ARCHITECTURE PATTERNS ON GCP

### 10.1 Serverless Web App

The simplest production architecture. No servers to manage, no capacity planning, no patching. This is the pattern you reach for by default.

```
Client → Cloud Load Balancing + Cloud CDN
           |
        Cloud Run (API) ←→ Cloud SQL (PostgreSQL)
           |
        Cloud Storage (static assets, uploads)
           |
        Secret Manager (credentials)
```

```bash
# Deploy the entire stack
gcloud run deploy my-api \
  --image=us-central1-docker.pkg.dev/my-project/my-repo/api:latest \
  --add-cloudsql-instances=my-project:us-central1:my-db \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --min-instances=1 \
  --max-instances=50 \
  --region=us-central1
```

**Cost for a moderate-traffic app (100K requests/day):** ~$20-50/month (Cloud Run + Cloud SQL small instance). That includes TLS termination, automatic scaling, database failover, and DDoS protection at the load balancer layer. Try pricing that equivalent stack on raw EC2 + RDS + ALB.

### 10.2 Event-Driven Microservices

For systems where services need to react to each other's events without direct coupling — the pattern from Chapter 13 applied to GCP primitives:

```
                    Pub/Sub (orders topic)
                    /        |           \
            Cloud Run    Cloud Run    Cloud Run
          (inventory)   (payment)    (notification)
               |            |             |
           Firestore    Cloud SQL    Cloud Tasks
                                    (email queue)
               \            |           /
                    Eventarc (audit events)
                         |
                     BigQuery (analytics)
```

Each service publishes events to Pub/Sub, other services subscribe. Eventarc routes system events for audit trails and operational workflows. BigQuery is the analytics sink where all events eventually flow for analysis. Everything scales independently because there's no direct coupling between services.

The key advantage over the AWS equivalent (SQS + SNS + EventBridge + Lambda) is operational simplicity: fewer services with cleaner integration. The architecture diagram above maps to about five GCP services vs eight or nine on AWS.

### 10.3 Data Platform

```
Data Sources → Cloud Storage (data lake, raw files)
                    |
                Dataflow (ETL — clean, transform, enrich)
                    |
                BigQuery (data warehouse — SQL analytics)
                    |
              Looker / Looker Studio (dashboards, BI)
                    |
              BigQuery ML (predictive models)
```

```bash
# Typical data ingestion pipeline:
# 1. Raw data lands in Cloud Storage
gsutil cp data.json gs://my-data-lake/raw/2026/03/24/

# 2. Dataflow job transforms and loads into BigQuery
gcloud dataflow jobs run my-etl \
  --gcs-location=gs://dataflow-templates/latest/GCS_Text_to_BigQuery \
  --parameters=inputFilePattern=gs://my-data-lake/raw/2026/03/24/*.json,outputTable=my-project:analytics.events,JSONPath=gs://my-bucket/schema.json

# 3. Analysts query BigQuery directly
# 4. Dashboards in Looker Studio auto-refresh
```

This is the data platform that makes data engineers happy. Cloud Storage as the raw data lake with automatic storage class tiering, Dataflow for transformation (unified batch and streaming), BigQuery for analytics (no cluster management), and Looker Studio for free dashboards. The end-to-end solution is operationally lighter than the equivalent AWS stack (S3 + Glue + Redshift + QuickSight).

### 10.4 Global Application

When you need low latency for users on multiple continents, GCP's global networking infrastructure is a genuine asset:

```
Users (worldwide) → Global HTTPS Load Balancer (anycast IP)
                         |
              Cloud CDN (static content caching)
                         |
           +-------------+-------------+
           |             |             |
    Cloud Run        Cloud Run     Cloud Run
    (us-central1)   (europe-west1) (asia-east1)
           |             |             |
           +-------------+-------------+
                         |
                   Cloud Spanner (multi-region, globally consistent)
```

```bash
# Deploy Cloud Run in multiple regions
for region in us-central1 europe-west1 asia-east1; do
  gcloud run deploy my-app \
    --image=us-central1-docker.pkg.dev/my-project/my-repo/app:latest \
    --region=$region \
    --min-instances=1
done

# Create a global load balancer with serverless NEGs
# (Network Endpoint Groups for Cloud Run)
gcloud compute network-endpoint-groups create neg-us \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=my-app

gcloud compute network-endpoint-groups create neg-eu \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=my-app
```

The global anycast IP means your users connect to the geographically closest Google point of presence, regardless of which region your Cloud Run service is in. Combined with Cloud Spanner's global consistency, this is the architecture for financial systems, gaming, or any application where users on different continents share data that must be consistent.

### 10.5 ML Platform

```
Training Data → Cloud Storage → Vertex AI Training
                                      |
BigQuery (features) ──────────→ Vertex AI Feature Store
                                      |
                              Vertex AI Model Registry
                                      |
                              Vertex AI Prediction (serving)
                                      |
                              Cloud Run (custom inference API)
```

BigQuery ML for simple models (linear regression, classification, forecasting) — train with SQL, no infrastructure, no Python. Vertex AI for complex models (custom TensorFlow/PyTorch training, LLMs, fine-tuning, RAG pipelines). The integration between BigQuery feature stores and Vertex AI training is tighter than the equivalent SageMaker + Glue integration on AWS, and Google's TPUs make large model training significantly cheaper than GPU-based alternatives.

---

## 11. GCP vs AWS COMPARISON TABLE

Let's put the full comparison in one place, with honest verdicts rather than "it depends" non-answers:

| Category | AWS | GCP | Honest Verdict |
|----------|-----|-----|----------------|
| VMs | EC2 | Compute Engine | Similar. GCP wins on custom machine types and SUDs. AWS wins on instance variety. |
| Serverless containers | Fargate | Cloud Run | Cloud Run wins clearly on simplicity and cost model. |
| Managed K8s | EKS | GKE | GKE wins clearly (Autopilot, tighter integration, zero-downtime upgrades). |
| Serverless functions | Lambda | Cloud Functions | Lambda wins on ecosystem and tooling maturity. GCF 2nd gen closes the gap. |
| Object storage | S3 | Cloud Storage | Effectively a tie. S3 has more ecosystem integrations. Cloud Storage has cleaner pricing. |
| Relational DB | RDS/Aurora | Cloud SQL/AlloyDB | Aurora vs AlloyDB is genuinely close. AlloyDB wins on HTAP; Aurora wins on maturity. |
| Global DB | DynamoDB Global Tables | Cloud Spanner | Spanner wins — it's the only truly globally consistent relational DB. |
| NoSQL | DynamoDB | Firestore/Bigtable | Different tools. Firestore for mobile/real-time; DynamoDB for high-throughput server-side. |
| Data warehouse | Redshift | BigQuery | BigQuery wins decisively for operational simplicity. Redshift wins if you need query optimization control. |
| Message queue | SQS | Pub/Sub | Pub/Sub wins on fan-out simplicity. SQS wins on FIFO guarantees maturity. |
| Event bus | EventBridge | Eventarc | EventBridge is more mature and has more SaaS connectors. |
| Workflow | Step Functions | Workflows | Step Functions is more mature with better debugging tools. |
| Stream processing | Kinesis | Dataflow/Pub/Sub | Dataflow (Beam) is more powerful for complex transformations. |
| CDN | CloudFront | Cloud CDN | CloudFront wins on PoP count (450+ vs fewer). Cloud CDN has better BigQuery integration. |
| DNS | Route 53 | Cloud DNS | Route 53 wins on routing policy variety. |
| WAF | AWS WAF | Cloud Armor | Effectively a tie. |
| IAM | AWS IAM | GCP IAM | GCP IAM wins on simplicity. AWS IAM wins on flexibility. |
| Monitoring | CloudWatch | Cloud Monitoring | CloudWatch Insights is better for log analysis. Cloud Monitoring has cleaner SLO tooling. |
| CI/CD | CodePipeline | Cloud Build | Both work. Most teams use GitHub Actions anyway. |

### When to Choose GCP

**1. You're heavily into data and analytics.**
BigQuery alone is worth it. If your company runs on data, GCP saves you months of Redshift cluster tuning and maintenance. The analytics stack (Cloud Storage → Dataflow → BigQuery → Looker Studio) is tighter and more operationally lightweight than anything on AWS.

**2. You want the best Kubernetes experience.**
GKE Autopilot eliminates node management. Google literally wrote Kubernetes — the integration is unmatched, upgrades are zero-downtime, and you're paying a company to run a technology they invented.

**3. You want serverless containers that genuinely just work.**
Cloud Run is the simplest way to run containers in production. One command to deploy, automatic TLS, scale to zero, pay per request. It's what Heroku should have evolved into.

**4. You need a globally consistent database.**
Cloud Spanner is the only database that provides strong consistency across regions with relational semantics. If you need this, you don't have an AWS alternative — you'd be building distributed transaction logic yourself.

**5. You use TensorFlow or Vertex AI for ML.**
GCP has the best TensorFlow integration (Google built TensorFlow), and TPUs make large model training substantially cheaper than GPU-based alternatives on other clouds.

**6. Your team prefers simplicity over breadth.**
GCP has fewer services but they're more opinionated and easier to configure correctly. IAM is simpler. Networking is simpler. The console is cleaner. For teams without dedicated cloud platform engineers, GCP's opinionated defaults reduce the surface area of things that can go wrong.

### When to Choose AWS

**1. You need the broadest service catalog.**
AWS has 200+ services. If you need a niche managed service — IoT Core, Ground Station, Outposts, Braket (quantum computing) — AWS probably has it. GCP's catalog is more focused.

**2. Your enterprise mandates AWS.**
Most Fortune 500 companies standardized on AWS. Fighting this is rarely worth it; the productivity cost of going against organizational momentum outweighs the service advantages.

**3. You need specific services with no GCP equivalent.**
AWS services like IoT Core, Ground Station, Outposts, and WorkSpaces have no direct GCP competitors. If your use case centers on one of these, AWS is the answer.

**4. Your team has deep AWS expertise.**
Retraining is expensive. If everyone knows AWS cold and GCP is foreign territory, stay on AWS unless GCP offers a compelling advantage for your specific workload. Cloud expertise compounds; don't throw it away without a clear reason.

**5. You need the most edge locations.**
CloudFront has 450+ edge locations vs Cloud CDN's smaller network. For latency-critical global content delivery, AWS has more geographic presence at the edge.

**6. You need the most mature serverless ecosystem.**
Lambda + API Gateway + DynamoDB + Step Functions + EventBridge is a more mature stack with more community resources, more third-party integrations, and more production battle-testing than the GCP equivalent. If serverless is your primary compute pattern, AWS still leads.

### The Multi-Cloud Reality

Many organizations end up using both clouds deliberately:
- **GCP for data** (BigQuery, Dataflow, Looker) + **AWS for everything else**
- **GCP for ML** (Vertex AI, TPUs) + **AWS for production services**
- **GCP for Kubernetes** (GKE) + **AWS for serverless** (Lambda + DynamoDB)

This is fine, and it's not "accidental multi-cloud" when it's intentional. The integration patterns from Chapter 13 apply here — use Pub/Sub or Kafka to bridge between clouds, use Workload Identity Federation to authenticate GCP services to AWS resources, and keep your data transfer costs in mind (cross-cloud egress is expensive).

What to avoid: ending up on two clouds because of organizational entropy rather than deliberate choice. Accidental multi-cloud doubles your operational complexity, your IAM surface area, and your training burden without doubling your capabilities. Be intentional. Use GCP where it's clearly better (data, K8s), use AWS where it's clearly better (breadth, ecosystem), and don't use both where one would do.

---

> **Next:** Chapter 32 explores Azure and multi-cloud strategies for organizations that need to operate across cloud providers.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M62: Cloud Provider Deep Dive](../course/modules/loop-3/L3-M62-cloud-provider-deep-dive.md)** — Compare AWS and GCP primitives side by side using TicketPulse as the reference workload, and make deliberate placement decisions
- **[L3-M75: Cost Optimization](../course/modules/loop-3/L3-M75-cost-optimization.md)** — Apply committed use discounts, right-size GKE node pools, and instrument BigQuery queries to control cost as TicketPulse scales

### Quick Exercises

1. **Run a BigQuery dry run on your most expensive query to see bytes scanned** — add `--dry_run` to your `bq query` command or use the query validator in the console. If the estimate surprises you, find the missing partition filter or clustering key.
2. **Check your GKE cluster for over-provisioned nodes** — look at actual CPU and memory utilization in Cloud Monitoring over the past 7 days. If nodes are consistently below 40% utilized, evaluate a smaller machine type or the cluster autoscaler's scale-down settings.
3. **Set up a Cloud Run service with minimum instances = 0 and test cold start latency** — deploy a lightweight service with no minimum instances, then measure the p50 and p99 latency for a cold request. Decide whether the cost saving is worth the latency for your use case.

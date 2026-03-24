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

GCP's strengths: the best managed Kubernetes (GKE), the best data warehouse (BigQuery), globally consistent databases (Spanner), and a developer experience that favors simplicity over exhaustive configurability.

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

GCP has ~100+ services, but these cover 95% of production workloads:

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

### 1.3 GCP Naming Conventions

GCP naming is more straightforward than AWS:

- **"Cloud"** prefix = GCP-managed service: Cloud Run, Cloud SQL, Cloud Storage, Cloud Functions
- **"Google Kubernetes Engine"** = GKE (always abbreviated)
- **Products without "Cloud"** = standalone brands: BigQuery, Spanner, Bigtable, Firestore, Pub/Sub
- **"Vertex AI"** = the ML/AI platform (covers training, prediction, MLOps)
- **"AlloyDB"** = PostgreSQL-compatible, high-performance DB (GCP's Aurora equivalent)

---

## 2. COMPUTE

### 2.1 Compute Engine (Virtual Machines)

The equivalent of EC2. Full-featured VMs with one key advantage: **custom machine types** — you pick the exact vCPU and memory ratio you need instead of choosing from fixed instance sizes.

**Machine families:**

| Family | Use Case | Example |
|---|---|---|
| **General-purpose (E2, N2, N2D, N4)** | Web servers, small-to-medium DBs, dev/test | `e2-medium` (2 vCPU, 4 GB) |
| **Compute-optimized (C2, C2D, C3, H3)** | Batch processing, HPC, game servers | `c2-standard-8` (8 vCPU, 32 GB) |
| **Memory-optimized (M1, M2, M3)** | In-memory databases, SAP HANA | `m2-ultramem-416` (416 vCPU, 12 TB) |
| **Accelerator-optimized (A2, A3, G2)** | ML training/inference, GPU workloads | `a2-highgpu-1g` (1 A100 GPU) |
| **Custom machine types** | Anything in between | You pick: 6 vCPU + 24 GB RAM |

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

**Committed Use Discounts (CUDs):**
- 1-year commitment: ~37% discount
- 3-year commitment: ~55% discount
- Resource-based (vCPU + memory) or machine-type-based
- Unlike AWS Reserved Instances, GCP CUDs are more flexible — they apply to any machine type in the same family

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

### 2.2 Cloud Run (The Star of GCP)

Cloud Run is GCP's most compelling compute service. It runs any container, any language, scales to zero, and you pay only when handling requests. It's what Lambda would be if Lambda could run arbitrary containers with no cold start penalty on warm instances.

**Why Cloud Run is special:**
- **Any container, any language** — no runtime restrictions like Lambda
- **Scale to zero** — no cost when idle (unlike ECS/Fargate which has minimum tasks)
- **Scale to thousands** — handles traffic spikes automatically
- **Pay per request** — billed per 100ms of CPU time actually used
- **No infrastructure to manage** — no clusters, no nodes, no patches
- **Concurrency** — each instance handles up to 1000 concurrent requests (vs Lambda's 1)

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

**Rule of thumb:** Start with Cloud Run. Move to GKE only if you need Kubernetes-specific features (StatefulSets, DaemonSets, service mesh, complex scheduling). Use Cloud Functions for simple event-driven glue.

### 2.3 GKE (Google Kubernetes Engine)

GKE is widely considered the best managed Kubernetes service — Google literally invented Kubernetes, and it shows. The key differentiator is **Autopilot mode**, which eliminates node management entirely.

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

**Why GKE is considered the best managed K8s:**
- **Autopilot** removes node management entirely (EKS has no equivalent)
- **Node auto-provisioning** in Standard mode automatically selects machine types
- **Cluster autoscaler** is tightly integrated (not a separate add-on)
- **Binary Authorization** enforces deploy-time security policies
- **GKE multi-cluster** with fleet management (Anthos)
- **Cost optimization** with spot pods, autoscaling, and right-sizing recommendations
- **Upgrades** are automatic and zero-downtime

### 2.4 Cloud Functions (2nd Gen)

Cloud Functions 2nd gen is built on Cloud Run under the hood, which means it inherits Cloud Run's capabilities (longer timeouts, higher concurrency, traffic splitting).

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

### 2.5 App Engine

The original PaaS (predates Lambda, Cloud Run, and most modern serverless). Two environments:

- **Standard** — sandbox with auto-scaling to zero, limited runtimes (Python, Java, Node.js, Go, PHP, Ruby). Fast cold starts. Best for simple web apps.
- **Flexible** — runs Docker containers on VMs. Does not scale to zero. Largely superseded by Cloud Run.

**When App Engine still makes sense:** Legacy apps already on it, or very simple apps where you want zero-config deployment with `gcloud app deploy`. For new projects, Cloud Run is almost always the better choice.

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

---

## 3. NETWORKING

### 3.1 VPC (Virtual Private Cloud)

GCP VPCs are **global** by default (unlike AWS where VPCs are regional). Subnets are regional. This simplifies multi-region architectures.

```bash
# Create a VPC with custom subnets
gcloud compute networks create my-vpc \
  --subnet-mode=custom

# Create subnets in different regions
gcloud compute networks subnets create us-subnet \
  --network=my-vpc \
  --region=us-central1 \
  --range=10.0.1.0/24

gcloud compute networks subnets create eu-subnet \
  --network=my-vpc \
  --region=europe-west1 \
  --range=10.0.2.0/24

# Firewall rules (GCP uses network-level firewall rules, not security groups)
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

- **Shared VPC** — one VPC shared across multiple projects in an organization. The host project owns the network, service projects deploy resources into it. This is the recommended pattern for enterprise GCP.
- **VPC Peering** — connects two VPCs (even across organizations). Non-transitive.
- **Private Google Access** — allows VMs without external IPs to reach Google APIs (Cloud Storage, BigQuery, etc.) over internal network.

### 3.2 Cloud Load Balancing

GCP load balancers are a single product with different configurations, not separate services like AWS (ALB/NLB/CLB):

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

### 3.3 Other Networking Services

- **Cloud CDN** — integrated with the HTTP(S) load balancer. One checkbox to enable. Caches at Google's edge network (same network that serves YouTube and Google Search).
- **Cloud DNS** — managed DNS. Supports DNSSEC, private zones (internal DNS for your VPC).
- **Cloud Armor** — WAF and DDoS protection. Attach security policies to the load balancer. Supports IP allowlisting/blocklisting, geo-based rules, rate limiting, pre-configured WAF rules (OWASP Top 10).
- **Cloud NAT** — managed NAT gateway for VMs without external IPs.
- **Private Service Connect** — like AWS PrivateLink. Private endpoints to Google services or your own services without traversing the public internet.
- **Cloud Interconnect** — dedicated physical connection to Google's network (10/100 Gbps). For enterprises with on-prem datacenters.
- **Cloud VPN** — IPsec VPN tunnels to connect on-prem or other clouds. HA VPN provides 99.99% SLA.

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

The equivalent of S3. Stores objects (files) in buckets with four storage classes:

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

### 4.2 Cloud SQL

Managed PostgreSQL, MySQL, and SQL Server. Comparable to AWS RDS.

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

Cloud Run connects to Cloud SQL via the built-in Cloud SQL Auth Proxy — no VPC connector needed:

```bash
gcloud run deploy my-api \
  --image=gcr.io/my-project/my-api:latest \
  --add-cloudsql-instances=my-project:us-central1:my-db \
  --set-env-vars="DB_HOST=/cloudsql/my-project:us-central1:my-db,DB_USER=myuser,DB_NAME=myapp"
```

### 4.3 AlloyDB

GCP's answer to Amazon Aurora. PostgreSQL-compatible with:
- Up to 4x better performance than standard Cloud SQL PostgreSQL
- **Columnar engine** for analytics queries (OLAP) on the same database handling OLTP — true HTAP
- AI/ML integrations (vector embeddings, model inference inside SQL)
- 99.99% SLA with regional HA

**When to choose AlloyDB over Cloud SQL:**
- High-performance OLTP workloads (high-throughput writes)
- Mixed OLTP + analytics (HTAP) — the columnar engine handles analytics without a separate warehouse
- Need for vector search (pgvector on steroids)
- When you'd reach for Aurora on AWS

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

The only database that is **globally distributed AND strongly consistent AND relational**. This is not marketing — it uses TrueTime (atomic clocks + GPS receivers in every datacenter) to provide external consistency across the planet.

**When to use Spanner:**
- Global applications needing consistent reads/writes across regions (financial systems, inventory management, gaming leaderboards)
- When you need relational semantics (JOINs, secondary indexes, schema enforcement) at global scale
- When eventual consistency is unacceptable

**When NOT to use Spanner:**
- Single-region applications (Cloud SQL or AlloyDB is far cheaper)
- Simple key-value lookups (Firestore or Bigtable is cheaper)
- Analytics (BigQuery is better)
- Cost-sensitive projects — Spanner starts at ~$0.90/node/hr (minimum 1 node = ~$650/month)

**Schema design (critical for performance):**

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
```

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

Covered in detail in Chapter 19 (Firebase section). Brief recap:

- **Document database** — collections and documents, real-time listeners, offline support
- **Native mode** (recommended) — full Firestore with real-time sync
- **Datastore mode** — backward-compatible, no real-time, better for server-side-only workloads
- Scales automatically to millions of concurrent connections
- Strong consistency for all reads (since 2021)
- **Pricing** — per document read/write/delete + storage. Can get expensive at scale if not designed carefully.

```bash
# Firestore operations via gcloud
gcloud firestore databases create --location=us-central1

# Most Firestore work is done via SDKs, not CLI
# Node.js example:
# const doc = await db.collection('users').doc('user123').get();
```

### 4.6 Bigtable

Wide-column NoSQL database for massive-scale, low-latency workloads (millions of rows/sec). Think of it as managed HBase.

**Use cases:** Time-series data, IoT telemetry, financial tick data, analytics raw storage, large-scale ML feature stores.

**Key design principle:** Row key design determines everything. Bigtable stores data sorted by row key and shards by row key ranges. Bad row key = hot nodes.

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

### 4.7 Memorystore

Managed Redis and Memcached. Use for caching, session storage, rate limiting, leaderboards.

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

---

## 5. MESSAGING & EVENT-DRIVEN

### 5.1 Pub/Sub

GCP's fully managed message queue and pub-sub system. Combines the roles of SQS + SNS + Kafka-lite in a single service.

**Core concepts:**
- **Topic** — a named channel for messages
- **Subscription** — a named consumer of a topic (pull or push)
- **One topic, many subscriptions** — each subscription gets every message (fan-out)
- **At-least-once delivery** by default (messages may be delivered more than once)
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

### 5.2 Eventarc

Routes events from GCP services (Cloud Storage, Firestore, BigQuery, Pub/Sub, Cloud Audit Logs, and 100+ sources) to Cloud Run, Cloud Functions, or Workflows.

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

### 5.3 Cloud Tasks

Task queues for asynchronous work with rate limiting, scheduled execution, and retry policies. Like SQS but with built-in rate control and scheduling.

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

### 5.4 Workflows

Serverless workflow orchestration — GCP's equivalent of AWS Step Functions. Define workflows in YAML, chain together Cloud Run services, Cloud Functions, APIs, and GCP services.

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

---

## 6. DATA & ANALYTICS (GCP's Crown Jewel)

### 6.1 BigQuery

BigQuery is often the single reason companies choose GCP. It's a serverless, petabyte-scale data warehouse where you write SQL and Google handles everything else — no clusters to provision, no indexes to manage, no vacuuming.

**Why BigQuery is special:**
- **Serverless** — no infrastructure to manage, ever
- **Separated storage and compute** — pay for storage and queries independently
- **Columnar storage** — reads only the columns your query needs
- **Automatic scaling** — scans terabytes in seconds
- **Standard SQL** — no proprietary query language
- **Nested/repeated fields** — first-class support for STRUCT and ARRAY types (no need to flatten JSON into relational tables)
- **Streaming inserts** — real-time data ingestion
- **ML in SQL** — train and deploy ML models without leaving BigQuery

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

**Partitioning and clustering (critical for cost and performance):**

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

**BI Engine:** In-memory acceleration layer that sits on top of BigQuery. Makes dashboards (Looker, Data Studio) interactive-speed on large datasets. No code changes needed — just enable it.

### 6.2 Dataflow (Apache Beam)

Managed Apache Beam runner for unified batch and stream processing. You write one pipeline, run it in batch or streaming mode.

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

### 6.3 Dataproc

Managed Apache Spark and Hadoop. For teams with existing Spark jobs or when Dataflow is not the right fit.

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

### 6.4 Looker and Looker Studio

- **Looker** — enterprise BI platform with LookML (semantic modeling layer). Expensive, powerful.
- **Looker Studio** (formerly Data Studio) — free, drag-and-drop dashboards. Connects directly to BigQuery, Cloud SQL, Sheets, and 800+ connectors.

### 6.5 Data Fusion

Visual ETL/ELT tool built on CDAP (open source). Drag-and-drop pipeline builder for non-engineering users. Like AWS Glue visual editor. Good for simple transformations; use Dataflow for complex pipelines.

---

## 7. SECURITY & IAM

### 7.1 GCP IAM Model

GCP IAM is simpler than AWS IAM. The core model:

```
WHO (member)  +  WHAT (role)  +  WHERE (resource)
```

- **Members:** users (user@gmail.com), service accounts (sa@project.iam.gserviceaccount.com), groups, domains
- **Roles:** collections of permissions
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
| **Policy format** | Who + Role + Resource (simple) | JSON policy documents (complex) |
| **Hierarchy** | Org → Folder → Project → Resource (inherits down) | Account → Resource (flat, cross-account is complex) |
| **Deny policies** | Supported (relatively new) | Always supported |
| **Conditions** | IAM Conditions (time, resource attributes) | Policy conditions (extensive) |
| **Verdict** | Easier to learn, harder to do wrong | More flexible, easier to misconfigure |

### 7.2 Service Accounts

Service accounts are GCP's way of giving identities to services (instead of humans). Best practices:

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
1. **One service account per service** — never share service accounts between services
2. **No service account keys** — use Workload Identity (GKE), built-in identity (Cloud Run), or Workload Identity Federation (external)
3. **Minimum roles** — grant only what the service needs
4. **Disable unused service accounts** — `gcloud iam service-accounts disable`

### 7.3 Workload Identity Federation

Lets external systems (AWS, Azure, GitHub Actions, any OIDC provider) authenticate to GCP without service account keys. The equivalent of AWS OIDC federation.

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

### 7.4 Secret Manager

Versioned secrets with automatic rotation support.

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

### 7.5 VPC Service Controls

Creates a security perimeter around GCP services to prevent data exfiltration. Even if an attacker compromises a service account, they cannot copy data out of the perimeter.

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

### 7.6 Security Command Center

GCP's central security dashboard. Provides:
- Vulnerability scanning (web apps, container images)
- Threat detection (anomalous IAM activity, crypto mining, malware)
- Compliance monitoring (CIS benchmarks, PCI DSS)
- Security findings from multiple sources (Cloud Armor, IAM recommender, etc.)

---

## 8. DEVELOPER & OPERATIONS TOOLS

### 8.1 Cloud Monitoring (formerly Stackdriver)

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
- Metrics from 100+ GCP services (automatic, no agent needed)
- Custom metrics via OpenTelemetry or Cloud Monitoring API
- Dashboards (pre-built for GKE, Cloud Run, Cloud SQL, etc.)
- Alerting with notification channels (email, Slack, PagerDuty, webhooks)
- Uptime checks (HTTP, HTTPS, TCP) from global probes
- SLO monitoring (define SLIs/SLOs, track error budgets)

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

**Structured logging best practice:**

```javascript
// Cloud Run / Cloud Functions — structured logging to stdout
// GCP automatically parses JSON log lines

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

### 8.3 Cloud Trace

Distributed tracing compatible with OpenTelemetry. Automatically traces requests through Cloud Run, Cloud Functions, GKE, App Engine, and Pub/Sub.

```bash
# View traces
gcloud trace list --project=my-project --limit=10

# For custom tracing, use OpenTelemetry SDK with the GCP exporter
# npm install @google-cloud/opentelemetry-cloud-trace-exporter
```

### 8.4 Error Reporting

Automatic error grouping and notification. Scans Cloud Logging for exceptions and stack traces, groups them by root cause, and alerts on new errors or regressions.

Works out of the box with Cloud Run, Cloud Functions, GKE, and App Engine. No configuration needed — just log errors with stack traces.

### 8.5 Cloud Build

CI/CD service that runs builds in containers. Similar to GitHub Actions but GCP-native.

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

Container images and language packages (npm, Maven, Python, Go, etc.). Replaces the older Container Registry (gcr.io).

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

**Note:** Use the `google-beta` provider for newer GCP features not yet in the stable provider.

### 8.8 gcloud CLI Essentials

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

SUDs are automatic. If a VM runs for more than 25% of the month, GCP starts discounting. At 100% uptime, you get ~30% off — with no commitment. AWS has nothing equivalent (you must buy Reserved Instances for savings).

```
Usage    | Effective discount
0-25%    | 0% (full price)
25-50%   | ~10%
50-75%   | ~20%
75-100%  | ~30%
```

### 9.2 Service-Specific Cost Optimization

**BigQuery:**

| Strategy | Savings |
|---|---|
| Use partitioned tables + filter on partition column | 10-1000x |
| SELECT only needed columns (never SELECT *) | 2-100x |
| Use clustered tables for frequent filters | 2-10x |
| Materialized views for repeated queries | Cost of one query |
| Slot reservations for predictable workloads | Up to 60% |
| Set per-user/per-project query quotas | Prevents runaway costs |

**Cloud Run:**

Cloud Run can be extremely cheap for variable-traffic workloads because you pay only for actual request handling time. A service with 1M requests/month at 200ms each costs approximately $1-5 (depending on CPU/memory).

Tips:
- Set `--min-instances=0` for non-critical services (scale to zero)
- Use `--min-instances=1` only for latency-sensitive services
- Set `--cpu-throttling` (default) to reduce cost when not processing requests
- Right-size memory (512Mi is enough for most APIs)

**Compute Engine / GKE:**

- Use E2 machine types for general workloads (cheapest)
- Use custom machine types (don't pay for 8 vCPU when you need 6)
- Spot VMs for fault-tolerant batch workloads
- Right-size with Recommender (GCP suggests if a VM is over-provisioned)
- GKE Autopilot avoids over-provisioned node pools

### 9.3 Common Cost Traps

| Trap | What Happens | Fix |
|---|---|---|
| Always-on Compute Engine with no CUDs | Paying full on-demand price 24/7 | Buy CUDs or use Cloud Run |
| BigQuery `SELECT *` on large tables | Scans terabytes, costs hundreds | Select specific columns, partition |
| Unused persistent disks | Paying for storage nobody uses | Audit with `gcloud compute disks list` |
| Over-provisioned GKE node pools | Nodes sitting at 15% CPU | Use Autopilot or enable autoscaler |
| Idle Cloud SQL instances | Dev/staging DBs running 24/7 | Schedule start/stop or use serverless |
| Undeleted snapshots and images | Storage costs accumulate silently | Set up lifecycle policies |
| Cross-region data transfer | $0.01-0.08/GB | Co-locate services in the same region |

### 9.4 Cost Management Tools

```bash
# View billing account
gcloud billing accounts list

# Link a project to a billing account
gcloud billing projects link my-project --billing-account=ACCOUNT_ID

# Export billing data to BigQuery (enables custom cost analysis)
# Set up in Console: Billing → Billing Export → BigQuery Export

# Set a budget alert
gcloud billing budgets create \
  --billing-account=ACCOUNT_ID \
  --display-name="Monthly Budget" \
  --budget-amount=1000USD \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0

# Recommendations (GCP suggests cost savings)
gcloud recommender recommendations list \
  --project=my-project \
  --location=us-central1-a \
  --recommender=google.compute.instance.MachineTypeRecommender
```

---

## 10. ARCHITECTURE PATTERNS ON GCP

### 10.1 Serverless Web App

The simplest production architecture. No servers to manage.

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

**Cost for a moderate-traffic app (100K requests/day):** ~$20-50/month (Cloud Run + Cloud SQL small instance)

### 10.2 Event-Driven Microservices

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

Each service publishes events to Pub/Sub, other services subscribe. Eventarc routes system events. Everything scales independently.

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

### 10.4 Global Application

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

BigQuery ML for simple models (linear regression, classification, forecasting) — train with SQL, no infrastructure. Vertex AI for complex models (custom TensorFlow/PyTorch, LLMs, fine-tuning).

---

## 11. GCP vs AWS COMPARISON TABLE

| Category | AWS | GCP | Notes |
|----------|-----|-----|-------|
| VMs | EC2 | Compute Engine | Similar, GCP has custom machine types |
| Serverless containers | Fargate | Cloud Run | Cloud Run is simpler and cheaper for many workloads |
| Managed K8s | EKS | GKE | GKE is widely considered better (Autopilot, node auto-provisioning) |
| Serverless functions | Lambda | Cloud Functions | Similar, GCF 2nd gen is Cloud Run under the hood |
| Object storage | S3 | Cloud Storage | Similar features, S3 has more ecosystem integrations |
| Relational DB | RDS/Aurora | Cloud SQL/AlloyDB | AlloyDB is GCP's Aurora competitor |
| Global DB | DynamoDB Global Tables | Cloud Spanner | Spanner is truly globally consistent (stronger guarantee) |
| NoSQL | DynamoDB | Firestore/Bigtable | Different models — Firestore is document, Bigtable is wide-column |
| Data warehouse | Redshift | BigQuery | BigQuery is significantly easier to use and often cheaper |
| Message queue | SQS | Pub/Sub | Pub/Sub is more feature-rich (topics, ordering, DLQ) |
| Event bus | EventBridge | Eventarc | EventBridge is more mature |
| Workflow | Step Functions | Workflows | Step Functions is more mature |
| Stream processing | Kinesis | Dataflow/Pub/Sub | Dataflow (Beam) is more powerful |
| CDN | CloudFront | Cloud CDN | CloudFront has more edge locations |
| DNS | Route 53 | Cloud DNS | Route 53 has more routing policies |
| WAF | AWS WAF | Cloud Armor | Similar capabilities |
| IAM | AWS IAM | GCP IAM | GCP's is simpler (resource-level roles) |
| Monitoring | CloudWatch | Cloud Monitoring | Similar, GCP bundles more in free tier |
| CI/CD | CodePipeline | Cloud Build | Both work, most teams use GitHub Actions anyway |

### When to Choose GCP

1. **You're heavily into data and analytics.** BigQuery alone is worth it. If your company runs on data, GCP saves you months of Redshift cluster tuning and management.

2. **You want the best Kubernetes experience.** GKE Autopilot eliminates node management. Google literally wrote Kubernetes — the integration is unmatched.

3. **You want serverless containers that just work.** Cloud Run is the simplest way to run containers in production. Deploy with one command, scale to zero, pay per request.

4. **You need a globally consistent database.** Cloud Spanner is the only database that provides strong consistency across regions with relational semantics. No other cloud has an equivalent.

5. **You use TensorFlow or Vertex AI for ML.** GCP has the best TensorFlow integration (Google built TensorFlow), and Vertex AI is a cohesive ML platform.

6. **Your team prefers simplicity.** GCP has fewer services but they're more opinionated and easier to configure. IAM is simpler. Networking is simpler. The console is cleaner.

### When to Choose AWS

1. **You need the broadest service catalog.** AWS has 200+ services. If you need a niche managed service, AWS probably has it.

2. **Your enterprise mandates AWS.** Most Fortune 500 companies standardized on AWS. Fighting this is rarely worth it.

3. **You need specific services with no GCP equivalent.** AWS has services like IoT Core, Ground Station, Outposts, and dozens more with no direct GCP competitor.

4. **Your team has deep AWS expertise.** Retraining is expensive. If everyone knows AWS, stay on AWS unless GCP offers a compelling advantage for your specific workload.

5. **You need the most edge locations.** CloudFront has 450+ edge locations vs Cloud CDN's smaller network. For latency-critical global content delivery, AWS has the edge.

6. **You need the most mature serverless ecosystem.** Lambda + API Gateway + DynamoDB + Step Functions + EventBridge is a more mature serverless stack with more community resources.

### The Multi-Cloud Reality

Many organizations end up using both:
- **GCP for data** (BigQuery, Dataflow, Looker) + **AWS for everything else**
- **GCP for ML** (Vertex AI, TPUs) + **AWS for production services**
- **GCP for Kubernetes** (GKE) + **AWS for serverless** (Lambda + DynamoDB)

This is fine. Use the best tool for each job. Just be deliberate about it — accidental multi-cloud is expensive and complex.

---

> **Next:** Chapter 32 explores Azure and multi-cloud strategies for organizations that need to operate across cloud providers.

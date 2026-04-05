<!--
  CHAPTER: 19
  TITLE: AWS & Firebase Deep Dive
  PART: IV — Cloud & Operations
  PREREQS: Chapter 7 (infrastructure concepts), Chapter 13 (system integration)
  KEY_TOPICS: EC2, Lambda, ECS, VPC, S3, DynamoDB, RDS, SQS, SNS, EventBridge, IAM, CloudWatch, Firestore, Firebase Auth, Cloud Functions, security rules
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 19: AWS & Firebase Deep Dive

> **Part IV — Cloud & Operations** | Prerequisites: Chapter 7 (infrastructure concepts), Chapter 13 (system integration) | Difficulty: Intermediate → Advanced

Let's be honest about what cloud platforms actually are. AWS is 200+ managed services layered on top of the same physical hardware you could rent yourself — but the layering is the product. Firebase is a BaaS (Backend-as-a-Service) that lets a three-person team ship a real-time app in a weekend. Both are tools. Neither is magic.

This chapter gives you the real deal on the 20 AWS services that power 95% of production workloads, the networking and security model underneath them, how to deploy frontends correctly, and the full Firebase toolkit — plus the honest comparison of when to use each.

You'll also find cross-references back to Chapter 13 (where cloud services connect into real integration patterns) and forward to Chapter 31 (the GCP deep dive) wherever the comparison matters.

### In This Chapter
- AWS Core Services Map
- Compute
- Networking
- Storage & Databases
- Messaging & Event-Driven
- Security & IAM
- Developer & Operations Tools
- Cost Optimization
- Architecture Patterns on AWS
- Frontend Deployment on AWS
- Firebase Services Map
- Core Services (Firebase)
- Firebase Security Rules
- Firebase + Modern Frameworks
- Scaling Firebase
- Firebase vs AWS Comparison

### Related Chapters
- Chapter 13 (how cloud services connect)
- Chapter 7 (infrastructure/K8s)
- Chapter 5 (security/IAM)

---

# PART 1: AWS DEEP DIVE

---

## 1. AWS CORE SERVICES MAP

### 1.1 The 20 Services That Matter Most

AWS has over 200 services. A huge number of them are either niche, legacy, or just wrappers around something else. In practice, you will use the same 20 services over and over. Here they are, organized by what they actually do — not by the category names on the AWS console, which are optimized for confusion.

| Category | Services | What They Do |
|---|---|---|
| **Compute** | EC2, Lambda, ECS/EKS, Fargate | Run code on servers, functions, or containers |
| **Networking** | VPC, ALB/NLB, Route 53, CloudFront, API Gateway | Connect, route, and protect traffic |
| **Storage** | S3, EBS, EFS | Store objects, block data, and shared filesystems |
| **Databases** | RDS/Aurora, DynamoDB, ElastiCache | Relational, key-value, and caching |
| **Messaging** | SQS, SNS, EventBridge | Decouple services with queues, topics, and event buses |
| **Security** | IAM, KMS, Secrets Manager, WAF | Identity, encryption, secrets, and firewalls |
| **Observability** | CloudWatch, X-Ray, CloudTrail | Metrics, tracing, and audit logs |
| **Infrastructure** | CloudFormation/CDK, Systems Manager | Define and manage infrastructure as code |

### 1.2 How They Connect

The mental model that saves you: traffic enters from the internet at Route 53 (DNS), fans out through CloudFront (CDN), hits your load balancer or API Gateway, reaches your compute layer, which reads from and writes to your data layer, and kicks off async work through the messaging layer. Everything else is supporting infrastructure around this core flow.

```
                         Route 53 (DNS)
                             |
                         CloudFront (CDN)
                             |
                    +--------+--------+
                    |                 |
               API Gateway          ALB
                    |                 |
                 Lambda        ECS / EKS / EC2
                    |                 |
            +-------+-------+   +----+----+
            |       |       |   |         |
         DynamoDB  SQS   S3   RDS/Aurora ElastiCache
                    |
                 Lambda (consumer)
                    |
               EventBridge / SNS (fan-out)
```

Chapter 13 covers how these services connect into integration patterns at a higher level. This chapter is about the internals — what each service actually does, how to configure it, and where it will bite you.

### 1.3 Naming Conventions and Service Categories

AWS naming follows patterns worth memorizing. Once you see the logic, the service catalog becomes less intimidating:

- **"Elastic"** = auto-scaling: Elastic Load Balancing, ElastiCache, Elastic Beanstalk, ECS, EKS
- **"Simple"** = managed wrapper: Simple Queue Service (SQS), Simple Notification Service (SNS), Simple Storage Service (S3)
- **"Cloud"** = AWS-native: CloudWatch, CloudFront, CloudFormation, CloudTrail
- **"Amazon"** prefix = the service itself (Amazon RDS). **"AWS"** prefix = platform-level (AWS IAM, AWS Lambda)
- **"Aurora"** = AWS's MySQL/PostgreSQL-compatible engine with proprietary storage layer
- **"Kinesis"** = real-time streaming family (Data Streams, Firehose, Analytics, Video Streams)

---

## 2. COMPUTE

### 2.1 EC2 (Elastic Compute Cloud)

EC2 is a computer in someone else's data center. That's it. Everything else is just abstractions on top.

You pick a CPU/memory configuration (instance type), choose an OS image (AMI), put it in a network (VPC/subnet), and you have a machine that you can SSH into and run whatever you want. The "elastic" part means you can add more machines when you need them and remove them when you don't.

**Instance Type Families:**

| Family | Prefix | Optimized For | Use Cases |
|---|---|---|---|
| General Purpose | t3, t3a, m5, m6i, m7g | Balanced CPU/memory | Web servers, microservices, dev/test |
| Compute-Optimized | c5, c6i, c7g | High CPU | Batch processing, ML inference, gaming servers |
| Memory-Optimized | r5, r6i, r7g, x2idn | High RAM | In-memory databases, real-time analytics |
| Storage-Optimized | i3, i4i, d3 | High sequential I/O | Data warehouses, distributed file systems |
| Accelerated (GPU) | p4d, p5, g5, inf2, trn1 | GPU/ML chips | Training ML models, video encoding, HPC |

**Instance naming convention:** `m6i.xlarge` = family(m) + generation(6) + processor(i=Intel) + size(xlarge).

**Graviton (g suffix)** instances use ARM-based AWS-designed processors. Typically 20-40% better price/performance than x86 equivalents. My default recommendation: always try Graviton first for new workloads. The compatibility story is nearly seamless for most languages and runtimes, and you will save real money at any scale.

**Pricing Models:**

| Model | Discount | Commitment | Best For |
|---|---|---|---|
| On-Demand | 0% (baseline) | None | Unpredictable workloads, short-term |
| Reserved Instances | 30-72% | 1 or 3 years | Steady-state workloads |
| Savings Plans | 30-72% | 1 or 3 years ($/hr commitment) | Flexible across instance types |
| Spot Instances | Up to 90% | None (can be interrupted with 2-min notice) | Fault-tolerant batch jobs, CI/CD |

**Practical example -- launching an instance:**
```bash
# Launch a t3.medium instance in us-east-1
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name my-key-pair \
  --security-group-ids sg-0a1b2c3d4e5f6g7h8 \
  --subnet-id subnet-0123456789abcdef0 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=my-server},{Key=Environment,Value=production}]'

# Check spot pricing before using spot instances
aws ec2 describe-spot-price-history \
  --instance-types m5.xlarge \
  --product-descriptions "Linux/UNIX" \
  --start-time $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --max-items 5
```

**Placement Groups:**
- **Cluster:** Pack instances close together in one AZ for low-latency networking (10 Gbps inter-instance). Use for HPC, tightly coupled workloads.
- **Spread:** Spread instances across distinct hardware. Max 7 instances per AZ. Use for critical instances that must not fail together.
- **Partition:** Logical partitions, each on separate racks. Use for large distributed systems like HDFS, HBase, Cassandra.

**AMIs (Amazon Machine Images):** Snapshots of configured instances. Build custom AMIs with Packer for consistent deployments. Use AWS-provided AMIs (Amazon Linux 2023, Ubuntu) as base images.

**Common gotchas:**
- T-series instances have CPU credits. Burstable performance means you can exhaust credits under sustained load. Use `unlimited` mode or switch to M-series for sustained workloads. I've seen teams wonder why their app gets slow at 2 PM every day — it's the t3 running out of CPU credits.
- EBS volumes are network-attached, not local. I/O-heavy workloads need instance store or provisioned IOPS EBS.
- Stopping an instance releases the underlying host. Public IP changes on restart unless you use an Elastic IP.

### 2.2 Lambda (Serverless Functions)

Lambda is the compute model that changes how you think about servers: you write a function, AWS runs it when something happens, you pay only for the time it runs. No servers to patch. No capacity to provision. No idle costs when no one is calling your API at 3 AM.

The catch is that you are not running a server — you are running a function in a shared environment that might need to be initialized from scratch (cold start) or might reuse a warm execution context. That distinction matters a lot for latency-sensitive work.

**Runtime model:**
1. Event arrives (HTTP request, SQS message, S3 notification, etc.)
2. AWS either reuses a warm execution environment or creates a new one (cold start)
3. Your handler function runs
4. Environment stays warm for ~5-15 minutes for potential reuse

**Configuration limits:**
- Memory: 128 MB to 10,240 MB (CPU scales proportionally)
- Timeout: max 15 minutes
- Deployment package: 50 MB zipped, 250 MB unzipped (or 10 GB with container images)
- Concurrency: 1,000 default (soft limit, can request increase)
- Ephemeral storage (/tmp): 512 MB to 10,240 MB

**Cold starts -- the critical performance concern:**

| Runtime | Typical Cold Start | Notes |
|---|---|---|
| Python | 200-500ms | Fastest native runtime |
| Node.js | 200-500ms | Fast, large ecosystem |
| Go | 100-300ms | Compiled binary, very fast |
| Java | 2-8 seconds | JVM startup overhead; use GraalVM native-image or SnapStart |
| .NET | 1-3 seconds | Improved with AOT compilation |
| Container Image | 3-10 seconds | Depends on image size |

**Mitigation strategies:**
- **Provisioned Concurrency:** Pre-warm N instances. Eliminates cold starts at the cost of paying for idle capacity. Use for latency-sensitive APIs.
- **SnapStart (Java only):** Snapshots the initialized JVM. Reduces Java cold starts to ~200ms.
- **Keep functions small:** Minimize dependencies. Lazy-load AWS SDK clients.
- **Lambda Layers:** Share common dependencies across functions. Up to 5 layers per function.

**Event sources and patterns:**

```bash
# Create a Lambda function
aws lambda create-function \
  --function-name my-processor \
  --runtime nodejs20.x \
  --handler index.handler \
  --role arn:aws:iam::123456789012:role/lambda-role \
  --zip-file fileb://function.zip \
  --memory-size 512 \
  --timeout 30 \
  --environment Variables='{DB_HOST=mydb.cluster-xyz.us-east-1.rds.amazonaws.com}'

# Add SQS trigger
aws lambda create-event-source-mapping \
  --function-name my-processor \
  --event-source-arn arn:aws:sqs:us-east-1:123456789012:my-queue \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5

# Add S3 trigger (via S3 notification configuration)
aws s3api put-bucket-notification-configuration \
  --bucket my-bucket \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-processor",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "uploads/"}]}}
    }]
  }'

# Invoke directly for testing
aws lambda invoke \
  --function-name my-processor \
  --payload '{"key": "value"}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

**Lambda Destinations:** Route async invocation results (success or failure) to SQS, SNS, Lambda, or EventBridge without code changes. Prefer over DLQs for async invocations because destinations carry the full invocation record.

**Lambda container images:** Package functions as Docker containers up to 10 GB. Must implement the Lambda Runtime Interface Client (RIC). Useful for large dependencies (ML models, native binaries).

**Common gotchas:**
- Lambda functions inside a VPC add cold start time (ENI attachment). Use VPC only when necessary (e.g., accessing RDS). Lambda VPC-to-internet requires a NAT Gateway.
- Concurrency is shared across all functions in an account per region. One runaway function can starve others. Use reserved concurrency to isolate critical functions.
- Lambda pricing: $0.20 per 1M requests + $0.0000166667 per GB-second. Memory allocation directly affects CPU allocation. Sometimes doubling memory halves execution time and costs the same — always benchmark before assuming more memory costs more money.

### 2.3 ECS vs EKS (Container Orchestration)

When you need to run containers in production, AWS gives you two main paths: ECS (their own thing) and EKS (managed Kubernetes). Here is the real tradeoff.

**ECS (Elastic Container Service):**
- AWS-native container orchestrator
- Simpler mental model: Task Definitions (container specs) -> Services (desired count, scaling) -> Cluster
- Tightly integrated with ALB, CloudWatch, IAM, Secrets Manager
- No control plane cost
- Best for: Teams that want containers without Kubernetes complexity

**EKS (Elastic Kubernetes Service):**
- Managed Kubernetes control plane
- Full Kubernetes API compatibility
- Can run the same manifests as on-prem or other clouds
- Control plane cost: ~$0.10/hr ($73/month)
- Best for: Teams already on Kubernetes, multi-cloud strategies, advanced scheduling needs

**Fargate vs EC2 Launch Type:**

| Factor | Fargate (Serverless) | EC2 Launch Type |
|---|---|---|
| Management | No instances to manage | You manage EC2 instances |
| Pricing | Per vCPU + memory/second | EC2 instance pricing |
| Cost at scale | 20-40% more expensive | Cheaper with reserved instances |
| Startup time | 30-60 seconds | Faster if instances have capacity |
| GPU support | No | Yes |
| Best for | Variable workloads, small teams | Steady-state, GPU, cost optimization |

Here is my honest take on the Fargate vs EC2 question: **for most teams, start with Fargate**. The operational savings of not managing EC2 instances — no patching, no capacity planning, no figuring out why the node pool is at 94% and a new task won't schedule — easily outweigh the 20-40% cost premium until you are spending real money (think $5K+/month on compute). At that point, run the numbers, consider reserved EC2 capacity, and migrate the services that justify it. But ECS on Fargate first is the right default.

```bash
# ECS: Create a Fargate service
aws ecs create-service \
  --cluster my-cluster \
  --service-name my-api \
  --task-definition my-api:3 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-abc,subnet-def],securityGroups=[sg-123],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=8080"
```

### 2.4 App Runner

**What it is:** The simplest way to run containers on AWS. Point it at a container image or source repo, and it handles build, deploy, scaling, and TLS.

Think of App Runner as Heroku on AWS. You give it a container image and a port, and in five minutes you have a URL. It's not for everything — you lose control over networking, you can't attach it to your VPC without extra config, and it doesn't make sense at scale. But for a quick API, an internal tool, or a prototype you want to show a customer this afternoon, it's the fastest path from container to public URL on AWS.

**When to use:** Prototypes, simple APIs, when you do not want to configure VPC/ALB/ECS.

**When NOT to use:** Complex networking, multi-container pods, GPU workloads, cost-sensitive production at scale.

```bash
aws apprunner create-service \
  --service-name my-api \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-api:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {"Port": "8080"}
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{"Cpu": "1024", "Memory": "2048"}'
```

### 2.5 Elastic Beanstalk

**What it is:** PaaS that provisions EC2, ALB, Auto Scaling, RDS, etc., from a single configuration. Deploys applications from ZIP files or Docker containers.

Beanstalk occupies a weird middle ground: it creates real AWS resources you can inspect and customize, but abstracts enough away that you lose fine-grained control. It made a lot of sense in 2013. Today, if you want simplicity, App Runner is simpler. If you want control, ECS is worth the learning curve.

**When it makes sense:** Legacy apps that need a quick lift-and-shift, teams unfamiliar with IaC, simple CRUD apps.

**When to avoid:** Microservices (use ECS/EKS), serverless (use Lambda), anything requiring fine-grained infrastructure control.

---

## 3. NETWORKING

### 3.1 VPC Design Patterns

**VPC (Virtual Private Cloud):** Your isolated network in AWS. Every resource you launch goes into a VPC. Think of it as carving out your own section of AWS's network — your IP address space, your routing rules, your firewall rules, completely isolated from other AWS accounts.

The mental model: public subnets have a direct route to the internet. Private subnets do not. Your load balancers and NAT Gateways live in public subnets. Your application servers and databases live in private subnets. That separation is the foundation of every secure AWS architecture.

**Standard multi-AZ production VPC:**

```
VPC: 10.0.0.0/16 (65,536 IPs)
├── AZ-a
│   ├── Public Subnet:  10.0.1.0/24  (256 IPs) -- ALB, NAT Gateway, bastion
│   ├── Private Subnet: 10.0.10.0/24 (256 IPs) -- App servers (ECS, EC2)
│   └── Data Subnet:    10.0.20.0/24 (256 IPs) -- RDS, ElastiCache
├── AZ-b
│   ├── Public Subnet:  10.0.2.0/24
│   ├── Private Subnet: 10.0.11.0/24
│   └── Data Subnet:    10.0.21.0/24
└── AZ-c
    ├── Public Subnet:  10.0.3.0/24
    ├── Private Subnet: 10.0.12.0/24
    └── Data Subnet:    10.0.22.0/24
```

**Key components:**
- **Internet Gateway (IGW):** Enables internet access for public subnets
- **NAT Gateway:** Lets private subnet resources reach the internet (for updates, API calls) without being directly accessible. Deployed in public subnets, one per AZ for high availability
- **Route Tables:** Public subnets route `0.0.0.0/0` to IGW. Private subnets route `0.0.0.0/0` to NAT Gateway

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=prod-vpc}]'

# Create subnets
aws ec2 create-subnet --vpc-id vpc-abc123 --cidr-block 10.0.1.0/24 --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-1a}]'

# Create and attach internet gateway
aws ec2 create-internet-gateway --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=prod-igw}]'
aws ec2 attach-internet-gateway --internet-gateway-id igw-abc123 --vpc-id vpc-abc123

# Create NAT Gateway (requires an Elastic IP)
aws ec2 allocate-address --domain vpc
aws ec2 create-nat-gateway --subnet-id subnet-public-1a --allocation-id eipalloc-abc123
```

### 3.2 Security Groups vs NACLs

This is one of those AWS concepts where the docs tell you what it is, but not when to use which. The short version: use Security Groups for almost everything. NACLs are your blunt backup.

| Feature | Security Groups | NACLs |
|---|---|---|
| Scope | ENI (instance/container level) | Subnet level |
| Statefulness | **Stateful** (return traffic auto-allowed) | **Stateless** (must explicitly allow return traffic) |
| Rules | Allow rules only | Allow AND deny rules |
| Evaluation | All rules evaluated | Rules evaluated in order (lowest number first) |
| Default | Deny all inbound, allow all outbound | Allow all inbound and outbound |

**Best practice:** Use Security Groups as your primary firewall. Use NACLs as a coarse-grained backup (e.g., blocking known bad IP ranges at the subnet level). The stateless nature of NACLs trips up almost every team the first time they use them — if you allow port 443 inbound but forget to allow ephemeral ports 1024-65535 outbound, TLS handshakes fail in mysterious ways.

```bash
# Create security group for a web server
aws ec2 create-security-group --group-name web-sg --description "Web server SG" --vpc-id vpc-abc123

# Allow HTTP/HTTPS from anywhere, SSH from office IP only
aws ec2 authorize-security-group-ingress --group-id sg-abc123 \
  --ip-permissions \
  'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=203.0.113.0/24,Description=Office}]'

# Security group referencing: allow app tier to reach DB tier
aws ec2 authorize-security-group-ingress --group-id sg-db \
  --ip-permissions 'IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=sg-app}]'
```

### 3.3 ALB vs NLB vs API Gateway

Three ways to get traffic into your application, and the choice matters more than most teams realize:

**ALB (Application Load Balancer) -- Layer 7:**
- HTTP/HTTPS traffic, path-based and host-based routing
- WebSocket support, gRPC support
- Native integration with ECS, EKS, EC2, Lambda
- WAF integration for web application firewall
- Use for: Web applications, microservices with HTTP APIs

**NLB (Network Load Balancer) -- Layer 4:**
- TCP/UDP/TLS traffic, ultra-low latency (~100us overhead)
- Static IP addresses and Elastic IP support
- Millions of requests per second
- Use for: Real-time gaming, IoT, non-HTTP protocols, extreme performance requirements

**API Gateway:**
- Fully managed API front door
- REST APIs (v1) and HTTP APIs (v2 -- cheaper, faster, simpler)
- Built-in authentication (Cognito, Lambda authorizers, IAM)
- Rate limiting, usage plans, API keys
- WebSocket APIs for real-time bidirectional communication
- Use for: Serverless APIs (API Gateway -> Lambda), API management with throttling/auth

```
Request Flow Comparison:

ALB:     Client -> ALB (path routing) -> Target Group -> ECS/EC2/Lambda
NLB:     Client -> NLB (TCP passthrough) -> Target Group -> EC2/ECS
API GW:  Client -> API Gateway (auth, throttle, transform) -> Lambda/HTTP endpoint
```

**When to use each:**
- Public-facing web app with multiple microservices: **ALB**
- Need static IP or non-HTTP protocol: **NLB**
- Serverless API with Lambda: **API Gateway (HTTP API)**
- Need request/response transformation, API keys, usage plans: **API Gateway (REST API)**
- Internal service-to-service: **ALB (internal)** or **App Mesh/Service Connect**

### 3.4 Route 53 (DNS)

**What it is:** AWS's DNS service with 100% SLA. Also handles domain registration and health checks.

Route 53 is more than DNS — the routing policies are where it gets powerful for multi-region and disaster recovery setups:

**Routing Policies:**

| Policy | How It Works | Use Case |
|---|---|---|
| Simple | Returns a single value (or multiple for client-side random) | Single resource |
| Weighted | Distributes traffic by weight (e.g., 80/20) | Canary deployments, A/B testing |
| Latency | Routes to the region with lowest latency to user | Multi-region active-active |
| Failover | Primary/secondary with health checks | Disaster recovery |
| Geolocation | Routes based on user's geographic location | Compliance (data sovereignty), localization |
| Geoproximity | Routes based on distance, with adjustable bias | Shift traffic between regions gradually |
| Multivalue Answer | Returns up to 8 healthy records randomly | Simple load balancing with health checks |

```bash
# Create a weighted routing record (for canary deployments)
aws route53 change-resource-record-sets --hosted-zone-id Z123456 --change-batch '{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "api.example.com",
      "Type": "A",
      "SetIdentifier": "primary",
      "Weight": 90,
      "AliasTarget": {
        "HostedZoneId": "Z35SXDOTRQ7X7K",
        "DNSName": "primary-alb-123.us-east-1.elb.amazonaws.com",
        "EvaluateTargetHealth": true
      }
    }
  }]
}'
```

### 3.5 CloudFront (CDN)

**What it is:** Global content delivery network with 400+ edge locations. Caches content close to users.

CloudFront is the front door for almost every high-traffic AWS architecture. But it does more than cache static files — it's a programmable edge layer where you can run code, manipulate requests and responses, and make routing decisions before traffic ever reaches your origin.

**Key features:**
- **Origins:** S3, ALB, EC2, API Gateway, any HTTP endpoint
- **Lambda@Edge:** Run Node.js/Python at edge locations. Full request/response manipulation. ~5ms cold start. Use for: A/B testing, auth, SEO, dynamic origin selection
- **CloudFront Functions:** Lighter-weight, JavaScript only, ~1ms execution. Use for: URL rewrites, header manipulation, simple redirects, cache key normalization
- **Origin Shield:** Extra caching layer between edge and origin. Reduces origin load by collapsing requests across regions into one origin fetch

```bash
# Create CloudFront distribution for S3 static site + API
aws cloudfront create-distribution --distribution-config '{
  "CallerReference": "unique-string-123",
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-website",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true
  },
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "s3-website",
        "DomainName": "my-bucket.s3.us-east-1.amazonaws.com",
        "S3OriginConfig": {"OriginAccessIdentity": ""}
      },
      {
        "Id": "api-backend",
        "DomainName": "api-alb-123.us-east-1.elb.amazonaws.com",
        "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "https-only"}
      }
    ]
  },
  "CacheBehaviors": {
    "Quantity": 1,
    "Items": [{
      "PathPattern": "/api/*",
      "TargetOriginId": "api-backend",
      "ViewerProtocolPolicy": "https-only",
      "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    }]
  },
  "Enabled": true
}'
```

### 3.6 VPC Connectivity

Once you have multiple VPCs — or need to connect AWS to on-premises — you have several options with different tradeoffs:

**VPC Peering:** Direct network connection between two VPCs. Non-transitive (A-B and B-C does not mean A-C). Free for same-AZ traffic. Use for: Simple two-VPC connectivity.

**Transit Gateway:** Hub-and-spoke network connecting multiple VPCs and on-premises networks. Transitive routing. Use for: Organizations with many VPCs, hybrid cloud.

**PrivateLink (VPC Endpoints):**
- **Gateway Endpoints:** Free. S3 and DynamoDB only. Routes traffic through VPC route table.
- **Interface Endpoints:** Creates ENIs in your VPC. Accesses AWS services privately without internet. $0.01/hr per AZ + data processing. Use for: Keeping traffic off the public internet.

**Direct Connect:** Dedicated physical network connection from your data center to AWS. 1 Gbps or 10 Gbps. Lower latency, consistent bandwidth, reduced data transfer costs. Lead time: weeks to months.

**AWS Global Accelerator:** Routes traffic through AWS's global network instead of the public internet. Provides two static anycast IPs. Improves performance by 60% for users far from your region. Use for: Global TCP/UDP applications where CloudFront (HTTP-only) does not apply.

---

## 4. STORAGE & DATABASES

### 4.1 S3 (Simple Storage Service)

S3 is the most fundamental AWS service. Not the most exciting, but the most important. Almost every other service integrates with it: Lambda reads from it, CloudFront serves from it, Athena queries it, Glue processes it, CloudTrail logs to it. If you learn one AWS service deeply before the others, make it S3.

The core insight: S3 is not a filesystem. It's an object store. Objects have a key (the path), a value (the bytes), and metadata. There are no directories — just key prefixes. The "/" in `logs/2024/01/15/app.log` is a convention, not a real folder structure. Once you internalize that, the rest of S3 makes sense.

**Storage Classes:**

| Class | Durability | Availability | Min Duration | Use Case | Cost (per GB/mo, us-east-1) |
|---|---|---|---|---|---|
| Standard | 99.999999999% (11 9s) | 99.99% | None | Frequently accessed data | $0.023 |
| Intelligent-Tiering | 11 9s | 99.9% | None | Unknown/changing access patterns | $0.023 + $0.0025/1K objects monitoring |
| Standard-IA | 11 9s | 99.9% | 30 days | Infrequent but rapid access | $0.0125 |
| One Zone-IA | 11 9s | 99.5% | 30 days | Reproducible infrequent data | $0.01 |
| Glacier Instant | 11 9s | 99.9% | 90 days | Archive with ms retrieval | $0.004 |
| Glacier Flexible | 11 9s | 99.99% | 90 days | Archive (1-12 hr retrieval) | $0.0036 |
| Glacier Deep Archive | 11 9s | 99.99% | 180 days | Long-term archive (12-48 hr) | $0.00099 |

**Lifecycle policies -- automate tiering:**
```bash
aws s3api put-bucket-lifecycle-configuration --bucket my-bucket --lifecycle-configuration '{
  "Rules": [{
    "ID": "archive-old-data",
    "Status": "Enabled",
    "Filter": {"Prefix": "logs/"},
    "Transitions": [
      {"Days": 30, "StorageClass": "STANDARD_IA"},
      {"Days": 90, "StorageClass": "GLACIER_IR"},
      {"Days": 365, "StorageClass": "DEEP_ARCHIVE"}
    ],
    "Expiration": {"Days": 2555}
  }]
}'
```

**Versioning:** Preserves every version of every object. Enables MFA Delete for critical buckets. Versioning cannot be disabled once enabled -- only suspended.

**Encryption:**
- **SSE-S3:** AWS manages keys. Default since January 2023. Zero configuration.
- **SSE-KMS:** You control the key in KMS. Audit key usage in CloudTrail. Adds KMS API costs.
- **SSE-C:** You provide the encryption key with each request. AWS does not store your key.

**S3 Select / S3 Object Lambda:** Query CSV/JSON/Parquet data in place without downloading entire objects. Reduces data transfer by up to 400%.

**Event notifications:** Trigger Lambda, SQS, SNS, or EventBridge on object creation, deletion, or restoration. Foundation of event-driven architectures.

**Common gotchas:**
- S3 is eventually consistent for overwrite PUTs and DELETEs (this was fixed -- S3 now provides strong read-after-write consistency as of December 2020).
- Pricing has three components: storage, requests, and data transfer. High-frequency small object access can be expensive on request costs alone.
- `ListObjects` calls are expensive at scale ($0.005 per 1K requests). Use S3 Inventory for large-scale listing.

### 4.2 DynamoDB

DynamoDB is one of the most powerful and most misused databases in the AWS ecosystem. It delivers single-digit millisecond latency at any scale — and it means it. Netflix, Amazon itself, Lyft — these are DynamoDB shops for good reason. But teams coming from relational databases hit a wall because the query model is completely different.

The key mindset shift: **with relational databases, you design your schema and figure out queries later. With DynamoDB, you design your access patterns first and build your schema around them.** Get this backwards and you will end up with full table scans in production, which is both slow and expensive.

**Data model:**
- **Table** -> collection of **Items** (rows)
- Each item has **Attributes** (columns), but schema is flexible per item
- **Partition Key (PK):** Required. Determines data distribution across partitions
- **Sort Key (SK):** Optional. Enables range queries within a partition

**The single most important DynamoDB skill is partition key design.**

**Design principles:**
1. **Start with access patterns, not entities.** List every query your app needs. Design keys to serve those queries.
2. **High-cardinality partition keys.** Avoid hot partitions. Bad: `status` (only a few values). Good: `userId`, `orderId`.
3. **Composite sort keys.** Use delimiters to enable hierarchical queries: `SK = "ORDER#2024-01-15#12345"` allows querying all orders for a date range.

**Single-table design pattern:**
```
PK                  SK                      Attributes
USER#u123           PROFILE                 {name, email, ...}
USER#u123           ORDER#2024-01-15#o456   {total, status, ...}
USER#u123           ORDER#2024-01-20#o789   {total, status, ...}
ORG#acme            MEMBER#u123             {role, joinedAt, ...}
ORG#acme            MEMBER#u456             {role, joinedAt, ...}
```

This allows:
- Get user profile: `PK = USER#u123, SK = PROFILE`
- Get user's orders: `PK = USER#u123, SK begins_with ORDER#`
- Get user's orders in date range: `PK = USER#u123, SK between ORDER#2024-01-01 and ORDER#2024-02-01`
- Get org members: `PK = ORG#acme, SK begins_with MEMBER#`

**GSIs and LSIs:**
- **GSI (Global Secondary Index):** Different partition key and sort key. Eventually consistent. Own provisioned capacity. Create up to 20 per table. **Use freely -- this is how you support additional access patterns.**
- **LSI (Local Secondary Index):** Same partition key, different sort key. Strongly consistent option. Must be created at table creation time. Max 10 GB per partition key value.

**Capacity modes:**

| Mode | Pricing | Best For |
|---|---|---|
| On-Demand | Per-request pricing ($1.25/M writes, $0.25/M reads) | Unpredictable traffic, new tables, development |
| Provisioned | Per-RCU/WCU-hour + auto-scaling | Predictable workloads, cost optimization |

**DynamoDB Streams:** Capture item-level changes (INSERT, MODIFY, REMOVE) in order. Feed to Lambda for event-driven architectures. 24-hour retention. Use for: Materialized views, cross-region replication, analytics pipelines.

**DAX (DynamoDB Accelerator):** In-memory cache for DynamoDB. Microsecond read latency. Drop-in replacement (same API). Use for: Read-heavy workloads with repeated access patterns.

**TTL (Time to Live):** Automatically delete expired items at no cost. Set a TTL attribute with a Unix timestamp. Items are deleted within 48 hours of expiration (not exact).

```bash
# Create a DynamoDB table with on-demand capacity
aws dynamodb create-table \
  --table-name Orders \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
    AttributeName=GSI1PK,AttributeType=S \
    AttributeName=GSI1SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[{
    "IndexName": "GSI1",
    "KeySchema": [
      {"AttributeName": "GSI1PK", "KeyType": "HASH"},
      {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
    ],
    "Projection": {"ProjectionType": "ALL"}
  }]' \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Environment,Value=production

# Enable DynamoDB Streams
aws dynamodb update-table \
  --table-name Orders \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES

# Enable TTL
aws dynamodb update-time-to-live \
  --table-name Orders \
  --time-to-live-specification Enabled=true,AttributeName=expiresAt
```

**Common gotchas:**
- 400 KB max item size. If you need larger documents, store metadata in DynamoDB and the blob in S3.
- GSI writes consume additional WCUs. Projecting all attributes to a GSI doubles your write costs.
- Hot partitions cause throttling even with remaining capacity. Use write sharding (append random suffix to PK) for high-throughput scenarios.
- `Scan` reads the entire table. Never scan in production unless you truly need every item. Use `Query` with proper key design.
- Transactions cost 2x normal capacity (2 WCUs per transactional write vs 1).

### 4.3 RDS & Aurora

When your data is fundamentally relational — complex transactions, joins across multiple tables, constraints you actually need enforced — use RDS. AWS's managed relational database service handles the things you don't want to: provisioning, patching, backups, failover.

**Engine selection:**

| Engine | Best For | Notes |
|---|---|---|
| PostgreSQL | General purpose, complex queries, JSON, geospatial | Most feature-rich open-source option |
| MySQL | Web applications, read-heavy workloads | Widest tool/framework compatibility |
| Aurora (PostgreSQL/MySQL) | Production workloads needing 5x MySQL / 3x PostgreSQL throughput | AWS-proprietary storage layer, auto-scaling storage |
| MariaDB | MySQL alternative, community-driven | Use if you need MySQL-compatible but prefer open governance |
| SQL Server | .NET applications, Windows ecosystem | License included or bring your own |
| Oracle | Legacy enterprise applications | Expensive; migrate away if possible |

**Aurora architecture:**
- Storage is decoupled from compute. 6 copies of data across 3 AZs automatically.
- Storage auto-scales from 10 GB to 128 TB. You never provision storage.
- Aurora Serverless v2: Scales compute capacity in fine-grained increments (0.5 ACU steps). Scales to zero (with cold start). Use for: Dev/test, infrequent workloads, variable traffic.

If you are starting a new production PostgreSQL workload on AWS, Aurora PostgreSQL is the right default. The storage engine handles replication automatically, failover is significantly faster than standard RDS Multi-AZ (seconds vs minutes), and you never think about disk provisioning again.

**Read replicas vs Multi-AZ:**
- **Multi-AZ:** Synchronous standby replica for high availability. Automatic failover in ~60 seconds. You do not read from it. Use for: Production databases.
- **Read Replicas:** Asynchronous replicas for read scaling. Up to 15 for Aurora, 5 for other engines. Can be promoted to standalone. Can be cross-region. Use for: Read-heavy workloads, reporting, cross-region reads.

**RDS Proxy:** Connection pooling for RDS/Aurora. Multiplexes thousands of application connections into a smaller pool of database connections. Reduces failover time to <1 second. Essential for Lambda -> RDS (Lambda can exhaust connection limits).

```bash
# Create Aurora PostgreSQL cluster
aws rds create-db-cluster \
  --db-cluster-identifier prod-cluster \
  --engine aurora-postgresql \
  --engine-version 15.4 \
  --master-username admin \
  --manage-master-user-password \
  --db-subnet-group-name my-db-subnet-group \
  --vpc-security-group-ids sg-db-123 \
  --storage-encrypted \
  --backup-retention-period 7

# Create writer instance
aws rds create-db-instance \
  --db-instance-identifier prod-writer \
  --db-cluster-identifier prod-cluster \
  --engine aurora-postgresql \
  --db-instance-class db.r6g.xlarge

# Create reader instance
aws rds create-db-instance \
  --db-instance-identifier prod-reader-1 \
  --db-cluster-identifier prod-cluster \
  --engine aurora-postgresql \
  --db-instance-class db.r6g.large

# Create RDS Proxy (for Lambda connections)
aws rds create-db-proxy \
  --db-proxy-name my-proxy \
  --engine-family POSTGRESQL \
  --auth '[{"AuthScheme":"SECRETS","SecretArn":"arn:aws:secretsmanager:...","IAMAuth":"REQUIRED"}]' \
  --role-arn arn:aws:iam::123456789012:role/rds-proxy-role \
  --vpc-subnet-ids subnet-abc subnet-def \
  --vpc-security-group-ids sg-proxy
```

**Performance Insights:** Free tier available. Shows which SQL queries consume the most CPU/IO and which sessions are waiting. Essential for database performance troubleshooting.

**Common gotchas:**
- Aurora storage is billed even after deleting data (storage does not shrink). Dumping and restoring to a new cluster is the workaround.
- Multi-AZ failover causes a brief DNS change, not a connection keepalive. Applications must handle reconnection.
- RDS instances inside a VPC are not publicly accessible by default. This is the correct configuration for production.

### 4.4 ElastiCache

**What it is:** Managed Redis or Memcached for in-memory caching.

**Redis vs Memcached:**

| Feature | Redis | Memcached |
|---|---|---|
| Data structures | Strings, lists, sets, sorted sets, hashes, streams | Simple key-value strings |
| Persistence | Yes (RDB snapshots, AOF) | No |
| Replication | Yes (read replicas) | No |
| Cluster mode | Yes (data sharding) | Yes (multi-node) |
| Pub/Sub | Yes | No |
| Lua scripting | Yes | No |
| Multi-threaded | Single-threaded (but I/O threads in Redis 7) | Multi-threaded |

**Use Redis unless** you only need simple string caching and want multi-threaded performance. Redis covers 95% of use cases and gives you a surprising amount of leverage beyond caching: rate limiting with sorted sets, leaderboards, pub/sub channels, queues via Redis Streams. It is one of those tools that rewards learning deeply.

**Common use cases:** Session storage, API response caching, rate limiting (sorted sets with timestamps), leaderboards (sorted sets), real-time analytics, message queues (Redis Streams).

**Cluster mode:** Shards data across up to 500 nodes with up to 500 shards. Enables horizontal scaling for both reads and writes. Without cluster mode, you are limited to the memory of a single node (max ~635 GB on r7g.16xlarge).

### 4.5 Specialty Databases

**DocumentDB:** MongoDB-compatible document database. Use when: You need MongoDB API compatibility but want AWS management. Note: Not actually MongoDB under the hood. Some compatibility gaps exist.

**Neptune:** Graph database (supports Gremlin and SPARQL). Use for: Social networks, knowledge graphs, fraud detection, recommendation engines.

**Keyspaces:** Managed Apache Cassandra-compatible. Use for: Wide-column workloads, IoT time-series data, workloads already on Cassandra.

**Timestream:** Purpose-built time-series database. Automatic data tiering from memory to magnetic storage. Use for: IoT metrics, DevOps monitoring, financial ticks. Up to 1000x faster and 1/10th the cost of relational databases for time-series queries.

---

## 5. MESSAGING & EVENT-DRIVEN

### 5.1 SQS (Simple Queue Service)

SQS is the workhorse of async processing on AWS. Any time you have work that doesn't need to happen synchronously — sending emails, processing uploaded files, updating analytics, talking to slow third-party APIs — you put it in a queue. The producer drops a message and moves on. The consumer works through the queue at its own pace. The two sides scale independently.

**Standard vs FIFO:**

| Feature | Standard | FIFO |
|---|---|---|
| Throughput | Unlimited | 3,000 msg/sec with batching (300 without) |
| Ordering | Best-effort | Strict ordering within message groups |
| Delivery | At-least-once (possible duplicates) | Exactly-once processing |
| Price | $0.40/M requests | $0.50/M requests |

**Key concepts:**
- **Visibility Timeout:** After a consumer receives a message, it becomes invisible to other consumers for this duration (default 30s, max 12 hours). If not deleted within the timeout, the message reappears for retry.
- **Dead Letter Queue (DLQ):** Messages that fail processing N times are moved to a DLQ for inspection. Always configure this.
- **Long Polling:** Set `WaitTimeSeconds` to 1-20 seconds. Reduces empty responses and costs. Always enable.
- **Message Groups (FIFO):** Messages with the same `MessageGroupId` are processed in order. Different groups are processed in parallel.

```bash
# Create a FIFO queue with DLQ
aws sqs create-queue --queue-name orders-dlq.fifo --attributes '{"FifoQueue": "true"}'
aws sqs create-queue --queue-name orders.fifo --attributes '{
  "FifoQueue": "true",
  "ContentBasedDeduplication": "true",
  "VisibilityTimeout": "60",
  "ReceiveMessageWaitTimeSeconds": "20",
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:123456789012:orders-dlq.fifo\",\"maxReceiveCount\":\"3\"}"
}'

# Send a message to FIFO queue
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders.fifo \
  --message-body '{"orderId": "123", "amount": 99.99}' \
  --message-group-id "customer-456"
```

### 5.2 SNS (Simple Notification Service)

**What it is:** Pub/sub messaging. One message, many subscribers. Push-based delivery.

**Subscription types:** SQS, Lambda, HTTP/HTTPS, Email, SMS, Kinesis Data Firehose, platform push (iOS/Android).

**Message filtering:** Subscribers receive only messages matching a filter policy. Applied on message attributes, not the body. This eliminates consumer-side filtering logic.

```bash
# Create topic and subscribe an SQS queue with filter
aws sns create-topic --name order-events
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:order-events \
  --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:123456789012:high-value-orders \
  --attributes '{"FilterPolicy": "{\"order_value\": [{\"numeric\": [\">\", 1000]}]}"}'
```

**SNS + SQS fan-out pattern:** Publish to SNS topic, which fans out to multiple SQS queues. Each queue has its own consumer processing messages independently. The most common messaging pattern on AWS. When an order is placed, one message to the SNS topic triggers: inventory service, fulfillment service, analytics service, notification service — all independently, all with their own retry logic.

### 5.3 EventBridge

**What it is:** Serverless event bus for building event-driven architectures. The evolution of CloudWatch Events.

EventBridge is the backbone of modern event-driven AWS architectures. Where SQS is a queue (one producer, one consumer per message) and SNS is a pub/sub system (one-to-many fan-out), EventBridge is an event router with content-based filtering, schema registry, and native integration with 90+ AWS services and SaaS providers. It connects AWS services, SaaS apps, and your own applications.

**Key concepts:**
- **Event Bus:** Container for events. Default bus receives AWS service events. Create custom buses for your application events.
- **Rules:** Match events by pattern and route to targets. Up to 5 targets per rule.
- **Schema Registry:** Auto-discovers event schemas. Generates code bindings (TypeScript, Python, Java).
- **Pipes:** Point-to-point integration between a source and a target with optional filtering, enrichment, and transformation. Simpler than rules for 1:1 integrations.

```bash
# Create custom event bus
aws events create-event-bus --name my-app-events

# Create rule matching order events
aws events put-rule \
  --name process-high-value-orders \
  --event-bus-name my-app-events \
  --event-pattern '{
    "source": ["my-app.orders"],
    "detail-type": ["OrderCreated"],
    "detail": {"amount": [{"numeric": [">", 1000]}]}
  }'

# Add Lambda target
aws events put-targets \
  --rule process-high-value-orders \
  --event-bus-name my-app-events \
  --targets '[{"Id": "process-order", "Arn": "arn:aws:lambda:us-east-1:123456789012:function:process-order"}]'

# Publish event from your application
aws events put-events --entries '[{
  "Source": "my-app.orders",
  "DetailType": "OrderCreated",
  "Detail": "{\"orderId\": \"123\", \"amount\": 1500, \"customerId\": \"c456\"}",
  "EventBusName": "my-app-events"
}]'
```

**EventBridge vs SNS:** Use EventBridge when you need content-based filtering on event body, schema registry, archive/replay, or integration with SaaS. Use SNS for simple fan-out, SMS/email notifications, or mobile push.

### 5.4 Kinesis (Real-Time Streaming)

**What it is:** A family of services for real-time data streaming at scale.

**Kinesis Data Streams:**
- Real-time data ingestion (200ms latency)
- Ordered within a shard (like Kafka partitions)
- Retention: 24 hours (default) to 365 days
- Consumers: KCL (Kinesis Client Library), Lambda, enhanced fan-out
- On-demand mode: auto-scales shards, pay per GB ingested/retrieved
- Provisioned mode: you manage shard count ($0.015/shard-hour)

**Kinesis Data Firehose:**
- Fully managed delivery to S3, Redshift, Elasticsearch, Splunk, HTTP endpoints
- Near-real-time (60-second minimum buffering)
- Automatic batching, compression, encryption, transformation (via Lambda)
- Zero administration -- no shards to manage

**When to use Kinesis vs SQS:**
- Kinesis: Ordered processing, multiple consumers reading same data, real-time analytics, replay capability
- SQS: Simple task queues, one consumer per message, no ordering requirement, simpler operational model

**Enhanced fan-out:** Dedicated 2 MB/sec throughput per consumer per shard. Without it, all consumers share 2 MB/sec per shard. Use when you have multiple consumers and need low latency.

### 5.5 Step Functions

**What it is:** Visual workflow orchestrator. Coordinates multiple AWS services into serverless workflows using state machines defined in Amazon States Language (JSON).

Step Functions shine for workflows that span multiple services with retry logic, branching, parallel execution, and human approval steps. Instead of encoding complex workflow logic inside individual Lambda functions, you externalize it into the state machine. The functions stay small and focused; the orchestration lives in a visual graph you can actually inspect.

**Standard vs Express:**

| Feature | Standard | Express |
|---|---|---|
| Duration | Up to 1 year | Up to 5 minutes |
| Execution | Exactly-once | At-least-once |
| Pricing | Per state transition ($0.025/1K) | Per execution + duration |
| Use case | Long-running workflows, human approval | High-volume event processing, ETL |

**State types:**
- **Task:** Invoke a service (Lambda, ECS, DynamoDB, SQS, etc.)
- **Choice:** Branching logic (if/else)
- **Parallel:** Execute branches concurrently
- **Map:** Process items in an array (fan-out)
- **Wait:** Delay execution
- **Succeed/Fail:** Terminal states

**Error handling:**
```json
{
  "ProcessOrder": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:...:function:process-order",
    "Retry": [
      {
        "ErrorEquals": ["States.TaskFailed"],
        "IntervalSeconds": 3,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }
    ],
    "Catch": [
      {
        "ErrorEquals": ["States.ALL"],
        "Next": "HandleError",
        "ResultPath": "$.error"
      }
    ],
    "Next": "NotifySuccess"
  }
}
```

### 5.6 MSK (Managed Streaming for Apache Kafka)

**What it is:** Fully managed Apache Kafka. Use the Kafka API directly.

**When to use MSK over SQS/SNS/EventBridge:**
- You already have Kafka expertise and tooling
- Need log compaction (keep latest value per key)
- Need very high throughput (millions of events/sec)
- Need exact ordering with consumer groups
- Need the Kafka Connect ecosystem (hundreds of pre-built connectors)

**When NOT to use MSK:**
- Minimum 3 broker nodes (~$200/month minimum). SQS costs nearly nothing at low volume.
- Requires VPC, broker management, ZooKeeper (or KRaft). Operational overhead is significant.

The honest tradeoff: MSK is the right answer when you need Kafka's specific guarantees or ecosystem. But if you're reaching for Kafka because it "scales better," know that SQS and EventBridge at AWS scale are no joke. Most teams adopting MSK are either migrating an existing Kafka workload or have an engineering team with deep Kafka expertise. Greenfield event-driven architectures are usually better served by SQS + EventBridge.

---

## 6. SECURITY & IAM

### 6.1 IAM Deep Dive

IAM is the foundation of security on AWS. Every API call — every `GetObject`, every `CreateFunction`, every `DescribeInstances` — goes through IAM policy evaluation. If you understand IAM deeply, you understand how AWS security works. If you don't, you will either break things accidentally or leave things dangerously open.

**Core concepts:**
- **Users:** Long-term credentials (access keys). Use for humans and CI/CD. Prefer SSO/federated access for humans.
- **Groups:** Collections of users. Attach policies to groups, not individual users.
- **Roles:** Temporary credentials assumed by services, users, or external identities. Always prefer roles over static credentials.
- **Policies:** JSON documents defining permissions. Attached to users, groups, or roles.

**Policy types:**
- **Identity-based policies:** Attached to IAM identities (users, groups, roles). "What can this identity do?"
- **Resource-based policies:** Attached to AWS resources (S3 bucket policy, SQS queue policy). "Who can access this resource?"
- **Permission boundaries:** Maximum permissions an identity can have. Used for delegation.
- **Service Control Policies (SCPs):** Maximum permissions for an entire AWS account (via AWS Organizations).
- **Session policies:** Limit permissions for a specific session when assuming a role.

**Policy evaluation logic (simplified):**
1. All requests start as **implicit deny**
2. Evaluate all applicable policies
3. If any policy has an **explicit deny** -> DENY (deny always wins)
4. If any policy has an **allow** -> ALLOW
5. Otherwise -> DENY (implicit deny)

**Least privilege policy example:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowDynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:123456789012:table/Orders",
        "arn:aws:dynamodb:us-east-1:123456789012:table/Orders/index/*"
      ],
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:PrincipalTag/tenantId}"]
        }
      }
    }
  ]
}
```

### 6.2 Assuming Roles

Roles are the right way to grant access between services and accounts. A role has no long-lived credentials — it issues temporary tokens that expire. When a Lambda function needs to read from S3, it assumes a role. When a CI/CD system needs to deploy to your account, it assumes a role. When an engineer needs to access a production account, they assume a role.

**Cross-account access:** Account A creates a role that Account B can assume. Account B users call `sts:AssumeRole` to get temporary credentials.

```bash
# Assume a role (returns temporary credentials)
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/cross-account-role \
  --role-session-name my-session

# Use the returned credentials
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

# Or use named profiles in ~/.aws/config
# [profile cross-account]
# role_arn = arn:aws:iam::987654321098:role/cross-account-role
# source_profile = default
```

**Service roles:** IAM roles assumed by AWS services. Example: Lambda execution role, ECS task role, EC2 instance profile. These let your code call AWS APIs without embedding credentials.

### 6.3 AWS Organizations and SCPs

**What it is:** Centrally manage multiple AWS accounts. Accounts are organized into Organizational Units (OUs).

For any non-trivial company, running everything in a single AWS account is a mistake. Multiple accounts give you billing separation, blast radius containment, and the ability to apply different security policies to production vs development. AWS Organizations is how you manage all of them from a single place.

**SCPs (Service Control Policies):** Guardrails applied to accounts/OUs. They restrict what actions are allowed, even if an IAM policy grants them.

**Common SCP patterns:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyLeavingOrganization",
      "Effect": "Deny",
      "Action": "organizations:LeaveOrganization",
      "Resource": "*"
    },
    {
      "Sid": "RestrictToApprovedRegions",
      "Effect": "Deny",
      "NotAction": [
        "iam:*",
        "organizations:*",
        "sts:*",
        "support:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2", "eu-west-1"]
        }
      }
    }
  ]
}
```

### 6.4 Secrets Manager vs Parameter Store

Two services for storing sensitive configuration. The decision is mostly about cost and rotation:

| Feature | Secrets Manager | Parameter Store (SSM) |
|---|---|---|
| Cost | $0.40/secret/month + $0.05/10K API calls | Free tier (standard), $0.05/10K advanced |
| Auto-rotation | Built-in for RDS, Redshift, DocumentDB | Manual (via Lambda) |
| Cross-account | Yes (resource-based policy) | No (same account only) |
| Max size | 64 KB | 4 KB standard, 8 KB advanced |
| Best for | Database passwords, API keys, certificates | Configuration values, feature flags, non-secret params |

**Rule of thumb:** Use Secrets Manager for actual secrets that need rotation. Use Parameter Store for everything else (config values, feature flags, non-sensitive parameters).

```bash
# Store a secret
aws secretsmanager create-secret \
  --name prod/database/password \
  --secret-string '{"username":"admin","password":"s3cur3P@ss","host":"mydb.cluster-xyz.rds.amazonaws.com","port":5432}'

# Retrieve in application code (Node.js)
# const { SecretsManagerClient, GetSecretValueCommand } = require('@aws-sdk/client-secrets-manager');
# const secret = await client.send(new GetSecretValueCommand({ SecretId: 'prod/database/password' }));

# Store config in Parameter Store
aws ssm put-parameter \
  --name /prod/app/feature-flags \
  --value '{"darkMode": true, "newCheckout": false}' \
  --type String

# Store encrypted parameter
aws ssm put-parameter \
  --name /prod/app/api-key \
  --value "sk-abc123" \
  --type SecureString \
  --key-id alias/my-key
```

### 6.5 KMS (Key Management Service)

**What it is:** Managed encryption key service. Create, control, and audit encryption keys used to protect your data.

**Key types:**
- **AWS Managed Keys:** Created automatically by AWS services (e.g., `aws/s3`, `aws/rds`). Free. You cannot manage rotation or policies.
- **Customer Managed Keys (CMK):** You create and control. $1/month per key + $0.03/10K API calls. Full control over key policy and rotation.
- **Customer-provided keys:** You generate externally and import into KMS. Use when you need to control key material.

**Envelope encryption:**
1. KMS generates a data encryption key (DEK)
2. You encrypt your data with the plaintext DEK
3. You store the encrypted DEK alongside the encrypted data
4. To decrypt: KMS decrypts the DEK, then you decrypt the data
5. This avoids sending large data to KMS (4 KB API limit)

### 6.6 WAF and Shield

**WAF (Web Application Firewall):** Protects against common web exploits (SQL injection, XSS, bad bots). Attaches to ALB, API Gateway, CloudFront, App Runner. Use AWS Managed Rule Groups (free with WAF) for baseline protection.

**Shield Standard:** Free DDoS protection for all AWS customers (L3/L4 attacks). Automatic.

**Shield Advanced:** $3,000/month. L7 DDoS protection, 24/7 DDoS Response Team, cost protection (credits for scaling costs during attacks). Worth it only for high-value targets.

### 6.7 Audit and Detection

- **CloudTrail:** Records every API call in your AWS account. Who did what, when, and from where. Enable across all regions and all accounts. This is your audit log. If something goes wrong — a data breach, an accidental deletion, a privilege escalation — CloudTrail is how you reconstruct the story.
- **GuardDuty:** ML-powered threat detection. Analyzes CloudTrail, VPC Flow Logs, and DNS logs for suspicious activity. Enable it and forget about it (minimal operational overhead). Seriously, just turn it on in every account right now.
- **Security Hub:** Aggregated security findings from GuardDuty, Inspector, Macie, and third-party tools. Provides compliance checks (CIS benchmarks, PCI DSS, AWS Foundational).
- **VPC Flow Logs:** Capture IP traffic metadata for VPC, subnet, or ENI. Use for troubleshooting connectivity issues and security analysis.

---

## 7. DEVELOPER & OPERATIONS TOOLS

### 7.1 Infrastructure as Code

If you are clicking around the AWS console to create resources, you are building technical debt. Every resource you create needs to be reproducible, versionable, and auditable. That's what Infrastructure as Code (IaC) gives you.

**CloudFormation:**
- AWS-native IaC. JSON or YAML templates.
- Stacks are the unit of deployment. Stack sets deploy across accounts/regions.
- Change sets preview changes before applying.
- Drift detection shows manual changes.
- Drawback: verbose, slow feedback loop, limited programming constructs.

**CDK (Cloud Development Kit):**
- Write infrastructure in TypeScript, Python, Java, Go, C#.
- Synthesizes to CloudFormation. Higher-level constructs reduce boilerplate.
- L1 (1:1 CloudFormation), L2 (opinionated defaults), L3 (multi-resource patterns).
- Best for: Teams who prefer programming languages over YAML/HCL.

```typescript
// CDK example: Lambda + API Gateway + DynamoDB
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

const table = new dynamodb.Table(this, 'Orders', {
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});

const fn = new lambda.Function(this, 'Handler', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('lambda'),
  environment: { TABLE_NAME: table.tableName },
});
table.grantReadWriteData(fn);  // CDK generates the IAM policy for you

const api = new apigw.RestApi(this, 'Api');
api.root.addResource('orders').addMethod('POST', new apigw.LambdaIntegration(fn));
```

CDK is my recommendation for AWS-only infrastructure. The ability to use real programming constructs — loops, conditionals, functions, types — makes complex infrastructure dramatically more manageable than YAML. The `grantReadWriteData` call above is doing IAM policy work that would take ten lines of CloudFormation YAML. That's the leverage.

**Terraform on AWS:**
- Multi-cloud IaC. HCL language.
- State management is your responsibility (use S3 + DynamoDB for remote state).
- Largest provider ecosystem. Best for: Multi-cloud environments, teams already using Terraform.

**Decision matrix:**
- AWS-only, prefer YAML/simple: **CloudFormation**
- AWS-only, prefer programming languages: **CDK**
- Multi-cloud or already using Terraform: **Terraform**

### 7.2 CloudWatch

CloudWatch is your operational nervous system on AWS. Metrics, logs, alarms, dashboards — all centralized. Not the most beautiful tool, but deeply integrated with every AWS service.

**Metrics:** Built-in metrics for every AWS service. Custom metrics via `PutMetricData` API. Resolution: standard (1 minute) or high-resolution (1 second).

**Logs:** Centralized log storage. Log groups -> log streams -> log events.

**Logs Insights query language:**
```
# Find the slowest API requests in the last hour
fields @timestamp, @message
| filter @message like /duration/
| parse @message "duration=* ms" as duration
| sort duration desc
| limit 20

# Count errors by status code
fields @timestamp, status
| filter status >= 400
| stats count(*) as errorCount by status
| sort errorCount desc

# P99 latency by API endpoint
fields @timestamp, endpoint, duration
| stats percentile(duration, 99) as p99,
        percentile(duration, 95) as p95,
        avg(duration) as avg_duration
  by endpoint
| sort p99 desc
```

**Alarms:** Trigger on metric thresholds. Actions: SNS notification, Auto Scaling, EC2 action. Use composite alarms to reduce alert noise.

**Dashboards:** Build operational dashboards with metrics, logs, and alarms. Share with cross-functional teams.

### 7.3 X-Ray (Distributed Tracing)

**What it is:** Trace requests as they flow through your application. Visualize service maps and identify bottlenecks.

When you have a request that goes through API Gateway -> Lambda -> DynamoDB -> another Lambda -> SNS -> SQS -> another Lambda, and it's slow, X-Ray is how you find which step is the bottleneck. The service map visualization alone is worth the setup time.

**How it works:**
1. Instrument your application with the X-Ray SDK (or OpenTelemetry with X-Ray exporter)
2. SDK creates trace segments for each service, subsegments for downstream calls
3. X-Ray daemon forwards traces to the X-Ray service
4. Service map and trace timeline available in the console

**Key tip:** Use annotations for filterable trace attributes (e.g., `customerId`, `orderId`). Use metadata for non-filterable context.

### 7.4 Systems Manager (SSM)

**Parameter Store:** Covered in Security section. Hierarchical configuration storage.

**Session Manager:** SSH into EC2 instances without opening port 22 or managing SSH keys. Uses IAM for authentication. All sessions are logged to CloudWatch/S3. Use this instead of bastion hosts.

Session Manager is one of those features that seems minor until you realize what it eliminates: no bastion hosts to maintain, no SSH keys to rotate, no port 22 attack surface, and automatic session logging for compliance. If you're still running bastion hosts, switch to Session Manager.

```bash
# Start a session to an EC2 instance (no SSH key needed)
aws ssm start-session --target i-0123456789abcdef0

# Run a command across multiple instances
aws ssm send-command \
  --targets Key=tag:Environment,Values=production \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["df -h", "free -m"]'
```

### 7.5 CI/CD: AWS Native vs GitHub Actions

**AWS CodePipeline/CodeBuild/CodeDeploy:** Full CI/CD suite. Advantage: deep IAM integration, VPC access, no credential management. Disadvantage: clunky UI, slower iteration than GitHub Actions.

**GitHub Actions on AWS:** More popular, better developer experience, larger marketplace. Use OIDC federation (no long-lived AWS credentials):
```yaml
# .github/workflows/deploy.yml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/github-actions-role
      aws-region: us-east-1
  - run: aws ecs update-service --cluster prod --service api --force-new-deployment
```

**Recommendation:** Use GitHub Actions for CI/CD with OIDC role assumption unless you have a specific reason to use CodePipeline (e.g., CodeDeploy blue/green deployments for ECS, which integrate tightly with CodePipeline). OIDC federation means GitHub gets temporary credentials per workflow run — no long-lived access keys to rotate or accidentally leak.

---

## 8. COST OPTIMIZATION

Cost optimization on AWS isn't about being cheap. It's about being strategic — putting your money where it buys the most reliability, performance, and velocity, and not wasting it on idle resources or wrong-sized instances. The teams that do this well treat it like a normal engineering problem: instrument it, understand it, optimize iteratively.

### 8.1 AWS Pricing Models Explained

**On-Demand:** Pay by the hour/second with no commitment. Baseline price. Use for: Unpredictable workloads, short-term needs, initial exploration.

**Reserved Instances (RIs):** Commit to 1 or 3 years for a specific instance type in a specific region. Up to 72% discount. Payment options: all upfront (biggest discount), partial upfront, no upfront. Applies to: EC2, RDS, ElastiCache, Elasticsearch, Redshift.

**Savings Plans:** Commit to a consistent amount of compute usage (measured in $/hour) for 1 or 3 years. More flexible than RIs:
- **Compute Savings Plans:** Applies to any EC2 instance, Fargate, and Lambda. Most flexible.
- **EC2 Instance Savings Plans:** Locked to instance family in a region. Bigger discount.

**Spot Instances:** Bid on unused EC2 capacity. Up to 90% discount. AWS can reclaim with 2-minute notice. Use for: Batch processing, CI/CD, stateless web servers behind ASG, big data (EMR), ML training.

The playbook for mature AWS cost management: run your steady-state production workloads on Compute Savings Plans (commit to a dollar-per-hour amount, not a specific instance type), use spot instances for batch and CI/CD, and right-size everything with Compute Optimizer before committing. That combination routinely delivers 60-70% savings vs baseline on-demand pricing.

### 8.2 Cost Explorer and Budgets

```bash
# Get cost and usage for the last month
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-02-01 \
  --granularity MONTHLY \
  --metrics "BlendedCost" "UsageQuantity" \
  --group-by Type=DIMENSION,Key=SERVICE

# Create a budget alert
aws budgets create-budget --account-id 123456789012 --budget '{
  "BudgetName": "Monthly-Total",
  "BudgetLimit": {"Amount": "5000", "Unit": "USD"},
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}' --notifications-with-subscribers '[{
  "Notification": {
    "NotificationType": "ACTUAL",
    "ComparisonOperator": "GREATER_THAN",
    "Threshold": 80,
    "ThresholdType": "PERCENTAGE"
  },
  "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "team@example.com"}]
}]'
```

### 8.3 Common Cost Traps

These are the line items that routinely surprise teams on their first big AWS bill. None of them are unreasonable charges — they're all logical — but they're easy to overlook until you're staring at an unexpected $4,000 invoice.

| Trap | Typical Impact | Fix |
|---|---|---|
| **NAT Gateway data processing** | $0.045/GB processed. A busy app can rack up $1000+/month | Use VPC endpoints for S3/DynamoDB (free). Consider NAT instances for cost savings |
| **CloudWatch Logs ingestion** | $0.50/GB ingested | Reduce log verbosity in production. Use log levels. Set retention policies |
| **Cross-AZ data transfer** | $0.01/GB each way | Keep communicating services in the same AZ when possible. Use VPC endpoints |
| **Idle load balancers** | ~$16/month minimum per ALB | Delete unused ALBs. Consolidate with path-based routing |
| **Unattached EBS volumes** | $0.08-$0.125/GB/month | Audit with `aws ec2 describe-volumes --filters Name=status,Values=available` |
| **Forgotten resources** | Variable | Use AWS Resource Explorer. Tag everything. Review Cost Explorer weekly |
| **Oversized instances** | 2-4x overspend | Use Compute Optimizer recommendations. Right-size based on actual CPU/memory utilization |
| **Elastic IPs not attached** | $0.005/hour ($3.60/month) | Release unassociated Elastic IPs |
| **S3 incomplete multipart uploads** | Accumulate silently | Add lifecycle rule to abort incomplete multipart uploads after 7 days |

The NAT Gateway one deserves special emphasis. When your ECS tasks pull Docker images from ECR through a NAT Gateway, you pay $0.045/GB for every image layer. When your Lambda functions fetch secrets from Secrets Manager through a NAT Gateway, you pay $0.045/GB. The fix: add VPC endpoints for ECR, S3, and Secrets Manager. Free (or nearly free), and the NAT Gateway line on your bill drops dramatically.

---

## 9. ARCHITECTURE PATTERNS ON AWS

These are the reference architectures you will build variations of over and over. Not blueprints to copy blindly, but proven starting points with decisions already made for you.

### 9.1 Three-Tier Web Application

```
                     Route 53
                        |
                    CloudFront
                        |
                       ALB
                   /    |    \
              ECS-a  ECS-b  ECS-c    (Application Tier, Fargate)
                   \    |    /
              +-----+---+---+-----+
              |                   |
         Aurora Writer      Aurora Reader(s)
              |                   |
         ElastiCache (Redis)     S3 (static assets, uploads)
```

**Key decisions:**
- ECS Fargate for containers (unless cost requires EC2 launch type)
- Aurora for the database (automatic storage scaling, fast failover)
- ElastiCache for session storage and hot data caching
- CloudFront for static assets and API caching
- Private subnets for app and data tiers

### 9.2 Serverless API

```
    CloudFront (optional caching)
           |
      API Gateway (HTTP API)
           |
    Lambda Functions
      /    |    \
DynamoDB  S3  SQS -> Lambda (async processing)
```

**Key decisions:**
- HTTP API (not REST API) for 70% lower cost and lower latency
- DynamoDB on-demand for unpredictable traffic
- SQS for decoupling heavy processing from the API response
- No VPC for Lambda unless accessing RDS (faster cold starts)
- Use Lambda Powertools for structured logging, tracing, and metrics

### 9.3 Event-Driven Microservices

```
Service A  Service B  Service C
    \          |          /
     \         |         /
      EventBridge (central event bus)
     /    |    \    |    \
  SQS   SQS   SQS  SQS  SQS  (one queue per consumer)
   |      |     |    |     |
Lambda Lambda Lambda Lambda Lambda
   |      |     |    |     |
 DynamoDB RDS   S3  External  SNS (notification)
```

**Key decisions:**
- EventBridge as the event bus (content-based filtering, schema registry)
- SQS between EventBridge and Lambda (buffering, retry, DLQ)
- Each service owns its own data store
- Services communicate only through events, never direct DB access

### 9.4 Real-Time Streaming

```
IoT Devices / Click Streams / Application Logs
              |
        Kinesis Data Streams
         /         |        \
    Lambda   Kinesis Firehose  KCL Application
       |          |                |
  DynamoDB    S3 (data lake)   OpenSearch
  (real-time  (long-term        (search &
   counters)   storage)          analytics)
```

### 9.5 Multi-Region Active-Active

```
               Route 53 (latency-based routing)
              /                                \
     us-east-1                              eu-west-1
         |                                      |
    CloudFront                             CloudFront
         |                                      |
        ALB                                    ALB
         |                                      |
    ECS Cluster                           ECS Cluster
         |                                      |
    Aurora Writer  <-- replication -->    Aurora Reader
    (Global DB)                          (Global DB, can promote)
         |                                      |
    ElastiCache                           ElastiCache
    (Global Datastore)                    (Global Datastore)
```

**Key decisions:**
- Aurora Global Database: <1 second replication lag across regions
- ElastiCache Global Datastore: cross-region Redis replication
- DynamoDB Global Tables: multi-region, multi-active (no primary/replica distinction)
- Route 53 health checks with failover routing
- Conflict resolution strategy required for writes in multiple regions

---

## 10. FRONTEND DEPLOYMENT ON AWS

### 10.1 SPA Deployment: S3 + CloudFront

**Why S3 alone is not enough:** S3 static website hosting gives you an HTTP endpoint, but no HTTPS, no custom domain with TLS, no edge caching, and no SPA routing (refreshing `/dashboard` returns 404). CloudFront solves all of these.

The standard architecture is: S3 bucket (private, block all public access) -> CloudFront with **Origin Access Control (OAC)** -> custom error responses for SPA routing. This is the same pattern serving millions of React, Vue, and Svelte apps in production. Get this right once and you will use it everywhere.

**The standard architecture:** S3 bucket (private, block all public access) -> CloudFront with **Origin Access Control (OAC)** -> custom error responses for SPA routing.

```hcl
# Terraform: Full SPA stack (S3 + CloudFront + ACM + Route 53)
resource "aws_s3_bucket" "spa" {
  bucket = "myapp-frontend-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "spa" {
  bucket                  = aws_s3_bucket.spa.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "spa" {
  name                              = "spa-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "spa" {
  origin {
    domain_name              = aws_s3_bucket.spa.bucket_regional_domain_name
    origin_id                = "s3-spa"
    origin_access_control_id = aws_cloudfront_origin_access_control.spa.id
  }

  enabled             = true
  default_root_object = "index.html"

  # SPA routing: serve index.html for all 403/404 from S3
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-spa"
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # CachingOptimized
    compress               = true
  }

  aliases = [var.domain_name]

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.spa.arn  # Must be us-east-1
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }
}
```

**Custom domain setup:** Route 53 alias record pointing to the CloudFront distribution. The ACM certificate **must be in us-east-1** regardless of where your bucket lives -- CloudFront is a global service that reads certs from us-east-1 only. This trips up everyone at least once.

### 10.2 Caching Architecture

**Three cache layers** operate between your users and S3:

| Layer | Controls | Where |
|---|---|---|
| **Browser cache** | `Cache-Control` header on the object | User's browser |
| **CloudFront edge cache** | TTL in cache behavior + origin headers | 400+ edge locations |
| **S3 origin** | Object metadata | Single region |

**The fingerprinting pattern** (used by every modern bundler):
- **`index.html`**: `Cache-Control: no-cache` -- always revalidated so users get the latest entry point
- **Hashed assets** (`main.a3f8c2.js`, `style.b7d1e4.css`): `Cache-Control: public, max-age=31536000, immutable` -- cached for 1 year because the filename changes when content changes

This is the elegant part of the pattern: `index.html` is tiny and always fresh, but it references the hashed assets, which are huge and always served from cache. New deploy = new hashes = new filenames = instant global rollout with zero cache invalidation cost.

**Cache invalidation options:**
- **CloudFront invalidation** (`/*`): Costs $0.005 per path after the first 1,000/month. Good for emergencies, not for every deploy.
- **Versioned paths** (`/v2/app.js`): No invalidation needed. Best for APIs and shared libraries.
- **Fingerprinted filenames**: The best approach for SPAs -- deploy new files, update `index.html`, old files age out.

**Debugging stale content:** Check CloudFront response headers. `X-Cache: Hit from cloudfront` means edge served it. `Age: 3600` tells you seconds since edge cached it. `Via` confirms the request went through CloudFront.

### 10.3 Edge Logic

**CloudFront Functions** run at viewer request/response. They are lightweight (max 10 KB, <1 ms execution, no network access). Use for:
- URL rewrites (trailing slash normalization, `www` redirect)
- Security headers injection
- Simple A/B routing via cookies
- Geo-based redirects using `CloudFront-Viewer-Country`

```javascript
// CloudFront Function: Add security headers to every response
function handler(event) {
  var response = event.response;
  var headers = response.headers;
  headers['strict-transport-security'] = { value: 'max-age=63072000; includeSubdomains; preload' };
  headers['content-security-policy']   = { value: "default-src 'self'; script-src 'self'" };
  headers['x-frame-options']           = { value: 'DENY' };
  headers['x-content-type-options']    = { value: 'nosniff' };
  return response;
}
```

**Lambda@Edge** runs at origin request/response. Full Node.js/Python runtime, up to 5 seconds (viewer-triggered) or 30 seconds (origin-triggered), network access allowed. Use for:
- Server-side rendering at the edge for SEO-critical pages
- Image optimization (resize/convert on the fly)
- Advanced geolocation routing or authentication
- A/B testing with complex logic

| Criteria | CloudFront Functions | Lambda@Edge |
|---|---|---|
| **Runtime** | JavaScript only | Node.js, Python |
| **Execution limit** | <1 ms | 5-30 s |
| **Max memory** | 2 MB | 128-10,240 MB |
| **Network access** | No | Yes |
| **Cost** | ~1/6 of Lambda@Edge | Higher |
| **Deploy region** | All edges automatically | us-east-1 (replicated) |
| **Best for** | Header manipulation, redirects | SSR, auth, image processing |

The default choice is CloudFront Functions. They are fast, cheap, and globally replicated automatically. Reach for Lambda@Edge only when you need network calls, longer execution time, or more than 10 KB of code.

### 10.4 Serverless APIs for Frontend

**Lambda + API Gateway (HTTP API)** is the default choice for frontend backends on AWS. Use **HTTP API**, not REST API -- it is 70% cheaper, supports OIDC/JWT auth natively, and has lower latency.

**CORS configuration** is the number one source of frontend-backend integration pain. You need both API Gateway CORS settings *and* your Lambda must return CORS headers (API Gateway CORS only applies to preflight `OPTIONS` requests):

```javascript
// Lambda: API endpoint with proper CORS and error handling
export const handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': process.env.ALLOWED_ORIGIN,  // Never use '*' in production
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  };
  try {
    const body = JSON.parse(event.body || '{}');
    const result = await processRequest(body);
    return { statusCode: 200, headers, body: JSON.stringify(result) };
  } catch (err) {
    console.error('Request failed:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Internal server error' }) };
  }
};
```

**Lambda Function URLs** are a simpler alternative when you do not need API Gateway features (throttling, usage plans, request validation). A Function URL gives your Lambda a dedicated HTTPS endpoint with built-in CORS configuration -- good for internal tools or webhook receivers.

### 10.5 Frontend Observability on AWS

**Access logs:** Enable CloudFront access logs to an S3 bucket, then query with **Athena** using a standard SQL table definition over the log format. This gives you per-request data (status codes, cache hit/miss, latency, user agent) at pennies per query.

**CloudWatch metrics to watch:**
- **Cache hit ratio** (target >95% for SPAs): low ratio means your `Cache-Control` headers are wrong
- **Origin latency**: should be <100 ms for S3 origins; spikes suggest S3 throttling or large objects
- **4xx/5xx error rates**: 403 spikes often mean OAC misconfiguration or missing objects
- **Requests per second**: capacity planning and anomaly detection

**Real User Monitoring (RUM):** CloudWatch RUM captures page load times, Web Vitals (LCP, FID, CLS), and JavaScript errors from real browser sessions. Third-party alternatives (Datadog RUM, Sentry) offer richer dashboards and session replay.

**Alarms to set from day one:** 5xx error rate > 1%, cache hit ratio < 90%, origin latency p99 > 500 ms.

### 10.6 Cost Drivers for Frontend Workloads

| Component | Primary Cost Driver | Typical SPA Cost |
|---|---|---|
| **CloudFront** | Data transfer out ($0.085/GB NA) | Dominates at scale |
| **S3** | GET requests ($0.0004/1000) | Trivial for SPAs |
| **Lambda@Edge** | Invocations x duration | Can surprise at high traffic |
| **ACM certificates** | Free | $0 |
| **Route 53** | $0.50/hosted zone + $0.40/M queries | Negligible |

**Common cost surprises:**
- **Over-invalidation**: Running `/*` invalidation on every deploy instead of invalidating only `index.html`
- **Uncompressed assets**: CloudFront compresses on the fly if you enable it, but serving pre-compressed Brotli assets from S3 is more efficient
- **Missing Cache-Control**: Without proper headers, CloudFront re-fetches from S3 on every request, multiplying origin request costs
- **Lambda@Edge at scale**: A CloudFront Function at $0.10/M requests vs Lambda@Edge at $0.60/M -- choose the lightest tool that works

**Optimization checklist:** Enable compression in CloudFront (Brotli > gzip). Set aggressive `Cache-Control` on hashed assets. Use **CloudFront Price Classes** to limit edge locations (Price Class 100 covers NA + EU only, cheapest). Pre-compress assets with Brotli during your build step.

---

# PART 2: FIREBASE DEEP DIVE

---

## 1. FIREBASE SERVICES MAP

### 1.1 What Firebase Is (and Is Not)

Firebase is Google's Backend-as-a-Service (BaaS) platform. The value proposition is simple: skip the server. Firebase gives you authentication, a real-time database, file storage, serverless functions, and hosting — all managed, all integrated, all working together from a single Firebase project. A two-person team can build a full-stack real-time app in a week.

But Firebase is not a replacement for AWS or GCP for complex backends. It's optimized for a specific class of apps — and when you're in that class, it's brilliant. When you're not, you'll feel the constraints.

**Firebase is NOT:**
- A replacement for AWS or GCP for complex backends
- Suitable for all workloads (compute-heavy, complex querying, multi-tenancy at scale)
- Free at scale (costs grow with reads/writes, can surprise you)

**Where Firebase fits:** Rapid prototyping, real-time apps, mobile-first products, small to medium teams. Firebase excels when your data model fits its document-oriented design and you want to ship fast.

**Firebase is built on Google Cloud Platform.** Cloud Functions are Cloud Run under the hood. Firestore is a GCP product. You can mix Firebase services with full GCP services when needed. This is worth remembering when you need to extend beyond what Firebase's abstraction layer offers — you're not trapped.

Compare this to Chapter 31 (GCP deep dive), where Firestore appears again without the Firebase wrapper. Same underlying service, different interface and mental model.

### 1.2 Firebase Project Structure

```
Firebase Project (= GCP Project)
├── Apps
│   ├── iOS App (bundle ID)
│   ├── Android App (package name)
│   └── Web App (config object)
├── Firestore Database
├── Realtime Database (can have multiple)
├── Authentication
├── Cloud Functions
├── Hosting
├── Storage (= GCS bucket)
└── Extensions (pre-built solutions)
```

**Multi-environment setup:** Create separate Firebase projects for dev/staging/production. Use `.firebaserc` to manage aliases:

```json
{
  "projects": {
    "default": "my-app-dev",
    "staging": "my-app-staging",
    "production": "my-app-prod"
  }
}
```

```bash
# Initialize Firebase in your project
firebase init

# Switch between environments
firebase use staging
firebase use production

# Deploy to a specific environment
firebase deploy --project my-app-prod
```

---

## 2. CORE SERVICES

### 2.1 Firestore

Firestore is a serverless NoSQL document database that does two things most databases don't: real-time synchronization and offline support. When a document changes in Firestore, every client listening to that document gets the update automatically — no polling, no websocket management, no server-side push logic. You write the data once; Firestore handles the delivery.

The offline support is genuinely impressive. Reads return cached data when offline. Writes are queued locally and synced when connectivity returns. For mobile apps, this makes Firestore feel magic.

**Data model:**
```
Collection: users/
  Document: user123
    Fields: { name: "Alice", email: "alice@example.com", createdAt: Timestamp }
    Subcollection: orders/
      Document: order456
        Fields: { total: 99.99, status: "shipped", items: [...] }
```

**Key rules:**
- Documents are limited to 1 MB
- Collections contain only documents (no nested collections without going through a document)
- Document IDs must be unique within a collection
- Maximum document nesting: 100 levels (via subcollections)

**Queries:**

```javascript
import { collection, query, where, orderBy, limit, getDocs, onSnapshot } from 'firebase/firestore';

// Simple query
const q = query(
  collection(db, 'orders'),
  where('status', '==', 'pending'),
  where('total', '>', 100),
  orderBy('total', 'desc'),
  limit(25)
);
const snapshot = await getDocs(q);

// Array-contains (find documents where tags array includes 'urgent')
const q2 = query(
  collection(db, 'orders'),
  where('tags', 'array-contains', 'urgent')
);

// 'in' query (up to 30 values)
const q3 = query(
  collection(db, 'users'),
  where('status', 'in', ['active', 'trial'])
);

// Real-time listener
const unsubscribe = onSnapshot(q, (snapshot) => {
  snapshot.docChanges().forEach((change) => {
    if (change.type === 'added') console.log('New:', change.doc.data());
    if (change.type === 'modified') console.log('Modified:', change.doc.data());
    if (change.type === 'removed') console.log('Removed:', change.doc.data());
  });
});

// Collection group query (query across all subcollections with the same name)
const allOrders = query(
  collectionGroup(db, 'orders'),
  where('status', '==', 'pending')
);
```

**Indexes:**
- **Single-field indexes:** Automatically created for every field. Supports `==`, `<`, `>`, `array-contains`.
- **Composite indexes:** Required for queries combining multiple fields with inequality or ordering. Must be created explicitly (Firestore error messages include the exact index creation link).

```bash
# Deploy indexes defined in firestore.indexes.json
firebase deploy --only firestore:indexes
```

**Offline persistence:** Enabled by default on mobile (iOS/Android). For web:
```javascript
import { enableIndexedDbPersistence } from 'firebase/firestore';
enableIndexedDbPersistence(db);
```

Reads return cached data when offline. Writes are queued and synced when connectivity returns.

**Pricing model:**
- Document reads: $0.06 per 100K
- Document writes: $0.18 per 100K
- Document deletes: $0.02 per 100K
- Storage: $0.18 per GB/month
- Free tier: 50K reads, 20K writes, 20K deletes per day

**Common gotchas:**
- Reads are billed per document returned. A query returning 1000 documents costs 1000 reads, even if you only need one field. Design queries to return minimal documents.
- `in` and `array-contains-any` operators are limited to 30 values (as of 2024, increased from 10).
- Firestore does not support full-text search. Use Algolia, Typesense, or a Cloud Function with Elasticsearch.
- Inequality filters (`<`, `>`, `!=`) can only be applied to a single field per query (relaxed in 2023 -- multiple inequality filters now supported but require composite indexes).

### 2.2 Realtime Database

**What it is:** Firebase's original database. A giant JSON tree with real-time synchronization.

Realtime Database predates Firestore and has a simpler model: it's a JSON tree, everything is a string or a number or an object or an array, and changes propagate to all listeners in real time. Firestore is better for most use cases now, but Realtime Database has some specific advantages worth knowing.

**When to use instead of Firestore:**
- Very low latency requirements (Realtime DB has ~10ms latency vs Firestore's ~30ms)
- Simple key-value presence systems (online/offline status)
- You need client-side fan-out writes (write to multiple locations atomically in one update)
- Cost optimization for high-frequency small reads (Realtime DB charges by bandwidth, not per-read)

**Data modeling -- keep it flat:**
```json
{
  "users": {
    "user123": { "name": "Alice", "email": "alice@example.com" }
  },
  "userOrders": {
    "user123": {
      "order456": true,
      "order789": true
    }
  },
  "orders": {
    "order456": { "total": 99.99, "status": "shipped" },
    "order789": { "total": 49.99, "status": "pending" }
  }
}
```

**Why flat?** When you read a node, you download ALL data under it (including nested children). Deep nesting means downloading unnecessary data. This is the most common Realtime Database mistake.

**Pricing:** Based on data stored ($5/GB/month) and data downloaded ($1/GB). No per-operation charge. This makes it cheaper than Firestore for high-frequency small reads.

### 2.3 Authentication

**What it is:** Complete authentication system supporting multiple providers, with client SDKs and server-side verification.

Firebase Auth handles the hardest parts of auth: the OAuth flows, the token management, the account linking, the password reset emails. You configure providers in the console; it handles the rest.

**Supported providers:**
- Email/Password (with email verification, password reset)
- Google, Apple, Facebook, Twitter, GitHub, Microsoft
- Phone (SMS verification)
- Anonymous (convert to permanent later)
- Custom tokens (integrate with any auth system)
- SAML and OIDC (enterprise SSO)

**Client-side usage:**

```javascript
import {
  getAuth, signInWithEmailAndPassword, signInWithPopup,
  GoogleAuthProvider, onAuthStateChanged, signOut
} from 'firebase/auth';

const auth = getAuth();

// Email/password sign-in
await signInWithEmailAndPassword(auth, 'user@example.com', 'password123');

// Google sign-in
const provider = new GoogleAuthProvider();
provider.addScope('profile');
const result = await signInWithPopup(auth, provider);
const credential = GoogleAuthProvider.credentialFromResult(result);

// Listen for auth state changes (fires on page load if user is logged in)
onAuthStateChanged(auth, (user) => {
  if (user) {
    console.log('Signed in:', user.uid, user.email);
    const token = await user.getIdToken(); // JWT for server verification
  } else {
    console.log('Signed out');
  }
});

// Anonymous auth (useful for shopping carts before sign-up)
import { signInAnonymously, linkWithCredential, EmailAuthProvider } from 'firebase/auth';
await signInAnonymously(auth);
// Later, upgrade to permanent account:
const credential = EmailAuthProvider.credential('user@example.com', 'password');
await linkWithCredential(auth.currentUser, credential);
```

**Server-side verification (Admin SDK):**

```javascript
const admin = require('firebase-admin');
admin.initializeApp();

// Verify ID token from client
async function verifyRequest(req, res, next) {
  const token = req.headers.authorization?.split('Bearer ')[1];
  if (!token) return res.status(401).json({ error: 'No token provided' });

  try {
    const decoded = await admin.auth().verifyIdToken(token);
    req.user = decoded; // { uid, email, ... }
    next();
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
}

// Create custom token (for integrating with external auth)
const customToken = await admin.auth().createCustomToken(uid, { role: 'admin' });

// Set custom claims (for role-based access)
await admin.auth().setCustomUserClaims(uid, { admin: true, orgId: 'acme' });
```

**Pricing:** Free for most auth methods. Phone auth: $0.01-0.06/verification (volume-based). SAML/OIDC: requires Identity Platform upgrade (50 free MAU, then $0.0055/MAU).

### 2.4 Cloud Functions

**What it is:** Serverless functions triggered by Firebase/GCP events or HTTP requests. V2 functions run on Cloud Run (better scaling, longer timeouts, concurrency).

Cloud Functions are how you add server-side logic to Firebase without managing a server. Firestore trigger fires when a document is created, you send an email. Storage trigger fires when a file is uploaded, you resize it. Auth trigger fires when a user signs up, you validate their email domain. All the things you'd otherwise need a server for, handled in individual functions.

**Trigger types:**

```javascript
const { onRequest } = require('firebase-functions/v2/https');
const { onDocumentCreated, onDocumentUpdated } = require('firebase-functions/v2/firestore');
const { onObjectFinalized } = require('firebase-functions/v2/storage');
const { beforeUserCreated } = require('firebase-functions/v2/identity');
const { onSchedule } = require('firebase-functions/v2/scheduler');
const { onMessagePublished } = require('firebase-functions/v2/pubsub');

// HTTP trigger
exports.api = onRequest({ cors: true, memory: '256MiB', region: 'us-central1' }, async (req, res) => {
  res.json({ message: 'Hello from Firebase!' });
});

// Firestore trigger -- runs when a new order is created
exports.onNewOrder = onDocumentCreated('orders/{orderId}', async (event) => {
  const order = event.data.data();
  const orderId = event.params.orderId;
  // Send confirmation email, update analytics, etc.
  await sendOrderConfirmation(order.email, orderId);
});

// Firestore trigger -- runs when order status changes
exports.onOrderUpdate = onDocumentUpdated('orders/{orderId}', async (event) => {
  const before = event.data.before.data();
  const after = event.data.after.data();
  if (before.status !== after.status && after.status === 'shipped') {
    await sendShippingNotification(after.email);
  }
});

// Storage trigger -- resize uploaded images
exports.onImageUpload = onObjectFinalized({ bucket: 'my-app.appspot.com' }, async (event) => {
  const filePath = event.data.name;
  if (!filePath.startsWith('uploads/') || filePath.includes('_thumb')) return;
  await generateThumbnail(filePath);
});

// Scheduled function (cron)
exports.dailyCleanup = onSchedule('every day 02:00', async (event) => {
  await deleteExpiredSessions();
});

// Auth trigger -- block sign-ups from non-company emails
exports.beforeCreate = beforeUserCreated((event) => {
  const email = event.data.email;
  if (!email?.endsWith('@mycompany.com')) {
    throw new HttpsError('permission-denied', 'Unauthorized email domain');
  }
});
```

**V1 vs V2 functions:**

| Feature | V1 | V2 (Recommended) |
|---|---|---|
| Runtime | Cloud Functions (1st gen) | Cloud Run |
| Concurrency | 1 request per instance | Up to 1000 concurrent requests per instance |
| Timeout | 9 minutes | 60 minutes (HTTP) |
| Min instances | Yes | Yes (with idle billing) |
| Traffic splitting | No | Yes (canary deployments) |

Use V2 for new functions. The concurrency model alone makes it significantly more efficient — a single instance can handle 1000 concurrent requests instead of needing 1000 instances.

**Cold starts:** Similar to Lambda (200ms-2s for Node.js). Mitigate with `minInstances`:
```javascript
exports.api = onRequest({ minInstances: 1, memory: '512MiB' }, handler);
```

**Environment configuration:**
```bash
# Set environment variables
firebase functions:config:set stripe.key="sk_live_abc123"

# V2 functions use parameterized config
# In code:
const { defineString } = require('firebase-functions/params');
const stripeKey = defineString('STRIPE_KEY');
```

```bash
# Deploy functions
firebase deploy --only functions

# Deploy a specific function
firebase deploy --only functions:onNewOrder

# View logs
firebase functions:log --only onNewOrder
```

### 2.5 Hosting

**What it is:** Fast, secure static web hosting with global CDN. Supports dynamic content via Cloud Functions or Cloud Run.

**Key features:**
- Automatic SSL certificates
- Atomic deploys with instant rollback
- Preview channels for PR previews
- Custom domain support
- Integration with GitHub Actions for CI/CD

```json
// firebase.json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "/api/**",
        "function": "api"
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(jpg|jpeg|gif|png|svg|webp)",
        "headers": [{ "key": "Cache-Control", "value": "max-age=31536000" }]
      }
    ]
  }
}
```

```bash
# Deploy
firebase deploy --only hosting

# Create a preview channel (great for PR previews)
firebase hosting:channel:deploy pr-123 --expires 7d

# Rollback to previous release
firebase hosting:rollback
```

**Pricing:** Free tier: 10 GB storage, 360 MB/day transfer. Paid: $0.026/GB storage, $0.15/GB transfer.

### 2.6 Storage

**What it is:** File storage backed by Google Cloud Storage. Upload and serve user-generated content with security rules.

```javascript
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage';

const storage = getStorage();

// Upload a file
const storageRef = ref(storage, `uploads/${userId}/${file.name}`);
const snapshot = await uploadBytes(storageRef, file, {
  contentType: file.type,
  customMetadata: { uploadedBy: userId }
});

// Get download URL (long-lived, includes access token)
const url = await getDownloadURL(snapshot.ref);
```

**Security rules for storage:**
```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /uploads/{userId}/{fileName} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == userId
                   && request.resource.size < 10 * 1024 * 1024  // 10 MB max
                   && request.resource.contentType.matches('image/.*');
    }
  }
}
```

**Image resizing:** Use the `Resize Images` Firebase Extension to automatically generate thumbnails when images are uploaded.

---

## 3. FIREBASE SECURITY RULES

### 3.1 Firestore Rules Deep Dive

Security rules are the most critical and most commonly misconfigured part of Firebase. The reason is subtle: in a traditional backend, you write authorization logic in your server code, which you control. In Firebase, clients talk directly to the database, and rules are the only thing between your data and the world. Getting them wrong isn't a code smell — it's a data breach.

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Helper function: check if user is authenticated
    function isAuthenticated() {
      return request.auth != null;
    }

    // Helper function: check if user owns the document
    function isOwner(userId) {
      return request.auth.uid == userId;
    }

    // Helper function: check custom claim
    function hasRole(role) {
      return request.auth.token[role] == true;
    }

    // Helper function: validate required fields exist
    function hasRequiredFields(fields) {
      return request.resource.data.keys().hasAll(fields);
    }

    // Users collection: owner-only access
    match /users/{userId} {
      allow read: if isAuthenticated() && isOwner(userId);
      allow create: if isAuthenticated() && isOwner(userId)
                    && hasRequiredFields(['name', 'email'])
                    && request.resource.data.name is string
                    && request.resource.data.name.size() <= 100;
      allow update: if isAuthenticated() && isOwner(userId)
                    && !request.resource.data.diff(resource.data).affectedKeys()
                       .hasAny(['createdAt', 'uid']);  // Cannot modify immutable fields
      allow delete: if false;  // Users cannot delete their own account via client
    }

    // Organizations: role-based access
    match /organizations/{orgId} {
      allow read: if isAuthenticated()
                  && exists(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid));

      allow update: if isAuthenticated()
                    && get(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid)).data.role == 'admin';

      // Members subcollection
      match /members/{memberId} {
        allow read: if isAuthenticated()
                    && exists(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid));
        allow write: if isAuthenticated()
                     && get(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid)).data.role == 'admin';
      }
    }

    // Public posts: anyone can read, only author can write
    match /posts/{postId} {
      allow read: if true;
      allow create: if isAuthenticated()
                    && request.resource.data.authorId == request.auth.uid
                    && request.resource.data.createdAt == request.time;
      allow update: if isAuthenticated()
                    && resource.data.authorId == request.auth.uid
                    && request.resource.data.authorId == resource.data.authorId;  // Cannot change author
      allow delete: if isAuthenticated()
                    && resource.data.authorId == request.auth.uid;
    }
  }
}
```

### 3.2 Common Security Mistakes

1. **Open rules in production:** `allow read, write: if true;` -- this is the default for development mode. Never deploy this.

2. **Only checking auth, not ownership:**
   ```
   // BAD: Any authenticated user can read any user's data
   allow read: if request.auth != null;

   // GOOD: Only the document owner can read their data
   allow read: if request.auth.uid == userId;
   ```

3. **Not validating write data:** Clients can send arbitrary fields. Always validate shape, types, and values.

4. **Forgetting `get()` costs reads:** Each `get()` or `exists()` call in rules costs one document read. Use sparingly.

5. **Not testing rules:** Rules bugs are security vulnerabilities. Every rule should have a test.

### 3.3 Testing Rules with Firebase Emulator

```bash
# Start the emulator suite
firebase emulators:start

# Run rules unit tests
firebase emulators:exec "npm test"
```

```javascript
// rules.test.js
const { initializeTestEnvironment, assertSucceeds, assertFails } = require('@firebase/rules-unit-testing');

let testEnv;
beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'test-project',
    firestore: { rules: fs.readFileSync('firestore.rules', 'utf8') }
  });
});

afterAll(() => testEnv.cleanup());

test('users can only read their own profile', async () => {
  const alice = testEnv.authenticatedContext('alice');
  const bob = testEnv.authenticatedContext('bob');

  // Alice can read her own profile
  await assertSucceeds(alice.firestore().doc('users/alice').get());

  // Bob cannot read Alice's profile
  await assertFails(bob.firestore().doc('users/alice').get());
});

test('unauthenticated users cannot read profiles', async () => {
  const unauth = testEnv.unauthenticatedContext();
  await assertFails(unauth.firestore().doc('users/alice').get());
});
```

---

## 4. FIREBASE + MODERN FRAMEWORKS

### 4.1 Firebase with Next.js

The key challenge: Firebase Client SDK runs on the browser. Firebase Admin SDK runs on the server. Never use the Admin SDK on the client (it bypasses security rules and exposes service account credentials).

This architecture boundary matters more than it might seem. The client SDK respects your security rules — it's constrained by them by design. The Admin SDK bypasses all of them — it has root access. Mixing them up is the kind of mistake that results in all your users' data being readable by anyone who reads your JavaScript bundle.

**Architecture:**
```
Browser (Client SDK)          Server (Admin SDK)
├── Auth state listener       ├── Verify ID tokens
├── Firestore queries         ├── Server-side Firestore queries (bypasses rules)
├── Real-time listeners       ├── API routes / Server Actions
└── Storage uploads           └── Server Components (data fetching)
```

**Server-side setup (Admin SDK):**
```javascript
// lib/firebase-admin.ts
import { getApps, initializeApp, cert } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

if (!getApps().length) {
  initializeApp({
    credential: cert({
      projectId: process.env.FIREBASE_PROJECT_ID,
      clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
      privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
    }),
  });
}

export const adminAuth = getAuth();
export const adminDb = getFirestore();
```

**Client-side setup:**
```javascript
// lib/firebase.ts
import { initializeApp, getApps } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const app = !getApps().length ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
export const db = getFirestore(app);
```

**Server Component using Admin SDK:**
```javascript
// app/dashboard/page.tsx (Server Component)
import { adminDb } from '@/lib/firebase-admin';
import { cookies } from 'next/headers';

export default async function DashboardPage() {
  const sessionCookie = cookies().get('session')?.value;
  if (!sessionCookie) redirect('/login');

  const decoded = await adminAuth.verifySessionCookie(sessionCookie);
  const ordersSnap = await adminDb
    .collection('orders')
    .where('userId', '==', decoded.uid)
    .orderBy('createdAt', 'desc')
    .limit(20)
    .get();

  const orders = ordersSnap.docs.map(doc => ({ id: doc.id, ...doc.data() }));

  return <OrderList orders={orders} />;
}
```

### 4.2 Firebase with React Native / Expo

Use `@react-native-firebase/app` for native modules (better performance, offline support) or the JS SDK for Expo Go compatibility.

```javascript
// With @react-native-firebase (recommended for production)
import auth from '@react-native-firebase/auth';
import firestore from '@react-native-firebase/firestore';

// Sign in
await auth().signInWithEmailAndPassword(email, password);

// Firestore query with real-time listener
useEffect(() => {
  const unsubscribe = firestore()
    .collection('messages')
    .where('chatId', '==', chatId)
    .orderBy('createdAt', 'desc')
    .limit(50)
    .onSnapshot(snapshot => {
      const messages = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setMessages(messages);
    });
  return unsubscribe;
}, [chatId]);
```

### 4.3 Firebase Admin SDK

Available for **Node.js**, **Python**, **Go**, and **Java**.

```python
# Python Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore, auth

cred = credentials.Certificate('service-account.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

# Verify ID token
decoded = auth.verify_id_token(id_token)
uid = decoded['uid']

# Firestore operations (bypasses security rules)
doc_ref = db.collection('users').document(uid)
doc_ref.set({'name': 'Alice', 'updatedAt': firestore.SERVER_TIMESTAMP})

# Batch writes
batch = db.batch()
for item in items:
    ref = db.collection('items').document(item['id'])
    batch.set(ref, item)
batch.commit()  # Atomic: all or nothing (max 500 operations)
```

---

## 5. SCALING FIREBASE

### 5.1 Firestore Limitations

Every database has limits. Firestore's limits are worth knowing upfront, not after you've hit them in production at 2 AM:

| Limit | Value | Impact |
|---|---|---|
| Max document size | 1 MB | Store large blobs in Storage, not Firestore |
| Max fields per document | 40,000 | Rarely hit unless storing arrays of objects |
| Max writes per document per second | 1 | **This is the critical bottleneck** |
| Max writes per database per second | 10,000 (default) | Can be increased by contacting Google |
| Max `in` clause values | 30 | Split queries if you need more |
| Max composite indexes per database | 200 | Plan indexes carefully |

The 1-write-per-second-per-document limit is the one that surprises teams. A global counter in a single document, a leaderboard updated on every game action, a popular post with a like counter — all of these will hit this limit the moment you get real traffic.

### 5.2 Distributed Counters

The 1-write-per-document-per-second limit means you cannot have a popular counter in a single document. Solution: shard the counter across N documents.

```javascript
// Initialize counter with 10 shards
async function initCounter(docRef, numShards) {
  const batch = writeBatch(db);
  for (let i = 0; i < numShards; i++) {
    batch.set(doc(docRef, 'shards', `${i}`), { count: 0 });
  }
  await batch.commit();
}

// Increment: pick a random shard
async function incrementCounter(docRef, numShards) {
  const shardId = Math.floor(Math.random() * numShards);
  const shardRef = doc(docRef, 'shards', `${shardId}`);
  await updateDoc(shardRef, { count: increment(1) });
}

// Read: sum all shards
async function getCount(docRef) {
  const shards = await getDocs(collection(docRef, 'shards'));
  let total = 0;
  shards.forEach(snap => { total += snap.data().count; });
  return total;
}
```

With 10 shards, you can handle 10 writes/second. With 100 shards, 100 writes/second. Trade-off: reads become more expensive (N reads to get the count).

### 5.3 Data Modeling Patterns

**Denormalization:** Duplicate data to avoid joins (Firestore has no joins). When you display an order with the customer name, store the name in the order document instead of looking up the user document.

```javascript
// Instead of:  { userId: "u123" }  + separate lookup
// Store:       { userId: "u123", userName: "Alice", userAvatar: "https://..." }
```

Trade-off: Updates require fan-out writes. Use Cloud Functions to propagate changes:
```javascript
exports.onUserUpdate = onDocumentUpdated('users/{userId}', async (event) => {
  const { name, avatar } = event.data.after.data();
  const orders = await adminDb.collection('orders')
    .where('userId', '==', event.params.userId).get();

  const batch = adminDb.batch();
  orders.forEach(doc => {
    batch.update(doc.ref, { userName: name, userAvatar: avatar });
  });
  await batch.commit();
});
```

**Subcollections vs root collections:**
- **Subcollections** (e.g., `users/{userId}/orders`): Natural hierarchy, queries scoped to parent, good for per-user data. Cannot easily query across all users' orders without collection group queries.
- **Root collections** (e.g., `orders` with `userId` field): Flat structure, easy cross-user queries, simpler security rules. Better for data accessed across multiple parents.

**Rule of thumb:** If you primarily query within a single parent (e.g., "get this user's orders"), use subcollections. If you need cross-parent queries (e.g., "get all pending orders"), use root collections.

### 5.4 When to Move Beyond Firebase

**Signs you have outgrown Firebase:**
- Monthly bill exceeds what equivalent infrastructure would cost on AWS/GCP
- You need complex queries (aggregations, joins, full-text search) that Firestore does not support natively
- The 1 write/sec/document limit is causing contention despite sharding
- You need multi-tenancy with strong data isolation
- You need relational data modeling with complex transactions
- Compliance requirements mandate infrastructure you control

This is a normal part of a product's evolution. Firebase is optimized for getting to product-market fit. AWS is optimized for operating at scale. The best teams use Firebase to learn what they're building, then migrate the parts that need more power when they need them — not before.

**Migration paths:**
- **Firebase Auth -> AWS Cognito or Auth0:** Export users with `admin.auth().listUsers()`, import to new system, update tokens on client
- **Firestore -> PostgreSQL:** Export via `gcloud firestore export`, transform documents to relational schema
- **Firestore -> DynamoDB:** Document model maps more naturally. Export and transform PK/SK design
- **Cloud Functions -> AWS Lambda:** Rewrite triggers. Firebase-specific triggers (Firestore, Auth) need equivalent event sources
- **Firebase Hosting -> Vercel/AWS CloudFront + S3:** Straightforward static asset migration

**Gradual migration pattern:** Keep Firebase Auth (it is the hardest to migrate), move the database and backend to AWS/GCP. Firebase Auth works with any backend -- just verify ID tokens server-side. This way you migrate the database and compute at your own pace without forcing all your users to re-authenticate.

---

## 6. FIREBASE VS AWS COMPARISON

### 6.1 Feature-by-Feature Comparison

| Feature | Firebase | AWS Equivalent | Notes |
|---|---|---|---|
| Authentication | Firebase Auth | Cognito | Firebase Auth has simpler setup and more providers OOTB |
| Document Database | Firestore | DynamoDB | Firestore has real-time sync built in; DynamoDB is more scalable |
| Relational Database | None | RDS/Aurora | Firebase has no relational option |
| Real-time Database | Realtime Database | AppSync + DynamoDB | Firebase is simpler; AppSync is more flexible |
| Serverless Functions | Cloud Functions | Lambda | Lambda has more runtimes, better scaling, richer event sources |
| Object Storage | Cloud Storage | S3 | S3 is cheaper and more feature-rich at scale |
| CDN/Hosting | Firebase Hosting | CloudFront + S3 | Firebase is simpler; CloudFront is more configurable |
| Push Notifications | Cloud Messaging (FCM) | SNS / Pinpoint | FCM is the industry standard for mobile push |
| Analytics | Google Analytics | Pinpoint / custom | Firebase Analytics is free and powerful for mobile |
| Crash Reporting | Crashlytics | None (use Sentry) | Crashlytics is best-in-class for mobile |
| ML | ML Kit | SageMaker / Rekognition | Different scope: on-device (ML Kit) vs cloud (SageMaker) |
| Full-text Search | None | OpenSearch | Firebase requires third-party (Algolia, Typesense) |
| Message Queues | Pub/Sub (GCP) | SQS/SNS/EventBridge | No native Firebase queue; must use GCP Pub/Sub |

### 6.2 When to Use Firebase

- **Rapid prototyping:** Get a full backend running in hours, not days
- **Real-time applications:** Chat, collaboration, live dashboards (Firestore real-time listeners are unmatched)
- **Mobile-first products:** Best-in-class mobile SDKs, offline persistence, push notifications, analytics, crash reporting
- **Small teams (1-5 engineers):** Minimal backend code, managed infrastructure, generous free tier
- **MVPs and startups:** Ship fast, validate the idea, migrate later if needed

### 6.3 When to Use AWS

- **Enterprise applications:** Complex compliance (HIPAA, SOC2, PCI), VPC isolation, fine-grained IAM
- **Complex backends:** Relational data, complex queries, multi-service architectures, custom middleware
- **Cost optimization at scale:** Firebase costs grow linearly with usage. AWS offers reserved pricing, spot instances, and more pricing levers
- **High-throughput workloads:** DynamoDB scales far beyond Firestore limits. Lambda handles millions of concurrent invocations
- **ML/AI workloads:** SageMaker, Bedrock, GPU instances -- AWS has the deepest ML infrastructure

See Chapter 31 for the GCP angle: when your team is already Google-native, Firebase + GCP is a coherent stack where Firebase provides the developer experience and GCP provides the escape hatch when you need raw infrastructure.

### 6.4 Hybrid Patterns

The most elegant architectures often use both. Firebase for the parts it does brilliantly (real-time, mobile, auth), AWS for the parts it does brilliantly (scale, compliance, compute).

**Firebase Auth + AWS Backend:**
The most common hybrid pattern. Firebase Auth handles sign-up/sign-in. Your AWS backend verifies Firebase ID tokens:

```javascript
// AWS Lambda verifier
const admin = require('firebase-admin');
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

exports.handler = async (event) => {
  const token = event.headers.authorization?.split('Bearer ')[1];
  try {
    const decoded = await admin.auth().verifyIdToken(token);
    // decoded.uid, decoded.email available
    // Query DynamoDB, RDS, etc.
    return { statusCode: 200, body: JSON.stringify(data) };
  } catch (error) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Unauthorized' }) };
  }
};
```

This pattern is useful because Firebase Auth is genuinely hard to replace. It handles OAuth provider integrations, token refresh, session management, and device-specific quirks (especially on iOS and Android). Once your users are in Firebase Auth, migrating them to a different auth system requires either a forced re-login or a careful token migration. Keeping Firebase Auth while moving your data layer to AWS/DynamoDB/RDS is often the smoothest path forward.

**Firebase Hosting + AWS Lambda:**
Use Firebase Hosting as your CDN/static host. API calls go to API Gateway + Lambda:
```json
// firebase.json
{
  "hosting": {
    "public": "dist",
    "rewrites": [
      { "source": "/api/**", "run": { "serviceId": "api" } },
      { "source": "**", "destination": "/index.html" }
    ]
  }
}
```
Or simply call your AWS API Gateway URL directly from the client (configure CORS).

**Firestore for real-time + DynamoDB for analytics:**
Use Firestore for user-facing real-time features (chat, presence, live updates). Stream changes to DynamoDB via Cloud Functions for analytics queries and reporting that need DynamoDB's query flexibility.

---

## QUICK REFERENCE: AWS CLI CHEAT SHEET

```bash
# Identity
aws sts get-caller-identity                    # Who am I?
aws configure list-profiles                    # List configured profiles

# EC2
aws ec2 describe-instances --filters "Name=tag:Environment,Values=production" \
  --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType,PrivateIpAddress]' \
  --output table

# S3
aws s3 ls s3://my-bucket/prefix/ --recursive --human-readable --summarize
aws s3 sync ./dist s3://my-bucket --delete     # Deploy static site
aws s3 cp s3://bucket/key - | jq .             # Stream and parse JSON

# Lambda
aws lambda list-functions --query 'Functions[].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize}'
aws lambda update-function-code --function-name my-fn --zip-file fileb://function.zip

# DynamoDB
aws dynamodb scan --table-name MyTable --max-items 5  # Quick peek (never in prod)
aws dynamodb query --table-name MyTable \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#123"},":sk":{"S":"ORDER#"}}'

# CloudWatch Logs
aws logs tail /aws/lambda/my-function --follow  # Tail logs in real-time
aws logs filter-log-events --log-group-name /aws/lambda/my-function \
  --filter-pattern "ERROR" --start-time $(date -d '1 hour ago' +%s)000

# ECS
aws ecs list-services --cluster prod
aws ecs update-service --cluster prod --service api --force-new-deployment  # Rolling restart

# Secrets
aws secretsmanager get-secret-value --secret-id prod/db/password --query SecretString --output text

# Cost
aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-02-01 \
  --granularity DAILY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
```

## QUICK REFERENCE: FIREBASE CLI CHEAT SHEET

```bash
# Project management
firebase projects:list
firebase use --add                              # Add a project alias
firebase use production                         # Switch to production

# Emulators (local development)
firebase emulators:start                        # Start all emulators
firebase emulators:start --only firestore,auth  # Start specific emulators
firebase emulators:export ./seed-data           # Export emulator data
firebase emulators:start --import ./seed-data   # Import seed data on start

# Deployment
firebase deploy                                 # Deploy everything
firebase deploy --only hosting                  # Deploy only hosting
firebase deploy --only functions:myFunction     # Deploy single function
firebase deploy --only firestore:rules          # Deploy Firestore rules
firebase deploy --only firestore:indexes        # Deploy Firestore indexes

# Functions
firebase functions:log                          # View function logs
firebase functions:delete myFunction            # Delete a function
firebase functions:shell                        # Interactive function testing

# Hosting
firebase hosting:channel:deploy preview-123     # Deploy to preview channel
firebase hosting:channel:list                   # List preview channels
firebase hosting:rollback                       # Rollback last deploy

# Firestore
firebase firestore:delete --all-collections     # Delete all data (careful!)
firebase firestore:indexes                      # List indexes
```

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M14: Your First Deployment](../course/modules/loop-1/L1-M14-first-deployment.md)** — Deploy TicketPulse to AWS for the first time, covering ECS, RDS, and the IAM roles that tie them together
- **[L2-M44: Terraform & Infrastructure as Code](../course/modules/loop-2/L2-M44-terraform-and-iac.md)** — Replace click-ops with Terraform modules for TicketPulse's AWS and Firebase infrastructure
- **[L3-M62: Cloud Provider Deep Dive](../course/modules/loop-3/L3-M62-cloud-provider-deep-dive.md)** — Go beyond the basics: ALB routing rules, CloudFront distributions, Firestore security rules at production scale
- **[L3-M75: Cost Optimization](../course/modules/loop-3/L3-M75-cost-optimization.md)** — Right-size TicketPulse's infrastructure and implement the cost controls that keep a growing system within budget

### Quick Exercises

1. **Run AWS Cost Explorer and find your top 3 spend categories** — filter by the last 30 days, group by service, and identify the largest line items. For each, ask whether the spend is proportional to the value delivered.
2. **Check your IAM policies for overly broad permissions** — find any policy with `"Action": "*"` or `"Resource": "*"` and scope it down to the specific actions and resources that service actually needs.
3. **Set up a billing alarm at 80% of your budget** — create a CloudWatch billing alarm that alerts before you hit your monthly limit, not after.

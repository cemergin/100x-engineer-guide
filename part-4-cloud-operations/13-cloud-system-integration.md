<!--
  CHAPTER: 13
  TITLE: Cloud Computing & System Integration
  PART: IV — Cloud & Operations
  PREREQS: Chapters 1-4, 7
  KEY_TOPICS: VPC networking, message queues, Kafka, SQS, event-driven architecture, data flow, CQRS, CDC, database migrations, system architecture walkthrough, Prometheus, Grafana, OpenTelemetry, cost management
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 13: Cloud Computing & System Integration

> **Part IV — Cloud & Operations** | Prerequisites: Chapters 1-4, 7 | Difficulty: Advanced

Every large-scale system is really a city. You have highways (networks), postal systems (message queues), utilities (databases), emergency services (monitoring), and a budget office trying to stop everyone from paving the city in gold. This chapter is your urban planning guide — it shows you how the twenty-plus components of a modern cloud architecture actually connect, communicate, and stay alive under load.

We're not going to skim the surface. We're going to walk through every layer — from the IP packets traveling your VPC subnets, to the Kafka topic absorbing a billion Shopify events, to the PromQL query that catches a silent service failure at 2 AM. By the end, you'll understand why Netflix runs active-active across three regions, why Stripe uses Temporal for payment orchestration, and why that one harmless-looking schema migration is about to lock your database for twenty minutes at peak traffic.

### In This Chapter
- Cloud Networking Deep Dive
- Message Queues & Event-Based Architecture
- Data Flow & Pipeline Architecture
- Database Migrations
- How a Large-Scale App Comes Together
- Monitoring & Observability in Practice
- Cost Management
- Synthesis: How It All Connects

### Related Chapters
- Chapter 19 — AWS/Firebase specifics
- Chapter 4 — reliability/observability theory
- Chapter 18 — monitoring tools in depth
- Chapter 2 — data patterns

---

## 1. CLOUD NETWORKING DEEP DIVE

### 1.1 VPC Architecture

Here's the thing about cloud networking that nobody explains well: it's just software-defined data center infrastructure. A Virtual Private Cloud is your isolated network within a cloud provider — your own address space, your own routing rules, your own walls keeping the internet out. Think of it as building a private office park inside a massive public city. You control every road inside your park.

The core components are simple once you see how they relate:

| Component | Purpose |
|---|---|
| **VPC** | Isolated virtual network with its own CIDR block (e.g., `10.0.0.0/16` = 65,536 IPs) |
| **Subnet** | Partition of a VPC within one Availability Zone. Public or private by routing, not by declaration. |
| **Internet Gateway (IGW)** | Attaches to VPC. Enables inbound/outbound internet traffic for public subnets. |
| **NAT Gateway** | Sits in public subnet. Allows private subnet instances to reach the internet (outbound only). |
| **Route Table** | Rules determining where network traffic is directed. Each subnet associates with exactly one. |

**Public vs private subnets — the real distinction:**

This trips up almost everyone. A subnet is "public" if its route table has a route to an Internet Gateway (`0.0.0.0/0 → igw-xxx`). A subnet is "private" if it does not. That's literally it. It is purely a routing decision — not a label, not a flag, not a setting. You could name your subnet "definitely-private" and if it has a route to an IGW, it's public. The internet doesn't care about your naming conventions.

**Standard three-tier VPC layout:**

This pattern shows up everywhere from startups to Fortune 500s because it separates concerns cleanly: internet-facing stuff lives in public subnets, application logic lives in private subnets, data stores live in isolated data subnets that can't reach the internet at all.

```
┌─────────────────────────────────────────────────────────────┐
│  VPC: 10.0.0.0/16                                           │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │ Public Subnet (AZ-a)│    │ Public Subnet (AZ-b)│        │
│  │ 10.0.1.0/24         │    │ 10.0.2.0/24         │        │
│  │ ALB, NAT Gateway    │    │ ALB, NAT Gateway    │        │
│  │ Route: 0.0.0.0/0→IGW│    │ Route: 0.0.0.0/0→IGW│        │
│  └─────────────────────┘    └─────────────────────┘        │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │ Private Subnet (AZ-a)│   │ Private Subnet (AZ-b)│       │
│  │ 10.0.3.0/24          │   │ 10.0.4.0/24          │       │
│  │ App servers (ECS/K8s) │   │ App servers (ECS/K8s) │      │
│  │ Route: 0.0.0.0/0→NAT │   │ Route: 0.0.0.0/0→NAT │      │
│  └───────────────────────┘   └───────────────────────┘      │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │ Data Subnet (AZ-a)  │    │ Data Subnet (AZ-b)  │        │
│  │ 10.0.5.0/24         │    │ 10.0.6.0/24         │        │
│  │ RDS, ElastiCache     │    │ RDS, ElastiCache     │       │
│  │ No internet route    │    │ No internet route    │        │
│  └─────────────────────┘    └─────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**The NAT Gateway cost trap:** Here's a bill line item that quietly destroys engineering budgets. NAT Gateways cost ~$0.045/hr (~$32/mo) *plus* $0.045/GB of processed data. For a high-throughput private subnet that's pulling container images on every deploy or hammering external APIs, this adds up shockingly fast. The fix: use VPC endpoints for AWS services (S3, ECR, DynamoDB are free or near-free), and set up pull-through caches for container images. We'll cover this more in the cost section, but plant the flag now: every byte through a NAT Gateway costs money.

### 1.2 Security Groups vs NACLs

Most engineers learn security groups and ignore NACLs entirely. That's mostly fine — but understanding the difference matters when something goes wrong and you're hunting for why traffic is being blocked.

| Feature | Security Group | NACL |
|---|---|---|
| **Level** | Instance (ENI) | Subnet |
| **Statefulness** | **Stateful** — return traffic automatically allowed | **Stateless** — must explicitly allow return traffic |
| **Rules** | Allow only (implicit deny) | Allow and Deny |
| **Evaluation** | All rules evaluated together | Rules evaluated in order (lowest number first) |
| **Default** | Deny all inbound, allow all outbound | Allow all inbound and outbound |

The stateful vs stateless distinction is the big one. When your EC2 instance in a security group responds to an inbound HTTP request, the response traffic is automatically allowed — the security group tracks the connection state. NACLs have no memory. If you open inbound port 443, you also need to open the ephemeral port range (1024-65535) outbound for response traffic. Miss that and you'll spend an hour wondering why your HTTPS requests time out.

**Layered security model:**
- NACLs = coarse perimeter control (block known bad IP ranges, restrict ports at subnet boundary)
- Security Groups = fine-grained application control (web servers accept 443 only from ALB security group)

**Security group chaining** is one of those elegant patterns that both increases security and self-documents your architecture. Instead of specifying IP ranges in security group rules, you reference other security groups: ALB-SG allows 443 from `0.0.0.0/0`. App-SG allows 8080 from ALB-SG. DB-SG allows 5432 from App-SG. This creates an explicit dependency chain — you can look at the DB security group and immediately see that only the app tier can talk to it, with no IP ranges to maintain or rotate.

### 1.3 VPC Peering, Transit Gateway, PrivateLink

As systems grow, you'll inevitably need to connect VPCs together. Maybe you have separate VPCs per environment, per team, or per business unit. There are three main ways to do this, and each solves a different problem.

**VPC Peering** is the simplest: a direct network connection between two VPCs. Traffic stays on the cloud backbone — it never touches the public internet. But here's the catch that bites everyone eventually: VPC peering is *non-transitive*. If VPC-A peers with VPC-B, and VPC-B peers with VPC-C, A still cannot reach C. You need a direct peering between A and C. This becomes an N*(N-1)/2 problem — 10 VPCs need 45 peering connections, each managed separately. It doesn't scale.

Additional constraints: CIDRs must not overlap, and the connection works cross-account and cross-region without any bandwidth bottleneck (it uses the cloud backbone).

**Transit Gateway** solves the scaling problem with a hub-and-spoke model. Every VPC connects to the Transit Gateway once, and the TGW handles routing between all spokes. It's transitive — any spoke can reach any other spoke through the hub. It supports route tables for segmentation (maybe your prod VPCs can't talk to dev VPCs), and it connects on-premises networks too.

Real-world: large organizations running 50+ VPCs, a shared services VPC, and Direct Connect to their data center. This is where Transit Gateway earns its keep.

**PrivateLink** solves a completely different problem: exposing *one specific service* from one VPC to consumers in other VPCs, without full network access between them. Traffic never leaves the cloud network — consumers see it as a private IP in their own VPC. There are two types: Interface endpoints (ENI with private IP, for most AWS services) and Gateway endpoints (for S3 and DynamoDB — and they're free).

SaaS vendors love PrivateLink because customers can access their APIs without any internet traversal, satisfying security and compliance requirements in one shot.

**Decision tree:**
- 2-3 VPCs needing full connectivity → VPC Peering
- Many VPCs, hub-and-spoke, on-prem connectivity → Transit Gateway
- Expose one specific service to another VPC → PrivateLink

### 1.4 DNS in the Cloud

DNS is the phone book of the internet, and in a cloud architecture it's also your service discovery mechanism, your traffic routing engine, and your failover system.

| Record Type | Purpose | Example |
|---|---|---|
| **A** | Domain → IPv4 | `api.example.com → 203.0.113.10` |
| **AAAA** | Domain → IPv6 | `api.example.com → 2001:db8::1` |
| **CNAME** | Alias to another domain | `www.example.com → example.com` |
| **ALIAS/ANAME** | Like CNAME but at zone apex | `example.com → d111.cloudfront.net` |
| **SRV** | Service locator (port + host) | Used by service discovery |
| **TXT** | Verification, SPF, DKIM | `"v=spf1 include:_spf.google.com"` |

**Internal vs external hosted zones** are where it gets interesting for microservices. A public zone resolves from the internet: `api.example.com → public ALB IP`. A private zone resolves *only within associated VPCs*: `db.internal.example.com → 10.0.5.20`. It's never exposed externally.

Private zones enable service discovery without DNS exposure. Your Order Service calls `orders.internal.example.com` and it resolves to the internal load balancer — no hardcoded IPs, no service registry to maintain, no cross-environment confusion. This is elegant and underused.

**Routing policies** turn Route 53 from a simple address book into an intelligent traffic router:
- **Simple:** One record, one answer.
- **Weighted:** Split traffic by percentage. This is how you do canary deploys at the DNS level — 90% to stable, 10% to new.
- **Latency-based:** Route to the region with lowest latency for the requester. Users in Tokyo hit your Asia-Pacific deployment.
- **Failover:** Active/passive. Health check fails → route to standby. Your disaster recovery automatically engages.
- **Geolocation:** Route by requester's geography. Required for GDPR data residency — European users stay in European regions.

### 1.5 Load Balancer Types

"Load balancer" is not a single thing. The three types operate at different network layers, handle different protocols, and optimize for different goals.

| Type | Layer | Protocol | Use Case |
|---|---|---|---|
| **ALB** (Application LB) | L7 | HTTP/HTTPS, gRPC, WebSocket | Path-based routing, host-based routing, microservices |
| **NLB** (Network LB) | L4 | TCP, UDP, TLS | Ultra-low latency, static IPs, millions of requests/sec |
| **GLB** (Gateway LB) | L3 | IP | Inline traffic inspection (firewalls, IDS/IPS) |

**ALB deep dive:**

The ALB is your default choice for web applications, and once you see what it can do you'll appreciate why. Content-based routing means `/api/*` goes to your API target group while `/static/*` goes to a static server target group — one load balancer, many backends. Host-based routing means `api.example.com` and `admin.example.com` can both point to the same ALB and land on different services. It integrates natively with Cognito and OIDC for auth (you can offload token validation from your app tier entirely), supports gRPC with HTTP/2, and has a slow start mode that gradually increases traffic to new targets — so a cold-starting JVM doesn't immediately get hammered.

**NLB deep dive:**

When you need to handle millions of requests per second with latency measured in *microseconds*, the ALB's L7 processing becomes overhead. The NLB operates at L4 — it doesn't read HTTP, it just routes TCP/UDP packets extremely fast. The latency at the load balancer itself is ~100 microseconds. It preserves the client's source IP address (no X-Forwarded-For header dance). It gives you static IPs per AZ, which you can attach Elastic IPs to — critical when partners need to allowlist your service by IP. And it does TCP passthrough, meaning TLS termination happens at your target, not the load balancer.

**When to choose:**
- Default choice for web apps → **ALB**
- Need static IPs, extreme performance, non-HTTP protocols → **NLB**
- NLB in front of ALB: the pattern for when you need both static IPs *and* L7 routing
- Third-party virtual appliances (firewalls, IDS/IPS) → **GLB**

### 1.6 CDN Integration

A CDN is a distributed cache network. Instead of every user in every geography hitting your origin servers, their request hits a nearby "edge location" that might already have the response cached. If it does, the response comes back in single-digit milliseconds. If not, the edge fetches from your origin, caches it, and serves future requests from cache.

```
User → Edge Location (CDN) ──cache miss──→ Origin (ALB/S3)
                            ──cache hit──→ Response from edge
```

**CloudFront configuration that matters:**

The parts of CloudFront that separate competent configurations from great ones are the details:

- **Origin types:** S3 for static assets, ALB for dynamic API, any HTTP server as a custom origin.
- **Cache behaviors:** Match URL patterns to origins. `/api/*` → ALB with TTL=0 (passthrough, don't cache API responses). `/*` → S3 with TTL=86400 (cache for 24 hours).
- **Origin Access Control (OAC):** Your S3 bucket is only accessible via CloudFront, not directly. Without this, users can bypass your CDN and hammer your origin.
- **Cache key:** By default, just the URL path. Customize with headers, query strings, cookies — be careful here, every unique cache key is a separate cache entry.
- **Invalidation:** `/*` invalidates everything and costs money after the first 1,000/month. The better approach is versioned filenames (`app.3a7b2c.js`) — when the file changes, the filename changes, the old one expires naturally, the new one populates fresh.

**Cloudflare differentiators:**

Cloudflare's architecture is fundamentally different. Their Anycast network runs every service (CDN, WAF, DDoS protection, Workers) at every edge location. Cloudflare Workers run V8 isolates at the edge with sub-millisecond cold starts and a pricing model far cheaper than Lambda@Edge. And their R2 object storage is S3-compatible with *zero egress fees* — which eliminates the "CDN pulling from S3 costs money" trap that quietly inflates AWS bills.

### 1.7 Multi-Region Networking

At some scale, one region isn't enough. It might be latency (users in Asia hitting US-East adds 200-300ms of round-trip time), availability (an entire AWS region going down — it happens), or compliance (GDPR data residency, financial regulations requiring data to stay in specific geographies).

| Pattern | Complexity | RPO/RTO | Cost |
|---|---|---|---|
| **Active-Passive** | Medium | RPO: minutes, RTO: minutes | ~1.5x |
| **Active-Active** | High | RPO: ~0, RTO: ~0 | 2x+ |
| **Read replicas** | Low | N/A (writes to one region) | ~1.3x |

**Active-Active challenges** are where the real engineering lives. You're now running two or more live systems that both accept writes, and you need to keep them consistent. Async replication is fast but creates conflict potential — what if the same record is updated in two regions simultaneously? Sync replication eliminates conflicts but adds latency because every write must be acknowledged from another continent. Conflict resolution strategies range from last-writer-wins (simple, with data loss risk) to CRDTs (complex, eventually consistent, no data loss) to application-level merge logic.

For global SQL, DynamoDB global tables handle replication automatically. CockroachDB and Spanner are built for this problem at the database level.

*Real-world:* Netflix runs active-active across three US regions. If one fails, traffic shifts to the other two within minutes. They had to build Zuul (their edge gateway) and Eureka (service discovery) specifically to support this architecture. It's not cheap or simple — but for a service where every minute of downtime is global and catastrophic, it's the right call.

### 1.8 VPN and Direct Connect

Once you're running a meaningful operation, you'll need to connect your cloud to your data center, office network, or corporate infrastructure. Two options, very different trade-offs.

**Site-to-Site VPN** creates an IPsec tunnel over the public internet. It's encrypted, cost-effective, and can be set up in hours. The downside is that your bandwidth is limited by your internet connection and your latency varies with internet congestion. It's fine for dev/test, low-bandwidth hybrid connectivity, or as a backup link.

**Direct Connect (AWS) / Cloud Interconnect (GCP) / ExpressRoute (Azure)** is a dedicated physical circuit between your facility and the cloud provider. One or ten Gigabits per second. Consistent, predictable latency with no internet dependency. Required for high-throughput data transfer workloads and latency-sensitive applications. The trade-off: setup takes weeks to months because you're provisioning physical infrastructure, and the cost is a port fee plus data transfer fees.

**Hybrid architecture best practice:** Direct Connect as primary, Site-to-Site VPN as automatic failover. If the physical circuit goes down, traffic reroutes through VPN with the latency and bandwidth trade-offs that entails — but your connectivity survives.

### 1.9 IP Addressing Strategy

Your IP address plan is one of those things you do once and live with forever. Plan wrong and you're doing painful subnetting gymnastics as you grow.

**Planning for growth:**
- Use a large VPC CIDR (`/16` = 65,536 IPs). You cannot resize a VPC easily after creation.
- Reserve separate blocks per environment: `10.0.0.0/16` = production, `10.1.0.0/16` = staging, `10.2.0.0/16` = dev.
- Never overlap CIDRs between VPCs you might need to connect later. Future-you will be grateful.
- Document allocations in a central IPAM (IP Address Management). AWS offers VPC IPAM as a managed service.

**Subnet sizing:**
- `/24` (256 IPs, 251 usable after AWS reserves 5) for most subnets.
- `/20` (4,096 IPs) for Kubernetes node subnets — Kubernetes with VPC CNI assigns a VPC IP to every pod, and pods multiply fast.
- AWS reserves 5 IPs per subnet: the first 4 and the last 1.

**IPv6:** Dual-stack is the future. AWS gives you a free `/56` IPv6 block. No NAT needed (every IPv6 address is globally routable), and security is handled entirely by security groups. If you're building something new, consider adding IPv6 from day one.

---

## 2. MESSAGE QUEUES & EVENT-BASED ARCHITECTURE

### 2.1 Message Queue Fundamentals

Imagine you're running a restaurant. When a customer places an order, you don't want the waiter standing in the kitchen watching the chef cook. You want the waiter to drop the ticket and go take more orders. The kitchen processes tickets at its own pace. That's a message queue.

In distributed systems, the same idea prevents services from blocking on each other, absorbs traffic spikes, and enables services to fail and recover independently. The vocabulary:

| Term | Meaning |
|---|---|
| **Producer** | Publishes messages to a queue or topic |
| **Consumer** | Reads and processes messages |
| **Topic** | Named channel for pub/sub (Kafka, SNS) |
| **Queue** | FIFO or near-FIFO buffer for point-to-point messaging |
| **Partition** | Sub-division of a topic for parallelism (Kafka) |
| **Consumer Group** | Set of consumers that cooperatively process partitions. Each partition assigned to one consumer in the group. |
| **Offset** | Position marker in a partition (Kafka). Consumers track their own offset. |
| **Acknowledgment** | Consumer confirms successful processing. Message removed/marked from queue. |
| **Visibility Timeout** | Time a message is hidden from other consumers after being read (SQS). If not acknowledged, it reappears. |

**The fundamental guarantee spectrum:**

This is the core trade-off in any messaging system:

```
At-most-once ←────────────────────────→ At-least-once ←──────→ Exactly-once
(may lose msgs)                         (may duplicate)         (expensive/complex)
Fire-and-forget                         Ack after processing    Idempotent consumers
UDP-like                                Most systems default    + transactional writes
```

True exactly-once delivery is theoretically impossible in a distributed system — networks fail at inopportune moments and you can't know if the consumer received and processed the message before the failure. In practice, most systems are at-least-once with idempotent consumers, which gives you the safety of exactly-once without the cost.

### 2.2 Queue Types Compared

Not all message systems are the same. Choosing the wrong one is a real mistake, and the right answer depends on your throughput, ordering requirements, and operational complexity budget.

| System | Model | Ordering | Throughput | Latency | Best For |
|---|---|---|---|---|---|
| **SQS** | Queue | FIFO mode: per-group. Standard: best-effort | ~3,000 msg/s (FIFO), unlimited (standard) | 1-10ms | Simple task queues, decoupling AWS services |
| **RabbitMQ** | Broker (AMQP) | Per-queue FIFO | ~20-50K msg/s | Sub-ms | Complex routing (topic, fanout, headers exchange), RPC |
| **Kafka** | Distributed log | Per-partition | Millions msg/s | 2-10ms | Event streaming, replay, high throughput |
| **NATS** | Lightweight pub/sub | Per-subject (JetStream) | ~10M msg/s | Sub-ms | Cloud-native microservices, edge, IoT |
| **Redis Streams** | Append-only log | Per-stream | ~100K msg/s | Sub-ms | Lightweight streaming when you already run Redis |

**RabbitMQ exchange types explained:**

RabbitMQ's routing model is its superpower. Four exchange types give you every routing pattern you could want:
- **Direct:** Route by exact routing key match. Message with key `order.created` goes only to queues bound with `order.created`.
- **Topic:** Route by pattern. `order.*` matches `order.created` and `order.shipped`. `#` matches everything.
- **Fanout:** Broadcast to all bound queues. No routing key needed. Classic pub/sub.
- **Headers:** Route by message header attributes instead of routing key. Flexible but slower.

**Kafka architecture in 60 seconds:**

Topics split into partitions. Partitions are the unit of parallelism — more partitions means more parallel consumers. Producers send to a partition by key hash (deterministic — same key always goes to same partition) or round-robin. Each partition is an ordered, immutable, append-only log.

Consumer groups are the magic: each partition is consumed by exactly one consumer in a group. Add consumers up to the partition count for linear scaling — ten partitions, ten consumers, ten-way parallelism. Add an eleventh consumer and it sits idle. Add an eleventh partition and suddenly you have capacity for an eleventh consumer.

Retention is time-based (7 days default) or size-based. Unlike traditional queues, messages aren't deleted after consumption — they expire. This enables replay. That `order.created` event from three days ago? You can re-consume it if you need to rebuild state. Replication: each partition has a leader broker and N-1 followers. ISR (in-sync replicas) ensures durability — a write is only acknowledged after it's on all in-sync replicas.

### What Messaging Systems Cost

You can choose the right queue for the wrong reason (it's what you know, it's what's cool) or the wrong queue for the right reason (it's cheap, it's enough). Know the price before you commit.

> All figures are ballpark estimates as of 2025 — check current pricing before budgeting.

| System | Approximate Monthly Cost | At 10M Messages/Month | What Tips the Decision |
|---|---|---|---|
| **SQS Standard** | $0 (first 1M free), then ~$0.40/million | ~$3.60/mo | Simple task queues, no replay needed |
| **SQS FIFO** | ~$0.50/million messages | ~$4.50/mo | Ordering matters, lower throughput ok |
| **SNS** | ~$0.50/million notifications | ~$4.50/mo | Fan-out to multiple subscribers |
| **EventBridge** | ~$1.00/million events | ~$9/mo | Rule-based routing, AWS service events |
| **MSK (managed Kafka)** | $800–2,500/mo minimum (3-broker cluster) | Same — cluster cost dominates | Replay needed, >50M msg/mo, multi-consumer |
| **Self-managed Kafka** | ~$300–600/mo (3 EC2 instances) | Same — always paying for cluster | Cost savings vs MSK, if you have ops bandwidth |
| **Redis Streams** | Included in ElastiCache cost | — | Lightweight streaming, already run Redis |

**If your message volume is under 10M/month, SQS costs less than your morning coffee. Don't default to Kafka.**

The urge to reach for Kafka is real — it's powerful, it scales to millions of messages per second, it has replay, it has consumer groups. But an MSK cluster costs $800–2,500/month whether you send 100 messages or 100 million. The math only works when your volume actually justifies it or when replay/multi-consumer semantics are a hard requirement. At startup scale, SQS handles almost every use case for under $10/month.

A practical decision rule: start with SQS. When your SQS bill exceeds $300/month (you're above ~750M messages/month), or when you need event replay for rebuilding state, or when you have 5+ consumer groups with different retention needs — then look at MSK or self-managed Kafka.

### 2.3 When to Use Queues

Understanding *why* you'd reach for a queue is as important as knowing how to configure one.

**Decoupling:** Service A publishes an event and doesn't know or care who processes it. You can deploy, scale, and fail the producer and consumer independently. The team building the email service doesn't need to coordinate releases with the team building the order service.

**Load leveling:** Your system gets hit with 10,000 requests per second during a flash sale. Without a queue, your downstream services get hammered or crash. With a queue, the spike hits the queue, and your workers process events at 1,000/second. Queue depth grows temporarily but the system survives. This is like a shock absorber for your architecture.

**Fan-out:** One event needs to trigger multiple independent actions. An order is placed: charge payment, send email, update inventory, notify the warehouse. Each action is independent — a shipping delay shouldn't block a payment charge. Fan these out through queues and they each succeed or fail independently.

**Retry with backoff:** Consumer fails? Message returns to queue. Retry with exponential backoff — first retry after 1 second, then 2, then 4, then 8. After N failures it goes to a Dead Letter Queue where humans investigate. This is elegant error handling that works at scale without any custom retry logic in your application code.

### 2.4 Dead Letter Queues (DLQ)

A DLQ is where messages go when your system has repeatedly failed to process them. Think of it as the unclaimed baggage office — things end up there when something went wrong, and someone needs to figure out what.

Without a DLQ, you have two bad options: silently drop failed messages (data loss), or retry forever (a "poison message" that keeps failing blocks processing of everything behind it).

**Setup pattern:**
```
Main Queue ──→ Consumer (fails) ──→ retry 1 ──→ retry 2 ──→ retry 3 ──→ DLQ
```

**DLQ operational requirements** — this is the stuff that separates teams that use DLQs well from teams that have DLQs they never look at:

- **Alerting:** DLQ depth > 0 should trigger a page or at least a Slack alert. A growing DLQ is a production incident, not a log line.
- **Inspection tooling:** Engineers need to read DLQ messages, understand why they failed, fix the bug, and replay them. Without tooling for this, DLQs become message graveyards.
- **Replay mechanism:** After fixing the consumer bug, you need to replay messages from DLQ back to the main queue. SQS has built-in DLQ redrive. For Kafka you typically write a small script.
- **Retention:** DLQ should have longer retention than the main queue — 14 days vs 4 days. You need time to investigate and replay.

**Poison message patterns** — what actually causes messages to repeatedly fail:
- Malformed data → fix the producer or add validation in the consumer.
- Schema mismatch → version your schemas (see section 2.7).
- Downstream dependency down → retry with exponential backoff; only DLQ after *persistent* failure, not transient.
- Message too large → reject at the producer. Store the payload in S3, send a reference URL in the message.

### 2.5 Ordering Guarantees

"I need messages in order" is often stated as an absolute requirement. In practice, you almost never need *global* ordering. What you need is *per-entity* ordering, and that's much cheaper to achieve.

**No ordering (SQS Standard):** Messages may arrive out of order. Cheapest, highest throughput. Fine when processing is idempotent and order-independent — sending a batch of analytics events, for example.

**Per-group ordering (SQS FIFO, Kafka partitions):** Messages with the same group/partition key are ordered. Different keys are processed in parallel. The canonical example: all events for `order-123` are ordered (create → payment → ship, in that order), but events for `order-456` may interleave with order-123's events. Use the entity ID as your partition key.

**Global ordering:** All messages in strict sequence. Requires a single partition or queue, which kills parallelism entirely. Almost never actually needed — if you think you need global ordering, probe deeper and you'll usually find you really need per-entity ordering.

**Kafka ordering gotcha:** Changing partition count re-hashes all keys. An order that was previously landing on partition 3 might now land on partition 7. Existing ordering guarantees break during repartitioning. Plan your partition count before going to production and change it carefully.

### 2.6 Event-Based Architecture Patterns

Not all events are the same. There are three distinct patterns, each with different trade-offs:

**Pattern 1 — Event Notification:**
An event simply notifies that something happened. Minimal data. Consumer must call back to get details.
```json
{ "event": "order.placed", "order_id": "ord-123", "timestamp": "..." }
```
The consumer receives this and then calls `GET /orders/ord-123` to get the full order. Simple and small, but it creates a callback dependency and increases load on the source system. Every consumer that receives the event makes another API call.

**Pattern 2 — Event-Carried State Transfer:**
The event contains everything the consumer needs. No callback required.
```json
{
  "event": "order.placed",
  "order_id": "ord-123",
  "customer": { "id": "cust-456", "email": "..." },
  "items": [ { "sku": "...", "qty": 2, "price": 29.99 } ],
  "total": 59.98
}
```
Consumers are fully decoupled. Trade-offs: larger messages, potential data staleness (the email in the event might change), and schema coupling between producer and every consumer.

**Pattern 3 — Event Sourcing:**
Store state as a sequence of events rather than current state. The current state is derived by replaying events.

```
Account Events:
  1. AccountOpened { id: "acc-1", owner: "Alice" }
  2. MoneyDeposited { id: "acc-1", amount: 1000 }
  3. MoneyWithdrawn { id: "acc-1", amount: 200 }
  4. MoneyDeposited { id: "acc-1", amount: 50 }

Current balance = replay: 0 + 1000 - 200 + 50 = 850
```

Event sourcing gives you a complete audit trail, time-travel queries, and the ability to rebuild state from any point in history. The costs are real: eventual consistency, performance requiring snapshots for large event logs, and event schema evolution is genuinely hard. This pattern appears naturally in accounting systems and banking — a ledger is event-sourced by definition.

### 2.7 Event Schema Evolution

Schemas change over time. Producers and consumers evolve independently. A breaking schema change in a message format can silently take down every consumer that doesn't upgrade simultaneously. This is how production incidents are born.

| Strategy | Tool | Wire Format | Schema Registry |
|---|---|---|---|
| **Avro + Schema Registry** | Confluent Schema Registry | Binary, compact | Yes, enforces compatibility |
| **Protobuf** | buf, protoc | Binary, compact | Optional (buf registry) |
| **JSON Schema** | JSON Schema validators | JSON, verbose | Optional |

**Avro compatibility modes:**
- **Backward compatible:** New schema can read old data. (Add fields with defaults, remove optional fields.) Old consumers can still process new messages.
- **Forward compatible:** Old schema can read new data. (Remove fields, add optional fields.) New consumers can process old messages.
- **Full compatible:** Both backward and forward. The gold standard — deploy producer and consumer independently in any order.

**Rules for safe schema evolution — memorize these:**
1. Adding a field → always include a default value. Consumers that don't know about the field use the default.
2. Removing a field → stop reading it first (deploy consumers that ignore it), then remove from the schema.
3. Renaming a field → add new field, deprecate old, remove old after all consumers migrate. Renaming is three steps.
4. Changing a field type → never. Add a new field of the new type instead. Type changes are breaking.

### 2.8 Idempotency and Exactly-Once Processing

True exactly-once delivery is impossible in distributed systems. Networks partition. Servers crash after processing but before acknowledging. What we actually implement is **effectively exactly-once** = at-least-once delivery + idempotent processing.

An idempotent operation produces the same result whether run once or a thousand times. `SET balance = 850` is idempotent. `ADD 50 TO balance` is not.

**Idempotency patterns:**

**1. Idempotency key:** The producer assigns a unique ID. The consumer checks "have I processed this ID?" before acting.
```sql
-- Before processing:
INSERT INTO processed_events (event_id) VALUES ('evt-123')
  ON CONFLICT DO NOTHING;
-- If inserted (affected rows = 1): process the event
-- If conflict (affected rows = 0): skip (already processed)
```

**2. Natural idempotency:** Design state mutations as absolute values when possible. `SET inventory_count = 47` is idempotent. `DECREMENT inventory_count BY 3` is not. This is a design choice, not just an implementation detail.

**3. Kafka exactly-once semantics (EOS):**
Kafka added transactional support to enable true EOS:
- Producer: `enable.idempotence=true` deduplicates at the broker using sequence numbers per partition.
- Transactional producer + consumer: `read_committed` isolation level. Atomic produce-and-commit-offset.
- Cost: ~20% throughput reduction. Use only when the business cost of a duplicate is high — financial transactions, inventory adjustments.

### 2.9 Real-World Architecture: Order Processing Pipeline

Let's put it all together. This is how a real order processing system looks in production:

```
┌─────────┐     ┌────────────┐     ┌───────────────┐     ┌──────────────┐
│  Client  │────→│  API (REST) │────→│ Order Created  │────→│  Payment Svc  │
│          │     │             │     │  (Kafka topic) │     │              │
└─────────┘     └────────────┘     └───────────────┘     └──────┬───────┘
                                          │                      │
                                          │               payment.completed
                                          │                      │
                                          ▼                      ▼
                                   ┌──────────────┐     ┌──────────────┐
                                   │ Inventory Svc │     │  Email Svc   │
                                   │ (reserve stock)│    │ (send conf.) │
                                   └──────────────┘     └──────────────┘
                                          │
                                   inventory.reserved
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ Shipping Svc  │
                                   │ (create label) │
                                   └──────────────┘
```

**Key design decisions worth internalizing:**
- Kafka topic per event type: `order.created`, `payment.completed`, `inventory.reserved`, `order.shipped`.
- Partition key: `order_id` — all events for one order are ordered within a partition.
- Each service has its own consumer group — independent processing at independent speeds.
- DLQ per service — payment failures don't block inventory processing.
- Idempotency key: `order_id + event_type` — safe to retry any event.

*Real-world:* Shopify processes billions of events through a Kafka-based pipeline. They migrated from a monolithic Rails app to event-driven services, using Kafka as the backbone for order processing, inventory, and payments. The migration took years, was done incrementally, and Kafka was the connective tissue that let them decompose the monolith one service at a time.

---

## 3. DATA FLOW & PIPELINE ARCHITECTURE

### 3.1 How Data Flows Through a Modern Application

Before you can optimize a system, you need to understand the journey of a single request through it. Here's every hop a request makes — from browser to response:

```
Browser/Mobile App
    │
    ▼
DNS Resolution (Route 53 → CloudFront IP)
    │
    ▼
CDN Edge (cache hit? return. miss? forward to origin)
    │
    ▼
Load Balancer (ALB — TLS termination, routing)
    │
    ▼
API Gateway / Middleware (auth, rate limiting, request validation)
    │
    ▼
Application Service (business logic)
    │
    ├──→ Cache check (Redis) ──→ hit? return cached response
    │
    ├──→ Database query (Postgres/MySQL)
    │         │
    │         └──→ Write? Publish event to Kafka
    │
    ├──→ External API call (payment provider, shipping)
    │
    ▼
Response (serialize → compress → CDN caches if applicable → client)
```

And in the background, the event-driven work happens:

```
Kafka Event
    │
    ▼
Consumer Service (picks up event from topic)
    │
    ├──→ Process business logic
    │
    ├──→ Call external APIs (with retry + circuit breaker)
    │
    ├──→ Write results to database
    │
    ├──→ Publish downstream events
    │
    └──→ Send webhook/notification
```

Every millisecond in the synchronous path matters because a user is waiting. Every failure in the asynchronous path needs to be handled gracefully because nobody is waiting but the state must eventually be consistent.

### 3.2 Synchronous vs Asynchronous Data Flow

The choice between sync and async isn't about technology preference — it's about whether the user needs to wait for the result.

**Use synchronous when:**
- User is waiting for a response (page load, form submission, API call).
- Operation is fast (<500ms).
- You need the result to continue — payment authorization before showing the confirmation page.
- Simplicity matters more than throughput.

**Use asynchronous when:**
- User doesn't need an immediate result — email sending, report generation, image processing.
- Operation is slow (>1s) or unreliable (external API calls with variable latency).
- You need to decouple producer from consumer — different teams, different scaling needs.
- Traffic is bursty — absorb spikes with a queue rather than scaling your entire stack.

**The hybrid pattern (accept-and-process-later):**

This is the pattern that makes most large-scale applications work:

```
Client ──→ POST /orders ──→ API validates, writes to DB, publishes event
                          ──→ Returns 202 Accepted { "order_id": "ord-123", "status": "processing" }

Background: Event → Payment → Inventory → Shipping → Update order status

Client ──→ GET /orders/ord-123 ──→ { "status": "shipped" }  (polling)
   or
Client ──→ WebSocket ──→ receives status updates in real-time
```

The client gets an immediate `202 Accepted` — they know the order was received. The slow work (charging payment, reserving inventory, creating shipping labels) happens asynchronously. The client polls or listens on a WebSocket for status updates. This pattern appears everywhere: Stripe payment processing, GitHub Actions run submissions, AWS job submissions. It's the right default for any operation over a second or two.

### 3.3 Fan-Out Patterns

Fan-out is when one event needs to trigger multiple independent processing paths. The order is placed — now you need payment, inventory, email, analytics, and potentially a dozen other things to happen. Doing these synchronously in sequence is slow and fragile (one failure blocks everything). Fan-out solves this.

**SNS + SQS Fan-Out (AWS):**
One event hits an SNS topic, which fans out to multiple SQS queues, each with independent consumers.

```
Order Placed ──→ SNS Topic ──→ SQS (payment processing)
                            ──→ SQS (inventory update)
                            ──→ SQS (email notification)
                            ──→ SQS (analytics ingestion)
```

Each queue has independent retry, DLQ, and scaling. If the email service is down, payment processing is completely unaffected.

**Kafka Fan-Out:**
One topic, multiple consumer groups. Same event, different consumers:

```
order.placed topic
    ├──→ Consumer Group: payment-service (reads all partitions)
    ├──→ Consumer Group: inventory-service (reads all partitions)
    ├──→ Consumer Group: notification-service (reads all partitions)
    └──→ Consumer Group: analytics-pipeline (reads all partitions)
```

**Key difference:** SNS+SQS physically duplicates the message per queue. Kafka stores once, and each consumer group tracks its own offset. Kafka is more storage-efficient at scale; SNS+SQS is simpler for AWS-native architectures and has per-queue DLQ, retry, and visibility configuration.

### 3.4 Saga Pattern for Distributed Transactions

Here's a scenario that will break your brain if you haven't thought about it: you need to charge a customer, decrement their inventory, and create a shipping order — across three separate microservices, each with their own database. If the inventory decrement fails after payment succeeds, you have a charged customer with no inventory allocated. How do you roll back across services with no shared transaction?

Traditional distributed transactions (two-phase commit / 2PC) solve this but are slow and brittle. A network partition during the commit phase leaves all participants blocked waiting indefinitely. In a microservices world, you cannot accept that.

**Sagas** provide eventual consistency without distributed locks. Each step in the saga has a corresponding compensating transaction. If a step fails, the saga runs compensating transactions for all previous steps in reverse order.

**Concrete example — E-commerce order saga (orchestration):**

```
Saga Orchestrator (Order Service)
    │
    ├── Step 1: Create Order (Order DB)        → success
    │                                            ↓
    ├── Step 2: Reserve Payment (Payment Svc)  → success
    │                                            ↓
    ├── Step 3: Reserve Inventory (Inventory)  → FAILURE
    │                                            ↓
    │   ┌── Compensate Step 2: Refund Payment (Payment Svc)
    │   │
    │   └── Compensate Step 1: Cancel Order (Order DB)
    │
    └── Final state: Order cancelled, payment refunded
```

**Implementation with Temporal/Step Functions:**
```python
# Temporal workflow (Python SDK)
@workflow.defn
class OrderSaga:
    @workflow.run
    async def run(self, order: Order):
        # Forward steps
        order_id = await workflow.execute_activity(
            create_order, order, start_to_close_timeout=timedelta(seconds=30)
        )
        try:
            payment_id = await workflow.execute_activity(
                reserve_payment, order, start_to_close_timeout=timedelta(seconds=30)
            )
            await workflow.execute_activity(
                reserve_inventory, order, start_to_close_timeout=timedelta(seconds=30)
            )
        except Exception:
            # Compensating transactions
            await workflow.execute_activity(refund_payment, payment_id)
            await workflow.execute_activity(cancel_order, order_id)
            raise

        await workflow.execute_activity(confirm_order, order_id)
```

**Saga design rules:**
1. Every step must have a compensating action.
2. Compensating actions must be idempotent — they may run multiple times due to retries.
3. Compensating actions cannot fail permanently — use retry with eventual manual intervention as last resort.
4. Order of compensation is reverse of execution.

Choreography (each service reacts to events and publishes its own events) is an alternative to orchestration (one orchestrator directs the saga). Choreography is more decoupled but harder to debug — you need to trace the event chain across services to understand what happened.

### 3.5 CQRS in Practice

CQRS stands for Command Query Responsibility Segregation. The core idea: your write path and your read path have different performance characteristics and should use different models — and often different databases.

```
                    ┌─────────────────┐
  Commands ────────→│  Write Model    │──→ PostgreSQL (normalized, optimized for writes)
  (create, update)  │  (Domain logic) │        │
                    └─────────────────┘        │ Events
                                               ▼
                                        ┌──────────────┐
                                        │  Event Bus   │
                                        │  (Kafka)     │
                                        └──────┬───────┘
                                               │
                    ┌─────────────────┐        │
  Queries ─────────→│  Read Model     │←───────┘
  (list, search)    │  (Denormalized) │  Elasticsearch / Redis / Materialized views
                    └─────────────────┘
```

**When CQRS is justified:**
- Read and write patterns are drastically different — e.g., a 1000:1 read:write ratio with complex queries.
- Your read model needs a fundamentally different structure: denormalized for fast retrieval, search-optimized, geospatially indexed.
- Your write model needs strong consistency; your read model can tolerate a few hundred milliseconds of staleness.

**When CQRS is overkill:**
- Simple CRUD applications where reads and writes look essentially the same.
- Your team cannot handle the eventual consistency complexity (the read model is always slightly behind the write model).

*Real-world:* Uber uses CQRS for their driver matching system. Writes (driver location updates coming in hundreds of times per minute per driver) go to a fast write store. Reads (find the nearest ten available drivers for this pickup request) go to a geospatial index purpose-built for proximity queries. Using one database for both would be a non-starter at Uber's scale.

### 3.6 Change Data Capture (CDC) Pipelines

CDC is one of those elegant solutions that makes you wonder why you'd ever do things the other way. Instead of application code publishing events (which has a subtle but serious failure mode), CDC reads the database's transaction log and streams changes as events automatically.

**The dual-write problem CDC solves:**

```python
# BAD: dual write — what if step 2 fails?
def place_order(order):
    db.insert(order)          # Step 1: write to DB
    kafka.publish(order)      # Step 2: publish event — network error? event lost.

# GOOD: CDC — database is the single source of truth
def place_order(order):
    db.insert(order)          # Only write to DB
# Debezium reads the WAL/binlog and publishes to Kafka automatically
```

In the dual-write pattern, if your application crashes between the database write and the Kafka publish, the event is lost and you have silently inconsistent state. With CDC, the database transaction log is your source of truth — if the write committed, Debezium will eventually read it and publish the event.

**Debezium → Kafka → Elasticsearch pipeline:**
```
PostgreSQL (WAL) ──→ Debezium Connector ──→ Kafka ──→ Elasticsearch Sink Connector
                     (Kafka Connect)                   (Kafka Connect)
```

**CDC use cases:**
- Replicate data to search indices (Postgres → Elasticsearch) — changes appear in search within a second.
- Feed data warehouses in real-time (OLTP → Kafka → Snowflake) — no more nightly ETL jobs.
- Sync caches: a database change automatically invalidates or updates the Redis cache.
- Audit log: every database change is captured automatically, with before and after state.
- Database migration: stream changes from old database to new while both run simultaneously.

### 3.7 Data Warehouse Feeding

Your operational database is optimized for low-latency reads and writes of individual records. Your analytics database (the warehouse) is optimized for scanning billions of records and computing aggregates. These are fundamentally different optimization profiles — which is why data always needs to move from one to the other.

**Real-time ingestion (streaming):**
```
Application DB ──→ CDC (Debezium) ──→ Kafka ──→ Flink/ksqlDB ──→ Data Warehouse
```
Latency: seconds to minutes. Use when dashboards need near-real-time data, for fraud detection, or real-time recommendations. More infrastructure to manage but the freshness is worth it.

**Batch ingestion:**
```
Application DB ──→ Scheduled ETL (Airflow) ──→ Transform (dbt) ──→ Data Warehouse
```
Latency: hours. Use for daily reports, historical analysis, or when cost is more important than freshness. Batch is dramatically cheaper — you're doing one big job instead of continuous streaming.

**Modern lakehouse pattern:**
```
Sources ──→ Kafka ──→ Object Storage (S3/GCS) in Parquet/Iceberg ──→ Query Engine (Spark/Trino)
```
Store everything cheaply in object storage with open formats. Query with any engine. Avoid vendor lock-in. Apache Iceberg adds table semantics (ACID transactions, schema evolution, time travel) on top of plain object storage files. This is the architecture of modern data platforms.

### 3.8 Workflow Orchestration

When your business logic spans multiple steps, multiple services, and time windows that might stretch hours or days, you need workflow orchestration. Think of it as managed state machines with persistence and retry built in.

| Tool | Type | Language | Strengths |
|---|---|---|---|
| **Temporal** | Durable execution | Go, Java, Python, TS | Code-first, fault-tolerant, long-running workflows |
| **Apache Airflow** | DAG scheduler | Python | Data pipeline standard, massive operator library |
| **AWS Step Functions** | State machine | JSON/ASL | Serverless, AWS-native, visual designer |
| **Prefect** | DAG scheduler | Python | Modern Airflow alternative, better DX |
| **Dagster** | Asset-based | Python | Software-defined assets, data-aware orchestration |

**Temporal deep dive:**

Temporal is what you'd build if you sat down and said "what if workflows were as reliable as database transactions?" Workflows survive process crashes, server restarts, even datacenter failures — the runtime persists workflow state to a durable backend. Activities are the side-effecting operations (API calls, database writes) that get automatically retried on failure. Signals let you inject external events into a running workflow. Timers are durable sleeps — you can literally `sleep(30 days)` and the timer fires even if every server restarts in between.

*Real-world:* Stripe uses Temporal for payment orchestration — a payment attempt that hits a processing error can retry the specific failed step without re-running the entire payment flow. Snap uses it for content moderation pipelines where a single piece of content might need to go through a dozen review steps over hours.

**Airflow deep dive:**

Airflow defines workflows as DAGs (Directed Acyclic Graphs) — tasks with explicit dependency relationships. Tasks might be `PythonOperator`, `BashOperator`, `PostgresOperator`, `S3ToRedshiftOperator`. The scheduler determines what runs when; the executor determines where it runs (locally, on Celery workers, on Kubernetes pods).

Critical pitfall: don't put heavy processing in the DAG definition file. It runs on the scheduler process, not on workers. Your DAG should only define the structure; the actual work happens inside the operator.

---

## 4. DATABASE MIGRATIONS

### 4.1 Schema Migration Tools

The first time you accidentally break a production database with a schema migration, you develop a healthy respect for this topic. Every migration tool shares the same core model: a sequence of numbered or timestamped migration files applied in order, tracked in a `schema_migrations` table, never modified after deployment. The files are your history; the table is your position in that history.

| Tool | Language | Approach | Key Feature |
|---|---|---|---|
| **Flyway** | Java (any DB) | Versioned SQL files (`V1__create_users.sql`) | Simple, convention-based |
| **Liquibase** | Java (any DB) | XML/YAML/JSON/SQL changesets | Rollback generation, diff |
| **Alembic** | Python (SQLAlchemy) | Python migration scripts | Auto-generates from model changes |
| **Prisma Migrate** | TypeScript | Declarative schema → SQL migrations | Schema-first, great DX |
| **golang-migrate** | Go | Numbered SQL files (up/down) | Lightweight, CLI-driven |
| **Knex** | JavaScript | JS migration files | Part of the Knex query builder ecosystem |

The choice of tool is usually dictated by your stack. What matters far more than the tool is *how* you write migrations.

### 4.2 Zero-Downtime Migration Strategies

Here's the brutal truth about schema migrations in production: during a deployment, **both old and new application code are running simultaneously**. Rolling deploys mean old containers are still processing requests while new containers start up. Any migration must be compatible with both versions — simultaneously.

This single constraint drives everything else.

#### Expand-and-Contract Pattern

The universal strategy for safe schema changes. Two phases separated by at least one full deploy cycle:

**Expand phase (additive, backward-compatible):**
- Add new columns, tables, indexes.
- Old code ignores new columns. New code uses them.
- Deploy new application code that writes to both old and new locations.

**Contract phase (remove old, after all code is updated):**
- Remove old columns, tables, deprecated fields.
- Only after confirming no code anywhere reads or writes the old structure.

#### Adding Columns

```sql
-- Migration 1: Add nullable column (safe, no lock on reads)
ALTER TABLE orders ADD COLUMN shipping_address_id INTEGER;

-- Application deploy: code writes to both old (shipping_address text) and new (shipping_address_id)

-- Migration 2: Backfill (do in batches, not one UPDATE)
UPDATE orders SET shipping_address_id = addresses.id
FROM addresses WHERE orders.shipping_address = addresses.full_text
WHERE orders.id BETWEEN 1 AND 10000;  -- batch by ID range

-- Migration 3: After backfill complete, add constraint
ALTER TABLE orders ALTER COLUMN shipping_address_id SET NOT NULL;

-- Application deploy: code reads from new column only

-- Migration 4: Drop old column (contract phase)
ALTER TABLE orders DROP COLUMN shipping_address;
```

**Critical: backfill in batches.** A single `UPDATE orders SET ...` on a 100M row table holds a lock for minutes, potentially grinding your database to a halt during peak traffic. Batch by ID range, add a small sleep between batches, monitor your database CPU and replication lag.

#### Dropping Columns

Never drop a column in the same deploy that stops reading it. Old code instances are still running and will crash trying to SELECT a column that no longer exists.

```
Deploy 1: Stop reading the column. Stop writing to it.
Deploy 2: (after all old instances are gone) DROP COLUMN.
```

In practice, use a "column ignore" list in your ORM (most ORMs support this) or add the column to a deprecation config that your CI validates.

#### Renaming Columns

Renaming is a four-step process, not a one-liner. It's effectively: add + backfill + migrate code + drop.

```sql
-- Step 1: Add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);

-- Step 2: Backfill
UPDATE users SET full_name = name WHERE id BETWEEN ... AND ...;

-- Step 3: Deploy code that writes to BOTH name and full_name, reads from full_name
-- Step 4: After all old code is gone, drop old column
ALTER TABLE users DROP COLUMN name;
```

If you try to rename in one step, you'll have old code reading from `name` (which no longer exists) and new code reading from `full_name` — and since both are running simultaneously, chaos ensues.

#### Adding Indexes Concurrently

Standard `CREATE INDEX` locks the table for writes. On a 50M row table, that's minutes of write downtime. Never do this in production.

```sql
-- PostgreSQL: CONCURRENTLY doesn't lock the table
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders(customer_id);

-- Caveat: CONCURRENTLY can't run inside a transaction.
-- If it fails partway, you get an INVALID index. Check and retry:
-- SELECT * FROM pg_indexes WHERE indexdef LIKE '%INVALID%';
```

**MySQL equivalent:** `ALTER TABLE ... ADD INDEX` is online by default in InnoDB (MySQL 5.6+), but may still require a table copy for some operations — verify with your specific MySQL version and operation type.

#### Large Table Migrations

For tables with billions of rows, even `ALTER TABLE ... ADD COLUMN` can be problematic depending on the database version and the specific operation.

**Tools for MySQL:**
- **gh-ost** (GitHub's OST): Creates a ghost table, copies data incrementally using binlog replication, then swaps atomically. No triggers. Pausable and throttleable — you can slow it down if the database is under load.
- **pt-online-schema-change** (Percona Toolkit): Similar approach using triggers to capture changes during the copy.

**Tools for PostgreSQL:**
- **pg_repack:** Reorganizes tables online without heavy locks. Useful for reclaiming bloat from lots of updates and deletes.
- Most `ALTER TABLE ADD COLUMN` with a default is instant in Postgres 11+ — it stores the default in the catalog rather than rewriting the table. This is a massive quality-of-life improvement.

### 4.3 Data Migrations vs Schema Migrations

These are not the same thing, and conflating them is a mistake.

**Schema migrations** change the structure: add tables, columns, indexes, constraints. They're typically fast and deterministic.

**Data migrations** change the content: backfill values, transform data formats, merge duplicates, normalize inconsistent data. They can be slow (touching billions of rows), non-deterministic (dependent on data state), and need to run in batches.

**Keep them strictly separate:**
- Schema migrations run as part of the deploy pipeline — they're fast and safe.
- Data migrations run as background jobs with monitoring — they're slow and need care.
- A blocked data migration should never block a code rollback. If you bundle them and the data migration is half-done, rolling back the code doesn't undo the half-migrated data.

### 4.4 Rollback Strategies

The instinct to write `up` and `down` migrations is understandable but often wrong. The problem: `down` migrations are frequently data-destructive. You dropped a column in the `up`. Your `down` tries to add it back — but all the data that was in it is gone forever.

**Backward-compatible migrations (the correct approach):**
Every migration is forward-only but backward-compatible. Old code works with the new schema. If the deploy fails, roll back the code — not the schema. This is the expand phase of expand-and-contract.

**Down migrations (only for development):**
Every migration file has an `up` and `down`. The `down` reverses the `up`. These are useful in development when you're iterating on schema design. In production, they're a liability.

**Practical approach:**
1. Write migrations that are always backward-compatible with the previous version of the code.
2. Never write `down` migrations for production deployments. They create false confidence.
3. If a migration is genuinely wrong, write a new forward migration to fix it. The history stays intact.

### 4.5 Multi-Service Migration Coordination

When multiple services depend on the same schema (even indirectly through shared events), migrations get harder.

1. **Schema changes must be backward-compatible** — you cannot coordinate deploys across N services atomically. The window between services deploying might be hours.
2. **Version your event schemas** — a schema change that affects events needs schema registry compatibility checks before the migration even starts.
3. **Expand-contract across services:** Deploy producing service with new schema first. Deploy consuming services to handle both old and new schema. Remove old format.
4. **Feature flags:** Gate new behavior behind flags. Enable per-service after confirming compatibility. This decouples deploy from activation.

### 4.6 Database Branching

One of the most exciting developments in recent database infrastructure is database branching — the ability to create independent copies of your database schema and data for testing, just like you branch code in git.

**Neon (Postgres):** Copy-on-write branching. Create a full copy of your production database in seconds, regardless of size. Each branch is an independent Postgres instance with its own compute. Perfect for: preview environments per PR (test your schema migration against a copy of production data before deploying), debugging production data issues without risk.

**PlanetScale (MySQL):** Git-like branching for schemas specifically. Create a branch, make schema changes, open a "deploy request" (like a pull request for your schema). PlanetScale diffs the schema, shows the impact, and deploys with zero downtime. Non-blocking schema changes are built into the platform.

**The workflow:**
```
main (production DB)
    │
    ├── branch: feature-add-shipping (schema changes + test data)
    │       └── PR preview environment uses this branch
    │
    └── merge: schema changes applied to main via deploy request
```

This workflow makes migrations reviewable and testable in a way that's simply not possible when your only option is "apply to production and hope."

---

## 5. HOW A LARGE-SCALE APP COMES TOGETHER

### 5.1 Complete Architecture — E-Commerce Platform

Everything we've covered in this chapter exists to serve real systems. Here's what it looks like when it all comes together — an e-commerce platform serving millions of users, built from components you now recognize.

```
                            ┌──────────────────────────────────────────────┐
                            │              EXTERNAL                        │
                            │                                              │
                            │  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
                            │  │ Browser │  │ Mobile   │  │ Partner   │  │
                            │  │  (React)│  │  (RN)    │  │   APIs    │  │
                            │  └────┬────┘  └────┬─────┘  └─────┬─────┘  │
                            └───────┼────────────┼──────────────┼─────────┘
                                    │            │              │
                                    ▼            ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  EDGE LAYER                                                                  │
│  ┌──────────────┐    ┌──────────────┐                                       │
│  │   Route 53   │───→│  CloudFront  │  (CDN: static assets, API caching)    │
│  │   (DNS)      │    │  / Cloudflare│                                       │
│  └──────────────┘    └──────┬───────┘                                       │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────────────┐
│  INGRESS LAYER              ▼                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   WAF        │───→│  ALB         │───→│ API Gateway  │                   │
│  │  (Firewall)  │    │ (L7 routing) │    │ (auth, rate  │                   │
│  └──────────────┘    └──────────────┘    │  limit, logs)│                   │
│                                          └──────┬───────┘                   │
└─────────────────────────────────────────────────┼───────────────────────────┘
                                                  │
┌─────────────────────────────────────────────────┼───────────────────────────┐
│  APPLICATION LAYER (Kubernetes / ECS)           ▼                            │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Order   │  │ Product  │  │ Payment  │  │ Shipping │  │  User    │    │
│  │ Service  │  │ Catalog  │  │ Service  │  │ Service  │  │ Service  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │              │          │
└───────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────┘
        │              │              │              │              │
┌───────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────┐
│  DATA LAYER          │              │              │              │          │
│                      ▼              ▼              ▼              ▼          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Orders   │  │ Products │  │ Payments │  │ Shipping │  │ Users    │    │
│  │ (Postgres)│ │ (Postgres)│ │ (Postgres)│ │ (Postgres)│ │ (Postgres)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ Redis Cluster │  │Elasticsearch │  │   S3         │                     │
│  │ (cache+pubsub)│  │  (search)    │  │ (files/media)│                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└────────────────────────────────────────────────────────────────────────────┘
        │
┌───────┼────────────────────────────────────────────────────────────────────┐
│  EVENT / ASYNC LAYER                                                        │
│       ▼                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐               │
│  │ Kafka Cluster │────→│  Workers     │────→│  External    │               │
│  │ (event bus)   │     │ (consumers)  │     │  APIs        │               │
│  └──────┬───────┘     └──────────────┘     │(Stripe,etc.) │               │
│         │                                   └──────────────┘               │
│         │             ┌──────────────┐                                     │
│         └────────────→│  Debezium    │──→ CDC to Elasticsearch, Warehouse  │
│                       │ (CDC)        │                                     │
│                       └──────────────┘                                     │
└────────────────────────────────────────────────────────────────────────────┘
        │
┌───────┼────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY LAYER                                                        │
│       ▼                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Prometheus   │  │   Grafana    │  │   Jaeger     │  │  PagerDuty   │  │
│  │ (metrics)    │  │ (dashboards) │  │  (tracing)   │  │  (alerting)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 User Request Flow — Buying a Product

Let's trace exactly what happens when a user clicks "Buy Now." Every layer is doing something important.

**1. DNS:** The user types `shop.example.com`. Route 53 returns a CloudFront distribution IP — latency-based routing picks the closest edge location, so a user in Singapore gets a Singapore edge, not US-East.

**2. CDN:** CloudFront serves cached product images, JavaScript bundles, and CSS directly from the edge. API requests (`/api/*`) pass through to origin because they can't be cached (they depend on user identity and live data).

**3. WAF:** AWS WAF inspects the request for known attack patterns: SQL injection attempts, XSS payloads, known bad bot fingerprints. It also applies rate limits per IP — 1,000 requests per minute is fine; 100,000 in a minute is probably an attack.

**4. Load Balancer:** The ALB terminates TLS (your application servers never see raw TLS). It routes `/api/orders/*` → Order Service target group, `/api/products/*` → Product Catalog target group. Health checks continuously test each target and remove unhealthy instances from rotation.

**5. API Gateway:** Validates the JWT token from Auth0/Cognito. Extracts user identity (user_id, roles, permissions) from the token claims. Applies per-user rate limits. Logs the request for audit purposes. All of this before your application code runs.

**6. Order Service:** Validates order data. Makes a synchronous call to Product Catalog to check inventory (the user needs to know immediately if something is out of stock). Writes the order to Postgres. Publishes `order.created` to Kafka. Returns `202 Accepted` — the order is queued, not yet fulfilled.

**7. Kafka:** The `order.created` event is consumed by Payment Service, Inventory Service, and Notification Service — each through their own consumer group. They proceed independently and at their own pace.

**8. Payment Service:** Calls Stripe API. On success, publishes `payment.completed`. On failure, publishes `payment.failed`, which triggers saga compensation — the order gets cancelled and the customer is notified.

**9. Cache:** Product catalog data is cached in Redis (TTL 5 minutes). Cache-aside pattern: check Redis first, cache miss → query Postgres → populate Redis. The next request for the same product hits Redis, not Postgres.

**10. Response:** The `202 Accepted` response lands immediately. A WebSocket connection (established when the user loaded the page) pushes real-time status updates: "Payment confirmed," "Order preparing," "Shipped."

### 5.3 Background Processing Flow

The synchronous request ended at step 10. In the background, the real work continues:

```
order.created (Kafka)
    │
    ├──→ Payment Worker: charge customer via Stripe API
    │       └──→ payment.completed / payment.failed
    │
    ├──→ Inventory Worker: decrement stock in Inventory DB
    │       └──→ inventory.reserved / inventory.insufficient
    │
    ├──→ Notification Worker: send order confirmation email via SendGrid
    │       └──→ notification.sent (fire-and-forget, DLQ on failure)
    │
    └──→ Analytics Worker: write to data warehouse (Snowflake via Kafka Connect)
```

**Failure handling — the system that makes sleep possible:**
- Payment fails → saga compensates: cancel order, release inventory.
- Inventory insufficient → saga compensates: refund payment, notify customer.
- Email fails → goes to DLQ. Alert fires. Manual replay after fix. The order is still valid — email failure doesn't break the order.
- Analytics fails → Kafka retains events for 7 days. Consumer resumes from its last committed offset when it comes back up.

### 5.4 Real-Time Features

The WebSocket pushing status updates is its own mini-architecture:

```
Client ──WebSocket──→ WebSocket Server (Node.js/Go)
                           │
                           ├──subscribe──→ Redis Pub/Sub (channel: order:ord-123)
                           │
                           │  Order Service publishes status update to Redis
                           │
                           └──push──→ Client receives: { "status": "shipped" }
```

**Scaling WebSockets** requires care. Each WebSocket server maintains persistent connections — roughly 10K to 100K concurrent connections per server, depending on memory and CPU. Redis Pub/Sub ensures that a status update published from any app server reaches the correct WebSocket server, regardless of which server holds that user's connection.

For higher throughput or managed infrastructure, managed services like Ably, Pusher, and AWS AppSync handle the WebSocket scaling complexity for you.

### 5.5 Search Pipeline

Why doesn't the search query just hit Postgres? Because full-text search, fuzzy matching, relevance scoring, faceted filtering, and sub-100ms response times on millions of products require a search engine. Postgres is a relational database — it's exceptional at what it does, but Elasticsearch is purpose-built for this.

```
Product Catalog DB (Postgres)
    │
    └──→ Debezium (reads WAL) ──→ Kafka topic: products.changes
                                       │
                                       └──→ Kafka Connect Elasticsearch Sink
                                                │
                                                └──→ Elasticsearch (search-optimized index)
                                                        │
                                                        └──→ Search API ──→ Client
```

**Consistency:** There's typically a sub-second delay between a product update in Postgres and its appearance in Elasticsearch. For the search results page, this is completely acceptable. For the product detail page (where you want to be sure you're showing current price and availability), read directly from Postgres.

### 5.6 Analytics Pipeline

Operational data flows to the warehouse through a pipeline designed for throughput over latency:

```
Application events ──→ Kafka ──→ Flink (stream processing)
                                      │
                                      ├──→ Real-time dashboard (Grafana)
                                      │
                                      └──→ S3 (Parquet files) ──→ Snowflake / BigQuery
                                                                      │
                                                                      └──→ dbt (transforms)
                                                                            │
                                                                            └──→ Looker / Metabase
```

**Event taxonomy matters more than engineers expect.** Define a schema for analytics events early: `event_name`, `timestamp`, `user_id`, `session_id`, `properties` (JSON). Put it in a schema registry. Enforce it at the producer. Garbage analytics data is worse than no analytics data — it takes months to discover and erodes trust in the data team.

### 5.7 Auth Flow

Authentication and authorization are woven through every request:

```
Client ──→ Auth Provider (Auth0 / Cognito / Clerk)
              │
              └──→ Returns JWT (access token + refresh token)

Client ──→ API Request (Authorization: Bearer <JWT>)
              │
              └──→ API Gateway / Middleware
                      │
                      ├── Verify JWT signature (public key from JWKS endpoint, cached)
                      ├── Check expiration
                      ├── Extract claims (user_id, roles, permissions)
                      └── Pass to service: request.user = { id, roles, permissions }

Service ──→ Authorization check: does this user have permission for this action?
```

**Token lifecycle:**
- Access token: short-lived (15 minutes). Stateless verification — no database call needed, just verify the cryptographic signature against the public key.
- Refresh token: long-lived (7-30 days). Stored securely in an httpOnly cookie (not accessible to JavaScript). Used to get new access tokens transparently.
- Token revocation: maintain a blocklist in Redis (check on each request) for immediate revocation, or rely on the short access token TTL and wait for expiry. Which approach depends on your security requirements.

### 5.8 Deployment Pipeline

Getting code safely from "git push" to "serving production traffic" is itself a complex system:

```
Developer ──→ git push ──→ GitHub
                              │
                              └──→ CI (GitHub Actions / CircleCI)
                                      │
                                      ├── Lint + type check
                                      ├── Unit tests
                                      ├── Integration tests (testcontainers)
                                      ├── Build container image
                                      ├── Push to container registry (ECR)
                                      ├── Run DB migrations (expand phase)
                                      │
                                      └──→ CD (ArgoCD / Spinnaker)
                                              │
                                              ├── Deploy to staging (auto)
                                              ├── Run smoke tests
                                              ├── Deploy to production (canary: 5%)
                                              ├── Monitor error rates, latency (15 min)
                                              ├── Promote to 100% (auto if metrics OK)
                                              └── Alert on-call if rollback triggered
```

**Key details that separate mature pipelines from naive ones:**

Container images are tagged with the git SHA — immutable and traceable. You can always answer "what exact code is running in production right now?" Database migrations run *before* new code deploys (this is the expand phase — backward-compatible additions only). The contract phase runs as a separate follow-up after the old code is fully gone.

Canary deploys route 5% of production traffic to the new version. The pipeline automatically compares error rate and p99 latency against the baseline. If the new version is degraded, it rolls back automatically. If metrics are healthy after 15 minutes, it promotes to 100%.

Feature flags (LaunchDarkly, Unleash, or homegrown) decouple *deploy* from *release*. Deploy the code dark. Enable it for 1% of users. Watch metrics. Ramp to 10%, 50%, 100%. Roll back in seconds if something goes wrong. This is how you do safe releases without zero-downtime pressure.

---

## 6. MONITORING & OBSERVABILITY IN PRACTICE

### 6.1 The Three Pillars

You can't fix what you can't see. Observability is the lens that lets you understand what's happening inside a system from the outside. The three pillars give you complementary views:

| Pillar | What | Tool (Open Source) | Tool (Commercial) |
|---|---|---|---|
| **Metrics** | Numeric measurements over time | Prometheus + Grafana | Datadog, New Relic |
| **Logs** | Discrete events with context | Loki + Grafana / ELK | Datadog Logs, Splunk |
| **Traces** | Request flow across services | Jaeger / Tempo + OTel | Datadog APM, Honeycomb |

Metrics tell you *that* something is wrong. Logs tell you *what* happened. Traces tell you *where* in the system it happened. You need all three — they're complementary, not substitutable.

### 6.2 Metrics: Prometheus + Grafana

Prometheus is pull-based, which is the opposite of what most people expect. Instead of services pushing metrics to a central collector, Prometheus *scrapes* `/metrics` endpoints on your services every 15-30 seconds. This model is elegant: services don't need to know about Prometheus, and you can add Prometheus to an existing system without changing the services.

The data model is `metric_name{label=value} value timestamp`. Every unique combination of metric name and label set is a separate time series. Labels are how you slice and dice: `http_requests_total{service="order-api", status="500"}`.

**Essential PromQL patterns:**

```promql
# Request rate (per second, over 5 min window)
rate(http_requests_total{service="order-api"}[5m])

# Error rate percentage
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="order-api"}[5m]))

# Saturation: CPU usage per pod
rate(container_cpu_usage_seconds_total[5m]) / container_spec_cpu_quota * 100
```

**Alert rules (what to alert on):**

Alert on symptoms, not causes. Don't alert on "CPU is 80%" — alert on "error rate is above 5%" or "p99 latency is above 2 seconds." Those are user-facing problems. High CPU might be fine if the service is healthy.

```yaml
groups:
  - name: critical
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5% for {{ $labels.service }}"

      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p99 latency above 2s for {{ $labels.service }}"
```

### 6.3 Logging: ELK vs Loki

Logs are the most expensive observability signal. Every log line is written, shipped, stored, and possibly indexed. At scale, your logging bill can exceed your compute bill if you're not careful.

**ELK Stack (Elasticsearch + Logstash + Kibana):**
Full-text indexing of every log line. You can grep anything, run regex across billions of lines, aggregate on any field. The power is real. So is the cost: Elasticsearch stores and indexes everything, and the storage and compute requirements scale linearly with log volume. Logstash (or lighter alternatives like Fluentd or Fluent Bit) parses, transforms, and routes logs before they reach Elasticsearch.

**Loki + Grafana:**
Loki made a deliberate trade-off: it indexes only labels (like Prometheus) and stores raw log lines without full-text indexing. You query by labels first (which is fast), then grep through the matching log streams. Orders of magnitude cheaper than ELK because you're not indexing the log content, just the metadata. LogQL is the query language.

The choice: if most of your log queries are "show me logs for the order service in the last hour during this incident," Loki is sufficient and dramatically cheaper. If you need complex log analysis, regex searches across all services, or statistical aggregations over log content, ELK is worth the cost.

**Structured logging is non-negotiable:**
```json
{
  "timestamp": "2025-03-15T10:23:45Z",
  "level": "error",
  "service": "order-service",
  "trace_id": "abc123",
  "user_id": "usr-456",
  "order_id": "ord-789",
  "message": "Payment processing failed",
  "error": "stripe_timeout",
  "duration_ms": 30000
}
```

The `trace_id` field is critical — it lets you jump from a log entry directly to the distributed trace that shows every service involved in that request. Never log PII: no emails, passwords, or credit card numbers. Compliance violations from logging PII are embarrassing and expensive.

### 6.4 Tracing: OpenTelemetry + Jaeger/Tempo

Distributed tracing solves a specific and painful problem: a request enters your system and touches ten services before returning. Something is slow. Which service is the bottleneck? Without tracing, you're reading ten separate log files and trying to mentally assemble the timeline.

```
Trace: abc123
├── Span: API Gateway (12ms)
│   └── Span: Order Service (45ms)
│       ├── Span: Redis cache lookup (2ms) — cache miss
│       ├── Span: Postgres query (8ms)
│       ├── Span: Payment Service call (120ms)  ← bottleneck
│       │   └── Span: Stripe API call (115ms)
│       └── Span: Kafka publish (3ms)
└── Total: 190ms
```

The bottleneck is immediately obvious: 115ms spent waiting on Stripe. Without this trace, you'd be guessing.

**OpenTelemetry (OTel)** is the vendor-neutral standard for instrumenting applications. Instrument once with OTel, export to any backend — Jaeger, Tempo, Honeycomb, Datadog. No more lock-in.

```python
# Auto-instrumentation (Python) — zero code changes
# pip install opentelemetry-distro opentelemetry-exporter-otlp
# opentelemetry-bootstrap -a install
# opentelemetry-instrument python app.py

# Manual instrumentation for custom spans
from opentelemetry import trace

tracer = trace.get_tracer("order-service")

def process_order(order_id):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        # ... business logic
```

**Backends:**
- **Jaeger:** Open source, battle-tested (created by Uber). Self-hosted.
- **Tempo:** Grafana's tracing backend. Stores traces in object storage (S3). Cost-effective at scale.
- **Honeycomb:** SaaS, exceptional query UX for exploring high-cardinality trace data.

### 6.5 APM: When to Use Commercial vs Open Source

This is a legitimate architectural decision with real financial consequences.

**Open source (Prometheus + Grafana + Loki + Tempo):**
Full control. No per-host or per-GB pricing. Works across any cloud. But it requires operational expertise to run — someone needs to manage the Prometheus configuration, the Grafana dashboards, the Loki ingestion pipeline. If your team has platform engineering capacity and cost sensitivity, this is the right choice.

**Commercial (Datadog, New Relic, Dynatrace):**
Unified platform: metrics, logs, traces, APM, Real User Monitoring, synthetic checks, security, profiling — all with seamless correlation. The operational burden is essentially zero. The cost can be substantial at scale: Datadog bills per host plus per GB ingested. A 200-node Kubernetes cluster can run $50K-$200K per year depending on features enabled.

**Decision framework:**
- Small team, strong platform engineering capacity → open source.
- Fast-moving team that needs to ship features, not manage monitoring infrastructure → commercial.
- Hybrid: Prometheus for metrics (free, pull-based, low operational overhead), commercial for traces and APM (higher value per dollar for the complexity saved).

### 6.6 Uptime Monitoring

Metrics and traces tell you what's happening inside your system. Uptime monitoring tells you if your system is reachable *from the outside*, from multiple locations around the world.

**Synthetic checks:** External probes that hit your endpoints from multiple locations every 30-60 seconds. They verify not just that you return HTTP 200, but that the response body contains expected content and that the response arrives within your latency threshold.

Tools: Checkly, Pingdom, UptimeRobot, AWS CloudWatch Synthetics.

Alert only when 2+ consecutive failures occur from 2+ locations — this filters out transient DNS failures or single flaky probes that would otherwise page your on-call at 3 AM for nothing.

**Health endpoints:**
```json
GET /health → { "status": "healthy" }          // for load balancers (fast, no auth)
GET /health/ready → { "status": "ready" }      // K8s readiness (can accept traffic?)
GET /health/live → { "status": "alive" }       // K8s liveness (should restart?)
GET /health/detailed → {                       // for operators (authenticated)
  "status": "healthy",
  "checks": {
    "database": { "status": "healthy", "latency_ms": 5 },
    "redis": { "status": "healthy", "latency_ms": 1 },
    "kafka": { "status": "degraded", "message": "1 of 3 brokers unreachable" }
  }
}
```

The readiness and liveness distinction matters for Kubernetes: a pod that can't yet connect to the database (liveness check passes, readiness fails) should be excluded from load balancer rotation but shouldn't be restarted. A pod that's completely deadlocked (liveness fails) should be restarted.

**Status pages:** Public communication during incidents. Atlassian Statuspage, Instatus, or self-hosted options. Update proactively — customers trust transparency. A detailed incident update in Slack feels better than silence, even when you don't yet know the root cause.

### 6.7 On-Call and Incident Management

The alerting pipeline:
```
Prometheus alert → Alertmanager → PagerDuty/OpsGenie → On-call engineer phone
```

**Alertmanager routing** is where alert fatigue is defeated or created. Group related alerts — 50 alerts firing for one root cause should become one page, not fifty. Route by severity: `critical` → page the on-call. `warning` → Slack channel. `info` → dashboard only. Silence during maintenance windows.

**Incident response tools:**
- **PagerDuty:** Industry standard. Escalation policies, schedules, analytics.
- **OpsGenie (Atlassian):** Similar to PagerDuty. Better Jira integration.
- **incident.io:** Modern incident management. Slack-native. Auto-creates channels, tracks timeline, generates postmortems.

**Incident severity levels:**

| Level | Definition | Response |
|---|---|---|
| **SEV1** | Total outage, data loss risk | All hands, war room, 15-min updates |
| **SEV2** | Major feature broken, affecting many users | On-call + escalation, 30-min updates |
| **SEV3** | Minor feature broken, workaround exists | On-call investigates, next business day |
| **SEV4** | Cosmetic, no user impact | Ticket, normal sprint work |

### 6.8 Dashboard Design Principles

A dashboard that nobody uses is worse than no dashboard — it creates false confidence. Good dashboards are designed around decision-making, not data display.

**The USE Method (for infrastructure):**
- **U**tilization: What percentage of the resource is being used? (CPU, memory, disk, network)
- **S**aturation: What work is queued? (run queue length, swap usage, connection queue depth)
- **E**rrors: What error counts and rates? (disk errors, network errors, hardware faults)

**The RED Method (for services):**
- **R**ate: How many requests per second?
- **E**rrors: How many errors per second?
- **D**uration: What's the distribution of request latency?

**The Four Golden Signals (Google SRE):**
1. **Latency:** How long requests take — differentiate successful vs failed (a failing fast is better than a slow success).
2. **Traffic:** Demand on the system — requests/sec, active sessions, transactions per second.
3. **Errors:** Rate of failed requests — both explicit (5xx) and implicit (returning wrong results with 200).
4. **Saturation:** How full the system is — CPU, memory, queue depth, disk I/O. Predict failure before it happens.

**Dashboard hierarchy:**
1. **Executive dashboard:** Overall health. Green/red. SLO burn rate. One screen. For executives and war rooms.
2. **Service dashboard:** RED metrics per service. Top errors. Dependency health. For on-call.
3. **Investigation dashboard:** Detailed metrics, logs, and traces side by side. For debugging a specific incident.

---

## 7. COST MANAGEMENT

### 7.1 Cloud Cost Anatomy

Cloud bills have a way of being surprising. The line items that surprise teams most are rarely compute — they're the invisible taxes on data movement and the costs of components left running between environments.

| Category | % of Typical Bill | Key Drivers |
|---|---|---|
| **Compute** | 40-60% | Instance type, hours running, right-sizing |
| **Storage** | 15-25% | Volume type (gp3 vs io2), snapshots, object storage tier |
| **Network egress** | 10-20% | Cross-AZ traffic, internet egress, CDN origin pulls |
| **Managed services** | 10-20% | RDS, ElastiCache, Elasticsearch, NAT Gateway |
| **API calls** | <5% | S3 GET/PUT, Lambda invocations, API Gateway |

**Hidden costs that surprise teams:**

**Cross-AZ traffic** at $0.01/GB each way sounds trivial. But a chatty microservice architecture where services in AZ-a constantly call services in AZ-b can generate hundreds of terabytes of cross-AZ traffic monthly. Mitigation: service mesh locality-aware routing (prefer targets in the same AZ), and design services to minimize cross-service calls.

**NAT Gateway data processing** at $0.045/GB. Every container image pulled through NAT on every deploy. A 1GB image pulled to 50 nodes = 50GB = $2.25 per deploy. At 10 deploys per day, that's $22.50/day, $675/month, just for container image pulls. Mitigation: VPC Interface Endpoints for ECR and S3.

**Idle load balancers** cost ~$16/month minimum regardless of traffic. Staging environments with their own load balancers add up. Consolidate or use a single ALB with multiple target groups.

**Unattached EBS volumes** persist after instance termination. They accrue storage costs indefinitely. Audit monthly.

**CloudWatch Logs** at $0.50/GB ingested. Verbose debug logging in production is expensive. Structured logging at INFO level in production, DEBUG only when actively debugging.

### 7.2 Cost Optimization Quick Wins

**Right-sizing (biggest single lever):**

Most instances are over-provisioned. Industry data consistently shows that 40%+ of EC2 instances have under 10% average CPU utilization. Engineers provision for peak capacity and never revisit. Use AWS Compute Optimizer (free, checks your usage and recommends downsizes), Datadog resource recommendations, or Kubecost for Kubernetes. Check actual usage over 2 weeks before making changes — some services have weekly or monthly peak patterns.

**Reserved Instances / Savings Plans:**

Commitment discounts are the easiest cost reduction for stable workloads:
- 1-year commitment: ~30% savings vs on-demand.
- 3-year commitment: ~50% savings vs on-demand.
- Savings Plans (AWS): flexible across instance families. Commit to a $/hour spend level, not a specific instance type.
- Convertible Reserved Instances: locked to a specific instance type but can exchange. More flexibility than Standard RIs.
- Rule of thumb: reserve your baseline load, use on-demand for the variable portion.

**Spot/Preemptible Instances:**

60-90% cheaper than on-demand, with one catch: the cloud provider can terminate them with 2 minutes of warning when they need the capacity back. This sounds scary but is very manageable with the right workloads:

Good for: batch processing, CI/CD runners, stateless workers, Kafka consumers (with proper offset management), non-critical async work.

Bad for: databases, anything with local state, single-instance workloads with no failover.

Use mixed instance groups: 70% spot + 30% on-demand. If spot capacity disappears, on-demand picks up the slack automatically.

**Storage tiering:**

| Tier | Cost (S3) | Access | Use Case |
|---|---|---|---|
| **Standard** | $0.023/GB | Frequent | Active data, CDN origins |
| **Infrequent Access** | $0.0125/GB | Monthly | Backups, older logs |
| **Glacier Instant** | $0.004/GB | Quarterly | Compliance archives |
| **Glacier Deep** | $0.00099/GB | Yearly | Legal holds, raw data lake |

**S3 Intelligent-Tiering** automatically moves objects between tiers based on access patterns, for a monitoring fee of $0.0025/1,000 objects. Worth it for any data with unpredictable access patterns.

### 7.3 Tagging Strategy

Tags are the foundation of cost allocation. Without tags, you cannot answer "how much does the payments team's infrastructure cost?" and you cannot hold teams accountable for their spending.

**Mandatory tags (enforce these or you're flying blind):**
```
team: payments
service: payment-api
environment: production
cost-center: CC-1234
managed-by: terraform
```

**Enforcement:**
- AWS Service Control Policies (SCPs): deny resource creation without required tags. Teams cannot create resources without tagging.
- Terraform: `default_tags` block in the provider config applies tags to every resource automatically. Add validation in CI.
- Tag compliance dashboards: weekly audit of untagged resources, with automated email to team leads.

Without enforcement, tags become "something we're supposed to do" and you'll have 40% untagged resources within six months.

### 7.4 FinOps Practices

FinOps stands for Finance + DevOps — the discipline of making cloud spending decisions collaboratively between engineers, finance, and leadership. The engineers who understand the systems also understand the cost levers; finance provides budget context and accountability.

**Core practices:**

**1. Budgets and alerts:** Set monthly budgets per team and per service. Alert at 80%, 100%, and 120%. AWS Budgets and GCP Budget Alerts support this natively.

**2. Anomaly detection:** Automatic detection of spending spikes. AWS Cost Anomaly Detection is free and flags things like "Compute spend jumped 40% today vs your 7-day average." Catch runaway jobs before the end of the month.

**3. Unit economics:** Track cost-per-transaction, cost-per-user, cost-per-API-call. If cost grows linearly with traffic as you scale, you're efficient. If cost grows faster than traffic, you have a scaling problem that needs investigation.

**4. Showback/chargeback:**
- **Showback:** Show teams their costs. No financial consequence. The first step that creates awareness.
- **Chargeback:** Allocate actual cloud costs to team budgets. Creates accountability and incentivizes optimization. Adds process overhead.

**5. Reserved instance planning:** Quarterly review of committed vs actual usage. Unused reservations are pure waste. Undercommitted stable workloads are missed savings.

**Tools:**
- AWS Cost Explorer + Cost and Usage Report (CUR).
- Kubecost (Kubernetes cost allocation by namespace, team, deployment).
- Infracost (Terraform cost estimation in PRs — "this PR will add ~$150/month to your bill"). Engineers see cost impact before it's deployed.
- Vantage, CloudHealth (multi-cloud FinOps platforms for large organizations).

*Real-world:* Spotify runs a FinOps program where each squad sees their cloud costs weekly in their engineering dashboard. By creating visibility and accountability, they reduced cloud spend by 40% through identifying zombie resources, right-sizing instances, and purchasing savings plans — without reducing functionality or headcount. The engineers who build the services are also the ones who optimize their costs. That direct connection is what makes FinOps work.

---

## SYNTHESIS: HOW IT ALL CONNECTS

The seven sections of this chapter are not independent topics. They form a coherent system, and the architecture we walked through in Section 5 only makes sense when you understand why each piece exists.

**Cloud networking** (Section 1) provides the secure, isolated foundation where everything runs. The three-tier VPC layout is not bureaucracy — it's the reason a compromised web server cannot directly reach the database.

**Message queues** (Section 2) decouple services so they can be developed, deployed, and scaled independently. Without Kafka, the Order Service would need to synchronously call every downstream service, and a slow Payment Service call would make every order slow.

**Data flow patterns** (Section 3) — CQRS, CDC, sagas — solve the genuinely hard problems of keeping data consistent across decoupled services. These patterns exist because distributed systems cannot share database transactions, so consistency must be achieved through coordination.

**Database migrations** (Section 4) ensure the data layer evolves safely as the application grows. The expand-and-contract pattern exists because you cannot stop the world to change a schema — old and new code run simultaneously and both must work.

**The complete architecture** (Section 5) shows how all these pieces compose into a working system. Every component has a reason to exist. The Elasticsearch cluster exists because Postgres cannot serve search queries at that latency. The Kafka cluster exists because the Order Service cannot synchronously call eight other services. Debezium exists because dual-writes are unreliable.

**Observability** (Section 6) gives you eyes into the running system. Without Prometheus, you find out about problems from customer support tickets. Without distributed tracing, you spend hours reading logs from ten services to understand one slow request.

**Cost management** (Section 7) ensures the system remains economically sustainable as it scales. The best architecture in the world fails if it's too expensive to run.

The difference between a senior engineer and a staff+ engineer is understanding these connections. Any competent engineer can configure Kafka or write a database migration. A 100x engineer understands *why* the CDC pipeline feeds Elasticsearch instead of querying Postgres directly, *why* the saga compensates in reverse order, *why* the NAT Gateway is consuming 15% of the cloud bill, and *how* a schema migration that looks harmless will lock a table for 20 minutes during peak traffic.

Build the system that works. Observe it rigorously. Understand where it breaks and where it wastes money. Then make it better. That's the loop.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L2-M33: Kafka Deep Dive](../course/modules/loop-2/L2-M33-kafka-deep-dive.md)** — Build TicketPulse's event streaming backbone: topics, partitions, consumer groups, and exactly-once semantics under load
- **[L2-M34: The Saga Pattern](../course/modules/loop-2/L2-M34-the-saga-pattern.md)** — Implement a distributed transaction for ticket purchase with choreography-based compensation on failure
- **[L3-M61: Multi-Region Design](../course/modules/loop-3/L3-M61-multi-region-design.md)** — Deploy TicketPulse across regions and work through the replication lag, failover, and data residency trade-offs in a live system
- **[L3-M82: Event Sourcing at Scale](../course/modules/loop-3/L3-M82-event-sourcing-at-scale.md)** — Replace mutable state with an immutable event log and build projections for TicketPulse's audit and analytics needs

### Quick Exercises

> **No codebase handy?** Try the self-contained version in [Appendix B: Exercise Sandbox](../appendices/appendix-exercise-sandbox.md) — the [Kafka producer/consumer lag exercise](../appendices/appendix-exercise-sandbox.md#exercise-6-kafka--produce-consume-observe-lag) runs a real Kafka cluster in Docker and lets you watch consumer lag grow and shrink in real time.

1. **Draw your system's data flow diagram** — map every service, every database, every queue, and every external dependency. Annotate each arrow with the protocol and whether it is synchronous or asynchronous.
2. **Identify one synchronous call that should be async** — find a request path where the caller blocks waiting for a downstream service that does not need to respond immediately. Sketch what the async version would look like.
3. **Calculate your monthly spend on NAT Gateways and evaluate VPC endpoints** — pull your AWS Cost Explorer data, find the NAT Gateway line, and check whether any of your high-volume traffic to S3 or DynamoDB could use a VPC endpoint instead.

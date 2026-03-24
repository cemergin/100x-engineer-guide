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

How everything connects — from VPC networking to message queues to monitoring, this chapter walks through the complete architecture of a large-scale application showing how 20+ components work together.

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

A Virtual Private Cloud is your isolated network within a cloud provider. Think of it as your own data center's network, but defined in software.

**Core components:**

| Component | Purpose |
|---|---|
| **VPC** | Isolated virtual network with its own CIDR block (e.g., `10.0.0.0/16` = 65,536 IPs) |
| **Subnet** | Partition of a VPC within one Availability Zone. Public or private by routing, not by declaration. |
| **Internet Gateway (IGW)** | Attaches to VPC. Enables inbound/outbound internet traffic for public subnets. |
| **NAT Gateway** | Sits in public subnet. Allows private subnet instances to reach the internet (outbound only). |
| **Route Table** | Rules determining where network traffic is directed. Each subnet associates with exactly one. |

**Public vs private subnets — the real distinction:**
A subnet is "public" if its route table has a route to an Internet Gateway (`0.0.0.0/0 → igw-xxx`). A subnet is "private" if it does not. It is purely a routing decision.

**Standard three-tier VPC layout:**

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

**NAT Gateway cost trap:** NAT Gateways cost ~$0.045/hr (~$32/mo) plus $0.045/GB processed. For high-throughput private subnets pulling container images or calling external APIs, this adds up fast. Mitigation: VPC endpoints for AWS services (S3, ECR, DynamoDB), pull-through caches for container images.

### 1.2 Security Groups vs NACLs

| Feature | Security Group | NACL |
|---|---|---|
| **Level** | Instance (ENI) | Subnet |
| **Statefulness** | **Stateful** — return traffic automatically allowed | **Stateless** — must explicitly allow return traffic |
| **Rules** | Allow only (implicit deny) | Allow and Deny |
| **Evaluation** | All rules evaluated together | Rules evaluated in order (lowest number first) |
| **Default** | Deny all inbound, allow all outbound | Allow all inbound and outbound |

**Layered security model:**
- NACLs = coarse perimeter control (block known bad IP ranges, restrict ports at subnet boundary)
- Security Groups = fine-grained application control (web servers accept 443 only from ALB security group)

**Security group chaining:** Reference other security groups instead of IP ranges. ALB-SG allows 443 from `0.0.0.0/0`. App-SG allows 8080 from ALB-SG. DB-SG allows 5432 from App-SG. This creates an explicit dependency chain that self-documents the architecture.

### 1.3 VPC Peering, Transit Gateway, PrivateLink

**VPC Peering:**
- Direct network connection between two VPCs. Traffic stays on cloud backbone (no internet).
- Non-transitive: If VPC-A peers with VPC-B, and VPC-B peers with VPC-C, A cannot reach C.
- Works cross-account, cross-region. No bandwidth bottleneck (uses cloud backbone).
- Limitation: CIDR blocks must not overlap. Doesn't scale beyond ~20 connections (N*(N-1)/2 problem).

**Transit Gateway:**
- Hub-and-spoke model. Central hub connects all VPCs and on-prem networks.
- Transitive routing: Any spoke can reach any other spoke through the hub.
- Scales to thousands of VPCs. Supports route tables for segmentation.
- *Real-world:* Large orgs with 50+ VPCs, shared services VPC, and on-prem connectivity.

**PrivateLink (VPC Endpoints):**
- Expose a service in one VPC to consumers in other VPCs without peering or Transit Gateway.
- Traffic never leaves the cloud network. Consumer sees it as a private IP in their VPC.
- Two types: **Interface endpoints** (ENI with private IP, most AWS services) and **Gateway endpoints** (S3, DynamoDB only, free).
- *Real-world:* SaaS vendors expose APIs via PrivateLink so customers access them without internet traversal.

**Decision tree:**
- 2-3 VPCs needing full connectivity → VPC Peering
- Many VPCs, hub-and-spoke, on-prem connectivity → Transit Gateway
- Expose one specific service to another VPC → PrivateLink

### 1.4 DNS in the Cloud

**Route 53 / Cloud DNS fundamentals:**

| Record Type | Purpose | Example |
|---|---|---|
| **A** | Domain → IPv4 | `api.example.com → 203.0.113.10` |
| **AAAA** | Domain → IPv6 | `api.example.com → 2001:db8::1` |
| **CNAME** | Alias to another domain | `www.example.com → example.com` |
| **ALIAS/ANAME** | Like CNAME but at zone apex | `example.com → d111.cloudfront.net` |
| **SRV** | Service locator (port + host) | Used by service discovery |
| **TXT** | Verification, SPF, DKIM | `"v=spf1 include:_spf.google.com"` |

**Internal vs external hosted zones:**
- **Public zone:** Resolves from the internet. `api.example.com → public ALB IP`.
- **Private zone:** Resolves only within associated VPCs. `db.internal.example.com → 10.0.5.20`. Never exposed externally.
- Private zones enable service discovery without external DNS exposure. A service calls `orders.internal.example.com` and it resolves to the internal load balancer.

**Routing policies:**
- **Simple:** One record, one answer.
- **Weighted:** Split traffic by percentage (90/10 canary deploys).
- **Latency-based:** Route to the region with lowest latency for the requester.
- **Failover:** Active/passive. Health check fails → route to standby.
- **Geolocation:** Route by requester's geography (compliance, data residency).

### 1.5 Load Balancer Types

| Type | Layer | Protocol | Use Case |
|---|---|---|---|
| **ALB** (Application LB) | L7 | HTTP/HTTPS, gRPC, WebSocket | Path-based routing, host-based routing, microservices |
| **NLB** (Network LB) | L4 | TCP, UDP, TLS | Ultra-low latency, static IPs, millions of requests/sec |
| **GLB** (Gateway LB) | L3 | IP | Inline traffic inspection (firewalls, IDS/IPS) |

**ALB deep dive:**
- Content-based routing: `/api/*` → API target group, `/static/*` → static server target group.
- Host-based routing: `api.example.com` → API, `admin.example.com` → admin service.
- Native auth integration (Cognito, OIDC).
- gRPC support with HTTP/2.
- Slow start mode: gradually increase traffic to new targets.

**NLB deep dive:**
- Handles millions of requests per second with ultra-low latency (~100us at LB).
- Preserves source IP (no X-Forwarded-For needed).
- Static IP per AZ (or attach Elastic IPs). Critical for allowlisting by partners.
- TCP passthrough: TLS termination at the target, not the LB.

**When to choose:**
- Default choice for web apps → **ALB**.
- Need static IPs, extreme performance, non-HTTP protocols → **NLB**.
- NLB in front of ALB: when you need both static IPs and L7 routing.
- Third-party virtual appliances (firewalls) → **GLB**.

### 1.6 CDN Integration

**How CDN + Origin works:**

```
User → Edge Location (CDN) ──cache miss──→ Origin (ALB/S3)
                            ──cache hit──→ Response from edge
```

**CloudFront configuration that matters:**
- **Origin types:** S3 (static assets), ALB (dynamic API), custom origin (any HTTP server).
- **Cache behaviors:** Match URL patterns to origins. `/api/*` → ALB (TTL=0, passthrough). `/*` → S3 (TTL=86400).
- **Origin Access Control (OAC):** S3 bucket only accessible via CloudFront, not directly.
- **Cache key:** By default, URL path. Customize with headers, query strings, cookies.
- **Invalidation:** `/*` invalidates everything. Cost: first 1,000/mo free, $0.005 each after. Prefer versioned filenames (`app.3a7b2c.js`) over invalidation.

**Cloudflare differentiators:**
- Anycast network: every edge location runs every service (CDN, WAF, DDoS, Workers).
- Workers: V8 isolates at the edge. Sub-millisecond cold starts. Cheaper than Lambda@Edge.
- R2: S3-compatible storage with zero egress fees. Eliminates the "CDN origin egress" cost trap.

### 1.7 Multi-Region Networking

**Why multi-region:**
- Latency: users in Asia hitting US-East adds 200-300ms RTT.
- Availability: survive an entire region failure.
- Compliance: data residency laws (GDPR, data sovereignty).

**Multi-region patterns:**

| Pattern | Complexity | RPO/RTO | Cost |
|---|---|---|---|
| **Active-Passive** | Medium | RPO: minutes, RTO: minutes | ~1.5x |
| **Active-Active** | High | RPO: ~0, RTO: ~0 | 2x+ |
| **Read replicas** | Low | N/A (writes to one region) | ~1.3x |

**Active-Active challenges:**
- Data replication: async replication = conflict potential. Sync replication = latency.
- Conflict resolution: last-writer-wins (data loss risk), CRDTs, application-level merge.
- Global tables: DynamoDB global tables handle replication automatically. CockroachDB, Spanner for global SQL.

*Real-world:* Netflix runs active-active across three US regions. If one fails, traffic shifts to the other two within minutes. They built Zuul (gateway) and Eureka (discovery) to support this.

### 1.8 VPN and Direct Connect

**Site-to-Site VPN:**
- IPsec tunnel over the public internet. Encrypted, cost-effective.
- Bandwidth limited by internet connection. Latency varies.
- Setup: minutes to hours. Good for: dev/test, low-bandwidth hybrid, backup connectivity.

**Direct Connect (AWS) / Interconnect (GCP) / ExpressRoute (Azure):**
- Dedicated physical connection to cloud. 1 Gbps or 10 Gbps.
- Consistent latency, no internet dependency. Required for: high-throughput data transfer, latency-sensitive workloads.
- Setup: weeks to months (physical circuit provisioning).
- Cost: port fee + data transfer. Cheaper than internet egress at scale.

**Hybrid architecture:** Direct Connect as primary, VPN as failover. If the physical circuit goes down, traffic automatically routes through VPN.

### 1.9 IP Addressing Strategy

**Planning for growth:**
- Use a large VPC CIDR (`/16` = 65,536 IPs). You can't resize a VPC easily.
- Reserve blocks per environment: `10.0.0.0/16` = production, `10.1.0.0/16` = staging, `10.2.0.0/16` = dev.
- Never overlap CIDRs between VPCs you might need to connect.
- Document allocations in a central IPAM (IP Address Management). AWS offers VPC IPAM.

**Subnet sizing:**
- `/24` (256 IPs, 251 usable) for most subnets.
- `/20` (4,096 IPs) for Kubernetes node subnets (pods consume IPs aggressively with VPC CNI).
- AWS reserves 5 IPs per subnet (first 4 + last 1).

**IPv6:** Dual-stack is the future. AWS gives free `/56` IPv6 blocks. No NAT needed for IPv6 (every address is globally routable, security via security groups).

---

## 2. MESSAGE QUEUES & EVENT-BASED ARCHITECTURE

### 2.1 Message Queue Fundamentals

**Core vocabulary:**

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

```
At-most-once ←────────────────────────→ At-least-once ←──────→ Exactly-once
(may lose msgs)                         (may duplicate)         (expensive/complex)
Fire-and-forget                         Ack after processing    Idempotent consumers
UDP-like                                Most systems default    + transactional writes
```

### 2.2 Queue Types Compared

| System | Model | Ordering | Throughput | Latency | Best For |
|---|---|---|---|---|---|
| **SQS** | Queue | FIFO mode: per-group. Standard: best-effort | ~3,000 msg/s (FIFO), unlimited (standard) | 1-10ms | Simple task queues, decoupling AWS services |
| **RabbitMQ** | Broker (AMQP) | Per-queue FIFO | ~20-50K msg/s | Sub-ms | Complex routing (topic, fanout, headers exchange), RPC |
| **Kafka** | Distributed log | Per-partition | Millions msg/s | 2-10ms | Event streaming, replay, high throughput |
| **NATS** | Lightweight pub/sub | Per-subject (JetStream) | ~10M msg/s | Sub-ms | Cloud-native microservices, edge, IoT |
| **Redis Streams** | Append-only log | Per-stream | ~100K msg/s | Sub-ms | Lightweight streaming when you already run Redis |

**RabbitMQ exchange types explained:**
- **Direct:** Route by exact routing key match. Message with key `order.created` → only queues bound with `order.created`.
- **Topic:** Route by pattern. `order.*` matches `order.created`, `order.shipped`. `#` matches everything.
- **Fanout:** Broadcast to all bound queues. No routing key needed. Classic pub/sub.
- **Headers:** Route by message header attributes instead of routing key.

**Kafka architecture in 60 seconds:**
- Topics split into partitions. Partitions are the unit of parallelism.
- Producers send to a partition (by key hash or round-robin).
- Each partition is an ordered, immutable append-only log.
- Consumer groups: each partition is consumed by exactly one consumer in a group. Add consumers up to partition count for linear scaling.
- Retention: time-based (7 days default) or size-based. Old messages are deleted, not after consumption.
- Replication: each partition has a leader and N-1 followers. ISR (in-sync replicas) for durability.

### 2.3 When to Use Queues

**Decoupling:** Service A publishes event, doesn't know or care who processes it. Deploy, scale, and fail independently.

**Load leveling:** Absorb traffic spikes. 10,000 requests/sec → queue → workers process at 1,000/sec steadily. Queue depth grows temporarily but system doesn't collapse.

**Fan-out:** One event triggers multiple independent actions. Order placed → charge payment, send email, update inventory, notify warehouse. Use SNS → SQS fan-out (each subscriber gets its own queue) or Kafka consumer groups.

**Retry with backoff:** Consumer fails? Message returns to queue. Retry with exponential backoff. After N failures → Dead Letter Queue.

### 2.4 Dead Letter Queues (DLQ)

A DLQ captures messages that repeatedly fail processing. Without a DLQ, poison messages block the queue or get silently dropped.

**Setup pattern:**
```
Main Queue ──→ Consumer (fails) ──→ retry 1 ──→ retry 2 ──→ retry 3 ──→ DLQ
```

**DLQ operational requirements:**
- **Alerting:** DLQ depth > 0 should trigger an alert. A growing DLQ is a production incident.
- **Inspection tooling:** Engineers need to read DLQ messages, understand why they failed, fix the bug, and replay them.
- **Replay mechanism:** After fixing the consumer bug, redrive messages from DLQ back to the main queue. SQS has built-in DLQ redrive.
- **Retention:** DLQ should have longer retention than the main queue (14 days vs 4 days).

**Poison message patterns:**
- Malformed data → fix producer or add validation.
- Schema mismatch → version your schemas (see 2.7).
- Downstream dependency down → retry with exponential backoff; DLQ only after persistent failure.
- Message too large → reject at producer side. Store payload in S3, send reference in message.

### 2.5 Ordering Guarantees

**No ordering (SQS Standard):** Messages may arrive out of order. Cheapest, highest throughput. Fine when processing is idempotent and order-independent.

**Per-group ordering (SQS FIFO, Kafka partitions):**
- Messages with the same group/partition key are ordered.
- Different keys processed in parallel.
- *Example:* All events for `order-123` are ordered. Events for `order-456` may interleave. Use the entity ID as partition key.

**Global ordering:** All messages in strict order. Requires single partition/queue. Kills parallelism. Almost never needed. If you think you need it, you probably need per-entity ordering instead.

**Kafka ordering guarantee:**
- Within a partition: strictly ordered.
- Across partitions: no ordering guarantee.
- Choose partition key wisely: `customer_id` means all events for a customer are ordered. `order_id` means all events for an order are ordered.
- Gotcha: changing partition count re-hashes keys. Existing ordering guarantees break during repartitioning.

### 2.6 Event-Based Architecture Patterns

**Pattern 1 — Event Notification:**
An event simply notifies that something happened. Minimal data. Consumer must call back for details.
```
{ "event": "order.placed", "order_id": "ord-123", "timestamp": "..." }
```
Consumer calls Order Service API to get full order details. Simple, but creates coupling and increases load on the source.

**Pattern 2 — Event-Carried State Transfer:**
Event contains all the data the consumer needs. No callback required.
```
{
  "event": "order.placed",
  "order_id": "ord-123",
  "customer": { "id": "cust-456", "email": "..." },
  "items": [ { "sku": "...", "qty": 2, "price": 29.99 } ],
  "total": 59.98
}
```
Consumers are fully decoupled. Trade-off: larger messages, potential data staleness, schema coupling.

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

**Event sourcing trade-offs:**
- Complete audit trail. Time-travel queries. Rebuild state from any point.
- Complexity: eventual consistency, snapshots needed for performance, event schema evolution is hard.
- *Real-world:* Accounting systems, banking (ledger is naturally event-sourced), Greg Young's original domain.

### 2.7 Event Schema Evolution

Schemas change over time. Producers and consumers evolve independently. Breaking changes = production outages.

**Schema evolution strategies:**

| Strategy | Tool | Wire Format | Schema Registry |
|---|---|---|---|
| **Avro + Schema Registry** | Confluent Schema Registry | Binary, compact | Yes, enforces compatibility |
| **Protobuf** | buf, protoc | Binary, compact | Optional (buf registry) |
| **JSON Schema** | JSON Schema validators | JSON, verbose | Optional |

**Avro compatibility modes:**
- **Backward compatible:** New schema can read old data. (Add fields with defaults, remove optional fields.)
- **Forward compatible:** Old schema can read new data. (Remove fields, add optional fields.)
- **Full compatible:** Both backward and forward. The gold standard.

**Rules for safe schema evolution:**
1. Adding a field → always include a default value.
2. Removing a field → stop reading it first, then remove.
3. Renaming a field → add new field, deprecate old, remove old after all consumers migrate.
4. Changing a field type → never. Add a new field instead.

### 2.8 Idempotency and Exactly-Once Processing

True exactly-once delivery is impossible in distributed systems. What we actually implement is **effectively exactly-once** = at-least-once delivery + idempotent processing.

**Idempotency patterns:**

1. **Idempotency key:** Producer assigns a unique ID. Consumer checks "have I processed this ID?" before acting.
```sql
-- Before processing:
INSERT INTO processed_events (event_id) VALUES ('evt-123')
  ON CONFLICT DO NOTHING;
-- If inserted (affected rows = 1): process the event
-- If conflict (affected rows = 0): skip (already processed)
```

2. **Natural idempotency:** Operations that are inherently idempotent. `SET balance = 850` is idempotent. `ADD 50 to balance` is not. Design state mutations as absolute values when possible.

3. **Kafka exactly-once semantics (EOS):**
   - Producer: `enable.idempotence=true` deduplicates at the broker (sequence numbers per partition).
   - Transactional producer + consumer: `read_committed` isolation. Atomic produce-and-commit-offset.
   - Cost: ~20% throughput reduction. Use only when needed (financial transactions).

### 2.9 Real-World Architecture: Order Processing Pipeline

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

**Key design decisions:**
- Kafka topic per event type: `order.created`, `payment.completed`, `inventory.reserved`, `order.shipped`.
- Partition key: `order_id` — all events for one order are ordered.
- Each service has its own consumer group — independent processing at independent speeds.
- DLQ per service — payment failures don't block inventory processing.
- Idempotency key: `order_id + event_type` — safe to retry any event.

*Real-world:* Shopify processes billions of events through a Kafka-based pipeline. They migrated from a monolithic Rails app to event-driven services, using Kafka as the backbone for order processing, inventory, and payments.

---

## 3. DATA FLOW & PIPELINE ARCHITECTURE

### 3.1 How Data Flows Through a Modern Application

**The complete request lifecycle:**

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

**The background processing lifecycle:**

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

### 3.2 Synchronous vs Asynchronous Data Flow

**Use synchronous when:**
- User is waiting for a response (page load, form submission, API call).
- Operation is fast (<500ms).
- You need the result to continue (payment authorization before showing confirmation).
- Simplicity matters more than throughput.

**Use asynchronous when:**
- User doesn't need an immediate result (email sending, report generation, image processing).
- Operation is slow (>1s) or unreliable (external API calls).
- You need to decouple producer from consumer (different teams, different scaling needs).
- Traffic is bursty (absorb spikes with a queue).

**The hybrid pattern (accept-and-process-later):**
```
Client ──→ POST /orders ──→ API validates, writes to DB, publishes event
                          ──→ Returns 202 Accepted { "order_id": "ord-123", "status": "processing" }

Background: Event → Payment → Inventory → Shipping → Update order status

Client ──→ GET /orders/ord-123 ──→ { "status": "shipped" }  (polling)
   or
Client ──→ WebSocket ──→ receives status updates in real-time
```

### 3.3 Fan-Out Patterns

**SNS + SQS Fan-Out (AWS):**
One event → SNS topic → multiple SQS queues → independent consumers.
```
Order Placed ──→ SNS Topic ──→ SQS (payment processing)
                            ──→ SQS (inventory update)
                            ──→ SQS (email notification)
                            ──→ SQS (analytics ingestion)
```
Each queue has independent retry, DLQ, and scaling. If email service is down, payment processing is unaffected.

**Kafka Fan-Out:**
One topic → multiple consumer groups. Same event, different consumers.
```
order.placed topic
    ├──→ Consumer Group: payment-service (reads all partitions)
    ├──→ Consumer Group: inventory-service (reads all partitions)
    ├──→ Consumer Group: notification-service (reads all partitions)
    └──→ Consumer Group: analytics-pipeline (reads all partitions)
```

**Key difference:** SNS+SQS duplicates the message per queue. Kafka stores once, each group tracks its own offset. Kafka is more efficient at scale; SNS+SQS is simpler for AWS-native architectures.

### 3.4 Saga Pattern for Distributed Transactions

**The problem:** You need to update data across multiple services atomically. Distributed transactions (2PC) are slow and brittle. Sagas provide eventual consistency without distributed locks.

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
2. Compensating actions must be idempotent (they may run multiple times).
3. Compensating actions cannot fail permanently (use retry with manual intervention as last resort).
4. Order of compensation is reverse of execution.

### 3.5 CQRS in Practice

**Command Query Responsibility Segregation:** Use different models (and often different stores) for reads and writes.

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
- Read and write patterns are drastically different (e.g., 1000:1 read:write ratio with complex queries).
- Read model needs different structure (denormalized for fast retrieval, search-optimized).
- Write model needs strong consistency; read model tolerates staleness.

**When CQRS is overkill:**
- Simple CRUD applications.
- Read and write models are nearly identical.
- Your team cannot handle the eventual consistency complexity.

*Real-world:* Uber uses CQRS for their driver matching system. Writes (driver location updates) go to a fast write store. Reads (find nearest drivers) go to a geospatial index optimized for proximity queries.

### 3.6 Change Data Capture (CDC) Pipelines

**CDC captures every change in a database and streams it as events.** Instead of application code publishing events (dual-write problem), CDC reads the database's transaction log.

**The dual-write problem CDC solves:**
```
# BAD: dual write — what if step 2 fails?
def place_order(order):
    db.insert(order)          # Step 1: write to DB
    kafka.publish(order)      # Step 2: publish event — network error? event lost.

# GOOD: CDC — database is the single source of truth
def place_order(order):
    db.insert(order)          # Only write to DB
# Debezium reads the WAL/binlog and publishes to Kafka automatically
```

**Debezium → Kafka → Elasticsearch pipeline:**
```
PostgreSQL (WAL) ──→ Debezium Connector ──→ Kafka ──→ Elasticsearch Sink Connector
                     (Kafka Connect)                   (Kafka Connect)
```

**CDC use cases:**
- Replicate data to search indices (Postgres → Elasticsearch).
- Feed data warehouses in real-time (OLTP → Kafka → Snowflake).
- Sync caches (DB change → invalidate/update Redis).
- Audit log (every change captured automatically).
- Migrate between databases (old DB → CDC → new DB).

### 3.7 Data Warehouse Feeding

**Real-time ingestion (streaming):**
```
Application DB ──→ CDC (Debezium) ──→ Kafka ──→ Flink/ksqlDB ──→ Data Warehouse
```
Latency: seconds to minutes. Use when: dashboards need near-real-time data, fraud detection, real-time recommendations.

**Batch ingestion:**
```
Application DB ──→ Scheduled ETL (Airflow) ──→ Transform (dbt) ──→ Data Warehouse
```
Latency: hours. Use when: daily reports, historical analysis, cost-sensitive (batch is cheaper).

**Modern lakehouse pattern:**
```
Sources ──→ Kafka ──→ Object Storage (S3/GCS) in Parquet/Iceberg ──→ Query Engine (Spark/Trino)
```
Store everything cheaply in object storage with open formats. Query with any engine. Avoid vendor lock-in.

### 3.8 Workflow Orchestration

| Tool | Type | Language | Strengths |
|---|---|---|---|
| **Temporal** | Durable execution | Go, Java, Python, TS | Code-first, fault-tolerant, long-running workflows |
| **Apache Airflow** | DAG scheduler | Python | Data pipeline standard, massive operator library |
| **AWS Step Functions** | State machine | JSON/ASL | Serverless, AWS-native, visual designer |
| **Prefect** | DAG scheduler | Python | Modern Airflow alternative, better DX |
| **Dagster** | Asset-based | Python | Software-defined assets, data-aware orchestration |

**Temporal deep dive:**
- Workflows survive process crashes, server restarts, even datacenter failures. The runtime persists workflow state.
- Activities: side-effecting operations (API calls, DB writes). Automatically retried on failure.
- Signals: external events injected into a running workflow. Timers: durable sleep (sleep 30 days — server can restart, timer still fires).
- *Real-world:* Stripe uses Temporal for payment orchestration. Snap uses it for content moderation pipelines.

**Airflow deep dive:**
- DAGs (Directed Acyclic Graphs) define task dependencies.
- Operators: `PythonOperator`, `BashOperator`, `PostgresOperator`, `S3ToRedshiftOperator`, etc.
- Scheduler: determines when and what to run. Executor: determines where (local, Celery, Kubernetes).
- Pitfall: don't put heavy processing in the DAG definition file. It runs on the scheduler, not the worker.

---

## 4. DATABASE MIGRATIONS

### 4.1 Schema Migration Tools

| Tool | Language | Approach | Key Feature |
|---|---|---|---|
| **Flyway** | Java (any DB) | Versioned SQL files (`V1__create_users.sql`) | Simple, convention-based |
| **Liquibase** | Java (any DB) | XML/YAML/JSON/SQL changesets | Rollback generation, diff |
| **Alembic** | Python (SQLAlchemy) | Python migration scripts | Auto-generates from model changes |
| **Prisma Migrate** | TypeScript | Declarative schema → SQL migrations | Schema-first, great DX |
| **golang-migrate** | Go | Numbered SQL files (up/down) | Lightweight, CLI-driven |
| **Knex** | JavaScript | JS migration files | Part of the Knex query builder ecosystem |

**All tools share the same core model:** A sequence of numbered/timestamped migration files, applied in order, tracked in a schema_migrations table, never modified after deployment.

### 4.2 Zero-Downtime Migration Strategies

The fundamental constraint: during deployment, **both old and new application code run simultaneously**. Any migration must be compatible with both versions.

#### Expand-and-Contract Pattern

The universal strategy for safe schema changes. Two phases:

**Expand phase (additive, backward-compatible):**
- Add new columns, tables, indexes.
- Old code ignores new columns. New code uses them.
- Deploy new application code that writes to both old and new locations.

**Contract phase (remove old, after all code is updated):**
- Remove old columns, tables, deprecated fields.
- Only after confirming no code reads/writes the old structure.

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

**Critical: backfill in batches.** A single `UPDATE orders SET ...` on a 100M row table holds a lock for minutes and kills your database.

#### Dropping Columns

**Never drop a column in the same deploy that stops reading it.** Old code instances still running will crash.

```
Deploy 1: Stop reading the column. Stop writing to it.
Deploy 2: (after all old instances are gone) DROP COLUMN.
```

In practice, use a "column ignore" list in your ORM or add the column to a deprecation config.

#### Renaming Columns

Renaming is effectively add + backfill + migrate code + drop:

```sql
-- Step 1: Add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);

-- Step 2: Backfill
UPDATE users SET full_name = name WHERE id BETWEEN ... AND ...;

-- Step 3: Deploy code that writes to BOTH name and full_name, reads from full_name
-- Step 4: After all old code is gone, drop old column
ALTER TABLE users DROP COLUMN name;
```

#### Adding Indexes Concurrently

Standard `CREATE INDEX` locks the table for writes. On a large table, this means downtime.

```sql
-- PostgreSQL: CONCURRENTLY doesn't lock the table
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders(customer_id);

-- Caveat: CONCURRENTLY can't run inside a transaction.
-- If it fails partway, you get an INVALID index. Check and retry:
-- SELECT * FROM pg_indexes WHERE indexdef LIKE '%INVALID%';
```

**MySQL equivalent:** `ALTER TABLE ... ADD INDEX` is online by default in InnoDB (MySQL 5.6+), but may still require a table copy for some operations.

#### Large Table Migrations

For tables with billions of rows, even `ALTER TABLE ... ADD COLUMN` can be problematic.

**Tools for MySQL:**
- **gh-ost** (GitHub): Creates a ghost table, copies data incrementally using binlog, then swaps atomically. No triggers. Pausable, throttleable.
- **pt-online-schema-change** (Percona): Similar approach using triggers to capture changes during copy.

**Tools for PostgreSQL:**
- **pg_repack:** Reorganizes tables online without heavy locks. Useful for reclaiming bloat.
- Most `ALTER TABLE ADD COLUMN` with a default is instant in Postgres 11+ (stores default in catalog, doesn't rewrite table).

### 4.3 Data Migrations vs Schema Migrations

**Schema migrations** change the structure: add tables, columns, indexes, constraints.
**Data migrations** change the content: backfill values, transform data formats, merge duplicates.

**Keep them separate:**
- Schema migrations are fast and deterministic.
- Data migrations can be slow, may need to run in batches, may need to be idempotent.
- Run data migrations as background jobs, not as part of the deploy pipeline.
- A blocked data migration should never block a rollback.

### 4.4 Rollback Strategies

**Backward-compatible migrations (preferred):**
Every migration is forward-only but backward-compatible. Old code works with the new schema. If the deploy fails, roll back the code, not the schema.

**Down migrations (traditional):**
Every migration file has an `up` and `down`. `down` reverses the `up`. Problem: data-destructive `down` migrations (dropping a column you just added is fine; re-adding a column you just dropped loses data).

**Practical approach:**
1. Write migrations that are always backward-compatible.
2. Never write `down` migrations for production. They're useful for development only.
3. If a migration is truly wrong, write a new forward migration to fix it.

### 4.5 Multi-Service Migration Coordination

When multiple services share dependencies on a schema (even indirectly through events):

1. **Schema changes must be backward-compatible** — you cannot coordinate deploys across N services atomically.
2. **Version your event schemas** — a schema change that affects events needs schema registry compatibility checks.
3. **Expand-contract across services:** Deploy producing service with new schema first. Deploy consuming services to handle both old and new. Remove old format.
4. **Feature flags:** Gate new behavior behind flags. Enable per-service after confirming compatibility.

### 4.6 Database Branching

**Neon (Postgres):** Copy-on-write branching. Create a full copy of your database in seconds, regardless of size. Each branch is an independent Postgres instance. Perfect for: preview environments per PR, testing migrations against production data.

**PlanetScale (MySQL):** Git-like branching for schemas. Create a branch, make schema changes, open a "deploy request" (like a PR). PlanetScale diffs the schema, shows impact, and deploys with zero downtime. Non-blocking schema changes built-in.

**The workflow:**
```
main (production DB)
    │
    ├── branch: feature-add-shipping (schema changes + test data)
    │       └── PR preview environment uses this branch
    │
    └── merge: schema changes applied to main via deploy request
```

---

## 5. HOW A LARGE-SCALE APP COMES TOGETHER

### 5.1 Complete Architecture — E-Commerce Platform

The following shows how every component connects in a real-world e-commerce platform serving millions of users.

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

**Step-by-step through every layer:**

1. **DNS:** User types `shop.example.com`. Route 53 returns CloudFront distribution IP (latency-based routing picks closest edge).

2. **CDN:** CloudFront serves cached product images, JS bundles, CSS. API requests (`/api/*`) pass through to origin.

3. **WAF:** AWS WAF inspects the request. Blocks known attack patterns (SQL injection, XSS). Rate limits by IP.

4. **Load Balancer:** ALB terminates TLS. Routes `/api/orders/*` → Order Service target group. Health checks remove unhealthy instances.

5. **API Gateway:** Validates JWT token (from Auth0/Cognito). Extracts user identity. Rate limits per-user. Logs the request.

6. **Order Service:** Validates order data. Checks inventory (sync call to Product Catalog). Writes order to Postgres. Publishes `order.created` to Kafka. Returns `202 Accepted`.

7. **Kafka:** `order.created` event consumed by Payment Service, Inventory Service, Notification Service (separate consumer groups).

8. **Payment Service:** Calls Stripe API. On success, publishes `payment.completed`. On failure, publishes `payment.failed` (triggers saga compensation).

9. **Cache:** Product catalog data cached in Redis (TTL 5 min). Cache-aside pattern: check Redis first, miss → query Postgres → populate Redis.

10. **Response:** Order confirmation returned to client. WebSocket connection pushes real-time status updates as each downstream service completes.

### 5.3 Background Processing Flow

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

**Failure handling:**
- Payment fails → saga compensates: cancel order, release inventory.
- Inventory insufficient → saga compensates: refund payment, notify customer.
- Email fails → goes to DLQ. Alert. Manual replay after fix. Order still valid.
- Analytics fails → Kafka retains events. Consumer resumes from last committed offset.

### 5.4 Real-Time Features

```
Client ──WebSocket──→ WebSocket Server (Node.js/Go)
                           │
                           ├──subscribe──→ Redis Pub/Sub (channel: order:ord-123)
                           │
                           │  Order Service publishes status update to Redis
                           │
                           └──push──→ Client receives: { "status": "shipped" }
```

**Scaling WebSockets:**
- Each WebSocket server handles 10K-100K concurrent connections.
- Redis Pub/Sub ensures a status update published from any app server reaches the correct WebSocket server.
- Alternative: Kafka → WebSocket adapter for higher throughput. Or managed services (Ably, Pusher, AWS AppSync).

### 5.5 Search Pipeline

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

**Why not query Postgres directly?** Full-text search, faceted filtering, fuzzy matching, relevance scoring, and sub-100ms response times on millions of products. Elasticsearch is purpose-built for this.

**Consistency:** There is a delay (typically <1s) between a product update in Postgres and its appearance in Elasticsearch. Acceptable for search. For the product detail page, read from Postgres directly.

### 5.6 Analytics Pipeline

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

**Event taxonomy matters:** Define a schema for analytics events early. `event_name`, `timestamp`, `user_id`, `session_id`, `properties` (JSON). Use a schema registry. Garbage in = garbage out.

### 5.7 Auth Flow

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
- Access token: short-lived (15 min). Stateless verification (no DB call).
- Refresh token: long-lived (7-30 days). Stored securely (httpOnly cookie). Used to get new access tokens.
- Token revocation: maintain a blocklist in Redis (check on each request) or rely on short access token TTL.

### 5.8 Deployment Pipeline

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

**Key details:**
- Container images tagged with git SHA (immutable, traceable).
- Database migrations run before new code deploys (expand phase). Contract phase in a separate follow-up.
- Canary deploys: route 5% of traffic to new version. Compare error rate and p99 latency against baseline. Auto-rollback if degraded.
- Feature flags (LaunchDarkly, Unleash): decouple deploy from release. Deploy dark, enable for 1% of users, ramp to 100%.

---

## 6. MONITORING & OBSERVABILITY IN PRACTICE

### 6.1 The Three Pillars

| Pillar | What | Tool (Open Source) | Tool (Commercial) |
|---|---|---|---|
| **Metrics** | Numeric measurements over time | Prometheus + Grafana | Datadog, New Relic |
| **Logs** | Discrete events with context | Loki + Grafana / ELK | Datadog Logs, Splunk |
| **Traces** | Request flow across services | Jaeger / Tempo + OTel | Datadog APM, Honeycomb |

### 6.2 Metrics: Prometheus + Grafana

**How Prometheus works:**
- Pull-based: Prometheus scrapes `/metrics` endpoints on your services every 15-30s.
- Time-series database: stores `metric_name{label=value} value timestamp`.
- PromQL for querying and alerting.

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

**ELK Stack (Elasticsearch + Logstash + Kibana):**
- Full-text indexing of every log line. Powerful queries. Expensive: stores and indexes everything.
- Logstash: parse, transform, route logs. Alternatives: Fluentd, Fluent Bit (lighter).
- Best for: organizations that need complex log analysis, regex searches across millions of lines.

**Loki + Grafana:**
- Stores only labels (indexed) + raw log lines (not indexed). Orders of magnitude cheaper.
- Query by labels first, then grep through matching streams. LogQL query language.
- Best for: cost-conscious orgs, teams already using Grafana, when most log queries are "show me logs for service X in the last hour."

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
Key fields: `timestamp`, `level`, `service`, `trace_id` (correlate with traces), `request_id`, business-relevant IDs. Never log PII (emails, passwords, credit cards).

### 6.4 Tracing: OpenTelemetry + Jaeger/Tempo

**Distributed tracing** shows the path of a single request across all services it touches.

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

**OpenTelemetry (OTel):** The vendor-neutral standard. Instrument once, export to any backend.

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
- **Honeycomb:** SaaS, exceptional query UX for exploring high-cardinality data.

### 6.5 APM: When to Use Commercial vs Open Source

**Open source (Prometheus + Grafana + Loki + Tempo):**
- Full control. No per-host/per-GB pricing. Requires operational expertise to run.
- Good for: teams with platform engineering capacity, cost-sensitive orgs, data privacy requirements.

**Commercial (Datadog, New Relic, Dynatrace):**
- Unified platform: metrics, logs, traces, APM, RUM, synthetics, security, profiling.
- Expensive at scale. Datadog bills per host + per GB ingested. Costs can surprise you.
- Good for: teams without dedicated platform engineering, when time-to-value matters, when correlation across signals is critical.

**Decision framework:**
- <50 services, strong platform team → open source.
- >50 services, need fast onboarding → commercial.
- Hybrid: Prometheus for metrics (free, pull-based), commercial for traces and APM (higher value per dollar).

*Real-world cost trap:* A 200-node Kubernetes cluster with Datadog can cost $50K-$200K/year depending on features. Budget this early.

### 6.6 Uptime Monitoring

**Synthetic checks:** External probes that hit your endpoints from multiple locations every 30-60s.
- Tools: Checkly, Pingdom, UptimeRobot, AWS CloudWatch Synthetics.
- Check: HTTP status, response body contains expected content, response time < threshold.
- Alert if: 2+ consecutive failures from 2+ locations (avoid false positives from one flaky probe).

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

**Status pages:** Public communication during incidents. Atlassian Statuspage, Instatus, or self-hosted. Update proactively — customers trust transparency.

### 6.7 On-Call and Incident Management

**Alerting pipeline:**
```
Prometheus alert → Alertmanager → PagerDuty/OpsGenie → On-call engineer phone
```

**Alertmanager routing:**
- Group related alerts (avoid alert storms — 50 alerts for one root cause).
- Route by severity: `critical` → page. `warning` → Slack channel. `info` → dashboard only.
- Silence during maintenance windows.

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

**The USE Method (for infrastructure):**
- **U**tilization: % of resource being used (CPU, memory, disk, network).
- **S**aturation: Work that is queued (run queue length, swap usage).
- **E**rrors: Error counts and rates.

**The RED Method (for services):**
- **R**ate: Requests per second.
- **E**rrors: Errors per second.
- **D**uration: Distribution of request latency.

**The Four Golden Signals (Google SRE):**
1. **Latency:** How long requests take (differentiate successful vs failed).
2. **Traffic:** Demand on the system (requests/sec, sessions, transactions).
3. **Errors:** Rate of failed requests (explicit 5xx, implicit wrong results).
4. **Saturation:** How full the system is (CPU, memory, queue depth, disk I/O).

**Dashboard hierarchy:**
1. **Executive dashboard:** Overall health. Green/red. SLO burn rate. One screen.
2. **Service dashboard:** RED metrics per service. Top errors. Dependency health.
3. **Investigation dashboard:** Detailed metrics, logs, and traces. For debugging, not monitoring.

---

## 7. COST MANAGEMENT

### 7.1 Cloud Cost Anatomy

| Category | % of Typical Bill | Key Drivers |
|---|---|---|
| **Compute** | 40-60% | Instance type, hours running, right-sizing |
| **Storage** | 15-25% | Volume type (gp3 vs io2), snapshots, object storage tier |
| **Network egress** | 10-20% | Cross-AZ traffic, internet egress, CDN origin pulls |
| **Managed services** | 10-20% | RDS, ElastiCache, Elasticsearch, NAT Gateway |
| **API calls** | <5% | S3 GET/PUT, Lambda invocations, API Gateway |

**Hidden costs that surprise teams:**
- **Cross-AZ traffic:** $0.01/GB each way. A chatty microservice architecture across AZs adds up. Mitigation: service mesh locality-aware routing, keep communication within AZ when possible.
- **NAT Gateway data processing:** $0.045/GB. Container images pulled through NAT on every deploy. Mitigation: VPC endpoints for ECR, S3.
- **Idle load balancers:** ALB minimum ~$16/mo even with zero traffic. Consolidate environments.
- **Unattached EBS volumes:** Persist after instance termination. Audit monthly.
- **CloudWatch Logs:** $0.50/GB ingested. Verbose debug logging in production is expensive.

### 7.2 Cost Optimization Quick Wins

**Right-sizing (biggest single lever):**
- Most instances are over-provisioned. 40% of EC2 instances have <10% average CPU utilization.
- Use AWS Compute Optimizer, Datadog resource recommendations, or Kubecost for K8s.
- Check actual usage over 2 weeks before downsizing.

**Reserved Instances / Savings Plans:**
- 1-year commitment: ~30% savings. 3-year: ~50% savings.
- Savings Plans (AWS): flexible across instance families. Commit to $/hour spend.
- Reserved Instances: locked to specific instance type (convertible RIs are more flexible).
- Rule of thumb: reserve your baseline, use on-demand for the variable portion.

**Spot/Preemptible Instances:**
- 60-90% cheaper than on-demand. Can be terminated with 2-min warning.
- Good for: batch processing, CI/CD runners, stateless workers, Kafka consumers (with proper offset management).
- Bad for: databases, stateful services, single-instance workloads.
- Use mixed instance groups: 70% spot + 30% on-demand for resilience.

**Storage tiering:**

| Tier | Cost (S3) | Access | Use Case |
|---|---|---|---|
| **Standard** | $0.023/GB | Frequent | Active data, CDN origins |
| **Infrequent Access** | $0.0125/GB | Monthly | Backups, older logs |
| **Glacier Instant** | $0.004/GB | Quarterly | Compliance archives |
| **Glacier Deep** | $0.00099/GB | Yearly | Legal holds, raw data lake |

**S3 Intelligent-Tiering:** Automatically moves objects between tiers based on access patterns. $0.0025/1000 objects monitoring fee. Worth it for data with unpredictable access patterns.

### 7.3 Tagging Strategy

Tags are the foundation of cost allocation. Without tags, you cannot answer "how much does team X's service cost?"

**Mandatory tags:**
```
team: payments
service: payment-api
environment: production
cost-center: CC-1234
managed-by: terraform
```

**Enforcement:**
- AWS Service Control Policies (SCPs): deny resource creation without required tags.
- Terraform: `default_tags` block in provider config. Validation in CI.
- Tag compliance dashboards: weekly audit of untagged resources.

### 7.4 FinOps Practices

**FinOps = Finance + DevOps.** Engineers, finance, and leadership collaborate on cloud spending decisions.

**Core practices:**

1. **Budgets and alerts:** Set monthly budgets per team/service. Alert at 80%, 100%, 120%. AWS Budgets, GCP Budget Alerts.

2. **Anomaly detection:** Automatic detection of spending spikes. AWS Cost Anomaly Detection (free). Flag: "Compute spend jumped 40% today vs 7-day average."

3. **Unit economics:** Track cost-per-transaction, cost-per-user, cost-per-API-call. If cost grows linearly with traffic, you're efficient. If cost grows faster, investigate.

4. **Showback/chargeback:**
   - **Showback:** Show teams their costs. No financial consequence. First step.
   - **Chargeback:** Allocate actual cloud costs to team budgets. Creates accountability but adds process overhead.

5. **Reserved instance planning:** Quarterly review of committed vs actual usage. Unused reservations are waste. Undercommitted workloads are missed savings.

**Tools:**
- AWS Cost Explorer + Cost and Usage Report (CUR).
- Kubecost (Kubernetes cost allocation).
- Infracost (Terraform cost estimation in PRs — "this PR will cost ~$150/mo").
- Vantage, CloudHealth (multi-cloud FinOps platforms).

*Real-world:* Spotify runs a FinOps program where each squad sees their cloud costs weekly. They reduced cloud spend by 40% by identifying zombie resources, right-sizing, and purchasing savings plans — without reducing functionality.

---

## SYNTHESIS: HOW IT ALL CONNECTS

The seven sections of this chapter are not independent topics. They form a coherent system:

1. **Cloud networking** provides the secure, isolated foundation where everything runs.
2. **Message queues** decouple services so they can be developed, deployed, and scaled independently.
3. **Data flow patterns** (CQRS, CDC, sagas) solve the hard problems of keeping data consistent across decoupled services.
4. **Database migrations** ensure the data layer evolves safely as the application grows.
5. **The complete architecture** shows how all these pieces compose into a working system — from the user's click to the warehouse dashboard.
6. **Observability** gives you eyes into the running system — without it, you're flying blind.
7. **Cost management** ensures the system remains economically sustainable as it scales.

The difference between a senior engineer and a staff+ engineer is understanding these connections. Any competent engineer can set up Kafka or write a database migration. A 100x engineer understands *why* the CDC pipeline feeds Elasticsearch instead of querying Postgres directly, *why* the saga compensates in reverse order, *why* the NAT Gateway is eating 15% of the cloud bill, and *how* a schema migration that looks harmless will lock a table for 20 minutes during peak traffic.

Build the system that works. Observe it. Understand where it breaks and where it wastes money. Then make it better.

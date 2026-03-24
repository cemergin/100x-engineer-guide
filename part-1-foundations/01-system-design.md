<!--
  CHAPTER: 1
  TITLE: System Design Paradigms & Philosophies
  PART: I — Foundations
  PREREQS: None
  KEY_TOPICS: CAP theorem, PACELC, consistency models, Paxos, Raft, distributed transactions, CRDTs, sharding, load balancing, auto-scaling, capacity planning
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 1: System Design Paradigms & Philosophies

> **Part I — Foundations** | Prerequisites: None | Difficulty: Advanced

The foundational theory of distributed systems — how data stays consistent, how systems scale, and how to design for failure. Every other chapter builds on these concepts.

### In This Chapter
- Distributed Systems Fundamentals
- Scalability Patterns
- System Design Principles
- High Availability & Fault Tolerance
- Key Philosophies

### Related Chapters
- [Ch 2: Data Engineering Paradigms] — data engineering builds on consistency models
- [Ch 3: Software Architecture Patterns] — architecture patterns apply these concepts
- [Ch 4: Reliability Engineering & Operations] — reliability operationalizes these designs

---

## 1. DISTRIBUTED SYSTEMS FUNDAMENTALS

### 1.1 CAP Theorem (Brewer's Theorem)

**What it is:** In any distributed data store, you can only guarantee two of three properties simultaneously:

- **Consistency (C):** Every read receives the most recent write or an error. All nodes see the same data at the same time.
- **Availability (A):** Every request receives a non-error response, without guarantee that it contains the most recent write.
- **Partition Tolerance (P):** The system continues to operate despite arbitrary message loss or failure of part of the network.

**The critical insight:** Partition tolerance is not optional in a distributed system. Network partitions *will* happen. The real choice is between **CP** and **AP** during a partition event.

- **CP systems** (e.g., ZooKeeper, etcd, HBase, MongoDB with majority write concern): During a partition, the system may refuse requests on the minority side to maintain consistency. Use when correctness is non-negotiable: financial ledgers, distributed locks, configuration management.
- **AP systems** (e.g., Cassandra, DynamoDB, CouchDB, Riak): During a partition, every node continues serving requests, but reads may return stale data. Use when availability matters more than immediate consistency: shopping carts, social media feeds, DNS.

**Trade-offs:** CAP is often misunderstood as a static, binary choice. In practice, systems operate on a spectrum. You can tune consistency *per-operation* (e.g., Cassandra's tunable consistency levels: ONE, QUORUM, ALL). CAP also says nothing about latency, which leads us to PACELC.

### 1.2 PACELC Theorem

**What it is:** An extension of CAP that addresses system behavior when there is *no* partition. The formulation:

> If there is a **P**artition, choose between **A**vailability and **C**onsistency; **E**lse (normal operation), choose between **L**atency and **C**onsistency.

This is more practical than CAP because partitions are rare. Most of the time, the real trade-off is latency vs. consistency.

| System | During Partition (PAC) | Normal Operation (ELC) |
|---|---|---|
| DynamoDB | PA | EL (low latency, eventual consistency) |
| Cassandra | PA | EL |
| MongoDB | PC | EC |
| PNUTS (Yahoo) | PC | EL |
| VoltDB | PC | EC |

**When to use this framing:** When CAP analysis is insufficient. PACELC captures why two AP systems can feel very different in practice.

### 1.3 Consistency Models

**Eventual Consistency:** If no new updates are made to a given data item, eventually all accesses to that item will return the last updated value. The convergence window is unbounded in theory but typically milliseconds to seconds in practice.

- *Real-world example:* DNS propagation. When you update a DNS record, it takes time to propagate across nameservers worldwide.
- *Trade-off:* Maximum availability and performance; application code must tolerate reading stale data. Conflict resolution becomes the application's problem.

**Strong Consistency (Linearizability):** Every operation appears to take effect atomically at some point between its invocation and its response. All observers see operations in the same order.

- *Real-world example:* Google Spanner uses TrueTime (GPS + atomic clocks) to achieve external consistency across globally distributed data centers.
- *Trade-off:* Higher latency (requires coordination). Lower availability during partitions.

**Causal Consistency:** Operations that are causally related are seen by all nodes in the same order. Concurrent (causally unrelated) operations may be seen in different orders by different nodes.

- *Real-world example:* A social media comment system. If user A posts a message and user B replies, all observers must see A's post before B's reply.
- *Trade-off:* Stronger than eventual, weaker than linearizable. Requires tracking causal dependencies (vector clocks, version vectors).

**Other notable models:**
- **Read-your-writes:** A client always sees its own writes. Essential for user-facing applications.
- **Monotonic reads:** If a process has seen a particular value, subsequent accesses will never return previous values.
- **Session consistency:** Guarantees within a session scope. Used by Azure Cosmos DB as a default level.

### 1.4 Consensus Algorithms

**The Problem:** Getting multiple nodes to agree on a single value in the presence of failures.

**Paxos:**
- Invented by Leslie Lamport (1989). The foundational consensus algorithm.
- Operates in phases: Prepare/Promise (phase 1), Accept/Accepted (phase 2).
- *Trade-off:* Provably correct but notoriously difficult to understand and implement.

**Raft:**
- Designed explicitly for *understandability* (2014).
- Decomposes consensus into: **Leader Election**, **Log Replication**, **Safety**.
- *Trade-off:* Equivalent to Multi-Paxos in performance. Easier to implement correctly. Used by etcd, CockroachDB, TiKV, Consul.
- **Key property:** Both Paxos and Raft tolerate `f` failures with `2f + 1` nodes.

### 1.5 Distributed Transactions

**Two-Phase Commit (2PC):**
- Phase 1 (Prepare): Coordinator asks all participants "can you commit?"
- Phase 2 (Commit/Abort): If all vote YES, coordinator sends COMMIT.
- *Trade-off:* Provides atomicity but is a **blocking protocol**. If coordinator crashes mid-protocol, participants hold locks indefinitely.

**Saga Pattern:**
- Decomposes a distributed transaction into local transactions, each with a **compensating transaction**.
- **Choreography-based:** Each service publishes events; no central coordinator.
- **Orchestration-based:** A central saga orchestrator tells each participant what to do.
- *Trade-off:* No distributed locks, much better performance. But provides only eventual consistency. Compensating transactions can be complex.
- *Real-world example:* E-commerce order flow: (1) Create order, (2) Reserve inventory, (3) Charge payment, (4) Ship. If payment fails, compensate by releasing inventory.

### 1.6 Vector Clocks

**What they are:** A mechanism for tracking causality in distributed systems. Each node maintains a vector of logical clocks, one per node.

**Comparison rules:** Given vectors A and B:
- `A < B` (A happened before B) if every element of A <= corresponding element of B, and at least one is strictly less.
- `A || B` (concurrent) if neither A < B nor B < A.

**Trade-off:** Accurate causality tracking, but vector size grows linearly with nodes. Solutions include version vectors and dotted version vectors.

### 1.7 CRDTs (Conflict-free Replicated Data Types)

**What they are:** Data structures that can be replicated across multiple nodes, updated independently and concurrently without coordination, and mathematically guaranteed to converge.

| Type | Description | Use Case |
|---|---|---|
| G-Counter | Grow-only counter | Like counts, view counts |
| PN-Counter | Positive-negative counter pair | Inventory counts |
| G-Set | Grow-only set | Tag sets |
| OR-Set | Add/remove with add-wins semantics | Collaborative editing |
| LWW-Register | Last-writer-wins register | Simple key-value stores |
| Sequence CRDTs | Ordered lists with concurrent inserts | Collaborative text editing |

**Real-world examples:** Redis Enterprise (active-active geo-replication), Figma (real-time collaborative design), Apple Notes (cross-device sync).

---

## 2. SCALABILITY PATTERNS

### 2.1 Horizontal vs. Vertical Scaling

**Vertical (Scale Up):** Add more resources to existing machines.
- *Limits:* Hardware ceilings. Single point of failure. Cost grows super-linearly.
- *Real-world:* Stack Overflow runs on a small number of very powerful servers.

**Horizontal (Scale Out):** Add more machines.
- *Complexity:* Introduces distributed systems problems. Requires stateless application design.
- *Practical approach:* Scale vertically until it hurts, then scale horizontally.

### 2.2 Sharding Strategies

**Hash-Based Partitioning:** `shard = hash(key) % num_shards`. Uniform distribution. Range queries become expensive. **Consistent hashing** minimizes data movement when nodes change. **Virtual nodes** improve balance.

**Range-Based Partitioning:** Contiguous ranges per shard. Efficient range queries. Prone to hotspots. Used by HBase, Bigtable, CockroachDB.

**Geographic Partitioning:** By region for latency and compliance. Cross-region queries are expensive.

**Choosing a shard key is critical.** Bad choices create hotspots.

### 2.3 Load Balancing Algorithms

| Algorithm | Best For |
|---|---|
| Round Robin | Homogeneous servers, uniform request cost |
| Weighted Round Robin | Heterogeneous hardware |
| Least Connections | Varying request durations (WebSockets) |
| Least Response Time | Latency optimization |
| Consistent Hashing | Cache layers, stateful backends |
| Random with Two Choices | Surprisingly effective at scale |

**L4 vs L7:** L4 routes by IP/port (fast). L7 routes by HTTP content (flexible).

### 2.4 Auto-Scaling

- **Reactive:** Scale on observed metrics (CPU, queue depth, p99 latency). Introduces lag.
- **Predictive:** ML models on historical patterns. Essential for periodic traffic.
- **Scheduled:** Pre-scale for known events.
- **Key concerns:** Cool-down periods, warm-up time, scale down slowly.

### 2.5 Capacity Planning

**Key numbers every engineer should know:**

| Operation | Latency |
|---|---|
| L1 cache reference | 1 ns |
| Main memory reference | 100 ns |
| SSD random read | 16 μs |
| HDD random read | 2 ms |
| Same datacenter round trip | 0.5 ms |
| US East ↔ US West | 40 ms |
| US ↔ Europe | 80 ms |

---

## 3. SYSTEM DESIGN PRINCIPLES

### 3.1 Separation of Concerns
Each component should address a distinct concern. Data plane vs. control plane. Read path vs. write path (CQRS).

### 3.2 Single Responsibility (System Level)
Each service owns one bounded context. Anti-pattern: Distributed Monolith.

### 3.3 Loose Coupling & High Cohesion
Achieved through async messaging, schema evolution, API versioning, and service mesh.

### 3.4 Defense in Depth
Multiple security layers: Edge/WAF → API Gateway → Service mesh → Application → Data layer.

### 3.5 Principle of Least Privilege
Minimum required permissions. IAM roles over shared credentials. Network segmentation.

---

## 4. HIGH AVAILABILITY & FAULT TOLERANCE

### 4.1 Replication
- **Synchronous:** Strong consistency, RPO=0. Higher write latency.
- **Asynchronous:** Low latency. Data loss risk on primary failure.
- **Quorum-Based:** Write to W, read from R, where W + R > N.

### 4.2 Failover Strategies
- **Active-Passive:** Simple but wastes capacity.
- **Active-Active:** Maximum utilization. Write conflicts must be resolved.
- **Leader-Follower with Auto Failover:** Watch for split-brain. Use fencing.

### 4.3 Circuit Breakers
States: **Closed** → (failures exceed threshold) → **Open** → (timeout) → **Half-Open** → (probe succeeds) → **Closed**.

### 4.4 Bulkhead Pattern
Isolate components (thread pool, process, shard isolation) so failure in one doesn't sink the whole ship.

### 4.5 Retry with Exponential Backoff and Jitter
Full jitter: `wait = random(0, base * 2^attempt)`. Must-haves: max retry count, retry budget, idempotency, distinguish retryable vs non-retryable errors.

### 4.6 Chaos Engineering
Define steady state → Hypothesize → Introduce real-world events → Observe. Start in staging, graduate to production with small blast radius.

### 4.7 Graceful Degradation
Feature flags, read-only mode, fallback responses, load shedding, timeout-based degradation.

---

## 5. KEY PHILOSOPHIES

### 5.1 Design for Failure
Every network call has a timeout. Every dependency is unreliable. Test failure scenarios explicitly. Optimize MTTR over MTBF.

### 5.2 Idempotency Everywhere
Idempotency keys, natural idempotency (`SET x = 100` not `SET x = x + 10`), conditional writes, deduplication at consumer.

### 5.3 Eventual Consistency as Default
Default to eventual, opt into strong only where business requires it (financial transactions, last-item inventory, unique constraints, distributed locks).

### 5.4 Immutability
Event sourcing, append-only logs (Kafka), immutable infrastructure, copy-on-write. Eliminates concurrency bugs, enables audit trails and replay.

### 5.5 Statelessness
No local state between requests. Externalize sessions (JWT, Redis). The 12-Factor App methodology codifies this.

---

## Decision Framework

1. **What are the consistency requirements?** Per-operation, not globally.
2. **What is the failure domain?** Design blast radius containment.
3. **What is the read/write ratio?** Drives caching and replication strategy.
4. **What are the latency requirements?** Determines distribution and caching (PACELC).
5. **What is the growth trajectory?** Design for 10x, plan for 100x.
6. **What happens when each component fails?** Have an answer for every one.

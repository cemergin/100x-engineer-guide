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

Here's the thing about distributed systems: they are fundamentally about making promises you can't always keep.

When you run a single database on a single server, life is simple. You write something, you read it back, it's there. Causality works. Time makes sense. But the moment you split that system across two machines — for reliability, for scale, for geography — you've entered a world where the laws of physics start working against you. Light takes time to travel. Networks drop packets. Servers crash at the worst possible moment.

Every senior engineer has a story. Maybe it's the time their database replica fell 30 seconds behind during a traffic spike and users started seeing "phantom" data — items they'd just deleted reappearing, or payments that seemed to have never happened. Maybe it's the 3am incident where a network partition split their cluster and both halves happily accepted writes, creating a consistency nightmare that took days to untangle.

These aren't edge cases. They're the baseline reality of distributed systems. And the engineers who thrive in this world are the ones who understand the theory deeply enough to make *deliberate* trade-offs — not the ones who cargo-cult best practices without knowing why they exist.

This chapter is your foundation. Every other chapter in this guide builds on it. We're going to cover the core theorems, the consistency models, the algorithms that make distributed databases tick, and the patterns that let you build systems that survive reality. Let's dig in.

### In This Chapter
- Distributed Systems Fundamentals (CAP, PACELC, consistency models, consensus, transactions, CRDTs)
- Scalability Patterns (sharding, load balancing, auto-scaling, capacity planning)
- System Design Principles
- High Availability & Fault Tolerance
- Key Philosophies

### Related Chapters
- [Ch 2: Data Engineering Paradigms] — data engineering builds on consistency models covered here
- [Ch 3: Software Architecture Patterns] — architecture patterns apply these concepts in practice
- [Ch 4: Reliability Engineering & Operations] — reliability operationalizes these designs

---

## 1. DISTRIBUTED SYSTEMS FUNDAMENTALS

### 1.1 CAP Theorem (Brewer's Theorem)

In 1998, Eric Brewer stood up at a conference and made a conjecture that would become one of the most influential ideas in systems engineering: you can only get two out of three properties in a distributed data store. A few years later, it was formally proven. We call it CAP.

Here are the three properties:

- **Consistency (C):** Every read receives the most recent write or an error. All nodes see the same data at the same time. If you write `x = 5` and then read `x`, you get `5` — always, from any node in the cluster.
- **Availability (A):** Every request receives a non-error response. The system keeps answering, even if it can't guarantee the response contains the most recent write.
- **Partition Tolerance (P):** The system continues to operate despite arbitrary message loss or failure of part of the network. If two nodes can't talk to each other, the system doesn't just die.

The critical insight — and the one that's most often missed — is that **partition tolerance isn't optional.** If you're running a distributed system, network partitions *will* happen. A flaky switch, a misconfigured firewall, a data center fiber cut — you cannot eliminate them. So the real choice, when a partition occurs, is: do you stay **Consistent** (and potentially reject requests from nodes that can't verify they have the latest data), or do you stay **Available** (and potentially serve stale data)?

That gives you:

- **CP systems** (e.g., ZooKeeper, etcd, HBase, MongoDB with majority write concern): During a partition, the minority side of the split refuses requests rather than risk serving or accepting inconsistent data. Think of it as the cautious choice — "I'd rather say 'I don't know' than give you a wrong answer." Use CP when correctness is non-negotiable: financial ledgers, distributed locks, leader election, configuration management.

- **AP systems** (e.g., Cassandra, DynamoDB, CouchDB, Riak): During a partition, every node keeps serving requests. You stay up, but some reads may return stale data. This is the optimistic choice — "I'd rather give you something than nothing, even if it's slightly out of date." Use AP when availability matters more than immediate consistency: shopping carts, social media feeds, DNS, product catalogs.

**The moment it clicks:** Imagine you're building a bank. Customer A has $100. They withdraw $100 on their phone. Before that transaction propagates, their laptop also tries to withdraw $100. A CP system would block one of those — "I can't verify your balance right now." An AP system would let both go through, leaving the account at -$100. For a bank, CP is obviously right. For a tweet like count? You can live with approximate numbers.

**One common misconception to kill right now:** CAP is often treated as a static, binary design choice you make once at architecture time. It's not. Many systems let you tune consistency *per operation*. Cassandra's consistency levels — `ONE`, `QUORUM`, `ALL` — let you decide for each query whether you want maximum speed or maximum correctness. A background analytics job might use `ONE`; an inventory decrement that could oversell might use `QUORUM`.

CAP also says nothing about latency. Which brings us to something more useful in practice.

### 1.2 PACELC Theorem

CAP is a great thought experiment, but it has a practical problem: it only describes system behavior during a partition. And partitions, while inevitable, are *rare*. Your system spends 99.99% of its time in normal operation. What does CAP tell you about trade-offs then? Nothing.

Daniel Abadi proposed PACELC in 2010 to fill that gap. The formulation is:

> If there is a **P**artition, choose between **A**vailability and **C**onsistency; **E**lse (normal operation), choose between **L**atency and **C**onsistency.

This is a much more practical lens. Because here's the thing: even in normal operation, there's a tension. If you want every write to be immediately visible to every reader across all replicas, you have to wait for all those replicas to acknowledge. That takes time — sometimes a lot of time if replicas are in different geographies. Consistency costs latency.

The PACELC trade-off shows up everywhere you haven't thought about it:

- When Cassandra replicates a write to three nodes but only waits for one to acknowledge (consistency level ONE), it's choosing latency over consistency.
- When DynamoDB's global tables propagate writes asynchronously across regions, it's choosing low latency over synchronous consistency.
- When MongoDB uses a write concern of `{w: "majority"}`, it's choosing consistency over latency — it waits until most replicas confirm the write.

Here's how major systems classify on the PACELC spectrum:

| System | During Partition (PAC) | Normal Operation (ELC) |
|---|---|---|
| DynamoDB | PA (prefers availability) | EL (low latency, eventual consistency) |
| Cassandra | PA | EL |
| MongoDB | PC (prefers consistency) | EC (strong consistency, higher latency) |
| PNUTS (Yahoo) | PC | EL |
| VoltDB | PC | EC |

Notice that DynamoDB and MongoDB are both "PA" — they both prioritize availability during partitions. But in normal operation they feel completely different: DynamoDB is designed for sub-millisecond reads with eventual consistency, while MongoDB offers strong consistency by default. PACELC captures that distinction; CAP doesn't.

**When to use this framing:** Any time you're evaluating databases for a new system, run through PACELC explicitly. Ask: "What's the partition behavior?" and "In the happy path, are we trading latency or consistency?" You'll make much better choices.

### 1.3 Consistency Models

Okay, so "consistency" is in CAP and PACELC, but engineers throw the word around loosely and it causes a lot of confusion. Let's be precise. There's actually a whole spectrum of consistency models, from "totally relaxed, anything goes" to "so strict you'll feel it in your latency."

**Eventual Consistency: The Optimist**

The guarantee is simple: if you stop making updates to a piece of data, eventually all replicas will converge to the same value. Note what's *not* guaranteed: when that convergence happens. In practice it's usually milliseconds to seconds. But in theory it's unbounded.

The most relatable example is DNS. When you update a DNS record — say, you're migrating a domain to a new server — the change propagates across nameservers worldwide. In the meantime, some users get routed to the old server and some to the new one, depending on which nameserver they hit. Eventually (usually within 24-48 hours, often much faster) everyone converges. DNS's entire design is built around eventual consistency because the alternative — strong consistency across thousands of distributed nameservers — would make DNS too slow and fragile to function at internet scale.

The catch is that application code has to *handle* stale reads. If your shopping cart is eventually consistent, users might add an item and then not see it immediately if their next request hits a different replica that hasn't caught up. You need to either tolerate this (most shopping cart scenarios are fine with it) or use read-your-writes guarantees (see below).

**Strong Consistency (Linearizability): The Perfectionist**

Linearizability is the gold standard of consistency. Every operation appears to take effect atomically at some single point in time between when it was invoked and when it returned. All observers everywhere see all operations in the same order, as if there were a single, perfectly synchronized history.

This is what you'd get from a single-machine system. The challenge in distributed systems is achieving it without bringing your system to its knees.

The most impressive example in production is **Google Spanner**. Spanner achieves what they call "external consistency" — essentially linearizability — across data centers on multiple continents. Their secret weapon is called **TrueTime**: a combination of GPS receivers and atomic clocks at every data center that bounds clock uncertainty to within ~7ms. Instead of pretending clocks are synchronized (they never are), TrueTime acknowledges the uncertainty and builds the protocol around it. When a transaction commits, Spanner waits out the maximum clock uncertainty before considering it done. The result is a globally distributed database with strong consistency — but you pay for it in commit latency.

For most applications, you don't need Spanner-level global linearizability. You need it per-object, or within a shard. That's much cheaper.

**Causal Consistency: The Middle Path**

Here's a consistency model that's often underappreciated: causal consistency. It's stronger than eventual but weaker than linearizable, and it maps beautifully to how humans think about cause and effect.

The rule is: if operation A causally precedes operation B (meaning A's result was visible when B happened), then every observer must see A before B. Operations that aren't causally related can be observed in any order.

The classic example is a comment thread. If Alice posts "anyone know a good Python tutorial?" and Bob replies "yes, check out the official docs," any user reading the thread must see Alice's question *before* Bob's answer. It would be bizarre to show Bob's reply without Alice's question — the reply only makes sense in context. But Bob's reply and Carol's separate reply to a different comment in the same thread? Those have no causal relationship, so different nodes might see them in different orders.

Implementing causal consistency requires tracking what you've seen. The usual mechanism is **vector clocks**: each piece of data carries a version vector noting which updates from which nodes have been incorporated. We'll cover vector clocks in section 1.6.

**Other Notable Models Worth Knowing**

- **Read-your-writes:** You always see your own writes, even if other clients don't see them yet. This sounds like table stakes but requires deliberate implementation — you need to route your subsequent reads to the same replica, or wait for the write to propagate, or pass a read token. Crucial for user-facing applications where you'd otherwise show someone a page that's missing the change they just made.

- **Monotonic reads:** Once you've seen a value, you'll never see an older value. If you read `x = 5`, you'll never subsequently read `x = 3`. This is about not going backwards in time, even if you're slightly behind. Easy to implement by always reading from the same replica in a session.

- **Session consistency:** Read-your-writes + monotonic reads + a few other guarantees, but only within a single session. Once you start a new session (or reconnect), no guarantees about what state you see. Azure Cosmos DB offers session consistency as its default because it covers most application needs with minimal performance impact.

**Picking the right model matters more than picking the "best" one.** The goal isn't to always choose linearizability — it's to understand what each service in your system actually needs and give it exactly that. Over-engineering a real-time game leaderboard to use linearizable reads is waste. Under-engineering a payment processor to use eventual consistency is a bug.

### 1.4 Consensus Algorithms

Here's a problem that sounds deceptively simple: you have a cluster of nodes, some of which might fail, and you want them all to agree on a single value. Say, "who is the leader right now?" Or "was this transaction committed or aborted?"

This is the consensus problem. And it turns out to be surprisingly hard — hard enough that it took decades of academic research and some genuinely brilliant people to produce practical algorithms. Let's look at the two that matter most in production systems today.

**Paxos: The Provably Correct One**

Leslie Lamport described Paxos in a 1989 paper that he submitted to a journal, got rejected because reviewers found it "too theoretical," and eventually published in 1998. It's now one of the most cited papers in computer science.

The core idea is elegant. Paxos separates the process of reaching consensus into two phases:

- **Phase 1 (Prepare/Promise):** A node that wants to propose a value sends a "Prepare" message with a proposal number `n` to a quorum of other nodes. Each node that receives this message promises: "I won't accept any proposal numbered less than `n`," and tells the proposer about any value it's already accepted.

- **Phase 2 (Accept/Accepted):** If the proposer gets a quorum of promises, it sends an "Accept" message with its proposal. If the value from phase 1 included an already-accepted value from some node, the proposer *must* use that value (this is how Paxos prevents conflicts). If no prior value exists, the proposer can use whatever value it wants. A quorum of accepts means consensus is reached.

The protocol is provably safe — it will never decide two different values — even in the presence of arbitrary message loss, reordering, and node crashes. What it doesn't handle is Byzantine failures (nodes that actively lie). For that you'd need BFT protocols, which have much higher cost.

The practical problem with Paxos is captured best by this famous quote from Lamport's colleague Henry Robinson: "There are two types of people: those who haven't read Paxos and those who don't understand it." Implementing Paxos correctly is notoriously difficult. The original paper describes "single-decree Paxos" (agreement on one value). Extending it to the repeated-consensus problem of a replicated log ("Multi-Paxos") requires significant additions that are only partially described in the literature. Google's Chubby and Bigtable use Paxos under the hood, but they had to fill in a lot of gaps themselves.

**Raft: The Understandable One**

Diego Ongaro and John Ousterhout designed Raft in 2014 with a stated goal: understandability. Their paper is literally titled "In Search of an Understandable Consensus Algorithm." They made design decisions specifically to make the algorithm easier to reason about, even at the cost of some elegance.

Raft decomposes consensus into three relatively independent sub-problems:

1. **Leader Election:** At any time, one node is the leader. The leader handles all client requests. If the leader fails, the remaining nodes elect a new one. Each election uses a term number; within a term, there can be at most one leader.

2. **Log Replication:** The leader accepts log entries (commands from clients) and replicates them to followers. Once a majority has acknowledged a log entry, it's considered "committed" — it's safe to apply to the state machine and respond to the client.

3. **Safety:** Raft's safety property is that if any server has applied a log entry at a given index to its state machine, no other server will ever apply a different log entry for that index. This is guaranteed by election restrictions: a node can only become leader if its log is at least as up-to-date as any majority.

The key numbers: both Paxos and Raft require `2f + 1` nodes to tolerate `f` failures. To survive 1 failure, you need 3 nodes. To survive 2 failures, you need 5. This is the minimum quorum math.

Raft is used by **etcd** (the backing store for Kubernetes), **CockroachDB**, **TiKV** (the storage layer for TiDB), and **Consul**. If you're operating Kubernetes, you're depending on Raft every time a pod starts or a ConfigMap changes.

**The moment it clicks:** Think of Raft like a company with a CEO (leader) and department heads (followers). The CEO decides everything; department heads replicate decisions. If the CEO goes on vacation unexpectedly, the department heads hold an election — whoever has the most complete record of past decisions becomes the new CEO. No department head can claim to be CEO without convincing a majority of colleagues that they're the most informed. That's leader election + log replication in a nutshell.

We'll revisit consensus in the context of distributed databases in Ch 2, and in the context of service mesh and configuration management in Ch 3.

### 1.5 Distributed Transactions

Let's say you're building an e-commerce system. When a customer clicks "Buy Now," you need to: (1) debit their account, (2) decrement inventory, (3) create the order record. These happen across three different services with three different databases. How do you make sure all three succeed, or all three fail? Welcome to the distributed transactions problem.

**Two-Phase Commit (2PC): The Classic Answer**

2PC is the textbook solution and has been around since the 1970s. The protocol has two participants: a **coordinator** (usually the service initiating the transaction) and multiple **participants** (the services being coordinated).

- **Phase 1 (Prepare):** The coordinator sends a "prepare" message to all participants. Each participant checks whether it *can* commit its part of the transaction — does it have the resources? Are there conflicts? If yes, it responds "YES" and durably logs its intent to commit. If no, it responds "NO."

- **Phase 2 (Commit/Abort):** If *all* participants voted YES, the coordinator sends COMMIT and everyone applies their changes. If *any* participant voted NO, the coordinator sends ABORT and everyone rolls back.

This gives you atomicity: either everything commits or nothing does.

The problem is that 2PC is a **blocking protocol.** If the coordinator crashes after participants have voted YES but before sending COMMIT or ABORT, the participants are stuck — they've promised to commit but don't know the final decision. They hold their locks indefinitely, waiting for the coordinator to recover. In a high-throughput system, this is catastrophic. You can mitigate it with a coordinator that writes its decision to durable storage before dying, but recovery is still slow and complex.

2PC also creates a latency multiplier: you need at least 2 round trips to complete any transaction, plus the overhead of participants writing to their own durable logs. For cross-region transactions, that can mean hundreds of milliseconds of added latency.

**The Saga Pattern: The Modern Answer**

The Saga pattern trades away strict atomicity for a much more practical model. Instead of one big distributed transaction with locks, you decompose the operation into a sequence of **local transactions**, each within a single service. The key innovation: every step has a corresponding **compensating transaction** that can undo it if something goes wrong later.

For the e-commerce example:
1. Create order (compensation: cancel order)
2. Reserve inventory (compensation: release reservation)
3. Charge payment card (compensation: issue refund)
4. Confirm shipping (compensation: cancel shipment)

If step 3 (charge payment) fails, you run the compensations for steps 1 and 2 — cancel the order and release the reservation. No distributed locks held. No coordinator blocking.

There are two ways to orchestrate a Saga:

- **Choreography-based:** Each service listens for events from previous steps and publishes events when its step completes. No central coordinator. Very decoupled, but harder to reason about the global flow. Good when steps are simple and the flow is stable.

- **Orchestration-based:** A dedicated Saga orchestrator (often implemented as a state machine) tells each service what to do and handles the flow explicitly. Easier to debug and monitor. Good when the flow is complex or needs visibility.

The trade-off: Sagas provide **eventual consistency**, not atomicity. There's a window between when one step completes and the next begins where the system is in a partially-updated state. External observers — and compensating logic — have to account for this. This is fine for most business processes. It's not fine for operations like "transfer exactly $100 from account A to account B" where you need atomic debit + credit.

A useful mental model: think of Sagas as long-running business processes, not database transactions. Your bank already operates this way — ACH transfers are asynchronous, can be reversed, and the accounting system deals with interim states. It works because the business rules are designed around eventual consistency.

We'll revisit Sagas in Ch 3 when we cover event-driven architectures and microservices.

### 1.6 Vector Clocks

Here's a puzzle. You have three servers — A, B, and C — all accepting writes to a shared key-value store. Server A updates `x = 1`. Server B simultaneously updates `x = 2`. A few seconds later, Server C receives both updates. Which one wins?

If you just use wall-clock timestamps, you're in trouble. Clocks drift. NTP can only sync to within a few milliseconds, and in the time it takes a message to travel between servers, clock differences matter. You might think you're ordering events correctly but you're actually getting it wrong.

Vector clocks solve this by abandoning the idea of a global clock entirely. Instead, each node maintains a **vector** of logical counters — one per node in the system.

The rules:
- When a node processes a local event, it increments its own counter.
- When a node sends a message, it includes its current vector.
- When a node receives a message, it merges the incoming vector with its own by taking the max of each element, then increments its own counter.

Now you can determine causality precisely. Given two version vectors A and B:
- **A happened before B** (`A < B`) if every element of A is less than or equal to the corresponding element of B, and at least one element is strictly less.
- **A and B are concurrent** (`A || B`) if neither `A < B` nor `B < A` — they were independent events with no causal relationship.

When A and B are concurrent, you have a **conflict** that needs resolution. That's fine — at least you know it's a conflict, rather than silently picking the wrong winner based on bad clocks. Resolution strategies vary: last-writer-wins (using some other tie-breaker), application-level merge (like a CRDT), or surface the conflict to the user (like Dropbox's "conflicted copy").

Amazon Dynamo (the paper that inspired DynamoDB) famously used vector clocks, surfacing conflicts to the shopping cart application layer. The "add to cart" operation was designed to be mergeable — worst case you show a user items they already removed, which is less bad than losing items they meant to keep.

**Trade-off:** Vector size grows linearly with the number of nodes. In a large cluster, this can get expensive. Solutions include **version vectors** (track per-replica rather than per-client), **dotted version vectors** (add more precise causality tracking), and **logical timestamps** for approximate ordering when exact causality isn't needed.

### 1.7 CRDTs (Conflict-free Replicated Data Types)

What if you could design data structures that *never* had conflicts? Not by preventing concurrent writes, but by making concurrent writes mathematically guaranteed to produce the same final state regardless of the order they're applied?

That's the promise of CRDTs — Conflict-free Replicated Data Types. The math behind them comes from lattice theory: a CRDT is a data structure with a merge function that is commutative, associative, and idempotent. In English: it doesn't matter what order you apply updates, and applying the same update twice is the same as once.

This is a profound guarantee. You can let every replica accept writes with zero coordination, ship those writes to other replicas in any order, and the system will converge to the same final state everywhere. No locks. No consensus rounds. Just eventual convergence with mathematical proof.

Here are the most common CRDTs and where they shine:

| Type | Description | Use Case |
|---|---|---|
| G-Counter | Grow-only counter. Each node owns its own counter; total is the sum. | Like counts, view counts |
| PN-Counter | Two G-Counters — one for increments, one for decrements | Inventory counts |
| G-Set | Grow-only set. You can add elements but never remove them. | Tag sets, feature flags |
| OR-Set | Add/remove with "add-wins" semantics — concurrent add and remove resolves to added | Collaborative editing, carts |
| LWW-Register | Last-writer-wins register using a timestamp | Simple key-value stores |
| Sequence CRDTs | Ordered lists that handle concurrent insertions deterministically | Collaborative text editing |

The most mind-blowing application of CRDTs is collaborative document editing. When you and a colleague simultaneously edit the same document in **Figma** or **Google Docs**, you're both making changes to replicated state without waiting for each other. The underlying algorithms (often tree-based sequence CRDTs) ensure your cursor positions and text content always converge to something consistent. No edit gets lost. No "conflicted copy" dialog.

Real-world deployments: **Redis Enterprise** uses CRDTs for active-active geo-replication — you can write to a Redis cluster in us-east and eu-west simultaneously and they'll converge. **Apple Notes** uses a CRDT-based sync mechanism so you can edit on your phone without network access, then sync later without conflicts.

The trade-off is expressiveness. Not every data type can be made conflict-free without semantic restrictions. You can't have a general-purpose decrement-wins rule and an add-wins rule simultaneously — you have to pick one semantic. For complex business logic, CRDTs get tricky. But for the cases they cover — counters, sets, registers, lists — they're elegant and powerful.

---

## 2. SCALABILITY PATTERNS

### 2.1 Horizontal vs. Vertical Scaling

Before we get into sophisticated patterns, let's settle the foundational debate: when your system is struggling to keep up, do you buy a bigger box or more boxes?

**Vertical scaling (scale up)** is adding resources to the machine you already have — more CPUs, more RAM, faster SSD, bigger NIC. The advantages are real: you don't change your software architecture, you don't introduce distributed systems complexity, and operational overhead stays low. Stack Overflow — one of the highest-traffic developer sites on the internet — famously ran on a *tiny* number of very powerful servers for years. At their scale, that was the right call.

But vertical scaling has hard limits. There are only so many CPUs you can put in one machine. Memory bandwidth becomes a bottleneck before you run out of RAM slots. And critically: a single machine is a single point of failure. When that box dies (and it will), your entire service goes with it.

**Horizontal scaling (scale out)** is adding more machines. You go from one server to ten to a hundred. The advantages are massive: effectively unlimited scale ceiling, fault tolerance through redundancy, and the ability to add capacity incrementally as traffic grows.

The cost is complexity. The moment you have two machines, you have a distributed system. State that lived simply on one box now needs to be shared, partitioned, or replicated. Requests need to be routed. Failures need to be handled. Your application code needs to be stateless (or your state management needs to be explicit and external).

**The practical heuristic:** Scale vertically until it hurts, then scale horizontally. Most teams scale horizontally too early and pay the complexity tax before they need to. But don't go so vertical that you have a single point of failure in your critical path.

The deeper lesson is that these aren't mutually exclusive. Modern cloud architectures do both: horizontal scaling of application servers (many relatively modest instances) plus vertical scaling of individual database nodes (large memory instances for in-memory caching).

### 2.2 Sharding Strategies

When a single database node can't hold or serve all your data, you shard — you split the data across multiple nodes, each responsible for a partition of the total dataset. The science of sharding is really the science of picking a partition strategy that matches your access patterns.

**Hash-Based Partitioning**

The simplest approach: `shard = hash(key) % num_shards`. You hash the row's key and take the modulo. This distributes data uniformly across shards — no hotspots, good balance.

The problem is resharding. If you go from 10 shards to 11, almost every key maps to a different shard. You'd have to move virtually all your data. That's why you almost always use **consistent hashing** instead. Consistent hashing places both nodes and keys on a circular ring; when you add a node, only the keys between the new node and its predecessor need to move — roughly `1/n` of the data.

To improve balance further (since random node placement on the ring can be uneven), you use **virtual nodes**: each physical server represents multiple positions on the ring. Cassandra and DynamoDB both use consistent hashing with virtual nodes.

**Range-Based Partitioning**

Assign contiguous key ranges to shards — shard 1 gets keys A-M, shard 2 gets N-Z. The huge advantage is that **range queries are efficient**: "give me all orders from user IDs 1000-2000" hits one shard, not all of them.

The risk is hotspots. If your keys aren't uniformly distributed — if, say, you're using timestamps as keys and all your traffic is recent — all writes land on the most recent shard while earlier shards sit idle. HBase, Bigtable, and CockroachDB all use range partitioning, and all have tooling to detect and split hot ranges.

**Geographic Partitioning**

Route data based on where it originates. European users' data lives in EU shards; North American users' in US shards. This gets you:
- Low latency (users' data is close to them)
- Regulatory compliance (GDPR data residency requirements)

The cost is cross-region queries becoming very expensive, and complexity in routing logic.

**Choosing a shard key is the most important decision you'll make in a sharded system.** A bad shard key creates hotspots that completely undermine the point of sharding. Some guidelines:
- High cardinality (many distinct values, so data spreads across shards)
- Uniform distribution (not clustered in time or value space)
- Aligns with your most common access patterns
- Avoids cross-shard joins for your hottest queries

The horror story you want to avoid: a company shards their user table by `first_name`. Users named "John" and "James" swamp a single shard while "Xander" and "Zelda" barely get any traffic. The hotspot shard becomes the bottleneck for the whole system.

### 2.3 Load Balancing Algorithms

You've got ten application servers. A request comes in. Which server handles it? That sounds like a simple question, but the answer has significant performance implications — especially under load.

Here's the toolkit:

| Algorithm | Best For |
|---|---|
| Round Robin | Homogeneous servers, uniform request cost |
| Weighted Round Robin | Heterogeneous hardware (send more to bigger boxes) |
| Least Connections | Varying request durations, long-lived connections (WebSockets) |
| Least Response Time | Latency optimization (send to fastest server) |
| Consistent Hashing | Cache layers, stateful backends (same key, same server) |
| Random with Two Choices | Surprisingly effective at scale |

The surprisingly effective one at the bottom — **random with two choices** (also called "the power of two random choices") — deserves explanation. Instead of tracking all servers and picking the least-loaded one (expensive at scale), you pick two servers at random and route to whichever is less loaded. This sounds crude, but mathematically it reduces the maximum load imbalance from `O(log n / log log n)` (pure random) to `O(log log n)`. It's near-optimal with almost no coordination overhead. NGINX and HAProxy support variants of this.

**L4 vs L7 load balancing:** You'll hear these terms constantly.

- **L4 (transport layer):** Routes based on IP address and port. The load balancer doesn't inspect the packet contents. Very fast (can be done in hardware or kernel space), but can't make routing decisions based on HTTP headers, paths, or cookies.

- **L7 (application layer):** Routes based on HTTP content — URL path, host header, cookies, request body. Slower (must parse the HTTP request), but massively more flexible. You can send `/api/*` traffic to your API servers and `/static/*` traffic to a CDN. L7 load balancers also terminate TLS, handle HTTP/2, and provide better observability.

In practice: use L4 at the network edge for raw throughput, L7 (usually something like NGINX, HAProxy, Envoy, or a cloud ALB) at the application tier for flexibility.

### 2.4 Auto-Scaling

Manual capacity management is how you end up with an on-call alert at 2am because your traffic doubled and you forgot to add servers. Auto-scaling is the answer.

There are three models, and the best systems combine all three:

**Reactive auto-scaling** watches metrics in real time and adds or removes capacity based on what it observes. When CPU exceeds 70%, spin up more instances; when it drops below 30%, spin down. Simple and robust, but has an inherent lag — by the time your metric crosses the threshold, starts an alert, triggers a scale-out, and waits for new instances to warm up, your users have already been suffering for 2-5 minutes.

Better metrics to react to than CPU: **request queue depth** (are requests piling up?), **p99 latency** (are users seeing slow responses?), **error rate** (are requests failing?). These are more direct signals of user impact than infrastructure metrics.

**Predictive auto-scaling** uses machine learning on historical patterns to forecast future traffic and pre-scale before the load arrives. If you know your traffic spikes at 9am every weekday because that's when your users start work, why wait for the spike to hit? Scale up at 8:45am. AWS, GCP, and Azure all offer predictive scaling. It requires several weeks of history to train effectively, but it's worth it for workloads with regular patterns.

**Scheduled scaling** is the simplest form of proactive scaling: just tell the system "at 8am, set minimum instance count to 20." Use this for known events — a marketing email going out, a product launch, a sale — where you know exactly when demand will spike. Scheduled scaling is cheap, reliable, and requires zero ML.

**Key concerns that bite teams:**

- **Cool-down periods:** Don't scale down immediately after a scale-up. Give the new instances time to prove themselves and prevent oscillation (scale up → scale down → scale up again).
- **Warm-up time:** New application instances often need 30-120 seconds to warm their JVM, load their caches, and establish database connections. Don't count them as ready before they are.
- **Scale down slowly:** Scaling down aggressively can shed load too fast. A good rule: scale up fast, scale down conservatively.

### 2.5 Capacity Planning

Here's something that separates senior engineers from everyone else: they have a gut sense for latency numbers. When someone says "we're adding a Redis cache," they can roughly estimate how much that will help. When someone proposes a cross-region database query on every page load, they know immediately that's a problem.

Jeff Dean's famous "latency numbers every programmer should know" are the foundation. Memorize these:

| Operation | Latency |
|---|---|
| L1 cache reference | 1 ns |
| Branch misprediction | 5 ns |
| L2 cache reference | 4 ns |
| Mutex lock/unlock | 17 ns |
| Main memory reference | 100 ns |
| Compress 1K with Snappy | 3 μs |
| SSD random read (4K) | 16 μs |
| Read 1 MB sequentially from memory | 3 μs |
| Read 1 MB sequentially from SSD | 49 μs |
| HDD random read | 2 ms |
| HDD sequential read (1 MB) | 825 μs |
| Same datacenter round trip | 0.5 ms |
| US East ↔ US West | 40 ms |
| US ↔ Europe | 80 ms |

The ratios matter more than the exact numbers. Memory is ~100x faster than SSD. SSD is ~125x faster than HDD for random reads. A same-datacenter network round trip is ~200x more expensive than a main memory access. Cross-region is ~160x more expensive than intra-datacenter.

**Practical implications:**

- That "quick database lookup" on every request? If it's a network call, it's at minimum 0.5ms. At 1000 req/s, you're spending 500ms/s just on that one lookup. Add caching.
- That fancy ML model running on the request path? If inference takes 50ms and you're doing it synchronously, you've just set your p50 latency floor.
- That cross-region replication for disaster recovery? You're looking at 40-80ms minimum lag. Design your consistency model around it.

**Back-of-envelope estimating** is a skill. In system design conversations (interviews, architecture reviews, "should we do X?" discussions), you should be able to derive rough numbers: "We have 10M users, each generating 10 events/day. That's 100M events/day = ~1,150 events/second. Each event is 1KB, so that's ~1.15 MB/s ingest. Easy for a single Kafka partition, probably want 3-5 for headroom."

---

## 3. SYSTEM DESIGN PRINCIPLES

These aren't rules you mechanically follow — they're ways of thinking that, once internalized, change how you see systems.

### 3.1 Separation of Concerns

Every component should address one distinct concern, and the concerns should be clearly bounded. This sounds obvious but it's violated constantly.

The most important separations in distributed systems:

**Data plane vs. control plane.** The data plane handles the actual traffic — forwarding packets, serving requests, processing events. The control plane manages configuration — routing tables, service discovery, feature flags, auto-scaling decisions. They should be independent so that a control plane failure doesn't take down the data plane. Kubernetes is built entirely around this: the API server (control plane) can go down for minutes without affecting running pods (data plane).

**Read path vs. write path (CQRS).** Command Query Responsibility Segregation is the pattern of separating the models you use to read data from the models you use to write data. Why? Read and write access patterns are often radically different. Your write path needs to be optimized for consistency and durability. Your read path needs to be optimized for query flexibility and latency. Combining them in one model means you're making compromises in both directions. Event sourcing systems naturally fall into CQRS: writes are appended events, reads are projections over those events.

**Serving tier vs. storage tier.** Keep your stateless application logic separate from your stateful data layer. This enables horizontal scaling of the serving tier without touching storage.

### 3.2 Single Responsibility (System Level)

The Single Responsibility Principle usually gets taught as an OOP concept ("a class should have only one reason to change"), but it applies just as powerfully at the system level.

Each service should own one **bounded context** — a well-defined slice of the domain, from its data to its logic to its external API. If two services need to share data through a shared database table, something has gone wrong. If one service needs to call five other services to answer a simple question, your context boundaries are wrong.

The failure mode to avoid is the **Distributed Monolith**: microservices that are so tightly coupled — shared databases, synchronous call chains, shared deployment schedules — that you get all the operational complexity of microservices with none of the independence benefits. It's the worst of both worlds. If you can't deploy one service without coordinating a release with three others, you don't have microservices. You have a monolith that happens to be running on separate machines.

### 3.3 Loose Coupling & High Cohesion

Coupling is about how much one component knows about another. Cohesion is about how well a component's pieces belong together. You want low coupling between components and high cohesion within them.

In distributed systems, the tools for loose coupling are:

- **Async messaging:** Service A publishes an event; Service B consumes it. A doesn't know B exists. B doesn't care when A runs. They evolve independently.
- **Schema evolution with backward/forward compatibility:** Protobuf, Avro, and JSON Schema all let you add fields to messages without breaking existing consumers. This is mandatory in long-lived systems.
- **API versioning:** Never break your contract. Version your APIs. Give consumers time to migrate before removing old versions.
- **Service mesh:** A sidecar proxy (Envoy, Linkerd) that handles service-to-service communication — retries, timeouts, circuit breaking, mTLS — at the infrastructure level, so services don't need to implement these in their business logic.

### 3.4 Defense in Depth

Never rely on a single security control. If one layer fails, another catches it. This is borrowed from military strategy ("defense in layers") and applied to security architecture.

The layers in a typical system:

```
Internet traffic
    → WAF / DDoS protection (Cloudflare, AWS Shield)
        → API Gateway (rate limiting, auth, request validation)
            → Service mesh (mTLS, authorization policies between services)
                → Application (input validation, authorization in business logic)
                    → Database (encryption at rest, row-level security, least-privilege credentials)
```

Each layer assumes the previous one can be bypassed. If your WAF gets fooled, your API gateway catches the malicious request. If somehow a malicious request reaches your application, your database only allows the minimum necessary operations. No single failure compromises everything.

### 3.5 Principle of Least Privilege

Every component — services, users, operators — should have the minimum permissions needed to do its job. Nothing more.

In practice:
- **IAM roles over shared credentials.** Each service has its own IAM role with permissions scoped to exactly what it needs. No "service account with full admin access."
- **Network segmentation.** Your application servers shouldn't be able to directly reach your database from the internet. VPC, security groups, and private subnets enforce this.
- **Temporary credentials.** Where possible, use short-lived tokens (AWS IAM roles, Vault-issued credentials) rather than long-lived API keys. A compromised short-lived token has limited blast radius.

This principle matters most in incident scenarios. When something goes wrong — an exploit, a misconfiguration, a compromised dependency — least privilege limits the damage. An attacker who compromises your frontend service should not be able to access your payment processing database.

---

## 4. HIGH AVAILABILITY & FAULT TOLERANCE

If the distributed systems fundamentals section was about theory, this section is about practice. How do you build systems that keep running when things break? And things will break — disks fail, networks flap, software has bugs, operators make mistakes, cosmic rays flip bits. The goal isn't to prevent all failures. The goal is to build systems that degrade gracefully when failures occur.

### 4.1 Replication

Replication is the most fundamental availability technique: keep multiple copies of your data so that losing one copy doesn't mean losing the data.

**Synchronous replication** means the primary waits for at least one replica to confirm the write before acknowledging success to the client. The benefit: if the primary dies, the replica has every committed write. RPO (Recovery Point Objective) is zero — no data loss. The cost: write latency includes a full round trip to the replica. For cross-availability-zone replication, that's ~1ms. For cross-region, it's 40-80ms. Some applications can't absorb that.

**Asynchronous replication** means the primary acknowledges the write immediately and ships it to replicas in the background. Write latency is minimal. But if the primary crashes before a write reaches the replica, that write is lost. RPO is non-zero — you might lose the last few seconds of writes. Acceptable for analytics databases where a few seconds of lost data is survivable. Unacceptable for a payment ledger.

**Quorum-based replication** is the middle path used by most production distributed databases. Write to `W` replicas, read from `R` replicas, total replicas `N`. As long as `W + R > N`, your reads will always see the latest write (because any quorum of reads overlaps with any quorum of writes).

A common configuration for Cassandra: `N=3, W=2, R=2` (QUORUM). You tolerate one replica being down for both reads and writes. If you want stronger durability, use `W=3` (ALL writes): every replica has the data, but one slow or failed replica blocks all writes.

### 4.2 Failover Strategies

**Active-Passive (Primary-Standby):** One node handles all traffic; the other sits warm but idle, ready to take over if the primary fails. Simple to reason about, easy to implement. The cost: the standby's capacity is wasted during normal operation. Failover is manual or automated, but there's always some downtime during the switch (seconds to minutes, depending on how sophisticated your automation is).

**Active-Active:** Multiple nodes handle traffic simultaneously. Maximum utilization. True zero-downtime failover — if one node dies, the others are already serving traffic. The complexity: you now have multiple writers, which means write conflicts are possible. You need either a strategy to avoid conflicts (shard so each node owns different keys) or a strategy to resolve them (CRDTs, application-layer merge logic).

**Leader-Follower with Auto Failover:** A common pattern for relational databases. One node is the elected leader and handles writes. Others are followers that replicate and handle reads. If the leader dies, an automated process elects a new leader from the followers. Used by PostgreSQL (with Patroni, Stolon, or RDS Multi-AZ), MySQL Group Replication, and many managed database services.

The big risk with automated failover is **split-brain**: if two nodes both believe they're the leader — typically because a network partition makes each believe the other is dead — you have two writers that don't know about each other. The solution is **fencing**: before a new leader starts accepting writes, it must fence the old leader (revoke its storage access, shut it down, or confirm it's genuinely dead via a STONITH — Shoot The Other Node In The Head — device). Aggressive? Yes. But preventing split-brain data corruption justifies it.

### 4.3 Circuit Breakers

The circuit breaker pattern is borrowed from electrical engineering. In your house, a circuit breaker prevents a short circuit in one room from burning down the whole house. In distributed systems, it prevents one failing dependency from cascading through your entire system.

Here's the failure mode without circuit breakers: Service A calls Service B. Service B is slow (maybe it's overloaded, maybe it's having a disk issue). Service A's requests pile up waiting for B. Service A's thread pool exhausts. Service A becomes slow. Service C, which calls Service A, also piles up. The failure cascades.

Circuit breakers short-circuit this cascade. The states:

**Closed (normal operation):** Requests flow through. The circuit breaker tracks failure rate. When failures exceed a threshold (e.g., >50% failures in a 10-second window), the circuit trips.

**Open (failure detected):** For a configured timeout period (e.g., 60 seconds), all requests immediately fail-fast without even attempting the call. Service B gets a break; Service A doesn't waste time waiting.

**Half-Open (recovery probe):** After the timeout, a small number of requests are allowed through to probe whether Service B has recovered. If they succeed, the circuit closes. If they fail, the circuit opens again.

The beauty: the circuit breaker doesn't require any coordination between services. It's local state in Service A. Netflix's Hystrix library popularized this pattern; Resilience4j, Polly (.NET), and most service meshes (Istio, Linkerd) implement it at the infrastructure level.

### 4.4 Bulkhead Pattern

On ships, bulkheads are watertight dividers. If the hull is breached, only the compartment that was hit fills with water — not the whole ship. The Titanic would have survived if its bulkheads had been taller.

The bulkhead pattern in software: isolate components so that failure in one doesn't sink everything.

Examples:
- **Thread pool isolation:** Give your integration with each external service its own thread pool. If payment processing becomes slow and exhausts its pool, your order service and notification service keep running fine.
- **Process isolation:** Run different services in separate processes (or containers). A memory leak in one doesn't crash others.
- **Database connection pool isolation:** Separate pools for different query types. An expensive reporting query that exhausts connections doesn't starve your user-facing queries.

Kubernetes resource limits are a form of bulkheading: a runaway pod that consumes all available CPU is constrained to its limit, preventing it from starving other pods.

### 4.5 Retry with Exponential Backoff and Jitter

When a request fails, retry it. This sounds obvious, but naive retries make things much worse.

**The problem with naive retries:** Imagine 1,000 services all hitting an overloaded backend. The backend returns errors. All 1,000 services retry immediately. The backend gets 1,000 more requests on top of the load that was already overloading it. The backend gets more overloaded. This is a **retry storm**, and it's how brief hiccups become prolonged outages.

**The solution: exponential backoff.** After each failure, wait longer before the next retry. Wait 1s, then 2s, then 4s, then 8s. The load the failing service produces decreases exponentially, giving the backend time to recover.

**The problem with pure exponential backoff:** All 1,000 services are still synchronized. They all waited 1s, all retried at the same moment. All waited 2s, all retried simultaneously. You've turned a continuous storm into periodic synchronized bursts.

**The solution: jitter.** Add randomness to the wait time. The standard formula:

```
wait = random_between(0, min(cap, base * 2^attempt))
```

Where `cap` is your maximum wait (e.g., 32 seconds) and `base` is your starting wait (e.g., 1 second). This spreads retries across time, smoothing the load on the recovering backend.

**Other must-haves for production retry logic:**
- **Max retry count:** Don't retry forever. Set a limit (3-5 retries is typical).
- **Retry budget:** At the system level, limit the total rate of retries. If more than 10% of your requests are retries, something is seriously wrong; stop amplifying the load.
- **Idempotency:** Only retry safe/idempotent operations. Retrying a `POST /charges` endpoint without idempotency keys charges the customer twice.
- **Distinguish retryable vs. non-retryable errors:** A `500 Internal Server Error` is worth retrying. A `400 Bad Request` or `404 Not Found` is not — no amount of waiting will make a bad request succeed.

### 4.6 Chaos Engineering

How do you actually know your fault tolerance works? Unit tests don't reveal cascading failures. Load tests don't simulate random disk failures. The answer is chaos engineering: intentionally introducing failures in production to prove your system can handle them.

Netflix's **Chaos Monkey** — which randomly kills production instances — is the most famous example. They built it because they wanted to be confident their system could survive AWS instances dying (which they do, regularly). The only way to be confident is to practice surviving it.

The chaos engineering process:
1. **Define steady state:** What does "healthy" look like? Define measurable metrics — p99 latency, error rate, successful requests per second.
2. **Hypothesize:** "If we terminate a random instance in service X, steady state will be maintained."
3. **Introduce real-world events:** Kill the instance. Or inject latency. Or drop packets. Or fill a disk.
4. **Observe:** Does steady state hold? If not, you've found a real weakness before your users did.

Start in staging. Graduate to production with small blast radius (one node in one region, not everything at once). The Netflix Chaos Engineering team runs continuous experiments in production — it's just how they validate their assumptions. The Chaos Engineering community has produced the **Principles of Chaos Engineering** (principlesofchaos.org) as a guide.

### 4.7 Graceful Degradation

When things go wrong, don't fail catastrophically — degrade gracefully. Serve a reduced experience rather than no experience at all.

The patterns:

**Feature flags:** Kill non-critical features under load. If your recommendation engine is overloaded, show a generic "popular items" list instead. The user gets *something*, not an error.

**Read-only mode:** If your database primary is failing over, can you serve cached reads while writes are unavailable? Many systems can. Users can browse; they just can't place orders for the 30 seconds it takes to promote a replica.

**Fallback responses:** Cache last-known-good responses. If the real-time inventory service is down, show inventory counts that are 60 seconds stale rather than an error page.

**Load shedding:** When you're overloaded, start dropping the least important requests first. Background batch jobs? Drop them. Unauthenticated API requests that are clearly bots? Drop them. Preserve capacity for paying customers doing critical operations.

**Timeout-based degradation:** Set aggressive timeouts on non-critical dependencies. If your personalization service doesn't respond in 50ms, proceed without personalization. If your A/B testing service is slow, default to variant A. Don't let optional enhancements block your core flow.

The mental model: draw a circle around the absolute minimum functionality your users need. Everything outside that circle can degrade. Inside the circle, you defend aggressively.

---

## 5. KEY PHILOSOPHIES

These are the mental models that elite systems engineers carry with them always. They're not rules — they're lenses that change how you see design problems.

### 5.1 Design for Failure

The most important mindset shift in distributed systems is this: **failure is not an exception, it's the normal condition.** Networks fail. Disks fail. Processes crash. Operators make mistakes. Dependencies become unavailable. This is the water you swim in.

What follows from this:

- Every network call needs a timeout. Every single one. An operation that can block indefinitely will eventually block indefinitely, at the worst possible moment.
- Every dependency is unreliable. Design your system to handle the failure of any single dependency without total collapse.
- Test failure scenarios explicitly. If you haven't tested what happens when your database goes down, you don't know what happens. The chaos engineering section above shows how.
- **Optimize MTTR over MTBF.** Mean Time To Recovery over Mean Time Between Failures. You can't prevent all failures. But you can get really good at recovering fast. Fast recovery — great observability, runbooks, automated failover — is more valuable than trying to make systems that never fail.

### 5.2 Idempotency Everywhere

An idempotent operation is one you can perform multiple times and get the same result as if you'd performed it once. `DELETE /orders/123` is idempotent — deleting a thing that's already deleted is a no-op. `POST /orders/123/charge` without an idempotency key is not — calling it twice charges the customer twice.

Idempotency is the foundation of reliable distributed systems because it makes retries safe.

How to achieve it:
- **Idempotency keys:** Clients generate a unique key (UUID) for each logical operation. If the same key is submitted twice, the server detects it and returns the cached result of the first execution without re-running the operation. Stripe uses this pattern for all payment API calls.
- **Natural idempotency:** Design your operations to be naturally idempotent. `SET balance = 100` is idempotent. `SET balance = balance + 10` is not. Where you can, prefer absolute over relative updates.
- **Conditional writes:** "Update record X only if its version is still Y." If someone else updated it, the conditional check fails and you don't apply the change twice.
- **Deduplication at consumer:** Message queues guarantee at-least-once delivery. Your consumer should track which message IDs it's already processed and skip duplicates.

### 5.3 Eventual Consistency as Default

Most of the time, you don't need strong consistency. Most of the time, the business logic genuinely doesn't require it. Users can tolerate a few seconds of lag before seeing someone else's comment. Analytics dashboards don't need to be perfectly up-to-the-millisecond. Product catalogs can be a bit stale.

Default to eventual consistency, and **opt into strong consistency only where the business genuinely requires it:**

- Financial ledgers (double-entry bookkeeping, account balances)
- Last-item inventory ("only 1 left in stock" — you cannot oversell)
- Unique constraints ("email address already taken")
- Distributed locks (mutual exclusion, "only one process should run this job")

This is a powerful design discipline. When you're designing a new feature, explicitly ask: "What are the consistency requirements here?" Often the answer is "eventually consistent is fine." When it's not, you've identified a place that needs careful engineering. Don't accidentally apply strong consistency everywhere because it's the default path of least resistance — you'll pay in latency and complexity.

### 5.4 Immutability

Mutable shared state is the source of most concurrency bugs. If you need to update X and Y atomically, but threads can see partial updates... that's a bug. If you're debugging a production incident and the state has mutated multiple times since the problem occurred... you can't reconstruct what happened.

The immutability philosophy pushes you toward systems where data is never changed, only appended to:

- **Event sourcing:** Don't store current state; store the sequence of events that produced it. Accounts don't have a "balance" field — they have a transaction log and the balance is derived. You can replay history. You can audit everything. You can reproject to a different read model. The trade-off: reading the current state requires replay (usually solved by maintaining a snapshot/materialized view).
- **Append-only logs:** Kafka is fundamentally an immutable, append-only log. Events are written; nothing is modified or deleted (within the retention window). This makes Kafka trivially replayable and easy to reason about.
- **Immutable infrastructure:** Servers are never patched or modified. When you need an update, you build a new image and replace the running instances. No configuration drift. No "snowflake" servers that can't be reproduced.
- **Copy-on-write data structures:** When you need to "modify" a value, create a new version that incorporates the change. The old version is preserved. Functional languages lean heavily on this; it's also how many MVCC databases work.

### 5.5 Statelessness

If your application servers store any state between requests — in memory, on disk — you have constraints on where you can run them, how many you can run, and what happens when one dies.

The stateless ideal: any server can handle any request. A request arrives, the server fetches whatever state it needs from an external store, processes the request, writes results back to the external store, and returns the response. When the server dies, nothing is lost. When you need more capacity, just add servers.

How to achieve it:
- **No in-process session state.** Use JWTs (stateless tokens that carry session info) or externalize sessions to Redis/Memcached.
- **No in-process caches that affect correctness.** Caches for performance are fine; caches that your business logic depends on for correctness create coupling to specific server instances.
- **Configuration from environment, not local files.** Your 12-Factor App principle: config in environment variables, not baked into the build artifact.

The 12-Factor App methodology (12factor.net) codifies statelessness along with 11 other principles for building cloud-native applications. If you haven't read it, read it. It's old but it's foundational.

---

## Decision Framework

You've got a system to design. Here's the sequence of questions that should drive your thinking:

**1. What are the consistency requirements?**
Ask this per-operation, not globally. "The system needs strong consistency" is probably wrong. "The payment ledger needs linearizable writes, the recommendation engine can be eventually consistent" is right. Map each data type and operation to its required consistency model.

**2. What is the failure domain?**
Design blast radius containment first. When service X fails, what should (and shouldn't) be affected? Draw those boundaries before you write any code. Circuit breakers, bulkheads, and graceful degradation implement those boundaries.

**3. What is the read/write ratio?**
A system with 100:1 read/write ratio should be optimized for reads — aggressively cached, denormalized, read replicas. A 1:1 write-heavy system needs write path optimization — async processing, event queues, write-behind caching.

**4. What are the latency requirements?**
Use the latency numbers table. If your SLA is 100ms p99 and you're doing 3 network calls and a database query, you've already burned through your budget in the best case. PACELC forces you to acknowledge that consistency costs latency.

**5. What is the growth trajectory?**
Design for 10x your current load. Plan for 100x. Don't over-engineer for 100x on day one — that's premature optimization. But don't design something that breaks at 2x because you assumed scale wouldn't be an issue. Know which parts of your design are the scaling bottlenecks and have a path for addressing them.

**6. What happens when each component fails?**
Walk through every external dependency and service in your architecture. Ask: "What happens when this dies?" Have an explicit answer for every one. If the answer is "the whole system goes down," that's a finding — decide whether to fix it or consciously accept the risk.

These six questions won't design your system for you. But they'll make sure you've thought about the things that matter before the first line of code is written.

---

The theory in this chapter is foundation, not abstraction. Every design decision you'll encounter in the rest of this guide traces back to trade-offs rooted here. When we talk about choosing a database in Ch 2, you'll be thinking about PACELC. When we design microservices in Ch 3, you'll be thinking about eventual consistency and Sagas. When we build reliability practices in Ch 4, you'll be thinking about fault tolerance and the philosophy of designing for failure.

Carry these models with you. They're the tools that let you have opinions in architecture discussions instead of just nodding along.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M19: Architecture Patterns Overview](../course/modules/loop-1/L1-M19-architecture-patterns-overview.md)** — Survey monolith, microservices, and event-driven architectures by evolving TicketPulse's initial design
- **[L2-M33: Kafka Deep Dive](../course/modules/loop-2/L2-M33-kafka-deep-dive.md)** — Build a real event streaming backbone and see how event-driven systems handle consistency at scale
- **[L3-M61: Multi-Region Design](../course/modules/loop-3/L3-M61-multi-region-design.md)** — Deploy TicketPulse across regions and work through the CAP trade-offs in a live system
- **[L3-M76: System Design Interview Practice](../course/modules/loop-3/L3-M76-system-design-interview-practice.md)** — Apply the decision frameworks from this chapter to realistic whiteboard problems under time pressure

### Quick Exercises

1. **Draw your current system's architecture in boxes and arrows** — no tooling required, just pen and paper. Identify every external dependency, every database, and every async queue. If you can't draw it in 10 minutes, that's signal worth paying attention to.
2. **Identify which consistency model each data store in your system uses** — is it linearizable, sequential, causal, or eventual? Check whether the code that reads from it actually tolerates the consistency level it provides.
3. **Find one single point of failure** — a component whose outage would take down the whole system. Write down what would be needed to eliminate it and what the trade-off would be.

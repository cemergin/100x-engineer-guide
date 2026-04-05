# L3-M65: Consistent Hashing & Distributed Cache

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L3-M64 (CDN & Edge Computing), L2-M37 (PostgreSQL Internals), L3-M63 (Database at Scale)
>
> **Source:** Chapters 1, 19, 31, 22, 23 of the 100x Engineer Guide

---

## The Goal

TicketPulse's Redis cache is a single node. It holds event data, session tokens, rate limiter counters, and ticket availability snapshots. It handles 10,000 reads per second. The problem:

- A single Redis node has a memory ceiling (around 25GB usable before performance degrades).
- If that node fails, the entire cache layer is gone. Every request hits the database.
- You cannot scale a single node horizontally. You can only buy a bigger machine (vertical scaling).

You need to distribute the cache across multiple nodes. But naive distribution (`hash(key) % num_servers`) is fragile: adding or removing a single server invalidates nearly every cached key. Consistent hashing solves this.

**By the end of this module, you will have implemented consistent hashing, understood why it matters, and designed a production cache architecture for TicketPulse.**

---

## 0. The Problem with Naive Hashing (5 minutes)

### The Naive Approach

```
Given 4 Redis servers (0, 1, 2, 3):
  server = hash(key) % 4

  hash("event:123")  = 7823  → 7823 % 4 = 3 → Server 3
  hash("event:456")  = 2190  → 2190 % 4 = 2 → Server 2
  hash("user:789")   = 5501  → 5501 % 4 = 1 → Server 1
```

This works fine until you add a 5th server:

```
Now: server = hash(key) % 5

  hash("event:123")  = 7823  → 7823 % 5 = 3 → Server 3  (same)
  hash("event:456")  = 2190  → 2190 % 5 = 0 → Server 0  (MOVED from 2!)
  hash("user:789")   = 5501  → 5501 % 5 = 1 → Server 1  (same)
```

Adding one server changes the mapping for approximately `(N-1)/N` of all keys. With 4 servers going to 5, that is ~80% of keys remapped. Those keys are now "missing" from their new server — cache miss storm. Your database gets hit with 80% of the total cache load simultaneously.

This is called a **thundering herd** or **cache avalanche**. It can take down your database.

---

## 1. Consistent Hashing (20 minutes)

### The Ring

Consistent hashing maps both keys and servers onto a circular hash space (a ring from 0 to 2^32 - 1).

```
The Ring (0 to 2³²-1):

              0
              │
     ┌────────┼────────┐
     │     Server A    │
     │    (hash: 1000)  │
     │                  │
     │  key "event:123" │
     │  (hash: 800)     │
     │  → maps to A     │
     │  (next clockwise)│
     │                  │
     │     Server B     │
     │    (hash: 5000)  │
     │                  │
     │     Server C     │
     │    (hash: 9000)  │
     └──────────────────┘
            2³²-1

Rule: A key maps to the first server found
      going clockwise from the key's position.
```

### 🤔 Prediction Prompt

Before looking at the implementation, think: if you add a 6th node to a 5-node consistent hashing ring, what percentage of keys would you expect to move? Compare that with naive `hash % N`.

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Implement a Consistent Hashing Ring

<details>
<summary>💡 Hint 1: Direction</summary>
Map both servers and keys onto the same circular hash space (0 to 2^32-1). A key belongs to the first server found clockwise from its position on the ring.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use MD5 (or any hash) to place nodes on the ring. For lookup, binary search the sorted positions array for the first position >= the key's hash. Wrap around to position 0 if past the end.
</details>

Implement this in TypeScript (or pseudocode). The implementation should support:
- Adding a node
- Removing a node
- Looking up which node owns a key
- Virtual nodes for balance

```typescript
import * as crypto from 'crypto';

class ConsistentHashRing {
  private ring: Map<number, string> = new Map();     // hash position → node name
  private sortedPositions: number[] = [];              // sorted hash positions
  private virtualNodes: number;                         // virtual nodes per physical node

  constructor(virtualNodes: number = 150) {
    this.virtualNodes = virtualNodes;
  }

  // Hash a string to a 32-bit integer
  private hash(key: string): number {
    const md5 = crypto.createHash('md5').update(key).digest('hex');
    return parseInt(md5.substring(0, 8), 16);
  }

  // Add a physical node to the ring
  addNode(node: string): void {
    for (let i = 0; i < this.virtualNodes; i++) {
      const virtualKey = `${node}:vn${i}`;
      const position = this.hash(virtualKey);
      this.ring.set(position, node);
      this.sortedPositions.push(position);
    }
    this.sortedPositions.sort((a, b) => a - b);
  }

  // Remove a physical node from the ring
  removeNode(node: string): void {
    for (let i = 0; i < this.virtualNodes; i++) {
      const virtualKey = `${node}:vn${i}`;
      const position = this.hash(virtualKey);
      this.ring.delete(position);
    }
    this.sortedPositions = this.sortedPositions.filter(
      pos => this.ring.has(pos)
    );
  }

  // Find which node owns a key
  getNode(key: string): string | null {
    if (this.ring.size === 0) return null;

    const keyHash = this.hash(key);

    // Binary search for the first position >= keyHash
    let low = 0;
    let high = this.sortedPositions.length - 1;
    let result = 0; // default to first position (wrap around)

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.sortedPositions[mid] >= keyHash) {
        result = mid;
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }

    // If keyHash is greater than all positions, wrap to the first position
    if (low > this.sortedPositions.length - 1) {
      result = 0;
    }

    return this.ring.get(this.sortedPositions[result]) || null;
  }

  // Get node count (physical nodes)
  getNodeCount(): number {
    return new Set(this.ring.values()).size;
  }
}
```

### 🔍 Try It: Simulate Key Distribution

```typescript
// Create a ring with 5 nodes
const ring = new ConsistentHashRing(150);
ring.addNode('redis-1');
ring.addNode('redis-2');
ring.addNode('redis-3');
ring.addNode('redis-4');
ring.addNode('redis-5');

// Distribute 1 million keys
const distribution: Record<string, number> = {};
for (let i = 0; i < 1_000_000; i++) {
  const key = `key:${i}`;
  const node = ring.getNode(key)!;
  distribution[node] = (distribution[node] || 0) + 1;
}

console.log('Distribution across 5 nodes:');
for (const [node, count] of Object.entries(distribution)) {
  const percentage = ((count / 1_000_000) * 100).toFixed(1);
  console.log(`  ${node}: ${count} keys (${percentage}%)`);
}

// Expected: each node has roughly 200,000 keys (20% ± 2%)
```

### 🔍 Try It: Add a 6th Node — How Many Keys Move?

```typescript
// Record current assignment
const before: Record<string, string> = {};
for (let i = 0; i < 1_000_000; i++) {
  before[`key:${i}`] = ring.getNode(`key:${i}`)!;
}

// Add a 6th node
ring.addNode('redis-6');

// Count how many keys changed nodes
let moved = 0;
for (let i = 0; i < 1_000_000; i++) {
  const key = `key:${i}`;
  if (ring.getNode(key) !== before[key]) {
    moved++;
  }
}

console.log(`\nAfter adding redis-6:`);
console.log(`  Keys moved: ${moved} (${((moved / 1_000_000) * 100).toFixed(1)}%)`);
console.log(`  Expected with consistent hashing: ~16.7% (1/6)`);
console.log(`  Expected with naive hash % N: ~83.3% (5/6)`);
```

**Expected results:**
- Consistent hashing: ~16-17% of keys move (approximately 1/N where N is the new node count).
- Naive `hash % N`: ~83% of keys would remap.

This is the power of consistent hashing. Adding a server causes minimal disruption. Removing a server similarly only redistributes the keys from that server to its neighbors on the ring.

### Virtual Nodes: Why 150?

Without virtual nodes, each physical server has one position on the ring. With 5 servers, one server might own 40% of the ring while another owns 5%. The distribution is uneven.

Virtual nodes place each physical server at many positions on the ring. With 150 virtual nodes per server:
- 5 physical servers = 750 positions on the ring.
- The distribution approaches uniform.

| Virtual Nodes | Standard Deviation of Key Distribution |
|---|---|
| 1 | ~40% (very uneven) |
| 10 | ~15% |
| 50 | ~7% |
| 100 | ~5% |
| 150 | ~3% |
| 200 | ~2.5% |

150 is a good balance between memory overhead and distribution quality. Each virtual node costs a few bytes of memory — negligible.

> **The bigger picture:** Consistent hashing is not just a caching technique -- it is the foundational algorithm behind Cassandra, DynamoDB, Riak, and most distributed storage systems built after 2007.

### Amazon's Dynamo Paper

Amazon's Dynamo paper (2007) introduced consistent hashing to the mainstream. Dynamo used consistent hashing to distribute data across a cluster of commodity servers. Each server owned a range of the hash ring. Adding or removing servers only required migrating data from neighboring nodes.

This paper directly influenced: Apache Cassandra, Amazon DynamoDB, Riak, Voldemort, and most distributed caches and databases built after 2007.

---

## 2. Redis Cluster (10 minutes)

### How Redis Cluster Actually Works

Redis Cluster does not use a traditional consistent hashing ring. Instead, it uses a fixed number of **hash slots**: exactly 16,384 slots (0 to 16,383).

```
Key → CRC16(key) % 16384 → hash slot → node

Hash slot distribution across 3 nodes:
  Node A: slots 0-5460
  Node B: slots 5461-10922
  Node C: slots 10923-16383
```

When you add a 4th node, Redis Cluster migrates a subset of slots from existing nodes to the new node. You control which slots move.

```
After adding Node D:
  Node A: slots 0-4095
  Node B: slots 4096-8191
  Node C: slots 8192-12287
  Node D: slots 12288-16383
```

**Why 16,384 slots?**
- Large enough for up to 1,000 nodes (16 slots per node minimum).
- Small enough that the slot configuration can be transmitted as a compact bitmap (2KB).
- A fixed number simplifies the protocol — every node knows the complete slot map.

### Redis Cluster Limitations

| Limitation | Impact |
|---|---|
| **Multi-key operations** require all keys on the same slot | Use hash tags: `{event:123}:tickets` and `{event:123}:metadata` go to the same slot because of `{event:123}` |
| **Transactions** limited to keys on the same node | Design key structures to co-locate related data |
| **No cross-slot Lua scripts** | Lua scripts must operate on keys in the same slot |
| **Latency variance** increases with cluster size | More nodes = more potential hops for redirected queries |

### Hash Tags for Co-location

```
// Without hash tags:
event:123:tickets    → slot 7234 → Node B
event:123:metadata   → slot 1892 → Node A  (different node!)

// With hash tags:
{event:123}:tickets  → CRC16("event:123") % 16384 → same slot
{event:123}:metadata → CRC16("event:123") % 16384 → same slot!
```

Redis uses the content inside `{}` for the hash calculation. This guarantees co-location.

---

## 3. Design: TicketPulse's Cache Architecture (15 minutes)

### 📐 Design Exercise: Multi-Layer Cache

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Design a caching strategy for TicketPulse with three layers:

| Layer | Technology | Latency | Size | Scope |
|---|---|---|---|---|
| **L1** | In-process cache | Microseconds | Small (MB) | Per-instance |
| **L2** | Redis Cluster | Sub-millisecond | Large (GB) | Shared across instances |
| **L3** | CDN | Milliseconds | Huge (TB) | Global, public content only |

For each TicketPulse data type, decide which layers to use:

| Data | L1 (In-Process) | L2 (Redis) | L3 (CDN) | TTL | Why |
|---|---|---|---|---|---|
| Event metadata | ??? | ??? | ??? | ??? | ??? |
| Available ticket count | ??? | ??? | ??? | ??? | ??? |
| User session | ??? | ??? | ??? | ??? | ??? |
| Feature flags | ??? | ??? | ??? | ??? | ??? |
| Event images | ??? | ??? | ??? | ??? | ??? |
| Rate limiter counters | ??? | ??? | ??? | ??? | ??? |

**Reference Design:**

| Data | L1 | L2 | L3 | TTL | Reasoning |
|---|---|---|---|---|---|
| **Event metadata** | Yes | Yes | Yes | L1: 30s, L2: 5min, L3: 60s | Read-heavy, rarely changes. Cache everywhere. |
| **Available ticket count** | No | Yes | No | 5s | Changes frequently during sales. Short TTL. Must not serve stale counts from in-process cache during flash sales. |
| **User session** | No | Yes | No | 30min | Must be shared across instances. Cannot use L1 (sticky routing not guaranteed). |
| **Feature flags** | Yes | Yes | No | L1: 60s, L2: 5min | Read on every request. L1 avoids Redis round trip. Staleness of 60s is acceptable. |
| **Event images** | No | No | Yes | 24hr | Large binary data. CDN is purpose-built for this. |
| **Rate limiter counters** | No | Yes | No | 60s (window) | Must be shared across instances for accurate limiting. Redis atomic increments. |

### L1: In-Process Cache

```typescript
// Simple in-process cache with TTL (use a library like 'lru-cache' in production)
import { LRUCache } from 'lru-cache';

const l1Cache = new LRUCache<string, unknown>({
  max: 1000,          // max 1000 entries
  ttl: 30_000,        // 30 second TTL
  ttlAutopurge: true,
});

async function getEvent(eventId: string): Promise<Event> {
  const cacheKey = `event:${eventId}`;

  // L1: Check in-process cache
  const l1 = l1Cache.get(cacheKey);
  if (l1) return l1 as Event;

  // L2: Check Redis
  const l2 = await redis.get(cacheKey);
  if (l2) {
    const event = JSON.parse(l2);
    l1Cache.set(cacheKey, event); // Populate L1
    return event;
  }

  // L3 (CDN) is handled at the HTTP layer, not here

  // Cache miss: fetch from database
  const event = await db.events.findById(eventId);
  if (event) {
    await redis.set(cacheKey, JSON.stringify(event), 'EX', 300); // L2: 5 min
    l1Cache.set(cacheKey, event); // L1: 30s
  }

  return event;
}
```

**Why L1 matters:** Every Redis call takes ~0.5ms (network round trip within the same datacenter). On a hot path with 10 cache lookups per request, that is 5ms of pure network overhead. L1 eliminates this for frequently accessed data.

**The danger of L1:** Each application instance has its own L1. When data changes, L1 caches across instances are inconsistent until their TTL expires. Keep L1 TTLs short (10-60 seconds) and only use it for data where short-lived staleness is acceptable.

---

## 4. Cache Stampede Prevention (10 minutes)

### The Problem

When a popular cached key expires, hundreds of concurrent requests all get a cache miss simultaneously. They all hit the database at once. This is a **cache stampede** (also called thundering herd).

```
Time 0s: event:taylor-swift cached, 50,000 requests/sec served from cache
Time 300s: cache expires
Time 300.001s: 1,000 concurrent requests all miss cache
              → 1,000 simultaneous DB queries for the same data
              → Database overwhelmed
```

### Strategy 1: Distributed Lock (Mutex)

Only one request fetches from the database. Others wait for the result.

```typescript
async function getEventWithLock(eventId: string): Promise<Event> {
  const cacheKey = `event:${eventId}`;

  // Try cache first
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  // Acquire a lock
  const lockKey = `lock:${cacheKey}`;
  const acquired = await redis.set(lockKey, '1', 'NX', 'EX', 5); // Lock for 5 seconds

  if (acquired) {
    // We got the lock — fetch from DB
    try {
      const event = await db.events.findById(eventId);
      await redis.set(cacheKey, JSON.stringify(event), 'EX', 300);
      return event;
    } finally {
      await redis.del(lockKey);
    }
  } else {
    // Someone else is fetching — wait and retry
    await sleep(50); // 50ms
    return getEventWithLock(eventId); // Retry (add max retry limit)
  }
}
```

### Strategy 2: Probabilistic Early Expiration

Randomly refresh the cache before it actually expires. The closer to expiration, the higher the probability of a refresh.

```typescript
async function getEventWithEarlyExpiry(eventId: string): Promise<Event> {
  const cacheKey = `event:${eventId}`;
  const raw = await redis.get(cacheKey);

  if (raw) {
    const { data, expiresAt } = JSON.parse(raw);
    const ttlRemaining = expiresAt - Date.now();
    const totalTtl = 300_000; // 5 minutes

    // Probability of refresh increases as TTL decreases
    // At 10% remaining TTL, ~50% chance of refresh
    const probability = Math.exp(-1 * (ttlRemaining / totalTtl) * 5);

    if (Math.random() < probability) {
      // Refresh in background (don't await — serve stale immediately)
      refreshCache(eventId, cacheKey).catch(console.error);
    }

    return data;
  }

  // Full cache miss
  return refreshCache(eventId, cacheKey);
}
```

### Strategy 3: Never Expire (Background Refresh)

Popular keys never expire. A background process refreshes them periodically.

```typescript
// Background worker: refresh popular keys every 60 seconds
async function refreshPopularKeys(): Promise<void> {
  const popularEventIds = await getPopularEventIds(); // From analytics

  for (const eventId of popularEventIds) {
    const event = await db.events.findById(eventId);
    await redis.set(`event:${eventId}`, JSON.stringify(event), 'EX', 300);
  }
}

// Run every 60 seconds
setInterval(refreshPopularKeys, 60_000);
```

**For TicketPulse:** Use Strategy 1 (distributed lock) for general keys. Use Strategy 3 (background refresh) for the top 100 most popular events. These are predictable (events with upcoming dates, flash sales) and worth the extra infrastructure.

---

## 5. Reflect (5 minutes)

### 🤔 Questions

1. **TicketPulse runs 5 Redis Cluster nodes. One node crashes. What happens to the keys on that node?** How does Redis Cluster handle this? (Hint: replicas.)

2. **Your consistent hashing ring has 5 nodes with 150 virtual nodes each. You need to add 3 more nodes during a flash sale. What is the expected percentage of keys that will need to migrate?** Is this safe to do under load?

3. **An engineer proposes removing L2 (Redis) entirely and using only L1 (in-process) and L3 (CDN). What breaks?**

4. **TicketPulse has a hot key problem: `event:taylor-swift` gets 50,000 reads/second, all hitting the same Redis Cluster node. How do you distribute the load?** (Hint: read replicas, key replication, or client-side caching.)

### 🤔 Reflection Prompt

Now that you understand consistent hashing and multi-layer caching, revisit the CDN caching decisions from M64. How does the L1/L2/L3 hierarchy change your thinking about where to cache what?

---

## 6. Checkpoint

After this module, you should have:

- [ ] A working consistent hashing ring implementation (TypeScript or pseudocode)
- [ ] Simulated results: key distribution across 5 nodes, and key movement when adding a 6th
- [ ] Understanding of virtual nodes and why they improve distribution
- [ ] Understanding of Redis Cluster's 16,384 hash slots and hash tags
- [ ] A multi-layer cache design for TicketPulse (L1 in-process, L2 Redis, L3 CDN)
- [ ] Cache stampede prevention strategy implemented (distributed lock or probabilistic early expiry)
- [ ] Understanding of the Dynamo paper's influence on modern distributed systems

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Naive hashing** | `hash % N` remaps ~(N-1)/N keys when N changes. Causes cache avalanche. |
| **Consistent hashing** | Maps keys and servers to a ring. Adding/removing a server only moves ~1/N keys. |
| **Virtual nodes** | Each physical node gets 100-200 positions on the ring for even distribution. |
| **Redis Cluster** | Uses 16,384 fixed hash slots. Hash tags enable co-location of related keys. |
| **Multi-layer cache** | L1 (in-process, microseconds) → L2 (Redis, sub-ms) → L3 (CDN, milliseconds). |
| **Cache stampede** | Prevent with distributed locks, probabilistic early expiration, or background refresh. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Consistent hashing** | A hashing technique that minimizes key redistribution when the number of servers changes. Keys and servers are mapped to a ring. |
| **Virtual node (vnode)** | A technique where each physical node is represented by multiple points on the hash ring, improving distribution balance. |
| **Hash slot** | In Redis Cluster, one of 16,384 fixed slots. Each key maps to a slot, and each slot is assigned to a node. |
| **Hash tag** | In Redis Cluster, the substring inside `{}` in a key name that determines the hash slot. Used to co-locate related keys. |
| **Cache stampede** | When a popular cached key expires and many concurrent requests simultaneously hit the database. Also called thundering herd. |
| **L1/L2/L3 cache** | A multi-layer caching hierarchy. L1 is closest to the application (fastest, smallest). L3 is furthest (slowest, largest). |
| **Dynamo paper** | Amazon's 2007 paper describing a highly available key-value store using consistent hashing, vector clocks, and quorum reads/writes. |

---

## Further Reading

- DeCandia et al., ["Dynamo: Amazon's Highly Available Key-Value Store"](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) — the paper that popularized consistent hashing
- [Redis Cluster Specification](https://redis.io/docs/reference/cluster-spec/) — official Redis Cluster protocol documentation
- Karger et al., ["Consistent Hashing and Random Trees"](https://dl.acm.org/doi/10.1145/258533.258660) — the original 1997 paper
- Chapter 22 of the 100x Engineer Guide: Section 2.5 (Consistent Hashing), Section 6.3 (Consistent Hashing Ring)
- Chapter 1 of the 100x Engineer Guide: Section 2.2 (Sharding Strategies)

---

## What's Next

Next up: **[L3-M66: The Payment System](L3-M66-the-payment-system.md)** -- you will design the most critical system in TicketPulse, where bugs mean double-charging customers and idempotency is not optional.

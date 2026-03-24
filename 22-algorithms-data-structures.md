<!--
  CHAPTER: 22
  TITLE: Algorithms & Data Structures for Real Work
  PART: I — Foundations
  PREREQS: None
  KEY_TOPICS: hash maps, trees, graphs, bloom filters, consistent hashing, LRU cache, rate limiters, sorting, searching, Big-O, amortized analysis
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 22: Algorithms & Data Structures for Real Work

> **Part I — Foundations** | Prerequisites: None | Difficulty: Intermediate → Advanced

Not LeetCode grinding — the data structures and algorithms that backend engineers actually encounter in production systems, databases, and distributed infrastructure.

### In This Chapter
- Complexity Analysis That Matters
- Hash-Based Structures
- Tree Structures in Databases & Systems
- Graph Algorithms in Infrastructure
- Probabilistic Data Structures
- Practical Implementations
- Sorting & Searching in the Real World

### Related Chapters
- Ch 1 (consistent hashing, distributed systems)
- Ch 2 (B-trees, LSM trees, indexing)
- Ch 6 (lock-free data structures)

---

## 1. Complexity Analysis That Matters

Complexity analysis is not an academic exercise. It is how you predict whether your system will survive at 10x the current traffic. The difference between O(n) and O(n^2) is the difference between a 200ms response and a 20-minute timeout.

### 1.1 Big-O Refresher with Real-World Examples

Big-O describes how an operation's cost grows as the input size (n) increases. Here is every complexity class you will actually encounter in backend work:

| Complexity | Name | Real-World Example |
|---|---|---|
| O(1) | Constant | Hash map lookup, array index access, checking if a bit is set |
| O(log n) | Logarithmic | Binary search, B-tree index lookup in Postgres, finding an element in a balanced BST |
| O(n) | Linear | Scanning every row in a table without an index, iterating a linked list, `grep` through a file |
| O(n log n) | Linearithmic | Sorting query results (ORDER BY without an index), building a B-tree index from scratch |
| O(n^2) | Quadratic | Nested loop join without indexes, comparing every pair of items (naive deduplication) |

To put these in perspective with concrete numbers:

```
n = 1,000,000 (one million rows)

O(1)        →  1 operation
O(log n)    →  20 operations
O(n)        →  1,000,000 operations
O(n log n)  →  20,000,000 operations
O(n²)       →  1,000,000,000,000 operations  ← this kills your server
```

The jump from O(n) to O(n^2) is where systems fall over. A query that scans 1M rows in 100ms will take 100,000 seconds with an O(n^2) algorithm. This is the number one reason to add database indexes.

### 1.2 Amortized Analysis

Some operations are expensive occasionally but cheap on average. Amortized analysis accounts for this.

**Dynamic arrays (ArrayList, Go slices, Python lists)** are the canonical example:

```
Append operation:
- Usually O(1): write to the next empty slot
- Occasionally O(n): array is full, allocate 2x the space, copy everything over

But if the array doubles each time:
- After n appends, total work = n + n/2 + n/4 + n/8 + ... ≈ 2n
- Average cost per append = 2n / n = O(1) amortized
```

This matters in practice. When someone says "appending to a slice is O(1)," they mean amortized O(1). If you are building a system that cannot tolerate occasional latency spikes (say, a real-time trading system), you care about the worst case, not the amortized case. Pre-allocate your arrays.

**Hash map resize** follows the same pattern. When the load factor exceeds a threshold (typically 0.75), the map doubles its bucket count and rehashes every key. Individual inserts are O(1) amortized but occasionally O(n).

### 1.3 Space-Time Trade-offs

Almost every design decision in backend engineering is a space-time trade-off:

**Trading space for time (caching):**
- Database query cache: store result sets to avoid recomputation
- CDN: replicate content closer to users (more storage, less latency)
- Denormalization: store redundant data to avoid JOINs
- Materialized views: precompute expensive aggregations

**Trading accuracy for space (probabilistic structures):**
- Bloom filters: 1% false positive rate in 1MB vs exact set membership in 100MB
- HyperLogLog: count distinct elements with 0.81% error using 12KB vs exact count requiring O(n) memory
- Count-Min Sketch: approximate frequency counts in bounded memory

**Trading time for space (compression):**
- Gzip responses: spend CPU cycles to reduce bandwidth
- Column-oriented storage: compress similar values together
- Delta encoding: store differences instead of absolute values

### 1.4 Why Constants Matter

Big-O hides constant factors, but constants dominate at practical scales.

```
Algorithm A: O(n)     with constant factor 1000  → 1000n operations
Algorithm B: O(n²)    with constant factor 1     → n² operations

Crossover point: 1000n = n²  →  n = 1000

For n < 1000: Algorithm B is faster
For n > 1000: Algorithm A is faster
```

Real examples where constants matter:

- **Insertion sort vs quicksort for small arrays**: Insertion sort is O(n^2) but has tiny constants (no recursion, good cache locality). Most standard library sort implementations switch to insertion sort for arrays under 10-20 elements.
- **Hash map vs linear scan for small collections**: For fewer than ~10 elements, linear scan through an array beats a hash map because hash computation, memory indirection, and cache misses cost more than scanning a handful of elements.
- **B-tree fan-out**: A B-tree with node size matching a disk page (4KB) can store ~500 keys per node. A binary search tree stores 1 key per node. Same O(log n) lookup, but the B-tree does log_500(n) disk reads vs log_2(n). For 1 billion keys, that is 3 disk reads vs 30.

### 1.5 The Operations That Matter

For backend work, these are the operations you evaluate data structures against:

| Operation | Why It Matters |
|---|---|
| **Insert** | How fast can you write new data? (API writes, log ingestion, event processing) |
| **Lookup (point query)** | Find one record by key. The bread and butter of web applications. |
| **Range scan** | Find all records in a range. Time-series queries, pagination, analytics. |
| **Delete** | Remove data. Harder than it sounds — tombstones, compaction, fragmentation. |
| **Iterate (full scan)** | Process every element. Batch jobs, migrations, analytics. |

Different data structures optimize for different operations. There is no structure that is best at everything:

```
               Insert    Lookup    Range Scan    Delete    Iterate
Hash Map       O(1)*     O(1)*     O(n)          O(1)*     O(n)
B-Tree         O(log n)  O(log n)  O(log n + k)  O(log n)  O(n)
LSM-Tree       O(1)*     O(log n)  O(log n + k)  O(1)*     O(n)
Skip List      O(log n)  O(log n)  O(log n + k)  O(log n)  O(n)
Sorted Array   O(n)      O(log n)  O(log n + k)  O(n)      O(n)

* = amortized
k = number of elements in the range
```

---

## 2. Hash-Based Structures

Hash maps are the most important data structure in backend engineering. If you understand nothing else in this chapter, understand hash maps.

### 2.1 How Hash Maps Work Internally

A hash map is an array of "buckets" combined with a hash function:

```
put(key, value):
    1. Compute hash = hash_function(key)         # e.g., "user:123" → 0xA3F2...
    2. Compute index = hash % num_buckets         # e.g., 0xA3F2... % 16 = 7
    3. Store (key, value) in bucket[7]

get(key):
    1. Compute hash = hash_function(key)
    2. Compute index = hash % num_buckets
    3. Look in bucket[index] for matching key
    4. Return value (or "not found")
```

The hash function must be:
- **Deterministic**: same key always produces the same hash
- **Uniform**: keys should spread evenly across buckets
- **Fast**: hashing should be cheaper than the alternative (linear scan)

Common hash functions in practice:
- **MurmurHash3**: fast, good distribution, used by many hash map implementations
- **SipHash**: DoS-resistant (Python dicts, Rust HashMaps use it to prevent hash-flooding attacks)
- **xxHash**: extremely fast, used for checksums and non-cryptographic hashing
- **CityHash/FarmHash**: Google's fast hash families, optimized for short strings

### 2.2 Why Hash Maps Are O(1) Amortized

With a good hash function and reasonable load factor, most buckets contain 0 or 1 entries. The hash computation is O(1) (fixed work regardless of map size), and jumping to a bucket index is O(1) (array index access). Therefore, the expected lookup time is O(1).

But this is an average. In the worst case, every key hashes to the same bucket, and lookup degenerates to O(n) — scanning a linked list of all entries. This is why hash function quality matters, and why language runtimes use randomized hash seeds to prevent attackers from crafting collision-heavy inputs (hash-flooding DoS attacks).

**Load factor** = number of entries / number of buckets. When the load factor exceeds a threshold (typically 0.75 in Java, 6.5 average per bucket in Go), the map resizes — doubles the bucket count and rehashes every key. This is the O(n) operation that makes the amortized cost still O(1).

### 2.3 Hash Collisions: Chaining vs Open Addressing

When two keys hash to the same bucket, you have a collision. Two strategies:

**Chaining (separate chaining):**
```
bucket[7] → (key1, val1) → (key2, val2) → (key3, val3)

Each bucket is a linked list (or in Java 8+, a red-black tree if
the chain exceeds 8 elements).

Pros: Simple, load factor can exceed 1.0, deletion is easy
Cons: Pointer chasing (cache-unfriendly), extra memory for pointers
Used by: Java HashMap, Go map (with overflow buckets)
```

**Open addressing:**
```
Collision at bucket[7]?
- Linear probing:   try 7, 8, 9, 10, ...
- Quadratic probing: try 7, 7+1², 7+2², 7+3², ...
- Robin Hood hashing: linear probing, but swap entries to minimize
                      max probe distance (more fair distribution)

Pros: Cache-friendly (data in contiguous memory), no pointer overhead
Cons: Clustering (long probe sequences), deletion requires tombstones,
      load factor must stay below ~0.7
Used by: Python dict (open addressing with perturbation),
         Rust HashMap (Robin Hood → SwissTable),
         Google's Swiss Tables (SIMD-accelerated probing)
```

**In practice**: Modern high-performance hash maps use open addressing with SIMD instructions to probe multiple slots simultaneously (Google's SwissTable, adopted by Rust and Abseil C++). The cache-friendliness of open addressing wins on modern hardware.

### 2.4 Hash Sets

A hash set is simply a hash map where you only care about the keys (values are ignored or boolean). All the same internals apply.

Use cases you encounter constantly:
- **Deduplication**: `seen = set()` to skip already-processed records
- **Membership testing**: is this user ID in the blocklist?
- **Set operations**: intersection (common friends), union (merge results), difference (what changed?)

```python
# Deduplication during event processing
processed_ids = set()
for event in event_stream:
    if event.id in processed_ids:    # O(1) lookup
        continue                      # skip duplicate
    process(event)
    processed_ids.add(event.id)       # O(1) insert
```

### 2.5 Consistent Hashing

Standard hashing (`hash(key) % N`) falls apart when you add or remove servers. If N changes from 4 to 5, nearly every key maps to a different server — cache miss storm, mass data migration.

**Consistent hashing** fixes this by mapping both keys and servers onto a ring (0 to 2^32 - 1):

```
The Ring (0 to 2³²-1):

        ServerA(hash=1000)
           /
    ------*-----------
   /                   \
  |    key1(hash=800)   |
  |         ↓           |
  |    maps to ServerA  |
  |    (next server     |
  |     clockwise)      |
   \                   /
    ------*-----------
           \
        ServerB(hash=5000)

Rule: A key maps to the first server found going clockwise from
      the key's hash position on the ring.
```

**Virtual nodes** solve the problem of uneven distribution. Instead of placing each server once on the ring, place it 100-200 times (with different hash values). This smooths out the distribution:

```python
class ConsistentHashRing:
    def __init__(self, nodes=None, num_virtual=150):
        self.ring = {}              # hash_value → node
        self.sorted_keys = []       # sorted hash values for binary search
        self.num_virtual = num_virtual
        if nodes:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node):
        for i in range(self.num_virtual):
            virtual_key = f"{node}:vn{i}"
            hash_val = self._hash(virtual_key)
            self.ring[hash_val] = node
            self.sorted_keys.append(hash_val)
        self.sorted_keys.sort()

    def remove_node(self, node):
        for i in range(self.num_virtual):
            virtual_key = f"{node}:vn{i}"
            hash_val = self._hash(virtual_key)
            del self.ring[hash_val]
            self.sorted_keys.remove(hash_val)

    def get_node(self, key):
        if not self.ring:
            return None
        hash_val = self._hash(key)
        # Find first server clockwise (binary search for next largest hash)
        idx = bisect.bisect_right(self.sorted_keys, hash_val)
        if idx == len(self.sorted_keys):
            idx = 0  # wrap around the ring
        return self.ring[self.sorted_keys[idx]]

    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
```

**Why it minimizes redistribution**: When a server is added, it takes ownership of a portion of the ring from its clockwise neighbor. Only keys in that arc are reassigned — roughly `1/N` of all keys, not all of them. When a server is removed, its keys move to the next clockwise server.

**Used by**: Amazon DynamoDB (partition assignment), Apache Cassandra (token ring), Memcached client-side sharding, Nginx upstream consistent hashing, Akka Cluster Sharding.

### 2.6 Hash-Based Algorithms in Practice

**Deduplication at scale:**
```
Problem: Process 1 billion events, skip duplicates
Solution 1: Hash set in memory (requires ~16GB for 1B 128-bit hashes)
Solution 2: Bloom filter (1% false positive rate in ~1.2GB)
Solution 3: Hash to partition, deduplicate per partition (distributed)
```

**Counting distinct elements:**
```
Problem: How many unique users visited in the last 24 hours?
Exact: Store every user ID in a set → O(n) memory
Approximate: HyperLogLog → 12KB memory, 0.81% error (Redis PFCOUNT)
```

**Partitioning (how Kafka and DynamoDB assign data to shards):**
```
partition = hash(key) % num_partitions

Kafka: Messages with the same key always go to the same partition
       (guarantees ordering per key)
DynamoDB: hash(partition_key) determines which storage node holds the item
```

---

## 3. Tree Structures in Databases & Systems

Trees are how databases organize data on disk. If you understand B-trees and LSM-trees, you understand how virtually every database works under the hood.

### 3.1 Binary Search Trees (BST)

A BST maintains the invariant: left child < parent < right child. This gives O(log n) lookup, insert, and delete — but only if the tree is balanced.

```
Balanced BST (height = 3):          Degenerate BST (height = 5):

        4                            1
       / \                            \
      2   6                            2
     / \ / \                            \
    1  3 5  7                            3
                                          \
                                           4
                                            \
                                             5

Lookup: O(log n) = O(3)             Lookup: O(n) = O(5)
```

An unbalanced BST is just a linked list. This is why self-balancing trees exist.

### 3.2 Red-Black Trees and AVL Trees

Both are self-balancing BSTs that guarantee O(log n) height through rotation operations on insert and delete.

**Red-Black Trees:**
- Every node is red or black
- Root is black, leaves (NIL) are black
- Red nodes cannot have red children
- Every path from root to leaf has the same number of black nodes
- Guarantees: height <= 2 * log2(n+1)
- **Slightly less balanced** than AVL but **fewer rotations on insert/delete**

**AVL Trees:**
- Heights of left and right subtrees differ by at most 1
- Stricter balancing = faster lookups, but more rotations on modification
- **Better for read-heavy workloads**

**Where you encounter them:**
- `java.util.TreeMap`, `java.util.TreeSet` — Red-Black Tree
- `std::map`, `std::set` in C++ — typically Red-Black Tree
- Linux kernel `CFS` (Completely Fair Scheduler) — Red-Black Tree for process scheduling by virtual runtime
- In-memory ordered indexes in databases

You almost never implement these yourself. You use them through standard library ordered maps/sets when you need sorted iteration, range queries, or finding the min/max efficiently.

### 3.3 B-Trees: How Database Indexes Actually Work

B-Trees are the most important data structure in databases. Every time you create an index in Postgres or MySQL, you are building a B-Tree (technically, a B+ Tree).

**Why not a binary tree?** Disk I/O. A binary tree with 1 billion entries has height log2(10^9) = 30. That is 30 disk reads per lookup. A B-Tree with a branching factor of 500 (typical for 4KB pages) has height log500(10^9) = 3. Three disk reads to find any record among a billion.

**B-Tree node structure:**

```
Each node (= one disk page, typically 4KB or 8KB):

┌────────────────────────────────────────────────────┐
│ key1 │ key2 │ key3 │ ... │ keyN │                  │
│  ↓      ↓      ↓      ↓     ↓     ↓               │
│ ptr0  ptr1   ptr2   ptr3   ptrN  ptrN+1            │
└────────────────────────────────────────────────────┘

ptr0 → all keys < key1
ptr1 → all keys >= key1 and < key2
ptr2 → all keys >= key2 and < key3
...
```

**Lookup** walks from root to leaf, doing binary search within each node to pick the right child pointer. With pages cached in the buffer pool, the root and first few levels are almost always in memory, so a lookup typically does 1-2 actual disk reads.

**Insert** finds the correct leaf, inserts the key. If the leaf is full, it splits into two nodes and pushes the middle key up to the parent. Splits can cascade up but are rare.

**B+ Trees (what databases actually use):**

```
B-Tree: data stored in internal nodes AND leaves
B+ Tree: data stored ONLY in leaves; internal nodes are pure index

Internal nodes:  [  10  |  20  |  30  ]
                 /    |      |      \
Leaf nodes:  [1,5,8] → [10,12,15] → [20,22,28] → [30,35,40]
                 ↑           ↑            ↑            ↑
              linked list connecting all leaves

Advantages of B+ Trees:
1. Internal nodes hold more keys (no data pointers) → higher fan-out → shorter tree
2. Leaves form a linked list → range scans are sequential reads (fast!)
3. All lookups go to leaves → more predictable performance
```

**This is why `WHERE id BETWEEN 100 AND 200` is fast with an index**: the database finds leaf 100 via the tree, then follows the linked list to leaf 200, reading sequential pages.

**This is why `SELECT * FROM users ORDER BY created_at` is fast with an index on `created_at`**: the leaves are already in order, just scan the linked list.

### 3.4 LSM Trees: Write-Optimized Databases

B-Trees are optimized for reads (O(log n) with high fan-out). But every write to a B-Tree requires a random disk seek to find the right page. For write-heavy workloads (logging, time-series, event ingestion), this becomes a bottleneck.

**Log-Structured Merge Trees (LSM Trees)** optimize for writes by turning random writes into sequential writes:

```
Write path:

1. Write to WAL (Write-Ahead Log) on disk           ← sequential write (fast)
2. Write to MemTable (in-memory sorted structure)    ← in-memory (fast)
3. When MemTable is full → flush to SSTable on disk  ← sequential write (fast)

                ┌─────────────┐
  Writes ──→    │  MemTable   │  (sorted, in-memory, typically a skip list or red-black tree)
                │  (4MB-64MB) │
                └──────┬──────┘
                       │ flush when full
                       ▼
              ┌──────────────────┐
    Level 0:  │ SSTable │ SSTable │  (sorted, immutable files on disk)
              └────────┬─────────┘
                       │ compaction (merge sorted files)
                       ▼
              ┌───────────────────────────┐
    Level 1:  │ SSTable │ SSTable │ SSTable │  (10x larger than Level 0)
              └────────┬──────────────────┘
                       │ compaction
                       ▼
              ┌──────────────────────────────────────┐
    Level 2:  │ SSTable │ SSTable │ SSTable │ SSTable │  (10x larger)
              └──────────────────────────────────────┘
```

**Read path** (slower than B-Tree):
1. Check MemTable
2. Check each SSTable level (newest first), using Bloom filters to skip SSTables that definitely do not contain the key
3. Merge results

**Compaction** merges SSTables to:
- Remove deleted keys (tombstones)
- Remove older versions of updated keys
- Reduce the number of files to check on reads

**Write amplification**: a single write may be rewritten multiple times as it moves through compaction levels. If there are L levels and each is 10x larger, write amplification is ~10 * L.

### 3.5 B-Tree vs LSM-Tree

| Property | B-Tree | LSM-Tree |
|---|---|---|
| **Write throughput** | Moderate (random I/O) | High (sequential I/O) |
| **Read latency** | Low (1-3 disk reads) | Higher (check multiple levels) |
| **Range scans** | Fast (B+ tree leaf list) | Fast after compaction |
| **Space amplification** | Low (~page fill factor ~70%) | Can be high (multiple copies during compaction) |
| **Write amplification** | Moderate (page rewrites) | High (compaction rewrites) |
| **Predictable latency** | Yes | No (compaction spikes) |
| **Used by** | Postgres, MySQL (InnoDB), SQL Server | Cassandra, RocksDB, LevelDB, HBase, ScyllaDB |

**Rule of thumb**: B-Tree for read-heavy, mixed workloads (most web apps). LSM-Tree for write-heavy workloads (logging, metrics, time-series, IoT ingestion).

### 3.6 Tries (Prefix Trees)

A trie stores strings character-by-character along tree edges. Common prefix = shared path.

```
Storing: "cat", "car", "card", "do", "dog"

        (root)
        /    \
       c      d
       |      |
       a      o
      / \      \
     t   r      g
         |
         d

Lookup "car":  root → c → a → r  ✓ (3 steps, regardless of how many words are stored)
Lookup "cab":  root → c → a → ?  ✗ (no 'b' child)
```

**Where you encounter tries:**
- **Autocomplete / typeahead**: traverse the trie to the prefix, then enumerate all descendants
- **IP routing tables**: longest-prefix match on IP addresses (trie variant called a Patricia/Radix tree)
- **Spell checking**: traverse the trie to find similar words within edit distance
- **HTTP routers**: many web frameworks use radix trees for route matching (Go's `httprouter`)

### 3.7 Skip Lists

A skip list is a probabilistic alternative to balanced BSTs. It is a layered linked list where higher layers skip over elements, enabling O(log n) search.

```
Level 3: HEAD ─────────────────────────────────── 50 ──────────── NIL
Level 2: HEAD ────────── 20 ───────────────────── 50 ──── 70 ─── NIL
Level 1: HEAD ──── 10 ── 20 ──── 30 ──── 40 ──── 50 ──── 70 ─── NIL
Level 0: HEAD ─ 5─ 10 ── 20 ─ 25─ 30 ─ 35─ 40 ── 50 ─60─ 70 ─80 NIL

To find 35:
1. Start at Level 3 HEAD → 50 (too far) → stay at HEAD
2. Drop to Level 2 HEAD → 20 (ok) → 50 (too far) → stay at 20
3. Drop to Level 1: 20 → 30 (ok) → 40 (too far) → stay at 30
4. Drop to Level 0: 30 → 35 (found!)
```

Each element is promoted to the next level with probability p (typically 0.5 or 0.25). This gives O(log n) expected height and O(log n) expected search time.

**Why skip lists matter in practice:**
- **Redis sorted sets (ZSET)**: Uses a skip list for the ordered index. Chosen over red-black trees because skip lists are simpler to implement, easier to reason about concurrently, and range queries are natural (just walk the bottom level).
- **LevelDB / RocksDB MemTable**: The in-memory sorted structure before flushing to SSTables. Skip lists allow concurrent reads and writes without global locks.
- **MemSQL / SingleStore**: Uses lock-free skip lists for in-memory indexes.

Skip lists are easier to make concurrent than balanced BSTs because they avoid complex tree rotations — inserts only modify local pointers.

---

## 4. Graph Algorithms in Infrastructure

Graphs are everywhere in backend systems, even when you do not think of them as graphs:
- **Service dependency graph**: Service A calls Service B, which calls Service C
- **Database entity-relationship diagram**: Users have Orders, Orders have Items
- **Network topology**: Routers and switches connected by links
- **Permission model**: User is member of Group, Group has Role, Role grants Permission
- **Task dependencies**: Migration B depends on Migration A

### 4.1 Graph Representations

Two ways to store a graph:

**Adjacency List** (most common in practice):
```python
# Each node stores a list of its neighbors
graph = {
    "service-a": ["service-b", "service-c"],
    "service-b": ["service-d", "database"],
    "service-c": ["service-d", "cache"],
    "service-d": ["database"],
    "database":  [],
    "cache":     []
}

# Space: O(V + E)  — vertices + edges
# Check if edge exists: O(degree of vertex) — scan neighbor list
# Iterate neighbors: O(degree of vertex)
```

**Adjacency Matrix:**
```
              a  b  c  d  db  cache
service-a  [  0  1  1  0   0    0 ]
service-b  [  0  0  0  1   1    0 ]
service-c  [  0  0  0  1   0    1 ]
service-d  [  0  0  0  0   1    0 ]
database   [  0  0  0  0   0    0 ]
cache      [  0  0  0  0   0    0 ]

# Space: O(V²)
# Check if edge exists: O(1) — direct array lookup
# Iterate neighbors: O(V) — scan entire row
```

**When to use which:**
- **Adjacency list**: sparse graphs (most real systems), memory-efficient, better for traversal
- **Adjacency matrix**: dense graphs, or when you need O(1) edge existence checks (rare in backend work)

### 4.2 BFS (Breadth-First Search)

BFS explores all nodes at distance 1, then distance 2, then distance 3, and so on. It finds the shortest path in unweighted graphs.

```python
from collections import deque

def bfs_shortest_path(graph, start, target):
    """Find shortest path (fewest hops) between two nodes."""
    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        node, path = queue.popleft()

        if node == target:
            return path

        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None  # no path exists
```

**Where BFS is used:**
- **Social networks**: "degrees of separation" between users (LinkedIn's connection degree)
- **Service dependency blast radius**: "if service X goes down, what is affected within 2 hops?"
- **Network routing**: finding the fewest hops between two hosts
- **Garbage collection**: mark-and-sweep (BFS from root objects to find all reachable objects)

### 4.3 DFS (Depth-First Search)

DFS explores as deep as possible along each branch before backtracking. It is simpler to implement (naturally recursive) and uses less memory than BFS for deep graphs.

```python
def dfs(graph, node, visited=None):
    """Traverse all reachable nodes depth-first."""
    if visited is None:
        visited = set()
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(graph, neighbor, visited)
    return visited

def has_cycle(graph):
    """Detect cycles in a directed graph using DFS coloring."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}

    def dfs_visit(node):
        color[node] = GRAY           # currently being explored
        for neighbor in graph[node]:
            if color[neighbor] == GRAY:
                return True           # back edge = cycle!
            if color[neighbor] == WHITE:
                if dfs_visit(neighbor):
                    return True
        color[node] = BLACK           # fully explored
        return False

    return any(
        dfs_visit(node)
        for node in graph
        if color[node] == WHITE
    )
```

**Where DFS is used:**
- **Deadlock detection**: model lock waits as a directed graph; a cycle means deadlock
- **Circular dependency detection**: in module imports, service dependencies, database foreign keys
- **Topological sorting** (see below)
- **Connected components**: finding isolated clusters in a system

### 4.4 Topological Sort

A topological sort of a directed acyclic graph (DAG) produces a linear ordering where for every edge A → B, A appears before B. Only possible if the graph has no cycles.

```python
def topological_sort(graph):
    """Kahn's algorithm: BFS-based topological sort."""
    # Count incoming edges for each node
    in_degree = {node: 0 for node in graph}
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] += 1

    # Start with nodes that have no dependencies
    queue = deque([node for node in graph if in_degree[node] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(graph):
        raise ValueError("Graph has a cycle — topological sort impossible")

    return result
```

**Where topological sort is used:**
- **Database migrations**: Migration 003 depends on 002 depends on 001. Run them in topological order.
- **Build systems**: `make`, Bazel, and Gradle use topological sort to determine build order
- **Package managers**: `npm`, `pip`, `cargo` resolve dependency trees with topological sort
- **Task schedulers**: Airflow DAGs, CI/CD pipelines with step dependencies
- **Spreadsheet recalculation**: cells depend on other cells; recalculate in topological order

### 4.5 Dijkstra's Algorithm

BFS finds shortest paths when all edges have equal weight. Dijkstra handles weighted edges (as long as weights are non-negative):

```python
import heapq

def dijkstra(graph, start):
    """
    graph[node] = [(neighbor, weight), ...]
    Returns shortest distance from start to every reachable node.
    """
    distances = {start: 0}
    priority_queue = [(0, start)]      # (distance, node)

    while priority_queue:
        dist, node = heapq.heappop(priority_queue)

        if dist > distances.get(node, float('inf')):
            continue  # we already found a shorter path

        for neighbor, weight in graph[node]:
            new_dist = dist + weight
            if new_dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_dist
                heapq.heappush(priority_queue, (new_dist, neighbor))

    return distances
```

**Where Dijkstra is used:**
- **Network routing**: OSPF (Open Shortest Path First) protocol uses Dijkstra to compute shortest paths between routers
- **Cost optimization**: finding the cheapest cloud region-to-region data transfer path
- **Load balancing**: routing requests through the lowest-latency path
- **Game servers**: geographic routing to minimize player latency

### 4.6 Cycle Detection

Beyond the DFS coloring approach shown above, cycle detection is critical in:

- **Deadlock detection in databases**: Postgres maintains a wait-for graph. When a transaction waits for a lock held by another, an edge is added. A cycle means deadlock — Postgres aborts one of the transactions.
- **Circular dependency prevention**: module systems, microservice dependency validation
- **Reference counting garbage collection**: cycles of objects pointing to each other will never reach refcount 0. This is why Python uses a separate cycle-detecting GC alongside reference counting.

---

## 5. Probabilistic Data Structures

Sometimes you do not need an exact answer. Probabilistic data structures trade a small, bounded error rate for massive savings in memory and computation.

### 5.1 Bloom Filters

A Bloom filter answers the question: "Is this element in the set?"

- **"No"** — definitely not in the set (100% certain)
- **"Yes"** — probably in the set (might be a false positive)

**No false negatives, but possible false positives.**

**How it works:**

```
Initialize: m-bit array, all zeros
            k hash functions (h1, h2, ..., hk)

Insert("hello"):
    h1("hello") % m = 3   → set bit 3
    h2("hello") % m = 7   → set bit 7
    h3("hello") % m = 11  → set bit 11

    Bit array: [0 0 0 1 0 0 0 1 0 0 0 1 0 0 0 0]

Check("hello"):
    Check bits 3, 7, 11 → all set → "probably yes" ✓

Check("world"):
    h1("world") % m = 3   → set ✓
    h2("world") % m = 5   → NOT set ✗
    → "definitely no" (if any bit is 0, element was never inserted)

Check("xyz"):
    h1("xyz") % m = 3     → set ✓
    h2("xyz") % m = 7     → set ✓
    h3("xyz") % m = 11    → set ✓
    → "probably yes" — but this is a FALSE POSITIVE
       (all bits happen to be set by other elements)
```

**Tuning**: For a target false positive rate `p` with `n` elements:
- Optimal number of bits: `m = -n * ln(p) / (ln 2)^2`
- Optimal number of hash functions: `k = (m/n) * ln 2`
- For p = 1%, n = 1M: m = 9.6M bits (1.2MB), k = 7

```python
import mmh3  # MurmurHash3
from bitarray import bitarray

class BloomFilter:
    def __init__(self, size, num_hashes):
        self.size = size
        self.num_hashes = num_hashes
        self.bit_array = bitarray(size)
        self.bit_array.setall(0)

    def add(self, item):
        for i in range(self.num_hashes):
            idx = mmh3.hash(item, i) % self.size
            self.bit_array[idx] = 1

    def might_contain(self, item):
        return all(
            self.bit_array[mmh3.hash(item, i) % self.size]
            for i in range(self.num_hashes)
        )
```

**Where Bloom filters are used:**

| System | Use Case |
|---|---|
| **Cassandra** | Checks Bloom filter before reading an SSTable — avoids disk I/O for SSTables that definitely do not contain the key |
| **Google Chrome** | Checks URLs against a Bloom filter of known malicious URLs (a few MB instead of a multi-GB database) |
| **Akamai CDN** | Avoids caching one-hit-wonder URLs — only cache if the URL has been seen before (Bloom filter check) |
| **Medium** | Avoids recommending articles a user has already read |
| **Bitcoin** | SPV (Simplified Payment Verification) nodes use Bloom filters to request relevant transactions without downloading the full blockchain |

### 5.2 Count-Min Sketch

Estimates the frequency of elements in a stream using bounded memory.

```
Structure: d hash functions, each mapping to a row of w counters

Insert("cat"):
    h1("cat") % w = 2  → row1[2] += 1
    h2("cat") % w = 5  → row2[5] += 1
    h3("cat") % w = 1  → row3[1] += 1

Query frequency("cat"):
    return min(row1[2], row2[5], row3[1])
    (take the minimum to reduce over-counting from collisions)

         0   1   2   3   4   5   6
row 1: [ 0   0   3   1   0   0   0 ]  ← h1("cat")=2
row 2: [ 1   0   0   0   0   2   0 ]  ← h2("cat")=5
row 3: [ 0   4   0   0   1   0   0 ]  ← h3("cat")=1

min(3, 2, 4) = 2  (true count might be 2; never underestimates)
```

**Where Count-Min Sketch is used:**
- **Heavy hitters detection**: finding the most frequent API endpoints, most active users, hottest cache keys
- **Network monitoring**: detecting DDoS by finding source IPs with abnormally high request counts
- **Database query optimization**: approximate frequency statistics for query planning

### 5.3 HyperLogLog

Estimates the number of distinct elements (cardinality) in a dataset.

**The core insight**: if you hash elements uniformly and count the maximum number of leading zeros in any hash, that correlates with the log2 of the number of distinct elements.

```
Intuition:
- Hash every element to a uniform random binary string
- If you see a hash starting with 0...   → probably >= 2 distinct elements
- If you see a hash starting with 00...  → probably >= 4 distinct elements
- If you see a hash starting with 000... → probably >= 8 distinct elements
- If you see a hash starting with k zeros → probably >= 2^k distinct elements

Problem: High variance from a single estimate
Solution: Split into m buckets (registers), estimate per bucket, take harmonic mean

HyperLogLog with m=16384 (2^14) registers:
- Each register: 6 bits (max leading zeros in 64-bit hash)
- Total memory: 16384 * 6 bits = 12KB
- Error rate: 1.04 / sqrt(m) ≈ 0.81%
```

**Where HyperLogLog is used:**

| System | Use Case |
|---|---|
| **Redis `PFADD` / `PFCOUNT`** | Count unique visitors, unique IPs, unique events — 12KB per counter regardless of cardinality |
| **Google BigQuery** | `APPROX_COUNT_DISTINCT()` uses HyperLogLog++ |
| **Presto / Trino** | `approx_distinct()` for fast analytics |
| **Elasticsearch** | Cardinality aggregation |

```
# Redis example: count unique daily visitors
PFADD visitors:2026-03-24 "user:123"
PFADD visitors:2026-03-24 "user:456"
PFADD visitors:2026-03-24 "user:123"    # duplicate, no effect
PFCOUNT visitors:2026-03-24              # returns ~2

# Merge multiple days
PFMERGE visitors:week visitors:2026-03-18 visitors:2026-03-19 ... visitors:2026-03-24
PFCOUNT visitors:week                    # unique visitors across the entire week
```

### 5.4 Cuckoo Filters

Like Bloom filters but with two advantages:
1. **Support deletion** (Bloom filters do not — you cannot unset a bit shared by multiple elements)
2. **Better space efficiency** at low false positive rates (below ~3%)

Named after the cuckoo bird that displaces other birds' eggs from nests:

```
Two hash functions, two possible buckets per element.

Insert("hello"):
    bucket_a = h1("hello") = 4
    bucket_b = h2("hello") = 9

    If bucket 4 has space → store fingerprint of "hello" in bucket 4
    If bucket 9 has space → store fingerprint of "hello" in bucket 9
    If both full → kick out the existing element in bucket 4,
                   relocate it to its alternate bucket,
                   store "hello" in bucket 4
                   (may cascade, like cuckoo hashing)
```

**Use when**: you need Bloom filter functionality but also need to remove elements (e.g., a distributed blocklist that entries can be removed from).

---

## 6. Practical Implementations

These are the "system design building blocks" that come up repeatedly. Each one is a small system unto itself, combining multiple data structures.

### 6.1 LRU Cache

An LRU (Least Recently Used) cache evicts the least recently accessed entry when it reaches capacity. It requires O(1) for both `get` and `put`.

**The trick**: combine a hash map (O(1) key lookup) with a doubly linked list (O(1) move-to-front and remove-from-tail).

```
Hash Map:  key → pointer to linked list node
Doubly Linked List:  most recent ←→ ... ←→ least recent

get(key):
    1. Look up node in hash map          O(1)
    2. Move node to front of linked list  O(1) — just relink pointers
    3. Return value

put(key, value):
    1. If key exists: update value, move to front
    2. If key doesn't exist:
       a. If at capacity: remove tail node, delete from hash map
       b. Create new node, add to front, add to hash map
```

```python
class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}            # key → Node
        # Sentinel nodes simplify edge cases
        self.head = Node(0, 0)     # dummy head (most recent side)
        self.tail = Node(0, 0)     # dummy tail (least recent side)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key):
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)
        self._add_to_front(node)
        return node.value

    def put(self, key, value):
        if key in self.cache:
            self._remove(self.cache[key])
        node = Node(key, value)
        self._add_to_front(node)
        self.cache[key] = node
        if len(self.cache) > self.capacity:
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]

    def _add_to_front(self, node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
```

**Where LRU caches are used:**
- **Database buffer pool**: Postgres/MySQL keep frequently accessed disk pages in memory using an LRU-like policy (Postgres uses a clock-sweep algorithm, a cheaper approximation)
- **Web application caching**: in-process caches (Guava Cache, Caffeine in Java; `lru-cache` in Node.js)
- **CPU caches**: hardware LRU approximations for L1/L2/L3 cache eviction
- **Operating system page cache**: which disk pages to keep in RAM

### 6.2 Rate Limiter

#### Token Bucket

The token bucket is the most common rate limiting algorithm. Imagine a bucket that fills with tokens at a steady rate. Each request consumes a token. If the bucket is empty, the request is denied.

```
Bucket:
  - capacity: 10 tokens (max burst)
  - refill_rate: 2 tokens/second
  - tokens: current number of tokens
  - last_refill: timestamp of last refill

allow_request():
    now = current_time()
    elapsed = now - last_refill

    # Add tokens based on elapsed time
    tokens = min(capacity, tokens + elapsed * refill_rate)
    last_refill = now

    if tokens >= 1:
        tokens -= 1
        return True     # request allowed
    else:
        return False    # rate limited (429 Too Many Requests)
```

```python
import time

class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def allow(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

**Properties**: allows bursts (up to `capacity` requests at once), then rate-limits to `refill_rate` sustained throughput. Most APIs use this because it naturally handles bursty traffic.

#### Sliding Window Counter

Provides smoother rate limiting than fixed windows, without the memory overhead of tracking every individual request timestamp.

```
Fixed window problem:
    Window 1 (0:00-1:00): 100 requests (limit: 100/min)
    Window 2 (1:00-2:00): 100 requests
    But: 100 requests at 0:59 + 100 requests at 1:01 = 200 requests in 2 seconds!

Sliding window counter solution:
    Current window count + (previous window count * overlap percentage)

    At time 1:15 (15 seconds into window 2):
    Previous window (0:00-1:00): 84 requests
    Current window  (1:00-2:00): 36 requests so far

    Overlap of previous window: (60 - 15) / 60 = 75%
    Estimated count: 36 + (84 * 0.75) = 36 + 63 = 99

    If limit is 100 → allow (99 < 100)
```

```python
class SlidingWindowCounter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.prev_count = 0
        self.curr_count = 0
        self.curr_window_start = 0

    def allow(self):
        now = time.monotonic()
        window_start = now - (now % self.window)

        # Roll over to new window if needed
        if window_start != self.curr_window_start:
            self.prev_count = self.curr_count
            self.curr_count = 0
            self.curr_window_start = window_start

        # Calculate weighted count
        elapsed_in_window = now - window_start
        weight = (self.window - elapsed_in_window) / self.window
        estimated = self.curr_count + (self.prev_count * weight)

        if estimated < self.limit:
            self.curr_count += 1
            return True
        return False
```

#### Distributed Rate Limiting with Redis

For multi-server deployments, rate limit state must be shared. Redis is the standard solution:

```python
# Token bucket in Redis using a Lua script for atomicity
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])   -- tokens per second
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill tokens
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- Try to consume a token
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) * 2)
    return 1  -- allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) * 2)
    return 0  -- denied
end
"""
```

The Lua script runs atomically in Redis — no race conditions between multiple application servers checking and decrementing the counter.

### 6.3 Consistent Hashing Ring

(Detailed implementation covered in Section 2.5 above. Here we focus on the operational aspects.)

**Adding a node:**
```
Before: Nodes A, B, C on the ring
        A handles keys in range (C, A]
        B handles keys in range (A, B]
        C handles keys in range (B, C]

Add node D between A and B:
        A handles keys in range (C, A]     ← unchanged
        D handles keys in range (A, D]     ← takes from B
        B handles keys in range (D, B]     ← smaller range now
        C handles keys in range (B, C]     ← unchanged

Only keys in range (A, D] need to migrate from B to D.
With virtual nodes, this is ~1/N of all keys (evenly distributed).
```

**Removing a node:**
```
Remove node D:
        All keys in (A, D] transfer to B (the next node clockwise)
        Again, only ~1/N of keys move.
```

**Used in practice by:**
- **Amazon DynamoDB**: partition assignment across storage nodes
- **Apache Cassandra**: token ring for data distribution
- **Nginx**: `upstream` consistent hashing for sticky sessions
- **HAProxy**: `balance uri consistent` for cache-friendly load balancing

### 6.4 URL Shortener

Two approaches to generating short URLs:

#### Approach 1: Base62 Encoding from Auto-Increment ID

```python
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def encode_base62(num):
    """Convert integer to base62 string."""
    if num == 0:
        return ALPHABET[0]
    result = []
    while num > 0:
        result.append(ALPHABET[num % 62])
        num //= 62
    return ''.join(reversed(result))

def decode_base62(s):
    """Convert base62 string back to integer."""
    num = 0
    for char in s:
        num = num * 62 + ALPHABET.index(char)
    return num

# Database auto-increment ID → short code
# ID 1000000 → encode_base62(1000000) → "4c92"
# 6-character base62 → 62^6 = 56.8 billion possible URLs
```

**Write path**: Insert URL into database, get auto-increment ID, encode as base62, return short URL.

**Read path**: Decode base62 to ID, look up in database by primary key (O(1) with index), redirect.

**Pros**: Simple, guaranteed unique, predictable length.
**Cons**: Sequential IDs are predictable (user can enumerate URLs), requires centralized ID generation.

#### Approach 2: Hash-Based with Collision Handling

```python
import hashlib

def shorten(long_url):
    """Generate short code from URL hash."""
    hash_hex = hashlib.sha256(long_url.encode()).hexdigest()
    short_code = encode_base62(int(hash_hex[:12], 16))[:7]  # take first 7 chars

    # Check for collision
    existing = db.get(short_code)
    if existing and existing.long_url != long_url:
        # Collision! Append a counter and retry
        for i in range(1, 100):
            candidate = encode_base62(int(hash_hex[:12], 16) + i)[:7]
            if not db.get(candidate):
                short_code = candidate
                break

    db.put(short_code, long_url)
    return short_code
```

**Pros**: No centralized counter, same URL always generates same short code (idempotent).
**Cons**: Collision handling adds complexity, requires a read-before-write.

### 6.5 Distributed ID Generation

In distributed systems, you cannot rely on a single database auto-increment. Multiple machines need to generate unique IDs independently, often with ordering guarantees.

#### Snowflake IDs (Twitter's approach)

```
64-bit ID:

┌─ 1 bit ─┬─── 41 bits ────┬── 10 bits ──┬── 12 bits ──┐
│  unused  │  timestamp(ms) │  machine ID │  sequence   │
└──────────┴────────────────┴─────────────┴─────────────┘

- Timestamp: milliseconds since custom epoch
  → 2^41 ms ≈ 69 years before overflow
- Machine ID: 1024 unique workers (datacenter ID + worker ID)
- Sequence: 4096 IDs per millisecond per machine

Total capacity: 4096 * 1000 * 1024 ≈ 4 billion IDs per second cluster-wide
```

```python
import time

class SnowflakeGenerator:
    EPOCH = 1609459200000  # 2021-01-01 00:00:00 UTC in ms

    def __init__(self, machine_id):
        assert 0 <= machine_id < 1024
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1

    def next_id(self):
        timestamp = int(time.time() * 1000) - self.EPOCH

        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & 0xFFF  # 12-bit wrap
            if self.sequence == 0:
                # Exhausted 4096 IDs this millisecond — wait for next ms
                while timestamp == self.last_timestamp:
                    timestamp = int(time.time() * 1000) - self.EPOCH
        else:
            self.sequence = 0

        self.last_timestamp = timestamp

        return (
            (timestamp << 22) |
            (self.machine_id << 12) |
            self.sequence
        )
```

**Properties**: Roughly time-sorted (not perfectly — clock skew between machines), 64-bit (fits in a `bigint`), no coordination needed between machines.

**Used by**: Twitter (original Snowflake), Discord (modified Snowflake), Instagram (similar scheme).

#### UUIDv7 (Timestamp-Ordered UUIDs)

```
128-bit UUID (standard UUID format, but timestamp-prefixed):

xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx

First 48 bits: Unix timestamp in milliseconds
Next 4 bits:   version (7)
Next 12 bits:  random
Next 2 bits:   variant (RFC 4122)
Next 62 bits:  random

Example: 018e0a3c-5b00-7123-a456-789012345678
         ^^^^^^^^^^^^
         timestamp portion → IDs are naturally sorted by creation time
```

**Advantages over UUIDv4**:
- **Time-sortable**: B-tree indexes stay sequential (no random page splits)
- **Standard format**: works with any system that accepts UUIDs
- **No coordination**: pure random component ensures uniqueness without a central authority

**UUIDv4's problem with databases**: Random UUIDs cause random B-tree inserts, leading to poor cache utilization, excessive page splits, and index fragmentation. UUIDv7 fixes this by being monotonically increasing.

#### ULID (Universally Unique Lexicographically Sortable Identifier)

```
128-bit, encoded as 26-character Crockford's Base32:

01ARZ3NDEKTSV4RRFFQ69G5FAV

┌──── 48 bits ────┬──── 80 bits ────┐
│  timestamp(ms)  │    randomness   │
└─────────────────┴─────────────────┘

- Timestamp: milliseconds since Unix epoch
- Randomness: 80 bits of cryptographic randomness
- Lexicographically sortable (string comparison = time comparison)
- Case-insensitive, no special characters (URL-safe)
```

#### Comparison

| Property | Snowflake | UUIDv7 | ULID | UUIDv4 |
|---|---|---|---|---|
| **Size** | 64 bits | 128 bits | 128 bits | 128 bits |
| **Sortable by time** | Yes | Yes | Yes | No |
| **Coordination needed** | Machine ID assignment | No | No | No |
| **DB index friendly** | Yes | Yes | Yes | No (random) |
| **Standard format** | Custom | UUID | Custom (26 chars) | UUID |
| **IDs per ms per node** | 4096 | Unlimited (random) | Unlimited (random) | N/A |
| **Uniqueness guarantee** | Machine ID + sequence | Probabilistic | Probabilistic | Probabilistic |

**Guidance**: Use Snowflake (or a variant) when you need compact 64-bit IDs and can manage machine ID assignment. Use UUIDv7 when you need standard UUID compatibility. Use ULID when you want string-sortable IDs without UUID format constraints. Avoid UUIDv4 as a primary key in B-tree indexed databases.

---

## 7. Sorting & Searching in the Real World

You will almost never implement a sorting algorithm. But you must understand them because they determine how your database executes queries, how your files are organized, and where your performance bottlenecks are.

### 7.1 The Sorting Algorithms That Matter

#### QuickSort

```
1. Pick a pivot element
2. Partition: move elements < pivot to left, > pivot to right
3. Recursively sort left and right partitions

Average: O(n log n)   Worst: O(n²) — when pivot is always min/max
Space:   O(log n) stack depth
Stable:  No (equal elements may change relative order)
```

**Why it is the default**: Excellent cache locality (operates on contiguous memory), low constant factors, in-place (no extra array allocation). Most standard library `sort()` functions use QuickSort or a variant.

**The worst case**: If you always pick the first element as pivot and the array is already sorted, you get O(n^2). Modern implementations use median-of-three or random pivots to avoid this. IntroSort (used by C++ `std::sort`) switches to HeapSort if recursion depth exceeds 2*log(n), guaranteeing O(n log n) worst case.

#### MergeSort

```
1. Split array in half
2. Recursively sort each half
3. Merge the two sorted halves

Always:  O(n log n)   (no worst case degradation)
Space:   O(n) — needs a temporary array for merging
Stable:  Yes (equal elements maintain relative order)
```

**Why it matters**:
- **Stable sorting**: when you `ORDER BY created_at, name`, stability ensures that rows with the same `created_at` maintain their `name` ordering from the second sort pass
- **External sorting**: when data does not fit in memory, MergeSort is the only practical algorithm (see below)
- **Linked lists**: MergeSort is optimal for linked lists (no random access needed, O(1) extra space)

#### TimSort

```
1. Divide array into "runs" (already-sorted subsequences)
2. Extend short runs using insertion sort (to minimum run length, usually 32-64)
3. Merge runs using a modified merge sort with galloping mode

Always:  O(n log n) worst case
Best:    O(n) when data is already sorted or nearly sorted
Space:   O(n)
Stable:  Yes
```

**Why it is used by Python and Java**: Real-world data is often partially sorted (log entries, time-series data, nearly-sorted lists after a small update). TimSort exploits existing order and achieves near-O(n) performance on such inputs.

### 7.2 Binary Search

Binary search is the most useful algorithm you will actually write (or debug) in production code. It applies anywhere you have sorted data and need to find a boundary.

#### Standard Binary Search

```python
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2      # avoid integer overflow
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1  # not found
```

#### Finding Boundaries (Lower Bound / Upper Bound)

More useful than exact search in practice. "Find the first element >= X" or "find the last element <= X."

```python
def lower_bound(arr, target):
    """Find the index of the first element >= target."""
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo

def upper_bound(arr, target):
    """Find the index of the first element > target."""
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if arr[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo
```

**Where boundary search is used:**
- **Database range queries**: B-tree index finds the lower bound, then scans forward
- **Time-series data**: "find the first event after timestamp T"
- **Rate limiting sliding windows**: "find all requests in the last 60 seconds"
- **Version ranges**: "find the latest version <= 2.5"

#### Binary Search on Answer Space

This is the most powerful and under-appreciated application. Instead of searching in an array, you binary search on the possible answer range.

```python
def min_capacity_to_ship(weights, days):
    """
    Given packages with given weights and a deadline of D days,
    find the minimum ship capacity to deliver all packages on time.
    (This is a capacity planning problem.)
    """
    def can_ship_in_time(capacity):
        current_load = 0
        days_needed = 1
        for w in weights:
            if current_load + w > capacity:
                days_needed += 1
                current_load = 0
            current_load += w
        return days_needed <= days

    lo = max(weights)          # must carry at least the heaviest package
    hi = sum(weights)          # worst case: ship everything in one day
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if can_ship_in_time(mid):
            hi = mid           # try smaller capacity
        else:
            lo = mid + 1       # need more capacity
    return lo
```

**Real applications of binary search on answer space:**
- **Capacity planning**: "What is the minimum number of servers to handle this traffic?" (binary search on server count, simulate load for each)
- **SLA optimization**: "What is the lowest latency budget per service that still meets our end-to-end SLA?"
- **Batch size tuning**: "What is the largest batch size that still processes within the timeout?"
- **Resource allocation**: "What is the minimum memory allocation that avoids OOM for this workload?"

### 7.3 External Sorting

When your dataset does not fit in memory (sorting a 100GB file on a machine with 8GB RAM), you use external merge sort:

```
Phase 1: Create sorted runs
    1. Read 8GB chunk from disk into memory
    2. Sort in memory (quicksort)
    3. Write sorted chunk ("run") to disk
    4. Repeat until all data is processed
    → Result: ~13 sorted runs of 8GB each

Phase 2: K-way merge
    1. Open all 13 runs simultaneously
    2. Read a small buffer (e.g., 100MB) from each run
    3. Use a min-heap (priority queue) to find the smallest element
       across all runs
    4. Output the smallest, refill buffer when empty
    5. Continue until all runs are exhausted

    Heap size: 13 elements (one per run) — fits easily in memory
    I/O pattern: sequential reads from each run — disk-friendly
```

```python
import heapq

def external_sort(input_file, output_file, memory_limit):
    # Phase 1: Create sorted runs
    runs = []
    chunk = []
    chunk_size = 0

    for record in read_records(input_file):
        chunk.append(record)
        chunk_size += record.size
        if chunk_size >= memory_limit:
            chunk.sort(key=lambda r: r.sort_key)
            run_file = write_run(chunk)
            runs.append(run_file)
            chunk = []
            chunk_size = 0

    if chunk:  # remaining records
        chunk.sort(key=lambda r: r.sort_key)
        runs.append(write_run(chunk))

    # Phase 2: K-way merge
    readers = [open_run_reader(run) for run in runs]
    heap = []
    for i, reader in enumerate(readers):
        record = next(reader, None)
        if record:
            heapq.heappush(heap, (record.sort_key, i, record))

    with open(output_file, 'w') as out:
        while heap:
            _, run_idx, record = heapq.heappop(heap)
            out.write(record)
            next_record = next(readers[run_idx], None)
            if next_record:
                heapq.heappush(heap, (next_record.sort_key, run_idx, next_record))
```

**Where external sorting is used:**
- **Database `ORDER BY` on large result sets**: when the sort buffer (`work_mem` in Postgres, `sort_buffer_size` in MySQL) is too small, the database switches to external sort
- **MapReduce shuffle phase**: sorting intermediate key-value pairs before the reduce step
- **Log aggregation**: merging sorted log files from multiple servers into a single sorted stream
- **`sort` command**: Unix `sort` uses external merge sort for large files

### 7.4 How Database Sorting Works

When you write `SELECT * FROM orders ORDER BY created_at`, the database has three strategies:

**1. Index-ordered scan (best case):**
```
If there's a B+ tree index on created_at:
→ Just scan the leaf nodes in order (they're already sorted via the linked list)
→ No sorting needed!
→ Cost: O(n) sequential I/O

EXPLAIN: "Index Scan using idx_orders_created_at"
```

**2. In-memory sort (small result set):**
```
If the result fits in work_mem (default 4MB in Postgres):
→ Load all rows into memory
→ QuickSort
→ Return

EXPLAIN: "Sort  Sort Method: quicksort  Memory: 3412kB"
```

**3. External merge sort (large result set):**
```
If the result exceeds work_mem:
→ External merge sort using temp files on disk
→ Much slower due to disk I/O

EXPLAIN: "Sort  Sort Method: external merge  Disk: 145MB"

Fix: Increase work_mem (per-query) or add an index
SET work_mem = '256MB';
```

**This is why "add an index" is the answer to most performance questions.** An index transforms a sort operation from O(n log n) with potential disk I/O into a simple O(n) sequential scan.

---

## Summary: When to Use What

| Problem | Data Structure / Algorithm | Why |
|---|---|---|
| Key-value lookup | Hash map | O(1) average lookup |
| Ordered data, range queries | B+ Tree (database index) | O(log n) lookup + sequential range scan |
| Write-heavy ingestion | LSM Tree (Cassandra, RocksDB) | O(1) amortized writes, sequential I/O |
| Set membership at scale | Bloom filter | O(1) check, tiny memory footprint |
| Count distinct at scale | HyperLogLog | 12KB for billions of elements |
| Frequency estimation in streams | Count-Min Sketch | Bounded memory, no false negatives on count |
| In-memory cache with eviction | LRU Cache | O(1) get/put with bounded memory |
| Rate limiting | Token bucket / sliding window | Smooth rate enforcement with burst support |
| Distribute data across nodes | Consistent hashing | Minimal redistribution on node add/remove |
| Find boundary in sorted data | Binary search | O(log n), universally applicable |
| Sort data larger than memory | External merge sort | Disk-friendly, O(n log n) I/O operations |
| Task/build ordering | Topological sort | Respects dependencies, detects cycles |
| Shortest path (unweighted) | BFS | O(V + E), guarantees shortest |
| Shortest path (weighted) | Dijkstra | O((V + E) log V) with priority queue |
| Cycle/deadlock detection | DFS with coloring | O(V + E), finds back edges |
| Autocomplete, prefix matching | Trie / Radix tree | O(k) lookup where k = key length |
| Ordered set with concurrency | Skip list | O(log n), simpler concurrent access than trees |
| Distributed unique IDs | Snowflake / UUIDv7 / ULID | Time-sorted, no coordination, index-friendly |

The structures in this chapter are not interview trivia. They are the building blocks of every database, cache, load balancer, and distributed system you work with. Understanding them means you can read a Postgres `EXPLAIN` plan and know what is happening, choose the right database for your workload, debug performance problems from first principles, and design systems that scale.

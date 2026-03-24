<!--
  CHAPTER: 6
  TITLE: Concurrency, Parallelism & Computing Paradigms
  PART: II — Applied Engineering
  PREREQS: None
  KEY_TOPICS: threads, event loop, actors, CSP, coroutines, mutex, CAS, lock-free, deadlock, race conditions, memory models, GC, SOLID, functional programming
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 6: Concurrency, Parallelism & Computing Paradigms

> **Part II — Applied Engineering** | Prerequisites: None (standalone, but Ch 1 helps) | Difficulty: Advanced

How computers do many things at once — concurrency models, synchronization primitives, common pitfalls, memory models, and the programming paradigms that tame complexity.

### In This Chapter
- Concurrency Models
- Concurrency Primitives
- Concurrency Patterns
- Concurrency Problems
- Distributed Computing Paradigms
- Memory & Performance
- Programming Paradigms
- Choosing the Right Model

### Related Chapters
- Chapter 1 (distributed computing extends concurrency)
- Chapter 11 (language-specific concurrency)
- Chapter 4 (performance engineering)

---

## 1. CONCURRENCY MODELS

### Thread-Based (Java, C++, C#)
OS threads, shared memory, preemptive scheduling. ~1MB stack per thread.
**Use for:** CPU-bound parallelism, legacy frameworks.
**Watch for:** Deadlocks, race conditions, context switch overhead.

### Event Loop (Node.js, Python asyncio, Nginx)
Single thread, non-blocking I/O, poll-based dispatch. All logic on one thread.
**Use for:** I/O-bound workloads, 10K+ concurrent connections, real-time apps.
**Watch for:** CPU-bound work blocks everything. Use worker threads/processes for compute.

### Actor Model (Erlang/OTP, Akka, Orleans)
Independent actors, private state, async message passing, supervision hierarchies. "Let it crash."
**Use for:** Fault-tolerant systems, natural entity decomposition (users, devices, sessions).
**Real-world:** WhatsApp (2M connections/server), Halo game services (Orleans virtual actors).

### CSP — Communicating Sequential Processes (Go)
Goroutines (lightweight, ~2-8KB) + typed channels. "Share memory by communicating."
**Use for:** Pipelines, concurrent services, structured concurrency.
**Real-world:** Kubernetes controllers, Go HTTP servers (goroutine per request).

### Coroutines / Green Threads
Language-runtime managed, cooperative yielding. Stackful (Go, Java virtual threads) or stackless (Rust async, Kotlin, Python async).
**Use for:** Synchronous-looking async code. Java 21 virtual threads are a game changer for I/O-bound apps.

### Reactive Streams (RxJava, Project Reactor)
Data flows through pipelines with built-in backpressure. Rich operator library.
**Use for:** Streaming data, when backpressure is critical.
**Watch for:** Steep learning curve, unreadable stack traces.

---

## 2. CONCURRENCY PRIMITIVES

| Primitive | What It Does | Use When |
|---|---|---|
| **Mutex** | Exclusive access to critical section | Protecting shared mutable state |
| **Semaphore** | Allow up to N concurrent accesses | Resource pool limiting (DB connections) |
| **RWLock** | Multiple readers OR one writer | Read-heavy shared data (caches, config) |
| **Condition Variable** | Sleep until condition is met | Producer-consumer queues |
| **Atomic Operations** | CPU-level indivisible operations | Simple counters, flags, reference counts |
| **CAS (Compare-and-Swap)** | "If X is A, set to B" atomically | Lock-free algorithms |

### Lock-Free Data Structures
Built on CAS. No deadlock, better worst-case latency. Extremely hard to implement correctly.
Examples: Michael-Scott queue, Treiber stack, ConcurrentHashMap.

### Memory Barriers
Enforce ordering on memory operations. Acquire (no reorder before), Release (no reorder after), SeqCst (total order).
**Critical:** x86 is forgiving; ARM/POWER are not. Code to the language memory model, not the hardware.

---

## 3. CONCURRENCY PATTERNS

| Pattern | Description | Use Case |
|---|---|---|
| **Producer-Consumer** | Producers → buffer → consumers | Decoupling ingestion from processing |
| **Reader-Writer** | Multiple concurrent readers, exclusive writers | Caches, config stores |
| **Thread Pool** | Fixed set of pre-created threads pulling from queue | Default for most servers |
| **Work Stealing** | Idle workers steal from others' queues | Irregular/recursive workloads |
| **Fork-Join** | Recursive split → parallel execute → merge | Divide-and-conquer algorithms |
| **Pipeline** | Stages run concurrently, data flows through | ETL, video encoding |
| **Scatter-Gather** | Fan-out to N workers → gather results | Searching shards, calling multiple services |

---

## 4. CONCURRENCY PROBLEMS

| Problem | Description | Prevention |
|---|---|---|
| **Race Condition** | Behavior depends on thread timing | Locks, atomics, immutability |
| **Deadlock** | Circular wait on resources | Global lock ordering, tryLock with timeout |
| **Livelock** | Active but no progress (mutual yielding) | Randomized backoff |
| **Starvation** | Thread never gets resource | Fair locks, priority inheritance |
| **Priority Inversion** | High-priority blocked by low-priority | Priority inheritance protocol |
| **ABA Problem** | CAS succeeds but value was changed and changed back | Tagged pointers, version counters |
| **False Sharing** | Unrelated data on same cache line causes thrashing | Pad to cache line boundaries (64 bytes) |
| **Thundering Herd** | Many threads wake but only one can proceed | Wake-one, EPOLLEXCLUSIVE, single-flight |

---

## 5. DISTRIBUTED COMPUTING PARADIGMS

**MapReduce:** Map (transform each record) → Shuffle (redistribute by key) → Reduce (aggregate per key). Being supplanted by Spark/Flink.

**BSP (Bulk Synchronous Parallel):** Supersteps: compute → communicate → barrier. For graph algorithms, scientific simulations.

**Dataflow Programming:** DAG of computations. Node executes when inputs ready. Flink, TensorFlow, Apache Beam.

**Stream Processing Semantics:**
- **At-most-once:** May lose messages. Simplest.
- **At-least-once:** May duplicate. Use idempotent processing.
- **Exactly-once:** At-least-once + idempotency OR transactional processing (Kafka transactions, Flink checkpointing).

---

## 6. MEMORY & PERFORMANCE

### Memory Models
**JMM:** "Happens-before" relationships. `volatile` = visibility + ordering. `synchronized` = mutual exclusion + visibility.
**C++11:** Six memory orderings from `relaxed` to `seq_cst`. Fine-grained control, deep expertise required.

### NUMA Awareness
Multi-socket: local memory fast, remote memory 1.5-3x slower. Pin threads to NUMA nodes. JVM: `-XX:+UseNUMA`.

### Zero-Copy
Transfer data without kernel↔user space copies. `sendfile()`, `splice()`, `mmap()`. Kafka uses sendfile for consumer reads.

### Garbage Collection (JVM)

| Collector | Pause Target | Use Case |
|---|---|---|
| **G1 GC** | Configurable (~200ms) | General purpose (default since Java 9) |
| **ZGC** | Sub-millisecond | Ultra-low-latency (trading, real-time) |
| **Shenandoah** | Sub-millisecond | Low-latency (RedHat JDK) |
| **Parallel GC** | Throughput-optimized | Batch processing |

---

## 7. PROGRAMMING PARADIGMS

### Functional Programming for Backends
- **Immutability:** No synchronization needed. Eliminates data races.
- **Pure functions:** Same input → same output. Trivially parallelizable, testable, memoizable.
- **Monads for errors:** `Option/Maybe` (no null), `Result/Either` (no exceptions). Compose with `flatMap`.

### OOP — SOLID Principles
| Principle | Meaning |
|---|---|
| **S** — Single Responsibility | One class, one reason to change |
| **O** — Open/Closed | Open for extension, closed for modification |
| **L** — Liskov Substitution | Subtypes must be substitutable for base types |
| **I** — Interface Segregation | No client depends on methods it doesn't use |
| **D** — Dependency Inversion | Depend on abstractions, not concretions |

### Reactive Programming
Data streams + backpressure. Strategies: buffer, drop, throttle, request-based pull.

---

## Choosing the Right Model

| Scenario | Approach |
|---|---|
| High-concurrency I/O (10K+ conn) | Event loop or virtual threads |
| CPU-bound parallel compute | Thread pool + work stealing |
| Distributed fault-tolerant system | Actor model |
| Data pipeline with clear stages | CSP (channels) or pipeline parallelism |
| Streaming data + backpressure | Reactive streams |
| Simple request-response server | Thread pool (or virtual threads Java 21+) |
| Latency-sensitive system | Lock-free + NUMA-aware + ZGC |

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

Here is a truth that takes most engineers years to fully appreciate: your computer is lying to you about time.

When you write `counter++` in a multi-threaded program, you probably imagine one clean operation: read the value, add one, write it back. But the CPU is actually doing three separate things — and between any two of those steps, another thread can swoop in, perform its own read-add-write, and silently overwrite your work. Both threads believe they incremented the counter. The counter says otherwise. Nobody panicked. No exception was thrown. The number is just wrong, and somewhere downstream a balance sheet doesn't add up, or a rate limiter lets through twice as many requests as it should, or a payment gets processed twice.

Concurrency bugs are the most humbling category of engineering problems. They don't reproduce consistently. They disappear the moment you add a log statement. They only manifest under load, at 3 AM, on the one day your senior engineer is on vacation. And they're usually not caused by someone being careless — they're caused by someone who didn't fully internalize how CPUs, caches, compilers, and operating systems actually work.

That's what this chapter is about. Not just "here are the primitives," but "here is the mental model that makes the primitives click." Once you understand why concurrency is hard, the solutions stop feeling like arbitrary rules you have to memorize and start feeling like satisfying puzzle solutions.

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

## 1. Concurrency Models

Before we talk about *how* to handle concurrency, let's talk about the fundamentally different *philosophies* for handling it. These aren't just different libraries or APIs — they're different mental models for how you think about your program's structure.

### The Core Tension

Every concurrency model is trying to solve the same underlying tension: you have multiple things that need to happen, and some of them need to happen at the same time, but some of them also need to coordinate. The coordination is where things get complicated. The different models are really different answers to the question: *where do you put the coordination logic?*

### Thread-Based Concurrency (Java, C++, C#)

The oldest model, and still the most widely used by sheer market share. The operating system gives you threads — independent execution contexts that share the same memory space. The OS schedules them, pauses them, resumes them. You don't control the timing; the scheduler does.

This model maps directly onto the hardware. Modern CPUs have multiple cores, and OS threads are how your program puts those cores to work. If you have a matrix multiplication that takes four seconds on one core, you can genuinely cut it to one second by splitting the work across four threads. That's real parallelism — four cores, four operations, happening simultaneously.

The cost is that "shared memory" means exactly that. Every thread can read and write every variable. You don't have to do anything special to share data — it's shared by default. This is convenient right up until it isn't, because it means every piece of mutable state is a potential hazard. You need to protect it explicitly with locks, and locks are where the classic disasters live: deadlocks, starvation, priority inversion.

Each OS thread also comes with roughly a 1MB stack. That means you can't have a million of them — at a thousand threads, you're already burning a gigabyte of RAM just on stacks, before your application has done anything. For I/O-bound workloads where most threads spend their time waiting, this overhead is deeply wasteful.

**Use threads for:** CPU-bound parallelism where you want to saturate multiple cores. Legacy frameworks that were built around this model. Any situation where you're genuinely compute-bound, not I/O-bound.

**Watch out for:** Deadlocks when you acquire locks in different orders. Race conditions on any state that multiple threads can modify. Context switch overhead when you have many more threads than cores.

### Event Loop (Node.js, Python asyncio, Nginx)

Someone looked at thread-based concurrency and asked: "What if instead of blocking a thread while we wait for I/O, we just... registered a callback and moved on?"

The event loop model is beautifully simple in concept. There's one thread. It runs an infinite loop. In each iteration, it checks whether any pending I/O operations have completed, runs the callbacks for ones that have, then checks again. Your code never blocks — when you make a database call, you hand off a callback and go do something else. The database result comes back, your callback fires, you process it.

This model handles I/O-bound concurrency with extraordinary efficiency. An Nginx server can handle 10,000 simultaneous connections on a single thread because most of those connections are just waiting — waiting for the client to send data, waiting for a database query, waiting for a file to be read. The CPU isn't sitting idle while waiting; it's serving other connections. No thread stack overhead, no context switching — just one tight loop dispatching work as it arrives.

The catch is both obvious and subtle. The obvious part: if any piece of your code runs for too long synchronously, everything else stops. The event loop is single-threaded; it can only do one thing at a time. A CPU-intensive operation — image processing, cryptography, a tight computation loop — will block the loop and make every other pending request wait. This is why Node.js applications use worker threads or child processes for heavy computation.

The subtle part: callback-based code has historically been painful to reason about. The "callback hell" problem — deeply nested callbacks creating code that's nearly impossible to follow — was the original motivation for promises, and then async/await. Modern event-loop code written with async/await reads synchronously (which is nice), but it still executes on a single thread (which you must remember).

**Use event loops for:** I/O-bound workloads, 10,000+ concurrent connections, real-time applications (chat, live updates), proxies, gateways, any situation where you're mostly waiting.

**Watch out for:** CPU-bound work that blocks the loop. Forgetting that `await` only yields when there's actual async work — you can still write blocking synchronous code inside an async function.

#### What Actually Happens When 10,000 Connections Arrive

This is a scenario worth tracing through both models, because the numbers are striking.

**Thread-per-connection model (classic Apache):**

```
10,000 connections arrive
→ 10,000 OS threads created
→ 10,000 × 1MB stack = 10GB RAM just for thread stacks
→ Each thread context-switch: ~1-10 microseconds
→ With 10K threads, the scheduler is burning significant CPU just deciding who runs next
→ Most threads are blocked on I/O, achieving nothing useful
→ System bogs down around 1,000-5,000 threads on typical hardware
```

**Event-loop model (Nginx, Node.js):**

```
10,000 connections arrive
→ 1 thread, 1 event loop, 10,000 file descriptors registered with epoll/kqueue
→ Memory: ~kilobytes per connection for the socket buffer
→ When connection 1's data arrives, epoll returns it
→ Callback fires, processes the data, kicks off async I/O, returns to loop
→ Loop immediately handles the next ready event
→ CPU is only busy when there's actually work to do
→ 10,000 connections handled with ~10MB overhead, not 10GB
```

The C10K problem (can a server handle 10,000 concurrent connections?) was a famous 1999 engineering challenge. The event loop model solved it. Nginx regularly handles 100K+ concurrent connections on a single machine. The thread model can't compete on I/O-bound workloads — not because threads are bad, but because threads were designed for CPU parallelism, not I/O concurrency.

The punchline: **threads give you parallelism; event loops give you concurrency.** They're solving different problems. If you have 10,000 database connections all waiting for results, you don't need 10,000 CPU cores — you just need a way to track 10,000 pending operations and dispatch callbacks when they complete. That's the event loop.

### Actor Model (Erlang/OTP, Akka, Orleans)

What if you gave up on shared memory entirely?

The actor model makes a radical choice: actors have no shared state at all. Each actor is a little world unto itself — private state, a mailbox, a behavior. Actors communicate exclusively by sending messages. There's no way to reach into another actor's memory. If you want data from an actor, you send it a message and wait for a reply.

This eliminates an entire category of bugs. You can't have a race condition on an actor's state because only that actor touches it. You can't deadlock on a lock you don't hold. The concurrency problems in an actor system are different (and often more tractable) than the ones in a threaded system.

The supervision hierarchy is the other killer feature. Erlang actors can be arranged in trees: supervisors at the branches, workers at the leaves. When a worker crashes — and the philosophy is "let it crash" rather than trying to handle every error defensively — the supervisor detects it and restarts it. This is how Erlang systems achieve the legendary "nine nines" uptime. It's not that individual components never fail; it's that failure is isolated and recovery is automatic.

#### The WhatsApp Story

WhatsApp's infrastructure is one of the most cited proofs of concept for the actor model at scale. In 2012, they were serving 450 million users with a team of 32 engineers. Each WhatsApp server ran Erlang and handled roughly **2 million simultaneous TCP connections** per machine. At the time, most messaging systems required many more servers to handle the same load.

How? Each user connection was an Erlang process (actor). Each user session was an actor. Each message routing decision was actor-to-actor messaging. When a connection dropped, its actor died and its supervisor restarted a fresh one. No shared mutable state meant no synchronization overhead. No synchronization overhead meant the system scaled almost linearly with hardware.

When Facebook acquired WhatsApp in 2014 for $19 billion, they had 55 engineers total and served 700 million users. The ratio of users-to-engineers was extraordinary precisely because the actor model's fault isolation made the system self-healing — engineers weren't paged at 3 AM because a session actor crashed and caused cascading failures. It crashed, restarted, and the user's phone reconnected without them noticing.

#### The Akka Story (Lightbend / Reactive Microservices)

Akka brought the actor model to the JVM ecosystem. LinkedIn used Akka to power real-time data pipelines at scale. The Kafka project itself was built at LinkedIn, and its internal architecture for handling partition leadership, consumer group coordination, and metadata management borrowed actor-like patterns.

The more vivid story is from the gaming world. Microsoft's **Azure PlayFab** (acquired from a gaming backend startup) uses an Orleans-based actor model for game session management. Each game session, each player inventory, each leaderboard entry is an actor (called a "grain" in Orleans). When 10 million players are online simultaneously, you have 10 million+ active grains. Grains that haven't been active for a while are deactivated and their state is persisted. When a player returns, their grain is reactivated from storage. The runtime handles all of this transparently.

The key insight: **the actor model matches the problem shape of stateful entities.** If your system is fundamentally about things that have identity and state — users, sessions, devices, game characters, bank accounts — then an actor per entity is architecturally natural. One actor owns one entity's state. No one else touches it. Coordination happens through messages.

The trade-off is message passing overhead and the different mental model. Synchronous-feeling operations become asynchronous conversations. Simple mutations become message exchanges. For some problems this is natural; for others it feels like bureaucracy.

**Use actors for:** Fault-tolerant distributed systems, systems with natural entity decomposition (users, devices, sessions, game state), any situation where isolated failure and automatic recovery are more important than raw throughput.

**Watch out for:** Message passing overhead for fine-grained operations. Debugging message flows can be harder than debugging a call stack.

### CSP — Communicating Sequential Processes (Go)

Go took a different approach to the "no shared memory" insight: instead of actors with mailboxes, give programmers goroutines (lightweight threads) and channels (typed communication pipes). The mantra is: *"Don't communicate by sharing memory; share memory by communicating."*

Goroutines are extremely lightweight compared to OS threads — a goroutine starts at around 2-8KB of stack space and can grow dynamically. The Go runtime multiplexes thousands of goroutines onto a small pool of OS threads. This means you can spawn a goroutine per request in a server and it's totally fine at 100,000 concurrent requests in a way it never would be with OS threads.

Channels are the coordination mechanism. When a goroutine sends on a channel, it blocks until something receives. When a goroutine receives from a channel, it blocks until something sends. This blocking-by-default makes data flow explicit and visible in the code structure. You can see the synchronization points.

```go
// A simple pipeline: generator → squarer → printer
func main() {
    naturals := make(chan int)
    squares := make(chan int)

    go func() {
        for x := 0; ; x++ {
            naturals <- x  // blocks until someone receives
        }
    }()

    go func() {
        for {
            x := <-naturals  // blocks until something sends
            squares <- x * x
        }
    }()

    for {
        fmt.Println(<-squares)
    }
}
```

This style — stages connected by channels — is natural for pipelines, data processing, and service logic. Kubernetes controllers are almost entirely built this way.

**Use CSP for:** Pipelines where data flows through processing stages, concurrent services with clear producer-consumer relationships, structured concurrency where you want explicit coordination points.

**Watch out for:** Channel direction and buffering choices have subtle performance and correctness implications. Goroutine leaks (goroutines blocked on channels that will never receive) are a real problem in long-running services.

### Coroutines and Green Threads

Threads are expensive. Event loops are limiting. What if there were a middle path — thousands of concurrent "threads" that are managed by the language runtime rather than the OS, and that can yield cooperatively rather than being preempted?

This is the idea behind coroutines and green threads. The key distinction is **stackful** vs. **stackless**:

**Stackful coroutines** (Go goroutines, Java virtual threads) have their own call stacks and can be suspended at any point — even deep inside a call chain. You can `yield` from a function that called a function that called a function. The runtime saves the entire stack and restores it later. Go goroutines work this way, which is why any goroutine can block on a channel without blocking an OS thread.

Java 21's virtual threads are a massive deal for the Java ecosystem specifically. Before virtual threads, Java's threading model was one-to-one with OS threads, which meant you paid the 1MB stack overhead for every thread. With virtual threads, you can run millions of them. The existing blocking I/O APIs — JDBC, file I/O, all the synchronous code that Java's ecosystem is built on — "just works" with virtual threads without any rewriting. An application that would have needed a reactive framework can now use plain blocking code and achieve the same scalability.

**Stackless coroutines** (Rust `async/await`, Kotlin coroutines, Python `asyncio`) work differently. The compiler transforms `async` functions into state machines at compile time. The function can only suspend at explicit `await` points — not deep inside arbitrary call chains. This makes them more efficient (smaller state to save) but more restrictive (async infects the call tree; calling an async function from a non-async context requires careful handling).

**Use coroutines/virtual threads for:** Writing synchronous-looking code that is actually asynchronous under the hood. Java 21+ virtual threads are particularly compelling for I/O-heavy Java apps that don't want to rewrite everything with reactive frameworks.

### Reactive Streams (RxJava, Project Reactor)

What if data was a river, not a bucket?

Reactive streams treat data as a continuous flow that can be transformed, filtered, merged, and split. The programming model is functional and declarative: you describe *what* you want to happen to the data, and the framework handles threading, buffering, and backpressure.

Backpressure is the critical concept here. A naive producer-consumer system can easily overwhelm a slow consumer — the queue fills up, you run out of memory, the process dies. Reactive streams build backpressure into the protocol. A consumer tells the producer how many items it can handle. The producer doesn't produce more until capacity is available. This makes the system self-regulating.

The operator libraries (RxJava's operators, Project Reactor's Flux/Mono) let you express complex async transformations concisely:

```java
// Read from Kafka, transform, write to database — all with backpressure
Flux.from(kafkaConsumer)
    .filter(event -> event.getType().equals("purchase"))
    .flatMap(event -> enrichFromDatabase(event))  // async, parallel
    .buffer(100)  // batch 100 items at a time
    .flatMap(batch -> saveToDatabase(batch))       // async batch write
    .subscribe();
```

The cost is real: reactive code has a steep learning curve, stack traces are nearly unreadable when something goes wrong, and the programming model is fundamentally different from imperative code. Many teams have found that Java virtual threads give them the scalability benefits without the cognitive overhead.

**Use reactive streams for:** Streaming data pipelines where backpressure is critical, systems that need rich stream transformation operators, Spring WebFlux-based services where the ecosystem is already reactive.

**Watch out for:** The learning curve is steep. Error handling in reactive chains is different from try/catch. Stack traces can be nightmarish.

---

## 2. Concurrency Primitives

Every concurrency model eventually bottoms out in primitives — the low-level building blocks that the higher-level abstractions are made of. Even if you're using actors or channels, understanding these is essential for knowing what's actually happening underneath.

### Mutex — The Bouncer

A mutex (mutual exclusion lock) is conceptually simple: only one thread can hold it at a time. If you try to acquire a mutex that's held, you wait. This is how you protect a critical section — a piece of code that accesses shared state.

```java
// Without mutex: race condition
counter++;  // NOT atomic: read, add, write

// With mutex: protected
lock.lock();
try {
    counter++;  // now atomic with respect to other threads holding the same lock
} finally {
    lock.unlock();
}
```

The tricky part isn't using a mutex — it's using it *consistently*. Every path that touches the shared state must hold the lock. One missed call site and you've broken the invariant. This is why higher-level abstractions like `synchronized` blocks in Java or `with lock:` in Python exist — they make it harder to accidentally forget to release.

#### The Dining Philosophers: A Modern Framing

The dining philosophers problem was invented by Dijkstra in 1965 as a teaching tool, but it maps almost perfectly onto a class of real production bugs you will encounter.

The original setup: five philosophers sit at a round table. Between each adjacent pair is one fork (five forks total). A philosopher either thinks (no resources needed) or eats (needs both the fork to their left and the fork to their right). Since forks are shared, two adjacent philosophers can't eat simultaneously.

The naive code:

```python
def philosopher(id, left_fork, right_fork):
    while True:
        think()
        left_fork.acquire()   # pick up left fork
        right_fork.acquire()  # pick up right fork
        eat()
        right_fork.release()
        left_fork.release()
```

This deadlocks. Every philosopher picks up their left fork simultaneously. Now every philosopher is waiting for their right fork — which is held by their right neighbor, who is waiting for *their* right fork, and so on around the table. Circular wait. Everyone starves.

**Modern equivalent:** You have five microservices, each of which needs to hold a distributed lock on two resources before processing. Service A holds lock "payments" and waits for "inventory". Service B holds "inventory" and waits for "notifications". Service C holds "notifications" and waits for "payments". Classic circular deadlock, played out across RPC calls instead of forks.

**The classic fix — global lock ordering:**

```python
def philosopher(id, left_fork, right_fork):
    # Always acquire the lower-numbered fork first
    first, second = sorted([left_fork, right_fork], key=lambda f: f.id)
    while True:
        think()
        first.acquire()
        second.acquire()
        eat()
        second.release()
        first.release()
```

If every philosopher acquires locks in the same global order (by fork ID), the circular wait cannot form. Philosopher 4 will try to acquire fork 0 before fork 4, breaking the cycle. This principle — **always acquire multiple locks in a consistent global order** — is one of the most important rules in concurrent systems engineering.

**The modern fix — resource hierarchy or timeout:**

In distributed systems where you can't always control lock acquisition order, use `tryLock` with a timeout and backoff:

```python
def philosopher(id, left_fork, right_fork):
    while True:
        think()
        while True:
            if left_fork.try_acquire(timeout=100ms):
                if right_fork.try_acquire(timeout=100ms):
                    break  # got both
                left_fork.release()  # give up, retry
            sleep(random_jitter())  # avoid livelock
        eat()
        right_fork.release()
        left_fork.release()
```

The randomized jitter prevents livelock — without it, all philosophers could retry in lockstep, repeatedly grabbing and releasing forks without ever getting to eat (just as in the hallway collision analogy).

### Semaphore — The Capacity Controller

A semaphore generalizes a mutex. Instead of "only one thread at a time," a semaphore says "up to N threads at a time." This makes it perfect for resource pool management.

Imagine you have a database connection pool with a maximum of 20 connections. A semaphore initialized to 20 lets up to 20 threads acquire connections concurrently. Thread 21 blocks until one of the 20 finishes and releases. This is the exact mechanism behind most connection pool implementations.

A semaphore with N=1 is functionally equivalent to a mutex, though there's a subtle difference: a mutex has the concept of ownership (only the thread that locked it can unlock it), while a semaphore can be released by any thread.

### RWLock — The Librarian

A read-write lock recognizes an asymmetry that a plain mutex ignores: reading shared state doesn't conflict with other reads, only with writes. If you have a configuration object that's read thousands of times per second but only updated occasionally, making every read operation exclusive is unnecessarily conservative.

An RWLock allows multiple concurrent readers *or* one exclusive writer. Readers never block each other. Writers wait for all readers to finish. Reads wait for any active writer.

```go
var config Config
var mu sync.RWMutex

// Many goroutines can do this concurrently:
func readConfig() Config {
    mu.RLock()
    defer mu.RUnlock()
    return config
}

// Only one goroutine can do this at a time, and readers wait:
func updateConfig(newConfig Config) {
    mu.Lock()
    defer mu.Unlock()
    config = newConfig
}
```

This pattern is everywhere: caches, routing tables, in-memory indexes, feature flag stores. If your workload is 99% reads and 1% writes, an RWLock can dramatically reduce contention.

**Watch out for:** Write starvation. If readers are always present, a writer may never get exclusive access. Some implementations have "write preference" to prevent this.

### Condition Variable — The Appointment Setter

A condition variable solves a specific problem: "I need to wait until some condition is true, but I don't want to burn a CPU core spinning in a loop checking."

The classic use case is a bounded queue in a producer-consumer system. A producer should wait if the queue is full. A consumer should wait if the queue is empty. When the state changes, the appropriate thread should wake up.

```java
// Producer waits while queue is full
while (queue.isFull()) {
    notFull.await();  // releases lock and sleeps
}
queue.add(item);
notEmpty.signal();  // wake a waiting consumer

// Consumer waits while queue is empty
while (queue.isEmpty()) {
    notEmpty.await();  // releases lock and sleeps
}
T item = queue.remove();
notFull.signal();  // wake a waiting producer
```

The critical detail: condition variables must be used with a mutex, and the condition must be checked in a loop (not an if statement). Spurious wakeups — a thread waking up even though the condition wasn't signaled — are real and must be handled.

### Atomic Operations — The Cheat Code

Some operations are so common — incrementing a counter, swapping a flag, updating a pointer — that CPUs have dedicated hardware support for doing them atomically. No locks required. The CPU itself guarantees that the operation is indivisible.

```java
// This is NOT atomic (read-modify-write, three operations):
counter++;

// This IS atomic (single CPU instruction with lock prefix on x86):
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();  // always correct, even with a thousand threads
```

Atomics are fantastic for simple cases: counters, flags, reference counts. They're significantly faster than mutexes for these use cases because they don't involve OS-level thread suspension. Under low contention, an atomic increment is just a single CPU instruction.

### CAS — Compare-And-Swap

CAS (Compare-And-Swap) is the atomic operation that makes lock-free algorithms possible. The idea: "If the value at this memory location is X, change it to Y. If it's not X, do nothing. Either way, tell me what you found."

```
bool CAS(int* ptr, int expected, int desired) {
    if (*ptr == expected) {
        *ptr = desired;
        return true;
    }
    return false;
}
```

This is a single atomic operation at the CPU level. You can build surprisingly sophisticated data structures on top of it. The typical pattern is "optimistic" — you read the current value, compute the new value, then atomically swap only if the value hasn't changed since you read it. If it has changed (some other thread got there first), you retry.

```java
// Atomic increment using CAS:
int current, next;
do {
    current = value.get();
    next = current + 1;
} while (!value.compareAndSet(current, next));
// If CAS fails, retry with the new current value
```

**Lock-Free Data Structures** are built this way. The Michael-Scott queue, the Treiber stack, Java's `ConcurrentHashMap` — all built on CAS loops. The appeal: no deadlock (you can always make progress), better worst-case latency (no thread ever blocks indefinitely). The cost: much harder to implement correctly. The ABA problem (more on this shortly) lurks here.

#### The CAS Retry Loop: Step by Step

The CAS retry loop is worth stepping through slowly, because it's the foundation of all lock-free programming and the subtle parts are easy to miss.

Here's the goal: implement a thread-safe `max` operation — atomically update a value to be the maximum of its current value and a new candidate.

**Why this is hard without CAS:**

```java
// NOT thread-safe
void updateMax(AtomicLong value, long candidate) {
    if (candidate > value.get()) {   // read
        value.set(candidate);         // write  ← another thread can modify between read and write
    }
}
```

Between the `get()` and the `set()`, another thread can also do a `set()` with a higher value, which we'd then overwrite with a smaller one. Classic race.

**The CAS retry loop:**

```java
void updateMax(AtomicLong value, long candidate) {
    long current;
    do {
        current = value.get();            // Step 1: Read current value
        if (candidate <= current) return; // Step 2: If candidate isn't bigger, nothing to do
        // Step 3: Try to atomically swap current → candidate
        // This only succeeds if value is still `current` at the moment of the swap.
        // If another thread changed value between Step 1 and Step 3, CAS returns false
        // and we loop back to Step 1 to re-read.
    } while (!value.compareAndSet(current, candidate));
}
```

Walk through a three-thread scenario:

```
Initial value: 5

Thread A: reads current = 5, candidate = 10
Thread B: reads current = 5, candidate = 7
Thread C: reads current = 5, candidate = 3

Thread A: CAS(5 → 10) succeeds. Value is now 10.
Thread B: CAS(5 → 7) FAILS — value is 10, not 5. Loop.
          re-reads current = 10. 7 <= 10 → returns early (correct, 10 > 7)
Thread C: CAS(5 → 3) FAILS — value is 10, not 5. Loop.
          re-reads current = 10. 3 <= 10 → returns early (correct, 10 > 3)
```

Final value: 10. Correct, with zero locks.

**What makes a retry loop safe vs. a spinning loop:**

A spinning loop holds no resources and can always retry. A CAS retry is progress-safe — each failed CAS means *some other thread* succeeded. The system as a whole is always making progress, even if your thread specifically is retrying. This is the lock-free guarantee: no thread can prevent other threads from making progress.

Under high contention, retry loops can be wasteful (many CPUs spinning on the same memory location). The practical threshold: CAS loops are excellent for a few dozen threads. Beyond that, contention on a single atomic variable becomes a bottleneck and you want either finer-grained structures or coordination (semaphores, queues).

### Memory Barriers — The Secret Third Thing

Here's the part that surprises most engineers: CPUs and compilers are allowed to reorder memory operations. For performance reasons, a modern out-of-order CPU doesn't necessarily execute instructions in the order you wrote them. The compiler may also reorder stores and loads. This is mostly invisible in single-threaded code (the result is always equivalent) but becomes a real problem in multi-threaded code.

Memory barriers (also called memory fences) are instructions that tell the CPU and compiler: "Don't reorder past this point."

- **Acquire barrier:** No memory operation after this point can be moved before it. Used when you're "taking ownership" — e.g., after acquiring a lock, you must see all writes made by the previous owner.
- **Release barrier:** No memory operation before this point can be moved after it. Used when you're "giving up ownership" — e.g., before releasing a lock, all your writes must be visible to the next owner.
- **Sequential consistency (SeqCst):** Total ordering — everyone sees memory operations in the same order.

The practical advice: **code to the language memory model, not the hardware.** x86 CPUs have a relatively strong memory model — they don't reorder stores past stores — which means many concurrency bugs don't manifest on x86 even when they're technically incorrect. ARM and POWER have weaker memory models, so code that "works" on an x86 development machine can fail catastrophically on an ARM production server. If you're writing lock-free code in Java, use `volatile` and the Java Memory Model semantics. In C++, use the appropriate `std::memory_order`. Don't assume x86 behavior.

---

## 3. Concurrency Patterns

With the primitives in hand, there are well-known patterns for how to combine them. These are the recurring solutions that show up across nearly every concurrent system.

### Producer-Consumer

The most fundamental concurrency pattern. One or more threads *produce* work items; one or more threads *consume* them; a shared buffer sits in between.

Why does this matter? Because production and consumption almost never happen at the same rate. A network server might receive requests in bursts. A database writer might be slower than the request rate. The buffer absorbs the mismatch and lets both sides operate at their own pace.

The buffer is a bounded queue (use a bounded queue — an unbounded one will eat your memory during a traffic spike). The producer blocks when the queue is full. The consumer blocks when it's empty. A condition variable coordinates the blocking and waking.

This is the backbone of almost every message queue, thread pool, and async processing system. Kafka is essentially a distributed, durable, highly scalable producer-consumer queue.

### Reader-Writer

Many concurrent data structures are read far more often than they're written. A routing table. A cache. A feature flag store. An in-memory index. For these, the Reader-Writer pattern uses an RWLock to allow concurrent reads while serializing writes. The pattern is simple but the performance improvement can be dramatic.

### Thread Pool

Creating and destroying OS threads is expensive. Spawning a new thread for each unit of work — each HTTP request, each task, each query — would crush a busy server under thread creation overhead.

The solution: create a fixed number of threads at startup, keep them alive, and feed work to them via a shared queue. This is the thread pool pattern, and it's what virtually every server framework uses under the hood. Java's `ExecutorService`, Python's `ThreadPoolExecutor`, .NET's `ThreadPool` — all thread pools.

Choosing the right pool size is genuinely nuanced. CPU-bound work: `N_threads = N_cpus` (maybe N+1 to keep CPUs busy during occasional blocking). I/O-bound work: much larger pools are appropriate because threads spend most of their time waiting rather than executing.

### Work Stealing

Regular thread pools have a problem with irregular workloads. If one thread gets stuck on a long task, the other threads finish their work early and sit idle while the pool's queue is empty. You have unused compute capacity sitting next to a bottleneck.

Work stealing fixes this. Each thread has its own local queue. When a thread finishes its local work, it can "steal" tasks from the end of another thread's queue. This keeps all threads busy and naturally load-balances across irregular workloads.

Work stealing is the algorithm behind Java's `ForkJoinPool`, Rust's Rayon library, and Go's goroutine scheduler. It's particularly effective for recursive divide-and-conquer algorithms where subtasks have unpredictable sizes.

### Fork-Join

For divide-and-conquer algorithms, the Fork-Join pattern is the standard template:

1. **Fork:** Split the problem into subproblems. Spawn parallel tasks for each.
2. **Join:** Wait for all subtasks to complete. Merge their results.

```java
class MergeSort extends RecursiveAction {
    void compute() {
        if (size <= THRESHOLD) {
            sequentialSort();  // small enough: do it here
            return;
        }
        MergeSort left = new MergeSort(left_half);
        MergeSort right = new MergeSort(right_half);
        invokeAll(left, right);  // fork: run both in parallel
        merge(left, right);       // join: combine results
    }
}
```

The recursion continues until subproblems are small enough to handle sequentially. Work stealing makes this efficient — threads that finish their subtrees early steal work from threads that are still splitting.

### Pipeline

A pipeline arranges stages of processing so they can run concurrently. Stage 1 processes item 0 while Stage 2 processes item 1 while Stage 3 processes item 2 — like an assembly line where every station is always busy.

In Go, pipelines are expressed naturally with channels:

```go
// Each stage is a goroutine, connected by channels
decoded := decode(rawBytes)    // goroutine 1: decode
filtered := filter(decoded)    // goroutine 2: filter
encoded := encode(filtered)    // goroutine 3: re-encode
```

This is the natural model for ETL processes, video transcoding pipelines, compilers (lexing → parsing → type-checking → code generation), and stream processing systems.

### Scatter-Gather

Fan out to N workers, collect all results, combine them. This is how search engines work: scatter a query to all shards in parallel, gather the results, merge and rank. It's also how microservice aggregation works: one request triggers parallel calls to multiple backend services, and the response is assembled from all of them.

The tricky part is handling partial failure. If you scatter to 10 shards and 2 are slow, do you wait? Set a timeout? Return partial results? These are design questions with no universal answer, but the scatter-gather pattern at least makes the structure explicit.

---

## 4. Concurrency Problems

Now for the failure modes. These are the things that go wrong when concurrent code isn't written carefully. Each one has a specific shape, specific causes, and specific preventions.

### Race Conditions

A race condition occurs when the correctness of a program depends on the relative timing of operations across threads. Two threads race to perform some operation, and the outcome depends on who wins.

Imagine two goroutines both reading a bank balance, deciding it's positive, and initiating a withdrawal. The read → check → debit is not atomic. Both goroutines see the pre-debit balance, both approve the withdrawal, and you've just let someone overdraft their account.

```
Thread A: read balance (100)
Thread B: read balance (100)
Thread A: balance > 0? Yes. Debit 100. Write 0.
Thread B: balance > 0? Yes. Debit 100. Write -100.  ← race condition
```

Prevention: make the check-and-debit atomic using a lock, or use an atomic compare-and-swap. Or, at the architecture level, use a single-threaded actor for each account — no concurrent writes possible.

Tools like Go's race detector (`go test -race`) and Java's Thread Sanitizer can detect race conditions at runtime. Use them in your test suite. Always.

#### Race Condition: A Full Worked Example

Here's a race condition you could reasonably write in a production system, how to detect it, and three ways to fix it.

**The bug — a naive rate limiter:**

```go
type RateLimiter struct {
    requests int
    limit    int
    window   time.Time
}

func (r *RateLimiter) Allow() bool {
    now := time.Now()
    if now.After(r.window) {
        r.requests = 0                       // reset counter
        r.window = now.Add(time.Second)      // new window
    }
    if r.requests >= r.limit {
        return false
    }
    r.requests++                             // increment counter
    return true
}
```

This looks reasonable. But it's not thread-safe. The check-then-act on `r.requests` is not atomic. With concurrent requests:

```
Thread A: reads r.requests = 99  (limit = 100)
Thread B: reads r.requests = 99
Thread A: 99 < 100 → increments to 100, returns true
Thread B: 99 < 100 → increments to 100, returns true ← both allowed!
          (but r.requests is now 100, not 101 — the increment raced too)
```

In fact it's worse: `r.requests++` is three operations (read, add, write), so you can also get lost increments, making the counter less than the true number of requests seen.

**Step 1: Detect it with the race detector:**

```bash
go test -race ./...
```

Output:
```
WARNING: DATA RACE
Write at 0x00c000018050 by goroutine 7:
  RateLimiter.Allow()
      ./ratelimiter.go:18

Previous write at 0x00c000018050 by goroutine 6:
  RateLimiter.Allow()
      ./ratelimiter.go:18

Goroutine 7 (running) created at:
  TestConcurrentRateLimit()
```

The race detector catches it immediately. This is why you run tests under `-race` in CI — not just locally, not just occasionally, but on every push.

**Fix 1: Mutex (simplest, often fine):**

```go
type RateLimiter struct {
    mu       sync.Mutex
    requests int
    limit    int
    window   time.Time
}

func (r *RateLimiter) Allow() bool {
    r.mu.Lock()
    defer r.mu.Unlock()

    now := time.Now()
    if now.After(r.window) {
        r.requests = 0
        r.window = now.Add(time.Second)
    }
    if r.requests >= r.limit {
        return false
    }
    r.requests++
    return true
}
```

One mutex, all reads and writes protected. Simple, correct. Performance is fine for most use cases — a mutex acquisition under low contention is ~20-30ns.

**Fix 2: Atomic counter (higher throughput, no window reset logic):**

```go
type RateLimiter struct {
    requests atomic.Int64
    resetAt  atomic.Int64   // unix nano
    limit    int64
}

func (r *RateLimiter) Allow() bool {
    now := time.Now().UnixNano()
    resetAt := r.resetAt.Load()
    
    if now > resetAt {
        // Try to be the one to reset the window (only one goroutine should win)
        if r.resetAt.CompareAndSwap(resetAt, now+int64(time.Second)) {
            r.requests.Store(0)
        }
    }
    
    return r.requests.Add(1) <= r.limit
}
```

This uses atomics for lock-free operation. Higher throughput under extreme contention, but more complex and has subtle edge cases (multiple goroutines can race on the window reset even with the CAS — production rate limiters often use Redis or a dedicated counter service for this reason).

**Fix 3: Actor model (single goroutine owns the state):**

```go
type rateLimiterMsg struct {
    reply chan bool
}

type RateLimiter struct {
    ch chan rateLimiterMsg
}

func NewRateLimiter(limit int) *RateLimiter {
    rl := &RateLimiter{ch: make(chan rateLimiterMsg, 100)}
    go func() {
        requests := 0
        window := time.Now().Add(time.Second)
        for msg := range rl.ch {
            if time.Now().After(window) {
                requests = 0
                window = time.Now().Add(time.Second)
            }
            allowed := requests < limit
            if allowed { requests++ }
            msg.reply <- allowed
        }
    }()
    return rl
}

func (r *RateLimiter) Allow() bool {
    reply := make(chan bool, 1)
    r.ch <- rateLimiterMsg{reply: reply}
    return <-reply
}
```

No shared state, no locks — a single goroutine owns all the state and processes requests sequentially. This is the actor model at micro-scale. It's never wrong about thread safety because only one goroutine ever touches the variables.

The lesson: there are usually multiple correct solutions to a race condition. The mutex solution is easiest to understand. The atomic solution is fastest under contention. The actor solution is architecturally cleanest. Choose based on your performance requirements and team familiarity.

### Deadlock

A deadlock occurs when two or more threads are each waiting for a resource held by the other, and none can proceed.

```
Thread A holds Lock 1, waits for Lock 2
Thread B holds Lock 2, waits for Lock 1
→ Neither can proceed. Forever.
```

This is the concurrency equivalent of two cars on a one-lane bridge, each waiting for the other to back up. Nobody backs up. Traffic stops.

The canonical prevention: **establish a global lock ordering.** If every thread in the system acquires locks in the same order (always Lock 1 before Lock 2, never the reverse), the circular wait is impossible. This requires discipline and documentation, because the order must be consistent across every code path.

The pragmatic alternative: `tryLock` with a timeout. Instead of blocking indefinitely, a thread tries to acquire the lock and gives up after N milliseconds. If it gives up, it releases all its current locks and retries. Combined with jitter on the retry delay, this breaks most deadlocks in practice (though it can mask real design problems).

Deadlocks in production are brutal. The service appears to be running — no crashes, no errors — but requests pile up and the latency graph goes vertical. Thread dumps are your diagnostic tool: they show exactly which threads are blocked and what they're waiting for.

### Livelock

A livelock is deadlock's annoying cousin. In a deadlock, threads are frozen. In a livelock, threads are active — they're doing things — but making no progress. They keep responding to each other's actions in a way that keeps everyone busy and nobody advancing.

The classic human analogy: two people in a hallway each step to the side to let the other pass, then both step back to the original side simultaneously, then repeat forever.

In code, livelocks often happen when multiple threads respond to a conflict by retrying, and the retries keep colliding. If Thread A and Thread B both use CAS to update a counter, fail, and immediately retry, they can keep bumping into each other indefinitely.

Prevention: **randomized backoff.** When a retry is needed, wait a random amount of time before retrying. With randomization, the probability of repeated collision drops exponentially.

### Starvation

A thread is starved when it can never get the resource it needs, even though no deadlock exists — other threads are just consistently getting priority.

Starvation can happen with unfair lock implementations. If a heavily contended mutex always grants the lock to the thread that has been waiting the shortest time (LIFO), a thread that arrived early might wait forever while a constant stream of newcomers cuts the queue.

Prevention: use fair lock implementations that grant access in arrival order (FIFO). Java's `ReentrantLock(true)` is a fair lock. Priority inheritance (where a high-priority task temporarily donates its priority to a low-priority task it's waiting on) prevents the related priority inversion problem.

### Priority Inversion

Priority inversion is a subtle and famous bug. It happens when a high-priority thread is blocked by a low-priority thread holding a resource, while medium-priority threads preempt the low-priority thread, effectively preventing the high-priority thread from running.

The Mars Pathfinder rover experienced a priority inversion bug in 1997 that caused it to repeatedly reset. A low-priority meteorological task held a shared mutex. A high-priority information bus task tried to acquire it and blocked. Meanwhile, medium-priority tasks ran freely, starving the low-priority task. The bus task never got unblocked, and the watchdog timer reset the system.

The fix (which NASA applied remotely to a rover on Mars, impressively) was priority inheritance: when a low-priority thread holds a resource needed by a high-priority thread, temporarily elevate the low-priority thread's priority to match. This prevents medium-priority threads from preempting it and lets it release the resource quickly.

### The ABA Problem

CAS is powerful but has a subtle failure mode. CAS checks whether a value is still what you expect before updating it. But what if the value changed from A to B and back to A? CAS will succeed — it sees A as expected — even though the underlying state may have changed meaningfully in between.

Example: a lock-free stack. You want to pop the top node (A → B → C). You read the top as A, prepare to CAS from A to B. But another thread pops A, pops B, and pushes A back (maybe the same memory address, recycled from a pool). The top is now A again, but it points somewhere different. Your CAS succeeds, but you've corrupted the stack.

Prevention: **tagged pointers** — associate a monotonically incrementing version counter with each pointer. The CAS checks both the pointer and the version; A-at-version-1 doesn't match A-at-version-3. Java's `AtomicStampedReference` does this. Most lock-free library implementations handle this for you.

### False Sharing

This one is pure performance, not correctness, but it can murder throughput in high-performance systems.

CPUs don't read and write individual bytes from memory — they operate in cache lines, typically 64 bytes. When one CPU modifies a byte, the entire 64-byte cache line is marked dirty and must be invalidated in every other CPU's cache. If two threads frequently write to variables that happen to sit on the same cache line, they'll constantly invalidate each other's caches — even though they're modifying logically independent data.

This is false sharing: two threads "share" a cache line without intending to.

```java
// These two fields are on the same cache line.
// Threads updating them fight over the cache line constantly.
class Counter {
    volatile long value1;
    volatile long value2;  // adjacent in memory
}

// Solution: pad to separate cache lines.
class Counter {
    volatile long value1;
    long p1, p2, p3, p4, p5, p6, p7;  // 56 bytes of padding
    volatile long value2;              // now on a different cache line
}
```

Java's `@Contended` annotation does this padding automatically (with `-XX:-RestrictContended`). In C/C++, you can use `alignas(64)`.

### Thundering Herd

When many threads are waiting for a single event and that event fires, they all wake up simultaneously — but only one can proceed. The rest check the condition, find it unmet, and go back to sleep. This mass wakeup → mass sleep cycle is wasteful and can cause significant latency spikes.

Classic scenario: a connection pool runs dry. One hundred threads are waiting for a connection. One connection is released. All 100 threads wake up. One thread gets the connection. The other 99 check, find no connection, go back to sleep.

Prevention strategies:
- **Wake-one** instead of broadcast: `signal()` instead of `signalAll()`. Only one waiter is woken.
- **`EPOLLEXCLUSIVE`** in Linux event loops: ensures a socket's readiness event is only delivered to one epoll instance.
- **Single-flight** pattern (Go's `singleflight` package): when multiple goroutines make the same expensive call simultaneously, collapse them into a single call and fan the result out to all waiters. Popular for cache stampedes.

---

## 5. Distributed Computing Paradigms

When concurrency crosses machine boundaries, new coordination challenges emerge. These are the paradigms for how computation is organized across distributed systems.

### MapReduce

MapReduce was Google's answer to a very specific question: how do you process petabytes of data across thousands of machines with commodity hardware, tolerating frequent failures?

The model is elegantly simple in structure:

1. **Map:** Apply a function to each record, outputting (key, value) pairs.
2. **Shuffle:** Redistribute all pairs by key — all pairs with key "New York" end up on the same reducer.
3. **Reduce:** For each key, aggregate all the values associated with it.

```
Map("The quick brown fox"):
  ("The", 1), ("quick", 1), ("brown", 1), ("fox", 1)

Shuffle: group by word

Reduce("fox", [1, 1, 1]):
  ("fox", 3)
```

The framework handles all the hard parts: splitting input across mappers, shuffling data between machines, managing failures (a machine dies? re-run its tasks elsewhere), and collecting output. You write the Map and Reduce functions; the framework handles the distributed execution.

MapReduce was transformative when it launched, but it's been substantially supplanted by Spark and Flink, which support iterative algorithms (MapReduce requires starting from scratch each iteration), streaming data (MapReduce is batch-only), and more complex DAGs of computation.

### BSP — Bulk Synchronous Parallel

BSP is the model that underlies graph processing systems and scientific simulations. Its structure is repetitive supersteps:

1. **Compute:** Each processor performs local computation.
2. **Communicate:** Processors send messages to each other.
3. **Synchronize:** All processors wait at a global barrier until everyone has finished.

Then repeat. The barrier between supersteps is critical — it ensures that in superstep N+1, every processor has received all messages sent in superstep N. This global synchronization makes reasoning about correctness straightforward, at the cost of performance: a fast processor must wait for the slowest one at each barrier.

BSP is the model behind Google's Pregel (for graph algorithms like PageRank), Apache Giraph, and various scientific simulation frameworks.

### Dataflow Programming

Dataflow turns computation inside out. Instead of writing imperative code that does step 1, step 2, step 3, you describe a directed acyclic graph (DAG) of computation nodes. Each node executes when all its inputs are ready.

```
[Kafka Topic] → [Parse JSON] → [Filter Events] → [Aggregate] → [Write to DB]
```

This model maps naturally onto distributed systems because the DAG can be partitioned across machines, and each node can run where its inputs are. TensorFlow uses a dataflow model for neural network training. Apache Flink and Apache Beam are streaming/batch processing systems based on dataflow. The computation graph is inspectable, optimizable, and parallelizable by construction.

### Stream Processing Semantics: The Delivery Guarantee Spectrum

When you're processing a stream of events, "what happens if something fails?" is not a simple question. There are three delivery guarantees, each with different complexity and trade-offs:

**At-most-once:** Events are processed zero or one times. If something fails, events are dropped. This is the simplest implementation — fire and forget, no bookkeeping. It's acceptable for metrics, logging, and any situation where occasional loss is tolerable. Not acceptable for financial transactions.

**At-least-once:** Events are processed one or more times. If something fails, events are retried — potentially processed again. This is achievable without complex coordination (just retry on failure), but it means your processing must be idempotent: processing the same event twice must produce the same result as processing it once.

Idempotency is a design discipline. "Create user" is not idempotent (two calls create two users). "Create user if not exists, else update" is idempotent. "Increment counter by 1" is not idempotent. "Set counter to max(current, value)" might be. Designing for idempotency is a useful constraint that generally produces cleaner, more robust systems.

**Exactly-once:** Every event is processed exactly one time. No drops, no duplicates. This is the hardest guarantee and requires either:
- **Transactional processing:** The consume + process + produce are wrapped in a distributed transaction (Kafka Transactions, Flink's checkpointing with transactional sinks).
- **Idempotent processing with deduplication:** At-least-once delivery, combined with a deduplication mechanism that tracks processed message IDs and ignores duplicates.

Exactly-once in a distributed system is expensive. The coordination required for distributed transactions has real overhead. Many systems that claim exactly-once are actually implementing idempotent at-least-once. That's fine — it's often the right trade-off.

---

## 6. Memory & Performance

Understanding concurrency at the hardware level unlocks your ability to write genuinely high-performance concurrent code. The primitives are the grammar; this is the physics underneath.

### Memory Models: The Contract Between You and the CPU

A memory model is a formal specification of what guarantees a multi-threaded program can rely on regarding the visibility and ordering of memory operations. It's the contract between your code and the runtime.

**The Java Memory Model (JMM)** is built around "happens-before" relationships. If action A happens-before action B, then A's effects are guaranteed to be visible to B. The key happens-before relationships:

- Thread start: all actions before `thread.start()` happen-before any actions in the started thread.
- Lock release: all actions before `unlock()` happen-before any subsequent `lock()` on the same monitor.
- `volatile` write: a write to a `volatile` variable happens-before every subsequent read of that variable.

`volatile` in Java gives you two things: **visibility** (writes are immediately visible to all threads, not cached in registers or CPU caches) and **ordering** (writes and reads to volatile variables aren't reordered with respect to each other). This makes `volatile` sufficient for a single flag that one thread writes and another reads — but insufficient for compound operations like check-then-act.

`synchronized` adds **mutual exclusion** on top of the visibility and ordering guarantees.

**C++11 memory orderings** are more explicit and fine-grained. Six orderings, from `relaxed` (no ordering guarantees, just atomicity) to `seq_cst` (sequential consistency, total order across all operations). The trade-off is performance: `relaxed` is cheapest, `seq_cst` is most expensive. Getting the ordering right requires deep expertise — use `seq_cst` by default and only loosen it after profiling and careful reasoning.

The practical lesson: don't write lock-free code that relies on specific hardware memory ordering behavior. Write to the language's memory model. Your code will be portable, and the compiler/runtime will insert the right hardware instructions for each target architecture.

#### Why You Should Care: The x86 vs. ARM Bug That Bites in Production

This is not a theoretical concern. It is a class of bugs that kills engineers in production when they move workloads from x86 to ARM — which, in 2024 and beyond, is increasingly common as AWS Graviton, Apple Silicon, and Ampere Altra servers go mainstream.

**x86's memory model is unusually strong.** The Total Store Order (TSO) model means that on x86:
- Stores are not reordered with respect to other stores.
- Loads are not reordered with respect to other loads.
- Loads are not reordered with respect to prior stores.

This means many programs that are technically incorrect from a memory model perspective will appear to work correctly on x86, because the hardware provides stronger guarantees than the language standard requires.

**ARM's memory model is weak.** ARM allows stores to be reordered with respect to other stores, and loads to be reordered with respect to other loads, unless you insert explicit memory barrier instructions (`dmb`, `dsb`, `isb`). The CPU is free to reorder memory operations in ways that produce different results when observed from another core.

**The bug scenario:**

```c
// Shared flag pattern — common in low-level systems code
// This is technically undefined behavior in C without proper atomics,
// but let's trace what actually happens on different hardware.

// Thread 1 (writer):
data = 42;         // write data
ready = 1;         // signal that data is ready

// Thread 2 (reader):
while (!ready) {}  // wait for signal
use(data);         // use data — is this always 42?
```

On x86: this almost always works. The TSO model means stores are observed in order by other processors. By the time Thread 2 sees `ready = 1`, it will also see `data = 42`.

On ARM: this can fail. The ARM CPU can reorder the two stores, so Thread 2 might observe `ready = 1` before it observes `data = 42`. It reads `data` and gets whatever garbage was in memory before the write, or 0. The bug is real, intermittent, and potentially data-corrupting.

**How to fix it properly (C11/C++):**

```c
// Thread 1:
atomic_store_explicit(&data, 42, memory_order_relaxed);
atomic_store_explicit(&ready, 1, memory_order_release);  // release barrier

// Thread 2:
while (!atomic_load_explicit(&ready, memory_order_acquire)) {} // acquire barrier
use(atomic_load_explicit(&data, memory_order_relaxed));
```

The `memory_order_release` on the store ensures all prior stores are visible before the flag is set. The `memory_order_acquire` on the load ensures all subsequent loads see the stores that happened before the release. Together they form the acquire-release pair that the language standard defines — and the compiler emits the right barrier instructions for both x86 and ARM.

**The AWS Graviton production story:**

Multiple engineering teams have documented bugs discovered only when migrating to Graviton (ARM-based AWS instances). A common pattern: C++ code that used `volatile` instead of `std::atomic` for inter-thread flags. On x86, `volatile` happens to prevent compiler reordering, and the hardware's strong ordering prevents the worst CPU reordering. On ARM, both compiler and hardware reordering can happen, surfacing data corruption.

One specific case (documented publicly by a kernel developer): a Linux kernel driver used plain writes to shared flag variables between interrupt handler and process context. It had been "working" on x86 for years. On ARM, the missing memory barriers caused occasional data corruption during high-interrupt-rate workloads.

**The practical rule:** if you're writing any code that coordinates threads without using high-level primitives (mutexes, channels, language atomics with explicit ordering), test it on ARM before shipping. If you can't easily test on ARM, use the strongest memory ordering (`seq_cst`) everywhere that correctness is involved, and only consider loosening it after profiling reveals it's actually a bottleneck.

### NUMA: The Memory Hierarchy You Forgot About

Modern servers often have multiple CPU sockets, each with its own bank of RAM. A CPU can access its local RAM at full speed, but accessing RAM attached to another socket has to go through an interconnect — typically 1.5-3x slower. This is Non-Uniform Memory Access (NUMA).

If you have a Java application running on a 4-socket server and the JVM's GC is allocating objects willy-nilly across all sockets, some of those objects will be in remote NUMA nodes. Every access is slower. Under high load, this can become a significant bottleneck.

Fix: pin threads to NUMA nodes, and ensure memory allocation happens on the same NUMA node as the thread that will use it. JVM: `-XX:+UseNUMA`. Linux: `numactl --localalloc`. This is usually only worth worrying about for high-performance, latency-sensitive systems — but if you're seeing unexplained performance degradation on a multi-socket server, NUMA is worth investigating.

### Zero-Copy I/O

Normal I/O is expensive. When a kernel reads data from disk, it copies it into a kernel buffer. When user code reads it, the kernel copies it again from kernel space to user space. When you want to write it to a network socket, you copy it back to kernel space. That's at minimum two copies (and often more with SSL, compression, etc.).

Zero-copy techniques let you skip some or all of these copies:

- **`sendfile()`:** Transfers data directly from a file descriptor to a socket descriptor, entirely in kernel space. No copy to user space at all. This is how Kafka achieves its remarkable consumer read performance — the broker uses `sendfile()` to transfer message bytes directly from the page cache to the consumer's network socket.
- **`splice()`:** Moves data between two file descriptors without copying to user space. Works between pipes, sockets, and files.
- **`mmap()`:** Maps a file directly into the process's address space. Reads and writes hit the page cache directly; no explicit copy. Databases often use mmap for their data files.

For high-throughput data services — messaging systems, streaming platforms, file servers — zero-copy can make a substantial difference.

### Garbage Collection: Not Just for Java Developers

If you're working in a GC'd language, the garbage collector is a concurrent system running alongside your code. Understanding it means you can tune it and avoid causing it to hurt you.

The JVM's garbage collector landscape:

| Collector | Pause Target | Best For |
|---|---|---|
| **G1 GC** | Configurable (~200ms default) | General purpose — the default since Java 9. Most applications should start here. |
| **ZGC** | Sub-millisecond | Ultra-low-latency applications: trading systems, real-time APIs, anything where 200ms pauses are unacceptable. |
| **Shenandoah** | Sub-millisecond | Low-latency, developed by Red Hat. Similar goals to ZGC, different implementation trade-offs. |
| **Parallel GC** | Throughput-optimized, longer pauses acceptable | Batch processing, analytics workloads where overall throughput matters more than individual latency. |

The reason low-latency collectors (ZGC, Shenandoah) exist: traditional collectors like G1 need to stop the world for major garbage collection phases. "Stop the world" means all application threads pause. A 200ms pause might be acceptable for a web app but is catastrophic for a high-frequency trading system that measures latency in microseconds.

ZGC and Shenandoah do most of their work concurrently — running alongside the application threads, not stopping them. Their worst-case pauses are in the single-digit milliseconds range, which was achieved by engineering that verges on magic (concurrent relocation, load barriers, colored pointers).

The practical advice for JVM applications: start with G1 GC. Add `-XX:MaxGCPauseMillis=200` to set a target. Profile GC behavior with `-verbose:gc` or GC logs. If you see pause times that are impacting your SLAs, switch to ZGC.

---

## 7. Programming Paradigms

Concurrency doesn't exist in a vacuum — it intersects with how you structure your code. Different programming paradigms have very different relationships with concurrency, ranging from "concurrency is nearly impossible to get wrong" to "concurrency is the primary concern."

### Functional Programming: Concurrency as a Gift

The core insight of functional programming as it relates to concurrency is almost comically simple: if data never changes, there's nothing to synchronize.

**Immutability** eliminates data races by definition. You can't have a race condition on data that nobody writes. Immutable data structures can be freely shared across threads with no locks. This is why Clojure, Haskell, and F# make immutability the default — it's not just an aesthetic choice, it's a concurrency guarantee.

**Pure functions** — functions that take input and return output with no side effects — are trivially parallelizable. If `f(x)` doesn't read or modify any external state, you can call it from a hundred goroutines simultaneously with zero coordination. Parallelizing pure functions is just a matter of scheduling, not synchronization.

**Monads for error handling** seem like an academic concern until you've shipped a concurrent system. The standard alternatives — null (NullPointerException) and exceptions — interact badly with concurrent code. An exception thrown in a worker thread has to be caught in the right place and surfaced back to the caller, which in async contexts requires careful handling. Monadic types like `Option/Maybe` (no null) and `Result/Either` (no exceptions) make the success and failure cases explicit in the type system:

```rust
// Rust: the type tells you this might fail and you must handle both cases
fn fetch_user(id: u64) -> Result<User, DatabaseError> {
    // ...
}

// Chain operations that might fail without nesting try-catch:
fetch_user(id)
    .and_then(|user| fetch_permissions(user.role_id))
    .and_then(|perms| build_response(user, perms))
    .unwrap_or_else(|err| error_response(err))
```

In practice, you don't have to write in a pure FP language to benefit from these ideas. Write immutable data transfer objects. Prefer pure functions for transformation logic. Use `Optional` or `Result` types for operations that can fail. These choices make concurrent code substantially easier to reason about.

### OOP — SOLID Principles for Concurrent Systems

SOLID principles were articulated in the context of OOP, but they're particularly valuable in concurrent systems where the cost of bad design is higher (wrong interactions between concurrent components are hard to debug).

| Principle | Meaning | Concurrency Relevance |
|---|---|---|
| **S** — Single Responsibility | One class, one reason to change | Classes with fewer responsibilities have clearer lock boundaries |
| **O** — Open/Closed | Open for extension, closed for modification | Immutable base behavior is inherently thread-safe |
| **L** — Liskov Substitution | Subtypes must be substitutable for base types | Thread-safety guarantees must be honored in subclasses |
| **I** — Interface Segregation | No client depends on methods it doesn't use | Narrow interfaces expose less shared state surface area |
| **D** — Dependency Inversion | Depend on abstractions, not concretions | Inject thread-safe implementations; swap without changing calling code |

The single responsibility principle is particularly relevant: a class that mixes business logic with concurrency control is hard to reason about. Separate them — let a concurrent wrapper handle the synchronization, and let the inner class be single-threaded and pure.

### Reactive Programming

Reactive programming combines the event-loop model with a rich functional API for stream transformation. Everything is a stream. Mouse clicks are a stream. HTTP requests are a stream. Database results are a stream. You compose transformations on these streams using operators like `map`, `filter`, `flatMap`, `merge`, and `zip`.

The key addition over a plain event loop is **backpressure** — the demand-driven protocol where consumers tell producers how much they can handle. Backpressure strategies:

- **Buffer:** Queue items until the consumer is ready. Risk: unbounded queues, OOM.
- **Drop:** Discard items when the consumer is overwhelmed. Risk: data loss.
- **Throttle/Sample:** Only process one item per time window. Risk: stale data.
- **Request-based pull:** Consumers explicitly request batches. This is the Reactive Streams specification approach — no events are pushed until the consumer signals readiness.

Reactive programming is powerful for complex stream transformations and systems where backpressure is structurally important. The cost is a steep learning curve and deeply unhelpful stack traces when something goes wrong. Most engineers will find that Java virtual threads deliver equivalent scalability with a fraction of the complexity.

---

---

## Concurrency Bugs Hall of Fame

Real bugs from real systems. These are not hypothetical — they happened, they caused significant harm, and each one illustrates a concurrency principle from this chapter.

### The Therac-25: Race Condition That Killed People (1985-1987)

The Therac-25 was a radiation therapy machine that killed six patients and injured several more due to software bugs, several of which were race conditions.

The machine had two operating modes: a low-power electron beam mode and a high-power X-ray mode (which used a metal plate to diffuse the beam). A race condition in the control software meant that if an operator typed too quickly — entering the treatment type and confirming it before the software had finished setting up the previous state — the machine could set up for X-ray mode (high power) but skip placing the metal plate, and then fire the raw electron beam at full power directly at the patient.

The flag that controlled whether the beam intersector was in position was a single byte. The operator interface software and the beam control software both read and wrote this flag without synchronization. The race window was tiny — it only manifested when operators typed at a specific speed, which is why it wasn't caught in testing. The engineers had removed a hardware interlock that had existed in earlier models (trusting the software), and the software had no protection against concurrent access to shared state.

**Lesson:** Shared mutable state without synchronization is not just a performance bug or a data integrity bug — in safety-critical systems, it is a lethal bug. Hardware interlocks exist because software race conditions do.

### The Mars Pathfinder Priority Inversion (1997)

Already mentioned in the priority inversion section, but worth recounting in full because the debugging story is remarkable.

The Mars Pathfinder rover began experiencing system resets after landing on Mars. The team back on Earth had no direct access to the rover's system — they had to reason about the bug from telemetry data and their knowledge of the software.

The system used VxWorks (a real-time operating system) with priority-based scheduling. A low-priority meteorological data collection task held a mutex shared with the high-priority information bus task. Medium-priority tasks preempted the low-priority task before it could release the mutex. The high-priority bus task waited indefinitely, triggering the watchdog timer, which reset the system.

The debugging was done largely by recreating the conditions in a lab on Earth. Engineers realized that the root cause was that VxWorks' mutexes had priority inheritance as a configurable option — and it had been left off. The fix was to enable priority inheritance via a command sent to a rover on Mars.

This was executed successfully. A software configuration change was uploaded to a rover 120 million miles away to fix a concurrency bug. It worked.

**Lesson:** Priority inversion is not theoretical. Use RTOS mutexes with priority inheritance enabled in any real-time system. And invest in the ability to reconfigure production systems remotely — you will need it.

### The Python GIL and the Missing Parallelism (2004-present)

This is less a bug and more a pervasive architectural constraint that catches Python engineers off guard.

CPython (the standard Python interpreter) has a Global Interpreter Lock — a mutex that prevents more than one thread from executing Python bytecode at a time. Threads exist, but only one runs at any given moment. The GIL is released during I/O operations, which is why threading works for I/O-bound work. But for CPU-bound work, adding more threads achieves nothing — they take turns holding the GIL.

The GIL was introduced in 1992 as a practical simplification to protect CPython's reference counting garbage collector. It made extension modules simpler and avoided a whole class of memory safety bugs. But it also meant that Python's threading model fundamentally cannot provide CPU parallelism.

The workarounds are `multiprocessing` (separate processes, separate GILs, but IPC overhead and no shared memory), C extensions that release the GIL during computation (NumPy does this — which is why NumPy matrix operations can be fast), and more recently, subinterpreters in Python 3.12+ and work toward a "nogil" build.

The real lesson: this was a correct engineering tradeoff in 1992 that became increasingly painful as the world went multicore. Many engineers have spent days debugging "why isn't my Python code using all cores?" before discovering the GIL.

**Lesson:** Every concurrency model has constraints. Know the constraints of your runtime. Python's answer to CPU parallelism is multiprocessing, not multithreading.

### The Node.js Single-Thread Event Loop Bomb (common, no single canonical incident)

This is the pattern that occurs regularly in Node.js production systems: an async function that contains a synchronous computation bomb.

```javascript
// This looks async. It is not, in the way that matters.
app.get('/process', async (req, res) => {
    const data = await fetchFromDatabase(req.query.id);  // yields to event loop ✓
    const result = computeExpensiveHash(data);            // runs synchronously ✗
    res.json({ result });
});

function computeExpensiveHash(data) {
    // This takes 500ms of pure CPU computation
    // During these 500ms, the event loop is blocked
    // All other pending requests are frozen
    return crypto.createHash('sha512').update(data.repeat(100000)).digest('hex');
}
```

A team at a payments company shipped exactly this pattern — an expensive HMAC computation for webhook signature verification that took ~300ms on large payloads. Under normal load: fine. Under a burst of large webhook deliveries: the event loop blocked, and their entire API server became unresponsive for several seconds at a time. Latency graphs showed flat lines, not spikes — the server simply stopped responding.

The fix: move CPU-bound work to worker threads (`worker_threads` in Node.js) or to a separate process pool.

**Lesson:** `async/await` in Node.js means "this function can yield at I/O boundaries." It does not mean "this function is parallelized." CPU work inside an async function blocks the event loop exactly as much as it would in synchronous code. Profile your async functions; not all `await` points are equal.

### The Java `HashMap` Infinite Loop (Java 6, 2008-era)

A particularly nasty concurrency bug in Java's standard library HashMap.

Before Java 8, `HashMap` used a singly-linked list for collision chaining. When the map grew beyond its load factor, it was resized — a new array allocated, all entries rehashed and reinserted. This rehashing process was not thread-safe, and HashMap's documentation said so clearly. But the warning was easy to miss.

If two threads both triggered a resize simultaneously (both inserted new keys that crossed the load factor threshold), a race condition in the linked list rebalancing could produce a cycle in the linked list. Two nodes pointing to each other in a circle. After this happened, any call to `get()` or `put()` that resolved to that bucket would loop forever — 100% CPU, never returning.

This caused production outages at companies across the industry. The symptoms were mysterious: a Java service pegging a CPU core at 100% with thread dumps showing a single thread spinning in `HashMap.get()`. The bug was invisible under normal single-threaded load, only manifested under concurrent access, and was already fixed by using `ConcurrentHashMap` — a class the Java documentation recommended for concurrent use.

**Lesson:** "Not thread-safe" means exactly that. Even read operations on a `HashMap` during a concurrent resize can trigger infinite loops. If a data structure might be accessed concurrently, use the explicitly concurrent version. And read the documentation about thread safety before reaching for a shared collection.

### The AWS us-east-1 Kinesis Outage and the Thundering Herd (2020)

In November 2020, AWS experienced a significant outage in us-east-1. The root cause was instructive.

A service responsible for managing Kinesis front-end fleet capacity experienced a capacity addition event (new servers brought online to handle increased load). A large number of front-end servers came online simultaneously and began their startup sequence — which included querying an internal metadata service to get shard-to-server routing tables.

Hundreds of servers all queried the metadata service at the same time. The metadata service was not provisioned for this burst of simultaneous requests. It slowed down, which caused the front-end servers' initialization to time out, which caused them to retry — adding more load to an already overloaded metadata service. A thundering herd, compounded by retry storms.

The metadata service degradation cascaded to other services that depended on it (including IAM authentication in the same region), broadening the blast radius significantly.

**Lesson:** Thundering herds are real at distributed scale. Staggered startup, jittered retries, and capacity planning for "all servers restart simultaneously" scenarios are not edge cases — they are foreseeable operational events that you must design for. The single-flight pattern, exponential backoff with jitter, and circuit breakers exist precisely for this class of problem.

---

There's no universal answer, but there are clear patterns.

| Scenario | Recommended Approach | Why |
|---|---|---|
| High-concurrency I/O (10K+ connections) | Event loop (Node.js, asyncio) or virtual threads (Java 21+) | Low per-connection overhead; threads spend most time waiting |
| CPU-bound parallel compute | Thread pool + work stealing | Saturate CPU cores; work stealing handles uneven task sizes |
| Distributed fault-tolerant system | Actor model (Erlang/Akka/Orleans) | Isolated state, supervision, natural fit for entity-per-actor |
| Data pipeline with clear stages | CSP with channels (Go) or pipeline parallelism | Explicit data flow, backpressure via channel buffering |
| Streaming data + backpressure | Reactive streams (Reactor, RxJava) | Backpressure is built into the protocol |
| Simple request-response server | Thread pool, or virtual threads (Java 21+) | Simple, proven, and virtual threads eliminate the old scaling concerns |
| Ultra-low-latency system | Lock-free data structures + NUMA-aware allocation + ZGC | Eliminate every source of non-deterministic pause |

A few guiding principles worth internalizing:

**Match the model to the problem shape.** Actors are natural for systems with distinct stateful entities. Channels are natural for pipelines. Event loops are natural for I/O-heavy workloads. Forcing the wrong model onto a problem creates unnecessary complexity.

**Prefer immutability.** Any state that doesn't need to be mutable should be immutable. Immutable objects can be freely shared. The synchronization you don't need is the synchronization that can't go wrong.

**Measure before optimizing.** Lock-free algorithms are harder to implement and harder to reason about. Unless you have profiling data showing that lock contention is your actual bottleneck, reach for the simpler mutex-based solution first.

**Concurrency is an API.** When you write a concurrent data structure or class, document its thread-safety guarantees. "Thread-safe" and "not thread-safe" are part of the class's contract. Callers need to know.

**The race detector is your friend.** If you're writing Go, run your tests with `-race`. Always. It will catch real bugs. The overhead in testing is trivially acceptable for the bugs it surfaces.

---

Concurrency is one of those topics where you can go very deep and still find more. The models described here — threads, event loops, actors, CSP, coroutines, reactive — are all real choices you'll face. The primitives — mutexes, semaphores, condition variables, atomics, CAS — are the tools you'll reach for. The problems — race conditions, deadlocks, livelocks, false sharing, thundering herds — are the traps that are waiting for you if you get careless.

But here's the thing: once you have the mental model, the bugs stop feeling like random bad luck and start feeling like puzzles with known solutions. "This is a deadlock because of lock ordering." "This is a thundering herd — I need a single-flight pattern here." "This counter is being corrupted — I need an atomic, not a plain integer."

That pattern recognition is worth more than memorizing any individual technique. Build the mental model, and the rest follows.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M20: Domain-Driven Design Basics](../course/modules/loop-1/L1-M20-domain-driven-design-basics.md)** — Model TicketPulse's concurrent ticket reservation domain with aggregates that enforce invariants under contention
- **[L2-M33: Kafka Deep Dive](../course/modules/loop-2/L2-M33-kafka-deep-dive.md)** — Build event-driven concurrent processing with Kafka consumer groups, partition assignment, and backpressure handling
- **[L3-M67: WebSockets and Real-Time](../course/modules/loop-3/L3-M67-websockets-and-real-time.md)** — Implement real-time seat availability updates using WebSockets, managing concurrent connections and broadcast fan-out

### Quick Exercises

1. **Write a goroutine (or async function) that demonstrates a race condition, then fix it** — create a counter incremented by multiple concurrent workers without synchronization, observe the incorrect result under the race detector (`go test -race`), then fix it with a mutex or atomic operation.
2. **Find one place in your codebase where concurrent access isn't properly guarded** — look for shared mutable state (caches, counters, maps) that's accessed from multiple goroutines, threads, or async handlers without explicit synchronization. Document the risk and propose a fix.
3. **Trace one request through your system and identify every blocking operation** — pick a slow endpoint, add timing instrumentation, and map out where time is spent: database queries, external API calls, lock waits. Identify which of these could be parallelized.

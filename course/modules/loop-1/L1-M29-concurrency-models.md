# L1-M29: Concurrency Models

> **Loop 1 (Foundation)** | Section 1F: Language Exposure + Capstone | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L1-M28 (The Language Landscape)
>
> **Source:** Chapters 11, 6 of the 100x Engineer Guide

---

## The Goal

In M28, all four servers handled 100 concurrent connections easily. That is not a real test. A real test is what happens when 10,000 users hit your server simultaneously -- during a concert ticket drop, during Black Friday, during a viral moment.

This module is about understanding *how* each language handles concurrency, not just that they do. By the end, you will have a mental model for choosing the right concurrency approach for the right problem.

**You will see your first server collapse under load within the first five minutes.**

---

## 0. Quick Start (5 minutes)

Make sure all four servers from M28 are running:

```bash
# Verify all four are responding
for port in 3000 3001 3002 3003; do
  curl -sf http://localhost:$port/health > /dev/null && echo "Port $port: OK" || echo "Port $port: DOWN"
done
```

Now hit them hard:

```bash
# 10,000 concurrent connections, 4 threads, 30 seconds
wrk -t4 -c10000 -d30s http://localhost:3001/api/events
```

> **Note:** Your OS may limit the number of open file descriptors. If you get connection errors, increase the limit:
> ```bash
> ulimit -n 65536
> ```

---

## 1. The Concurrency Models

Before we benchmark, understand what each language is doing under the hood:

### 1.1 Go: Goroutines (CSP)

```
Request 1 ──→ goroutine 1 ──→ handler ──→ response
Request 2 ──→ goroutine 2 ──→ handler ──→ response
Request 3 ──→ goroutine 3 ──→ handler ──→ response
   ...          ...
Request 10000 → goroutine 10000 → handler → response

M goroutines multiplexed onto N OS threads (runtime scheduler)
Each goroutine: ~2-8 KB of stack (grows dynamically)
10,000 goroutines: ~20-80 MB of memory
```

Go creates a goroutine per request. Goroutines are lightweight (not OS threads). The Go runtime scheduler maps thousands of goroutines onto a small number of OS threads using work-stealing. When a goroutine blocks on I/O, the scheduler transparently runs another goroutine on the same OS thread.

### 1.2 Node.js: Event Loop (Single Thread)

```
Request 1 ──┐
Request 2 ──┤
Request 3 ──┤──→ Event Loop (single thread) ──→ handler ──→ callback ──→ response
   ...      │         │
Request 10000 ┘       ├──→ I/O operation (non-blocking)
                      ├──→ I/O operation (non-blocking)
                      └──→ I/O operation (non-blocking)
```

Node.js has ONE thread running JavaScript. All requests share that thread. When a request needs I/O (database, file, network), it registers a callback and yields. The event loop picks up the next piece of work. When the I/O completes, the callback is queued and eventually executed.

The critical implication: **if your handler does CPU-heavy work (JSON parsing of a 10 MB payload, cryptographic operations, image processing), it blocks the entire event loop.** Nothing else can run until it finishes.

### 1.3 Python: asyncio (Cooperative Scheduling)

```
Request 1 ──┐
Request 2 ──┤──→ asyncio event loop ──→ async handler ──→ await I/O ──→ response
Request 3 ──┤         │
   ...      │         └──→ While awaiting, run other handlers
```

FastAPI with uvicorn uses Python's `asyncio` -- a cooperative scheduler similar to Node.js. When a handler hits `await`, it yields control. Other handlers run in the meantime.

But there is a catch: Python has the **GIL (Global Interpreter Lock)**. Only one thread can execute Python bytecode at a time. Even with multi-threading, CPU-bound work is not parallel. Uvicorn compensates by running multiple worker processes.

### 1.4 Rust: tokio (Async Runtime)

```
Request 1 ──→ Future 1 ──→ .await ──→ poll ──→ response
Request 2 ──→ Future 2 ──→ .await ──→ poll ──→ response
   ...
Futures are state machines compiled at build time.
tokio runtime: M:N threading (async tasks on a thread pool)
```

Rust's async model compiles `async fn` into state machines at compile time. There is no garbage collector, no runtime overhead. `tokio` provides the runtime that drives these futures, using a multi-threaded work-stealing scheduler similar to Go's.

The key difference from Go: Rust futures are "zero-cost abstractions" -- the compiler generates exactly the state machine code needed, with no heap allocation for the future itself.

---

## 2. Benchmark: Pure Throughput (No I/O)

The servers from M28 return in-memory data. No database, no I/O. This tests pure HTTP handling speed.

```bash
echo "=== Go (goroutines) ==="
wrk -t4 -c10000 -d30s http://localhost:3001/api/events
echo ""

echo "=== Node.js (event loop) ==="
wrk -t4 -c10000 -d30s http://localhost:3000/api/events
echo ""

echo "=== Python (asyncio) ==="
wrk -t4 -c10000 -d30s http://localhost:3002/api/events
echo ""

echo "=== Rust (tokio) ==="
wrk -t4 -c10000 -d30s http://localhost:3003/api/events
echo ""
```

### 2.1 Record Your Results

Fill in your numbers:

| Language | Requests/sec | Avg Latency | Max Latency | Errors |
|---|---|---|---|---|
| Go | | | | |
| Node.js | | | | |
| Python | | | | |
| Rust | | | | |

At 10,000 concurrent connections, you should see:
- **Rust and Go** handle it comfortably. Latency stays low.
- **Node.js** handles it but latency increases. The single thread is saturated with JSON serialization.
- **Python** starts struggling. Latency spikes, some timeouts may appear.

---

## 3. Try It: Add a 100ms I/O Delay

The pure throughput test is not realistic. Real servers hit databases, call APIs, read files. Let us simulate a 100ms database query.

### 3.1 Add the Delay to Each Server

**Go:**

```go
// Add to the /api/events handler
mux.HandleFunc("GET /api/events-slow", func(w http.ResponseWriter, r *http.Request) {
    time.Sleep(100 * time.Millisecond)  // Simulate DB query
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(events)
})
```

**Node.js:**

```typescript
// Add to Express routes
router.get('/api/events-slow', async (req, res) => {
  await new Promise(resolve => setTimeout(resolve, 100));  // Simulate DB query
  res.json(events);
});
```

**Python (FastAPI):**

```python
import asyncio

@app.get("/api/events-slow")
async def list_events_slow() -> list[Event]:
    await asyncio.sleep(0.1)  # Simulate DB query
    return events
```

**Python (Flask -- synchronous for comparison):**

```python
# Also start a Flask server on port 3004 to compare sync vs async Python
import time
from flask import Flask, jsonify

flask_app = Flask(__name__)

@flask_app.route("/api/events-slow")
def list_events_slow():
    time.sleep(0.1)  # BLOCKING sleep -- this blocks the entire thread
    return jsonify([e.dict() for e in events])
```

```bash
# Start Flask for comparison (sync Python)
cd ticketpulse/language-comparison/python
pip install flask
flask --app sync_main run --port 3004 &
```

**Rust:**

```rust
// Add to routes
async fn list_events_slow(events: axum::extract::State<Events>) -> Json<Vec<Event>> {
    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
    Json(events.as_ref().clone())
}
```

### 3.2 Benchmark with I/O Delay

```bash
echo "=== Go (goroutines + 100ms I/O) ==="
wrk -t4 -c1000 -d30s http://localhost:3001/api/events-slow
echo ""

echo "=== Node.js (event loop + 100ms I/O) ==="
wrk -t4 -c1000 -d30s http://localhost:3000/api/events-slow
echo ""

echo "=== Python async (FastAPI + 100ms I/O) ==="
wrk -t4 -c1000 -d30s http://localhost:3002/api/events-slow
echo ""

echo "=== Python sync (Flask + 100ms I/O) ==="
wrk -t4 -c1000 -d30s http://localhost:3004/api/events-slow
echo ""

echo "=== Rust (tokio + 100ms I/O) ==="
wrk -t4 -c1000 -d30s http://localhost:3003/api/events-slow
echo ""
```

### 3.3 Observe the Results

Record your numbers:

| Language | Requests/sec | Avg Latency | Notes |
|---|---|---|---|
| Go | ~9,500 | ~105ms | Goroutines handle the delay efficiently |
| Node.js | ~9,000 | ~110ms | Event loop: non-blocking I/O shines |
| Python async (FastAPI) | ~8,000 | ~120ms | asyncio handles I/O concurrency well |
| Python sync (Flask) | ~10 | ~10s+ | **Collapses.** One thread blocked = one request at a time |
| Rust (tokio) | ~9,500 | ~105ms | Async runtime handles it efficiently |

The dramatic result is **synchronous Python (Flask)**. With a blocking `time.sleep(0.1)`, each request holds a thread for 100ms. With the default single worker thread, Flask can only handle ~10 requests per second. The other 990 connections are queued, waiting.

This is why the async vs sync distinction matters more than the language choice in many cases. **Async Python and async Node.js both handle I/O-heavy concurrency well. Synchronous Python does not.**

---

## 4. CPU-Bound vs I/O-Bound: The Critical Distinction

### 4.1 I/O-Bound Work (Waiting for External Resources)

```
Database queries, HTTP calls to other services, file reads, network I/O
```

All four async runtimes handle this well. The pattern is the same:
- Start the I/O operation
- While waiting, do other work
- When I/O completes, resume

Winner: **all four are roughly equal for I/O-bound work.** The language barely matters when you are waiting on a database.

### 4.2 CPU-Bound Work (Computing)

```
JSON parsing, cryptography, image processing, data transformation, compression
```

This is where the differences are stark:

```bash
# Add a CPU-intensive endpoint to each server
# (e.g., compute the Nth Fibonacci number synchronously)
```

**Go:** Goroutines are preemptively scheduled. CPU-bound work in one goroutine does not block others (the Go scheduler can preempt it).

**Node.js:** CPU-bound work **blocks the event loop.** While computing Fibonacci, zero other requests can be served. This is Node's Achilles' heel.

**Python:** The GIL means CPU-bound Python code in threads does not run in parallel. Use multiprocessing or a separate worker process.

**Rust:** Full access to OS threads. CPU-bound work can run on separate threads via `tokio::task::spawn_blocking`, keeping the async runtime responsive.

### 4.3 The Mental Model

| Workload Type | Best Concurrency Model |
|---|---|
| I/O-bound (APIs, databases) | Event loop (Node.js), asyncio (Python), goroutines (Go), tokio (Rust) -- all good |
| CPU-bound (computation) | OS threads (Go, Rust), worker processes (Python), worker threads (Node.js -- separate from event loop) |
| Mixed (some I/O, some CPU) | Go goroutines or Rust tokio (both handle the transition naturally) |
| Massive concurrent connections (100K+) | Event-driven (Node.js, Rust tokio) or goroutines (Go) |

---

## 5. The Four Concurrency Mental Models

### 5.1 Threads (Java, C++, C#)

```
Thread 1: ████░░░░████████░░░████  (CPU work + I/O waits)
Thread 2: ░░░░████░░░░░░░░████░░░
Thread 3: ████████░░░░████░░░░████
```

Shared memory, locks for synchronization. ~1 MB stack per thread. Good for CPU parallelism. Watch for: deadlocks, race conditions.

### 5.2 Event Loop (Node.js, Python asyncio)

```
Event Loop: ██ callback ██ callback ██ callback ██ callback
            ↑           ↑           ↑
         I/O done    I/O done    timer fires
```

Single thread, non-blocking I/O. Callbacks/promises/async-await. Extremely efficient for I/O. Blocks on CPU work.

### 5.3 Goroutines / CSP (Go)

```
Goroutine 1: ████──channel──████
Goroutine 2:       ──channel──████──channel──
Goroutine 3: ████████──channel──████
```

Lightweight green threads + typed channels. "Share memory by communicating." The scheduler handles multiplexing.

### 5.4 Actor Model (Erlang/Elixir, Akka)

```
Actor 1: [private state] ←── message ←── Actor 2: [private state]
                         ──→ message ──→
```

Independent actors with private state. Communication only through messages. No shared memory. "Let it crash" -- supervisors restart failed actors.

> **Insight:** "WhatsApp handled 2 million concurrent connections per server using Erlang's actor model. Node.js powers Netflix's API serving 200 million users. Go powers Kubernetes, which orchestrates containers across millions of machines. Rust powers Cloudflare's network edge, handling millions of requests per second. The right tool depends on the right problem."

---

## 6. Try It: The Event Loop Blocking Demonstration

This exercise makes the Node.js event loop limitation visceral. You will see it happen, not just read about it.

### 6.1 Add a CPU-Intensive Endpoint

```typescript
// Add to TicketPulse Express routes
router.get('/api/cpu-heavy', (req, res) => {
  // Simulate CPU-bound work: compute Fibonacci(40)
  function fib(n: number): number {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
  }

  const start = Date.now();
  const result = fib(40);  // Takes ~1-2 seconds of pure CPU
  const elapsed = Date.now() - start;

  res.json({ result, computeTimeMs: elapsed });
});
```

### 6.2 Watch It Block Everything

Open two terminals. In the first, trigger the CPU-heavy endpoint:

```bash
# Terminal 1: start a slow CPU-bound request
curl -s http://localhost:3000/api/cpu-heavy | jq .
# This will take 1-2 seconds
```

While that is running, in the second terminal, try a fast request:

```bash
# Terminal 2: this should be instant, but watch what happens
time curl -s http://localhost:3000/api/health | jq .
```

The health check -- which should take less than 1ms -- takes 1-2 seconds because the event loop is blocked computing Fibonacci. **Every request to the entire server is stalled** while one request does CPU work.

### 6.3 The Fix: Worker Threads

```typescript
// src/workers/cpu-worker.ts
import { parentPort } from 'worker_threads';

function fib(n: number): number {
  if (n <= 1) return n;
  return fib(n - 1) + fib(n - 2);
}

parentPort?.on('message', (n: number) => {
  const result = fib(n);
  parentPort?.postMessage(result);
});
```

```typescript
// Updated route: offload CPU work to a worker thread
import { Worker } from 'worker_threads';
import path from 'path';

router.get('/api/cpu-heavy-fixed', (req, res) => {
  const worker = new Worker(path.join(__dirname, '../workers/cpu-worker.ts'));
  const start = Date.now();

  worker.postMessage(40);

  worker.on('message', (result) => {
    const elapsed = Date.now() - start;
    res.json({ result, computeTimeMs: elapsed });
    worker.terminate();
  });

  worker.on('error', (err) => {
    res.status(500).json({ error: err.message });
    worker.terminate();
  });
});
```

Now test again: start the CPU-heavy request, then immediately hit the health check. The health check responds instantly because the CPU work runs on a separate thread.

This is the core lesson: **in Node.js, CPU-bound work must be offloaded to worker threads.** The event loop must stay free for I/O callbacks. If you block the event loop, you block everything.

### 6.4 Compare with Go

Go does not have this problem. Try the equivalent:

```go
// Add to Go server
mux.HandleFunc("GET /api/cpu-heavy", func(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    result := fib(40)
    elapsed := time.Since(start)

    writeJSON(w, http.StatusOK, map[string]any{
        "result":        result,
        "computeTimeMs": elapsed.Milliseconds(),
    })
})

func fib(n int) int {
    if n <= 1 {
        return n
    }
    return fib(n-1) + fib(n-2)
}
```

Start the CPU-heavy request and hit the health check simultaneously. The health check responds instantly. Go's goroutine scheduler preempts the CPU-bound goroutine and lets other goroutines run. No manual worker thread management needed.

---

## 7. Reflect: Which Model for Which Problem?

> **Reflect:** For each scenario, which concurrency model would you choose?
>
> 1. A chat application with 100K concurrent WebSocket connections
> 2. A video transcoding service that processes uploaded videos
> 3. A REST API that mostly reads from a database
> 4. A real-time trading system that needs sub-millisecond latency
> 5. A game server managing 10,000 player entities with independent state
>
> Suggested answers (there are multiple valid choices):
> 1. Event loop (Node.js) or goroutines (Go) -- I/O-bound, many connections
> 2. Thread pool (any language) -- CPU-bound, parallelism needed
> 3. Any async model -- I/O-bound, all four languages work fine
> 4. Rust (tokio) or Go -- minimal overhead, predictable latency, no GC pauses
> 5. Actor model (Erlang/Elixir) -- natural entity mapping, fault isolation

---

## 7. Checkpoint

Before continuing to the capstone, verify:

- [ ] You benchmarked all four servers at 10,000 concurrent connections
- [ ] You added a 100ms I/O delay and saw how sync Python collapses
- [ ] You understand why Node.js blocks on CPU-bound work
- [ ] You can explain the difference between threads, event loop, goroutines, and actors
- [ ] You know when to choose each concurrency model based on I/O-bound vs CPU-bound workloads

```bash
# Clean up the background servers
kill %1 %2 %3 %4 2>/dev/null  # Stop background processes
```

> **The key takeaway:** For I/O-bound web applications (which is most web applications), the concurrency model matters less than you think. All four handle it well. The difference shows up at extreme scale or with CPU-bound workloads. Choose based on your team, your ecosystem, and your specific bottleneck -- not based on synthetic benchmarks.

---

## What's Next

You have built, secured, logged, measured, and benchmarked TicketPulse across multiple languages. The capstone brings everything together: architecture review, load testing, and a plan for what comes next in Loop 2.

## Key Terms

| Term | Definition |
|------|-----------|
| **Thread** | An operating-system-level unit of execution that shares memory with other threads in the same process. |
| **Event loop** | A single-threaded programming construct that waits for and dispatches events or callbacks without blocking. |
| **Goroutine** | A lightweight concurrent function in Go that is scheduled by the Go runtime rather than the OS. |
| **Coroutine** | A generalizable subroutine that can suspend and resume execution at specific yield points. |
| **Async/await** | Language syntax that lets developers write asynchronous code in a sequential style using promises or futures. |

<!--
  CHAPTER: 18
  TITLE: Debugging, Profiling & Monitoring
  PART: IV — Cloud & Operations
  PREREQS: Chapter 4 (reliability concepts)
  KEY_TOPICS: debugging methodology, Node.js/Python/Go/Java debuggers, CPU/memory/IO profiling, flame graphs, Datadog, Prometheus, Grafana, ELK, OpenTelemetry, Sentry, production debugging, incident playbook
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 18: Debugging, Profiling & Monitoring

> **Part IV — Cloud & Operations** | Prerequisites: Chapter 4 (reliability concepts) | Difficulty: Intermediate → Advanced

Finding and fixing problems — systematic debugging methodology, language-specific profiling tools, and deep dives into every major monitoring platform from Datadog to Prometheus to Sentry.

### In This Chapter
- Debugging Methodology
- Language-Specific Debugging
- Profiling Deep Dive
- Monitoring Tools Deep Dive
- Production Debugging
- Incident Debugging Playbook

### Related Chapters
- Chapter 4 (observability/SRE theory)
- Chapter 13 (monitoring in system context)
- Chapter 11 (language-specific debugging)

---

## 1. DEBUGGING METHODOLOGY

### Systematic Debugging Process

Every bug fix should follow this cycle: **Reproduce -> Isolate -> Identify -> Fix -> Verify -> Prevent.**

1. **Reproduce:** Create the shortest, most reliable reproduction. If you cannot reproduce it, you cannot prove you fixed it. Capture exact inputs, environment, timing. Flaky bugs: increase logging and wait, or use stress tests to force the race.
2. **Isolate:** Shrink the problem space. Comment out code, disable features, swap components, use binary search. Goal: smallest possible system that still exhibits the bug.
3. **Identify:** Form a hypothesis, then test it. Read the code, read the error, read the logs. Do NOT guess randomly.
4. **Fix:** Change one thing at a time. Understand WHY the fix works. If you cannot explain it, you have not found the root cause.
5. **Verify:** Confirm the fix resolves the original reproduction. Run the full test suite. Check edge cases.
6. **Prevent:** Write a regression test. Add assertions, validation, or monitoring to catch recurrence. Update documentation if the failure mode was non-obvious.

### Rubber Duck Debugging

Explain the problem out loud, line by line, to an inanimate object (or a patient colleague). This works because:
- Verbalization forces you to serialize your understanding sequentially.
- You encounter gaps in your mental model when you cannot explain a step.
- The act of teaching activates different cognitive pathways than silent reading.

In practice: open a blank document and write "The request comes in at line X, then calls Y, which should return Z because..." -- the moment you write "should" and realize you have not verified it, you have found your next investigation target.

### Binary Search Debugging

When a bug exists somewhere in a large codebase or long execution path:
1. Find a point where behavior is correct (start) and incorrect (end).
2. Test the midpoint.
3. Narrow to the half that contains the transition from correct to incorrect.
4. Repeat until you have a single function, line, or commit.

Time complexity: O(log n) instead of O(n). For 1000 lines of suspect code, ~10 checks instead of 1000.

### Git Bisect

Automates binary search across commits to find the exact commit that introduced a regression.

```bash
# Manual bisect
git bisect start
git bisect bad                     # current commit is broken
git bisect good v2.1.0             # this tag was working
# Git checks out a midpoint commit. Test it, then:
git bisect good                    # or: git bisect bad
# Repeat until git identifies the first bad commit
git bisect reset                   # return to original HEAD

# Automated bisect with a test script
git bisect start HEAD v2.1.0
git bisect run ./test-regression.sh
# Script must exit 0 for good, 1-124/126-127 for bad, 125 for skip
```

**Pro tips:**
- Write the test script BEFORE starting bisect. It should be self-contained and fast.
- Use `git bisect skip` if a commit does not compile or is otherwise untestable.
- `git bisect log` shows history; `git bisect replay` re-runs from a log file.
- For merge-heavy histories, consider `git bisect --first-parent` to stay on the main branch.

### Reading Error Messages and Stack Traces

**Read from the bottom up** (most languages). The root cause is usually the innermost frame.

```
Traceback (most recent call last):
  File "main.py", line 45, in handle_request     # <-- entry point
    result = process(data)
  File "process.py", line 12, in process          # <-- intermediate
    return transform(data["key"])
KeyError: 'key'                                    # <-- ROOT CAUSE: read this first
```

**For JavaScript/Node.js:** Read top-down. The first line is the error, the first frame is where it was thrown.

**Key skills:**
- Distinguish YOUR code frames from library/framework frames. Start investigation in your code.
- Search the exact error message (with quotes) before reading source code.
- For async stack traces: enable `--async-stack-traces` (Node 12+) or `Error.stackTraceLimit = 50`.
- For minified stack traces: use source maps (`--enable-source-maps` in Node, upload to Sentry).

### The 5 Whys Technique

Drill past symptoms to root causes by asking "why" iteratively:

1. **Why** did the API return 500? -- The database query timed out.
2. **Why** did the query time out? -- It was doing a full table scan on 50M rows.
3. **Why** was it doing a full table scan? -- The `WHERE` clause column has no index.
4. **Why** is there no index? -- The migration that added the column did not include one.
5. **Why** did the migration ship without an index? -- There is no review checklist for schema changes.

Root cause: process gap. Fix: add a schema change checklist to the PR template. The query timeout is a symptom; the missing process is the cause.

**Pitfall:** Do not stop at the first technical cause. Keep asking until you reach something you can change systemically.

### Common Debugging Anti-Patterns

| Anti-Pattern | Problem | Better Approach |
|---|---|---|
| **Shotgun debugging** | Change random things hoping something works | Form a hypothesis first, test one change at a time |
| **Printf without hypothesis** | Scatter print statements everywhere | Add targeted logging at decision points based on your theory |
| **Blaming the tool** | "It must be a compiler/framework bug" | It is almost never the tool. Check your code first |
| **Debugging by diff** | "What changed recently?" without understanding | Useful as a starting point, but understand the WHY |
| **Pair debugging too early** | Grabbing a colleague before spending 15 minutes alone | Spend 15-30 minutes solo first to form your own mental model |
| **Not reading the error** | Googling symptoms without reading the actual message | Read. The. Error. Message. Completely. |
| **Fear of the debugger** | Only using print/log because "debuggers are slow to set up" | Invest 10 minutes to learn your debugger. It pays back 100x |

---

## 2. LANGUAGE-SPECIFIC DEBUGGING

### Node.js / TypeScript

**Node.js Inspector:**
```bash
# Start with debugger listening
node --inspect app.js              # listen on 127.0.0.1:9229
node --inspect-brk app.js         # break on first line
node --inspect=0.0.0.0:9229 app.js  # allow remote (use in Docker)

# For TypeScript with ts-node
node --inspect -r ts-node/register app.ts
```

**Chrome DevTools for Node.js:**
1. Start node with `--inspect`.
2. Open `chrome://inspect` in Chrome.
3. Click "inspect" under your Node process.
4. Full access: breakpoints, profiler, memory snapshots, console.

**VS Code Debugger (launch.json):**
```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Current File",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "${workspaceFolder}/node_modules/.bin/ts-node",
      "args": ["${file}"],
      "console": "integratedTerminal",
      "sourceMaps": true
    },
    {
      "name": "Attach to Running Process",
      "type": "node",
      "request": "attach",
      "port": 9229,
      "restart": true,
      "sourceMaps": true
    },
    {
      "name": "Debug Jest Tests",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "${workspaceFolder}/node_modules/.bin/jest",
      "args": ["--runInBand", "--no-cache", "${fileBasenameNoExtension}"],
      "console": "integratedTerminal"
    },
    {
      "name": "Debug Next.js",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npx",
      "args": ["next", "dev"],
      "console": "integratedTerminal",
      "serverReadyAction": {
        "pattern": "started server on .+, url: (https?://.+)",
        "uriFormat": "%s",
        "action": "debugWithChrome"
      }
    }
  ]
}
```

**Debugging Async Code:**
```bash
# Enable async stack traces (default in Node 16+)
node --async-stack-traces app.js

# For unhandled promise rejections (crash instead of silent swallow)
node --unhandled-rejections=throw app.js
```

Common async pitfalls to watch for:
- Missing `await` -- function returns Promise instead of resolved value.
- `Promise.all` vs `Promise.allSettled` -- the former rejects on first failure.
- Error swallowed in `.catch(() => {})` -- always log or rethrow.
- `async` in `forEach` -- does NOT await. Use `for...of` or `Promise.all(arr.map(...))`.

**Memory Leak Detection:**
```bash
# Heap profiling
node --heap-prof app.js            # generates .heapprofile on exit
node --heap-prof --heap-prof-interval=512 app.js  # more granular

# Take heap snapshots programmatically
node --expose-gc -e "
  const v8 = require('v8');
  const fs = require('fs');
  global.gc();  // force GC before snapshot
  const snap = v8.writeHeapSnapshot();
  console.log('Snapshot written to', snap);
"

# clinic.js suite
npx clinic doctor -- node app.js   # overall health check
npx clinic flame -- node app.js    # CPU flame graph
npx clinic bubbleprof -- node app.js  # async delays visualization
npx clinic heapprofiler -- node app.js  # memory allocation tracking

# Process-level memory monitoring
node -e "setInterval(() => {
  const mem = process.memoryUsage();
  console.log(JSON.stringify({
    rss: (mem.rss / 1e6).toFixed(1) + 'MB',
    heap: (mem.heapUsed / 1e6).toFixed(1) + 'MB',
    external: (mem.external / 1e6).toFixed(1) + 'MB'
  }));
}, 5000);"
```

### Python

**pdb / ipdb Interactive Debugger:**
```python
# Insert breakpoint (Python 3.7+)
breakpoint()  # drops into pdb; set PYTHONBREAKPOINT=ipdb.set_trace for ipdb

# Or explicitly:
import pdb; pdb.set_trace()
import ipdb; ipdb.set_trace()  # ipdb has tab completion, syntax highlighting
```

**Key pdb commands:**
| Command | Action |
|---|---|
| `n` (next) | Execute next line (step over) |
| `s` (step) | Step into function call |
| `c` (continue) | Continue to next breakpoint |
| `r` (return) | Continue until current function returns |
| `p expr` | Print expression |
| `pp expr` | Pretty-print expression |
| `l` (list) | Show source code around current line |
| `ll` (longlist) | Show entire current function |
| `w` (where) | Print stack trace |
| `u` / `d` | Move up/down the call stack |
| `b file:line` | Set breakpoint |
| `condition N expr` | Make breakpoint N conditional |
| `commands N` | Run commands when breakpoint N is hit |

**VS Code Python Debugger (launch.json):**
```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": false  // step into library code
    },
    {
      "name": "Debug FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "jinja": true
    },
    {
      "name": "Debug pytest",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["-xvs", "${file}"]
    }
  ]
}
```

**Memory Profiling:**
```python
# tracemalloc -- built-in, low overhead
import tracemalloc
tracemalloc.start()

# ... your code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)

# Compare two snapshots to find leaks
snapshot1 = tracemalloc.take_snapshot()
# ... code that might leak ...
snapshot2 = tracemalloc.take_snapshot()
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
for stat in top_stats[:10]:
    print(stat)

# memory_profiler -- line-by-line memory usage
# pip install memory_profiler
from memory_profiler import profile

@profile
def my_function():
    a = [1] * (10 ** 6)   # ~8 MB
    b = [2] * (2 * 10 ** 7)  # ~160 MB
    del b
    return a

# objgraph -- visualize object references (great for finding what holds refs)
# pip install objgraph
import objgraph
objgraph.show_most_common_types(limit=20)
objgraph.show_growth()  # call periodically to see what is accumulating
objgraph.show_backrefs(obj, max_depth=5, filename='refs.png')  # why is this alive?
```

**Debugging Async Python:**
```python
# Enable asyncio debug mode
import asyncio
asyncio.run(main(), debug=True)  # or set PYTHONASYNCIODEBUG=1

# Debug mode enables:
# - Log coroutines that were never awaited
# - Log callbacks taking >100ms
# - Log resource warnings for unclosed transports/sockets
# - Detailed tracebacks for tasks
```

### Go

**Delve Debugger:**
```bash
# Install
go install github.com/go-delve/delve/cmd/dlv@latest

# Debug a program
dlv debug ./cmd/server            # compile and debug
dlv debug ./cmd/server -- --port 8080  # pass args after --

# Debug tests
dlv test ./pkg/handler -- -run TestCreate  # debug specific test

# Attach to running process
dlv attach $(pgrep myserver)

# Core dump analysis
dlv core ./myserver core.12345

# Headless mode (for editor integration)
dlv debug --headless --listen=:2345 --api-version=2 ./cmd/server
```

**Key Delve commands:**
```
break main.go:42                  # set breakpoint
break mypackage.MyFunc            # break on function entry
condition 1 i > 100               # conditional breakpoint
on 1 print myVar                  # print var when breakpoint 1 hits
goroutines                        # list all goroutines
goroutine 23                      # switch to goroutine 23
stack                             # print stack trace
locals                            # print local variables
print myStruct.Field              # inspect values
whatis myVar                      # show type
```

**pprof for CPU and Memory Profiling:**
```go
// Add to your server:
import _ "net/http/pprof"
// Then http://localhost:6060/debug/pprof/ is available

// Or import explicitly and register:
import "net/http/pprof"
mux.HandleFunc("/debug/pprof/", pprof.Index)
```

```bash
# CPU profile (30 seconds by default)
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Memory (heap) profile
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine profile (find goroutine leaks)
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Inside pprof interactive mode:
top 20                            # top functions by CPU/memory
list myFunction                   # annotated source for a function
web                               # open flame graph in browser
pdf > profile.pdf                 # export as PDF

# Generate flame graph directly
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30
```

**Race Detector:**
```bash
go run -race ./cmd/server         # run with race detector
go test -race ./...               # test with race detector
go build -race -o myserver ./cmd/server  # build with race detector

# Output on race detection:
# WARNING: DATA RACE
# Goroutine 7 at 0x... (read):  main.go:42
# Goroutine 12 at 0x... (write): main.go:58
# The stack traces show exactly which goroutines and lines conflict
```

**Goroutine Leak Detection:**
```go
// In tests, use goleak:
// go get go.uber.org/goleak
import "go.uber.org/goleak"

func TestMain(m *testing.M) {
    goleak.VerifyTestMain(m)
}

// Or per-test:
func TestNoLeak(t *testing.T) {
    defer goleak.VerifyNone(t)
    // ... test code ...
}
```

```bash
# Monitor goroutine count at runtime
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | head -1
# "goroutine profile: total 147"
# If this number grows unboundedly over time, you have a leak
```

### Java / JVM

**JVM Debugging:**
```bash
# Start JVM with remote debugging enabled
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar app.jar
# suspend=y to wait for debugger before starting (useful for startup bugs)

# jdb command-line debugger (rarely used directly, but available everywhere)
jdb -connect com.sun.jdi.SocketAttach:hostname=localhost,port=5005

# VS Code / IntelliJ: point remote debug config at localhost:5005
```

**JVisualVM and JConsole:**
```bash
# JConsole -- included with JDK, connects to local or remote JVM
jconsole                          # GUI: memory, threads, classes, MBeans
jconsole localhost:9999           # connect to JMX port

# JVisualVM -- more powerful (separate download since JDK 9)
# Features: CPU/memory profiling, thread visualization, heap dumps, sampler
```

**Java Flight Recorder (JFR) + Mission Control:**
```bash
# Start recording with JVM
java -XX:StartFlightRecording=duration=60s,filename=recording.jfr -jar app.jar

# Start/stop recording on running JVM
jcmd <pid> JFR.start duration=60s filename=recording.jfr
jcmd <pid> JFR.dump filename=recording.jfr
jcmd <pid> JFR.stop

# Continuous recording with max size
java -XX:StartFlightRecording=maxsize=500m,disk=true,dumponexit=true,filename=app.jfr -jar app.jar

# Open in JDK Mission Control (jmc) for analysis:
# - Method profiling (flame graph equivalent)
# - Memory allocation tracking by call site
# - GC pauses with before/after heap state
# - I/O latency breakdown
# - Lock contention analysis
# - Thread state timeline
```

**Thread Dumps and Heap Dumps:**
```bash
# Thread dump (three ways)
kill -3 <pid>                     # prints to stderr
jstack <pid>                      # standalone tool
jcmd <pid> Thread.print           # modern approach

# What to look for in thread dumps:
# - BLOCKED threads waiting on the same monitor = potential deadlock
# - Many threads in WAITING state on the same condition = bottleneck
# - "Found one Java-level deadlock" = jstack detects simple deadlocks

# Heap dump
jmap -dump:live,format=b,file=heap.hprof <pid>
jcmd <pid> GC.heap_dump heap.hprof

# Auto heap dump on OOM
java -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heapdump.hprof -jar app.jar

# Analyze with Eclipse MAT, VisualVM, or jhat:
# - Dominator tree: what objects retain the most memory
# - Leak suspects report: automatic analysis
# - Histogram: object count by class
# - Path to GC root: why an object is not collected
```

**GC Log Analysis:**
```bash
# Enable GC logging
java -Xlog:gc*:file=gc.log:time,uptime,level,tags -jar app.jar

# Key things to look for:
# - Full GC frequency (should be rare)
# - GC pause times (should be < 200ms for most apps)
# - Heap after GC trending upward = memory leak
# - Tools: GCEasy.io (upload gc.log), GCViewer, Eclipse GC Toolkit
```

---

## 3. PROFILING DEEP DIVE

### CPU Profiling

**Flame Graphs -- How to Read Them:**
- X-axis: proportion of total samples (NOT time sequence). Wider = more CPU time.
- Y-axis: stack depth. Bottom = entry point, top = leaf function (where CPU actually runs).
- Color: typically random or grouped by module. Not meaningful by default.
- **Look for:** Wide plateaus at the top (functions consuming lots of CPU), wide towers (deep call stacks that dominate), and unexpected functions.

**Generating Flame Graphs:**
```bash
# Linux perf + Brendan Gregg's scripts
perf record -F 99 -p <pid> -g -- sleep 30
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg

# Go
go tool pprof -http=:8081 cpu.prof   # built-in flame graph view

# Node.js
npx clinic flame -- node app.js      # generates interactive HTML
# or: node --cpu-prof app.js && speedscope cpu.*.cpuprofile

# Python
pip install py-spy
py-spy record -o profile.svg --pid <pid>     # sampling, no code changes
py-spy record -o profile.svg -- python app.py  # launch and profile
py-spy top --pid <pid>                        # live top-like view

# Java
# async-profiler (handles JIT, inlining, native code correctly)
./asprof -d 30 -f profile.html <pid>         # 30 second profile
./asprof -e alloc -d 30 -f alloc.html <pid>  # allocation profiling
```

**Sampling vs Instrumentation Profilers:**

| Aspect | Sampling | Instrumentation |
|---|---|---|
| **Mechanism** | Periodically capture stack trace | Wrap every function with timing code |
| **Overhead** | Low (1-5%) | High (10-100x slowdown) |
| **Accuracy** | Statistical (misses short functions) | Exact counts and times |
| **Use when** | Finding hot spots in production | Precise measurement in dev/test |
| **Examples** | perf, py-spy, async-profiler | cProfile, gprof, JProfiler instrumentation mode |

**Linux perf:**
```bash
# System-wide CPU profiling
perf stat ./myprogram              # high-level counters (IPC, cache misses, branch mispredictions)
perf record -g ./myprogram         # record call stacks
perf report                        # interactive TUI analysis

# Specific events
perf stat -e cache-misses,cache-references,instructions,cycles ./myprogram
perf record -e cache-misses -g ./myprogram

# Flame graph from perf
perf script > out.perf
# Use flamegraph.pl or import into speedscope
```

### Memory Profiling

**Heap Snapshots and Diffing:**

The most powerful technique for finding memory leaks:
1. Take snapshot at baseline (after warmup).
2. Run the suspected leaking operation N times.
3. Force garbage collection.
4. Take second snapshot.
5. Diff the two snapshots -- objects that grew proportionally to N are your leak.

**In Chrome DevTools (Node.js):**
1. Connect to `node --inspect` process.
2. Memory tab -> Take heap snapshot.
3. Perform operation.
4. Take second snapshot.
5. Select "Comparison" view between snapshots.
6. Sort by "# Delta" or "Size Delta" to find growing objects.

**Memory Leak Patterns:**

| Pattern | Example | Fix |
|---|---|---|
| **Event listeners not removed** | `emitter.on('data', handler)` in a function called repeatedly | Store reference, call `removeListener` in cleanup |
| **Closures capturing scope** | Closure holds reference to large parent scope variable | Null out references, restructure closure |
| **Unbounded caches** | `const cache = {}; cache[key] = value` forever | Use LRU cache with max size (`lru-cache`, `@isaacs/lru-cache`) |
| **Circular references** | Object A references B, B references A | Usually fine for GC, but problematic with C++ addons, `JSON.stringify` |
| **Detached DOM nodes** | JS holds reference to removed DOM element | Clear references when removing from DOM |
| **Global variables** | Accidentally creating globals (`x = 5` without `let/const/var`) | Use strict mode, linting rules |
| **Timers not cleared** | `setInterval` without `clearInterval` | Store interval ID, clear on cleanup |
| **Streams not consumed** | Readable stream created but never piped or read | Always consume or destroy streams |

### I/O Profiling

**PostgreSQL Query Analysis:**
```sql
-- Enable pg_stat_statements (in postgresql.conf)
-- shared_preload_libraries = 'pg_stat_statements'

-- Top queries by total time
SELECT query, calls, total_exec_time, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Top queries by calls (high frequency)
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 20;

-- Reset statistics
SELECT pg_stat_statements_reset();
```

**EXPLAIN ANALYZE Deep Dive:**
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

**How to read the output:**
```
Nested Loop  (cost=0.87..123.45 rows=10 width=200) (actual time=0.05..15.23 rows=10 loops=1)
  ->  Index Scan using idx_users_email on users  (cost=0.43..8.45 rows=1 width=100) (actual time=0.03..0.04 rows=1 loops=1)
        Index Cond: (email = 'test@example.com')
        Buffers: shared hit=4
  ->  Index Scan using idx_orders_user_id on orders  (cost=0.43..11.40 rows=10 width=100) (actual time=0.01..0.12 rows=10 loops=1)
        Index Cond: (user_id = users.id)
        Buffers: shared hit=12
Planning Time: 0.15 ms
Execution Time: 15.35 ms
```

**Key things to look for:**
- **Seq Scan on large tables:** Missing index. Compare `cost` estimate to `actual time`.
- **Rows estimate vs actual:** Large mismatch means stale statistics. Run `ANALYZE tablename;`.
- **Nested Loop with high loops count:** Consider if a Hash Join would be better.
- **Buffers: shared read (vs hit):** Reads go to disk, hits come from cache. High reads = cold cache or table too large for memory.
- **Sort with external merge:** Sort spilling to disk. Increase `work_mem` or add an index.

**MySQL Slow Query Log:**
```ini
# In my.cnf
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 0.5        # seconds
log_queries_not_using_indexes = 1
```

```bash
# Analyze slow query log
mysqldumpslow -s t /var/log/mysql/slow.log    # sorted by total time
pt-query-digest /var/log/mysql/slow.log       # Percona Toolkit, more detailed
```

**Connection Pool Monitoring:**
```sql
-- PostgreSQL: current connections
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
-- idle | 15
-- active | 3
-- idle in transaction | 2   <-- these are problematic if they linger

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '5 seconds'
ORDER BY duration DESC;

-- Kill a stuck query
SELECT pg_cancel_backend(<pid>);    -- graceful
SELECT pg_terminate_backend(<pid>); -- forceful
```

**Network Profiling:**
```bash
# tcpdump -- capture packets
tcpdump -i eth0 -nn port 5432       # capture PostgreSQL traffic
tcpdump -i any -w capture.pcap      # save for Wireshark analysis
tcpdump -A -s0 port 80              # print HTTP request/response bodies

# mtr -- network path analysis (traceroute + ping)
mtr --report --report-cycles 100 api.example.com
# Shows: packet loss and latency at each hop

# ss -- socket statistics (faster than netstat)
ss -tlnp                            # listening TCP sockets with process names
ss -tn state established            # established connections
ss -s                               # summary statistics

# curl timing breakdown
curl -w "\n  DNS: %{time_namelookup}s\n  Connect: %{time_connect}s\n  TLS: %{time_appconnect}s\n  TTFB: %{time_starttransfer}s\n  Total: %{time_total}s\n" -o /dev/null -s https://api.example.com/health
```

### Application Profiling

**Request Tracing End-to-End:**

For any slow request, break down where time is spent:

```
Total request time: 1200ms
├── Middleware (auth, logging): 5ms
├── Input validation: 2ms
├── Database query 1 (user lookup): 15ms
├── Database query 2 (permissions): 180ms    <-- SUSPICIOUS
├── External API call (payment): 350ms       <-- EXPECTED but monitor
├── Business logic computation: 8ms
├── Database query 3 (write order): 25ms
├── Response serialization: 3ms
└── Unaccounted: 612ms                       <-- WHERE IS THIS GOING?
```

If you cannot account for time, likely culprits: DNS resolution, connection establishment, TLS handshake, connection pool wait time, GC pauses, or untracked async operations.

**Instrumentation approach:**
```typescript
// Simple timing wrapper
function timed<T>(label: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  try {
    return await fn();
  } finally {
    const ms = (performance.now() - start).toFixed(2);
    console.log(`[timing] ${label}: ${ms}ms`);
  }
}

// Usage
const user = await timed('db:getUser', () => db.users.findById(id));
const payment = await timed('api:processPayment', () => paymentAPI.charge(amount));
```

---

## 4. MONITORING TOOLS DEEP DIVE

### Datadog

**Agent Installation:**
```bash
# Linux (one-line install)
DD_API_KEY=<your-api-key> DD_SITE="datadoghq.com" bash -c \
  "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"

# Docker
docker run -d --name dd-agent \
  -e DD_API_KEY=<your-api-key> \
  -e DD_SITE="datadoghq.com" \
  -e DD_APM_ENABLED=true \
  -e DD_LOGS_ENABLED=true \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc/:/host/proc/:ro \
  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
  -p 8126:8126 \
  gcr.io/datadoghq/agent:7

# Kubernetes (Helm)
helm install datadog-agent datadog/datadog \
  --set datadog.apiKey=<your-api-key> \
  --set datadog.site=datadoghq.com \
  --set datadog.apm.portEnabled=true \
  --set datadog.logs.enabled=true \
  --set datadog.logs.containerCollectAll=true
```

**APM Setup (Node.js example):**
```typescript
// dd-trace must be imported FIRST, before any other modules
import 'dd-trace/init';
// or with configuration:
import tracer from 'dd-trace';
tracer.init({
  service: 'my-api',
  env: process.env.NODE_ENV,
  version: process.env.APP_VERSION,
  logInjection: true,           // correlate logs with traces
  runtimeMetrics: true,         // event loop lag, GC, heap stats
  profiling: true,              // continuous profiling
});
```

**Custom Metrics:**
```typescript
import { StatsD } from 'hot-shots';
const metrics = new StatsD({ prefix: 'myapp.' });

// Counter (things that only go up)
metrics.increment('orders.created', 1, { region: 'us-east' });

// Gauge (current value)
metrics.gauge('queue.depth', 42);

// Histogram (distribution of values)
metrics.histogram('request.duration', responseTimeMs, { endpoint: '/api/users' });

// Distribution (like histogram but computed server-side, more flexible)
metrics.distribution('payment.amount', amount, { currency: 'usd' });
```

**Monitor Types and When to Use:**
| Monitor Type | Use For | Example |
|---|---|---|
| **Metric** | Threshold on any metric | CPU > 90% for 5 min |
| **APM** | Service-level latency/errors | p99 latency > 500ms |
| **Log** | Pattern in logs | "OutOfMemoryError" count > 0 |
| **Composite** | Multiple conditions | High error rate AND high latency |
| **Anomaly** | Deviation from historical pattern | Traffic 3 sigma below normal |
| **Forecast** | Predict future threshold breach | Disk full in < 48 hours |
| **SLO** | Error budget burn rate | >2% budget consumed in 1 hour |

**Cost Optimization Tips:**
- Use `exclude_tags` on high-cardinality metrics (user IDs, request IDs).
- Set custom metric aggregations to reduce unique timeseries.
- Use log exclusion filters to drop debug logs before indexing.
- Archive logs to S3 instead of long retention in Datadog.
- Use `distribution` metrics instead of `histogram` when you need percentiles (fewer timeseries).

### Prometheus + Grafana

**Prometheus Architecture:**

Prometheus scrapes targets at configured intervals, stores data in a local TSDB, evaluates alert rules, and exposes PromQL for querying. It is pull-based (scrapes endpoints), not push-based.

**Instrumentation (Go example):**
```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    httpRequestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total HTTP requests",
        },
        []string{"method", "endpoint", "status"},
    )
    httpRequestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "http_request_duration_seconds",
            Help:    "HTTP request latency",
            Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
        },
        []string{"method", "endpoint"},
    )
    activeConnections = prometheus.NewGauge(
        prometheus.GaugeOpts{
            Name: "active_connections",
            Help: "Currently active connections",
        },
    )
)

func init() {
    prometheus.MustRegister(httpRequestsTotal, httpRequestDuration, activeConnections)
}

// Expose metrics endpoint
http.Handle("/metrics", promhttp.Handler())
```

**Key PromQL Patterns:**
```promql
# Request rate (per second, over 5 minutes)
rate(http_requests_total[5m])

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m]))
/ sum(rate(http_requests_total[5m])) * 100

# p99 latency from histogram
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# p99 by endpoint
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)
)

# Increase over time window (good for counters)
increase(http_requests_total[1h])

# Top 5 endpoints by request rate
topk(5, sum by (endpoint) (rate(http_requests_total[5m])))

# Predict disk full (linear extrapolation)
predict_linear(node_filesystem_avail_bytes[6h], 3600 * 24)

# Absent alert (detect missing metric / dead service)
absent(up{job="my-service"})
```

**Alertmanager Configuration:**
```yaml
# alertmanager.yml
route:
  receiver: 'slack-default'
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      repeat_interval: 15m
    - match:
        severity: warning
      receiver: 'slack-warnings'

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'
  - name: 'slack-warnings'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#alerts-warning'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

# Silence noisy alerts during maintenance
# Use Alertmanager UI or amtool
amtool silence add alertname=HighCPU --duration=2h --comment="Planned batch job"
```

**Recording Rules (for performance):**
```yaml
# prometheus-rules.yml
groups:
  - name: request_rates
    interval: 15s
    rules:
      - record: job:http_requests_total:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
      - record: job:http_request_duration_seconds:p99_5m
        expr: histogram_quantile(0.99, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))
```

Use recording rules when: a PromQL query is used in multiple dashboards/alerts, or when it is computationally expensive and would timeout on ad-hoc queries.

**Prometheus Operator for Kubernetes:**
```yaml
# ServiceMonitor CRD -- auto-discovers pods to scrape
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-api
  labels:
    release: prometheus   # must match Prometheus operator selector
spec:
  selector:
    matchLabels:
      app: my-api
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

### ELK Stack (Elasticsearch + Logstash + Kibana)

**Architecture:**
```
Applications -> Filebeat/Fluentd -> Logstash -> Elasticsearch -> Kibana
                (collection)       (transform)   (store+index)  (visualize)
```

**Logstash Pipeline:**
```ruby
# /etc/logstash/conf.d/pipeline.conf
input {
  beats {
    port => 5044
  }
}

filter {
  # Parse JSON logs
  if [message] =~ /^\{/ {
    json {
      source => "message"
    }
  }

  # Parse unstructured logs with grok
  grok {
    match => {
      "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} \[%{DATA:service}\] %{GREEDYDATA:msg}"
    }
  }

  # Parse timestamps
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }

  # Add geo data from IP
  geoip {
    source => "client_ip"
  }

  # Drop health check noise
  if [request_path] == "/health" {
    drop {}
  }

  # Enrich with lookup
  translate {
    field => "status_code"
    destination => "status_category"
    dictionary => {
      "200" => "success"
      "404" => "not_found"
      "500" => "server_error"
    }
  }
}

output {
  elasticsearch {
    hosts => ["https://elasticsearch:9200"]
    index => "logs-%{[service]}-%{+YYYY.MM.dd}"
    user => "elastic"
    password => "${ES_PASSWORD}"
  }
}
```

**Elasticsearch Index Lifecycle Management (ILM):**
```json
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": { "snapshot_repository": "my-repo" }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

**KQL (Kibana Query Language):**
```
# Simple field matching
status: 500
service: "payment-api" and level: "error"

# Wildcards
message: *timeout*

# Range
response_time > 1000
@timestamp >= "2024-01-01" and @timestamp < "2024-02-01"

# Nested
kubernetes.labels.app: "my-service"

# Negation
NOT status: 200
```

**Alternative: Loki + Grafana:**

Loki indexes only labels (metadata), not the full log content. Drastically cheaper storage, but queries on log content are slower (grep-like scan).

```yaml
# promtail config (Loki's log shipper)
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      - docker: {}
      - match:
          selector: '{app="my-api"}'
          stages:
            - json:
                expressions:
                  level: level
                  msg: message
            - labels:
                level:
```

```
# LogQL (Loki's query language)
{app="my-api"} |= "error"                              # contains "error"
{app="my-api"} | json | level="error" | line_format "{{.msg}}"
{app="my-api"} | json | duration > 1s                  # parsed field filtering
sum(rate({app="my-api"} |= "error" [5m])) by (level)   # metric from logs
```

### OpenTelemetry

**The Three Signals:**
- **Traces:** Request flow across services. A trace contains spans; each span represents a unit of work (HTTP call, DB query, function execution).
- **Metrics:** Numeric measurements over time (counters, gauges, histograms).
- **Logs:** Discrete events with context. Correlated with traces via trace_id/span_id.

**Auto-Instrumentation (Node.js):**
```typescript
// tracing.ts -- must be loaded before application code
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';

const sdk = new NodeSDK({
  serviceName: 'my-api',
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4318/v1/traces',
  }),
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: 'http://otel-collector:4318/v1/metrics',
    }),
    exportIntervalMillis: 15000,
  }),
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-http': { enabled: true },
      '@opentelemetry/instrumentation-express': { enabled: true },
      '@opentelemetry/instrumentation-pg': { enabled: true },
      '@opentelemetry/instrumentation-redis': { enabled: true },
    }),
  ],
});

sdk.start();
```

```bash
# Run with auto-instrumentation (no code changes)
node --require ./tracing.ts app.ts
# or: NODE_OPTIONS="--require ./tracing.js" node app.js
```

**Manual Instrumentation (adding custom spans):**
```typescript
import { trace, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('my-service');

async function processOrder(orderId: string) {
  return tracer.startActiveSpan('processOrder', async (span) => {
    span.setAttribute('order.id', orderId);
    try {
      const result = await validateOrder(orderId);
      span.setAttribute('order.items', result.itemCount);
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
      span.recordException(error as Error);
      throw error;
    } finally {
      span.end();
    }
  });
}
```

**Collector Configuration:**
```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 1024
  attributes:
    actions:
      - key: environment
        value: production
        action: upsert

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  otlp/datadog:
    endpoint: https://api.datadoghq.com
    headers:
      DD-API-KEY: ${DD_API_KEY}
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, attributes]
      exporters: [otlp/jaeger, otlp/datadog]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

**Context Propagation (W3C TraceContext):**

When service A calls service B, the trace context must be propagated via HTTP headers:
```
traceparent: 00-<trace-id>-<span-id>-<flags>
tracestate: vendor1=value1,vendor2=value2
```

Auto-instrumentation handles this for HTTP clients/servers. For manual propagation (e.g., message queues):
```typescript
import { propagation, context } from '@opentelemetry/api';

// Inject into carrier (producer side)
const carrier: Record<string, string> = {};
propagation.inject(context.active(), carrier);
// Attach carrier to message headers

// Extract from carrier (consumer side)
const extractedContext = propagation.extract(context.active(), messageHeaders);
context.with(extractedContext, () => {
  // This code runs within the extracted trace context
  tracer.startActiveSpan('processMessage', (span) => { /* ... */ });
});
```

### New Relic

**APM Setup (Node.js):**
```javascript
// newrelic.js in project root
'use strict';
exports.config = {
  app_name: ['my-api'],
  license_key: process.env.NEW_RELIC_LICENSE_KEY,
  distributed_tracing: { enabled: true },
  logging: { level: 'info' },
  allow_all_headers: true,
  attributes: {
    exclude: ['request.headers.cookie', 'request.headers.authorization'],
  },
};
// Then: node -r newrelic app.js
```

**NRQL (New Relic Query Language):**
```sql
-- Error rate by service
SELECT percentage(count(*), WHERE error IS true) AS 'Error Rate'
FROM Transaction
WHERE appName = 'my-api'
FACET name
SINCE 1 hour ago

-- p99 latency trend
SELECT percentile(duration, 99) FROM Transaction
WHERE appName = 'my-api'
TIMESERIES 5 minutes SINCE 24 hours ago

-- Slow external calls
SELECT average(duration) FROM ExternalTransaction
WHERE appName = 'my-api'
FACET host SINCE 1 hour ago

-- Deployment impact analysis
SELECT count(*), average(duration), percentage(count(*), WHERE error IS true)
FROM Transaction
WHERE appName = 'my-api'
SINCE 1 hour ago COMPARE WITH 1 hour ago TIMESERIES

-- Custom events
SELECT count(*) FROM OrderProcessed
WHERE status = 'failed'
FACET failureReason SINCE 1 day ago
```

### Sentry

**Error Tracking Setup (JavaScript):**
```typescript
import * as Sentry from '@sentry/node';

Sentry.init({
  dsn: 'https://examplePublicKey@o0.ingest.sentry.io/0',
  environment: process.env.NODE_ENV,
  release: process.env.APP_VERSION,   // enables release tracking
  tracesSampleRate: 0.1,              // 10% of transactions for performance
  profilesSampleRate: 0.1,            // 10% of sampled transactions for profiling
  integrations: [
    Sentry.httpIntegration(),
    Sentry.expressIntegration(),
    Sentry.prismaIntegration(),
  ],
  beforeSend(event) {
    // Scrub sensitive data
    if (event.request?.headers) {
      delete event.request.headers['authorization'];
    }
    return event;
  },
});

// Express middleware
app.use(Sentry.expressErrorHandler());

// Manual error capture with context
try {
  await processOrder(order);
} catch (error) {
  Sentry.withScope((scope) => {
    scope.setTag('order.type', order.type);
    scope.setUser({ id: order.userId });
    scope.setExtra('orderDetails', order);
    scope.setLevel('error');
    Sentry.captureException(error);
  });
}
```

**Source Maps for Minified Code:**
```bash
# Upload source maps during build
npx @sentry/cli releases new $VERSION
npx @sentry/cli releases files $VERSION upload-sourcemaps ./dist \
  --url-prefix '~/static/js' \
  --validate
npx @sentry/cli releases finalize $VERSION

# Associate commits with release (shows suspect commits in Sentry UI)
npx @sentry/cli releases set-commits $VERSION --auto
```

**Python Setup:**
```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    environment=os.environ.get("ENV", "development"),
    release=os.environ.get("APP_VERSION"),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[DjangoIntegration(), SqlalchemyIntegration()],
)
```

**Go Setup:**
```go
import "github.com/getsentry/sentry-go"

func main() {
    err := sentry.Init(sentry.ClientOptions{
        Dsn:              os.Getenv("SENTRY_DSN"),
        Environment:      os.Getenv("ENV"),
        Release:          os.Getenv("APP_VERSION"),
        TracesSampleRate: 0.1,
    })
    if err != nil {
        log.Fatalf("sentry.Init: %s", err)
    }
    defer sentry.Flush(2 * time.Second)

    // Capture panics
    defer sentry.Recover()
}
```

---

## 5. PRODUCTION DEBUGGING

### Debugging Without SSH Access

Modern cloud-native systems (serverless, Kubernetes, PaaS) often do not allow SSH. You debug through observability.

**The observability-only approach:**
1. **Structured logs** are your primary tool. Every log line should be JSON with: timestamp, level, service, trace_id, span_id, and relevant business context.
2. **Distributed traces** show the request flow across services. Find the failing trace by error status or high latency.
3. **Metrics** reveal patterns: is this a single request or a systemic issue? When did it start? What changed?
4. **Dashboards** give context: correlate the incident with deployments, traffic changes, dependency health.

### Structured Logging

```typescript
// Use structured logging -- NOT console.log with string concatenation
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  redact: ['req.headers.authorization', 'user.email'],  // PII protection
});

// Correlation IDs (set via middleware, propagate everywhere)
app.use((req, res, next) => {
  const requestId = req.headers['x-request-id'] || crypto.randomUUID();
  const traceId = req.headers['traceparent']?.split('-')[1];
  req.log = logger.child({
    requestId,
    traceId,
    method: req.method,
    path: req.path,
    userId: req.user?.id,
  });
  next();
});

// Then in handlers:
req.log.info({ orderId, amount }, 'Processing payment');
req.log.error({ err, orderId }, 'Payment failed');
// Output: {"level":"error","requestId":"abc-123","traceId":"def-456","orderId":"ord-789","err":{"message":"timeout","stack":"..."},"msg":"Payment failed"}
```

### Feature Flags for Debugging

Enable verbose logging for a specific user or request without redeploying:

```typescript
// Feature flag: debug_logging_users = ["user-123", "user-456"]
function getLogLevel(userId: string): string {
  if (featureFlags.isEnabled('debug_logging_users', { userId })) {
    return 'debug';
  }
  return 'info';
}

// Or: header-based debug mode
app.use((req, res, next) => {
  if (req.headers['x-debug'] === process.env.DEBUG_SECRET) {
    req.log = req.log.child({ level: 'trace' });
    // Also add response timing headers
    res.setHeader('Server-Timing', `total;dur=${Date.now() - req.startTime}`);
  }
  next();
});
```

### Canary Debugging

Deploy the suspect fix to a small percentage of traffic and compare:

```yaml
# Kubernetes canary with Argo Rollouts
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  strategy:
    canary:
      steps:
        - setWeight: 5          # 5% of traffic
        - pause: { duration: 10m }
        - analysis:
            templates:
              - templateName: error-rate-check
        - setWeight: 25
        - pause: { duration: 10m }
        - setWeight: 50
        - pause: { duration: 10m }

---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-rate-check
spec:
  metrics:
    - name: error-rate
      interval: 60s
      failureLimit: 3
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(http_requests_total{status=~"5..",app="my-api",version="canary"}[5m]))
            / sum(rate(http_requests_total{app="my-api",version="canary"}[5m]))
      successCondition: result[0] < 0.01  # < 1% error rate
```

### Core Dumps and Post-Mortem Debugging

```bash
# Enable core dumps
ulimit -c unlimited
echo '/tmp/core.%e.%p.%t' | sudo tee /proc/sys/kernel/core_pattern

# Node.js: generate core dump on crash
node --abort-on-uncaught-exception app.js

# Analyze with llnode (Node.js) or gdb (C/C++/Go)
llnode -c /tmp/core.node.12345
# > v8 bt          -- JavaScript stack trace
# > v8 findjsobjects  -- find JS objects in heap
# > v8 inspect <address>  -- inspect specific object

# Go: analyze with delve
dlv core ./myserver /tmp/core.myserver.12345
# > goroutines     -- show all goroutine stacks
# > goroutine 1    -- switch to goroutine
# > bt             -- backtrace
```

### eBPF for Production Debugging

eBPF allows attaching programs to kernel and user-space functions with negligible overhead. No application restart required.

```bash
# bpftrace one-liners

# Trace all syscalls by a process
bpftrace -e 'tracepoint:syscalls:sys_enter_* /pid == 12345/ { @[probe] = count(); }'

# Latency histogram of read() calls
bpftrace -e 'tracepoint:syscalls:sys_enter_read /pid == 12345/ { @start[tid] = nsecs; }
  tracepoint:syscalls:sys_exit_read /pid == 12345 && @start[tid]/ {
    @us = hist((nsecs - @start[tid]) / 1000);
    delete(@start[tid]);
  }'

# Trace TCP connections
bpftrace -e 'kprobe:tcp_connect { printf("connect: pid=%d comm=%s\n", pid, comm); }'

# Using bcc tools (higher-level)
tcpconnect          # trace TCP connect() calls (outbound connections)
tcplife             # trace TCP sessions with duration and throughput
opensnoop           # trace file opens
biolatency          # block I/O latency histogram
funclatency         # function latency (user or kernel)
```

---

## 6. INCIDENT DEBUGGING PLAYBOOK

When something breaks in production, follow this sequence. Speed matters, but so does systematic thinking. Do not skip steps.

### Step 1: Assess Impact

**Questions to answer immediately (< 2 minutes):**
- Who is affected? (All users, specific region, specific feature, internal only)
- What is broken? (Complete outage, degraded, intermittent, cosmetic)
- When did it start? (Check error rate graphs -- the inflection point is your timeline anchor)
- How many? (Error count, affected user count, revenue impact estimate)

**Actions:**
```bash
# Quick impact check queries (adjust to your monitoring tool)

# Datadog
# Dashboard: error rate spike? latency spike? traffic drop?
# APM > Service Map: which service is red?

# PromQL
sum(rate(http_requests_total{status=~"5.."}[5m]))  # current error rate
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))  # error percentage
```

**Communication:** Immediately post in the incident channel: "Investigating elevated error rates on [service]. Impact: [description]. Updates every 15 minutes."

### Step 2: Check Recent Changes

Most incidents are caused by a recent change. Check these in order:

```bash
# Recent deployments
git log --oneline --since="2 hours ago" main
kubectl rollout history deployment/my-api
vercel ls --limit 5

# Config changes
# Check your config management system (Consul, AWS Parameter Store, etc.)
aws ssm get-parameters-by-path --path /prod/ --query 'Parameters[].{Name:Name,Modified:LastModifiedDate}' --output table

# Feature flag changes
# Check your feature flag system's audit log

# Dependency updates
# Check if any auto-update merged (Dependabot, Renovate)

# Infrastructure changes
# Check Terraform/CloudFormation change history
# Check cloud provider event log
```

**If you find a recent change that correlates with the incident start time, strongly consider rolling back immediately before investigating further.** Fix forward only if the rollback is riskier than the current state.

### Step 3: Check Dashboards

Look for THE FOUR GOLDEN SIGNALS (Google SRE):

| Signal | What to Look For |
|---|---|
| **Latency** | p50, p95, p99 increased? Bi-modal distribution (some fast, some slow)? |
| **Traffic** | Unexpected spike or drop? Traffic shift between endpoints? |
| **Errors** | Error rate spike? New error types appearing? |
| **Saturation** | CPU, memory, disk, connections approaching limits? |

Check service dependencies: is YOUR service failing, or is it a downstream dependency?

### Step 4: Check Logs

```bash
# Search for errors in the incident time window

# Kibana/KQL
level: "error" AND service: "payment-api" AND @timestamp >= "2024-01-15T14:00:00"

# Loki/LogQL
{service="payment-api"} |= "error" | json | level="error"

# Datadog Logs
service:payment-api status:error @timestamp:[now-1h TO now]

# CloudWatch Logs Insights
fields @timestamp, @message
| filter @message like /error|Error|ERROR/
| sort @timestamp desc
| limit 100
```

**What to look for:**
- The FIRST error (often the root cause; subsequent errors are cascading failures).
- Error patterns: are all errors the same, or are there multiple types?
- Correlation with specific users, endpoints, or request attributes.
- Warnings that started before the errors (often early signals).

### Step 5: Check Infrastructure

```bash
# Kubernetes
kubectl top pods -n production          # CPU/memory usage
kubectl get pods -n production          # pod status (CrashLoopBackOff, OOMKilled, etc.)
kubectl describe pod <pod-name> -n production  # events, exit codes
kubectl logs <pod-name> --previous -n production  # logs from crashed container

# Linux host
top / htop                              # CPU, memory overview
iostat -x 1                             # disk I/O saturation
free -h                                 # memory breakdown
df -h                                   # disk space
dmesg | tail -50                        # kernel messages (OOM killer, hardware errors)

# Network
ss -tlnp                               # listening ports
ss -tn state established | wc -l       # connection count
```

### Step 6: Check Dependencies

```bash
# Database
# PostgreSQL
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 10;

# Redis
redis-cli info stats | grep -E "connected_clients|blocked_clients|used_memory_human"
redis-cli --latency                      # measure latency
redis-cli slowlog get 10                 # recent slow commands

# External APIs
# Check status pages: status.stripe.com, status.aws.amazon.com, etc.
# Check your synthetic monitors for external dependency health
```

### Step 7: Isolate and Rollback

```bash
# Kubernetes rollback
kubectl rollout undo deployment/my-api -n production
kubectl rollout status deployment/my-api -n production

# Vercel rollback
vercel rollback <previous-deployment-url>

# Feature flag: disable suspicious feature
# (fastest "rollback" if the issue is in a flagged feature)

# Traffic shift: route away from problematic instance/region
# Update load balancer, DNS, or service mesh routing
```

### Step 8: Root Cause Analysis

Once the incident is mitigated (users are no longer impacted), investigate the root cause:

1. Correlate the timeline: what changed just before the incident?
2. Reproduce in a staging environment if possible.
3. Use the 5 Whys technique to go beyond the proximate cause.
4. Identify contributing factors (lack of monitoring, missing test, process gap).

### Step 9: Fix and Verify

1. Write a test that reproduces the bug.
2. Implement the fix.
3. Verify the test passes.
4. Deploy to staging, verify with the same signals that detected the incident.
5. Deploy to production (canary if possible).
6. Monitor the signals that were affected for at least 1 hour.

### Step 10: Postmortem

Write a blameless postmortem within 48 hours. Template:

```markdown
## Incident: [Title]
**Date:** YYYY-MM-DD
**Duration:** X hours Y minutes
**Severity:** SEV-1/2/3/4
**Impact:** [Who was affected and how]

## Timeline
- HH:MM - First alert fired
- HH:MM - Engineer acknowledged
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Incident resolved

## Root Cause
[Clear, technical explanation. Not "human error."]

## Contributing Factors
- [Factor 1]
- [Factor 2]

## What Went Well
- [What worked in the response]

## What Went Poorly
- [What made detection/mitigation harder]

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| Add missing index to orders table | @alice | P1 | 2024-01-20 |
| Add alerting for query latency p99 | @bob | P1 | 2024-01-22 |
| Add schema change checklist to PR template | @charlie | P2 | 2024-01-31 |
```

**Key principles:**
- **Blameless.** "The deploy process allowed an unindexed migration to reach production" -- NOT "Alice forgot to add an index."
- **Focus on systemic fixes.** If a human can make the same mistake again, the fix is not done.
- **Action items must have owners and deadlines.** Track them to completion.
- **Share widely.** The organization learns from postmortems only if people read them.

---

## QUICK REFERENCE: DEBUGGING DECISION TREE

```
Problem reported
├── Can you reproduce it?
│   ├── YES → Isolate (binary search, disable components)
│   │         → Identify (debugger, logs, profiler)
│   │         → Fix → Test → Prevent
│   └── NO  → Add logging/monitoring at suspect boundaries
│            → Wait for recurrence with better observability
│            → Check if environment-specific (OS, config, data)
│
├── Is it a performance problem?
│   ├── CPU bound → Flame graph (py-spy, async-profiler, perf)
│   ├── Memory bound → Heap snapshot + diff
│   ├── I/O bound → Slow query log, EXPLAIN ANALYZE, tcpdump
│   └── Concurrency → Race detector, thread dump, goroutine profile
│
├── Is it in production?
│   ├── YES → Follow Incident Playbook (Section 6)
│   │         → Do NOT SSH and poke around
│   │         → Use observability tools only
│   └── NO  → Use debugger freely, add breakpoints, inspect state
│
└── Is it intermittent?
    ├── Timing-dependent → Race condition. Use race detector, stress tests
    ├── Data-dependent → Log the inputs that cause failure. Fuzz test
    └── Environment-dependent → Diff configs, deps, OS, timezone, locale
```

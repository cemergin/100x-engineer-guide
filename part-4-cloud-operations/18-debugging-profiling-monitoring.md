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

Every bug is a mystery. Every flame graph is a map. And once you know how to read the signals your system is already sending you, debugging transforms from panic into detective work you actually enjoy.

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
- Chapter 26 (incident management — when bugs become outages)
- Chapter 36 (Beast Mode observability — advanced telemetry and chaos engineering)

---

## 1. DEBUGGING METHODOLOGY

Here is the mental model that separates engineers who debug quickly from engineers who flail: **debugging is detective work, not guesswork.** Every bug leaves evidence. Your job is to find it systematically, not stumble onto it accidentally.

The best debuggers I know share one habit: they never touch the keyboard before forming a hypothesis. They observe, think, predict, then test. It sounds slow. It is dramatically faster.

### Systematic Debugging Process

Every bug fix should follow this cycle: **Reproduce -> Isolate -> Identify -> Fix -> Verify -> Prevent.**

1. **Reproduce:** Create the shortest, most reliable reproduction. If you cannot reproduce it, you cannot prove you fixed it. Capture exact inputs, environment, timing. Flaky bugs: increase logging and wait, or use stress tests to force the race. This step alone eliminates 30% of bugs — you discover the reproduction does not match your mental model of what is happening.

2. **Isolate:** Shrink the problem space. Comment out code, disable features, swap components, use binary search. Goal: smallest possible system that still exhibits the bug. The smaller the system, the louder the signal.

3. **Identify:** Form a hypothesis, then test it. Read the code, read the error, read the logs. Do NOT guess randomly. A hypothesis is a prediction: "I believe the timeout happens because the connection pool is exhausted." That prediction tells you exactly what to check.

4. **Fix:** Change one thing at a time. Understand WHY the fix works. If you cannot explain it, you have not found the root cause. The most dangerous bug fix is the one that works for reasons you do not understand — it will bite you again in a different form.

5. **Verify:** Confirm the fix resolves the original reproduction. Run the full test suite. Check edge cases. Verify against the conditions that caused the original failure.

6. **Prevent:** Write a regression test. Add assertions, validation, or monitoring to catch recurrence. Update documentation if the failure mode was non-obvious. The goal is to make this class of bug impossible — or at minimum, immediately detectable.

> **War story.** A colleague spent three days on a "memory leak" in a Python service. It turned out the leak only happened in staging, not production. Step one (reproduce) would have immediately surfaced this. Once she stopped trying to fix it and started trying to reproduce it reliably, she found the real culprit in four hours: a feature flag enabled in staging was holding a reference to a module-level list that grew on every request. Root cause found in hours, not days — because she finally followed the process.

### Rubber Duck Debugging

Explain the problem out loud, line by line, to an inanimate object (or a patient colleague). This works because:
- Verbalization forces you to serialize your understanding sequentially.
- You encounter gaps in your mental model when you cannot explain a step.
- The act of teaching activates different cognitive pathways than silent reading.

In practice: open a blank document and write "The request comes in at line X, then calls Y, which should return Z because..." The moment you write "should" and realize you have not verified it, you have found your next investigation target. That word "should" is almost always where the bug lives.

I have solved bugs by explaining them to my coffee mug. The mug has a 100% resolution rate.

### Binary Search Debugging

When a bug exists somewhere in a large codebase or long execution path:
1. Find a point where behavior is correct (start) and incorrect (end).
2. Test the midpoint.
3. Narrow to the half that contains the transition from correct to incorrect.
4. Repeat until you have a single function, line, or commit.

Time complexity: O(log n) instead of O(n). For 1000 lines of suspect code, ~10 checks instead of 1000. For 1000 commits, about 10 checkouts with `git bisect` instead of reading every diff. The math is working in your favor — use it.

### Git Bisect

Automates binary search across commits to find the exact commit that introduced a regression. This is one of those tools that feels like cheating the first time you use it.

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

> **Here's the weirdest bug I ever found with bisect.** The performance regression was introduced by a commit that added a comment. Literally just a comment. But that comment contained a word that matched a regex in a codegen script, which caused it to generate an extra middleware handler, which added 40ms to every request. Bisect found it in eleven steps across 800 commits. Without bisect, we would have been reading diffs for days.

### Reading Error Messages and Stack Traces

This sounds obvious. Engineers still do not do it. **Read the entire error message before you Google it.**

**Read from the bottom up** (most languages). The root cause is usually the innermost frame.

```
Traceback (most recent call last):
  File "main.py", line 45, in handle_request     # <-- entry point
    result = process(data)
  File "process.py", line 12, in process          # <-- intermediate
    return transform(data["key"])
KeyError: 'key'                                    # <-- ROOT CAUSE: read this first
```

The error message is telling you exactly what happened. It says "KeyError: 'key'" which means a dictionary was accessed with the key `'key'` and that key did not exist. That is the entire bug. Line 12 is where to look. You do not need to read lines 1 through 44 first.

**For JavaScript/Node.js:** Read top-down. The first line is the error, the first frame is where it was thrown.

**Key skills:**
- Distinguish YOUR code frames from library/framework frames. Start investigation in your code.
- Search the exact error message (with quotes) before reading source code.
- For async stack traces: enable `--async-stack-traces` (Node 12+) or `Error.stackTraceLimit = 50`.
- For minified stack traces: use source maps (`--enable-source-maps` in Node, upload to Sentry).

### The 5 Whys Technique

Drill past symptoms to root causes by asking "why" iteratively. The goal is not to find who made a mistake — it is to find what in the system allowed the mistake to cause harm.

1. **Why** did the API return 500? — The database query timed out.
2. **Why** did the query time out? — It was doing a full table scan on 50M rows.
3. **Why** was it doing a full table scan? — The `WHERE` clause column has no index.
4. **Why** is there no index? — The migration that added the column did not include one.
5. **Why** did the migration ship without an index? — There is no review checklist for schema changes.

Root cause: process gap. Fix: add a schema change checklist to the PR template. The query timeout is a symptom; the missing process is the cause. If you stop at "missing index" you will get another missing index next year. If you stop at "engineer forgot" you have learned nothing.

**Pitfall:** Do not stop at the first technical cause. Keep asking until you reach something you can change systemically. "Human error" is never a root cause. Humans have always made errors and always will. The question is what systemic protection was missing.

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

That last one is worth dwelling on. If you are still `console.log`-ing your way through bugs in 2026, you are leaving a superpower unused. A debugger lets you pause time, inspect every variable, step through execution at human speed, and set conditional breakpoints that only fire when `user.id === "the-broken-one"`. The setup cost is minutes. The debugging time savings are hours per week.

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

This is the secret weapon most Node.js developers do not know they have. The same DevTools you use to debug React components can attach to your backend process. You get a real call stack, real variable inspection, a real profiler — all in a UI you already know.

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
- Missing `await` — function returns a Promise instead of a resolved value. The error message will be something mystifying like "Cannot read properties of undefined (reading 'id')" because the code received a Promise object where it expected a user object.
- `Promise.all` vs `Promise.allSettled` — the former rejects on the first failure, leaving the others dangling. Use `allSettled` when you care about all results regardless of individual failures.
- Error swallowed in `.catch(() => {})` — always log or rethrow. Silent error swallowing is the ghost in your machine.
- `async` in `forEach` — does NOT await. Use `for...of` or `Promise.all(arr.map(...))`. This one has burned every JavaScript developer at least once.

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

# clinic.js suite -- the all-in-one diagnostic toolkit
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

> **War story.** A Node.js service was consuming 4 GB of RAM after running for 12 hours, then crashing. Classic memory leak. The heap profiler pointed to a specific object type: `EventEmitter`. The team had an analytics pipeline that attached a `data` listener on every request — but never called `removeListener`. Over 50,000 requests, that was 50,000 orphaned listeners on the same emitter. `clinic heapprofiler` showed the growing object count in about 10 minutes of profiling. Fix: one `removeListener` call in the cleanup function. The service now runs indefinitely with stable memory.

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

That `condition` command is underused. Instead of adding `if user_id == "problem-user": import pdb; pdb.set_trace()` to your source code, you can set the breakpoint from the pdb prompt: `b my_module.py:42` then `condition 1 user_id == "problem-user"`. Clean, temporary, no code changes required.

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

Set `justMyCode: false` when you suspect the bug is actually in a library dependency. This is rare, but it happens — and being able to step into library code is invaluable when it does.

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

The `objgraph.show_backrefs` call is the real magic. It generates a visual graph showing you exactly which object is holding a reference to the leaking object — and which object holds that one, and so on. It turns "something is keeping this object alive" into a clear chain you can trace to a single line of code.

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

The `goroutines` command is invaluable for diagnosing goroutine leaks. If you have 5,000 goroutines and your server only handles 50 concurrent requests, something is wrong. Switch to a few and inspect their stacks — you will find them all waiting on the same blocked channel or mutex.

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

Always run your test suite with `-race`. The overhead is 5-10x slower execution, which is fine for a CI pipeline. The alternative is shipping data races that manifest as random corruption in production at 3 AM. The race detector is not optional; it is a correctness tool.

> **War story.** A Go microservice had a bug that appeared maybe once a week: incorrect prices on invoices. The amounts were slightly wrong — sometimes off by a few cents. With the race detector: `WARNING: DATA RACE. Goroutine 7 (read): pricing.go:88. Goroutine 23 (write): pricing.go:112`. A shared `lastPrice` variable was being written in a goroutine that handled price updates and read in a goroutine that computed invoice totals. No mutex. Five minutes to understand, one line to fix. Without the race detector: a six-month financial audit.

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

JFR is remarkably low-overhead for what it captures — typically under 1% CPU impact. That means you can run it continuously in production and always have a recording from the minutes before a problem occurred. It is like a flight data recorder for your JVM.

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

Always configure `-XX:+HeapDumpOnOutOfMemoryError` in production. OOMKilled containers are painful mysteries without a heap dump. With a heap dump, they are solved in an afternoon.

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

Profiling is where debugging gets genuinely exciting. You stop guessing about performance and start seeing it — exact CPU time by function, exact memory allocation by call site, exact I/O latency by query. It is like putting on X-ray glasses for your system's internals.

### CPU Profiling

**Flame Graphs — How to Read Them:**

The flame graph is arguably the most powerful performance debugging visualization ever invented. Once you can read one, you will wonder how engineers survived without them.

- **X-axis:** proportion of total samples (NOT time sequence). Wider = more CPU time consumed.
- **Y-axis:** stack depth. Bottom = entry point, top = leaf function (where CPU actually executes).
- **Color:** typically random or grouped by module. Color is not meaningful by default — do not try to read meaning into it.
- **Look for:** Wide plateaus at the top (functions consuming lots of CPU), wide towers (deep call stacks that dominate), and unexpected functions (why is JSON serialization taking 30% of CPU?).

The "plateau" pattern is the money shot. When you see a wide flat top on a flame graph, you have found exactly where your CPU is spending its time. That flat bar IS your performance problem. Everything below it is context telling you how execution got there.

In L2-M58 (Debugging in Production), you'll use flame graphs as your primary diagnostic tool against a degraded TicketPulse — the purchase service is slow, you have no SSH access, and the only tools available are the ones in the observability stack. Generating a `py-spy` flame graph against the running process and spotting the plateau is the turning point of the module. Once you've found a real CPU hog that way, you'll reach for flame graphs instinctively in every future production investigation.

> **War story.** We had a Python API that was inexplicably slow — 800ms per request for what should have been simple JSON transformation. A 30-second `py-spy` profile revealed a stunning plateau: `deepcopy`. Deep in a data transformation library, someone had called `copy.deepcopy()` on a 50MB data structure on every request. It was faster to construct the output directly than to copy the input. One-line fix, latency dropped to 45ms. The flame graph showed it instantly; we had been guessing for two weeks.

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

`py-spy` is particularly magical because it is a sampling profiler that attaches to a running Python process with zero code changes and near-zero overhead. You can profile production without restarting. The equivalent for Java is `async-profiler`. Both tools are essential.

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

`perf stat` output is a goldmine. If your IPC (instructions per cycle) is below 0.5, your code is probably memory-bound (cache misses). If cache-miss rate is high, look for access patterns that do not respect cache locality — iterating a large array of structs by a single field rather than packing related fields together, for example.

### Memory Profiling

**Heap Snapshots and Diffing:**

The most powerful technique for finding memory leaks is snapshot comparison:
1. Take snapshot at baseline (after warmup).
2. Run the suspected leaking operation N times.
3. Force garbage collection.
4. Take second snapshot.
5. Diff the two snapshots — objects that grew proportionally to N are your leak.

This technique works in every language and every environment. The specific tools differ; the process is identical.

**In Chrome DevTools (Node.js):**
1. Connect to `node --inspect` process.
2. Memory tab -> Take heap snapshot.
3. Perform operation.
4. Take second snapshot.
5. Select "Comparison" view between snapshots.
6. Sort by "# Delta" or "Size Delta" to find growing objects.

When you sort by `# Delta` and see `(closure)` at the top with +5,000 instances after 1,000 requests, you have found your leak: closures created on every request and never released.

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

The unbounded cache is the most common production leak in my experience. Someone writes a "cache for performance" as a plain object, and nobody sets a size limit. Over days, it grows to contain every input the system has ever seen. The fix is always the same: use an LRU with a sensible max size.

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

`pg_stat_statements` is the single most useful PostgreSQL performance tool. Enable it. The "top queries by total time" view tells you where to focus optimization effort — it is not always the slowest query, but the one that is called most frequently while being slow.

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

The `BUFFERS` option is the one people forget. `shared hit` means the data came from PostgreSQL's shared buffer cache (fast). `shared read` means it came from disk (slow). A query plan that looks fine on paper but has `Buffers: shared read=50000` is reading 50,000 disk pages — likely because the relevant data is not cached.

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

`idle in transaction` connections are a red flag. They hold locks and block autovacuum. If you see many of these, look for code paths that begin a transaction, do some work, hit an error, and never commit or roll back. The connection returns to the pool with an open transaction — and sits there indefinitely.

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

That `curl` timing breakdown is something every engineer should have in their muscle memory. When a request is "slow," this tells you immediately whether the slowness is in DNS resolution (network config issue), TCP connect (routing or firewall issue), TLS handshake (certificate or cipher negotiation), or actual server processing time (application issue). Four different problems, four different fixes — the timing breakdown points you at the right one.

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

If you cannot account for all the time, likely culprits: DNS resolution, connection establishment, TLS handshake, connection pool wait time, GC pauses, or untracked async operations. The "unaccounted" time is never actually unaccounted — it just means you have not instrumented that code path yet.

**Instrumentation approach:**
```typescript
// Simple timing wrapper
async function timed<T>(label: string, fn: () => Promise<T>): Promise<T> {
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

This simple wrapper has helped me find more performance bugs than any APM tool. It makes the invisible visible. The APM tool (Datadog, Honeycomb, Jaeger — see Ch 36 for the full Beast Mode observability stack) is what you use when you need this at scale, automated, without code changes.

---

## 4. MONITORING TOOLS DEEP DIVE

This is where things get genuinely fun. These tools are your X-ray vision for production systems. Prometheus and Grafana let you see things that are literally happening in millions of processes simultaneously. Datadog correlates your logs, metrics, and traces in a single investigation. Sentry shows you the exact line of code that is breaking for real users in real time. Once you internalize what these tools can do, you start seeing monitoring as a superpower rather than a chore.

See Ch 36 (Beast Mode Observability) for the advanced layer: distributed tracing with Honeycomb, chaos engineering to validate your monitoring, and SLO-based alerting that measures what users actually experience.

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

The `logInjection: true` flag is what makes Datadog genuinely magical. Every log line your application emits gets automatically annotated with the `trace_id` and `span_id` of the request that caused it. When you find a trace with high latency in the APM view, you can click straight to the correlated logs. No manual correlation, no `grep`-ing across files — instant context switching.

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

The Anomaly monitor is underused and extremely powerful. Instead of threshold alerts ("alert if error rate > 5%"), it alerts based on historical patterns ("alert if error rate is 3 standard deviations above what it was at this time last week"). This catches gradual degradation that never crosses a fixed threshold, and avoids false positives during expected traffic peaks.

**Cost Optimization Tips:**
- Use `exclude_tags` on high-cardinality metrics (user IDs, request IDs).
- Set custom metric aggregations to reduce unique timeseries.
- Use log exclusion filters to drop debug logs before indexing.
- Archive logs to S3 instead of long retention in Datadog.
- Use `distribution` metrics instead of `histogram` when you need percentiles (fewer timeseries).

Datadog bills by custom metric count. A metric tagged with user IDs creates one timeseries per user. For a million-user app, that is a million timeseries for a single metric. This is how teams get surprise $50,000 Datadog bills. Use cardinality-safe tags and always check the "estimated usage" before shipping new metric code.

### Prometheus + Grafana

**Prometheus Architecture:**

Prometheus scrapes targets at configured intervals, stores data in a local TSDB, evaluates alert rules, and exposes PromQL for querying. It is pull-based (scrapes your endpoints), not push-based. This inversion matters: Prometheus decides when to collect data, not your application. Your application just needs to expose a `/metrics` endpoint in the right format.

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

Choosing the right histogram buckets matters more than it looks. If your p99 latency is typically 800ms and your highest bucket is `5`, the histogram will tell you almost nothing about the distribution between 800ms and 5000ms. Set buckets around your expected SLO thresholds.

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

The `absent()` function is the one that catches silent failures. If your service crashes completely, it stops emitting metrics. A threshold-based alert (`error_rate > 0.05`) will never fire if there are no metrics to evaluate. `absent()` fires when the metric disappears entirely — it is the "is it even running?" check.

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

Use recording rules when: a PromQL query is used in multiple dashboards/alerts, or when it is computationally expensive and would timeout on ad-hoc queries. Recording rules pre-compute the result and store it as a new timeseries — dashboards load instantly instead of running expensive queries on every page load.

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

Loki indexes only labels (metadata), not the full log content. Drastically cheaper storage, but queries on log content are slower (grep-like scan). If you are already running Grafana for Prometheus metrics, Loki is the natural complement — one dashboarding layer for both metrics and logs, with logs that reference the same labels as your metrics.

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

OpenTelemetry is the convergence of the observability world. Instead of instrumenting your code three different ways for Datadog, Jaeger, and Prometheus, you instrument once with OTel and route the data wherever you want. The vendor independence is real and valuable.

**The Three Signals:**
- **Traces:** Request flow across services. A trace contains spans; each span represents a unit of work (HTTP call, DB query, function execution). This is how you answer "why was this request slow?"
- **Metrics:** Numeric measurements over time (counters, gauges, histograms). This is how you answer "is this service healthy right now?"
- **Logs:** Discrete events with context. Correlated with traces via trace_id/span_id. This is how you answer "what exactly happened at this moment?"

The magic is correlation. A span ID in a trace links to the log lines emitted during that span. A log line links back to the trace it belongs to. Together, they give you complete context for any event in your system.

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

Custom spans are where tracing becomes personally useful rather than generically informative. Auto-instrumentation tells you that a request took 800ms. Custom spans tell you that `validateOrder` took 650ms of those 800ms, specifically the `checkInventory` sub-call, specifically for SKU `XYZ-001` that is out of stock. That level of specificity is what lets you debug production issues without SSH access.

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

Without context propagation through your message queue, every consumer creates a new root trace. You see hundreds of disconnected 50ms traces instead of one connected 2-second trace that shows the message sitting in the queue for 1.9 seconds and being processed for 100ms. The full picture is worth the extra four lines of code.

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

Sentry occupies a unique niche: it is specifically about errors, not general metrics. When an exception fires in your code, Sentry captures the full stack trace, the local variables at each frame, the user who was affected, the sequence of actions that led to the error (breadcrumbs), and the exact release that introduced it. This is a different kind of debugging power than Datadog's wide-angle view — it is a microscope on individual failures.

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

The `withScope` pattern is crucial for production debugging. Without context, Sentry shows you the stack trace — useful. With `setUser` and `setTag`, it also shows you who was affected and what kind of order they were processing — invaluable. This extra context has saved me hours of "what was the user doing when this happened?" investigation.

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

Source map upload + commit association is the combination that enables Sentry's "suspect commits" feature. When an error is introduced in a new release, Sentry shows you which commits touched the files related to the error — it narrows the investigation to a handful of diffs instead of an entire release.

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

Production debugging is a different discipline from local debugging. You cannot pause execution, you cannot attach a debugger (usually), and every action you take can affect real users. The constraint forces you to think more carefully — and it makes your observability setup the limiting factor on how fast you can debug.

The engineers who debug production fastest are the ones who invested in observability before they needed it. Their systems narrate exactly what is happening. When something breaks, they are reading a story, not sifting through noise.

### Debugging Without SSH Access

Modern cloud-native systems (serverless, Kubernetes, PaaS) often do not allow SSH. You debug through observability.

**The observability-only approach:**
1. **Structured logs** are your primary tool. Every log line should be JSON with: timestamp, level, service, trace_id, span_id, and relevant business context. When a user reports "my order didn't go through," you should be able to search `order_id: "ord-12345"` and see the entire life of that request across every service it touched.
2. **Distributed traces** show the request flow across services. Find the failing trace by error status or high latency. The trace waterfall view tells you immediately which service is the bottleneck and which is just waiting for a downstream dependency.
3. **Metrics** reveal patterns: is this a single request or a systemic issue? When did it start? What changed? A single spike vs. a sustained elevation are two completely different problems.
4. **Dashboards** give context: correlate the incident with deployments, traffic changes, dependency health. The dashboard is your map; the logs and traces are the terrain.

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

The `redact` option is not optional — it is required for PII compliance. Log the request ID, not the user's email. Log the order ID, not the credit card number. Structure your logs so they are maximally useful for debugging and minimally risky for compliance.

> **War story.** A payment service was intermittently failing to process orders. The error was "transaction timeout" — not helpful. No request IDs, no correlation. Engineers spent two days trying to reproduce it. When we finally added structured logging with request IDs and correlation across services, we found the bug in twenty minutes: a database connection in a worker thread was taking 45 seconds to reconnect after a brief network blip, and the 30-second timeout was firing before it could succeed. The fix was a retry with exponential backoff. The structured logging was the X-ray machine. Without it, we were diagnosing by feel.

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

This pattern lets you turn on trace-level logging for a specific user without affecting anyone else and without a deploy. When a specific customer reports "my requests are slow," you enable the flag for their user ID and ask them to reproduce the issue. Their requests now emit detailed timing and context; everyone else's requests are unaffected.

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

Canary deployments give you a live A/B test between old and new code in production. If the canary error rate is higher than stable, the rollout stops automatically and you have a perfect comparison group to investigate against. See Ch 26 (incidents) for how canary analysis integrates into your incident response process.

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

Core dump analysis is the forensic science of debugging. The process is dead, but the memory is not. You can inspect every goroutine stack, every variable, every object — exactly as they were at the moment of crash. It is time travel for bugs.

### eBPF for Production Debugging

eBPF allows attaching programs to kernel and user-space functions with negligible overhead. No application restart required. This is the closest thing to a superpower that production debugging has ever had.

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

The `tcpconnect` tool is the one I reach for when something mysterious is happening with external connections. Is the service making unexpected DNS lookups? Are connections timing out at a particular rate? `tcpconnect` shows you every outbound TCP connection with timing — no code changes, no restart, zero impact on the running process.

---

## 6. INCIDENT DEBUGGING PLAYBOOK

When something breaks in production, this is where everything in this chapter becomes real. Speed matters. Systematic thinking matters more. The engineers who resolve incidents fastest are the ones with the methodology so deeply internalized that they run the steps without thinking — while simultaneously communicating status, delegating investigation tasks, and keeping calm enough for everyone around them.

This is precisely what L3-M73 (Incident Response Simulation) puts you through. It's Friday 4 PM, TicketPulse's purchase success rate has dropped to 85%, and the CEO is in the Slack channel. The module runs you through this exact playbook — detect, assess, investigate, mitigate, communicate — under time pressure, with incomplete information, and with the added constraint that some of your usual debugging tools are behaving strangely because the very infrastructure running them is degraded.

See Ch 26 (Incident Management) for the full organizational playbook: escalation paths, communication templates, and post-incident review processes. This section covers the technical debugging steps.

### Step 1: Assess Impact

**Questions to answer immediately (< 2 minutes):**
- Who is affected? (All users, specific region, specific feature, internal only)
- What is broken? (Complete outage, degraded, intermittent, cosmetic)
- When did it start? (Check error rate graphs — the inflection point is your timeline anchor)
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

**Communication:** Immediately post in the incident channel: "Investigating elevated error rates on [service]. Impact: [description]. Updates every 15 minutes." Even if you have nothing to report, send the update at 15 minutes. The silence kills more trust than the outage.

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

**If you find a recent change that correlates with the incident start time, strongly consider rolling back immediately before investigating further.** Fix forward only if the rollback is riskier than the current state. Rolling back a bad deploy takes minutes. Finding the root cause and deploying a fix takes hours. During an incident, time is user trust.

### Step 3: Check Dashboards

Look for THE FOUR GOLDEN SIGNALS (Google SRE):

| Signal | What to Look For |
|---|---|
| **Latency** | p50, p95, p99 increased? Bi-modal distribution (some fast, some slow)? |
| **Traffic** | Unexpected spike or drop? Traffic shift between endpoints? |
| **Errors** | Error rate spike? New error types appearing? |
| **Saturation** | CPU, memory, disk, connections approaching limits? |

Check service dependencies: is YOUR service failing, or is it a downstream dependency? If your error rate spike started at the exact same time as an AWS RDS maintenance window, the answer is staring at you.

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
- The FIRST error (often the root cause; subsequent errors are cascading failures). Scroll to the beginning of the incident window, not the most recent errors.
- Error patterns: are all errors the same, or are there multiple types? Multiple types suggest a shared upstream dependency.
- Correlation with specific users, endpoints, or request attributes. If errors only affect users in a specific region, your investigation just narrowed dramatically.
- Warnings that started before the errors (often early signals). The canary in the coal mine was already dead before the alarm went off.

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

`kubectl get pods` is the first command I run in a Kubernetes incident. If I see `OOMKilled` or `CrashLoopBackOff`, I have already found the problem category. `OOMKilled` means the container hit its memory limit and was killed by the kernel. `CrashLoopBackOff` means it is crashing repeatedly — look at `kubectl logs <pod> --previous` for the crash logs.

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

Check the external status pages early — before you spend an hour debugging your code when the real problem is Stripe having an incident. Bookmark `status.stripe.com`, `status.aws.amazon.com`, `status.github.com`, and every other critical external dependency. The fastest debugging is recognizing that the problem is not yours to fix.

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

Once the incident is mitigated (users are no longer impacted), investigate the root cause with the urgency removed:

1. Correlate the timeline: what changed just before the incident?
2. Reproduce in a staging environment if possible.
3. Use the 5 Whys technique to go beyond the proximate cause.
4. Identify contributing factors (lack of monitoring, missing test, process gap).

Do not root-cause analyze while the incident is active. Parallel investigations slow the primary response. Assign one person to mitigation; assign a separate person to documentation and root cause exploration if you have the headcount.

### Step 9: Fix and Verify

1. Write a test that reproduces the bug.
2. Implement the fix.
3. Verify the test passes.
4. Deploy to staging, verify with the same signals that detected the incident.
5. Deploy to production (canary if possible).
6. Monitor the signals that were affected for at least 1 hour.

The regression test is the most important step that teams consistently skip. Without it, the same bug returns. With it, you have permanently improved your system's defenses.

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
- **Blameless.** "The deploy process allowed an unindexed migration to reach production" — NOT "Alice forgot to add an index."
- **Focus on systemic fixes.** If a human can make the same mistake again, the fix is not done.
- **Action items must have owners and deadlines.** Track them to completion. A postmortem with unfinished action items is a postmortem that did not work.
- **Share widely.** The organization learns from postmortems only if people read them. Publish them, present them in engineering all-hands, celebrate them as evidence of a learning culture.

> **The blameless culture point is worth emphasizing.** Engineers who fear punishment for incidents learn to hide problems, over-communicate risk to avoid blame, and avoid making changes that might cause incidents. Engineers in blameless cultures learn to instrument better, report accurately, and improve systems. The postmortem is a learning tool, not a tribunal. See Ch 26 for how to build the organizational culture that makes postmortems valuable.

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

Every tool in this chapter — from `git bisect` to flame graphs to Datadog APM to eBPF — exists to answer a question faster. The mystery is always solvable. The evidence is always there. Your job as the detective is to ask the right question, look in the right place, and trust the process when the answer is not immediately obvious.

That is what makes debugging genuinely fun, once you stop treating it as an interruption and start treating it as the puzzle it actually is.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L2-M45: Monitoring — Prometheus & Grafana](../course/modules/loop-2/L2-M45-monitoring-prometheus-grafana.md)** — Instrument TicketPulse with Prometheus metrics, build Grafana dashboards, and set the golden signals as your operational baseline
- **[L2-M46: Distributed Tracing — OpenTelemetry](../course/modules/loop-2/L2-M46-distributed-tracing-opentelemetry.md)** — Add OpenTelemetry traces to TicketPulse's full request path and debug a latency problem across service boundaries
- **[L2-M58: Debugging in Production](../course/modules/loop-2/L2-M58-debugging-in-production.md)** — Work through a realistic production incident in TicketPulse using only observability tools — no SSH, no print statements
- **[L3-M73: Incident Response Simulation](../course/modules/loop-3/L3-M73-incident-response-simulation.md)** — Run a full incident from PagerDuty alert through mitigation and postmortem using TicketPulse as the patient

### Quick Exercises

> **No codebase handy?** Try the self-contained version in [Appendix B: Exercise Sandbox](../appendices/appendix-exercise-sandbox.md) — the [Prometheus + Grafana observability exercise](../appendices/appendix-exercise-sandbox.md#exercise-5-observability--prometheus--grafana--instrumented-server) spins up a full golden-signals stack with Docker Compose in under 5 minutes.

1. **Generate a flame graph for your slowest API endpoint** — use `py-spy`, `async-profiler`, `perf`, or your language's equivalent profiler. Run it against a staging environment under load and identify the top two CPU consumers in the call stack.
2. **Add structured logging with correlation IDs to one request path** — pick one endpoint and ensure that every log line it emits (including logs from called services or database queries) includes the same `trace_id` field. Verify in your log aggregation tool that you can pull up all logs for a single request.
3. **Set up one golden signals dashboard** — create a dashboard (Grafana, Datadog, or CloudWatch) for one service with four panels: request rate, error rate, latency (p50/p95/p99), and saturation (CPU or queue depth). Set alert thresholds on at least two of them.

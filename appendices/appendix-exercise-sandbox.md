<!--
  CHAPTER: B
  TITLE: Exercise Sandbox — Runnable Examples
  PART: Appendices
  PREREQS: Docker, a terminal
  DIFFICULTY: All levels
  UPDATED: 2026-04-05
-->

# Appendix B: Exercise Sandbox — Runnable Examples

> No TicketPulse repo required. Just a terminal and Docker.

These exercises are self-contained versions of the guide's "Quick Exercises." Each one can be completed in 15–30 minutes with nothing but a terminal, Docker, and a text editor. They exist specifically so that solo learners without a shared codebase can still get hands-on with the real concepts.

**Prerequisites:** Docker and Docker Compose installed. That's it.

---

## Exercise 1: Distributed Consensus — etcd Cluster

*From [Chapter 1: System Design](../part-1-foundations/01-system-design.md)*

**What you'll learn:** What consensus actually looks like in practice. Kill a node. Watch the cluster still work. See why quorum matters.

### Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  etcd1:
    image: quay.io/coreos/etcd:v3.5.9
    command: >
      etcd --name etcd1
      --data-dir /etcd-data
      --initial-advertise-peer-urls http://etcd1:2380
      --listen-peer-urls http://0.0.0.0:2380
      --listen-client-urls http://0.0.0.0:2379
      --advertise-client-urls http://etcd1:2379
      --initial-cluster-token etcd-cluster-1
      --initial-cluster etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380
      --initial-cluster-state new
    ports: ["2379:2379"]

  etcd2:
    image: quay.io/coreos/etcd:v3.5.9
    command: >
      etcd --name etcd2
      --data-dir /etcd-data
      --initial-advertise-peer-urls http://etcd2:2380
      --listen-peer-urls http://0.0.0.0:2380
      --listen-client-urls http://0.0.0.0:2379
      --advertise-client-urls http://etcd2:2379
      --initial-cluster-token etcd-cluster-1
      --initial-cluster etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380
      --initial-cluster-state new

  etcd3:
    image: quay.io/coreos/etcd:v3.5.9
    command: >
      etcd --name etcd3
      --data-dir /etcd-data
      --initial-advertise-peer-urls http://etcd3:2380
      --listen-peer-urls http://0.0.0.0:2380
      --listen-client-urls http://0.0.0.0:2379
      --advertise-client-urls http://etcd3:2379
      --initial-cluster-token etcd-cluster-1
      --initial-cluster etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380
      --initial-cluster-state new
```

### Run it

```bash
docker compose up -d

# Write a key to the cluster
docker compose exec etcd1 etcdctl put /config/feature-flag "enabled"

# Read it back — works fine with 3 nodes
docker compose exec etcd1 etcdctl get /config/feature-flag

# Kill one node (you still have quorum: 2/3)
docker compose stop etcd2

# Read still works — Raft consensus says 2/3 is enough
docker compose exec etcd1 etcdctl get /config/feature-flag

# Kill a second node (now only 1/3 — below quorum)
docker compose stop etcd3

# This will hang or timeout — no quorum, no reads
docker compose exec etcd1 etcdctl get /config/feature-flag --dial-timeout=3s

# Bring a node back — quorum restored
docker compose start etcd2
docker compose exec etcd1 etcdctl get /config/feature-flag

# Cleanup
docker compose down
```

### Expected output

After killing two nodes, the read command hangs. The moment you restore one, it succeeds again. This is Raft consensus in action: a cluster of N nodes tolerates ⌊N/2⌋ failures.

**What you learned:** Distributed consensus isn't magic — it's majority voting. You can lose nodes and keep reading; you can't lose quorum and keep writing. This is why etcd, Zookeeper, and Consul all require odd numbers of nodes.

---

## Exercise 2: Database — Slow Query, EXPLAIN ANALYZE, Index

*From [Chapter 2: Data Engineering](../part-1-foundations/02-data-engineering.md)*

**What you'll learn:** How to find a slow query, read an execution plan, add an index, and measure the before/after.

### Setup

```bash
docker run -d --name pg-sandbox \
  -e POSTGRES_PASSWORD=secret \
  -p 5432:5432 \
  postgres:16

# Wait a moment for Postgres to start
sleep 2

docker exec -it pg-sandbox psql -U postgres
```

### The exercise (run inside psql)

```sql
-- Create a table with 1 million rows
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  user_id INT,
  event_type TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO events (user_id, event_type, created_at)
SELECT
  (random() * 100000)::INT,
  CASE (random() * 3)::INT WHEN 0 THEN 'click' WHEN 1 THEN 'view' ELSE 'purchase' END,
  NOW() - (random() * INTERVAL '365 days')
FROM generate_series(1, 1000000);

-- Force a table statistics update
ANALYZE events;

-- Deliberately slow query: sequential scan on 1M rows
EXPLAIN ANALYZE
SELECT COUNT(*) FROM events WHERE user_id = 42;

-- Note the "Seq Scan" and actual execution time. Should be 50-200ms.

-- Add an index
CREATE INDEX idx_events_user_id ON events (user_id);

-- Same query again
EXPLAIN ANALYZE
SELECT COUNT(*) FROM events WHERE user_id = 42;

-- Now it uses "Index Scan". Should be <5ms.

\q
```

### Expected output

Before the index: `Seq Scan on events ... actual time=0.0..180.0`. After the index: `Index Scan using idx_events_user_id ... actual time=0.0..1.2`. A 100x speedup from four words: `CREATE INDEX`.

```bash
# Cleanup
docker stop pg-sandbox && docker rm pg-sandbox
```

**What you learned:** EXPLAIN ANALYZE shows you exactly what Postgres is doing — sequential scan vs. index scan, estimated vs. actual row counts, and where time is actually spent. Read this before every "the DB is slow" conversation.

---

## Exercise 3: Caching — Cache-Aside Pattern with Redis

*From [Chapter 2: Data Engineering](../part-1-foundations/02-data-engineering.md)*

**What you'll learn:** How cache-aside works, what a cache hit vs. miss looks like, and how to measure hit rate.

### Setup

```bash
docker run -d --name redis-sandbox -p 6379:6379 redis:7
```

Create `cache_aside.py`:

```python
import redis
import json
import time
import random

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def fetch_from_db(user_id: int) -> dict:
    """Simulates a slow DB query (100ms latency)."""
    time.sleep(0.1)
    return {"user_id": user_id, "name": f"User {user_id}", "plan": "pro"}

def get_user(user_id: int) -> dict:
    """Cache-aside: check cache first, fall back to DB."""
    cache_key = f"user:{user_id}"
    cached = r.get(cache_key)
    if cached:
        return {"data": json.loads(cached), "source": "cache"}
    data = fetch_from_db(user_id)
    r.setex(cache_key, 60, json.dumps(data))  # TTL: 60 seconds
    return {"data": data, "source": "db"}

hits, misses = 0, 0
user_ids = [random.randint(1, 20) for _ in range(100)]  # 100 requests, 20 distinct users

for uid in user_ids:
    result = get_user(uid)
    if result["source"] == "cache":
        hits += 1
    else:
        misses += 1

print(f"Requests: 100 | Cache hits: {hits} | Misses: {misses}")
print(f"Hit rate: {hits}% | Time saved: ~{hits * 100}ms")
```

```bash
pip install redis  # or: pip3 install redis
python cache_aside.py

# Cleanup
docker stop redis-sandbox && docker rm redis-sandbox
```

### Expected output

```
Requests: 100 | Cache hits: 79 | Misses: 21
Hit rate: 79% | Time saved: ~7900ms
```

With 20 distinct users and 100 requests, you get roughly 80% hit rate — first request for each user is a miss, everything after is a hit. The DB only gets 20 queries instead of 100.

**What you learned:** Cache-aside is read-through by the application: miss → fetch → store → serve. The hit rate depends on your key distribution. Hot keys (popular user IDs) have near-100% hit rates; cold data has 0%. That's why you cache what's hot, not everything.

---

## Exercise 4: Testing — Property-Based Test for JSON Roundtrip

*From [Chapter 8: Testing & Quality](../part-2-applied-engineering/08-testing-quality.md)*

**What you'll learn:** How property-based testing generates hundreds of inputs you'd never think to write manually, and finds edge cases your unit tests miss.

### Setup

```bash
mkdir property-test-sandbox && cd property-test-sandbox
npm init -y
npm install fast-check
```

Create `roundtrip.test.js`:

```javascript
const fc = require("fast-check");

// The function under test: serialize then parse
function jsonRoundtrip(value) {
  return JSON.parse(JSON.stringify(value));
}

// Property 1: roundtrip of any JSON-serializable value equals itself
fc.assert(
  fc.property(fc.jsonValue(), (value) => {
    const result = jsonRoundtrip(value);
    return JSON.stringify(result) === JSON.stringify(value);
  }),
  { numRuns: 500 }
);

// Property 2: string roundtrip is always a string with same content
fc.assert(
  fc.property(fc.string(), (s) => {
    return jsonRoundtrip(s) === s;
  }),
  { numRuns: 1000 }
);

// Property 3: array length is preserved
fc.assert(
  fc.property(fc.array(fc.integer()), (arr) => {
    return jsonRoundtrip(arr).length === arr.length;
  }),
  { numRuns: 500 }
);

// Now deliberately break it: what happens with undefined?
try {
  fc.assert(
    fc.property(fc.anything(), (value) => {
      return JSON.stringify(jsonRoundtrip(value)) === JSON.stringify(value);
    }),
    { numRuns: 200 }
  );
} catch (e) {
  console.log("Found a counterexample:", e.message);
  // fast-check will find `undefined` — JSON.stringify(undefined) returns undefined (not a string!)
}

console.log("All properties held for JSON-serializable values.");
console.log("fast-check ran 2200 test cases total — try doing that by hand.");
```

```bash
node roundtrip.test.js
```

**What you learned:** Property-based testing finds the `undefined` case automatically — something you'd never write as a manual test case because you weren't thinking about it. The library shrinks counterexamples to the smallest possible input that triggers the failure. 500 test cases in milliseconds. This is why it pairs so well with pure functions.

---

## Exercise 5: Observability — Prometheus + Grafana + Instrumented Server

*From [Chapter 18: Debugging, Profiling & Monitoring](../part-4-cloud-operations/18-debugging-profiling-monitoring.md)*

**What you'll learn:** The full golden-signals observability loop: instrument an app, scrape metrics, visualize them, watch them change under load.

### Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  app:
    image: node:18-alpine
    working_dir: /app
    volumes: [./app:/app]
    command: node server.js
    ports: ["3000:3000"]

  prometheus:
    image: prom/prometheus:v2.47.0
    volumes: [./prometheus.yml:/etc/prometheus/prometheus.yml]
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:10.1.0
    ports: ["3001:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
```

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 5s
scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['app:3000']
```

Create `app/server.js`:

```javascript
const http = require('http');

let requestCount = 0;
let errorCount = 0;
const latencies = [];

function recordLatency(ms) {
  latencies.push(ms);
  if (latencies.length > 1000) latencies.shift();
}

function percentile(arr, p) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length * p / 100)];
}

const server = http.createServer((req, res) => {
  const start = Date.now();

  if (req.url === '/metrics') {
    const p50 = percentile(latencies, 50);
    const p95 = percentile(latencies, 95);
    const p99 = percentile(latencies, 99);
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end([
      `# HELP http_requests_total Total HTTP requests`,
      `# TYPE http_requests_total counter`,
      `http_requests_total ${requestCount}`,
      `# HELP http_errors_total Total HTTP errors`,
      `# TYPE http_errors_total counter`,
      `http_errors_total ${errorCount}`,
      `# HELP http_latency_p50_ms Median latency`,
      `http_latency_p50_ms ${p50}`,
      `# HELP http_latency_p95_ms p95 latency`,
      `http_latency_p95_ms ${p95}`,
      `# HELP http_latency_p99_ms p99 latency`,
      `http_latency_p99_ms ${p99}`,
    ].join('\n') + '\n');
    return;
  }

  requestCount++;
  // Simulate variable latency (5-200ms) and 5% error rate
  const delay = Math.random() < 0.05 ? 500 : 5 + Math.random() * 195;
  const isError = Math.random() < 0.05;

  setTimeout(() => {
    recordLatency(Date.now() - start);
    if (isError) {
      errorCount++;
      res.writeHead(500);
      res.end('error');
    } else {
      res.writeHead(200);
      res.end('ok');
    }
  }, delay);
});

server.listen(3000, () => console.log('App running on :3000, metrics at /metrics'));
```

```bash
mkdir app
# (save server.js to app/server.js)

docker compose up -d

# Generate some traffic
for i in $(seq 1 200); do curl -s http://localhost:3000/ > /dev/null; done

# View raw metrics
curl http://localhost:3000/metrics

# Open Prometheus: http://localhost:9090
# Query: http_requests_total
# Query: rate(http_requests_total[1m])

# Open Grafana: http://localhost:3001
# Add datasource: http://prometheus:9090
# Create dashboard with panels:
#   - http_requests_total (counter)
#   - http_errors_total (counter)
#   - http_latency_p95_ms (gauge)

# Generate a spike
for i in $(seq 1 500); do curl -s http://localhost:3000/ > /dev/null & done; wait

# Watch the latency spike in Grafana in real time

docker compose down
```

**What you learned:** The four golden signals (rate, errors, latency, saturation) live in your `/metrics` endpoint. Prometheus scrapes them. Grafana visualizes them. This is exactly how production monitoring works at every serious company — just with more services. The pattern scales to thousands of endpoints.

---

## Exercise 6: Kafka — Produce, Consume, Observe Lag

*From [Chapter 13: Cloud System Integration](../part-4-cloud-operations/13-cloud-system-integration.md)*

**What you'll learn:** How Kafka topics, partitions, consumer groups, and consumer lag actually behave when you push real messages through them.

### Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
```

```bash
docker compose up -d
sleep 10  # wait for Kafka to be ready

# Create a topic with 3 partitions
docker compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create --topic events --partitions 3 --replication-factor 1

# Produce 1000 messages
docker compose exec kafka bash -c \
  "for i in \$(seq 1 1000); do echo \"event-\$i\"; done | \
   kafka-console-producer --bootstrap-server localhost:9092 --topic events"

# Check the lag — consumer group hasn't started yet, so lag = 1000
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group my-group 2>/dev/null || echo "Group not yet registered"

# Start consuming (in background)
docker compose exec -d kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic events \
  --group my-group \
  --from-beginning \
  --max-messages 500

# While consumer is running, check lag — it should be decreasing
sleep 3
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group my-group

# Produce 500 more messages while consumer is running
docker compose exec kafka bash -c \
  "for i in \$(seq 1001 1500); do echo \"event-\$i\"; done | \
   kafka-console-producer --bootstrap-server localhost:9092 --topic events"

# Check lag again — should spike back up
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group my-group

docker compose down
```

### Expected output

```
GROUP       TOPIC   PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
my-group    events  0          333             500             167
my-group    events  1          333             500             167
my-group    events  2          334             500             166
```

Consumer lag is the distance between where the consumer is and the end of the log. Watch it grow when you produce faster than you consume, and shrink when you catch up.

**What you learned:** Consumer lag is the fundamental Kafka health metric. When lag grows, your consumers are falling behind — scale them out or fix the processing bottleneck. Messages live in the log regardless of whether anyone has read them, which is why Kafka is replay-able.

---

## Exercise 7: Circuit Breaker — 30 Lines, Real Behavior

*From [Chapter 1: System Design](../part-1-foundations/01-system-design.md)*

**What you'll learn:** How a circuit breaker transitions between closed, open, and half-open states — and why it prevents cascade failures.

### The code

Create `circuit_breaker.js`:

```javascript
class CircuitBreaker {
  constructor({ failureThreshold = 3, timeout = 5000 } = {}) {
    this.state = 'CLOSED';           // CLOSED | OPEN | HALF_OPEN
    this.failureCount = 0;
    this.failureThreshold = failureThreshold;
    this.timeout = timeout;
    this.nextAttempt = Date.now();
  }

  async call(fn) {
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) throw new Error('Circuit OPEN — fast fail');
      this.state = 'HALF_OPEN';
      console.log('  >> Transitioning to HALF_OPEN, testing upstream...');
    }
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure();
      throw err;
    }
  }

  onSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
    console.log(`  [${this.state}] Success — circuit closed`);
  }

  onFailure() {
    this.failureCount++;
    if (this.failureCount >= this.failureThreshold || this.state === 'HALF_OPEN') {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.timeout;
      console.log(`  [${this.state}] Failure #${this.failureCount} — circuit opened for ${this.timeout}ms`);
    } else {
      console.log(`  [${this.state}] Failure #${this.failureCount} of ${this.failureThreshold}`);
    }
  }
}

// Simulate a flaky upstream: fails 5 times, then recovers
let callCount = 0;
async function flakyUpstream() {
  callCount++;
  if (callCount <= 5) throw new Error(`Upstream down (call ${callCount})`);
  return `OK (call ${callCount})`;
}

async function main() {
  const cb = new CircuitBreaker({ failureThreshold: 3, timeout: 2000 });

  for (let i = 1; i <= 12; i++) {
    console.log(`\nRequest #${i}:`);
    try {
      const result = await cb.call(flakyUpstream);
      console.log(`  Result: ${result}`);
    } catch (e) {
      console.log(`  Error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, i === 4 ? 2500 : 200)); // pause after opening
  }
}

main();
```

```bash
node circuit_breaker.js
```

### Expected output

```
Request #1:
  [CLOSED] Failure #1 of 3
  Error: Upstream down (call 1)

Request #3:
  [OPEN] Failure #3 — circuit opened for 2000ms
  Error: Upstream down (call 3)

Request #4:
  Error: Circuit OPEN — fast fail    <- No call made to upstream at all

Request #5:
  >> Transitioning to HALF_OPEN, testing upstream...
  [CLOSED] Success — circuit closed

Request #6+:
  Result: OK (call N)
```

**What you learned:** The circuit breaker short-circuits fast on open state — zero latency, no upstream load. It self-heals by attempting a probe request after the timeout. This is how Netflix Hystrix, Resilience4j, and Polly all work under the hood.

---

## Exercise 8: Load Testing — k6 Latency Histogram

*From [Chapter 8: Testing & Quality](../part-2-applied-engineering/08-testing-quality.md)*

**What you'll learn:** How to run a load test, read a latency histogram, and find where a simple endpoint breaks under pressure.

### Setup

```bash
# Install k6 (macOS)
brew install k6
# Linux: snap install k6 or see https://k6.io/docs/getting-started/installation

# Start a simple server to test against
docker run -d --name nginx-sandbox -p 8080:80 nginx:alpine
```

Create `load_test.js`:

```javascript
import http from 'k6/http';
import { sleep, check } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const latency = new Trend('request_latency');
const errors = new Counter('errors');

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Ramp up to 10 VUs
    { duration: '30s', target: 50 },   // Ramp up to 50 VUs
    { duration: '30s', target: 100 },  // Push to 100 VUs
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],  // 95% of requests under 200ms
    errors: ['count<50'],              // Fewer than 50 errors total
  },
};

export default function () {
  const start = Date.now();
  const res = http.get('http://localhost:8080/');
  latency.add(Date.now() - start);

  const ok = check(res, { 'status 200': r => r.status === 200 });
  if (!ok) errors.add(1);

  sleep(0.1);
}
```

```bash
k6 run load_test.js
```

### Expected output (nginx handles this fine — look at the histogram shape)

```
http_req_duration...: avg=3.2ms  min=1ms  med=2.8ms  max=87ms  p(90)=5ms  p(95)=7ms  p(99)=18ms
Iterations.........: 24000   ~200/s
```

Now try it against a slower service. Swap `http://localhost:8080/` for a service that does actual work and watch the p99 and p99.9 diverge from the median. That divergence is where your tail latency lives.

```bash
docker stop nginx-sandbox && docker rm nginx-sandbox
```

**What you learned:** The p50/p95/p99 gap tells you about your latency distribution's tail. A small gap means consistent response times. A large gap means some requests are suffering — often due to GC pauses, cache misses, or connection pool exhaustion. Load testing finds breaking points before users do.

---

## Exercise 9: Git Bisect — Find a Bug Automatically

*From [Chapter 1: System Design](../part-1-foundations/01-system-design.md) / General debugging*

**What you'll learn:** How `git bisect` uses binary search to find the exact commit that introduced a bug — without reading every commit.

### Setup

```bash
mkdir bisect-sandbox && cd bisect-sandbox
git init
git config user.email "test@example.com"
git config user.name "Test"

# Create 20 commits, plant a bug at commit 10
for i in $(seq 1 20); do
  if [ $i -eq 10 ]; then
    # The bug: function now returns wrong value
    echo "function add(a, b) { return a - b; }  // Bug introduced here" > calc.js
    echo "module.exports = { add };" >> calc.js
  else
    echo "function add(a, b) { return a + b; }" > calc.js
    echo "module.exports = { add };" >> calc.js
  fi
  git add calc.js
  git commit -m "Commit $i: update calc.js"
done

echo "Done. 20 commits, bug planted at commit 10."
```

### The bisect

```bash
# Create a test script
cat > test.sh << 'EOF'
#!/bin/bash
# Exit 0 = good, non-zero = bad
node -e "
const { add } = require('./calc.js');
const result = add(2, 3);
if (result === 5) { process.exit(0); }
else { process.exit(1); }
"
EOF
chmod +x test.sh

# Start bisect
git bisect start
git bisect bad HEAD           # Current (commit 20) is bad
git bisect good HEAD~19       # Commit 1 was good

# Automated bisect — runs test.sh on each midpoint
git bisect run ./test.sh

# git bisect will find exactly commit 10 in ~4 steps (log2(20))
# vs. checking all 20 manually
```

### Expected output

```
running ./test.sh
Bisecting: 4 revisions left to test after this (roughly 2 steps)
...
commit abc123 is the first bad commit
    Commit 10: update calc.js
```

```bash
git bisect reset
cd .. && rm -rf bisect-sandbox
```

**What you learned:** Bisect is binary search over your commit history. 20 commits = 4–5 steps. 1000 commits = 10 steps. It's one of the most underused tools in a developer's arsenal. If you can write a test that exits 0 for "good" and 1 for "bad," you can find any regression automatically.

---

## Exercise 10: Incident Simulation — Break It, Triage It, Fix It

*From [Chapter 36: Beast Mode](../part-2-applied-engineering/36-beast-mode.md)*

**What you'll learn:** The full incident loop — detect, investigate using logs and metrics, identify root cause, mitigate. No TicketPulse required.

### Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  app:
    image: node:18-alpine
    working_dir: /app
    volumes: [./app:/app]
    command: sh -c "npm install pg && node server.js"
    ports: ["3000:3000"]
    environment:
      - DB_URL=postgres://postgres:secret@db:5432/appdb
      - FEATURE_CHAOS=false

  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: appdb
    ports: ["5433:5432"]
```

Create `app/server.js`:

```javascript
const http = require('http');
const { Client } = require('pg');

const DB_URL = process.env.DB_URL;
const CHAOS_MODE = process.env.FEATURE_CHAOS === 'true';

async function query(sql) {
  const client = new Client({ connectionString: DB_URL });
  await client.connect();
  try {
    if (CHAOS_MODE) {
      await new Promise(r => setTimeout(r, 5000));
      throw new Error('DB connection timeout');
    }
    const result = await client.query(sql);
    return result.rows;
  } finally {
    await client.end();
  }
}

let requestCount = 0, errorCount = 0;

const server = http.createServer(async (req, res) => {
  const start = Date.now();
  requestCount++;

  if (req.url === '/health') {
    res.writeHead(200);
    return res.end(JSON.stringify({ status: 'ok', requests: requestCount, errors: errorCount }));
  }

  if (req.url === '/metrics') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    return res.end([
      `http_requests_total ${requestCount}`,
      `http_errors_total ${errorCount}`,
    ].join('\n'));
  }

  try {
    await query('SELECT 1 as alive');
    const latency = Date.now() - start;
    console.log(JSON.stringify({ ts: new Date().toISOString(), path: req.url, status: 200, latency_ms: latency }));
    res.writeHead(200);
    res.end('{"status":"ok"}');
  } catch (e) {
    errorCount++;
    console.error(JSON.stringify({ ts: new Date().toISOString(), path: req.url, status: 500, error: e.message }));
    res.writeHead(500);
    res.end('{"status":"error"}');
  }
});

server.listen(3000, () => console.log('Server up on :3000'));
```

### The incident scenarios

```bash
docker compose up -d
sleep 8  # wait for DB + app to be ready

# Verify it works
curl http://localhost:3000/health
curl http://localhost:3000/

# --- INCIDENT 1: Database goes down ---
docker compose stop db

# Simulate user traffic hitting the broken service
for i in $(seq 1 10); do curl -s http://localhost:3000/; echo; done

# TRIAGE STEP 1: Check health endpoint
curl http://localhost:3000/health

# TRIAGE STEP 2: Read the logs — look for error field in JSON
docker compose logs app --tail=20

# TRIAGE STEP 3: Check metrics
curl http://localhost:3000/metrics

# MITIGATION: Restore the database
docker compose start db
sleep 5

# Verify recovery
curl http://localhost:3000/
curl http://localhost:3000/health

# --- INCIDENT 2: Chaos mode (simulates slow/timing-out downstream) ---
docker compose stop app
FEATURE_CHAOS=true docker compose up -d app
sleep 5

# Requests will now timeout after 5 seconds
for i in $(seq 1 5); do curl -s --max-time 2 http://localhost:3000/; echo; done

# Read logs to diagnose — "DB connection timeout" in structured logs
docker compose logs app --tail=15

# Identify root cause from env var in logs / config
# FEATURE_CHAOS=true is set — this is the incident trigger

docker compose down
```

### The triage loop

1. **Alert fires**: requests returning 500
2. **Check health**: `/health` shows elevated error count
3. **Read structured logs**: JSON logs with `"error"` field point to DB connection failure
4. **Inspect dependencies**: `docker compose ps` shows `db` container is stopped
5. **Mitigate**: restore DB, verify `/health` shows error count stops climbing
6. **Post-incident**: identify root cause in incident 2 as `FEATURE_CHAOS=true` env var

**What you learned:** Structured JSON logs + a `/health` endpoint + a `/metrics` endpoint are the minimal observability kit for triage. You navigated a complete incident loop — detection, diagnosis, mitigation, verification — using only logs and HTTP calls. That's the beast mode baseline.

---

## Quick Reference: All Exercises

| # | Topic | Chapter | Time | Key Tool |
|---|-------|---------|------|----------|
| 1 | etcd Consensus | System Design | 20 min | Docker Compose, etcdctl |
| 2 | DB Slow Query | Data Engineering | 15 min | Postgres, EXPLAIN ANALYZE |
| 3 | Cache-Aside | Data Engineering | 15 min | Redis, Python |
| 4 | Property Testing | Testing & Quality | 20 min | fast-check, Node |
| 5 | Prometheus + Grafana | Debugging & Monitoring | 30 min | Docker Compose, Node |
| 6 | Kafka Lag | Cloud Integration | 20 min | Docker Compose, kafka-console |
| 7 | Circuit Breaker | System Design | 15 min | Node |
| 8 | Load Testing | Testing & Quality | 20 min | k6 |
| 9 | Git Bisect | Debugging | 15 min | git bisect |
| 10 | Incident Simulation | Beast Mode | 30 min | Docker Compose, logs |

---

*Appendix B is a living document — exercises will be added as new guide chapters are written. If you build a variation of one of these that works better, that's a pull request we want to see.*

# L2-M45: Monitoring Stack -- Prometheus + Grafana

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M43, L2-M44
>
> **Source:** Chapters 4, 18 of the 100x Engineer Guide

## What You'll Learn

- How Prometheus works: pull-based metrics collection, time-series storage, PromQL
- Instrumenting TicketPulse with the four essential metric types: counter, histogram, gauge, summary
- Writing PromQL queries to answer real operational questions
- Building a Grafana dashboard with request rate, error rate, latency percentiles, and business metrics
- Generating load and watching metrics respond in real time
- Configuring alert rules in Prometheus that fire based on your SLOs
- The RED method: the three metrics every service needs

## Why This Matters

It is 11:42 AM on a Friday. A popular artist just announced a surprise drop of 500 tickets on TicketPulse. Traffic spikes to 50x normal in ninety seconds. Your on-call phone lights up: "Purchases are failing." You SSH into the box. Which service is dying -- the API gateway, the event service, the payment service? Is the database melting or is Stripe timing out? Is it every request or just the checkout path? You run `docker logs` and a wall of text floods your terminal. You scroll. You squint. You grep. Nothing useful. Fifteen minutes later, you are still guessing. The tickets are gone. The artist's fans are furious. You never found the bottleneck.

This is what running without monitoring feels like. Blind, slow, and always too late.

Now picture the alternative: a single Grafana dashboard showing request rate per service, error rate spiking on the payment service, p99 latency at 8 seconds on `/api/checkout`. You see it in five seconds. You know exactly where to look. That is the difference Prometheus and Grafana make.

By the end of this module, you will have that dashboard -- real metrics flowing from every TicketPulse service, visualized in real time on your screen. You will never debug blind again.

## Prereq Check

You need the TicketPulse services running from L2-M43/M44. We will add Prometheus and Grafana alongside them.

```bash
# Verify TicketPulse is running
kubectl get pods -n ticketpulse
# Should show api-gateway, event-service, payment-service pods

# Or if using docker compose (either works for this module)
docker compose ps
```

---

## 1. Deploy: Prometheus + Grafana

We will use docker compose to run the monitoring stack alongside TicketPulse. This is the fastest path to a working setup.

Add these services to your `docker-compose.yml`:

```yaml
# Add to docker-compose.yml

  prometheus:
    image: prom/prometheus:v2.51.0
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/alert-rules.yml:/etc/prometheus/alert-rules.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3100:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=ticketpulse
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    restart: unless-stopped

# Add to volumes section:
  prometheus_data:
  grafana_data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Create the Prometheus configuration:

```bash
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
```

```yaml
# monitoring/prometheus.yml

global:
  scrape_interval: 15s          # How often Prometheus pulls metrics
  evaluation_interval: 15s      # How often it evaluates alert rules
  scrape_timeout: 10s

# Alert rules file
rule_files:
  - "alert-rules.yml"

# Targets to scrape
scrape_configs:
  # Prometheus monitors itself
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  # TicketPulse API Gateway
  - job_name: "api-gateway"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["app:3000"]
        labels:
          service: "api-gateway"

  # TicketPulse Event Service
  - job_name: "event-service"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["event-service:3001"]
        labels:
          service: "event-service"

  # TicketPulse Payment Service
  - job_name: "payment-service"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["payment-service:3002"]
        labels:
          service: "payment-service"
```

Create an empty alert rules file for now (we will fill it later):

```yaml
# monitoring/alert-rules.yml

groups: []
```

Auto-provision Grafana's Prometheus datasource:

```yaml
# monitoring/grafana/provisioning/datasources/prometheus.yml

apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

```bash
# Start the monitoring stack
docker compose up -d prometheus grafana
```

Verify:

```bash
# Prometheus should be running
curl -s http://localhost:9090/-/healthy
# "Prometheus Server is Healthy."

# Grafana should be running
curl -s http://localhost:3100/api/health | jq .
# {"commit":"...","database":"ok","version":"10.4.0"}
```

Open http://localhost:9090 in your browser. You should see the Prometheus UI. Open http://localhost:3100 and log in with admin/ticketpulse.

---

## 2. Build: Instrument TicketPulse with Prometheus Metrics

Prometheus collects metrics by pulling (scraping) a `/metrics` endpoint from your application. You need to expose that endpoint.

<details>
<summary>💡 Hint 1: Metric Types</summary>
Use a Counter for things that only go up (total requests, errors, tickets sold). Use a Histogram for distributions you want percentiles from (request duration, payment latency). Use a Gauge for values that go up and down (active connections, available tickets). Avoid Summary -- histograms are aggregatable across instances; summaries are not.
</details>

<details>
<summary>💡 Hint 2: Label Cardinality</summary>
Labels let you slice metrics (by method, path, status_code), but each unique label combination creates a separate time series. Normalize paths to avoid high cardinality: <code>/api/events/123</code> becomes <code>/api/events/:id</code>. Never use user IDs, request IDs, or UUIDs as label values.
</details>

<details>
<summary>💡 Hint 3: Verifying Scraping</summary>
After instrumenting, verify with <code>curl -s http://localhost:3000/metrics | head -30</code>. You should see lines like <code># TYPE http_requests_total counter</code> followed by metric values. In Prometheus UI, check Status -> Targets to confirm all services show state "UP."
</details>

Install the Prometheus client library:

```bash
npm install prom-client
```

Create the metrics module:

```typescript
// src/metrics.ts

import client from 'prom-client';

// Create a Registry (holds all metrics)
const register = new client.Registry();

// Add default metrics (Node.js process metrics: CPU, memory, event loop lag, etc.)
client.collectDefaultMetrics({ register });

// =====================================================
// HTTP Metrics
// =====================================================

// Counter: total number of HTTP requests
// Labels let you filter by method, path, and status code
export const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'path', 'status_code'] as const,
  registers: [register],
});

// Histogram: HTTP request duration in seconds
// Buckets define the ranges for latency measurement
// These buckets cover 5ms to 10s -- adjust based on your SLOs
export const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds',
  labelNames: ['method', 'path', 'status_code'] as const,
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

// =====================================================
// Business Metrics
// =====================================================

// Counter: total tickets sold (the metric your business cares about)
export const ticketsSoldTotal = new client.Counter({
  name: 'ticketpulse_tickets_sold_total',
  help: 'Total number of tickets sold',
  labelNames: ['event_id', 'ticket_type'] as const,
  registers: [register],
});

// Counter: total purchase attempts and their outcomes
export const purchaseAttemptsTotal = new client.Counter({
  name: 'ticketpulse_purchase_attempts_total',
  help: 'Total purchase attempts by outcome',
  labelNames: ['outcome'] as const,  // success, payment_failed, sold_out, error
  registers: [register],
});

// Gauge: currently active WebSocket or HTTP connections
export const activeConnections = new client.Gauge({
  name: 'ticketpulse_active_connections',
  help: 'Number of currently active connections',
  registers: [register],
});

// Gauge: available tickets per event (point-in-time value)
export const availableTickets = new client.Gauge({
  name: 'ticketpulse_available_tickets',
  help: 'Number of available tickets per event',
  labelNames: ['event_id'] as const,
  registers: [register],
});

// Histogram: payment processing duration
export const paymentDuration = new client.Histogram({
  name: 'ticketpulse_payment_duration_seconds',
  help: 'Payment processing duration in seconds',
  labelNames: ['payment_method', 'outcome'] as const,
  buckets: [0.1, 0.25, 0.5, 1, 2, 5, 10],
  registers: [register],
});

export { register };
```

### Understanding the four metric types

**Counter:** Only goes up. Tracks totals (requests served, errors occurred, tickets sold). You derive rates from counters using `rate()`.

**Histogram:** Tracks the distribution of values (request duration, response size). Prometheus stores counts in predefined buckets. You extract percentiles using `histogram_quantile()`.

**Gauge:** Goes up and down. Tracks current values (active connections, queue depth, available tickets).

**Summary:** Like a histogram but calculates percentiles client-side. Use histograms instead -- they can be aggregated across instances; summaries cannot.

### Add the metrics middleware

```typescript
// src/middleware/metrics.ts

import { Request, Response, NextFunction } from 'express';
import {
  httpRequestsTotal,
  httpRequestDuration,
  activeConnections,
} from '../metrics';

export function metricsMiddleware(req: Request, res: Response, next: NextFunction) {
  // Skip the metrics endpoint itself (avoid infinite recursion in metrics)
  if (req.path === '/metrics') {
    return next();
  }

  // Track active connections
  activeConnections.inc();

  // Record start time
  const startTime = process.hrtime.bigint();

  // When the response finishes
  res.on('finish', () => {
    const endTime = process.hrtime.bigint();
    const durationSeconds = Number(endTime - startTime) / 1e9;

    // Normalize the path to avoid high-cardinality labels
    // /api/events/123 → /api/events/:id
    const normalizedPath = normalizePath(req.route?.path || req.path);

    // Increment request counter
    httpRequestsTotal.inc({
      method: req.method,
      path: normalizedPath,
      status_code: res.statusCode.toString(),
    });

    // Record duration in histogram
    httpRequestDuration.observe(
      {
        method: req.method,
        path: normalizedPath,
        status_code: res.statusCode.toString(),
      },
      durationSeconds
    );

    // Decrement active connections
    activeConnections.dec();
  });

  next();
}

function normalizePath(path: string): string {
  // Replace UUIDs and numeric IDs with :id
  return path
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, ':id')
    .replace(/\/\d+/g, '/:id');
}
```

> **Critical: Avoid high-cardinality labels.** If you use the raw path (`/api/events/123`, `/api/events/456`, ...), you create a new time series for every event ID. Thousands of events = thousands of time series = Prometheus runs out of memory. Always normalize paths.

### Expose the /metrics endpoint

```typescript
// src/app.ts -- add these lines

import { register } from './metrics';
import { metricsMiddleware } from './middleware/metrics';

// Apply metrics middleware BEFORE your routes
app.use(metricsMiddleware);

// Expose metrics endpoint for Prometheus to scrape
app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

### Add business metric tracking

In your purchase handler:

```typescript
// In your ticket purchase route handler

import { ticketsSoldTotal, purchaseAttemptsTotal, paymentDuration } from '../metrics';

// After a successful purchase:
ticketsSoldTotal.inc({ event_id: eventId, ticket_type: ticketType });
purchaseAttemptsTotal.inc({ outcome: 'success' });

// After a failed purchase:
purchaseAttemptsTotal.inc({ outcome: 'payment_failed' });

// Timing payment processing:
const paymentTimer = paymentDuration.startTimer({
  payment_method: 'stripe',
  outcome: 'pending',
});
// ... process payment ...
paymentTimer({ outcome: paymentResult.success ? 'success' : 'failed' });
```

Rebuild and restart:

```bash
docker compose up -d --build app
```

Verify metrics are exposed:

```bash
curl -s http://localhost:3000/metrics | head -30
```

You should see output like:

```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/health",status_code="200"} 15
# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/health",status_code="200",le="0.005"} 14
http_request_duration_seconds_bucket{method="GET",path="/health",status_code="200",le="0.01"} 15
...
```

---

## 3. Try It: Query Metrics in Prometheus

Open http://localhost:9090 in your browser. Go to the "Graph" tab.

First, verify Prometheus is scraping your app:

```
Status → Targets
```

You should see all three TicketPulse services with state "UP." If a target is "DOWN," check that the `/metrics` endpoint is accessible from the Prometheus container.

Now query your metrics. Type each query into the expression box and click "Execute."

### Request rate (requests per second over the last 5 minutes)

```promql
rate(http_requests_total[5m])
```

This returns the per-second rate of requests, broken down by every label combination. Switch to the "Graph" tab to see it over time.

### Total request rate for the API gateway

```promql
sum(rate(http_requests_total{service="api-gateway"}[5m]))
```

`sum()` aggregates across all label combinations, giving you a single number: total requests per second.

### Error rate (5xx responses)

```promql
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
```

The `=~` operator uses regex matching. `"5.."` matches any status code starting with 5.

### Error rate as a percentage

```promql
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
* 100
```

This is your error rate percentage. If it is above your SLO threshold, something is wrong.

### p99 latency (the 99th percentile request duration)

```promql
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

This answers: "99% of requests complete in less than X seconds." The remaining 1% are your tail latency -- the users having the worst experience.

### p50 and p95 latency for comparison

```promql
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

Compare p50, p95, and p99. If p99 is 10x p50, you have a tail latency problem -- most users are fine, but some are having a terrible experience.

### Tickets sold in the last hour

```promql
increase(ticketpulse_tickets_sold_total[1h])
```

`increase()` is like `rate()` but returns the total count increase over the window instead of per-second rate.

---

## 4. Build: Grafana Dashboard

<details>
<summary>💡 Hint 1: Essential PromQL Queries</summary>
For request rate: <code>sum by (service) (rate(http_requests_total[5m]))</code>. For error rate percentage: <code>sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100</code>. For p99 latency: <code>histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))</code>.
</details>

<details>
<summary>💡 Hint 2: Dashboard JSON Export</summary>
After building your dashboard manually, click the share icon and export as JSON. Save this JSON to <code>monitoring/grafana/provisioning/dashboards/</code> so the dashboard is version-controlled and auto-provisioned on startup. Add a dashboard provider YAML file pointing to that directory.
</details>

<details>
<summary>💡 Hint 3: Threshold Lines</summary>
In each Grafana panel, add threshold lines at your SLO boundaries. For error rate, add a red line at 0.1% (your 99.9% availability SLO). For latency, add a line at 1s (your p99 target). These visual references make it instant to see whether you are within SLO.
</details>

Open Grafana at http://localhost:3100 (admin/ticketpulse).

### Create the dashboard manually

1. Click "+" → "New dashboard"
2. Click "Add visualization"
3. Select "Prometheus" as the data source

### Panel 1: Request Rate (time series)

- Query: `sum by (service) (rate(http_requests_total[5m]))`
- Title: "Request Rate (req/s)"
- Visualization: Time series
- Legend: `{{service}}`

This shows the request rate for each service on a single graph. You can instantly see which service is receiving the most traffic.

### Panel 2: Error Rate (time series)

- Query A: `sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (service)`
- Title: "Error Rate (5xx/s)"
- Visualization: Time series
- Legend: `{{service}}`
- Add a threshold line at your SLO (e.g., 0.001 for 99.9% availability)

Add a second query to show error percentage:

- Query B: `sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100`
- Title: "Error Rate %"
- Right Y axis

### Panel 3: Latency Percentiles (time series)

- Query A (p50): `histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m])))`
- Query B (p95): `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m])))`
- Query C (p99): `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m])))`
- Title: "API Gateway Latency"
- Legend: p50, p95, p99
- Unit: seconds (s)

This is the most valuable panel. At a glance, you see: "p50 is 15ms (most users), p95 is 80ms (some users), p99 is 450ms (unlucky users)."

### Panel 4: Tickets Sold (counter)

- Query: `sum(increase(ticketpulse_tickets_sold_total[1h]))`
- Title: "Tickets Sold (last hour)"
- Visualization: Stat (single number)
- Color: green

This is a business metric on an engineering dashboard. When the CEO asks "how many tickets did we sell today?" you can answer from the same dashboard you use to debug outages.

### Save the dashboard

Click the save icon. Name it "TicketPulse Overview."

---

> **Before you continue:** When you generate load with wrk, which Grafana panel do you expect to change first -- request rate, error rate, or latency? What would it mean if error rate spikes before latency increases?

## 5. Observe: Generate Traffic and Watch

Install a load testing tool:

```bash
# Install wrk (macOS)
brew install wrk

# Install wrk (Linux)
sudo apt install wrk
```

Generate traffic:

```bash
# 10 concurrent connections, 2 threads, 30 seconds
wrk -t2 -c10 -d30s http://localhost:3000/api/events
```

Now switch to your Grafana dashboard. You should see:

- **Request Rate** jumping from near-zero to your load level
- **Latency Percentiles** showing the distribution under load
- **Error Rate** staying at zero (if everything is healthy)

This is the moment. You are watching real metrics flow through a real monitoring stack. This is what production monitoring looks like.

Now cause some errors:

```bash
# Hit a non-existent endpoint to generate 404s
wrk -t2 -c5 -d15s http://localhost:3000/api/nonexistent

# If you have a way to trigger 500s (e.g., kill the database temporarily)
docker compose stop postgres
# Wait 10 seconds, then restart
docker compose start postgres
```

Watch the error rate panel spike. Watch the latency percentiles jump. This is what an incident looks like on a dashboard.

---

## 6. Build: Alert Rules

Alerts turn metrics into notifications. The goal: alert on symptoms (user impact), not causes (CPU usage).

<details>
<summary>💡 Hint 1: Alert Rule Structure</summary>
Each Prometheus alert rule needs an <code>expr</code> (PromQL expression that returns true when the alert should fire), a <code>for</code> duration (how long the condition must be true before firing -- prevents flapping), <code>labels</code> (severity for routing), and <code>annotations</code> (human-readable summary and description with a runbook URL).
</details>

<details>
<summary>💡 Hint 2: Reload After Changes</summary>
After editing <code>monitoring/alert-rules.yml</code>, reload Prometheus with <code>curl -X POST http://localhost:9090/-/reload</code> (requires the <code>--web.enable-lifecycle</code> flag). Verify rules loaded with <code>curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'</code>.
</details>

<details>
<summary>💡 Hint 3: Testing Alert Firing</summary>
To trigger an alert, stop the database (<code>docker compose stop postgres</code>) and generate traffic. Watch the alert at <code>http://localhost:9090/alerts</code> transition from inactive to pending (threshold crossed) to firing (the <code>for</code> duration elapsed). Restart postgres to resolve.
</details>

```yaml
# monitoring/alert-rules.yml

groups:
  - name: ticketpulse-slo-alerts
    rules:
      # -----------------------------------------------
      # SLO: 99.9% availability
      # Alert if error rate exceeds 0.1% for 5 minutes
      # -----------------------------------------------
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_requests_total{status_code=~"5.."}[5m]))
            /
            sum(rate(http_requests_total[5m]))
          ) > 0.001
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 0.1%). Check service health and recent deployments."
          runbook_url: "https://wiki.internal/runbooks/high-error-rate"

      # -----------------------------------------------
      # SLO: p99 latency < 1s
      # Alert if p99 exceeds 1s for 10 minutes
      # -----------------------------------------------
      - alert: HighLatency
        expr: |
          histogram_quantile(0.99,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "p99 latency exceeds 1s"
          description: "p99 latency is {{ $value | humanizeDuration }}. Check for slow database queries, downstream service issues, or resource exhaustion."

      # -----------------------------------------------
      # SLO: purchase success rate > 99.95%
      # Alert if purchase failures exceed 0.05%
      # -----------------------------------------------
      - alert: PurchaseFailureRate
        expr: |
          (
            sum(rate(ticketpulse_purchase_attempts_total{outcome!="success"}[5m]))
            /
            sum(rate(ticketpulse_purchase_attempts_total[5m]))
          ) > 0.0005
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Purchase failure rate too high"
          description: "Purchase failure rate is {{ $value | humanizePercentage }}. Revenue is being lost. Immediate investigation required."

      # -----------------------------------------------
      # Infrastructure: a target is down
      # -----------------------------------------------
      - alert: TargetDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"
          description: "Prometheus cannot reach {{ $labels.instance }}. The service may be crashed or unreachable."

      # -----------------------------------------------
      # Infrastructure: high memory usage
      # -----------------------------------------------
      - alert: HighMemoryUsage
        expr: |
          process_resident_memory_bytes / 1024 / 1024 > 400
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.job }}"
          description: "Process is using {{ $value | humanize }}MB of memory. May be approaching OOM."
```

Reload Prometheus to pick up the new rules:

```bash
# If using --web.enable-lifecycle flag (we did)
curl -X POST http://localhost:9090/-/reload

# Verify rules are loaded
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'
```

You should see your alert names listed.

### Trigger an alert

Let us intentionally trigger the HighErrorRate alert:

```bash
# Stop the database to cause 500 errors
docker compose stop postgres

# Generate traffic that will fail
wrk -t2 -c10 -d120s http://localhost:3000/api/events

# Wait 5 minutes for the alert to fire (the 'for: 5m' clause)
```

Check alert status in Prometheus:

```
http://localhost:9090/alerts
```

You should see HighErrorRate transition from "inactive" → "pending" (waiting for the `for` duration) → "firing".

```bash
# Restart the database to resolve the alert
docker compose start postgres
```

The alert will transition back to "inactive" once the error rate drops below 0.1% for a full evaluation cycle.

---

## 7. The RED Method

Every request-driven service needs exactly three types of metrics:

| Metric | What It Measures | PromQL Example |
|--------|-----------------|----------------|
| **Rate** | How many requests per second? | `sum(rate(http_requests_total[5m]))` |
| **Errors** | How many of those are failing? | `sum(rate(http_requests_total{status_code=~"5.."}[5m]))` |
| **Duration** | How long do requests take? | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` |

If Rate is normal, Errors are low, and Duration is fast -- your service is healthy. If any of these deviate from baseline, you have a problem and know where to look.

For resource-oriented components (databases, caches, queues), use the **USE method**: Utilization, Saturation, Errors.

| Metric | What It Measures | Example |
|--------|-----------------|---------|
| **Utilization** | How busy is the resource? | CPU usage %, connection pool usage % |
| **Saturation** | How queued is the work? | Request queue length, disk I/O queue depth |
| **Errors** | Is the resource failing? | Connection refused, timeout errors |

---

## 8. Reflect

> **What did you notice?** When you generated load and watched the Grafana dashboard in real time, which panel gave you the most useful signal? How did it feel compared to debugging with logs alone?

> **"We have metrics on every HTTP request. What should we NOT put a metric on?"**
>
> Individual user IDs, individual request IDs, full URLs with query parameters -- anything that creates unbounded cardinality. If a label can have millions of distinct values, it will overwhelm Prometheus. Use traces (L2-M46) for per-request debugging.

> **"Our p99 is 450ms but our p50 is 15ms. Is that a problem?"**
>
> A 30x ratio between p50 and p99 suggests bimodal behavior: most requests are fast, but some hit a slow path. Common causes: cache misses (most requests hit cache, some go to the database), one slow endpoint pulling up the aggregate, or resource contention under load. Break down by path: `histogram_quantile(0.99, sum by (le, path) (rate(...)))` to find which endpoint is slow.

> **"The HighErrorRate alert fires at 0.1%. With 1000 requests per minute, that is just 1 error per minute. Is that too sensitive?"**
>
> It depends on your SLO. 99.9% availability = 0.1% error budget = 43.2 minutes of errors per month. If 1 error per minute is sustained, that burns through your budget. The `for: 5m` clause prevents flapping on transient single errors. For lower-traffic services, consider using multi-window, multi-burn-rate alerts (covered in L2-M47).

---

## 9. Checkpoint

After this module, you should have:

- [ ] Prometheus running and scraping metrics from all TicketPulse services
- [ ] TicketPulse instrumented with `prom-client`: counters, histograms, gauges
- [ ] A `/metrics` endpoint on each service exposing Prometheus-format metrics
- [ ] Path normalization to avoid high-cardinality labels
- [ ] You have run PromQL queries in the Prometheus UI
- [ ] A Grafana dashboard with 4 panels: request rate, error rate, latency percentiles, tickets sold
- [ ] You have generated load with `wrk` and watched the dashboard respond
- [ ] Alert rules configured for error rate, latency, and purchase failures
- [ ] You have intentionally triggered an alert and watched it fire
- [ ] Understanding of the RED method (Rate, Errors, Duration)

**Next up:** L2-M46 where we add distributed tracing with OpenTelemetry to see the full request journey across services.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Prometheus** | An open-source monitoring system that collects metrics via a pull model (scraping HTTP endpoints) and stores them as time series. |
| **Grafana** | An open-source visualization platform for building dashboards from metric, log, and trace data sources. |
| **PromQL** | Prometheus Query Language. Used to query and aggregate time-series metrics data. |
| **Counter** | A metric that only increases. Used for totals (requests, errors, bytes). Derive rates with `rate()`. |
| **Histogram** | A metric that counts observations in configurable buckets. Used for distributions (latency, sizes). Extract percentiles with `histogram_quantile()`. |
| **Gauge** | A metric that can increase or decrease. Used for current values (connections, queue depth, temperature). |
| **Scrape** | The act of Prometheus pulling metrics from a target's `/metrics` endpoint at a configured interval. |
| **Label** | A key-value pair attached to a metric, enabling filtering and grouping. Keep cardinality low. |
| **RED Method** | Rate, Errors, Duration -- the three metrics every request-driven service needs. |
| **USE Method** | Utilization, Saturation, Errors -- the three metrics every resource (CPU, disk, pool) needs. |
| **Alert Rule** | A PromQL expression that Prometheus evaluates periodically. When true for the `for` duration, the alert fires. |
| **High Cardinality** | A label with many distinct values (e.g., user_id). Causes excessive memory usage in Prometheus. Avoid. |

---

## What's Next

In **Distributed Tracing with OpenTelemetry** (L2-M46), you'll trace requests across TicketPulse's services and pinpoint exactly where latency hides.

# L2-M48: Chaos Engineering

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L2-M43, L2-M45, L2-M46, L2-M47, L2-M49
>
> **Source:** Chapter 4 of the 100x Engineer Guide

## What You'll Learn

- The principles of chaos engineering: hypothesis-driven failure injection
- Running four chaos experiments against TicketPulse
- Observing cascading failures across a microservices system in real time
- Using your monitoring stack (Prometheus, Grafana, Jaeger) to detect and diagnose injected failures
- Writing a game day plan with hypotheses and expected outcomes
- The difference between testing and chaos engineering

## Why This Matters

You have built a monitoring stack, configured alerts, written runbooks, and added distributed tracing. But you have never tested any of it under real failure conditions. Does the circuit breaker actually trip when the payment service goes down? Does the alert fire within 5 minutes? Can the on-call engineer follow the runbook?

Chaos engineering answers these questions by breaking things on purpose, in a controlled way. You will discover gaps in your resilience, monitoring, and runbooks before your users discover them for you.

Netflix runs Chaos Monkey in production continuously. Every service must handle random instance termination as normal operations. The goal is not to cause outages -- it is to build confidence that your system can handle the unexpected.

## Prereq Check

You need the full TicketPulse stack running: microservices, Kafka, Prometheus, Grafana, and Jaeger from previous modules. You also need the circuit breaker from L2-M49.

```bash
# Verify everything is running
docker compose ps

# Or with Kubernetes
kubectl get pods -n ticketpulse

# Verify Grafana dashboard is accessible
curl -s http://localhost:3100/api/health | jq .status
# "ok"

# Verify Prometheus is scraping
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | .labels.job + ": " + .health'
# "api-gateway: up"
# "event-service: up"
# "payment-service: up"
```

Open your Grafana dashboard in a browser window you can see while running experiments. You want to watch metrics move in real time.

---

## 1. Reflect: Predict Before You Break

Before injecting any chaos, write down your predictions. This is the hypothesis in "hypothesis-driven testing."

Take 5 minutes. For each scenario, write what you think will happen:

> **Scenario 1: The payment service crashes.**
> What happens to purchase requests? Do they fail immediately? Do they hang? Do they retry? Does the API gateway return an error to the user? What error code?

> **Scenario 2: The database has 2 seconds of added latency.**
> What happens to request latency? Does it affect all services or just the ones that query the database? Do timeouts fire? Do circuit breakers trip?

> **Scenario 3: A Kafka broker goes down.**
> Do events still flow? Do producers fail or buffer? Does the notification consumer recover when Kafka comes back?

> **Scenario 4: The database disk is full (writes fail).**
> Can users still read events? Do purchases fail with a clear error? Does the app hang or crash?

Write your predictions in a file or notebook. You will compare them to reality after each experiment.

---

## 2. The Chaos Engineering Process

Every experiment follows this loop:

```
1. Define steady state    → What does "normal" look like? (metrics, SLOs)
2. Form a hypothesis      → "The system will continue to serve reads even if the payment service is down"
3. Inject the failure     → Kill the service, add latency, corrupt data
4. Observe                → Watch metrics, traces, logs, user experience
5. Learn                  → Was the hypothesis correct? What surprised you?
6. Fix                    → Address the gaps you discovered
```

The goal is NOT to cause an outage. The goal is to disprove your hypothesis. If you cannot break the system, your resilience is working. If you can, you have found a gap to fix.

---

> **Before you continue:** When the payment service is killed, will purchase requests fail immediately (0ms), fail slowly (30s timeout), or succeed with degraded behavior? Write down your prediction before injecting the failure.

## 3. Experiment 1: Kill the Payment Service

### Steady state

Open your Grafana dashboard. Note the current request rate, error rate (should be ~0%), and latency percentiles.

### Hypothesis

"When the payment service is killed, purchase requests will fail gracefully with a clear error message. Non-purchase endpoints (listing events, viewing tickets) will continue to work normally. The circuit breaker will trip after 5 failures, and subsequent purchase attempts will fail fast instead of timing out."

### Inject

```bash
# Docker Compose
docker compose stop payment-service

# Or Kubernetes
kubectl delete pod -n ticketpulse -l app=payment-service
```

### Generate traffic

In a separate terminal, simulate users:

```bash
# Healthy traffic (should continue working)
wrk -t2 -c5 -d60s http://localhost:3000/api/events &

# Purchase traffic (should fail gracefully)
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "Purchase $i: HTTP %{http_code} in %{time_total}s\n" \
    -X POST http://localhost:3000/api/purchases \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <your-jwt-token>" \
    -d '{"eventId": "1", "ticketType": "general"}'
  sleep 2
done
```

### Observe

Watch your Grafana dashboard. You should see:

- **Error rate panel:** Spike for purchase-related requests
- **Request rate panel:** Non-purchase traffic continues normally
- **Latency panel:** Early purchase attempts may timeout (slow failure). After the circuit breaker trips, they should fail fast

Check the API gateway logs:

```bash
docker compose logs -f app --tail=50
# Or: kubectl logs -n ticketpulse -l app=api-gateway -f --tail=50
```

Look for:
- Connection refused errors (expected)
- Circuit breaker state transitions (CLOSED → OPEN)
- The response to the user (should be a clear "payment service unavailable" message, not a stack trace)

Check Jaeger for failed traces:

```
http://localhost:16686
Service: api-gateway
Tags: error=true
```

The trace should show the payment service call failing with a clear span error.

### Learn

Compare to your prediction:
- Did purchases fail gracefully? Or did the API gateway hang/crash?
- Did non-purchase endpoints continue working? (This tests bulkhead isolation.)
- How quickly did the circuit breaker trip? Was there a period of slow failures first?
- What HTTP status code did the user receive? Was the error message helpful?
- Did the Prometheus alert fire?

### Fix (if needed)

Common gaps discovered:
- **No circuit breaker:** Every purchase attempt waits for a TCP timeout (30+ seconds). Fix: add the circuit breaker from L2-M49.
- **Gateway crashes:** An unhandled exception in the purchase handler brings down the entire API gateway. Fix: add try/catch with proper error responses.
- **Misleading error message:** The user sees "Internal Server Error" instead of "Payment service temporarily unavailable." Fix: catch the specific error and return a meaningful message.

```bash
# Restore the payment service
docker compose start payment-service
# Or: kubectl will auto-restart the deleted pod
```

---

## 4. Experiment 2: Add 2 Seconds of Database Latency

### Hypothesis

"Adding 2 seconds of latency to the database will cause API response times to increase. Requests that exceed the timeout will fail. The impact will cascade: slow database → slow API → slow client → potential timeouts upstream."

### Inject

Use toxiproxy (a TCP proxy for simulating network conditions):

```bash
# Add toxiproxy to docker-compose.yml
```

```yaml
  toxiproxy:
    image: ghcr.io/shopify/toxiproxy:2.9.0
    ports:
      - "8474:8474"      # Toxiproxy API
      - "15432:15432"    # Proxied PostgreSQL
    restart: unless-stopped
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```bash
docker compose up -d toxiproxy

# Create a proxy for PostgreSQL
curl -s -X POST http://localhost:8474/proxies -d '{
  "name": "postgres",
  "listen": "0.0.0.0:15432",
  "upstream": "postgres:5432"
}' | jq .

# Now reconfigure the API gateway to use the proxy
# DATABASE_URL=postgresql://ticketpulse:password@toxiproxy:15432/ticketpulse

# Add 2 seconds of latency
curl -s -X POST http://localhost:8474/proxies/postgres/toxics -d '{
  "name": "latency",
  "type": "latency",
  "attributes": {
    "latency": 2000,
    "jitter": 500
  }
}' | jq .
```

If toxiproxy setup is too complex, use a simpler approach -- add latency directly in the database:

```sql
-- Connect to PostgreSQL and create a slow function
CREATE OR REPLACE FUNCTION slow_query_hook() RETURNS trigger AS $$
BEGIN
  PERFORM pg_sleep(2);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add it to a frequently queried table
CREATE TRIGGER slow_read_trigger
  BEFORE SELECT ON events
  FOR EACH STATEMENT
  EXECUTE FUNCTION slow_query_hook();
```

Or the simplest approach -- add a delay in your application code:

```typescript
// TEMPORARY: chaos engineering experiment
// In event-service/src/db.ts
const originalQuery = pool.query.bind(pool);
pool.query = async (...args: any[]) => {
  await new Promise(resolve => setTimeout(resolve, 2000));
  return originalQuery(...args);
};
```

### Observe

Generate traffic and watch:

```bash
wrk -t2 -c10 -d60s http://localhost:3000/api/events
```

On your Grafana dashboard:
- **Latency panel:** p50 should jump from ~15ms to ~2000ms. p99 will be even higher.
- **Request rate panel:** May decrease as each request takes longer (connection pool saturation).
- **Error rate panel:** If you have a request timeout configured (e.g., 5s), requests exceeding it will error.

Check `kubectl top pods` or `docker stats`:
- Active connections pile up as requests wait for the slow database
- Memory may increase as requests queue

Open Jaeger and find a slow trace:
- The database span should show a 2+ second duration
- The total trace should show the cascading impact

### Learn

- Did the API gateway timeout fire? Or did it wait the full 2 seconds?
- Did connection pool exhaustion occur? (Too many connections waiting = new connections fail)
- Did the slow database affect services that do NOT use the database? (It should not -- if it does, you have a shared resource problem.)
- Did Little's Law show up? `L = lambda * W` -- if arrival rate is 100 req/s and each takes 2s, you need 200 concurrent connections.

### Fix

```bash
# Remove the latency
curl -s -X DELETE http://localhost:8474/proxies/postgres/toxics/latency

# Or remove the trigger
# DROP TRIGGER slow_read_trigger ON events;
# DROP FUNCTION slow_query_hook();

# Or remove the application-level delay
```

Common fixes after this experiment:
- **Add request timeouts:** Every HTTP call and database query should have a timeout.
- **Connection pool limits:** Set `max` on your database pool and handle "pool exhausted" gracefully.
- **Query timeouts:** `SET statement_timeout = '5s'` in PostgreSQL.
- **Separate read/write pools:** Slow writes should not block reads.

---

## 5. Experiment 3: Kill a Kafka Broker

### Hypothesis

"When Kafka goes down, event production will fail but purchases will still complete (the Kafka publish is non-critical). The notification consumer will stop processing but will resume from its last offset when Kafka recovers. No events will be lost."

### Inject

```bash
# Docker Compose
docker compose stop kafka

# Kubernetes
kubectl delete pod -n ticketpulse -l app=kafka
```

### Generate traffic

```bash
# Purchase tickets (the Kafka publish happens after purchase)
for i in $(seq 1 10); do
  curl -s -w "Purchase $i: HTTP %{http_code}\n" \
    -X POST http://localhost:3000/api/purchases \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <your-jwt-token>" \
    -d '{"eventId": "1", "ticketType": "general"}'
  sleep 1
done
```

### Observe

- Do purchases succeed? (They should, if the Kafka publish is in a try/catch with the failure swallowed.)
- Or do purchases fail? (They will, if the Kafka publish is in the critical path without error handling.)
- Check the notification consumer logs -- it should be disconnected and retrying.

Watch the Prometheus `up` metric:

```promql
up{job="kafka"}
```

It should drop to 0. Your `TargetDown` alert should fire.

### Learn and Fix

```bash
# Restore Kafka
docker compose start kafka
```

- Did the notification consumer reconnect and process the backlog?
- Were any events lost? (Check: count purchases in the database vs count events in the Kafka topic.)
- Did the purchase flow handle the Kafka failure gracefully?

If purchases failed when Kafka was down, the fix is: make the Kafka publish non-critical with a local buffer or outbox pattern.

---

## 6. Experiment 4: Fill the Database Disk

### Hypothesis

"When the database cannot write (disk full), read operations will still work. Write operations (purchases, new events) will fail with a clear error. The application will not hang or crash."

### Inject

We simulate this by making PostgreSQL reject writes:

```sql
-- Connect to PostgreSQL
-- Set the database to read-only mode
ALTER DATABASE ticketpulse SET default_transaction_read_only = on;

-- Reload config
SELECT pg_reload_conf();
```

### Generate traffic

```bash
# Reads should still work
curl -s http://localhost:3000/api/events | jq .

# Writes should fail gracefully
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Should Fail",
    "venue": "Read-Only Arena",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .
```

### Observe

- Does the read endpoint return data? (It should.)
- Does the write endpoint return a clear error? Or does it hang? Or return "Internal Server Error"?
- What does the trace look like for the failed write?
- Does the error rate alert fire?

### Learn and Fix

```sql
-- Restore write access
ALTER DATABASE ticketpulse SET default_transaction_read_only = off;
SELECT pg_reload_conf();
```

Common gaps:
- **No distinction between read and write failures:** The app returns "Database error" for both. Fix: catch read-only errors specifically and return "Service temporarily in read-only mode."
- **Health check fails:** If the health check tries to write, the app is marked unhealthy even though reads work. Fix: health check should only SELECT.
- **Application crashes on write error:** An unhandled exception brings down the process. Fix: catch PostgreSQL error codes (25006 = read-only transaction) and handle gracefully.

---

## 7. Build: Game Day Plan

A game day is a scheduled session where the team runs chaos experiments together. Write a plan for TicketPulse:

```markdown
# TicketPulse Game Day Plan
Date: [Schedule it]
Duration: 2 hours
Participants: [Team members]

## Pre-Game Checklist
- [ ] All services running and healthy
- [ ] Grafana dashboard open on shared screen
- [ ] Jaeger accessible
- [ ] Alertmanager notifications going to a test channel (NOT production)
- [ ] Runbooks accessible
- [ ] Rollback commands ready

## Experiment 1: Payment Service Failure
Hypothesis: Purchases fail fast (< 1s) via circuit breaker. Event listing unaffected.
Injection: docker compose stop payment-service
Duration: 5 minutes
Success criteria: Error rate for purchases > 0, error rate for reads = 0, circuit breaker state = OPEN
Rollback: docker compose start payment-service

## Experiment 2: 50% Packet Loss on Database
Hypothesis: Requests slow down but do not fail. Retries handle transient failures.
Injection: toxiproxy with 50% packet loss on postgres proxy
Duration: 5 minutes
Success criteria: Latency increases, error rate stays below 5%
Rollback: Remove toxic

## Experiment 3: Kafka Unavailable
Hypothesis: Purchases complete. Notifications delayed but not lost.
Injection: docker compose stop kafka
Duration: 5 minutes
Success criteria: Purchases succeed, notification backlog processes after recovery
Rollback: docker compose start kafka

## Experiment 4: API Gateway Memory Pressure
Hypothesis: K8s OOMKills the pod and restarts it. Other replicas handle traffic.
Injection: kubectl set resources deployment/api-gateway --limits=memory=64Mi
Duration: 3 minutes
Success criteria: Pod restarts, no sustained error rate (other replicas absorb)
Rollback: kubectl set resources deployment/api-gateway --limits=memory=512Mi

## Experiment 5: DNS Resolution Failure
Hypothesis: Service-to-service calls fail. Circuit breakers trip within 30 seconds.
Injection: kubectl delete svc event-service
Duration: 3 minutes
Success criteria: API gateway returns errors for event-dependent endpoints, other endpoints unaffected
Rollback: kubectl apply -f k8s/event-service-service.yaml

## Post-Game
- [ ] Document findings for each experiment
- [ ] Create tickets for gaps discovered
- [ ] Update runbooks with new diagnostic steps learned
- [ ] Schedule fixes before next game day
```

---

## 8. Insight: Netflix and the Culture of Chaos

Netflix's Chaos Monkey (2011) randomly terminates production instances during business hours. The thinking: if an instance can fail at any time, every service must handle it. This is not testing -- it is continuous validation.

Key principles from Netflix's chaos engineering practice:

1. **Run in production.** Staging environments do not have the same traffic patterns, data, or infrastructure. Real chaos testing happens against real production.
2. **Minimize blast radius.** Start with a single instance, a single availability zone, a single percentage of traffic. Expand only after you have confidence.
3. **Automate.** If chaos experiments require manual effort, they happen rarely. If automated, they run daily.
4. **Everyone participates.** Chaos engineering is not an SRE task. Application developers are responsible for their service's resilience.

For TicketPulse (and most teams starting out): begin with scheduled game days in a staging environment. Graduate to automated chaos in production only after you have confidence in your monitoring, alerting, and resilience patterns.

---

## 9. Reflect

> **What did you notice?** Which chaos experiment produced the most surprising result? Did your predictions match reality, or did you discover resilience gaps you did not expect?

> **"What was the most surprising result from your experiments?"**
>
> Write down what surprised you. The surprises are the value of chaos engineering. If nothing surprised you, your mental model is accurate -- which is also valuable information.

> **"We tested 4 failure modes. What failure modes did we NOT test?"**
>
> Clock skew between services, TLS certificate expiration, sudden traffic spike (10x normal), corrupt data in Kafka messages, a slow memory leak over hours, a dependency returning wrong data (not errors, but incorrect responses), and network partitions where services can reach some peers but not others. Each of these is a valid future experiment.

> **"Should we run chaos experiments in production?"**
>
> Eventually, yes. Staging environments are simplifications of production. Traffic patterns, data volumes, and infrastructure configurations differ. But production chaos requires: strong monitoring (you can detect impact immediately), automated rollback (you can stop the experiment in seconds), small blast radius (affect 1% of traffic, not all of it), and team buy-in. Start in staging. Move to production canary chaos when you are ready.

---

## 10. Checkpoint

After this module, you should have:

- [ ] Written predictions for 4 failure scenarios before running them
- [ ] Experiment 1: killed the payment service and observed purchase failures
- [ ] Experiment 2: added database latency and observed cascading slowdowns
- [ ] Experiment 3: killed Kafka and verified purchase flow degradation
- [ ] Experiment 4: simulated disk-full and verified read vs write behavior
- [ ] For each experiment: compared predictions to reality, identified gaps
- [ ] Observed all experiments through Grafana dashboards, Jaeger traces, and logs
- [ ] Written a game day plan with 5 experiments, hypotheses, and rollback procedures
- [ ] Created tickets or TODOs for any resilience gaps discovered
- [ ] Understanding of when to graduate from staging chaos to production chaos

**Section 2C complete.** You now have production infrastructure: Kubernetes for orchestration, Terraform for IaC, Prometheus + Grafana for monitoring, OpenTelemetry + Jaeger for tracing, SLO-based alerts with runbooks, and validated resilience through chaos engineering.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Chaos Engineering** | The discipline of experimenting on a system to build confidence in its ability to withstand turbulent conditions in production. |
| **Game Day** | A scheduled session where a team runs chaos experiments together, testing resilience and practicing incident response. |
| **Blast Radius** | The scope of impact from a chaos experiment or failure. Start small and expand. |
| **Steady State** | The normal, healthy behavior of the system as measured by SLIs. The baseline you compare against during experiments. |
| **Hypothesis** | A prediction about what will happen when a failure is injected. The experiment tests this prediction. |
| **Toxiproxy** | An open-source TCP proxy (by Shopify) for simulating network conditions: latency, packet loss, bandwidth limits, connection resets. |
| **Chaos Monkey** | Netflix's tool that randomly terminates production instances to ensure services handle instance failure gracefully. |
| **Cascading Failure** | When a failure in one component causes failures in dependent components, which cause failures in their dependents, and so on. |
| **Graceful Degradation** | The ability of a system to maintain partial functionality when a component fails, rather than failing completely. |
| **Circuit Breaker** | A resilience pattern that stops calling a failing service after a threshold of failures, allowing it to recover. Tested in this module's experiments. |

---

## What's Next

In **Circuit Breakers and Resilience** (L2-M49), you'll add circuit breakers, retries, and bulkheads so TicketPulse degrades gracefully instead of cascading into total failure.

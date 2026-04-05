# L2-M46: Distributed Tracing -- OpenTelemetry

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M45
>
> **Source:** Chapters 4, 18 of the 100x Engineer Guide

## What You'll Learn

- Why metrics alone are insufficient for debugging microservices
- How distributed tracing works: traces, spans, context propagation
- Adding OpenTelemetry instrumentation to TicketPulse services
- Auto-instrumentation for HTTP, database, and Kafka operations
- Manual spans for business logic with custom attributes
- Reading trace waterfalls in Jaeger to identify bottlenecks
- Finding the slow service in a multi-service request chain
- Adding span attributes for production debugging

## Why This Matters

A user reports: "Buying a ticket takes 5 seconds." You check the Prometheus dashboard from L2-M45 -- the API gateway p99 is 800ms, the event service p99 is 50ms, the payment service p99 is 300ms. None of them individually explain 5 seconds. Where is the time going?

The answer: between services. Network latency, serialization, queue wait times, retries -- none of these show up in per-service metrics. Distributed tracing follows a single request across every service it touches, measuring time at every step. By the end of this module, you will see a full trace waterfall for a TicketPulse purchase -- every service, every database query, every Kafka message -- and you will be able to pinpoint exactly where the 5 seconds went.

## Prereq Check

You need the TicketPulse services running with Prometheus and Grafana from L2-M45.

```bash
# Verify services are running
docker compose ps
# Should show api-gateway, event-service, payment-service, prometheus, grafana
```

---

## 1. The Problem: Logs Lie About Latency

Here is what each service logs for a ticket purchase:

```
[api-gateway]     POST /api/purchases - completed in 45ms
[event-service]   check-availability - completed in 12ms
[payment-service] process-payment - completed in 280ms
[notification]    send-confirmation - completed in 8ms
```

Total from the logs: 45 + 12 + 280 + 8 = 345ms. But the user experienced 5 seconds.

The logs are not wrong -- each service measured its own processing time accurately. But they do not account for:
- Network latency between services (especially if services are in different availability zones)
- Serialization/deserialization overhead
- Queue wait time in Kafka (the notification consumer might process it 2 seconds later)
- Retry attempts that succeeded on the second try
- Connection pool wait time at the database

Distributed tracing captures ALL of this. Every millisecond is accounted for.

---

## 2. Deploy: Jaeger for Trace Visualization

Jaeger is an open-source distributed tracing backend, originally built by Uber. It collects, stores, and visualizes traces.

Add Jaeger to your `docker-compose.yml`:

```yaml
  jaeger:
    image: jaegertracing/all-in-one:1.55
    ports:
      - "16686:16686"    # Jaeger UI
      - "4318:4318"      # OTLP HTTP receiver (OpenTelemetry)
      - "4317:4317"      # OTLP gRPC receiver (OpenTelemetry)
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    restart: unless-stopped
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```bash
docker compose up -d jaeger
```

Open http://localhost:16686 in your browser. You should see the Jaeger UI with a service dropdown. It will be empty until we start sending traces.

---

## 3. Build: Add OpenTelemetry Instrumentation

OpenTelemetry (OTel) is the vendor-neutral standard for traces, metrics, and logs. It works with Jaeger, Zipkin, Datadog, Honeycomb, Grafana Tempo, and any other backend that speaks OTLP.

Install the OpenTelemetry packages:

```bash
npm install @opentelemetry/sdk-node \
  @opentelemetry/api \
  @opentelemetry/auto-instrumentations-node \
  @opentelemetry/exporter-trace-otlp-http \
  @opentelemetry/resources \
  @opentelemetry/semantic-conventions
```

### 3a. The Tracing Setup File

Create the tracing configuration. This MUST be loaded before any other code in your application.

```typescript
// src/tracing.ts

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { Resource } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_DEPLOYMENT_ENVIRONMENT_NAME,
} from '@opentelemetry/semantic-conventions';

const serviceName = process.env.OTEL_SERVICE_NAME || 'api-gateway';

const sdk = new NodeSDK({
  resource: new Resource({
    [ATTR_SERVICE_NAME]: serviceName,
    [ATTR_SERVICE_VERSION]: process.env.APP_VERSION || '1.0.0',
    [ATTR_DEPLOYMENT_ENVIRONMENT_NAME]: process.env.NODE_ENV || 'development',
  }),

  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://jaeger:4318/v1/traces',
  }),

  instrumentations: [
    getNodeAutoInstrumentations({
      // Auto-instrument these libraries:
      '@opentelemetry/instrumentation-http': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-express': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-pg': {
        enabled: true,           // PostgreSQL queries
        enhancedDatabaseReporting: true,
      },
      '@opentelemetry/instrumentation-redis': {
        enabled: true,           // Redis commands
      },
      '@opentelemetry/instrumentation-kafkajs': {
        enabled: true,           // Kafka produce/consume
      },
      // Disable noisy instrumentations
      '@opentelemetry/instrumentation-fs': {
        enabled: false,          // Filesystem operations (too noisy)
      },
      '@opentelemetry/instrumentation-dns': {
        enabled: false,          // DNS lookups (too noisy)
      },
    }),
  ],
});

sdk.start();
console.log(`[tracing] OpenTelemetry initialized for service: ${serviceName}`);

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('[tracing] OpenTelemetry shut down'))
    .catch((err) => console.error('[tracing] Error shutting down', err));
});
```

### 3b. Load Tracing Before Everything Else

The tracing setup must run before Express, before database connections, before anything. Modify your entry point:

```typescript
// src/server.ts

// THIS MUST BE THE FIRST IMPORT
import './tracing';

// Now import everything else
import { app } from './app';
import { pool } from './db';
// ...
```

Or use the Node.js `--require` flag:

```bash
node --require ./dist/tracing.js dist/server.js
```

### 3c. Update docker-compose.yml

Add environment variables for each service:

```yaml
  app:
    # ... existing config ...
    environment:
      - OTEL_SERVICE_NAME=api-gateway
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces
      # ... other env vars ...

  event-service:
    # ... existing config ...
    environment:
      - OTEL_SERVICE_NAME=event-service
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces

  payment-service:
    # ... existing config ...
    environment:
      - OTEL_SERVICE_NAME=payment-service
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces
```

Rebuild and restart:

```bash
docker compose up -d --build
```

---

## 4. Build: Manual Spans for Business Logic

Auto-instrumentation captures HTTP requests, database queries, and Kafka messages. But it does not know about your business logic. You need manual spans for operations like "validate-ticket," "check-availability," and "process-payment."

```typescript
// src/services/purchase.ts

import { trace, SpanStatusCode, context } from '@opentelemetry/api';

// Get a tracer for this module
const tracer = trace.getTracer('ticketpulse-purchase');

export async function purchaseTicket(userId: string, eventId: string, ticketType: string) {
  // Create a span that wraps the entire purchase flow
  return tracer.startActiveSpan('purchase-ticket', async (purchaseSpan) => {
    try {
      // Add attributes for debugging
      purchaseSpan.setAttribute('user.id', userId);
      purchaseSpan.setAttribute('event.id', eventId);
      purchaseSpan.setAttribute('ticket.type', ticketType);

      // Step 1: Validate the ticket request
      const ticket = await tracer.startActiveSpan('validate-ticket', async (span) => {
        try {
          const result = await validateTicketRequest(eventId, ticketType);
          span.setAttribute('ticket.id', result.ticketId);
          span.setAttribute('ticket.price_cents', result.priceCents);
          span.setStatus({ code: SpanStatusCode.OK });
          return result;
        } catch (error) {
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: (error as Error).message,
          });
          span.recordException(error as Error);
          throw error;
        } finally {
          span.end();
        }
      });

      // Step 2: Check availability
      const available = await tracer.startActiveSpan('check-availability', async (span) => {
        try {
          span.setAttribute('event.id', eventId);
          const result = await checkAvailability(eventId, ticketType);
          span.setAttribute('available_count', result.availableCount);
          span.setStatus({ code: SpanStatusCode.OK });
          return result;
        } catch (error) {
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: (error as Error).message,
          });
          span.recordException(error as Error);
          throw error;
        } finally {
          span.end();
        }
      });

      // Step 3: Process payment
      const payment = await tracer.startActiveSpan('process-payment', async (span) => {
        try {
          span.setAttribute('payment.amount_cents', ticket.priceCents);
          span.setAttribute('payment.method', 'stripe');
          const result = await processPayment(userId, ticket.priceCents);
          span.setAttribute('payment.id', result.paymentId);
          span.setAttribute('payment.status', result.status);
          span.setStatus({ code: SpanStatusCode.OK });
          return result;
        } catch (error) {
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: (error as Error).message,
          });
          span.recordException(error as Error);
          throw error;
        } finally {
          span.end();
        }
      });

      // Step 4: Confirm purchase (update database)
      await tracer.startActiveSpan('confirm-purchase', async (span) => {
        try {
          await confirmPurchase(ticket.ticketId, payment.paymentId, userId);
          span.setStatus({ code: SpanStatusCode.OK });
        } catch (error) {
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: (error as Error).message,
          });
          span.recordException(error as Error);
          throw error;
        } finally {
          span.end();
        }
      });

      // Step 5: Publish event to Kafka (async -- not in critical path)
      await tracer.startActiveSpan('publish-purchase-event', async (span) => {
        try {
          span.setAttribute('kafka.topic', 'ticket-purchases');
          await publishPurchaseEvent(ticket.ticketId, userId, eventId);
          span.setStatus({ code: SpanStatusCode.OK });
        } catch (error) {
          // Non-critical -- log but don't fail the purchase
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: (error as Error).message,
          });
          span.recordException(error as Error);
          console.error('Failed to publish purchase event:', error);
        } finally {
          span.end();
        }
      });

      purchaseSpan.setStatus({ code: SpanStatusCode.OK });
      return { success: true, ticketId: ticket.ticketId, paymentId: payment.paymentId };

    } catch (error) {
      purchaseSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: (error as Error).message,
      });
      purchaseSpan.recordException(error as Error);
      throw error;
    } finally {
      purchaseSpan.end();
    }
  });
}
```

### Context Propagation

When the API gateway calls the event service over HTTP, the trace ID must travel with the request. OpenTelemetry auto-instrumentation handles this for HTTP calls by injecting W3C TraceContext headers:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

This header contains:
- `4bf92f3577b34da6a3ce929d0e0e4736` -- the trace ID (same for all spans in the request)
- `00f067aa0ba902b7` -- the parent span ID
- `01` -- the trace flags (sampled)

The receiving service reads this header and creates child spans under the same trace. You do not need to write any propagation code -- the HTTP auto-instrumentation does it.

For Kafka, the auto-instrumentation injects trace context into Kafka message headers. The consumer side extracts it and links the consumer span to the producer span.

---

> **Before you continue:** A ticket purchase involves the API gateway, event service, payment service, and Kafka. Where do you predict the most time will be spent in the trace waterfall? Write down your guess before finding the trace.

## 5. Try It: Buy a Ticket and Find the Trace

Make a purchase request:

```bash
# Create an event first
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Trace Test Concert",
    "venue": "Debug Arena",
    "date": "2026-12-15T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 7500
  }' | jq .

# Buy a ticket (adjust the event ID from the response above)
curl -s -X POST http://localhost:3000/api/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "eventId": "1",
    "ticketType": "general"
  }' | jq .
```

Now open Jaeger: http://localhost:16686

1. Select "api-gateway" from the Service dropdown
2. Click "Find Traces"
3. Find the `POST /api/purchases` trace
4. Click on it

---

## 6. Observe: Reading the Trace Waterfall

You should see a waterfall diagram like this:

```
api-gateway: POST /api/purchases                         [==========================] 850ms
  api-gateway: purchase-ticket                            [========================] 820ms
    api-gateway: validate-ticket                          [==]   15ms
      pg: SELECT                                          [=]    8ms
    event-service: POST /internal/check-availability      [===]  45ms
      event-service: check-availability                   [==]   35ms
        pg: SELECT ... FOR UPDATE                         [=]    12ms
    payment-service: POST /internal/process-payment       [===============]         380ms
      payment-service: process-payment                    [=============]           350ms
        HTTP: POST https://api.stripe.com/v1/charges      [===========]            310ms
    api-gateway: confirm-purchase                         [==]   20ms
      pg: UPDATE                                          [=]    10ms
      pg: INSERT                                          [=]    6ms
    api-gateway: publish-purchase-event                   [=]    5ms
      kafka: produce ticket-purchases                     [=]    3ms
```

Read this waterfall:

1. **Total time: 850ms.** The client waited 850ms for the response.
2. **validate-ticket: 15ms.** A quick database lookup. Not the bottleneck.
3. **check-availability: 45ms.** The event service checked availability with a `SELECT ... FOR UPDATE`. Reasonable.
4. **process-payment: 380ms.** The payment service took 380ms, and 310ms of that was the external Stripe API call. **This is the bottleneck.** The payment provider's API latency dominates the request.
5. **confirm-purchase: 20ms.** Database writes to record the purchase.
6. **publish-purchase-event: 5ms.** Publishing to Kafka is fast and non-blocking.

**Gap analysis:** 15 + 45 + 380 + 20 + 5 = 465ms in spans. The trace shows 850ms total. Where is the remaining 385ms? Look for gaps between spans in the waterfall -- these are network latency, serialization, and connection pool wait times.

---

## 7. Debug: Add an Artificial Delay

Let us make the bottleneck obvious:

```typescript
// In the payment service, add a delay
// payment-service/src/routes/process-payment.ts

export async function processPayment(req: Request, res: Response) {
  // TEMPORARY: artificial delay for tracing demo
  await new Promise((resolve) => setTimeout(resolve, 500));

  // ... rest of payment processing ...
}
```

Rebuild, buy another ticket, and look at the trace:

```
payment-service: POST /internal/process-payment    [============================] 880ms
  payment-service: process-payment                  [==========================] 860ms
    <500ms gap -- the artificial delay>
    HTTP: POST https://api.stripe.com/v1/charges    [===========]              310ms
```

The 500ms delay is visible as a gap between the span start and the first child span. If you see unexplained gaps in production traces, investigate: it could be a slow mutex, a connection pool wait, or a missing `await` that serialized something unnecessarily.

Remove the artificial delay after observing.

---

## 8. Span Attributes for Production Debugging

Attributes are key-value pairs attached to spans. They turn a generic "POST /api/purchases" into a searchable, debuggable record.

Add attributes that help you debug in production:

```typescript
// Good attributes for a purchase span
span.setAttribute('user.id', userId);
span.setAttribute('event.id', eventId);
span.setAttribute('ticket.type', ticketType);
span.setAttribute('ticket.price_cents', 7500);
span.setAttribute('payment.method', 'stripe');
span.setAttribute('payment.id', 'pi_3abc123');

// These let you search in Jaeger:
// "Show me all traces where event.id = 42"
// "Show me all traces where payment.method = stripe and duration > 1s"
```

Do NOT add high-cardinality or sensitive attributes:

```typescript
// BAD -- do not add these
span.setAttribute('user.email', 'john@example.com');   // PII
span.setAttribute('request.body', JSON.stringify(body)); // Too large
span.setAttribute('credit_card', '4242...');            // Sensitive
```

---

## 9. Connecting Traces to Metrics and Logs

The three pillars of observability work together:

**Metrics → Traces:** Your Grafana dashboard shows p99 latency spiked to 3s at 14:32. Search Jaeger for traces in that time window with duration > 2s. You find 5 traces where the payment service is slow.

**Traces → Logs:** A trace shows a span with `SpanStatusCode.ERROR` and the attribute `error.message = "connection refused"`. Search your logs for that trace ID to find the full error stack trace.

**Logs → Traces:** A log line says `[ERROR] purchase failed: timeout`. The log includes a trace ID (if you add it to your logger). Paste the trace ID into Jaeger to see the full request path.

Add the trace ID to your logger:

```typescript
// src/middleware/logging.ts

import { trace, context } from '@opentelemetry/api';

export function getTraceId(): string {
  const span = trace.getSpan(context.active());
  if (!span) return 'no-trace';
  return span.spanContext().traceId;
}

// In your request logger:
console.log(JSON.stringify({
  timestamp: new Date().toISOString(),
  level: 'info',
  message: 'Purchase completed',
  traceId: getTraceId(),      // Links this log to the trace
  userId,
  eventId,
  duration: endTime - startTime,
}));
```

Now every log line carries a trace ID. When debugging, grep for the trace ID to find all logs from all services for that single request.

---

## 10. Insight: The Origin of Distributed Tracing

Google published the Dapper paper in 2010, describing their production tracing system. Key ideas:

- **Every request gets a trace ID.** Propagated through all service calls.
- **Sampling:** Dapper traced 1 in 1000 requests in production. Even at 0.1%, the volume was enough for debugging. Modern systems often use adaptive sampling or tail-based sampling (keep traces that are slow or errored).
- **Low overhead:** Dapper added less than 0.01% latency overhead.
- **Always-on:** Tracing was not something you turned on for debugging. It ran continuously.

Twitter open-sourced Zipkin (2012) based on the Dapper paper. Uber built Jaeger (2017). Today, OpenTelemetry unifies them all into a single vendor-neutral standard.

---

## 11. Reflect

> **What did you notice?** When you found the trace waterfall for a ticket purchase, where did the time actually go? Was it where you expected, or did the gaps between spans reveal something surprising?

> **"Auto-instrumentation captured HTTP requests, database queries, and Kafka messages. What does it NOT capture?"**
>
> Business logic, in-memory computations, conditional branches, cache lookups that do not use an instrumented library, and external API calls to non-instrumented clients. Anything that happens inside your code without crossing an instrumented boundary needs a manual span.

> **"We trace every request. At 10,000 requests per second, that is 10,000 traces per second. Is that sustainable?"**
>
> No. In production, you use sampling. Head-based sampling (decide at the start: trace 10% of requests) or tail-based sampling (collect all traces, then keep only slow/errored ones). The OpenTelemetry SDK supports both. Start with 10% random sampling and 100% error sampling.

> **"The payment service calls Stripe's API, which takes 310ms. Is that a problem we can fix?"**
>
> You cannot make Stripe faster. But you can: (1) set a timeout so a slow Stripe call does not block forever, (2) add a circuit breaker so repeated Stripe failures fail fast instead of accumulating, (3) consider async payment processing for non-critical flows, (4) cache Stripe responses where appropriate. The trace told you where the time goes -- the fix is an engineering decision.

---

## 12. Checkpoint

After this module, you should have:

- [ ] Jaeger running and accessible at http://localhost:16686
- [ ] OpenTelemetry SDK initialized in all TicketPulse services
- [ ] Auto-instrumentation for HTTP, PostgreSQL, Redis, and Kafka
- [ ] Manual spans for business logic: validate, check-availability, process-payment, confirm
- [ ] Context propagation working across services (W3C TraceContext headers)
- [ ] You have found a purchase trace in Jaeger and read the waterfall
- [ ] You identified the payment service / Stripe call as the latency bottleneck
- [ ] You injected a delay and found it in the trace
- [ ] Span attributes for debugging: user_id, event_id, ticket_type, payment_id
- [ ] Trace IDs in your application logs for cross-referencing
- [ ] Understanding of sampling strategies for production use

**Next up:** L2-M47 where we turn metrics and traces into actionable alerts with on-call practices.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Distributed Trace** | A record of a request's journey through all services it touches, represented as a tree of spans sharing a trace ID. |
| **Span** | A single unit of work within a trace. Has a start time, duration, status, and optional attributes and events. |
| **Trace ID** | A globally unique identifier shared by all spans in a single request's trace. Used to correlate data across services. |
| **Parent Span** | The span that initiated a child span. Creates the tree structure of a trace. |
| **Context Propagation** | Passing trace context (trace ID, span ID) between services, typically via HTTP headers (W3C TraceContext). |
| **OpenTelemetry (OTel)** | A vendor-neutral observability framework providing APIs, SDKs, and tools for traces, metrics, and logs. |
| **Auto-Instrumentation** | Automatically creating spans for known libraries (HTTP, database, message queue) without manual code changes. |
| **Jaeger** | An open-source distributed tracing platform, originally built by Uber. Collects, stores, and visualizes traces. |
| **OTLP** | OpenTelemetry Protocol. The standard wire format for sending telemetry data to backends. |
| **Sampling** | Reducing the volume of traces collected. Head-based (decide upfront) or tail-based (decide after collecting). |
| **Waterfall** | A visualization showing spans as horizontal bars on a timeline, revealing the time spent in each operation. |
| **Dapper** | Google's internal distributed tracing system (2010). The conceptual ancestor of Zipkin, Jaeger, and OpenTelemetry. |

---

## What's Next

In **Alerting and On-Call** (L2-M47), you'll turn your monitoring data into actionable alerts and build an on-call rotation that does not burn out the team.

# L1-M25: Logging & Observability 101

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M24 (Secrets Management)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

Open TicketPulse's code right now and search for logging:

```bash
grep -rn "console.log\|console.error" src/ --include="*.ts"
```

You will find lines like:

```typescript
console.log('Event created');
console.log('Error:', err);
console.log('Ticket purchased for user', userId);
```

This is useless in production. Why?

1. **No timestamps.** When did the error happen?
2. **No log levels.** Is this informational or a critical error? You cannot filter.
3. **No request context.** Which user? Which request? If 100 requests are happening simultaneously, these logs are an unreadable jumble.
4. **No structure.** You cannot parse `console.log('Error:', err)` programmatically. Good luck piping that to a log aggregator.

By the end of this module, TicketPulse will have structured JSON logs with timestamps, levels, request IDs, and metadata. You will be able to trace a single request's journey from entry to exit across all log lines.

**You will see structured logs within the first three minutes.**

---

## 0. Quick Start (3 minutes)

Let us see what the current logging looks like. Start TicketPulse and make a few requests:

```bash
cd ticketpulse
docker compose up -d

# Make some requests
curl -s http://localhost:3000/api/events | jq '.data | length'
curl -s http://localhost:3000/api/health | jq .
curl -s -X POST http://localhost:3000/api/events/999/tickets \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}' 2>/dev/null
```

Check the logs:

```bash
docker compose logs app --tail 20
```

What you will see is a mess of unstructured text. Try to answer: "Which log line came from which request?" You cannot. That is the problem we are solving.

---

## 1. Build: Structured JSON Logger

### 1.1 Create the Logger Module

We are not installing a logging library yet -- we are building a minimal structured logger to understand what "structured logging" actually means. In production, you would use pino or winston. For learning, we build it from scratch.

```typescript
// src/utils/logger.ts

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  service: string;
  requestId?: string;
  [key: string]: unknown;  // Allow arbitrary metadata
}

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

// Read minimum log level from environment (default: 'info' in production, 'debug' in dev)
const MIN_LEVEL: LogLevel = (process.env.LOG_LEVEL as LogLevel) ||
  (process.env.NODE_ENV === 'production' ? 'info' : 'debug');

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[MIN_LEVEL];
}

function formatEntry(entry: LogEntry): string {
  return JSON.stringify(entry);
}

function log(level: LogLevel, message: string, metadata: Record<string, unknown> = {}) {
  if (!shouldLog(level)) return;

  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    service: 'ticketpulse',
    ...metadata,
  };

  const output = formatEntry(entry);

  if (level === 'error') {
    process.stderr.write(output + '\n');
  } else {
    process.stdout.write(output + '\n');
  }
}

export const logger = {
  debug: (message: string, metadata?: Record<string, unknown>) => log('debug', message, metadata),
  info: (message: string, metadata?: Record<string, unknown>) => log('info', message, metadata),
  warn: (message: string, metadata?: Record<string, unknown>) => log('warn', message, metadata),
  error: (message: string, metadata?: Record<string, unknown>) => log('error', message, metadata),
};
```

### 1.2 Replace console.log Throughout the Codebase

Before:

```typescript
console.log('Event created');
console.log('Error:', err);
```

After:

```typescript
import { logger } from '../utils/logger';

logger.info('Event created', { eventId: event.id, title: event.title });
logger.error('Failed to create event', { error: err.message, stack: err.stack });
```

The difference is not cosmetic. The JSON format means every log line is machine-parseable. You can filter, search, aggregate, and alert on any field.

### 1.3 See It in Action

Restart the server and make a request:

```bash
npm run dev
```

```bash
curl -s http://localhost:3000/api/events | jq '.data | length'
```

Check the server output. You should see:

```json
{"timestamp":"2026-03-24T10:30:00.123Z","level":"info","message":"Request received","service":"ticketpulse","method":"GET","path":"/api/events"}
{"timestamp":"2026-03-24T10:30:00.145Z","level":"debug","message":"Database query completed","service":"ticketpulse","query":"SELECT * FROM events","rows":12,"durationMs":22}
{"timestamp":"2026-03-24T10:30:00.146Z","level":"info","message":"Request completed","service":"ticketpulse","method":"GET","path":"/api/events","statusCode":200,"durationMs":23}
```

Every line is valid JSON. Every line has a timestamp. Every line tells you what happened.

---

## 2. Build: Request ID Middleware

Right now, if 50 requests arrive simultaneously, the log lines are interleaved. You cannot tell which log line belongs to which request.

The fix: generate a unique ID for every request and attach it to every log line for that request.

### 2.1 Generate Request IDs

```typescript
// src/middleware/request-id.ts

import { randomUUID } from 'crypto';
import { Request, Response, NextFunction } from 'express';
import { AsyncLocalStorage } from 'async_hooks';

// AsyncLocalStorage lets us store per-request state without threading it through every function call.
// Think of it as "thread-local storage" for Node.js async operations.
export const requestContext = new AsyncLocalStorage<{ requestId: string }>();

export function requestIdMiddleware(req: Request, res: Response, next: NextFunction) {
  // Use the client-provided request ID if present (for tracing across services),
  // otherwise generate a new one.
  const requestId = (req.headers['x-request-id'] as string) || randomUUID();

  // Set the response header so the client can reference it
  res.setHeader('x-request-id', requestId);

  // Store in async-local storage so any code in this request's call chain can access it
  requestContext.run({ requestId }, () => {
    next();
  });
}

// Helper: get the current request ID from anywhere in the call chain
export function getRequestId(): string | undefined {
  return requestContext.getStore()?.requestId;
}
```

### 2.2 Update the Logger to Include Request ID

```typescript
// src/utils/logger.ts -- updated

import { getRequestId } from '../middleware/request-id';

function log(level: LogLevel, message: string, metadata: Record<string, unknown> = {}) {
  if (!shouldLog(level)) return;

  const requestId = getRequestId();

  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    service: 'ticketpulse',
    ...(requestId && { requestId }),  // Only include if available
    ...metadata,
  };

  const output = formatEntry(entry);

  if (level === 'error') {
    process.stderr.write(output + '\n');
  } else {
    process.stdout.write(output + '\n');
  }
}
```

### 2.3 Add Request Logging Middleware

```typescript
// src/middleware/request-logger.ts

import { Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';

export function requestLogger(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();

  logger.info('Request received', {
    method: req.method,
    path: req.path,
    query: Object.keys(req.query).length > 0 ? req.query : undefined,
    userAgent: req.headers['user-agent'],
    ip: req.ip,
  });

  // Capture when the response finishes
  res.on('finish', () => {
    const durationMs = Date.now() - start;
    const logFn = res.statusCode >= 500 ? logger.error
                : res.statusCode >= 400 ? logger.warn
                : logger.info;

    logFn('Request completed', {
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      durationMs,
    });
  });

  next();
}
```

### 2.4 Wire It Up

```typescript
// src/index.ts

import { requestIdMiddleware } from './middleware/request-id';
import { requestLogger } from './middleware/request-logger';

const app = express();

// Request ID must come FIRST -- everything else depends on it
app.use(requestIdMiddleware);
app.use(requestLogger);

// ... rest of your middleware and routes
```

---

## 3. Try It: Trace a Request

Make 5 API calls:

```bash
for i in {1..5}; do
  curl -s http://localhost:3000/api/events > /dev/null &
done
wait
```

Now look at the logs. Every line has a `requestId`:

```json
{"timestamp":"2026-03-24T10:31:00.100Z","level":"info","message":"Request received","service":"ticketpulse","requestId":"a1b2c3d4-...","method":"GET","path":"/api/events"}
{"timestamp":"2026-03-24T10:31:00.101Z","level":"info","message":"Request received","service":"ticketpulse","requestId":"e5f6a7b8-...","method":"GET","path":"/api/events"}
{"timestamp":"2026-03-24T10:31:00.115Z","level":"debug","message":"Database query completed","service":"ticketpulse","requestId":"a1b2c3d4-...","rows":12,"durationMs":15}
```

Filter logs for a single request:

```bash
# Pipe server output to a log file
npm run dev 2>&1 | tee logs.jsonl &

# Make a request and capture the request ID
REQUEST_ID=$(curl -sI http://localhost:3000/api/events | grep -i x-request-id | awk '{print $2}' | tr -d '\r')
echo "Request ID: $REQUEST_ID"

# Filter all log lines for this one request
grep "$REQUEST_ID" logs.jsonl | jq .
```

You should see the complete journey of that single request:

```
1. Request received  (GET /api/events)
2. Database query completed  (12 rows, 15ms)
3. Cache miss  (events not in Redis)
4. Request completed  (200, 23ms)
```

> **Reflect:** A TicketPulse purchase fails for one user out of thousands. With `console.log`, you would be scrolling through thousands of interleaved log lines trying to find the relevant ones. With request IDs, you grep for the ID from the user's error response and see exactly what happened, step by step.

---

## 4. Log Levels: When to Use Each

| Level | When to Use | Example |
|---|---|---|
| **DEBUG** | Detailed internal state, useful during development. Noisy. | `Database query: SELECT * FROM events WHERE id = 42` |
| **INFO** | Normal operations worth recording. The "heartbeat." | `Request completed: GET /api/events 200 23ms` |
| **WARN** | Something unexpected but not broken. Needs attention soon. | `Cache miss for hot key: events:popular (falling back to DB)` |
| **ERROR** | Something failed. Needs investigation. | `Failed to process ticket purchase: connection refused` |

Rules of thumb:
- **DEBUG** is off in production (too noisy, too much data). Turn it on temporarily when debugging a specific issue.
- **INFO** is your default production level. You should be able to reconstruct what happened from INFO logs alone.
- **WARN** means "this is not broken yet, but it will be if you do not fix it." Treat warnings as future errors.
- **ERROR** means "something is broken right now." Every ERROR log should be actionable.

### 4.1 Add Log Levels to TicketPulse

```typescript
// In your route handlers and services:

// DEBUG: internal details
logger.debug('Checking ticket availability', {
  eventId,
  requestedQuantity: quantity,
  currentAvailable: available,
});

// INFO: normal business operations
logger.info('Ticket purchased', {
  eventId,
  userId,
  quantity,
  totalInCents: pricing.totalInCents,
});

// WARN: something to keep an eye on
logger.warn('Low ticket inventory', {
  eventId,
  remainingTickets: available,
  threshold: 10,
});

// ERROR: something broke
logger.error('Purchase failed', {
  eventId,
  userId,
  error: err.message,
  stack: err.stack,
});
```

---

## 5. Observe: jq for Log Analysis

`jq` is the Swiss Army knife for JSON logs. Here are the most useful pipelines:

```bash
# Pretty-print all logs
cat logs.jsonl | jq .

# Show only errors
cat logs.jsonl | jq 'select(.level == "error")'

# Show only slow requests (>100ms)
cat logs.jsonl | jq 'select(.durationMs > 100)'

# Count log lines by level
cat logs.jsonl | jq -r '.level' | sort | uniq -c | sort -rn
#   847 info
#   123 debug
#    15 warn
#     3 error

# Find the slowest requests
cat logs.jsonl | jq 'select(.message == "Request completed")' | \
  jq -s 'sort_by(-.durationMs) | .[0:5]'

# Show all errors with their request IDs
cat logs.jsonl | jq 'select(.level == "error") | {requestId, message, error}'

# Count requests per path
cat logs.jsonl | jq -r 'select(.message == "Request received") | .path' | \
  sort | uniq -c | sort -rn
```

> **Try It:** pipe your TicketPulse logs through each of these commands. Get comfortable with `jq` -- you will use it constantly when debugging production issues.

---

## 6. Build: Developer Log Viewer (Dev Only)

For convenience during development, add an endpoint that shows recent logs:

```typescript
// src/routes/debug.ts

import { Router } from 'express';
import { env } from '../config/environment';

const router = Router();

// In-memory ring buffer for recent logs (dev only)
const LOG_BUFFER_SIZE = 500;
const logBuffer: object[] = [];

export function addToLogBuffer(entry: object) {
  logBuffer.push(entry);
  if (logBuffer.length > LOG_BUFFER_SIZE) {
    logBuffer.shift();  // Remove oldest
  }
}

// Only register in development
if (env.NODE_ENV === 'development') {
  router.get('/api/debug/logs', (req, res) => {
    const { level, requestId, limit = '50' } = req.query;

    let filtered = [...logBuffer];

    if (level && typeof level === 'string') {
      filtered = filtered.filter((entry: any) => entry.level === level);
    }

    if (requestId && typeof requestId === 'string') {
      filtered = filtered.filter((entry: any) => entry.requestId === requestId);
    }

    const limitNum = Math.min(parseInt(limit as string, 10) || 50, 500);
    filtered = filtered.slice(-limitNum);

    res.json({
      total: logBuffer.length,
      filtered: filtered.length,
      logs: filtered,
    });
  });
}

export default router;
```

Use it:

```bash
# Get the last 20 logs
curl -s http://localhost:3000/api/debug/logs?limit=20 | jq '.logs[] | {level, message, requestId}'

# Get only error logs
curl -s http://localhost:3000/api/debug/logs?level=error | jq .

# Get logs for a specific request
curl -s "http://localhost:3000/api/debug/logs?requestId=a1b2c3d4-..." | jq .
```

> **Important:** This endpoint must NEVER exist in production. The `if (env.NODE_ENV === 'development')` guard ensures it is only registered in dev. In production, use a proper log aggregation service (Datadog, Grafana Loki, AWS CloudWatch).

---

## 7. What NOT to Log

Never log:
- **Passwords** (even hashed ones in most cases)
- **Full credit card numbers** (log last 4 digits at most)
- **JWT tokens** (log that a token was present, not the token itself)
- **API keys** (log that authentication succeeded, not the key)
- **PII at DEBUG level** (email addresses, phone numbers -- unless you have explicit consent and proper data retention)
- **Full request bodies for sensitive endpoints** (login, payment)

```typescript
// BAD -- logs the password
logger.info('Login attempt', { email: req.body.email, password: req.body.password });

// GOOD -- logs only what you need to debug
logger.info('Login attempt', { email: req.body.email, success: true });

// BAD -- logs the full token
logger.debug('Auth header', { authorization: req.headers.authorization });

// GOOD -- logs that auth was present
logger.debug('Auth header present', { hasToken: !!req.headers.authorization });
```

---

## 8. Checkpoint

Before continuing to the next module, verify:

- [ ] All `console.log` calls are replaced with structured logger calls
- [ ] Every log line is valid JSON with timestamp, level, service, and message
- [ ] Request ID middleware generates a UUID for every request
- [ ] The request ID appears in the `x-request-id` response header
- [ ] You can grep logs by request ID and see a full request trace
- [ ] You can use `jq` to filter logs by level, path, or duration
- [ ] The debug log endpoint works in development and does not exist in production
- [ ] Sensitive data (passwords, tokens) is not logged

```bash
# Quick verification: make a request, get the ID, trace it
REQUEST_ID=$(curl -sI http://localhost:3000/api/events | grep -i x-request-id | awk '{print $2}' | tr -d '\r')
curl -s "http://localhost:3000/api/debug/logs?requestId=$REQUEST_ID" | jq '.logs[] | {level, message, durationMs}'
```

> **Reflect:** "A TicketPulse purchase fails for one user. With our current logging, how would you debug it?" Answer: get the request ID from the error response, grep the logs, and see exactly where the failure happened -- which database query, which validation, which external service call. That is the power of structured, request-scoped logging.

---

## What's Next

TicketPulse now has proper logging. But what does "reliable" actually mean? How much downtime is acceptable? The next module introduces SLOs and error budgets -- the framework for defining and measuring reliability.

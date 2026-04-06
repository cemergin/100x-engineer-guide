# L1-M12: Error Handling That Doesn't Suck

> **Loop 1 (Foundation)** | Section 1C: Building the API | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M11 (REST API Design)
>
> **Source:** Chapters 25, 5, 7, 8 of the 100x Engineer Guide

---

## The Problem

Right now, TicketPulse's error handling is a mess. Some endpoints return `{ error: "Something went wrong" }`. Others return raw database errors. One endpoint leaks a full stack trace to the client. And when validation fails, it only reports the first problem -- forcing developers to fix and resubmit over and over.

We are going to fix all of that.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Start TicketPulse and send a request that will break:

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

What do you get back? Probably something like:

```json
{
  "error": {
    "code": "MISSING_FIELDS",
    "message": "Required fields: title, venue, date, totalTickets, priceInCents"
  }
}
```

That is better than nothing, but it is not good enough. The developer has to guess which fields are missing. And there is no request ID to trace this error in the logs. Let us build something much better.

---

## 1. Design the Error Format

Every error response from TicketPulse will follow this exact shape:

```typescript
interface ApiError {
  error: {
    code: string;           // Machine-readable: "VALIDATION_ERROR", "NOT_FOUND", etc.
    message: string;        // Human-readable summary
    details?: ErrorDetail[];// Field-level errors for validation
    requestId: string;      // Unique ID to trace in logs
  };
}

interface ErrorDetail {
  field: string;    // Which field has the problem
  issue: string;    // What's wrong with it
  value?: any;      // What the client sent (so they can see the mismatch)
}
```

Why this structure:
- **`code`**: Clients switch on this programmatically. Never parse the `message` string.
- **`message`**: Developers read this in logs and during debugging.
- **`details`**: Returns ALL validation errors at once, not just the first one.
- **`requestId`**: Links this error to a specific log trail on the server side.

> **Insight:** Stripe's API errors include a `type` field (`card_error`, `api_error`, `authentication_error`, etc.) and a `doc_url` linking to the documentation for that specific error. That is the gold standard -- every error teaches the developer how to fix it.

---

## 2. Build: Custom Error Classes

<details>
<summary>💡 Hint 1: Extend the Native Error Class</summary>
Create an `AppError` base class that extends `Error`. Give it `statusCode` (number), `code` (string like `NOT_FOUND`), `message`, an optional `details` array for field-level issues, and a `requestId` (UUID). All other error classes extend `AppError` with preset values.
</details>

<details>
<summary>💡 Hint 2: Map HTTP Status Codes to Error Types</summary>
Each subclass should hardcode its status: `NotFoundError` = 404, `ValidationError` = 400, `ConflictError` = 409, `UnauthorizedError` = 401, `ForbiddenError` = 403. The error middleware checks `err instanceof AppError` and uses `err.statusCode` to set the response status.
</details>

<details>
<summary>💡 Hint 3: ValidationError Carries Field Details</summary>
`ValidationError` takes an array of `{ field: string, issue: string, value?: any }` objects. The constructor counts the details and builds a summary message like "The request body contains 3 invalid fields." This way the client gets ALL problems at once instead of one-at-a-time.
</details>

Create a set of error classes that the rest of the application can throw:

```typescript
// src/errors.ts

import { randomUUID } from 'crypto';

export class AppError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly details?: ErrorDetail[];
  public readonly requestId: string;

  constructor(
    statusCode: number,
    code: string,
    message: string,
    details?: ErrorDetail[],
    requestId?: string
  ) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.requestId = requestId || randomUUID();
    this.name = 'AppError';
  }
}

export interface ErrorDetail {
  field: string;
  issue: string;
  value?: any;
}

// --- Specific error types ---

export class NotFoundError extends AppError {
  constructor(resource: string, id: string, requestId?: string) {
    super(404, 'NOT_FOUND', `${resource} with id '${id}' not found.`, undefined, requestId);
  }
}

export class ValidationError extends AppError {
  constructor(details: ErrorDetail[], requestId?: string) {
    const count = details.length;
    super(
      400,
      'VALIDATION_ERROR',
      `The request body contains ${count} invalid field${count > 1 ? 's' : ''}.`,
      details,
      requestId
    );
  }
}

export class ConflictError extends AppError {
  constructor(message: string, requestId?: string) {
    super(409, 'CONFLICT', message, undefined, requestId);
  }
}

export class UnauthorizedError extends AppError {
  constructor(message = 'Authentication required.', requestId?: string) {
    super(401, 'UNAUTHORIZED', message, undefined, requestId);
  }
}

export class ForbiddenError extends AppError {
  constructor(message = 'You do not have permission to perform this action.', requestId?: string) {
    super(403, 'FORBIDDEN', message, undefined, requestId);
  }
}
```

Now any route handler can do:

```typescript
throw new NotFoundError('Event', id);
throw new ValidationError([
  { field: 'email', issue: 'Must be a valid email address.', value: req.body.email },
  { field: 'title', issue: 'Required field is missing.' },
]);
```

---

## 3. Build: Request ID Middleware

Before we handle errors, we need request IDs. Every single request gets a unique ID that follows it through every log line and into the error response:

```typescript
// src/middleware/requestId.ts

import { Request, Response, NextFunction } from 'express';
import { randomUUID } from 'crypto';

declare global {
  namespace Express {
    interface Request {
      requestId: string;
    }
  }
}

export function requestIdMiddleware(req: Request, res: Response, next: NextFunction) {
  // Use the client's request ID if provided, otherwise generate one
  const requestId = (req.headers['x-request-id'] as string) || randomUUID();

  req.requestId = requestId;
  res.setHeader('X-Request-Id', requestId);

  next();
}
```

Wire it in early -- before all other middleware:

```typescript
// src/app.ts
import { requestIdMiddleware } from './middleware/requestId';

app.use(requestIdMiddleware);
app.use(express.json());
// ... routes
```

Now every request has a `req.requestId` and every response has an `X-Request-Id` header.

---

## 4. Build: Error Handling Middleware

<details>
<summary>💡 Hint 1: Express Error Middleware Has 4 Parameters</summary>
Express distinguishes error middleware by its signature: `(err, req, res, next)` -- exactly 4 parameters. Place it AFTER all routes with `app.use(errorHandler)`. Express will route thrown errors and `next(err)` calls to this middleware automatically.
</details>

<details>
<summary>💡 Hint 2: Branch on Error Type</summary>
Check `err instanceof AppError` first -- these are known application errors (4xx). For JSON parse errors, check `err.type === 'entity.parse.failed'` (Express sets this). Everything else is an unknown 500 error. Log the full stack trace server-side but NEVER send it to the client.
</details>

<details>
<summary>💡 Hint 3: Consistent Shape for Every Error Response</summary>
Every error response must have `{ error: { code, message, requestId } }`. For validation errors, add a `details` array. Use `req.requestId` (set by your requestId middleware) so every error can be traced in logs. Log known errors at `warn` level, unknown errors at `error` level.
</details>

This is the centerpiece. A single middleware that catches ALL errors and returns consistent responses:

```typescript
// src/middleware/errorHandler.ts

import { Request, Response, NextFunction } from 'express';
import { AppError } from '../errors';

export function errorHandler(err: Error, req: Request, res: Response, _next: NextFunction) {
  const requestId = req.requestId || 'unknown';

  // --- Known application errors ---
  if (err instanceof AppError) {
    // Log at warn level -- these are expected errors (client mistakes, business rule violations)
    console.warn(JSON.stringify({
      level: 'warn',
      requestId,
      errorCode: err.code,
      statusCode: err.statusCode,
      message: err.message,
      path: req.path,
      method: req.method,
    }));

    const response: any = {
      error: {
        code: err.code,
        message: err.message,
        requestId,
      },
    };

    if (err.details && err.details.length > 0) {
      response.error.details = err.details;
    }

    res.status(err.statusCode).json(response);
    return;
  }

  // --- JSON parse errors ---
  if (err.type === 'entity.parse.failed') {
    console.warn(JSON.stringify({
      level: 'warn',
      requestId,
      errorCode: 'INVALID_JSON',
      message: 'Request body is not valid JSON',
      path: req.path,
      method: req.method,
    }));

    res.status(400).json({
      error: {
        code: 'INVALID_JSON',
        message: 'The request body is not valid JSON.',
        requestId,
      },
    });
    return;
  }

  // --- Unknown errors (bugs in our code) ---
  // CRITICAL: Never expose internal details to the client
  console.error(JSON.stringify({
    level: 'error',
    requestId,
    errorCode: 'INTERNAL_ERROR',
    message: err.message,
    stack: err.stack,          // Logged internally -- NOT sent to client
    path: req.path,
    method: req.method,
  }));

  res.status(500).json({
    error: {
      code: 'INTERNAL_ERROR',
      message: 'An unexpected error occurred. Please try again or contact support.',
      requestId,
    },
  });
}
```

Wire it LAST -- after all routes:

```typescript
// src/app.ts
import { errorHandler } from './middleware/errorHandler';

// ... all routes ...

app.use(errorHandler);
```

---

## 5. Build: Validation That Reports ALL Issues

<details>
<summary>💡 Hint 1: Accumulate Errors in an Array</summary>
Create an `errors: ErrorDetail[]` array at the top of the function. For each field, check presence and type, then push `{ field: 'title', issue: 'Required. Must be a non-empty string.', value: body.title }` into the array. Do NOT return early on the first error.
</details>

<details>
<summary>💡 Hint 2: Chain Validations With else-if</summary>
For each field, check required-ness first, then format. Use `else if` so you do not report both "required" and "must be at most 200 chars" for the same field. For dates, parse with `new Date()` and check `isNaN(parsed.getTime())`. For numbers, use `Number.isInteger()`.
</details>

<details>
<summary>💡 Hint 3: Throw at the End, Not in the Middle</summary>
After all checks, do `if (errors.length > 0) throw new ValidationError(errors, requestId)`. This single throw replaces the old pattern of `if (!title) return res.status(400)...`. The error middleware handles formatting and sending the response.
</details>

The old validation checked one thing at a time. Let us build a validator that collects every problem and returns them all:

```typescript
// src/validators/eventValidator.ts

import { ErrorDetail, ValidationError } from '../errors';

interface CreateEventInput {
  title?: string;
  venue?: string;
  city?: string;
  date?: string;
  totalTickets?: number;
  priceInCents?: number;
  description?: string;
}

export function validateCreateEvent(body: CreateEventInput, requestId: string): void {
  const errors: ErrorDetail[] = [];

  // --- Required fields ---
  if (!body.title || typeof body.title !== 'string') {
    errors.push({
      field: 'title',
      issue: 'Required. Must be a non-empty string.',
      value: body.title,
    });
  } else if (body.title.length > 200) {
    errors.push({
      field: 'title',
      issue: 'Must be 200 characters or fewer.',
      value: `${body.title.substring(0, 20)}... (${body.title.length} chars)`,
    });
  }

  if (!body.venue || typeof body.venue !== 'string') {
    errors.push({
      field: 'venue',
      issue: 'Required. Must be a non-empty string.',
      value: body.venue,
    });
  }

  if (!body.date) {
    errors.push({
      field: 'date',
      issue: 'Required. Must be a valid ISO 8601 date string.',
      value: body.date,
    });
  } else {
    const parsed = new Date(body.date);
    if (isNaN(parsed.getTime())) {
      errors.push({
        field: 'date',
        issue: 'Must be a valid ISO 8601 date string (e.g., "2026-09-15T20:00:00Z").',
        value: body.date,
      });
    } else if (parsed <= new Date()) {
      errors.push({
        field: 'date',
        issue: 'Must be a future date.',
        value: body.date,
      });
    }
  }

  if (body.totalTickets === undefined || body.totalTickets === null) {
    errors.push({
      field: 'totalTickets',
      issue: 'Required. Must be a positive integer.',
      value: body.totalTickets,
    });
  } else if (!Number.isInteger(body.totalTickets) || body.totalTickets <= 0) {
    errors.push({
      field: 'totalTickets',
      issue: 'Must be a positive integer.',
      value: body.totalTickets,
    });
  } else if (body.totalTickets > 100000) {
    errors.push({
      field: 'totalTickets',
      issue: 'Must be 100,000 or fewer.',
      value: body.totalTickets,
    });
  }

  if (body.priceInCents === undefined || body.priceInCents === null) {
    errors.push({
      field: 'priceInCents',
      issue: 'Required. Must be a non-negative integer (price in cents).',
      value: body.priceInCents,
    });
  } else if (!Number.isInteger(body.priceInCents) || body.priceInCents < 0) {
    errors.push({
      field: 'priceInCents',
      issue: 'Must be a non-negative integer (price in cents, e.g., 8500 for $85.00).',
      value: body.priceInCents,
    });
  }

  // --- If any errors were found, throw them all at once ---
  if (errors.length > 0) {
    throw new ValidationError(errors, requestId);
  }
}
```

Update the create event route to use it:

```typescript
// src/routes/events.ts -- updated POST / handler

import { validateCreateEvent } from '../validators/eventValidator';
import { NotFoundError, ConflictError } from '../errors';

router.post('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    validateCreateEvent(req.body, req.requestId);

    const { title, description, venue, city, date, totalTickets, priceInCents } = req.body;

    const result = await pool.query(
      `INSERT INTO events (title, description, venue, city, date, total_tickets, available_tickets, price_in_cents)
       VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
       RETURNING *`,
      [title, description || '', venue, city || '', date, totalTickets, priceInCents]
    );

    res.status(201).json({ data: formatEvent(result.rows[0]) });
  } catch (err) {
    next(err);
  }
});
```

---

## 6. Try It: Send Malformed Requests

Now test the new error handling:

### Multiple validation errors at once

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "",
    "date": "not-a-date",
    "totalTickets": -5,
    "priceInCents": "free"
  }' | jq .
```

Expected response:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request body contains 5 invalid fields.",
    "details": [
      { "field": "title", "issue": "Required. Must be a non-empty string.", "value": "" },
      { "field": "venue", "issue": "Required. Must be a non-empty string." },
      { "field": "date", "issue": "Must be a valid ISO 8601 date string...", "value": "not-a-date" },
      { "field": "totalTickets", "issue": "Must be a positive integer.", "value": -5 },
      { "field": "priceInCents", "issue": "Must be a non-negative integer...", "value": "free" }
    ],
    "requestId": "a1b2c3d4-e5f6-..."
  }
}
```

ALL five errors at once. The developer fixes everything in one round trip.

### Invalid JSON

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d 'this is not json' | jq .
```

Expected:

```json
{
  "error": {
    "code": "INVALID_JSON",
    "message": "The request body is not valid JSON.",
    "requestId": "..."
  }
}
```

### Request ID tracing

```bash
# Notice the X-Request-Id header in every response
curl -s -D - -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{}' 2>&1 | grep -i "x-request-id"
```

You should see something like:

```
X-Request-Id: f47ac10b-58cc-4372-a567-0e02b2c3d479
```

That same ID appears in the server logs. When a user reports an error, they give you the request ID, and you can find every log line for that request instantly.

---

## 7. Common Mistake: Leaking Stack Traces in Production

This is a security risk, not just a cosmetic issue. Look at what a leaked stack trace reveals:

```json
{
  "error": "PgError: relation 'users' does not exist at Pool.query (/app/node_modules/pg/lib/pool.js:45)\n    at /app/src/routes/events.ts:23:14\n    at processTicksAndRejections (node:internal/process/task_queues:95:5)"
}
```

An attacker now knows:
- You are using PostgreSQL
- Your table is called `users`
- Your code lives in `/app/src/routes/events.ts`
- You are using the `pg` npm package
- Your Node.js version supports `processTicksAndRejections`

Our error middleware prevents this. Internal errors get a safe message:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again or contact support.",
    "requestId": "f47ac10b-..."
  }
}
```

The full stack trace is logged server-side (where it belongs), tagged with the request ID (so you can find it). The client gets only what it needs.

### Try It: Trigger an internal error

Temporarily add a route that throws an unhandled error:

```typescript
// Add this to test, then remove it
router.get('/debug/crash', async (_req: Request, _res: Response) => {
  throw new Error('Something broke inside the database layer');
});
```

```bash
curl -s http://localhost:3000/api/events/debug/crash | jq .
```

You should see the safe error response (not the stack trace). Check your server logs to confirm the full details are logged there.

**Remove the debug route after testing.**

---

## 8. The Complete Error Code Catalog

Document every error your API can return. Here is TicketPulse's catalog:

| Code | HTTP Status | Cause | Fix |
|------|-------------|-------|-----|
| `VALIDATION_ERROR` | 400 | Request body has invalid fields | Check `details` array for specific field issues |
| `INVALID_JSON` | 400 | Request body is not valid JSON | Send valid JSON with `Content-Type: application/json` |
| `NOT_FOUND` | 404 | The requested resource does not exist | Check the resource ID |
| `CONFLICT` | 409 | Action conflicts with current state | Event is sold out, duplicate email, etc. |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication | Include a valid Bearer token (coming in M13) |
| `FORBIDDEN` | 403 | Authenticated but not authorized | You need a different role for this action |
| `INTERNAL_ERROR` | 500 | Bug in TicketPulse | Contact support with the `requestId` |

---

## 9. Reflect

> Think about these questions:
>
> 1. We return the invalid `value` in validation error details. Is there a case where this could be a security risk? (Hint: what if someone sends a password to the wrong endpoint?)
>
> 2. Our `requestId` is a UUID. What are the pros and cons of using a sequential ID instead?
>
> 3. How would you test that your error middleware never leaks stack traces? Could you write an automated test for that?
>
> 4. Stripe returns a `doc_url` in every error linking to documentation for that specific error code. How much effort would that take to implement? Is it worth it?

---

## 10. Checkpoint

After this module, TicketPulse should have:

- [ ] Custom error classes: `AppError`, `NotFoundError`, `ValidationError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`
- [ ] Request ID middleware that tags every request with a UUID
- [ ] Error handling middleware that catches all errors and returns consistent JSON
- [ ] Validation that reports ALL issues at once (not just the first)
- [ ] Stack traces are logged server-side but never exposed to clients
- [ ] Every error response includes `code`, `message`, and `requestId`

**Next up:** L1-M13 where we add authentication and authorization -- JWT tokens, password hashing, and role-based access control.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Error middleware** | Express middleware with 4 parameters (err, req, res, next). Catches all errors thrown in route handlers. |
| **Request ID** | A unique identifier assigned to every request. Used to correlate log entries across the request lifecycle. |
| **Validation error** | A 400-level error indicating the client sent invalid data. Should include details about every invalid field. |
| **Stack trace** | The call stack at the point of an error. Contains file paths, line numbers, and function names. Never expose to clients in production. |
| **Error code** | A machine-readable string (like `VALIDATION_ERROR`) that clients use to handle errors programmatically. More stable than HTTP status codes or messages. |
---

## What's Next

In **Authentication & Authorization** (L1-M13), you'll build on what you learned here and take it further.

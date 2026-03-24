<!--
  CHAPTER: 25
  TITLE: API Design & Developer Experience
  PART: II — Applied Engineering
  PREREQS: Chapter 3
  KEY_TOPICS: REST API design, error handling, pagination, versioning, idempotency, webhooks, SDK design, OpenAPI, rate limiting, authentication patterns, API documentation
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 25: API Design & Developer Experience

> **Part II — Applied Engineering** | Prerequisites: Chapter 3 | Difficulty: Intermediate

Designing APIs that developers love — from consistent error handling to pagination patterns to webhook design. Great APIs are the difference between a product developers adopt eagerly and one they avoid.

### In This Chapter
- API Design Principles
- REST API Conventions
- Error Handling
- Pagination Patterns
- Versioning Strategies
- Idempotency & Safety
- Authentication Patterns
- Webhook Design
- Rate Limiting & Quotas
- SDK & Client Library Design
- API Documentation
- Real-World API Analysis

### Related Chapters
- Ch 3 (REST/gRPC/GraphQL architecture)
- Ch 5 (authentication/authorization)
- Ch 21 (HTTP protocol details)
- Ch 23 (system design case studies)

---

## 25.1 API Design Principles

The best APIs feel invisible. Developers pick them up quickly, make fewer mistakes, and rarely need to consult the docs after the first session. That does not happen by accident — it comes from a small set of principles applied relentlessly.

### Consistency Is the Foundation

Every endpoint should feel like it belongs to the same API. If you use `created_at` on one resource, do not switch to `createdAt` on another. If `GET /users` returns a list with a `data` wrapper, then `GET /orders` should do the same.

Consistency applies to:
- **Naming conventions** — pick `snake_case` or `camelCase` and commit
- **Response shapes** — every list endpoint returns `{ "data": [...], "pagination": {...} }`
- **Error formats** — every error follows the same structure (covered in 25.3)
- **URL patterns** — pluralized nouns, consistent nesting depth
- **Query parameter names** — `limit` everywhere, not `limit` on one endpoint and `page_size` on another

A style guide written before the first endpoint is built pays for itself a hundred times over.

### Predictability

If a developer learns how `GET /users`, `POST /users`, `GET /users/:id`, `PATCH /users/:id`, and `DELETE /users/:id` work, they should be able to predict the exact behavior of every other resource in your API without reading the docs.

```
# If you know this...
GET    /users
POST   /users
GET    /users/:id
PATCH  /users/:id
DELETE /users/:id

# ...you can guess all of this:
GET    /orders
POST   /orders
GET    /orders/:id
PATCH  /orders/:id
DELETE /orders/:id
```

The moment you break the pattern (one resource uses `PUT` instead of `PATCH`, another uses `/create` instead of `POST`), developers lose trust and start double-checking everything.

### Resource-Oriented Design

Design around nouns, not verbs. Resources are things; HTTP methods are the verbs.

```
# Good — resources are nouns, HTTP method is the verb
POST   /users              # Create a user
GET    /users/:id          # Read a user
PATCH  /users/:id          # Update a user
DELETE /users/:id          # Delete a user

# Bad — verbs in the URL
POST   /createUser
GET    /getUser?id=123
POST   /updateUser
POST   /deleteUser
```

There are exceptions — actions that don't map cleanly to CRUD. For these, use a verb as a sub-resource:

```
POST /orders/:id/cancel
POST /users/:id/verify-email
POST /payments/:id/refund
```

Keep these to a minimum. If you find yourself creating many action endpoints, your resource model probably needs rethinking.

### HATEOAS — In Theory and Practice

Hypermedia as the Engine of Application State is the idea that API responses include links to related actions and resources:

```json
{
  "id": "usr_123",
  "name": "Alice",
  "email": "alice@example.com",
  "_links": {
    "self": { "href": "/api/v1/users/usr_123" },
    "orders": { "href": "/api/v1/users/usr_123/orders" },
    "update": { "href": "/api/v1/users/usr_123", "method": "PATCH" },
    "delete": { "href": "/api/v1/users/usr_123", "method": "DELETE" }
  }
}
```

In practice, almost no one implements full HATEOAS. Why:
- Client SDKs hardcode URL patterns anyway
- It adds payload bloat
- Clients rarely follow links dynamically — they know the URL structure at build time

**What is worth adopting from HATEOAS**: pagination links (`next`, `prev`) and action URLs in webhook payloads. Skip the rest unless you are building a truly generic hypermedia client.

### API-First Design

Design the API before writing a single line of implementation code. The sequence:

1. Write the OpenAPI spec (or at minimum, sketch the endpoints, request/response shapes, and error codes on paper)
2. Review the spec with API consumers (frontend team, partner developers, your future self)
3. Generate mocks from the spec so consumers can start building against it immediately
4. Implement the server
5. Validate the implementation against the spec in CI

API-first catches design mistakes when they are cheap to fix — before anyone has written code against a bad contract.

### Backward Compatibility Is the Number One Rule

Once an API is in production, breaking it is the most expensive thing you can do. Every breaking change forces every consumer to update their code, test, and redeploy. Multiply that by hundreds of integrators and you understand why Stripe has not broken their API in over a decade.

**Non-breaking changes** (always safe):
- Adding a new optional field to a response
- Adding a new optional query parameter
- Adding a new endpoint
- Adding a new enum value (if clients handle unknown values gracefully)

**Breaking changes** (require versioning):
- Removing or renaming a field
- Changing a field's type
- Making an optional parameter required
- Changing the meaning of an existing field
- Removing an endpoint

When in doubt, it is a breaking change. Treat it as one.

---

## 25.2 REST API Conventions

### URL Structure

```
https://api.example.com/v1/resources/:id/sub-resources/:sub_id
```

Rules:
- **Base URL**: Use a subdomain (`api.example.com`) or path prefix (`example.com/api`)
- **Version**: In the URL path (`/v1/`). More on this in 25.5
- **Resources**: Plural nouns (`/users`, `/orders`, `/invoices`)
- **Identifiers**: After the resource name (`/users/usr_123`)
- **Sub-resources**: Nested under their parent (`/users/usr_123/orders`)
- **Max nesting depth**: Two levels. `/users/:id/orders/:id` is fine. `/users/:id/orders/:id/items/:id/variants/:id` is not — flatten it

### HTTP Methods

| Method   | Meaning         | Idempotent | Safe | Request Body |
|----------|-----------------|------------|------|--------------|
| `GET`    | Read            | Yes        | Yes  | No           |
| `POST`   | Create          | No         | No   | Yes          |
| `PUT`    | Full replace    | Yes        | No   | Yes          |
| `PATCH`  | Partial update  | Yes*       | No   | Yes          |
| `DELETE` | Remove          | Yes        | No   | Optional     |
| `HEAD`   | Read headers    | Yes        | Yes  | No           |
| `OPTIONS`| Discover        | Yes        | Yes  | No           |

*`PATCH` is idempotent if the patch document describes the final state (e.g., `{"name": "Alice"}`), not if it describes a transformation (e.g., `{"$increment": {"count": 1}}`).

**When to use PUT vs PATCH**:
- `PUT /users/123` — client sends the **complete** user object. Any fields not included are reset to defaults or nulled
- `PATCH /users/123` — client sends **only the fields to change**. Everything else stays the same

In practice, most APIs use `PATCH` for updates because clients rarely want to send the full object.

### Naming Conventions

Pick one casing style and stick with it:

```
# snake_case (most common for JSON APIs — Python, Ruby ecosystem)
GET /api/v1/user_accounts?sort_by=created_at&page_size=20

# camelCase (common in JavaScript/TypeScript ecosystem)
GET /api/v1/userAccounts?sortBy=createdAt&pageSize=20

# kebab-case for URLs, snake_case for JSON (good compromise)
GET /api/v1/user-accounts?sort_by=created_at&page_size=20
```

The right answer is: whatever your ecosystem expects. If your primary consumers are JavaScript developers, `camelCase` in JSON bodies is idiomatic. If they are Python developers, `snake_case`. URL paths tend toward `kebab-case` or `snake_case` — never `camelCase` (URLs are case-insensitive by convention in many systems).

### Filtering

Use query parameters for filtering:

```
GET /users?status=active&role=admin&created_after=2025-01-01
```

For complex filters, consider a structured approach:

```
# Simple equality
GET /orders?status=shipped

# Multiple values (OR logic)
GET /orders?status=shipped,delivered

# Range filters
GET /orders?total_min=100&total_max=500

# Date ranges
GET /orders?created_after=2025-01-01&created_before=2025-12-31
```

Do not invent a query language in query parameters. If filtering needs are complex, consider a `POST /search` endpoint with a JSON body:

```json
{
  "filters": {
    "status": ["shipped", "delivered"],
    "total": { "gte": 100, "lte": 500 },
    "created_at": { "after": "2025-01-01" }
  },
  "sort": ["-created_at"],
  "limit": 20
}
```

### Sorting

Use a `sort` parameter with field names. Prefix with `-` for descending:

```
# Sort by created_at descending, then name ascending
GET /users?sort=-created_at,name
```

Response:

```json
{
  "data": [],
  "pagination": {},
  "sort": ["-created_at", "name"]
}
```

### Field Selection (Sparse Fieldsets)

Let clients request only the fields they need to reduce payload size:

```
GET /users?fields=id,name,email
```

Response:

```json
{
  "data": [
    { "id": "usr_123", "name": "Alice", "email": "alice@example.com" },
    { "id": "usr_456", "name": "Bob", "email": "bob@example.com" }
  ]
}
```

This is especially valuable for mobile clients on slow connections.

### Bulk Operations

For operations on multiple resources:

```json
{
  "operations": [
    { "method": "create", "body": { "name": "Alice", "email": "alice@example.com" } },
    { "method": "create", "body": { "name": "Bob", "email": "bob@example.com" } }
  ]
}
```

Response (report per-item results):

```json
{
  "results": [
    { "index": 0, "status": 201, "data": { "id": "usr_789", "name": "Alice" } },
    { "index": 1, "status": 400, "error": { "code": "DUPLICATE_EMAIL", "message": "Email already exists" } }
  ],
  "summary": { "succeeded": 1, "failed": 1 }
}
```

Key design decisions for bulk endpoints:
- **Partial success**: Always allow partial success. Do not roll back everything because one item failed
- **Ordering**: Process items in order and return results in the same order
- **Limits**: Cap the batch size (e.g., max 100 items per request)
- **HTTP status**: Return `200` or `207 Multi-Status` for the overall response, even if some items failed — the per-item status tells the real story

### Sub-Resources vs Query Parameters

```
# Sub-resource — implies strong ownership (orders belong to a user)
GET /users/123/orders

# Query parameter — implies filtering (orders can exist independently)
GET /orders?user_id=123
```

Use sub-resources when:
- The child cannot exist without the parent (a user's API keys, a post's comments)
- You want to scope permissions (accessing `/users/123/orders` requires access to user 123)

Use query parameters when:
- The resource is independent and you're just filtering
- You need to filter by multiple dimensions simultaneously

---

## 25.3 Error Handling

Error handling is where most APIs fail. A good error response tells the developer exactly what went wrong, where, and how to fix it. A bad one returns `500 Internal Server Error` with no body.

### The Standard Error Format

Every error response from your API should follow the same structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request body contains invalid fields.",
    "details": [
      {
        "field": "email",
        "issue": "Must be a valid email address.",
        "value": "not-an-email"
      },
      {
        "field": "age",
        "issue": "Must be a positive integer.",
        "value": -5
      }
    ],
    "request_id": "req_abc123def456",
    "doc_url": "https://docs.example.com/errors/VALIDATION_ERROR"
  }
}
```

Breaking this down:
- **`code`**: Machine-readable error code. Clients switch on this, not the HTTP status
- **`message`**: Human-readable summary for developers reading logs
- **`details`**: Array of specific issues (especially for validation errors)
- **`request_id`**: Unique ID for this request — essential for debugging. Include it in every response, success or error
- **`doc_url`**: Link to documentation for this error type (Twilio does this brilliantly)

### HTTP Status Code Usage

Use status codes correctly. This is not optional.

**2xx — Success**:

| Code | Meaning | When to Use |
|------|---------|-------------|
| `200 OK` | Success | GET, PATCH, PUT, DELETE (when returning a body) |
| `201 Created` | Resource created | POST that creates a resource |
| `202 Accepted` | Accepted for processing | Async operations (job queued) |
| `204 No Content` | Success, no body | DELETE (when not returning the deleted resource) |

**4xx — Client Error** (the client did something wrong):

| Code | Meaning | When to Use |
|------|---------|-------------|
| `400 Bad Request` | Malformed request | Invalid JSON, wrong Content-Type |
| `401 Unauthorized` | Not authenticated | Missing or invalid API key/token |
| `403 Forbidden` | Not authorized | Valid credentials, but no permission |
| `404 Not Found` | Resource not found | ID doesn't exist |
| `409 Conflict` | State conflict | Duplicate creation, version conflict |
| `422 Unprocessable Entity` | Validation failed | Valid JSON but invalid values |
| `429 Too Many Requests` | Rate limited | Exceeded rate limit |

**5xx — Server Error** (something broke on your side):

| Code | Meaning | When to Use |
|------|---------|-------------|
| `500 Internal Server Error` | Bug in your code | Unhandled exceptions |
| `502 Bad Gateway` | Upstream failure | Dependency returned an error |
| `503 Service Unavailable` | Temporarily down | Maintenance, overload |
| `504 Gateway Timeout` | Upstream timeout | Dependency took too long |

**Common mistakes**:
- Using `200` for everything and putting the real status in the body — clients cannot use HTTP-level error handling
- Using `500` for validation errors — that is your bug, not the client's
- Using `403` when you mean `401` — "you aren't logged in" is `401`, "you're logged in but can't do this" is `403`
- Using `404` to mean "this feature isn't built yet" — that is `501 Not Implemented`

### Return ALL Validation Errors

Never return only the first validation error. The developer will fix it, resubmit, get the next error, fix that, resubmit, and hate your API by the third round trip.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format"
  }
}
```

That is bad. This is good:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request body contains 3 invalid fields.",
    "details": [
      { "field": "email", "issue": "Must be a valid email address." },
      { "field": "name", "issue": "Required field is missing." },
      { "field": "age", "issue": "Must be between 0 and 150." }
    ]
  }
}
```

### Rate Limit Errors

Always include `Retry-After` so clients know when to retry:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706284800
```

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "You have exceeded your rate limit of 100 requests per minute.",
    "retry_after": 30
  }
}
```

### Internal Error Handling

Never expose stack traces, database queries, or internal paths in error responses.

Bad:

```json
{
  "error": "PgError: relation 'users' does not exist at Pool.query (/app/node_modules/pg/lib/pool.js:45)"
}
```

Good:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again or contact support.",
    "request_id": "req_abc123"
  }
}
```

The `request_id` lets your support team find the full stack trace in your internal logs without exposing it to the client.

### Error Documentation

Document every error code your API can return. For each one, include the HTTP status, what causes it, how to fix it, and an example response.

Example documentation entry:

```
VALIDATION_ERROR (HTTP 422)
Cause: One or more fields in the request body failed validation.
Fix: Check the details array for specific field errors and correct them.
```

---

## 25.4 Pagination Patterns

Any endpoint that returns a list needs pagination. No exceptions. Even if you think "there will never be more than a few" — you are wrong.

### Offset Pagination

The simplest approach:

```
GET /users?page=1&limit=20
GET /users?page=2&limit=20
```

Server implementation (SQL):

```sql
SELECT * FROM users ORDER BY id LIMIT 20 OFFSET 20;  -- page 2
```

Response:

```json
{
  "data": [
    { "id": "usr_101", "name": "Alice" },
    { "id": "usr_102", "name": "Bob" }
  ],
  "pagination": {
    "page": 2,
    "limit": 20,
    "total_count": 354,
    "total_pages": 18
  }
}
```

**Pros**:
- Simple to implement
- Clients can jump to any page
- Easy to show "Page 2 of 18" in UI

**Cons**:
- **Slow for deep pages** — `OFFSET 100000` still scans 100,000 rows (O(n))
- **Unstable** — if a record is inserted or deleted between page requests, items shift and you get duplicates or gaps
- **`total_count` is expensive** — `SELECT COUNT(*)` on large tables is slow in many databases

### Cursor-Based (Keyset) Pagination

The production-grade approach:

```
GET /users?limit=20
GET /users?after=eyJpZCI6InVzcl8xMjAifQ&limit=20
```

The cursor is an opaque, base64-encoded token. The server decodes it to get the last seen record's sort key:

```javascript
// Decode cursor
const cursor = JSON.parse(atob("eyJpZCI6InVzcl8xMjAifQ"));
// Result: { id: "usr_120" }

// Query: get the next 20 after this ID
// SELECT * FROM users WHERE id > 'usr_120' ORDER BY id LIMIT 21
```

Request 21 rows, return 20. If you got 21, there is a next page.

Response:

```json
{
  "data": [
    { "id": "usr_121", "name": "Charlie" },
    { "id": "usr_122", "name": "Diana" }
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6InVzcl8xNDAifQ",
    "has_more": true
  }
}
```

**Pros**:
- **Fast at any depth** — uses an indexed `WHERE` clause, not `OFFSET`
- **Stable** — inserts and deletes don't cause duplicates or gaps
- **No `total_count` needed** — just `has_more`

**Cons**:
- Cannot jump to page N
- Cursor is opaque — clients must use it as given
- Multi-column sort requires more complex cursors

### When to Use Which

| Scenario | Use |
|----------|-----|
| Admin dashboard with page numbers | Offset (acceptable for internal tools) |
| Infinite scroll UI | Cursor |
| Public API consumed by other services | Cursor |
| Data export / sync | Cursor |
| Small dataset (fewer than 10K rows) | Either works fine |
| Large dataset (more than 100K rows) | Cursor (offset will degrade) |

### Cursor for Multi-Column Sort

When sorting by more than one column, the cursor must encode all sort keys:

```
GET /users?sort=-created_at,id&limit=20
```

Cursor encodes:

```json
{ "created_at": "2025-06-15T10:30:00Z", "id": "usr_120" }
```

Query:

```sql
SELECT * FROM users
WHERE (created_at, id) < ('2025-06-15T10:30:00Z', 'usr_120')
ORDER BY created_at DESC, id DESC
LIMIT 21;
```

### Relay-Style Connections (GraphQL)

The GraphQL community standardized on the Relay connection spec:

```json
{
  "data": {
    "users": {
      "edges": [
        {
          "node": { "id": "usr_121", "name": "Charlie" },
          "cursor": "YXJyYXljb25uZWN0aW9uOjA="
        },
        {
          "node": { "id": "usr_122", "name": "Diana" },
          "cursor": "YXJyYXljb25uZWN0aW9uOjE="
        }
      ],
      "pageInfo": {
        "hasNextPage": true,
        "hasPreviousPage": true,
        "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
        "endCursor": "YXJyYXljb25uZWN0aW9uOjE="
      }
    }
  }
}
```

This is verbose but allows each edge to carry its own cursor, enabling fine-grained pagination. For REST APIs, the simpler format in the previous section is sufficient.

---

## 25.5 Versioning Strategies

APIs change. The question is how you manage those changes without breaking existing clients.

### URL Versioning

```
GET /v1/users
GET /v2/users
```

**Pros**: Explicit, easy to understand, easy to route, easy to deprecate. Most common approach.

**Cons**: Clients must update URLs to adopt a new version. You maintain multiple route handlers.

This is the right default choice for most APIs.

### Header Versioning

```http
GET /users
Accept: application/vnd.myapi.v2+json
```

Or with a custom header:

```http
GET /users
API-Version: 2
```

**Pros**: Clean URLs. Can version individual endpoints independently.

**Cons**: Harder to test (you cannot just paste a URL into a browser). Many API tools don't make it obvious which version you are calling. Easy to forget to set the header.

### Query Parameter Versioning

```
GET /users?version=2
```

**Pros**: Simple. Easy to test.

**Cons**: Mixes infrastructure concerns (versioning) with business concerns (filtering). Gets lost among other query parameters.

### Date-Based Versioning (Stripe's Approach)

This is the gold standard for APIs with many consumers.

```http
GET /v1/users
Stripe-Version: 2025-01-15
```

How it works:

1. Each API key has a default version (the version when the key was created)
2. Clients can override per-request with a version header
3. Every breaking change gets a new date-based version
4. The server applies **backward-compatibility transforms** — internally, only the latest code runs, and a compatibility layer transforms responses for older versions

```
Internal representation (latest)
        |
  Compat transform for 2025-01-15
        |
  Compat transform for 2024-06-01
        |
  Compat transform for 2024-01-01
        |
Response sent to client
```

**Pros**:
- Clients are never forced to upgrade — their default version just works forever
- New features are available immediately without a version bump
- Breaking changes are isolated and documented per date

**Cons**:
- Complex to implement — the compatibility transform layer is non-trivial
- Only worth it for APIs with hundreds of consumers

### Breaking vs Non-Breaking Changes

| Change | Breaking? |
|--------|-----------|
| Add optional field to response | No |
| Add optional query parameter | No |
| Add new endpoint | No |
| Add new enum value | Maybe (if clients don't handle unknowns) |
| Add required field to request | Yes |
| Remove field from response | Yes |
| Rename field | Yes |
| Change field type (string to int) | Yes |
| Change error code format | Yes |
| Change URL structure | Yes |

### Deprecation Workflow

1. **Announce**: Publish the deprecation in your changelog, API docs, and developer newsletter
2. **Sunset header**: Add a `Sunset: Sat, 01 Mar 2026 00:00:00 GMT` header to deprecated endpoint responses
3. **Warn in logs**: Log warnings when deprecated endpoints are called, including which API key is calling them
4. **Contact heavy users**: Reach out directly to top consumers of the deprecated endpoint
5. **Grace period**: Give at least 6-12 months for major changes
6. **Remove**: Turn off the endpoint and return `410 Gone`

```http
HTTP/1.1 200 OK
Sunset: Sat, 01 Mar 2026 00:00:00 GMT
Deprecation: true
Link: <https://docs.example.com/migration/v2>; rel="successor-version"
```

---

## 25.6 Idempotency & Safety

Understanding idempotency prevents duplicated charges, double-sent emails, and corrupted data.

### Safe vs Unsafe Methods

**Safe methods** do not modify server state. Calling them has no side effects:
- `GET`, `HEAD`, `OPTIONS`

**Unsafe methods** modify server state:
- `POST`, `PUT`, `PATCH`, `DELETE`

### Idempotent Methods

An operation is idempotent if doing it twice produces the same result as doing it once.

```
GET  /users/123       -> Always returns user 123. Idempotent.
PUT  /users/123       -> Replaces user 123 with the given body. Do it twice, same result. Idempotent.
DELETE /users/123     -> Deletes user 123. Second call gets 404, but server state is the same. Idempotent.

POST /users           -> Creates a new user. Do it twice, you get two users. NOT idempotent.
POST /payments        -> Charges a card. Do it twice, you charge twice. NOT idempotent.
```

### The Idempotency-Key Pattern

`POST` is neither safe nor idempotent. But clients retry failed requests (network timeout, no response received). Without protection, retries cause duplicates.

Stripe popularized the `Idempotency-Key` header:

```http
POST /v1/payments
Idempotency-Key: idem_a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{
  "amount": 5000,
  "currency": "usd",
  "customer": "cus_123"
}
```

**How it works**:

1. Client generates a UUID (or any unique string) and sends it with the request
2. Server checks if this key has been seen before
3. **First time**: Execute the operation, store `key -> response` mapping in the database
4. **Retry**: Return the stored response without re-executing the operation
5. **Keys expire** after 24-48 hours (old enough that retries have stopped, young enough to not fill the database)

### Implementation

Database schema for idempotency keys:

```sql
CREATE TABLE idempotency_keys (
    key          TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    request_path TEXT NOT NULL,
    request_body JSONB,
    response_code INTEGER,
    response_body JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at    TIMESTAMPTZ
);
```

Handler logic (Node.js pseudocode):

```javascript
async function handlePayment(req, res) {
  const idempotencyKey = req.headers['idempotency-key'];

  if (!idempotencyKey) {
    return res.status(400).json({
      error: {
        code: 'MISSING_IDEMPOTENCY_KEY',
        message: 'POST requests require an Idempotency-Key header.'
      }
    });
  }

  // Check for existing result
  const existing = await db.query(
    'SELECT response_code, response_body FROM idempotency_keys WHERE key = $1 AND user_id = $2',
    [idempotencyKey, req.userId]
  );

  if (existing.rows.length > 0) {
    const { response_code, response_body } = existing.rows[0];
    return res.status(response_code).json(response_body);
  }

  // Acquire lock (prevents race condition on parallel retries)
  const locked = await db.query(
    'INSERT INTO idempotency_keys (key, user_id, request_path, request_body, locked_at) ' +
    'VALUES ($1, $2, $3, $4, NOW()) ' +
    'ON CONFLICT (key) DO NOTHING RETURNING key',
    [idempotencyKey, req.userId, req.path, req.body]
  );

  if (locked.rows.length === 0) {
    return res.status(409).json({
      error: {
        code: 'IDEMPOTENCY_KEY_IN_USE',
        message: 'A request with this idempotency key is already being processed.'
      }
    });
  }

  try {
    const result = await processPayment(req.body);
    const responseBody = { data: result };

    await db.query(
      'UPDATE idempotency_keys SET response_code = $1, response_body = $2 WHERE key = $3',
      [201, responseBody, idempotencyKey]
    );

    return res.status(201).json(responseBody);
  } catch (error) {
    const errorBody = {
      error: { code: 'PAYMENT_FAILED', message: error.message }
    };
    await db.query(
      'UPDATE idempotency_keys SET response_code = $1, response_body = $2 WHERE key = $3',
      [400, errorBody, idempotencyKey]
    );
    return res.status(400).json(errorBody);
  }
}
```

**Critical implementation details**:
- Scope idempotency keys per user/API key — different users can reuse the same key string
- Use database-level locking (INSERT ... ON CONFLICT) to handle parallel retries
- Store error responses too — a failed request should return the same error on retry, not re-execute
- Set a TTL on keys (48 hours is standard)

---

## 25.7 Authentication Patterns for APIs

### API Keys

The simplest authentication method. Appropriate for server-to-server communication.

```http
GET /v1/users
Authorization: Bearer sk_live_abc123def456
```

Design principles:
- **Prefixed keys**: `sk_live_` (secret, live), `sk_test_` (secret, test), `pk_live_` (publishable, live). The prefix tells developers immediately what the key is for and prevents accidental misuse
- **Scoped keys**: Allow creating keys with limited permissions

```json
{
  "name": "Reporting Dashboard",
  "permissions": ["read:orders", "read:users"],
  "expires_at": "2026-06-01T00:00:00Z"
}
```

Response:

```json
{
  "id": "key_123",
  "name": "Reporting Dashboard",
  "key": "sk_live_abc123def456",
  "permissions": ["read:orders", "read:users"],
  "expires_at": "2026-06-01T00:00:00Z",
  "created_at": "2025-12-01T00:00:00Z"
}
```

**Important**: The full key is only shown once (at creation time). Store the hash, not the plaintext.

### Key Rotation Without Downtime

Support two active keys simultaneously during rotation:

```json
{
  "new_key": {
    "id": "key_456",
    "key": "sk_live_new789xyz"
  },
  "old_key": {
    "id": "key_123",
    "expires_at": "2025-12-04T00:00:00Z"
  }
}
```

Both keys work during the grace period. The client updates to the new key, then the old key expires.

### OAuth 2.0 for Delegated Access

When third-party apps need to access user data on their behalf:

```
Step 1 — Redirect user to authorization endpoint:
GET https://api.example.com/oauth/authorize?
    response_type=code&
    client_id=app_123&
    redirect_uri=https://myapp.com/callback&
    scope=read:orders+write:orders&
    state=random_csrf_token&
    code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
    code_challenge_method=S256

Step 2 — User approves, redirect back with code:
GET https://myapp.com/callback?code=auth_code_xyz&state=random_csrf_token

Step 3 — Exchange code for tokens:
POST https://api.example.com/oauth/token
{
  "grant_type": "authorization_code",
  "code": "auth_code_xyz",
  "redirect_uri": "https://myapp.com/callback",
  "client_id": "app_123",
  "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
}
```

Token response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_token": "rt_abc123",
  "scope": "read:orders write:orders"
}
```

**Always use PKCE** (Proof Key for Code Exchange) for authorization code flow — even for confidential clients, it adds a layer of protection against code interception.

### JWT Access Tokens

Short-lived (15 minutes), stateless verification:

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key_2025_01"
  },
  "payload": {
    "sub": "usr_123",
    "iss": "https://api.example.com",
    "aud": "https://api.example.com",
    "exp": 1706285700,
    "iat": 1706284800,
    "scope": "read:orders write:orders",
    "client_id": "app_123"
  }
}
```

**Verification** on every request:
1. Decode the JWT (do not trust it yet)
2. Verify the signature using the public key (fetched from JWKS endpoint)
3. Check `exp` — reject if expired
4. Check `iss` — must match your issuer
5. Check `aud` — must match your API
6. Check `scope` — must include the required scope for this endpoint

No database lookup needed — that is the point of JWTs. The trade-off is that you cannot revoke a specific JWT before it expires (unless you add a blocklist, which defeats the purpose).

---

## 25.8 Webhook Design

Webhooks are how your API pushes events to consumers instead of consumers polling.

### Payload Design

```json
{
  "id": "evt_abc123",
  "type": "order.completed",
  "api_version": "2025-01-15",
  "created_at": "2025-06-15T10:30:00Z",
  "data": {
    "object": {
      "id": "ord_456",
      "status": "completed",
      "total": 5000,
      "currency": "usd",
      "customer_id": "cus_789",
      "completed_at": "2025-06-15T10:30:00Z"
    }
  }
}
```

Design rules:
- **Include an event ID** (`evt_abc123`) — consumers use it for deduplication
- **Include the event type** (`order.completed`) — consumers route on this
- **Include enough data to act on** — do not force consumers to make a follow-up API call for basic information
- **Do not include sensitive data** unless necessary — webhooks go over the public internet. Include IDs and let consumers fetch sensitive details via authenticated API calls if needed
- **Include the API version** — so consumers know which schema to expect

### Event Type Naming

Use `resource.action` format with dots:

```
order.created
order.updated
order.completed
order.cancelled
payment.succeeded
payment.failed
payment.refunded
customer.created
customer.updated
customer.deleted
invoice.sent
invoice.paid
invoice.overdue
```

Let consumers subscribe to specific events:

```json
{
  "url": "https://myapp.com/webhooks/example",
  "events": ["order.completed", "payment.failed"],
  "secret": "whsec_auto_generated"
}
```

### Signature Verification

Every webhook request must be signed so consumers can verify it came from you.

**Server (sending)**:

```javascript
const crypto = require('crypto');

function signWebhookPayload(secret, payload) {
  const timestamp = Math.floor(Date.now() / 1000);
  const signedPayload = timestamp + '.' + JSON.stringify(payload);
  const signature = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  return { timestamp, signature };
}
```

The webhook request includes:

```http
POST /webhooks/example
Content-Type: application/json
X-Webhook-Signature: t=1718444400,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
X-Webhook-ID: evt_abc123
```

**Consumer (receiving)**:

```javascript
function verifyWebhookSignature(secret, signatureHeader, rawBody) {
  const parts = Object.fromEntries(
    signatureHeader.split(',').map(p => p.split('='))
  );

  const timestamp = parseInt(parts.t);
  const receivedSignature = parts.v1;

  // Reject if timestamp is too old (prevent replay attacks)
  const fiveMinutesAgo = Math.floor(Date.now() / 1000) - 300;
  if (timestamp < fiveMinutesAgo) {
    throw new Error('Webhook timestamp too old');
  }

  const signedPayload = timestamp + '.' + rawBody;
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  if (!crypto.timingSafeEqual(
    Buffer.from(receivedSignature),
    Buffer.from(expectedSignature)
  )) {
    throw new Error('Invalid webhook signature');
  }

  return true;
}
```

**Important**: Use `crypto.timingSafeEqual` (constant-time comparison) to prevent timing attacks.

### Delivery Guarantees and Retries

Webhooks guarantee **at-least-once** delivery, never exactly-once. Your retry policy:

```
Attempt 1: Immediate
Attempt 2: 1 minute later
Attempt 3: 5 minutes later
Attempt 4: 30 minutes later
Attempt 5: 2 hours later
Attempt 6: 8 hours later
Attempt 7: 24 hours later
Give up, mark as failed.
```

A successful delivery is any `2xx` response. Anything else (including `3xx` redirects) is a failure that triggers a retry.

**Consumer-side idempotency**: Because consumers may receive the same event multiple times, they must deduplicate by event ID:

```javascript
app.post('/webhooks/example', async (req, res) => {
  const event = req.body;

  // Check if already processed
  const processed = await db.query(
    'SELECT id FROM processed_events WHERE event_id = $1',
    [event.id]
  );

  if (processed.rows.length > 0) {
    return res.status(200).json({ received: true });
  }

  await handleEvent(event);

  await db.query(
    'INSERT INTO processed_events (event_id, processed_at) VALUES ($1, NOW())',
    [event.id]
  );

  return res.status(200).json({ received: true });
});
```

### Failure Handling

After exhausting retries:
- Move the event to a **dead letter queue (DLQ)** for manual inspection
- Notify the webhook owner (email or dashboard alert)
- After N consecutive failures (e.g., 50), **disable the webhook** and notify the owner
- Provide a **retry button** in the dashboard for manual re-delivery
- Provide an **event replay** endpoint so consumers can request re-delivery of any past event:

```
POST /v1/webhooks/:id/replay
{
  "event_id": "evt_abc123"
}
```

### Webhook Testing

Make webhooks easy to develop against:
- **Test endpoint**: `POST /v1/webhooks/:id/test` sends a synthetic event to the webhook URL
- **Event log**: Dashboard showing recent deliveries, response status, response body, and timing
- **CLI tool**: `example-cli listen` opens a tunnel from localhost to receive webhooks during development (like `stripe listen`)

---

## 25.9 Rate Limiting & Quotas

Rate limiting protects your API from abuse and ensures fair usage across consumers.

### Rate Limit Headers

Include these headers on **every** response, not just `429` responses:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1706284800
```

| Header | Meaning |
|--------|---------|
| `X-RateLimit-Limit` | Maximum requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `Retry-After` | Seconds until the client should retry (only on 429) |

### When Rate Limited

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706284800
Retry-After: 45
```

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Retry after 45 seconds.",
    "retry_after": 45,
    "limit": 1000,
    "window": "1 minute"
  }
}
```

### Tiered Rate Limits

Different limits for different plans:

```json
{
  "free": {
    "requests_per_minute": 60,
    "requests_per_day": 1000
  },
  "pro": {
    "requests_per_minute": 600,
    "requests_per_day": 50000
  },
  "enterprise": {
    "requests_per_minute": 6000,
    "requests_per_day": 500000
  }
}
```

### Per-Endpoint Limits

Not all endpoints are equal. Write operations are more expensive than reads:

```json
{
  "GET /users":             { "per_minute": 600 },
  "POST /users":            { "per_minute": 60 },
  "GET /reports/generate":  { "per_minute": 5 },
  "POST /bulk/import":      { "per_hour": 10 }
}
```

### Rate Limiting Algorithms

**Token Bucket** (most common):
- Bucket fills at a steady rate (e.g., 10 tokens/second)
- Each request costs one token
- Bucket has a maximum size (burst limit)
- Request is rejected when bucket is empty

**Sliding Window**:
- Count requests in a rolling time window
- More accurate than fixed windows (avoids burst at window boundaries)

**Implementation with Redis** (sliding window):

```javascript
async function checkRateLimit(apiKey, limit, windowSeconds) {
  const key = 'ratelimit:' + apiKey;
  const now = Date.now();
  const windowStart = now - (windowSeconds * 1000);

  const pipeline = redis.pipeline();
  pipeline.zremrangebyscore(key, 0, windowStart);
  pipeline.zadd(key, now, now + '-' + Math.random());
  pipeline.zcard(key);
  pipeline.expire(key, windowSeconds);

  const results = await pipeline.exec();
  const requestCount = results[2][1];

  return {
    allowed: requestCount <= limit,
    remaining: Math.max(0, limit - requestCount),
    reset: Math.ceil((windowStart + windowSeconds * 1000) / 1000)
  };
}
```

### Burst Allowance

Allow short bursts above the sustained rate. A limit of "100 requests/minute with burst of 20" means:
- Sustained: 100 requests evenly spread over a minute
- Burst: Up to 20 requests in a single second, as long as you are under the per-minute limit

Token bucket naturally supports this — the bucket size is the burst limit, the fill rate is the sustained limit.

### Graceful Degradation

When your API is under extreme load, consider degrading gracefully instead of hard-rejecting:
- Return cached responses for read endpoints
- Queue write operations for async processing (return `202 Accepted`)
- Reduce payload size (skip optional fields)
- Increase latency (add a delay) instead of rejecting

---

## 25.10 SDK & Client Library Design

A great API with a terrible SDK still feels terrible to use.

### Generate, Then Customize

Start with auto-generation from your OpenAPI spec, then heavily customize:

```yaml
# openapi.yaml (excerpt)
paths:
  /v1/users:
    get:
      operationId: listUsers
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
        - name: after
          in: query
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserList'
```

Auto-generated code gives you the skeleton. Manually add:
- Idiomatic error handling
- Pagination iterators
- Retry logic
- Request/response logging

### Language-Idiomatic Design

The SDK should feel native to the language.

**Python SDK**:

```python
import example

client = example.Client(api_key="sk_live_abc123")

# Create a user
user = client.users.create(
    name="Alice",
    email="alice@example.com",
    metadata={"team": "engineering"}
)
print(user.id)  # "usr_789" — attribute access, not dict access

# List users with auto-pagination
for user in client.users.list(limit=100):
    print(user.name)  # Automatically fetches next pages

# Error handling with typed exceptions
try:
    user = client.users.retrieve("usr_nonexistent")
except example.NotFoundError as e:
    print(f"User not found: {e.message}")
except example.AuthenticationError as e:
    print(f"Bad API key: {e.message}")
except example.RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except example.APIError as e:
    print(f"API error: {e.code} - {e.message}")
```

**TypeScript SDK**:

```typescript
import Example from 'example';

const client = new Example({ apiKey: 'sk_live_abc123' });

// Create a user — fully typed
const user = await client.users.create({
  name: 'Alice',
  email: 'alice@example.com',
  metadata: { team: 'engineering' },
});
console.log(user.id); // string, fully typed

// Auto-pagination with async iterators
for await (const user of client.users.list({ limit: 100 })) {
  console.log(user.name);
}

// Error handling
try {
  await client.users.retrieve('usr_nonexistent');
} catch (err) {
  if (err instanceof Example.NotFoundError) {
    console.log('Not found:', err.message);
  } else if (err instanceof Example.RateLimitError) {
    console.log('Retry after', err.retryAfter, 'seconds');
  }
}
```

### Built-In Retries

The SDK should retry transient failures automatically:

```python
client = example.Client(
    api_key="sk_live_abc123",
    max_retries=3,          # Default: 2
    timeout=30,             # Seconds
)

# Retries automatically on:
# - Network errors (connection reset, DNS failure)
# - 429 Too Many Requests (respects Retry-After)
# - 500, 502, 503, 504 (server errors)
#
# Does NOT retry on:
# - 400, 401, 403, 404, 422 (client errors — retrying won't help)
```

Retry with exponential backoff and jitter:

```
Attempt 1: immediate
Attempt 2: 500ms + random(0-250ms)
Attempt 3: 1000ms + random(0-500ms)
Attempt 4: 2000ms + random(0-1000ms)
```

### Configuration

```typescript
const client = new Example({
  apiKey: 'sk_live_abc123',
  baseURL: 'https://api.example.com',    // Override for testing
  timeout: 30_000,                         // Request timeout (ms)
  maxRetries: 2,                           // Automatic retries
  httpClient: myCustomFetch,               // Custom HTTP client
  defaultHeaders: {                        // Extra headers on every request
    'X-Custom-Header': 'value',
  },
  logger: console,                         // Enable request/response logging
});
```

### Debug Logging

When enabled, log requests and responses so developers can debug integration issues:

```
[Example SDK] POST https://api.example.com/v1/users
[Example SDK] Request body: {"name":"Alice","email":"alice@example.com"}
[Example SDK] Response 201 (143ms)
[Example SDK] Response body: {"id":"usr_789","name":"Alice",...}
```

Off by default. Enabled by passing a logger or setting an environment variable (`EXAMPLE_LOG=debug`).

---

## 25.11 API Documentation

Documentation is the UI of your API. If developers cannot figure out how to use your API in five minutes, they will use a competitor's.

### OpenAPI as Source of Truth

Your OpenAPI spec should be the single source of truth that generates:
- Interactive documentation (Swagger UI, Redoc, Stoplight)
- Client SDKs
- Server stubs
- Request validation middleware
- Mock servers for testing

```yaml
openapi: 3.1.0
info:
  title: Example API
  version: '2025-01-15'
  description: The Example API for managing users and orders.

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://sandbox.api.example.com/v1
    description: Sandbox

paths:
  /users:
    get:
      summary: List all users
      operationId: listUsers
      tags:
        - Users
      parameters:
        - name: limit
          in: query
          description: Number of users to return (max 100)
          schema:
            type: integer
            default: 20
            minimum: 1
            maximum: 100
        - name: after
          in: query
          description: Cursor for pagination (from previous response)
          schema:
            type: string
      responses:
        '200':
          description: A paginated list of users
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/User'
                  pagination:
                    $ref: '#/components/schemas/CursorPagination'
              example:
                data:
                  - id: "usr_123"
                    name: "Alice"
                    email: "alice@example.com"
                    created_at: "2025-01-15T10:30:00Z"
                pagination:
                  next_cursor: "eyJpZCI6InVzcl8xMjMifQ"
                  has_more: true
        '401':
          $ref: '#/components/responses/Unauthorized'

components:
  schemas:
    User:
      type: object
      required: [id, name, email, created_at]
      properties:
        id:
          type: string
          description: Unique user identifier
          example: "usr_123"
        name:
          type: string
          description: Full name
          example: "Alice Smith"
        email:
          type: string
          format: email
          description: Email address
          example: "alice@example.com"
        created_at:
          type: string
          format: date-time
          description: When the user was created
          example: "2025-01-15T10:30:00Z"
```

### What Great API Docs Include

1. **Quick start guide**: From zero to first successful API call in under 5 minutes

```bash
# Install
npm install example-sdk

# First API call
curl https://api.example.com/v1/users \
  -H "Authorization: Bearer sk_test_abc123"
```

2. **Authentication guide**: How to get an API key, how to authenticate, test vs live mode

3. **Code examples for every endpoint** in at least 3 languages (cURL, Python, TypeScript, Ruby, Go, Java)

4. **Error reference**: Every error code with cause, example response, and how to fix it

5. **Changelog**: Every change, dated, with migration guides for breaking changes

6. **Interactive explorer**: Try endpoints directly in the browser with your API key

7. **Webhooks guide**: How to set up, verify, and handle webhooks

8. **Rate limits page**: Every limit, per plan, per endpoint

9. **Status page**: Current API status and historical uptime

10. **SDKs and libraries**: Installation instructions and links, prominently placed

### API Collections

Provide pre-built collections for popular API clients:

```json
{
  "info": {
    "name": "Example API",
    "description": "Complete API collection with authentication pre-configured"
  },
  "auth": {
    "type": "bearer",
    "bearer": [{ "key": "token", "value": "{{api_key}}" }]
  },
  "variable": [
    { "key": "base_url", "value": "https://api.example.com/v1" },
    { "key": "api_key", "value": "sk_test_YOUR_KEY_HERE" }
  ],
  "item": [
    {
      "name": "Users",
      "item": [
        {
          "name": "List Users",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/users?limit=20"
          }
        },
        {
          "name": "Create User",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/users",
            "body": {
              "mode": "raw",
              "raw": "{\"name\": \"Alice\", \"email\": \"alice@example.com\"}"
            }
          }
        }
      ]
    }
  ]
}
```

---

## 25.12 Real-World API Analysis

### Stripe: The Gold Standard

Stripe is widely considered the best-designed API in the industry. What they get right:

**Date-based versioning**: Every breaking change gets a date-based version. Your API key defaults to the version when it was created. You upgrade when you are ready.

```http
POST /v1/charges
Stripe-Version: 2025-01-15
Authorization: Bearer sk_live_abc123
```

**Idempotency keys**: Every mutating operation supports idempotency, preventing double charges:

```http
POST /v1/payments
Idempotency-Key: unique-request-id-123
```

**Excellent error messages**:

```json
{
  "error": {
    "type": "card_error",
    "code": "card_declined",
    "decline_code": "insufficient_funds",
    "message": "Your card has insufficient funds.",
    "param": "source",
    "doc_url": "https://stripe.com/docs/error-codes/card-declined"
  }
}
```

Every error includes a `doc_url` linking directly to documentation for that specific error.

**Expandable objects**: Instead of N+1 API calls, expand related objects inline:

```
GET /v1/charges/ch_123?expand[]=customer&expand[]=invoice
```

**Test mode**: Every feature works identically in test mode with `sk_test_` keys, including webhooks.

### GitHub: Best-in-Class Pagination and Rate Limiting

**Link-header pagination** (RFC 8288):

```http
HTTP/1.1 200 OK
Link: <https://api.github.com/user/repos?page=3&per_page=100>; rel="next",
      <https://api.github.com/user/repos?page=50&per_page=100>; rel="last"
```

Clients parse the `Link` header for `next`, `prev`, `first`, and `last` URLs. No URL construction needed.

**Rate limiting transparency**:

```http
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4987
X-RateLimit-Reset: 1706284800
X-RateLimit-Resource: core
```

GitHub separates rate limits by resource type (`core`, `search`, `graphql`) with different limits per category.

**Webhooks with fine-grained events**: Over 200 event types, each triggerable individually. The webhook configuration UI shows recent deliveries with full request/response details for debugging.

**Conditional requests**: GitHub supports `ETag` and `If-None-Match` — requests that return `304 Not Modified` do not count against your rate limit.

```http
GET /repos/octocat/Hello-World
If-None-Match: "abc123"

HTTP/1.1 304 Not Modified
X-RateLimit-Remaining: 4987
```

### Twilio: Error Documentation Links

Every Twilio error includes a numeric error code and a direct link to documentation:

```json
{
  "code": 21211,
  "message": "The 'To' number +1555BADNUMBER is not a valid phone number.",
  "more_info": "https://www.twilio.com/docs/errors/21211",
  "status": 400
}
```

The documentation page for each error code includes:
- What the error means
- Common causes
- Step-by-step fix instructions
- Related errors

This is one of the highest-ROI investments in developer experience — it turns a frustrating error into a solvable problem.

**Webhook verification**: Twilio provides helper methods in every SDK:

```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(auth_token)
is_valid = validator.validate(url, post_vars, signature)
```

### Slack: Event Subscriptions and Interactive Components

**Event API with challenge verification**: When you register a webhook URL, Slack sends a challenge to verify you own it:

```json
{
  "type": "url_verification",
  "challenge": "abc123xyz",
  "token": "deprecated_field"
}
```

You respond with:

```json
{
  "challenge": "abc123xyz"
}
```

**Socket Mode**: For development, Slack offers WebSocket-based event delivery — no public URL needed. This eliminates the ngrok/tunnel setup that makes webhook development painful.

**Interactive components**: Slack's API design allows composing rich UI (buttons, menus, modals) that send payloads back to your server. The payload includes the full interaction context:

```json
{
  "type": "block_actions",
  "trigger_id": "12345.98765.abcd2358fdea",
  "user": { "id": "U12345", "name": "alice" },
  "actions": [
    {
      "type": "button",
      "action_id": "approve_request",
      "block_id": "request_block",
      "value": "req_789"
    }
  ]
}
```

**Rate limiting with Retry-After**: Slack's rate limits include a `Retry-After` header and their SDKs automatically queue and retry requests — developers never need to implement retry logic manually.

---

## Quick Reference

### API Design Checklist

```
[ ] Consistent naming convention throughout (snake_case or camelCase)
[ ] Consistent response envelope ({"data": ..., "pagination": ...})
[ ] Consistent error format with machine-readable codes
[ ] Plural nouns for resources (/users, /orders)
[ ] HTTP methods used correctly (GET=read, POST=create, etc.)
[ ] Pagination on every list endpoint
[ ] Rate limit headers on every response
[ ] Authentication documented in quick start guide
[ ] Idempotency-Key support on POST endpoints
[ ] Request ID in every response (success and error)
[ ] OpenAPI spec maintained as source of truth
[ ] Webhook signatures with HMAC-SHA256
[ ] SDK available in top 3 languages of your audience
[ ] Every error code documented with examples and fixes
[ ] Versioning strategy chosen and documented
[ ] Deprecation policy published
```

### HTTP Status Code Cheat Sheet

```
200 OK                    — Success (GET, PATCH, PUT, DELETE with body)
201 Created               — Resource created (POST)
202 Accepted              — Queued for processing
204 No Content            — Success, no body (DELETE)
400 Bad Request           — Malformed request
401 Unauthorized          — Not authenticated
403 Forbidden             — Authenticated but not authorized
404 Not Found             — Resource doesn't exist
409 Conflict              — State conflict (duplicate, version mismatch)
422 Unprocessable Entity  — Validation failed
429 Too Many Requests     — Rate limited (include Retry-After)
500 Internal Server Error — Bug (include request_id, never stack traces)
502 Bad Gateway           — Upstream service error
503 Service Unavailable   — Temporarily unavailable
```

### Response Envelope Template

```json
{
  "data": { "id": "usr_123", "name": "Alice" },
  "request_id": "req_abc123"
}
```

```json
{
  "data": [
    { "id": "usr_123", "name": "Alice" },
    { "id": "usr_456", "name": "Bob" }
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6InVzcl80NTYifQ",
    "has_more": true
  },
  "request_id": "req_abc123"
}
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request body contains invalid fields.",
    "details": [
      { "field": "email", "issue": "Must be a valid email address." }
    ],
    "request_id": "req_abc123",
    "doc_url": "https://docs.example.com/errors/VALIDATION_ERROR"
  }
}
```

---

**Key Takeaway**: The best APIs are boring. They are predictable, consistent, and well-documented. Every endpoint works the way you expect it to after learning the first one. Invest in error messages, pagination, and SDK quality — these are what developers interact with every day, and they determine whether developers choose your product or a competitor's.

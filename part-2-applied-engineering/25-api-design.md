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

There is a moment every developer has had. You crack open a new API, read the first endpoint, and feel a small spark of delight — everything just makes sense. Then there is the other moment: forty minutes of trial and error, four different error messages, zero useful docs, and the quiet rage of someone who just wants to create a user account and go home.

The difference between those two experiences is not magic. It is craft. API design is one of the highest-leverage skills an engineer can develop because your API is a product that other developers use every day, for years. A poorly designed API multiplies frustration across every team that integrates with you. A well-designed one lets your users build things you never imagined.

This chapter is about designing APIs that people are genuinely glad to use — from consistent error handling to pagination patterns to webhook verification. Not specification compliance, but craft.

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
- GraphQL Deep Dive

### Related Chapters
- Ch 3 (REST/gRPC/GraphQL architecture)
- Ch 5 (authentication/authorization)
- Ch 21 (HTTP protocol details)
- Ch 23 (system design case studies)
- Ch 34 (spec-driven development — write the OpenAPI contract first)

---

## 25.1 API Design Principles

A great API is like a well-designed tool — you pick it up and immediately know how to use it. A hammer does not need a manual. Neither should your `POST /users` endpoint.

The best APIs feel invisible. Developers pick them up quickly, make fewer mistakes, and rarely need to consult the docs after the first session. That does not happen by accident — it comes from a small set of principles applied relentlessly, starting before you write a single line of implementation code.

### Consistency Is the Foundation

Imagine learning to drive a car where the turn signal sometimes controls the windshield wipers, and the gas pedal sometimes applies the brakes. That is what an inconsistent API feels like. Every inconsistency is a surprise, and surprises in APIs cost developers time and trust.

Every endpoint should feel like it belongs to the same API. If you use `created_at` on one resource, do not switch to `createdAt` on another. If `GET /users` returns a list with a `data` wrapper, then `GET /orders` should do the same.

Consistency applies to:
- **Naming conventions** — pick `snake_case` or `camelCase` and commit
- **Response shapes** — every list endpoint returns `{ "data": [...], "pagination": {...} }`
- **Error formats** — every error follows the same structure (covered in 25.3)
- **URL patterns** — pluralized nouns, consistent nesting depth
- **Query parameter names** — `limit` everywhere, not `limit` on one endpoint and `page_size` on another

A style guide written before the first endpoint is built pays for itself a hundred times over. Think of it as the constitution of your API — everything that comes after must be consistent with it, not because you like rules, but because your users deserve predictability.

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

This is not laziness on the developer's part — it is the best sign that your API design is working. Predictability means the mental model they built from the first resource transfers to every other resource instantly. That is free knowledge you gave them.

The moment you break the pattern — one resource uses `PUT` instead of `PATCH`, another uses `/create` instead of `POST` — developers lose trust and start double-checking everything. Every exception is a tiny tax on every developer who touches your API, forever.

### Resource-Oriented Design

Think of your API as a collection of things in the world, not a list of operations the server knows how to perform. Resources are nouns; HTTP methods are the verbs.

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

The verb-in-URL style is a legacy of RPC thinking — it treats every operation as a remote function call. REST thinking treats every operation as a state change on a resource. REST wins for public APIs because HTTP clients already understand what `GET`, `POST`, `PATCH`, and `DELETE` mean. You are not inventing a new protocol; you are participating in one that already exists.

There are exceptions — actions that do not map cleanly to CRUD. For these, use a verb as a sub-resource:

```
POST /orders/:id/cancel
POST /users/:id/verify-email
POST /payments/:id/refund
```

Keep these to a minimum. If you find yourself creating many action endpoints, your resource model probably needs rethinking. "Cancel" belongs on the order; "refund" belongs on the payment. If you have ten action endpoints for one resource, you probably have ten resources hiding inside what you called one.

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

Here is the discipline that separates APIs people love from APIs people endure: design the API before writing a single line of implementation code.

This is not theoretical. When you write the implementation first, you end up with an API that reflects your database schema, your internal method names, and the order in which you wrote things. That API serves your implementation, not your users. API-first flips this: your API serves your users, and your implementation serves your API.

The sequence (and read Ch 34 for the spec-driven workflow in depth):

1. Write the OpenAPI spec (or at minimum, sketch the endpoints, request/response shapes, and error codes on paper)
2. Review the spec with API consumers (frontend team, partner developers, your future self)
3. Generate mocks from the spec so consumers can start building against it immediately
4. Implement the server
5. Validate the implementation against the spec in CI

API-first catches design mistakes when they are cheap to fix — before anyone has written code against a bad contract. A bad API design you discover in a spec review takes five minutes to fix. The same mistake discovered after three teams have integrated against it takes months of migration work and breaks developer trust in the process.

### Backward Compatibility Is the Number One Rule

Once an API is in production, breaking it is the most expensive thing you can do. Every breaking change forces every consumer to update their code, test, and redeploy. Multiply that by hundreds of integrators and you understand why Stripe has not broken their API in over a decade.

That is not an accident of history. Stripe made a deliberate engineering decision that backward compatibility was not optional — it was a core product value. Every new engineer learns this on day one. The result is that developers trust Stripe's API in a way that is almost impossible to achieve with APIs that break their contracts.

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

When in doubt, it is a breaking change. Treat it as one. The cost of being too cautious here is zero. The cost of being too aggressive is paid by every developer who integrates with you.

---

## 25.2 REST API Conventions

REST conventions are not arbitrary rules. They are the accumulated wisdom of thousands of APIs and millions of developer-hours spent figuring out what works. When you follow them, developers can bring their existing mental model to your API. When you break them, you force every user to learn your exceptions.

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

Deep nesting is a smell. If you find yourself building `/companies/:id/departments/:id/teams/:id/members/:id`, you probably want a `/team-members` resource that you filter by `team_id`. Flat is better than nested, beyond two levels.

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

In practice, most APIs use `PATCH` for updates because clients rarely want to send the full object. A user settings page should not have to know about every field on the user record just to update the display name. `PATCH` respects this; `PUT` does not.

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

There is no universally correct answer here, just the answer that is right for your audience. The important thing is consistency — not which style you pick, but that you pick one and never deviate from it.

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

This is especially valuable for mobile clients on slow connections, and for dashboards that need to display a list of records without loading every field. A user list showing name, email, and avatar does not need to transfer the user's billing address, metadata blob, and preferences on every row.

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

The partial success decision deserves emphasis: if a developer sends 50 records and one is invalid, failing the whole batch is cruel. They have to figure out which one failed, fix it, and resubmit. Return per-item results and let them handle failures surgically.

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

The sub-resource pattern has a hidden implication: it tells the client that the resource lives in a hierarchy. If an order can be retrieved in any context — by user, by date, by status — make it a top-level resource you filter. If an order genuinely cannot exist without belonging to a user, the nesting communicates that relationship explicitly.

---

## 25.3 Error Handling

Here is where most APIs fail their developers. Not in the happy path — the happy path usually works fine. In the error cases, when the developer is already frustrated and confused, your API either helps them or twists the knife.

Think about the experience from the developer's side: they are staring at a response, it is not what they expected, and the clock is ticking. A great error response is like a helpful colleague — it tells you exactly what went wrong, where, and how to fix it. A bad one is a `500 Internal Server Error` with no body, a cryptic code nobody explains, or a raw database exception pasted into JSON.

The quality of your error messages is directly proportional to how much developers trust your API.

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
- **`code`**: Machine-readable error code. Clients switch on this, not the HTTP status. Design these codes like an enum — stable, clear, documented
- **`message`**: Human-readable summary for developers reading logs. Write it for a person who is having a bad day
- **`details`**: Array of specific issues (especially for validation errors) — cover all of them, not just the first
- **`request_id`**: Unique ID for this request — essential for debugging. Include it in every response, success or error
- **`doc_url`**: Link to documentation for this error type (Twilio does this brilliantly — see 25.12)

The `doc_url` field is criminally underused. Linking an error directly to its documentation turns a frustrating moment into a solved problem. The developer does not have to search; they just click.

### HTTP Status Code Usage

Use status codes correctly. This is not optional — it is part of the HTTP protocol contract, and developers who know HTTP will be confused and annoyed when you violate it.

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
- Using `200` for everything and putting the real status in the body — clients cannot use HTTP-level error handling, monitoring is broken, and retry logic cannot function
- Using `500` for validation errors — that is your bug, not the client's
- Using `403` when you mean `401` — "you aren't logged in" is `401`, "you're logged in but can't do this" is `403`
- Using `404` to mean "this feature isn't built yet" — that is `501 Not Implemented`

The `401` vs `403` confusion has real consequences. A client that receives `403` might assume it has the right credentials and start rotating keys or asking users to re-authenticate. The right behavior on `401` (re-authenticate) is completely different from the right behavior on `403` (request elevated permissions or accept access is denied). Confusing them breaks client error handling logic.

### Return ALL Validation Errors

Never return only the first validation error. This is the most common and most infuriating mistake in API design. The developer will fix it, resubmit, get the next error, fix that, resubmit, and hate your API by the third round trip.

Every round trip is 30 seconds of wasted time, compounding frustration, and eroding trust. Just tell them everything that is wrong, all at once, up front.

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

The good response takes the same amount of server work (you validated all the fields anyway) and saves the developer multiple round trips. This is free goodwill you are leaving on the table if you do not implement it.

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

Without `Retry-After`, clients have two bad options: hammer your API with retries (making the problem worse) or implement arbitrary backoff logic (fragile and inconsistent). Give them the information they need to do the right thing.

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

The error documentation is often the most-read page in your developer docs, because developers read it when something is broken and they are motivated. Make it excellent.

---

## 25.4 Pagination Patterns

Any endpoint that returns a list needs pagination. No exceptions. "There will never be more than a few" is the most dangerous lie in software engineering — data grows, users grow, time passes, and the query that returned 12 records in 2025 returns 120,000 in 2027.

Pagination is not just a performance feature. It is a contract with your API consumers about how data access works. The pagination style you choose has real consequences for usability, performance, and correctness that compound over time.

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

The instability problem is subtle but real: imagine a user loading page 2 of results while someone else deletes a record. The item that was at the top of page 2 just shifted to page 1, and page 2 now shows what was previously page 2's second item. The user either sees a duplicate or misses an item entirely — and they have no way to know. For UI that requires stable, consistent paging under concurrent writes, offset pagination is a trap.

### Cursor-Based (Keyset) Pagination

The production-grade approach — and the one you should reach for by default:

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

The opaque cursor is a feature, not a bug. By encoding the cursor as base64 and treating it as a black box, you preserve the freedom to change your pagination implementation without breaking clients. Start with a simple `{ id: "usr_120" }` cursor; upgrade to a more complex implementation later, clients never know the difference.

### When to Use Which

| Scenario | Use |
|----------|-----|
| Admin dashboard with page numbers | Offset (acceptable for internal tools) |
| Infinite scroll UI | Cursor |
| Public API consumed by other services | Cursor |
| Data export / sync | Cursor |
| Small dataset (fewer than 10K rows) | Either works fine |
| Large dataset (more than 100K rows) | Cursor (offset will degrade) |

The general rule: cursor pagination for public APIs and anything data-intensive, offset pagination for internal admin interfaces where the data is small and simplicity matters more than performance.

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

The `id` is included as a tiebreaker — if two records share the same `created_at` timestamp, you need a unique field to establish a stable order. Always include your primary key as the final sort column for this reason.

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

APIs change. Features evolve, mistakes get corrected, business requirements shift. The question is not whether your API will change, but how you manage those changes without breaking the developers who built their products on top of yours.

Versioning is a design decision with real consequences for the trust relationship between you and your API consumers. Get it right and developers build confidently on your platform knowing you will not pull the rug out from under them. Get it wrong and every release is a gamble that breaks someone's integration.

### URL Versioning

```
GET /v1/users
GET /v2/users
```

**Pros**: Explicit, easy to understand, easy to route, easy to deprecate. Most common approach.

**Cons**: Clients must update URLs to adopt a new version. You maintain multiple route handlers.

This is the right default choice for most APIs. URL versioning is obvious — anyone can tell which version they are calling by looking at the URL. That clarity makes it easy to deprecate old versions (just turn off the route), communicate which version you are building against (the URL is in every code snippet), and route traffic to the right implementation.

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

Header versioning is beloved in REST purist circles and used in practice mostly by developers who regret it. The inability to paste a versioned URL into a browser or share it in a Slack message is a bigger daily friction point than it sounds.

### Query Parameter Versioning

```
GET /users?version=2
```

**Pros**: Simple. Easy to test.

**Cons**: Mixes infrastructure concerns (versioning) with business concerns (filtering). Gets lost among other query parameters.

### Date-Based Versioning (Stripe's Approach)

This is the gold standard for APIs with many consumers — and the approach that most elegantly solves the problem of keeping existing integrations stable while allowing the API to evolve.

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

The payoff of Stripe's approach is visible in their developer community: integrations from 2012 still work. Developers who learned the API in 2015 can still use their existing knowledge. That stability is a competitive moat that is extraordinarily hard to replicate once you've broken trust.

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

The "new enum value" case is worth calling out: if your clients are using exhaustive switches or if-else chains and do not have a default/unknown case, adding a new enum value breaks them. Good SDK design handles this by always including an `UNKNOWN` fallback, but API design has to account for clients that do not.

### Deprecation Workflow

Deprecating an endpoint well is as much an art as deprecating it at all. Rush it and you burn developer trust. Handle it with care and you maintain it.

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

The `Sunset` header (RFC 8594) is underused and wonderful. It gives developers programmatic access to the deprecation timeline. A well-written HTTP client can log warnings when it sees `Deprecation: true` and tell developers exactly when the endpoint will stop working. This turns a vague "we're deprecating this someday" into an actionable reminder with a deadline.

---

## 25.6 Idempotency & Safety

Idempotency is one of those concepts that sounds academic until you are debugging why a customer got charged twice. Then it becomes very concrete, very fast.

The story plays out the same way every time: a client sends a payment request, the network times out before the response arrives, the client retries (as it should), and the payment processes twice. The customer sees two charges. Support gets a ticket. Engineers investigate. Everyone is unhappy. The fix requires one well-placed database insert and a design decision made before you ship.

Understanding idempotency is what separates APIs that handle failure gracefully from APIs that cause data corruption when the network misbehaves.

### Safe vs Unsafe Methods

**Safe methods** do not modify server state. Calling them has no side effects:
- `GET`, `HEAD`, `OPTIONS`

**Unsafe methods** modify server state:
- `POST`, `PUT`, `PATCH`, `DELETE`

Safety is a promise to clients: "calling this endpoint will never change anything." Clients can cache safe methods, retry them without worry, and call them from preflight requests. Never use `GET` to modify state — it breaks this promise and breaks any infrastructure (caches, load balancers, monitoring) that treats `GET` as safe.

### Idempotent Methods

An operation is idempotent if doing it twice produces the same result as doing it once. Think of it as: the second call is safe, the outcome is the same as if you only called it once.

```
GET  /users/123       -> Always returns user 123. Idempotent.
PUT  /users/123       -> Replaces user 123 with the given body. Do it twice, same result. Idempotent.
DELETE /users/123     -> Deletes user 123. Second call gets 404, but server state is the same. Idempotent.

POST /users           -> Creates a new user. Do it twice, you get two users. NOT idempotent.
POST /payments        -> Charges a card. Do it twice, you charge twice. NOT idempotent.
```

Idempotency is not the same as returning the same response — it means producing the same server-side outcome. `DELETE /users/123` called twice might return `200` the first time and `404` the second, but the server state after both calls is identical: user 123 does not exist.

### The Idempotency-Key Pattern

`POST` is neither safe nor idempotent. But clients retry failed requests — network timeouts happen, load balancers drop connections, services restart mid-request. Without protection, retries cause duplicates.

Stripe popularized the `Idempotency-Key` header, and it is the right pattern for any POST that creates resources or triggers side effects like payments, emails, or notifications:

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

The key insight: the server remembers what it did and gives clients the same answer. The client cannot tell whether the operation executed or whether it got a cached response — and it does not need to know. From the client's perspective, the payment either went through or it did not, and the server says which.

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

The locking detail matters: without it, two parallel retries arriving simultaneously can both see "key not found," both attempt to create the record, and race to execute the operation. The `ON CONFLICT DO NOTHING` pattern means only one wins; the other gets a `409` and knows to wait for the first to complete.

---

## 25.7 Authentication Patterns for APIs

Authentication is the front door to your API. If it is confusing, insecure, or painful to implement, developers will get stuck before they even see your endpoints. Make it effortless and secure.

### API Keys

The simplest authentication method. Appropriate for server-to-server communication.

```http
GET /v1/users
Authorization: Bearer sk_live_abc123def456
```

Design principles:
- **Prefixed keys**: `sk_live_` (secret, live), `sk_test_` (secret, test), `pk_live_` (publishable, live). The prefix tells developers immediately what the key is for and prevents accidental misuse. If a key leaks in a screenshot or a commit, the prefix tells you at a glance how bad the situation is
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

**Important**: The full key is only shown once (at creation time). Store the hash, not the plaintext. Tell developers explicitly that this is their only chance to copy it — do not make them discover it the hard way.

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

Both keys work during the grace period. The client updates to the new key, then the old key expires. Without this pattern, key rotation requires a maintenance window where nothing works — which means developers avoid rotating keys, which means your security posture degrades over time. Make the secure path easy.

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

**Always use PKCE** (Proof Key for Code Exchange) for authorization code flow — even for confidential clients, it adds a layer of protection against code interception. PKCE is not optional in 2026; it is the baseline.

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

No database lookup needed — that is the point of JWTs. The trade-off is that you cannot revoke a specific JWT before it expires (unless you add a blocklist, which defeats the purpose). This is why short expiry times matter: a 15-minute token that leaks is much less dangerous than a 30-day token that leaks.

---

## 25.8 Webhook Design

Webhooks are how your API pushes events to consumers instead of consumers polling. They shift the burden from consumer to producer: instead of a thousand clients making a thousand API calls every minute asking "did anything change?", your server proactively tells them when something does.

Done well, webhooks feel like magic — your integration just knows when things happen. Done poorly, they are a reliability nightmare of dropped events, missed deliveries, and race conditions.

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
- **Include an event ID** (`evt_abc123`) — consumers use it for deduplication, and it is essential for your own debugging
- **Include the event type** (`order.completed`) — consumers route on this, like a switch statement over a network
- **Include enough data to act on** — do not force consumers to make a follow-up API call for basic information. If you send `order.completed` with just an order ID, every consumer has to make another API call to get the order details. That doubles the latency and complexity on their end
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

Per-event subscriptions let consumers receive only what they care about. A billing service should not have to process every `customer.updated` event just to catch `payment.failed`. Selective subscriptions also reduce the load on your delivery infrastructure — fewer events delivered to consumers who would ignore them anyway.

### Signature Verification

Every webhook request must be signed so consumers can verify it came from you. An unsigned webhook endpoint is a security hole — anyone who discovers the URL can send fake events and trigger actions in your consumer's system.

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

**Important**: Use `crypto.timingSafeEqual` (constant-time comparison) to prevent timing attacks. A naive string comparison leaks information about how many characters matched before the comparison failed — over many requests, an attacker can reconstruct the expected signature bit by bit. Constant-time comparison removes this information channel.

The timestamp in the signature is also not decoration. Without it, an attacker can capture a valid webhook payload and replay it later. The 5-minute timestamp window means replayed events are rejected — they are too old.

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

**Consumer-side idempotency**: Because consumers may receive the same event multiple times (at-least-once means exactly that), they must deduplicate by event ID:

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

This pattern is the webhook equivalent of idempotency keys on the send side. The event ID is your deduplication key; the `processed_events` table is your memory. A well-behaved webhook consumer is idempotent — receiving the same event twice produces the same outcome as receiving it once.

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

Event replay is one of the highest-value webhook features you can build. When a consumer's server was down for maintenance and missed events, or when a bug in their handler caused silent failures, replay lets them recover without any manual data reconciliation. It turns a disaster into a minor inconvenience.

### Webhook Testing

Make webhooks easy to develop against:
- **Test endpoint**: `POST /v1/webhooks/:id/test` sends a synthetic event to the webhook URL
- **Event log**: Dashboard showing recent deliveries, response status, response body, and timing
- **CLI tool**: `example-cli listen` opens a tunnel from localhost to receive webhooks during development (like `stripe listen`)

The local development story for webhooks is often the most painful part of the experience. A developer working on their laptop needs a way to receive webhooks without deploying to a public server first. If your CLI tool solves this problem (the way `stripe listen` does), it removes a significant barrier to getting started with your API.

---

## 25.9 Rate Limiting & Quotas

Rate limiting protects your API from abuse and ensures fair usage across consumers. Done right, it is nearly invisible — developers build within their limits and never hit them accidentally. Done poorly, it is a constant source of friction, mysterious failures, and angry support tickets.

The key insight: rate limiting is only as good as the information you give clients about it. If they cannot see their limits and remaining allowance, they cannot build against them intelligently.

### Rate Limit Headers

Include these headers on **every** response, not just `429` responses — this is the detail most APIs get wrong:

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

Sending these headers on every successful response (not just on 429) lets clients pace themselves. A well-written SDK can monitor `X-RateLimit-Remaining` and add a small delay when it drops below a threshold, preventing a 429 entirely. That is only possible if the headers are always present.

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

Expose these per-endpoint limits in your documentation so developers know what to expect before they hit the wall.

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

Token bucket naturally supports this — the bucket size is the burst limit, the fill rate is the sustained limit. This distinction matters for real usage patterns: most legitimate API clients make bursts of requests (loading a dashboard, processing a batch), then go quiet for a while. Allowing short bursts without penalizing them reflects how good developers actually write integrations.

### Graceful Degradation

When your API is under extreme load, consider degrading gracefully instead of hard-rejecting:
- Return cached responses for read endpoints
- Queue write operations for async processing (return `202 Accepted`)
- Reduce payload size (skip optional fields)
- Increase latency (add a delay) instead of rejecting

A slow response is often better than a rejected one — at least it confirms the request was received and gives the client something to work with.

---

## 25.10 SDK & Client Library Design

A great API with a terrible SDK still feels terrible to use. The SDK is the API from the developer's perspective — most developers never call your REST endpoints directly. They install your SDK, read a few examples, and go. If the SDK is bad, the API is bad, no matter how well-designed the underlying HTTP contract is.

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

The generated code handles the mechanical work — request construction, response parsing, authentication headers. The manual work is what makes the SDK feel native. A Python SDK that forces you to do `response['data'][0]['name']` instead of `user.name` is a generated SDK that was not finished.

### Language-Idiomatic Design

The SDK should feel native to the language. A developer using your Python SDK should feel like they are writing Python, not translating REST calls into Python syntax.

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

Notice the typed exceptions — `NotFoundError`, `RateLimitError`, `AuthenticationError`. This lets developers catch specific error types instead of parsing error codes from a generic exception. The pattern maps directly to how good Python and TypeScript developers write error handling, so it feels natural rather than foreign.

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

The jitter is not decoration — it prevents thundering herd problems where every SDK client retries simultaneously after a server hiccup, amplifying the problem rather than giving the server time to recover.

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

Off by default. Enabled by passing a logger or setting an environment variable (`EXAMPLE_LOG=debug`). This single feature cuts debugging time dramatically — when something is not working, a developer can enable request logging and see exactly what the SDK is sending and receiving. Without it, they have to intercept network traffic or write print statements.

---

## 25.11 API Documentation

Documentation is the UI of your API. If developers cannot figure out how to use your API in five minutes, they will use a competitor's. This is not hyperbole — developer time is expensive, attention is finite, and if the first five minutes of experience with your API are frustrating, most developers will not give it five more.

The best documentation does not just describe the API — it teaches developers how to think about it. What are the core concepts? What are the typical workflows? What are the gotchas? It anticipates questions and answers them before they arise.

### OpenAPI as Source of Truth

Your OpenAPI spec should be the single source of truth that generates everything else — and this connects directly to the spec-driven workflow in Ch 34, where the spec comes first and the implementation follows:
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

The quick start is the most important page in your documentation. Most developers read it before anything else. If they can get a successful API call in five minutes, they are invested. If they cannot, they leave.

2. **Authentication guide**: How to get an API key, how to authenticate, test vs live mode

3. **Code examples for every endpoint** in at least 3 languages (cURL, Python, TypeScript, Ruby, Go, Java)

4. **Error reference**: Every error code with cause, example response, and how to fix it

5. **Changelog**: Every change, dated, with migration guides for breaking changes

6. **Interactive explorer**: Try endpoints directly in the browser with your API key

7. **Webhooks guide**: How to set up, verify, and handle webhooks

8. **Rate limits page**: Every limit, per plan, per endpoint

9. **Status page**: Current API status and historical uptime

10. **SDKs and libraries**: Installation instructions and links, prominently placed — not buried in the footer

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

A Postman or Insomnia collection lets developers explore your API interactively without writing a single line of code. For many developers, this is how they first understand the API's structure and test their understanding. Lower the barrier to exploration and more developers will invest in your platform.

---

## 25.12 Real-World API Analysis

The best way to develop taste in API design is to study APIs that have earned the love of developers. Each of the examples below has been battle-tested at massive scale. There is something to learn from each one.

### Stripe: The Gold Standard

Stripe is widely considered the best-designed API in the industry. Not just "pretty good" — genuinely excellent, in a way that has shaped how the whole industry thinks about API design. The things they get right are worth studying carefully.

**Date-based versioning**: Every breaking change gets a date-based version. Your API key defaults to the version when it was created. You upgrade when you are ready — not when Stripe decides it is time. This single design decision is responsible for the trust that allows Stripe to power payments for millions of businesses without those businesses worrying that an API update will break their checkout flow.

```http
POST /v1/charges
Stripe-Version: 2025-01-15
Authorization: Bearer sk_live_abc123
```

**Idempotency keys**: Every mutating operation supports idempotency, preventing double charges. This is not a nice-to-have for a payments API — it is the engineering foundation that makes Stripe safe:

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

Every error includes a `doc_url` linking directly to documentation for that specific error. A developer who sees a card declined error knows immediately what it means, why it happened, and how to handle it. That is not an accident — it is the result of deliberate investment in the developer experience.

**Expandable objects**: Instead of N+1 API calls, expand related objects inline:

```
GET /v1/charges/ch_123?expand[]=customer&expand[]=invoice
```

**Test mode**: Every feature works identically in test mode with `sk_test_` keys, including webhooks. You can test your entire integration end-to-end without touching production. This is harder to build than it sounds — maintaining full feature parity between test and live modes requires significant engineering discipline — and it pays off in developer confidence.

### GitHub: Best-in-Class Pagination and Rate Limiting

**Link-header pagination** (RFC 8288):

```http
HTTP/1.1 200 OK
Link: <https://api.github.com/user/repos?page=3&per_page=100>; rel="next",
      <https://api.github.com/user/repos?page=50&per_page=100>; rel="last"
```

Clients parse the `Link` header for `next`, `prev`, `first`, and `last` URLs. No URL construction needed. GitHub was following an existing RFC here rather than inventing something new, which is exactly the right instinct — use standards when they exist.

**Rate limiting transparency**:

```http
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4987
X-RateLimit-Reset: 1706284800
X-RateLimit-Resource: core
```

GitHub separates rate limits by resource type (`core`, `search`, `graphql`) with different limits per category. This matters for tools that need to make both search queries and core API calls — they can budget each independently.

**Webhooks with fine-grained events**: Over 200 event types, each triggerable individually. The webhook configuration UI shows recent deliveries with full request/response details for debugging.

**Conditional requests**: GitHub supports `ETag` and `If-None-Match` — requests that return `304 Not Modified` do not count against your rate limit.

```http
GET /repos/octocat/Hello-World
If-None-Match: "abc123"

HTTP/1.1 304 Not Modified
X-RateLimit-Remaining: 4987
```

The 304 not counting against rate limits is a subtle but powerful incentive for clients to implement proper caching. Good design aligns incentives: the behavior that is good for GitHub (reduced server load) is also good for API consumers (rate limit preservation). When your API design makes the right thing easy and rewarding, developers will do the right thing.

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

This is one of the highest-ROI investments in developer experience — it turns a frustrating error into a solvable problem with a clear path forward. Compare this to the alternative: a cryptic error code, a frantic search through documentation, a Stack Overflow search, maybe a support ticket. The linked doc URL collapses all of that into a single click.

**Webhook verification**: Twilio provides helper methods in every SDK:

```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(auth_token)
is_valid = validator.validate(url, post_vars, signature)
```

The SDK handling webhook verification is another example of the same principle: put the complexity in the library, not in every integration that uses it.

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

**Socket Mode**: For development, Slack offers WebSocket-based event delivery — no public URL needed. This eliminates the ngrok/tunnel setup that makes webhook development painful. Any developer who has spent an afternoon fighting ngrok to test a webhook handler will immediately appreciate this. Socket Mode removes an entire class of setup friction from the development experience.

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

## 25.13 GraphQL Deep Dive

GraphQL is not a replacement for REST — it is an alternative with different tradeoffs. When those tradeoffs align with your needs (multiple client types, complex data relationships, rapid frontend iteration), GraphQL shines. When they do not, it adds complexity for no gain. This section covers the depth you need to use GraphQL well.

The architecture decision between REST and GraphQL lives in Ch 3. This section assumes you've made the choice and want to do GraphQL right.

### Schema Design Best Practices

The schema is the contract between your backend and every client that consumes it. Getting it right matters more than any resolver optimization. A poorly designed schema is technically correct and practically painful; a well-designed schema makes writing client code feel natural.

**Schema-first vs code-first approach.**

In the schema-first approach, you write the `.graphql` schema file by hand and then implement resolvers that match it. This works well when the schema is a collaboration artifact — designers, frontend developers, and backend engineers agree on the shape before anyone writes code. Tools like Apollo Server and graphql-tools support this natively.

In the code-first approach, you define types in your programming language (using decorators, classes, or builder functions) and the schema is generated from your code. Libraries like Nexus (JS/TS), Strawberry (Python), and gqlgen (Go) follow this pattern. Code-first is better when type safety across the stack matters more than a human-readable schema file, or when the schema is owned entirely by the backend team.

**Use schema-first** when: multiple teams collaborate on the schema, you want the schema to be the source of truth, you are doing API-first design.
**Use code-first** when: a single team owns the API, you want compile-time type checking, your schema closely mirrors your domain models.

**Naming conventions.** PascalCase for types (`User`, `OrderStatus`, `CreateUserInput`). camelCase for fields and arguments (`firstName`, `createdAt`, `pageSize`). SCREAMING_SNAKE_CASE for enum values (`PENDING`, `CONFIRMED`, `SHIPPED`). These are not arbitrary — they are the conventions the entire GraphQL ecosystem expects, and violating them confuses every developer who touches your API.

**Design from the client's perspective, not the database.** Your schema should reflect what clients need, not how your tables are structured. If the client thinks in terms of a `UserProfile` with `recentOrders`, expose that — even if internally it requires joining three tables. The schema is a product interface, not a database view.

**Use domain language, not CRUD language.** Name mutations after what they mean in the business domain:

```graphql
# Good — domain language
mutation {
  approveOrder(orderId: "ord_123") { ... }
  cancelSubscription(subscriptionId: "sub_456") { ... }
  archiveProject(projectId: "proj_789") { ... }
}

# Bad — generic CRUD
mutation {
  updateOrder(id: "ord_123", input: { status: APPROVED }) { ... }
  updateSubscription(id: "sub_456", input: { active: false }) { ... }
  updateProject(id: "proj_789", input: { archived: true }) { ... }
}
```

Domain-specific mutations are self-documenting, easier to authorize (you can check `canApproveOrder` instead of parsing what fields changed), and produce cleaner audit logs.

**Input types for mutations.** Always use dedicated input types rather than inline arguments:

```graphql
input CreateUserInput {
  name: String!
  email: String!
  role: UserRole
}

input UpdateUserInput {
  name: String
  email: String
  role: UserRole
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
}
```

Notice that `CreateUserInput` has required fields while `UpdateUserInput` makes everything optional — this is the standard pattern. Separate input types per mutation keep your schema clean as it grows.

**Enums for finite sets.** Whenever a field has a known, finite set of values, use an enum:

```graphql
enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}

enum UserRole {
  ADMIN
  MEMBER
  VIEWER
}
```

Enums give you schema-level validation, autocomplete in tooling, and documentation for free. Do not use `String` where an enum belongs.

**Interfaces and Union types for polymorphism.** Use interfaces when types share common fields:

```graphql
interface Node {
  id: ID!
}

interface Timestamped {
  createdAt: DateTime!
  updatedAt: DateTime!
}

type User implements Node & Timestamped {
  id: ID!
  name: String!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

Use unions when types are fundamentally different but can appear in the same context:

```graphql
union SearchResult = User | Order | Product

type Query {
  search(query: String!): [SearchResult!]!
}
```

Clients use inline fragments (`... on User { name }`) to handle each type. This is far cleaner than a single type with dozens of nullable fields.

**Custom scalars.** The built-in scalars (`String`, `Int`, `Float`, `Boolean`, `ID`) are not enough for real applications. Define custom scalars for domain-specific types:

```graphql
scalar DateTime    # ISO 8601 format
scalar URL         # Valid URL string
scalar Email       # Valid email address
scalar JSON        # Arbitrary JSON blob (use sparingly)
```

Custom scalars add validation at the schema level and communicate intent clearly. Every GraphQL server library supports custom scalar definitions with parsing and serialization logic.

**Nullable vs non-nullable fields.** In GraphQL, fields are nullable by default. Add `!` (non-null) only when you can guarantee the field will always have a value. Be conservative — marking a field as non-null and then encountering a case where it is null causes the error to propagate up to the nearest nullable parent, potentially nulling out an entire object. Start nullable, tighten later.

### The N+1 Problem and DataLoader

The N+1 problem is GraphQL's most notorious performance pitfall — and the most common reason GraphQL APIs become slow. Consider a query that fetches a list of orders, each with its associated user:

```graphql
query {
  orders {
    id
    total
    user {
      id
      name
    }
  }
}
```

A naive implementation resolves `orders` with one query (fetching 50 orders), then resolves `user` for each order individually — 50 separate queries. That is 1 + 50 = 51 database calls for what should be 2.

The first time you encounter this in production, it is usually because a query that ran fine in development with 10 records starts timing out in production with 10,000. The fix is architectural, not incidental.

**The DataLoader pattern** solves this by batching and deduplicating requests within a single tick of the event loop. Instead of resolving each `user` field immediately, DataLoader collects all the user IDs requested in the current execution frame, makes a single batched query, and distributes the results. Instead of resolving each `user` field immediately, DataLoader collects all the user IDs requested in the current execution frame, makes a single batched query, and distributes the results.

```javascript
const DataLoader = require('dataloader')

// Create a loader that batches user lookups
const userLoader = new DataLoader(async (userIds) => {
  // One query for ALL requested users
  const users = await db.users.findMany({
    where: { id: { in: userIds } }
  })
  // IMPORTANT: return results in the same order as the input IDs
  return userIds.map(id => users.find(u => u.id === id) || null)
})

// In the resolver
const resolvers = {
  Order: {
    user: (order) => userLoader.load(order.userId)
  }
}
```

Now those 50 individual user lookups become a single `SELECT * FROM users WHERE id IN (...)` query. Total database calls: 2 instead of 51.

**Critical rule: create DataLoader instances per request.** DataLoader caches results for the lifetime of the instance. If you share a loader across requests, user A might see data that was loaded for user B (stale cache), or you might serve data that the requesting user is not authorized to see. Every incoming request should get a fresh set of loaders:

```javascript
// In your context factory
function createContext({ req }) {
  return {
    loaders: {
      user: new DataLoader(batchUsers),
      product: new DataLoader(batchProducts),
      order: new DataLoader(batchOrders),
    },
    currentUser: authenticateRequest(req),
  }
}
```

**DataLoader in different frameworks:**
- **Apollo Server (JS/TS)**: Pass loaders via the context object as shown above. The `dataloader` npm package is the standard.
- **Mercurius (Fastify)**: Built-in loader support via the `loaders` option — you define batch functions and Mercurius handles the DataLoader lifecycle automatically.
- **Strawberry (Python)**: Use `strawberry.dataloader.DataLoader` which integrates with Python's `asyncio`. Same batching concept, Python-native API.
- **gqlgen (Go)**: Use the `graph/dataloader` pattern with per-request middleware. The `dataloaden` code generator creates type-safe loaders.

### Subscriptions

Subscriptions are GraphQL's answer to real-time data. While queries and mutations follow the request-response pattern, subscriptions establish a persistent connection where the server pushes updates to the client.

```graphql
type Subscription {
  messageReceived(channelId: ID!): Message!
  orderStatusChanged(orderId: ID!): Order!
  notificationCreated(userId: ID!): Notification!
}
```

**Transport.** Subscriptions use WebSockets. The current standard protocol is `graphql-ws` (maintained by the `graphql-ws` npm package). The older `subscriptions-transport-ws` is deprecated but still widely deployed — if you are starting fresh, use `graphql-ws`. The two are not compatible, so clients and servers must agree on the protocol.

**Use cases where subscriptions excel:**
- **Live chat**: messages appear instantly for all participants
- **Notifications**: real-time alerts without polling
- **Real-time dashboards**: metrics, stock prices, live scores
- **Collaborative editing**: multiple users editing the same document (though for heavy collaboration, CRDTs are more appropriate than raw subscriptions)

**Implementation pattern.** Subscriptions require a pub/sub system to decouple the event producer from the subscription resolver:

```javascript
// Using a simple in-memory PubSub (fine for single-server dev)
const { PubSub } = require('graphql-subscriptions')
const pubsub = new PubSub()

// Mutation that publishes an event
const resolvers = {
  Mutation: {
    sendMessage: async (_, { channelId, text }, ctx) => {
      const message = await db.messages.create({ channelId, text, authorId: ctx.userId })
      pubsub.publish(`MESSAGE_RECEIVED_${channelId}`, { messageReceived: message })
      return message
    }
  },
  Subscription: {
    messageReceived: {
      subscribe: (_, { channelId }) =>
        pubsub.asyncIterator(`MESSAGE_RECEIVED_${channelId}`)
    }
  }
}
```

**Scaling subscriptions horizontally.** In-memory pub/sub only works on a single server. When you scale to multiple instances, an event published on server A needs to reach subscribers connected to server B. You need an external pub/sub backbone:
- **Redis Pub/Sub**: Simple, low-latency, good for most cases. Use `graphql-redis-subscriptions`.
- **Kafka**: When you need durability, replay, and high throughput. Heavier to operate.
- **Google Cloud Pub/Sub / AWS SNS**: Managed options for cloud-native deployments.

**When NOT to use subscriptions.** Subscriptions add operational complexity (WebSocket connections are stateful, harder to load balance, break through some proxies). If your data changes infrequently (every 30+ seconds), polling with a simple query is simpler and more reliable. Use subscriptions when latency matters and updates are frequent.

### Pagination: Relay Connection Spec

GraphQL does not prescribe a pagination approach, but the Relay Connection Specification has become the de facto standard — even for APIs that have nothing to do with the Relay client framework.

```graphql
type Query {
  users(first: Int, after: String, last: Int, before: String): UserConnection!
}

type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

**Why this is the standard:**

1. **Cursor-based** — no page drift. Unlike offset-based pagination where inserting a record shifts everything, cursors are stable pointers.
2. **Bidirectional** — `first`/`after` for forward pagination, `last`/`before` for backward pagination.
3. **Consistent** — every paginated field in your schema has the same shape. Clients can write generic pagination logic once.
4. **Edge metadata** — the `edge` layer lets you attach metadata to the relationship itself (e.g., `role` on a `TeamMemberEdge`, `addedAt` on a `PlaylistTrackEdge`).

**Cursor encoding.** Cursors should be opaque to clients — they should not parse or construct them. The common approach is to base64-encode the primary key or sort value:

```javascript
// Encoding
const cursor = Buffer.from(`id:${user.id}`).toString('base64')
// "aWQ6dXNyXzEyMw==" — opaque to the client

// Decoding (server-side only)
const decoded = Buffer.from(cursor, 'base64').toString()
// "id:usr_123" — server extracts the key
```

Do not use raw offsets as cursors — they defeat the purpose of cursor-based pagination (stability under inserts/deletes). Use the primary key, a timestamp, or a composite sort key.

**Usage example:**

```graphql
# First page
query { users(first: 20) { edges { node { id name } cursor } pageInfo { hasNextPage endCursor } } }

# Next page — pass endCursor as "after"
query { users(first: 20, after: "aWQ6dXNyXzIw") { edges { node { id name } cursor } pageInfo { hasNextPage endCursor } } }
```

### Federation & Schema Stitching

As your GraphQL API grows, a single monolithic schema becomes a bottleneck — one team's changes block another's deployments, the codebase becomes unwieldy, and ownership boundaries blur. This is the same architectural pressure that drives microservices in REST APIs, and the solution in GraphQL is federation.

**Schema Stitching (legacy approach).** Schema stitching merges multiple GraphQL schemas into one at the gateway level. The gateway downloads each sub-schema, merges them (resolving conflicts manually), and exposes a unified graph. This was the first solution to the "big schema" problem, but it has serious downsides:
- **Brittle**: adding a field in one service can conflict with another
- **Gateway owns the logic**: cross-service resolution logic lives in the gateway, not the services
- **Hard to maintain**: as the number of services grows, the merge configuration becomes unmanageable

Schema stitching still works for simple cases (two or three schemas, one team), but for anything larger, federation is the answer.

**Apollo Federation (modern approach).** Federation flips the model: each service (called a **subgraph**) owns its part of the graph and declares how its types connect to types in other subgraphs. A **gateway** (or **router**) composes the subgraphs into a unified schema and routes queries to the right services.

```graphql
# Users subgraph
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}

type Query {
  user(id: ID!): User
}
```

```graphql
# Orders subgraph — extends the User type from another service
type User @key(fields: "id") {
  id: ID! @external
  orders: [Order!]!
}

type Order @key(fields: "id") {
  id: ID!
  total: Float!
  status: OrderStatus!
}
```

Key directives:
- **`@key`**: Defines the primary key for an entity, used to fetch it across subgraph boundaries
- **`@external`**: Marks a field as owned by another subgraph (needed for reference)
- **`@requires`**: Declares that a field needs data from external fields to resolve (e.g., `@requires(fields: "weight")` to calculate shipping cost)
- **`@provides`**: Indicates that a resolver provides additional fields on a returned type

**Subgraph architecture.** Each team owns their subgraph: the Users team owns user types and resolvers, the Orders team owns order types and resolvers. Teams deploy independently. The gateway recomposes on deploy (Apollo Router does this automatically via managed federation with Apollo Studio, or you can self-host with supergraph composition).

**When to federate:**
- Multiple teams need to contribute to the same graph
- The schema is large enough that a single codebase is a bottleneck
- Teams need to deploy their part of the API independently
- You need different languages/runtimes for different parts of the graph

**When NOT to federate:**
- Small team (under ~8 engineers working on the API)
- Single service backing the entire API
- Early-stage product where the schema is still changing rapidly
- Adding federation is premature complexity — you can always migrate later

### Security

GraphQL's flexibility is a double-edged sword. Clients can construct arbitrary queries, which means a malicious or careless client can easily overwhelm your server. REST has natural limits — every endpoint does a bounded amount of work. GraphQL has no such limits by default, which means you have to add them explicitly.

**Query depth limiting.** Deeply nested queries can cause exponential database load:

```graphql
# Malicious query — each level triggers new resolver calls
query {
  user(id: "1") {
    friends {
      friends {
        friends {
          friends {
            friends { name }
          }
        }
      }
    }
  }
}
```

Set a maximum depth (typically 7-10 levels). Libraries like `graphql-depth-limit` reject queries that exceed the threshold before execution.

**Query complexity analysis.** Depth alone is not enough — a shallow but wide query can be just as expensive:

```graphql
# Shallow but expensive — fetches thousands of records
query {
  users(first: 1000) {
    orders(first: 1000) {
      items(first: 1000) { name }
    }
  }
}
```

Assign a cost to each field (scalars = 0 or 1, lists = multiplier based on the `first`/`last` argument) and reject queries whose total cost exceeds a budget. Apollo Server and graphql-query-complexity support this out of the box.

**Persisted queries.** In production, you may not want clients to send arbitrary query strings at all. With persisted queries, the client sends a hash (e.g., SHA-256 of the query), and the server looks up the corresponding pre-approved query from a registry. This:
- Prevents arbitrary query attacks entirely
- Reduces bandwidth (hashes are tiny compared to query strings)
- Allows you to analyze and approve queries before they hit production

**Rate limiting.** Standard request-count rate limiting does not work well for GraphQL because one request can range from trivial to catastrophic in cost. Rate limit by **query complexity** — each client gets a complexity budget per time window, and each query deducts its computed cost.

**Authentication in context.** Pass the auth token via HTTP headers (typically `Authorization: Bearer <token>`), validate it in your context factory, and attach the authenticated user to the context object. Every resolver can then access `ctx.currentUser`:

```javascript
function createContext({ req }) {
  const token = req.headers.authorization?.replace('Bearer ', '')
  const user = token ? verifyToken(token) : null
  return { currentUser: user }
}
```

**Field-level authorization.** Do not rely solely on top-level query authorization. Check permissions in individual resolvers:

```javascript
const resolvers = {
  User: {
    email: (user, _, ctx) => {
      // Only the user themselves or an admin can see the email
      if (ctx.currentUser?.id === user.id || ctx.currentUser?.role === 'ADMIN') {
        return user.email
      }
      return null
    },
    salary: (user, _, ctx) => {
      if (ctx.currentUser?.role !== 'ADMIN') {
        throw new ForbiddenError('Not authorized to view salary')
      }
      return user.salary
    }
  }
}
```

For complex authorization, use a schema directive (`@auth(requires: ADMIN)`) or a library like GraphQL Shield that lets you define a permission layer declaratively.

### Performance

**Query batching.** Clients can send multiple GraphQL operations in a single HTTP request as a JSON array. The server executes them all and returns an array of responses. This reduces HTTP round trips when a page needs data from multiple independent queries.

**Automatic Persisted Queries (APQ).** A performance optimization where the client sends a query hash first. If the server recognizes the hash, it executes the cached query. If not, the server responds with a "not found" error, and the client retries with the full query string — which the server then caches for next time. This eliminates the bandwidth cost of sending large query strings on every request after the first.

**Response caching.** Caching GraphQL responses is harder than REST because every request goes to the same URL (`POST /graphql`). You cannot use standard HTTP caching. Instead:
- Cache by query hash + variables + auth context
- Use CDN-level caching only for public, non-personalized queries
- Use server-side caching (Redis) keyed on the normalized query
- Apollo Server supports `@cacheControl` directives to set per-field TTLs

**`@defer` and `@stream` directives (incremental delivery).** These directives let the server send critical data immediately and stream less important data as it becomes available:

```graphql
query {
  user(id: "123") {
    id
    name
    ... @defer {
      # Sent later — maybe requires a slow DB call
      analyticsData {
        totalOrders
        lifetimeValue
      }
    }
  }
}
```

`@defer` works on fragments (send the fragment's data when ready). `@stream` works on lists (send list items incrementally as they resolve). Both require server and client support — Apollo, Relay, and urql have varying levels of support.

**Fragment colocation.** Keep GraphQL fragments next to the components that use them. Each component declares exactly what data it needs:

```javascript
// UserAvatar.jsx
export const USER_AVATAR_FRAGMENT = gql`
  fragment UserAvatar on User {
    id
    avatarUrl
    name
  }
`

// ParentComponent.jsx — composes the fragment
const GET_USER = gql`
  query GetUser($id: ID!) {
    user(id: $id) {
      ...UserAvatar
      email
      createdAt
    }
  }
  ${USER_AVATAR_FRAGMENT}
`
```

This ensures components fetch only what they need, makes data dependencies explicit, and enables tooling (like Relay's compiler) to optimize queries automatically.

### GraphQL vs REST Decision Framework

Not every API should be GraphQL, and not every API should be REST. Use this framework to decide:

| Factor | Choose REST | Choose GraphQL |
|--------|-------------|----------------|
| **Clients** | One client type, simple needs | Multiple clients with different data needs |
| **Caching** | Standard HTTP caching is sufficient | Custom caching needed or acceptable |
| **Team** | Backend-driven, API-first | Frontend-driven, rapid iteration |
| **Real-time** | SSE/WebSocket added separately | Subscriptions built into the schema |
| **File upload** | Multipart form data (native HTTP) | Needs multipart request spec extension |
| **Tooling** | Universal, massive ecosystem | Growing but smaller ecosystem |
| **Learning curve** | Low | Medium-high |
| **Over/under-fetching** | Managed via endpoint design | Solved by client-specified queries |
| **API evolution** | Versioned endpoints | Schema evolution with deprecation |

**The honest answer for most teams**: if you have a single frontend and a straightforward CRUD API, REST is simpler and you will move faster. If you have a mobile app, a web app, and a third-party API all consuming the same backend, and each needs different slices of the same data, GraphQL pays for itself quickly. Many production systems use both — REST for simple CRUD and webhooks, GraphQL for complex data-fetching needs.

---

**Key Takeaway**: The best APIs are not the ones with the most features — they are the ones that make developers productive immediately and keep working reliably for years. That means investing in the things that are easy to skip: error messages, pagination, idempotency, SDK quality, documentation. These are what developers interact with every day. They determine whether developers build on your platform or someone else's, whether they recommend your API or complain about it, whether they come back for your next product or look elsewhere.

Design every API like it will outlive you. Because it will.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M11: REST API Design](../course/modules/loop-1/L1-M11-rest-api-design.md)** — Design and implement TicketPulse's core REST API with proper resource modeling, versioning, and pagination
- **[L1-M12: Error Handling That Doesn't Suck](../course/modules/loop-1/L1-M12-error-handling.md)** — Build an error response format for TicketPulse that gives clients enough context to recover without exposing internals
- **[L2-M36: API Gateway & BFF](../course/modules/loop-2/L2-M36-api-gateway-and-bff.md)** — Add an API gateway in front of TicketPulse's services and build a Backend-for-Frontend tailored to the mobile client
- **[L3-M72: GraphQL API](../course/modules/loop-3/L3-M72-graphql-api.md)** — Expose TicketPulse's event and ticket data through a GraphQL API and learn where GraphQL's trade-offs hurt you in production

### Quick Exercises

1. **Audit one of your existing API endpoints against the Richardson Maturity Model: does it use nouns for resources, HTTP verbs correctly, and hypermedia links? Write down which level it's at and what it would take to reach Level 3.**
2. **Add idempotency keys to one write endpoint: generate a key on the client, store it server-side with the result, and verify that replaying the same request returns the cached response instead of creating a duplicate.**
3. **Review your error responses — pick three recent 4xx or 5xx errors from your logs and ask: would a developer who has never seen this API know what went wrong and how to fix it? Rewrite the ones that fail this test.**

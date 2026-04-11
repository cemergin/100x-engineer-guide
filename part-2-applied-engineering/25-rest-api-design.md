<!--
  CHAPTER: 25
  TITLE: REST API Design
  PART: II — Applied Engineering
  PREREQS: Chapter 3
  KEY_TOPICS: REST API design, error handling, pagination, versioning, idempotency, API-first design
  DIFFICULTY: Intermediate
  UPDATED: 2026-04-10
-->

# Chapter 25: REST API Design

> **Part II — Applied Engineering** | Prerequisites: Chapter 3 | Difficulty: Intermediate

There is a moment every developer has had. You crack open a new API, read the first endpoint, and feel a small spark of delight — everything just makes sense. Then there is the other moment: forty minutes of trial and error, four different error messages, zero useful docs, and the quiet rage of someone who just wants to create a user account and go home.

The difference between those two experiences is not magic. It is craft. API design is one of the highest-leverage skills an engineer can develop because your API is a product that other developers use every day, for years. A poorly designed API multiplies frustration across every team that integrates with you. A well-designed one lets your users build things you never imagined.

This chapter is about designing REST APIs that people are genuinely glad to use — from consistent error handling to pagination patterns to idempotency guarantees. Not specification compliance, but craft.

### In This Chapter
- API Design Principles
- REST API Conventions
- Error Handling
- Pagination Patterns
- Versioning Strategies
- Idempotency & Safety

### Related Chapters
- Ch 3 (REST/gRPC/GraphQL architecture)
- Ch 5 (authentication/authorization)
- Ch 21 (HTTP protocol details)
- Ch 25b (API operations, authentication, webhooks, SDKs, documentation)
- Ch 25c (GraphQL deep dive)
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
- **`doc_url`**: Link to documentation for this error type (Twilio does this brilliantly — see 25b)

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

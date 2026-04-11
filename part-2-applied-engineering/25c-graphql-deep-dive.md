<!--
  CHAPTER: 25c
  TITLE: GraphQL Deep Dive
  PART: II — Applied Engineering
  PREREQS: Chapter 3, Chapter 25
  KEY_TOPICS: GraphQL schema design, N+1 problem, DataLoader, subscriptions, Relay pagination, federation, security, performance
  DIFFICULTY: Intermediate
  UPDATED: 2026-04-10
-->

# Chapter 25c: GraphQL Deep Dive

> **Part II — Applied Engineering** | Prerequisites: Chapter 3, Chapter 25 | Difficulty: Intermediate

GraphQL is not a replacement for REST — it is an alternative with different tradeoffs. When those tradeoffs align with your needs (multiple client types, complex data relationships, rapid frontend iteration), GraphQL shines. When they do not, it adds complexity for no gain.

The architecture decision between REST and GraphQL lives in Ch 3. This chapter assumes you have made the choice and want to do GraphQL right — from schema design to the N+1 problem, from subscriptions to federation, from security hardening to performance optimization.

### In This Chapter
- Schema Design Best Practices
- The N+1 Problem and DataLoader
- Subscriptions
- Pagination: Relay Connection Spec
- Federation & Schema Stitching
- Security
- Performance
- GraphQL vs REST Decision Framework

### Related Chapters
- Ch 3 (REST/gRPC/GraphQL architecture)
- Ch 25 (REST API design principles, conventions, error handling, pagination, versioning, idempotency)
- Ch 25b (API operations, authentication, webhooks, SDKs, documentation)
- Ch 34 (spec-driven development)

---

## 25.13 GraphQL Deep Dive

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

**The DataLoader pattern** solves this by batching and deduplicating requests within a single tick of the event loop. Instead of resolving each `user` field immediately, DataLoader collects all the user IDs requested in the current execution frame, makes a single batched query, and distributes the results.

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

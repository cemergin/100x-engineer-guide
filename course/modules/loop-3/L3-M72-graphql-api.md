# L3-M72: GraphQL API

> ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M36, L3-M67
> Source: Chapter 25 (GraphQL Deep Dive, Pagination, Federation, Security)

## What You'll Learn

- Why TicketPulse needs GraphQL: the over-fetching and under-fetching problem
- Designing a GraphQL schema for TicketPulse: types, queries, mutations, subscriptions
- Solving the N+1 problem with DataLoader
- Implementing Relay-style cursor-based pagination
- Securing GraphQL: query depth limiting, complexity analysis, persisted queries
- GraphQL subscriptions for real-time ticket availability (connecting to the WebSocket work from M67)
- When to use GraphQL vs REST -- and when to use both

## Why This Matters

TicketPulse has a REST API. It works. But the mobile app team keeps asking for changes.

The event list endpoint returns 20 fields per event. The mobile app only needs 5. That is wasted bandwidth on cellular connections. The event detail page needs event data, venue data, and ticket availability -- three separate REST calls that the mobile app chains sequentially, adding latency.

The web app has the opposite problem. The event detail page needs event data plus the organizer's profile plus related events. That requires three REST calls too, but with different fields than the mobile app needs. The backend team is drowning in "can you add an endpoint that returns exactly these fields" requests.

GraphQL solves this by letting the client specify exactly what it needs in a single request. One endpoint, flexible queries, no over-fetching, no under-fetching. But this flexibility comes with real costs: N+1 query problems, security risks from arbitrary queries, and operational complexity.

This module covers how to add GraphQL to TicketPulse correctly.

---

## 1. The Schema

GraphQL is schema-first. The schema defines every type, query, mutation, and subscription your API supports. It is the contract between backend and frontend.

### Design: TicketPulse GraphQL Schema

Stop and design the schema yourself first. What types does TicketPulse need? What queries? What mutations?

Then compare with this reference:

```graphql
# Custom scalars
scalar DateTime
scalar URL

# Enums
enum TicketStatus {
  AVAILABLE
  RESERVED
  SOLD
  CANCELLED
}

enum OrderStatus {
  PENDING
  CONFIRMED
  CANCELLED
  REFUNDED
}

enum EventSortField {
  DATE
  PRICE
  POPULARITY
  RELEVANCE
}

enum SortDirection {
  ASC
  DESC
}

# Core types
type Event {
  id: ID!
  title: String!
  description: String
  genre: String
  date: DateTime!
  venue: Venue!
  ticketTypes: [TicketType!]!
  availableCount: Int!
  totalCapacity: Int!
  imageUrl: URL
  organizer: User!
  isSoldOut: Boolean!
  createdAt: DateTime!
}

type Venue {
  id: ID!
  name: String!
  address: String!
  city: String!
  state: String
  capacity: Int!
  events(first: Int, after: String): EventConnection!
}

type TicketType {
  id: ID!
  name: String!          # "General Admission", "VIP", "Balcony"
  price: Float!
  available: Int!
  total: Int!
}

type Order {
  id: ID!
  event: Event!
  tickets: [Ticket!]!
  totalAmount: Float!
  status: OrderStatus!
  purchasedAt: DateTime!
}

type Ticket {
  id: ID!
  event: Event!
  ticketType: TicketType!
  seatId: String
  status: TicketStatus!
}

type User {
  id: ID!
  name: String!
  email: String!
  orders(first: Int, after: String): OrderConnection!
}

# Relay-style pagination (covered in section 4)
type EventConnection { edges: [EventEdge!]!; pageInfo: PageInfo!; totalCount: Int! }
type EventEdge { node: Event!; cursor: String! }
type OrderConnection { edges: [OrderEdge!]!; pageInfo: PageInfo!; totalCount: Int! }
type OrderEdge { node: Order!; cursor: String! }
type PageInfo { hasNextPage: Boolean!; hasPreviousPage: Boolean!; startCursor: String; endCursor: String }

# Input types
input EventFilterInput {
  genre: String
  city: String
  dateFrom: DateTime
  dateTo: DateTime
  minPrice: Float
  maxPrice: Float
  searchQuery: String
}

input EventSortInput {
  field: EventSortField!
  direction: SortDirection!
}

input PurchaseTicketInput {
  eventId: ID!
  ticketTypeId: ID!
  quantity: Int!
  idempotencyKey: String!
}

# Queries
type Query {
  # Event queries
  event(id: ID!): Event
  events(
    filter: EventFilterInput
    sort: EventSortInput
    first: Int
    after: String
  ): EventConnection!

  # Venue queries
  venue(id: ID!): Venue

  # User queries (authenticated)
  me: User!
  myOrders(first: Int, after: String): OrderConnection!
}

# Mutations
type Mutation {
  purchaseTicket(input: PurchaseTicketInput!): PurchaseResult!
  cancelOrder(orderId: ID!): CancelResult!
}

type PurchaseResult {
  success: Boolean!
  order: Order
  error: String
  queuePosition: Int  # If queued during a rush
}

type CancelResult {
  success: Boolean!
  refundAmount: Float
  error: String
}

# Subscriptions (real-time via WebSocket)
type Subscription {
  ticketAvailability(eventId: ID!): TicketAvailabilityUpdate!
}

type TicketAvailabilityUpdate {
  eventId: ID!
  ticketTypeId: ID!
  available: Int!
  seatId: String
  timestamp: DateTime!
}
```

### Schema Design Decisions

**Domain language, not CRUD.** The mutation is `purchaseTicket`, not `createOrder`. The schema reflects the business domain.

**Dedicated input types.** `PurchaseTicketInput` bundles parameters cleanly. Adding a field to an input type is backward-compatible.

**Non-null strategy.** Fields are non-null (`!`) only when guaranteed to always have a value. `description` is nullable; `id` and `title` are not. Be conservative -- making a nullable field non-null later is safe, the reverse is a breaking change.

---

## 2. Build: Resolvers

```javascript
const { ApolloServer } = require('@apollo/server');
const { expressMiddleware } = require('@apollo/server/express4');
const DataLoader = require('dataloader');

const resolvers = {
  Query: {
    event: (_, { id }, ctx) => ctx.loaders.event.load(id),
    events: async (_, { filter, sort, first = 20, after }) => {
      const { rows, totalCount } = await queryEvents(filter, sort, first, after);
      return toConnection(rows, totalCount, first, after);
    },
    me: (_, __, ctx) => {
      if (!ctx.userId) throw new Error('Not authenticated');
      return ctx.loaders.user.load(ctx.userId);
    },
    myOrders: async (_, { first = 20, after }, ctx) => {
      if (!ctx.userId) throw new Error('Not authenticated');
      const { rows, totalCount } = await queryUserOrders(ctx.userId, first, after);
      return toConnection(rows, totalCount, first, after);
    }
  },
  Mutation: {
    purchaseTicket: async (_, { input }, ctx) => {
      if (!ctx.userId) throw new Error('Not authenticated');
      try {
        const order = await purchaseTicketService(ctx.userId, input.eventId,
          input.ticketTypeId, input.quantity, input.idempotencyKey);
        return { success: true, order };
      } catch (err) { return { success: false, error: err.message }; }
    },
    cancelOrder: async (_, { orderId }, ctx) => {
      if (!ctx.userId) throw new Error('Not authenticated');
      try {
        const refund = await cancelOrderService(ctx.userId, orderId);
        return { success: true, refundAmount: refund.amount };
      } catch (err) { return { success: false, error: err.message }; }
    }
  },
  // Type resolvers: resolve relationships between types
  Event: {
    venue: (event, _, ctx) => ctx.loaders.venue.load(event.venueId),
    organizer: (event, _, ctx) => ctx.loaders.user.load(event.organizerId),
    ticketTypes: (event, _, ctx) => ctx.loaders.ticketTypesByEvent.load(event.id),
    availableCount: async (event, _, ctx) => {
      const types = await ctx.loaders.ticketTypesByEvent.load(event.id);
      return types.reduce((sum, t) => sum + t.available, 0);
    },
    isSoldOut: async (event, _, ctx) => {
      const types = await ctx.loaders.ticketTypesByEvent.load(event.id);
      return types.every(t => t.available === 0);
    }
  },
  Order: {
    event: (order, _, ctx) => ctx.loaders.event.load(order.eventId),
    tickets: (order, _, ctx) => ctx.loaders.ticketsByOrder.load(order.id)
  }
};
```

---

## 3. DataLoader: Solving the N+1 Problem

This is GraphQL's most notorious performance pitfall. Consider this query:

```graphql
query {
  events(first: 20) {
    edges {
      node {
        id
        title
        venue {
          id
          name
          city
        }
      }
    }
  }
}
```

Without DataLoader, the `venue` resolver fires 20 times -- one per event. Each call hits the database:

```sql
-- 1 query for events
SELECT * FROM events LIMIT 20;
-- 20 queries for venues (one per event)
SELECT * FROM venues WHERE id = 'v1';
SELECT * FROM venues WHERE id = 'v2';
SELECT * FROM venues WHERE id = 'v1';  -- duplicate! Same venue as event 1
...
```

That is 21 queries. DataLoader batches and deduplicates them into 2.

### Build: DataLoaders for TicketPulse

```javascript
function createLoaders() {
  return {
    event: new DataLoader(async (eventIds) => {
      const events = await db.query(
        `SELECT * FROM events WHERE id = ANY($1)`,
        [eventIds]
      );
      // CRITICAL: return in the same order as the input IDs
      return eventIds.map(id => events.rows.find(e => e.id === id) || null);
    }),

    venue: new DataLoader(async (venueIds) => {
      const venues = await db.query(
        `SELECT * FROM venues WHERE id = ANY($1)`,
        [venueIds]
      );
      return venueIds.map(id => venues.rows.find(v => v.id === id) || null);
    }),

    user: new DataLoader(async (userIds) => {
      const users = await db.query(
        `SELECT id, name, email FROM users WHERE id = ANY($1)`,
        [userIds]
      );
      return userIds.map(id => users.rows.find(u => u.id === id) || null);
    }),

    ticketTypesByEvent: new DataLoader(async (eventIds) => {
      const types = await db.query(
        `SELECT * FROM ticket_types WHERE event_id = ANY($1)`,
        [eventIds]
      );
      // Group by event_id, return array per event
      return eventIds.map(id =>
        types.rows.filter(t => t.event_id === id)
      );
    }),

    ticketsByOrder: new DataLoader(async (orderIds) => {
      const tickets = await db.query(
        `SELECT * FROM tickets WHERE order_id = ANY($1)`,
        [orderIds]
      );
      return orderIds.map(id =>
        tickets.rows.filter(t => t.order_id === id)
      );
    })
  };
}
```

### Per-Request Loader Creation

DataLoaders cache results for their lifetime. Sharing loaders across requests would serve stale data and leak information between users:

```javascript
const server = new ApolloServer({
  typeDefs,
  resolvers,
});

app.use('/graphql', expressMiddleware(server, {
  context: async ({ req }) => ({
    userId: authenticateRequest(req),
    loaders: createLoaders()  // Fresh loaders per request
  })
}));
```

### Observe: Before and After

Add query logging to see the difference:

```javascript
// Before DataLoader: events(first: 20) with venue resolution
// Query log:
//   SELECT * FROM events LIMIT 20                    -- 1 query
//   SELECT * FROM venues WHERE id = 'v1'             -- 20 queries
//   SELECT * FROM venues WHERE id = 'v2'             -- (one per event)
//   ...
// Total: 21 queries

// After DataLoader:
// Query log:
//   SELECT * FROM events LIMIT 20                    -- 1 query
//   SELECT * FROM venues WHERE id IN ('v1','v2',...) -- 1 query (batched!)
// Total: 2 queries
```

From N+1 to 2. This is not an optimization -- it is a requirement. Without DataLoader, a GraphQL API is unusably slow.

---

## 4. Relay-Style Cursor Pagination

TicketPulse needs pagination for event lists, order history, and more. The Relay Connection Spec is the standard.

### Build: Cursor Encoding

```javascript
// Encode a cursor (opaque to the client)
function encodeCursor(id) {
  return Buffer.from(`cursor:${id}`).toString('base64');
}

// Decode a cursor (server-side only)
function decodeCursor(cursor) {
  const decoded = Buffer.from(cursor, 'base64').toString();
  return decoded.replace('cursor:', '');
}

// Convert a database result set to a Relay connection
function toConnection(rows, totalCount, first, after) {
  const startIndex = after ? rows.findIndex(r => r.id === decodeCursor(after)) + 1 : 0;
  const sliced = rows.slice(startIndex, startIndex + first);

  return {
    edges: sliced.map(node => ({
      node,
      cursor: encodeCursor(node.id)
    })),
    pageInfo: {
      hasNextPage: startIndex + first < rows.length,
      hasPreviousPage: startIndex > 0,
      startCursor: sliced.length > 0 ? encodeCursor(sliced[0].id) : null,
      endCursor: sliced.length > 0 ? encodeCursor(sliced[sliced.length - 1].id) : null
    },
    totalCount
  };
}
```

### Database-Level Cursor Pagination

The in-memory approach above works for small sets. For production, push pagination to the database:

```javascript
async function queryEvents(filter, sort, first, after) {
  let sql = `SELECT * FROM events WHERE event_date >= CURRENT_DATE`;
  const params = [];
  let idx = 1;

  if (filter?.genre)  { sql += ` AND genre = $${idx++}`; params.push(filter.genre); }
  if (filter?.city)   { sql += ` AND city = $${idx++}`; params.push(filter.city); }
  if (after)          { sql += ` AND id > $${idx++}`; params.push(decodeCursor(after)); }

  const countResult = await db.query(sql.replace('SELECT *', 'SELECT COUNT(*)'), params);
  const totalCount = parseInt(countResult.rows[0].count);

  sql += ` ORDER BY id ASC LIMIT $${idx}`;
  params.push(first + 1); // One extra to determine hasNextPage

  const result = await db.query(sql, params);
  return { rows: result.rows.slice(0, first), totalCount, hasNextPage: result.rows.length > first };
}
```

Client usage: request `events(first: 10)`, get back `pageInfo.endCursor`. Next page: `events(first: 10, after: "Y3Vyc29yOmV2dF8wMjA=")`.

---

## 5. Subscriptions: Real-Time Ticket Availability

Connect GraphQL subscriptions to the WebSocket infrastructure from M67:

```javascript
const { PubSub } = require('graphql-subscriptions');
const { RedisPubSub } = require('graphql-redis-subscriptions');
const Redis = require('ioredis');

// Use Redis-backed PubSub for multi-server support
const pubsub = new RedisPubSub({
  publisher: new Redis(process.env.REDIS_URL),
  subscriber: new Redis(process.env.REDIS_URL)
});

const resolvers = {
  Subscription: {
    ticketAvailability: {
      subscribe: (_, { eventId }) => {
        return pubsub.asyncIterator(`TICKET_UPDATE:${eventId}`);
      }
    }
  }
};

// When a ticket is purchased (in the purchase service):
async function onTicketPurchased(eventId, ticketTypeId, seatId) {
  const ticketType = await db.query(
    `SELECT available FROM ticket_types WHERE id = $1`,
    [ticketTypeId]
  );

  await pubsub.publish(`TICKET_UPDATE:${eventId}`, {
    ticketAvailability: {
      eventId,
      ticketTypeId,
      available: ticketType.rows[0].available,
      seatId,
      timestamp: new Date().toISOString()
    }
  });
}
```

Client subscription:

```graphql
subscription WatchTickets {
  ticketAvailability(eventId: "evt_001") {
    eventId
    ticketTypeId
    available
    seatId
    timestamp
  }
}
```

This uses the `graphql-ws` protocol over WebSocket. The client opens a WebSocket connection to the GraphQL endpoint, sends the subscription query, and receives updates whenever a ticket is sold.

---

## 6. Security

GraphQL's flexibility is a security risk. A client can construct arbitrarily complex queries that overwhelm your server.

### Query Depth Limiting

```javascript
const depthLimit = require('graphql-depth-limit');

const server = new ApolloServer({
  typeDefs,
  resolvers,
  validationRules: [depthLimit(7)] // Reject queries deeper than 7 levels
});
```

A depth of 7 covers any reasonable query. A malicious query like `event → venue → events → venue → events → venue → events` would be rejected.

### Query Complexity Analysis

Depth alone is insufficient. A shallow but wide query can be just as expensive:

```graphql
# Shallow (depth 3) but fetches 1,000,000 rows
query {
  events(first: 1000) {
    edges {
      node {
        tickets(first: 1000) { id }
      }
    }
  }
}
```

Assign cost to each field and reject queries that exceed a budget:

```javascript
const { createComplexityLimitRule } = require('graphql-validation-complexity');

const server = new ApolloServer({
  typeDefs,
  resolvers,
  validationRules: [
    depthLimit(7),
    createComplexityLimitRule(1000, {
      // Cost rules
      scalarCost: 1,
      objectCost: 2,
      listFactor: 10,  // Lists multiply cost by this factor
    })
  ]
});
```

The query above would be scored as: 1000 events x 10 (list factor) x 1000 tickets x 10 (list factor) = 100,000,000. Far exceeding the 1000 budget.

### Persisted Queries

The nuclear option for security: only allow queries that are pre-registered.

```javascript
// At build time, the frontend generates a hash for each query
// hash("query { events { id title } }") → "abc123"

// At runtime, the client sends only the hash
// POST /graphql
// { "extensions": { "persistedQuery": { "sha256Hash": "abc123" } } }

// The server looks up the hash and executes the associated query
// Arbitrary queries from unknown clients are rejected
```

This eliminates all query-based attacks. The tradeoff: you lose the flexibility that makes GraphQL attractive for third-party consumers. Use persisted queries for your own apps (mobile, web) while keeping the full query API for internal tools.

---

## 7. Try It: GraphQL Playground

Start the server and open GraphQL Playground at `http://localhost:4000/graphql`. Try these queries:

```graphql
# Mobile app: minimal fields, fast
query { events(first: 10, filter: { city: "New York" }) {
  edges { node { id title date venue { name } availableCount isSoldOut } }
  pageInfo { hasNextPage endCursor }
}}

# Web app: rich detail, single request
query { event(id: "evt_001") {
  id title description date imageUrl
  venue { name address city capacity }
  organizer { name }
  ticketTypes { id name price available }
}}

# Purchase
mutation { purchaseTicket(input: {
  eventId: "evt_001" ticketTypeId: "tt_general" quantity: 2
  idempotencyKey: "purchase_user123_evt001_1679000000"
}) { success order { id totalAmount tickets { id seatId } } error }}
```

Same endpoint, different queries. The mobile app fetches 5 fields, the web app fetches 15. No over-fetching, no under-fetching.

---

## 8. Design: REST, GraphQL, or Both?

Should TicketPulse replace REST with GraphQL? This is the wrong question. The right question: where does each shine?

| Scenario | Best Choice | Why |
|----------|-------------|-----|
| Mobile app (varying data needs) | GraphQL | Clients control what they fetch |
| Web app (complex pages) | GraphQL | Single request for multiple resources |
| Webhooks from payment provider | REST | Simple, standardized, no query language |
| Internal service-to-service | REST or gRPC | Fixed contracts, no query flexibility needed |
| Public API for event organizers | REST | Simpler to document, easier to cache, more familiar |
| Real-time seat map | GraphQL subscriptions | Integrates with the GraphQL layer |
| Health checks, metrics | REST | Simple GET endpoints |

The pragmatic answer: **use both.** GraphQL for client-facing queries where flexibility matters. REST for everything else. They can coexist on the same server.

```javascript
// REST endpoints (simple, cacheable, external)
app.get('/api/v1/events/:id', eventController.getById);
app.post('/api/v1/webhooks/payment', paymentWebhook);
app.get('/health', healthCheck);

// GraphQL endpoint (flexible, client-facing)
app.use('/graphql', expressMiddleware(apolloServer, { context: createContext }));
```

---

## 9. Federation Preview

If TicketPulse grew to multiple teams, each could own their subgraph. The Events team defines `type Event @key(fields: "id") { id: ID! title: String! venue: Venue! }`. The Payments team extends it: `type Event @key(fields: "id") { id: ID! @external ticketTypes: [TicketType!]! }`. An Apollo Router composes these into a unified graph. Teams deploy independently.

Federation is premature for a small team. But design with it in mind: reference types by ID, keep resolver logic close to the data it owns.

---

## 10. Checkpoint

Before moving on, verify:

- [ ] Your GraphQL schema defines Event, Venue, Ticket, Order, and User types
- [ ] Queries support filtering, sorting, and cursor-based pagination
- [ ] DataLoader reduces venue resolution from N+1 queries to 2
- [ ] Subscriptions push real-time ticket availability updates
- [ ] Query depth limiting and complexity analysis prevent abuse
- [ ] You can articulate when GraphQL adds value vs. when REST is better

---

## Summary

GraphQL gives TicketPulse's clients the power to request exactly what they need. The mobile app gets a minimal event list in one query. The web app gets a rich event detail page in one query. Both use the same endpoint.

The cost of this flexibility: you must solve the N+1 problem (DataLoader), implement pagination properly (Relay connections), and secure against malicious queries (depth limiting, complexity analysis). These are not optional. Without them, a GraphQL API is slower and less secure than the REST API it replaced.

The pragmatic approach: GraphQL for client-facing queries where flexibility drives developer velocity. REST for webhooks, internal services, and public APIs where simplicity and cacheability matter more. They are complementary tools, not competitors.

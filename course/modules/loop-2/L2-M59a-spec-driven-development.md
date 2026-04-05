# L2-M59a: Spec-Driven Development

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M59 (Technical Writing)
>
> **Source:** Chapter 34 of the 100x Engineer Guide

## What You'll Learn

- How to design APIs contract-first using OpenAPI so frontend and backend teams can work in parallel
- How to document event-driven systems with AsyncAPI before a single message is published
- How to write an RFC that gets approved by anchoring it in executable specs
- How to turn business requirements into executable Gherkin specifications that double as acceptance tests
- The spec-first workflow: spec → types → mocks → tests → implementation

## Why This Matters

In Loop 1, you built TicketPulse's API and frontend at the same time. Every API change meant a Slack message, a blocked PR, and a frustrated teammate. In Loop 2, you extracted microservices, and now every inter-service contract is an implicit agreement that lives in someone's head.

Spec-driven development makes those contracts explicit and machine-readable. An OpenAPI spec generates TypeScript types, mock servers, and contract tests. An AsyncAPI spec documents your Kafka messages before consumers exist. A Gherkin scenario is a requirement you can execute.

The pattern is always the same: write the spec first, generate everything else from it, and let the spec be the single source of truth.

## Prereq Check

You should have completed L2-M59 (Technical Writing). You wrote an RFC there -- this module will show you how to back an RFC with executable specifications.

You will need Node.js 18+ and npm installed. Several CLI tools will be installed via npx.

> **Before you continue:** Most APIs are built code-first: write the handler, then document it later (if ever). What if you wrote the API specification first and generated code, docs, and tests from it? What would that change about your development workflow?

---

## Part 1: Contract-First API Design with OpenAPI

### The Problem

TicketPulse's frontend team needs to build the event listing page. The backend team is still implementing the event service. Neither can wait for the other.

Without a shared contract, the frontend team invents request/response shapes, the backend team implements different ones, and integration day becomes a nightmare of mismatched field names, missing pagination parameters, and undocumented error codes.

### The Solution: Write the Spec First

With contract-first development, both teams agree on the API shape before writing a line of implementation code. The frontend generates a mock server and builds against it. The backend implements the spec and verifies with contract tests. Integration day becomes a non-event.

### The OpenAPI Spec

Here is a complete OpenAPI 3.1 spec for TicketPulse's event endpoints:

```yaml
# ticketpulse-events.openapi.yaml
openapi: "3.1.0"
info:
  title: TicketPulse Event Service API
  version: "2.0.0"
  description: |
    API for managing concert events on the TicketPulse platform.
    Supports listing, filtering, and creating events.

servers:
  - url: http://localhost:3001
    description: Local development
  - url: https://api.ticketpulse.dev
    description: Staging

security:
  - BearerAuth: []

paths:
  /api/events:
    get:
      operationId: listEvents
      summary: List events with filtering and pagination
      tags: [Events]
      security: []
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
          description: Page number (1-indexed)
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: Number of events per page
        - name: dateFrom
          in: query
          schema:
            type: string
            format: date
          description: Filter events on or after this date (YYYY-MM-DD)
          example: "2026-06-01"
        - name: dateTo
          in: query
          schema:
            type: string
            format: date
          description: Filter events on or before this date (YYYY-MM-DD)
          example: "2026-12-31"
        - name: venueId
          in: query
          schema:
            type: string
            format: uuid
          description: Filter by venue ID
        - name: genre
          in: query
          schema:
            type: string
            enum: [rock, pop, jazz, classical, hip-hop, electronic, country, r-and-b, other]
          description: Filter by music genre
        - name: sort
          in: query
          schema:
            type: string
            enum: [date_asc, date_desc, name_asc, price_asc, price_desc]
            default: date_asc
          description: Sort order for results
      responses:
        "200":
          description: Paginated list of events
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EventListResponse"
              example:
                data:
                  - id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    name: "Summer Jazz Festival"
                    artist: "Miles Davis Tribute Band"
                    venue:
                      id: "v1v2v3v4-a1b2-c3d4-e5f6-789012345678"
                      name: "Blue Note Arena"
                      city: "Austin"
                      state: "TX"
                    date: "2026-07-15T20:00:00Z"
                    genre: "jazz"
                    priceRange:
                      min: 45.00
                      max: 150.00
                    ticketsAvailable: 342
                    totalTickets: 2000
                    status: "on_sale"
                pagination:
                  page: 1
                  limit: 20
                  total: 87
                  totalPages: 5
        "400":
          $ref: "#/components/responses/BadRequest"

    post:
      operationId: createEvent
      summary: Create a new event
      tags: [Events]
      description: |
        Creates a new event on the platform. Requires organizer role.
        The event starts in "draft" status and must be published separately.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateEventRequest"
            example:
              name: "Summer Jazz Festival"
              artist: "Miles Davis Tribute Band"
              venueId: "v1v2v3v4-a1b2-c3d4-e5f6-789012345678"
              date: "2026-07-15T20:00:00Z"
              genre: "jazz"
              tiers:
                - name: "General Admission"
                  price: 45.00
                  quantity: 1500
                - name: "VIP"
                  price: 150.00
                  quantity: 500
              description: "A tribute to the legendary Miles Davis featuring a 12-piece ensemble."
      responses:
        "201":
          description: Event created successfully
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Event"
        "400":
          $ref: "#/components/responses/BadRequest"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "403":
          $ref: "#/components/responses/Forbidden"

  /api/events/{eventId}:
    get:
      operationId: getEvent
      summary: Get event details by ID
      tags: [Events]
      security: []
      parameters:
        - name: eventId
          in: path
          required: true
          schema:
            type: string
            format: uuid
          description: The event's unique identifier
      responses:
        "200":
          description: Event details
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Event"
        "404":
          $ref: "#/components/responses/NotFound"

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Event:
      type: object
      required: [id, name, artist, venue, date, genre, priceRange, ticketsAvailable, totalTickets, status, createdAt]
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
          maxLength: 200
        artist:
          type: string
          maxLength: 200
        venue:
          $ref: "#/components/schemas/Venue"
        date:
          type: string
          format: date-time
        genre:
          type: string
          enum: [rock, pop, jazz, classical, hip-hop, electronic, country, r-and-b, other]
        priceRange:
          type: object
          required: [min, max]
          properties:
            min:
              type: number
              format: float
              minimum: 0
            max:
              type: number
              format: float
              minimum: 0
        ticketsAvailable:
          type: integer
          minimum: 0
        totalTickets:
          type: integer
          minimum: 1
        status:
          type: string
          enum: [draft, on_sale, sold_out, cancelled, completed]
        description:
          type: string
          maxLength: 5000
        tiers:
          type: array
          items:
            $ref: "#/components/schemas/TicketTier"
        createdAt:
          type: string
          format: date-time

    Venue:
      type: object
      required: [id, name, city, state]
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        city:
          type: string
        state:
          type: string
          minLength: 2
          maxLength: 2

    TicketTier:
      type: object
      required: [name, price, quantity]
      properties:
        name:
          type: string
          example: "General Admission"
        price:
          type: number
          format: float
          minimum: 0
          example: 45.00
        quantity:
          type: integer
          minimum: 1
          example: 1500

    CreateEventRequest:
      type: object
      required: [name, artist, venueId, date, genre, tiers]
      properties:
        name:
          type: string
          maxLength: 200
        artist:
          type: string
          maxLength: 200
        venueId:
          type: string
          format: uuid
        date:
          type: string
          format: date-time
        genre:
          type: string
          enum: [rock, pop, jazz, classical, hip-hop, electronic, country, r-and-b, other]
        tiers:
          type: array
          items:
            $ref: "#/components/schemas/TicketTier"
          minItems: 1
        description:
          type: string
          maxLength: 5000

    EventListResponse:
      type: object
      required: [data, pagination]
      properties:
        data:
          type: array
          items:
            $ref: "#/components/schemas/Event"
        pagination:
          $ref: "#/components/schemas/Pagination"

    Pagination:
      type: object
      required: [page, limit, total, totalPages]
      properties:
        page:
          type: integer
        limit:
          type: integer
        total:
          type: integer
        totalPages:
          type: integer

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          example: "VALIDATION_ERROR"
        message:
          type: string
          example: "Invalid request parameters"
        details:
          type: array
          items:
            type: object
            properties:
              field:
                type: string
              message:
                type: string

  responses:
    BadRequest:
      description: Invalid request parameters
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "VALIDATION_ERROR"
            message: "Invalid request parameters"
            details:
              - field: "limit"
                message: "Must be between 1 and 100"
    Unauthorized:
      description: Missing or invalid authentication token
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "UNAUTHORIZED"
            message: "Bearer token is missing or invalid"
    Forbidden:
      description: Insufficient permissions
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "FORBIDDEN"
            message: "Organizer role required to create events"
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "NOT_FOUND"
            message: "Event not found"
```

### Generate TypeScript Types from the Spec

With the spec written, you never hand-write request/response types again:

```bash
npx openapi-typescript ticketpulse-events.openapi.yaml -o src/types/event-api.ts
```

This produces types like:

```typescript
// src/types/event-api.ts (generated -- do not edit by hand)
export interface paths {
  "/api/events": {
    get: operations["listEvents"];
    post: operations["createEvent"];
  };
  "/api/events/{eventId}": {
    get: operations["getEvent"];
  };
}

export interface components {
  schemas: {
    Event: {
      id: string;
      name: string;
      artist: string;
      venue: components["schemas"]["Venue"];
      date: string;
      genre: "rock" | "pop" | "jazz" | "classical" | "hip-hop" | "electronic" | "country" | "r-and-b" | "other";
      priceRange: {
        min: number;
        max: number;
      };
      ticketsAvailable: number;
      totalTickets: number;
      status: "draft" | "on_sale" | "sold_out" | "cancelled" | "completed";
      description?: string;
      tiers?: components["schemas"]["TicketTier"][];
      createdAt: string;
    };
    Venue: {
      id: string;
      name: string;
      city: string;
      state: string;
    };
    // ... remaining types
  };
}
```

Both the frontend and backend import from this generated file. If anyone changes the spec, the types update and the compiler catches mismatches.

### Generate a Mock Server

The frontend team does not wait for the backend. They run a mock server from the spec:

```bash
npx @stoplight/prism-cli mock ticketpulse-events.openapi.yaml --port 3001
```

Now the frontend can develop against `http://localhost:3001/api/events` and get realistic responses that match the agreed contract. When the real backend is ready, switch the base URL. Nothing else changes.

Test the mock:

```bash
# List events
curl http://localhost:3001/api/events?genre=jazz&limit=5

# Get a single event (Prism generates a UUID automatically)
curl http://localhost:3001/api/events/a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Create an event (requires auth header per the spec)
curl -X POST http://localhost:3001/api/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fake-token" \
  -d '{
    "name": "Neon Nights Tour",
    "artist": "The Synthetics",
    "venueId": "v1v2v3v4-a1b2-c3d4-e5f6-789012345678",
    "date": "2026-09-20T21:00:00Z",
    "genre": "electronic",
    "tiers": [{"name": "GA", "price": 55.00, "quantity": 3000}]
  }'
```

### Contract Testing

The mock server is useful during development, but you need to verify that the real implementation matches the spec. Contract testing closes this gap:

```typescript
// tests/contract/events.contract.test.ts
import { describe, it, expect } from "vitest";
import SwaggerParser from "@apidevtools/swagger-parser";

const SPEC_PATH = "./ticketpulse-events.openapi.yaml";
const BASE_URL = process.env.API_BASE_URL || "http://localhost:3001";

describe("Event API contract tests", () => {
  let spec: any;

  beforeAll(async () => {
    spec = await SwaggerParser.dereference(SPEC_PATH);
  });

  it("GET /api/events returns a valid EventListResponse", async () => {
    const response = await fetch(`${BASE_URL}/api/events?limit=5`);
    const body = await response.json();

    expect(response.status).toBe(200);

    // Validate structure matches spec
    expect(body).toHaveProperty("data");
    expect(body).toHaveProperty("pagination");
    expect(Array.isArray(body.data)).toBe(true);

    if (body.data.length > 0) {
      const event = body.data[0];
      const requiredFields = spec.components.schemas.Event.required;
      for (const field of requiredFields) {
        expect(event).toHaveProperty(field);
      }

      // Validate enum values match spec
      const validStatuses = spec.components.schemas.Event.properties.status.enum;
      expect(validStatuses).toContain(event.status);
    }

    // Validate pagination
    expect(body.pagination).toHaveProperty("page");
    expect(body.pagination).toHaveProperty("limit");
    expect(body.pagination).toHaveProperty("total");
    expect(body.pagination).toHaveProperty("totalPages");
  });

  it("GET /api/events/:id returns 404 for nonexistent event", async () => {
    const response = await fetch(
      `${BASE_URL}/api/events/00000000-0000-0000-0000-000000000000`
    );
    expect(response.status).toBe(404);

    const body = await response.json();
    expect(body).toHaveProperty("code");
    expect(body).toHaveProperty("message");
  });
});
```

Run contract tests against both the mock and the real server. If they both pass, the contract holds.

---

## Part 2: AsyncAPI for Event-Driven Specs

### The Problem

TicketPulse uses Kafka for asynchronous communication between services. The purchase service publishes a `TicketPurchased` event. The notification service, analytics service, and waitlist service all consume it. But the message schema is undocumented -- it lives in the purchase service's codebase, and consumers reverse-engineer it from example messages.

When the purchase service adds a field, consumers do not know. When a consumer expects a field that was renamed, it fails silently at runtime.

### The Solution: AsyncAPI

AsyncAPI is OpenAPI for event-driven systems. It documents channels (topics), messages, and schemas.

```yaml
# ticketpulse-events.asyncapi.yaml
asyncapi: "2.6.0"
info:
  title: TicketPulse Event-Driven API
  version: "2.0.0"
  description: |
    Asynchronous event specifications for TicketPulse's Kafka-based
    messaging system. All services producing or consuming these events
    MUST conform to these schemas.

servers:
  development:
    url: localhost:9092
    protocol: kafka
    description: Local Kafka broker
  staging:
    url: kafka.ticketpulse.dev:9092
    protocol: kafka-secure
    description: Staging Kafka cluster

defaultContentType: application/json

channels:
  ticket.purchased:
    description: |
      Published when a user successfully purchases tickets.
      Consumers: notification-service, analytics-service, waitlist-service.
    subscribe:
      operationId: onTicketPurchased
      summary: Receive ticket purchase events
      message:
        $ref: "#/components/messages/TicketPurchased"

  ticket.cancelled:
    description: |
      Published when a user cancels a ticket purchase (before the event date).
      Consumers: notification-service, analytics-service, waitlist-service, refund-service.
    subscribe:
      operationId: onTicketCancelled
      summary: Receive ticket cancellation events
      message:
        $ref: "#/components/messages/TicketCancelled"

  event.soldout:
    description: |
      Published when an event's available ticket count reaches zero.
      Consumers: waitlist-service, notification-service.
    subscribe:
      operationId: onEventSoldOut
      summary: Receive event sold-out notifications
      message:
        $ref: "#/components/messages/EventSoldOut"

components:
  messages:
    TicketPurchased:
      name: TicketPurchased
      title: Ticket Purchased Event
      contentType: application/json
      headers:
        type: object
        required: [correlationId, eventType, timestamp, version]
        properties:
          correlationId:
            type: string
            format: uuid
            description: Unique ID for tracing this event across services
          eventType:
            type: string
            const: "ticket.purchased"
          timestamp:
            type: string
            format: date-time
          version:
            type: integer
            const: 1
            description: Schema version for backward compatibility
      payload:
        type: object
        required: [purchaseId, userId, eventId, tickets, totalAmount, purchasedAt]
        properties:
          purchaseId:
            type: string
            format: uuid
          userId:
            type: string
            format: uuid
          eventId:
            type: string
            format: uuid
          tickets:
            type: array
            items:
              type: object
              required: [ticketId, tier, price]
              properties:
                ticketId:
                  type: string
                  format: uuid
                tier:
                  type: string
                  example: "General Admission"
                price:
                  type: number
                  format: float
                  example: 45.00
          totalAmount:
            type: number
            format: float
            example: 90.00
          currency:
            type: string
            default: "USD"
          purchasedAt:
            type: string
            format: date-time
      examples:
        - name: standardPurchase
          summary: A user buys 2 GA tickets
          headers:
            correlationId: "c7d8e9f0-1234-5678-abcd-ef0123456789"
            eventType: "ticket.purchased"
            timestamp: "2026-07-15T14:30:00Z"
            version: 1
          payload:
            purchaseId: "p1234567-89ab-cdef-0123-456789abcdef"
            userId: "u1234567-89ab-cdef-0123-456789abcdef"
            eventId: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            tickets:
              - ticketId: "t0000001-89ab-cdef-0123-456789abcdef"
                tier: "General Admission"
                price: 45.00
              - ticketId: "t0000002-89ab-cdef-0123-456789abcdef"
                tier: "General Admission"
                price: 45.00
            totalAmount: 90.00
            currency: "USD"
            purchasedAt: "2026-07-15T14:30:00Z"

    TicketCancelled:
      name: TicketCancelled
      title: Ticket Cancelled Event
      contentType: application/json
      headers:
        type: object
        required: [correlationId, eventType, timestamp, version]
        properties:
          correlationId:
            type: string
            format: uuid
          eventType:
            type: string
            const: "ticket.cancelled"
          timestamp:
            type: string
            format: date-time
          version:
            type: integer
            const: 1
      payload:
        type: object
        required: [purchaseId, userId, eventId, cancelledTicketIds, refundAmount, cancelledAt]
        properties:
          purchaseId:
            type: string
            format: uuid
          userId:
            type: string
            format: uuid
          eventId:
            type: string
            format: uuid
          cancelledTicketIds:
            type: array
            items:
              type: string
              format: uuid
          refundAmount:
            type: number
            format: float
          cancelledAt:
            type: string
            format: date-time
          reason:
            type: string
            enum: [user_requested, event_cancelled, duplicate_purchase, fraud]

    EventSoldOut:
      name: EventSoldOut
      title: Event Sold Out Notification
      contentType: application/json
      headers:
        type: object
        required: [correlationId, eventType, timestamp, version]
        properties:
          correlationId:
            type: string
            format: uuid
          eventType:
            type: string
            const: "event.soldout"
          timestamp:
            type: string
            format: date-time
          version:
            type: integer
            const: 1
      payload:
        type: object
        required: [eventId, eventName, soldOutAt, totalTicketsSold]
        properties:
          eventId:
            type: string
            format: uuid
          eventName:
            type: string
          soldOutAt:
            type: string
            format: date-time
          totalTicketsSold:
            type: integer
```

### Generate Types from AsyncAPI

```bash
npx @asyncapi/cli generate models typescript ticketpulse-events.asyncapi.yaml -o src/types/events/
```

### The Pattern

The pattern is the same whether you are dealing with REST or events:

1. **Spec** -- Write the machine-readable contract
2. **Schema** -- Extract schemas from the spec
3. **Validation** -- Validate messages at runtime against the schema
4. **Code generation** -- Generate types, mocks, and documentation from the spec
5. **Contract tests** -- Verify implementations match the spec

The spec is the source of truth. Everything else is derived.

---

## Part 3: Writing an RFC That Gets Approved

### Backing an RFC with Executable Specs

In L2-M59, you learned the RFC template. Now you will see how spec-driven development makes RFCs more concrete and reviewable. Instead of describing an API in prose, you attach the OpenAPI spec. Instead of describing behavior in paragraphs, you attach Gherkin scenarios.

### RFC: Add a Waitlist Feature for Sold-Out Events

```markdown
# RFC: Waitlist for Sold-Out Events

**Author:** [Your name]
**Date:** 2026-03-24
**Status:** In Review
**Reviewers:** Backend Lead, Product Manager, Infrastructure Lead

## TL;DR

Add a waitlist system so users can join a queue when events sell out.
When tickets become available (cancellations, additional inventory),
waitlisted users receive a time-limited purchase window in the order
they joined. Expected revenue recovery: $180K/year based on current
sellout rates.

## Problem

When popular events sell out, TicketPulse loses potential revenue and
frustrates users. Our support team receives ~200 emails per month
asking "can you notify me if tickets become available?" We have no
mechanism for this.

**Evidence from the last 6 months:**
- 34% of events sell out
- Of sold-out events, 12% release additional inventory later
- Average time between sellout and new inventory: 3.2 days
- Estimated lost revenue per month: $15K (based on conversion rates
  from similar platforms)

## Context

- The `event.soldout` Kafka event already exists (see AsyncAPI spec,
  `ticket.cancelled` channel)
- The notification service supports email and push notifications
- No waitlist infrastructure exists today
- Competitors (Eventbrite, Ticketmaster) offer waitlist functionality

## Proposed Solution

### Architecture

A new `waitlist-service` that:
1. Subscribes to `event.soldout` to know which events have waitlists
2. Exposes a REST API for users to join/leave the waitlist
3. Subscribes to `ticket.cancelled` to detect newly available tickets
4. Publishes `waitlist.offer` events when tickets become available
5. The notification service delivers the offer to the user

### API Design

See attached `waitlist.openapi.yaml` for the full specification.
Key endpoints:
- `POST /api/waitlist/{eventId}` -- join the waitlist
- `DELETE /api/waitlist/{eventId}` -- leave the waitlist
- `GET /api/waitlist/{eventId}/position` -- check your position
- `POST /api/waitlist/{eventId}/claim` -- claim offered tickets

### Data Model

```sql
CREATE TABLE waitlist_entries (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id    UUID NOT NULL,
  user_id     UUID NOT NULL,
  position    INTEGER NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'waiting',
  -- status: waiting | offered | claimed | expired | cancelled
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  offered_at  TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ,
  UNIQUE(event_id, user_id)
);

CREATE INDEX idx_waitlist_event_status ON waitlist_entries(event_id, status);
CREATE INDEX idx_waitlist_expires ON waitlist_entries(expires_at)
  WHERE status = 'offered';
```

### Offer Flow

1. `ticket.cancelled` event arrives
2. Waitlist service queries next N users in `waiting` status
   (N = number of newly available tickets)
3. Sets their status to `offered`, sets `expires_at` to NOW() + 15 minutes
4. Publishes `waitlist.offer` event per user
5. Notification service sends email + push notification
6. User has 15 minutes to call `POST /api/waitlist/{eventId}/claim`
7. If unclaimed after 15 minutes, a cron job expires the offer and
   moves to the next user in line

### Behavior Specification

See attached `waitlist.feature` for the complete Gherkin scenarios
covering: join, leave, offer, claim, expiration, and duplicate
attempts.

## Alternatives Considered

**Alternative 1: Notify all waitlisted users simultaneously**
- Pros: Simpler implementation, no offer/expiration logic
- Cons: Creates a stampede. 5,000 users get notified, 10 tickets
  are available. 4,990 users are disappointed. Worse UX than the
  current "Sold Out" message.
- Rejected because: The stampede problem makes this strictly worse
  than ordered offers.

**Alternative 2: Build waitlist into the purchase service**
- Pros: No new service, reuses existing database and API
- Cons: Adds complexity to the most critical service. Waitlist logic
  (offers, expirations, position tracking) is unrelated to purchase
  processing. A bug in waitlist code could affect ticket purchases.
- Rejected because: The purchase service is our highest-SLO service.
  Adding unrelated functionality increases its blast radius.

**Alternative 3: Use a third-party waitlist service (e.g., WaitWhile)**
- Pros: No development effort, proven solution
- Cons: Per-user pricing ($0.10/waitlist entry) would cost ~$8K/month
  at our scale. Limited customization. Data leaves our platform.
- Rejected because: Cost exceeds the engineering investment within
  6 months, and we lose control over the user experience.

## Risks

- **Scale:** A popular artist could have 50,000 waitlist entries.
  The position query must be O(1), not O(n). Solution: the `position`
  column is set at join time and updated only when entries are removed.
- **Thundering herd on offers:** If 100 tickets become available,
  100 users are notified simultaneously. The claim endpoint must handle
  this burst. Solution: rate limiting + idempotent claims.
- **Clock skew on expiration:** If the cron job runs late, expired
  offers might be claimed. Solution: the claim endpoint checks
  `expires_at` server-side, not just the cron.

## Rollout Plan

| Phase | Timeline | Scope |
|-------|----------|-------|
| 1. Internal beta | Week 1-2 | Deploy behind feature flag, test with internal events |
| 2. Limited rollout | Week 3-4 | Enable for 10% of sold-out events, monitor metrics |
| 3. General availability | Week 5 | Enable for all events, announce to users |

Success metrics:
- Waitlist join rate: >20% of users who see "Sold Out"
- Claim rate: >60% of offered tickets are claimed
- Revenue recovered: track tickets sold via waitlist offers
```

### The Review Process

Who reviews an RFC depends on what it changes:

| Change Type | Required Reviewers |
|---|---|
| New service | Backend lead, infrastructure lead |
| API changes | Frontend lead, API consumers |
| Data model changes | Database owner, privacy/compliance |
| Cross-team impact | Leads from affected teams |
| Cost implications | Engineering manager |

**How to respond to feedback:**

- If the feedback is a question, answer it in the RFC (not just in the comment thread). Future readers will have the same question.
- If the feedback identifies a flaw, fix it and note what changed. Do not argue in comments.
- If you disagree with feedback, state your reasoning once and let the reviewer decide. Escalate only if the disagreement is blocking.

**The 48-hour rule:** Reviewers have 48 hours to provide feedback. After 48 hours, silence is consent. This prevents RFCs from languishing in review for weeks. Announce this timeline when you send the RFC for review.

---

## Part 4: Executable Specifications with BDD

### From Requirements to Runnable Specs

Business requirements written in prose are ambiguous. "Users should be able to purchase tickets" does not specify what happens when tickets run out, when payment fails, or when a user tries to buy the same ticket twice.

Gherkin turns requirements into structured scenarios that are both human-readable and machine-executable.

### The Feature File

```gherkin
# features/ticket-purchase.feature

Feature: Ticket Purchase
  As a TicketPulse user
  I want to purchase tickets for events
  So that I can attend concerts

  Background:
    Given the following event exists:
      | id                                   | name                  | status  |
      | a1b2c3d4-e5f6-7890-abcd-ef1234567890 | Summer Jazz Festival  | on_sale |
    And the event has the following ticket tiers:
      | tier              | price  | available |
      | General Admission | 45.00  | 100       |
      | VIP               | 150.00 | 20        |
    And I am logged in as user "u1234567-89ab-cdef-0123-456789abcdef"
    And I have a valid payment method "pm_test_visa_4242"

  Scenario: Successful ticket purchase
    When I purchase 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 201
    And the response should contain a purchase ID
    And the response should show total amount 90.00
    And the event should have 98 "General Admission" tickets available
    And a "ticket.purchased" Kafka event should be published

  Scenario: Purchase reduces available ticket count
    Given there are 5 "General Admission" tickets available
    When I purchase 3 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 201
    And the event should have 2 "General Admission" tickets available

  Scenario: Insufficient tickets available
    Given there are 2 "General Admission" tickets available
    When I purchase 5 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 409
    And the response error code should be "INSUFFICIENT_TICKETS"
    And the response should include the number of available tickets
    And no "ticket.purchased" Kafka event should be published

  Scenario: Duplicate purchase attempt within 5-minute window
    Given I already purchased 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890" 2 minutes ago
    When I purchase 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 409
    And the response error code should be "DUPLICATE_PURCHASE"
    And the response should include the existing purchase ID

  Scenario: Payment failure
    Given my payment method "pm_test_visa_4242" will be declined
    When I purchase 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 402
    And the response error code should be "PAYMENT_FAILED"
    And the event ticket count should not change
    And no "ticket.purchased" Kafka event should be published

  Scenario: Purchase the last available tickets triggers sold-out event
    Given there are 2 "General Admission" tickets available
    And there are 0 "VIP" tickets available
    When I purchase 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 201
    And the event status should change to "sold_out"
    And an "event.soldout" Kafka event should be published

  Scenario: Cannot purchase tickets for a cancelled event
    Given the event status is "cancelled"
    When I purchase 2 "General Admission" tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 400
    And the response error code should be "EVENT_NOT_ON_SALE"

  Scenario: Quantity validation
    When I purchase 0 tickets for event "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    Then the response status should be 400
    And the response error code should be "VALIDATION_ERROR"
    And the response should say quantity must be between 1 and 10
```

### Step Definitions

Connect the Gherkin steps to actual API calls:

```typescript
// features/step-definitions/purchase.steps.ts
import { Given, When, Then, Before } from "@cucumber/cucumber";
import { expect } from "chai";

const BASE_URL = process.env.API_BASE_URL || "http://localhost:3001";

interface TestContext {
  authToken: string;
  response: Response | null;
  responseBody: any;
  lastPurchaseId: string | null;
  eventId: string;
}

let ctx: TestContext;

Before(function () {
  ctx = {
    authToken: "",
    response: null,
    responseBody: null,
    lastPurchaseId: null,
    eventId: "",
  };
});

Given("I am logged in as user {string}", async function (userId: string) {
  // In test environment, generate a JWT for the given user
  const res = await fetch(`${BASE_URL}/api/test/auth-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId }),
  });
  const body = await res.json();
  ctx.authToken = body.token;
});

Given("I have a valid payment method {string}", async function (pmId: string) {
  // Payment method is passed in the purchase request; no setup needed
  // unless the test environment requires Stripe test fixture creation
});

Given(
  "there are {int} {string} tickets available",
  async function (count: number, tier: string) {
    // Seed the test database with the specified inventory
    await fetch(`${BASE_URL}/api/test/set-inventory`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${ctx.authToken}`,
      },
      body: JSON.stringify({
        eventId: ctx.eventId,
        tier,
        available: count,
      }),
    });
  }
);

When(
  "I purchase {int} {string} tickets for event {string}",
  async function (quantity: number, tier: string, eventId: string) {
    ctx.eventId = eventId;
    ctx.response = await fetch(`${BASE_URL}/api/purchases`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${ctx.authToken}`,
      },
      body: JSON.stringify({
        eventId,
        tier,
        quantity,
        paymentMethodId: "pm_test_visa_4242",
      }),
    });
    ctx.responseBody = await ctx.response.json();

    if (ctx.responseBody.purchaseId) {
      ctx.lastPurchaseId = ctx.responseBody.purchaseId;
    }
  }
);

Then("the response status should be {int}", function (status: number) {
  expect(ctx.response!.status).to.equal(status);
});

Then("the response should contain a purchase ID", function () {
  expect(ctx.responseBody).to.have.property("purchaseId");
  expect(ctx.responseBody.purchaseId).to.match(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});

Then(
  "the response should show total amount {float}",
  function (amount: number) {
    expect(ctx.responseBody.totalAmount).to.equal(amount);
  }
);

Then(
  "the event should have {int} {string} tickets available",
  async function (count: number, tier: string) {
    const res = await fetch(`${BASE_URL}/api/events/${ctx.eventId}`);
    const event = await res.json();
    const matchingTier = event.tiers.find(
      (t: any) => t.name === tier
    );
    expect(matchingTier.available).to.equal(count);
  }
);

Then(
  "the response error code should be {string}",
  function (code: string) {
    expect(ctx.responseBody.code).to.equal(code);
  }
);

Then(
  "a {string} Kafka event should be published",
  async function (eventType: string) {
    // In test environment, check the test Kafka consumer or
    // an in-memory event store that captures published events
    const res = await fetch(
      `${BASE_URL}/api/test/kafka-events?type=${eventType}&since=5s`
    );
    const events = await res.json();
    expect(events.length).to.be.greaterThan(0);
  }
);

Then(
  "no {string} Kafka event should be published",
  async function (eventType: string) {
    const res = await fetch(
      `${BASE_URL}/api/test/kafka-events?type=${eventType}&since=5s`
    );
    const events = await res.json();
    expect(events.length).to.equal(0);
  }
);
```

### Running the Specs

```bash
# Install Cucumber.js
npm install --save-dev @cucumber/cucumber ts-node chai @types/chai

# Run all feature files
npx cucumber-js --require-module ts-node/register \
  --require 'features/step-definitions/**/*.ts' \
  features/

# Run a specific scenario by tag
npx cucumber-js --tags "@purchase" features/
```

Green means the feature works as specified. Red means there is a bug or the implementation does not match the spec. The Gherkin file is the single source of truth for what the system should do.

---

## Try It

### Exercise 1: Write the Purchase Endpoint Spec

Write an OpenAPI spec for `POST /api/purchases`. Include:
- Request body schema (eventId, tier, quantity, paymentMethodId)
- 201 response with purchase details
- 400, 401, 402, 409 error responses with specific error codes
- Authentication requirement

### Exercise 2: Generate and Test a Mock Server

```bash
# Start the mock server with your spec
npx @stoplight/prism-cli mock your-purchase.openapi.yaml --port 3002

# Test it with curl
curl -X POST http://localhost:3002/api/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"eventId": "abc-123", "tier": "GA", "quantity": 2, "paymentMethodId": "pm_test"}'
```

Verify: does the mock response match your schema? Does it reject requests with missing required fields?

### Exercise 3: Write a Gherkin Scenario for Refunds

Write a `.feature` file for the ticket refund flow. Include scenarios for:
- Successful refund before the event date
- Refund rejected after the event date
- Partial refund (refund 1 of 3 tickets)
- Refund when the event is on the waitlist (should trigger waitlist notification)

### Exercise 4: Curl the Mock

```bash
# Start the event service mock
npx @stoplight/prism-cli mock ticketpulse-events.openapi.yaml --port 3001

# Verify filtering works
curl "http://localhost:3001/api/events?genre=jazz&dateFrom=2026-06-01&limit=5"

# Verify error responses
curl "http://localhost:3001/api/events?limit=999"
# Should return 400 because limit max is 100

# Verify auth enforcement on create
curl -X POST http://localhost:3001/api/events \
  -H "Content-Type: application/json" \
  -d '{"name": "Test"}'
# Should return 401 because no Authorization header
```

---

## Debug

### Find the Contract Mismatch

The OpenAPI spec for the purchase endpoint defines `quantity` as:

```yaml
quantity:
  type: integer
  minimum: 1
  maximum: 10
```

But the actual API implementation accepts string values without validation:

```typescript
// BUG: No type coercion or validation
app.post("/api/purchases", async (req, res) => {
  const { eventId, quantity, paymentMethodId } = req.body;

  // quantity is "3" (string) when it should be 3 (integer)
  // This passes: "3" > 0 is true in JavaScript due to coercion
  if (quantity > 0 && quantity <= 10) {
    // But this breaks: "3" - 1 = 2, which happens to work,
    // while "3" + 1 = "31" (string concatenation!)
    const totalPrice = ticketPrice * quantity; // Works by accident
    const remaining = available - quantity;    // Works by accident
    const nextBatch = quantity + 1;            // BUG: "31" not 4

    // ...
  }
});
```

**The fix:** Add request validation middleware that enforces the OpenAPI spec at runtime:

```typescript
import { OpenApiValidator } from "express-openapi-validator";

app.use(
  OpenApiValidator.middleware({
    apiSpec: "./ticketpulse-purchase.openapi.yaml",
    validateRequests: true,
    validateResponses: true,
  })
);
```

Now the API rejects `quantity: "3"` with a 400 error before it reaches your handler. The spec is not just documentation -- it is enforcement.

---

## Reflect

Answer these questions:

1. **How much time would the OpenAPI-first approach have saved in Loop 1?** Think back to when you were building the API and consuming it at the same time. How many times did you change a response shape and break the frontend? How many Slack messages were "what's the field name for X?"

2. **When is an RFC overkill? When is it insufficient?** An RFC for a one-line bug fix wastes everyone's time. But what about a medium-sized feature? Where is the line? Consider the criteria: reversibility, scope, team impact, and cost.

3. **Could an AI agent implement the waitlist feature from just the RFC + OpenAPI spec + Gherkin scenarios?** You have a complete specification: the data model (SQL), the API contract (OpenAPI), the message schemas (AsyncAPI), and the expected behavior (Gherkin). Is that enough for an AI to generate a working implementation? What is missing?

---

> **What did you notice?** Spec-driven development inverts the usual workflow: design the contract first, then implement. How would adopting this approach have changed any of the APIs you built earlier in Loop 2?

## Checkpoint

Before moving on, verify:

- [ ] OpenAPI spec written for at least 3 TicketPulse endpoints (list events, get event, create event)
- [ ] Mock server generated with Prism and tested with curl
- [ ] TypeScript types generated from the OpenAPI spec using openapi-typescript
- [ ] RFC written for the waitlist feature with problem, solution, alternatives, risks, and rollout plan
- [ ] At least 3 Gherkin scenarios written for the ticket purchase flow
- [ ] AsyncAPI spec documents at least one Kafka channel with a complete message schema

---

## Key Terms

| Term | Definition |
|------|-----------|
| **OpenAPI** | A specification format (formerly Swagger) for describing RESTful APIs in machine-readable YAML or JSON. Enables code generation, mock servers, and contract testing. |
| **AsyncAPI** | The equivalent of OpenAPI for event-driven architectures. Describes message channels, schemas, and protocols (Kafka, AMQP, WebSocket). |
| **Contract-first** | A development approach where the API specification is written before the implementation. Both producer and consumer develop against the spec in parallel. |
| **Mock server** | A server that generates fake responses based on an API specification. Allows consumers to develop without waiting for the real implementation. |
| **Gherkin** | A structured language for writing executable specifications using Given/When/Then syntax. Each scenario describes one behavior of the system. |
| **BDD** | Behavior-Driven Development; a practice where expected behavior is specified in business-readable scenarios (Gherkin) before code is written. |
| **RFC** | Request for Comments; a document proposing a significant technical change for review. In spec-driven development, an RFC references attached specs rather than describing APIs in prose. |
| **Executable specification** | A specification that can be run as a test. Gherkin scenarios connected to step definitions are executable specs: they verify the system matches the specification. |
| **Code generation** | Automatically producing source code (types, clients, validators) from a machine-readable specification. Eliminates drift between spec and implementation. |
| **Contract testing** | Automated tests that verify an API implementation conforms to its specification. Catches mismatches between what the spec promises and what the code delivers. |

---

## What's Next

In **Loop 2 Capstone** (L2-M60), you'll bring everything together in the Loop 2 capstone — a comprehensive project that tests your mastery of distributed systems.

---

## Further Reading

- Chapter 34 of the 100x Engineer Guide (Spec-Driven Development) for the full treatment
- [OpenAPI 3.1 Specification](https://spec.openapis.org/oas/v3.1.0) -- the official standard
- [AsyncAPI Specification](https://www.asyncapi.com/docs/reference/specification/v2.6.0) -- event-driven API specs
- [Cucumber.js Documentation](https://cucumber.io/docs/installation/javascript/) -- BDD framework for JavaScript/TypeScript
- [Stoplight Prism](https://docs.stoplight.io/docs/prism/) -- mock server and contract testing from OpenAPI specs
- [openapi-typescript](https://openapi-ts.dev/) -- generate TypeScript types from OpenAPI specs

> **Next up:** L2-M60 is the Loop 2 Capstone. You have the specs, the types, the mocks, and the tests. Time to put it all together.

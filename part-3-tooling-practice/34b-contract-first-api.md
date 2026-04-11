<!--
  CHAPTER: 34b
  TITLE: Contract-First API & Executable Specs
  PART: III — Tooling & Practice
  PREREQS: Ch 34 (Specs, RFCs & ADRs), Ch 25 (API Design), Ch 27 (Technical Writing)
  KEY_TOPICS: Contract-first API design, OpenAPI, AsyncAPI, Protocol Buffers, gRPC, code generation, contract testing, BDD, Gherkin, executable specifications, property-based testing, specification formats
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 34b: Contract-First API & Executable Specs

> **Part III — Tooling & Practice** | Prerequisites: Ch 34 (Specs, RFCs & ADRs), Ch 25 (API Design), Ch 27 (Technical Writing) | Difficulty: Intermediate → Advanced

Contract-first development means you define the interface before writing a single line of server code. The contract — whether an OpenAPI spec, a Protobuf definition, or a Gherkin scenario — is the source of truth. Implementation follows. This chapter covers every major contract and executable specification format, showing you how to turn specs into generated code, automated tests, and enforceable API boundaries.

### In This Chapter
- Contract-First API Design
- Executable Specifications
- Specification Languages and Formats

### Related Chapters
- **TESTING spiral:** ← [Ch 8: Testing & Quality](../part-2-applied-engineering/08-testing-quality.md) | → [Ch 33: GitHub Actions Core](../part-3-tooling-practice/33-github-actions-core.md)
- Ch 34 (Specs, RFCs & Architecture Decision Records) — the spec-first thesis, RFCs, ADRs
- Ch 34c (AI-Native Specs & Spec Culture) — AI-native workflows, anti-patterns, measuring quality
- Ch 25 (API Design) — REST, GraphQL, gRPC design patterns
- Ch 27 (Technical Writing & Documentation) — writing principles
- Ch 3 (Architecture Patterns) — system design patterns referenced in specs

---

## 4. CONTRACT-FIRST API DESIGN

### 4.1 The Principle

Contract-first API design means you define the interface before writing a single line of server code. The contract (OpenAPI spec, Protobuf definition, GraphQL schema) is the source of truth. Implementation follows.

This inverts the common approach where developers build the server, then document the API after the fact. Contract-first has three major advantages:

1. **Parallel development.** Frontend and backend teams can work simultaneously. The frontend codes against the contract (using mock servers), while the backend implements it.
2. **Code generation.** Typed client SDKs, server stubs, and documentation are generated from the contract, eliminating an entire class of bugs (mismatched types, missing fields, wrong HTTP methods).
3. **Contract testing.** You can automatically verify that the implementation matches the contract, catching drift before it reaches production.

Here is a story I have seen play out more times than I can count. A backend team ships an endpoint. The frontend team integrates it. Two days later, someone notices that the response field the frontend relies on is named `user_id` in the contract and `userId` in the implementation. Both teams argue about who is "right." The spec was never authoritative. Now you have a production bug and a blame game.

Contract-first eliminates that entire class of argument. The contract is right, by definition. Implementations that deviate from it are wrong, and contract tests catch the deviation before it ships. Ch 25 covers API design patterns in depth — this section is about making that design stick through the power of a machine-readable, generated-from, tested-against contract.

### 4.2 OpenAPI for REST APIs

OpenAPI (formerly Swagger) is the standard for describing REST APIs. Here is a complete example for the TicketPulse event listing endpoint:

```yaml
openapi: 3.1.0
info:
  title: TicketPulse API
  version: 2.0.0
  description: |
    TicketPulse event discovery and ticket reservation API.
    All endpoints require Bearer token authentication unless
    marked as public.
  contact:
    name: TicketPulse Platform Team
    email: platform@ticketpulse.dev

servers:
  - url: https://api.ticketpulse.dev/v2
    description: Production
  - url: https://api.staging.ticketpulse.dev/v2
    description: Staging

security:
  - bearerAuth: []

paths:
  /events:
    get:
      operationId: listEvents
      summary: List upcoming events
      description: |
        Returns a paginated list of upcoming events. Results are ordered
        by event date ascending. Supports filtering by venue, category,
        date range, and price range.
      tags:
        - Events
      security: []  # Public endpoint — no auth required
      parameters:
        - name: venue_id
          in: query
          schema:
            type: string
            format: uuid
          description: Filter events by venue
          example: "550e8400-e29b-41d4-a716-446655440000"
        - name: category
          in: query
          schema:
            type: string
            enum:
              - concert
              - sports
              - theater
              - comedy
              - conference
          description: Filter by event category
        - name: date_from
          in: query
          schema:
            type: string
            format: date
          description: "Events on or after this date (ISO 8601: YYYY-MM-DD)"
          example: "2026-04-01"
        - name: date_to
          in: query
          schema:
            type: string
            format: date
          description: "Events on or before this date"
          example: "2026-06-30"
        - name: price_min
          in: query
          schema:
            type: integer
            minimum: 0
          description: "Minimum ticket price in cents"
        - name: price_max
          in: query
          schema:
            type: integer
            minimum: 0
          description: "Maximum ticket price in cents"
        - name: cursor
          in: query
          schema:
            type: string
          description: "Pagination cursor from previous response"
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: "Number of results per page"
      responses:
        "200":
          description: Successfully retrieved events
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EventListResponse"
              example:
                data:
                  - id: "evt_abc123"
                    title: "Arctic Monkeys — North American Tour"
                    slug: "arctic-monkeys-na-tour-2026"
                    category: "concert"
                    venue:
                      id: "ven_xyz789"
                      name: "Madison Square Garden"
                      city: "New York"
                      state: "NY"
                    date: "2026-05-15T20:00:00Z"
                    doors_open: "2026-05-15T18:30:00Z"
                    price_range:
                      min: 7500
                      max: 35000
                      currency: "USD"
                    availability: "available"
                    image_url: "https://cdn.ticketpulse.dev/events/evt_abc123/hero.jpg"
                pagination:
                  next_cursor: "eyJkYXRlIjoiMjAyNi0wNS0xNiJ9"
                  has_more: true
        "400":
          $ref: "#/components/responses/BadRequest"
        "429":
          $ref: "#/components/responses/RateLimited"
        "500":
          $ref: "#/components/responses/InternalError"

  /events/{event_id}:
    get:
      operationId: getEvent
      summary: Get event details
      tags:
        - Events
      security: []
      parameters:
        - name: event_id
          in: path
          required: true
          schema:
            type: string
          description: Event identifier
      responses:
        "200":
          description: Event details
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EventDetail"
        "404":
          $ref: "#/components/responses/NotFound"

  /reservations:
    post:
      operationId: createReservation
      summary: Reserve tickets for an event
      description: |
        Creates a ticket reservation. Returns 202 Accepted — the
        reservation is processed asynchronously. Poll the status
        endpoint or use WebSocket for real-time updates.
      tags:
        - Reservations
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateReservationRequest"
      responses:
        "202":
          description: Reservation accepted for processing
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ReservationAccepted"
        "400":
          $ref: "#/components/responses/BadRequest"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "409":
          description: Duplicate idempotency key
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "422":
          description: "Validation error (e.g., seats not available)"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Event:
      type: object
      required:
        - id
        - title
        - category
        - venue
        - date
        - price_range
        - availability
      properties:
        id:
          type: string
          description: Unique event identifier
        title:
          type: string
          maxLength: 200
        slug:
          type: string
          pattern: "^[a-z0-9-]+$"
        category:
          type: string
          enum: [concert, sports, theater, comedy, conference]
        venue:
          $ref: "#/components/schemas/VenueSummary"
        date:
          type: string
          format: date-time
        doors_open:
          type: string
          format: date-time
        price_range:
          $ref: "#/components/schemas/PriceRange"
        availability:
          type: string
          enum: [available, limited, sold_out]
        image_url:
          type: string
          format: uri

    EventDetail:
      allOf:
        - $ref: "#/components/schemas/Event"
        - type: object
          properties:
            description:
              type: string
              maxLength: 5000
            artists:
              type: array
              items:
                type: string
            sections:
              type: array
              items:
                $ref: "#/components/schemas/Section"
            policies:
              $ref: "#/components/schemas/EventPolicies"

    VenueSummary:
      type: object
      required: [id, name, city, state]
      properties:
        id:
          type: string
        name:
          type: string
        city:
          type: string
        state:
          type: string

    PriceRange:
      type: object
      required: [min, max, currency]
      properties:
        min:
          type: integer
          description: Minimum price in cents
        max:
          type: integer
          description: Maximum price in cents
        currency:
          type: string
          pattern: "^[A-Z]{3}$"
          description: ISO 4217 currency code

    Section:
      type: object
      required: [id, name, price, available_seats]
      properties:
        id:
          type: string
        name:
          type: string
        price:
          type: integer
          description: Price per seat in cents
        available_seats:
          type: integer
          minimum: 0

    EventPolicies:
      type: object
      properties:
        refund_policy:
          type: string
        age_restriction:
          type: string
        max_tickets_per_order:
          type: integer
          minimum: 1
          maximum: 8

    CreateReservationRequest:
      type: object
      required: [event_id, seat_ids, idempotency_key]
      properties:
        event_id:
          type: string
        seat_ids:
          type: array
          items:
            type: string
          minItems: 1
          maxItems: 8
        idempotency_key:
          type: string
          format: uuid
          description: |
            Client-generated UUID for idempotent reservation creation.
            If a reservation with this key already exists, the existing
            reservation is returned.

    ReservationAccepted:
      type: object
      required: [reservation_id, status, status_url]
      properties:
        reservation_id:
          type: string
        status:
          type: string
          enum: [pending]
        status_url:
          type: string
          format: uri

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
      required: [has_more]
      properties:
        next_cursor:
          type: string
        has_more:
          type: boolean

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          description: Machine-readable error code
        message:
          type: string
          description: Human-readable error message
        details:
          type: object
          description: Additional error context

  responses:
    BadRequest:
      description: Invalid request parameters
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
          example:
            code: "invalid_parameter"
            message: "date_from must be a valid ISO 8601 date"
    Unauthorized:
      description: Missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    RateLimited:
      description: Too many requests
      headers:
        Retry-After:
          schema:
            type: integer
          description: Seconds until the rate limit resets
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    InternalError:
      description: Unexpected server error
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
```

Look at what this spec does for you: it defines every parameter with its type, constraints, and description. It covers all the error codes a consumer needs to handle. It includes concrete examples so that a frontend engineer can immediately understand what the response looks like. Compare this to "here is the endpoint, ask me what fields it returns" — which is how most APIs get consumed at teams without contract-first discipline. The OpenAPI spec is a gift to every engineer who will ever integrate with this API, including your future self.

### 4.3 AsyncAPI for Event-Driven APIs

AsyncAPI does for event-driven systems what OpenAPI does for REST. Here is the TicketPulse reservation events spec:

```yaml
asyncapi: 3.0.0
info:
  title: TicketPulse Reservation Events
  version: 1.0.0
  description: |
    Event-driven reservation pipeline. All messages use Avro
    serialization with Schema Registry.

servers:
  production:
    host: kafka.ticketpulse.internal:9092
    protocol: kafka
    description: Production Kafka cluster (MSK)

channels:
  reservationCreated:
    address: reservations.created
    messages:
      ReservationCreated:
        $ref: "#/components/messages/ReservationCreated"
    description: |
      Published when a user initiates a ticket reservation.
      Partitioned by event_id for ordered processing.

  paymentCompleted:
    address: reservations.payment.completed
    messages:
      PaymentCompleted:
        $ref: "#/components/messages/PaymentCompleted"
    description: Published when payment is successfully processed.

  paymentFailed:
    address: reservations.payment.failed
    messages:
      PaymentFailed:
        $ref: "#/components/messages/PaymentFailed"
    description: Published when payment processing fails.

  reservationConfirmed:
    address: reservations.confirmed
    messages:
      ReservationConfirmed:
        $ref: "#/components/messages/ReservationConfirmed"
    description: Published when the reservation is fully confirmed.

operations:
  publishReservationCreated:
    action: send
    channel:
      $ref: "#/channels/reservationCreated"
    summary: ReservationService publishes when a new reservation is initiated

  consumeReservationCreated:
    action: receive
    channel:
      $ref: "#/channels/reservationCreated"
    summary: PaymentWorker and InventoryWorker consume new reservations

  publishPaymentCompleted:
    action: send
    channel:
      $ref: "#/channels/paymentCompleted"
    summary: PaymentWorker publishes on successful payment

  consumePaymentCompleted:
    action: receive
    channel:
      $ref: "#/channels/paymentCompleted"
    summary: ReservationService consumes to update reservation status

components:
  messages:
    ReservationCreated:
      name: ReservationCreated
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - event_id
          - user_id
          - seat_ids
          - idempotency_key
          - created_at
        properties:
          reservation_id:
            type: string
            description: Unique reservation identifier
          event_id:
            type: string
            description: Event being reserved
          user_id:
            type: string
            description: User making the reservation
          seat_ids:
            type: array
            items:
              type: string
            description: Seats being reserved
          idempotency_key:
            type: string
            format: uuid
          total_amount_cents:
            type: integer
            description: Total price in cents
          currency:
            type: string
            default: USD
          created_at:
            type: string
            format: date-time

    PaymentCompleted:
      name: PaymentCompleted
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - payment_id
          - amount_cents
          - completed_at
        properties:
          reservation_id:
            type: string
          payment_id:
            type: string
            description: Stripe PaymentIntent ID
          amount_cents:
            type: integer
          completed_at:
            type: string
            format: date-time

    PaymentFailed:
      name: PaymentFailed
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - failure_reason
          - failed_at
        properties:
          reservation_id:
            type: string
          failure_reason:
            type: string
            enum:
              - insufficient_funds
              - card_declined
              - expired_card
              - processing_error
              - fraud_detected
          failure_code:
            type: string
            description: Provider-specific error code
          failed_at:
            type: string
            format: date-time

    ReservationConfirmed:
      name: ReservationConfirmed
      contentType: application/json
      payload:
        type: object
        required:
          - reservation_id
          - event_id
          - user_id
          - confirmed_at
        properties:
          reservation_id:
            type: string
          event_id:
            type: string
          user_id:
            type: string
          seat_ids:
            type: array
            items:
              type: string
          confirmation_code:
            type: string
            description: Human-readable confirmation code (e.g., "TP-A3X9K2")
          confirmed_at:
            type: string
            format: date-time
```

### 4.4 Protocol Buffers for gRPC

For internal service-to-service communication where performance matters, Protocol Buffers define the contract:

```protobuf
syntax = "proto3";

package ticketpulse.inventory.v1;

import "google/protobuf/timestamp.proto";

option go_package = "github.com/ticketpulse/proto/inventory/v1";

// InventoryService manages seat availability and reservations.
// Internal service — not exposed to external clients.
service InventoryService {
  // ReserveSeats atomically reserves seats for a reservation.
  // Returns ALREADY_EXISTS if the idempotency_key was already used.
  // Returns RESOURCE_EXHAUSTED if any requested seat is unavailable.
  rpc ReserveSeats(ReserveSeatsRequest) returns (ReserveSeatsResponse);

  // ReleaseSeats releases previously reserved seats.
  // Used as a compensating transaction when payment fails.
  // Idempotent — releasing already-released seats is a no-op.
  rpc ReleaseSeats(ReleaseSeatsRequest) returns (ReleaseSeatsResponse);

  // GetAvailability returns real-time seat availability for an event.
  rpc GetAvailability(GetAvailabilityRequest) returns (GetAvailabilityResponse);

  // StreamAvailability provides real-time availability updates.
  rpc StreamAvailability(StreamAvailabilityRequest)
      returns (stream AvailabilityUpdate);
}

message ReserveSeatsRequest {
  string reservation_id = 1;
  string event_id = 2;
  repeated string seat_ids = 3;
  string idempotency_key = 4;
  // TTL for the reservation hold. If payment is not confirmed within
  // this duration, seats are automatically released.
  int32 hold_ttl_seconds = 5;  // Default: 600 (10 minutes)
}

message ReserveSeatsResponse {
  string reservation_id = 1;
  ReservationStatus status = 2;
  repeated SeatReservation seats = 3;
  google.protobuf.Timestamp expires_at = 4;
}

enum ReservationStatus {
  RESERVATION_STATUS_UNSPECIFIED = 0;
  RESERVATION_STATUS_HELD = 1;
  RESERVATION_STATUS_CONFIRMED = 2;
  RESERVATION_STATUS_RELEASED = 3;
  RESERVATION_STATUS_EXPIRED = 4;
}

message SeatReservation {
  string seat_id = 1;
  string section = 2;
  string row = 3;
  int32 number = 4;
  int32 price_cents = 5;
}

message ReleaseSeatsRequest {
  string reservation_id = 1;
  string event_id = 2;
  repeated string seat_ids = 3;
  string reason = 4;  // "payment_failed", "user_cancelled", "timeout"
}

message ReleaseSeatsResponse {
  int32 seats_released = 1;
}

message GetAvailabilityRequest {
  string event_id = 1;
  string section_id = 2;  // Optional — empty returns all sections
}

message GetAvailabilityResponse {
  string event_id = 1;
  repeated SectionAvailability sections = 2;
  google.protobuf.Timestamp as_of = 3;
}

message SectionAvailability {
  string section_id = 1;
  string name = 2;
  int32 total_seats = 3;
  int32 available_seats = 4;
  int32 price_cents = 5;
}

message StreamAvailabilityRequest {
  string event_id = 1;
}

message AvailabilityUpdate {
  string event_id = 1;
  string section_id = 2;
  int32 available_seats = 3;
  google.protobuf.Timestamp updated_at = 4;
}
```

### 4.5 The Code Generation Workflow

Once you have a contract, generate everything:

```bash
# From OpenAPI spec → TypeScript client SDK
npx @openapitools/openapi-generator-cli generate \
  -i specs/ticketpulse-api.yaml \
  -g typescript-fetch \
  -o generated/client-sdk \
  --additional-properties=supportsES6=true,typescriptThreePlus=true

# From OpenAPI spec → Go server stubs
npx @openapitools/openapi-generator-cli generate \
  -i specs/ticketpulse-api.yaml \
  -g go-server \
  -o generated/go-server

# From OpenAPI spec → TypeScript types only (lightweight)
npx openapi-typescript specs/ticketpulse-api.yaml \
  -o generated/types.ts

# From Protobuf → Go code
protoc --go_out=. --go-grpc_out=. \
  proto/inventory/v1/inventory.proto

# From Protobuf → TypeScript (for Node.js services)
npx grpc_tools_node_protoc \
  --ts_out=generated/ts \
  --grpc_out=generated/ts \
  proto/inventory/v1/inventory.proto
```

The generated TypeScript types from the OpenAPI spec look like this:

```typescript
// generated/types.ts — auto-generated, do not edit

export interface Event {
  id: string;
  title: string;
  slug?: string;
  category: "concert" | "sports" | "theater" | "comedy" | "conference";
  venue: VenueSummary;
  date: string;
  doors_open?: string;
  price_range: PriceRange;
  availability: "available" | "limited" | "sold_out";
  image_url?: string;
}

export interface CreateReservationRequest {
  event_id: string;
  seat_ids: string[];
  idempotency_key: string;
}

export interface ReservationAccepted {
  reservation_id: string;
  status: "pending";
  status_url: string;
}

// ... more types generated from every schema in the spec
```

Now the frontend team and backend team share the same types, generated from the same source of truth. If the spec changes, both sides regenerate and compilation errors tell you exactly what broke. That is the spec enforcing its own contract at compile time — one of the most powerful feedback loops in software engineering.

### 4.6 Contract Testing with Pact

Contract-first is only valuable if you verify that implementations match the contract. Pact is the standard tool for consumer-driven contract testing:

```typescript
// frontend/tests/contract/reservation.pact.ts
import { PactV4, MatchersV3 } from "@pact-foundation/pact";
const { like, eachLike, uuid } = MatchersV3;

const provider = new PactV4({
  consumer: "TicketPulse-WebApp",
  provider: "TicketPulse-API",
});

describe("Reservation API Contract", () => {
  it("creates a reservation and returns 202", async () => {
    await provider
      .addInteraction()
      .given("event evt_abc123 has available seats A1 and A2")
      .uponReceiving("a request to reserve seats")
      .withRequest("POST", "/api/v2/reservations", (builder) => {
        builder
          .headers({ "Content-Type": "application/json" })
          .jsonBody({
            event_id: "evt_abc123",
            seat_ids: ["A1", "A2"],
            idempotency_key: uuid(),
          });
      })
      .willRespondWith(202, (builder) => {
        builder.jsonBody({
          reservation_id: like("res_def456"),
          status: "pending",
          status_url: like("/api/v2/reservations/res_def456/status"),
        });
      })
      .executeTest(async (mockServer) => {
        const client = new TicketPulseClient(mockServer.url);
        const result = await client.createReservation({
          event_id: "evt_abc123",
          seat_ids: ["A1", "A2"],
        });

        expect(result.status).toBe("pending");
        expect(result.reservation_id).toBeDefined();
      });
  });
});
```

The Pact workflow:

1. **Consumer (frontend) writes a contract test** describing what it expects from the provider
2. **Pact generates a contract file** (JSON) from the test
3. **Provider (backend) verifies the contract** by replaying the consumer's expectations against the real implementation
4. **Pact Broker** (optional) stores contracts and tracks verification status across services

This closes the loop: the OpenAPI spec defines the contract, code generation produces types, and Pact verifies that the implementation matches. At no point can a backend engineer silently change a field name and break the frontend — the contract test will fail in CI, loudly, before the PR merges.

---

## 5. EXECUTABLE SPECIFICATIONS

### 5.1 BDD: Specs That Run as Tests

Behavior-Driven Development (BDD) closes the gap between specification and verification. Instead of writing requirements in one document and tests in another, you write specifications in a format that is both human-readable AND machine-executable.

This is the part where specs get genuinely exciting. You stop choosing between "document that's readable by stakeholders" and "tests that actually run." With Gherkin, you get both in one artifact.

Consider what this means in practice: your product manager can read your test suite. Your QA engineer can write test scenarios before implementation starts. Your compliance team can sign off on the exact scenarios that are verified in CI. A misunderstood requirement surfaces as a failing test before a single line of implementation code exists. That is the promise of BDD done well.

The Gherkin language is the standard:

```gherkin
Feature: Ticket Reservation
  As a TicketPulse user
  I want to reserve tickets for events
  So that I can attend live performances

  Background:
    Given the event "Arctic Monkeys — NA Tour" exists
    And the event has sections:
      | section    | price_cents | total_seats |
      | Floor      | 35000       | 200         |
      | Lower Bowl | 25000       | 500         |
      | Upper Bowl | 7500        | 1000        |
    And the user "alice@example.com" is authenticated

  Scenario: Successful reservation of available seats
    Given seats "F-A1" and "F-A2" in section "Floor" are available
    When Alice reserves seats "F-A1" and "F-A2"
    Then the reservation status should be "pending"
    And the reservation total should be 70000 cents
    And seats "F-A1" and "F-A2" should be held for 10 minutes

  Scenario: Reservation with unavailable seats
    Given seat "F-A1" is available
    And seat "F-A2" is already reserved by another user
    When Alice reserves seats "F-A1" and "F-A2"
    Then the reservation should fail with error "seats_unavailable"
    And seat "F-A1" should remain available
    And no payment should be initiated

  Scenario: Idempotent reservation creation
    Given Alice has already created a reservation with idempotency key "idk_123"
    When Alice creates another reservation with idempotency key "idk_123"
    Then the original reservation should be returned
    And no duplicate reservation should be created

  Scenario: Reservation hold expiration
    Given Alice has a pending reservation for seats "F-A1" and "F-A2"
    And the reservation hold TTL is 10 minutes
    When 11 minutes pass without payment confirmation
    Then the reservation status should be "expired"
    And seats "F-A1" and "F-A2" should be released
    And Alice should receive a "reservation_expired" notification

  Scenario: Concurrent reservation race condition
    Given seat "F-A1" is available
    And Alice and Bob both attempt to reserve seat "F-A1" simultaneously
    Then exactly one reservation should succeed
    And the other should fail with error "seats_unavailable"
    And the seat count should remain consistent

  Scenario Outline: Maximum tickets per order enforcement
    Given <available> seats are available in section "Floor"
    When Alice attempts to reserve <requested> seats
    Then the reservation should <result>

    Examples:
      | available | requested | result                                    |
      | 10        | 4         | succeed                                   |
      | 10        | 8         | succeed                                   |
      | 10        | 9         | fail with error "max_tickets_exceeded"    |
      | 2         | 4         | fail with error "insufficient_seats"      |
```

Notice the "Concurrent reservation race condition" scenario. That is not a unit test edge case — it is a business-critical correctness requirement expressed in plain English. When a new engineer joins the team, this file tells them, without ambiguity, that the system must handle concurrent reservation attempts correctly. When a refactor touches the reservation logic, these scenarios catch any regression immediately.

### 5.2 Implementing Gherkin Steps

The Gherkin spec becomes executable when you implement step definitions. Using Cucumber.js:

```typescript
// tests/steps/reservation.steps.ts
import { Given, When, Then, Before } from "@cucumber/cucumber";
import { expect } from "chai";
import { TestContext } from "../support/context";

let ctx: TestContext;

Before(async function () {
  ctx = new TestContext();
  await ctx.resetDatabase();
});

Given(
  "the event {string} exists",
  async function (eventTitle: string) {
    ctx.event = await ctx.createEvent({ title: eventTitle });
  }
);

Given(
  "the event has sections:",
  async function (dataTable) {
    const rows = dataTable.hashes();
    for (const row of rows) {
      await ctx.createSection({
        event_id: ctx.event.id,
        name: row.section,
        price_cents: parseInt(row.price_cents),
        total_seats: parseInt(row.total_seats),
      });
    }
  }
);

Given(
  "seats {string} and {string} in section {string} are available",
  async function (seat1: string, seat2: string, section: string) {
    const sectionRecord = await ctx.getSection(ctx.event.id, section);
    await ctx.ensureSeatsAvailable(sectionRecord.id, [seat1, seat2]);
  }
);

When(
  "Alice reserves seats {string} and {string}",
  async function (seat1: string, seat2: string) {
    ctx.reservationResult = await ctx.apiClient.createReservation({
      event_id: ctx.event.id,
      seat_ids: [seat1, seat2],
      idempotency_key: ctx.generateIdempotencyKey(),
    });
  }
);

Then(
  "the reservation status should be {string}",
  async function (expectedStatus: string) {
    expect(ctx.reservationResult.status).to.equal(expectedStatus);
  }
);

Then(
  "the reservation total should be {int} cents",
  async function (expectedTotal: number) {
    const details = await ctx.apiClient.getReservation(
      ctx.reservationResult.reservation_id
    );
    expect(details.total_amount_cents).to.equal(expectedTotal);
  }
);

Then(
  "seats {string} and {string} should be held for {int} minutes",
  async function (seat1: string, seat2: string, minutes: number) {
    const availability = await ctx.inventoryClient.getAvailability(
      ctx.event.id
    );
    const seat1Status = availability.seats.find((s) => s.id === seat1);
    const seat2Status = availability.seats.find((s) => s.id === seat2);

    expect(seat1Status?.status).to.equal("held");
    expect(seat2Status?.status).to.equal("held");

    const expectedExpiry = new Date(
      Date.now() + minutes * 60 * 1000
    );
    expect(new Date(seat1Status!.hold_expires_at)).to.be.closeTo(
      expectedExpiry,
      5000 // 5-second tolerance
    );
  }
);

Then(
  "the reservation should fail with error {string}",
  async function (errorCode: string) {
    expect(ctx.reservationResult.error?.code).to.equal(errorCode);
  }
);
```

### 5.3 When BDD Shines and When It Is Overkill

**BDD shines when:**

- Business stakeholders need to read and approve the test scenarios
- The domain is complex and edge cases are numerous (payments, compliance, reservations)
- Multiple teams need to agree on behavior before implementing
- Regulatory requirements demand human-readable test evidence
- The system has critical user-facing flows that must not regress

**BDD is overkill when:**

- The API is internal-only and the team is small
- The behavior is purely technical (connection pooling, caching logic)
- The feature is simple CRUD with no complex business rules
- You are prototyping and the requirements are still fluid

This calibration matters. BDD has a setup cost — writing step definitions, maintaining the test context, keeping the Gherkin in sync with implementation as requirements evolve. Apply it where it earns its keep. For a fintech payment flow or a healthcare authorization system, BDD is not optional — it is the spec that proves you built the right thing. For an internal admin dashboard that lists users? Overkill. Regular unit tests with clear names are sufficient.

### 5.4 Property-Based Testing as Specification

Property-based testing is another form of executable specification. Instead of specifying individual examples, you specify properties that should always hold:

```typescript
// tests/properties/reservation.property.ts
import * as fc from "fast-check";

describe("Reservation properties", () => {
  it("should never oversell seats", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 1000 }),   // total seats
        fc.integer({ min: 1, max: 100 }),     // concurrent requests
        fc.integer({ min: 1, max: 8 }),       // seats per request
        async (totalSeats, concurrentRequests, seatsPerRequest) => {
          const event = await createEventWithSeats(totalSeats);

          // Fire concurrent reservations
          const results = await Promise.allSettled(
            Array.from({ length: concurrentRequests }, () =>
              apiClient.createReservation({
                event_id: event.id,
                seat_count: seatsPerRequest,
              })
            )
          );

          const successfulReservations = results.filter(
            (r) => r.status === "fulfilled" && r.value.status !== "failed"
          );

          const totalReserved = successfulReservations.length * seatsPerRequest;

          // THE PROPERTY: total reserved seats must never exceed total seats
          expect(totalReserved).to.be.at.most(totalSeats);
        }
      ),
      { numRuns: 50 }  // Run 50 random combinations
    );
  });

  it("should produce consistent seat counts", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 500 }),
        async (totalSeats) => {
          const event = await createEventWithSeats(totalSeats);

          // Reserve some seats
          const reserved = Math.floor(Math.random() * totalSeats);
          await reserveNSeats(event.id, reserved);

          const availability = await apiClient.getAvailability(event.id);

          // THE PROPERTY: available + reserved + held = total
          const sum = availability.sections.reduce(
            (acc, s) => acc + s.available + s.reserved + s.held,
            0
          );
          expect(sum).to.equal(totalSeats);
        }
      )
    );
  });
});
```

Property-based tests encode invariants — rules that should hold for ALL possible inputs. They are particularly powerful for finding edge cases that example-based tests miss. "Never oversell seats" is not just a test case — it is a business rule expressed as an executable specification. When the property fails with a counter-example on some weird combination of inputs, you have found a real bug in your specification or implementation, not just a hypothetical.

---

## 6. SPECIFICATION LANGUAGES AND FORMATS

### 6.1 Comparison Table

| Format | Domain | Machine-Readable | Human-Readable | Generates Code | Best For |
|--------|--------|:---:|:---:|:---:|--------|
| OpenAPI | REST APIs | Yes | Yes (YAML) | Yes | External APIs, public docs |
| AsyncAPI | Event APIs | Yes | Yes (YAML) | Yes | Kafka, RabbitMQ, WebSocket |
| Protobuf | gRPC/RPC | Yes | Moderate | Yes | Internal service-to-service |
| JSON Schema | Data validation | Yes | Moderate | Yes | Request/response validation |
| GraphQL SDL | Graph APIs | Yes | Yes | Yes | Client-driven APIs |
| Gherkin | Business logic | Yes | Very | Tests only | Business-critical flows |
| ADR/RFC | Architecture | No | Very | No | Decision-making, alignment |
| CLAUDE.md | AI behavior | Moderate | Very | No (prompt) | AI agent configuration |

### 6.2 Decision Matrix

Use this to choose the right specification format:

**Is it a public-facing REST API?** → OpenAPI. No exceptions. The tooling ecosystem (Swagger UI, code generation, Postman import) is unmatched.

**Is it an event-driven system?** → AsyncAPI. It mirrors OpenAPI's structure for message-based systems, so if your team knows OpenAPI, the learning curve is minimal.

**Is it internal service-to-service over gRPC?** → Protobuf. The performance benefits of binary serialization and the type safety of generated code justify the reduced readability.

**Is it a client-driven API where different consumers need different data shapes?** → GraphQL SDL. The schema IS the specification.

**Is it a complex business process with stakeholder visibility requirements?** → Gherkin. The Given/When/Then format is readable by non-engineers and executable by CI.

**Is it a data format or configuration schema?** → JSON Schema. Supported by every language and used by OpenAPI internally.

**Is it an architectural decision?** → ADR. Short, committed to the repo alongside code.

**Is it a feature proposal affecting multiple teams?** → RFC. Longer, with alternatives and risk analysis.

The most common mistake is reaching for the most formal format for every situation. You do not need an OpenAPI spec for an internal helper script. You do not need a Gherkin scenario for a simple read endpoint. The right spec for the situation is the one that is actually going to get written, read, and maintained — not the theoretically most rigorous one.

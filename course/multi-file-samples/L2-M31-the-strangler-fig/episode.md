# Episode L2-M31: The Strangler Fig — Extracting Your First Service

## In This Episode
You'll use the Strangler Fig pattern to extract the Payments service from the TicketPulse monolith. By the end, two services run side by side behind an API gateway — the client sees no change, but the architecture is fundamentally different.

## Key Concepts
- The Strangler Fig pattern for incremental monolith decomposition
- Evaluating service extraction candidates (coupling, blast radius, data ownership)
- Service-to-service communication via HTTP
- API gateway routing (old code vs new service)
- Docker Compose multi-service orchestration

## Prerequisites
- Loop 1 complete (TicketPulse monolith with Postgres, Redis, auth, tests)
- If you can explain what a foreign key is and run `docker compose up`, you're ready

## Builds On
- L1-M30 (Loop 1 Capstone) — you have a working monolith; now you'll decompose it

## What's Next
- L2-M32 (Service Communication) — REST vs gRPC vs event-driven patterns for inter-service calls

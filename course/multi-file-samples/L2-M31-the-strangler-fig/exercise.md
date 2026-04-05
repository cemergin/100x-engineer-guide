# Exercise: Extract the Payments Service

## What We're Doing
You'll create a standalone Payments service, move payment logic out of the monolith, set up an API gateway to route traffic, and verify that everything works end-to-end.

## Before You Start
- TicketPulse monolith running (`docker compose up`)
- The ticket purchase flow working (test with curl)

## Steps

### Step 1: Create the Service Directory

```bash
mkdir -p services/payment-service/src
cd services/payment-service
```

Initialize with `package.json` and `tsconfig.json` (see lesson for the configs).

### Step 2: Build the Payment Service API

Create `src/server.ts` with Express endpoints:
- `POST /api/payments/charge` — process a payment
- `POST /api/payments/refund` — process a refund
- `GET /api/payments/:id` — get payment status
- `GET /api/payments/health` — health check

> **Before you continue:** What data does the Payment service own? What stays in the monolith? Draw the boundary.

### Step 3: Move Payment Logic from the Monolith

Identify payment-related code in the monolith:
- Payment processing function
- Refund logic
- Payment data models
- Payment-specific validation

Copy these to the new service. Don't delete from the monolith yet.

### Step 4: Add the Payment Service to Docker Compose

Add a new service block to `docker-compose.yml` for the payment service with its own Postgres database.

### Step 5: Set Up the API Gateway

Add an nginx or Express-based gateway that routes:
- `/api/payments/*` → Payment Service
- Everything else → Monolith

### Step 6: Update the Monolith

Change the monolith's ticket purchase flow to call the Payment Service via HTTP instead of using local payment code.

> **Pro tip:** Keep the old payment code in the monolith behind a feature flag. If the new service has issues, flip the flag and route locally again.

### Step 7: Test End-to-End

```bash
# Purchase a ticket (goes through gateway → monolith → payment service)
curl -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "email": "test@example.com"}'
```

Verify in the Payment Service logs that the charge was processed.

## What Just Happened?

You extracted a service without any client-visible change. The API gateway routes traffic transparently. The monolith is slightly smaller. This is the Strangler Fig in action — one vine at a time.

> **What did you notice?** Which part was hardest — the code extraction, the routing, or the inter-service communication? That tells you where microservices complexity actually lives.

## Try This

- Kill the payment service container. Does the monolith handle the failure gracefully?
- Add a 2-second delay to the payment service. How does the purchase flow respond?
- Check the Docker Compose logs — can you trace a request across both services?

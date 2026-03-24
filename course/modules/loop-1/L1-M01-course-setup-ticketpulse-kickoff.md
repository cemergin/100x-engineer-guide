# L1-M01: Course Setup & TicketPulse Kickoff

> **Loop 1 (Foundation)** | Section 1A: Tooling & Environment | ⏱️ 60 min | 🟢 Core | Prerequisites: A computer with Docker installed, basic terminal comfort
>
> **Source:** Chapters 12, 21 of the 100x Engineer Guide

## What You'll Learn
- How to get the TicketPulse application running locally with a single command
- How a real backend codebase is structured — and how to read one you've never seen before
- How to trace a request from `curl` through an API, into a database, and back

## Why This Matters

Welcome to the 100x Engineer Course. Here is the deal: you are not going to sit through lectures and take notes. You are going to build, break, debug, and ship a real system called **TicketPulse** — a concert ticketing platform that will grow from a simple CRUD app into a globally distributed, event-driven beast over the coming months.

Right now, in this first module, you are going to do the most important thing an engineer can do when joining a new project: **get it running, poke at it, and start building a mental model of how the pieces fit together**. By the end of this hour, you will have a running application, you will have hit its API, read its responses, traced a request through its code, and you will already know more about this codebase than many engineers know about codebases they've worked on for weeks.

Let's go.

## Prereq Check

Can you open a terminal and run `docker --version` and `docker compose version`? If both return version numbers, you're good. If not, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) first — it takes about 5 minutes.

Can you run `curl --version`? It's pre-installed on macOS and most Linux distributions. On Windows, use WSL2.

---

## Part 1: Clone and Launch (10 minutes)

The best way to understand a system is to see it alive. Let's get TicketPulse running before we read a single line of code.

### 1.1 Clone the Repo

Open your terminal and run:

```bash
git clone https://github.com/100x-engineer/ticketpulse.git
cd ticketpulse
```

You should see a directory listing something like this:

```
ticketpulse/
├── docker-compose.yml
├── Dockerfile
├── package.json
├── tsconfig.json
├── .env.example
├── README.md
├── src/
│   ├── index.ts                  # Application entry point
│   ├── config/
│   │   ├── database.ts           # Postgres connection config
│   │   ├── redis.ts              # Redis connection config
│   │   └── environment.ts        # Environment variable loading
│   ├── routes/
│   │   ├── index.ts              # Route registration
│   │   ├── events.ts             # GET/POST /api/events
│   │   ├── tickets.ts            # GET/POST /api/tickets
│   │   └── health.ts             # GET /api/health
│   ├── models/
│   │   ├── event.ts              # Event entity (concerts, shows)
│   │   ├── ticket.ts             # Ticket entity
│   │   └── venue.ts              # Venue entity
│   ├── services/
│   │   ├── event-service.ts      # Business logic for events
│   │   ├── ticket-service.ts     # Business logic for tickets
│   │   └── cache-service.ts      # Redis caching layer
│   ├── middleware/
│   │   ├── error-handler.ts      # Global error handling
│   │   ├── request-logger.ts     # Request logging middleware
│   │   └── validate.ts           # Request validation
│   └── db/
│       ├── migrations/           # Database schema migrations
│       │   ├── 001_create_venues.sql
│       │   ├── 002_create_events.sql
│       │   └── 003_create_tickets.sql
│       └── seed.ts               # Seed data (sample events, venues)
├── tests/
│   ├── events.test.ts
│   ├── tickets.test.ts
│   └── helpers/
│       └── setup.ts
└── scripts/
    ├── seed.sh
    └── reset-db.sh
```

Take 30 seconds to scan that tree. Don't read any code yet.

### 1.2 Fire It Up

```bash
cp .env.example .env
docker compose up --build
```

You'll see Docker pulling images, building the app, starting services. Watch the output scroll by. After 30-60 seconds, you should see something like:

```
ticketpulse-postgres-1  | database system is ready to accept connections
ticketpulse-redis-1     | Ready to accept connections tcp
ticketpulse-app-1       | [INFO] Running migrations...
ticketpulse-app-1       | [INFO] Seeding database with sample data...
ticketpulse-app-1       | [INFO] TicketPulse API listening on port 3000
```

That's three services starting up: a **Postgres database**, a **Redis cache**, and the **Node.js application** itself.

### 1.3 Verify It's Alive

Open a new terminal tab (keep the Docker logs running in the first one — you'll want to watch them).

```bash
curl http://localhost:3000/api/health
```

You should see:

```json
{"status":"ok","uptime":12.34,"database":"connected","cache":"connected"}
```

If you see that, congratulations — you have a running backend application with a database and cache. That took about 2 minutes. This is what Docker Compose gives you: a reproducible development environment that works the same on every machine.

---

## Part 2: Poke at the API (15 minutes)

Now let's actually use this thing. A ticketing system has events (concerts) and tickets. Let's explore.

### 2.1 List Events

```bash
curl -s http://localhost:3000/api/events | jq .
```

(If you don't have `jq` installed, just run the curl without `| jq .` — the output will be valid JSON, just harder to read. We'll install `jq` properly in Module 2.)

You should see something like:

```json
{
  "events": [
    {
      "id": 1,
      "title": "Midnight Echoes — World Tour 2026",
      "artist": "Midnight Echoes",
      "venue": {
        "id": 1,
        "name": "Madison Square Garden",
        "city": "New York",
        "capacity": 20000
      },
      "date": "2026-06-15T20:00:00.000Z",
      "price_cents": 8500,
      "tickets_total": 20000,
      "tickets_remaining": 19847,
      "status": "on_sale"
    },
    {
      "id": 2,
      "title": "Neon Dusk — Farewell Concert",
      "artist": "Neon Dusk",
      "venue": {
        "id": 2,
        "name": "The Wiltern",
        "city": "Los Angeles",
        "capacity": 1850
      },
      "date": "2026-07-22T21:00:00.000Z",
      "price_cents": 12000,
      "tickets_total": 1850,
      "tickets_remaining": 1850,
      "status": "on_sale"
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 20
}
```

Real data. A real API. Let's keep going.

### 2.2 Get a Single Event

```bash
curl -s http://localhost:3000/api/events/1 | jq .
```

### 2.3 Buy a Ticket

```bash
curl -s -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "customer_email": "you@example.com", "quantity": 2}' \
  | jq .
```

Expected response:

```json
{
  "tickets": [
    {
      "id": "tkt_a1b2c3d4",
      "event_id": 1,
      "customer_email": "you@example.com",
      "status": "confirmed",
      "created_at": "2026-03-24T10:30:00.000Z"
    },
    {
      "id": "tkt_e5f6g7h8",
      "event_id": 1,
      "customer_email": "you@example.com",
      "status": "confirmed",
      "created_at": "2026-03-24T10:30:00.000Z"
    }
  ],
  "total_charged_cents": 17000
}
```

Now look back at your Docker logs terminal. You should see the request being logged:

```
[INFO] POST /api/tickets 201 — 45ms
```

### 2.4 Check Ticket Count Changed

```bash
curl -s http://localhost:3000/api/events/1 | jq '.tickets_remaining'
```

It should now be 2 fewer than before. You just bought tickets, and the inventory updated. This is a real system doing real things.

### 2.5 Try to Break It

What happens if you try to buy tickets for an event that doesn't exist?

```bash
curl -s -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 99999, "customer_email": "test@example.com", "quantity": 1}' \
  | jq .
```

What status code did you get? What error message?

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 99999, "customer_email": "test@example.com", "quantity": 1}'
```

That `-o /dev/null -w "%{http_code}"` trick is one you'll use constantly — it discards the body and shows only the HTTP status code.

**Common Mistake:** Many engineers only test happy paths. Get in the habit of immediately trying to break things. Send bad data. Send missing fields. Send absurd values. The error handling tells you as much about a codebase as the happy path does.

---

## Part 3: Understand the Infrastructure (10 minutes)

### 3.1 Read the docker-compose.yml

This is the first file you should read in any new project that has one. It's the blueprint of the entire system.

Open `docker-compose.yml` in your editor, or read it in the terminal:

```bash
cat docker-compose.yml
```

You'll see three services:

**`app`** — The TicketPulse Node.js application:
- Built from the `Dockerfile` in the current directory
- Exposes port 3000
- Depends on `postgres` and `redis` (won't start until they're healthy)
- Mounts the `src/` directory as a volume (so code changes reload without rebuilding)

**`postgres`** — The PostgreSQL database:
- Uses the official `postgres:16` image
- Creates a database called `ticketpulse`
- Stores data in a named volume (`pgdata`) so it survives `docker compose down`
- Has a healthcheck that runs `pg_isready`

**`redis`** — The Redis cache:
- Uses the official `redis:7-alpine` image
- Exposes port 6379
- Has a healthcheck that runs `redis-cli ping`

### 3.2 Verify the Services

```bash
# See what's running
docker compose ps
```

You should see all three services in a "running" state with health status "healthy."

### 3.3 Peek Inside the Database

```bash
docker compose exec postgres psql -U ticketpulse -d ticketpulse -c "\dt"
```

This runs `psql` inside the running Postgres container. `\dt` lists all tables. You should see `venues`, `events`, `tickets`, and maybe a `migrations` table.

Let's look at the data:

```bash
docker compose exec postgres psql -U ticketpulse -d ticketpulse \
  -c "SELECT id, title, artist, tickets_remaining FROM events;"
```

There's your data — the same data the API returned, but now you're looking at it directly in the database.

### 3.4 Peek Inside Redis

```bash
docker compose exec redis redis-cli KEYS "*"
```

You might see keys like `events:list`, `events:1`, etc. — the cache layer stores API responses so repeated requests don't hit the database every time.

```bash
docker compose exec redis redis-cli GET "events:1"
```

That's the cached JSON for event 1. If you see it, the caching layer is working.

**Insight:** This three-tier architecture — application + database + cache — is the backbone of most backend systems you'll encounter in your career. Understanding how these three pieces talk to each other is fundamental. TicketPulse will grow way beyond this, but this foundation stays.

---

## Part 4: Read the Code (15 minutes)

Now comes the skill that separates great engineers from good ones: **reading code you didn't write**. You've seen the system from the outside. Let's go inside.

### 4.1 Start at the Entry Point

Every application has an entry point. For TicketPulse, it's `src/index.ts`.

```bash
cat src/index.ts
```

You'll see something like:

```typescript
import express from 'express';
import { connectDatabase } from './config/database';
import { connectRedis } from './config/redis';
import { registerRoutes } from './routes';
import { errorHandler } from './middleware/error-handler';
import { requestLogger } from './middleware/request-logger';

const app = express();

app.use(express.json());
app.use(requestLogger);

registerRoutes(app);

app.use(errorHandler);

async function start() {
  await connectDatabase();
  await connectRedis();

  const port = process.env.PORT || 3000;
  app.listen(port, () => {
    console.log(`[INFO] TicketPulse API listening on port ${port}`);
  });
}

start();
```

This tells you the entire application flow in 20 lines:
1. Create an Express app
2. Add JSON parsing middleware
3. Add request logging middleware
4. Register all routes
5. Add error handling (must be last — Express error handlers go at the end)
6. Connect to Postgres, connect to Redis, start listening

### 4.2 Trace a Request

Let's trace what happens when you hit `GET /api/events`.

**Step 1: Route registration** — Open `src/routes/index.ts`:

```bash
cat src/routes/index.ts
```

You'll see routes being mounted. The events routes are at `/api/events`.

**Step 2: The events route handler** — Open `src/routes/events.ts`:

```bash
cat src/routes/events.ts
```

The `GET /` handler (which becomes `GET /api/events` after mounting) does something like:
1. Check if the response is cached in Redis
2. If cached, return the cached response
3. If not cached, call the event service
4. Store the result in Redis with a TTL
5. Return the response

**Step 3: The service layer** — Open `src/services/event-service.ts`:

```bash
cat src/services/event-service.ts
```

The service queries the database, joins events with venues, and returns the data.

**Step 4: The model** — Open `src/models/event.ts`:

```bash
cat src/models/event.ts
```

The model defines the shape of an event and probably includes the SQL queries.

### 4.3 The Request Lifecycle

Here's what you just traced:

```
curl GET /api/events
  → Express receives the request
    → requestLogger middleware logs it
      → events route handler runs
        → cache-service checks Redis
          → MISS: event-service queries Postgres
            → Postgres returns rows
          → cache-service stores result in Redis
        → route handler sends JSON response
      → requestLogger logs the response time
    → Response sent to curl
```

**Pause & Reflect:** Before you looked at the code — based on the directory structure alone — could you have guessed this flow? The `routes/`, `services/`, `models/`, and `middleware/` directory names telegraph exactly how the code is organized. This pattern (route → service → model) shows up in the majority of backend applications, regardless of language or framework. Once you recognize it, you can navigate any new codebase in minutes.

### 4.4 The Error Path

Open `src/middleware/error-handler.ts`:

```bash
cat src/middleware/error-handler.ts
```

This is the centralized error handler. When any route throws an error, Express catches it and sends it here. The handler formats the error into a consistent JSON response with an appropriate status code.

Open `src/middleware/validate.ts`:

```bash
cat src/middleware/validate.ts
```

Validation middleware checks incoming request bodies. When you sent `event_id: 99999` earlier and got a 404, the route handler checked the database, didn't find the event, and threw a `NotFoundError`. The error handler caught it and returned a 404 with a message.

**Your Turn:** Open `src/routes/tickets.ts` and trace the `POST /` handler yourself. Can you follow the path from request to response? What validation happens? What error cases are handled? Take 5 minutes to read it. Don't skim — actually read each function call and understand what it does.

---

## Part 5: Make a Change (10 minutes)

You don't truly understand a codebase until you've changed it. Let's make a small modification and see it take effect immediately.

### 5.1 Add a Field to the Health Endpoint

Open `src/routes/health.ts` in your editor:

```bash
# Use your preferred editor, e.g.:
code src/routes/health.ts
# or
vim src/routes/health.ts
```

Find the health check response object and add a `version` field:

```typescript
// Add this to the response
version: process.env.npm_package_version || '0.1.0',
```

Save the file. Because Docker Compose is mounting the `src/` directory, the dev server should detect the change and restart automatically. Watch your Docker logs terminal for the restart.

Now test it:

```bash
curl -s http://localhost:3000/api/health | jq .
```

You should see the new `version` field in the response. You just made your first change to TicketPulse.

### 5.2 Watch the Logs

Keep your Docker logs terminal visible. Hit a few endpoints:

```bash
curl -s http://localhost:3000/api/events > /dev/null
curl -s http://localhost:3000/api/events/1 > /dev/null
curl -s http://localhost:3000/api/events/999 > /dev/null
```

Watch the log lines. Notice the status codes (200, 200, 404) and response times. These logs are your lifeline in production. Get comfortable reading them now.

### 5.3 Clean Up

When you're done for the day:

```bash
# Stop everything (preserves data)
docker compose down

# Stop everything AND delete data
docker compose down -v
```

The `-v` flag removes the named volumes, so your database will be fresh next time. During development, you usually want `docker compose down` (without `-v`) so your data persists between sessions.

---

## Module Summary

- **TicketPulse** is your companion for this entire course — a concert ticketing app built with Node.js, Postgres, and Redis
- **`docker compose up`** gives you a complete, reproducible development environment in one command
- The **route → service → model** pattern is the most common backend architecture, and once you see it, you'll recognize it everywhere
- **Reading a codebase** starts with the entry point, then traces requests through the layers — directory names are your map
- **Always test error cases** — `curl` with bad data tells you as much as the happy path
- **Docker Compose** orchestrates multiple services (app, database, cache) with dependency management and health checks

## What's Next

Your terminal is functional, but is it *fast*? In Module 2, you'll install the tools that will make you measurably more productive every single day — modern CLI tools that make searching, navigating, and manipulating code feel effortless. You'll feel the difference in the first 5 minutes.

## Further Reading

- [Docker Compose documentation](https://docs.docker.com/compose/) — reference for the `docker-compose.yml` format
- [Express.js guide](https://expressjs.com/en/guide/routing.html) — the web framework TicketPulse uses
- [The Twelve-Factor App](https://12factor.net/) — the methodology behind how TicketPulse is configured (especially Factor III: Config)

# TicketPulse — Course Code Checkpoints

This directory contains runnable code checkpoints for the TicketPulse application at key points in the course.

## How Checkpoints Work

Each loop has two checkpoints:

- **checkpoint-start/** — The state of TicketPulse at the *beginning* of that loop. Use this to jump into any loop without completing prior modules.
- **checkpoint-end/** — The state of TicketPulse at the *end* of that loop. Use this as a reference to check your work.

## Quick Start

```bash
cd loop-1/checkpoint-start
cp .env.example .env
docker compose up --build
```

After ~30 seconds, TicketPulse will be running at `http://localhost:3000`.

```bash
# Verify it's alive
curl http://localhost:3000/api/health

# List events
curl http://localhost:3000/api/events | jq .

# Buy a ticket
curl -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "email": "fan@example.com"}'
```

## Directory Structure

```
code/
├── loop-1/
│   ├── checkpoint-start/    # Simple CRUD monolith (Express + Postgres + Redis)
│   └── checkpoint-end/      # Monolith with auth, tests, CI/CD, caching, async notifications
├── loop-2/
│   ├── checkpoint-start/    # Same as Loop 1 end
│   └── checkpoint-end/      # Microservices + Kafka + Kubernetes + monitoring
└── loop-3/
    ├── checkpoint-start/    # Same as Loop 2 end
    └── checkpoint-end/      # Global multi-region + real-time + AI-powered platform
```

## Which Checkpoint Do I Need?

| Starting Module | Use This Checkpoint |
|-----------------|-------------------|
| L1-M01 through L1-M30 | `loop-1/checkpoint-start/` |
| L2-M31 through L2-M60 | `loop-2/checkpoint-start/` |
| L3-M61 through L3-M90 | `loop-3/checkpoint-start/` |

## Requirements

- Docker and Docker Compose (v2+)
- Node.js 20+ (for local development without Docker)
- A terminal with `curl` and optionally `jq`

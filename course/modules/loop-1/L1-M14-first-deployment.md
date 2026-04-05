# L1-M14: Your First Deployment

> **Loop 1 (Foundation)** | Section 1C: Building the API | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M01 (Course Setup)
>
> **Source:** Chapters 25, 5, 7, 8 of the 100x Engineer Guide

---

## The Goal

Right now, TicketPulse runs on your machine with `npm run dev`. That is fine for development, but it means "it works on my machine" and nowhere else.

By the end of this module, TicketPulse will be containerized. Anyone, anywhere, with Docker installed can run `docker compose up` and have the full stack running in seconds -- the app, the database, the cache, all wired together.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

If you already have docker compose running from M01, stop it and start fresh:

```bash
cd ticketpulse
docker compose down -v
```

Now let us see what we are working with. Check if Docker is running:

```bash
docker version
# Should show Client and Server versions

docker compose version
# Should show Docker Compose version 2.x+
```

Good. Let us build something.

---

## 1. Why Containers?

Before we write a Dockerfile, understand the problem containers solve.

Without containers:
- "It works on my machine" but not on yours (different Node version, different OS, different system libraries)
- Setting up a new developer takes hours of installing dependencies
- Production environment drifts from development
- Deploying means SSHing into a server and running commands manually

With containers:
- The Dockerfile IS the documentation for how to build and run the app
- Every environment runs the exact same image
- `docker compose up` gives every developer the same setup in seconds
- Deployment is "push new image, replace old container"

> **Insight:** Netflix pioneered "immutable infrastructure" -- they never SSH into production servers. Every change is a new Docker image deployed to replace the old one. If a server has a problem, they do not fix it -- they terminate it and spin up a new one from the known-good image.

---

## 2. Build: The Dockerfile (Step by Step)

We will write a multi-stage Dockerfile. Multi-stage means we use one stage to build the app and a separate stage to run it. The build tools (TypeScript compiler, dev dependencies) never end up in the production image.

```dockerfile
# Dockerfile

# ==============================================================
# Stage 1: Build
# ==============================================================
# This stage installs ALL dependencies (including devDependencies),
# compiles TypeScript, and produces the JavaScript output.

FROM node:20-alpine AS builder

# Set working directory inside the container
WORKDIR /app

# Copy package files FIRST (this layer gets cached if package.json hasn't changed)
COPY package.json package-lock.json ./

# Install ALL dependencies (including devDependencies for building)
RUN npm ci

# Now copy the source code
COPY tsconfig.json ./
COPY src/ ./src/

# Compile TypeScript to JavaScript
RUN npm run build

# Remove devDependencies -- we only need production deps in the final image
RUN npm ci --production && npm cache clean --force

# ==============================================================
# Stage 2: Production
# ==============================================================
# This stage copies ONLY the compiled output and production
# dependencies into a clean, minimal image.

FROM node:20-alpine AS production

# Security: don't run as root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy only what we need from the builder stage
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./package.json

# Copy migrations (needed at startup)
COPY migrations/ ./migrations/

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3000

# Expose the port
EXPOSE 3000

# Switch to non-root user
USER appuser

# Health check -- Docker will ping this every 30 seconds
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:3000/health || exit 1

# Start the application
CMD ["node", "dist/server.js"]
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Let us break down every decision:

### Why `node:20-alpine`?
- Alpine Linux is ~5MB vs ~900MB for Debian-based images
- Smaller image = faster builds, faster deployments, smaller attack surface
- The `-alpine` suffix is one of the highest-impact optimizations you can make

### Why copy `package.json` before `src/`?
- Docker caches each layer. If `package.json` has not changed, `npm ci` is skipped entirely
- This is huge -- `npm ci` takes 30-60 seconds, but source code changes happen every build
- Order your Dockerfile layers by change frequency: things that change rarely go first

### Why `npm ci` instead of `npm install`?
- `npm ci` installs the exact versions from `package-lock.json` (deterministic)
- `npm install` might resolve different versions (non-deterministic)
- In CI/CD and Docker, always use `npm ci`

### Why non-root user?
- If an attacker exploits a vulnerability in your app, they get shell access as that user
- As root: they own the entire container (and potentially escape to the host)
- As `appuser`: they can only access `/app` files, limiting damage

---

## 3. Build the Image

```bash
# Build the Docker image
docker build -t ticketpulse:latest .

# Check the image size
docker image ls ticketpulse
```

You should see something like:

```
REPOSITORY    TAG       SIZE
ticketpulse   latest    180MB
```

For comparison, a naive single-stage build (no multi-stage, Debian instead of Alpine):

```bash
# Don't actually build this -- just see the difference
# FROM node:20
# COPY . .
# RUN npm install
# CMD ["npx", "ts-node", "src/server.ts"]
# Result: ~1.2GB
```

Our multi-stage Alpine build is ~180MB vs ~1.2GB. That is an 85% reduction.

---

## 4. Build: Docker Compose for the Full Stack

Now let us wire up the entire stack -- app, Postgres, and Redis:

```yaml
# docker-compose.yml

services:
  # --- The TicketPulse API ---
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - PORT=3000
      - DATABASE_URL=postgresql://ticketpulse:ticketpulse@postgres:5432/ticketpulse
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=local-dev-secret-do-not-use-in-production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # --- PostgreSQL Database ---
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ticketpulse
      POSTGRES_PASSWORD: ticketpulse
      POSTGRES_DB: ticketpulse
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ticketpulse"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  # --- Redis Cache ---
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    command: redis-server --appendonly yes
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Key design decisions:

### `depends_on` with health checks
The app waits for Postgres and Redis to be **healthy**, not just started. Without this, the app would start before the database is ready and crash on the first query.

### Named volumes
`postgres_data` and `redis_data` persist data between restarts. Without volumes, every `docker compose down` would wipe your database.

### Service networking
Inside the Docker network, services reference each other by name: `postgres:5432`, `redis:6379`. Docker's internal DNS handles resolution. The app never needs to know IP addresses.

---

## 5. Try It: Bring Up the Stack

```bash
docker compose up --build
```

Watch the output. You will see:

1. Postgres starting and running its health check
2. Redis starting and running its health check
3. The app building (this takes a minute the first time)
4. The app starting once Postgres and Redis are healthy
5. Migration scripts running
6. "Server listening on port 3000"

Open a new terminal and test:

```bash
# Health check
curl -s http://localhost:3000/health | jq .

# Create an event
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Docker Test Event",
    "venue": "Container Hall",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .
```

It works. The entire stack is running in containers.

---

## 6. Try It: Watch the Logs

In a separate terminal:

```bash
# Follow logs from all services
docker compose logs -f

# Follow logs from just the app
docker compose logs -f app

# Follow logs from just Postgres
docker compose logs -f postgres
```

Now make some requests in another terminal and watch the logs scroll in real time. You can see:
- Request logs from the app
- Query logs from Postgres (if you enable `log_statement = 'all'`)
- Connection events from Redis

This is your first taste of observability. When something goes wrong, logs are the first place you look.

---

## 7. Build: Health Check Endpoint

If you do not already have one, add a health check endpoint that verifies the app can reach its dependencies:

```typescript
// src/routes/health.ts

import { Router, Request, Response } from 'express';
import { pool } from '../db';

const router = Router();

router.get('/', async (_req: Request, res: Response) => {
  const checks: Record<string, string> = {};

  // Check database
  try {
    await pool.query('SELECT 1');
    checks.database = 'ok';
  } catch {
    checks.database = 'error';
  }

  // Check Redis (if you have a Redis client)
  // try {
  //   await redisClient.ping();
  //   checks.redis = 'ok';
  // } catch {
  //   checks.redis = 'error';
  // }

  const allHealthy = Object.values(checks).every((v) => v === 'ok');

  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'ok' : 'degraded',
    timestamp: new Date().toISOString(),
    checks,
    uptime: process.uptime(),
  });
});

export default router;
```

Wire it up:

```typescript
// src/app.ts
import healthRouter from './routes/health';
app.use('/health', healthRouter);
```

Now Docker's HEALTHCHECK pings this endpoint. If the database goes down, the health check fails, and Docker knows the container is unhealthy. Orchestrators like Kubernetes use this to restart containers automatically.

---

## 8. Observe: Container Resource Usage

```bash
# Watch CPU and memory usage of each container in real time
docker stats
```

You will see something like:

```
CONTAINER ID   NAME                CPU %   MEM USAGE / LIMIT     MEM %   NET I/O         BLOCK I/O
a1b2c3d4e5f6   ticketpulse-app-1   0.15%   85.2MiB / 7.67GiB    1.08%   2.5kB / 1.8kB   0B / 0B
f6e5d4c3b2a1   ticketpulse-pg-1    0.02%   32.1MiB / 7.67GiB    0.41%   1.2kB / 800B    0B / 4.1MB
1a2b3c4d5e6f   ticketpulse-redis-1 0.01%   7.8MiB / 7.67GiB     0.10%   600B / 400B     0B / 0B
```

The Node.js app uses ~85MB, Postgres ~32MB, Redis ~8MB. These are your baselines. In a later module (L2-M45: Monitoring Stack), you will set up Prometheus and Grafana to track these over time and alert when they spike.

---

## 9. Image Optimization Checklist

Here are the optimizations we applied and some extras for production:

| Optimization | Why | Impact |
|-------------|-----|--------|
| Multi-stage build | Build tools stay out of production image | -70% size |
| Alpine base image | Minimal Linux distribution | -80% base size |
| Non-root user | Limits damage if compromised | Security |
| `.dockerignore` | Prevents copying node_modules, .git, etc. | -50% build context |
| Layer ordering | Dependencies before source code | Faster rebuilds |
| `npm ci` | Deterministic installs from lockfile | Reproducibility |
| Pin base image version | `node:20-alpine`, not `node:latest` | Reproducibility |
| HEALTHCHECK | Docker knows when the app is actually ready | Reliability |

Create a `.dockerignore` if you have not already:

```
# .dockerignore
node_modules
dist
.git
.env
.env.*
*.md
.vscode
coverage
.nyc_output
```

This prevents Docker from copying 200MB of `node_modules` into the build context (where they will be reinstalled anyway).

---

## 10. Graceful Shutdown

When Docker stops a container, it sends SIGTERM. Your app needs to handle this gracefully -- finish in-flight requests, close database connections, then exit:

```typescript
// src/server.ts -- add at the bottom

const server = app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});

// Graceful shutdown
function shutdown(signal: string) {
  console.log(`Received ${signal}. Shutting down gracefully...`);

  server.close(async () => {
    console.log('HTTP server closed.');

    // Close database pool
    await pool.end();
    console.log('Database pool closed.');

    process.exit(0);
  });

  // Force exit after 10 seconds if graceful shutdown fails
  setTimeout(() => {
    console.error('Forced shutdown after timeout.');
    process.exit(1);
  }, 10000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

Test it:

```bash
# Stop the app container gracefully
docker compose stop app

# Watch the logs -- you should see "Shutting down gracefully..."
docker compose logs app | tail -5
```

Without graceful shutdown, Docker sends SIGTERM, waits 10 seconds, then sends SIGKILL (which cannot be caught). In-flight requests get dropped, database connections leak, and data might be corrupted.

---

## 11. Reflect

> Think about these questions:
>
> 1. We use `node:20-alpine`. What happens when Alpine releases a security patch? How would you ensure your images get the update?
>
> 2. The `JWT_SECRET` is hardcoded in `docker-compose.yml`. In production, where should it come from? (Hint: Docker Secrets, or environment variables injected by the deployment platform.)
>
> 3. What happens if you run `docker compose up` on a machine with 512MB of RAM? How would you limit container memory in docker-compose.yml?
>
> 4. Our Postgres data is in a named volume. What happens to the data if you run `docker compose down -v`? How would you back it up?

---

## 12. Checkpoint

After this module, TicketPulse should have:

- [ ] Multi-stage Dockerfile (build stage + production stage)
- [ ] `docker-compose.yml` with app, Postgres, and Redis services
- [ ] Health checks on all three services
- [ ] Non-root user in the production image
- [ ] `.dockerignore` to keep the build context small
- [ ] Graceful shutdown handling (SIGTERM)
- [ ] Named volumes for data persistence
- [ ] `docker compose up --build` brings up the entire stack
- [ ] `docker stats` shows reasonable resource usage

**Next up:** L1-M15 where we set up CI/CD with GitHub Actions -- automated linting, testing, and building on every push.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Multi-stage build** | A Dockerfile with multiple `FROM` statements. Each stage can copy artifacts from previous stages. Build tools stay in the build stage; only production files go in the final image. |
| **Alpine** | A minimal Linux distribution (~5MB). Used as a base image for small, secure containers. |
| **`docker compose`** | A tool for defining and running multi-container applications. One YAML file describes the entire stack. |
| **Named volume** | A Docker-managed storage location that persists between container restarts. |
| **Health check** | A command Docker runs periodically to verify a container is working. Unhealthy containers can be restarted automatically. |
| **Graceful shutdown** | Handling SIGTERM by finishing in-flight work and closing connections cleanly before exiting. |
| **Build context** | The set of files Docker sends to the build engine. Controlled by `.dockerignore`. |
| **Immutable infrastructure** | The practice of never modifying running servers. Instead, deploy a new image and replace the old one. |
---

## What's Next

In **CI/CD Pipeline** (L1-M15), you'll build on what you learned here and take it further.

# L2-M50: Rate Limiting

> **Loop 2 (Applied)** | Section 2D: Advanced Patterns | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L2-M39 (Kubernetes Basics), L2-M43 (Alerting)
>
> **What you'll build:** You will protect TicketPulse from traffic spikes by implementing a Redis-backed token bucket rate limiter with per-user and global limits, proper HTTP headers, sliding window comparison, and per-endpoint configuration.

---

## The Goal

A popular artist announces a concert. Tickets go on sale at noon. 10,000 users hit the TicketPulse API simultaneously. Without rate limiting, the database is overwhelmed, the payment service buckles, and nobody gets tickets. With rate limiting, traffic is controlled, the system stays healthy, and users get a fair experience.

Rate limiting is not about saying "no" to users. It is about saying "not yet" -- smoothing demand so the system can serve everyone.

**You will run code within the first two minutes.**

---

## 0. Quick Start: See the Problem (3 minutes)

Simulate a ticket rush with no protection:

```bash
# Fire 100 concurrent requests at the event listing endpoint
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code} " \
    http://localhost:3000/api/events/evt_1/tickets &
done
wait
echo ""
```

If your database connection pool is 20, requests 21-100 queue up. Response times spike from 50ms to 5 seconds. Some requests timeout. The entire platform slows down -- not just the ticket rush endpoint, but also users browsing other events, checking their orders, and viewing their profiles.

---

## 1. Build: Token Bucket with Redis (15 minutes)

The token bucket algorithm: imagine a bucket that holds tokens. Tokens are added at a fixed rate. Each request consumes one token. If the bucket is empty, the request is rejected.

Why Redis? Because TicketPulse runs multiple replicas in Kubernetes. Rate limit state must be shared across all pods. An in-memory counter per pod would allow `N * limit` total requests (where N is the number of pods).

The critical implementation detail: the check-and-decrement must be atomic. If two pods both read "1 token remaining" at the same time, both allow the request, and the limit is exceeded. Redis Lua scripts solve this -- they execute atomically.

```typescript
// src/middleware/rate-limiter.ts

import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

// Lua script runs atomically in Redis -- no race conditions between pods
const TOKEN_BUCKET_SCRIPT = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refillRate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('hmget', key, 'tokens', 'lastRefill')
local tokens = tonumber(bucket[1])
local lastRefill = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  lastRefill = now
end

local elapsed = (now - lastRefill) / 1000
local newTokens = elapsed * refillRate
tokens = math.min(capacity, tokens + newTokens)

if tokens >= 1 then
  tokens = tokens - 1
  redis.call('hmset', key, 'tokens', tokens, 'lastRefill', now)
  redis.call('expire', key, 60)
  return {1, math.floor(tokens), capacity}
else
  redis.call('hmset', key, 'tokens', tokens, 'lastRefill', now)
  redis.call('expire', key, 60)
  local retryAfter = math.ceil((1 - tokens) / refillRate * 1000)
  return {0, 0, capacity, retryAfter}
end
`;

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  limit: number;
  retryAfterMs?: number;
}

export async function checkRateLimit(
  key: string,
  capacity: number,
  refillRatePerSecond: number
): Promise<RateLimitResult> {
  const now = Date.now();
  const result = await redis.call(
    'evalsha',
    // In production, use EVALSHA with a pre-loaded script hash for performance.
    // For clarity here, we use the direct approach:
  ) as number[];

  // Use the Lua script via ioredis's built-in eval support:
  const evalResult = await (redis as any).eval(
    TOKEN_BUCKET_SCRIPT,
    1,
    key,
    capacity,
    refillRatePerSecond,
    now
  ) as number[];

  if (evalResult[0] === 1) {
    return { allowed: true, remaining: evalResult[1], limit: evalResult[2] };
  } else {
    return {
      allowed: false,
      remaining: 0,
      limit: evalResult[2],
      retryAfterMs: evalResult[3],
    };
  }
}
```

Actually, let us simplify the TypeScript wrapper. The Lua script is the important part -- the wrapper is straightforward:

```typescript
// src/middleware/rate-limiter.ts (clean version)

import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

const TOKEN_BUCKET_LUA = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refillRate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('hmget', key, 'tokens', 'lastRefill')
local tokens = tonumber(bucket[1])
local lastRefill = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  lastRefill = now
end

local elapsed = (now - lastRefill) / 1000
local newTokens = elapsed * refillRate
tokens = math.min(capacity, tokens + newTokens)

if tokens >= 1 then
  tokens = tokens - 1
  redis.call('hmset', key, 'tokens', tokens, 'lastRefill', now)
  redis.call('expire', key, 60)
  return {1, math.floor(tokens), capacity}
else
  redis.call('hmset', key, 'tokens', tokens, 'lastRefill', now)
  redis.call('expire', key, 60)
  local retryAfter = math.ceil((1 - tokens) / refillRate * 1000)
  return {0, 0, capacity, retryAfter}
end
`;

// Define the command once, call it many times
redis.defineCommand('tokenBucket', {
  numberOfKeys: 1,
  lua: TOKEN_BUCKET_LUA,
});

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  limit: number;
  retryAfterMs?: number;
}

export async function checkRateLimit(
  key: string,
  capacity: number,
  refillRatePerSecond: number
): Promise<RateLimitResult> {
  const now = Date.now();
  const result = await (redis as any).tokenBucket(
    key, capacity, refillRatePerSecond, now
  ) as number[];

  if (result[0] === 1) {
    return { allowed: true, remaining: result[1], limit: result[2] };
  }
  return {
    allowed: false,
    remaining: 0,
    limit: result[2],
    retryAfterMs: result[3],
  };
}
```

Wire it into Express middleware:

```typescript
// src/middleware/rate-limit-middleware.ts

import { Request, Response, NextFunction } from 'express';
import { checkRateLimit } from './rate-limiter';

interface RateLimitConfig {
  perUser: { capacity: number; refillRate: number };
  global: { capacity: number; refillRate: number };
}

const DEFAULT_CONFIG: RateLimitConfig = {
  perUser: { capacity: 10, refillRate: 10 },     // 10 req/s per user, burst of 10
  global: { capacity: 1000, refillRate: 1000 },   // 1000 req/s global, burst of 1000
};

export function rateLimitMiddleware(config: RateLimitConfig = DEFAULT_CONFIG) {
  return async (req: Request, res: Response, next: NextFunction) => {
    // --- YOUR DECISION POINT ---
    // How do you identify the user?
    // Option A: API key from header (for authenticated API consumers)
    // Option B: JWT user ID (for logged-in users)
    // Option C: IP address (for unauthenticated traffic -- less reliable behind proxies)
    //
    // TicketPulse uses a combination: authenticated users get per-user limits,
    // unauthenticated requests get per-IP limits.

    const userId = (req as any).user?.id || req.ip;

    // Check global limit first
    const globalResult = await checkRateLimit(
      'ratelimit:global',
      config.global.capacity,
      config.global.refillRate
    );

    if (!globalResult.allowed) {
      return sendRateLimitResponse(res, globalResult, 'global');
    }

    // Check per-user limit
    const userResult = await checkRateLimit(
      `ratelimit:user:${userId}`,
      config.perUser.capacity,
      config.perUser.refillRate
    );

    // Always set rate limit headers, even on success
    setRateLimitHeaders(res, userResult);

    if (!userResult.allowed) {
      return sendRateLimitResponse(res, userResult, 'per-user');
    }

    next();
  };
}

function setRateLimitHeaders(
  res: Response,
  result: { remaining: number; limit: number; retryAfterMs?: number }
) {
  res.set('X-RateLimit-Limit', String(result.limit));
  res.set('X-RateLimit-Remaining', String(result.remaining));
  res.set('X-RateLimit-Reset', String(Math.ceil(Date.now() / 1000) + 1));

  if (result.retryAfterMs) {
    res.set('Retry-After', String(Math.ceil(result.retryAfterMs / 1000)));
  }
}

function sendRateLimitResponse(
  res: Response,
  result: { retryAfterMs?: number; limit: number; remaining: number },
  scope: string
) {
  setRateLimitHeaders(res, result);
  res.status(429).json({
    error: 'Too Many Requests',
    message: `Rate limit exceeded (${scope}). Try again in ${Math.ceil((result.retryAfterMs || 1000) / 1000)} seconds.`,
    retryAfter: Math.ceil((result.retryAfterMs || 1000) / 1000),
  });
}
```

Register the middleware:

```typescript
// src/app.ts (excerpt)

import { rateLimitMiddleware } from './middleware/rate-limit-middleware';

app.use(rateLimitMiddleware());
```

---

## 2. Try It: Exceed the Limit (5 minutes)

```bash
# Send 15 rapid requests (limit is 10/second per user)
for i in $(seq 1 15); do
  curl -s -w "\nRequest $i: HTTP %{http_code}\n" \
    -D - http://localhost:3000/api/events 2>/dev/null | \
    grep -E "(Request|X-RateLimit|Retry-After)"
done
```

**Expected output:**

```
Request 1: HTTP 200
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
...
Request 10: HTTP 200
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
Request 11: HTTP 429
X-RateLimit-Remaining: 0
Retry-After: 1
```

The first 10 requests succeed. Requests 11+ get 429 with a `Retry-After` header telling the client when to try again. Well-behaved API clients use this header to back off automatically.

---

## 3. Algorithm Comparison (10 minutes)

The token bucket is not the only option. Implement a sliding window counter and compare.

### Sliding Window Counter

Fixed windows have a boundary problem: if the limit is 100/minute, a user can send 100 requests at 0:59 and 100 more at 1:01 -- 200 requests in 2 seconds. The sliding window fixes this.

```typescript
// src/middleware/sliding-window-limiter.ts

const SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local windowMs = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local currentWindow = math.floor(now / windowMs)
local previousWindow = currentWindow - 1

local currentKey = key .. ':' .. currentWindow
local previousKey = key .. ':' .. previousWindow

local currentCount = tonumber(redis.call('get', currentKey) or '0')
local previousCount = tonumber(redis.call('get', previousKey) or '0')

local elapsedInCurrentWindow = now - (currentWindow * windowMs)
local previousWeight = 1 - (elapsedInCurrentWindow / windowMs)
local estimatedCount = math.floor(previousCount * previousWeight) + currentCount

if estimatedCount < limit then
  redis.call('incr', currentKey)
  redis.call('expire', currentKey, math.ceil(windowMs / 1000) * 2)
  return {1, limit - estimatedCount - 1, limit}
else
  local retryAfterMs = windowMs - elapsedInCurrentWindow
  return {0, 0, limit, retryAfterMs}
end
`;
```

### Leaky Bucket

Smooths output to a constant rate -- good for protecting downstream services that cannot handle bursts:

```typescript
// src/middleware/leaky-bucket-limiter.ts

const LEAKY_BUCKET_LUA = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local leakRate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('hmget', key, 'water', 'lastLeak')
local water = tonumber(bucket[1]) or 0
local lastLeak = tonumber(bucket[2]) or now

local elapsed = (now - lastLeak) / 1000
local leaked = elapsed * leakRate
water = math.max(0, water - leaked)

if water < capacity then
  water = water + 1
  redis.call('hmset', key, 'water', water, 'lastLeak', now)
  redis.call('expire', key, 60)
  return {1, math.floor(capacity - water), capacity}
else
  redis.call('hmset', key, 'water', water, 'lastLeak', now)
  redis.call('expire', key, 60)
  local retryAfterMs = math.ceil((1 / leakRate) * 1000)
  return {0, 0, capacity, retryAfterMs}
end
`;
```

### Comparison

| Algorithm | Burst Handling | Smoothness | Memory | Best For |
|---|---|---|---|---|
| **Token bucket** | Allows bursts up to capacity | Moderate | Low (2 values per key) | Most API rate limiting |
| **Sliding window** | Smoothly rejects at boundary | High | Moderate (2 counters per key) | When you need consistent enforcement |
| **Leaky bucket** | No bursts -- constant output rate | Very high | Low (2 values per key) | Protecting downstream services from bursts |

> **Your decision:** Which algorithm should TicketPulse use for the purchase endpoint? Consider: during a ticket rush, is it better to allow a burst of purchases (token bucket) or enforce a constant rate (leaky bucket)?

---

## 4. Per-Endpoint Limits (8 minutes)

Not all endpoints are equal. Browsing events is cheap. Purchasing tickets is expensive (database writes, payment processing, seat locking).

```typescript
// src/middleware/endpoint-rate-limits.ts

import { Request, Response, NextFunction } from 'express';
import { checkRateLimit } from './rate-limiter';

interface EndpointLimitConfig {
  capacity: number;
  refillRate: number;
}

const ENDPOINT_LIMITS: Record<string, EndpointLimitConfig> = {
  // Browse endpoints: generous limits
  'GET:/api/events':           { capacity: 30, refillRate: 30 },
  'GET:/api/events/:id':       { capacity: 30, refillRate: 30 },

  // Search: moderate limits (heavier on the database)
  'GET:/api/search':           { capacity: 10, refillRate: 10 },

  // Purchase: strict limits (expensive operation)
  'POST:/api/orders':          { capacity: 3, refillRate: 1 },

  // Admin: different limits entirely
  'POST:/api/admin/events':    { capacity: 5, refillRate: 5 },
};

export function endpointRateLimitMiddleware() {
  return async (req: Request, res: Response, next: NextFunction) => {
    const routeKey = `${req.method}:${req.route?.path || req.path}`;
    const config = ENDPOINT_LIMITS[routeKey];

    if (!config) return next();

    const userId = (req as any).user?.id || req.ip;
    const result = await checkRateLimit(
      `ratelimit:endpoint:${userId}:${routeKey}`,
      config.capacity,
      config.refillRate
    );

    res.set('X-RateLimit-Limit', String(result.limit));
    res.set('X-RateLimit-Remaining', String(result.remaining));

    if (!result.allowed) {
      res.set('Retry-After', String(Math.ceil((result.retryAfterMs || 1000) / 1000)));
      return res.status(429).json({
        error: 'Too Many Requests',
        message: `Endpoint rate limit exceeded for ${routeKey}.`,
        retryAfter: Math.ceil((result.retryAfterMs || 1000) / 1000),
      });
    }

    next();
  };
}
```

Register it after the global rate limiter:

```typescript
app.use(rateLimitMiddleware());           // Global + per-user limits
app.use(endpointRateLimitMiddleware());   // Per-endpoint limits (additional)
```

A user can make 30 browse requests per second but only 1 purchase per second. This protects the expensive operations while keeping the browsing experience smooth.

---

## 5. Observe: Rate Limiter Metrics in Grafana (5 minutes)

```typescript
// src/middleware/rate-limit-metrics.ts

import { Counter, Histogram } from 'prom-client';

const rateLimitAllowed = new Counter({
  name: 'rate_limit_allowed_total',
  help: 'Requests allowed by rate limiter',
  labelNames: ['scope', 'endpoint'],
});

const rateLimitDenied = new Counter({
  name: 'rate_limit_denied_total',
  help: 'Requests denied by rate limiter (429s)',
  labelNames: ['scope', 'endpoint'],
});
```

Grafana dashboard queries:

```
Panel 1 - Rejection Rate:
  rate(rate_limit_denied_total[5m]) / (rate(rate_limit_allowed_total[5m]) + rate(rate_limit_denied_total[5m]))

Panel 2 - 429 Responses by Endpoint:
  rate(rate_limit_denied_total[1m])

Alert Rule:
  rate(rate_limit_denied_total{scope="global"}[5m]) > 100
  Summary: "Global rate limit is rejecting >100 req/s -- investigate if this is a traffic spike or an attack"
```

---

## Checkpoint

Before continuing, verify:

- [ ] Token bucket rate limiter works with Redis (shared across pods)
- [ ] Per-user limit: 10 req/s, returns 429 when exceeded
- [ ] Global limit: 1000 req/s
- [ ] Response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After`
- [ ] Purchase endpoint has stricter limits than browse endpoints
- [ ] Metrics show allowed/denied breakdown

```bash
git add -A && git commit -m "feat: add Redis-backed rate limiting with per-user and per-endpoint limits"
```

---

## Reflect

> A partner integrator sends 500 req/s for a legitimate bulk import. How do you handle this without blocking them or overloading the system?
>
> Options to consider:
> 1. **API key tiers** -- partner keys get higher limits than default users
> 2. **Dedicated bulk import endpoint** -- accepts a batch of items in one request instead of 500 individual requests
> 3. **Queue-based import** -- partner uploads a file, TicketPulse processes it asynchronously at a controlled rate
> 4. **Separate rate limit namespace** -- partner traffic does not count against the global limit but has its own ceiling
>
> The best answer is usually a combination: a bulk endpoint (reduces 500 requests to 1) with a higher per-key limit and queue-based processing for very large imports.

---

## Further Reading

- Stripe's rate limiting blog post -- practical patterns from a company that handles millions of API calls
- Cloudflare's rate limiting architecture -- how they handle rate limiting at global scale
- Redis documentation on Lua scripting -- essential for atomic rate limit operations
- "Designing Data-Intensive Applications" Chapter 8 -- distributed systems challenges that affect rate limiting

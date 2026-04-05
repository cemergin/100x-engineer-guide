# L3-M64: CDN & Edge Computing

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 75 min | 🟢 Core | Prerequisites: L3-M61 (Multi-Region Design), L3-M62 (Cloud Provider Deep Dive)
>
> **Source:** Chapters 1, 19, 21, 22, 23 of the 100x Engineer Guide

---

## Why This Matters

TicketPulse serves everything from the origin server in US-East. Every user worldwide — whether they are in New York or New Zealand — makes a round trip to Virginia for every image, JavaScript bundle, and CSS file. Your 2MB of static assets multiply by 160ms of round-trip time for users in Tokyo.

A CDN (Content Delivery Network) caches your content at edge locations worldwide. There are 400+ CDN edge locations globally. The nearest one to any user is typically within 20ms. Putting your static assets behind a CDN turns a 160ms fetch into a 20ms fetch for most users.

Edge computing goes further: instead of just caching static files, you run code at the edge. Auth token validation, feature flag resolution, geo-based recommendations — all without hitting your origin server.

> **Ecosystem note:** Chapter 21 of the 100x Engineer Guide covers the networking fundamentals that make CDNs work: BGP routing, anycast, TLS termination, and the physics of network latency. Understanding those mechanics gives you intuition for when CDNs help (latency-dominated workloads) and when they do not (compute-dominated workloads). This module is the applied companion: you will configure Cache-Control headers, set up a CDN, measure the improvement, and design an edge compute strategy.

**By the end of this module, your TicketPulse assets will be served from the edge, and you will have a design for what logic should run there.**

---

## 0. What a CDN Actually Does (5 minutes)

### The Request Path Without a CDN

```
User in Tokyo
    │
    │  160ms round trip to US-East
    ▼
Origin Server (US-East)
    │
    │  Reads from disk / generates response
    ▼
Response back to Tokyo (160ms)

Total: 320ms + processing time
```

### The Request Path With a CDN

```
User in Tokyo
    │
    │  10ms to nearest CDN edge (Tokyo POP)
    ▼
CDN Edge (Tokyo)
    │
    ├── Cache HIT → Return immediately (10ms back to user)
    │   Total: 20ms
    │
    └── Cache MISS → Fetch from origin (320ms)
        Cache the response for next request
        Return to user
        Total: 340ms (first request only)
```

The first request to any edge location pays the full round trip. Every subsequent request to that edge is served locally. For popular assets (JavaScript bundles, CSS, images), the cache hit ratio is typically 95-99%.

### Why CDNs Are Not Just "Caches"

Modern CDNs do far more than cache:
- **TLS termination at the edge:** Your users' HTTPS connections terminate at the nearby edge, not the distant origin. This eliminates the TLS handshake latency for distant users.
- **HTTP/2 multiplexing:** CDNs speak HTTP/2 or HTTP/3 to clients even if your origin only speaks HTTP/1.1.
- **Compression:** Brotli/gzip compression is applied at the edge, reducing payload size.
- **DDoS protection:** Most CDN providers absorb attack traffic at their edge rather than passing it to your origin.
- **Bot detection:** Cloudflare and others fingerprint and block bots at the edge.

Understanding this matters because "adding a CDN" is often presented as a single decision. In practice, you are making many decisions about which CDN capabilities to enable.

### CDN Providers

| Provider | Strengths | Free Tier |
|---|---|---|
| **Cloudflare** | Largest network (300+ cities). Free tier is generous. Built-in DDoS protection. Workers for edge compute. | Unlimited bandwidth on free plan |
| **CloudFront (AWS)** | Deep AWS integration. Lambda@Edge for compute. | 1TB/month for 12 months |
| **Cloud CDN (GCP)** | Integrated with Global Load Balancer. Simple setup. | Included with LB; pay per GB |
| **Fastly** | Real-time purging. VCL-based configuration. Compute@Edge (Wasm). | Limited free tier |

---

## 1. Put TicketPulse Behind a CDN (20 minutes)

### 🤔 Prediction Prompt

Before reading the caching strategy table, write down your own Cache-Control header for each asset type: hashed JS bundles, HTML pages, API responses, and user-specific data. Then compare with the reference.

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Configure Cache-Control Headers

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered the difference between `max-age` (browser cache) and `s-maxage` (CDN/shared cache)? You often want the CDN to cache aggressively while the browser does not, especially for API responses.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Hashed static assets get `immutable` (the hash changes when content changes). User-specific endpoints get `private, no-store`. Everything else is a spectrum -- use `s-maxage` with `stale-while-revalidate` for the best latency/freshness trade-off.
</details>


Before setting up a CDN, your origin server must tell the CDN what to cache and for how long. This is done via the `Cache-Control` HTTP header.

**Design your caching strategy for each asset type:**

| Asset Type | Example | Cache-Control | Why |
|---|---|---|---|
| Hashed static assets | `/assets/app.a1b2c3.js` | `public, max-age=31536000, immutable` | The hash in the filename changes when the content changes. Cache forever. |
| HTML pages | `/events/london-concert` | `public, max-age=0, s-maxage=60, stale-while-revalidate=300` | HTML can change. CDN caches for 60s. Serve stale for 5 min while revalidating. |
| Event images | `/images/events/concert.jpg` | `public, max-age=86400` | Images rarely change. Cache for 24 hours. |
| API responses | `/api/events` | `public, s-maxage=10, stale-while-revalidate=30` | API data changes frequently. CDN caches for 10s. Browser does not cache. |
| User-specific API | `/api/users/me/orders` | `private, no-store` | User data must never be cached by a CDN. |

**Key headers explained:**

| Header | Meaning |
|---|---|
| `public` | CDN and browsers can cache this. |
| `private` | Only the user's browser can cache this. CDN must not cache. |
| `max-age=N` | Browser caches for N seconds. |
| `s-maxage=N` | CDN caches for N seconds (overrides max-age for shared caches). |
| `immutable` | Content will never change at this URL. Do not revalidate. |
| `stale-while-revalidate=N` | Serve stale content while fetching fresh content in the background, for up to N seconds. |
| `no-store` | Do not cache at all. Not even in the browser. |

### Implement in Your Express/Fastify Server

```typescript
// Middleware to set Cache-Control based on path
app.use((req, res, next) => {
  const path = req.path;

  if (path.match(/\.[a-f0-9]{8,}\.(js|css|woff2|png|jpg|svg)$/)) {
    // Hashed static assets — cache forever
    res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
  } else if (path.startsWith('/api/users/me') || path.startsWith('/api/orders')) {
    // User-specific data — never cache on CDN
    res.setHeader('Cache-Control', 'private, no-store');
  } else if (path.startsWith('/api/')) {
    // Public API data — short CDN cache with stale-while-revalidate
    res.setHeader('Cache-Control', 'public, s-maxage=10, stale-while-revalidate=30');
  } else if (path.match(/\.(jpg|jpeg|png|gif|svg|webp)$/)) {
    // Images — cache for 24 hours
    res.setHeader('Cache-Control', 'public, max-age=86400');
  } else {
    // HTML pages — short CDN cache
    res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=60, stale-while-revalidate=300');
  }

  next();
});
```

### 🛠️ Build: Set Up Cloudflare (Free Tier)

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered testing with CloudFront cache behaviors if you are on AWS? Each behavior can have different TTLs, origin settings, and compression policies per path pattern (e.g., `/api/*` vs `/assets/*`).
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Cloudflare free tier is the fastest path to a working CDN. Point your DNS to Cloudflare nameservers, enable "Full (strict)" SSL mode, and verify cache hits via the `cf-cache-status` response header.
</details>


```
1. Sign up at cloudflare.com (free)
2. Add your domain (or use a subdomain)
3. Point your DNS to Cloudflare's nameservers
4. Cloudflare proxies all requests through its CDN automatically
5. Static assets are cached based on your Cache-Control headers
6. Enable "Auto Minify" for JS/CSS (optional)
7. Enable Brotli compression (enabled by default)
```

**Or: Set Up CloudFront (AWS)**

```bash
# Create a CloudFront distribution pointing to your ALB
aws cloudfront create-distribution \
  --origin-domain-name ticketpulse-alb-123456.us-east-1.elb.amazonaws.com \
  --default-cache-behavior '{
    "TargetOriginId": "ticketpulse-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true
  }'
```

### 📊 Exercise: Measure the Improvement

Test your CDN cache hit ratio and latency improvement:

```bash
# Test from your location — first request (cache MISS)
curl -s -o /dev/null -w "HTTP %{http_code} | Time: %{time_total}s | Size: %{size_download} bytes\n" \
  -H "Cache-Control: no-cache" \
  https://ticketpulse.example.com/assets/app.a1b2c3.js

# Second request — should be cache HIT
curl -s -o /dev/null -w "HTTP %{http_code} | Time: %{time_total}s\n" \
  -I https://ticketpulse.example.com/assets/app.a1b2c3.js

# Check the response headers for cache status
curl -sI https://ticketpulse.example.com/assets/app.a1b2c3.js | grep -i "cf-cache-status\|x-cache\|age"
# Cloudflare: cf-cache-status: HIT
# CloudFront: X-Cache: Hit from cloudfront
# Age: 42 (seconds since cached)
```

**To test from multiple regions,** use online tools:
- [KeyCDN Performance Test](https://tools.keycdn.com/performance) — tests from 10+ global locations
- [Pingdom](https://tools.pingdom.com/) — website speed test from different regions
- `curl` with different DNS servers to hit different edge locations

**Expected results:**
- Cache hit ratio for static assets: >95% after warm-up
- Latency for cached assets: 10-50ms regardless of user location
- Latency reduction for users far from origin: 3-10x improvement

**Record your measurements:**

```
CDN Performance Baseline (before)
──────────────────────────────────
Asset request from local:   ___ ms
Asset request from Tokyo:   ___ ms (use a VPN or testing tool)
Cache hit ratio:            N/A (no CDN yet)

CDN Performance After Setup
────────────────────────────
Asset request from local:   ___ ms (first: miss, second: hit)
Asset request from Tokyo:   ___ ms
Cache hit ratio (after 1h): ___ %
```

---

## 2. Stale-While-Revalidate: The Best Caching Strategy You're Not Using (5 minutes)

### The Best of Both Worlds

The `stale-while-revalidate` directive is the most underused caching strategy. Here is how it works for TicketPulse's event listings:

```
Cache-Control: public, s-maxage=60, stale-while-revalidate=300

Timeline:
  0s   — CDN fetches from origin. Caches response. Serves to user.
  30s  — Another request. Cache is fresh (< 60s). Serve immediately.
  90s  — Another request. Cache is stale (> 60s, < 360s).
         CDN serves the stale response IMMEDIATELY (fast!).
         CDN fetches a fresh response from origin in the background.
         Next request gets the fresh version.
  400s — Another request. Cache is too stale (> 360s). CDN fetches from origin synchronously.
```

**Why this matters for TicketPulse:**
- Event listings update rarely (maybe once per hour).
- Users expect instant page loads.
- Serving a 90-second-old event listing is perfectly fine.
- The user gets instant response. The CDN refreshes in the background. Everyone wins.

### 📐 Caching Strategy Workshop

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered the staleness tolerance of each resource? Ticket availability during a flash sale can tolerate at most ~5 seconds of staleness, while event reviews can tolerate 5 minutes.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
User-specific endpoints (`/api/users/me`) must be `private, no-store` -- if you accidentally cache them on the CDN, one user sees another user's data. For ticket counts, keep `s-maxage` very short (5-10s) with `stale-while-revalidate` as a buffer.
</details>


For each TicketPulse resource, choose the right caching strategy and justify it:

| Resource | Description | Staleness Tolerance | Your Cache-Control |
|---|---|---|---|
| `GET /api/events?city=london` | Public event listings | Up to 60 seconds | |
| `GET /api/events/{id}/tickets` | Available tickets for an event | 5 seconds maximum | |
| `GET /api/users/me` | Current user profile | Must be fresh | |
| `GET /static/logo.png` | Site logo (never changes) | Forever | |
| `GET /events/concert-2026` | HTML page for a concert | Up to 60 seconds | |
| `GET /api/events/{id}/reviews` | Reviews for an event | Up to 5 minutes | |

**Reference answers:**
- Event listings: `public, s-maxage=60, stale-while-revalidate=300` — stale is fine for browsing
- Available tickets: `public, s-maxage=5, stale-while-revalidate=10` — tight TTL; stale could show wrong count
- User profile: `private, no-store` — personalized, must never be shared
- Logo: `public, max-age=31536000, immutable` — never changes, cache forever
- Concert HTML: `public, max-age=0, s-maxage=60, stale-while-revalidate=300`
- Reviews: `public, s-maxage=300, stale-while-revalidate=600` — reviews are slow-moving

---

## 3. Cache Invalidation (15 minutes)

### The Two Hardest Problems in Computer Science

> "There are only two hard things in Computer Science: cache invalidation and naming things." — Phil Karlton

When an event organizer updates the event description, changes the lineup, or (worst case) cancels the event, the CDN is still serving the old version. You need to invalidate the cache.

### Strategies

**1. TTL-Based (Time to Live)**

Set a short TTL and accept that data can be stale for up to that duration.

```
Cache-Control: s-maxage=60
```

Pros: Simplest. No active invalidation needed.
Cons: Data can be stale for up to 60 seconds. For event cancellations, this might not be acceptable.

**2. Purge API**

Actively invalidate specific URLs when data changes.

```bash
# Cloudflare: Purge specific URLs
curl -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/purge_cache" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"files": ["https://ticketpulse.example.com/api/events/london-concert"]}'

# CloudFront: Create invalidation
aws cloudfront create-invalidation \
  --distribution-id E1EXAMPLE \
  --paths "/api/events/london-concert" "/events/london-concert"
```

Pros: Immediate invalidation. Fresh content served right away.
Cons: Purge API calls have costs and rate limits. CloudFront charges $0.005 per invalidation path (first 1000/month free).

**3. Versioned URLs (for static assets)**

```
/assets/app.js?v=20260324  →  /assets/app.js?v=20260325
OR (better):
/assets/app.a1b2c3d4.js   →  /assets/app.e5f6g7h8.js
```

The URL changes when the content changes. The old URL stays cached (and unused). The new URL is fetched fresh.

Pros: No invalidation needed. Works perfectly for build artifacts.
Cons: Only works for assets where you control the URL. Does not work for API responses.

### 📐 Design: TicketPulse Invalidation Strategy

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered combining short TTLs as the baseline with active purge via Pub/Sub for critical updates? TTL handles the common case; active invalidation handles "event cancelled" urgency.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use versioned URLs for static assets (never invalidate -- the hash changes). For event pages, publish an `EventUpdated` message to a cache invalidation worker that calls the CDN purge API for the affected URLs. CloudFront charges $0.005 per invalidation path after the first 1000/month.
</details>


```
┌────────────────────┐
│ Event Service      │
│ (event updated)    │
└────────┬───────────┘
         │ Publish event: EventUpdated
         ▼
┌────────────────────┐
│ Cache Invalidation │
│ Worker             │
│                    │
│ 1. Purge CDN cache │
│    for event URL   │
│ 2. Purge API cache │
│    for event data  │
│ 3. Log invalidation│
└────────────────────┘
```

When an event is updated:
1. The event service publishes an `EventUpdated` event to the message queue.
2. A cache invalidation worker consumes the event.
3. The worker calls the CDN's purge API for all URLs related to that event.
4. Within seconds, all edge locations serve the updated data.

For TicketPulse, combine strategies:
- **Static assets:** Versioned URLs (hash in filename). Never invalidate.
- **Event pages and API:** Short TTL (60s) with stale-while-revalidate (300s) as the baseline. Active purge via Pub/Sub for critical updates (event cancellation, lineup change).
- **User-specific data:** Never cached on CDN (`private, no-store`).

### 🛠️ Build: The Cache Invalidation Worker

<details>
<summary>💡 Hint 1: Direction</summary>
The worker should listen for domain events (like EventUpdated) and translate them into CDN purge API calls for all affected URLs.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use a Kafka consumer (or SQS/Pub/Sub) that subscribes to "events.updated" topics. For each event, construct the list of URLs to purge: the API endpoint, the HTML page, and the ticket availability endpoint.
</details>

```typescript
// workers/cache-invalidation.ts
import { Kafka, Consumer } from 'kafkajs';

const CLOUDFLARE_ZONE_ID = process.env.CLOUDFLARE_ZONE_ID!;
const CLOUDFLARE_TOKEN = process.env.CLOUDFLARE_TOKEN!;

async function purgeCloudflareCache(urls: string[]): Promise<void> {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/purge_cache`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${CLOUDFLARE_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ files: urls }),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`Cache purge failed: ${JSON.stringify(error)}`);
  }

  console.log(`Purged ${urls.length} URLs from CDN cache`);
}

async function handleEventUpdated(eventId: string): Promise<void> {
  const baseUrl = 'https://ticketpulse.example.com';
  const urlsToPurge = [
    `${baseUrl}/api/events/${eventId}`,
    `${baseUrl}/api/events/${eventId}/tickets`,
    `${baseUrl}/events/${eventId}`,  // The HTML page
  ];

  await purgeCloudflareCache(urlsToPurge);
}

// Kafka consumer for EventUpdated messages
const consumer: Consumer = /* initialize */;
await consumer.subscribe({ topic: 'events.updated' });

await consumer.run({
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value!.toString());
    await handleEventUpdated(event.eventId);
  },
});
```

### 📐 Cache Invalidation Scenario Workshop

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered that "Event cancelled" and "doors time changed" have very different urgency profiles? Not every update warrants a purge API call.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
For Scenario C (immutable JS bundle with a vulnerability): you cannot purge `immutable` from browser caches. The answer is always to change the URL -- your build tool generates a new hash when content changes. The old URL stays cached but is no longer referenced by any HTML.
</details>


Work through these scenarios. For each one, decide the right invalidation strategy and any edge cases to handle:

**Scenario A:** An event organizer changes the event description from "Doors open at 7pm" to "Doors open at 8pm." The event page is cached at the CDN with `s-maxage=60`.

Questions:
- How quickly should this update be visible to users?
- Is this worth an active purge call? Or is a 60-second TTL acceptable?
- What if the change was "Event cancelled" instead?

**Scenario B:** TicketPulse adds a new feature where event pages display a real-time ticket count. The ticket count changes every second during a flash sale.

Questions:
- Can you cache this at the CDN? If so, with what TTL?
- What is the user experience trade-off between freshness and performance?
- Is there a different architectural approach that avoids the caching problem entirely?

**Scenario C:** A JavaScript bundle (`/assets/app.a1b2c3.js`) cached with `max-age=31536000, immutable` has a security vulnerability. You need to update it immediately.

Questions:
- How do you invalidate a URL cached with `immutable`?
- Why is the answer "you change the URL" rather than "you purge the cache"?
- What build system changes are needed to guarantee this works?

**Answers:**
- Scenario A: The description change is low urgency — 60s TTL is fine. "Event cancelled" is high urgency — trigger an active purge immediately via the cache invalidation worker.
- Scenario B: You cannot meaningfully cache a real-time count with a 60s TTL — it will always be wrong during fast sales. Better approach: cache the static event page but serve the ticket count via a separate client-side request to a non-cached API endpoint (or WebSocket). Separating concerns at the page level avoids the problem.
- Scenario C: Change the URL. Your build tool should generate a new hash when the file content changes (it will, because the content changed). The old URL stays cached (harmless, since no users should have it in their HTML anymore after a new deploy). The new URL is fetched fresh.

---

## 4. Edge Computing (20 minutes)

### Beyond Static Caching: Running Code at the Edge

Edge compute platforms run your code at CDN edge locations. Instead of caching responses, you compute them at the edge.

| Platform | Provider | Runtime | Cold Start |
|---|---|---|---|
| **Cloudflare Workers** | Cloudflare | V8 isolates (JavaScript/Wasm) | 0ms (no cold start) |
| **Lambda@Edge** | AWS CloudFront | Node.js, Python | 50-200ms |
| **CloudFront Functions** | AWS CloudFront | JavaScript (lightweight) | <1ms |
| **Fastly Compute** | Fastly | Wasm (Rust, Go, JS) | 0ms |
| **Vercel Edge Functions** | Vercel | V8 isolates | 0ms |

### 📐 Design Exercise: What Should Run at the Edge?

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered the rule: if it needs a database transaction, it stays at the origin; if it is a local computation (JWT verify, hash, KV lookup), it belongs at the edge?
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
JWT validation is a local crypto operation (verify signature with a public key) -- perfect for the edge. Ticket purchases require strong consistency and payment processing -- must stay at origin. Geo-based recommendations can use a pre-computed index synced to edge KV.
</details>


Evaluate each of these TicketPulse operations. Should it run at the edge, at the origin, or both?

| Operation | Edge or Origin? | Why |
|---|---|---|
| Auth token validation (JWT) | ??? | ??? |
| Feature flag resolution | ??? | ??? |
| Geo-based event recommendations | ??? | ??? |
| A/B test assignment | ??? | ??? |
| Ticket purchase | ??? | ??? |
| Event page rendering | ??? | ??? |
| Bot detection / rate limiting | ??? | ??? |

**Reference Answers:**

| Operation | Decision | Reasoning |
|---|---|---|
| **Auth token validation** | Edge | JWT validation is a local operation (verify signature with public key). No database needed. Reject invalid tokens before they hit your origin. |
| **Feature flag resolution** | Edge | Feature flags can be synced to edge KV stores. Resolve instantly without origin round trip. |
| **Geo-based recommendations** | Edge | The edge knows the user's location. Return "events near you" from a pre-computed geo index at the edge. |
| **A/B test assignment** | Edge | Hash the user ID to assign a variant. No origin needed. Consistent assignment without a database. |
| **Ticket purchase** | Origin | Requires strong consistency, database transactions, payment processing. Cannot run at the edge. |
| **Event page rendering** | Both | Serve cached HTML from edge. If stale, revalidate from origin in background. |
| **Bot detection / rate limiting** | Edge | Block bots and enforce rate limits before traffic reaches your origin. Saves origin resources. |

### Example: JWT Validation at the Edge

```typescript
// Cloudflare Worker: Validate JWT before forwarding to origin
export default {
  async fetch(request: Request): Promise<Response> {
    // Public endpoints — skip auth
    const url = new URL(request.url);
    if (url.pathname === '/health' || url.pathname.startsWith('/api/events')) {
      return fetch(request);
    }

    // Extract and validate JWT
    const authHeader = request.headers.get('Authorization');
    if (!authHeader?.startsWith('Bearer ')) {
      return new Response('Unauthorized', { status: 401 });
    }

    const token = authHeader.slice(7);
    try {
      const payload = await verifyJWT(token, JWT_PUBLIC_KEY);

      // Forward to origin with validated user info
      const modifiedRequest = new Request(request, {
        headers: new Headers({
          ...Object.fromEntries(request.headers),
          'X-User-Id': payload.sub,
          'X-User-Email': payload.email,
        }),
      });

      return fetch(modifiedRequest);
    } catch (err) {
      return new Response('Invalid token', { status: 401 });
    }
  },
};
```

This rejects 100% of invalid tokens at the edge. Your origin server never sees them. During a credential stuffing attack, the edge absorbs the load instead of your backend.

### 🛠️ Build: Rate Limiting at the Edge

<details>
<summary>💡 Hint 1: Direction</summary>
Combine bot detection, rate limiting (using a KV counter per IP), and JWT validation in a single edge function that runs before any request reaches your origin.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Use Cloudflare KV (or equivalent) with TTL-based expiry for rate limit counters. Check the bot score first (cheapest check), then rate limit, then JWT -- fail fast at each layer.
</details>

Here is a more complete Cloudflare Worker that combines JWT validation, rate limiting, and bot detection:

```typescript
// Cloudflare Worker with rate limiting
const RATE_LIMIT = 100; // requests per minute per IP
const RATE_WINDOW = 60; // seconds

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const clientIP = request.headers.get('CF-Connecting-IP') ?? 'unknown';

    // Step 1: Bot detection (Cloudflare provides bot score)
    const botScore = (request as any).cf?.botManagement?.score ?? 100;
    if (botScore < 30) {
      // Very likely a bot — reject
      return new Response('Forbidden', { status: 403 });
    }

    // Step 2: Rate limiting using Cloudflare KV
    const rateLimitKey = `rate:${clientIP}`;
    const currentCount = parseInt(await env.KV.get(rateLimitKey) ?? '0');

    if (currentCount >= RATE_LIMIT) {
      return new Response('Rate limit exceeded', {
        status: 429,
        headers: {
          'Retry-After': RATE_WINDOW.toString(),
          'X-RateLimit-Limit': RATE_LIMIT.toString(),
          'X-RateLimit-Remaining': '0',
        },
      });
    }

    // Increment the counter (with TTL for auto-expiry)
    await env.KV.put(rateLimitKey, (currentCount + 1).toString(), {
      expirationTtl: RATE_WINDOW,
    });

    // Step 3: JWT validation (only for authenticated endpoints)
    if (url.pathname.startsWith('/api/users') || url.pathname.startsWith('/api/orders')) {
      const authHeader = request.headers.get('Authorization');
      if (!authHeader?.startsWith('Bearer ')) {
        return new Response('Unauthorized', { status: 401 });
      }
      // ... validate JWT ...
    }

    // Forward to origin
    return fetch(request);
  },
};
```

This single Worker, running at Cloudflare's edge in 300+ cities, handles bot detection, rate limiting, and auth — all before your origin sees a single request.

### 🤔 Reflect: What Percentage of TicketPulse Requests Could Be Served Entirely from the Edge?

Think about the traffic breakdown:
- 60% of requests are browsing events (cacheable, serve from CDN).
- 20% are static assets (cacheable, serve from CDN).
- 10% are authenticated API calls (auth at edge, data from origin).
- 5% are ticket purchases (must hit origin).
- 5% are user profile operations (must hit origin).

**~80% of TicketPulse requests can be served entirely from the edge** with no origin hit. This means your origin servers only need to handle 20% of total traffic. This is the power of a well-designed CDN and edge compute strategy.

The economic implication: your origin needs to be sized for 20% of expected traffic, not 100%. If you expect 100,000 requests/minute at peak, your origin only needs to handle 20,000 requests/minute. This dramatically reduces infrastructure cost.

---

## 5. Reflect (5 minutes)

### 🤔 Questions

1. **A CDN edge in Tokyo has a cached event page showing 500 tickets available. The origin in US-East knows only 50 are left (they sold fast). A user in Tokyo sees "500 available" and tries to buy. What happens?** How do you handle this gracefully?

2. **You add edge caching with `s-maxage=60`. Your CEO updates the homepage banner and calls you asking why it has not changed. What do you tell them? What will you change to prevent this call from happening again?**

3. **Cloudflare Workers have no cold start but limited CPU time (10ms on free, 50ms on paid per request). What kinds of operations fit within 10ms? What operations are too slow?**

4. **A competitor runs their entire application at the edge using Cloudflare Workers + Durable Objects. What are the trade-offs compared to TicketPulse's origin-centric architecture?**

5. **You have a TicketPulse event page with `s-maxage=60`. During a Taylor Swift flash sale, 50,000 requests/second hit the CDN for that event page. How many of those requests reach your origin server?** (Hint: think about cache hit rate after the first requests warm the cache.)

### 🤔 Reflection Prompt

Before this module, what percentage of web traffic did you think could be served without hitting origin? Has the "80% at the edge" number changed how you think about infrastructure sizing?

---

## 6. Checkpoint

After this module, you should have:

- [ ] Cache-Control headers configured for each TicketPulse asset type
- [ ] A CDN (Cloudflare or CloudFront) in front of TicketPulse (or a documented setup plan)
- [ ] Measured cache hit ratio and latency improvement from multiple regions
- [ ] Understanding of stale-while-revalidate and when to use it
- [ ] Completed the caching strategy workshop for TicketPulse's key endpoints
- [ ] A cache invalidation strategy combining TTL, purge API, and versioned URLs
- [ ] A cache invalidation worker that listens to event update messages and purges affected URLs
- [ ] A design document listing which TicketPulse operations should run at the edge
- [ ] Understanding that ~80% of typical web traffic can be served from the edge

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **CDN basics** | Cache content at 400+ edge locations worldwide. First request is slow, subsequent requests are fast. |
| **Cache-Control headers** | The origin server controls caching behavior. `immutable` for hashed assets, `s-maxage` + `stale-while-revalidate` for dynamic content. |
| **Stale-while-revalidate** | Serve stale content instantly while refreshing in the background. Best of both worlds for freshness and speed. |
| **Cache invalidation** | Use versioned URLs for static assets, purge API for critical updates, TTL for everything else. Never try to invalidate `immutable` URLs — change the URL instead. |
| **Edge compute** | Run code at CDN edge locations. Best for auth, feature flags, geo-routing, and rate limiting. Not for database operations. |
| **80% at the edge** | Most web traffic is cacheable or computable at the edge. Design your system to minimize origin hits. |
| **Edge economics** | Shifting 80% of traffic to the edge means your origin only needs to handle 20% of peak load. This reduces infrastructure cost significantly. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **CDN** | Content Delivery Network. A globally distributed network of servers that cache and serve content close to users. |
| **Edge location / POP** | Point of Presence. A physical location where CDN servers are deployed, typically in major cities worldwide. |
| **Cache hit ratio** | The percentage of requests served from cache vs fetched from origin. Higher is better. |
| **Stale-while-revalidate** | A caching directive that serves stale content immediately while fetching fresh content in the background. |
| **Purge / Invalidation** | Removing cached content from CDN edge locations, forcing the next request to fetch from origin. |
| **Edge compute** | Running application code at CDN edge locations instead of (or in addition to) a central origin server. |
| **V8 isolate** | A lightweight execution environment used by Cloudflare Workers. Faster startup than containers or VMs. |
| **TLS termination** | The process of decrypting an HTTPS connection. When done at the edge, users get fast TLS handshakes regardless of origin distance. |
| **Cache warming** | The process of pre-populating CDN caches, either by sending requests through the CDN or using the provider's warming API. |

---

## Further Reading

- [Cloudflare CDN Documentation](https://developers.cloudflare.com/cache/) — comprehensive caching guide
- [HTTP Caching (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching) — the definitive reference for Cache-Control
- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers/) — edge compute platform
- Jake Archibald, ["Caching best practices"](https://jakearchibald.com/2016/caching-best-practices/) — practical caching patterns, especially on the `immutable` directive
- **Chapter 21 of the 100x Engineer Guide**: Networking fundamentals — BGP, anycast, TLS, and the physics of latency
- [Cloudflare Blog: "How Cloudflare's Global Network Works"](https://blog.cloudflare.com/) — the engineering behind one of the world's largest CDNs

---

## What's Next

Next up: **[L3-M65: Consistent Hashing & Distributed Cache](L3-M65-consistent-hashing-and-distributed-cache.md)** -- you will go deeper into the cache layer, implementing consistent hashing rings and designing a multi-layer cache architecture for TicketPulse.

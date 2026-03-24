# L3-M64: CDN & Edge Computing

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L3-M61 (Multi-Region Design), L3-M62 (Cloud Provider Deep Dive)
>
> **What you'll build:** Put TicketPulse's static assets behind a CDN. Configure Cache-Control headers for different asset types. Measure the latency improvement. Design which TicketPulse logic could run at the edge. Implement a cache invalidation strategy for when event data changes.

---

## The Goal

TicketPulse serves everything from the origin server in US-East. Every user worldwide — whether they are in New York or New Zealand — makes a round trip to Virginia for every image, JavaScript bundle, and CSS file. Your 2MB of static assets multiply by 160ms of round-trip time for users in Tokyo.

A CDN (Content Delivery Network) caches your content at edge locations worldwide. There are 400+ CDN edge locations globally. The nearest one to any user is typically within 20ms. Putting your static assets behind a CDN turns a 160ms fetch into a 20ms fetch for most users.

Edge computing goes further: instead of just caching static files, you run code at the edge. Auth token validation, feature flag resolution, geo-based recommendations — all without hitting your origin server.

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

### CDN Providers

| Provider | Strengths | Free Tier |
|---|---|---|
| **Cloudflare** | Largest network (300+ cities). Free tier is generous. Built-in DDoS protection. Workers for edge compute. | Unlimited bandwidth on free plan |
| **CloudFront (AWS)** | Deep AWS integration. Lambda@Edge for compute. | 1TB/month for 12 months |
| **Cloud CDN (GCP)** | Integrated with Global Load Balancer. Simple setup. | Included with LB; pay per GB |
| **Fastly** | Real-time purging. VCL-based configuration. Compute@Edge (Wasm). | Limited free tier |

For this module, Cloudflare or CloudFront are the best options. Cloudflare's free tier has no bandwidth limit, making it ideal for learning.

---

## 1. Put TicketPulse Behind a CDN (15 minutes)

### 🛠️ Build: Configure Cache-Control Headers

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

### 📊 Observe: Measure the Improvement

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

---

## 2. Stale-While-Revalidate (5 minutes)

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

---

## 3. Cache Invalidation (10 minutes)

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

---

## 4. Edge Computing (15 minutes)

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

### 🤔 Reflect: What Percentage of TicketPulse Requests Could Be Served Entirely from the Edge?

Think about the traffic breakdown:
- 60% of requests are browsing events (cacheable, serve from CDN).
- 20% are static assets (cacheable, serve from CDN).
- 10% are authenticated API calls (auth at edge, data from origin).
- 5% are ticket purchases (must hit origin).
- 5% are user profile operations (must hit origin).

**~80% of TicketPulse requests can be served entirely from the edge** with no origin hit. This means your origin servers only need to handle 20% of total traffic. This is the power of a well-designed CDN and edge compute strategy.

---

## 5. Reflect (5 minutes)

### 🤔 Questions

1. **A CDN edge in Tokyo has a cached event page showing 500 tickets available. The origin in US-East knows only 50 are left (they sold fast). A user in Tokyo sees "500 available" and tries to buy. What happens?** How do you handle this gracefully?

2. **You add edge caching with `s-maxage=60`. Your CEO updates the homepage banner and calls you asking why it has not changed. What do you tell them?**

3. **Cloudflare Workers have no cold start but limited CPU time (10ms on free, 50ms on paid per request). What kinds of operations fit within 10ms?**

4. **A competitor runs their entire application at the edge using Cloudflare Workers + Durable Objects. What are the trade-offs compared to TicketPulse's origin-centric architecture?**

---

## 6. Checkpoint

After this module, you should have:

- [ ] Cache-Control headers configured for each TicketPulse asset type
- [ ] A CDN (Cloudflare or CloudFront) in front of TicketPulse (or a documented setup plan)
- [ ] Measured cache hit ratio and latency improvement from multiple regions
- [ ] Understanding of stale-while-revalidate and when to use it
- [ ] A cache invalidation strategy combining TTL, purge API, and versioned URLs
- [ ] A design document listing which TicketPulse operations should run at the edge
- [ ] Understanding that ~80% of typical web traffic can be served from the edge

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **CDN basics** | Cache content at 400+ edge locations worldwide. First request is slow, subsequent requests are fast. |
| **Cache-Control headers** | The origin server controls caching behavior. `immutable` for hashed assets, `s-maxage` + `stale-while-revalidate` for dynamic content. |
| **Stale-while-revalidate** | Serve stale content instantly while refreshing in the background. Best of both worlds for freshness and speed. |
| **Cache invalidation** | Use versioned URLs for static assets, purge API for critical updates, TTL for everything else. |
| **Edge compute** | Run code at CDN edge locations. Best for auth, feature flags, geo-routing, and rate limiting. Not for database operations. |
| **80% at the edge** | Most web traffic is cacheable or computable at the edge. Design your system to minimize origin hits. |

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

---

## Further Reading

- [Cloudflare CDN Documentation](https://developers.cloudflare.com/cache/) — comprehensive caching guide
- [HTTP Caching (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching) — the definitive reference for Cache-Control
- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers/) — edge compute platform
- Jake Archibald, ["Caching best practices"](https://jakearchibald.com/2016/caching-best-practices/) — practical caching patterns
- Chapter 1 of the 100x Engineer Guide: Section 2.3 (Load Balancing), Section 4.7 (Graceful Degradation)

# L1-M04: How the Internet Actually Works

> **Loop 1 (Foundation)** | Section 1A: Tooling & Environment | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M01 (TicketPulse running), comfort with the terminal
>
> **Source:** Chapters 12, 21 of the 100x Engineer Guide

## What You'll Learn
- The complete journey of an HTTP request — from DNS resolution through TCP handshake, TLS negotiation, HTTP exchange, and back — with nothing hand-waved
- How to use `curl -v` and `curl -w` to see every layer of a network request and measure where time is actually spent
- How to diagnose "the site is slow" by identifying whether the bottleneck is DNS, the network, TLS, or the server

## Why This Matters

When something goes wrong in production — and it will — the first question is always "where is the problem?" The frontend team says it's the backend. The backend team says it's the database. The database team says it's the network. The network team says everything looks fine.

The engineer who can actually diagnose network issues is the one who understands what happens between the moment a user presses Enter and the moment bytes arrive at the server. Not vaguely — specifically. Which DNS server was queried. How long the TCP handshake took. Whether TLS negotiated 1.2 or 1.3. What the Time to First Byte was.

This module gives you that understanding. You are going to trace real requests, read real protocol exchanges, and measure real timings. By the end, you will be able to look at a `curl -v` output and immediately know which layer is causing a problem. This is one of the most valuable debugging skills in all of backend engineering.

Let's start with a request.

## Prereq Check

Can you run `curl -v https://example.com` and see output? Can you run `dig example.com` and see DNS records? If `dig` is not installed, `nslookup` works as a substitute. On macOS, both are pre-installed. On Ubuntu: `sudo apt install dnsutils`.

---

## Part 1: Trace a Real Request (20 minutes)

### 1.1 The Verbose Curl

`curl -v` (verbose) shows you every layer of the HTTP stack. Run this right now:

```bash
curl -v https://api.github.com 2>&1 | head -50
```

(The `2>&1` redirects stderr to stdout, since `curl -v` writes the protocol details to stderr.)

Read the output carefully. It looks something like this:

```
*   Trying 140.82.114.6:443...
* Connected to api.github.com (140.82.114.6) port 443
* ALPN: curl offers h2,http/1.1
* (304) (OUT), TLS handshake, Client hello (1):
* (304) (IN), TLS handshake, Server hello (2):
* (304) (IN), TLS handshake, [no content] (0):
* (304) (IN), TLS handshake, Certificate (11):
* (304) (IN), TLS handshake, CERT verify ok.
* (304) (IN), TLS handshake, Finished (20):
* (304) (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / AEAD-AES128-GCM-SHA256
* ALPN: server accepted h2
* using HTTP/2
> GET / HTTP/2
> Host: api.github.com
> User-Agent: curl/8.4.0
> Accept: */*
>
< HTTP/2 200
< content-type: application/json; charset=utf-8
< x-ratelimit-limit: 60
< x-ratelimit-remaining: 58
...
```

Let's decode every single line.

**Lines starting with `*`** — These are connection-level information from curl:
- `Trying 140.82.114.6:443` — DNS resolved `api.github.com` to this IP, connecting to port 443 (HTTPS)
- `Connected to api.github.com` — TCP handshake succeeded
- `ALPN: curl offers h2,http/1.1` — Application Layer Protocol Negotiation: curl offers HTTP/2 and HTTP/1.1
- `TLS handshake` lines — The TLS negotiation happening in real-time
- `SSL connection using TLSv1.3` — TLS 1.3 was negotiated (good — it's the fastest and most secure)
- `ALPN: server accepted h2` — The server chose HTTP/2

**Lines starting with `>`** — These are what curl SENT (the request):
- `GET / HTTP/2` — The HTTP method, path, and protocol version
- `Host: api.github.com` — Required HTTP/1.1+ header
- `User-Agent: curl/8.4.0` — Identifies the client
- `Accept: */*` — We'll accept any content type

**Lines starting with `<`** — These are what the server SENT BACK (the response):
- `HTTP/2 200` — Status 200 OK over HTTP/2
- `content-type: application/json` — The response body is JSON
- `x-ratelimit-limit: 60` — GitHub allows 60 unauthenticated requests per hour

**Pause & Reflect:** Before reading on, look at that output again. Can you identify which lines correspond to DNS resolution, TCP connection, TLS handshake, and HTTP exchange? The four phases are all visible in a single `curl -v` output.

### 1.2 The Seven Steps

Every HTTPS request follows the same path. Let's be explicit about each step:

```
Step 1: DNS Resolution
  api.github.com → 140.82.114.6
  (Your OS resolver queried DNS and got back an IP address)

Step 2: TCP Three-Way Handshake
  Your machine → SYN → Server
  Server → SYN-ACK → Your machine
  Your machine → ACK → Server
  (Connection established — this cost 1 round-trip)

Step 3: TLS Handshake
  ClientHello → Server (offering TLS versions, cipher suites, key share)
  ServerHello + Certificate + Finished ← Server
  Finished → Server
  (Encrypted channel established — 1 round-trip with TLS 1.3)

Step 4: HTTP Request
  GET / HTTP/2
  Host: api.github.com
  (Sent over the encrypted connection)

Step 5: Server Processing
  GitHub's servers receive the request, process it, prepare the response

Step 6: HTTP Response
  HTTP/2 200
  Content-Type: application/json
  {...response body...}

Step 7: Connection Handling
  The connection stays open for reuse (HTTP/2 multiplexing)
  or closes (Connection: close)
```

### 1.3 Measure Each Step

`curl` has a powerful timing feature. Let's measure exactly how long each step takes:

```bash
curl -w "\n--- Timing Breakdown ---\n\
DNS Lookup:    %{time_namelookup}s\n\
TCP Connect:   %{time_connect}s\n\
TLS Handshake: %{time_appconnect}s\n\
TTFB:          %{time_starttransfer}s\n\
Total:         %{time_total}s\n\
\n--- Details ---\n\
IP:            %{remote_ip}\n\
HTTP Code:     %{http_code}\n\
HTTP Version:  %{http_version}\n\
Size (bytes):  %{size_download}\n\
Speed:         %{speed_download} bytes/sec\n" \
  -o /dev/null -s https://api.github.com
```

You'll see something like:

```
--- Timing Breakdown ---
DNS Lookup:    0.012345s
TCP Connect:   0.045678s
TLS Handshake: 0.089012s
TTFB:          0.234567s
Total:         0.245678s

--- Details ---
IP:            140.82.114.6
HTTP Code:     200
HTTP Version:  2
Size (bytes):  2345
Speed:         9500.000 bytes/sec
```

Let's read this:

- **DNS Lookup: 12ms** — Resolving the hostname to an IP. Fast because it was probably cached.
- **TCP Connect: 46ms** — DNS time + TCP handshake. The TCP handshake alone was ~33ms (46 - 12).
- **TLS Handshake: 89ms** — DNS + TCP + TLS. The TLS handshake alone was ~43ms (89 - 46).
- **TTFB: 235ms** — Time to First Byte. Everything above + server processing + first byte of response. Server processing was ~146ms (235 - 89).
- **Total: 246ms** — Total time including downloading the full response body.

**Try It Now:** Run the same command against TicketPulse locally:

```bash
curl -w "\n--- Timing ---\nDNS: %{time_namelookup}s | TCP: %{time_connect}s | TLS: %{time_appconnect}s | TTFB: %{time_starttransfer}s | Total: %{time_total}s\n" \
  -o /dev/null -s http://localhost:3000/api/events
```

Notice the difference: DNS is essentially 0 (localhost doesn't need resolution), TCP is sub-millisecond (no network latency), there's no TLS (HTTP, not HTTPS), and TTFB is dominated entirely by server processing time. This tells you something important: **when testing locally, the only meaningful metric is TTFB, because you've eliminated all network overhead.**

### 1.4 Compare: Cold vs Warm Requests

Run the same request twice in quick succession:

```bash
# First request (cold — may need DNS resolution)
curl -w "Total: %{time_total}s | DNS: %{time_namelookup}s\n" -o /dev/null -s https://api.github.com

# Second request (warm — DNS cached, possibly connection reused)
curl -w "Total: %{time_total}s | DNS: %{time_namelookup}s\n" -o /dev/null -s https://api.github.com
```

The second request is often significantly faster. Why? DNS is cached. On some systems, the TCP connection may be reused. This is why connection pooling matters so much in production.

**Insight:** The total overhead for a cold HTTPS request to a server 30ms away is roughly:
```
DNS:    ~50ms (uncached, full resolution)
TCP:    ~30ms (1 round-trip)
TLS:    ~30ms (1 round-trip with TLS 1.3)
Total overhead: ~110ms before a single byte of your request is processed
```
With connection pooling, subsequent requests skip DNS, TCP, and TLS entirely. The overhead drops to ~30ms (one round-trip for the HTTP exchange). This is why every production HTTP client uses connection pooling.

---

## Part 2: DNS — The Internet's Phone Book (20 minutes)

### 2.1 What DNS Actually Does

Every time you type a URL, the first thing that happens is DNS resolution: converting a human-readable hostname (`api.github.com`) into a machine-readable IP address (`140.82.114.6`). Without DNS, you'd need to memorize IP addresses.

**Try It Now:** Let's look up a domain:

```bash
dig api.github.com
```

You'll see output like:

```
; <<>> DiG 9.18.18-0ubuntu0.22.04.1-Ubuntu <<>> api.github.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; QUESTION SECTION:
;api.github.com.              IN      A

;; ANSWER SECTION:
api.github.com.       60      IN      A       140.82.114.6

;; Query time: 12 msec
;; SERVER: 8.8.8.8#53(8.8.8.8)
;; MSG SIZE  rcvd: 60
```

Decoding this:
- **QUESTION SECTION:** We asked for the A record (IPv4 address) of `api.github.com`
- **ANSWER SECTION:** The IP is `140.82.114.6`, with a TTL of 60 seconds (this answer is valid for 60 seconds before re-querying)
- **Query time: 12 msec** — How long the DNS query took
- **SERVER: 8.8.8.8** — Which DNS server answered (Google's public DNS)

### 2.2 Watch DNS Resolution Step by Step

The most impressive DNS command is `dig +trace`, which shows you the entire resolution chain from the root servers down:

```bash
dig +trace api.github.com
```

This shows every step of the recursive resolution:

```
.                       518400  IN  NS  a.root-servers.net.
.                       518400  IN  NS  b.root-servers.net.
...
;; Received 239 bytes from 198.41.0.4#53(a.root-servers.net) in 23 ms

com.                    172800  IN  NS  a.gtld-servers.net.
com.                    172800  IN  NS  b.gtld-servers.net.
...
;; Received 845 bytes from 192.5.6.30#53(a.gtld-servers.net) in 34 ms

github.com.             172800  IN  NS  dns1.p08.nsone.net.
github.com.             172800  IN  NS  dns2.p08.nsone.net.
...
;; Received 295 bytes from 205.251.197.49#53(dns4.p08.nsone.net) in 15 ms

api.github.com.         60      IN  A   140.82.114.6
;; Received 60 bytes from 198.51.44.8#53(dns1.p08.nsone.net) in 12 ms
```

What happened:
1. **Root servers** (`.`) — Asked "who handles `.com`?" Answer: the `.com` TLD servers.
2. **TLD servers** (`com.`) — Asked "who handles `github.com`?" Answer: GitHub's authoritative nameservers at nsone.net.
3. **Authoritative servers** (`github.com.`) — Asked "what's the IP for `api.github.com`?" Answer: `140.82.114.6`.

This hierarchical resolution is the entire structure of the internet's naming system. Every domain name you've ever typed went through this exact process (though most of the time, caching means only step 3 happens).

### 2.3 DNS Record Types That Matter

```bash
# A record — IPv4 address
dig +short github.com A

# AAAA record — IPv6 address
dig +short github.com AAAA

# CNAME — alias (one hostname pointing to another)
dig +short www.github.com CNAME

# MX — mail servers
dig +short github.com MX

# TXT — arbitrary text (SPF records, domain verification, etc.)
dig +short github.com TXT

# NS — nameservers (who is authoritative for this domain?)
dig +short github.com NS
```

**Try It Now:** Run each of those commands. Notice how `www.github.com` is a CNAME pointing to `github.com`, which then has an A record. CNAMEs create chains — the resolver follows them until it reaches an A or AAAA record.

### 2.4 TTL and Caching

The number between the hostname and the record type is the **TTL (Time to Live)** in seconds:

```bash
dig api.github.com
```

If the answer shows `60 IN A 140.82.114.6`, that means this answer is valid for 60 seconds. Run it again after 30 seconds — the TTL will show ~30 (counting down). After 60 seconds, the resolver makes a fresh query.

**Practical implications:**
- **Low TTL (60s):** Changes propagate fast. Good for services that need quick failover. Bad if your DNS server goes down — clients re-query every 60 seconds.
- **High TTL (3600s):** Fewer DNS queries, more resilient to DNS server outages. But changes take up to an hour to propagate.
- **"DNS takes 24-48 hours to propagate"** is largely a myth. It takes however long the old TTL was. If the old TTL was 3600s, it takes at most 3600s.

### 2.5 When DNS Goes Wrong

Flush your local DNS cache and observe the difference:

```bash
# macOS
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Linux (systemd)
sudo systemd-resolve --flush-caches

# Then time a DNS lookup
time dig +short api.github.com
```

The first query after flushing takes longer because nothing is cached. Subsequent queries are fast.

**Common DNS problems you'll encounter in production:**
- **Stale cache:** You changed a DNS record but clients are still hitting the old IP. Wait for TTL to expire.
- **NXDOMAIN caching:** You tried to resolve a domain before its record existed. The "does not exist" answer is cached (negative caching). Flush and retry.
- **DNS server unreachable:** If your configured resolver is down, all name resolution fails. This is why systems configure multiple resolvers.

---

## Part 3: The TicketPulse Request Lifecycle (15 minutes)

### 3.1 What Happens When a User Loads the Events Page

Let's trace the full lifecycle of a request to TicketPulse. In production, this would go through the public internet. Locally, we skip DNS and network latency, but the application-level flow is the same.

```bash
# Full verbose request to TicketPulse
curl -v http://localhost:3000/api/events 2>&1
```

Read the output:

```
*   Trying 127.0.0.1:3000...
* Connected to localhost (127.0.0.1) port 3000
> GET /api/events HTTP/1.1
> Host: localhost:3000
> User-Agent: curl/8.4.0
> Accept: */*
>
< HTTP/1.1 200 OK
< X-Powered-By: Express
< Content-Type: application/json; charset=utf-8
< Content-Length: 1234
< ETag: W/"4d2-abc123"
< Date: Mon, 24 Mar 2026 10:30:00 GMT
< Connection: keep-alive
< Keep-Alive: timeout=5
<
{"events":[...]}
```

Now let's map this to the application code:

```
1. curl sends GET /api/events HTTP/1.1
   → Express receives the request

2. requestLogger middleware runs
   → Logs: [INFO] GET /api/events (start)

3. Express matches the route: /api/events → events router → GET /
   → The route handler in src/routes/events.ts runs

4. Route handler calls cache-service.get("events:list")
   → Redis is checked for cached data
   → If HIT: skip to step 7
   → If MISS: continue to step 5

5. Route handler calls event-service.getAll()
   → event-service queries Postgres:
     SELECT e.*, v.name as venue_name, v.city, v.capacity
     FROM events e
     JOIN venues v ON e.venue_id = v.id
     ORDER BY e.date ASC

6. Route handler calls cache-service.set("events:list", data, TTL=60)
   → Result is stored in Redis with 60-second TTL

7. Route handler sends response:
   res.json({ events: data, total: data.length, page: 1, per_page: 20 })

8. Express adds headers:
   Content-Type: application/json
   ETag: W/"4d2-abc123" (weak ETag based on content hash)
   Content-Length: 1234

9. requestLogger middleware logs completion:
   [INFO] GET /api/events 200 — 23ms
```

### 3.2 Observe the Cache in Action

```bash
# First request — cache miss (hits the database)
curl -w "Time: %{time_total}s\n" -o /dev/null -s http://localhost:3000/api/events

# Second request — cache hit (returns from Redis)
curl -w "Time: %{time_total}s\n" -o /dev/null -s http://localhost:3000/api/events
```

The second request should be noticeably faster. The difference is the database query time — Redis returns cached data in sub-millisecond time.

**Try It Now:** Watch the Docker logs while you make requests:

```bash
# In one terminal
docker compose logs -f app

# In another terminal
curl -s http://localhost:3000/api/events > /dev/null
# Wait 2 seconds
curl -s http://localhost:3000/api/events > /dev/null
```

The logs should show the first request hitting the database and the second returning from cache. If the app logs cache hits/misses, you'll see it explicitly.

### 3.3 The ETag Dance

Notice the `ETag` header in the response. ETags enable conditional requests — the client can say "give me this resource, but only if it's changed since I last got it."

```bash
# Get the ETag from the first request
ETAG=$(curl -s -I http://localhost:3000/api/events | grep -i etag | tr -d '\r')
echo "$ETAG"

# Make a conditional request
curl -v -H "If-None-Match: $(echo $ETAG | cut -d' ' -f2)" \
  http://localhost:3000/api/events 2>&1 | head -20
```

If the data hasn't changed, you should get a `304 Not Modified` with no body — the server tells you "your cached version is still good, no need to download again." This saves bandwidth and processing time.

---

## Part 4: HTTP Status Codes — The Language of APIs (10 minutes)

### 4.1 The Status Codes That Matter

You don't need to memorize all 60+ HTTP status codes. You need to know these:

**2xx — Success:**

```bash
# 200 OK — The standard success response
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/events
# Expected: 200

# 201 Created — Resource was created
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "customer_email": "test@example.com", "quantity": 1}'
# Expected: 201

# 204 No Content — Success, but nothing to return (common for DELETE)
```

**4xx — Client Error (YOUR fault):**

```bash
# 400 Bad Request — Malformed request
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"bad": "data"}'
# Expected: 400

# 404 Not Found — Resource doesn't exist
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/events/99999
# Expected: 404

# 401 Unauthorized — No authentication provided
# 403 Forbidden — Authenticated but not authorized
# 429 Too Many Requests — Rate limited
```

**5xx — Server Error (SERVER's fault):**

```
500 Internal Server Error — Unhandled exception
502 Bad Gateway — Reverse proxy got a bad response from upstream
503 Service Unavailable — Server overloaded or in maintenance
504 Gateway Timeout — Reverse proxy timed out waiting for upstream
```

### 4.2 The Debugging Heuristic

When you see a 5xx error in production:
- **502** usually means the upstream process is **dead or crashed**. The reverse proxy (nginx, ALB, etc.) tried to connect and either couldn't or got garbage back.
- **504** usually means the upstream process is **alive but too slow**. The reverse proxy timed out waiting for a response.
- **500** means the application threw an unhandled exception. Check the application logs.
- **503** means the server is explicitly saying "I can't handle this right now." Often during deployments or when the health check is failing.

Both 502 and 504 mean the problem is **upstream** of whatever returned the error. If your load balancer returns a 502, the problem is your application server, not the load balancer.

**Try It Now:** Create different error responses from TicketPulse and observe the status codes:

```bash
# Missing required field (400)
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1}'

# Non-existent resource (404)
curl -s -w "\nHTTP %{http_code}\n" http://localhost:3000/api/events/0

# Invalid JSON (400)
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:3000/api/tickets \
  -H "Content-Type: application/json" \
  -d 'this is not json'

# Non-existent route (404)
curl -s -w "\nHTTP %{http_code}\n" http://localhost:3000/api/nonexistent
```

---

## Part 5: Diagnosing Slowness (10 minutes)

### 5.1 The Scenario

A user reports: "The site is slow." This is the most common complaint in all of web engineering. Without the knowledge from this module, you'd shrug and say "works for me." With it, you can systematically identify where the time is being spent.

**Pause & Reflect:** A user reports the site is slow. The server logs show all requests completing in less than 50ms. Where else could the slowness be?

Think about it before reading on.

The answer: slowness can live in **any** of the seven steps from Part 1:

1. **DNS** — Their DNS resolver is slow, or caching has expired. Time wasted before any request starts.
2. **TCP** — High network latency between the user and the server (distance, congestion, packet loss).
3. **TLS** — Slow TLS handshake (server CPU overloaded, certificate chain too long, TLS 1.2 instead of 1.3).
4. **Server processing** — But you said logs show <50ms, so probably not this.
5. **Response transfer** — Large response body on a slow connection.
6. **Client-side rendering** — The browser is slow to parse, execute JavaScript, and render the page.
7. **CDN miss** — Static assets are being fetched from origin instead of a nearby edge cache.

### 5.2 The Diagnostic Toolkit

**Measure from the user's perspective** — not from the server:

```bash
# Full timing breakdown from a remote location
curl -w "\n\
   DNS Lookup:  %{time_namelookup}s\n\
   TCP Connect: %{time_connect}s\n\
   TLS Done:    %{time_appconnect}s\n\
   TTFB:        %{time_starttransfer}s\n\
   Total:       %{time_total}s\n\
   Download:    %{size_download} bytes\n" \
   -o /dev/null -s https://your-production-url.com/api/events
```

**Read the results:**

| If this is slow... | The problem is... | Fix |
|---|---|---|
| DNS Lookup > 100ms | DNS resolution | Use a faster resolver (1.1.1.1, 8.8.8.8), check TTL |
| TCP Connect - DNS > 100ms | Network latency | Server too far from user, need CDN/edge |
| TLS - TCP > 100ms | TLS handshake | Enable TLS 1.3, use ECDSA certs, check OCSP stapling |
| TTFB - TLS > 200ms | Server processing | Check application logs, database queries, cache hit rate |
| Total - TTFB > 200ms | Response download | Compress responses (gzip/br), reduce payload size |

### 5.3 Practice Diagnosis

**Try It Now:** Pick three different public APIs and profile them:

```bash
for url in https://api.github.com https://jsonplaceholder.typicode.com/posts https://httpbin.org/get; do
  echo "=== $url ==="
  curl -w "DNS: %{time_namelookup}s | TCP: %{time_connect}s | TLS: %{time_appconnect}s | TTFB: %{time_starttransfer}s | Total: %{time_total}s\n" \
    -o /dev/null -s "$url"
done
```

Compare the results. Which is fastest? Where does each one spend its time? Is the bottleneck DNS, network, TLS, or server processing? Can you explain the differences?

### 5.4 HTTP/1.1 vs HTTP/2

```bash
# Force HTTP/1.1
curl -w "HTTP Version: %{http_version} | Total: %{time_total}s\n" \
  --http1.1 -o /dev/null -s https://api.github.com

# Allow HTTP/2
curl -w "HTTP Version: %{http_version} | Total: %{time_total}s\n" \
  --http2 -o /dev/null -s https://api.github.com
```

For a single request, the difference is minimal. HTTP/2's advantage shows up when making many concurrent requests — it multiplexes them over a single connection instead of needing 6 parallel TCP connections. This matters enormously for web pages that load dozens of assets.

**Insight:** HTTP/2 solves head-of-line blocking at the HTTP layer by using streams within a single TCP connection. But TCP itself still delivers bytes in order — if one packet is lost, all streams stall until it's retransmitted. HTTP/3 (built on QUIC over UDP) eliminates even this by giving each stream independent delivery. A lost packet in one stream doesn't affect the others.

---

## Module Summary

- **Every HTTPS request follows 7 steps:** DNS resolution, TCP handshake, TLS negotiation, HTTP request, server processing, HTTP response, connection handling
- **`curl -v`** shows you every protocol layer in a single command — learn to read its output fluently
- **`curl -w`** with timing variables measures exactly where time is spent: DNS, TCP, TLS, TTFB, total
- **DNS resolution** is hierarchical: root servers, TLD servers, authoritative servers — and caching at every level
- **`dig +trace`** shows you the full resolution chain step by step
- **Connection pooling** eliminates DNS + TCP + TLS overhead on subsequent requests — this is why it's not optional in production
- **HTTP status codes** are a language: 4xx = client's fault, 5xx = server's fault, 502 = upstream dead, 504 = upstream slow
- **Diagnosing slowness** requires measuring from the client's perspective, not the server's — use the timing breakdown to identify which layer is the bottleneck

## What's Next

You now understand how requests flow through the network and into your application. In the next section, we start building real features for TicketPulse — starting with the data layer. You'll learn SQL beyond SELECT *, understand how indexes work (and when they hurt), and build the database schema that will power TicketPulse through the rest of the course. The network knowledge from this module will come back every time you debug a production issue.

## Key Terms

| Term | Definition |
|------|-----------|
| **TCP** | Transmission Control Protocol; a connection-oriented protocol that guarantees reliable, ordered delivery of data. |
| **TLS** | Transport Layer Security; a cryptographic protocol that provides encrypted communication over a network. |
| **HTTP** | Hypertext Transfer Protocol; the application-layer protocol used for transferring web resources between clients and servers. |
| **DNS** | Domain Name System; the distributed system that translates human-readable domain names into IP addresses. |
| **Latency** | The time delay between sending a request and receiving the first byte of the response. |
| **TTFB** | Time to First Byte; the duration from the client's request to when the first byte of the server's response arrives. |
| **Round trip** | The time it takes for a network packet to travel from source to destination and back. |

## Further Reading

- [How DNS Works (comic)](https://howdns.works/) — a beautifully illustrated walkthrough of DNS resolution
- [High Performance Browser Networking](https://hpbn.co/) by Ilya Grigorik — free online book covering TCP, TLS, HTTP/2, and performance optimization in depth
- [curl documentation: `-w` format variables](https://curl.se/docs/manpage.html) — the full list of timing and metadata variables available in `curl -w`

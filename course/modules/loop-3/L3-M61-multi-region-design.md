# L3-M61: Multi-Region Design

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M48 (Chaos Engineering), L2-M54 (Zero-Downtime Migrations), L2-M44 (Terraform & IaC)
>
> **Source:** Chapters 1, 19, 31, 22, 23 of the 100x Engineer Guide

---

## The Goal

TicketPulse is no longer a local product. Events are happening in New York, London, and Tokyo. Users are buying tickets from six continents. Your single-region deployment in US-East means a user in Sydney experiences 200ms+ of network latency on every API call before your server even starts processing. That is unacceptable for a ticket purchase flow where milliseconds matter during a flash sale.

You are going to design the multi-region architecture that takes TicketPulse global. This is not a step-by-step tutorial. You are the architect. The module provides the constraints, the trade-offs, and the reference designs. You provide the decisions.

**By the end of this module, you will have a multi-region architecture document for TicketPulse that you could present to a staff engineer for review.**

---

## 0. Why Multi-Region? (5 minutes)

### The Physics Problem

Data travels through fiber optic cables at roughly two-thirds the speed of light. Here are the real-world round-trip times:

| Route | Round-Trip Latency |
|---|---|
| US-East to US-West | ~40 ms |
| US-East to EU-West (Ireland) | ~80 ms |
| US-East to AP-Northeast (Tokyo) | ~160 ms |
| EU-West to AP-Northeast | ~220 ms |
| Same datacenter | ~0.5 ms |

These are network-level numbers. A single API call involves DNS resolution, TLS handshake, request transfer, server processing, and response transfer. A ticket purchase saga with four service calls could add 640ms+ of pure network overhead for a user in Tokyo hitting US-East.

### The Three Reasons to Go Multi-Region

1. **Latency:** Users in Tokyo should not wait for a round trip to Virginia to load an event page.
2. **Availability:** If US-East goes down (and it has — the 2017 S3 outage took out half the internet), TicketPulse must keep selling tickets.
3. **Compliance:** GDPR requires that EU user data can be stored and processed within the EU. Some countries have data residency laws.

### 🤔 Before You Read On

Think about TicketPulse's data. Which data MUST be close to the user? Which data MUST be close to the venue? Which data can live anywhere?

Write down your initial thoughts. You will refine them as you work through this module.

---

## 1. Choosing Your Regions (10 minutes)

### The Principle: Follow the Users AND the Venues

TicketPulse has two gravitational centers for data:

1. **Users** — they want low latency when browsing events, managing their profiles, and completing purchases.
2. **Venues** — ticket inventory is a physical-world resource. A concert in Madison Square Garden has seats in New York. That inventory has a natural home.

### 📐 Design Exercise: Region Selection

Choose three regions for TicketPulse's initial global deployment. For each region, justify:

- Which users does this region serve?
- Which venues (and their ticket inventory) live here?
- What is the latency improvement for the primary user population?

<details>
<summary>💡 Hint 1: Direction</summary>
Think about where the biggest concentration of events AND users overlap. Start with the three broadest geographic clusters.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Map major concert cities to cloud provider regions. The Americas, Europe, and Asia-Pacific are the standard three -- but which specific region within each matters for latency.
</details>

**Reference Selection (compare with yours):**

| Region | Cloud Region | Primary Users | Primary Venues |
|---|---|---|---|
| Americas | us-east-1 / us-central1 | North & South America | NYC, LA, Chicago, Toronto, Sao Paulo |
| Europe | eu-west-1 / europe-west1 | EU, UK, Middle East, Africa | London, Paris, Berlin, Amsterdam |
| Asia-Pacific | ap-northeast-1 / asia-northeast1 | East Asia, Southeast Asia, Oceania | Tokyo, Seoul, Sydney, Singapore |

### What Data Lives Where?

This is the critical design decision. Not all data is created equal.

**Global Data (replicated to all regions):**
- User accounts and authentication
- Payment methods (tokenized)
- Platform configuration and feature flags

**Regional Data (lives in one region, the region of the venue):**
- Event details and metadata
- Ticket inventory and availability
- Reservations and seat maps
- Venue information

**User-Local Data (lives in the user's home region):**
- Order history
- Preferences and notification settings
- Session data

### 🤔 Reflect

A user in London buys a ticket for a concert in NYC. Which region handles the purchase? Where is the source of truth for that ticket's availability?

Think carefully. The user is in EU-West. The ticket inventory is in US-East. The purchase involves both. There is no free answer here.

**The answer:** The ticket inventory is the scarce resource. The purchase must be processed in US-East where the inventory lives. The user's request is routed from EU-West to US-East for the actual reservation and payment. The order record is then replicated to EU-West for the user's order history.

This means: cross-region purchases are inherently slower. A London user buying a NYC ticket pays ~80ms per service call in additional latency. This is physics. You cannot cheat it. You can minimize the number of cross-region hops, but you cannot eliminate them.

---

## 2. Active-Active vs Active-Passive (15 minutes)

### 📐 Design Exercise: Draw Both

Before reading the comparison, draw both architectures for TicketPulse. Label the data flows, the replication directions, and where writes happen.

<details>
<summary>💡 Hint 1: Direction</summary>
The key difference is where writes are accepted. In one model, writes go to one place. In the other, writes happen locally in each region.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
For active-passive, draw a single primary with DNS failover. For active-active, draw each region with its own database and cross-region replication arrows. Label which data each region "owns."
</details>

### Active-Passive

```
                    ┌─────────────────────────────┐
                    │         DNS (Route 53)       │
                    │   Primary: US-East           │
                    │   Failover: EU-West          │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │          US-EAST              │
                    │     (Active — all traffic)    │
                    │                               │
                    │  ┌─────────┐  ┌────────────┐  │
                    │  │ Compute │  │ PostgreSQL  │  │
                    │  │ (ECS)   │  │ (Primary)   │──│──── async replication
                    │  └─────────┘  └────────────┘  │
                    └───────────────────────────────┘
                                                        │
                    ┌───────────────────────────────┐   │
                    │          EU-WEST              │   │
                    │    (Passive — standby)        │   │
                    │                               │   │
                    │  ┌─────────┐  ┌────────────┐  │   │
                    │  │ Compute │  │ PostgreSQL  │◄─│───┘
                    │  │ (cold)  │  │ (Replica)   │  │
                    │  └─────────┘  └────────────┘  │
                    └───────────────────────────────┘
```

**How it works:**
- All traffic goes to US-East.
- EU-West has a database replica receiving async replication.
- EU-West compute is either off or running minimal health checks.
- On failure: DNS failover switches traffic to EU-West. The replica is promoted to primary.
- Failover time: 1-5 minutes (DNS TTL + replica promotion + compute warm-up).

**Pros:** Simple. No write conflicts. No split-brain risk. Cheaper (passive region uses fewer resources).

**Cons:** EU and AP users always have high latency. Failover is not instant. The passive region may have stale data at failover time (replication lag).

### Active-Active

```
                    ┌─────────────────────────────────┐
                    │          DNS (Route 53)          │
                    │   Latency-based routing          │
                    │   US users → US-East             │
                    │   EU users → EU-West             │
                    │   AP users → AP-Northeast        │
                    └──────┬──────────┬──────────┬─────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────────┐  ┌──▼──────────────┐
              │    US-EAST    │  │   EU-WEST   │  │  AP-NORTHEAST   │
              │   (Active)    │  │  (Active)   │  │   (Active)      │
              │               │  │             │  │                 │
              │ ┌───────────┐ │  │ ┌─────────┐ │  │ ┌─────────────┐ │
              │ │ Compute   │ │  │ │ Compute │ │  │ │  Compute    │ │
              │ └───────────┘ │  │ └─────────┘ │  │ └─────────────┘ │
              │ ┌───────────┐ │  │ ┌─────────┐ │  │ ┌─────────────┐ │
              │ │ DB Primary│◄├──┼─┤DB Primary│◄├──┼─┤ DB Primary  │ │
              │ └───────────┘ │  │ └─────────┘ │  │ └─────────────┘ │
              └───────────────┘  └─────────────┘  └─────────────────┘
                      ▲                ▲                   ▲
                      └────── Cross-region replication ────┘
```

**How it works:**
- DNS routes users to the nearest region based on latency.
- Each region has its own compute and database.
- Regional data (events, tickets) is authoritative in one region. Other regions have read replicas.
- Global data (users, auth) is replicated across all regions.
- Cross-region writes are routed to the authoritative region.

**Pros:** Low latency for all users. No single point of failure. Each region serves its local events at full speed.

**Cons:** Complex. Write conflicts for global data. Cross-region purchase flow. More expensive (three full deployments). Split-brain risk during network partitions.

### 📐 Design Decision: Which Is Better for TicketPulse?

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Consider these facts:
- TicketPulse has clear data locality (events belong to venues, venues are in regions).
- Ticket purchases require strong consistency (no overselling).
- User profiles can tolerate eventual consistency (a name change can take seconds to propagate).
- Revenue depends on being available during flash sales.

**Recommended: Active-Active with Regional Data Ownership**

Each region owns the events and ticket inventory for its venues. Users are routed to the nearest region for reads. Purchases are routed to the region that owns the inventory. This gives you:
- Local-speed reads for event browsing (the most common operation).
- Strong consistency for ticket purchases within a region.
- Cross-region eventual consistency for global data.
- No single region failure takes down the whole platform.

---

## 3. DNS-Based Routing (10 minutes)

### How Users Reach the Right Region

DNS is the first hop in the multi-region routing chain. Cloud providers offer intelligent DNS routing:

**AWS Route 53:**
```
Record: api.ticketpulse.com
Type: A (Alias)
Routing Policy: Latency-based

us-east-1:     ALB in US-East       (weight: auto)
eu-west-1:     ALB in EU-West       (weight: auto)
ap-northeast-1: ALB in AP-Northeast (weight: auto)

Health checks: /health on each ALB
Failover: If a region fails health check, traffic reroutes to next-closest region
```

**GCP Cloud DNS with Global Load Balancer:**
```
GCP takes a different approach: the Global HTTP(S) Load Balancer has
a single anycast IP address. Google's network routes traffic to the
nearest healthy backend automatically. No DNS-level routing needed.

Backend services:
  - Cloud Run in us-central1
  - Cloud Run in europe-west1
  - Cloud Run in asia-northeast1

Routing rules:
  - /api/events/* → route to the region owning the event
  - /api/users/* → route to the user's home region
  - Default → route to nearest region
```

### The DNS TTL Trade-off

| TTL | Failover Speed | DNS Query Load |
|---|---|---|
| 60 seconds | Fast failover | High (clients re-resolve often) |
| 300 seconds | 5 min worst-case failover | Moderate |
| 3600 seconds | Slow failover | Low |

**Recommendation:** 60-second TTL for api.ticketpulse.com. The slight increase in DNS queries is worth the fast failover.

### 📐 Design Exercise: Request Routing

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Trace the complete request path for these scenarios:

1. **User in Paris browses events in Paris.** Which region handles this? How many network hops?
2. **User in Paris browses events in Tokyo.** Where does the request go? Where is the data?
3. **User in Paris buys a ticket for an event in NYC.** Which region processes the purchase? What is the expected additional latency?

**Reference Answers:**

1. Paris → EU-West (nearest region). Event data for Paris venues lives in EU-West. Zero cross-region hops. Fast.
2. Paris → EU-West (nearest region). EU-West does NOT have Tokyo event data as primary. Two options:
   - EU-West has a read replica of Tokyo events → serve from local replica (eventual consistency, fast).
   - EU-West proxies the request to AP-Northeast → slower but strongly consistent.
   For browsing, the read replica approach is correct. Stale event descriptions for a few seconds is fine.
3. Paris → EU-West → US-East (where NYC inventory lives). The purchase saga runs in US-East. ~80ms additional latency per hop. The order confirmation is replicated back to EU-West for the user's order history.

---

## 4. Consistency Across Regions (15 minutes)

### The Fundamental Trade-off

You cannot have both strong consistency and low latency across regions. This is PACELC in action:

> If there is a **P**artition, choose **A**vailability or **C**onsistency. **E**lse (normal operation), choose **L**atency or **C**onsistency.

For TicketPulse, the consistency strategy is different for each data type:

| Data Type | Consistency Model | Why |
|---|---|---|
| Ticket inventory | Strong (within owning region) | Cannot oversell. Double-selling a seat = angry customers + refunds. |
| User profiles | Eventual (cross-region) | A name change taking 2 seconds to propagate is invisible. |
| Event metadata | Eventual (cross-region) | Event description updates are rare and non-critical. |
| Order history | Eventual (cross-region) | Order appears in user's region within seconds. Acceptable. |
| Payment state | Strong (within processing region) | Money must be consistent. Process payment where inventory lives. |
| Session/auth | Eventual (cross-region) with read-your-writes | User must see their own session. Other regions can lag. |

### Region-Local Strong Consistency

Within a single region, you use normal database transactions. PostgreSQL with synchronous replicas across availability zones gives you:
- Strong consistency for all reads and writes.
- Automatic failover within the region (AZ failure).
- Sub-millisecond replication lag (same-region AZs are <1ms apart).

### Cross-Region Eventual Consistency

Between regions, you use asynchronous replication:
- PostgreSQL logical replication or change data capture (CDC) with Kafka.
- Replication lag: typically 100ms-2s depending on distance and load.
- Conflict resolution: last-write-wins for user profiles, no conflicts for append-only data (orders, ledger entries).

### 🤔 Prediction Prompt

Before reading about Spanner below, ask yourself: if you needed globally consistent reads across three continents, what would you need from the clock system? What trade-off would you pay on every write?

> **The bigger picture:** The consistency model you choose per data type is the single most consequential architecture decision in a multi-region system. Get it wrong and you either oversell tickets or add 200ms to every request for no reason.

### How Google Spanner Solved This

Google Spanner achieved externally consistent (linearizable) reads and writes across globally distributed data. How?

**TrueTime:** GPS receivers and atomic clocks in every data center provide a global time reference with bounded uncertainty (typically <7ms). Spanner uses this to assign globally meaningful timestamps to transactions. When a write completes, Spanner waits out the clock uncertainty before confirming. This means any subsequent read, anywhere in the world, is guaranteed to see the write.

**The cost:** Every write has a minimum latency equal to the TrueTime uncertainty bound (~7ms). Cross-region writes additionally pay the round-trip time for Paxos consensus across regions.

**For TicketPulse:** Spanner (or CockroachDB, which approximates this approach) could be used for the global user table. But for ticket inventory where strong consistency only matters within a region, standard PostgreSQL is simpler and faster. Do not reach for globally consistent databases unless you genuinely need global strong consistency.

---

## 5. Data Replication Design (10 minutes)

### 📐 Design Exercise: Replication Topology

<details>
<summary>💡 Hint 1: Direction</summary>
What constraints matter most here? Start from the requirements, not the implementation.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Revisit the architecture patterns from this module. The solution is a composition of techniques you already know.
</details>


Design the replication topology for TicketPulse's three regions. For each data type, specify:
- Where the primary (writable) copy lives.
- Which regions have read replicas.
- The replication method (sync within region, async across regions).

**Reference Design:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    GLOBAL USER DATABASE                          │
│                                                                 │
│  US-East (Primary)  ──async──►  EU-West (Replica)               │
│         │                          │                            │
│         └──────────async──────────►  AP-NE (Replica)            │
│                                                                 │
│  Writes: User's home region is primary for their profile.       │
│  Or: Single global primary (simpler but higher write latency    │
│       for non-US users).                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              REGIONAL EVENT & TICKET DATABASES                   │
│                                                                 │
│  US-East: Primary for Americas events                           │
│     └── sync replicas in us-east-1a, 1b, 1c (AZ-level HA)     │
│     └── async read replica → EU-West (for browsing)             │
│     └── async read replica → AP-NE (for browsing)               │
│                                                                 │
│  EU-West: Primary for European events                           │
│     └── sync replicas in eu-west-1a, 1b, 1c                    │
│     └── async read replica → US-East (for browsing)             │
│     └── async read replica → AP-NE (for browsing)               │
│                                                                 │
│  AP-NE: Primary for Asia-Pacific events                         │
│     └── sync replicas in ap-northeast-1a, 1b, 1c               │
│     └── async read replica → US-East (for browsing)             │
│     └── async read replica → EU-West (for browsing)             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ORDER/LEDGER DATABASE                         │
│                                                                 │
│  Orders are written in the region that processes the purchase.  │
│  Replicated async to the user's home region for their history.  │
│  Append-only: no conflicts possible.                            │
└─────────────────────────────────────────────────────────────────┘
```

### Conflict Resolution

For global data that can be written in multiple regions (user profiles, if you choose multi-primary), you need a conflict resolution strategy:

| Strategy | How It Works | Best For |
|---|---|---|
| Last-write-wins (LWW) | Compare timestamps, most recent write wins | User profiles, preferences |
| Application-level merge | Custom logic per field | Shopping carts, settings |
| CRDTs | Mathematically guaranteed convergence | Counters, sets, collaborative data |
| Single-primary per entity | Route writes to one region per user | Simplest. Recommended for TicketPulse. |

**Recommendation for TicketPulse:** Assign each user a "home region" based on their signup location. User profile writes always route to the home region. Other regions have read replicas. No conflicts possible.

---

## 6. The Speed of Light Problem (5 minutes)

### What You Cannot Optimize Away

No amount of engineering eliminates the speed of light. When a user in London buys a ticket for a NYC concert:

```
London → EU-West edge (5ms)
EU-West → US-East (80ms)
Reserve ticket in US-East DB (5ms)
Process payment in US-East (200ms — includes card network)
US-East → EU-West (80ms)
EU-West → London (5ms)
─────────────────────────
Total: ~375ms minimum for the purchase
```

Compare with a London user buying a ticket for a London concert:

```
London → EU-West edge (5ms)
Reserve ticket in EU-West DB (5ms)
Process payment in EU-West (200ms — card network is similar)
EU-West → London (5ms)
─────────────────────────
Total: ~215ms minimum for the purchase
```

The cross-region purchase is 160ms slower. This is irreducible. You can:
- **Minimize cross-region hops** by making the purchase a single remote call (not four separate cross-region calls).
- **Optimistically show progress** ("Reserving your ticket...") while the cross-region call completes.
- **Pre-warm data** by caching event details in the user's region so browsing is fast, even if the purchase hits another region.

But you cannot make light go faster.

---

## 7. Reflect (5 minutes)

### 🤔 Questions

1. **TicketPulse has a flash sale for a Taylor Swift concert in London. 500,000 users try to buy tickets simultaneously. Should users from other regions be throttled or given lower priority?** What are the trade-offs?

2. **A network partition isolates EU-West from US-East for 10 minutes. What happens to:**
   - A user in London browsing London events? (Should work — data is local.)
   - A user in London buying a London ticket? (Should work — inventory is local.)
   - A user in London buying a NYC ticket? (Fails — cannot reach US-East inventory.)
   - A user in NYC buying a NYC ticket? (Should work — data is local.)

3. **If you could only deploy to two regions instead of three, which two would you choose? Why?**

4. **What monitoring would you need to detect that cross-region replication has fallen behind?** What alerting threshold would you set?

---

## 8. Checkpoint

After this module, you should have:

- [ ] A multi-region architecture document for TicketPulse with three regions
- [ ] Data classification: global, regional, and user-local data with justifications
- [ ] Diagrams for both active-passive and active-active architectures
- [ ] A defended choice between the two (active-active with regional data ownership)
- [ ] DNS routing design with latency-based routing and health checks
- [ ] Consistency model per data type (strong vs eventual, with justification)
- [ ] Replication topology showing primary and replica locations
- [ ] Understanding of irreducible cross-region latency and mitigation strategies
- [ ] Answers to all reflect questions

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Follow the users and the venues** | Place compute near users for reads. Place data near the physical resource it represents. |
| **Active-active with regional ownership** | Each region owns its events and inventory. Cross-region reads use replicas. Cross-region writes route to the owning region. |
| **DNS-based routing** | Route 53 latency-based routing or GCP Global LB directs users to the nearest healthy region. |
| **Consistency per data type** | Strong consistency within a region for inventory. Eventual consistency across regions for profiles and browsing. |
| **The speed of light** | Cross-region latency is physics. Design to minimize hops, not eliminate them. |
| **Spanner and TrueTime** | Global strong consistency is possible but expensive. Use it only when the business requires it. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Active-active** | A deployment model where all regions serve live traffic simultaneously. |
| **Active-passive** | A deployment model where one region serves traffic and others are on standby for failover. |
| **Latency-based routing** | DNS routing that directs users to the region with the lowest measured network latency. |
| **Regional data ownership** | A pattern where each region is the authoritative source for a subset of the data. |
| **PACELC** | Extension of CAP: during Partition choose Availability/Consistency; Else choose Latency/Consistency. |
| **TrueTime** | Google's globally synchronized clock system using GPS and atomic clocks, enabling global strong consistency in Spanner. |
| **Replication lag** | The delay between a write on the primary and its appearance on a replica. |

---

---

## 9. Hands-On: Trace a Cross-Region Purchase End-to-End (20 min)

You cannot build multi-region infrastructure in a local lab in 20 minutes, but you can develop the muscle of tracing requests precisely — which is what you will do constantly when debugging cross-region issues in production.

### Step 1: Set Up a Local Multi-Region Simulation

Use Docker Compose with latency injection to simulate cross-region behavior:

```yaml
# docker-compose.multi-region-sim.yml
version: '3.9'
services:
  # Simulate US-East region (your "primary" local region)
  us-east-api:
    image: ticketpulse/api:latest
    environment:
      REGION: us-east
      DB_URL: postgresql://ticketpulse:password@us-east-db:5432/ticketpulse
    ports:
      - "3001:3000"

  # Simulate EU-West region
  eu-west-api:
    image: ticketpulse/api:latest
    environment:
      REGION: eu-west
      DB_URL: postgresql://ticketpulse:password@eu-west-db:5432/ticketpulse
    ports:
      - "3002:3000"

  # Latency proxy: adds 80ms to all connections through it (simulates trans-Atlantic)
  eu-west-proxy:
    image: alpine/socat
    command: "TCP-LISTEN:3080,fork,reuseaddr TCP:us-east-api:3000"
    ports:
      - "3080:3080"
    # Then use tc to add delay:
    # docker exec eu-west-proxy tc qdisc add dev eth0 root netem delay 80ms

  us-east-db:
    image: postgres:15
    environment:
      POSTGRES_DB: ticketpulse
      POSTGRES_USER: ticketpulse
      POSTGRES_PASSWORD: password

  eu-west-db:
    image: postgres:15
    environment:
      POSTGRES_DB: ticketpulse
      POSTGRES_USER: ticketpulse
      POSTGRES_PASSWORD: password
```

```bash
docker compose -f docker-compose.multi-region-sim.yml up -d

# Add simulated latency (80ms = EU-West to US-East round trip)
docker compose -f docker-compose.multi-region-sim.yml exec eu-west-proxy \
  sh -c "apk add iproute2 && tc qdisc add dev eth0 root netem delay 80ms"
```

### Step 2: Trace the Same Request Through Both Regions

```bash
# Request to US-East (no cross-region hop)
time curl -s http://localhost:3001/api/events/evt_nyc_1 | jq '.venue.city'
# Expected: "New York" in ~50ms

# Same request, but routed via EU-West → needs to cross-region to fetch US inventory
time curl -s http://localhost:3002/api/events/evt_nyc_1 | jq '.venue.city'
# Expected: "New York" in ~130ms (50ms processing + 80ms cross-region)
```

### Step 3: Simulate a Purchase Flow Across Regions

Write a script that traces each step of a cross-region purchase:

```bash
#!/bin/bash
# scripts/trace-cross-region-purchase.sh

echo "=== Cross-Region Purchase Trace ==="
echo "User: Paris (EU-West), Event: NYC Concert (US-East)"
echo ""

# Step 1: Browse event (from EU-West — should hit local replica if available)
echo "Step 1: Browse event details..."
START=$(date +%s%3N)
curl -s http://localhost:3002/api/events/evt_nyc_1 > /dev/null
END=$(date +%s%3N)
echo "  Browse: $((END-START))ms (served from EU-West replica)"

# Step 2: Check availability (must go to US-East — it owns the inventory)
echo "Step 2: Check ticket availability..."
START=$(date +%s%3N)
curl -s http://localhost:3080/api/events/evt_nyc_1/availability > /dev/null
# 3080 is our cross-region proxy with 80ms added latency
END=$(date +%s%3N)
echo "  Availability check: $((END-START))ms (US-East authoritative — cross-region!)"

# Step 3: Reserve ticket (US-East owns inventory, must happen there)
echo "Step 3: Reserve ticket..."
START=$(date +%s%3N)
RESERVATION=$(curl -s -X POST http://localhost:3080/api/orders/reserve \
  -H 'Content-Type: application/json' \
  -d '{"event_id": "evt_nyc_1", "user_id": "user_paris_1", "quantity": 2}')
END=$(date +%s%3N)
RESERVATION_ID=$(echo $RESERVATION | jq -r '.reservation_id')
echo "  Reserve: $((END-START))ms | Reservation: $RESERVATION_ID"

# Step 4: Process payment (payment gateway is in US-East)
echo "Step 4: Process payment..."
START=$(date +%s%3N)
curl -s -X POST http://localhost:3080/api/orders/pay \
  -H 'Content-Type: application/json' \
  -d "{\"reservation_id\": \"$RESERVATION_ID\", \"payment_method\": \"tok_visa\"}" > /dev/null
END=$(date +%s%3N)
echo "  Payment: $((END-START))ms (Stripe API adds ~200ms)"

# Step 5: Order confirmation replicated back to EU-West
echo "Step 5: Verify order in EU-West..."
sleep 1  # Allow async replication to propagate
START=$(date +%s%3N)
curl -s "http://localhost:3002/api/users/user_paris_1/orders" | jq '.[0].status' 
END=$(date +%s%3N)
echo "  Confirm: $((END-START))ms (replicated to EU-West)"

echo ""
echo "=== Summary ==="
echo "Steps involving US-East (cross-region for Paris user): 3 of 5"
echo "Irreducible latency added: ~240ms (3 × 80ms round trips)"
```

```bash
chmod +x scripts/trace-cross-region-purchase.sh
./scripts/trace-cross-region-purchase.sh
```

### Step 4: Calculate and Document Your Latency Budget

Fill in this table based on your trace results:

| Purchase Step | Region Handling | Latency (measured) | Cross-Region? |
|---|---|---|---|
| Browse event | EU-West replica | __ms | No |
| Check availability | US-East (authoritative) | __ms | Yes |
| Reserve ticket | US-East (authoritative) | __ms | Yes |
| Process payment | US-East + Stripe | __ms | Yes |
| View confirmation | EU-West (replicated) | __ms | No |
| **Total** | | __ms | |

This is your **latency budget reality check**. Compare with your theoretical estimate from Section 6.

### Step 5: Optimize — Reduce Cross-Region Hops

The availability check and reservation can be combined into one cross-region call (instead of two):

```javascript
// services/purchase.service.js (optimized)

// BEFORE: 2 separate cross-region calls
const available = await crossRegionClient.get(`/events/${eventId}/availability`);
if (available.tickets > 0) {
  const reservation = await crossRegionClient.post('/orders/reserve', { eventId, userId, quantity });
}

// AFTER: 1 cross-region call — reserve-or-fail atomically
const reservation = await crossRegionClient.post('/orders/reserve-or-fail', {
  eventId,
  userId,
  quantity,
  // If tickets not available, returns 409 Conflict (no additional round-trip)
});
```

**Result**: 3 cross-region hops → 2 cross-region hops. Saves ~80ms for every purchase from a non-US user.

---

## 10. Deep Reflection: Edge Cases You Must Plan For (10 min)

These scenarios will happen in production. Think through each one before they do.

### Scenario 1: Replication Lag Spike

Normally your cross-region replication lag is 200ms. During a traffic spike, it climbs to 45 seconds. A user in London sees an event description from 45 seconds ago — but that is fine, because event descriptions rarely change.

However, your read replica availability count is also 45 seconds stale. A Paris user sees "5 tickets available" but when they try to purchase, the tickets are gone (US-East sold them 45 seconds ago).

**Design question**: How does your system communicate that the availability count might be stale? What does the purchase confirmation flow look like when availability data is eventually consistent?

> **Guided answer**: Use "optimistic UX" — show the availability count but add subtle indicators when you know it's from a replica (e.g., "Availability updated 2 minutes ago"). When the user clicks "Buy," always go to the authoritative region. If tickets are gone, show a clear "Sorry, tickets just sold out" message with alternatives. The key: never let a user reach the payment screen for inventory that doesn't exist.

### Scenario 2: Split-Brain During Network Partition

EU-West and US-East lose connectivity for 8 minutes. A London user buys a ticket for a London event (EU-West handles it entirely — this works). A New York user buys the same ticket for that London event from US-East (which cannot reach EU-West's authoritative inventory).

**Design question**: What should US-East do with the NYC user's purchase request during the partition?

> **Guided answer**: Return a clear error: "Purchase temporarily unavailable for this event — please try again in a few minutes." This is the CP choice (consistency over availability) for ticket purchases. Overselling a concert is worse than a temporary 503. Implement circuit breakers that detect EU-West unavailability and fail-fast with a user-friendly message rather than hanging. 

### Scenario 3: Gradual Geographic Rollout

You are adding a 4th region (AP-Southeast — Singapore) to serve Southeast Asian users. How do you roll it out without risking consistency?

> **Guided answer**: Start AP-Southeast as read-only. Route all writes to the nearest existing region (AP-Northeast or US-East). Watch for replication lag, data correctness, and replica health for 2 weeks. Then, select a low-risk event category (e.g., small local venues in Singapore) and migrate those to AP-Southeast as the new authoritative source. Monitor purchases. Expand category by category. Never flip the entire region at once.

---

### 🤔 Reflection Prompt

Look back at your initial data classification from the start of this module. What changed? Where did you underestimate the complexity of cross-region writes, and where did you overestimate the need for strong consistency?

> **Ecosystem note:** See Ch 19 of the 100x Engineer Guide: "Distributed Systems Fundamentals" -- covers CAP, PACELC, consensus algorithms, and replication strategies with mathematical grounding.

---

## What's Next

Next up: **[L3-M62: Cloud Provider Deep Dive](L3-M62-cloud-provider-deep-dive.md)** -- you will take these multi-region designs and deploy them on real cloud infrastructure (AWS or GCP), hitting live endpoints and understanding the cost reality.

---

## Further Reading

- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 5 (Replication) and Chapter 9 (Consistency and Consensus)
- [AWS Multi-Region Architecture](https://docs.aws.amazon.com/whitepapers/latest/aws-multi-region-fundamentals/aws-multi-region-fundamentals.html) — AWS whitepaper on multi-region patterns
- Corbett et al., ["Spanner: Google's Globally-Distributed Database"](https://research.google/pubs/pub39966/) — the TrueTime paper
- Chapter 1 of the 100x Engineer Guide: Sections 1.2 (PACELC), 4.2 (Failover Strategies)

# Challenge: Design a Tiered Access Rush System

## The Scenario

TicketPulse is launching a major artist's world tour. 20K tickets across 4 tiers: (1) Fan Club members (2K tickets, access at 10:00 AM), (2) Presale code holders (5K tickets, 12:00 PM), (3) Credit card presale (5K tickets, 2:00 PM), (4) General public (8K tickets, 4:00 PM). Each tier has its own allocation. Unsold tickets from earlier tiers roll into the next.

## Your Task

Design the architecture for this tiered rush system. Deliver:
1. Data model changes (tables, constraints)
2. Queue architecture (how tiers interact with the virtual queue)
3. Rollover logic (unsold Tier 1 tickets available in Tier 2)
4. Anti-bot measures for the general public tier

## Success Criteria

- [ ] Each tier has its own allocation that cannot be exceeded
- [ ] Tier access windows are enforced (Fan Club can't buy during general public window)
- [ ] Unsold tickets roll forward correctly
- [ ] No overselling across any tier or in total
- [ ] System handles 100K concurrent users in the general public tier

## Hints

<details>
<summary>💡 Hint 1: Direction</summary>
Think of each tier as a separate "event" within the event — its own ticket pool, queue, and access window. A scheduler opens each tier at the designated time. Rollover is a batch operation that moves unsold tickets between pools.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Add a `ticket_tiers` table: tier_id, event_id, name, allocation, opens_at, closes_at. Each ticket gets a `tier_id`. The queue processor checks the user's tier eligibility before processing. Rollover: at closes_at, UPDATE remaining tickets SET tier_id = next_tier. The database constraint checks per-tier sold counts against per-tier allocations.
</details>

## Solution

<details>
<summary>View Solution</summary>

**Data model**: `ticket_tiers` table with allocation, open/close times. Tickets have tier_id FK. CHECK constraint: per-tier sold <= allocation.

**Queue**: One Redis sorted set per tier per event. Queue processor validates tier eligibility (fan club membership, presale code, card BIN) before purchase.

**Rollover**: Cron job at each tier's close time: `UPDATE tickets SET tier_id = $next WHERE tier_id = $current AND status = 'available'`. Update allocations accordingly.

**Anti-bot**: Rate limit per IP, browser fingerprint verification, CAPTCHA on general public tier, behavioral analysis (request timing patterns).

**Trade-off**: Complexity is significantly higher than single-tier. Each tier is essentially a separate rush event. The rollover logic must be atomic to prevent selling rolled-over tickets during the transition window.
</details>

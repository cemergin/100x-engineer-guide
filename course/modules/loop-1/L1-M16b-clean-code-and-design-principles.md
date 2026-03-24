# L1-M16b: Clean Code & Design Principles

> **Loop 1 (Foundation)** | Section 1C+: Software Engineering Principles | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M16a (SOLID Principles in Practice)
>
> **Source:** Chapter 32 of the 100x Engineer Guide

---

## The Goal

SOLID principles give you architectural guardrails. Clean code gives you readability. The difference between code that works and code that a teammate can understand in 30 seconds. This module is a code review exercise: you will read bad code, feel the friction, then fix it.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Create the messy file we are going to clean up:

```bash
cd ticketpulse
```

```typescript
// src/services/purchase-handler.ts
// This file is INTENTIONALLY messy. Do not fix it yet -- read it first.

import { Pool } from 'pg';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

interface EventRow {
  id: string;
  name: string;
  base_price_cents: number;
  capacity: number;
  tickets_sold: number;
  starts_at: string;
  venue_id: string;
}

// What does "processData" even mean?
export async function processData(
  d: any,
  flag: boolean,
  tmp: number,
  cb?: (x: any) => void
) {
  // Get stuff from DB
  const r = await pool.query('SELECT * FROM events WHERE id = $1', [d.eventId]);
  const e = r.rows[0] as EventRow;

  if (!e) {
    // Just return null, caller will figure it out... right?
    return null;
  }

  // Check stuff
  const n = e.tickets_sold;
  const c = e.capacity;
  if (n >= c) {
    return null; // Sold out, but no indication why
  }

  // Calculate price
  let p = e.base_price_cents;
  if (d.type === 'vip') {
    p = p * 2.5;
  } else if (d.type === 'early_bird') {
    if (flag) {
      p = p * 0.8;
      if (tmp > 0) {
        p = p - (p * (tmp / 100));
      }
    } else {
      p = p * 0.85;
    }
  } else if (d.type === 'student') {
    p = p * 0.6;
    if (flag && tmp > 0) {
      p = p - (p * (tmp / 100));
    }
  }

  p = Math.round(p * d.qty);

  // Do the purchase
  let orderId: string;
  try {
    const result = await pool.query(
      `INSERT INTO orders (event_id, user_id, ticket_type, quantity, total_in_cents, status)
       VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id`,
      [d.eventId, d.userId, d.type, d.qty, p]
    );
    orderId = result.rows[0].id;
  } catch (e) {
    // Swallow the error
    return null;
  }

  // Update tickets sold
  try {
    await pool.query(
      'UPDATE events SET tickets_sold = tickets_sold + $1 WHERE id = $2',
      [d.qty, d.eventId]
    );
  } catch (e) {
    // Swallow again -- tickets_sold might be wrong now but whatever
  }

  // Send confirmation
  try {
    const userResult = await pool.query('SELECT * FROM users WHERE id = $1', [d.userId]);
    const user = userResult.rows[0];
    if (user && user.email) {
      // Inline email template
      const html = `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h1 style="color: #333;">Order Confirmed!</h1>
          <p>Hi ${user.name || 'there'},</p>
          <p>Your order for <strong>${e.name}</strong> has been confirmed.</p>
          <table style="width: 100%; border-collapse: collapse;">
            <tr>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">Ticket Type</td>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">${d.type}</td>
            </tr>
            <tr>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">Quantity</td>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">${d.qty}</td>
            </tr>
            <tr>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">Total</td>
              <td style="padding: 8px; border-bottom: 1px solid #eee;">$${(p / 100).toFixed(2)}</td>
            </tr>
          </table>
          <p style="color: #666; font-size: 12px;">
            Event: ${e.name}<br>
            Date: ${new Date(e.starts_at).toLocaleDateString()}<br>
            Order ID: ${orderId}
          </p>
        </div>
      `;

      // Send email somehow
      const emailConfig = {
        host: process.env.SMTP_HOST || 'smtp.example.com',
        port: parseInt(process.env.SMTP_PORT || '587'),
      };
      const nodemailer = require('nodemailer');
      const transporter = nodemailer.createTransport(emailConfig);
      await transporter.sendMail({
        from: 'tickets@ticketpulse.com',
        to: user.email,
        subject: `Order Confirmed: ${e.name}`,
        html,
      });
    }
  } catch (e) {
    // Email failed? Oh well.
  }

  // Analytics
  try {
    console.log(JSON.stringify({
      event: 'purchase',
      data: { orderId, eventId: d.eventId, type: d.type, qty: d.qty, total: p },
      ts: Date.now(),
    }));
  } catch (e) {
    // Can't even log? Whatever.
  }

  // Callback if provided
  if (cb) {
    try {
      cb({ orderId, total: p });
    } catch (e) {
      // Callback failed, ignore
    }
  }

  return { orderId, total: p, eventName: e.name };
}

// ---- PREMATURE ABSTRACTION: PluginManager for exactly one plugin ----

interface Plugin {
  name: string;
  version: string;
  init(): Promise<void>;
  execute(context: any): Promise<any>;
  shutdown(): Promise<void>;
}

interface PluginConfig {
  enabled: boolean;
  priority: number;
  options: Record<string, unknown>;
}

export class PluginManager {
  private plugins = new Map<string, { plugin: Plugin; config: PluginConfig }>();
  private initialized = false;

  async register(plugin: Plugin, config: PluginConfig): Promise<void> {
    if (this.initialized) {
      throw new Error('Cannot register plugins after initialization');
    }
    this.plugins.set(plugin.name, { plugin, config });
  }

  async unregister(name: string): Promise<void> {
    const entry = this.plugins.get(name);
    if (entry) {
      await entry.plugin.shutdown();
      this.plugins.delete(name);
    }
  }

  async initialize(): Promise<void> {
    const sorted = [...this.plugins.entries()]
      .sort((a, b) => a[1].config.priority - b[1].config.priority);

    for (const [name, { plugin, config }] of sorted) {
      if (config.enabled) {
        await plugin.init();
      }
    }
    this.initialized = true;
  }

  async executeAll(context: any): Promise<any[]> {
    const results: any[] = [];
    for (const [name, { plugin, config }] of this.plugins) {
      if (config.enabled) {
        results.push(await plugin.execute(context));
      }
    }
    return results;
  }

  getPlugin<T extends Plugin>(name: string): T | undefined {
    return this.plugins.get(name)?.plugin as T | undefined;
  }

  listPlugins(): Array<{ name: string; version: string; enabled: boolean }> {
    return [...this.plugins.entries()].map(([name, { plugin, config }]) => ({
      name,
      version: plugin.version,
      enabled: config.enabled,
    }));
  }

  async shutdown(): Promise<void> {
    for (const [, { plugin }] of this.plugins) {
      await plugin.shutdown();
    }
    this.plugins.clear();
    this.initialized = false;
  }
}

// The ONE plugin that actually exists:
class AnalyticsPlugin implements Plugin {
  name = 'analytics';
  version = '1.0.0';

  async init(): Promise<void> {
    console.log('Analytics initialized');
  }

  async execute(context: any): Promise<void> {
    console.log('Analytics:', JSON.stringify(context));
  }

  async shutdown(): Promise<void> {
    console.log('Analytics shut down');
  }
}

// ---- WRONG DUPLICATION: These look similar but represent different business logic ----

export function formatEventDateForEmail(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
}

export function formatEventDateForReceipt(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
}

// ---- TRUE DUPLICATION: These three functions do the exact same thing ----

export function validateTicketQuantity(qty: number): boolean {
  if (qty < 1) return false;
  if (qty > 10) return false;
  if (!Number.isInteger(qty)) return false;
  return true;
}

export function checkQuantityValid(quantity: number): boolean {
  if (quantity < 1) return false;
  if (quantity > 10) return false;
  if (!Number.isInteger(quantity)) return false;
  return true;
}

export function isValidQty(q: number): boolean {
  if (q < 1) return false;
  if (q > 10) return false;
  if (!Number.isInteger(q)) return false;
  return true;
}
```

Read through the file. Do not fix anything yet.

```bash
wc -l src/services/purchase-handler.ts
# Should be around 230+ lines
```

> **Reflect:** Before reading further, list every problem you see. How many did you find?

---

## 1. Naming: Say What You Mean

The first thing wrong with this file is the names. Names are the primary way developers understand code. Bad names force you to read the implementation to understand the intent.

### The Offenders

| Bad Name | What It Actually Does | Better Name |
|----------|----------------------|-------------|
| `processData` | Handles a ticket purchase | `handleTicketPurchase` |
| `d` | Purchase request data | `purchaseRequest` |
| `flag` | Whether early bird pricing is eligible | `isEarlyBirdEligible` |
| `tmp` | Discount percentage | `discountPercentage` |
| `cb` | Post-purchase callback | `onPurchaseComplete` |
| `r` | Database query result | `eventQueryResult` |
| `e` | Event record | `event` |
| `n` | Tickets already sold | `ticketsSold` |
| `c` | Event capacity | `eventCapacity` |
| `p` | Calculated price | `totalPriceInCents` |

### Build: Rename 10 Things

Create the renamed version:

```typescript
// src/services/ticket-purchase.service.ts

import { Pool } from 'pg';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

interface PurchaseRequest {
  eventId: string;
  userId: string;
  type: 'general' | 'vip' | 'early_bird' | 'student';
  qty: number;
}

interface PurchaseResult {
  orderId: string;
  totalInCents: number;
  eventName: string;
}

export async function handleTicketPurchase(
  purchaseRequest: PurchaseRequest,
  isEarlyBirdEligible: boolean,
  discountPercentage: number,
  onPurchaseComplete?: (result: PurchaseResult) => void
): Promise<PurchaseResult | null> {
  // Fetch event
  const eventQueryResult = await pool.query(
    'SELECT * FROM events WHERE id = $1',
    [purchaseRequest.eventId]
  );
  const event = eventQueryResult.rows[0] as EventRow;

  if (!event) {
    return null; // We will fix error handling in section 3
  }

  // Check capacity
  const ticketsSold = event.tickets_sold;
  const eventCapacity = event.capacity;
  if (ticketsSold >= eventCapacity) {
    return null;
  }

  // ... rest of the function (still messy -- we will fix it next)
}
```

Run your tests to make sure nothing breaks:

```bash
npx jest --passWithNoTests
```

Notice how much more readable the function signature is. You can understand the intent without reading a single line of the body.

> **Rule of thumb:** If you need a comment to explain what a variable is, rename the variable instead.

---

## 2. Functions: One Level of Abstraction

### Spot the Problem

`processData` is 150+ lines doing everything: database lookup, capacity check, pricing, order insertion, inventory update, email composition, email sending, analytics, and callback. You have to read every line to understand any part.

### Refactor: Break Into Focused Functions

Each function should do one thing at one level of abstraction:

```typescript
// src/services/ticket-purchase.service.ts (refactored)

import { Pool, PoolClient } from 'pg';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// --- Types ---

interface PurchaseRequest {
  eventId: string;
  userId: string;
  ticketType: 'general' | 'vip' | 'early_bird' | 'student';
  quantity: number;
}

interface PricingContext {
  isEarlyBirdEligible: boolean;
  discountPercentage: number;
}

interface PurchaseResult {
  orderId: string;
  totalInCents: number;
  eventName: string;
}

interface EventDetails {
  id: string;
  name: string;
  basePriceCents: number;
  capacity: number;
  ticketsSold: number;
  startsAt: Date;
}

// --- Main orchestrator: reads like a recipe ---

export async function handleTicketPurchase(
  request: PurchaseRequest,
  pricing: PricingContext,
  onPurchaseComplete?: (result: PurchaseResult) => void
): Promise<PurchaseResult> {
  const event = await fetchEventOrThrow(request.eventId);

  assertCapacityAvailable(event, request.quantity);

  const totalInCents = calculateTicketPrice(
    event.basePriceCents,
    request.ticketType,
    request.quantity,
    pricing
  );

  const orderId = await createOrderAndReserveTickets(
    request,
    totalInCents
  );

  await sendConfirmationEmail(request.userId, event, request, totalInCents, orderId);

  logPurchaseAnalytics(orderId, request, totalInCents);

  const result: PurchaseResult = {
    orderId,
    totalInCents,
    eventName: event.name,
  };

  if (onPurchaseComplete) {
    onPurchaseComplete(result);
  }

  return result;
}

// --- Focused helper functions ---

async function fetchEventOrThrow(eventId: string): Promise<EventDetails> {
  const result = await pool.query('SELECT * FROM events WHERE id = $1', [eventId]);
  const row = result.rows[0];

  if (!row) {
    throw new Error(`Event not found: ${eventId}`);
  }

  return {
    id: row.id,
    name: row.name,
    basePriceCents: row.base_price_cents,
    capacity: row.capacity,
    ticketsSold: row.tickets_sold,
    startsAt: new Date(row.starts_at),
  };
}

function assertCapacityAvailable(event: EventDetails, requestedQuantity: number): void {
  const remainingCapacity = event.capacity - event.ticketsSold;

  if (remainingCapacity <= 0) {
    throw new Error(`Event ${event.id} is sold out`);
  }

  if (requestedQuantity > remainingCapacity) {
    throw new Error(
      `Only ${remainingCapacity} tickets remaining for event ${event.id}`
    );
  }
}

function calculateTicketPrice(
  basePriceCents: number,
  ticketType: string,
  quantity: number,
  pricing: PricingContext
): number {
  const MULTIPLIERS: Record<string, number> = {
    general: 1.0,
    vip: 2.5,
    early_bird: 0.8,
    student: 0.6,
  };

  const multiplier = MULTIPLIERS[ticketType];
  if (multiplier === undefined) {
    throw new Error(`Unknown ticket type: ${ticketType}`);
  }

  let unitPrice = basePriceCents * multiplier;

  // Apply early bird discount if eligible
  if (pricing.isEarlyBirdEligible && pricing.discountPercentage > 0) {
    unitPrice = unitPrice * (1 - pricing.discountPercentage / 100);
  }

  return Math.round(unitPrice * quantity);
}

async function createOrderAndReserveTickets(
  request: PurchaseRequest,
  totalInCents: number
): Promise<string> {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    const orderResult = await client.query(
      `INSERT INTO orders (event_id, user_id, ticket_type, quantity, total_in_cents, status)
       VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id`,
      [request.eventId, request.userId, request.ticketType, request.quantity, totalInCents]
    );
    const orderId = orderResult.rows[0].id;

    await client.query(
      'UPDATE events SET tickets_sold = tickets_sold + $1 WHERE id = $2',
      [request.quantity, request.eventId]
    );

    await client.query('COMMIT');
    return orderId;
  } catch (error) {
    await client.query('ROLLBACK');
    throw new Error(`Failed to create order: ${(error as Error).message}`);
  } finally {
    client.release();
  }
}

async function sendConfirmationEmail(
  userId: string,
  event: EventDetails,
  request: PurchaseRequest,
  totalInCents: number,
  orderId: string
): Promise<void> {
  const userResult = await pool.query('SELECT * FROM users WHERE id = $1', [userId]);
  const user = userResult.rows[0];

  if (!user?.email) {
    console.warn(`Cannot send confirmation: no email for user ${userId}`);
    return;
  }

  // Email sending delegated to email service (see M16a)
  // For now, log what we would send
  console.log(`[EMAIL] Confirmation to ${user.email} for order ${orderId}`);
}

function logPurchaseAnalytics(
  orderId: string,
  request: PurchaseRequest,
  totalInCents: number
): void {
  console.log(JSON.stringify({
    event: 'purchase',
    orderId,
    eventId: request.eventId,
    ticketType: request.ticketType,
    quantity: request.quantity,
    totalInCents,
    timestamp: new Date().toISOString(),
  }));
}
```

Now the main function reads like prose: fetch event, check capacity, calculate price, create order, send email, log analytics. Each helper function fits on one screen and does one thing.

**Try It:**

```bash
npx jest --passWithNoTests
```

---

## 3. Error Handling: Stop Swallowing Errors

### Spot the Problem

The original code had five `catch (e) {}` blocks that silently swallowed errors. This is the single worst error handling pattern in software engineering. When the order insertion fails, the function returns `null` and the caller has no idea why. When the inventory update fails, `tickets_sold` gets out of sync. Nobody is told.

### The Fix: Propagate Errors With Context

We already fixed this in the refactored version above. Compare:

```typescript
// BEFORE: Silent failure. tickets_sold is now wrong. Nobody knows.
try {
  await pool.query(
    'UPDATE events SET tickets_sold = tickets_sold + $1 WHERE id = $2',
    [d.qty, d.eventId]
  );
} catch (e) {
  // Swallow again -- tickets_sold might be wrong now but whatever
}

// AFTER: Transactional. If anything fails, everything rolls back. Error propagates.
try {
  await client.query('BEGIN');
  // ... insert order ...
  // ... update tickets_sold ...
  await client.query('COMMIT');
} catch (error) {
  await client.query('ROLLBACK');
  throw new Error(`Failed to create order: ${(error as Error).message}`);
}
```

**Rules for error handling:**

1. **Never swallow errors.** If you catch, either handle meaningfully or re-throw with context.
2. **Use transactions for related writes.** If step 2 fails, step 1 should be rolled back.
3. **Distinguish recoverable from unrecoverable.** Email failing is recoverable (log and continue). Order insertion failing is unrecoverable (throw).
4. **Add context when re-throwing.** `"Failed to create order: connection refused"` is infinitely better than `"connection refused"`.

Here is a practical pattern for optional side effects:

```typescript
// Email failure should NOT prevent the purchase from succeeding
async function handleTicketPurchase(/* ... */): Promise<PurchaseResult> {
  // ... order creation (must succeed) ...

  // Non-critical: best effort
  try {
    await sendConfirmationEmail(userId, event, request, totalInCents, orderId);
  } catch (error) {
    // Log with full context, but do NOT re-throw
    console.error('Failed to send confirmation email', {
      orderId,
      userId,
      error: (error as Error).message,
    });
  }

  return result;
}
```

---

## 4. DRY vs the Wrong Abstraction

### Spot the "Wrong" Duplication

Look at these two functions from the messy file:

```typescript
export function formatEventDateForEmail(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
}

export function formatEventDateForReceipt(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
}
```

They are identical. Your instinct says "extract a shared function." **Resist that instinct.** These represent different business concerns:

- Email date formatting is controlled by the marketing team. They might switch to "March 24, 2026" for friendliness.
- Receipt date formatting is controlled by the finance team. They might switch to "2026-03-24" for compliance.

If you extract `formatEventDate()`, one team's change breaks the other. This is the wrong abstraction. Leave them separate.

> **Insight:** Sandi Metz wrote: *"Duplication is far cheaper than the wrong abstraction. Prefer duplication over the wrong abstraction."* The cost of maintaining two identical functions is low. The cost of untangling a shared function that has grown `if` branches for each caller is high.

### Spot the True Duplication

Now look at these three functions:

```typescript
export function validateTicketQuantity(qty: number): boolean { /* ... */ }
export function checkQuantityValid(quantity: number): boolean { /* ... */ }
export function isValidQty(q: number): boolean { /* ... */ }
```

These are the exact same business rule (quantity must be 1-10, integer) copy-pasted three times with different names. If the maximum changes from 10 to 20, you must find and update all three. You will miss one. This is real duplication.

### Build: Extract the True Duplicate

```typescript
// src/validation/ticket.validation.ts

const MIN_TICKET_QUANTITY = 1;
const MAX_TICKET_QUANTITY = 10;

export function isValidTicketQuantity(quantity: number): boolean {
  return (
    Number.isInteger(quantity) &&
    quantity >= MIN_TICKET_QUANTITY &&
    quantity <= MAX_TICKET_QUANTITY
  );
}
```

Now find every usage of the three old functions and replace them with `isValidTicketQuantity`. Delete the originals.

```bash
npx jest --passWithNoTests
```

**The Rule of Three:** Duplicating once is acceptable. Duplicating twice is a signal. The third time you see the same knowledge, extract it.

---

## 5. KISS/YAGNI: Remove the Premature Abstraction

### Spot the Problem

The `PluginManager` class is 70+ lines of code. It supports registering, unregistering, prioritized initialization, executing all plugins, listing plugins, and graceful shutdown. It has exactly **one** plugin: `AnalyticsPlugin`.

This is a textbook YAGNI violation. Someone anticipated a plugin system that never materialized. Every developer now must understand the plugin lifecycle to modify analytics tracking.

### Build: Replace With What You Actually Need

```typescript
// BEFORE: 70 lines of PluginManager + AnalyticsPlugin

// AFTER: 5 lines
class AnalyticsTracker {
  track(event: string, data: Record<string, unknown>): void {
    console.log(JSON.stringify({ event, ...data, timestamp: new Date().toISOString() }));
  }
}

export const analyticsTracker = new AnalyticsTracker();
```

If a second analytics destination appears (say, Segment or Mixpanel), you can introduce an interface at that point. Not before. The speculative plugin system is gone. The code is simpler, easier to understand, and does exactly what the business needs.

Delete the `PluginManager`, `Plugin` interface, `PluginConfig` interface, and `AnalyticsPlugin` class from the file. Replace all usages with `analyticsTracker.track(...)`.

---

## 6. The Final Review

Let us compare the before and after:

**Before:**
- `processData(d, flag, tmp, cb)` -- unreadable signature
- 150+ lines doing 6 things
- 5 silently swallowed errors
- `PluginManager` for one plugin
- 3 copies of the same validation
- Variables named `d`, `e`, `r`, `n`, `c`, `p`

**After:**
- `handleTicketPurchase(request, pricing, onPurchaseComplete)` -- self-documenting
- Orchestrator + 5 focused helper functions (~15 lines each)
- Errors propagated with context; optional side effects caught and logged
- `AnalyticsTracker` (5 lines)
- One `isValidTicketQuantity` function
- Variables named `purchaseRequest`, `event`, `ticketsSold`, `eventCapacity`, `totalPriceInCents`

---

## 7. Reflect

> **Is this codebase better after our changes? How would you measure "better"?**

Some ways to measure:
- **Time to understand:** How long does it take a new developer to understand `handleTicketPurchase` vs `processData`?
- **Time to change:** Adding a new ticket type, changing the email template, or modifying analytics -- how many files must change?
- **Error visibility:** When something breaks, how quickly can you find the root cause?
- **Test coverage:** Can you unit-test the pricing logic without a database?

Clean code is not about aesthetics. It is about the economics of change. Every minute saved reading code is a minute available for building features.

---

## Checklist

Before moving on, confirm:

- [ ] You renamed 10 identifiers to be self-documenting
- [ ] The 150-line function is broken into functions of ~15 lines each
- [ ] No `catch (e) {}` blocks remain -- errors are handled or propagated with context
- [ ] The two date formatting functions remain separate (different business concerns)
- [ ] The three duplicate validation functions are consolidated into one
- [ ] The `PluginManager` is replaced with a simple `AnalyticsTracker`
- [ ] Tests still pass after every change

---

## What's Next

In L1-M16c, we move from code-level principles to design patterns: Strategy, Observer, Repository, Decorator, and Factory. You will build each one into TicketPulse, solving real problems rather than memorizing textbook definitions.

## Key Terms

| Term | Definition |
|------|-----------|
| **Code smell** | A surface-level indicator in code that often signals a deeper structural or design problem. |
| **DRY** | Don't Repeat Yourself; a principle that aims to reduce duplication of logic or knowledge in a codebase. |
| **KISS** | Keep It Simple, Stupid; a principle favoring straightforward solutions over unnecessarily complex ones. |
| **YAGNI** | You Ain't Gonna Need It; a principle advising against building features until they are actually required. |
| **Refactoring** | The process of restructuring existing code to improve readability, structure, or performance without changing its behavior. |

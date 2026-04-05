# L1-M16: Testing Fundamentals

> **Loop 1 (Foundation)** | Section 1C: Building the API | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M11 (REST API Design)
>
> **Source:** Chapters 25, 5, 7, 8 of the 100x Engineer Guide

---

## The Goal

TicketPulse has zero tests. Every time you change something, you have to manually curl the endpoints and visually check the output. That is slow, error-prone, and does not scale.

**From the guide:** Chapter 8 makes the argument that TDD is a design tool, not a testing tool. The claim sounds like a slogan until you experience it. When you write a test before the code, you're forced to answer — from the caller's perspective — "what should this actually do?" That question shapes the interface, the error handling, and the names. Code written test-first is almost always cleaner and more modular than code written implementation-first, because the test will immediately surface any design that's awkward to verify. Chapter 8 also makes the case that tests are what let you refactor fearlessly: "Refactoring without tests is archaeology. Refactoring with tests is sculpture." You're about to prove both claims on a real codebase. Start with zero tests, write your first failing test against TicketPulse's ticket pricing logic, and notice what the act of writing the test tells you about the design before you've written a single line of implementation.

By the end of this module, TicketPulse will have a proper test suite: fast unit tests for pure business logic, integration tests that hit a real database, mocked external services, and a coverage report showing exactly what is tested and what is not.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Install the testing dependencies:

```bash
cd ticketpulse
npm install -D jest ts-jest @types/jest supertest @types/supertest
```

Create the Jest config:

```typescript
// jest.config.ts

import type { Config } from 'jest';

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.test.ts'],
  coverageDirectory: 'coverage',
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/server.ts',        // Entry point, not unit-testable
    '!src/db/migrate.ts',    // Migration script
  ],
  // Separate unit and integration tests
  projects: [
    {
      displayName: 'unit',
      testMatch: ['<rootDir>/src/**/*.unit.test.ts'],
      preset: 'ts-jest',
      testEnvironment: 'node',
    },
    {
      displayName: 'integration',
      testMatch: ['<rootDir>/src/**/*.integration.test.ts'],
      preset: 'ts-jest',
      testEnvironment: 'node',
      // Integration tests need more time (database setup)
      testTimeout: 30000,
    },
  ],
};

export default config;
```

Run the test command to verify it works (it should find zero tests):

```bash
npx jest --passWithNoTests
# Expected: Test Suites: 0 total | Tests: 0 total | PASS
```

Good. Time to write actual tests.

---

## 1. The Testing Pyramid

Before writing a single test, understand what goes where:

```
        /  E2E  \          Few (5-10): Full browser, real deployment
       / -------- \        Slow, expensive, flaky. Critical paths only.
      /            \
     / Integration  \      Some (20-50): Your code + real database
    / -------------- \     Medium speed. Catches cross-cutting issues.
   /                  \
  /     Unit Tests     \   Many (100+): Pure functions, isolated logic
 / -------------------- \  Fast, cheap, precise. The foundation.
```

**Unit tests** are fast because they test pure functions with no external dependencies. No database, no network, no file system.

**Integration tests** are slower because they test your code with real dependencies (a real Postgres instance). They catch the bugs that unit tests miss -- wrong SQL, transaction issues, race conditions.

**E2E tests** test the full system from the user's perspective. We will not write these in this module (they come in Loop 2).

For TicketPulse, the split should be roughly:
- **Unit tests**: Pricing logic, validation logic, formatters, utility functions
- **Integration tests**: API endpoints with a real database, the full ticket purchase flow
- **E2E tests** (later): Sign up, find event, buy ticket, receive confirmation

---

## 2. Build: Unit Test the Pricing Function

First, let us extract the ticket pricing logic into a pure function. Pure functions are the easiest things to test -- no side effects, no database, no state.

```typescript
// src/services/pricing.ts

export interface PricingInput {
  basePriceInCents: number;
  tier: 'general' | 'vip' | 'early_bird';
  quantity: number;
  eventDate: Date;
  purchaseDate?: Date;  // Defaults to now
}

export interface PricingResult {
  unitPriceInCents: number;
  subtotalInCents: number;
  serviceFeeInCents: number;
  totalInCents: number;
  breakdown: {
    basePrice: number;
    tierMultiplier: number;
    earlyBirdDiscount: number;
    serviceFeeRate: number;
  };
}

const TIER_MULTIPLIERS: Record<string, number> = {
  general: 1.0,
  vip: 2.5,
  early_bird: 0.8,
};

const SERVICE_FEE_RATE = 0.15;  // 15% service fee
const EARLY_BIRD_DAYS = 30;     // Early bird pricing if purchased 30+ days before event

export function calculateTicketPrice(input: PricingInput): PricingResult {
  const { basePriceInCents, tier, quantity, eventDate } = input;
  const purchaseDate = input.purchaseDate || new Date();

  if (basePriceInCents < 0) {
    throw new Error('Base price cannot be negative');
  }
  if (quantity < 1 || !Number.isInteger(quantity)) {
    throw new Error('Quantity must be a positive integer');
  }
  if (quantity > 10) {
    throw new Error('Maximum 10 tickets per purchase');
  }

  // Calculate tier multiplier
  const tierMultiplier = TIER_MULTIPLIERS[tier] || 1.0;

  // Calculate early bird discount (additional 10% off if 30+ days before event)
  const daysUntilEvent = Math.floor((eventDate.getTime() - purchaseDate.getTime()) / (1000 * 60 * 60 * 24));
  const earlyBirdDiscount = daysUntilEvent >= EARLY_BIRD_DAYS ? 0.10 : 0;

  // Calculate unit price
  let unitPriceInCents = Math.round(basePriceInCents * tierMultiplier);

  // Apply early bird discount
  if (earlyBirdDiscount > 0) {
    unitPriceInCents = Math.round(unitPriceInCents * (1 - earlyBirdDiscount));
  }

  // Calculate totals
  const subtotalInCents = unitPriceInCents * quantity;
  const serviceFeeInCents = Math.round(subtotalInCents * SERVICE_FEE_RATE);
  const totalInCents = subtotalInCents + serviceFeeInCents;

  return {
    unitPriceInCents,
    subtotalInCents,
    serviceFeeInCents,
    totalInCents,
    breakdown: {
      basePrice: basePriceInCents,
      tierMultiplier,
      earlyBirdDiscount,
      serviceFeeRate: SERVICE_FEE_RATE,
    },
  };
}
```

Now write the unit tests:

```typescript
// src/services/pricing.unit.test.ts

import { calculateTicketPrice, PricingInput } from './pricing';

describe('calculateTicketPrice', () => {
  const futureDate = new Date('2026-12-01T20:00:00Z');
  const purchaseDate = new Date('2026-03-24T10:00:00Z'); // ~8 months before event

  const baseInput: PricingInput = {
    basePriceInCents: 10000,  // $100.00
    tier: 'general',
    quantity: 1,
    eventDate: futureDate,
    purchaseDate,
  };

  // -----------------------------------------------
  // Basic pricing
  // -----------------------------------------------
  describe('general tier', () => {
    it('calculates correct price for a single general ticket', () => {
      const result = calculateTicketPrice(baseInput);

      // Base: $100 * 1.0 (general) = $100
      // Early bird: 10% off = $90
      // Service fee: 15% of $90 = $13.50
      // Total: $103.50
      expect(result.unitPriceInCents).toBe(9000);
      expect(result.subtotalInCents).toBe(9000);
      expect(result.serviceFeeInCents).toBe(1350);
      expect(result.totalInCents).toBe(10350);
    });

    it('multiplies correctly for multiple tickets', () => {
      const result = calculateTicketPrice({ ...baseInput, quantity: 3 });

      expect(result.unitPriceInCents).toBe(9000);
      expect(result.subtotalInCents).toBe(27000);  // 3 * $90
      expect(result.serviceFeeInCents).toBe(4050);  // 15% of $270
      expect(result.totalInCents).toBe(31050);       // $310.50
    });
  });

  // -----------------------------------------------
  // Tier pricing
  // -----------------------------------------------
  describe('VIP tier', () => {
    it('applies 2.5x multiplier for VIP tickets', () => {
      const result = calculateTicketPrice({ ...baseInput, tier: 'vip' });

      // Base: $100 * 2.5 (VIP) = $250
      // Early bird: 10% off = $225
      expect(result.unitPriceInCents).toBe(22500);
    });
  });

  describe('early_bird tier', () => {
    it('applies 0.8x multiplier for early bird tickets', () => {
      const result = calculateTicketPrice({ ...baseInput, tier: 'early_bird' });

      // Base: $100 * 0.8 (early bird tier) = $80
      // Early bird time discount: 10% off = $72
      expect(result.unitPriceInCents).toBe(7200);
    });
  });

  // -----------------------------------------------
  // Early bird discount timing
  // -----------------------------------------------
  describe('early bird time discount', () => {
    it('applies 10% discount when purchased 30+ days before event', () => {
      const farFuture = new Date('2026-06-01T20:00:00Z');
      const earlyPurchase = new Date('2026-03-01T10:00:00Z'); // 92 days before

      const result = calculateTicketPrice({
        ...baseInput,
        eventDate: farFuture,
        purchaseDate: earlyPurchase,
      });

      expect(result.breakdown.earlyBirdDiscount).toBe(0.10);
      expect(result.unitPriceInCents).toBe(9000); // $100 - 10%
    });

    it('does NOT apply discount when purchased less than 30 days before event', () => {
      const soonEvent = new Date('2026-04-10T20:00:00Z');
      const latePurchase = new Date('2026-04-01T10:00:00Z'); // 9 days before

      const result = calculateTicketPrice({
        ...baseInput,
        eventDate: soonEvent,
        purchaseDate: latePurchase,
      });

      expect(result.breakdown.earlyBirdDiscount).toBe(0);
      expect(result.unitPriceInCents).toBe(10000); // Full price
    });

    it('applies discount at exactly 30 days', () => {
      const event = new Date('2026-05-01T20:00:00Z');
      const purchase = new Date('2026-04-01T20:00:00Z'); // Exactly 30 days

      const result = calculateTicketPrice({
        ...baseInput,
        eventDate: event,
        purchaseDate: purchase,
      });

      expect(result.breakdown.earlyBirdDiscount).toBe(0.10);
    });
  });

  // -----------------------------------------------
  // Edge cases and validation
  // -----------------------------------------------
  describe('validation', () => {
    it('throws on negative base price', () => {
      expect(() =>
        calculateTicketPrice({ ...baseInput, basePriceInCents: -100 })
      ).toThrow('Base price cannot be negative');
    });

    it('throws on zero quantity', () => {
      expect(() =>
        calculateTicketPrice({ ...baseInput, quantity: 0 })
      ).toThrow('Quantity must be a positive integer');
    });

    it('throws on fractional quantity', () => {
      expect(() =>
        calculateTicketPrice({ ...baseInput, quantity: 1.5 })
      ).toThrow('Quantity must be a positive integer');
    });

    it('throws when quantity exceeds maximum', () => {
      expect(() =>
        calculateTicketPrice({ ...baseInput, quantity: 11 })
      ).toThrow('Maximum 10 tickets per purchase');
    });
  });

  // -----------------------------------------------
  // Rounding
  // -----------------------------------------------
  describe('rounding', () => {
    it('rounds to the nearest cent (no fractional cents)', () => {
      // $33.33 base price -> various multipliers will produce fractional cents
      const result = calculateTicketPrice({
        ...baseInput,
        basePriceInCents: 3333,
      });

      expect(Number.isInteger(result.unitPriceInCents)).toBe(true);
      expect(Number.isInteger(result.serviceFeeInCents)).toBe(true);
      expect(Number.isInteger(result.totalInCents)).toBe(true);
    });
  });

  // -----------------------------------------------
  // Free events
  // -----------------------------------------------
  describe('free events', () => {
    it('handles zero base price correctly', () => {
      const result = calculateTicketPrice({
        ...baseInput,
        basePriceInCents: 0,
      });

      expect(result.unitPriceInCents).toBe(0);
      expect(result.subtotalInCents).toBe(0);
      expect(result.serviceFeeInCents).toBe(0);
      expect(result.totalInCents).toBe(0);
    });
  });
});
```

Run the unit tests:

```bash
npx jest --selectProjects unit
```

Expected:

```
 PASS   unit  src/services/pricing.unit.test.ts
  calculateTicketPrice
    general tier
      ✓ calculates correct price for a single general ticket (2 ms)
      ✓ multiplies correctly for multiple tickets (1 ms)
    VIP tier
      ✓ applies 2.5x multiplier for VIP tickets
    early_bird tier
      ✓ applies 0.8x multiplier for early bird tickets
    early bird time discount
      ✓ applies 10% discount when purchased 30+ days before event
      ✓ does NOT apply discount when purchased less than 30 days before event
      ✓ applies discount at exactly 30 days
    validation
      ✓ throws on negative base price
      ✓ throws on zero quantity
      ✓ throws on fractional quantity
      ✓ throws when quantity exceeds maximum
    rounding
      ✓ rounds to the nearest cent (no fractional cents)
    free events
      ✓ handles zero base price correctly

Test Suites: 1 passed, 1 total
Tests:       13 passed, 13 total
Time:        1.2s
```

13 tests, all passing, in 1.2 seconds. That is the power of unit tests -- they are fast because they test pure functions with no I/O.

---

## 3. Build: Integration Test the Ticket Purchase Flow

Unit tests verify individual functions. Integration tests verify that the pieces work together -- your route handler, your database queries, your transaction logic.

For integration tests, we need a real database. We will use the Postgres service from docker compose (or you can use testcontainers for fully isolated tests):

```typescript
// src/routes/events.integration.test.ts

import request from 'supertest';
import { app } from '../app';
import { pool } from '../db';

describe('Events API (integration)', () => {
  // Clean up the database before each test
  beforeEach(async () => {
    await pool.query('DELETE FROM tickets');
    await pool.query('DELETE FROM events');
    await pool.query('ALTER SEQUENCE events_id_seq RESTART WITH 1');
    await pool.query('ALTER SEQUENCE tickets_id_seq RESTART WITH 1');
  });

  // Close the database connection pool after all tests
  afterAll(async () => {
    await pool.end();
  });

  // -----------------------------------------------
  // Create event
  // -----------------------------------------------
  describe('POST /api/events', () => {
    const validEvent = {
      title: 'Test Concert',
      description: 'A test event',
      venue: 'Test Arena',
      city: 'Test City',
      date: '2026-12-01T20:00:00Z',
      totalTickets: 100,
      priceInCents: 5000,
    };

    it('creates an event and returns 201', async () => {
      const res = await request(app)
        .post('/api/events')
        .send(validEvent)
        .expect(201);

      expect(res.body.data).toMatchObject({
        title: 'Test Concert',
        venue: 'Test Arena',
        totalTickets: 100,
        availableTickets: 100,
        priceInCents: 5000,
      });
      expect(res.body.data.id).toBeDefined();
      expect(res.body.data.createdAt).toBeDefined();
    });

    it('returns 400 when required fields are missing', async () => {
      const res = await request(app)
        .post('/api/events')
        .send({ title: 'Incomplete Event' })
        .expect(400);

      expect(res.body.error.code).toBe('VALIDATION_ERROR');
      expect(res.body.error.details.length).toBeGreaterThan(0);
    });
  });

  // -----------------------------------------------
  // List events
  // -----------------------------------------------
  describe('GET /api/events', () => {
    it('returns an empty list when no events exist', async () => {
      const res = await request(app)
        .get('/api/events')
        .expect(200);

      expect(res.body.data).toEqual([]);
      expect(res.body.pagination.totalCount).toBe(0);
    });

    it('returns events with pagination', async () => {
      // Create 3 events
      for (let i = 1; i <= 3; i++) {
        await request(app)
          .post('/api/events')
          .send({
            title: `Event ${i}`,
            venue: `Venue ${i}`,
            city: i <= 2 ? 'NYC' : 'LA',
            date: `2026-${String(i + 6).padStart(2, '0')}-15T20:00:00Z`,
            totalTickets: 100,
            priceInCents: 5000,
          });
      }

      const res = await request(app)
        .get('/api/events?limit=2&page=1')
        .expect(200);

      expect(res.body.data).toHaveLength(2);
      expect(res.body.pagination.totalCount).toBe(3);
      expect(res.body.pagination.totalPages).toBe(2);
    });

    it('filters events by city', async () => {
      // Create events in different cities
      await request(app).post('/api/events').send({
        title: 'NYC Event', venue: 'MSG', city: 'NYC',
        date: '2026-09-01T20:00:00Z', totalTickets: 100, priceInCents: 5000,
      });
      await request(app).post('/api/events').send({
        title: 'LA Event', venue: 'Hollywood Bowl', city: 'LA',
        date: '2026-09-15T20:00:00Z', totalTickets: 100, priceInCents: 5000,
      });

      const res = await request(app)
        .get('/api/events?city=NYC')
        .expect(200);

      expect(res.body.data).toHaveLength(1);
      expect(res.body.data[0].city).toBe('NYC');
    });
  });

  // -----------------------------------------------
  // Full purchase flow
  // -----------------------------------------------
  describe('Ticket purchase flow', () => {
    let eventId: number;

    beforeEach(async () => {
      const res = await request(app)
        .post('/api/events')
        .send({
          title: 'Sellout Show',
          venue: 'Tiny Club',
          date: '2026-12-01T20:00:00Z',
          totalTickets: 2,  // Only 2 tickets available!
          priceInCents: 5000,
        });
      eventId = res.body.data.id;
    });

    it('purchases a ticket and decrements available count', async () => {
      // Purchase first ticket
      const purchaseRes = await request(app)
        .post(`/api/events/${eventId}/tickets`)
        .send({ email: 'fan1@example.com', tier: 'general' })
        .expect(201);

      expect(purchaseRes.body.data.purchaserEmail).toBe('fan1@example.com');

      // Verify available tickets decreased
      const eventRes = await request(app)
        .get(`/api/events/${eventId}`)
        .expect(200);

      expect(eventRes.body.data.availableTickets).toBe(1);
    });

    it('returns 409 when event is sold out', async () => {
      // Buy both tickets
      await request(app)
        .post(`/api/events/${eventId}/tickets`)
        .send({ email: 'fan1@example.com' })
        .expect(201);

      await request(app)
        .post(`/api/events/${eventId}/tickets`)
        .send({ email: 'fan2@example.com' })
        .expect(201);

      // Try to buy a third ticket
      const res = await request(app)
        .post(`/api/events/${eventId}/tickets`)
        .send({ email: 'fan3@example.com' })
        .expect(409);

      expect(res.body.error.code).toBe('SOLD_OUT');
    });

    it('returns 404 when event does not exist', async () => {
      const res = await request(app)
        .post('/api/events/99999/tickets')
        .send({ email: 'fan@example.com' })
        .expect(404);

      expect(res.body.error.code).toBe('NOT_FOUND');
    });
  });
});
```

Run the integration tests:

```bash
# Make sure Postgres is running (docker compose up -d postgres)
DATABASE_URL=postgresql://ticketpulse:ticketpulse@localhost:5432/ticketpulse_test \
  npx jest --selectProjects integration
```

---

## 4. Test Doubles: Mock the Email Service

When a ticket is purchased, TicketPulse should send a confirmation email. But we do NOT want to send real emails in tests. This is where test doubles come in.

```typescript
// src/services/emailService.ts

export interface EmailService {
  sendTicketConfirmation(to: string, eventTitle: string, ticketId: number): Promise<void>;
}

// Real implementation (used in production)
export class SendGridEmailService implements EmailService {
  async sendTicketConfirmation(to: string, eventTitle: string, ticketId: number): Promise<void> {
    // In production, this calls the SendGrid API
    console.log(`Sending confirmation email to ${to} for ${eventTitle} (ticket ${ticketId})`);
    // await sendgrid.send({ to, subject: `Your ticket for ${eventTitle}`, ... });
  }
}

// Mock implementation (used in tests)
export class MockEmailService implements EmailService {
  public sentEmails: Array<{ to: string; eventTitle: string; ticketId: number }> = [];

  async sendTicketConfirmation(to: string, eventTitle: string, ticketId: number): Promise<void> {
    // Don't send real emails -- just record the call
    this.sentEmails.push({ to, eventTitle, ticketId });
  }

  // Helper for assertions
  getLastEmail() {
    return this.sentEmails[this.sentEmails.length - 1];
  }

  reset() {
    this.sentEmails = [];
  }
}
```

In tests:

```typescript
// In your integration test setup
import { MockEmailService } from '../services/emailService';

const mockEmail = new MockEmailService();

// After purchasing a ticket:
it('sends a confirmation email after purchase', async () => {
  await request(app)
    .post(`/api/events/${eventId}/tickets`)
    .send({ email: 'fan@example.com' })
    .expect(201);

  expect(mockEmail.sentEmails).toHaveLength(1);
  expect(mockEmail.getLastEmail()).toMatchObject({
    to: 'fan@example.com',
    eventTitle: 'Sellout Show',
  });
});
```

The five types of test doubles:
- **Dummy**: Passed around but never used. Fills a parameter list.
- **Stub**: Returns canned answers. "When asked for the price, always return $100."
- **Spy**: Records how it was called. "Was `sendEmail` called? With what arguments?"
- **Mock**: Pre-programmed expectations. "Expect `sendEmail` to be called exactly once with these args."
- **Fake**: A working but simplified implementation. Our `MockEmailService` is a fake -- it actually stores sent emails in memory.

---

## 5. Debug: A Test That Passes Locally but Fails in CI

This is a real scenario. Here is a test that works on your machine but fails in CI:

```typescript
// BUGGY TEST -- DO NOT COPY
it('creates an event with the correct date', async () => {
  const res = await request(app)
    .post('/api/events')
    .send({
      title: 'Timezone Trap',
      venue: 'Anywhere',
      date: '2026-09-15T20:00:00Z',
      totalTickets: 100,
      priceInCents: 5000,
    })
    .expect(201);

  // This passes on your machine (EST) but fails in CI (UTC)
  expect(res.body.data.createdAt).toContain('2026-03-24');
});
```

Why it fails: `createdAt` uses `NOW()` from the database. On your machine, "now" is in your local timezone. In CI, "now" is UTC. The date might be different.

The fix: never assert on `createdAt` with exact date strings. Instead:

```typescript
it('creates an event with a recent createdAt timestamp', async () => {
  const before = new Date();

  const res = await request(app)
    .post('/api/events')
    .send({ /* ... */ })
    .expect(201);

  const after = new Date();
  const createdAt = new Date(res.body.data.createdAt);

  expect(createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime() - 1000);
  expect(createdAt.getTime()).toBeLessThanOrEqual(after.getTime() + 1000);
});
```

Common reasons tests fail in CI but pass locally:
- **Timezone differences**: CI runs in UTC, your machine doesn't
- **Missing environment variables**: `.env` file exists locally but not in CI
- **Port conflicts**: Another service is using the port
- **Database state**: Local DB has data from previous runs; CI starts fresh
- **File system ordering**: `readdir` order varies by OS
- **Timing**: `setTimeout` or race conditions that work on your fast machine but not on a slower CI runner

---

## 6. TDD Mini-Exercise: Discount Codes

Let us practice Test-Driven Development. Write the tests FIRST, then implement the feature.

**Feature**: TicketPulse should support discount codes. A code gives a percentage off the ticket price.

### Step 1: Write the test (RED)

```typescript
// src/services/discounts.unit.test.ts

import { applyDiscount, DiscountCode } from './discounts';

describe('applyDiscount', () => {
  const validCode: DiscountCode = {
    code: 'SUMMER20',
    percentOff: 20,
    maxUses: 100,
    currentUses: 0,
    expiresAt: new Date('2026-12-31T23:59:59Z'),
  };

  it('applies the percentage discount correctly', () => {
    const result = applyDiscount(10000, validCode);
    expect(result).toBe(8000); // $100 - 20% = $80
  });

  it('rounds to the nearest cent', () => {
    const result = applyDiscount(3333, validCode); // $33.33 - 20%
    expect(result).toBe(2666); // $26.66 (rounded)
    expect(Number.isInteger(result)).toBe(true);
  });

  it('returns 0 for 100% discount', () => {
    const freeCode = { ...validCode, percentOff: 100 };
    const result = applyDiscount(10000, freeCode);
    expect(result).toBe(0);
  });

  it('throws when discount code is expired', () => {
    const expiredCode = { ...validCode, expiresAt: new Date('2025-01-01') };
    expect(() => applyDiscount(10000, expiredCode)).toThrow('Discount code has expired');
  });

  it('throws when discount code has reached max uses', () => {
    const usedUp = { ...validCode, maxUses: 100, currentUses: 100 };
    expect(() => applyDiscount(10000, usedUp)).toThrow('Discount code has been fully redeemed');
  });

  it('throws on invalid percentage (negative)', () => {
    const badCode = { ...validCode, percentOff: -10 };
    expect(() => applyDiscount(10000, badCode)).toThrow('Invalid discount percentage');
  });

  it('throws on invalid percentage (over 100)', () => {
    const badCode = { ...validCode, percentOff: 150 };
    expect(() => applyDiscount(10000, badCode)).toThrow('Invalid discount percentage');
  });
});
```

Run the tests -- they should all FAIL (the module does not exist yet):

```bash
npx jest discounts.unit.test.ts
# Expected: Cannot find module './discounts'
```

### Step 2: Write the minimum code to pass (GREEN)

```typescript
// src/services/discounts.ts

export interface DiscountCode {
  code: string;
  percentOff: number;
  maxUses: number;
  currentUses: number;
  expiresAt: Date;
}

export function applyDiscount(priceInCents: number, discount: DiscountCode): number {
  // Validate the discount
  if (discount.percentOff < 0 || discount.percentOff > 100) {
    throw new Error('Invalid discount percentage');
  }

  if (new Date() > discount.expiresAt) {
    throw new Error('Discount code has expired');
  }

  if (discount.currentUses >= discount.maxUses) {
    throw new Error('Discount code has been fully redeemed');
  }

  // Apply the discount
  const discountAmount = Math.round(priceInCents * (discount.percentOff / 100));
  return priceInCents - discountAmount;
}
```

Run the tests again:

```bash
npx jest discounts.unit.test.ts
# Expected: 7 passed, 7 total
```

All green.

### Step 3: Refactor if needed

The code is clean enough. In TDD, you only refactor when the tests are green and you see an opportunity to improve the code. The tests give you a safety net -- if your refactoring breaks something, the tests catch it.

---

## 7. Common Mistake: Testing Implementation Details

Bad test (tests HOW the code works):

```typescript
// BAD -- this test is coupled to the implementation
it('calls pool.query with the correct SQL', () => {
  const spy = jest.spyOn(pool, 'query');
  await getEvents();
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining('SELECT * FROM events'),
    expect.any(Array)
  );
});
```

If you refactor the SQL (add a column, change the query), this test breaks even though the behavior is identical. You end up spending more time updating tests than writing features.

Good test (tests WHAT the code does):

```typescript
// GOOD -- this test verifies behavior
it('returns active events sorted by date', async () => {
  // Setup: create events in the database
  await createEvent({ title: 'Later', date: '2026-12-01' });
  await createEvent({ title: 'Sooner', date: '2026-06-01' });
  await createEvent({ title: 'Cancelled', date: '2026-09-01', cancelled: true });

  const events = await getEvents();

  expect(events).toHaveLength(2);           // Cancelled event excluded
  expect(events[0].title).toBe('Sooner');   // Sorted by date ascending
  expect(events[1].title).toBe('Later');
});
```

This test does not care about the SQL. It cares about the result. You can rewrite the query, switch to an ORM, or change the database entirely -- as long as the behavior is correct, the test passes.

---

## 8. Observe: Coverage Report

Run the full test suite with coverage:

```bash
npx jest --coverage
```

The coverage report shows:

```
---------------------|---------|----------|---------|---------|---
File                 | % Stmts | % Branch | % Funcs | % Lines |
---------------------|---------|----------|---------|---------|---
All files            |   67.3  |    55.2  |   72.1  |   68.5  |
 services/pricing.ts |   100   |    100   |   100   |   100   |
 services/discounts.ts|  100   |    100   |   100   |   100   |
 routes/events.ts    |   45.2  |    30.1  |   60.0  |   46.8  |
 routes/tickets.ts   |   38.9  |    25.0  |   50.0  |   40.0  |
 middleware/auth.ts   |    0   |      0   |     0   |     0   |
 errors.ts           |   85.7  |    75.0  |   85.7  |   85.7  |
---------------------|---------|----------|---------|---------|---
```

What this tells you:
- **`pricing.ts` and `discounts.ts`**: 100% coverage. Pure functions, fully tested. Good.
- **`routes/events.ts`**: 45% coverage. The route handlers need integration tests.
- **`middleware/auth.ts`**: 0% coverage. No auth tests yet (we will add them).
- **Overall 67%**: Not bad for a start, but we should aim for 80%+.

**What SHOULD be tested** (high value):
- Business logic (pricing, validation, discounts)
- Critical paths (purchase flow, authentication)
- Error handling (what happens when things fail)

**What should NOT obsess you** (low value):
- Simple getters/setters
- Third-party library wrappers
- Configuration files

Target 80%+ line coverage as a hygiene metric. Never chase 100% -- the last 20% has diminishing returns and creates brittle tests.

---

## 9. Checkpoint

After this module, TicketPulse should have:

- [ ] Jest configured with separate unit and integration test projects
- [ ] Unit tests for ticket pricing logic (13+ tests, all passing)
- [ ] Integration tests for the events API and ticket purchase flow
- [ ] A mock email service (test double) for avoiding real email sends
- [ ] TDD-built discount code feature with full test coverage
- [ ] Coverage report showing tested vs untested code
- [ ] Understanding of the testing pyramid (many unit > some integration > few E2E)

**Next up:** L1-M16a where we apply SOLID principles to refactor TicketPulse's code into clean, maintainable modules.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Unit test** | Tests a single function or class in isolation. No database, no network. Fast (milliseconds). |
| **Integration test** | Tests multiple components working together, often with a real database. Slower (seconds). |
| **E2E test** | Tests the full system from the user's perspective. A real browser hitting a real deployment. Slowest (minutes). |
| **Testing pyramid** | Many unit tests (bottom), some integration (middle), few E2E (top). The optimal distribution. |
| **Test double** | A substitute for a real dependency in tests. Types: dummy, stub, spy, mock, fake. |
| **TDD (Test-Driven Development)** | Red-Green-Refactor cycle. Write a failing test, write the minimum code to pass it, then refactor. |
| **Coverage** | The percentage of code executed by tests. Useful as a negative signal (low = under-tested). Poor as a positive signal (high does not mean well-tested). |
| **Supertest** | A library for testing HTTP endpoints in Node.js without starting a server. |
| **Testcontainers** | A library that spins up real Docker containers (Postgres, Redis, etc.) for integration tests. |
---

## What's Next

In **SOLID Principles in Practice** (L1-M16a), you'll build on what you learned here and take it further.

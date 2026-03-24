# L1-M16a: SOLID Principles in Practice

> **Loop 1 (Foundation)** | Section 1D: Software Engineering Principles | Duration: 75 min | Tier: Core
>
> **Prerequisites:** L1-M16 (Testing Fundamentals)
>
> **What you'll build:** You will take TicketPulse's monolithic OrderService -- riddled with SOLID violations -- and refactor it principle by principle. Each refactoring is a separate commit. Tests pass after every step.

---

## The Goal

TicketPulse works. The endpoints return the right data. The tests pass. But the codebase is getting harder to change. Adding a new ticket type means editing three files. Testing the order flow requires a real database and a real email provider. A single service handles order creation, email sending, payment processing, and analytics tracking.

This module walks through each SOLID principle with a real violation planted in TicketPulse, then refactors it. You will feel the pain of the violation first, then feel the relief of the fix.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Set up the starting point. Create the monolithic OrderService that we will tear apart:

```bash
cd ticketpulse
mkdir -p src/services src/repositories src/interfaces
```

```typescript
// src/services/order.service.ts
// THE MONOLITH: This file violates every SOLID principle.
// By the end of this module, it will be clean.

import { Pool } from 'pg';
import Stripe from 'stripe';
import nodemailer from 'nodemailer';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const mailer = nodemailer.createTransport({ host: 'smtp.example.com', port: 587 });

interface Order {
  id: string;
  eventId: string;
  userId: string;
  ticketType: 'general' | 'vip' | 'early_bird';
  quantity: number;
  totalInCents: number;
  status: string;
  createdAt: Date;
}

export class OrderService {
  // ---- SRP VIOLATION: This class handles orders, emails, payments, AND analytics ----

  async createOrder(
    userId: string,
    eventId: string,
    ticketType: string,
    quantity: number
  ): Promise<Order> {
    // Fetch event details
    const eventResult = await pool.query(
      'SELECT * FROM events WHERE id = $1', [eventId]
    );
    const event = eventResult.rows[0];
    if (!event) throw new Error('Event not found');

    // ---- OCP VIOLATION: Adding a new ticket type means modifying this function ----
    let priceInCents: number;
    if (ticketType === 'general') {
      priceInCents = event.base_price_cents;
    } else if (ticketType === 'vip') {
      priceInCents = event.base_price_cents * 2.5;
    } else if (ticketType === 'early_bird') {
      priceInCents = event.base_price_cents * 0.8;
    } else {
      throw new Error(`Unknown ticket type: ${ticketType}`);
    }

    const totalInCents = Math.round(priceInCents * quantity);

    // ---- DIP VIOLATION: Directly using pg Pool, not an abstraction ----
    const orderResult = await pool.query(
      `INSERT INTO orders (event_id, user_id, ticket_type, quantity, total_in_cents, status)
       VALUES ($1, $2, $3, $4, $5, 'pending')
       RETURNING *`,
      [eventId, userId, ticketType, quantity, totalInCents]
    );
    const order = orderResult.rows[0];

    // Process payment directly
    const paymentIntent = await stripe.paymentIntents.create({
      amount: totalInCents,
      currency: 'usd',
      metadata: { orderId: order.id },
    });

    await pool.query(
      'UPDATE orders SET status = $1, payment_id = $2 WHERE id = $3',
      ['confirmed', paymentIntent.id, order.id]
    );

    // Send confirmation email directly
    await mailer.sendMail({
      from: 'tickets@ticketpulse.com',
      to: await this.getUserEmail(userId),
      subject: `Order Confirmed: ${event.name}`,
      html: `<h1>Your tickets are confirmed!</h1>
             <p>${quantity}x ${ticketType} for ${event.name}</p>
             <p>Total: $${(totalInCents / 100).toFixed(2)}</p>`,
    });

    // Track analytics directly
    console.log(JSON.stringify({
      event: 'order_created',
      orderId: order.id,
      eventId,
      ticketType,
      quantity,
      totalInCents,
      timestamp: new Date().toISOString(),
    }));

    return order;
  }

  private async getUserEmail(userId: string): Promise<string> {
    const result = await pool.query('SELECT email FROM users WHERE id = $1', [userId]);
    return result.rows[0]?.email;
  }

  // ---- ISP VIOLATION: Callers who only need to read orders are forced to ----
  // ---- depend on all of these methods ----
  async getOrder(id: string): Promise<Order> {
    const result = await pool.query('SELECT * FROM orders WHERE id = $1', [id]);
    return result.rows[0];
  }

  async getOrdersByUser(userId: string): Promise<Order[]> {
    const result = await pool.query(
      'SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC', [userId]
    );
    return result.rows;
  }

  async cancelOrder(id: string): Promise<void> {
    await pool.query('UPDATE orders SET status = $1 WHERE id = $2', ['cancelled', id]);
  }

  async generateSalesReport(eventId: string): Promise<{ total: number; count: number }> {
    const result = await pool.query(
      'SELECT SUM(total_in_cents) as total, COUNT(*) as count FROM orders WHERE event_id = $1',
      [eventId]
    );
    return { total: result.rows[0].total, count: result.rows[0].count };
  }

  async bulkRefund(orderIds: string[]): Promise<void> {
    for (const id of orderIds) {
      await this.cancelOrder(id);
      // refund logic...
    }
  }
}
```

Verify the file is there:

```bash
npx tsc --noEmit src/services/order.service.ts 2>&1 | head -5
# You will see type errors -- that is fine, we are about to refactor
```

Good. Now let us study this mess.

---

## 1. Single Responsibility Principle (SRP)

> "A module should be responsible to one, and only one, actor."
> -- Robert C. Martin

### Spot the Violation

Look at `OrderService.createOrder()`. Count the distinct responsibilities:

1. **Order creation** -- building and persisting the order
2. **Payment processing** -- charging via Stripe
3. **Email sending** -- composing and delivering a confirmation email
4. **Analytics tracking** -- logging the purchase event

Four responsibilities. Four different actors who might request changes to this code: the product team (order flow), the finance team (payment logic), the marketing team (email templates), and the data team (analytics schema).

> **Reflect:** If the marketing team asks you to change the email template, you are editing the same file that handles payments. If you introduce a bug, you break the purchase flow. Is that acceptable?

### Refactor: Extract Each Responsibility

Create focused services:

```typescript
// src/services/payment.service.ts

import Stripe from 'stripe';

export interface PaymentService {
  charge(amountInCents: number, metadata: Record<string, string>): Promise<string>;
}

export class StripePaymentService implements PaymentService {
  private stripe: Stripe;

  constructor(secretKey: string) {
    this.stripe = new Stripe(secretKey);
  }

  async charge(amountInCents: number, metadata: Record<string, string>): Promise<string> {
    const paymentIntent = await this.stripe.paymentIntents.create({
      amount: amountInCents,
      currency: 'usd',
      metadata,
    });
    return paymentIntent.id;
  }
}
```

```typescript
// src/services/email.service.ts

import nodemailer, { Transporter } from 'nodemailer';

export interface EmailService {
  sendOrderConfirmation(
    to: string,
    eventName: string,
    ticketType: string,
    quantity: number,
    totalInCents: number
  ): Promise<void>;
}

export class SmtpEmailService implements EmailService {
  private transporter: Transporter;

  constructor(host: string, port: number) {
    this.transporter = nodemailer.createTransport({ host, port });
  }

  async sendOrderConfirmation(
    to: string,
    eventName: string,
    ticketType: string,
    quantity: number,
    totalInCents: number
  ): Promise<void> {
    await this.transporter.sendMail({
      from: 'tickets@ticketpulse.com',
      to,
      subject: `Order Confirmed: ${eventName}`,
      html: `<h1>Your tickets are confirmed!</h1>
             <p>${quantity}x ${ticketType} for ${eventName}</p>
             <p>Total: $${(totalInCents / 100).toFixed(2)}</p>`,
    });
  }
}
```

```typescript
// src/services/analytics.service.ts

export interface AnalyticsService {
  trackOrderCreated(data: {
    orderId: string;
    eventId: string;
    ticketType: string;
    quantity: number;
    totalInCents: number;
  }): void;
}

export class ConsoleAnalyticsService implements AnalyticsService {
  trackOrderCreated(data: {
    orderId: string;
    eventId: string;
    ticketType: string;
    quantity: number;
    totalInCents: number;
  }): void {
    console.log(JSON.stringify({
      event: 'order_created',
      ...data,
      timestamp: new Date().toISOString(),
    }));
  }
}
```

Now `OrderService.createOrder()` becomes an orchestrator:

```typescript
// src/services/order.service.ts (after SRP refactor)

export class OrderService {
  constructor(
    private orderRepo: OrderRepository,
    private userRepo: UserRepository,
    private eventRepo: EventRepository,
    private paymentService: PaymentService,
    private emailService: EmailService,
    private analyticsService: AnalyticsService
  ) {}

  async createOrder(
    userId: string,
    eventId: string,
    ticketType: string,
    quantity: number
  ): Promise<Order> {
    const event = await this.eventRepo.findById(eventId);
    if (!event) throw new Error('Event not found');

    // Pricing logic still lives here (we will fix this with OCP next)
    const priceInCents = this.calculatePrice(event.basePriceCents, ticketType);
    const totalInCents = Math.round(priceInCents * quantity);

    const order = await this.orderRepo.create({
      eventId, userId, ticketType, quantity, totalInCents, status: 'pending',
    });

    const paymentId = await this.paymentService.charge(totalInCents, { orderId: order.id });
    await this.orderRepo.updateStatus(order.id, 'confirmed', paymentId);

    const user = await this.userRepo.findById(userId);
    await this.emailService.sendOrderConfirmation(
      user!.email, event.name, ticketType, quantity, totalInCents
    );

    this.analyticsService.trackOrderCreated({
      orderId: order.id, eventId, ticketType, quantity, totalInCents,
    });

    return { ...order, status: 'confirmed' };
  }

  private calculatePrice(basePriceCents: number, ticketType: string): number {
    if (ticketType === 'general') return basePriceCents;
    if (ticketType === 'vip') return basePriceCents * 2.5;
    if (ticketType === 'early_bird') return basePriceCents * 0.8;
    throw new Error(`Unknown ticket type: ${ticketType}`);
  }
}
```

**Try It:** Run your tests after this refactoring:

```bash
npx jest --passWithNoTests
```

Commit:

```bash
git add -A && git commit -m "refactor: extract payment, email, analytics from OrderService (SRP)"
```

---

## 2. Open/Closed Principle (OCP)

> "Software entities should be open for extension, but closed for modification."
> -- Bertrand Meyer

### Spot the Violation

Look at `calculatePrice()`. To add a new ticket type -- say, "group_discount" or "student" -- you must modify this function. Every modification risks breaking existing pricing for general, VIP, and early bird tickets.

### Refactor: Strategy Pattern

```typescript
// src/services/pricing-strategy.ts

export interface PricingStrategy {
  calculate(basePriceCents: number, quantity: number): number;
}

export class FlatPricing implements PricingStrategy {
  calculate(basePriceCents: number, quantity: number): number {
    return basePriceCents * quantity;
  }
}

export class VipPricing implements PricingStrategy {
  private multiplier = 2.5;

  calculate(basePriceCents: number, quantity: number): number {
    return Math.round(basePriceCents * this.multiplier * quantity);
  }
}

export class EarlyBirdPricing implements PricingStrategy {
  private discount = 0.2; // 20% off

  calculate(basePriceCents: number, quantity: number): number {
    return Math.round(basePriceCents * (1 - this.discount) * quantity);
  }
}

export class GroupDiscountPricing implements PricingStrategy {
  private groupThreshold = 5;
  private discountRate = 0.15; // 15% off for groups of 5+

  calculate(basePriceCents: number, quantity: number): number {
    const subtotal = basePriceCents * quantity;
    if (quantity >= this.groupThreshold) {
      return Math.round(subtotal * (1 - this.discountRate));
    }
    return subtotal;
  }
}
```

```typescript
// src/services/pricing-registry.ts

import { PricingStrategy, FlatPricing, VipPricing, EarlyBirdPricing, GroupDiscountPricing } from './pricing-strategy';

export class PricingRegistry {
  private strategies = new Map<string, PricingStrategy>();

  constructor() {
    // Register default strategies
    this.register('general', new FlatPricing());
    this.register('vip', new VipPricing());
    this.register('early_bird', new EarlyBirdPricing());
    this.register('group_discount', new GroupDiscountPricing());
  }

  register(ticketType: string, strategy: PricingStrategy): void {
    this.strategies.set(ticketType, strategy);
  }

  getStrategy(ticketType: string): PricingStrategy {
    const strategy = this.strategies.get(ticketType);
    if (!strategy) {
      throw new Error(`No pricing strategy for ticket type: ${ticketType}`);
    }
    return strategy;
  }
}
```

Update OrderService:

```typescript
// In OrderService.createOrder(), replace the pricing block:

// BEFORE:
// const priceInCents = this.calculatePrice(event.basePriceCents, ticketType);
// const totalInCents = Math.round(priceInCents * quantity);

// AFTER:
const strategy = this.pricingRegistry.getStrategy(ticketType);
const totalInCents = strategy.calculate(event.basePriceCents, quantity);
```

Now adding a "student" ticket type means creating a `StudentPricing` class and registering it. Zero changes to `OrderService`. Zero changes to existing strategies. The system is open for extension, closed for modification.

**Try It:**

```bash
npx jest --passWithNoTests
git add -A && git commit -m "refactor: replace pricing if/else with Strategy pattern (OCP)"
```

> **Reflect:** Notice we did not apply Strategy from the start. The if/else was fine for two ticket types. By the third, the pattern earns its keep. This is YAGNI in action -- wait for the signal before abstracting.

---

## 3. Liskov Substitution Principle (LSP)

> "Subtypes must be substitutable for their base types without altering the correctness of the program."
> -- Barbara Liskov

### Spot the Violation

Create this file to see the problem:

```typescript
// src/repositories/ticket.repository.ts

export interface TicketRepository {
  findById(id: string): Promise<Ticket | null>;
  findByEvent(eventId: string): Promise<Ticket[]>;
  save(ticket: Ticket): Promise<void>;
  delete(id: string): Promise<void>;
}

// Used by the reporting dashboard -- it should never write data
export class ReadOnlyTicketRepository implements TicketRepository {
  constructor(private pool: Pool) {}

  async findById(id: string): Promise<Ticket | null> {
    const result = await this.pool.query('SELECT * FROM tickets WHERE id = $1', [id]);
    return result.rows[0] ?? null;
  }

  async findByEvent(eventId: string): Promise<Ticket[]> {
    const result = await this.pool.query('SELECT * FROM tickets WHERE event_id = $1', [eventId]);
    return result.rows;
  }

  async save(ticket: Ticket): Promise<void> {
    throw new Error('Cannot save: repository is read-only');
  }

  async delete(id: string): Promise<void> {
    throw new Error('Cannot delete: repository is read-only');
  }
}
```

Any function that accepts a `TicketRepository` and calls `save()` will blow up at runtime when handed a `ReadOnlyTicketRepository`. The type system says it is safe. The runtime says otherwise. This is an LSP violation.

### Refactor: Separate Interfaces

```typescript
// src/interfaces/ticket-repository.interfaces.ts

export interface Ticket {
  id: string;
  eventId: string;
  orderId: string;
  seat: string | null;
  status: string;
}

// Read operations
export interface TicketReader {
  findById(id: string): Promise<Ticket | null>;
  findByEvent(eventId: string): Promise<Ticket[]>;
}

// Write operations
export interface TicketWriter {
  save(ticket: Ticket): Promise<void>;
  delete(id: string): Promise<void>;
}

// Full repository for services that need both
export interface TicketRepository extends TicketReader, TicketWriter {}
```

```typescript
// src/repositories/postgres-ticket.repository.ts

import { Ticket, TicketRepository } from '../interfaces/ticket-repository.interfaces';
import { Pool } from 'pg';

export class PostgresTicketRepository implements TicketRepository {
  constructor(private pool: Pool) {}

  async findById(id: string): Promise<Ticket | null> {
    const result = await this.pool.query('SELECT * FROM tickets WHERE id = $1', [id]);
    return result.rows[0] ?? null;
  }

  async findByEvent(eventId: string): Promise<Ticket[]> {
    const result = await this.pool.query(
      'SELECT * FROM tickets WHERE event_id = $1', [eventId]
    );
    return result.rows;
  }

  async save(ticket: Ticket): Promise<void> {
    await this.pool.query(
      `INSERT INTO tickets (id, event_id, order_id, seat, status)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (id) DO UPDATE SET status = $5`,
      [ticket.id, ticket.eventId, ticket.orderId, ticket.seat, ticket.status]
    );
  }

  async delete(id: string): Promise<void> {
    await this.pool.query('DELETE FROM tickets WHERE id = $1', [id]);
  }
}
```

```typescript
// src/repositories/readonly-ticket.repository.ts

import { Ticket, TicketReader } from '../interfaces/ticket-repository.interfaces';
import { Pool } from 'pg';

// Only implements TicketReader -- no save() or delete() to break
export class ReadOnlyTicketRepository implements TicketReader {
  constructor(private pool: Pool) {}

  async findById(id: string): Promise<Ticket | null> {
    const result = await this.pool.query('SELECT * FROM tickets WHERE id = $1', [id]);
    return result.rows[0] ?? null;
  }

  async findByEvent(eventId: string): Promise<Ticket[]> {
    const result = await this.pool.query(
      'SELECT * FROM tickets WHERE event_id = $1', [eventId]
    );
    return result.rows;
  }
}
```

Now functions declare what they actually need:

```typescript
// The reporting service only reads -- it asks for TicketReader
class ReportingService {
  constructor(private tickets: TicketReader) {}

  async getEventAttendance(eventId: string): Promise<number> {
    const tickets = await this.tickets.findByEvent(eventId);
    return tickets.filter(t => t.status === 'active').length;
  }
}

// The order service needs to write -- it asks for TicketRepository
class TicketIssuer {
  constructor(private tickets: TicketRepository) {}

  async issueTicket(orderId: string, eventId: string, seat: string | null): Promise<Ticket> {
    const ticket: Ticket = {
      id: crypto.randomUUID(),
      eventId,
      orderId,
      seat,
      status: 'active',
    };
    await this.tickets.save(ticket);
    return ticket;
  }
}
```

No runtime surprises. The type system enforces what operations are available.

```bash
git add -A && git commit -m "refactor: split TicketRepository into Reader/Writer interfaces (LSP)"
```

---

## 4. Interface Segregation Principle (ISP)

> "No client should be forced to depend on methods it does not use."
> -- Robert C. Martin

### Spot the Violation

Look back at the original `OrderService`. It has methods for:
- Creating orders (`createOrder`)
- Reading orders (`getOrder`, `getOrdersByUser`)
- Cancelling orders (`cancelOrder`)
- Generating reports (`generateSalesReport`)
- Bulk operations (`bulkRefund`)

A controller that only needs to display a user's order history depends on `bulkRefund` and `generateSalesReport`. If those methods change, the controller must be retested. This is a fat interface.

### Refactor: Split Interfaces

```typescript
// src/interfaces/order.interfaces.ts

export interface Order {
  id: string;
  eventId: string;
  userId: string;
  ticketType: string;
  quantity: number;
  totalInCents: number;
  status: string;
  createdAt: Date;
}

// Read operations -- for controllers, dashboards
export interface OrderReader {
  findById(id: string): Promise<Order | null>;
  findByUser(userId: string): Promise<Order[]>;
}

// Write operations -- for the purchase flow
export interface OrderWriter {
  create(data: Omit<Order, 'id' | 'createdAt'>): Promise<Order>;
  updateStatus(id: string, status: string, paymentId?: string): Promise<void>;
}

// Reporting -- for the analytics dashboard
export interface OrderReporter {
  getSalesReport(eventId: string): Promise<{ total: number; count: number }>;
}

// Admin operations -- for the back office
export interface OrderAdmin {
  cancelOrder(id: string): Promise<void>;
  bulkRefund(orderIds: string[]): Promise<void>;
}
```

Each consumer depends only on what it needs:

```typescript
// src/controllers/order-history.controller.ts
// Only needs OrderReader -- does not depend on refund, reporting, or creation

export class OrderHistoryController {
  constructor(private orders: OrderReader) {}

  async getUserOrders(req: Request, res: Response): Promise<void> {
    const userId = req.params.userId;
    const orders = await this.orders.findByUser(userId);
    res.json({ orders });
  }
}
```

```typescript
// src/controllers/admin.controller.ts
// Only needs OrderAdmin and OrderReporter

export class AdminController {
  constructor(
    private admin: OrderAdmin,
    private reporter: OrderReporter
  ) {}

  async refundOrders(req: Request, res: Response): Promise<void> {
    await this.admin.bulkRefund(req.body.orderIds);
    res.json({ success: true });
  }

  async salesReport(req: Request, res: Response): Promise<void> {
    const report = await this.reporter.getSalesReport(req.params.eventId);
    res.json(report);
  }
}
```

The concrete repository implements all interfaces:

```typescript
// src/repositories/postgres-order.repository.ts

export class PostgresOrderRepository
  implements OrderReader, OrderWriter, OrderReporter, OrderAdmin {

  constructor(private pool: Pool) {}

  async findById(id: string): Promise<Order | null> {
    const result = await this.pool.query('SELECT * FROM orders WHERE id = $1', [id]);
    return result.rows[0] ?? null;
  }

  async findByUser(userId: string): Promise<Order[]> {
    const result = await this.pool.query(
      'SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC', [userId]
    );
    return result.rows;
  }

  async create(data: Omit<Order, 'id' | 'createdAt'>): Promise<Order> {
    const result = await this.pool.query(
      `INSERT INTO orders (event_id, user_id, ticket_type, quantity, total_in_cents, status)
       VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
      [data.eventId, data.userId, data.ticketType, data.quantity, data.totalInCents, data.status]
    );
    return result.rows[0];
  }

  async updateStatus(id: string, status: string, paymentId?: string): Promise<void> {
    if (paymentId) {
      await this.pool.query(
        'UPDATE orders SET status = $1, payment_id = $2 WHERE id = $3',
        [status, paymentId, id]
      );
    } else {
      await this.pool.query('UPDATE orders SET status = $1 WHERE id = $2', [status, id]);
    }
  }

  async getSalesReport(eventId: string): Promise<{ total: number; count: number }> {
    const result = await this.pool.query(
      'SELECT COALESCE(SUM(total_in_cents), 0) as total, COUNT(*) as count FROM orders WHERE event_id = $1',
      [eventId]
    );
    return { total: Number(result.rows[0].total), count: Number(result.rows[0].count) };
  }

  async cancelOrder(id: string): Promise<void> {
    await this.pool.query("UPDATE orders SET status = 'cancelled' WHERE id = $1", [id]);
  }

  async bulkRefund(orderIds: string[]): Promise<void> {
    await this.pool.query(
      "UPDATE orders SET status = 'refunded' WHERE id = ANY($1)",
      [orderIds]
    );
  }
}
```

```bash
git add -A && git commit -m "refactor: split fat OrderService interface into focused contracts (ISP)"
```

---

## 5. Dependency Inversion Principle (DIP)

> "High-level modules should not depend on low-level modules. Both should depend on abstractions."
> -- Robert C. Martin

### Spot the Violation

Look at the original OrderService:

```typescript
import { Pool } from 'pg';
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
```

`OrderService` directly creates and uses a Postgres connection pool. It is welded to PostgreSQL. Testing requires a real database. You cannot swap in an in-memory store for fast tests.

### Refactor: Inject Abstractions

We already created the interfaces (`OrderReader`, `OrderWriter`, etc.) in the ISP refactoring. Now we wire them up through constructor injection:

```typescript
// src/services/order.service.ts (final version)

import { OrderWriter, OrderReader, Order } from '../interfaces/order.interfaces';
import { PaymentService } from './payment.service';
import { EmailService } from './email.service';
import { AnalyticsService } from './analytics.service';
import { PricingRegistry } from './pricing-registry';

export interface EventRepository {
  findById(id: string): Promise<{ id: string; name: string; basePriceCents: number } | null>;
}

export interface UserRepository {
  findById(id: string): Promise<{ id: string; email: string } | null>;
}

export class OrderService {
  constructor(
    private orderWriter: OrderWriter,
    private eventRepo: EventRepository,
    private userRepo: UserRepository,
    private paymentService: PaymentService,
    private emailService: EmailService,
    private analyticsService: AnalyticsService,
    private pricingRegistry: PricingRegistry
  ) {}

  async createOrder(
    userId: string,
    eventId: string,
    ticketType: string,
    quantity: number
  ): Promise<Order> {
    const event = await this.eventRepo.findById(eventId);
    if (!event) throw new Error('Event not found');

    const strategy = this.pricingRegistry.getStrategy(ticketType);
    const totalInCents = strategy.calculate(event.basePriceCents, quantity);

    const order = await this.orderWriter.create({
      eventId, userId, ticketType, quantity, totalInCents, status: 'pending',
    });

    const paymentId = await this.paymentService.charge(totalInCents, { orderId: order.id });
    await this.orderWriter.updateStatus(order.id, 'confirmed', paymentId);

    const user = await this.userRepo.findById(userId);
    if (user) {
      await this.emailService.sendOrderConfirmation(
        user.email, event.name, ticketType, quantity, totalInCents
      );
    }

    this.analyticsService.trackOrderCreated({
      orderId: order.id, eventId, ticketType, quantity, totalInCents,
    });

    return { ...order, status: 'confirmed' };
  }
}
```

Now write a test with in-memory fakes -- no database, no Stripe, no SMTP server:

```typescript
// src/services/order.service.unit.test.ts

import { OrderService, EventRepository, UserRepository } from './order.service';
import { OrderWriter, Order } from '../interfaces/order.interfaces';
import { PaymentService } from './payment.service';
import { EmailService } from './email.service';
import { AnalyticsService } from './analytics.service';
import { PricingRegistry } from './pricing-registry';

// In-memory fakes
class FakeOrderWriter implements OrderWriter {
  orders: Order[] = [];

  async create(data: Omit<Order, 'id' | 'createdAt'>): Promise<Order> {
    const order: Order = {
      ...data,
      id: `order-${this.orders.length + 1}`,
      createdAt: new Date(),
    };
    this.orders.push(order);
    return order;
  }

  async updateStatus(id: string, status: string): Promise<void> {
    const order = this.orders.find(o => o.id === id);
    if (order) order.status = status;
  }
}

class FakePaymentService implements PaymentService {
  charges: { amount: number; metadata: Record<string, string> }[] = [];

  async charge(amount: number, metadata: Record<string, string>): Promise<string> {
    this.charges.push({ amount, metadata });
    return `pay_${this.charges.length}`;
  }
}

class FakeEmailService implements EmailService {
  sent: { to: string; eventName: string }[] = [];

  async sendOrderConfirmation(
    to: string, eventName: string, ticketType: string, quantity: number, total: number
  ): Promise<void> {
    this.sent.push({ to, eventName });
  }
}

class FakeAnalyticsService implements AnalyticsService {
  tracked: any[] = [];

  trackOrderCreated(data: any): void {
    this.tracked.push(data);
  }
}

describe('OrderService', () => {
  let orderService: OrderService;
  let fakeOrders: FakeOrderWriter;
  let fakePayments: FakePaymentService;
  let fakeEmails: FakeEmailService;
  let fakeAnalytics: FakeAnalyticsService;

  const fakeEventRepo: EventRepository = {
    findById: async (id: string) => ({
      id, name: 'Summer Concert', basePriceCents: 10000,
    }),
  };

  const fakeUserRepo: UserRepository = {
    findById: async (id: string) => ({
      id, email: 'test@example.com',
    }),
  };

  beforeEach(() => {
    fakeOrders = new FakeOrderWriter();
    fakePayments = new FakePaymentService();
    fakeEmails = new FakeEmailService();
    fakeAnalytics = new FakeAnalyticsService();

    orderService = new OrderService(
      fakeOrders,
      fakeEventRepo,
      fakeUserRepo,
      fakePayments,
      fakeEmails,
      fakeAnalytics,
      new PricingRegistry()
    );
  });

  it('creates an order, charges payment, sends email, and tracks analytics', async () => {
    const order = await orderService.createOrder('user-1', 'event-1', 'general', 2);

    // Order was created
    expect(order.status).toBe('confirmed');
    expect(fakeOrders.orders).toHaveLength(1);

    // Payment was charged
    expect(fakePayments.charges).toHaveLength(1);
    expect(fakePayments.charges[0].amount).toBe(20000); // 2 * $100

    // Email was sent
    expect(fakeEmails.sent).toHaveLength(1);
    expect(fakeEmails.sent[0].to).toBe('test@example.com');

    // Analytics was tracked
    expect(fakeAnalytics.tracked).toHaveLength(1);
    expect(fakeAnalytics.tracked[0].quantity).toBe(2);
  });

  it('uses VIP pricing for VIP tickets', async () => {
    await orderService.createOrder('user-1', 'event-1', 'vip', 1);

    expect(fakePayments.charges[0].amount).toBe(25000); // $100 * 2.5
  });

  it('throws when event is not found', async () => {
    const emptyEventRepo: EventRepository = {
      findById: async () => null,
    };

    const service = new OrderService(
      fakeOrders, emptyEventRepo, fakeUserRepo,
      fakePayments, fakeEmails, fakeAnalytics, new PricingRegistry()
    );

    await expect(service.createOrder('user-1', 'nope', 'general', 1))
      .rejects.toThrow('Event not found');
  });
});
```

Run the tests:

```bash
npx jest src/services/order.service.unit.test.ts
```

These tests run in milliseconds. No database. No network. No environment variables. That is the power of Dependency Inversion.

```bash
git add -A && git commit -m "refactor: inject dependencies into OrderService, add unit tests (DIP)"
```

---

## 6. The Full Picture

Here is what we started with versus where we ended:

**Before (1 file, ~100 lines, untestable):**
```
OrderService
├── creates Pool directly
├── creates Stripe directly
├── creates nodemailer directly
├── calculates prices with if/else
├── sends emails inline
├── tracks analytics inline
├── has fat interface (read + write + report + admin)
└── ReadOnlyTicketRepository throws on save()
```

**After (10+ files, each focused, fully testable):**
```
OrderService (orchestrator only)
├── depends on OrderWriter interface
├── depends on EventRepository interface
├── depends on UserRepository interface
├── depends on PaymentService interface
├── depends on EmailService interface
├── depends on AnalyticsService interface
└── depends on PricingRegistry (strategies)

PricingStrategy interface
├── FlatPricing
├── VipPricing
├── EarlyBirdPricing
└── GroupDiscountPricing (added without modifying anything)

TicketReader / TicketWriter (separate interfaces)
├── PostgresTicketRepository (implements both)
└── ReadOnlyTicketRepository (implements TicketReader only)

OrderReader / OrderWriter / OrderReporter / OrderAdmin
└── PostgresOrderRepository (implements all four)
```

---

## 7. Reflect

> **Which SOLID principle gave you the most "aha" moment? Which one seems like overkill for TicketPulse's current size?**

Be honest. For a small project with one developer, some of this is overhead. SRP and DIP almost always pay off because they enable testing. OCP pays off when you see the third variation. ISP and LSP are more about preventing future bugs in larger teams.

> **Common Mistake:** Applying SOLID to everything. A 10-line utility function does not need dependency injection. A script with two if/else branches does not need Strategy pattern. Principles are tools, not commandments. Use them when the complexity warrants it.

---

## Checklist

Before moving on, confirm:

- [ ] You can explain each SOLID principle in one sentence
- [ ] OrderService delegates to focused services (SRP)
- [ ] New ticket types can be added without modifying existing code (OCP)
- [ ] ReadOnlyTicketRepository does not implement methods it cannot fulfill (LSP)
- [ ] Controllers depend only on the interfaces they need (ISP)
- [ ] OrderService can be tested with in-memory fakes (DIP)
- [ ] All five refactorings are separate commits
- [ ] Tests pass after each commit

---

## What's Next

In L1-M16b, we will review TicketPulse code that is technically correct but hard to read -- bad names, long functions, swallowed errors, and wrong abstractions. Clean code is not about SOLID; it is about the humans who read your code next.

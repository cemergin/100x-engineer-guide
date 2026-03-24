<!--
  CHAPTER: 32
  TITLE: Software Engineering Principles & Design Patterns
  PART: I — Foundations
  PREREQS: None
  KEY_TOPICS: SOLID, DRY, KISS, YAGNI, coupling, cohesion, design patterns, clean code, code smells, composition vs inheritance, Law of Demeter, package principles, functional vs OOP, refactoring, modularity
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 32: Software Engineering Principles & Design Patterns

> **Part I — Foundations** | Prerequisites: None | Difficulty: Beginner → Advanced

The principles that turn "code that works" into "code that lasts." This chapter covers the timeless ideas — from SOLID to design patterns to clean code — with real backend examples, not textbook abstractions.

### In This Chapter
- Why Principles Matter
- SOLID Principles (With Real Code)
- Core Design Principles (DRY, KISS, YAGNI, and friends)
- Coupling & Cohesion
- Design Patterns That Actually Matter
- Clean Code Essentials
- Code Smells & Anti-Patterns
- Composition vs Inheritance
- Functional vs OOP in Backend Engineering
- Package & Module Design Principles
- Essential Reading

### Related Chapters
- Ch 3 (architecture patterns apply these at system level)
- Ch 6 (concurrency paradigms — FP/OOP)
- Ch 8 (testing, refactoring, code quality)
- Ch 15 (codebase organization at scale)
- Ch 28 (code reading)

---

## 1. Why Principles Matter

Principles are **heuristics, not laws**. They have trade-offs, contexts where they shine, and contexts where they actively hurt. The engineer who applies SOLID to every 50-line script is as dangerous as the one who has never heard of it.

### The Goal: Manage Complexity

Software does not die from a lack of features. It dies from complexity. Every system starts simple — a single file, a handful of functions, a clear purpose. Then requirements accumulate. The codebase grows. Shortcuts compound. One day, nobody wants to touch the code anymore. That is the moment the system starts dying.

Fred Brooks drew the critical distinction in his 1986 paper **"No Silver Bullet: Essence and Accident in Software Engineering"**:

- **Essential complexity** is inherent to the problem. A tax calculation system is complex because tax law is complex. You cannot remove this complexity — you can only model it faithfully.
- **Accidental complexity** is introduced by your tools, abstractions, and decisions. A tax calculation system that requires restarting three microservices to test a rule change has accidental complexity. This is the complexity you can fight.

Principles are weapons against accidental complexity. They do not simplify the problem — they simplify *your solution* to the problem.

### The Cost of Change Curve

In the 1980s, Barry Boehm showed that the cost of fixing a bug grows exponentially as it moves from design to production. While modern practices (CI/CD, automated testing, fast deploys) have flattened that curve, the core truth remains: **code that is easy to understand is easy to change, and code that is easy to change is cheap to maintain.**

Principles reduce the cost of future changes by making the codebase:
- **Readable**: new developers can understand intent without archaeology
- **Modular**: changing one feature does not ripple across ten files
- **Testable**: you can verify behavior in isolation
- **Flexible**: new requirements fit into the existing structure without surgery

### "Make It Work, Make It Right, Make It Fast"

Kent Beck's three-step mantra captures the role of principles perfectly:

1. **Make it work** — get the feature passing tests, delivering value. Ugly code is fine here.
2. **Make it right** — refactor toward clarity and good structure. This is where principles live.
3. **Make it fast** — optimize only what profiling proves is slow.

Most teams skip step 2. They ship "make it work" code, promise to come back, and never do. Principles are not about writing perfect code on the first pass — they are about knowing what "right" looks like so you can steer toward it during refactoring.

---

## 2. SOLID Principles (With Real Code)

SOLID was formalized by Robert C. Martin in **"Agile Software Development: Principles, Patterns, and Practices"** (2002), though the individual principles were developed over the preceding decade. The acronym was coined by Michael Feathers.

These five principles target the design of classes, modules, and interfaces. They are most valuable in codebases that are large enough to have real dependency structures — applying them to a weekend project is usually overkill.

### S — Single Responsibility Principle (SRP)

> "A module should be responsible to one, and only one, actor."
> — Robert C. Martin (the refined definition, from "Clean Architecture", 2017)

The common paraphrase is "a class should have only one reason to change," but the deeper meaning is about *who* requests changes. If the accounting department and the operations department both need changes to the same class, that class has two responsibilities.

**Violation:**

```typescript
// This class serves three different actors:
// - User onboarding team (registration logic)
// - Marketing team (welcome emails)
// - Finance team (trial billing)
class UserService {
  async registerUser(email: string, password: string): Promise<User> {
    // Validate input
    if (!email.includes("@")) throw new Error("Invalid email");
    const hashedPassword = await bcrypt.hash(password, 10);

    // Save to database
    const user = await db.query(
      "INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *",
      [email, hashedPassword]
    );

    // Send welcome email
    await sendgrid.send({
      to: email,
      subject: "Welcome!",
      html: renderWelcomeTemplate(user),
    });

    // Create trial subscription
    const subscription = await stripe.subscriptions.create({
      customer: await stripe.customers.create({ email }).then((c) => c.id),
      items: [{ price: "price_trial_monthly" }],
      trial_period_days: 14,
    });

    await db.query("UPDATE users SET subscription_id = $1 WHERE id = $2", [
      subscription.id,
      user.id,
    ]);

    return user;
  }
}
```

**Refactored:**

```typescript
// Each class is responsible to a single actor

class UserRepository {
  async create(email: string, hashedPassword: string): Promise<User> {
    return db.query(
      "INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *",
      [email, hashedPassword]
    );
  }

  async setSubscription(userId: string, subscriptionId: string): Promise<void> {
    await db.query("UPDATE users SET subscription_id = $1 WHERE id = $2", [
      subscriptionId,
      userId,
    ]);
  }
}

class WelcomeEmailSender {
  async send(user: User): Promise<void> {
    await sendgrid.send({
      to: user.email,
      subject: "Welcome!",
      html: renderWelcomeTemplate(user),
    });
  }
}

class TrialSubscriptionService {
  async createTrial(email: string): Promise<Subscription> {
    const customer = await stripe.customers.create({ email });
    return stripe.subscriptions.create({
      customer: customer.id,
      items: [{ price: "price_trial_monthly" }],
      trial_period_days: 14,
    });
  }
}

class UserRegistrationService {
  constructor(
    private userRepo: UserRepository,
    private emailSender: WelcomeEmailSender,
    private subscriptionService: TrialSubscriptionService
  ) {}

  async register(email: string, password: string): Promise<User> {
    if (!email.includes("@")) throw new Error("Invalid email");
    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await this.userRepo.create(email, hashedPassword);
    const subscription = await this.subscriptionService.createTrial(email);
    await this.userRepo.setSubscription(user.id, subscription.id);
    await this.emailSender.send(user);

    return user;
  }
}
```

**When it is overkill:** A small script or single-purpose CLI tool. If the module genuinely has one actor and one reason to exist, splitting it further just adds indirection. SRP is most valuable when you feel the pull of multiple stakeholders changing the same file for different reasons.

---

### O — Open/Closed Principle (OCP)

> "Software entities should be open for extension, but closed for modification."
> — Bertrand Meyer, "Object-Oriented Software Construction" (1988)

You should be able to add new behavior without changing existing, tested code. The Strategy pattern is the classic mechanism.

**Violation:**

```typescript
class PaymentProcessor {
  async processPayment(order: Order, method: string): Promise<PaymentResult> {
    if (method === "stripe") {
      return stripe.charges.create({
        amount: order.totalCents,
        currency: "usd",
        source: order.paymentToken,
      });
    } else if (method === "paypal") {
      return paypal.execute(order.paymentToken, { amount: order.totalCents });
    } else if (method === "bank_transfer") {
      // Added 6 months later — required modifying this file
      return bankApi.initTransfer({
        amount: order.totalCents,
        reference: order.id,
      });
    }
    throw new Error(`Unknown payment method: ${method}`);
  }
}
```

Every new payment provider requires modifying `processPayment`. If this function has 200 lines, you risk breaking Stripe when you add Klarna.

**Refactored:**

```typescript
interface PaymentGateway {
  charge(amount: number, token: string): Promise<PaymentResult>;
}

class StripeGateway implements PaymentGateway {
  async charge(amount: number, token: string): Promise<PaymentResult> {
    return stripe.charges.create({ amount, currency: "usd", source: token });
  }
}

class PayPalGateway implements PaymentGateway {
  async charge(amount: number, token: string): Promise<PaymentResult> {
    return paypal.execute(token, { amount });
  }
}

// Adding a new provider = adding a new class. No existing code changes.
class BankTransferGateway implements PaymentGateway {
  async charge(amount: number, reference: string): Promise<PaymentResult> {
    return bankApi.initTransfer({ amount, reference });
  }
}

class PaymentProcessor {
  constructor(private gateways: Map<string, PaymentGateway>) {}

  async processPayment(order: Order, method: string): Promise<PaymentResult> {
    const gateway = this.gateways.get(method);
    if (!gateway) throw new Error(`Unknown payment method: ${method}`);
    return gateway.charge(order.totalCents, order.paymentToken);
  }
}
```

**When it is overkill:** When you have exactly two cases and no signal that a third is coming. An `if/else` for two branches is clearer than a Strategy + Factory + Registry. Apply OCP when you see the second or third variation — not preemptively. That is what YAGNI is for.

---

### L — Liskov Substitution Principle (LSP)

> "Subtypes must be substitutable for their base types without altering the correctness of the program."
> — Barbara Liskov & Jeannette Wing, "A Behavioral Notion of Subtyping" (1994)

If code works with a base type, it must also work with any subtype. Violations usually surface as runtime exceptions in code that "should work" based on the type signature.

**Violation:**

```typescript
class UserRepository {
  async find(id: string): Promise<User | null> { /* ... */ }
  async save(user: User): Promise<void> { /* ... */ }
  async delete(id: string): Promise<void> { /* ... */ }
}

class ReadOnlyUserRepository extends UserRepository {
  async save(user: User): Promise<void> {
    throw new Error("Cannot save: repository is read-only");
  }

  async delete(id: string): Promise<void> {
    throw new Error("Cannot delete: repository is read-only");
  }
}
```

Any function that accepts a `UserRepository` and calls `save()` will blow up at runtime when given a `ReadOnlyUserRepository`. The subtype is not substitutable.

**Refactored:**

```typescript
interface ReadableRepository<T> {
  find(id: string): Promise<T | null>;
}

interface WritableRepository<T> extends ReadableRepository<T> {
  save(entity: T): Promise<void>;
  delete(id: string): Promise<void>;
}

class UserRepository implements WritableRepository<User> {
  async find(id: string): Promise<User | null> { /* ... */ }
  async save(user: User): Promise<void> { /* ... */ }
  async delete(id: string): Promise<void> { /* ... */ }
}

class ReadOnlyUserRepository implements ReadableRepository<User> {
  async find(id: string): Promise<User | null> { /* ... */ }
  // No save or delete — the interface does not require them
}
```

Now functions declare what they actually need. A reporting function takes `ReadableRepository<User>`. A registration function takes `WritableRepository<User>`. No surprises.

**Design by Contract** (Bertrand Meyer): a subtype may *weaken* preconditions and *strengthen* postconditions, but never the reverse. If the base type accepts any string, the subtype cannot reject empty strings. If the base type promises a non-null return, the subtype cannot return null.

---

### I — Interface Segregation Principle (ISP)

> "No client should be forced to depend on methods it does not use."
> — Robert C. Martin

Fat interfaces force implementors to provide methods they do not need, and force consumers to depend on methods they never call.

**Violation:**

```typescript
interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  findByCustomer(customerId: string): Promise<Order[]>;
  save(order: Order): Promise<void>;
  delete(id: string): Promise<void>;
  bulkInsert(orders: Order[]): Promise<void>;
  generateMonthlyReport(month: Date): Promise<Report>;
  archiveOlderThan(date: Date): Promise<number>;
}
```

A simple order lookup handler now depends on `generateMonthlyReport` and `archiveOlderThan`. The reporting module depends on `bulkInsert`. Everything depends on everything.

**Refactored:**

```typescript
interface OrderReader {
  findById(id: string): Promise<Order | null>;
  findByCustomer(customerId: string): Promise<Order[]>;
}

interface OrderWriter {
  save(order: Order): Promise<void>;
  delete(id: string): Promise<void>;
}

interface OrderBulkOperations {
  bulkInsert(orders: Order[]): Promise<void>;
  archiveOlderThan(date: Date): Promise<number>;
}

interface OrderReporting {
  generateMonthlyReport(month: Date): Promise<Report>;
}

// The concrete implementation can implement all of them
class PostgresOrderRepository
  implements OrderReader, OrderWriter, OrderBulkOperations, OrderReporting {
  // ...
}

// But consumers only depend on what they need
class OrderLookupHandler {
  constructor(private orders: OrderReader) {}
}
```

This is idiomatic in Go, where interfaces are typically 1-3 methods (`io.Reader` is a single `Read` method). In TypeScript, keep interfaces focused. In Python, use Protocols (PEP 544) for the same effect.

---

### D — Dependency Inversion Principle (DIP)

> "High-level modules should not depend on low-level modules. Both should depend on abstractions."
> — Robert C. Martin

This is the foundation of hexagonal architecture, clean architecture, and every testable backend system (see Ch 3).

**Violation:**

```typescript
import { Pool } from "pg";

class OrderService {
  private db = new Pool({ connectionString: process.env.DATABASE_URL });

  async getOrder(id: string): Promise<Order> {
    const result = await this.db.query("SELECT * FROM orders WHERE id = $1", [id]);
    return this.mapToOrder(result.rows[0]);
  }
}
```

`OrderService` is welded to PostgreSQL. Testing requires a real database. Switching to MySQL means rewriting the service.

**Refactored:**

```typescript
// The abstraction — owned by the domain layer
interface OrderRepository {
  findById(id: string): Promise<Order | null>;
  save(order: Order): Promise<void>;
}

// High-level module depends on the abstraction
class OrderService {
  constructor(private orderRepo: OrderRepository) {}

  async getOrder(id: string): Promise<Order> {
    const order = await this.orderRepo.findById(id);
    if (!order) throw new NotFoundError(`Order ${id} not found`);
    return order;
  }
}

// Low-level module implements the abstraction
class PostgresOrderRepository implements OrderRepository {
  constructor(private db: Pool) {}

  async findById(id: string): Promise<Order | null> {
    const result = await this.db.query("SELECT * FROM orders WHERE id = $1", [id]);
    return result.rows[0] ? this.mapToOrder(result.rows[0]) : null;
  }

  async save(order: Order): Promise<void> { /* ... */ }
}

// In tests: swap in a fake
class InMemoryOrderRepository implements OrderRepository {
  private orders = new Map<string, Order>();

  async findById(id: string): Promise<Order | null> {
    return this.orders.get(id) ?? null;
  }

  async save(order: Order): Promise<void> {
    this.orders.set(order.id, order);
  }
}
```

**Dependency injection** is the mechanism that delivers DIP. Constructor injection — passing dependencies through the constructor — is the simplest and most explicit approach. Avoid service locators (hidden global lookups) and property injection (dependencies can be undefined between construction and injection).

---

## 3. Core Design Principles

### DRY (Don't Repeat Yourself)

> "Every piece of knowledge must have a single, unambiguous, authoritative representation within a system."
> — Andrew Hunt & David Thomas, **"The Pragmatic Programmer"** (1999)

DRY is about **knowledge duplication**, not **code duplication**. This is the most commonly misunderstood principle in software engineering.

Two functions can have identical code and *not* be a DRY violation — if they represent different domain concepts that happen to have the same implementation today but will diverge tomorrow.

```typescript
// These look identical but serve different business rules.
// They are NOT a DRY violation.

function calculateShippingTax(amount: number): number {
  return amount * 0.08;
}

function calculateServiceTax(amount: number): number {
  return amount * 0.08;  // Same rate today, but governed by different tax codes
}
```

Extracting these into a shared `calculateTax()` creates **coupling**. When shipping tax changes to 0.10, you risk breaking service tax.

> "A little copying is better than a little dependency."
> — Go proverb

**The Rule of Three:** Duplicating once is acceptable. Duplicating twice is a signal. The third time you see the same knowledge in the same form, extract it. By the third occurrence, you have enough evidence that it represents a real, stable abstraction.

The danger of premature abstraction is a shared function or class that accumulates parameters, flags, and special cases to handle all its callers — eventually becoming harder to understand than the original duplication. Sandi Metz calls this **"the wrong abstraction"**: it is cheaper to duplicate than to maintain a bad abstraction.

---

### KISS (Keep It Simple, Stupid)

Simple is not the same as easy. Simple means **fewer moving parts, less indirection, clearer intent**. Easy means "I already know how to do it this way." Sometimes the easy path (copy-paste, global variables, one giant function) creates a complex system. Sometimes the simple solution (a clean abstraction, a well-chosen data structure) requires upfront effort.

```typescript
// OVER-ENGINEERED for two notification channels:
// NotificationStrategy + NotificationFactory + NotificationRegistry
// + NotificationContext + AbstractNotificationProvider

// KISS for two channels:
async function notifyUser(userId: string, message: string, channel: "email" | "sms") {
  const user = await userRepo.findById(userId);
  if (!user) throw new NotFoundError(`User ${userId} not found`);

  if (channel === "email") {
    await emailClient.send({ to: user.email, body: message });
  } else {
    await smsClient.send({ to: user.phone, body: message });
  }
}
```

If a third or fourth channel appears, refactor to a strategy. Not before.

**Complexity budget:** every abstraction layer, every indirection, every configuration option costs comprehension. Before adding one, ask: *Is this abstraction earning its keep? Does the simplification it provides outweigh the comprehension cost it adds?*

---

### YAGNI (You Ain't Gonna Need It)

> "Always implement things when you actually need them, never when you just foresee that you need them."
> — Kent Beck, **Extreme Programming Explained** (1999)

YAGNI attacks speculative generality — building for requirements that do not exist yet.

```typescript
// YAGNI violation: a plugin system for an app with one plugin
class PluginManager {
  private plugins: Map<string, Plugin> = new Map();

  register(name: string, plugin: Plugin): void { /* ... */ }
  unregister(name: string): void { /* ... */ }
  getPlugin<T extends Plugin>(name: string): T { /* ... */ }
  listPlugins(): PluginInfo[] { /* ... */ }
  reloadPlugin(name: string): Promise<void> { /* ... */ }
}

// What you actually need:
const analyticsTracker = new AnalyticsTracker(config);
```

The plugin system took a week to build. The second plugin never materialized. Now every developer must understand the plugin lifecycle to modify analytics tracking.

**The flip side:** some things are genuinely expensive to add later. Security, structured logging, internationalization, and accessibility are easier to build in from the start than to bolt on after the fact. YAGNI is about *features and abstractions*, not about *foundational concerns*. Use judgment.

---

### Principle of Least Astonishment (POLA)

Code should behave the way a reasonable developer would expect given its name and signature.

```typescript
// SURPRISING: getUser modifies the database
async function getUser(id: string): Promise<User> {
  const user = await db.query("SELECT * FROM users WHERE id = $1", [id]);
  // Why is a getter updating last_accessed?
  await db.query("UPDATE users SET last_accessed = NOW() WHERE id = $1", [id]);
  return mapToUser(user.rows[0]);
}

// UNSURPRISING: name communicates the side effect
async function getUserAndRecordAccess(id: string): Promise<User> {
  const user = await db.query("SELECT * FROM users WHERE id = $1", [id]);
  await db.query("UPDATE users SET last_accessed = NOW() WHERE id = $1", [id]);
  return mapToUser(user.rows[0]);
}
```

Know your ecosystem's conventions. In JavaScript, `Array.sort()` mutates in place (surprising to many). In Rust, `.iter()` borrows and `.into_iter()` consumes (unsurprising once you know ownership). Follow the conventions your team's developers expect.

---

### Law of Demeter (Principle of Least Knowledge)

> "Only talk to your immediate friends."

Each unit should only have limited knowledge of other units — specifically, only the units "closely" related to it.

**Violation (the "train wreck"):**

```typescript
function getShippingLabel(order: Order): string {
  // Reaches through three objects — tightly coupled to the entire object graph
  const city = order.getCustomer().getAddress().getCity();
  const zip = order.getCustomer().getAddress().getZipCode();
  return `${city}, ${zip}`;
}
```

If the `Address` structure changes, this function breaks — even though it has nothing to do with addresses.

**Refactored:**

```typescript
// Order exposes what callers need, hiding its internal structure
class Order {
  getShippingCity(): string {
    return this.customer.address.city;
  }

  getShippingZip(): string {
    return this.customer.address.zipCode;
  }
}

function getShippingLabel(order: Order): string {
  return `${order.getShippingCity()}, ${order.getShippingZip()}`;
}
```

**Trade-off:** strict Law of Demeter can create an explosion of small forwarding methods. Apply it at module/service boundaries where coupling is costly. Inside a tightly cohesive module, reaching into collaborators is often acceptable.

---

### Fail Fast

Detect and report errors as early as possible. Do not let bad data travel through the system, only to cause a cryptic failure three layers deeper.

```typescript
// BAD: silently accepts invalid input, fails mysteriously later
async function createOrder(input: any): Promise<Order> {
  const order = new Order();
  order.customerId = input.customerId;  // could be undefined
  order.items = input.items;            // could be null
  // ... 50 lines later, deep in the billing module:
  // TypeError: Cannot read property 'price' of undefined
}

// GOOD: validate at the boundary, fail immediately with context
async function createOrder(input: CreateOrderInput): Promise<Order> {
  if (!input.customerId) {
    throw new ValidationError("customerId is required");
  }
  if (!input.items || input.items.length === 0) {
    throw new ValidationError("Order must contain at least one item");
  }
  for (const item of input.items) {
    if (item.quantity <= 0) {
      throw new ValidationError(
        `Invalid quantity ${item.quantity} for product ${item.productId}`
      );
    }
  }
  // Proceed with confidence that input is valid
}
```

This connects to Yaron Minsky's principle: **"Make illegal states unrepresentable."** Use your type system to prevent bad data from existing in the first place. An `OrderStatus` enum is better than a `status: string` that could be anything.

---

### Separation of Concerns

Each module addresses a distinct concern. A concern is a set of information that affects the code.

**Horizontal separation** (layers):

```
Controller  →  handles HTTP, request parsing, response formatting
Service     →  business logic, orchestration, domain rules
Repository  →  data access, persistence, query construction
```

**Vertical separation** (features):

```
users/       →  everything related to user management
orders/      →  everything related to order processing
payments/    →  everything related to payment handling
```

The best architectures combine both: vertical slices (features) with horizontal layers within each slice. This is the foundation of every architecture pattern discussed in Ch 3.

---

### Encapsulation

Hide internal state and implementation details. Expose behavior through a well-defined interface.

```typescript
// BAD: callers manipulate internal state directly
class ShoppingCart {
  public items: CartItem[] = [];
  public discount: number = 0;
}

// Callers do this:
cart.items.push(newItem);
cart.discount = cart.items.length > 5 ? 0.1 : 0;
// The discount logic is scattered across every caller

// GOOD: cart enforces its own rules
class ShoppingCart {
  private items: CartItem[] = [];
  private discount: number = 0;

  addItem(item: CartItem): void {
    this.items.push(item);
    this.recalculateDiscount();
  }

  removeItem(itemId: string): void {
    this.items = this.items.filter((i) => i.id !== itemId);
    this.recalculateDiscount();
  }

  getTotal(): number {
    const subtotal = this.items.reduce((sum, i) => sum + i.price * i.quantity, 0);
    return subtotal * (1 - this.discount);
  }

  private recalculateDiscount(): void {
    this.discount = this.items.length > 5 ? 0.1 : 0;
  }
}
```

The principle is **"Tell, don't ask"**: tell an object to do something, rather than asking for its internals and doing it yourself. Encapsulation is not just an OOP concept — it applies to modules, services, and APIs. A microservice that exposes its database schema to callers has broken encapsulation at the system level.

---

## 4. Coupling & Cohesion

These are the two most fundamental metrics of module design. Good design **minimizes coupling** (dependencies between modules) and **maximizes cohesion** (relatedness within a module).

### Coupling (Minimize)

Coupling types, from worst to best:

| Type | Description | Example |
|------|-------------|---------|
| **Content coupling** | One module reaches into another's internals | Directly accessing another service's database tables |
| **Common coupling** | Modules share global mutable state | Two services writing to the same Redis key without coordination |
| **Control coupling** | One module controls another's flow via flags | `processOrder(order, skipValidation: true)` — the caller controls internal logic |
| **Stamp coupling** | Modules share a data structure but only use parts of it | Passing a full `User` object when only `userId` is needed |
| **Data coupling** | Modules share only necessary data through parameters | `calculateTax(amount, taxRate)` — minimal, explicit dependencies |

Move toward data coupling wherever possible. At service boundaries, this means well-defined API contracts with minimal payloads.

### Cohesion (Maximize)

Cohesion types, from worst to best:

| Type | Description | Example |
|------|-------------|---------|
| **Coincidental** | Elements are unrelated | A `Utils` class with `formatDate()`, `sendEmail()`, `calculateDistance()` |
| **Logical** | Elements do similar things but are unrelated | A `Validator` class with `validateEmail()`, `validateCreditCard()`, `validateAddress()` |
| **Temporal** | Elements execute at the same time | A `Startup` class that initializes DB, cache, logger, and message queue |
| **Functional** | Every element contributes to a single, well-defined task | An `EmailSender` class whose every method supports sending emails |

When you see a class with low cohesion, it usually has multiple responsibilities (SRP violation). The fix is extraction: split the `Utils` class into `DateFormatter`, `EmailClient`, and `GeoCalculator`.

### Connascence: A More Nuanced Framework

Coupling is a blunt instrument. **Connascence**, developed by Meilir Page-Jones in **"What Every Programmer Should Know About Object-Oriented Design"** (1995) and later popularized by Jim Weirich, provides a finer-grained taxonomy.

Connascence types, from weakest (acceptable) to strongest (dangerous):

| Type | Description | Example |
|------|-------------|---------|
| **Name** | Two components agree on a name | Calling `userRepo.findById()` — both sides agree on the method name |
| **Type** | Two components agree on a type | A function accepts `string` and caller passes `string` |
| **Meaning** | Two components agree on the meaning of a value | `status: 1` means "active" — magic numbers |
| **Position** | Two components agree on the order of parameters | `createUser(name, email, age)` — swap `email` and `age` and it compiles but breaks |
| **Algorithm** | Two components agree on a specific algorithm | Client and server both use the same hash algorithm for tokens |
| **Timing** | Two components agree on *when* things happen | Service A must be called before Service B |
| **Execution** | Two components agree on the *order of execution* | Initialization order dependencies |

**Rule:** Minimize the strength of connascence across module boundaries. Within a module, stronger connascence is acceptable because the code is co-located and co-maintained.

**Practical application:** If you find connascence of meaning (magic numbers) crossing a boundary, refactor to connascence of name (enums, constants). If you find connascence of position (parameter order) in a public API, refactor to named parameters or an options object.

---

## 5. Design Patterns That Actually Matter

The "Gang of Four" book — **"Design Patterns: Elements of Reusable Object-Oriented Software"** by Gamma, Helm, Johnson, and Vlissides (1994) — catalogs 23 patterns. You do not need all 23. Here are the 10 that backend engineers use regularly.

### Creational Patterns

#### Factory Method / Abstract Factory

**What it is:** Create objects without specifying their concrete class. The creation logic is behind an interface.

```typescript
interface CacheClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, ttlSeconds: number): Promise<void>;
}

class RedisCacheClient implements CacheClient {
  constructor(private redis: Redis) {}
  async get(key: string) { return this.redis.get(key); }
  async set(key: string, value: string, ttl: number) { await this.redis.setex(key, ttl, value); }
}

class InMemoryCacheClient implements CacheClient {
  private store = new Map<string, { value: string; expiry: number }>();
  async get(key: string) {
    const entry = this.store.get(key);
    if (!entry || Date.now() > entry.expiry) return null;
    return entry.value;
  }
  async set(key: string, value: string, ttl: number) {
    this.store.set(key, { value, expiry: Date.now() + ttl * 1000 });
  }
}

function createCacheClient(config: AppConfig): CacheClient {
  if (config.environment === "test") {
    return new InMemoryCacheClient();
  }
  return new RedisCacheClient(new Redis(config.redisUrl));
}
```

**When to use:** Multiple implementations that can be swapped (different environments, different providers). **When NOT to use:** When there is only one implementation and no foreseeable need for another.

#### Builder

**What it is:** Construct complex objects step by step, separating construction from representation.

```python
class QueryBuilder:
    def __init__(self, table: str):
        self._table = table
        self._conditions: list[str] = []
        self._params: list[Any] = []
        self._order_by: str | None = None
        self._limit: int | None = None

    def where(self, condition: str, param: Any) -> "QueryBuilder":
        self._conditions.append(condition)
        self._params.append(param)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        self._order_by = f"{column} {direction}"
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit = n
        return self

    def build(self) -> tuple[str, list[Any]]:
        sql = f"SELECT * FROM {self._table}"
        if self._conditions:
            clauses = [f"{c} = ${i+1}" for i, c in enumerate(self._conditions)]
            sql += " WHERE " + " AND ".join(clauses)
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        if self._limit:
            sql += f" LIMIT {self._limit}"
        return sql, self._params


# Usage
query, params = (
    QueryBuilder("orders")
    .where("customer_id", customer_id)
    .where("status", "pending")
    .order_by("created_at", "DESC")
    .limit(10)
    .build()
)
```

**When to use:** Objects with many optional parameters or complex construction sequences. **When NOT to use:** Simple objects that a constructor or literal handles fine.

#### Singleton (Use with Caution)

**What it is:** Ensure a class has only one instance, with a global access point.

```typescript
// The classic singleton — often an anti-pattern
class DatabasePool {
  private static instance: DatabasePool;

  private constructor(private pool: Pool) {}

  static getInstance(): DatabasePool {
    if (!DatabasePool.instance) {
      DatabasePool.instance = new DatabasePool(
        new Pool({ connectionString: process.env.DATABASE_URL })
      );
    }
    return DatabasePool.instance;
  }
}
```

**The problem:** Singletons are global state in disguise. They make testing hard (you cannot swap the instance), hide dependencies (any code can grab the singleton), and create ordering issues (what if `getInstance()` is called before the environment variable is set?).

**Better alternative:** Create the instance once at the composition root and inject it:

```typescript
// main.ts — the composition root
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const orderRepo = new PostgresOrderRepository(pool);
const orderService = new OrderService(orderRepo);
```

Dependency injection gives you a single instance *without* the baggage of global state. Use actual singletons only when the language/framework forces it (some Android components, some game engine systems).

---

### Structural Patterns

#### Adapter

**What it is:** Make an incompatible interface work with your system by wrapping it.

```typescript
// Third-party email API with its own interface
interface SendGridResponse {
  statusCode: number;
  body: { message_id: string };
}

class SendGridClient {
  async sendMail(msg: {
    to: string; from: string; subject: string; html: string;
  }): Promise<SendGridResponse> { /* ... */ }
}

// Your internal interface
interface EmailService {
  send(to: string, subject: string, body: string): Promise<{ id: string }>;
}

// Adapter: wraps SendGrid behind your interface
class SendGridAdapter implements EmailService {
  constructor(
    private client: SendGridClient,
    private fromAddress: string
  ) {}

  async send(to: string, subject: string, body: string): Promise<{ id: string }> {
    const response = await this.client.sendMail({
      to,
      from: this.fromAddress,
      subject,
      html: body,
    });
    return { id: response.body.message_id };
  }
}
```

This is the core of the **Anti-Corruption Layer** (see Ch 3). Your domain code depends on `EmailService`. Third-party SDKs stay behind adapters. When you switch from SendGrid to Postmark, you write a new adapter — nothing else changes.

**When to use:** Integrating third-party services, migrating between implementations. **When NOT to use:** Wrapping your own code — if you control both sides, just fix the interface.

#### Decorator

**What it is:** Add behavior to an object without modifying its code. Decorators wrap the original and add functionality before or after delegating.

```typescript
interface OrderRepository {
  findById(id: string): Promise<Order | null>;
  save(order: Order): Promise<void>;
}

class PostgresOrderRepository implements OrderRepository {
  async findById(id: string): Promise<Order | null> { /* ... */ }
  async save(order: Order): Promise<void> { /* ... */ }
}

// Decorator: adds caching
class CachedOrderRepository implements OrderRepository {
  constructor(
    private inner: OrderRepository,
    private cache: CacheClient
  ) {}

  async findById(id: string): Promise<Order | null> {
    const cached = await this.cache.get(`order:${id}`);
    if (cached) return JSON.parse(cached);

    const order = await this.inner.findById(id);
    if (order) {
      await this.cache.set(`order:${id}`, JSON.stringify(order), 300);
    }
    return order;
  }

  async save(order: Order): Promise<void> {
    await this.inner.save(order);
    await this.cache.set(`order:${order.id}`, JSON.stringify(order), 300);
  }
}

// Decorator: adds logging
class LoggedOrderRepository implements OrderRepository {
  constructor(
    private inner: OrderRepository,
    private logger: Logger
  ) {}

  async findById(id: string): Promise<Order | null> {
    this.logger.info("OrderRepository.findById", { id });
    const result = await this.inner.findById(id);
    this.logger.info("OrderRepository.findById result", { id, found: !!result });
    return result;
  }

  async save(order: Order): Promise<void> {
    this.logger.info("OrderRepository.save", { orderId: order.id });
    await this.inner.save(order);
  }
}

// Compose: Postgres → cached → logged
const orderRepo = new LoggedOrderRepository(
  new CachedOrderRepository(
    new PostgresOrderRepository(pool),
    cacheClient
  ),
  logger
);
```

Middleware chains in Express, Koa, and similar frameworks are decorators. Each middleware wraps the next handler, adding behavior (auth, logging, rate limiting, CORS) without modifying the core handler.

**When to use:** Cross-cutting concerns (caching, logging, retry, auth, metrics). **When NOT to use:** When you need to fundamentally change behavior, not just wrap it.

#### Facade

**What it is:** A simplified interface to a complex subsystem.

```python
class PaymentFacade:
    """Hides the complexity of payment processing behind a single method."""

    def __init__(
        self,
        stripe_client: StripeClient,
        tax_calculator: TaxCalculator,
        fraud_checker: FraudChecker,
        receipt_generator: ReceiptGenerator,
    ):
        self._stripe = stripe_client
        self._tax = tax_calculator
        self._fraud = fraud_checker
        self._receipts = receipt_generator

    async def process_payment(
        self, order: Order, payment_method: str
    ) -> PaymentResult:
        # 1. Check for fraud
        fraud_result = await self._fraud.assess(order, payment_method)
        if fraud_result.is_suspicious:
            return PaymentResult(
                success=False, reason="Payment flagged for review"
            )

        # 2. Calculate tax
        tax = await self._tax.calculate(order.items, order.shipping_address)

        # 3. Charge
        charge = await self._stripe.charge(
            amount=order.subtotal + tax.amount,
            payment_method=payment_method,
        )

        # 4. Generate receipt
        receipt = await self._receipts.generate(order, charge, tax)

        return PaymentResult(
            success=True, charge_id=charge.id, receipt_url=receipt.url
        )
```

**When to use:** When a subsystem is complex and most callers need a simplified workflow. **When NOT to use:** When callers genuinely need fine-grained control — do not hide necessary complexity.

---

### Behavioral Patterns

#### Strategy

**What it is:** Define a family of algorithms and make them interchangeable.

```typescript
interface PricingStrategy {
  calculate(basePrice: number, quantity: number): number;
}

class FlatPricing implements PricingStrategy {
  calculate(basePrice: number, quantity: number): number {
    return basePrice * quantity;
  }
}

class TieredPricing implements PricingStrategy {
  constructor(private tiers: { upTo: number; pricePerUnit: number }[]) {}

  calculate(basePrice: number, quantity: number): number {
    let total = 0;
    let remaining = quantity;

    for (const tier of this.tiers) {
      const unitsInTier = Math.min(remaining, tier.upTo);
      total += unitsInTier * tier.pricePerUnit;
      remaining -= unitsInTier;
      if (remaining <= 0) break;
    }
    return total;
  }
}

class VolumePricing implements PricingStrategy {
  constructor(private discountThreshold: number, private discountRate: number) {}

  calculate(basePrice: number, quantity: number): number {
    const subtotal = basePrice * quantity;
    if (quantity >= this.discountThreshold) {
      return subtotal * (1 - this.discountRate);
    }
    return subtotal;
  }
}

// Usage
class InvoiceGenerator {
  constructor(private pricing: PricingStrategy) {}

  generateLineItem(product: Product, quantity: number): LineItem {
    return {
      product,
      quantity,
      total: this.pricing.calculate(product.basePrice, quantity),
    };
  }
}
```

**When to use:** Multiple algorithms for the same task, chosen at runtime. **When NOT to use:** Two branches — use an `if/else`.

#### Observer / Event Emitter

**What it is:** When something happens, notify all interested parties without the source knowing who they are.

```typescript
// Domain event
interface DomainEvent {
  type: string;
  timestamp: Date;
  payload: unknown;
}

interface OrderPlacedEvent extends DomainEvent {
  type: "OrderPlaced";
  payload: { orderId: string; customerId: string; total: number };
}

// Event bus
class EventBus {
  private handlers = new Map<string, Array<(event: DomainEvent) => Promise<void>>>();

  on(eventType: string, handler: (event: DomainEvent) => Promise<void>): void {
    const existing = this.handlers.get(eventType) ?? [];
    existing.push(handler);
    this.handlers.set(eventType, existing);
  }

  async emit(event: DomainEvent): Promise<void> {
    const handlers = this.handlers.get(event.type) ?? [];
    await Promise.allSettled(handlers.map((h) => h(event)));
  }
}

// Registering handlers — each is a separate concern
eventBus.on("OrderPlaced", async (event) => {
  await inventoryService.reserveItems(event.payload.orderId);
});

eventBus.on("OrderPlaced", async (event) => {
  await emailService.sendOrderConfirmation(event.payload.customerId, event.payload.orderId);
});

eventBus.on("OrderPlaced", async (event) => {
  await analyticsService.trackPurchase(event.payload);
});
```

The `OrderService` emits `OrderPlaced` and has no idea who is listening. Adding a new reaction (send a Slack notification) requires zero changes to the order code.

**When to use:** Decoupling event producers from consumers, especially across domain boundaries. **When NOT to use:** When there is only one handler and the indirection harms readability — just call the function directly.

#### Repository

**What it is:** Abstract data access behind a collection-like interface oriented around the domain.

```python
from abc import ABC, abstractmethod

class UserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str) -> None: ...


class PostgresUserRepository(UserRepository):
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def find_by_id(self, user_id: str) -> User | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        return User.from_row(row) if row else None

    async def find_by_email(self, email: str) -> User | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM users WHERE email = $1", email
        )
        return User.from_row(row) if row else None

    async def save(self, user: User) -> None:
        await self._pool.execute(
            """INSERT INTO users (id, email, name, created_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (id) DO UPDATE
               SET email = $2, name = $3""",
            user.id, user.email, user.name, user.created_at,
        )

    async def delete(self, user_id: str) -> None:
        await self._pool.execute("DELETE FROM users WHERE id = $1", user_id)
```

**When to use:** Any application with non-trivial data access. Repositories make persistence swappable and testable. **When NOT to use:** Trivial scripts where direct SQL is clearer.

#### Command / CQRS

**What it is:** Encapsulate a request as an object. Separate reads (queries) from writes (commands).

```typescript
// Command: a pure data object describing intent
interface CreateOrderCommand {
  customerId: string;
  items: Array<{ productId: string; quantity: number }>;
  shippingAddress: Address;
}

// Command handler: processes the command
class CreateOrderHandler {
  constructor(
    private orderRepo: OrderRepository,
    private inventoryService: InventoryService,
    private eventBus: EventBus
  ) {}

  async execute(command: CreateOrderCommand): Promise<string> {
    // Validate inventory
    for (const item of command.items) {
      const available = await this.inventoryService.check(item.productId, item.quantity);
      if (!available) {
        throw new InsufficientInventoryError(item.productId);
      }
    }

    // Create order
    const order = Order.create(command.customerId, command.items, command.shippingAddress);
    await this.orderRepo.save(order);

    // Emit event
    await this.eventBus.emit({
      type: "OrderPlaced",
      timestamp: new Date(),
      payload: { orderId: order.id, customerId: command.customerId, total: order.total },
    });

    return order.id;
  }
}
```

Commands make intent explicit, enable audit logging (store every command), and form the foundation of CQRS and event sourcing (see Ch 3).

**When to use:** Complex domain operations, audit requirements, systems that benefit from separating read and write models. **When NOT to use:** Simple CRUD — the overhead of command objects and handlers is not justified.

---

### Anti-Patterns to Recognize

| Anti-Pattern | Description | Remedy |
|-------------|-------------|--------|
| **God Object** | One class that does everything (the 3000-line `UserService`) | Extract classes by responsibility (SRP) |
| **Anemic Domain Model** | Domain objects are data bags with no behavior; all logic lives in services | Move behavior into domain objects |
| **Service Locator** | Hidden global dependency lookup (`ServiceLocator.get(UserRepo)`) | Use explicit constructor injection |
| **Cargo Cult Programming** | Using patterns because "that's how it's done" without understanding why | Understand the problem before choosing a pattern |
| **Golden Hammer** | Using your favorite pattern/tool for everything | Match the solution to the problem |
| **Premature Optimization** | Optimizing before profiling shows a bottleneck | "We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil." — Donald Knuth (1974) |

---

## 6. Clean Code Essentials

Reference: **"Clean Code"** by Robert C. Martin (2008). The book is controversial — some examples are dated, and the Java-centric style does not translate directly to every language. But the *principles* are widely applicable. Take what works, adapt the rest.

### Naming

Names are the most important documentation. A good name eliminates the need for a comment.

```typescript
// BAD
const d = new Date();  // what is d?
const list = getList(); // list of what?
function proc(r: any) { /* ... */ }  // proc what? what is r?

// GOOD
const orderCreatedAt = new Date();
const activeSubscriptions = getActiveSubscriptions();
function processRefundRequest(request: RefundRequest) { /* ... */ }
```

**Rules of thumb:**
- **Variables/properties**: nouns that describe the data (`activeUsers`, `retryCount`, `shippingAddress`)
- **Functions/methods**: verbs that describe the action (`createOrder`, `validateEmail`, `sendNotification`)
- **Booleans**: prefix with `is`, `has`, `can`, `should` (`isActive`, `hasPermission`, `canRetry`)
- **Classes/types**: nouns that describe the concept (`UserRepository`, `PaymentService`, `OrderStatus`)
- **Constants**: `SCREAMING_SNAKE_CASE` for true compile-time constants (`MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_MS`)
- **Avoid abbreviations** unless universally understood: `url`, `id`, `config` are fine. `usr`, `mgr`, `proc`, `txn` are not — they save keystrokes and cost comprehension.

### Functions

```typescript
// BAD: does multiple things, long, unclear purpose
async function handleOrder(data: any, sendEmail: boolean, applyDiscount: boolean) {
  // ... 80 lines of validation, transformation, persistence, emailing, discounting
}

// GOOD: each function does one thing
async function validateOrderInput(input: CreateOrderInput): ValidatedOrder {
  // 10 lines of validation
}

async function applyOrderDiscount(order: Order, discountCode: string): Order {
  // 8 lines of discount logic
}

async function persistOrder(order: Order): void {
  // 5 lines of database interaction
}

async function sendOrderConfirmation(order: Order): void {
  // 6 lines of email composition and sending
}
```

**Guidelines:**
- **Do one thing** (SRP at the function level)
- **Keep them short** — aim for under 20 lines. If it is longer, look for extraction opportunities.
- **Minimize parameters** — 0-2 is ideal, 3 is the practical maximum. Beyond that, introduce an options/config object:
  ```typescript
  // BAD: 6 positional parameters
  createUser(name, email, password, role, department, sendWelcome);

  // GOOD: options object
  createUser({ name, email, password, role, department, sendWelcomeEmail: true });
  ```
- **No hidden side effects** — a function called `validate()` should not save to the database. A function called `getUser()` should not increment a counter.
- **Command-Query Separation** (Bertrand Meyer): a function either *does something* (command) or *returns something* (query), not both. `stack.pop()` violates this by both removing an element and returning it — a well-known design compromise.

### Error Handling

```typescript
// TERRIBLE: swallow the error
try {
  await processPayment(order);
} catch (e) {
  // TODO: handle this later
}

// BAD: generic error with no context
try {
  await processPayment(order);
} catch (e) {
  throw new Error("Something went wrong");
}

// GOOD: specific error type with full context
try {
  await processPayment(order);
} catch (e) {
  throw new PaymentProcessingError(
    `Failed to process payment for order ${order.id} ` +
    `(customer: ${order.customerId}, amount: ${order.totalCents}): ${e.message}`,
    { cause: e, orderId: order.id, customerId: order.customerId }
  );
}
```

**Guidelines:**
- Never write `catch(e) {}`. If you cannot handle the error, let it propagate.
- Use specific exception types, not generic `Error`.
- Include context: *what* was being done, *with what data*, and *why* it failed.
- Prefer exceptions or `Result` types over error codes. Error codes are easy to ignore; exceptions are impossible to ignore (unless you catch and swallow them — see above).
- Validate at the boundary, fail fast with descriptive messages.

### Comments

```typescript
// BAD: explains WHAT (the code already says this)
// Check if user is active
if (user.isActive) {

// BAD: commented-out code — delete it, git remembers
// const oldDiscount = calculateLegacyDiscount(order);
// const result = applyOldPricing(order, oldDiscount);

// BAD: TODO without ownership
// TODO: fix this

// GOOD: explains WHY
// We cap retries at 3 because the payment provider rate-limits after
// 5 attempts per minute and we leave headroom for other services.
const MAX_PAYMENT_RETRIES = 3;

// GOOD: documents a non-obvious algorithm choice
// Insertion sort for small arrays: faster than quicksort below ~16 elements
// due to lower overhead. See: Musser's introsort paper (1997).
if (items.length < 16) {
  insertionSort(items);
}

// GOOD: public API documentation
/**
 * Creates a new subscription for the given customer.
 *
 * @param customerId - Must be an existing, verified customer
 * @param plan - The pricing plan to subscribe to
 * @returns The created subscription with a 14-day trial
 * @throws {CustomerNotFoundError} If the customer does not exist
 * @throws {PlanNotAvailableError} If the plan is discontinued
 */
async function createSubscription(
  customerId: string,
  plan: PricingPlan
): Promise<Subscription> { /* ... */ }
```

The best comment is the one you did not have to write because the code was clear enough. If you feel the need to add a comment, first ask: *Can I rename the variable, extract a function, or restructure the code to make this obvious?* If yes, do that instead. If the comment explains *why* (business context, performance rationale, non-obvious constraint), keep it.

---

## 7. Code Smells & Anti-Patterns

Reference: **"Refactoring: Improving the Design of Existing Code"** by Martin Fowler (2nd edition, 2018). The catalog of code smells and their corresponding refactoring patterns is one of the most practical tools in a developer's arsenal.

| Smell | Description | Backend Example | Refactoring |
|-------|-------------|-----------------|-------------|
| **Long Method** | >20 lines doing multiple things | A 200-line `processOrder()` that validates, calculates pricing, saves, and sends emails | **Extract Method** — pull each concern into a named function |
| **Large Class** | Too many responsibilities | `UserService` handling auth, profile updates, billing, and notifications | **Extract Class** — one class per responsibility |
| **Feature Envy** | A method uses another object's data more than its own | `billingService.calculate(order.items, order.address, order.currency, order.discount)` | **Move Method** — move `calculate` onto `Order` or create a dedicated calculator |
| **Data Clumps** | The same group of parameters always appears together | `(userId, userName, userEmail)` repeated across 10 function signatures | **Introduce Parameter Object** — create a `UserInfo` value object |
| **Primitive Obsession** | Using strings/numbers instead of domain types | `status: string` instead of `OrderStatus` enum; `email: string` instead of `EmailAddress` value object | **Replace Primitive with Value Object** |
| **Shotgun Surgery** | One logical change requires editing many files | Adding a new `OrderStatus` requires changes in controller, service, repository, serializer, validator, and tests | **Consolidate** — group related logic so changes are local |
| **Divergent Change** | One class changes for many unrelated reasons | `OrderProcessor` changes when tax rules change AND when shipping rules change AND when inventory rules change | **Extract Class** — one class per axis of change |
| **Refused Bequest** | A subclass doesn't use or want inherited behavior | `ReadOnlyRepository extends Repository` and throws on `save()` | **Replace Inheritance with Composition** or **Extract Interface** |
| **Speculative Generality** | Infrastructure built for hypothetical future needs | A `PluginManager` with hot-reload, dependency resolution, and lifecycle hooks for a system with one plugin | **Remove** — delete it and add back when actually needed (YAGNI) |
| **Dead Code** | Unreachable or unused code paths | Feature flag handling for a flag removed two years ago; an entire module that nothing imports | **Delete it** — dead code is noise that wastes every reader's time |
| **Middle Man** | A class that only delegates to another class | `OrderFacade.save(order)` calls `orderService.save(order)` which calls `orderRepo.save(order)` — three layers of pure delegation | **Remove Middle Man** — call the actual class directly |
| **Message Chains** | `a.getB().getC().getD().doThing()` | `order.getCustomer().getAddress().getCountry().getTaxRate()` | **Hide Delegate** — `order.getTaxRate()` |

The refactoring process is always: (1) have tests, (2) make a small structural change, (3) run tests, (4) repeat. Never refactor without a safety net.

---

## 8. Composition Over Inheritance

> "Favor object composition over class inheritance."
> — Gang of Four, "Design Patterns" (1994)

Inheritance creates **tight coupling** between parent and child. Changes to the parent ripple through every descendant. Deep hierarchies become rigid — adding behavior to one child without affecting its siblings is difficult.

**The problem with inheritance:**

```typescript
// Deep hierarchy — changes at any level affect everything below
class BaseService {
  protected logger: Logger;
  log(message: string) { this.logger.info(message); }
}

class AuthenticatedService extends BaseService {
  protected currentUser: User;
  assertAuthenticated() { if (!this.currentUser) throw new AuthError(); }
}

class CachedAuthenticatedService extends AuthenticatedService {
  protected cache: CacheClient;
  getCached<T>(key: string): Promise<T | null> { /* ... */ }
}

class UserService extends CachedAuthenticatedService {
  // Inherits logging, auth, caching — but what if I need logging
  // and caching WITHOUT auth? I need a new branch of the hierarchy.
  // This is the "fragile base class" problem.
}
```

**Composition:**

```typescript
class UserService {
  constructor(
    private userRepo: UserRepository,
    private cache: CacheClient,
    private logger: Logger,
    private auth: AuthContext
  ) {}

  async getUser(id: string): Promise<User> {
    this.auth.assertAuthenticated();
    this.logger.info("Fetching user", { id });

    const cached = await this.cache.get(`user:${id}`);
    if (cached) return cached as User;

    const user = await this.userRepo.findById(id);
    if (user) await this.cache.set(`user:${id}`, user, 300);
    return user;
  }
}
```

Each capability (logging, caching, auth) is an independent, injectable component. You can combine them in any configuration. Testing is straightforward — inject mocks for exactly the dependencies you want to control.

Go and Rust have no class inheritance at all. They use composition plus interfaces (Go) or traits (Rust). This is a deliberate design choice, not a limitation.

### When Inheritance IS Appropriate

- **Genuinely stable "is-a" relationships**: An `HttpError` IS an `Error`. This hierarchy is unlikely to change.
- **Framework extension points**: Django views, React components — these are designed for single-level inheritance.
- **Very shallow hierarchies** (one level): A base `Event` class with `OrderEvent` and `PaymentEvent` subclasses is fine.
- **Shared implementation** where the entire contract is stable: abstract base classes in Python (`collections.abc.Mapping`).

The rule of thumb: if you are debating between inheritance and composition, choose composition. Use inheritance only when the relationship is clearly "is-a," the hierarchy is shallow, and the parent's interface is stable.

---

## 9. Functional vs OOP in Backend Engineering

This is not a religious war. Both paradigms have their strengths, and most modern backend systems use both.

### Functional Style

Core ideas: **immutable data**, **pure functions** (no side effects, same input always produces same output), **function composition**.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

@dataclass(frozen=True)  # Immutable
class LineItem:
    product_id: str
    quantity: int
    unit_price: Decimal

@dataclass(frozen=True)
class PricingResult:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal

# Pure functions — no side effects, easy to test
def calculate_subtotal(items: list[LineItem]) -> Decimal:
    return sum(item.unit_price * item.quantity for item in items)

def apply_discount(subtotal: Decimal, discount_rate: Decimal) -> Decimal:
    return subtotal * discount_rate

def calculate_tax(amount: Decimal, tax_rate: Decimal) -> Decimal:
    return amount * tax_rate

def compute_pricing(
    items: list[LineItem],
    discount_rate: Decimal,
    tax_rate: Decimal,
) -> PricingResult:
    subtotal = calculate_subtotal(items)
    discount = apply_discount(subtotal, discount_rate)
    taxable = subtotal - discount
    tax = calculate_tax(taxable, tax_rate)
    return PricingResult(
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=taxable + tax,
    )
```

**Strengths:**
- **Testability**: No setup, no mocks, no state to manage. Input goes in, output comes out.
- **Thread safety**: No shared mutable state means no race conditions.
- **Composability**: Small functions combine into complex pipelines.
- **Reasoning**: You can understand each function in isolation.

**Great for:** Data transformation pipelines, business rule calculations, validation logic, event processing.

### OOP Style

Core ideas: **encapsulated state**, **behavior attached to data**, **identity and lifecycle**.

```typescript
class Order {
  private status: OrderStatus = OrderStatus.DRAFT;
  private items: OrderItem[] = [];
  private paidAt: Date | null = null;

  constructor(
    public readonly id: string,
    public readonly customerId: string,
    public readonly createdAt: Date
  ) {}

  addItem(item: OrderItem): void {
    if (this.status !== OrderStatus.DRAFT) {
      throw new InvalidOperationError(
        `Cannot add items to order ${this.id}: status is ${this.status}`
      );
    }
    this.items.push(item);
  }

  submit(): void {
    if (this.items.length === 0) {
      throw new InvalidOperationError(
        `Cannot submit order ${this.id}: no items`
      );
    }
    if (this.status !== OrderStatus.DRAFT) {
      throw new InvalidOperationError(
        `Cannot submit order ${this.id}: status is ${this.status}`
      );
    }
    this.status = OrderStatus.SUBMITTED;
  }

  markPaid(paidAt: Date): void {
    if (this.status !== OrderStatus.SUBMITTED) {
      throw new InvalidOperationError(
        `Cannot mark order ${this.id} as paid: status is ${this.status}`
      );
    }
    this.paidAt = paidAt;
    this.status = OrderStatus.PAID;
  }

  ship(): void {
    if (this.status !== OrderStatus.PAID) {
      throw new InvalidOperationError(
        `Cannot ship order ${this.id}: not yet paid`
      );
    }
    this.status = OrderStatus.SHIPPED;
  }
}
```

**Strengths:**
- **Invariant enforcement**: The `Order` object guarantees its own consistency. You cannot ship before payment — the state machine is built into the class.
- **Natural modeling**: Entities with identity and lifecycle (users, orders, accounts) map naturally to objects.
- **Encapsulation**: Internal state is hidden; only valid transitions are exposed.

**Great for:** Domain modeling (DDD), state machines, entities with identity, resource management.

### The Pragmatic Middle Ground

Most real backend systems are not purely functional or purely OOP. The most effective approach:

- **Use FP for stateless logic**: calculations, validations, transformations, pipelines. These are the pure core of your system.
- **Use OOP for stateful entities**: domain objects that enforce invariants, services with injected dependencies, objects that manage lifecycle.
- **Use FP at the edges**: Request handlers are often best expressed as pure transformations: `Request → Response`.

> "Objects are not about state — objects are about boundaries."
> — Gary Bernhardt, "Boundaries" (2012)

The key insight: use objects to define boundaries (APIs, modules, services) and use functions for the logic within those boundaries. This gives you the testability of FP and the modularity of OOP.

Most modern languages support both paradigms well: TypeScript, Kotlin, Scala, Python, Rust (which is multi-paradigm but leans functional). Choose the paradigm that matches the nature of each piece of code, not the one you prefer.

---

## 10. Package & Module Design Principles

Robert C. Martin defined six principles for organizing packages (modules, libraries, crates) in **"Agile Software Development: Principles, Patterns, and Practices"** (2002). These principles govern how you group code into deployable/releasable units.

### Cohesion Principles (What Goes Together)

#### REP — Reuse-Release Equivalence Principle
> The unit of reuse is the unit of release.

If you version and release code together, it should be cohesive. A package that contains a date formatter, a payment gateway, and an image resizer is not reusable — consumers must depend on all three even if they need one.

#### CCP — Common Closure Principle
> Classes that change together belong together.

This is SRP for packages. If a regulatory change requires updating `TaxCalculator`, `TaxRules`, and `TaxReport`, they should be in the same package. This minimizes the number of packages that change for a single business reason.

#### CRP — Common Reuse Principle
> Classes that are used together belong together. Don't force users to depend on things they don't need.

This is ISP for packages. If a consumer uses your `HttpClient` but not your `WebSocketClient`, they should not be forced to install (and keep up to date) a package containing both.

**The tension:** CCP says "group things that change together" (potentially larger packages). CRP says "don't force unnecessary dependencies" (potentially smaller packages). The balance depends on the maturity and stability of the code. Early on, favor CCP (change is frequent). For stable, widely-reused code, favor CRP.

### Coupling Principles (How Packages Relate)

#### ADP — Acyclic Dependencies Principle
> The dependency graph must have no cycles.

If package A depends on B, B depends on C, and C depends on A, you have a cycle. Cycles mean you cannot build, test, or release packages independently. Breaking cycles usually involves **dependency inversion**: extract an interface into a new package that both sides depend on.

```
BEFORE (cycle):       A → B → C → A

AFTER (acyclic):      A → B → C
                      A → IShared ← C
```

#### SDP — Stable Dependencies Principle
> Depend in the direction of stability.

A *stable* package has many dependents and few dependencies — it is hard to change because changes would break many consumers. An *unstable* package has few dependents and many dependencies — it is easy to change.

Unstable packages should depend on stable packages, not the other way around. If a stable, widely-used package depends on a volatile feature package, every change to the feature package destabilizes the foundation.

#### SAP — Stable Abstractions Principle
> Stable packages should be abstract. Unstable packages should be concrete.

This follows from SDP. A stable package that is full of concrete implementations is rigid — it is hard to change *and* hard to extend. Stable packages should contain abstractions (interfaces, abstract classes) that concrete packages implement.

**In practice:**
```
// Stable, abstract — depended on by many packages
@company/order-domain        →  interfaces, types, domain events
@company/persistence-api     →  Repository interfaces, query types

// Unstable, concrete — depends on the stable abstractions
@company/order-api           →  HTTP handlers, request validation
@company/order-persistence   →  PostgresOrderRepository implementation
@company/order-notifications →  Email/SMS sending for order events
```

### Practical Application

- **In a monorepo**: shared packages (`libs/`, `packages/`) should be stable and abstract. Feature packages (`features/`, `apps/`) should be unstable and concrete.
- **Dependency direction**: features depend on shared libraries, which depend on abstractions. Never the reverse.
- **Enforce it**: Use tools to validate the dependency graph:
  - **JavaScript/TypeScript**: dependency-cruiser, Nx module boundaries, ESLint import rules
  - **Java/Kotlin**: ArchUnit
  - **Go**: `go vet`, custom analyzers
  - **Python**: import-linter, pydeps
  - **General**: Madge (JS), deptry (Python)

---

## 11. Essential Reading

### The Canon (Must-Read)

- **"A Philosophy of Software Design"** — John Ousterhout (2018). The best modern book on managing complexity. Shorter and more focused than Clean Code. Core thesis: *"Complexity is the root cause of the vast majority of software problems."* Its concept of "deep modules" (simple interfaces hiding complex implementations) is immediately actionable.

- **"Clean Code"** — Robert C. Martin (2008). The naming, function design, and error handling principles remain valuable. Some Java-centric examples are dated and the strict "no functions longer than 5 lines" advice should be taken as aspiration, not dogma. Adapt to your language's idioms.

- **"Refactoring: Improving the Design of Existing Code"** — Martin Fowler (2nd edition, 2018). The definitive catalog of code smells and refactoring patterns. The 2nd edition uses JavaScript, making it accessible to a broader audience. Chapter 3 ("Bad Smells in Code") alone is worth the price.

- **"Design Patterns: Elements of Reusable Object-Oriented Software"** — Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides (1994). The "Gang of Four" book. Read selectively — focus on the 10 patterns in section 5 of this chapter. The opening chapters on design principles are as valuable as the pattern catalog itself.

- **"The Pragmatic Programmer: Your Journey to Mastery"** — David Thomas & Andrew Hunt (20th anniversary edition, 2019). DRY, orthogonality, tracer bullets, the broken window theory, and dozens of other principles. Timeless advice that transcends any particular technology stack.

### Deep Dives

- **"Agile Software Development: Principles, Patterns, and Practices"** — Robert C. Martin (2002). Where SOLID was formally defined and explained. The package principles section (Part IV) is excellent and underappreciated.

- **"Working Effectively with Legacy Code"** — Michael Feathers (2004). How to safely change code that has no tests. Introduces the concept of "seams" — places where you can alter behavior without changing code. Invaluable for anyone inheriting a codebase.

- **"Structure and Interpretation of Computer Programs" (SICP)** — Harold Abelson & Gerald Jay Sussman. The functional programming and abstraction foundation. Dense but transformative. Available free at [mitpress.mit.edu/sites/default/files/sicp/index.html](https://mitpress.mit.edu/sites/default/files/sicp/index.html).

- **"Domain-Driven Design: Tackling Complexity in the Heart of Software"** — Eric Evans (2003). Tactical patterns (entities, value objects, aggregates, repositories) and strategic patterns (bounded contexts, context maps). Dense but essential for complex domains. Read Part I and Part III first.

### Articles & Talks

- **"No Silver Bullet: Essence and Accident in Software Engineering"** — Fred Brooks (1986). The essential vs accidental complexity distinction. A short paper that remains endlessly relevant. Available in "The Mythical Man-Month" anniversary edition.

- **"Simple Made Easy"** — Rich Hickey (Strange Loop, 2011). The most important talk on simplicity in software. Hickey distinguishes "simple" (few interleaved concepts) from "easy" (familiar, nearby). Available on InfoQ and YouTube.

- **"The Wrong Abstraction"** — Sandi Metz (2016, blog post at sandimetz.com). *"Prefer duplication over the wrong abstraction."* A necessary correction to over-applied DRY. Short and actionable.

- **"Boundaries"** — Gary Bernhardt (2012). *"Objects are not about state — objects are about boundaries."* A practical talk on combining FP purity with OOP structure. Available on destroyallsoftware.com.

- **"Out of the Tar Pit"** — Ben Moseley & Peter Marks (2006). A rigorous analysis of complexity, state, and control flow. Argues for functional-relational programming as a way to minimize accidental complexity. Academic but deeply insightful.

---

**Chapter Summary:**

Principles are tools, not commandments. The right question is never "Does this follow SOLID?" but rather "Does this design manage complexity well for the current needs and likely changes?" The best engineers internalize these principles deeply enough to apply them by instinct — and ignore them deliberately when the context calls for it.

Start with the basics: name things well, keep functions small, separate concerns, minimize coupling. Then layer in SOLID, design patterns, and package principles as the codebase grows. The goal is always the same: code that a new team member can read, understand, and change with confidence.

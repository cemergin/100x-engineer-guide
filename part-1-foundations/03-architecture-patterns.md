<!--
  CHAPTER: 3
  TITLE: Software Architecture Patterns
  PART: I — Foundations
  PREREQS: Chapters 1, 2
  KEY_TOPICS: monolith, microservices, hexagonal/clean/vertical slice, DDD, event-driven, CQRS, REST/gRPC/GraphQL, API design, saga pattern
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 3: Software Architecture Patterns

> **Part I — Foundations** | Prerequisites: Chapters 1, 2 | Difficulty: Intermediate to Advanced

The structural blueprints for software systems — from monoliths to microservices, from REST to event-driven, and the domain modeling that ties them together.

### In This Chapter
- Architectural Styles
- Communication Patterns
- API Design Philosophies
- Domain-Driven Design (DDD)
- Event-Driven Patterns
- Monolith-to-Microservices

### Related Chapters
- [Ch 1: System Design Paradigms & Philosophies] — distributed systems theory
- [Ch 2: Data Engineering Paradigms] — data modeling/CQRS
- [Ch 7: Deployment Strategies] — deploying these architectures
- [Ch 13: Cloud Databases] — how it all connects in practice

---

## Why Architecture Patterns Matter (More Than You Think)

Here's a hard truth most engineering courses skip: **architecture decisions made in the first six months of a product's life often outlast the entire original engineering team.** The choices you make about how to structure your code — how components talk to each other, where data lives, how teams own boundaries — echo through every hire you make, every feature you ship, and every incident you page someone at 2am to fix.

Architecture is not about drawing boxes on a whiteboard. It's about making the invisible tangible. Every successful product eventually runs into the same fundamental tensions: speed vs. safety, simplicity vs. flexibility, team autonomy vs. system coherence. Architecture patterns are the accumulated wisdom of engineers who hit those walls before you and figured out — sometimes painfully — which trade-offs were worth making.

This chapter is about giving you the vocabulary, the mental models, and the judgment to make those calls well. Not just "here are the patterns" but "here's when you'd actually want each one, here's what goes wrong when you pick wrong, and here's the real cost no one talks about."

Let's start where everyone starts: with the monolith.

---

## 1. ARCHITECTURAL STYLES

### Monolithic Architecture

Before you roll your eyes at the word "monolith" — stop. Monoliths built Instagram, GitHub, Shopify, and Stack Overflow. Some of the most successful engineering organizations in the world ran monoliths for years and deliberately chose to keep them. The monolith gets a bad rap it doesn't deserve, almost always from people who confused "it got complicated" with "the architecture was wrong."

A monolith is a single deployable unit. All your components — web handlers, business logic, background jobs, data access — live in one process and typically share one database. You run one thing. You deploy one thing. When it crashes, one thing is broken.

**Why this is actually great:** The simplicity dividend is enormous, especially early. You can refactor across the entire codebase in one PR. Your IDE gives you accurate call stacks. Your tests run against the whole thing. When a new engineer joins, there's one repo to clone, one thing to run locally, and one mental model to build. Transaction semantics are trivially correct — when a user places an order and you need to update inventory, create a payment record, and send a confirmation, that's one database transaction. It either works or it doesn't. No distributed coordination required.

**When the monolith starts hurting:** The trouble comes at scale — and scale here means both codebase size and team size. When your monolith reaches 500,000 lines of code, you start noticing that every change feels risky because anything could affect anything. Build times stretch from seconds to minutes. A bug in the notification module can crash the whole checkout flow. Ten teams are all trying to merge to main at the same time, and every deployment requires a "big bang" that someone needs to coordinate.

This is the moment when the monolith tempts you toward microservices. But notice: the problems are mostly organizational, not technical. You're hitting team coordination overhead and code coupling issues — and both of those can be addressed without splitting your deployment units. Which brings us to the modular monolith.

> **The Shopify Lesson:** Shopify ran a monolith for years. By 2016, it had grown to over one million lines of Ruby and 4,500 engineers were touching the same codebase. The response wasn't a rewrite — it was a multi-year investment in modularity. They introduced component boundaries enforced by their own tooling, built a "shopify-module-registry" to track ownership, and enforced that modules could only call each other through declared interfaces. The result: they could ship dozens of deploys per day from the same monolith, with different teams moving at different speeds. They called it the "modular monolith" and it kept them competitive for years without the operational overhead of microservices. The lesson is not "monoliths forever" — they did eventually extract some services. The lesson is that modularity is a software property, not a deployment property.

**The real trade-offs:**

| Dimension | Reality |
|---|---|
| Development velocity | Extremely high early-stage, decreases as coupling grows |
| Deployment simplicity | Single artifact, single rollback, one CI/CD pipeline |
| Scaling | Must scale the whole thing, even if only one part is under load |
| Fault isolation | Zero — a bad memory leak in one module can crash everything |
| Operational complexity | Very low — one service to monitor, one thing to restart |

**When to use it:** Early-stage startups, small teams (under ten engineers), unknown domain where you're still learning what the bounded contexts even are, time-to-market is the top priority. If you're building a V1 and you're not sure what you're building yet, start here. You can always extract later. You cannot easily stuff microservices back into a monolith.

---

### Modular Monolith

This is the pattern Shopify would tell you changed everything for them. It's also the pattern most engineers skip entirely, jumping straight from "monolith is getting messy" to "let's do microservices" — and that leap costs years.

A modular monolith is deployed as a single unit but organized internally into well-defined modules with explicit, enforced boundaries. Think of it as a monolith that practices what microservices preach — clear ownership, isolated data, explicit interfaces — without the operational cost of actually splitting across the network.

Here's the key insight: **most of the pain people associate with monoliths is actually caused by poor modularity, not by being a single deployable unit.** When an engineer can reach into any part of the codebase from anywhere else, you get the coupling problems. When your user module directly calls a SQL query from your billing module's table, you get the scary-to-change mess. The fix isn't to split across the network — it's to actually enforce the boundaries.

**What good modularity looks like:**

Each module owns:
- Its own package/namespace (no reaching in from outside)
- Its own database schema or at least its own tables
- A public interface — exposed types, functions, events — that other modules must use
- Its own tests that can run in isolation

Other modules interact with yours only through that public interface. If the user module needs billing data, it calls `billing.GetSubscriptionStatus(userID)`, not `SELECT * FROM billing_subscriptions WHERE user_id = ?`. This seems like a small distinction but it's enormous: the billing module can change its schema completely without breaking the user module, because the contract is the function signature, not the SQL tables.

**Enforcing the boundaries:** The dangerous thing about modular monoliths is that the boundaries are voluntary unless you enforce them with tooling. In Java, you'd use modules (Java 9+ module system) or ArchUnit to write tests that fail if billing code imports from user internals. In Go, package visibility rules do some of this work. In JavaScript/TypeScript, you'd use ESLint import rules or tools like `dependency-cruiser`. The point is: if the boundaries aren't enforced by something that fails loudly, they will be violated under deadline pressure, and you'll be back to a big ball of mud within two years.

**The path to microservices:** Here's the elegant thing. A well-structured modular monolith is halfway to microservices. When you're genuinely ready to split a module out — because it has wildly different scaling requirements, or a different team wants full ownership — you have everything you need. The interface is already defined. The data is already isolated. You mostly just need to put the network wire in. Teams that skip modular monolith and go straight to microservices often spend years trying to reconstruct these boundaries after the fact.

**Key techniques:**
- Separate modules by package/namespace with no cross-module imports except through public interfaces
- Each module owns its schema (different table prefix, schema, or database)
- Inter-module communication through public interfaces only
- Enforce boundaries with architecture fitness functions (ArchUnit for Java, dependency-cruiser for JS/TS)
- Integration tests between modules; unit tests within modules

---

### Microservices Architecture

Here's the architecture pattern that launched a thousand conference talks — and caused at least as many production outages from teams who adopted it too early.

The idea is seductive: instead of one big application, you build many small ones. Each service owns its data, deploys independently, and communicates over the network. Your payments team can deploy five times a day without coordinating with the catalog team. Your search service can be written in Go while your checkout is in Java. Teams move fast because they own their boundaries. When Netflix's recommendation engine has a bug, it doesn't take down your ability to stream a video. The blast radius of any failure is contained.

Amazon is the canonical success story. Jeff Bezos famously issued his API Mandate around 2002: every team would expose its data and functionality through service interfaces, no exceptions. Teams would communicate only through those interfaces — no direct function calls, no shared memory, no back-doors. And every interface had to be designed as if external developers would use it someday. The memo concluded with a line that became legendary: "Anyone who doesn't do this will be fired."

This was not a technical decision first. It was an organizational decision. Amazon was growing faster than its communication structures could handle. The API Mandate forced each team to think of themselves as a product team, with external customers, rather than a component team embedded in a larger system. When AWS launched in 2006, the primitive they needed was already there: teams that had been building reliable APIs for internal use for four years.

The "two-pizza teams" principle — if you can't feed the team with two pizzas, it's too big — wasn't just about team size; it was about system structure. Small teams own small, coherent services. They deploy on their own schedule. They're accountable for their service's uptime. This is microservices as organizational design as much as technical design.

Netflix's migration tells a different story — one about scaling under crisis rather than proactive design. In 2008, a database corruption event took Netflix's DVD shipping service offline for three days. That event prompted a multi-year migration to AWS and microservices. By 2012, Netflix was running hundreds of microservices on AWS. By 2015, thousands. They built and open-sourced much of the tooling that made this possible: Hystrix (circuit breaking), Ribbon (client-side load balancing), Eureka (service discovery), Zuul (API gateway), Chaos Monkey (deliberately killing instances to build resilience). Their migration was successful not because microservices are easy, but because Netflix invested heavily in the operational infrastructure that makes distributed systems manageable. They also had something most teams lack: full-time engineers whose job was just making the distributed system work reliably.

**But here's what the conference talks don't emphasize enough: microservices are a distributed systems problem.** Every function call that used to be in-process is now a network call. And network calls fail. They're slow. They time out. They return partial results. The thing that made your monolith scary — coupling — is still there in microservices. You've just moved it from compile-time dependencies to runtime dependencies. And runtime dependencies fail in ways that compile-time ones don't.

Consider what happens when you decompose an e-commerce checkout into services. The checkout service calls the inventory service to reserve stock, the pricing service to get the current price, the coupon service to apply discounts, the payment service to charge the card, the order service to create the record, and the notification service to send the confirmation email. In a monolith, that's six function calls. In microservices, it's six network calls. Each one can fail. Each one can be slow. Each one can return stale data. You now need to think about: what happens if inventory succeeds but payment fails? Do you undo the inventory reservation? How? What if the undo call itself fails?

This is not a reason to avoid microservices. It's a reason to understand what you're signing up for.

**The minimum viable microservices setup:**

There's a floor below which microservices become a chaos experiment rather than an architecture pattern. You need at minimum:

- **Centralized logging** — your request now touches 7 services; you need to be able to correlate logs across all of them. ELK stack, Datadog, or similar.
- **Distributed tracing** — when something is slow, you need to see the entire call graph. Without Jaeger, Zipkin, or OpenTelemetry, you're debugging with blindfold on.
- **Health checks** — every service must expose readiness and liveness endpoints. Your orchestration layer (Kubernetes, ECS) needs to know when to restart a failing service.
- **Independent CI/CD per service** — if deploying Service A requires coordinating with Service B, you've already lost the main benefit. Each service needs its own pipeline.
- **Service discovery** — services need to find each other. DNS-based (Kubernetes services), registry-based (Consul), or service mesh (Istio, Linkerd).
- **Clear ownership model** — who is on-call for each service? Who approves its API changes? Microservices without clear ownership create a different kind of mess: the "orphan service" problem, where nobody knows who maintains this thing.

**The anti-pattern to avoid: the Distributed Monolith**

This is the nightmare scenario, and it's more common than you'd think. You split your monolith into services, but the services are still tightly coupled — they share a database, or Service A only works when it can synchronously call Services B, C, and D, or every feature change requires coordinating deployments across five teams. You have all the operational complexity of microservices with none of the independence benefits. Distributed monoliths are worse than the original monolith. They're the worst of both worlds.

The telltale signs: services that can't be deployed independently, shared database tables, synchronous chains where if one service is down everything is down, and "we can only deploy on Tuesdays because everything needs to go at once."

**Real-world scale:**

Netflix operates thousands of microservices. They've built enormous internal tooling — Hystrix for circuit breaking, Eureka for service discovery, Zuul for API gateway — specifically to manage this complexity. They employ reliability engineers whose entire job is making these services play nicely together. If you're a 15-person startup, you don't have this. Microservices might still make sense for you, but you need to be eyes-open about the operational cost.

**When microservices genuinely shine:**

- Multiple teams need to deploy independently and frequently
- Different services have radically different scaling requirements (your video transcoding service needs GPUs; your email notification service needs nothing special)
- Different security or compliance boundaries (payment processing under PCI-DSS vs. general user features)
- The organizational structure genuinely maps to service boundaries (Conway's Law working in your favor)
- You have the operational maturity to run them (container orchestration, observability, on-call culture)

---

### Service-Oriented Architecture (SOA)

Before microservices, there was SOA — and understanding why SOA fell out of favor tells you something important about what microservices got right.

SOA emerged in the 2000s as enterprise software tried to get to reusability and integration at scale. The vision was noble: instead of every team building their own user management, their own authentication, their own data access layer, you'd have shared services that everyone calls. The business processes — get customer data, process payment, fulfill order — would be composed from these shared, reusable services.

The execution, unfortunately, was often terrible. The Enterprise Service Bus (ESB) became the defining failure of SOA. The ESB was a central message broker that sat in the middle of everything and was supposed to handle routing, transformation, orchestration, and protocol bridging. In practice, it became a God Bus — a massive central component that everything depended on, that was incredibly difficult to reason about, and that became the single point of failure and the single team's bottleneck for every integration.

The SOA principle of "smart pipes, dumb endpoints" — put the business logic in the bus, keep the services simple — turned out to be the wrong inversion. You end up with a bus that knows too much, teams that can't deploy without touching the shared bus, and a configuration-heavy system where finding a bug requires understanding flows spread across multiple bus configurations.

Microservices explicitly inverted this: dumb pipes (HTTP, message queues), smart endpoints (the services themselves own their logic). This turned out to be dramatically better for team autonomy and operational simplicity.

SOA still exists in enterprise contexts, particularly where you have legacy systems that need to be integrated without rewriting. The patterns around anti-corruption layers and context mapping from DDD (covered later in this chapter) are directly applicable to SOA integration scenarios. But if you're building something new, you're choosing between monolith, modular monolith, and microservices — SOA as a new architecture choice is mostly a museum piece.

---

### Serverless Architecture

Serverless is one of those paradigm shifts that sounds like marketing fluff until you actually use it, and then you see why people get excited — and where it absolutely falls apart.

The premise: instead of running servers (even virtual ones), you write functions that execute in response to events. AWS Lambda, Google Cloud Functions, Azure Functions. You deploy code, not infrastructure. The platform handles scaling (zero instances when idle, thousands under load), availability, and the underlying servers. You pay only for the compute time you actually use — measured in milliseconds, not hours.

For the right use case, this is genuinely transformative. Imagine an API with highly variable traffic: quiet overnight, spikes during business hours, huge peaks during sales events. With traditional servers or containers, you provision for peak (expensive and wasteful at quiet times) or you build auto-scaling (complex to get right). With serverless, it just scales. The platform figures it out. You go from 0 to 10,000 concurrent invocations in seconds, and you never pay for idle time.

**Where serverless shines:**
- Event-driven processing (images uploaded to S3, trigger processing function)
- Scheduled tasks (cron jobs — Lambda + EventBridge is elegant and cheap)
- API backends with variable traffic and relatively stateless request handling
- Glue code and integrations between services
- Prototypes and experiments where operational overhead should be zero

**Where serverless will hurt you:**

**Cold starts:** When a function hasn't been invoked recently, the platform needs to start a new container to run it. This takes anywhere from 100ms (Go, Python) to several seconds (Java with a heavy framework). For a user-facing API endpoint, that's the difference between "snappy" and "what is wrong with this site." You can mitigate with provisioned concurrency (keeping warm instances), but now you're paying for idle time again — which erodes the cost model.

**Vendor lock-in:** AWS Lambda code isn't trivially portable to Google Cloud Functions. The event source integrations (API Gateway, SQS, DynamoDB Streams) are deeply platform-specific. If AWS changes pricing or deprecates a feature, migrating is painful. You can use frameworks like Serverless Framework or SST to abstract some of this, but the abstraction is never complete.

**Execution time limits:** Lambda functions have a 15-minute maximum runtime. This is fine for most API calls and event processing. It's a hard wall for long-running jobs — video transcoding, large data transformations, machine learning training runs.

**Observability:** When something goes wrong, debugging serverless functions requires good tooling. You need to search through CloudWatch logs (or a third-party aggregation service), stitch together invocations, and figure out what happened without a continuous process you can attach a debugger to. Distributed tracing (X-Ray, OpenTelemetry) is almost mandatory for anything non-trivial.

**Local development:** Running Lambda functions locally is better than it used to be (SAM CLI, LocalStack) but still awkward compared to running a server process. The development loop can be slower, especially for complex integrations.

**The pragmatic take:** Serverless is a fantastic tool for specific jobs. The mistake is treating it as a universal architecture. Many teams would benefit from a hybrid: a main application running on containers for the user-facing core, with serverless functions handling the background processing, scheduled jobs, and event-driven integrations. Use it where it's genuinely the right tool; don't dogmatically apply it everywhere.

---

### Event-Driven Architecture (EDA)

If microservices are about space separation (code in different processes), event-driven architecture is about time separation. Services don't call each other directly — they emit events into a shared channel, and other services react when they're ready.

Imagine your e-commerce platform when a user completes a purchase. In a synchronous, request-response model, the checkout service would directly call: inventory service (update stock), fulfillment service (create pick task), notification service (send email), analytics service (record the sale), loyalty service (award points). That's five synchronous calls, each of which can fail. If the loyalty service is down, does the checkout fail? If notification is slow, does the user wait?

In an event-driven model, checkout does exactly one thing: it emits an `OrderPlaced` event. Then it's done. The inventory service is subscribed to `OrderPlaced` events and reacts. The fulfillment service is subscribed. The notification service is subscribed. Each of them processes the event independently, at their own pace, with their own retry logic. The checkout service doesn't know or care about any of them.

The loose coupling here is profound. You can add a new subscriber — say, a fraud detection service — without touching the checkout service at all. You can take the notification service down for maintenance without affecting order placement. You can replay events from an hour ago if a new service needs to catch up on missed data.

**The trade-offs are real:**

**Eventual consistency:** When an event system processes order placement, inventory might not be updated for 50 milliseconds. During that window, is the stock count accurate? For most systems, this is fine — the window is tiny and rare edge cases are acceptable. For financial systems where double-spending is a concern, this requires careful design.

**Reasoning about flow:** Synchronous code is easy to trace: call A leads to call B leads to call C, and if C fails, B's exception handler runs. In event-driven systems, following what happens when an order is placed means understanding which services subscribe to which events, in what order, with what failure modes. Without distributed tracing and good tooling, this becomes genuinely hard to reason about. Engineers call this "event spaghetti" when it gets out of hand.

**Ordering and idempotency:** Events can arrive out of order (especially under load). Consumers need to be idempotent — processing the same event twice should produce the same result as processing it once. This is not hard to implement, but it's extra work that synchronous systems don't require.

**Debugging failures:** When something goes wrong in a synchronous call stack, you have a clear exception with a stack trace. When something goes wrong in an event-driven system, the event was emitted, the consumer received it, it maybe processed partially, and then... nothing happened. Finding what broke requires good logging, monitoring, and dead-letter queues for events that couldn't be processed.

**When EDA is genuinely the right call:**
- High-throughput systems where services don't need to wait for each other
- Systems with many downstream integrations that shouldn't be coupled to the source
- Systems where auditability matters (events provide a natural log)
- Systems where different parts scale very differently
- Cases where adding new integrations should require zero changes to existing services

---

### Hexagonal Architecture (Ports and Adapters)

Alistair Cockburn introduced hexagonal architecture in 2005, and it's one of those patterns where once you internalize it, you start seeing everything through that lens.

The core problem it solves: most software ends up with business logic entangled with infrastructure concerns. Your domain logic that decides "is this user eligible for a refund?" ends up knowing about HTTP request objects, database connection strings, and email provider SDKs. When you want to test that logic, you need to set up a whole environment. When you want to switch from MySQL to PostgreSQL, you're rewriting business logic. When you want to run the same logic as a cron job instead of an HTTP handler, you can't easily do it.

Hexagonal architecture draws a hard line: the domain (your actual business logic) sits at the center, and it does not depend on anything external. Not HTTP, not databases, not email providers, not clocks. It depends only on abstractions — interfaces — that describe what it needs without specifying how those needs are met.

**Ports** are the interfaces. They come in two flavors:

**Driving ports (inbound):** How the outside world talks to your application. An HTTP handler receives a REST request and calls a port: `OrderService.PlaceOrder(ctx, request)`. A CLI command calls the same port. A test calls the same port. The domain logic doesn't know or care which one is calling it.

**Driven ports (outbound):** How your application talks to the outside world. Your domain logic needs to save an order — it calls `OrderRepository.Save(order)`. It doesn't know if that's PostgreSQL, MongoDB, or an in-memory map. It doesn't care. The adapter wired in at startup determines the actual behavior.

**Adapters** are the implementations that live outside the hexagon. The REST adapter receives HTTP, translates it to domain concepts, and calls the driving port. The PostgreSQL adapter implements the `OrderRepository` interface using actual SQL. The email adapter implements `NotificationService` using SES. The in-memory adapter implements `OrderRepository` using a Go map — perfect for tests.

This unlocks some powerful things:

**Fast tests.** Your domain logic tests use in-memory adapters. No database to set up. No network calls. Tests run in milliseconds. The only slow tests are the ones that explicitly test the actual adapters (your PostgreSQL adapter tests, which hit a real database).

**Easy swapping.** Want to move from Postgres to DynamoDB? Write a new adapter that implements the repository interface. The domain logic doesn't change. The tests don't change (except adapter-specific tests).

**Multiple interfaces to the same logic.** The same business logic can be called via REST, GraphQL, CLI, gRPC, or a background job — each is just a different adapter. You write the logic once.

**The hexagon shape** in the name is somewhat metaphorical — it's just saying "more than one side" (as opposed to a simple layered cake). The point is that the center has no single input or output direction; it can talk to the outside world through many different ports.

**A worked example: Order placement with hexagonal architecture**

Here's how a real order placement flow looks with ports and adapters. The domain layer is completely ignorant of HTTP, databases, or any external system:

```typescript
// === DOMAIN LAYER ===
// Pure business logic. No imports from Express, Postgres, or any framework.

interface OrderRepository {
  save(order: Order): Promise<void>;
  findById(id: OrderId): Promise<Order | null>;
}

interface PaymentGateway {
  charge(amount: Money, paymentMethod: PaymentMethodId): Promise<PaymentResult>;
}

interface OrderEventPublisher {
  publish(event: OrderPlacedEvent): Promise<void>;
}

class PlaceOrderUseCase {
  constructor(
    private orders: OrderRepository,         // driven port
    private payments: PaymentGateway,         // driven port
    private events: OrderEventPublisher       // driven port
  ) {}

  async execute(command: PlaceOrderCommand): Promise<OrderId> {
    const order = Order.create(command.userId, command.items);
    
    const payment = await this.payments.charge(
      order.totalAmount,
      command.paymentMethodId
    );
    
    if (!payment.succeeded) {
      throw new PaymentFailedError(payment.reason);
    }
    
    order.confirmPayment(payment.transactionId);
    await this.orders.save(order);
    await this.events.publish(new OrderPlacedEvent(order));
    
    return order.id;
  }
}

// === ADAPTERS (live outside the hexagon) ===

// Driving adapter: translates HTTP → domain
class PlaceOrderHttpHandler {
  constructor(private useCase: PlaceOrderUseCase) {}

  async handle(req: Request, res: Response) {
    const command = PlaceOrderCommand.fromRequest(req.body);
    const orderId = await this.useCase.execute(command);
    res.status(201).json({ orderId: orderId.value });
  }
}

// Driven adapter: implements OrderRepository using PostgreSQL
class PostgresOrderRepository implements OrderRepository {
  async save(order: Order): Promise<void> {
    await db.query(
      'INSERT INTO orders (id, user_id, status, total_cents) VALUES ($1, $2, $3, $4)',
      [order.id.value, order.userId.value, order.status, order.totalAmount.cents]
    );
  }
  // ...
}

// Driven adapter: in-memory implementation for tests
class InMemoryOrderRepository implements OrderRepository {
  private store = new Map<string, Order>();
  
  async save(order: Order): Promise<void> {
    this.store.set(order.id.value, order);
  }
  
  async findById(id: OrderId): Promise<Order | null> {
    return this.store.get(id.value) ?? null;
  }
}

// === TESTS: no database, no HTTP, no network ===
describe('PlaceOrderUseCase', () => {
  it('charges payment and saves order', async () => {
    const orders = new InMemoryOrderRepository();
    const payments = new MockPaymentGateway({ succeeds: true });
    const events = new InMemoryEventPublisher();
    
    const useCase = new PlaceOrderUseCase(orders, payments, events);
    const orderId = await useCase.execute(validCommand);
    
    expect(orders.findById(orderId)).resolves.toBeDefined();
    expect(events.published).toHaveLength(1);
  });
  
  it('throws when payment fails', async () => {
    const payments = new MockPaymentGateway({ succeeds: false });
    const useCase = new PlaceOrderUseCase(new InMemoryOrderRepository(), payments, new InMemoryEventPublisher());
    
    await expect(useCase.execute(validCommand)).rejects.toThrow(PaymentFailedError);
  });
});
```

Notice what the tests do not require: no running PostgreSQL, no HTTP server, no payment provider credentials. The business logic runs in milliseconds. This is the dividend of the ports and adapters design — when you wire in real infrastructure (Postgres, Stripe, SQS), only the adapter code changes. The use case, the domain objects, and the tests stay exactly the same.

This also means you can plug in the same `PlaceOrderUseCase` into a CLI command, a cron job, or a gRPC handler by writing a new driving adapter — without touching any business logic.

---

### Clean Architecture

Robert C. Martin (Uncle Bob) formalized a version of this in his book Clean Architecture, and it's worth understanding both as its own pattern and as context for why these patterns exist.

Clean Architecture organizes code into concentric rings:

- **Entities** (innermost): The enterprise-wide business rules. User, Order, Product. Pure business logic with no framework dependencies. These change rarely and only when business rules change.
- **Use Cases**: Application-specific business rules. `PlaceOrder`, `ProcessRefund`, `UpdateUserProfile`. These orchestrate entity logic to fulfill specific application goals. They change when what the application does changes.
- **Interface Adapters**: The converters. Takes data from use cases and entities and converts it to formats the outside world expects (HTTP responses, database rows, event messages). Controllers, presenters, gateways live here.
- **Frameworks & Drivers** (outermost): The actual implementation of external things. Express, Django, Spring. PostgreSQL driver. AWS SDK. These are details.

The fundamental rule: **dependencies always point inward.** Entities don't know about use cases. Use cases don't know about controllers. Nothing in the inner rings imports from the outer rings. This is the Dependency Rule.

Why does this matter? Because it means the things that are most likely to change (frameworks, databases, delivery mechanisms) are in the outermost ring, and they don't pollute your business logic. You can upgrade from Express v4 to v5 without touching a single use case. You can switch ORMs without touching an entity.

**Clean vs. Hexagonal:** They're solving the same problem and the vocabulary differs. Hexagonal uses "ports and adapters" and doesn't prescribe a specific number of rings. Clean Architecture has a more specific layering and emphasizes use cases as a distinct layer. In practice, many teams blend the ideas. The important principle — domain logic isolated from infrastructure — is shared by both.

---

### Onion Architecture

Jeffrey Palermo's Onion Architecture (2008) is essentially a variant of Clean Architecture with slightly different layering vocabulary:

- **Domain Model** (center): Pure domain objects. No dependencies.
- **Domain Services**: Domain logic that doesn't belong to a single entity (e.g., a pricing calculation that touches products, coupons, and shipping rules).
- **Application Services**: Orchestrates domain objects and services to fulfill use cases. Similar to Use Cases in Clean Architecture.
- **Infrastructure** (outermost): Database access, external APIs, UI.

The dependency rule is the same: outer layers depend on inner layers, never the reverse.

The practical difference from Clean Architecture is mostly vocabulary and emphasis. If your team is already using "domain services" in their DDD vocabulary, Onion maps more naturally. If your team thinks in use cases, Clean Architecture language fits better. Pick the vocabulary that resonates and apply the principle consistently.

---

### Vertical Slice Architecture

Jimmy Bogard popularized Vertical Slice Architecture as a reaction to a common problem with layered architectures (including Clean and Onion): the layers force you to touch many files across many layers to add a single feature.

In a classic layered architecture, adding "allow users to view their order history" requires:
- A controller method in the presentation layer
- An application service method in the application layer
- Domain entities (maybe nothing new)
- A repository method in the data layer
- Database query implementation
- Possibly a DTO or view model

Each of those files is in a different directory, likely owned by different conventions. Adding the feature means jumping around the codebase. The cohesion is vertical (by feature) but the code organization is horizontal (by layer).

Vertical Slice inverts this: organize by feature, not by layer. Every file related to "view order history" lives in one place — `/features/orders/view-history/`. The handler, the query logic, the data access, any mappers or DTOs — all co-located.

```
/features
  /orders
    /place-order
      PlaceOrderHandler.cs
      PlaceOrderRequest.cs
      PlaceOrderResponse.cs
      PlaceOrderValidator.cs
    /view-order-history
      ViewOrderHistoryHandler.cs
      ViewOrderHistoryQuery.cs
      ViewOrderHistoryResponse.cs
      OrderHistoryRepository.cs
```

**The trade-offs are real but often worth it:**

**High cohesion within features.** Everything for one feature is in one place. When requirements change for "view order history," you change one directory. You don't need to hunt across five layers.

**Potential duplication across features.** If "place order" and "view order" both need to query the orders table, each slice might have its own query logic. This can be fine (queries are often different enough), or you can extract shared infrastructure — but now you have an infrastructure layer anyway, just smaller and more focused.

**Works naturally with CQRS.** Commands (writes) and Queries (reads) are often different enough in their needs that they naturally want to be separate slices. A command needs validation, events, transaction management. A query needs optimized read models and caching. Vertical slices let you optimize each independently.

**When to use it:** Vertical Slice works particularly well in medium-to-large applications with many features that don't heavily share domain logic. CRUD-heavy applications, admin tools, and reporting dashboards are often a good fit. It's less natural for domain-heavy systems where rich entity behavior is shared across many features.

---

## 2. COMMUNICATION PATTERNS

Your services are defined. Now they need to talk to each other. This might seem like a detail — surely you just... make HTTP calls? — but the communication pattern you choose has enormous implications for system behavior, operational complexity, and your ability to reason about failures.

The fundamental question is: does the caller wait for a response, or does it fire-and-forget?

### Choosing Your Communication Protocol: A Practical Framework

Before diving into the protocols, here is the decision logic most senior engineers apply:

```
Is this browser-facing or requires human-readable debugging?
  YES → REST (or GraphQL if client data needs are highly variable)

Is this internal service-to-service with high throughput (>1,000 RPS)?
  YES → gRPC

Do different clients need radically different data shapes (mobile vs. web vs. partner API)?
  YES → GraphQL (or BFF pattern)

Can the caller tolerate latency / doesn't need an immediate response?
  YES → Message queue or event stream (async)

Is this a fan-out scenario (one event, many independent consumers)?
  YES → Pub/Sub (Kafka topic, SNS, Google Pub/Sub)
```

This is not the only lens — team familiarity, existing infrastructure, and contract enforcement requirements all matter. But these are the first questions to ask.

**Real scenario comparisons:**

| Scenario | Recommended | Why |
|---|---|---|
| Mobile app fetching user profile + feed | GraphQL | One round trip, client-defined shape, reduce over-fetching |
| Search service calling inventory service 50,000 times/min | gRPC | Binary serialization, HTTP/2 multiplexing, strong typing |
| Checkout publishing order completion | Kafka event | Fan-out to 6+ consumers, temporal decoupling, replayability |
| Public API for third-party developers | REST | Ubiquitous client libraries, easy to debug, familiar ergonomics |
| Admin dashboard reading aggregated reports | REST or GraphQL | Low frequency, readability matters more than throughput |
| Payment service calling fraud check synchronously | gRPC or REST | Needs synchronous response before proceeding, retry on failure |

### Synchronous Communication

Synchronous communication means the caller waits. It sends a request, the remote service processes it, and the caller gets a response — or it times out waiting. The calling thread (or coroutine) is blocked for the duration.

**REST**

REST (Representational State Transfer) is the universal default for service-to-service communication, and for good reason. It's built on HTTP — a protocol every language has libraries for, every infrastructure component understands, and every engineer has used. It's debuggable with curl. It's explorable in a browser. Caching infrastructure (CDNs, reverse proxies) understands HTTP verbs and status codes natively. The barrier to entry is near-zero.

The downsides are real but manageable. **Over-fetching** happens when you need a user's name and email but the `/users/{id}` endpoint returns a 50-field object — you're transferring data you don't need. **Under-fetching** happens when you need data that requires multiple API calls — get the user, then get their orders, then get each order's items. This N+1 pattern translates directly to N+1 network round trips.

REST also doesn't enforce a contract at the protocol level. One service calls another with an assumed request shape and expected response shape, and if those shapes drift without both teams knowing, you get runtime failures. Tools like OpenAPI/Swagger help, but they're documentation, not enforcement.

**gRPC**

gRPC is what you choose when you need performance and you control both ends of the connection. It uses Protocol Buffers for serialization (binary, compact, efficient) and runs over HTTP/2 (multiplexed streams over a single connection, bidirectional streaming).

The numbers are genuinely striking. Protocol Buffer serialization is roughly 3-10x smaller than equivalent JSON and 5-10x faster to serialize/deserialize. HTTP/2 multiplexing means you don't pay per-connection overhead. For internal services doing high-frequency communication — think a service making 10,000 calls/second to another service — this matters enormously.

The `.proto` file defines your service contract with strong typing. If Service A expects a `CreateOrderRequest` with a required `userId` field and Service B's implementation doesn't provide it, you know at build time, not at runtime. This is a significant reliability improvement over REST.

Here's what a `.proto` definition looks like compared to an equivalent REST design, to make the contract-first benefit concrete:

```protobuf
// order_service.proto
service OrderService {
  rpc PlaceOrder (PlaceOrderRequest) returns (PlaceOrderResponse);
  rpc GetOrder (GetOrderRequest) returns (Order);
  rpc StreamOrderUpdates (GetOrderRequest) returns (stream OrderUpdate);
}

message PlaceOrderRequest {
  string user_id = 1;
  repeated OrderItem items = 2;
  string payment_method_id = 3;
}

message PlaceOrderResponse {
  string order_id = 1;
  OrderStatus status = 2;
}

message OrderItem {
  string product_id = 1;
  int32 quantity = 2;
  // proto3: all fields are optional by default
  // Breaking change: adding required field requires new message type
}
```

This file generates type-safe client and server code in Go, Python, TypeScript, Java, and others simultaneously. The streaming capability (`returns (stream OrderUpdate)`) — which lets the server push updates to the client over a single long-lived connection — is a significant capability that REST cannot replicate without server-sent events or WebSockets. For scenarios like real-time order tracking or live price feeds, gRPC streaming is dramatically simpler than the REST equivalent.

The catch: gRPC is not browser-friendly. Browsers can't make native HTTP/2 requests with binary frames (yet). You need gRPC-Web with a proxy layer for browser clients. The tooling has improved a lot, but it's still more friction than REST for browser-facing APIs. The pragmatic pattern: use gRPC for internal service-to-service communication where you control both sides and performance matters, use REST (or GraphQL) for public-facing and browser-facing APIs.

**GraphQL**

GraphQL solves the over-fetching and under-fetching problems directly: the client specifies exactly what data it needs, and that's all it gets. One endpoint. No versioning. The client drives the query.

```graphql
query {
  user(id: "123") {
    name
    email
    recentOrders(limit: 5) {
      id
      total
      status
    }
  }
}
```

This single query fetches exactly the user fields you need plus their recent orders in one round trip. No separate calls. No over-fetching. The mobile app can request a minimal payload; the desktop app can request a richer one — both through the same API.

But GraphQL introduces its own complexity. The N+1 problem is actually worse by default: when your resolver for `recentOrders` fetches each order independently, a query for 100 users triggers 100 separate database queries for orders. The solution — DataLoader (batching and caching) — is well-understood but requires explicit implementation. Schema design requires more upfront thought than REST. Query complexity can be unpredictable (a malicious or poorly-written client can issue an enormously expensive query). You need query depth limiting, rate limiting by complexity, and persisted queries to protect yourself.

For teams building mobile apps or complex SPAs where clients have diverse data needs, GraphQL is genuinely powerful. For teams with simpler, more uniform data access patterns, REST is usually enough.

**REST vs gRPC vs GraphQL: When to use which**

| Dimension | REST | gRPC | GraphQL |
|---|---|---|---|
| Primary use case | Public APIs, browser-facing | Internal high-throughput RPC | Client-defined data fetching |
| Protocol | HTTP/1.1 or 2, JSON | HTTP/2, Protocol Buffers (binary) | HTTP/1.1 or 2, JSON |
| Contract | Optional (OpenAPI) | Mandatory (.proto files) | Mandatory (schema) |
| Browser support | Native | Requires proxy (gRPC-Web) | Native |
| Streaming | SSE / WebSocket (bolt-on) | Native bidirectional streaming | Subscriptions (WebSocket) |
| Schema evolution | Manual discipline | Backward-compatible field rules | Additive by convention |
| Performance | Moderate (text serialization) | High (binary, multiplexed) | Moderate (single round trip) |
| Debugging | Excellent (curl, browser) | Moderate (need proto tool) | Good (GraphiQL playground) |
| Learning curve | Low | Medium | Medium-High |
| N+1 problem | Manual batching | Manual batching | Requires DataLoader |

**The hidden cost nobody talks about:** switching protocols is expensive after the fact. REST APIs grow organically — teams add endpoints, add fields, ship v2s. By the time a team seriously evaluates gRPC, they have dozens of external consumers on REST. Migration is a multi-year project. This means the protocol decision made in year one carries forward. Make it deliberately.

---

### Asynchronous Communication

Asynchronous communication means the caller doesn't wait. It sends a message and continues with its work. The receiver processes the message on its own schedule. This decoupling in time is the source of both the power and the complexity of async systems.

**Message Queues (Point-to-Point)**

A message queue is the simplest async primitive: one producer puts a message on the queue, one consumer takes it off and processes it. The message persists until the consumer acknowledges successful processing.

This pattern is powerful for **load leveling**. Imagine your image processing service can handle 100 images per second, but your upload service receives 1,000 images per second during a promotion. Without a queue, your image processor is overwhelmed or you need to provision for peak. With a queue, uploads go in the queue at whatever rate they arrive, and the image processor works through them at a steady 100/sec. The queue absorbs the spike. Users' uploads are acknowledged immediately; the processing might be 30 seconds delayed during peak, but nothing breaks.

RabbitMQ and AWS SQS are the canonical implementations. SQS in particular has excellent reliability characteristics — at-least-once delivery, configurable retry with backoff, dead-letter queues for messages that repeatedly fail processing.

**Pub/Sub**

Pub/Sub (Publish/Subscribe) extends the queue concept to fan-out: one producer publishes to a topic, and many consumers receive the message independently. The producer doesn't know who's listening.

When an order is placed, the order service publishes to an `order-placed` topic. The inventory service subscribes. The fulfillment service subscribes. The analytics service subscribes. Each gets their own copy of the event and processes it independently. Adding a new subscriber (loyalty points service) requires zero changes to the publisher.

Kafka is the dominant implementation for high-throughput event streaming. Google Pub/Sub is the managed cloud alternative. The important distinction: Pub/Sub systems typically deliver events to all current subscribers; event streaming systems (Kafka) store the events persistently and let consumers replay from any point. More on this distinction below.

**Event Streaming**

Kafka deserves its own discussion because it's architecturally different from traditional message queues in important ways.

Kafka stores events in persistent, ordered logs called topics. Unlike a queue (where the message is deleted after processing), Kafka retains events for a configurable period (days, weeks, forever). Each consumer tracks its own offset — its current position in the log. This means:

- Multiple consumers can read the same events independently without interfering with each other
- New consumers can read historical events ("give me all orders from the last 30 days")
- Failed consumers can replay events they missed
- Events can be replayed to rebuild downstream state from scratch

This "replayability" is a fundamentally different capability from a queue. It enables event sourcing, allows new services to bootstrap from historical data, and provides a natural audit log of everything that happened in your system.

At high scale, Kafka is almost unmatched. Financial companies run it at billions of events per day. LinkedIn (who invented Kafka) runs it at trillions of events per day. The throughput is remarkable. The operational complexity is also remarkable — Kafka clusters require careful tuning, proper partitioning strategy, consumer group management, and monitoring.

AWS Kinesis and Google Pub/Sub with stream storage offer managed alternatives that are easier to operate at the cost of some flexibility and lower peak throughput.

---

### Choreography vs Orchestration

This is one of the most important architectural decisions in distributed systems, and most teams don't make it explicitly — they drift toward one pattern and then wonder why things got complicated.

**Choreography**

In choreography, there's no conductor. Each service knows its own role and responds to events. Service A publishes `OrderPlaced`. Service B (inventory) is subscribed and reacts by reserving stock, then publishes `StockReserved`. Service C (payment) is subscribed to `StockReserved` and charges the card, then publishes `PaymentProcessed`. And so on.

The beauty: pure loose coupling. Services don't know about each other. Adding Service D (fraud check) to the flow means Service D subscribes to the right events — no other service changes. The flow emerges from the individual reactions.

The problem: when something goes wrong, what happened? The flow only exists conceptually; it's distributed across the event bus and the reaction logic of each service. Debugging requires correlating events across multiple services and timelines. When a flow gets complex enough (especially when it involves conditional paths, compensating actions, and timeouts), choreography becomes "event spaghetti" — technically correct but impossible to reason about as a whole.

**Orchestration**

In orchestration, a central coordinator (the orchestrator) owns the flow. It calls Service B, waits for the result, decides what to do next, calls Service C, and so on. The flow logic lives in one place. When something fails, the orchestrator knows it and can take compensating actions.

The clarity is tremendous. An orchestrator for order processing might look like:

```
1. Reserve inventory (call inventory service)
   → If fails: mark order as failed, notify user
2. Process payment (call payment service)
   → If fails: release inventory reservation, mark order as failed, notify user
3. Create shipment (call fulfillment service)
4. Send confirmation (call notification service)
```

Every step, every failure path, every compensation is visible in one place. Debugging is straightforward. The business flow can be read as code.

The risk: the orchestrator can become a god service. If all the business logic migrates into the orchestrator, you've recreated a monolith in the middle of your distributed system. Orchestrators work best when they coordinate (call service, handle response, decide next step) without containing the actual business logic (which stays in the individual services).

**Practical guidance:**

The decision isn't either/or — most mature systems use both. Simple reactions (user placed order → send welcome email) are perfect for choreography. Complex, multi-step business processes with compensation logic (order placement with inventory, payment, fraud check, fulfillment) benefit enormously from orchestration.

**Temporal** is currently the best tool for durable orchestration. It provides workflow code that can be paused, resumed, retried, and compensated even if the orchestrator process restarts in the middle of execution. AWS Step Functions provides a managed alternative with good visibility but less flexibility. If you're dealing with multi-step business processes that need to be reliable, look at these tools before rolling your own.

---

## 3. API DESIGN PHILOSOPHIES

APIs are contracts. Once published and consumed, they're extraordinarily hard to change without breaking your consumers. The philosophy with which you design them — especially how you handle versioning, backward compatibility, and the vocabulary of your interface — has long-term implications that are easy to underestimate when you're writing the first version.

### Richardson Maturity Model

Leonard Richardson gave us a useful framework for thinking about REST API maturity. It's not a prescription — "you must reach Level 3" — but a useful vocabulary for discussing what your API actually is.

**Level 0: Single endpoint, RPC-style.** Everything goes to one URL, usually as a POST. The action is in the body. This is basically SOAP or old-school XML-RPC. `/api/doSomething` with `{"action": "placeOrder", "data": {...}}`. Works, but you lose all the benefits of HTTP as an application protocol.

**Level 1: Resources.** You have URLs that represent things. `/orders`, `/users`, `/products`. Multiple resources, but you might still be using POST for everything. Better — you're starting to use the URL structure meaningfully.

**Level 2: HTTP verbs and status codes.** GET to read, POST to create, PUT/PATCH to update, DELETE to delete. 200 OK, 201 Created, 404 Not Found, 409 Conflict. This is where most teams live and where most teams should live. You're using HTTP semantics correctly.

**Level 3: HATEOAS (Hypermedia as the Engine of Application State).** Responses include links to related actions. An order response includes a link to cancel the order, a link to view the customer, a link to add items. Clients navigate the API by following links rather than hardcoding URLs. This is the theoretically ideal REST, but almost nobody implements it because the tooling and client-side complexity isn't worth the benefit for most applications.

The honest guidance: aim for Level 2. Design your resources carefully, use HTTP verbs correctly, return meaningful status codes, and don't agonize over HATEOAS.

---

### API Versioning Strategies

Versioning is one of those things that's easy to ignore until you have consumers and then suddenly impossible to ignore. The question isn't whether you'll need to version your API — you will — but how.

| Strategy | Pros | Cons |
|---|---|---|
| URI versioning (`/v1/orders`) | Simple, explicit, cacheable, easy to test in browser | Routes duplication, /v1 and /v2 endpoints coexist indefinitely |
| Header versioning (`Accept: application/vnd.api+json;version=2`) | Clean URIs | Hidden in headers, harder to test with browser, can surprise proxy caches |
| No versioning (API evolution) | No version management overhead | Requires strict backward compatibility discipline, harder for breaking changes |

**URI versioning** is by far the most common in practice and for good reason. It's explicit — you can see in a request what version is being called. You can test it in a browser URL bar. Proxy caches and CDNs handle it correctly. The downside is duplication: `/v1/orders` and `/v2/orders` both exist and need to be maintained.

**Evolution-based APIs** (the "no versioning" approach, championed by the REST purists) work when the team has the discipline to never make breaking changes — only additive changes. This is actually achievable with the right backward compatibility rules (below), but requires real discipline and a culture of thinking carefully about API changes before they ship.

Practically, most teams use URI versioning for major, breaking changes and follow the evolution approach for minor, additive changes within a version. `/v1/orders` might gain new optional fields for years; `/v2/orders` only appears when you need to fundamentally change the shape.

---

### Backward Compatibility Rules

These are the laws of API design. Violate them and you break your consumers without knowing it, and they only find out in production.

**Never remove a field.** A consumer might be relying on that field. Even if you think nobody is using `legacy_user_id`, you don't know for certain, and removing it causes a runtime error for any consumer that reads it. Mark fields as deprecated in your docs, keep them forever (or until you've verified no consumer is using them).

**Never change a field's type.** If `orderId` was a string, it must remain a string. If `price` was a float, it must remain a float. Type changes break consumers at deserialization.

**Never rename a field.** Same as removing it plus adding a new one — old consumers don't see the new field, new consumers don't see the old one. If you must rename, add the new name as an additional field and deprecate the old one.

**New required input fields are breaking changes.** If you add a required field to a request schema, all existing clients that don't send that field will break. New optional input fields are safe (defaults apply); new required fields require a version bump.

**What is safe:**
- Adding a new optional field to a response (consumers ignore unknown fields)
- Adding a new optional parameter to a request
- Adding a new endpoint
- Adding a new enum value (be careful — some code switches on all enum values exhaustively)

---

### API Gateway Pattern

An API Gateway is a single entry point for all client requests to your services. Instead of clients knowing about ten different service URLs and ports, they talk to one place: the API gateway.

The gateway handles the cross-cutting concerns that every service would otherwise have to implement independently:

- **Authentication and authorization:** Validate tokens once at the gateway; services receive verified identity without re-implementing auth
- **Rate limiting:** Protect services from abuse without each service implementing their own rate limiting logic
- **Routing:** Direct requests to the appropriate backend service based on path, headers, or other rules
- **SSL/TLS termination:** Handle certificates at the boundary; internal services communicate over plain HTTP (encrypted at the network layer if needed)
- **Request/response transformation:** Adapt between client expectations and service interfaces
- **Caching:** Return cached responses for idempotent reads without hitting backend services
- **Monitoring and logging:** Centralized visibility into all inbound traffic

AWS API Gateway, Kong, Nginx, and Envoy are common implementations. AWS API Gateway is excellent for serverless architectures. Kong and Nginx are popular for self-hosted deployments. Envoy (the proxy underlying most service meshes) handles this at a lower level.

The risk: the API gateway can become a bottleneck and a single point of failure if not designed for high availability. It can also become a place where business logic accumulates ("just add the user ID to the header in the gateway!"). Keep business logic in services; keep the gateway as infrastructure.

---

### BFF (Backend for Frontend)

As applications develop multiple frontends — a web app, an iOS app, an Android app, maybe a third-party API — you often find that each client has different data needs and different performance characteristics.

The mobile app wants compact payloads with minimal fields (battery and bandwidth matter). The web app wants rich data to power complex UI. The third-party API needs stable, versioned contracts. Trying to serve all of these from a single general-purpose API is a constant negotiation and usually ends up serving nobody well.

The BFF pattern is to create a dedicated backend for each frontend type. The web BFF knows about the web app's data needs and aggregates/transforms the underlying service data accordingly. The mobile BFF knows about the iOS and Android app's needs and provides compact, optimized responses.

Each BFF:
- Is owned by the frontend team (they control their own API shape)
- Aggregates data from multiple backend services
- Returns exactly what the frontend needs
- Can evolve independently as the frontend evolves

SoundCloud was an early adopter and wrote about this pattern in 2015. The pattern is common in Netflix's architecture. The downside is duplication — you have multiple BFFs doing similar aggregations — but the frontend team's autonomy and the optimization opportunities are usually worth it.

---

## 4. DOMAIN-DRIVEN DESIGN (DDD)

Domain-Driven Design is one of those things that separates engineers who build systems that last from engineers who build systems that get rewritten every three years. Eric Evans wrote the definitive book in 2003, and it's still required reading. The ideas have only gotten more relevant.

Here's the core thesis: **software complexity comes from the domain's complexity, and the best way to manage it is to make the code reflect the domain accurately.** If the code uses the same language as the business (same concepts, same vocabulary, same names), then domain experts can review it, developers can have productive conversations with business stakeholders, and the code stays aligned with reality as the business evolves.

DDD has two levels: Strategic and Tactical.

---

### Strategic DDD

Strategic DDD is about the big picture. Where are the domain boundaries? How do different parts of the business model relate? Who owns what? This is the stuff that determines your team structure, your service boundaries, and your data ownership model.

**Bounded Contexts**

A Bounded Context is an explicit boundary within which a domain model has a specific, consistent meaning. This sounds abstract until you hit the problem it solves.

Consider "Customer" in an e-commerce company. The customer means different things to different parts of the business. To the sales team, a customer has a status (lead, prospect, active, churned), an account owner, and a contract value. To the payment team, a customer has a billing address, payment methods, and a payment history. To the shipping team, a customer has shipping addresses and delivery preferences. To the support team, a customer has a ticket history and escalation status.

These are the same person, but modeled differently for different purposes. If you try to build one unified "Customer" object that serves all of these, you either end up with a 200-field monster object that nobody understands, or you're constantly making trade-offs that satisfy nobody. The Bounded Context solution: let Sales have their Customer, let Payments have their Customer, let Shipping have their Customer. Each is correct within its context. Coordinate through explicit interfaces when contexts need to interact.

Bounded Contexts define where microservice boundaries should be. Each microservice should own exactly one Bounded Context. (Or sometimes, a Bounded Context is big enough to be a modular monolith, and that's fine too.) The context boundary is the service boundary.

Let's make this concrete with a ride-sharing app. The concept "Driver" means something completely different across three contexts:

**In the Dispatch Context:** A Driver is a current location, an availability status (available, on-trip, offline), and a vehicle type. Dispatch doesn't care about the driver's payment account or their rating history — only whether they can accept a ride right now.

```typescript
// Dispatch Context
interface Driver {
  driverId: DriverId;
  currentLocation: Coordinates;
  status: 'available' | 'on_trip' | 'offline';
  vehicleType: 'sedan' | 'suv' | 'xl';
}
```

**In the Payments Context:** A Driver is a bank account number, a tax ID, a payout schedule, and a ledger of earnings. Payments doesn't care where the driver is or whether they're available.

```typescript
// Payments Context
interface Driver {
  driverId: DriverId;
  bankAccountId: BankAccountId;
  taxId: TaxIdentifier;
  payoutSchedule: 'daily' | 'weekly';
  pendingEarnings: Money;
}
```

**In the Trust & Safety Context:** A Driver is a background check status, a reported incident history, a license expiry date, and a document verification state.

```typescript
// Trust & Safety Context
interface Driver {
  driverId: DriverId;
  backgroundCheckStatus: CheckStatus;
  licenseExpiresAt: Date;
  documentsVerified: boolean;
  incidentCount: number;
}
```

The only thing these three share is `driverId` — the identifier that lets contexts reference the same real-world person when they need to coordinate. When Dispatch needs to pay out earnings after a trip completes, it sends a `TripCompleted` event with `driverId` and earnings amount; Payments picks it up and handles the rest in its own model. They never share data structures.

This is why building a single universal `Driver` class is a trap. You'd either end up with a 40-field object that no single team understands, or you'd have constant merge conflicts as three teams fight over the same model. The Bounded Context says: each team owns their definition within their context. Coordinate through events and explicit APIs.

**Finding your Bounded Contexts**

The practical technique: run an Event Storming session (invented by Alberto Brandolini). Get domain experts and developers in a room with sticky notes. Write down domain events in past tense — `RideRequested`, `DriverMatched`, `TripCompleted`, `PaymentProcessed`, `DriverSuspended`. Arrange them on a timeline. Natural groupings emerge: events that belong together, handled by the same people, using the same vocabulary. Those groupings are your bounded context candidates.

The red flag that you've violated a context boundary: the same piece of data appears in two services' databases, and both services can write to it. That's shared state, and shared state is coupling — it just moves the coupling from code to data.

**Ubiquitous Language**

This is the principle that engineers should use the same language as domain experts — and that this language should be used in the code, in conversations, in documentation, everywhere.

This sounds like a soft "communication" principle, but it has hard technical implications. If business stakeholders call the thing-the-user-does "enrolling in a plan" but your code has `createSubscription(userId, planId)`, there's a translation step. Developers have to translate "enrollment" to "subscription" mentally. Business people can't read the code to verify it does what they think. When requirements change ("the enrollment process now needs a waiting period"), the developer has to map that back to what's happening in `createSubscription`.

Ubiquitous Language says: use `enrollUser(userId, planId)` or even better, `enrollment.enroll(user, plan)`. Write the code so that if a business stakeholder reads it, they recognize the concepts. This sounds simple and is actually quite hard — it requires developers to learn the business domain deeply and resist the temptation to use generic technical vocabulary ("create", "manage", "process") when the business has specific vocabulary.

**Context Mapping Patterns**

When two Bounded Contexts need to interact, the relationship between them has a specific pattern. Understanding which pattern you're in helps you design the integration correctly.

| Pattern | Description | When You're In It |
|---|---|---|
| Shared Kernel | Two contexts share a subset of the model | Two teams with tight coupling that's intentional; rarely ideal |
| Customer-Supplier | Upstream provides what downstream needs | One team depends on another's data; upstream should consider downstream's needs |
| Anti-Corruption Layer | Downstream translates upstream's model | You're integrating with a legacy system or external API with a bad model |
| Open Host Service | Upstream provides a well-defined protocol for integration | Upstream has many consumers; defines a published interface |
| Conformist | Downstream conforms to upstream as-is | Downstream team has little power; upstream changes at will |

The most important one to recognize in practice is the **Anti-Corruption Layer (ACL)**. When you're integrating with a legacy system, an external API, or a context with a poor domain model, the ACL is your defense. You write a translation layer that converts the external model to your domain concepts. Your code never sees the mess — it only sees your clean model. The ACL absorbs the impedance mismatch.

---

### Tactical DDD

Tactical DDD gives you the building blocks for modeling the domain richly within a Bounded Context.

**Entities**

Entities are objects defined by their identity, not their attributes. A user is still the same user if they change their name, email, or address — because the identity (user ID) is what makes them "that user." A bank account is the same account even if the balance changes.

The implication: entities are mutable (they change over time), they have a lifecycle (created, updated, deactivated), and equality is determined by identity, not by comparing attributes.

In code, entities typically have an ID field, and equality checks compare IDs:

```typescript
class Order {
  constructor(
    public readonly id: OrderId,
    public status: OrderStatus,
    public items: OrderItem[]
  ) {}

  equals(other: Order): boolean {
    return this.id.equals(other.id);
  }
}
```

**Value Objects**

Value Objects are the opposite: defined entirely by their attributes, not by any identity. Two `Money` objects with the same amount and currency are the same `Money`. There's no "which Money" question — they're equal if their values match.

Value Objects should be immutable. You don't modify a Money object in place; you create a new one. `price.add(tax)` returns a new `Money`; it doesn't mutate `price`.

Well-designed Value Objects carry domain logic:

```typescript
class Money {
  constructor(
    private readonly amount: number,
    private readonly currency: Currency
  ) {
    if (amount < 0) throw new InvalidMoneyError("Amount cannot be negative");
  }

  add(other: Money): Money {
    if (!this.currency.equals(other.currency)) {
      throw new CurrencyMismatchError();
    }
    return new Money(this.amount + other.amount, this.currency);
  }
}
```

Notice how `Money` enforces its own invariants (no negative amounts, same-currency addition). This is tactical DDD at work: the validation lives where it belongs, in the Value Object, not scattered across service methods.

Other examples: `EmailAddress`, `PhoneNumber`, `Coordinates`, `DateRange`. Every time you find yourself passing around a string with validation happening somewhere else, ask if this should be a Value Object.

**Aggregates**

Aggregates are the trickiest tactical DDD concept and the most important to get right.

An Aggregate is a cluster of Entities and Value Objects that are treated as a single unit for data consistency purposes. One Entity is the Aggregate Root — the only entry point for external interaction. The key rule: **one transaction modifies at most one Aggregate.**

The canonical example is `Order`. An Order has OrderItems. Neither an OrderItem nor the Order's TotalAmount can be in a consistent state independently — if you add an item, the total must update. These are part of the same Aggregate; Order is the Aggregate Root.

```typescript
class Order {
  private items: OrderItem[] = [];
  private totalAmount: Money;

  addItem(product: Product, quantity: number): void {
    // All logic for adding an item lives here
    // The Order maintains its own consistency
    const item = new OrderItem(product.id, product.price, quantity);
    this.items.push(item);
    this.totalAmount = this.recalculateTotal();
  }
}
```

External code adds items through `order.addItem()`, never by directly manipulating `order.items`. This gives the Aggregate Root full control over invariants.

The transaction boundary rule is crucial: if your business operation needs to modify two Aggregates in one transaction, that's a signal that either your Aggregate boundaries are wrong, or the operation should be handled through eventual consistency (domain events).

**Aggregate design heuristics**

Aggregate boundaries are one of the hardest design decisions in DDD. Here are the heuristics that experienced practitioners use:

**Keep aggregates small.** A common mistake is making aggregates too large — putting `Order`, `OrderItems`, `Shipping`, `Invoice`, and `Return` all into one aggregate. Large aggregates create contention (every operation locks the whole thing) and make the invariants hard to reason about. Start with the minimum cluster that must be consistent together.

**Ask: what invariants must hold within a single transaction?** If adding an item to an order must atomically recalculate the total, those belong in the same aggregate. If updating a user's shipping address can happen independently from their order, those can be separate aggregates.

**Use eventual consistency between aggregates, not within them.** When two aggregates need to stay in sync, do it through domain events. `OrderPlaced` → inventory aggregate reacts by creating a `StockReservation`. They're eventually consistent; they don't lock each other.

**Real boundary challenge: `Order` and `Customer`**

A natural mistake: putting `Order` inside the `Customer` aggregate. "A customer has orders, so orders belong to the customer aggregate." The problem: every time you need to modify an order, you lock the customer aggregate. At scale with many concurrent orders per customer, this creates serialization bottlenecks.

The better design: `Order` and `Customer` are separate aggregates. `Order` holds a `customerId` reference — just the ID, not the full `Customer` object. If the order service needs the customer's name for a receipt, it either denormalizes it at order creation (captures it as a value object within the order) or queries the customer service. The aggregates stay independent, and consistency between them is eventual.

```typescript
class Order {
  // Right: capture what you need from Customer at creation time
  private readonly customerSnapshot: CustomerSnapshot;
  // Wrong: private readonly customer: Customer  ← don't hold a reference to another aggregate
  
  constructor(
    id: OrderId,
    customerId: CustomerId,           // just the reference
    customerName: string,             // snapshot for display
    customerEmail: Email,             // snapshot for notifications
    items: OrderItem[]
  ) {
    this.customerSnapshot = new CustomerSnapshot(customerId, customerName, customerEmail);
    // ...
  }
}
```

This pattern — capturing a snapshot of the referenced aggregate's data at the moment of creation — is a pragmatic solution that keeps aggregates independent while preserving the data you need for the lifetime of the Order.

**Domain Events**

Domain Events record significant things that happened in the domain. They're named in past tense because they're facts: `OrderPlaced`, `PaymentReceived`, `ItemShipped`, `UserDeactivated`.

Their primary purpose: letting other parts of the system (or other Bounded Contexts) react to domain happenings without coupling the producer to the consumers.

When an Order is placed, the Order aggregate raises an `OrderPlaced` event. The application layer catches this and publishes it to a message bus. The inventory context subscribes and reserves stock. The notification context subscribes and sends an email. Neither the Order aggregate nor the Order application service knows about inventory or notifications. This is how you keep Bounded Contexts decoupled while still reacting to domain events.

**Practical guidance:**

Strategic DDD is almost always worth the investment. Identifying your Bounded Contexts, establishing Ubiquitous Language, and understanding your Context Map will improve every subsequent architectural decision. It's the foundation.

Tactical DDD — Aggregates, Value Objects, Domain Events — is most valuable in your core domain. The core domain is the part of your business that's genuinely complex, genuinely differentiating, and genuinely worth the investment in rich domain modeling. Your order management, your pricing engine, your fulfillment logic — these deserve tactical DDD. Your user management and authentication? Generic CRUD is fine.

Don't apply tactical DDD everywhere. The overhead is real. Apply it to what matters.

---

## 5. EVENT-DRIVEN PATTERNS

Several patterns have emerged around event-driven systems that are worth understanding as distinct techniques, because they solve different problems and are often confused with each other.

### Event Sourcing

Event Sourcing is the practice of storing every state change as an event, and deriving the current state by replaying those events.

**The moment it clicks**

Here's the thing that makes event sourcing suddenly obvious once you see it: most domains already think in events. They just store the summary and throw away the story.

Take an e-commerce order. Here's what a traditional CRUD system stores in the `orders` table:

```
id     | status    | total  | updated_at
-------|-----------|--------|--------------------
ord-1  | shipped   | 89.99  | 2026-03-15 14:32:00
```

That's it. The current state snapshot. From this record alone, you cannot answer:
- When was this order originally placed?
- Was there a payment failure before the successful charge?
- Did the customer update their shipping address after placing the order?
- How long did it sit in "processing" before fulfillment picked it up?
- Was there a fraud hold? Why was it released?

Now here's the same order in an event-sourced system:

```
event_id | order_id | event_type              | timestamp           | data
---------|----------|-------------------------|---------------------|-----
evt-001  | ord-1    | OrderPlaced             | 2026-03-15 09:11:00 | {items: [...], total: 89.99, address: "123 Main"}
evt-002  | ord-1    | PaymentAttempted        | 2026-03-15 09:11:02 | {gateway: "stripe", amount: 89.99}
evt-003  | ord-1    | PaymentFailed           | 2026-03-15 09:11:03 | {reason: "insufficient_funds", code: "card_declined"}
evt-004  | ord-1    | PaymentAttempted        | 2026-03-15 09:15:18 | {gateway: "stripe", amount: 89.99}  ← customer retried
evt-005  | ord-1    | PaymentSucceeded        | 2026-03-15 09:15:19 | {transaction_id: "txn_abc123"}
evt-006  | ord-1    | ShippingAddressUpdated  | 2026-03-15 10:02:44 | {old: "123 Main", new: "456 Oak Ave"}
evt-007  | ord-1    | FulfillmentPickedUp     | 2026-03-15 11:30:00 | {warehouse_id: "wh-east-1"}
evt-008  | ord-1    | Shipped                 | 2026-03-15 14:32:00 | {carrier: "UPS", tracking: "1Z999AA10123456784"}
```

The current state (status: "shipped", address: "456 Oak Ave") is derived by replaying these 8 events. But you also have the entire story: the failed payment, the address change, the exact fulfillment timeline.

**How replay works in code:**

```typescript
class Order {
  id: OrderId;
  status: OrderStatus;
  items: OrderItem[];
  shippingAddress: Address;
  totalAmount: Money;

  // The apply method evolves state from each event
  apply(event: OrderEvent): void {
    switch (event.type) {
      case 'OrderPlaced':
        this.id = event.orderId;
        this.status = 'pending';
        this.items = event.items;
        this.shippingAddress = event.address;
        this.totalAmount = event.total;
        break;
      case 'PaymentSucceeded':
        this.status = 'paid';
        break;
      case 'ShippingAddressUpdated':
        this.shippingAddress = event.newAddress;
        break;
      case 'Shipped':
        this.status = 'shipped';
        break;
    }
  }

  static rehydrate(events: OrderEvent[]): Order {
    const order = new Order();
    for (const event of events) {
      order.apply(event);
    }
    return order;
  }
}

// Load and reconstruct an order from its event history
const events = await eventStore.loadStream('order', orderId);
const order = Order.rehydrate(events);
```

This is the mental model shift. Instead of "the current state of the order," you think of the order as "the accumulated history of everything that happened to it." The current state is just a convenient view of that history.

**Snapshots** handle the performance concern for long-lived aggregates. If an order has 500 events over its lifetime, replaying all 500 on every load is slow. Snapshots periodically capture the materialized state: "As of event 450, the state was {...}." Then you only replay from event 451 forward. Snapshot every 50 or 100 events; the exact number is a performance tuning decision.

In a traditional database system, you store the current state: "User 123's balance is $500." When the balance changes, you overwrite the value. The history is gone.

In an event-sourced system, you store the events: "User 123 opened account with $0. User 123 deposited $600. User 123 withdrew $100." The current balance ($500) is derived by replaying these events. Nothing is overwritten.

This is extraordinarily powerful for certain domains:

**Complete audit trail.** You have a perfect, immutable record of everything that ever happened. For regulated industries (banking, healthcare, legal), this is often a compliance requirement.

**Temporal queries.** What was the state at any point in time? What would the state be if we retroactively applied a business rule change? Event sourcing makes these questions answerable. Traditional databases can't answer "what was the balance on March 15th at 14:32?" without explicit snapshotting or versioning.

**Debugging and root cause analysis.** When something went wrong, you can replay the exact sequence of events that led to it. This is invaluable.

**The costs are real:**

Event stores are unfamiliar. Most teams know how to work with relational databases; an event store (EventStoreDB, or Kafka as an event log) requires new skills and new patterns.

Querying current state requires replaying events (or maintaining a "read model" — more on this in CQRS). For large volumes of events, this can be slow without snapshots (periodic captures of the materialized state to avoid replaying from the beginning).

Schema evolution is genuinely hard. When your events need to change shape (you added a field, you split one event into two), you need an event versioning strategy. Events are immutable records of what happened; you can't just alter the schema.

**Use event sourcing when:** audit trails are a genuine requirement, temporal querying is valuable, or you're already committed to an event-driven architecture and the operational overhead is acceptable. Don't use it because it's cool or because you read about it — the complexity is real.

---

### CQRS (Command Query Responsibility Segregation)

CQRS is the pattern of using separate models for reading and writing data. Commands (writes) use one model; queries (reads) use a different model, optimized for reading.

In most systems, the write model and read model are the same: you write to a relational database and query the same relational database. This works until it doesn't. Writes need transaction management, constraint checking, business rule validation. Reads often need denormalized, pre-aggregated data that's fast to query for complex display requirements. These are different needs, and forcing one model to serve both creates friction.

In a CQRS architecture:

- **Commands** go to the write model. `PlaceOrder(userId, items)` modifies the authoritative data store. It enforces business rules. It's normalized. It might be relatively slow (transactions, joins, constraint checking).
- **Queries** go to the read model. `GetUserDashboard(userId)` reads from a pre-materialized view that has exactly the shape the dashboard needs. No joins at query time. Fast.

The read model is often maintained by consuming events from the write side. When an order is placed (event), the read model is updated asynchronously with a denormalized representation that's fast to query.

This solves a real problem: read traffic is often 10-100x write traffic, and reads often need different shapes than writes. CQRS lets you optimize each side independently. Scale reads independently (add more read replicas). Optimize the read model for your query patterns (materialized views, search indexes, graph databases for relationship queries) without affecting the write model.

**CQRS and Event Sourcing are often discussed together** but are independent patterns. You can have CQRS without event sourcing (just separate write and read databases, kept in sync synchronously or via CDC). You can have event sourcing without CQRS (store events, but derive read models on the fly). They're often combined because event sourcing naturally produces events that can be consumed to maintain read models.

**Apply CQRS when:** your read and write patterns are genuinely different, you have high read traffic requiring different data shapes, or you're building complex dashboards or reports that need denormalized data. Don't apply it by default — the two-model overhead is real, and for most CRUD applications it's not worth it.

---

### Event Notification vs. Event-Carried State Transfer

Two distinct patterns for what events contain:

**Event Notification:** Events are thin — they carry just enough information to tell consumers that something happened. The consumer calls back to get the details.

```json
// Event Notification
{
  "type": "OrderPlaced",
  "orderId": "ord-123",
  "timestamp": "2026-03-15T14:32:00Z"
}
```

When the inventory service receives this, it calls the order service API: `GET /orders/ord-123` to get the full order details it needs to reserve stock.

**Event-Carried State Transfer:** Events carry the full state, so consumers have everything they need.

```json
// Event-Carried State Transfer
{
  "type": "OrderPlaced",
  "orderId": "ord-123",
  "timestamp": "2026-03-15T14:32:00Z",
  "userId": "user-456",
  "items": [
    {"productId": "prod-789", "quantity": 2, "price": 49.99}
  ],
  "totalAmount": 99.98,
  "shippingAddress": {...}
}
```

The inventory service has everything it needs in the event. No callback required.

**Trade-offs:**

Event Notification keeps events small and simple, but consumers have temporal coupling — they must call back to the source while the data is still available. If the order service is down when inventory tries to fetch order details, the processing fails even though the event arrived fine.

Event-Carried State Transfer makes consumers autonomous — they can process events even if the source is down. But events are larger, and if the event schema changes, all consumers may need updates. Also, consumers receive a snapshot of state at the time of the event; if they need current state (post-event), they still need to query.

**The practical guidance:** Use Event Notification for simple notifications where the callback is cheap and reliable. Use Event-Carried State Transfer for events where consumers need to be truly autonomous, especially in Kafka-based systems where consumers might process events hours after they were produced.

---

### Saga Pattern

The Saga pattern solves the distributed transaction problem. In a monolith, you could wrap an entire operation in one database transaction: either everything commits or everything rolls back. In microservices, you can't span a database transaction across services. So how do you maintain consistency across multiple services?

The answer: instead of a distributed transaction, you use a sequence of local transactions, each publishing events or messages, with **compensating transactions** to undo completed steps when a later step fails.

Consider placing an order that spans three services:

```
1. OrderService: Create order record (LOCAL TRANSACTION)
   → Publish OrderCreated event

2. InventoryService: Reserve stock (LOCAL TRANSACTION)  
   → If fails: Publish StockReservationFailed
   → Compensate: OrderService cancels order

3. PaymentService: Charge card (LOCAL TRANSACTION)
   → If fails: Publish PaymentFailed
   → Compensate: InventoryService releases stock reservation
   → Compensate: OrderService cancels order
```

Each step is a local transaction (reliable, ACID). If a step fails, you don't try to roll back distributed transactions — you execute compensating transactions that undo the work done so far.

Sagas can be implemented through:
- **Choreography:** Each service publishes events and subscribes to events that trigger compensation. Decoupled but hard to reason about as flows grow complex.
- **Orchestration:** A saga orchestrator (Temporal, AWS Step Functions, or your own) manages the sequence, tracks state, and calls compensating actions when needed. More visible and easier to debug.

**What makes sagas hard:**
- Compensating transactions can fail too — you need retry logic on compensation
- The saga might be partially executed when you look at the data
- Idempotency is critical — steps might be executed multiple times due to retries
- The saga can be in an "in-between" state that business processes need to handle (order created but payment pending)

Sagas are the right answer when you have multi-service business processes that need consistency guarantees. They're complex to implement correctly. If you're starting this, look at Temporal seriously — it makes the implementation dramatically more reliable by handling persistence, retries, and timeouts at the framework level.

---

## 6. MONOLITH-TO-MICROSERVICES

Your monolith has been running for three years. The team has grown. Deployment is starting to be a coordination exercise. Some parts of the system scale very differently from others. The conversation about microservices has started.

**The journey, not the destination**

The monolith-to-microservices migration is not a project with an end date. It's a continuous architectural evolution that, if you do it right, delivers value at every incremental step. The teams that get this wrong treat it as a project: "by Q3, we'll have microservices." The teams that get it right treat it as an ongoing practice: "we identify pain, we extract the right service, we ship, we stabilize, we repeat."

Here's the realistic timeline for a mid-sized engineering organization (50-100 engineers):

**Year 0-1: The recognition**
The monolith is working but showing strain. Build times are 15 minutes. A bug in the email module caused a checkout outage last month because they share the same process. Six teams are all merging to main daily and conflicts are constant. Deployment requires a 3-hour coordination window on Tuesday evenings. This is the signal. The question isn't "should we migrate?" but "where does it hurt most and which service extraction would help the most people?"

**Year 1-2: First extractions**
Identify 2-3 candidates for extraction. Good first candidates are: bounded contexts with clear ownership, modules that scale differently from the rest, functionality that's changing frequently and blocking other teams, or capabilities that might be sold as standalone products. Do your first extraction with a small team who understands both the business domain and distributed systems. This team's job is not just to extract the service but to write the playbook for how to do it.

**Year 2-3: Infrastructure maturity**
By now you've learned painfully that logging, tracing, and service discovery are prerequisites, not afterthoughts. You've probably had at least one incident where debugging cross-service failure was miserable because you couldn't correlate logs. This is the year you invest in the platform: centralized tracing (OpenTelemetry), structured logging with trace IDs, service mesh or at minimum consistent retry/timeout policies.

**Year 3+: Sustained extraction**
Extraction becomes routine. New features are built as new services when the domain warrants it. The monolith shrinks gradually. Some parts of the monolith may never be worth extracting — they're stable, low-change, and extraction would cost more than the benefit. That's okay.

First: don't let the conversation push you into decomposing everything at once. "Big bang" monolith-to-microservices rewrites are one of the most expensive and risky things an engineering team can attempt. Teams have spent two years rewriting a monolith into microservices only to discover that the new system has all the same domain logic bugs (because they translated the bugs, not fixed them), plus a distributed systems layer on top.

The right way is incremental decomposition. Extract one service. Run it in production. Learn what you got wrong. Extract the next one. The patterns below are the tools for doing this incrementally and safely.

---

### Strangler Fig Pattern

The Strangler Fig is named after a tree that grows around another tree, gradually enveloping and replacing it. It's the canonical pattern for incrementally migrating away from a legacy system.

The mechanics: you put a routing layer (often a proxy or API gateway) in front of the monolith. For each feature you're migrating, you:

1. Build the new service
2. Route traffic for that feature to the new service
3. Monitor for correctness
4. When confident, remove the old code from the monolith

Over time, more and more routes are handled by new services. The monolith shrinks. Eventually (and this is the goal, though many teams are still "in progress" years later), there's nothing left in the monolith.

**Why this works well:** Each extraction is small and reversible. If the new user service has a bug, you flip the routing back to the monolith while you fix it. Nobody has to wait for the full migration to complete before getting value. Teams can work on different extractions in parallel.

**The routing layer** is critical to get right. It needs to be fast, reliable, and flexible. A feature flag system that routes based on path prefix, user attributes, or percentage rollout gives you tremendous control. The proxy shouldn't know about business logic; it should just forward requests.

**A concrete strangler fig: extracting the notification service**

Imagine a monolith where `/api/notifications` and `/api/users/{id}/notifications` are both handled inside the Rails monolith. Notifications are a good extraction candidate: they have clear boundaries, they're stateless, and the notification team is blocked on a major feature while the checkout team merges daily.

Step 1: Add a proxy. Put nginx or an API gateway in front of the monolith. All traffic still flows through — but now you have a routing layer you control.

```nginx
# Initially: everything goes to the monolith
location / {
  proxy_pass http://monolith:3000;
}
```

Step 2: Build the notification service independently. Run it in staging. Write a contract test that verifies it returns the same responses as the monolith for the same inputs.

Step 3: Shadow traffic (optional, high-value). Route notification requests to both the monolith AND the new service, discard the new service's responses, but compare them. You'll surface any behavioral differences before a single real user is affected.

Step 4: Canary rollout. Route 5% of notification traffic to the new service. Watch error rates, latency, and alert. Expand to 25%, 50%, 100%.

```nginx
# Split traffic: 5% to new service, 95% to monolith
upstream notifications_backend {
  server notification-service:8080 weight=5;
  server monolith:3000 weight=95;
}

location ~ ^/api/(notifications|users/.+/notifications) {
  proxy_pass http://notifications_backend;
}
```

Step 5: When at 100%, delete the notification code from the monolith. Don't leave dead code — the codebase should reflect reality.

The total elapsed time from Step 1 to Step 5 is often 4-8 weeks for a well-scoped service. The migration happens live, in production, with zero downtime and a clear rollback path at every step.

---

### Branch by Abstraction

Branch by Abstraction is particularly useful when you need to swap out an implementation inside the monolith without deploying a separate service — useful during the early stages when you're refactoring the codebase to prepare for extraction.

The steps:
1. Introduce an abstraction (interface) over the code you want to replace
2. Make existing code implement that interface
3. Build the new implementation behind the same interface
4. Add a switch (feature flag, configuration) to choose between implementations
5. Gradually move traffic to the new implementation
6. When fully migrated, delete the old implementation and possibly inline the interface

This pattern is particularly valuable when you're making internal architectural changes — swapping from direct database calls to repository patterns, or moving from synchronous calls to event-based — before you're ready to physically separate the code into a service.

**The key benefit:** The trunk is always deployable. You're not maintaining a long-running branch. The new implementation is hidden behind a flag until it's ready.

---

### Decomposition Strategies

When deciding which services to extract and in what order, there are several lenses:

**By business capability (most common)**

Business capabilities are the things the business does: "manage inventory," "process payments," "handle customer support." These tend to be stable — the business has been doing them for years, and they don't reorganize often. Services aligned to business capabilities tend to be stable, well-scoped, and have natural ownership boundaries.

This is the default recommendation and where most DDD-informed decompositions start.

**By subdomain (DDD-influenced)**

Similar to business capability, but informed by DDD's Bounded Contexts. You identify where the domain model changes meaning — where "customer" means something different — and those are your service boundaries. This produces services that are internally coherent (the model is consistent within the service) and that have explicit integration contracts at the boundaries.

**By change frequency (pragmatic)**

Extract the parts of your monolith that change most frequently. If the pricing engine changes every sprint while the authentication code hasn't changed in two years, extracting the pricing engine gives you the most deployment independence. This is the pragmatic "follow the pain" approach.

**By team (Conway's Law-aware)**

Conway's Law: organizations design systems that mirror their communication structure. If three teams all work in the same monolith, you'll get tangled architecture. If each team owns a service, you'll get cleaner boundaries — the team owns the API, the data, the deployment.

This is a valid lens, but be careful: don't create services just to give a team something to own. The service boundaries should reflect the domain, not the org chart (ideally, you want them to align).

---

### Data Ownership (The Hardest Part)

Here's the dirty secret of monolith-to-microservices: the code extraction is the easy part. The data extraction is where projects stall for years.

In a monolith, everything shares a database. The user table is joined to the orders table is joined to the products table everywhere. When you extract the user service, it needs to own the users table — but half the monolith still queries that table directly. When you extract the orders service, it needs order data — but orders join to user data, product data, and payment data that will end up in different services.

**Database-per-service is the target.** Each service has its own database (or at minimum, its own schema that no other service accesses directly). This is what gives services true independence — they can change their schema without asking permission from other teams.

**Transitional patterns for getting there:**

**Change Data Capture (CDC):** Instead of other services querying your database directly, they subscribe to a stream of change events from your database. Debezium is the standard tool — it tails the PostgreSQL/MySQL write-ahead log and publishes row changes as events. Services that used to join to your table now subscribe to your change stream and maintain their own local projection of the data they need.

**Database views:** A weaker transitional pattern. You extract the service's code but keep the data in the monolith's database, exposing it through views. This doesn't give full independence (you're still sharing a database), but it's a step toward explicit data contracts.

**Shared data as a service:** Some data genuinely needs to be shared — product catalog, reference data, configuration. Rather than every service having a copy, you extract this into its own service with a clear API. Consumers call the catalog service; the catalog service owns the data.

**The fundamental principle:** Each piece of data has exactly one authoritative owner. One service can write it. Other services query the owner's API or subscribe to the owner's events. This is non-negotiable for true microservices independence.

---

## Decision Framework

All these patterns, and you still need to pick one. Here's the distillation:

### Architecture Selection Flowchart

Work through these questions in order. Stop when you have an answer.

```
1. HOW BIG IS YOUR TEAM TODAY?
   ├── < 10 engineers → Monolith. Full stop.
   │     └── UNLESS: radically different scaling needs exist now (unusual for < 10)
   │
   └── 10-50 engineers → Continue to question 2

2. DO YOU KNOW YOUR DOMAIN WELL ENOUGH TO DRAW BOUNDARIES?
   ├── NO (building V1, still discovering what you're building)
   │     → Modular monolith. Invest in boundaries inside one deployment.
   │     └── Revisit in 6-12 months as the domain clarifies.
   │
   └── YES (3+ years of production learnings) → Continue to question 3

3. ARE TEAMS GENUINELY BLOCKED ON EACH OTHER'S DEPLOYMENTS?
   ├── NO → Modular monolith is still the right answer.
   │     └── Team coordination pain ≠ microservices problem if teams aren't blocked
   │
   └── YES (deployment coordination is a real, recurring bottleneck) → Continue to question 4

4. DO YOU HAVE THE OPERATIONAL FOUNDATIONS?
   ├── NO (no distributed tracing, no per-service CI/CD, no service discovery)
   │     → Build foundations first. Microservices without these are chaos, not architecture.
   │
   └── YES → Microservices are appropriate. Use Strangler Fig to migrate incrementally.

5. INTERNAL ARCHITECTURE STYLE (independent of deployment topology):
   ├── Complex domain with rich business rules → Hexagonal/Clean + DDD tactical patterns
   ├── Many features with little shared logic → Vertical Slice Architecture
   ├── CRUD-heavy with simple rules → Layered (Controller-Service-Repository)
   └── All of the above in different parts → Hybrid (common; align style to domain complexity)

6. COMMUNICATION PATTERNS:
   ├── Need real-time response → Synchronous (REST or gRPC)
   │     ├── Internal, high throughput → gRPC
   │     └── External/browser-facing → REST or GraphQL
   │
   └── Can tolerate latency / fan-out needed → Async (message queue or event stream)
         ├── Simple queue (one consumer) → SQS, RabbitMQ
         ├── Fan-out (many consumers) → Kafka topic, SNS
         └── Durable workflow with compensation → Temporal or AWS Step Functions
```

**The question to ask first:** "What's my team size and maturity?" Not "What does Netflix do?" or "What's the most scalable?" The right architecture is the one your team can build, understand, operate, and evolve. An architecture that's theoretically correct but operationally beyond your team's capabilities is the wrong architecture.

**Then ask:** "What do I actually know about my domain right now?" If you're building V1 and you're not sure what your bounded contexts are, don't design a microservices architecture yet. You'll get the boundaries wrong — guaranteed — and changing service boundaries is much harder than refactoring modules in a monolith.

**The pragmatic progression for most teams:**

1. Start with a monolith (fast to build, simple to operate, flexible to change)
2. As the codebase grows and teams form, invest in modularity (enforced module boundaries, clear data ownership within the monolith)
3. When team independence is genuinely blocked, extract services using Strangler Fig
4. Apply DDD to understand domain boundaries before you split
5. Add microservices operational infrastructure (observability, CI/CD per service) before you need it, not after

| Scenario | Start With |
|---|---|
| New startup, small team | Monolith or modular monolith |
| Growing team, clear boundaries emerging | Modular monolith with enforced boundaries |
| Large org, multiple teams with clear ownership | Microservices with careful boundary design |
| Complex domain logic | DDD + hexagonal/clean architecture |
| High-throughput events | Event-driven + Kafka |
| Full audit trail needed | Event sourcing + CQRS |
| Multiple client types | BFF + API gateway |
| Migrating from monolith | Strangler fig + branch by abstraction |

---

## Cost of Architecture

Architecture has a price tag. The microservices dream costs $3K/month in infrastructure before you write a line of business logic — and that's the *minimum* production-grade setup. If you're a 3-person startup debating microservices vs monolith, "which one is cooler" is the wrong question. "Which one can we actually afford to run and operate?" is the right one.

> All figures are ballpark estimates as of 2025 — check current pricing before budgeting.

| Architecture | Minimum Monthly Cost | Team Size to Operate | When It Pays Off |
|---|---|---|---|
| Simple monolith (single server) | $20–100 | 1–3 | MVP, <100K users |
| Modular monolith (managed container) | $100–500 | 2–5 | Growing startup |
| Microservices (basic) | $500–3,000 | 5–15 | Multiple teams, independent deploys needed |
| Microservices (production-grade with observability) | $3,000–15,000 | 10–30 | Scale demands it |
| Event-driven (managed Kafka/SQS) | SQS: $20–200 / MSK: $800–3,000 | Varies | Async workloads |

The minimum cost numbers above assume a single region, no multi-AZ for the monolith, and a bare-bones observability stack. Production-grade microservices at serious scale — distributed tracing, per-service alerting, managed service mesh, multiple environments — routinely run $10K–$30K/month before you've bought a single reserved instance.

The architectural decision that saves you the most money early isn't picking the right framework — it's resisting the urge to build for 100M users when you have 1,000. A monolith running on a $50/month server that your team understands completely beats a $5,000/month Kubernetes cluster that only one engineer groks.

---

### Architecture Decision Records (ADRs)

One practice that pays disproportionate dividends: write down the architectural decisions you make. Not the "how" but the "why" — and especially the options you considered and rejected.

An Architecture Decision Record (ADR) is a short document (typically 1-2 pages) that captures:

- **Context:** What situation prompted this decision? What were the constraints?
- **Decision:** What did you decide?
- **Alternatives considered:** What else did you evaluate and why did you reject it?
- **Consequences:** What becomes easier? What becomes harder? What do you now assume?
- **Status:** Proposed / Accepted / Deprecated / Superseded

```markdown
# ADR-007: Use gRPC for internal service communication

**Status:** Accepted | 2026-01-15

**Context:**
With the checkout, inventory, and pricing services now live, internal service
calls run at approximately 8,000 RPS during peak hours. Current REST/JSON
communication is adding ~12ms average serialization overhead per call, and
we're hitting schema drift issues where services have different assumptions
about field types.

**Decision:**
Adopt gRPC with Protocol Buffers for all new internal service-to-service 
communication. Existing REST endpoints remain unchanged for external consumers.

**Alternatives Considered:**
- Continue REST: Lower migration overhead but doesn't solve schema drift.
  Rejected because typed contracts are worth the migration cost at this scale.
- JSON over HTTP/2: Gets multiplexing benefits but not binary serialization.
  Partial solution; gRPC gives us both.
- GraphQL federation: Overkill for service-to-service; better suited for 
  client-facing APIs.

**Consequences:**
- Positive: Strong typing catches schema drift at build time. ~8x serialization 
  speedup. Native streaming support for order update push.
- Negative: Browser-facing APIs need gRPC-Web proxy. New team members need 
  to learn Protocol Buffers. Local development requires proto tooling.
- Assumption: We remain a Go/TypeScript shop where gRPC tooling is excellent.
  If we add a language without good gRPC support, revisit this decision.
```

ADRs live in a `/docs/decisions/` directory in your repo, numbered sequentially. They're committed alongside the code they describe. When a new engineer asks "why do we use gRPC?" the answer isn't "someone decided that years ago" — it's a link to a document that explains the reasoning, the tradeoffs, and what was true at the time.

This practice compounds. After two years, you have a map of every significant architectural decision and its context. Decisions made in 2024 that were correct then might become wrong by 2026 — the ADR tells you what was assumed, and when assumptions change, you can revisit deliberately.

---

### Common Architecture Anti-Patterns

These are the failure modes engineers encounter most often. Recognizing them in your own system is the first step.

**The Distributed Monolith**
Services exist but they can't be deployed independently. Each deployment requires coordinating three teams. The inventory service shares a database table with the order service. Removing this coupling requires more work than the original monolith extraction cost. Signs: deployment coordination still required, shared databases, services that fail together. Fix: go back to basics — enforce one authoritative owner per data, route through APIs not databases, make deployments independent.

**The God Service**
One service contains all the business logic. Other services are thin wrappers. When you add a feature, you always end up touching the God Service. Signs: one service is orders of magnitude larger than others, teams always coordinate changes through one team. Fix: identify what the God Service actually is — it's probably a core domain that hasn't been properly broken into bounded contexts. Apply DDD strategic design.

**Event Spaghetti**
Events flow everywhere and nobody can trace what happens when. Adding a new feature requires understanding 12 event subscriptions across 6 services. Signs: no choreography documentation, debugging requires reading subscriber code across every service, engineers afraid to change events because they don't know all the consumers. Fix: document event flows, add correlation IDs to trace event chains, consider orchestration for complex flows.

**The Premature Microservice**
A service extracted from a monolith before the domain was understood. The service boundaries are wrong. Adding a feature requires changing three services simultaneously. The services are so coupled they might as well be one service with network latency added. Signs: cross-service changes for single features, tight coupling despite being separate deployments. Fix: if the coupling is severe and consistent, seriously consider merging back — this is not failure, it's learning. Re-extract when you understand the domain better.

**Anemic Domain Model**
Entities are data bags with no behavior. All the logic lives in service classes. The `Order` class has only fields; the `OrderService` has hundreds of methods that operate on `Order`. Signs: domain objects with only getters/setters, services with names like `OrderProcessor`, `UserManager`, `PaymentHandler`. Fix: move behavior into the domain objects. Let `order.addItem()`, `order.calculateTotal()`, `order.place()` live in `Order` where they belong.

---

**The meta-lesson:** Architecture decisions are not permanent, but they're expensive to change. The best architecture is one that buys you flexibility as your understanding grows. A well-structured monolith that's refactorable is better than a premature microservices decomposition that locks you into the wrong boundaries.

The engineers who make the best architecture decisions are the ones who've learned to ask "what would need to be true for this pattern to be the right choice?" before adopting it — rather than reaching for the pattern they've heard most about.

Build what you need. Extract when you're actually in pain. Invest in the foundations (observability, testing, clean interfaces) that make any architecture change possible. And always, always talk to domain experts before you draw service boundaries.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M19: Architecture Patterns Overview](../course/modules/loop-1/L1-M19-architecture-patterns-overview.md)** — Survey the full pattern landscape and apply it to TicketPulse's evolving architecture
- **[L2-M31: The Strangler Fig — Extracting Your First Service](../course/modules/loop-2/L2-M31-the-strangler-fig-extracting-your-first-service.md)** — Hands-on strangler fig migration: pull the checkout flow out of the TicketPulse monolith without a big-bang rewrite
- **[L2-M32: Service Communication — REST vs. gRPC vs. Events](../course/modules/loop-2/L2-M32-service-communication-rest-vs-grpc-vs-events.md)** — Compare synchronous and asynchronous communication patterns by building real inter-service calls
- **[L3-M88: Architecture Review](../course/modules/loop-3/L3-M88-architecture-review.md)** — Run a structured architecture review of TicketPulse and produce a written recommendation document

### Quick Exercises

1. **Classify your codebase's current architecture pattern** — is it a monolith, modular monolith, or microservices? Write one paragraph describing the evidence for your classification and one paragraph on what the next evolutionary step would be.
2. **Identify the tightest coupling point in your system** — find two components where a change to one forces a change in the other. Draw out the dependency and describe what it would take to decouple them.
3. **Write a one-page ADR for a recent architectural decision** — pick something your team decided in the last 6 months. Document the context, the options considered, the decision made, and the consequences. Use the format from this chapter.

# The Strangler Fig Pattern

TicketPulse is a working monolith. It has authentication, ticket purchasing, payments, notifications, search, and analytics — all in one codebase. It works. Customers are happy.

But the team is growing. Deployments take longer. A bug in the search indexer crashed the payment flow last week. The monolith is becoming a liability.

## What Is the Strangler Fig?

You are not going to rewrite TicketPulse from scratch. Rewrites fail. Instead, you use the **Strangler Fig pattern** — incrementally extracting pieces of the monolith into independent services while keeping everything running.

Named after the strangler fig tree, which grows around a host tree and eventually replaces it entirely. Your new services grow around the monolith until the monolith is gone.

```
Before:                              After:
┌─────────────────────┐             ┌──────────────┐
│     Monolith        │             │   Gateway    │
│  Auth, Events,      │             └──┬───────┬───┘
│  Tickets, Payments, │────────→       │       │
│  Notifications,     │          ┌─────────┐ ┌──────────┐
│  Search, Analytics  │          │Monolith │ │ Payment  │
└─────────────────────┘          │(smaller)│ │ Service  │
                                 └─────────┘ └──────────┘
```

## The Key Rules

1. **Never rewrite.** Extract one piece at a time.
2. **The client sees no change.** URLs, response shapes, authentication — all identical.
3. **Route at the edge.** A proxy decides which service handles each request.
4. **Both old and new run simultaneously.** Roll back by changing routing.
5. **The monolith shrinks.** Delete old code once the new service is stable.

## How to Choose What to Extract First

| Criteria | Notifications | Payments | Search |
|----------|--------------|----------|--------|
| Coupling | Very low (async) | Medium (sync) | Low (read-only) |
| Risk if extraction fails | Low (emails delayed) | High (purchases break) | Medium |
| Value of independence | Medium | High (compliance) | Medium |
| Learning opportunity | Low | High | Medium |

> **The bigger picture:** In production, most teams start with the easiest extraction (Notifications) to build confidence. We're extracting Payments because it teaches the hardest problems: synchronous communication, failure handling, and data consistency.

## Key Takeaways

- The Strangler Fig pattern is incremental decomposition, not a rewrite
- Choose extraction candidates based on coupling, blast radius, and business value
- The API gateway is the routing layer that makes the transition invisible to clients
- Both old and new code run simultaneously — rollback is always possible
- Data ownership is the hardest part of service extraction

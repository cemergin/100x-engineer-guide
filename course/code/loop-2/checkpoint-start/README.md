# TicketPulse — Loop 2 Checkpoint Start

## Starting State for Loop 2: Practice

This checkpoint matches the Loop 1 end state. TicketPulse is a working monolith with authentication, tests, CI/CD, Redis caching, and RabbitMQ for async notifications.

See `../loop-1/checkpoint-end/README.md` for the full description.

## What Loop 2 Will Add

Over the next 30 modules, you'll transform TicketPulse from a monolith into a microservices architecture:

- Extract services using the Strangler Fig pattern
- Add Kafka for event-driven communication
- Deploy to Kubernetes
- Implement Infrastructure as Code with Terraform
- Add Prometheus + Grafana monitoring
- Implement distributed tracing with OpenTelemetry
- Build circuit breakers, rate limiters, and chaos experiments
- Add search with Elasticsearch
- Implement CQRS and saga patterns

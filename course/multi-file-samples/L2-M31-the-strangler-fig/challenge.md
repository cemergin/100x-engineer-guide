# Challenge: Extract the Notification Service

## The Scenario

The Payments service extraction went well. Now the team wants to extract Notifications next — email confirmations, purchase receipts, and event reminders. Unlike Payments, Notifications is already async (it consumes from RabbitMQ). But it has its own complexity: multiple delivery channels, templates, and retry logic.

## Your Task

Extract the Notification service from the monolith. Requirements:
- Consumes messages from RabbitMQ (already set up in Loop 1)
- Supports email delivery (mock the actual send)
- Has its own database for templates and delivery logs
- Exposes a health endpoint
- The monolith publishes notification events; the new service consumes them

## Success Criteria

- [ ] Notification service runs as a separate Docker Compose service
- [ ] Consumes messages from the existing RabbitMQ queue
- [ ] Has its own Postgres database for delivery logs
- [ ] Health endpoint returns service status including queue connection
- [ ] Monolith continues to publish events without code changes
- [ ] Failed deliveries are logged and can be retried

## Hints

<details>
<summary>💡 Hint 1: Direction</summary>
Since notifications are already async via RabbitMQ, the extraction is simpler than Payments. The monolith already publishes events — you just need a new consumer. Focus on: queue connection, message parsing, delivery logic, and logging.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create a standalone service that connects to RabbitMQ on startup, subscribes to the `notifications` queue, and processes messages. Each message type (purchase_confirmation, event_reminder) maps to a template. Store delivery attempts in a `notification_logs` table with status, attempts count, and last_error.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Your service needs: (1) RabbitMQ consumer with acknowledgment, (2) Template registry mapping event types to email templates, (3) `notification_logs` table: id, type, recipient, status (pending/sent/failed), attempts, last_error, created_at, (4) Retry logic: on failure, nack with requeue up to 3 times, then dead-letter. Add the service to docker-compose.yml depending on both rabbitmq and its own postgres instance.
</details>

## Solution

<details>
<summary>View Solution</summary>

The key architectural decisions:

1. **Separate database**: `notification_logs` lives in the notification service's own Postgres. The monolith never queries it directly.

2. **Consumer pattern**: Connect to RabbitMQ, subscribe to the queue, process each message, ack on success, nack with retry on failure.

3. **Dead letter queue**: After 3 failed attempts, messages go to a dead letter queue for manual investigation.

4. **Docker Compose addition**: New service with its own Postgres, connected to the shared RabbitMQ instance.

The monolith's code doesn't change at all — it already publishes to RabbitMQ. The new service simply takes over consuming those messages.

**Trade-off**: This is the simplest extraction pattern because the coupling was already async. Payments was harder because it required synchronous communication. Not all extractions are this clean.
</details>

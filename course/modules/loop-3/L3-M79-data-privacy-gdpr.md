# L3-M79: Data Privacy & GDPR

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M55 (Security Fundamentals), L2-M34 (Saga Pattern)
>
> **Source:** Chapter 30 of the 100x Engineer Guide

## What You'll Learn

- How to implement GDPR's Right to Access as a cross-service data export
- How to implement Right to Deletion across microservices, event stores, and search indices
- Crypto-shredding: the technique for deleting data from immutable event logs
- How to build a consent management system with granular, versioned opt-in/opt-out
- How to audit and scrub PII from logs before it becomes a compliance liability

## Why This Matters

TicketPulse stores personal data: names, email addresses, payment information, purchase history, location data from venue check-ins, IP addresses from every API call. Users in the EU have a legal right to see all of it, and a legal right to have it deleted. GDPR fines can reach 4% of global annual revenue or 20 million euros, whichever is higher.

This is not a legal problem. It is an engineering problem. The law says "delete all user data." The engineering reality is: data is spread across 5 services, replicated to Elasticsearch and Neo4j, immutably stored in Kafka events, included in database backups, and scattered through log files. "Just delete it" is a 6-month project if you did not design for it from the start.

> 💡 **Insight**: "Privacy is not a feature you add at the end. It is an architectural constraint you design for from the beginning. The companies that treat GDPR as a legal checkbox end up with the most expensive and painful compliance projects."

---

## Part 1: Right to Access -- Data Export

### The Requirement

Article 15 of GDPR: A user can request all data you hold about them. You must provide it in a "commonly used, machine-readable format" within 30 days.

### The Challenge

TicketPulse's data about a single user is spread across:

```
WHERE USER DATA LIVES
═════════════════════

1. User Service (PostgreSQL)
   - Profile: name, email, phone, address
   - Authentication: hashed password, 2FA settings, sessions

2. Order Service (PostgreSQL)
   - Purchase history: orders, tickets, payment references
   - Preferences: saved payment methods, favorite venues

3. Event Service (PostgreSQL + Elasticsearch)
   - Event interactions: views, searches, wishlists
   - Reviews and ratings

4. Notification Service (PostgreSQL)
   - Notification preferences: channels, frequency
   - Notification history: what was sent, when, was it read

5. Analytics Pipeline (Kafka events + ClickHouse)
   - Behavioral data: page views, click paths, search queries
   - Aggregated metrics: purchase frequency, average spend

6. Search Index (Elasticsearch)
   - User profile denormalized for search
   - Activity data indexed for recommendations

7. Log Files (Datadog / CloudWatch)
   - IP addresses, user agents, request payloads
   - May contain PII inadvertently
```

### 📐 Design: Data Export Architecture

```
USER DATA EXPORT FLOW
═════════════════════

User requests export → API Gateway → Data Export Service

Data Export Service:
  1. Generate export job (async -- may take hours)
  2. Fan out requests to each service:
     ┌─→ User Service: GET /internal/users/{id}/export
     ├─→ Order Service: GET /internal/orders/user/{id}/export
     ├─→ Event Service: GET /internal/events/user/{id}/export
     ├─→ Notification Service: GET /internal/notifications/user/{id}/export
     └─→ Analytics Service: GET /internal/analytics/user/{id}/export
  3. Each service returns its data in a standard format
  4. Data Export Service aggregates into a single JSON/ZIP file
  5. Upload to secure, time-limited S3 presigned URL
  6. Notify user that export is ready (email with download link)
  7. Delete the export file after 7 days
```

### 🛠️ Build: Data Export Endpoint

Each service implements an internal export endpoint:

```typescript
// In each service: /internal/users/:userId/export
// This endpoint is INTERNAL ONLY -- not exposed to public API

interface UserDataExport {
  service: string;
  exported_at: string;
  data: Record<string, unknown>;
}

// Order Service example
app.get("/internal/orders/user/:userId/export", async (req, res) => {
  const userId = req.params.userId;

  // Verify this is an internal request (service mesh auth, not user auth)
  if (!req.headers["x-internal-auth"]) {
    return res.status(403).json({ error: "Internal only" });
  }

  const orders = await db.query(
    `SELECT id, event_id, ticket_count, total_amount, status,
            payment_method_last4, created_at, updated_at
     FROM orders WHERE user_id = $1
     ORDER BY created_at DESC`,
    [userId]
  );

  const tickets = await db.query(
    `SELECT t.id, t.order_id, t.event_id, t.seat_section,
            t.seat_row, t.seat_number, t.status, t.created_at
     FROM tickets t
     JOIN orders o ON t.order_id = o.id
     WHERE o.user_id = $1`,
    [userId]
  );

  const export_data: UserDataExport = {
    service: "order-service",
    exported_at: new Date().toISOString(),
    data: {
      orders: orders.rows,
      tickets: tickets.rows,
    },
  };

  res.json(export_data);
});
```

**The aggregation service:**

```typescript
// Data Export Service -- orchestrates export from all services
async function generateUserExport(userId: string): Promise<string> {
  const services = [
    { name: "user-service", url: `http://user-service/internal/users/${userId}/export` },
    { name: "order-service", url: `http://order-service/internal/orders/user/${userId}/export` },
    { name: "event-service", url: `http://event-service/internal/events/user/${userId}/export` },
    { name: "notification-service", url: `http://notification-service/internal/notifications/user/${userId}/export` },
    { name: "analytics-service", url: `http://analytics-service/internal/analytics/user/${userId}/export` },
  ];

  // Fan out requests in parallel (with timeout per service)
  const results = await Promise.allSettled(
    services.map((svc) =>
      fetch(svc.url, {
        headers: { "x-internal-auth": process.env.INTERNAL_AUTH_TOKEN! },
        signal: AbortSignal.timeout(30_000), // 30s timeout per service
      }).then((r) => r.json())
    )
  );

  // Aggregate results (include partial export if a service fails)
  const exportData = {
    user_id: userId,
    export_date: new Date().toISOString(),
    sections: results.map((result, i) => ({
      service: services[i].name,
      status: result.status === "fulfilled" ? "complete" : "failed",
      data: result.status === "fulfilled" ? result.value : null,
    })),
  };

  // Upload to S3 with time-limited access
  const key = `exports/${userId}/${Date.now()}.json`;
  await s3.putObject({
    Bucket: "ticketpulse-data-exports",
    Key: key,
    Body: JSON.stringify(exportData, null, 2),
    ContentType: "application/json",
    ServerSideEncryption: "AES256",
  });

  // Generate presigned URL (valid for 7 days)
  const downloadUrl = await s3.getSignedUrl("getObject", {
    Bucket: "ticketpulse-data-exports",
    Key: key,
    Expires: 7 * 24 * 60 * 60,
  });

  return downloadUrl;
}
```

---

## Part 2: Right to Deletion

### The Requirement

Article 17 of GDPR: A user can request deletion of all their personal data. You must comply within 30 days, unless there is a legal obligation to retain it (e.g., financial records for tax purposes).

### The Hard Parts

```
WHY DELETION IS HARD IN DISTRIBUTED SYSTEMS
════════════════════════════════════════════

1. DATA IS EVERYWHERE
   The same user's email might exist in:
   - User table (primary store)
   - Order confirmation records
   - Elasticsearch index
   - Kafka events (immutable!)
   - Redis cache
   - Log files
   - Database backups

2. KAFKA EVENTS ARE IMMUTABLE
   You cannot delete a message from a Kafka topic.
   The event "UserPurchasedTicket { user_id: 123, email: alice@..." }"
   is permanently in the log until the retention period expires.

3. BACKUPS CONTAIN DELETED DATA
   If you delete a user today and restore from yesterday's backup
   tomorrow, the user is back. You need a deletion log that runs
   after every backup restore.

4. AGGREGATED DATA
   Analytics already aggregated this user's purchase data into
   "average revenue per user in Q3." Do you need to re-aggregate
   without this user? (Generally no -- aggregated, anonymized
   data is not personal data.)
```

### 📐 Design: Deletion Architecture

```
USER DELETION FLOW
══════════════════

User requests deletion → API Gateway → Deletion Orchestrator

Phase 1: SOFT DELETE (immediate)
  - Mark user as "deletion_pending" in User Service
  - Revoke all sessions and API keys
  - Remove from public search indices
  - User can no longer log in

Phase 2: HARD DELETE (async, within 30 days)
  Deletion Orchestrator fans out:
  ┌─→ User Service: DELETE /internal/users/{id}
  │     - Delete profile, auth records, preferences
  ├─→ Order Service: DELETE /internal/orders/user/{id}
  │     - Anonymize orders (keep for financial records, strip PII)
  │     - Delete saved payment methods
  ├─→ Event Service: DELETE /internal/events/user/{id}
  │     - Delete reviews, ratings, wishlists
  │     - Remove from Elasticsearch
  ├─→ Notification Service: DELETE /internal/notifications/user/{id}
  │     - Delete notification history and preferences
  ├─→ Analytics: anonymize user_id in raw events
  └─→ Kafka: crypto-shredding (see below)

Phase 3: VERIFICATION
  - Run data export for this user -- should return empty
  - Log the deletion for audit trail (who deleted, when, what was deleted)
  - The deletion log entry itself does NOT contain PII
```

### 🛠️ Build: Crypto-Shredding for Kafka Events

You cannot delete Kafka messages. But you CAN make them unreadable.

```
CRYPTO-SHREDDING
════════════════

Concept:
  1. Before storing PII in Kafka events, encrypt it with
     a per-user encryption key
  2. Store the key in a separate key store (e.g., AWS KMS or
     a dedicated keys table)
  3. When the user requests deletion, delete ONLY the key
  4. The Kafka events still exist, but the PII in them is now
     unreadable -- it is encrypted with a key that no longer exists

Before deletion:
  Event: { user_id: "123", email: "ENC(alice@example.com, key_123)" }
  Key store: { user_123: "aes-256-key-value" }
  → Consumers can decrypt email using key_123

After deletion:
  Event: { user_id: "123", email: "ENC(alice@example.com, key_123)" }
  Key store: { user_123: DELETED }
  → Consumers cannot decrypt -- PII is effectively destroyed
```

```typescript
// Crypto-shredding implementation sketch

interface EncryptedField {
  ciphertext: string;
  key_id: string;
}

// When producing events with PII:
async function encryptPII(userId: string, plaintext: string): Promise<EncryptedField> {
  // Get or create per-user encryption key
  const keyId = `user_${userId}`;
  let key = await keyStore.get(keyId);
  if (!key) {
    key = await keyStore.create(keyId);
  }

  const ciphertext = encrypt(plaintext, key);
  return { ciphertext, key_id: keyId };
}

// When consuming events:
async function decryptPII(field: EncryptedField): Promise<string | null> {
  const key = await keyStore.get(field.key_id);
  if (!key) {
    // Key was deleted (user exercised right to deletion)
    return null; // or "[DELETED]"
  }
  return decrypt(field.ciphertext, key);
}

// When deleting a user:
async function shredUserData(userId: string): Promise<void> {
  const keyId = `user_${userId}`;
  await keyStore.delete(keyId);
  // All Kafka events containing this user's PII are now unreadable
}
```

### 🛠️ Build: Post-Backup-Restore Deletion Cleanup

```typescript
// Run after EVERY database restore from backup
async function reapplyDeletions(): Promise<void> {
  // The deletion log records which users were deleted and when
  const deletedUsers = await db.query(
    `SELECT user_id, deleted_at FROM deletion_log
     WHERE deleted_at > $1`, // $1 = backup timestamp
    [backupTimestamp]
  );

  for (const user of deletedUsers.rows) {
    console.log(`[restore-cleanup] Re-deleting user ${user.user_id} (deleted at ${user.deleted_at})`);
    await deleteUserData(user.user_id);
  }

  console.log(`[restore-cleanup] Re-applied ${deletedUsers.rows.length} deletions`);
}
```

---

## Part 3: Consent Management

### 📐 Design: Granular Consent Records

GDPR requires that you track consent: what the user consented to, when, and under which version of the privacy policy.

```sql
-- Consent records table
CREATE TABLE user_consents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         BIGINT NOT NULL,
  purpose         VARCHAR(50) NOT NULL,
  -- 'marketing_email', 'marketing_push', 'analytics',
  -- 'personalization', 'third_party_sharing'
  granted         BOOLEAN NOT NULL,
  policy_version  VARCHAR(20) NOT NULL,   -- e.g., '2.3'
  ip_address      INET,                   -- where consent was given
  user_agent      TEXT,                    -- browser/device
  granted_at      TIMESTAMP DEFAULT NOW(),
  withdrawn_at    TIMESTAMP,              -- NULL if still active

  -- Every consent change creates a new row (audit trail)
  -- Never UPDATE; always INSERT
  CONSTRAINT unique_active_consent
    UNIQUE (user_id, purpose) -- only one active consent per purpose
);

CREATE INDEX idx_consents_user ON user_consents(user_id);
```

```typescript
// Consent check before sending marketing email
async function canSendMarketingEmail(userId: string): Promise<boolean> {
  const consent = await db.query(
    `SELECT granted FROM user_consents
     WHERE user_id = $1
       AND purpose = 'marketing_email'
       AND withdrawn_at IS NULL
     ORDER BY granted_at DESC
     LIMIT 1`,
    [userId]
  );

  // No consent record = no consent (opt-in, not opt-out)
  if (consent.rows.length === 0) return false;
  return consent.rows[0].granted === true;
}
```

---

## Part 4: PII in Logs

### 🔍 Audit: What PII Is in TicketPulse's Logs?

```
COMMON PII LEAKS IN LOGS
═════════════════════════

1. REQUEST LOGGING
   "POST /api/users { name: 'Alice', email: 'alice@example.com' }"
   → Logging the full request body exposes PII

2. ERROR MESSAGES
   "User alice@example.com failed to authenticate from 192.168.1.1"
   → Error context includes PII

3. DATABASE QUERY LOGGING
   "SELECT * FROM users WHERE email = 'alice@example.com'"
   → Query parameter logging exposes PII

4. PAYMENT PROCESSING
   "Processing payment for card ending in 4242, user 'Alice Smith'"
   → Payment logs may include cardholder names

5. THIRD-PARTY WEBHOOK PAYLOADS
   "Received Stripe webhook: { customer_email: 'alice@example.com' }"
   → External service callbacks contain PII
```

### 🛠️ Build: PII Scrubbing Middleware

```typescript
// PII scrubbing for structured logs
const PII_PATTERNS: Array<{ pattern: RegExp; replacement: string }> = [
  // Email addresses
  {
    pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    replacement: "[EMAIL_REDACTED]",
  },
  // IP addresses (IPv4)
  {
    pattern: /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g,
    replacement: "[IP_REDACTED]",
  },
  // Credit card numbers (basic pattern)
  {
    pattern: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g,
    replacement: "[CARD_REDACTED]",
  },
  // Phone numbers (various formats)
  {
    pattern: /\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
    replacement: "[PHONE_REDACTED]",
  },
];

function scrubPII(message: string): string {
  let scrubbed = message;
  for (const { pattern, replacement } of PII_PATTERNS) {
    scrubbed = scrubbed.replace(pattern, replacement);
  }
  return scrubbed;
}

// Apply as logging middleware
function createSafeLogger(baseLogger: Logger): Logger {
  return {
    info: (msg: string, meta?: object) =>
      baseLogger.info(scrubPII(msg), meta ? JSON.parse(scrubPII(JSON.stringify(meta))) : undefined),
    warn: (msg: string, meta?: object) =>
      baseLogger.warn(scrubPII(msg), meta ? JSON.parse(scrubPII(JSON.stringify(meta))) : undefined),
    error: (msg: string, meta?: object) =>
      baseLogger.error(scrubPII(msg), meta ? JSON.parse(scrubPII(JSON.stringify(meta))) : undefined),
  };
}

// Usage
const logger = createSafeLogger(winston.createLogger({ /* ... */ }));
logger.info("User alice@example.com logged in from 192.168.1.1");
// Logs: "User [EMAIL_REDACTED] logged in from [IP_REDACTED]"
```

**The better approach: do not log PII in the first place.**

```typescript
// INSTEAD of: logger.info(`User ${email} purchased ticket`)
// DO:         logger.info(`User ${userId} purchased ticket`, { orderId })

// If you need the email for debugging, look it up in the database.
// The user_id in the log + the email in the database gives you
// the same information, but the log file is PII-free.
```

---

## 📐 Design: The Compliance Audit

### 🤔 Reflect: If a Regulator Audited TicketPulse Tomorrow

```
GDPR COMPLIANCE AUDIT CHECKLIST
════════════════════════════════

Data Inventory:
  □ Do you have a record of all personal data you process? (Article 30)
  □ For each data element: what is the lawful basis? How long is it retained?
  □ Which third parties receive personal data? (payment providers, analytics)

Rights Implementation:
  □ Can a user request all their data? (Article 15 - Right to Access)
  □ Can a user request deletion? (Article 17 - Right to Erasure)
  □ Can a user request data portability? (Article 20 - machine-readable export)
  □ Can a user withdraw consent? (Article 7)
  □ Response time: can you fulfill requests within 30 days?

Consent:
  □ Is consent granular? (per purpose, not a single "I agree to everything")
  □ Is consent recorded? (who, when, what policy version)
  □ Is consent withdrawable? (as easy to withdraw as to give)
  □ Is the default opt-OUT? (not pre-checked boxes)

Security:
  □ Is PII encrypted at rest? (database, backups, S3)
  □ Is PII encrypted in transit? (TLS everywhere)
  □ Is access to PII logged and auditable?
  □ Is there a data breach notification process? (72-hour requirement)

Logs & Analytics:
  □ Are logs free of PII? (or scrubbed)
  □ Is analytics data anonymized?
  □ What is the log retention period?
  □ Can you delete a user's data from log archives?

Kafka & Event Sourcing:
  □ Is PII in events encrypted? (crypto-shredding ready)
  □ Can you effectively delete PII from the event log?
  □ What is the Kafka retention period? Does it align with GDPR?

YOUR BIGGEST GAP: _____________________________________________
```

---

## 🤔 Final Reflections

1. **If a regulator audited TicketPulse tomorrow, what would they find?** What is the single biggest gap?

2. **Crypto-shredding is clever, but it adds complexity to every consumer.** Every service that reads Kafka events must now handle decryption and missing keys. Is the complexity worth it? What is the alternative?

3. **The data export request fans out to 5+ services.** What happens if one service is down? Do you send a partial export? Wait? Retry? What does the law require?

4. **Financial records must be retained for 7 years.** But the user wants deletion. How do you reconcile "delete my data" with "keep records for legal compliance"? (Hint: anonymize the financial records -- keep the transaction, strip the identity.)

5. **PII scrubbing in logs is reactive. Not logging PII is proactive.** Which approach is more reliable? What are the trade-offs for debugging?

---

## Further Reading

- **Chapter 30**: Data Privacy, Ethics & Compliance -- the full technical guide
- **GDPR full text**: gdpr-info.eu -- read Articles 15, 17, 20, and 30 specifically
- **"GDPR for Engineers" by Simone Basso**: practical implementation guide
- **Crypto-shredding paper**: "Forgetting in Event-Sourced Systems" by Martin Kleppmann
- **CCPA (California)**: similar to GDPR, applies to California residents
- **HIPAA (Healthcare)**: stricter than GDPR for health data -- relevant if TicketPulse adds health-related events

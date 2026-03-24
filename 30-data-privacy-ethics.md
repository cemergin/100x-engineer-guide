<!--
  CHAPTER: 30
  TITLE: Data Privacy, Ethics & Compliance
  PART: II — Applied Engineering
  PREREQS: Chapter 5 (security)
  KEY_TOPICS: GDPR implementation, data anonymization, PII detection, consent management, data retention, right to deletion, event sourcing GDPR, CCPA, HIPAA, SOC2 engineering, privacy by design
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 30: Data Privacy, Ethics & Compliance

> **Part II — Applied Engineering** | Prerequisites: Chapter 5 | Difficulty: Intermediate

Privacy is not a legal checkbox — it's an engineering discipline. This chapter covers the technical implementation of privacy requirements, from GDPR's right to deletion in event-sourced systems to building consent management platforms.

### In This Chapter
- Privacy by Design Principles
- GDPR for Engineers
- Data Classification & PII
- Consent Management
- Data Retention & Deletion
- Anonymization & Pseudonymization
- Privacy in Event-Sourced Systems
- Other Regulations (CCPA, HIPAA, SOC2)
- Audit Logging & Compliance
- Ethical Engineering

### Related Chapters
- Ch 5 (security engineering)
- Ch 2 (data modeling for privacy)
- Ch 24 (database operations for data management)
- Ch 19 (AWS compliance features)

---

## 1. PRIVACY BY DESIGN PRINCIPLES

The 7 foundational principles (Ann Cavoukian, 2009) are not suggestions — they are architectural constraints. Every system design decision should be evaluated against them.

| # | Principle | Engineering Translation |
|---|---|---|
| 1 | **Proactive not Reactive** | Threat-model PII flows before writing code. Prevent exposure; don't wait for breach reports. |
| 2 | **Privacy as the Default** | Opt-in, not opt-out. New features collect zero PII unless explicitly justified and consented. |
| 3 | **Privacy Embedded into Design** | Data minimization is a first-class requirement, not a post-launch patch. |
| 4 | **Full Functionality** | Privacy AND business goals — false trade-offs mean the design is wrong. |
| 5 | **End-to-End Security** | Encrypt at rest, in transit, and in use. Cover the full data lifecycle: collection → processing → storage → deletion. |
| 6 | **Visibility and Transparency** | Users can see what data you hold and why. Audit logs prove compliance. |
| 7 | **Respect for User Privacy** | User-centric defaults. Granular controls. Easy data export and deletion. |

### How These Translate to Engineering Decisions

```
┌─────────────────────────────────────────────────────────────────┐
│  DESIGN PHASE CHECKLIST (apply before writing code)             │
├─────────────────────────────────────────────────────────────────┤
│  □ What PII does this feature collect? Is all of it necessary?  │
│  □ Where will the PII be stored? (DB, cache, logs, CDN, S3?)   │
│  □ Who can access it? (roles, services, third parties)          │
│  □ How long do we keep it? (retention policy)                   │
│  □ How do we delete it? (cascade plan across all stores)        │
│  □ Is consent required? Which lawful basis applies?             │
│  □ Can we achieve the goal with anonymized/aggregated data?     │
│  □ What happens during a breach? (notification plan)            │
└─────────────────────────────────────────────────────────────────┘
```

**Data Minimization in Practice:**
```python
# BAD: collecting everything "just in case"
user_profile = {
    "name": request.name,
    "email": request.email,
    "phone": request.phone,        # Not needed for this feature
    "date_of_birth": request.dob,  # Not needed for this feature
    "ip_address": request.ip,      # Not needed for this feature
    "browser_fingerprint": fp,     # Definitely not needed
}

# GOOD: collect only what the feature requires
user_profile = {
    "name": request.name,
    "email": request.email,
    # phone, dob, ip — not collected because not required
    # for account creation. Collected later only if user
    # opts into features that need them (e.g., 2FA for phone).
}
```

---

## 2. GDPR FOR ENGINEERS

GDPR creates **engineering requirements**, not just legal ones. Every right below maps to code you need to write.

### The Rights That Create Engineering Requirements

| Right | Article | What You Must Build |
|---|---|---|
| **Access** | Art. 15 | API endpoint returning all data held about a user, in a readable format |
| **Rectification** | Art. 16 | Ability to update all instances of user data across every system |
| **Erasure** ("Right to be Forgotten") | Art. 17 | Hard delete across all systems — databases, caches, backups, third parties |
| **Portability** | Art. 20 | Export in machine-readable format (JSON, CSV) |
| **Restrict Processing** | Art. 18 | Flag to pause all processing of a user's data without deleting it |
| **Object** | Art. 21 | Opt out of specific processing (e.g., profiling, marketing) |

### Data Subject Access Request (DSAR) Endpoint

```typescript
// POST /api/privacy/data-export
// Returns ALL data associated with a user across all systems

interface DataExportResponse {
  user_id: string;
  exported_at: string;           // ISO 8601
  format_version: string;        // For forward compatibility
  data: {
    profile: UserProfile;
    orders: Order[];
    payments: PaymentRecord[];   // Masked card numbers
    communications: Message[];
    consent_records: ConsentRecord[];
    activity_log: ActivityEntry[];
    third_party_shares: ThirdPartyShare[];  // Who got their data
  };
}

async function handleDataExport(userId: string): Promise<DataExportResponse> {
  // 1. Verify identity (re-authenticate before exporting PII)
  // 2. Gather data from ALL systems
  const [profile, orders, payments, comms, consents, activity, shares] =
    await Promise.all([
      userService.getProfile(userId),
      orderService.getByUser(userId),
      paymentService.getByUser(userId),      // Returns masked card numbers
      messageService.getByUser(userId),
      consentService.getByUser(userId),
      activityService.getByUser(userId),
      thirdPartyService.getShareLog(userId),
    ]);

  // 3. Package as JSON (machine-readable, portable)
  const exportData: DataExportResponse = {
    user_id: userId,
    exported_at: new Date().toISOString(),
    format_version: "1.0",
    data: { profile, orders, payments, comms, consents, activity, shares },
  };

  // 4. Log the export (audit trail)
  await auditLog.record({
    action: "DATA_EXPORT",
    user_id: userId,
    initiated_by: userId,
    timestamp: new Date().toISOString(),
  });

  return exportData;
}
```

### Lawful Basis for Processing

You **must** have one of these before processing any personal data:

| Basis | When to Use | Engineering Implication |
|---|---|---|
| **Consent** | User explicitly agrees | Store consent records; allow withdrawal |
| **Contract** | Necessary to fulfill a contract | Processing stops when contract ends |
| **Legitimate Interest** | Business need that doesn't override user rights | Document your balancing test |
| **Legal Obligation** | Law requires you to keep/process data | Retention rules override deletion requests |
| **Vital Interest** | Life-threatening situations | Rare; healthcare scenarios |
| **Public Interest** | Government/public authority functions | Unlikely for private companies |

### Breach Notification

```
┌────────────────────── BREACH RESPONSE TIMELINE ──────────────────────┐
│                                                                       │
│  T+0h    Breach detected                                              │
│  T+1h    Incident response team assembled, containment started        │
│  T+24h   Impact assessment complete (who, what data, how many)        │
│  T+72h   ← GDPR DEADLINE: notify supervisory authority                │
│           Report: nature of breach, categories of data, approx.       │
│           number of subjects, likely consequences, measures taken      │
│  T+ASAP  If high risk to individuals → notify affected users directly │
│                                                                       │
│  FINE: up to 4% of global annual revenue or €20M (whichever higher)  │
└───────────────────────────────────────────────────────────────────────┘
```

### Data Processing Agreements (DPAs)

Every third-party vendor that touches user data needs a DPA. Track them:

```sql
CREATE TABLE vendor_dpas (
    vendor_id       UUID PRIMARY KEY,
    vendor_name     TEXT NOT NULL,
    dpa_signed_at   TIMESTAMPTZ NOT NULL,
    dpa_expires_at  TIMESTAMPTZ,
    data_categories TEXT[] NOT NULL,         -- ['email', 'name', 'usage_data']
    processing_purpose TEXT NOT NULL,        -- 'email delivery', 'analytics'
    data_location   TEXT NOT NULL,           -- 'EU', 'US', 'US (SCCs in place)'
    sub_processors  TEXT[],                  -- Their vendors that also touch data
    reviewed_by     TEXT NOT NULL,
    next_review_at  TIMESTAMPTZ NOT NULL
);
```

### Data Protection Impact Assessment (DPIA)

Required when processing is **likely to result in a high risk** to individuals:
- Large-scale processing of sensitive data
- Systematic monitoring of public areas
- Automated decision-making with legal effects (credit scoring, hiring algorithms)
- New technology processing (biometrics, AI profiling)

---

## 3. DATA CLASSIFICATION & PII

### What Counts as PII

| Category | Examples | Risk Level |
|---|---|---|
| **Direct Identifiers** | Name, email, phone, SSN, passport number, driver's license | High |
| **Indirect Identifiers** | IP address, device ID, cookie ID, location data, browsing history | Medium-High |
| **Sensitive Data** (GDPR Art. 9) | Health, biometric, racial/ethnic origin, political opinions, sexual orientation, criminal records, trade union membership | Maximum |
| **Financial** | Credit card numbers, bank accounts, transaction history | High |
| **Authentication** | Passwords, security questions, MFA seeds | Critical |

### Data Classification Levels

```
┌─────────────────────────────────────────────────────────────────────┐
│  RESTRICTED   │ PII, PHI, financial data, credentials              │
│               │ Encrypted at rest + transit, access-logged,         │
│               │ retention-limited, deletion-tracked                 │
├───────────────┼─────────────────────────────────────────────────────┤
│  CONFIDENTIAL │ Internal business data, non-PII user behavior,     │
│               │ source code, configs                                │
│               │ Access-controlled, encrypted in transit             │
├───────────────┼─────────────────────────────────────────────────────┤
│  INTERNAL     │ Company announcements, internal docs, wiki          │
│               │ Behind auth, no public access                       │
├───────────────┼─────────────────────────────────────────────────────┤
│  PUBLIC       │ Marketing pages, public APIs, open-source code      │
│               │ No restrictions                                     │
└───────────────┴─────────────────────────────────────────────────────┘
```

### Automated PII Detection

```python
import re
from dataclasses import dataclass
from enum import Enum

class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"

@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str
    location: str  # file, column, field path

# Simple regex-based PII scanner (use AWS Macie or Google DLP for production)
PII_PATTERNS = {
    PIIType.EMAIL: r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    PIIType.PHONE: r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    PIIType.SSN: r'\b\d{3}-\d{2}-\d{4}\b',
    PIIType.CREDIT_CARD: r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    PIIType.IP_ADDRESS: r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
}

def scan_text(text: str, source: str) -> list[PIIMatch]:
    """Scan text for PII. Run this on log output, DB dumps, API responses."""
    matches = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in re.finditer(pattern, text):
            matches.append(PIIMatch(
                pii_type=pii_type,
                value=match.group()[:4] + "***",  # Partially mask in results
                location=source,
            ))
    return matches

# Production tools:
# - AWS Macie: scans S3 buckets for PII automatically
# - Google Cloud DLP: API-based PII detection and redaction
# - Microsoft Presidio: open-source PII detection (NLP-based, more accurate)
# - Custom: combine regex + NLP for domain-specific PII
```

### Data Mapping: Know Where ALL PII Lives

```
┌──────────────────────────────────────────────────────────────────┐
│  PII DATA MAP (maintain this — it's required for GDPR Art. 30)  │
├──────────────────────────────────────────────────────────────────┤
│  System              │ PII Fields          │ Retention  │ Owner  │
├──────────────────────┼─────────────────────┼────────────┼────────┤
│  PostgreSQL (users)  │ name, email, phone  │ Account +  │ Team A │
│                      │                     │ 30 days    │        │
│  Redis (sessions)    │ user_id, IP         │ 24 hours   │ Team A │
│  Elasticsearch       │ name, email (in     │ 90 days    │ Team B │
│  (search index)      │ search docs)        │            │        │
│  S3 (logs)           │ IP, user_id, email  │ 1 year     │ Team C │
│                      │ (in error logs)     │            │        │
│  Stripe (payments)   │ name, email, card   │ Per Stripe │ Team D │
│                      │ (last 4)            │ policy     │        │
│  SendGrid (email)    │ name, email         │ 30 days    │ Team D │
│  Snowflake (DW)      │ user_id, pseudo-    │ 2 years    │ Team E │
│                      │ nymized activity    │            │        │
│  Backups (daily)     │ All of the above    │ 30 days    │ Team C │
└──────────────────────┴─────────────────────┴────────────┴────────┘
```

---

## 4. CONSENT MANAGEMENT

### Legal Requirements for Valid Consent

Consent must be: **freely given**, **specific**, **informed**, and **unambiguous**. Pre-ticked checkboxes are not valid consent under GDPR.

### Consent Storage Schema

```sql
CREATE TABLE consent_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    purpose         TEXT NOT NULL,          -- 'marketing_email', 'analytics', 'personalization'
    granted         BOOLEAN NOT NULL,
    policy_version  TEXT NOT NULL,          -- 'privacy-policy-v2.3'
    consent_text    TEXT NOT NULL,          -- Exact text user agreed to (immutable snapshot)
    ip_address      INET,                  -- Evidence of who gave consent
    user_agent      TEXT,                  -- Evidence of how consent was given
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    withdrawn_at    TIMESTAMPTZ,           -- NULL if still active
    source          TEXT NOT NULL,          -- 'signup_form', 'settings_page', 'cookie_banner'

    -- Ensure one active consent per user per purpose
    CONSTRAINT unique_active_consent
        UNIQUE (user_id, purpose) WHERE withdrawn_at IS NULL
);

CREATE INDEX idx_consent_user ON consent_records(user_id);
CREATE INDEX idx_consent_purpose ON consent_records(purpose, granted);
```

### Granular Consent Implementation

```typescript
// Each purpose is a separate consent toggle — never bundle them
interface ConsentPreferences {
  essential: true;              // Always true, no consent needed (strictly necessary)
  analytics: boolean;           // Consent required
  marketing_email: boolean;     // Consent required
  marketing_push: boolean;      // Consent required
  personalization: boolean;     // Consent required
  third_party_sharing: boolean; // Consent required
}

async function updateConsent(
  userId: string,
  purpose: string,
  granted: boolean,
  context: { ip: string; userAgent: string; policyVersion: string }
): Promise<void> {
  if (!granted) {
    // Withdrawal: mark existing consent as withdrawn
    await db.query(`
      UPDATE consent_records
      SET withdrawn_at = NOW()
      WHERE user_id = $1 AND purpose = $2 AND withdrawn_at IS NULL
    `, [userId, purpose]);

    // CRITICAL: Stop all processing for this purpose immediately
    await processingService.stopForPurpose(userId, purpose);

    // If purpose is 'analytics', also remove user from analytics pipeline
    // If purpose is 'marketing_email', unsubscribe from all marketing lists
    await cleanupService.onConsentWithdrawn(userId, purpose);
  } else {
    // Grant: insert new consent record
    await db.query(`
      INSERT INTO consent_records (user_id, purpose, granted, policy_version,
                                    consent_text, ip_address, user_agent, source)
      VALUES ($1, $2, true, $3, $4, $5, $6, $7)
    `, [userId, purpose, context.policyVersion,
        CONSENT_TEXTS[purpose],  // Snapshot of the consent text at this version
        context.ip, context.userAgent, 'settings_page']);
  }

  await auditLog.record({
    action: granted ? "CONSENT_GRANTED" : "CONSENT_WITHDRAWN",
    user_id: userId,
    purpose,
    policy_version: context.policyVersion,
  });
}
```

### Cookie Consent (ePrivacy Directive)

| Cookie Category | Consent Required? | Examples |
|---|---|---|
| **Strictly Necessary** | No | Session cookies, CSRF tokens, load balancer cookies |
| **Analytics** | Yes | Google Analytics, Mixpanel, Amplitude |
| **Marketing / Advertising** | Yes | Facebook Pixel, Google Ads, retargeting |
| **Functional** | Yes (debatable by jurisdiction) | Language preferences, theme settings |

```typescript
// Server-side cookie gating — don't just rely on the banner
function shouldSetCookie(category: CookieCategory, userConsent: ConsentPreferences): boolean {
  switch (category) {
    case 'essential': return true;  // Always allowed
    case 'analytics': return userConsent.analytics === true;
    case 'marketing': return userConsent.marketing_email === true;
    case 'functional': return userConsent.personalization === true;
    default: return false;  // Fail-safe: deny unknown categories
  }
}
```

### Build vs. Buy

| Approach | Pros | Cons |
|---|---|---|
| **Build** | Full control, no vendor dependency, integrates perfectly with your data model | Engineering cost, must keep up with legal changes |
| **Buy** (OneTrust, Cookiebot, Osano) | Fast to deploy, auto-updates for legal changes, pre-built UIs | Cost, vendor lock-in, may not integrate cleanly with your consent-gated backend logic |
| **Hybrid** | Use a vendor for the UI/banner, build your own backend consent store | Best of both, moderate effort |

**Recommendation:** Hybrid. Use a vendor for the cookie banner (they track legal changes). Build your own consent records table (you need it for backend enforcement anyway).

---

## 5. DATA RETENTION & DELETION

### Retention Policy Matrix

```
┌────────────────────────────────────────────────────────────────────┐
│  DATA RETENTION POLICY                                             │
├──────────────────────┬─────────────┬──────────────┬────────────────┤
│  Data Type           │ Retention   │ Legal Basis  │ Deletion Method│
├──────────────────────┼─────────────┼──────────────┼────────────────┤
│  User profile        │ Account     │ Contract     │ Hard delete on │
│                      │ lifetime    │              │ account close  │
│                      │ + 30 days   │              │                │
│  Transaction records │ 7 years     │ Legal (tax)  │ Auto-delete    │
│  Session data        │ 24 hours    │ Contract     │ TTL in Redis   │
│  Server logs         │ 90 days     │ Legit.       │ Log rotation   │
│                      │             │ interest     │                │
│  Analytics (raw)     │ 30 days     │ Consent      │ Auto-delete    │
│  Analytics (aggreg.) │ Indefinite  │ N/A (anon.)  │ N/A            │
│  Marketing consent   │ Indefinite  │ Legal        │ Never (proof)  │
│  Backups             │ 30 days     │ Legit.       │ Rolling window │
│                      │             │ interest     │                │
│  Support tickets     │ 2 years     │ Legit.       │ Auto-archive   │
│                      │             │ interest     │ then delete    │
└──────────────────────┴─────────────┴──────────────┴────────────────┘
```

### Automated Deletion Pipeline

```python
# Soft delete → hard delete pipeline
# Retains data briefly for accidental deletion recovery,
# then permanently removes it.

from datetime import datetime, timedelta
from enum import Enum

class DeletionState(Enum):
    ACTIVE = "active"
    SOFT_DELETED = "soft_deleted"    # User can undo (30 days)
    PENDING_HARD_DELETE = "pending"  # Grace period expired, queued for removal
    HARD_DELETED = "hard_deleted"    # Gone forever

# Step 1: User requests deletion → soft delete
async def request_account_deletion(user_id: str) -> None:
    await db.execute("""
        UPDATE users
        SET deletion_state = 'soft_deleted',
            deletion_requested_at = NOW(),
            hard_delete_after = NOW() + INTERVAL '30 days'
        WHERE id = $1
    """, user_id)

    # Immediately stop all non-essential processing
    await stop_marketing(user_id)
    await stop_analytics(user_id)
    await revoke_api_keys(user_id)

    # Send confirmation email (they can still undo)
    await send_email(user_id, "deletion_scheduled", {
        "undo_deadline": datetime.now() + timedelta(days=30)
    })

# Step 2: Cron job runs daily → hard delete expired soft-deletes
async def hard_delete_expired_users() -> None:
    """Run daily via cron. Deletes users past their grace period."""
    users = await db.fetch("""
        SELECT id FROM users
        WHERE deletion_state = 'soft_deleted'
        AND hard_delete_after < NOW()
    """)

    for user in users:
        await hard_delete_user(user["id"])

async def hard_delete_user(user_id: str) -> None:
    """Delete ALL user data across ALL systems."""

    # 1. Database (cascade delete related records)
    await db.execute("DELETE FROM orders WHERE user_id = $1", user_id)
    await db.execute("DELETE FROM payments WHERE user_id = $1", user_id)
    await db.execute("DELETE FROM messages WHERE user_id = $1", user_id)
    await db.execute("DELETE FROM activity_log WHERE user_id = $1", user_id)
    await db.execute("DELETE FROM users WHERE id = $1", user_id)

    # 2. Cache
    await redis.delete(f"session:{user_id}")
    await redis.delete(f"profile:{user_id}")

    # 3. Search index
    await elasticsearch.delete_by_query(index="users", body={
        "query": {"term": {"user_id": user_id}}
    })

    # 4. Object storage (profile photos, uploads)
    await s3.delete_objects(bucket="user-uploads", prefix=f"{user_id}/")

    # 5. Third-party services
    await stripe_client.customers.delete(user_id)
    await sendgrid_client.contacts.delete(user_id)
    await analytics_client.delete_user(user_id)

    # 6. Log the deletion itself (keep this — proof of compliance)
    await audit_log.record({
        "action": "USER_HARD_DELETED",
        "user_id": user_id,  # Keep the ID for audit trail
        "deleted_systems": ["db", "redis", "elasticsearch", "s3",
                           "stripe", "sendgrid", "analytics"],
        "timestamp": datetime.now().isoformat(),
    })

    # 7. Add to backup exclusion list (re-apply deletion after any restore)
    await db.execute("""
        INSERT INTO deletion_log (user_id, deleted_at)
        VALUES ($1, NOW())
    """, user_id)
```

### Handling Backups

Backups are the hardest part of GDPR deletion. Two approaches:

| Approach | Pros | Cons |
|---|---|---|
| **Deletion Log** | Simple. After restoring a backup, re-run all deletions from the log. | Restoration is slower. Must always run post-restore script. |
| **Encrypted per-user backup segments** | True deletion (destroy user's key). | Complex. Only practical with crypto-shredding (see Section 7). |

```python
# Post-backup-restore script: re-apply all deletions
async def post_restore_cleanup() -> None:
    """MUST run after every backup restore. Re-deletes all previously deleted users."""
    deleted_users = await db.fetch("SELECT user_id FROM deletion_log")
    for user in deleted_users:
        await hard_delete_user(user["user_id"])
    print(f"Post-restore cleanup: re-deleted {len(deleted_users)} users")
```

---

## 6. ANONYMIZATION & PSEUDONYMIZATION

### Anonymization (Irreversible)

Anonymized data is **no longer personal data** under GDPR — you can keep it indefinitely.

| Technique | Description | Example |
|---|---|---|
| **Generalization** | Replace precise values with ranges | Age 34 → Age 30-39 |
| **Suppression** | Remove the field entirely | Delete the `email` column |
| **Noise Addition** | Add random noise to values | Salary $85,000 → $83,000-$87,000 |
| **k-Anonymity** | Every record is indistinguishable from at least k-1 others | Min k=5 for any quasi-identifier combination |
| **l-Diversity** | Each equivalence class has at least l distinct sensitive values | Prevents attribute disclosure |
| **t-Closeness** | Distribution of sensitive attribute in any class is within t of the overall distribution | Prevents skewness attacks |

**Re-identification risk is real:**
- The Netflix Prize dataset (2006) was de-anonymized by cross-referencing with IMDb ratings
- 87% of the US population can be uniquely identified by ZIP code + gender + date of birth
- Always assume an attacker has auxiliary data

### Pseudonymization (Reversible)

Still personal data under GDPR (because it's reversible with the key), but reduces risk and may allow processing under different legal bases.

```python
import hashlib
import hmac
from cryptography.fernet import Fernet

# Approach 1: Tokenization (lookup table)
class Tokenizer:
    """Replace PII with random tokens. Store mapping in a separate, secured system."""

    def __init__(self, db):
        self.db = db  # Secure token store (separate from main DB)

    async def tokenize(self, value: str, data_type: str) -> str:
        # Check if already tokenized
        existing = await self.db.fetch_one(
            "SELECT token FROM token_map WHERE original_hash = $1",
            hashlib.sha256(value.encode()).hexdigest()
        )
        if existing:
            return existing["token"]

        token = f"tok_{secrets.token_urlsafe(16)}"
        await self.db.execute(
            "INSERT INTO token_map (token, original_hash, encrypted_original, data_type) "
            "VALUES ($1, $2, $3, $4)",
            token,
            hashlib.sha256(value.encode()).hexdigest(),
            self.encrypt(value),  # Store encrypted original for de-tokenization
            data_type,
        )
        return token

    async def detokenize(self, token: str) -> str:
        row = await self.db.fetch_one(
            "SELECT encrypted_original FROM token_map WHERE token = $1", token
        )
        return self.decrypt(row["encrypted_original"])

# Approach 2: HMAC-based pseudonym (deterministic, no lookup needed)
def pseudonymize_email(email: str, secret_key: bytes) -> str:
    """Deterministic pseudonym. Same email always maps to same pseudonym.
    Destroy the secret_key to make it irreversible (= anonymization)."""
    return hmac.new(secret_key, email.encode(), hashlib.sha256).hexdigest()[:16]
```

### Data Masking for Non-Production Environments

**Rule: Production PII must NEVER exist in dev/staging environments.**

```python
# Masking rules for copying production data to staging
MASKING_RULES = {
    "users": {
        "email": lambda row: f"user_{row['id']}@example.com",
        "name": lambda row: f"User {row['id']}",
        "phone": lambda _: "+1-555-000-0000",
        "date_of_birth": lambda _: "1990-01-01",
        "ssn": lambda _: None,  # Suppress entirely
    },
    "payments": {
        "card_last_four": lambda _: "0000",
        "billing_address": lambda _: "123 Test St, Testville, TS 00000",
    },
}

async def create_masked_dump(source_db, target_db, table: str) -> None:
    """Copy a table from production to staging with PII masked."""
    rules = MASKING_RULES.get(table, {})
    rows = await source_db.fetch(f"SELECT * FROM {table}")

    for row in rows:
        masked_row = dict(row)
        for column, mask_fn in rules.items():
            if column in masked_row:
                masked_row[column] = mask_fn(row)
        await target_db.insert(table, masked_row)

# Tools for production masking:
# - pg_anonymize (PostgreSQL extension)
# - Delphix (enterprise, automatic discovery + masking)
# - Tonic.ai (generates realistic synthetic data)
# - Custom scripts (like above — fine for small teams)
```

---

## 7. PRIVACY IN EVENT-SOURCED SYSTEMS

### The Conflict

Event sourcing says: **events are immutable facts — never delete them.**
GDPR says: **delete this person's data when they ask.**

These are fundamentally incompatible. Three solutions exist, in order of practicality:

### Approach 1: Crypto-Shredding (Recommended)

Encrypt PII in events with a per-user encryption key. To "delete" a user, destroy their key. The events remain but the PII within them is unreadable.

```typescript
// ─── Key Management ───
interface UserKeyStore {
  getUserKey(userId: string): Promise<Buffer | null>;
  createUserKey(userId: string): Promise<Buffer>;
  destroyUserKey(userId: string): Promise<void>;  // This IS the "delete"
}

class CryptoShredder {
  constructor(private keyStore: UserKeyStore) {}

  // Encrypt PII before storing in event
  async encryptPII(userId: string, pii: Record<string, string>): Promise<string> {
    const key = await this.keyStore.getUserKey(userId);
    if (!key) throw new Error(`No key for user ${userId}`);

    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    const encrypted = Buffer.concat([
      cipher.update(JSON.stringify(pii), 'utf8'),
      cipher.final(),
    ]);
    const tag = cipher.getAuthTag();

    return JSON.stringify({
      iv: iv.toString('base64'),
      data: encrypted.toString('base64'),
      tag: tag.toString('base64'),
    });
  }

  // "Delete" user = destroy their encryption key
  async shredUser(userId: string): Promise<void> {
    await this.keyStore.destroyUserKey(userId);
    // Events still exist but PII is now unreadable
    // Projections will show [DELETED] for this user's PII
  }
}

// ─── Event Structure ───
interface OrderPlacedEvent {
  type: "OrderPlaced";
  aggregate_id: string;
  timestamp: string;
  // Non-PII fields stored in plain text (queryable, not affected by deletion)
  data: {
    order_id: string;
    total_amount: number;
    currency: string;
    item_count: number;
  };
  // PII stored encrypted (unreadable after key destruction)
  encrypted_pii: string;  // Contains: { name, email, shipping_address }
  pii_key_ref: string;    // Reference to key in key store (e.g., "user:abc123")
}

// ─── Projection Rebuild (handles deleted users gracefully) ───
async function rebuildOrderProjection(event: OrderPlacedEvent): Promise<void> {
  let customerName = "[DELETED]";
  let customerEmail = "[DELETED]";

  try {
    const key = await keyStore.getUserKey(event.pii_key_ref);
    if (key) {
      const pii = await cryptoShredder.decryptPII(key, event.encrypted_pii);
      customerName = pii.name;
      customerEmail = pii.email;
    }
  } catch {
    // Key destroyed — user was deleted. Use placeholder values.
  }

  await projectionStore.upsert("orders", event.data.order_id, {
    ...event.data,
    customer_name: customerName,
    customer_email: customerEmail,
  });
}
```

### Approach 2: Event Tombstoning

Replace events containing PII with a tombstone marker. Simpler but breaks event replay.

```typescript
// Replace the event in the store with a tombstone
async function tombstoneUserEvents(userId: string): Promise<void> {
  const events = await eventStore.getByUser(userId);
  for (const event of events) {
    await eventStore.replace(event.id, {
      type: "TOMBSTONE",
      original_type: event.type,
      aggregate_id: event.aggregate_id,
      timestamp: event.timestamp,
      reason: "GDPR_ERASURE",
      erased_at: new Date().toISOString(),
      // All PII removed. Non-PII aggregate data retained.
    });
  }
}
```

**Downside:** Projections rebuilt from tombstoned streams will have gaps. Use only if you can tolerate incomplete replay.

### Approach 3: Separate PII Store

Store PII in a mutable database, reference it by ID from immutable events. Events never contain PII directly.

```
┌──────────────────┐      ┌──────────────────────────────────┐
│  Event Store     │      │  PII Store (mutable, deletable)  │
│  (immutable)     │      │                                  │
│ ┌──────────────┐ │      │  user_id │ name  │ email         │
│ │ OrderPlaced  │ │ ref  │  abc123  │ Alice │ alice@ex.com  │
│ │ user_ref:    │─┼──────│  def456  │ Bob   │ bob@ex.com    │
│ │   abc123     │ │      │                                  │
│ │ amount: 50   │ │      │  After deletion:                 │
│ └──────────────┘ │      │  abc123  │ [row deleted]         │
└──────────────────┘      └──────────────────────────────────┘
```

### Which Approach to Choose

| Approach | Complexity | Event Integrity | GDPR Compliance | Recommendation |
|---|---|---|---|---|
| **Crypto-shredding** | Medium | Events intact (PII unreadable) | Strong | **Use this** |
| **Tombstoning** | Low | Events modified (breaks replay) | Adequate | Fallback if crypto is too complex |
| **Separate PII store** | Low | Events never had PII | Strong | Good for new systems |

---

## 8. OTHER REGULATIONS

### CCPA / CPRA (California)

| GDPR vs CCPA | GDPR | CCPA/CPRA |
|---|---|---|
| **Consent model** | Opt-in (must consent before collection) | Opt-out (can collect, must stop on request) |
| **"Do Not Sell"** | Not a concept (broader protections) | Explicit right; must display link |
| **Scope** | Any company processing EU residents' data | Businesses meeting revenue/data thresholds in CA |
| **Fines** | Up to 4% global revenue | $2,500/violation, $7,500/intentional |

```typescript
// CCPA: "Do Not Sell My Personal Information" flag
interface UserPrivacyFlags {
  do_not_sell: boolean;        // CCPA opt-out
  do_not_share: boolean;       // CPRA addition (covers "sharing" for cross-context ads)
  limit_sensitive_use: boolean; // CPRA right to limit use of sensitive PI
}

async function honorDoNotSell(userId: string): Promise<void> {
  // Set the flag
  await db.execute(
    "UPDATE users SET do_not_sell = true, dns_set_at = NOW() WHERE id = $1",
    userId
  );

  // Immediately stop sharing data with all third parties for advertising
  await disableThirdPartySharing(userId, [
    "facebook_pixel", "google_ads", "data_brokers", "ad_networks"
  ]);

  // Do NOT delete data — CCPA DNS only stops selling/sharing
}
```

### HIPAA (Healthcare)

**Protected Health Information (PHI)** = any health data + a patient identifier.

| Requirement | Engineering Control |
|---|---|
| **Encryption at rest** | AES-256 for databases, S3 SSE-KMS, encrypted EBS volumes |
| **Encryption in transit** | TLS 1.2+ everywhere, no exceptions |
| **Minimum necessary** | Role-based access; each role sees only the PHI needed for their function |
| **Audit logging** | Log every PHI access: who, what, when, from where |
| **BAAs** | Signed Business Associate Agreement with every vendor touching PHI |
| **Access controls** | Unique user IDs, automatic logoff, emergency access procedures |
| **Breach notification** | 60 days to notify HHS and affected individuals (500+ individuals → media notice) |

```yaml
# HIPAA-eligible AWS services (not all AWS services are eligible)
hipaa_eligible:
  compute: [Lambda, EC2, ECS, Fargate, EKS]
  storage: [S3, EBS, EFS, Glacier]
  database: [RDS, DynamoDB, Aurora, Redshift]
  networking: [VPC, CloudFront, Route 53, API Gateway]
  security: [KMS, CloudTrail, CloudWatch, GuardDuty]

not_eligible:  # DO NOT use for PHI
  - Amazon Lightsail
  - AWS Amplify (check current status)
  # Always verify: https://aws.amazon.com/compliance/hipaa-eligible-services-reference/
```

### SOC2

SOC2 is an **audit standard**, not a regulation. But customers (especially enterprise) require it.

| Trust Service Criteria | What Auditors Check | Engineering Controls |
|---|---|---|
| **Security** | Unauthorized access prevention | MFA, encryption, WAF, network segmentation |
| **Availability** | System uptime and reliability | Monitoring, incident response, DR plan |
| **Processing Integrity** | Accurate, complete processing | Input validation, reconciliation, testing |
| **Confidentiality** | Confidential data protection | Access controls, encryption, data classification |
| **Privacy** | PII handling per commitments | Consent management, retention, deletion |

**SOC2 Type I** = controls are designed correctly (point-in-time snapshot).
**SOC2 Type II** = controls operated effectively over a period (3-12 months). More valuable; customers prefer it.

```
┌────────────────────── SOC2 EVIDENCE AUTOMATION ──────────────────────┐
│                                                                       │
│  Manual evidence collection burns engineering time. Automate it.      │
│                                                                       │
│  Tools:                                                               │
│  ├── Vanta: continuous monitoring, auto-evidence collection           │
│  ├── Drata: similar, strong integration ecosystem                     │
│  ├── Secureframe: similar, good for startups                         │
│  └── Custom: pull from AWS Config, CloudTrail, GitHub audit log       │
│                                                                       │
│  What to automate:                                                    │
│  ├── Access reviews (who has access to what, quarterly)               │
│  ├── MFA enforcement status (all users, all environments)             │
│  ├── Encryption status (at rest, in transit, key rotation)            │
│  ├── Vulnerability scanning results (Dependabot, Snyk)               │
│  ├── Change management records (PRs, reviews, deployments)            │
│  └── Incident response records (PagerDuty, Opsgenie)                 │
└───────────────────────────────────────────────────────────────────────┘
```

### PCI DSS (Payment Card Data)

**Goal: reduce scope.** If card numbers never touch your servers, PCI compliance is dramatically simpler.

| Approach | PCI Scope | Effort |
|---|---|---|
| **Stripe / Braintree hosted payment page** | SAQ A (minimal) | Low |
| **Stripe Elements (JS SDK)** | SAQ A-EP | Low-Medium |
| **Direct card handling** | SAQ D (full audit) | Very High |

```typescript
// GOOD: Stripe handles all card data. Your server never sees card numbers.
const paymentIntent = await stripe.paymentIntents.create({
  amount: 2000,
  currency: 'usd',
  // Card details collected by Stripe.js on the client
  // Your server only receives a PaymentIntent ID — no card numbers
});

// BAD: Never do this — accepting raw card numbers puts you in full PCI scope
app.post('/pay', (req, res) => {
  const cardNumber = req.body.card_number;  // NO. Your server is now in PCI scope.
});
```

---

## 9. AUDIT LOGGING & COMPLIANCE

### What to Log

Every audit log entry must answer: **Who** did **what** to **which resource**, **when**, from **where**, and **did it succeed**?

```typescript
interface AuditLogEntry {
  // Identity
  actor_id: string;          // Who (user ID or service account)
  actor_type: "user" | "service" | "admin" | "system";
  actor_ip: string;          // From where

  // Action
  action: string;            // What (e.g., "USER_DATA_EXPORTED", "RECORD_DELETED")
  resource_type: string;     // On what type (e.g., "user", "order", "payment")
  resource_id: string;       // Which specific resource

  // Context
  timestamp: string;         // When (ISO 8601, UTC)
  result: "success" | "failure" | "denied";
  reason?: string;           // Why it failed or was denied

  // Change tracking (for write operations)
  changes?: {
    field: string;
    old_value?: string;      // Masked if PII
    new_value?: string;      // Masked if PII
  }[];

  // Correlation
  request_id: string;        // Trace across services
  session_id?: string;
}
```

### Immutable Audit Log Storage

```python
# Audit logs must be append-only. No one — not even admins — can modify or delete them.

# Option 1: Database with write-only permissions
# The application role can INSERT but not UPDATE or DELETE
"""
GRANT INSERT ON audit_log TO app_role;
REVOKE UPDATE, DELETE ON audit_log FROM app_role;
-- Even the DBA should not routinely delete audit logs
"""

# Option 2: AWS CloudWatch Logs (immutable by design)
# Log retention policy enforced at the AWS level

# Option 3: S3 with Object Lock (WORM - Write Once Read Many)
import boto3

s3 = boto3.client('s3')

# Enable Object Lock on the bucket (must be set at bucket creation)
# Governance mode: admins can override. Compliance mode: NO ONE can delete.
s3.put_object(
    Bucket='audit-logs',
    Key=f'audit/{datetime.now().strftime("%Y/%m/%d")}/{uuid4()}.json',
    Body=json.dumps(audit_entry),
    ObjectLockMode='COMPLIANCE',
    ObjectLockRetainUntilDate=datetime(2033, 1, 1),  # Retain for 7 years
)
```

### Retention Requirements by Regulation

| Regulation | Retention Period | What to Retain |
|---|---|---|
| **SOX** (Sarbanes-Oxley) | 7 years | Financial audit trails |
| **HIPAA** | 6 years | PHI access logs |
| **GDPR** | As long as processing continues | Processing activity records, consent records |
| **PCI DSS** | 1 year | Cardholder data access logs |
| **SOC2** | Per audit period (typically 1 year) | All controls evidence |

### Anomaly Detection on Audit Logs

```python
# Alert on suspicious access patterns
ALERT_RULES = [
    {
        "name": "bulk_data_export",
        "description": "Single user exported data for > 100 users in 1 hour",
        "query": """
            SELECT actor_id, COUNT(*) as export_count
            FROM audit_log
            WHERE action = 'USER_DATA_EXPORTED'
            AND timestamp > NOW() - INTERVAL '1 hour'
            GROUP BY actor_id
            HAVING COUNT(*) > 100
        """,
        "severity": "critical",
    },
    {
        "name": "off_hours_pii_access",
        "description": "PII accessed outside business hours",
        "query": """
            SELECT actor_id, action, resource_id, timestamp
            FROM audit_log
            WHERE resource_type IN ('user', 'payment', 'health_record')
            AND EXTRACT(HOUR FROM timestamp) NOT BETWEEN 8 AND 18
            AND actor_type = 'user'
        """,
        "severity": "high",
    },
    {
        "name": "permission_escalation",
        "description": "User granted themselves elevated permissions",
        "query": """
            SELECT actor_id, resource_id, changes
            FROM audit_log
            WHERE action = 'PERMISSION_CHANGED'
            AND actor_id = resource_id
        """,
        "severity": "critical",
    },
]
```

---

## 10. ETHICAL ENGINEERING

### Bias in Algorithms

| Bias Type | Example | Mitigation |
|---|---|---|
| **Training data bias** | Resume screening trained on historical hires (mostly male) → penalizes women | Audit training data for demographic representation |
| **Proxy discrimination** | ZIP code used as a feature → correlates with race | Identify and remove proxy features |
| **Feedback loops** | Predictive policing → more police in flagged areas → more arrests → reinforces prediction | Monitor for amplification effects |
| **Sampling bias** | Voice recognition trained on American English → fails for other accents | Test across demographic groups |

```python
# Fairness check: compare model outcomes across demographic groups
def check_demographic_parity(predictions, demographics, outcome_col, group_col):
    """
    Acceptance rate should be similar across groups.
    Ratio < 0.8 indicates potential disparate impact (80% rule / four-fifths rule).
    """
    groups = demographics[group_col].unique()
    rates = {}
    for group in groups:
        mask = demographics[group_col] == group
        rates[group] = predictions[mask][outcome_col].mean()

    max_rate = max(rates.values())
    for group, rate in rates.items():
        ratio = rate / max_rate
        if ratio < 0.8:
            print(f"WARNING: {group} acceptance rate ({rate:.2%}) is {ratio:.2%} "
                  f"of highest group — potential disparate impact")

    return rates
```

### Dark Patterns to Avoid

| Dark Pattern | Example | Why It's Wrong |
|---|---|---|
| **Confirm-shaming** | "No thanks, I don't want to save money" | Manipulates through guilt |
| **Roach motel** | Easy to sign up, impossible to delete account | Violates GDPR Art. 17 |
| **Hidden costs** | Fees revealed only at checkout | Deceptive |
| **Forced continuity** | Free trial → auto-charges with no warning | Often illegal |
| **Privacy zuckering** | Confusing settings that default to maximum data sharing | Violates GDPR consent requirements |
| **Trick questions** | Double negatives in opt-out checkboxes | Invalid consent |

### The Engineer's Decision Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│  ETHICAL DECISION CHECKLIST (before implementing a feature)         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. NEWSPAPER TEST                                                  │
│     "Would I be comfortable if this appeared in a news article?"    │
│     If no → escalate before building.                               │
│                                                                     │
│  2. REVERSIBILITY TEST                                              │
│     "Can the user undo this action and its consequences?"           │
│     If no → add friction, confirmation, and clear disclosure.       │
│                                                                     │
│  3. VULNERABILITY TEST                                              │
│     "Could this disproportionately harm vulnerable populations?"    │
│     (elderly, children, non-native speakers, low-income)            │
│     If yes → redesign with those populations in mind.               │
│                                                                     │
│  4. SCALE TEST                                                      │
│     "What happens when this is used by millions of people?"         │
│     Small harms at scale become large harms.                        │
│                                                                     │
│  5. INTENT vs. IMPACT TEST                                          │
│     "Does the impact match the stated intent?"                      │
│     If the system claims to 'help users' but primarily extracts     │
│     data → the intent and impact are misaligned.                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### When to Push Back

You write the code — you share the responsibility. Engineers are not just order-takers.

**Escalation ladder:**
1. Raise the concern with your direct manager (in writing)
2. If unresolved, escalate to the privacy/legal team
3. If still unresolved, escalate to senior leadership (skip level)
4. If the company insists on violating user trust or the law, consult an employment lawyer
5. Whistleblower protections exist in many jurisdictions (EU Whistleblower Directive, US SOX)

**Document everything.** Verbal objections don't exist. Written objections in email or Slack do.

### Resources

| Resource | Description |
|---|---|
| **ACM Code of Ethics** | Professional standards for computing professionals |
| **IEEE Code of Ethics** | Engineering ethics standards |
| **EFF (Electronic Frontier Foundation)** | Digital rights advocacy, practical privacy guidance |
| **NIST Privacy Framework** | Privacy risk management framework |
| **IAPP (International Association of Privacy Professionals)** | Certifications (CIPP, CIPM, CIPT), resources |
| **OWASP Privacy Risks** | Top 10 privacy risks in web applications |

---

## COMPLIANCE CHECKLIST

Use this as a starting point for any new project or privacy audit.

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRIVACY & COMPLIANCE ENGINEERING CHECKLIST                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DATA INVENTORY                                                     │
│  □ PII data map exists and is up to date (Art. 30 ROPA)            │
│  □ Every PII field has a documented lawful basis                    │
│  □ Every third-party vendor with PII access has a signed DPA       │
│  □ Data classification labels applied to all data stores            │
│                                                                     │
│  CONSENT                                                            │
│  □ Consent is granular (separate toggles per purpose)              │
│  □ Consent records stored with timestamp, version, and text        │
│  □ Withdrawal is as easy as granting consent                       │
│  □ Pre-ticked boxes are not used anywhere                          │
│                                                                     │
│  DATA SUBJECT RIGHTS                                                │
│  □ Data export endpoint exists and returns all user data            │
│  □ Data deletion pipeline covers ALL systems (DB, cache, search,   │
│    backups, third parties)                                          │
│  □ Deletion is verified (audit log confirms completion)            │
│  □ Rectification can propagate to all copies of the data           │
│                                                                     │
│  SECURITY                                                           │
│  □ PII encrypted at rest (AES-256 or equivalent)                   │
│  □ PII encrypted in transit (TLS 1.2+)                             │
│  □ Access to PII is role-based and logged                          │
│  □ Production PII never exists in dev/staging environments         │
│                                                                     │
│  RETENTION & DELETION                                               │
│  □ Retention policy defined for every data type                    │
│  □ Automated deletion jobs running on schedule                     │
│  □ Backup restoration triggers post-restore deletion cleanup       │
│                                                                     │
│  AUDIT & MONITORING                                                 │
│  □ Immutable audit logs capture all PII access                     │
│  □ Anomaly detection alerts on suspicious access patterns          │
│  □ Audit log retention meets regulatory requirements               │
│                                                                     │
│  INCIDENT RESPONSE                                                  │
│  □ Breach notification process documented and tested               │
│  □ 72-hour GDPR notification timeline achievable                   │
│  □ Contact details for supervisory authority on file               │
│                                                                     │
│  ENGINEERING CULTURE                                                │
│  □ Privacy review is part of the design review process             │
│  □ PII scanning runs in CI/CD (catch accidental PII in logs)      │
│  □ Team has completed privacy training in the last 12 months       │
│  □ DPIA conducted for high-risk processing activities              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

> **Next Steps:** With privacy infrastructure in place, Chapter 5 covers the broader security engineering foundations that underpin these controls. For database-level implementation of retention and deletion, see Chapter 24.

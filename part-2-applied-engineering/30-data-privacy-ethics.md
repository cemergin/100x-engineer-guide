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

Here's a framing that will change how you think about everything in this chapter: **data privacy is a distributed systems problem**.

Not a legal problem. Not a compliance checkbox. A distributed systems problem — the kind where you have data scattered across PostgreSQL, Redis, Elasticsearch, S3, Stripe, SendGrid, Snowflake, and fourteen other services, and you need to guarantee a property across all of them simultaneously. The property is: when a user says "delete my data," it's actually gone. All of it. Everywhere. Provably.

Sound familiar? That's the exact problem class from Chapter 24 on database internals — except instead of ACID guarantees within one transaction, you need them across your entire data estate, including third-party systems you don't control, backups you took six months ago, and log files you forgot existed.

That's why this chapter treats privacy as engineering, not law. The legal requirements are real — GDPR fines have crested €4 billion since 2018, and the ICO handed British Airways a £20 million fine for a breach they could have prevented with basic security hygiene (see Chapter 5 for exactly that hygiene). But the *response* to those requirements is code. Schema design. Cryptographic protocols. Deletion pipelines. Consent state machines.

Let's build them.

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
- **SECURITY spiral:** ← [Ch 19: AWS Deep Dive](../part-4-cloud-operations/19-aws-deep-dive.md) | → [Ch 33b: Advanced GitHub Actions](../part-3-tooling-practice/33b-github-actions-advanced.md)
- Ch 5 (security engineering — encryption, authentication, the security foundation this chapter builds on)
- Ch 2 (data modeling for privacy)
- Ch 24 (database operations — crypto-shredding and deletion pipelines live at this layer)
- Ch 19 (AWS compliance features)

---

## The Cambridge Analytica Problem

Before diving into the mechanics, it's worth understanding what happens when privacy engineering fails at scale.

In 2014, a researcher named Aleksandr Kogan built a Facebook quiz app called "thisisyourdigitallife." About 270,000 people installed it and consented to sharing their Facebook data. Standard stuff. Except Kogan's app also harvested the data of those users' *friends* — without their consent — exploiting a then-legal API loophole. The total haul: **87 million people's personal data**.

That data was sold to Cambridge Analytica, a political consulting firm that used psychographic profiling to micro-target voters in the 2016 US election and the Brexit referendum.

The engineering failures were mundane. No data minimization — the app collected everything it could access, not what it needed. No consent for secondary use — the data subjects whose friends installed the app never agreed to anything. No audit trail — Facebook had no idea how many apps were doing this until a journalist asked. No deletion mechanism — once data left Facebook's servers, it was gone forever in the wrong direction.

Facebook paid a $5 billion FTC fine. Cambridge Analytica dissolved. And we got GDPR — which in its 99 articles is essentially a response to exactly this architecture: collect everything, share it widely, and figure out the consequences later.

Your job is to build the opposite architecture. Privacy by design, not privacy by apology.

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

These seven principles look abstract until you're six months into a product and someone asks "how do we add GDPR deletion support?" The answer at that point is expensive: you find out your user's email address is baked into 23 different data stores, three of which are owned by a vendor whose DPA is expired. Privacy by design means you planned the deletion pipeline before you wrote the first INSERT statement.

### How These Translate to Engineering Decisions

The design-phase checklist below should happen in the same meeting where you design the feature — not after launch, not as a post-hoc audit.

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

This is the single highest-leverage principle. Every field you don't collect is a field you don't have to secure, retain-limit, delete, or explain to a regulator. Every extra field is technical debt with a legal liability attached.

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

The instinct to collect everything "for future analytics" is understandable — data has value, and who knows what you'll want to analyze later. But this is exactly the trap Cambridge Analytica's Facebook ecosystem fell into. Collect what you need today. If you need more tomorrow, ask for it tomorrow with fresh consent.

---

## 2. GDPR FOR ENGINEERS

GDPR went into effect in May 2018. By 2025, it had generated over €4 billion in fines across thousands of cases. The largest: Meta, €1.2 billion for transferring EU user data to US servers without adequate safeguards. The most instructive for engineers: British Airways, £20 million for a breach caused by skimping on the exact security controls covered in Chapter 5. The most ironic: Google, €50 million in France for consent violations — a consent management system failing in exactly the ways this section will show you how to avoid.

The lesson isn't "be scared." The lesson is that GDPR creates **engineering requirements**, not just legal ones. Every right below maps to code you need to write.

### The Rights That Create Engineering Requirements

| Right | Article | What You Must Build |
|---|---|---|
| **Access** | Art. 15 | API endpoint returning all data held about a user, in a readable format |
| **Rectification** | Art. 16 | Ability to update all instances of user data across every system |
| **Erasure** ("Right to be Forgotten") | Art. 17 | Hard delete across all systems — databases, caches, backups, third parties |
| **Portability** | Art. 20 | Export in machine-readable format (JSON, CSV) |
| **Restrict Processing** | Art. 18 | Flag to pause all processing of a user's data without deleting it |
| **Object** | Art. 21 | Opt out of specific processing (e.g., profiling, marketing) |

Think of each row as a ticket in your backlog. "Right to Erasure" isn't legal language — it's a deletion pipeline spanning your entire infrastructure. "Right to Access" is a DSAR endpoint that joins data from every service you run. "Right to Portability" is a JSON export format you need to design and version.

### Data Subject Access Request (DSAR) Endpoint

When a user asks "what data do you have about me?", you have one month to respond (GDPR Art. 12). The smart move is to build a self-service endpoint so users can get their data instantly without a support ticket.

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

Notice the `third_party_shares` field. Users have the right to know who received their data — not just what you hold. Your DPA tracking table (see below) feeds this. If you can't answer "who did we share this person's data with?", that's a compliance gap.

Also notice the re-authentication before export. You don't want an attacker who's hijacked a session to be able to download a user's entire data profile. Treat DSAR endpoints like password change — require fresh credentials.

### Lawful Basis for Processing

This is one of the most misunderstood parts of GDPR. You can't just say "we have consent for everything." You must identify the specific legal basis for each processing activity, and that basis determines what you can do with the data.

You **must** have one of these before processing any personal data:

| Basis | When to Use | Engineering Implication |
|---|---|---|
| **Consent** | User explicitly agrees | Store consent records; allow withdrawal |
| **Contract** | Necessary to fulfill a contract | Processing stops when contract ends |
| **Legitimate Interest** | Business need that doesn't override user rights | Document your balancing test |
| **Legal Obligation** | Law requires you to keep/process data | Retention rules override deletion requests |
| **Vital Interest** | Life-threatening situations | Rare; healthcare scenarios |
| **Public Interest** | Government/public authority functions | Unlikely for private companies |

The lawful basis matters for deletion. If you process transaction records under "legal obligation" (tax law requires 7-year retention), a user's erasure request under Art. 17 can't override it. But you still have to delete everything else — the email address, the name, anything not covered by the legal obligation. The engineering response is partial deletion: strip PII from tax records while retaining the financial figures. "Anonymize the record, retain the amount" is the pattern.

### Breach Notification

The 72-hour clock is ruthless. Most breach response teams spend the first 24 hours figuring out what happened. That leaves 48 hours to assess impact, draft the notification, and file it with your supervisory authority (ICO in the UK, CNIL in France, BSI in Germany, etc.). You need to have practiced this before it happens.

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

The British Airways breach took nine months to detect — the attackers had been exfiltrating customer payment data since June 2018. The breach happened because BA's website loaded JavaScript from a third-party domain that had been compromised. The ICO's reasoning in the £20 million fine was essentially: "You had the tools to prevent this; you chose not to use them." Chapter 5 covers supply chain security, subresource integrity, and Content Security Policy — all of which would have caught this specific attack.

### Data Processing Agreements (DPAs)

Every third-party vendor that touches user data needs a DPA. This is not optional. If Stripe processes payments, they're a data processor; you're the controller; you need a signed agreement specifying what they can do with that data and what their obligations are if there's a breach.

Build a vendor DPA registry and actually maintain it:

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

The `sub_processors` column matters. Sendgrid uses Amazon AWS. Stripe uses multiple cloud providers. Their sub-processors are *your* sub-processors for GDPR purposes. You need to know who they are, and your users have the right to know too.

Set a cron job to alert when `next_review_at` is approaching. Expired DPAs are a live compliance gap — you're processing data without legal authorization.

### Data Protection Impact Assessment (DPIA)

Required when processing is **likely to result in a high risk** to individuals. Don't wait for a regulator to ask for one — doing it proactively demonstrates good faith and often catches architecture problems before they're baked in.

Triggers for a required DPIA:
- Large-scale processing of sensitive data
- Systematic monitoring of public areas
- Automated decision-making with legal effects (credit scoring, hiring algorithms)
- New technology processing (biometrics, AI profiling)

The engineering artifact from a DPIA is a documented risk register: here's what we're doing, here's the risk, here's the mitigation. If the residual risk is still high after mitigations, you must consult your supervisory authority before proceeding. That's not a bug in the regulation — it's the point.

---

## 3. DATA CLASSIFICATION & PII

### What Counts as PII

The scope of "personal data" under GDPR is intentionally broad. If a piece of information can identify a person — alone or in combination with other data — it's personal data.

| Category | Examples | Risk Level |
|---|---|---|
| **Direct Identifiers** | Name, email, phone, SSN, passport number, driver's license | High |
| **Indirect Identifiers** | IP address, device ID, cookie ID, location data, browsing history | Medium-High |
| **Sensitive Data** (GDPR Art. 9) | Health, biometric, racial/ethnic origin, political opinions, sexual orientation, criminal records, trade union membership | Maximum |
| **Financial** | Credit card numbers, bank accounts, transaction history | High |
| **Authentication** | Passwords, security questions, MFA seeds | Critical |

IP addresses are personal data. This trips up a lot of engineers. Your server access logs that contain `192.168.1.1` — that's personal data under GDPR if it could be traced back to an individual. Which means your logs need retention limits, access controls, and deletion workflows. Yes, really. AWS CloudWatch logs retention settings are a GDPR compliance control.

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

Add classification metadata to your data stores. Tag your S3 buckets. Add a `data_classification` column to your tables if you have mixed data. Run automated scans to catch misclassified data. The gap between "this should be RESTRICTED" and "this is tagged INTERNAL because nobody thought about it" is where breaches live.

### Automated PII Detection

You can't protect PII you don't know about. And you have PII in places you don't expect: error logs that print full request objects, development databases copied from production, analytics pipelines that captured more than intended.

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

Run PII scanning in CI/CD. If a PR accidentally logs an email address in the error handler, catch it before it ships. Add a pre-commit hook or a CI step that scans changed files. The false positive rate will be annoying at first; tune your patterns.

### Data Mapping: Know Where ALL PII Lives

Article 30 of GDPR requires a "Record of Processing Activities" (ROPA) — essentially a data map. Even if you weren't legally required to maintain one, you'd want it anyway: it's the foundation of your deletion pipeline, your DSAR responses, and your breach impact assessment.

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

This table is the engineering artifact that turns "delete all user data" from a vague requirement into a checklist. Every row is a step in your deletion pipeline. Every missing row is a compliance gap. Maintain it in your wiki, review it quarterly, and gate new data store additions on getting added to the map.

---

## 4. CONSENT MANAGEMENT

### The Cookie Consent Mess — And How to Fix It

Most cookie banners are dark pattern theater. The "Accept All" button is huge and green. The "Manage Preferences" link is tiny gray text hidden in the footer. The preferences panel is a maze of toggles that all default to on. This isn't just ethically gross — it's legally invalid. The French data protection authority (CNIL) has explicitly ruled that consent obtained this way doesn't count.

Here's what valid consent actually looks like from an engineering perspective, starting with the legal requirements.

### Legal Requirements for Valid Consent

Consent must be: **freely given**, **specific**, **informed**, and **unambiguous**. Pre-ticked checkboxes are not valid consent under GDPR. "Freely given" means no penalty for refusing — if you gate access to your service on accepting analytics cookies, that's coercive, not consensual.

### Consent Storage Schema

This is the schema that lets you *prove* consent to a regulator. Every field matters.

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

The `consent_text` column is crucial and often forgotten. When you update your privacy policy, you need to know exactly what text a user agreed to at the time they consented. Store a snapshot. When a regulator asks "what exactly did user 12345 agree to on March 15, 2024?", you point to this row.

The `withdrawn_at` column pattern means you never delete consent records — you mark them withdrawn. This gives you an audit trail of consent history, which you need to demonstrate compliance.

### Granular Consent Implementation

One of the most common GDPR violations in consent implementation is bundling. You cannot ask users to consent to "analytics and marketing and personalization" as a single checkbox. Each purpose requires separate, explicit consent.

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

The `stopForPurpose` call on withdrawal is where most implementations fail. It's not enough to set the withdrawn flag in the database — you need to actually stop the processing. That means: remove from email marketing lists, stop sending analytics events, halt any ML pipeline that uses this user's data for training. The withdrawal has to propagate everywhere the consent was enabling.

### Cookie Consent (ePrivacy Directive)

| Cookie Category | Consent Required? | Examples |
|---|---|---|
| **Strictly Necessary** | No | Session cookies, CSRF tokens, load balancer cookies |
| **Analytics** | Yes | Google Analytics, Mixpanel, Amplitude |
| **Marketing / Advertising** | Yes | Facebook Pixel, Google Ads, retargeting |
| **Functional** | Yes (debatable by jurisdiction) | Language preferences, theme settings |

The "functional cookies" category is contested. Some regulators treat them as strictly necessary (they improve user experience without tracking for advertising), others require consent. Default to requiring consent and err toward user control.

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

The server-side enforcement here is important. Client-side banners can be dismissed, blocked by browser extensions, or simply bypassed. Your server needs to respect consent state independently of whether the banner was displayed correctly.

### Build vs. Buy

| Approach | Pros | Cons |
|---|---|---|
| **Build** | Full control, no vendor dependency, integrates perfectly with your data model | Engineering cost, must keep up with legal changes |
| **Buy** (OneTrust, Cookiebot, Osano) | Fast to deploy, auto-updates for legal changes, pre-built UIs | Cost, vendor lock-in, may not integrate cleanly with your consent-gated backend logic |
| **Hybrid** | Use a vendor for the UI/banner, build your own backend consent store | Best of both, moderate effort |

**Recommendation:** Hybrid. Use a vendor for the cookie banner (they track legal changes across jurisdictions). Build your own consent records table (you need it for backend enforcement anyway, and vendors typically don't give you the queryable data model you need for DSAR responses and deletion pipelines).

---

## 5. DATA RETENTION & DELETION

### Retention Is Not "Keep Forever"

The instinct in engineering is to keep everything. Storage is cheap. Future analytics might need it. Who knows what ML models you'll train in three years? This is the wrong instinct.

Data you retain is data you must secure, data you must delete on request, data that expands your breach impact, and data that might reveal things about users they didn't intend to share. "Data is the new oil" is a cliché, but the more complete analogy is: oil that you're legally required to clean up if it spills.

Keep data only as long as you have a legal basis to keep it. That means writing down retention periods before you collect the data.

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

Notice "Analytics (aggregated) — Indefinite." This is the core data strategy unlock: if you aggregate and anonymize, you're no longer processing personal data. The retention rules don't apply. This is why proper anonymization (Section 6) is so valuable — it lets you retain insights without retaining PII.

Notice also "Marketing consent — Indefinite — Never." Yes, you keep consent records forever. They're your legal defense that you had authorization to send those emails. Deleting consent records when a user requests erasure would be self-defeating.

### Automated Deletion Pipeline

Manual deletion is a compliance liability. A human will forget a step. A script runs the same way every time. The pattern is soft delete → grace period → hard delete, with a parallel pipeline across all your data stores.

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

Every step in `hard_delete_user` corresponds to a row in your data map. If your data map is incomplete, your deletion pipeline is incomplete. That's another reason the data map matters so much.

### Handling Backups — The Hardest Part

Backups are where GDPR deletion gets philosophically interesting. You can delete a user from your live database. But you took a backup last night, and that backup contains their data. Does the backup need to be updated? If so, how?

In practice, you have two engineering approaches:

| Approach | Pros | Cons |
|---|---|---|
| **Deletion Log** | Simple. After restoring a backup, re-run all deletions from the log. | Restoration is slower. Must always run post-restore script. |
| **Encrypted per-user backup segments** | True deletion (destroy user's key). | Complex. Only practical with crypto-shredding (see Section 7). |

The deletion log approach is the pragmatic choice for most teams. The key is making the post-restore script mandatory — ideally automated, triggered by whatever deploys the restored backup.

```python
# Post-backup-restore script: re-apply all deletions
async def post_restore_cleanup() -> None:
    """MUST run after every backup restore. Re-deletes all previously deleted users."""
    deleted_users = await db.fetch("SELECT user_id FROM deletion_log")
    for user in deleted_users:
        await hard_delete_user(user["user_id"])
    print(f"Post-restore cleanup: re-deleted {len(deleted_users)} users")
```

Supervisory authorities have generally accepted the deletion log approach as compliant — the spirit of the erasure right is that you can't actively use the data, not that every byte must be instantly vaporized from every backup tape. But you need to demonstrate the deletion was re-applied on restore. The `deletion_log` table is your proof.

---

## 6. ANONYMIZATION & PSEUDONYMIZATION

### The Re-identification Problem

Here's a counterintuitive fact about data privacy: **anonymization is much harder than it looks**. The Netflix Prize dataset makes this viscerally clear.

In 2006, Netflix released 100 million movie ratings from 500,000 subscribers — names replaced with random numbers — as a machine learning challenge. It was supposed to be fully anonymized. Researchers Narayanan and Shmatikoff took the dataset and cross-referenced it with IMDb reviews. By matching ratings, timestamps, and genres, they could identify specific individuals in the "anonymous" Netflix dataset with high confidence.

The problem: Netflix users who had also posted reviews to IMDb under their real names provided the linking data. The Netflix dataset wasn't really anonymous — it was pseudonymous, and the pseudonyms could be broken by correlation.

This is re-identification: you remove the obvious identifiers (name, email), but the combination of remaining attributes — age, ZIP code, movie preferences, rating timestamps — still uniquely identifies people. A 2000 study found that 87% of the US population can be uniquely identified by just ZIP code + gender + date of birth.

The implications for engineering: true anonymization is hard, and "removing the name and email" is not anonymization. It's pseudonymization, and you should treat it as still being personal data.

### Anonymization (Irreversible)

Properly anonymized data is **no longer personal data** under GDPR — you can keep it indefinitely without most of the regulatory obligations. Getting there requires techniques that genuinely destroy the link to individuals.

| Technique | Description | Example |
|---|---|---|
| **Generalization** | Replace precise values with ranges | Age 34 → Age 30-39 |
| **Suppression** | Remove the field entirely | Delete the `email` column |
| **Noise Addition** | Add random noise to values | Salary $85,000 → $83,000-$87,000 |
| **k-Anonymity** | Every record is indistinguishable from at least k-1 others | Min k=5 for any quasi-identifier combination |
| **l-Diversity** | Each equivalence class has at least l distinct sensitive values | Prevents attribute disclosure |
| **t-Closeness** | Distribution of sensitive attribute in any class is within t of the overall distribution | Prevents skewness attacks |

k-Anonymity is the workhorse here, and it's worth understanding concretely. Suppose you have medical records with Age, ZIP, and Diagnosis. If only one record has Age=34 and ZIP=02134, an attacker who knows you're 34 and live in that ZIP code can identify your diagnosis. k-Anonymity with k=5 requires that every combination of quasi-identifiers (Age, ZIP) appears in at least 5 records. You achieve this through generalization (34 → 30-39) and suppression.

Always assume an attacker has auxiliary data. Your users have public social media profiles, public records, IMDb reviews, and a thousand other data sources that can be used to break "anonymization" that isn't rigorous.

### Pseudonymization (Reversible)

Pseudonymized data is still personal data under GDPR (because it's reversible with the key), but it reduces risk and may allow processing under different legal bases — particularly valuable for analytics and ML where you need to track users over time without storing their raw PII in your analytics systems.

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

The HMAC approach has an elegant property: if you destroy the `secret_key`, the mapping becomes impossible to reverse. That's when pseudonymization converts to anonymization. This is the key insight behind crypto-shredding (Section 7): you encrypt PII with a key, and "deletion" means destroying the key.

### Data Masking for Non-Production Environments

This is a rule so important it deserves to be stated bluntly: **Production PII must NEVER exist in dev/staging environments.**

Every time a developer copies prod to staging "just to debug something real," they've created a compliance gap. Dev environments have weaker access controls. They're shared with contractors. They get backed up to places nobody audited. Developers accidentally log things in dev that they'd never log in prod.

The solution is a masking pipeline that you run every time you seed a non-production environment.

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

Tonic.ai and similar tools go further: they generate *synthetic* data that has the same statistical properties as real data (query plans work, distributions match, foreign key relationships are preserved) without containing any real PII. This is the gold standard for staging environments.

---

## 7. PRIVACY IN EVENT-SOURCED SYSTEMS

### The Immutability Paradox

This section sits at the intersection of Chapter 24 (database internals and event sourcing) and GDPR compliance, and it's one of the most technically interesting problems in privacy engineering.

Event sourcing says: **events are immutable facts — never delete them.** The append-only event log is the source of truth. You rebuild state by replaying events. Mutating or deleting events is architectural heresy — it breaks auditability, idempotency, and the fundamental contract of the pattern.

GDPR says: **delete this person's data when they ask.** Art. 17. Hard delete. Gone. Within 30 days of request.

These two requirements are in direct tension. You cannot both "never delete events" and "hard delete all user data on request." You have to choose — or you have to be clever about the architecture.

Three solutions exist, ranging from clever to pragmatic:

### Approach 1: Crypto-Shredding (Recommended)

The elegant solution. Encrypt PII in events with a per-user encryption key. To "delete" a user, destroy their key. The events remain but the PII within them is unreadable — effectively garbage data that cannot be linked to an individual.

This works because GDPR cares about *identifiable* personal data. An encrypted blob that cannot be decrypted without a destroyed key is no longer personal data — there's no feasible way to link it back to an individual. The event store is intact, replay works, and you've achieved functional deletion without touching the events themselves.

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

The key store itself needs serious engineering attention. AWS KMS, Azure Key Vault, and HashiCorp Vault are the production options — you want hardware-backed key storage with audit logs of every key usage and destruction. When a key is destroyed, that destruction event should be logged and immutable. The key reference in your events becomes a tombstone pointing at a destroyed key.

See Chapter 5 for key management best practices — the security chapter covers key rotation, KMS integration, and HSM usage that underpin this pattern.

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

**Downside:** Projections rebuilt from tombstoned streams will have gaps. Use only if you can tolerate incomplete replay. This also technically "mutates" the event store, which purists will object to — though for GDPR purposes the objection is moot.

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

This is actually the cleanest architectural approach for new systems — it never puts PII in the event store, so there's nothing to clean up. The events contain business data (amounts, item counts, references) and the PII store contains PII, and they're joined at query time. Deletion is a simple row delete in the PII store; the events are untouched.

The downside is that you lose the self-contained nature of events — you can't reconstruct full history from the event log alone. But for most systems, "full history with PII included" isn't actually what you need.

### Which Approach to Choose

| Approach | Complexity | Event Integrity | GDPR Compliance | Recommendation |
|---|---|---|---|---|
| **Crypto-shredding** | Medium | Events intact (PII unreadable) | Strong | **Use this for existing event-sourced systems** |
| **Tombstoning** | Low | Events modified (breaks replay) | Adequate | Fallback if crypto is too complex |
| **Separate PII store** | Low | Events never had PII | Strong | **Best for new systems** |

---

## 8. OTHER REGULATIONS

### CCPA / CPRA (California)

California's Consumer Privacy Act is GDPR's American cousin — similar goals, different mechanics. The fundamental difference: GDPR is opt-in (you need consent before collection), CCPA is opt-out (you can collect, but users can stop you from selling it).

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

The "Do Not Sell" right is about third-party data sharing for advertising — it doesn't require you to delete the data, just stop selling/sharing it. CCPA erasure rights are separate and narrower than GDPR's.

### HIPAA (Healthcare)

**Protected Health Information (PHI)** = any health data + a patient identifier. HIPAA is worth understanding even if you're not in healthcare, because its technical controls are a good baseline for any high-sensitivity data.

| Requirement | Engineering Control |
|---|---|
| **Encryption at rest** | AES-256 for databases, S3 SSE-KMS, encrypted EBS volumes |
| **Encryption in transit** | TLS 1.2+ everywhere, no exceptions |
| **Minimum necessary** | Role-based access; each role sees only the PHI needed for their function |
| **Audit logging** | Log every PHI access: who, what, when, from where |
| **BAAs** | Signed Business Associate Agreement with every vendor touching PHI |
| **Access controls** | Unique user IDs, automatic logoff, emergency access procedures |
| **Breach notification** | 60 days to notify HHS and affected individuals (500+ individuals → media notice) |

HIPAA doesn't have a standard fine schedule like GDPR — violations are tiered by culpability. "Did not know" is $100-$50,000 per violation. "Willful neglect — not corrected" is $50,000 per violation, maximum $1.9M per year for identical violations. Healthcare data breaches are uniquely damaging because health information can be used for discrimination, blackmail, and insurance fraud in ways that financial data can't.

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

The service eligibility list changes. AWS adds new services to the eligible list and occasionally removes them. Always check the current list before building HIPAA workloads — and sign a Business Associate Agreement (BAA) with AWS before processing any PHI, even on eligible services. Chapter 19 covers AWS compliance features in depth.

### SOC2

SOC2 is an **audit standard**, not a regulation. But customers (especially enterprise) require it, and "we're SOC2 Type II" unlocks sales conversations that "we take security seriously" cannot.

The key distinction that trips up many teams: SOC2 is not something you implement once and have forever. It's an ongoing operational discipline that you demonstrate over a period. Type II audits cover 3-12 months of continuous operation — the auditors want to see that your controls weren't just running on audit day but every day.

| Trust Service Criteria | What Auditors Check | Engineering Controls |
|---|---|---|
| **Security** | Unauthorized access prevention | MFA, encryption, WAF, network segmentation |
| **Availability** | System uptime and reliability | Monitoring, incident response, DR plan |
| **Processing Integrity** | Accurate, complete processing | Input validation, reconciliation, testing |
| **Confidentiality** | Confidential data protection | Access controls, encryption, data classification |
| **Privacy** | PII handling per commitments | Consent management, retention, deletion |

**SOC2 Type I** = controls are designed correctly (point-in-time snapshot). Faster and cheaper, but enterprise buyers often don't accept it.
**SOC2 Type II** = controls operated effectively over a period (3-12 months). More valuable; customers prefer it. Budget 6-12 months from starting your prep to getting your report.

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

Vanta and Drata pay for themselves within the first audit cycle. Manual evidence collection for a SOC2 audit typically consumes weeks of engineering and legal time. The automation tools continuously monitor your controls and automatically pull evidence artifacts when your auditor requests them.

### PCI DSS (Payment Card Data)

**Goal: reduce scope.** This is the single most important concept in PCI compliance. If card numbers never touch your servers, PCI compliance is dramatically simpler. If they do, you're looking at hundreds of controls across physical security, network architecture, code review, and vulnerability scanning.

| Approach | PCI Scope | Effort |
|---|---|---|
| **Stripe / Braintree hosted payment page** | SAQ A (minimal) | Low |
| **Stripe Elements (JS SDK)** | SAQ A-EP | Low-Medium |
| **Direct card handling** | SAQ D (full audit) | Very High |

The math is stark. SAQ A is 12 questions. SAQ D is hundreds of requirements. Every company that handles payments should default to SAQ A unless they have a compelling, specific reason to go otherwise.

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

Even if your backend never stores card numbers, passing them through is enough to bring you into scope. Your server receiving `card_number` in a request body — even if you immediately forward it to Stripe — means you're in PCI scope. Use Stripe Elements or Stripe Checkout to ensure card numbers only go directly from the user's browser to Stripe's servers.

---

## 9. AUDIT LOGGING & COMPLIANCE

### What to Log

Audit logs serve three masters: security (who did what, detect attacks), compliance (prove you're following the rules), and debugging (what happened when something went wrong). The key is designing them for all three uses at once.

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

The `changes` array with masked PII is subtle but important. You want to log that a user's email was changed (compliance: who changed what, when), but you don't want the audit log itself to contain the old and new email addresses in plain text (the audit log might have different retention and access rules than the user table). Log the field name and mask the values.

### Immutable Audit Log Storage

Audit logs that can be modified by an attacker — or by an administrator with something to hide — aren't audit logs. They're editable histories. The tamper-evidence property is not optional.

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

S3 Object Lock in COMPLIANCE mode is the strongest option — not even AWS support can delete an object before the retention date expires. This is the right choice for SOX or HIPAA audit logs. GOVERNANCE mode allows admins with special IAM permissions to override; use this when you need the immutability guarantee but need the escape hatch.

### Retention Requirements by Regulation

| Regulation | Retention Period | What to Retain |
|---|---|---|
| **SOX** (Sarbanes-Oxley) | 7 years | Financial audit trails |
| **HIPAA** | 6 years | PHI access logs |
| **GDPR** | As long as processing continues | Processing activity records, consent records |
| **PCI DSS** | 1 year | Cardholder data access logs |
| **SOC2** | Per audit period (typically 1 year) | All controls evidence |

These retention periods can conflict with data minimization principles. You want to minimize data, but you're legally required to keep audit logs for 7 years. The resolution: audit logs are themselves a lawful retention basis ("legal obligation"). They get their own retention policy, separate from the user data they reference.

### Anomaly Detection on Audit Logs

A compliance audit log that nobody reads is just a liability waiting to happen. You need active monitoring — alerts that fire when something looks wrong.

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

These queries are the difference between a compliance audit log and a security monitoring system. Run them on a schedule, send alerts to your incident response pipeline. The "bulk data export" rule catches both compromised accounts and insider threats. The "permission escalation" rule catches privilege escalation attacks. The "off-hours PII access" rule catches both suspicious behavior and legitimate-but-risky late-night admin work that should be questioned.

---

## 10. ETHICAL ENGINEERING

### Beyond Compliance

Compliance is the floor, not the ceiling. GDPR didn't exist in 2006 when the Netflix Prize dataset was released, and the re-identification attack that followed was entirely legal. "It doesn't violate any laws" and "it's not harmful" are not the same sentence.

The most sophisticated privacy failures of the last decade weren't illegal — they were architecturally enabling harm that the designers either didn't anticipate or chose not to think about. Cambridge Analytica didn't hack Facebook; they used Facebook's API as designed. Predatory payday lending algorithms that charged higher rates to people from predominantly Black ZIP codes weren't passing race as a feature — they were using geographic and behavioral proxies that correlated with race. The harm was real; the violation was subtle.

Your job as an engineer isn't just to implement requirements. It's to think about what you're building and whether you'd be comfortable explaining it to the people it affects.

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

The 80% rule (also called the four-fifths rule) comes from US employment discrimination law: if a selection rate for any group is less than 80% of the highest selection rate, it's evidence of adverse impact. This applies to algorithmic decisions too — hiring algorithms, credit scoring, insurance pricing, housing applications.

Amazon famously built and then scrapped a recruiting algorithm in 2018 because it systematically downgraded resumes that included the word "women's" (as in "women's chess club") and penalized graduates of all-women's colleges. The model was trained on historical hiring data from a tech industry that had historically hired mostly men. It learned to replicate that bias with mathematical precision.

### Dark Patterns to Avoid

These patterns are worth enumerating because they feel like clever UX and often are suggested in product meetings by well-meaning people who don't realize the implications.

| Dark Pattern | Example | Why It's Wrong |
|---|---|---|
| **Confirm-shaming** | "No thanks, I don't want to save money" | Manipulates through guilt |
| **Roach motel** | Easy to sign up, impossible to delete account | Violates GDPR Art. 17 |
| **Hidden costs** | Fees revealed only at checkout | Deceptive |
| **Forced continuity** | Free trial → auto-charges with no warning | Often illegal |
| **Privacy zuckering** | Confusing settings that default to maximum data sharing | Violates GDPR consent requirements |
| **Trick questions** | Double negatives in opt-out checkboxes | Invalid consent |

"Privacy zuckering" is named after a specific design philosophy: make privacy settings so complicated and buried that users give up and accept the default (maximum data sharing). CNIL has explicitly ruled that this kind of design doesn't produce valid GDPR consent. Dark patterns in consent interfaces have cost companies real money: in 2022, Google paid $391 million to 40 US states to settle claims about deceptive location tracking.

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

You write the code — you share the responsibility. Engineers are not just order-takers, and "I was just implementing the requirements" is not a career-safe position when a company faces a $5 billion FTC fine or a Congressional hearing.

The engineers who worked on Facebook's news feed algorithms knew they were optimizing for engagement over accuracy. Some of them raised concerns internally. Some of them left. The ones who stayed and kept shipping bear some portion of the moral weight for the outcomes.

This isn't about being precious or anti-business. It's about recognizing that technical decisions have consequences that extend beyond the sprint, and you are one of the people with the clearest view of those consequences.

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

Use this as a starting point for any new project or privacy audit. The goal is to be able to check every box before launch, not to use it as a retroactive gap analysis after something goes wrong.

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

## The Companies That Got It Right

It's worth ending with examples of privacy done well, because the narrative around privacy engineering is dominated by failure stories.

**Apple's differential privacy** deployment is one of the most elegant applied cryptography stories in software engineering. When Apple wants to know which emojis are most used, they use differential privacy — adding calibrated noise to the data at the device level before it's sent, so Apple gets accurate aggregate statistics but can't reconstruct any individual's behavior. The math is real, the implementation ships in iOS, and it's the kind of "privacy AND functionality" tradeoff that Cavoukian's Principle 4 is about.

**Signal's sealed sender** mechanism is another: when you send a message, even Signal's servers can't tell who sent it — the sender's identity is encrypted to the recipient's key. Signal has architecture decisions that make certain surveillance requests physically impossible to comply with, because the data simply doesn't exist.

**Basecamp's decision not to have analytics** is a business stance, not just a privacy one — they explicitly chose not to track individual user behavior, which means they can't be compelled to hand it over, can't suffer a breach of it, and don't have to build deletion pipelines for it. "The most private data is data you never collect" is privacy by design taken to its logical conclusion.

These aren't flukes. They're engineering decisions made early, consistently, and at some product cost — and they've become competitive advantages. Users trust these products specifically because of their privacy posture.

The opportunity for you: privacy done well is increasingly a product feature, not just a compliance burden. Build the deletion pipelines, the consent management, the crypto-shredding — not because the ICO might fine you, but because you're building something people should be able to trust.

---

> **Next Steps:** With privacy infrastructure in place, Chapter 5 covers the broader security engineering foundations that underpin these controls — the encryption primitives, key management, authentication systems, and security architecture that make everything in this chapter actually work. For database-level implementation of retention policies, deletion cascades, and the event sourcing patterns behind crypto-shredding, see Chapter 24.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M79: Data Privacy & GDPR](../course/modules/loop-3/L3-M79-data-privacy-gdpr.md)** — Implement GDPR-compliant deletion, consent management, and data subject access requests in TicketPulse
- **[L2-M52: Data Pipelines](../course/modules/loop-2/L2-M52-data-pipelines.md)** — Build data pipelines that enforce privacy controls at the ingestion layer, not as an afterthought

### Quick Exercises

1. **Map every place your system stores PII: search your codebase for email, name, address, phone, and IP address — then check whether each storage location has a documented retention period and deletion path.**
2. **Check if your team has a data retention policy: find the oldest user record in your database and ask whether you have a legitimate reason to still hold it under your privacy policy.**
3. **Implement one crypto-shredding key for a user record: generate a per-user encryption key, encrypt the PII fields with it, store the key separately, and verify that deleting the key makes the data unrecoverable.**

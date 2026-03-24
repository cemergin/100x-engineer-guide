# L3-M74: War Stories Analysis

> ⏱️ 60 min | 🟢 Core | Prerequisites: L3-M73 (Incident Response Simulation)
> Source: Chapter 26 of the 100x Engineer Guide

## What You'll Learn

- How to extract engineering lessons from real-world outages and apply them to your own systems
- The causal chain analysis technique: triggers, contributing factors, missing safeguards
- How to build a vulnerability checklist from other people's disasters
- The patterns that appear across every major incident: blast radius, defense in depth, human factors

## Why This Matters

Every major outage has already happened to someone else. Cloudflare, GitHub, Knight Capital, Facebook -- they all published detailed postmortems. The engineer who studies these does not need to make the same mistakes. The engineer who ignores them will.

TicketPulse is not Cloudflare. But the failure modes are universal. Regex backtracking, database inconsistency, partial deployments -- these can happen to any system at any scale. The question is not "could this happen to us?" but "what would happen when it does?"

> 💡 **Insight**: "Sidney Dekker, the human factors researcher, argues that we should study incidents not to find the 'root cause' but to understand the system conditions that made failure likely. The cause is never a single mistake. It is always a system that allowed the mistake to propagate."

---

## War Story 1: Cloudflare's Regex Outage (2019)

### What Happened

**Date:** July 2, 2019
**Duration:** 27 minutes
**Impact:** Every Cloudflare-proxied website worldwide returned 502 errors. Cloudflare serves ~10% of all HTTP requests globally.

A WAF (Web Application Firewall) rule was deployed containing a regular expression with catastrophic backtracking. The regex was:

```
(?:(?:\"|'|\]|\}|\\|\d|(?:nan|infinity|true|false|null|undefined|symbol|math)|\`|\-|\+)+[)]*;?((?:\s|-|~|!|{}|\|\||\+)*.*(?:.*=.*)))
```

When this regex was applied to certain HTTP request payloads, it caused the regex engine to enter an exponential backtracking loop, consuming 100% CPU on every edge server globally.

### The Causal Chain

```
1. TRIGGER: New WAF rule deployed with a pathological regex
     │
2. CONTRIBUTING: WAF rules bypassed the normal code review and
   │  testing pipeline (treated as "configuration," not "code")
     │
3. MISSING SAFEGUARD: No regex complexity analysis tool
   │  (would have caught the nested quantifiers)
     │
4. MISSING SAFEGUARD: No canary deployment for WAF rules
   │  (the rule went to 100% of servers simultaneously)
     │
5. AMPLIFIER: The WAF runs inline on every HTTP request
   │  (not async, not sampled -- every single request)
     │
6. RECOVERY OBSTACLE: The global deploy system was itself
   proxied through Cloudflare and was partially unavailable
```

### Key Lesson: Catastrophic Backtracking

Regular expressions with nested quantifiers can have exponential time complexity.

```
SAFE:      /\d+/             → Linear: O(n)
SAFE:      /[a-z]+@[a-z]+/   → Linear: O(n)
DANGEROUS: /(a+)+b/          → Exponential: O(2^n)
DANGEROUS: /(.*)+/           → Exponential: O(2^n)
DANGEROUS: /(\w+\s?)+$/      → Exponential: O(2^n)
```

The pattern is nested quantifiers: a quantifier inside a group that itself has a quantifier. When the regex engine fails to match, it backtracks through every possible combination.

### 📐 Design: Apply to TicketPulse

Answer these questions about TicketPulse:

```
CLOUDFLARE VULNERABILITY CHECK
──────────────────────────────

1. Where does TicketPulse use regex?
   □ Input validation (email, phone, event names)
   □ Search queries (user-provided patterns)
   □ Log parsing / filtering
   □ Rate limiting rules
   □ WAF / security rules

2. Are any of these user-supplied regex?
   □ If yes: does TicketPulse set execution time limits?
   □ If yes: does TicketPulse validate regex complexity before execution?

3. Does TicketPulse have canary deployments for config changes?
   □ Feature flags: canary? or all-at-once?
   □ Rate limiting rules: canary? or all-at-once?
   □ Database migrations: canary? or all-at-once?

4. What code in TicketPulse bypasses the normal deploy pipeline?
   □ Feature flags / config changes
   □ Database migrations
   □ Infrastructure changes (Terraform, K8s manifests)
   □ Third-party SDK updates
```

### 🛠️ Build: Regex Safety Check

If TicketPulse uses regex for input validation, audit the patterns:

```typescript
// Audit: find all regex in the codebase
// grep -rn "new RegExp\|/.*/" --include="*.ts" src/

// For each regex found, check:
// 1. Does it have nested quantifiers? (a+)+ or (a*)*
// 2. Is the input bounded? (max length check before regex)
// 3. Is there a timeout? (regex execution time limit)

// SAFE PATTERN: validate input length BEFORE regex
function validateEventName(name: string): boolean {
  if (name.length > 200) return false; // Bound the input
  return /^[\w\s\-.']+$/.test(name);   // Simple character class, no backtracking risk
}

// DANGEROUS PATTERN: unbounded input + complex regex
function validateDescription(desc: string): boolean {
  // No length check
  return /^(\w+\s?)+$/.test(desc); // Nested quantifier -- exponential on non-matching input
}
```

---

## War Story 2: GitHub's Database Incident (2018)

### What Happened

**Date:** October 21, 2018
**Duration:** 24 hours, 11 minutes
**Impact:** GitHub was degraded for over 24 hours. Users saw inconsistent data, stale information, and partial functionality.

A routine network maintenance caused a 43-second connectivity loss between the US East Coast primary database cluster and the US West Coast replicas. The database failover system promoted a West Coast replica to primary. When connectivity was restored, the original primary and the new primary had divergent data -- 43 seconds of writes existed on each that did not exist on the other.

### The Causal Chain

```
1. TRIGGER: 43-second network partition during maintenance
     │
2. AUTOMATIC: Orchestrator (failover tool) promoted a replica
   │  to primary -- as designed
     │
3. THE PROBLEM: The original primary was still accepting writes
   │  during the partition (split-brain)
     │
4. RESULT: Two databases with divergent data
   │  - Original primary: had 43 seconds of writes
   │  - New primary: had 43 seconds of different writes
     │
5. RECOVERY: Restoring consistency required replaying writes
   │  from both databases in the correct order
     │
6. DURATION: The replay and validation took 24+ hours
   because they had to verify every row for consistency
```

### Key Lesson: Automated Failover Is Not Free

```
THE FAILOVER PARADOX
────────────────────
- Manual failover is slow → longer outages
- Automatic failover is fast → risk of split-brain

GitHub chose automatic failover for speed.
The 43-second partition triggered it correctly.
But "correctly" still caused 24 hours of inconsistency.

The lesson: automatic failover needs FENCING.
The old primary must be PREVENTED from accepting writes
before the new primary starts. Without fencing, you get
split-brain.
```

### 📐 Design: Apply to TicketPulse

```
GITHUB VULNERABILITY CHECK
──────────────────────────

1. What happens to TicketPulse if the Postgres primary
   and replica diverge?
   □ Do we use automatic failover? (e.g., Patroni, RDS Multi-AZ)
   □ If yes: is the old primary fenced (prevented from writes)?
   □ If no: how long does manual failover take?

2. Can TicketPulse tolerate stale reads?
   □ Event catalog: stale for 30 seconds? (probably fine)
   □ Ticket inventory: stale for 30 seconds? (overselling risk)
   □ Payment records: stale for 30 seconds? (double-charge risk)

3. What is the data consistency model?
   □ Do we use read replicas for ticket availability checks?
   □ If yes: is there a risk of selling tickets that are already sold?
   □ What is the maximum acceptable replication lag?

4. How would we detect data divergence?
   □ Do we have consistency checks that compare primary and replica?
   □ Do we audit financial records for mismatches?
   □ How long would it take to discover inconsistency?
```

### 🛠️ Build: Consistency Check Design

Sketch a consistency verification approach for TicketPulse:

```
CONSISTENCY CHECK: Ticket Inventory
───────────────────────────────────
Every 60 seconds:
  1. Query primary: SELECT event_id, COUNT(*) as sold FROM tickets
     WHERE status = 'sold' GROUP BY event_id
  2. Query replica: same query
  3. Compare results
  4. If any event_id has a mismatch > 0:
     - Alert immediately
     - Log the divergent event_ids
     - Optionally: pause ticket sales for affected events
       until consistency is confirmed

This catches replication lag AND split-brain scenarios.
```

---

## War Story 3: Knight Capital ($440M Bug, 2012)

### What Happened

**Date:** August 1, 2012
**Duration:** 45 minutes
**Impact:** Knight Capital lost $440 million in 45 minutes. The company was bankrupt within days.

Knight Capital was deploying new trading software to 8 servers. A technician deployed to only 7 of 8. The 8th server still had an old version that contained dead code -- a test function called "Power Peg" that had been repurposed but never removed. When the new trading day started, the 8th server activated the dead code, which began making millions of unintended stock trades at maximum speed.

### The Causal Chain

```
1. TRIGGER: Partial deployment (7 of 8 servers updated)
     │
2. CONTRIBUTING: Dead code left in the codebase
   │  (Power Peg function was supposed to be removed years ago)
     │
3. CONTRIBUTING: The deployment reused an old feature flag
   │  that the dead code checked -- the new deployment
   │  inadvertently activated the dead code on the old server
     │
4. MISSING SAFEGUARD: No verification that all servers
   │  received the deployment
     │
5. MISSING SAFEGUARD: No kill switch to halt trading
   │  (it took 45 minutes to stop the bleeding)
     │
6. MISSING SAFEGUARD: No automated detection of anomalous
   trading patterns (millions of trades in minutes)
```

### Key Lessons

```
KNIGHT CAPITAL LESSONS
──────────────────────

1. DEAD CODE KILLS
   Code that is "not used anymore" but still exists in the
   codebase is a landmine. Delete it. Version control
   remembers everything.

2. VERIFY DEPLOYMENTS REACH EVERY INSTANCE
   "We deployed" is not the same as "every server is running
   the new version." Verify. Automatically.

3. KILL SWITCHES ARE NOT OPTIONAL
   If your system can cause unbounded damage, you need a way
   to stop it in seconds, not minutes.

4. FEATURE FLAGS MUST BE CLEANED UP
   Reusing old feature flags for new purposes is a recipe for
   exactly this kind of disaster.
```

### 📐 Design: Apply to TicketPulse

```
KNIGHT CAPITAL VULNERABILITY CHECK
───────────────────────────────────

1. Does TicketPulse have dead code?
   □ Old feature flags that are no longer used?
   □ Commented-out code blocks?
   □ Unused API endpoints still registered?
   □ Old migration code that could be re-triggered?

2. Do we verify deployments reach ALL instances?
   □ After a rolling deploy, do we check that every pod
     is running the expected version?
   □ kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}'
   □ Is this check automated in CI/CD?

3. Do we have kill switches?
   □ Can we disable ticket purchases instantly? (feature flag)
   □ Can we disable payment processing instantly?
   □ Can we put the system in read-only mode?
   □ How long does it take to activate a kill switch?

4. Can TicketPulse cause unbounded financial damage?
   □ Is there a maximum charge amount per transaction?
   □ Is there a maximum number of tickets per user per event?
   □ Is there rate limiting on the purchase API?
   □ If a bug caused duplicate charges, how quickly would
     we detect it?
```

### 🛠️ Build: Kill Switch Design

```typescript
// TicketPulse Kill Switches -- feature flags that can be
// toggled in seconds without a deployment

interface KillSwitches {
  // Immediately disable all purchases
  purchasesEnabled: boolean;

  // Disable payment processing (queue purchases for later)
  paymentProcessingEnabled: boolean;

  // Put system in read-only mode
  readOnlyMode: boolean;

  // Disable specific payment providers
  stripeEnabled: boolean;
  paypalEnabled: boolean;

  // Rate limiting overrides
  maxPurchasesPerMinute: number;
  maxPurchasesPerUserPerHour: number;
}

// These should be:
// - Stored in a fast config store (Redis, LaunchDarkly, etc.)
// - Changeable WITHOUT a deployment
// - Audited (who changed what, when)
// - Tested regularly (a kill switch you have never tested
//   is a kill switch that does not work)
```

---

## 🛠️ Build: TicketPulse Vulnerability Checklist

Synthesize lessons from all three war stories into a checklist that any team could use to audit TicketPulse.

```
TICKETPULSE VULNERABILITY CHECKLIST
════════════════════════════════════

Derived from: Cloudflare (2019), GitHub (2018), Knight Capital (2012)

 #  │ Question                                          │ Y/N │ Action
────┼───────────────────────────────────────────────────┼─────┼────────────
 1  │ Can a config change take down ALL instances        │     │
    │ simultaneously? (no canary for config)             │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 2  │ Do we verify that deployments reach every          │     │
    │ instance? (version check post-deploy)              │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 3  │ Can we roll back ANY service in under 5 minutes?   │     │
    │ (tested, not theoretical)                          │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 4  │ Do we have kill switches for critical flows?       │     │
    │ (purchases, payments, notifications)               │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 5  │ Is there dead code in the codebase that could      │     │
    │ be accidentally activated?                         │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 6  │ Are database failovers tested and fenced?          │     │
    │ (split-brain prevention verified)                  │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 7  │ Do we validate regex/query complexity before       │     │
    │ deploying to production?                           │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 8  │ Are infrastructure changes (Terraform, K8s,        │     │
    │ feature flags) reviewed like code changes?         │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
 9  │ Can we detect anomalous behavior automatically?    │     │
    │ (unusual purchase rates, unexpected charges)       │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
10  │ Is there a maximum financial exposure per          │     │
    │ transaction / per minute? (rate + amount limits)   │     │
────┼───────────────────────────────────────────────────┼─────┼────────────
```

For each "No" answer, write an action item with an owner and a due date. This checklist should be revisited quarterly.

---

## 🤔 Final Reflections

1. **Which of these failure modes is TicketPulse MOST vulnerable to right now?** Not the theoretical worst case -- the most likely one given the current state of the system.

2. **All three companies had talented engineers. Why did these incidents still happen?** What does that tell you about the relationship between individual skill and system safety?

3. **Cloudflare's outage lasted 27 minutes. GitHub's lasted 24 hours. Knight Capital's lasted 45 minutes but was financially fatal.** What made the difference in recovery time? What determines whether an incident is recoverable?

4. **If you could invest in only ONE safeguard for TicketPulse, derived from these war stories, what would it be?** Justify your choice.

5. **These are all "famous" incidents because the companies published postmortems.** What happens at companies that do not publish postmortems? Do they learn less?

---

## Further Reading

- **Cloudflare Blog**: "Details of the Cloudflare outage on July 2, 2019" -- the full postmortem
- **GitHub Blog**: "October 21 post-incident analysis" -- the complete incident report
- **SEC Filing on Knight Capital**: the official regulatory report on the $440M loss
- **Chapter 26**: Full analysis of these incidents plus Slack, Facebook/Meta, CrowdStrike, GitLab, and Stripe
- **"Normal Accidents" by Charles Perrow**: the theory of why complex, tightly-coupled systems inevitably fail
- **"The Field Guide to Understanding Human Error" by Sidney Dekker**: why blame is counterproductive

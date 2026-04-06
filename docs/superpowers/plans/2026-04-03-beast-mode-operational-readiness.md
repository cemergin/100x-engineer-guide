# Beast Mode — Operational Readiness from Day One: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write Chapter 36 (Beast Mode — Operational Readiness from Day One) and 4 companion course modules (L3-M91 through L3-M91c) following the guide's existing conventions.

**Architecture:** One new chapter file in `part-2-applied-engineering/`, four new course module files in `course/modules/loop-3/`, updates to `README.md`, `part-2-applied-engineering/README.md`, and `course/course.yaml` to register the new content.

**Tech Stack:** Markdown, YAML

**Spec:** `docs/superpowers/specs/2026-04-03-beast-mode-operational-readiness-design.md`

---

### Task 1: Create Chapter 36 — Sections 0-2 (Priority Triage, Access & Toolchain, System Mental Model)

**Files:**
- Create: `part-2-applied-engineering/36-beast-mode.md`

- [ ] **Step 1: Create the chapter file with metadata, intro, and sections 0-2**

Write the file with the HTML metadata comment block, chapter title, "In This Chapter" index, "Related Chapters" cross-references, and full content for:
- Section 0: Priority Triage (the "2 hours, 5 things" quick-hit)
- Section 1: Access & Toolchain (source code, cloud consoles, observability, CI/CD, secrets, communication, end-to-end verification)
- Section 2: System Mental Model (5-min architecture sketch, data flow tracing, dependency mapping, "what can kill us" list, read the IaC)

The chapter metadata block must follow this exact format:
```html
<!--
  CHAPTER: 36
  TITLE: Beast Mode — Operational Readiness from Day One
  PART: II — Applied Engineering
  PREREQS: None (Ch 12, 18 helpful)
  KEY_TOPICS: operational readiness, onboarding, codebase navigation, observability setup, incident readiness, system mental models, dashboard quicklinks, tribal knowledge extraction
  DIFFICULTY: All levels
  UPDATED: 2026-04-03
-->
```

The intro paragraph should open with the Nick Hook philosophy: your studio is pre-wired before the session starts. Include the "metrics and infra don't lie" core principle early.

Each subsection should follow the guide's convention:
- **What it is:** / **Why it matters:** / **The checklist:** / **Real-world example:** (adapted from the usual What/When/Trade-offs/Example pattern to fit a checklist-oriented chapter)

Include concrete commands, URLs patterns, and tool examples throughout. For example:
- `git log --oneline -20` to see recent changes
- AWS Console bookmark patterns (ECS, CloudWatch, RDS)
- Example Datadog/Grafana log queries
- `docker compose up` / `make dev` verification steps
- Example Terraform file reading to understand infra

Target: ~800 lines for this file so far.

- [ ] **Step 2: Verify the file renders correctly**

Run: `head -30 part-2-applied-engineering/36-beast-mode.md`
Expected: HTML metadata block and chapter title visible.

- [ ] **Step 3: Commit**

```bash
git add part-2-applied-engineering/36-beast-mode.md
git commit -m "Add Ch 36 Beast Mode: sections 0-2 (triage, access, mental model)"
```

---

### Task 2: Chapter 36 — Sections 3-4 (Observability & Dashboards, Codebase Navigation)

**Files:**
- Modify: `part-2-applied-engineering/36-beast-mode.md`

- [ ] **Step 1: Append sections 3 and 4 to the chapter file**

**Section 3: Observability & Dashboards** — "Your eyes and ears."
- Golden signals dashboard (latency, error rate, traffic, saturation)
- Learning what "normal" looks like — spend 15 min staring at dashboards
- The hotlinks list — bookmarkable quick-access list with specific examples:
  - Primary service dashboard
  - Error rate / exception tracker (Sentry, Datadog APM)
  - Logs filtered to team services
  - Deployment tracker
  - Database metrics (connections, query latency, replication lag)
  - Queue depth (Kafka/SQS — early warning)
  - Cost dashboard
- Alerts topology — who gets paged, thresholds, routing, escalation
- "Metrics don't lie" principle — observable truth over documented intention

Include a concrete example table: "Your Beast Mode Hotlinks Template" with columns for Category, Tool, URL Pattern, What to Look For.

**Section 4: Codebase Navigation** — "Reading the terrain, not every leaf."
- Entrypoint mapping (route handlers, event consumers, cron jobs)
- "Grep your way in" technique — start from error messages, API endpoints, log lines
- Identify architectural layers
- Spot load-bearing code with `git log --format='%H' -- <file> | wc -l`
- The archaeology layer — identifying legacy code boundaries

Include practical command examples:
```bash
# Find the most-changed files in the last 6 months
git log --since="6 months ago" --name-only --pretty=format: | sort | uniq -c | sort -rn | head -20

# Find all route/endpoint definitions
grep -rn "app.get\|app.post\|router\.\|@Get\|@Post\|@RequestMapping" src/

# Find where an error message originates
grep -rn "Payment processing failed" src/
```

Target: ~500 additional lines.

- [ ] **Step 2: Verify file length is growing**

Run: `wc -l part-2-applied-engineering/36-beast-mode.md`
Expected: ~1300 lines

- [ ] **Step 3: Commit**

```bash
git add part-2-applied-engineering/36-beast-mode.md
git commit -m "Add Ch 36 sections 3-4 (observability, codebase navigation)"
```

---

### Task 3: Chapter 36 — Sections 5-6 (Incident Readiness, Team & Tribal Knowledge)

**Files:**
- Modify: `part-2-applied-engineering/36-beast-mode.md`

- [ ] **Step 1: Append sections 5 and 6**

**Section 5: Incident Readiness** — "The fire drill you run before the fire."
- The first 5 minutes script (literal step-by-step flowchart)
- "What changed?" reflex — 90% of incidents are caused by a change
- Rollback muscle memory — know the command before you need it
- Communication during incidents — be useful, not the hero
- Shadow on-call — apprenticeship model
- Build your personal runbook

Include a decision tree in ASCII:
```
PAGED → Open primary dashboard
        ├── Metrics normal? → Check if alert is stale/resolved
        └── Metrics abnormal?
            ├── Check recent deployments
            │   └── Deploy in last 30 min? → Candidate for rollback
            ├── Check error logs
            │   └── New error type? → Likely code change
            ├── Check traffic
            │   └── Spike? → Likely load issue
            └── Check dependencies
                └── External service down? → Likely upstream
```

Include a "Rollback Cheat Sheet" table:
| Deployment Method | Rollback Command | Time to Effect |
|---|---|---|
| Git + CI/CD | `git revert <sha> && git push` | ~5 min (pipeline) |
| Feature flags | Kill switch in LaunchDarkly/Split | ~30 sec |
| Container (ECS/K8s) | Redeploy previous image tag | ~2 min |
| Serverless (Lambda) | Point alias to previous version | ~30 sec |

**Section 6: Team & Tribal Knowledge** — "The stuff that isn't written down."
- The three conversations (tech lead, longest-tenured, on-call engineer)
- Meeting archaeology — last month of retros, postmortems, meeting notes
- Known unknowns — the team's tech debt list
- Document what you learn — newcomer superpower of fresh eyes

Include specific question templates for each conversation.

Target: ~500 additional lines.

- [ ] **Step 2: Commit**

```bash
git add part-2-applied-engineering/36-beast-mode.md
git commit -m "Add Ch 36 sections 5-6 (incident readiness, tribal knowledge)"
```

---

### Task 4: Chapter 36 — Section 7 (Beast Mode Checklist) and Closing Narrative

**Files:**
- Modify: `part-2-applied-engineering/36-beast-mode.md`

- [ ] **Step 1: Append section 7 and closing scenario**

**Section 7: The Beast Mode Checklist** — A condensed, single-page, printable checklist.

Format as a markdown checkbox list grouped by the 6 domains:

```markdown
### Access & Toolchain
- [ ] Repo cloned, builds locally, tests pass
- [ ] Cloud console access verified (logged in, can see resources)
- [ ] Observability tool access (Datadog/Grafana — ran a query)
- [ ] CI/CD pipeline understood (found a recent deployment)
- [ ] Secrets system identified (know where, don't need every value)
- [ ] Communication channels joined (team, incidents, deploys)
- [ ] Pushed a trivial change through the full pipeline to production
```

(Continue for all 6 domains, ~5-7 items each)

**Closing: "It's Your First Week and There's an Outage"**

A ~2 page narrative walkthrough. Write it in second person present tense ("You're sitting at your desk..."). The scenario:
- Engineer is 4 days into a new job
- Gets paged for a latency spike on the order service
- Uses their bookmarked dashboard to see the golden signals
- Checks "what changed?" — spots a deploy from 20 minutes ago
- Communicates in the incident channel with what they see
- Suggests a rollback based on the timing correlation
- Senior engineer confirms, rollback happens, metrics recover
- Engineer takes timeline notes, contributes to the postmortem

The narrative should reference specific techniques from earlier sections (hotlinks, "what changed?" reflex, communication protocol, rollback knowledge).

Target: ~400 additional lines. Total chapter: ~2200-2500 lines.

- [ ] **Step 2: Verify total file length**

Run: `wc -l part-2-applied-engineering/36-beast-mode.md`
Expected: ~2200-2500 lines

- [ ] **Step 3: Commit**

```bash
git add part-2-applied-engineering/36-beast-mode.md
git commit -m "Add Ch 36 section 7 (checklist) and closing narrative"
```

---

### Task 5: Create Course Module L3-M91 — Beast Mode: Access & System Mapping

**Files:**
- Create: `course/modules/loop-3/L3-M91-beast-mode-access-and-system-mapping.md`

- [ ] **Step 1: Write the course module**

Follow the exact format of existing modules (see L3-M73 and L3-M89 for reference). The module header:

```markdown
# L3-M91: Beast Mode — Access & System Mapping

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M47 (Alerting & On-Call), L1-M01 (Course Setup)
>
> **Source:** Chapter 36 of the 100x Engineer Guide
```

**What You'll Learn:**
- How to systematically verify your access to every layer of the stack
- Drawing a system mental model from infrastructure-as-code and deployment configs
- Tracing a user request end-to-end through a distributed system
- Identifying single points of failure and blast radius boundaries

**Why This Matters:**
The Nick Hook principle — your studio is pre-wired before the session starts. Frame this around TicketPulse: you've just "joined" the TicketPulse team and need to become operational.

**Exercises (TicketPulse context):**

1. **🛠️ Build: Access Verification Sweep**
   Systematically verify access to every TicketPulse layer: clone repo, build locally, access the monitoring stack (Prometheus/Grafana from L2-M45), check CI/CD (GitHub Actions), find secrets config, join the right channels. Create a personal checklist doc tracking what works and what's blocked.

2. **📐 Design: The 5-Minute Architecture Sketch**
   Without reading any documentation, draw TicketPulse's architecture from the infrastructure code alone (docker-compose.yml, Terraform files, Kubernetes manifests). Draw boxes and arrows for every service, database, queue, and external dependency. Then compare your sketch to the actual architecture you know from building it. Note what the infra code revealed that documentation might have missed.

3. **🔍 Explore: Trace the Critical Path**
   Pick TicketPulse's most important user action (purchasing a ticket) and trace it from the HTTP request through every service, queue, and database it touches. Document each hop with: service name, protocol, what data passes, what can fail. Identify the single points of failure.

- [ ] **Step 2: Commit**

```bash
git add course/modules/loop-3/L3-M91-beast-mode-access-and-system-mapping.md
git commit -m "Add course module L3-M91: Beast Mode access & system mapping"
```

---

### Task 6: Create Course Module L3-M91a — Beast Mode: Observability & Dashboard Wiring

**Files:**
- Create: `course/modules/loop-3/L3-M91a-beast-mode-observability-wiring.md`

- [ ] **Step 1: Write the course module**

```markdown
# L3-M91a: Beast Mode — Observability & Dashboard Wiring

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 75 min | 🟢 Core | Prerequisites: L3-M91, L2-M45 (Monitoring), L2-M46 (Distributed Tracing)
>
> **Source:** Chapter 36 of the 100x Engineer Guide
```

**What You'll Learn:**
- Building a personal hotlinks dashboard for rapid incident triage
- Learning what "normal" looks like by studying baseline metrics
- Understanding alerting topology — who gets paged and why
- The "metrics don't lie" principle — trusting observable truth over documentation

**Why This Matters:**
The engineer who knows where to look beats the engineer who knows the code. This module wires up your eyes and ears.

**Exercises (TicketPulse context):**

1. **📊 Observe: Learn What Normal Looks Like**
   Open TicketPulse's Grafana dashboards (from L2-M45). Spend 15 minutes studying the golden signals during a calm period. Write down: baseline request rate, normal p99 latency, daily traffic pattern, typical error rate. You'll use these baselines in L3-M91b to spot anomalies.

2. **🛠️ Build: Your Beast Mode Hotlinks Page**
   Create a markdown file (`docs/beast-mode-hotlinks.md`) with your personal quick-access links for TicketPulse. Include: primary dashboard URL, error tracker, filtered logs, deployment history, database metrics, Kafka consumer lag, cost dashboard. This is your one-page "open this when paged" reference.

3. **🔍 Explore: Alert Archaeology**
   Examine TicketPulse's alerting rules (Prometheus alerting rules from L3-M83a or Grafana alert configs). For each alert, document: what triggers it, who gets notified, what the threshold is, and what the recommended response is. Find at least one alert that's too noisy (fires too often) and one gap (a failure mode with no alert).

- [ ] **Step 2: Commit**

```bash
git add course/modules/loop-3/L3-M91a-beast-mode-observability-wiring.md
git commit -m "Add course module L3-M91a: Beast Mode observability & dashboard wiring"
```

---

### Task 7: Create Course Module L3-M91b — Beast Mode: Incident Response Dry Run

**Files:**
- Create: `course/modules/loop-3/L3-M91b-beast-mode-incident-dry-run.md`

- [ ] **Step 1: Write the course module**

```markdown
# L3-M91b: Beast Mode — Incident Response Dry Run

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 90 min | 🟢 Core | Prerequisites: L3-M91a, L3-M73 (Incident Response Simulation)
>
> **Source:** Chapter 36 of the 100x Engineer Guide
```

**What You'll Learn:**
- The "first 5 minutes" script for when you're paged and you're new
- The "what changed?" reflex — systematic change detection
- Rollback muscle memory — practicing before you need it
- Effective communication during incidents when you're the new person

**Why This Matters:**
L3-M73 taught you incident response as an experienced team member. This module is different: you're practicing incident response as someone who just joined. You don't have full context. You don't know every service. But you have your Beast Mode setup from M91 and M91a, and that's enough to be useful.

**Exercises (TicketPulse context):**

1. **🐛 Debug: The "What Changed?" Drill**
   A simulated scenario: TicketPulse purchase success rate drops. Using ONLY your hotlinks page (from L3-M91a) and the "what changed?" checklist, investigate. Check recent deployments, config changes, traffic patterns, and dependency status. Write your findings in under 5 minutes. Compare your investigation speed to when you first did L3-M73.

2. **🛠️ Build: Rollback Practice**
   Practice three rollback methods on TicketPulse: (a) `git revert` the most recent commit and push through CI/CD, (b) redeploy the previous Docker image tag manually, (c) toggle a feature flag to disable a feature. Time each method. Document the steps in your personal runbook.

3. **📐 Design: Your Personal Runbook**
   Write your personal incident response runbook for TicketPulse. Include: the first 5 minutes script (what to check, in what order), the "what changed?" checklist, rollback procedures for each deployment method, communication templates ("I'm seeing X in the dashboard, checking Y next"), and escalation contacts. This is the document you open when paged at 2 AM.

- [ ] **Step 2: Commit**

```bash
git add course/modules/loop-3/L3-M91b-beast-mode-incident-dry-run.md
git commit -m "Add course module L3-M91b: Beast Mode incident response dry run"
```

---

### Task 8: Create Course Module L3-M91c — Beast Mode: Tribal Knowledge & the Newcomer Superpower

**Files:**
- Create: `course/modules/loop-3/L3-M91c-beast-mode-tribal-knowledge.md`

- [ ] **Step 1: Write the course module**

```markdown
# L3-M91c: Beast Mode — Tribal Knowledge & the Newcomer Superpower

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 60 min | 🟢 Core | Prerequisites: L3-M91b
>
> **Source:** Chapter 36 of the 100x Engineer Guide
```

**What You'll Learn:**
- How to extract tribal knowledge through structured conversations
- Meeting archaeology — mining retros, postmortems, and standups for signal
- Identifying a team's known unknowns and high-impact contribution targets
- The newcomer superpower: documenting what's confusing with fresh eyes

**Why This Matters:**
Every system has an oral history that never makes it into documentation. The engineer who builds the bridge between tribal knowledge and written knowledge makes the whole team faster — and makes themselves indispensable.

**Exercises (TicketPulse context):**

1. **🔍 Explore: Meeting Archaeology**
   Read through TicketPulse's incident postmortems (from L3-M73, L3-M74) and any retro notes. Extract: the top 3 recurring problems, the action items that were never completed, and the "known unknowns" — things the team acknowledges are problems but hasn't fixed. Present your findings as a prioritized list with effort/impact estimates.

2. **🤔 Reflect: The Three Conversations**
   Imagine you've just joined the TicketPulse team. Write out the specific questions you would ask in three conversations: (a) the tech lead — about architecture direction and current priorities, (b) the longest-tenured engineer — about skeletons, scary code, and historical decisions, (c) the on-call engineer — about what pages most and what the usual fix is. For each question, explain what signal you're looking for in the answer.

3. **🛠️ Build: The Fresh Eyes Audit**
   Pretend you are seeing TicketPulse's documentation for the first time. Walk through the README, architecture docs, and runbooks. For every point of confusion, missing context, or outdated information, file it. Then fix the 3 most impactful documentation gaps. This is the highest-leverage onboarding contribution.

- [ ] **Step 2: Commit**

```bash
git add course/modules/loop-3/L3-M91c-beast-mode-tribal-knowledge.md
git commit -m "Add course module L3-M91c: Beast Mode tribal knowledge & newcomer superpower"
```

---

### Task 9: Update course.yaml with new modules

**Files:**
- Modify: `course/course.yaml`

- [ ] **Step 1: Add the 4 new modules to course.yaml**

Add a new section after the L3-M90 entry (before the file ends). Insert this block:

```yaml
  # ---------------------------------------------------------------------------
  # Section 3F: Operational Readiness — Beast Mode (Modules 91-91c)
  # ---------------------------------------------------------------------------

  - id: L3-M91
    title: "Beast Mode: Access & System Mapping"
    tier: "🟢 Core"
    duration: "75 min"
    source_chapters: [36]
    ticketpulse: "You've verified access to every layer of TicketPulse's stack and drawn the system architecture from infrastructure code alone."
    summary: "Systematically verify access, draw architecture from IaC, and trace the critical purchase path end-to-end."
    exercises:
      - type: "🛠️ Build"
        description: "Verify access to every TicketPulse layer: repo, monitoring, CI/CD, secrets, communication channels. Create a personal access checklist."
      - type: "📐 Design"
        description: "Draw TicketPulse's architecture from infrastructure code alone (docker-compose, Terraform, K8s manifests). Compare to known architecture."
      - type: "🔍 Explore"
        description: "Trace the ticket purchase request end-to-end through every service, queue, and database. Document each hop and identify single points of failure."
    runs_locally: true
    prereqs: [L2-M47, L1-M01]

  - id: L3-M91a
    title: "Beast Mode: Observability & Dashboard Wiring"
    tier: "🟢 Core"
    duration: "75 min"
    source_chapters: [36]
    ticketpulse: "You have a personal hotlinks page, know what normal looks like on every dashboard, and have audited the alerting rules."
    summary: "Build your personal hotlinks dashboard, learn baseline metrics, and audit TicketPulse's alerting topology."
    exercises:
      - type: "📊 Observe"
        description: "Study TicketPulse's Grafana dashboards for 15 minutes during calm. Write down baseline request rate, p99 latency, traffic pattern, and error rate."
      - type: "🛠️ Build"
        description: "Create a beast-mode-hotlinks.md with quick-access links for TicketPulse: primary dashboard, error tracker, filtered logs, deploy history, DB metrics, Kafka lag, cost dashboard."
      - type: "🔍 Explore"
        description: "Audit TicketPulse's alerting rules. Document each alert's trigger, threshold, and recommended response. Find one too-noisy alert and one missing alert."
    runs_locally: true
    prereqs: [L3-M91, L2-M45, L2-M46]

  - id: L3-M91b
    title: "Beast Mode: Incident Response Dry Run"
    tier: "🟢 Core"
    duration: "90 min"
    source_chapters: [36]
    ticketpulse: "You've practiced the first-5-minutes script, drilled three rollback methods, and written your personal incident runbook."
    summary: "Practice incident triage as a new team member: the 'what changed?' drill, rollback muscle memory, and writing your personal runbook."
    exercises:
      - type: "🐛 Debug"
        description: "Simulated outage: purchase success rate drops. Using only your hotlinks page and the 'what changed?' checklist, investigate and document findings in under 5 minutes."
      - type: "🛠️ Build"
        description: "Practice three rollback methods: git revert through CI/CD, redeploy previous Docker image, and feature flag kill switch. Time each method."
      - type: "📐 Design"
        description: "Write your personal incident runbook: first 5 minutes script, 'what changed?' checklist, rollback procedures, communication templates, and escalation contacts."
    runs_locally: true
    prereqs: [L3-M91a, L3-M73]

  - id: L3-M91c
    title: "Beast Mode: Tribal Knowledge & the Newcomer Superpower"
    tier: "🟢 Core"
    duration: "60 min"
    source_chapters: [36]
    ticketpulse: "You've mined TicketPulse's postmortems for patterns, written the three key onboarding conversations, and fixed the 3 most impactful documentation gaps."
    summary: "Extract tribal knowledge through structured conversations and meeting archaeology. Use fresh eyes to fix documentation gaps."
    exercises:
      - type: "🔍 Explore"
        description: "Mine TicketPulse's postmortems and retro notes. Extract top 3 recurring problems, unfinished action items, and known-but-unfixed issues. Prioritize by effort/impact."
      - type: "🤔 Reflect"
        description: "Write specific questions for three onboarding conversations: tech lead (architecture direction), longest-tenured engineer (skeletons), on-call engineer (what pages most)."
      - type: "🛠️ Build"
        description: "Fresh eyes audit: walk through TicketPulse docs as a newcomer. For every confusion point, file it. Fix the 3 most impactful documentation gaps."
    runs_locally: false
    online_playground: "N/A — analysis and documentation module"
    prereqs: [L3-M91b]
```

- [ ] **Step 2: Update the course header module count**

At the top of `course/course.yaml`, update `total_modules: 104` to `total_modules: 108`.

- [ ] **Step 3: Commit**

```bash
git add course/course.yaml
git commit -m "Add Beast Mode modules (L3-M91 through L3-M91c) to course.yaml"
```

---

### Task 10: Update README.md and Part II README

**Files:**
- Modify: `README.md`
- Modify: `part-2-applied-engineering/README.md`

- [ ] **Step 1: Update the main README.md**

In the Part II table, add a new row after Ch 30:

```markdown
| 36 | [Beast Mode — Operational Readiness](./part-2-applied-engineering/36-beast-mode.md) | All levels | Operational readiness playbook, system mental models, observability hotlinks, incident readiness, codebase navigation, tribal knowledge |
```

Update the header stats: change `**35 chapters**` to `**36 chapters**`.

Update the chapter dependency graph to include:
```
  Ch 36         ← benefits from Ch 12, 18; standalone
```

In the "Quick Start — Reading Paths" table, add a new row:
```markdown
| **Hit the ground running (new team/company)** | Ch 36 (beast mode), 12 (tooling) | Ch 18, 28, 29 |
```

Update the course section to reflect `**108 hands-on modules**` (was 104).

- [ ] **Step 2: Update Part II README**

Read `part-2-applied-engineering/README.md` and add Ch 36 to the chapter listing following the existing format.

- [ ] **Step 3: Commit**

```bash
git add README.md part-2-applied-engineering/README.md
git commit -m "Register Ch 36 and Beast Mode modules in README and course index"
```

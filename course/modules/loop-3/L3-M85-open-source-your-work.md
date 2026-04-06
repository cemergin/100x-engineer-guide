# L3-M85: Open Source Your Work

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M34, L3-M67
>
> **Source:** Chapter 28 of the 100x Engineer Guide

## What You'll Learn

- Choosing and extracting a TicketPulse component for open source release
- Preparing a repository that invites contributions: README, CONTRIBUTING.md, LICENSE, issue templates
- What makes open source READMEs effective (studied from Redis, Fastify, and Prisma)
- Publishing to npm with semantic versioning and automated releases
- How to actually contribute to an existing OSS project (the pull request path)
- What makes a project actually get adopted vs what makes it sit at zero stars

## Why This Matters

Throughout this course, you have built components that solve real problems: a rate limiter, a webhook delivery system, an event bus, a circuit breaker. These are not TicketPulse-specific — they solve problems that thousands of other engineers face every day.

Open-sourcing one of these components does three things simultaneously. First, it forces you to write clean, documented, well-tested code — the act of preparing for public release improves the code. Second, it builds your engineering profile in a way that a resume cannot — a maintained open source project with a clear README, tests, and CI demonstrates more engineering maturity than any number of bullet points. Third, it contributes back to the ecosystem you have been learning from.

> **Ecosystem note:** Chapter 28 of the 100x Engineer Guide covers both sides of open source: reading other people's code to accelerate your own learning, and contributing your own work back. This module is the applied companion: you will go from "I have a component" to "I have a published, documented, maintained library."

Most engineers never open-source anything because they think their code is not good enough, or the problem is too small, or someone else already solved it. But a well-packaged solution to a real problem, even a small one, is more valuable than an ambitious project that is half-finished and undocumented.

---

### 🤔 Prediction Prompt

Before reading, think: which TicketPulse component would be most useful to other developers if extracted as a standalone library? What makes a component "open-sourceable" vs tightly coupled to your domain?

## 1. Choose a Component to Extract

### Stop and Think (5 minutes)

Look at what you have built across the course. Which components are general-purpose enough to be useful outside of TicketPulse?

| Component | Module Built | Reusable? | Existing Alternatives |
|-----------|-------------|-----------|----------------------|
| Rate limiter (token bucket + sliding window) | L1-M15 | High — every API needs one | Many, but yours has a specific approach |
| Webhook delivery system (with retries, signatures, dead letter) | L2-M35 | High — common infra need | Few good open-source options |
| Event bus (pub/sub with typed events) | L2-M34 | Medium — tightly coupled to your stack | Many options exist |
| Circuit breaker | L2-M38 | High — cross-cutting concern | Existing libraries, but good for learning |
| Durable workflow engine (simplified) | L3-M81 | Low — better to use Temporal/Restate | Mature alternatives exist |

Pick one. For this module, we will use the **webhook delivery system** as the example, but apply the same process to whichever component you choose.

### 📐 Exercise: Component Readiness Assessment

<details>
<summary>💡 Hint 1: Dependency count is the first filter</summary>
Run a dependency audit on the component you are considering. If it drags in half of TicketPulse's internals, it is not extractable yet -- refactor the imports until the component depends only on its own types and one or two well-known libraries.
</details>

<details>
<summary>💡 Hint 2: Semantic versioning tells you if the API is stable</summary>
Try writing the CHANGELOG entry for a hypothetical v1.0.0. If you cannot describe the public API in a single "Added" section without hedging, the API is not stable enough to publish. Narrow the surface area until you can.
</details>


Before you extract a component for open source, assess its readiness:

```
OSS READINESS CHECKLIST
────────────────────────

1. SCOPE CLARITY
   □ Can you describe the component in one sentence?
   □ Does it have clear boundaries — what it does and what it does NOT do?
   □ Is there a README.md draft in your head? (If you cannot describe it, users cannot use it)

2. QUALITY BASELINE
   □ Does the component have unit tests? (Target: >80% coverage)
   □ Do the tests describe behavior, not implementation?
   □ Would the tests catch a regression if you refactored internals?

3. DEPENDENCY HEALTH
   □ How many dependencies does it have?
   □ Are all dependencies actively maintained?
   □ Can a new user install it without also installing 50 other things?

4. API STABILITY
   □ Would you be comfortable making this public API a contract with users?
   □ Have you tried using the API from an "outside" perspective?
   □ Have you tried to write documentation for every public function?
      (Writing docs often reveals API design problems)

5. NAME AVAILABILITY
   □ Is the npm package name available? (check npmjs.com)
   □ Is the GitHub repository name available?
   □ Does a Google search for the name return anything confusing?
```

---

## 2. Prepare the Repository

### Repository Structure

```
ticketpulse-webhooks/
├── src/
│   ├── index.ts              # Public API exports
│   ├── webhook-sender.ts     # Core sending logic
│   ├── retry-strategy.ts     # Exponential backoff with jitter
│   ├── signature.ts          # HMAC signature generation/verification
│   ├── dead-letter.ts        # Failed delivery handling
│   └── types.ts              # TypeScript types
├── test/
│   ├── webhook-sender.test.ts
│   ├── retry-strategy.test.ts
│   ├── signature.test.ts
│   └── integration.test.ts
├── examples/
│   ├── basic-usage.ts
│   └── with-express.ts
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── release.yml
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── CHANGELOG.md
├── package.json
├── tsconfig.json
└── .gitignore
```

### README.md: The Most Important File

The README is your project's landing page. Engineers decide whether to use your library in under 60 seconds based on the README. It must answer four questions immediately: what is this, why should I care, how do I use it, and how do I install it.

```markdown
# ticketpulse-webhooks

Reliable webhook delivery with automatic retries, HMAC signatures,
and dead letter handling.

## Features

- **Automatic retries** with exponential backoff and jitter
- **HMAC-SHA256 signatures** for payload verification
- **Dead letter queue** for persistently failing deliveries
- **TypeScript-first** with full type definitions
- **Framework-agnostic** — works with Express, Fastify, Hono, or plain Node.js

## Quick Start

```bash
npm install ticketpulse-webhooks
```

```typescript
import { WebhookSender } from 'ticketpulse-webhooks';

const sender = new WebhookSender({
  signingSecret: process.env.WEBHOOK_SECRET,
  maxRetries: 5,
  onDeadLetter: async (delivery) => {
    console.error('Webhook permanently failed:', delivery.id);
  },
});

await sender.send({
  url: 'https://example.com/webhook',
  event: 'order.confirmed',
  payload: { orderId: 'ord_123', amount: 5000 },
});
```

## Verifying Signatures (Receiver Side)

```typescript
import { verifySignature } from 'ticketpulse-webhooks';

app.post('/webhook', (req, res) => {
  const isValid = verifySignature({
    payload: req.body,
    signature: req.headers['x-webhook-signature'],
    secret: process.env.WEBHOOK_SECRET,
  });

  if (!isValid) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Process the webhook...
  res.status(200).json({ received: true });
});
```

## API Reference

### `WebhookSender`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `signingSecret` | `string` | required | Secret for HMAC signature |
| `maxRetries` | `number` | `5` | Maximum retry attempts |
| `initialDelay` | `number` | `1000` | Initial retry delay (ms) |
| `maxDelay` | `number` | `300000` | Maximum retry delay (ms) |
| `timeout` | `number` | `30000` | Request timeout (ms) |
| `onDeadLetter` | `function` | `undefined` | Called when retries exhausted |

### `sender.send(options)`

| Option | Type | Description |
|--------|------|-------------|
| `url` | `string` | Destination URL |
| `event` | `string` | Event type (included in headers) |
| `payload` | `object` | JSON payload |
| `headers` | `object` | Additional headers (optional) |

## License

MIT
```

### Study: What Makes Great READMEs

Before finalizing your README, study three well-known projects:

**Redis README** (https://github.com/redis/redis): Starts with a clear one-line description, then immediately shows how to build and run. Minimal prose, maximum utility.

**Fastify README** (https://github.com/fastify/fastify): Leads with benchmarks (speed is the selling point), then a "quick start" that takes 10 seconds to understand. The README IS the documentation for getting started.

**Prisma README** (https://github.com/prisma/prisma): Beautiful badges, clear value proposition, multiple quick-start paths for different use cases. Links to comprehensive docs rather than putting everything in the README.

**Common patterns in great READMEs:**
- One-line description at the very top
- Install command within the first screenful
- Working code example within the first screenful
- Table of contents for longer READMEs
- Badges for build status, npm version, license
- "Why this over alternatives?" section for competitive landscapes

### 📐 README Critique Exercise

<details>
<summary>💡 Hint 1: The 10-second test is ruthless</summary>
Open the README, start a timer, and look away after 10 seconds. If you cannot state what the library does and how to install it, the README fails. Apply the same test to your own draft.
</details>


Find any open source library on npm that you have used. Read its README critically for 5 minutes:

```
README CRITIQUE FRAMEWORK
─────────────────────────

1. First 10 seconds: Can you tell what it does?
   □ Yes  □ No  □ Partially

2. First screenful: Is there an install command?
   □ Yes  □ No

3. First screenful: Is there a working code example?
   □ Yes  □ No

4. After 2 minutes: Do you know when to use it and when NOT to?
   □ Yes  □ No  □ Partially

5. After 5 minutes: Could you use it without visiting any other URL?
   □ Yes  □ No  □ I would need to visit the API docs

6. What is the single most confusing thing about this README?
   Write it down.
```

Then apply the same critique to your own README draft. The confusion you found in someone else's README is likely present in yours too.

### CONTRIBUTING.md

```markdown
# Contributing to ticketpulse-webhooks

Thank you for considering a contribution! Here is how to get started.

## Development Setup

```bash
git clone https://github.com/your-username/ticketpulse-webhooks.git
cd ticketpulse-webhooks
pnpm install
pnpm test        # Run tests
pnpm lint        # Run linter
```

## Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Run `pnpm test` and `pnpm lint`
6. Commit with a descriptive message
7. Push to your fork and open a Pull Request

## Pull Request Guidelines

- One PR, one concern. Do not bundle unrelated changes.
- Include tests for new features and bug fixes.
- Update the README if the public API changes.
- Follow the existing code style (enforced by the linter).

## What Makes a Good Issue

For bug reports:
- What did you expect to happen?
- What actually happened?
- A minimal reproduction (ideally a code snippet)
- Node.js version and OS

For feature requests:
- The use case that motivates it (not just the feature)
- What you tried before opening the request

## Code of Conduct

Be respectful and constructive. We are all here to build good software.

## Questions?

Open a GitHub Discussion or file an issue.
```

### LICENSE

Choose MIT for maximum adoption. If you want patent protection, use Apache 2.0. If you want to ensure derivatives stay open, use GPL. When in doubt, MIT.

```
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

### Issue Templates

```markdown
<!-- .github/ISSUE_TEMPLATE/bug_report.md -->
---
name: Bug Report
about: Report a bug
labels: bug
---

## Describe the Bug

A clear description of what the bug is.

## To Reproduce

Steps to reproduce:
1. ...
2. ...

## Expected Behavior

What you expected to happen.

## Minimal Reproduction

```typescript
// A code snippet that demonstrates the bug
```

## Environment

- Node.js version:
- Package version:
- OS:
```

---

## 3. CI and Publishing

### CI Workflow

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20, 22]
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'pnpm'
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm test
      - run: pnpm build
```

Testing against Node 18, 20, and 22 ensures your library works for users who have not yet upgraded. A badge showing green across all three Node versions builds trust.

### Automated Publishing with Changesets

```bash
# Install changesets
pnpm add -D @changesets/cli
pnpm changeset init
```

The workflow: when you make a change, run `pnpm changeset` to describe what changed and whether it is a patch, minor, or major version bump. A GitHub Action handles publishing to npm when changesets are merged.

```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          registry-url: 'https://registry.npmjs.org'
      - run: pnpm install
      - run: pnpm build
      - uses: changesets/action@v1
        with:
          publish: pnpm changeset publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

---

## 4. Contributing to Existing OSS Projects

Releasing your own library is one side of open source. The other side — contributing to existing projects — is often more impactful for learning and career growth.

### The OSS Contribution Path

```
CONTRIBUTING TO AN EXISTING OSS PROJECT
────────────────────────────────────────

Step 1: Find a good first issue
  - GitHub: search "good first issue" or "help wanted" labels
  - Pick something specific and bounded (not "add feature X")
  - Comment on the issue before starting work: "I'd like to work on this"
    (Prevents duplicated effort and gets maintainer buy-in early)

Step 2: Set up the dev environment correctly
  - Read CONTRIBUTING.md thoroughly before writing a line
  - Run the full test suite locally — if it doesn't pass, stop and investigate
  - Understand how the CI works before you start

Step 3: Make the smallest possible change
  - Open source maintainers review dozens of PRs a week
  - A 50-line PR with clear intent gets reviewed in hours
  - A 500-line PR with unclear scope waits days or weeks
  - If your change is large, split it into multiple PRs

Step 4: Write the PR description for a maintainer who knows nothing about you
  - What problem does this solve?
  - What approach did you take, and why?
  - Are there any trade-offs to this approach?
  - How did you test it?

Step 5: Respond to review quickly and graciously
  - The maintainer is a volunteer
  - "No" is a valid answer and not a rejection of you as a person
  - If they request changes, do them promptly and add a review comment
    explaining what you changed and why
```

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Exercise: Your First Real Contribution

<details>
<summary>💡 Hint 1: Start with a failing test, not a code fix</summary>
The highest-acceptance-rate first PR is a test that exposes an existing issue. Write a failing test that reproduces the bug, then fix the code to make it pass. Maintainers love PRs that come with proof.
</details>

<details>
<summary>💡 Hint 2: Read the CONTRIBUTING.md before touching a single line</summary>
Check whether the project uses a specific commit convention (Conventional Commits, squash-and-merge, signed commits). Getting the process wrong is the fastest way to get a PR ignored regardless of code quality.
</details>


Pick a library that TicketPulse depends on. Look at its issue list. Find one issue where you can contribute:

**Option A: Documentation improvement** (easiest, highest acceptance rate)
- Find a function or config option with unclear documentation
- Submit a PR that clarifies it with a concrete example
- Acceptance rate: very high, turnaround: fast

**Option B: Fix a bug with a clear reproduction case**
- Find an issue where someone posted a code snippet that demonstrates the bug
- Reproduce it locally first
- Write a failing test that captures the bug, then fix it
- Acceptance rate: high if the fix is clean

**Option C: Add a missing test case**
- Look at the test directory — what edge cases are not tested?
- Add a test for one of them (no behavior change, just coverage)
- Acceptance rate: high, low risk

For your first contribution, Option A or B is ideal. Document the experience:
- Which library did you target?
- What was the issue?
- How long did it take to set up the dev environment?
- What was the review feedback?
- Was your PR accepted?

The experience of having code reviewed by a stranger — and incorporating their feedback — teaches things that internal code review cannot.

### The OSS Contribution as Portfolio

A merged PR to a popular library is worth more than a hundred lines of private code. Here is why:

1. **Proof of collaboration:** You navigated someone else's codebase, understood their conventions, and delivered something they were willing to merge.
2. **Public artifact:** Any interviewer can read your PR and the review conversation.
3. **Community recognition:** Repeated contributions earn you contributor status, which opens doors to maintainership.

Build a habit: one small contribution per month. After a year, you have 12 PRs across 3-4 projects. That is a meaningful open source footprint.

---

## 5. Reflect: What Makes Projects Get Adopted?

### Stop and Think (10 minutes)

Think about the last three open source libraries you adopted. Why did you choose them?

**What drives adoption:**
- **Solves a real, specific problem** — not "a framework for everything" but "does this one thing well"
- **Easy to start** — install command + working example in under 2 minutes
- **Good documentation** — API reference, examples, error messages that help you fix the problem
- **Active maintenance** — recent commits, responsive issues, regular releases
- **Small surface area** — fewer dependencies, smaller bundle, less to go wrong

**What does NOT drive adoption:**
- Number of features (more features = more complexity = fewer adopters)
- Clever code (users do not read your source code, they read your README)
- Marketing without substance (a slick landing page for a broken library hurts trust)

One well-maintained, well-documented, focused library demonstrates more engineering maturity than fifty abandoned repositories.

### 🤔 The "Zero Stars" Autopsy

Look at a repository on GitHub with 0-5 stars that has been around for more than a year. What went wrong?

Common patterns:
- No README or a README with only "TODO"
- Works on the author's machine but has no CI
- Solves a problem that only exists in one codebase
- Solves a real problem but is 10x harder to set up than alternatives
- Published and then never updated (security vulnerabilities accumulate)

Apply this analysis to your own project before you publish. If you can identify the failure mode, you can prevent it.

---

## 6. Maintenance: The Work After the Launch

### What Maintenance Looks Like

Publishing is 20% of the effort. Maintenance is the other 80%. Be prepared for:

**Responding to issues:** Users will file bug reports, feature requests, and questions. Set expectations with a response time (even if it is "I check issues weekly"). An unresponsive maintainer kills adoption faster than missing features.

**Keeping dependencies updated:** Dependabot or Renovate will send you PRs to update dependencies. Review them, run tests, and merge or dismiss. An outdated dependency with known vulnerabilities makes users distrust your library.

**Handling breaking changes:** When you need to make a breaking change, follow semver strictly. Major version bump. Migration guide in the CHANGELOG. Deprecation warnings in the previous minor version. Give users time to migrate.

```markdown
# CHANGELOG.md

## [2.0.0] - 2026-06-15

### Breaking Changes
- `WebhookSender` constructor now requires `signingSecret` as a named option
  instead of a positional argument.
  - Before: `new WebhookSender('my-secret')`
  - After: `new WebhookSender({ signingSecret: 'my-secret' })`
  - Migration: search for `new WebhookSender(` and update to named options.

### Added
- `onRetry` callback for observability into retry behavior
- `batchSend()` method for sending multiple webhooks efficiently

### Fixed
- Timeout errors now include the URL that timed out (#23)
```

### Semver in Practice

```
SEMANTIC VERSIONING QUICK REFERENCE
─────────────────────────────────────

Given version MAJOR.MINOR.PATCH (e.g., 1.4.2):

PATCH (1.4.2 → 1.4.3):
  - Bug fixes
  - Performance improvements
  - Internal refactoring with no API changes
  Users can upgrade safely with no code changes.

MINOR (1.4.2 → 1.5.0):
  - New features that are backward compatible
  - New optional parameters
  - New exports
  Users can upgrade safely. New functionality is available.

MAJOR (1.4.2 → 2.0.0):
  - Breaking API changes
  - Removed exports or parameters
  - Changed behavior that users may depend on
  Users MUST read the migration guide before upgrading.
```

The discipline of semantic versioning is a contract with your users. Break it once and they stop trusting your releases.

### When to Archive a Project

It is better to archive a project clearly than to let it rot silently. If you are no longer maintaining a library:

```markdown
# ARCHIVED

This project is no longer actively maintained. It works as-is but will
not receive new features or bug fixes.

Alternatives:
- [other-library](link) — actively maintained, covers similar use cases
```

Archiving with a clear message and alternatives is a sign of engineering maturity, not failure.

---

## Checkpoint: What You Built

You have:

- [x] Chosen a TicketPulse component to open-source using the readiness assessment
- [x] Structured the repository with README, CONTRIBUTING.md, LICENSE, issue templates
- [x] Studied effective READMEs from Redis, Fastify, and Prisma, and critiqued one critically
- [x] Set up CI (multi-version Node testing) and automated publishing (changesets)
- [x] Understood the OSS contribution path and attempted a real contribution
- [x] Reflected on what drives adoption vs what makes projects sit at zero stars

**Key insight**: Open source is not about writing impressive code. It is about solving a real problem and packaging the solution so well that other engineers can adopt it in minutes. The README is more important than the implementation. And one merged PR to an existing library teaches you more than a dozen unreviewed personal projects.

---

**Next module**: L3-M86 — AI-Powered Engineering Workflow, where we use Claude Code to implement a new TicketPulse feature and evaluate where AI accelerates us and where it needs correction.

## Key Terms

| Term | Definition |
|------|-----------|
| **Open source** | Software whose source code is publicly available and licensed for use, modification, and redistribution. |
| **LICENSE** | A file declaring the legal terms under which a project's source code may be used and distributed. |
| **CONTRIBUTING** | A file that describes how external contributors can participate in a project (code style, PR process, etc.). |
| **Semver** | Semantic Versioning; a versioning scheme (MAJOR.MINOR.PATCH) that communicates the nature of changes in each release. |
| **Changeset** | A structured description of changes in a release, often auto-generated from commit messages or PR metadata. |
| **Maintainer** | A person responsible for reviewing contributions, merging changes, and guiding the direction of an open-source project. |
| **Good first issue** | A GitHub label used by maintainers to mark issues that are appropriate for new contributors. |
| **Scope creep** | The gradual expansion of a project's goals beyond its original intent, often making it harder to use and maintain. |

### 🤔 Reflection Prompt

After preparing the component for release, what surprised you about the gap between "works inside TicketPulse" and "works as a standalone library"? What assumptions about the host project did you have to remove?

## Further Reading

- **Chapter 28 of the 100x Engineer Guide**: Code reading, OSS contribution, and building your engineering portfolio
- **GitHub's "How to contribute to open source"** — practical guide from the platform perspective
- **"Working in Public" by Nadia Eghbal** — the economics and dynamics of modern open source maintenance
- **firstcontributions.github.io** — a practice repository for making your very first PR
- **choosealicense.com** — side-by-side license comparison to help you choose
---

## What's Next

In **AI-Powered Engineering Workflow** (L3-M86), you'll build on what you learned here and take it further.

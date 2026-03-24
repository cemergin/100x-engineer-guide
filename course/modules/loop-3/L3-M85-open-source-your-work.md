# L3-M85: Open Source Your Work

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 45 min | 🟢 Core | Prerequisites: L2-M34, L3-M67
>
> **Source:** Chapter 28 of the 100x Engineer Guide

## What You'll Learn

- Choosing and extracting a TicketPulse component for open source release
- Preparing a repository that invites contributions: README, CONTRIBUTING.md, LICENSE, issue templates
- What makes open source READMEs effective (studied from Redis, Fastify, and Prisma)
- Publishing to npm with semantic versioning and automated releases
- What makes a project actually get adopted vs what makes it sit at zero stars

## Why This Matters

Throughout this course, you have built components that solve real problems: a rate limiter, a webhook delivery system, an event bus, a circuit breaker. These are not TicketPulse-specific -- they solve problems that thousands of other engineers face every day.

Open-sourcing one of these components does three things simultaneously. First, it forces you to write clean, documented, well-tested code -- the act of preparing for public release improves the code. Second, it builds your engineering profile in a way that a resume cannot -- a maintained open source project with a clear README, tests, and CI demonstrates more engineering maturity than any number of bullet points. Third, it contributes back to the ecosystem you have been learning from.

Most engineers never open-source anything because they think their code is not good enough, or the problem is too small, or someone else already solved it. But a well-packaged solution to a real problem, even a small one, is more valuable than an ambitious project that is half-finished and undocumented.

---

## 1. Choose a Component to Extract

### Stop and Think (5 minutes)

Look at what you have built across the course. Which components are general-purpose enough to be useful outside of TicketPulse?

| Component | Module Built | Reusable? | Existing Alternatives |
|-----------|-------------|-----------|----------------------|
| Rate limiter (token bucket + sliding window) | L1-M15 | High -- every API needs one | Many, but yours has a specific approach |
| Webhook delivery system (with retries, signatures, dead letter) | L2-M35 | High -- common infra need | Few good open-source options |
| Event bus (pub/sub with typed events) | L2-M34 | Medium -- tightly coupled to your stack | Many options exist |
| Circuit breaker | L2-M38 | High -- cross-cutting concern | Existing libraries, but good for learning |
| Durable workflow engine (simplified) | L3-M81 | Low -- better to use Temporal/Restate | Mature alternatives exist |

Pick one. For this module, we will use the **webhook delivery system** as the example, but apply the same process to whichever component you choose.

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

## Code of Conduct

Be respectful and constructive. We are all here to build good software.

## Questions?

Open a GitHub Discussion or file an issue.
```

### LICENSE

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

Choose MIT for maximum adoption. If you want patent protection, use Apache 2.0. If you want to ensure derivatives stay open, use GPL. When in doubt, MIT.

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

## 4. Reflect: What Makes Projects Get Adopted?

### Stop and Think (10 minutes)

Think about the last three open source libraries you adopted. Why did you choose them?

**What drives adoption:**
- **Solves a real, specific problem** -- not "a framework for everything" but "does this one thing well"
- **Easy to start** -- install command + working example in under 2 minutes
- **Good documentation** -- API reference, examples, error messages that help you fix the problem
- **Active maintenance** -- recent commits, responsive issues, regular releases
- **Small surface area** -- fewer dependencies, smaller bundle, less to go wrong

**What does NOT drive adoption:**
- Number of features (more features = more complexity = fewer adopters)
- Clever code (users do not read your source code, they read your README)
- Marketing without substance (a slick landing page for a broken library hurts trust)

One well-maintained, well-documented, focused library demonstrates more engineering maturity than fifty abandoned repositories.

---

## 5. Maintenance: The Work After the Launch

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

- [x] Chosen a TicketPulse component to open-source
- [x] Structured the repository with README, CONTRIBUTING.md, LICENSE, issue templates
- [x] Studied effective READMEs from Redis, Fastify, and Prisma
- [x] Set up CI (multi-version Node testing) and automated publishing (changesets)
- [x] Reflected on what drives adoption vs what does not

**Key insight**: Open source is not about writing impressive code. It is about solving a real problem and packaging the solution so well that other engineers can adopt it in minutes. The README is more important than the implementation.

---

**Next module**: L3-M86 -- AI-Powered Engineering Workflow, where we use Claude Code to implement a new TicketPulse feature and evaluate where AI accelerates us and where it needs correction.

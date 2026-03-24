<!--
  TYPE: index
  TITLE: The 100x Engineer Guide
  CHAPTERS: 20
  PARTS: 5
  APPENDICES: 1
  UPDATED: 2026-03-24
  STRUCTURE: narrative-hierarchy
  AI_NOTE: Each chapter contains an HTML comment metadata block with CHAPTER, TITLE, PART, PREREQS, KEY_TOPICS, DIFFICULTY, UPDATED. Use these for filtering, prerequisite graphs, and topic search.
-->

# The 100x Engineer Guide
### Backend & Software Engineering Mastery

A comprehensive mega-guide covering every paradigm, philosophy, and hard skill needed to become a lead/staff+ engineer — organized as a narrative that builds from theory to practice.

---

## Reading Paths

| Goal | Start Here | Then |
|------|-----------|------|
| **Learn from scratch** | Part I (Ch 1→2→3→4→5) | Part II, then Part III |
| **System design interviews** | Ch 1, 3, 2, 6 | Ch 13, Appendix A (glossary) |
| **Get productive fast** | Part III (Ch 12, 20, 17) | Ch 15, 14 |
| **Go to production** | Part IV (Ch 13, 18, 19) | Ch 4, 7 |
| **Level up to staff+** | Ch 9, 10 | Ch 16 (resources) |
| **Quick reference** | Appendix A (glossary) | Ch 16 (resources) |

---

## Part I — Foundations
*The theory and principles that underpin everything else. Read these first.*

| Ch | Title | Difficulty | Key Topics |
|----|-------|-----------|------------|
| 1 | [System Design Paradigms](./01-system-design.md) | Advanced | CAP/PACELC, consistency models, Paxos/Raft, distributed transactions, CRDTs, sharding, load balancing, capacity planning |
| 2 | [Data Engineering](./02-data-engineering.md) | Intermediate→Advanced | Database paradigms (SQL/NoSQL/NewSQL), data modeling, indexing, caching, ETL/ELT, CDC, data mesh, consistency patterns |
| 3 | [Architecture Patterns](./03-architecture-patterns.md) | Intermediate→Advanced | Monolith→microservices, hexagonal/clean/vertical slice, DDD, event-driven, CQRS, REST/gRPC/GraphQL, saga pattern |
| 4 | [Reliability Engineering](./04-reliability-engineering.md) | Intermediate→Advanced | SRE, SLOs/SLIs/error budgets, observability, circuit breaker, bulkhead, retry, incident management, chaos engineering |
| 5 | [Security Engineering](./05-security-engineering.md) | Intermediate | Security principles, OAuth/OIDC/JWT, OWASP Top 10, cryptography, infrastructure security, GDPR/SOC2 |

**Narrative arc:** How distributed systems work (Ch 1) → how to store and move data through them (Ch 2) → how to structure the software (Ch 3) → how to keep it running (Ch 4) → how to keep it safe (Ch 5).

---

## Part II — Applied Engineering
*Deeper dives into specialized domains. Read after Part I, in any order based on need.*

| Ch | Title | Difficulty | Key Topics |
|----|-------|-----------|------------|
| 6 | [Concurrency & Computing](./06-concurrency-computing.md) | Advanced | Threads, event loop, actors, CSP, coroutines, mutex/CAS/lock-free, deadlocks, memory models, GC, FP/OOP/reactive |
| 7 | [DevOps & Infrastructure](./07-devops-infrastructure.md) | Intermediate | IaC/Terraform, containers/Kubernetes, CI/CD, 12-factor app, HTTP/2/3, DNS/CDN, service mesh, platform engineering |
| 8 | [Testing & Quality](./08-testing-quality.md) | Intermediate | TDD/BDD/property-based/mutation testing, unit/integration/E2E/contract tests, performance testing, refactoring |
| 9 | [Engineering Leadership](./09-engineering-leadership.md) | Advanced | ADRs/RFCs, system thinking, DORA/SPACE metrics, estimation, technical strategy, knowledge management |
| 10 | [Emerging Paradigms](./10-emerging-paradigms.md) | Advanced | AI-native engineering, RAG/agents, edge computing, real-time/CRDTs, durable execution, stream processing, FinOps, Wasm |

**Narrative arc:** How computers execute concurrently (Ch 6) → how to deploy and operate (Ch 7) → how to prove it works (Ch 8) → how to lead the team building it (Ch 9) → what's coming next (Ch 10).

---

## Part III — Tooling & Practice
*Hands-on skills and daily tools. Can be read independently at any point.*

| Ch | Title | Difficulty | Key Topics |
|----|-------|-----------|------------|
| 11 | [Programming Languages](./11-programming-languages.md) | Intermediate | Go, Rust, Python, Java/Kotlin, TypeScript, C#, Elixir, Zig — runnable server examples, comparison tables, selection matrix |
| 12 | [Developer Tooling & Productivity](./12-developer-tooling-productivity.md) | Beginner→Advanced | Linux, bash, SSH, shell productivity (fzf/tmux/rg), Vim/Neovim, VS Code, Git advanced, Docker, Terraform, kubectl |
| 14 | [AI-Powered Engineering](./14-ai-powered-engineering.md) | Beginner→Intermediate | AI for project planning, ERD design with LLMs, AI code review, debugging, Claude Code/Copilot/Cursor, prompt engineering |
| 15 | [Codebase Organization](./15-codebase-organization.md) | Beginner→Advanced | Linting (ESLint/Prettier/Ruff), CI/CD pipelines, team-size org (solo→100+), monorepo patterns, architecture fitness functions |
| 17 | [Claude Code Mastery](./17-claude-code-mastery.md) | Beginner→Advanced | Skills/plugins/hooks, MCP servers, agent teams, parallel dispatch, CLAUDE.md, plan mode, TDD/debugging workflows |
| 20 | [Dependency & Environment Management](./20-dependency-env-management.md) | Intermediate | Nix/NixOS, asdf/mise, nvm/pyenv/rustup, lockfiles, Docker dev envs, devcontainers, .env management, reproducible builds |

**Narrative arc:** Choose your language (Ch 11) → master your tools (Ch 12) → leverage AI (Ch 14, 17) → organize your codebase (Ch 15) → manage your environment (Ch 20).

---

## Part IV — Cloud & Operations
*Running systems in production at scale. Read after Parts I-II.*

| Ch | Title | Difficulty | Key Topics |
|----|-------|-----------|------------|
| 13 | [Cloud Computing & System Integration](./13-cloud-system-integration.md) | Advanced | VPC networking, message queues (Kafka/SQS/RabbitMQ), event-driven, data flow, database migrations, full system walkthrough, monitoring, FinOps |
| 18 | [Debugging, Profiling & Monitoring](./18-debugging-profiling-monitoring.md) | Intermediate→Advanced | Debugging methodology, Node/Python/Go/Java debuggers, flame graphs, Datadog, Prometheus+Grafana, ELK, OpenTelemetry, Sentry, incident playbook |
| 19 | [AWS & Firebase Deep Dive](./19-aws-firebase-deep-dive.md) | Intermediate→Advanced | AWS: EC2/Lambda/ECS, VPC, S3/DynamoDB/RDS, SQS/SNS/EventBridge, IAM, CloudWatch, cost optimization. Firebase: Firestore, Auth, Functions, security rules |

**Narrative arc:** How all the pieces connect (Ch 13) → how to find and fix problems (Ch 18) → the specific cloud platforms in depth (Ch 19).

---

## Part V — Appendices
*Reference material. Look things up as needed.*

| Ch | Title | Difficulty | Key Topics |
|----|-------|-----------|------------|
| 16 | [Essential Resources](./16-essential-resources.md) | All levels | 49 foundational papers, books, blogs, and newsletters — Dynamo paper, DDIA, SRE book, Brendan Gregg, Martin Fowler, and more |
| A | [Glossary & Dictionary](./appendix-glossary.md) | All levels | 250+ engineering terms, abbreviations, and culture phrases — from ACID to yak shaving |

---

## Chapter Dependency Graph

```
Part I (read in order):
  Ch 1 → Ch 2 → Ch 3 → Ch 4
  Ch 5 (standalone, read anytime)

Part II (read after Part I, any order):
  Ch 6  (benefits from Ch 1)
  Ch 7  (benefits from Ch 3)
  Ch 8  (standalone)
  Ch 9  (benefits from Ch 1-8)
  Ch 10 (benefits from Ch 1-4)

Part III (read anytime):
  Ch 11 (standalone)
  Ch 12 (standalone)
  Ch 14 (standalone)
  Ch 15 (standalone)
  Ch 17 (benefits from Ch 12)
  Ch 20 (benefits from Ch 12)

Part IV (read after Parts I-II):
  Ch 13 (benefits from Ch 1-4, 7)
  Ch 18 (benefits from Ch 4)
  Ch 19 (benefits from Ch 7, 13)

Part V (reference, anytime):
  Ch 16, Appendix A
```

---

## AI Scannability

Every chapter includes:
- **HTML comment metadata** at the top with: `CHAPTER`, `TITLE`, `PART`, `PREREQS`, `KEY_TOPICS`, `DIFFICULTY`, `UPDATED`
- **Blockquote summary** with part, prerequisites, and difficulty level
- **"In This Chapter"** section listing all major sections
- **"Related Chapters"** with cross-references
- **Consistent heading hierarchy**: `#` title → `##` major sections → `###` subsections → `####` sub-subsections
- **Structured patterns**: "What it is / When to use / Trade-offs / Real-world examples" for every concept

To find content programmatically:
- Parse `<!-- ... -->` blocks for metadata
- Search `KEY_TOPICS` for topic matching
- Follow `PREREQS` for dependency ordering
- Filter by `DIFFICULTY` for level-appropriate content

---

## Key Principles Across All Chapters

1. **Start simple, add complexity only when the problem demands it**
2. **Every pattern has a cost — the best architecture is the simplest one that solves actual problems**
3. **Measure before optimizing — intuition about bottlenecks is usually wrong**
4. **Design for failure — the question is not *if* but *when* and *how fast you recover***
5. **Composition over invention — compose proven primitives rather than building from scratch**

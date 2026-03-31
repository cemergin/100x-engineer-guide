<!--
  TYPE: index
  TITLE: The 100x Engineer Guide
  CHAPTERS: 35
  PARTS: 5
  APPENDICES: 1
  UPDATED: 2026-03-24
  STRUCTURE: narrative-hierarchy
  AI_NOTE: Each chapter file contains an HTML comment metadata block with CHAPTER, TITLE, PART, PREREQS, KEY_TOPICS, DIFFICULTY, UPDATED fields. Use these for filtering, prerequisite graphs, and topic search. Files are organized into subdirectories by Part.
-->

# The 100x Engineer Guide
### Backend & Software Engineering Mastery

A comprehensive, open-source mega-guide covering every paradigm, philosophy, and hard skill needed to become a lead/staff+ engineer — organized as a narrative that builds from theory to practice.

**35 chapters** · **~47,000 lines** · **~3.0 MB** · **5 parts + appendices**

```
100x-engineer-guide/
├── part-1-foundations/          ← Theory: systems, data, architecture, reliability, security
├── part-2-applied-engineering/  ← Domains: concurrency, DevOps, testing, leadership, API design
├── part-3-tooling-practice/     ← Hands-on: languages, Linux/Vim/Git, AI tools, codebase org
├── part-4-cloud-operations/     ← Production: cloud, monitoring, AWS/Firebase, incident stories
├── course/                      ← 97 hands-on modules across 3 progressive loops (see below)
├── appendices/                  ← Reference: reading list, 250+ term glossary
└── README.md                    ← You are here
```

---

## Quick Start — Reading Paths

| Your Goal | Start Here | Then |
|-----------|-----------|------|
| **Learn from zero** | Part I: Ch 1 → 2 → 3 → 4 → 5 | Part II, then Part III |
| **System design interviews** | Ch 1, 22, 3, 23 | Ch 2, 6, 25, Glossary |
| **Get productive immediately** | Ch 12 (tooling), 20 (env mgmt), 17 (Claude Code) | Ch 15, 14 |
| **Ship to production** | Ch 13 (cloud), 18 (monitoring), 19 (AWS) | Ch 4, 7, 26 |
| **Level up to staff+** | Ch 9 (leadership), 29 (career), 10 (emerging) | Ch 27, 16 |
| **Debug a production issue NOW** | Ch 18 (debugging), 21 (networking), 24 (DB internals) | Ch 26 (war stories) |
| **Quick lookup** | [Glossary](./appendices/appendix-glossary.md) (250+ terms) | [Resources](./appendices/16-essential-resources.md) (49 papers/books) |

---

## [Part I — Foundations](./part-1-foundations/)
*The theory and principles that underpin everything else.*

| Ch | Title | Difficulty | What You'll Learn |
|----|-------|-----------|-------------------|
| 1 | [System Design Paradigms](./part-1-foundations/01-system-design.md) | Advanced | CAP/PACELC, consistency models, Paxos/Raft, distributed transactions, CRDTs, sharding, load balancing |
| 2 | [Data Engineering](./part-1-foundations/02-data-engineering.md) | Inter→Adv | SQL/NoSQL/NewSQL paradigms, data modeling, indexing, caching strategies, ETL/ELT, CDC, data mesh |
| 3 | [Architecture Patterns](./part-1-foundations/03-architecture-patterns.md) | Inter→Adv | Monolith→microservices, hexagonal/clean/vertical slice, DDD, event-driven, CQRS, REST/gRPC/GraphQL |
| 4 | [Reliability Engineering](./part-1-foundations/04-reliability-engineering.md) | Inter→Adv | SRE, SLOs/SLIs/error budgets, observability, circuit breaker, bulkhead, chaos engineering |
| 5 | [Security Engineering](./part-1-foundations/05-security-engineering.md) | Intermediate | OAuth/OIDC/JWT, OWASP Top 10, cryptography, infrastructure security, GDPR/SOC2 |
| 21 | [Networking & Protocols](./part-1-foundations/21-networking-protocols.md) | Inter→Adv | TCP internals, TLS 1.3 handshake, HTTP lifecycle, DNS, WebSocket, gRPC/protobuf, network debugging |
| 22 | [Algorithms & Data Structures](./part-1-foundations/22-algorithms-data-structures.md) | Inter→Adv | Hash maps, B-trees, LSM trees, bloom filters, LRU cache, rate limiter, consistent hashing — with code |
| 24 | [Database Internals](./part-1-foundations/24-database-internals.md) | Advanced | Postgres MVCC/WAL/vacuum/planner, MySQL InnoDB, DynamoDB internals, EXPLAIN ANALYZE, perf tuning |
| 32 | [Software Engineering Principles](./part-1-foundations/32-software-engineering-principles.md) | Beg→Adv | SOLID with real code, DRY/KISS/YAGNI, coupling/cohesion, 10 essential design patterns, clean code, code smells, composition vs inheritance, FP vs OOP |

> **Read order:** 1 → 2 → 3 → 4 → 5 (core sequence), then 21, 22, 24 in any order.

---

## [Part II — Applied Engineering](./part-2-applied-engineering/)
*Deeper dives into specialized domains. Read after Part I, in any order.*

| Ch | Title | Difficulty | What You'll Learn |
|----|-------|-----------|-------------------|
| 6 | [Concurrency & Computing](./part-2-applied-engineering/06-concurrency-computing.md) | Advanced | Threads, event loop, actors, CSP, mutex/CAS/lock-free, deadlocks, memory models, GC, FP/OOP |
| 7 | [DevOps & Infrastructure](./part-2-applied-engineering/07-devops-infrastructure.md) | Intermediate | IaC/Terraform, containers/K8s, CI/CD, 12-factor app, DNS/CDN, service mesh, platform engineering |
| 8 | [Testing & Quality](./part-2-applied-engineering/08-testing-quality.md) | Intermediate | TDD/BDD/property-based/mutation testing, all test types, performance testing, refactoring patterns |
| 9 | [Engineering Leadership](./part-2-applied-engineering/09-engineering-leadership.md) | Advanced | ADRs/RFCs, system thinking, DORA/SPACE metrics, estimation, technical strategy, communication |
| 10 | [Emerging Paradigms](./part-2-applied-engineering/10-emerging-paradigms.md) | Advanced | AI-native engineering, RAG/agents, edge computing, CRDTs, durable execution, Wasm, FinOps |
| 23 | [System Design Case Studies](./part-2-applied-engineering/23-system-design-case-studies.md) | Advanced | 10 full designs: URL shortener, chat, payments, video streaming, ride-sharing — with diagrams |
| 25 | [API Design & DX](./part-2-applied-engineering/25-api-design.md) | Intermediate | REST conventions, error handling, pagination, versioning, idempotency, webhooks, SDK design |
| 29 | [Career Engineering](./part-2-applied-engineering/29-career-engineering.md) | All levels | Promotion packets, brag docs, staff+ archetypes, IC vs mgmt, negotiation, influence, brand |
| 30 | [Data Privacy & Compliance](./part-2-applied-engineering/30-data-privacy-ethics.md) | Intermediate | GDPR implementation, anonymization, crypto-shredding, consent management, HIPAA/SOC2/PCI |

---

## [Part III — Tooling & Practice](./part-3-tooling-practice/)
*Hands-on skills and daily tools. Read at any point.*

| Ch | Title | Difficulty | What You'll Learn |
|----|-------|-----------|-------------------|
| 11 | [Programming Languages](./part-3-tooling-practice/11-programming-languages.md) | Intermediate | Go, Rust, Python, Java/Kotlin, TypeScript, C#, Elixir, Zig — runnable servers, comparison tables |
| 12 | [Developer Tooling](./part-3-tooling-practice/12-developer-tooling-productivity.md) | Beg→Adv | Linux, bash, SSH, fzf/tmux/rg, Vim/Neovim, VS Code, Git advanced, Docker, Terraform, kubectl |
| 14 | [AI-Powered Engineering](./part-3-tooling-practice/14-ai-powered-engineering.md) | Beg→Inter | AI for project planning, ERD design, code review, debugging, prompt engineering as a skill |
| 15 | [Codebase Organization](./part-3-tooling-practice/15-codebase-organization.md) | Beg→Adv | Linting setup, CI/CD pipelines, team-size org (solo→100+), monorepo patterns, fitness functions |
| 17 | [Claude Code Mastery](./part-3-tooling-practice/17-claude-code-mastery.md) | Beg→Adv | Skills/plugins/hooks, MCP servers, agent teams, CLAUDE.md, plan mode, TDD/debugging workflows |
| 20 | [Dependency & Env Management](./part-3-tooling-practice/20-dependency-env-management.md) | Intermediate | Nix, asdf/mise, nvm/pyenv/rustup, lockfiles, Docker dev envs, devcontainers, reproducible builds |
| 27 | [Technical Writing](./part-3-tooling-practice/27-technical-writing.md) | Beg→Inter | Diátaxis framework, READMEs, ADRs, RFCs, commit messages, runbooks, postmortems, code comments |
| 28 | [Code Reading & Open Source](./part-3-tooling-practice/28-code-reading-oss.md) | Beg→Inter | Navigating unfamiliar codebases, OSS contribution workflow, licensing, building your profile |
| 33 | [GitHub Actions Mastery](./part-3-tooling-practice/33-github-actions-mastery.md) | Inter→Adv | Reusable workflows, composite actions, matrix strategies, OIDC federation, self-hosted runners, monorepo CI, custom actions, security hardening |
| 34 | [Spec-Driven Development](./part-3-tooling-practice/34-spec-driven-development.md) | Inter→Adv | RFCs, design docs, contract-first API design (OpenAPI/AsyncAPI), executable specs (BDD/Gherkin), AI-native specs, CLAUDE.md as spec |

---

## [Part IV — Cloud & Operations](./part-4-cloud-operations/)
*Running systems in production at scale. Read after Parts I–II.*

| Ch | Title | Difficulty | What You'll Learn |
|----|-------|-----------|-------------------|
| 13 | [Cloud & System Integration](./part-4-cloud-operations/13-cloud-system-integration.md) | Advanced | VPC networking, queues (Kafka/SQS), event-driven, data flow, migrations, full system walkthrough |
| 18 | [Debugging & Monitoring](./part-4-cloud-operations/18-debugging-profiling-monitoring.md) | Inter→Adv | Debugging methodology, flame graphs, Datadog, Prometheus+Grafana, ELK, OpenTelemetry, Sentry |
| 19 | [AWS & Firebase Deep Dive](./part-4-cloud-operations/19-aws-firebase-deep-dive.md) | Inter→Adv | AWS 20 core services, VPC, IAM, cost optimization, 5 reference architectures. Firebase: Firestore, Auth |
| 26 | [Incident War Stories](./part-4-cloud-operations/26-incident-war-stories.md) | Intermediate | 9 real outages analyzed: Cloudflare, GitHub, AWS S3, Knight Capital, Facebook BGP, CrowdStrike |
| 31 | [GCP Deep Dive](./part-4-cloud-operations/31-gcp-deep-dive.md) | Inter→Adv | Compute Engine, Cloud Run, GKE, BigQuery, Spanner, Pub/Sub, Cloud Storage, IAM, cost optimization, GCP vs AWS comparison |
| 35 | [Everything as Code](./part-4-cloud-operations/35-everything-as-code.md) | Inter→Adv | Policy-as-code (OPA/Kyverno/Checkov), secrets management (Vault/SOPS), DB migrations, observability-as-code, compliance-as-code, IaC testing, GitOps (ArgoCD/Flux), Crossplane, Backstage |

> **Narrative:** How all the pieces connect (Ch 13) → how to find and fix problems (Ch 18) → AWS in depth (Ch 19) → GCP in depth (Ch 31) → codify everything (Ch 35) → learning from others' failures (Ch 26).

---

## [Appendices](./appendices/)
*Reference material. Look things up as needed.*

| Ch | Title | What's Inside |
|----|-------|--------------|
| 16 | [Essential Resources](./appendices/16-essential-resources.md) | 49 foundational papers, books, blogs, and newsletters with summaries |
| A | [Glossary & Dictionary](./appendices/appendix-glossary.md) | 250+ engineering terms, abbreviations, and culture phrases — ACID to yak shaving |

---

## Chapter Dependency Graph

```
Part I — Foundations (start here):
  Ch 1 → Ch 2 → Ch 3 → Ch 4        (core sequence)
  Ch 5                                (standalone)
  Ch 21, 22, 24, 32                    (standalone, enrich Part I)

Part II — Applied Engineering (after Part I, any order):
  Ch 6          ← benefits from Ch 1
  Ch 7          ← benefits from Ch 3
  Ch 8          ← standalone
  Ch 9          ← benefits from broad experience
  Ch 10         ← benefits from Ch 1-4
  Ch 23         ← benefits from Ch 1, 2, 3, 22
  Ch 25         ← benefits from Ch 3
  Ch 29, 30     ← standalone

Part III — Tooling & Practice (anytime):
  Ch 11, 12, 14, 15, 27, 28    ← standalone
  Ch 17                          ← benefits from Ch 12
  Ch 20                          ← benefits from Ch 12
  Ch 33                          ← benefits from Ch 7, 15, 8
  Ch 34                          ← benefits from Ch 27, 25, 9

Part IV — Cloud & Operations (after Parts I-II):
  Ch 13         ← benefits from Ch 1-4, 7
  Ch 18         ← benefits from Ch 4
  Ch 19         ← benefits from Ch 7, 13
  Ch 31         ← benefits from Ch 7, 13
  Ch 35         ← benefits from Ch 7, 5
  Ch 26         ← benefits from Ch 4, 7

Appendices — anytime:
  Ch 16, Appendix A
```

---

## How Each Chapter Is Structured

Every chapter follows a consistent, AI-scannable format:

```
<!-- HTML metadata: CHAPTER, TITLE, PART, PREREQS, KEY_TOPICS, DIFFICULTY, UPDATED -->

# Chapter N: Title

> Part · Prerequisites · Difficulty

Summary sentence.

### In This Chapter        ← section index
### Related Chapters       ← cross-references

---

## 1. MAJOR SECTION
### 1.1 Subsection
**What it is:** ...
**When to use:** ...
**Trade-offs:** ...
**Real-world example:** ...
```

**To find content programmatically:**
- Parse `<!-- ... -->` blocks for structured metadata
- Search `KEY_TOPICS` for topic matching
- Follow `PREREQS` to build reading order
- Filter by `DIFFICULTY` for level-appropriate content
- Each subdirectory has its own `README.md` with local navigation

---

## Interactive Learning with AI

The [`course/`](./course/) directory contains **104 hands-on modules** organized in 3 progressive loops, built from the same material as the guide chapters. Each module has exercises you build on a running project (TicketPulse) so concepts compound as you go:

- **Loop 1** (M01–M30): Foundations — dev environment, databases, APIs, testing, security, observability
- **Loop 2** (M31–M60): Applied — microservices, Kafka, Kubernetes, Terraform, advanced patterns
- **Loop 3** (M61–M90): Mastery — multi-region, system design, incident response, capstone

This course pairs with **[Tech Skill Builder](https://github.com/cemergin/tech-skill-builder)**, a Claude Code plugin that turns these modules into interactive learning experiences.

### Learn with an AI Tutor

Use `/tech-skill-builder:learn` in [Claude Code](https://claude.ai/claude-code) to start a guided tutoring session through any module. The tutor:

- Walks you through concepts step-by-step with Socratic questioning
- Generates hands-on exercises tailored to your skill level
- Provides real-time feedback on your code and understanding
- Adapts pacing based on your progress

### Build Your Own Course

Use `/tech-skill-builder:create-course` to generate new courses from scratch — whether you want to extend this guide with your own topics or create entirely new curricula for your team.

### Getting Started

```bash
# Install the plugin in Claude Code
claude plugin add cemergin/tech-skill-builder

# Start learning any module
/tech-skill-builder:learn

# Create a new course
/tech-skill-builder:create-course
```

---

## Contributing

This guide is open source. To improve it:

1. Fork the repo
2. Create a branch (`git checkout -b improve/chapter-name`)
3. Make your changes (follow the chapter format above)
4. Submit a PR with a description of what you improved

Improvements welcome: corrections, deeper examples, new case studies, updated tool versions, additional resources.

---

## Key Principles

1. **Start simple, add complexity only when the problem demands it**
2. **Every pattern has a cost — the best architecture is the simplest one that solves actual problems**
3. **Measure before optimizing — intuition about bottlenecks is usually wrong**
4. **Design for failure — the question is not *if* but *when* and *how fast you recover***
5. **Composition over invention — compose proven primitives rather than building from scratch**

---

*Built with [Claude Code](https://claude.ai/claude-code). Contributions welcome.*

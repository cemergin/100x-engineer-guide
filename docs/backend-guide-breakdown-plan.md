# Backend Guide Breakdown Plan

> **Status:** Not started — feasibility analysis complete, ready to execute when time allows.
> **Estimated effort:** ~2-3 hours with diverge-converge agents
> **Created:** 2026-04-10

## Goal

Split 6 monolithic chapters (2,000-2,800 lines) into focused sub-chapters (~1,000-1,400 lines) to match the modularity of the AI Engineer and Frontend guides.

**Before:** 35 chapters, avg 1,881 lines, max 2,803
**After:** 45 chapters, avg ~1,430 lines, max ~1,700

## Phase 1: High ROI Splits (do first)

| Chapter | Lines | Split Into | Est. Lines |
|---------|------:|-----------|------------|
| Ch 19 - AWS & Firebase | 2,779 | **19a: AWS Deep Dive** + **19b: Firebase Deep Dive** | ~1,700 + ~1,030 |
| Ch 12 - Developer Tooling | 2,610 | **12a: Linux/Shell/Editors** + **12b: Git/Docker/Terraform/K8s** | ~1,420 + ~1,140 |
| Ch 34 - Spec-Driven Dev | 2,803 | **34a: RFCs & ADRs** + **34b: Contract-First API** + **34c: AI-Native Specs** | ~900 + ~1,150 + ~750 |

## Phase 2: Medium ROI Splits

| Chapter | Lines | Split Into | Est. Lines |
|---------|------:|-----------|------------|
| Ch 25 - API Design | 2,647 | **25a: REST Design** + **25b: API Ops & DX** + **25c: GraphQL** | ~970 + ~920 + ~540 |
| Ch 33 - GitHub Actions | 2,662 | **33a: Actions Core** + **33b: Advanced Actions** | ~1,050 + ~1,600 |
| Ch 24 - Database Internals | 2,614 | **24a: Engine Internals** + **24b: Query Optimization** + **24c: SQL Mastery** | ~980 + ~1,090 + ~490 |

## Keep Whole (skip)

Ch 22 (Algorithms), Ch 23 (Case Studies), Ch 36 (Beast Mode), Ch 31 (GCP), Ch 18 (Debugging), Ch 35 (Everything as Code) — tightly coupled, reference chapters, or barely over threshold.

## Phase 3: Cross-Reference Updates

- ~35-40 files need "Ch 24" → "Ch 24a/24b" style reference updates
- 4 Part READMEs updated
- Root README chapter tables, dependency graph, reading paths updated
- Course modules that reference split chapters (~30-40 of 108)

## Phase 4: Add Spiral Threads (optional, independent)

Five natural spiral threads to add:
1. **DATABASE:** Ch 2 → Ch 24 → Ch 23 → Ch 18
2. **SECURITY:** Ch 5 → Ch 19 → Ch 30 → Ch 33 → Ch 35
3. **TESTING:** Ch 8 → Ch 34 → Ch 33 → Ch 15 → Ch 17
4. **ARCHITECTURE:** Ch 3 → Ch 9 → Ch 34 → Ch 23
5. **OBSERVABILITY:** Ch 4 → Ch 18 → Ch 36 → Ch 26

## Execution

Use the guide-creator diverge-converge method (tech-skill-builder plugin):
- 5-6 agents for splitting (Phase 1+2)
- 2-3 agents for cross-references (Phase 3)
- 1 agent for quality review
- Total: 6-8 agents, ~2-3 hours elapsed

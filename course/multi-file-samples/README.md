# Multi-File Module Format — Reference Samples

This directory contains three modules converted from single-file format into the multi-file format prescribed by the tech-skill-builder course creator spec.

## Why Multi-File?

The single-file format (one `.md` per module) creates a great reading experience. The multi-file format enables:

- **Skip-ahead decisions** — `episode.md` lets learners quickly assess if they need a module
- **Tutoring integration** — The tech-tutor skill can target lesson vs exercise content with different tutoring modes
- **Modular content delivery** — Foundation, Practice, and Mastery tiers can be served independently
- **Runnable starter code** — `starter/` and `solution/` directories can accompany exercises

## File Format

Each module directory contains:

| File | Purpose | Bloom's Level |
|------|---------|---------------|
| `episode.md` | "In This Episode" — skip-ahead summary | N/A |
| `lesson.md` | Foundation — concepts, analogies, mental models | Remember + Understand |
| `exercise.md` | Practice — guided, step-by-step code-along | Apply + Analyze |
| `challenge.md` | Mastery — open-ended problem for independent solving | Evaluate + Create |

## Scaffolding Across Loops

| Aspect | Loop 1 (Foundation) | Loop 2 (Practice) | Loop 3 (Mastery) |
|--------|-------|--------|---------|
| Lesson detail | Full analogies, step-by-step | Builds on prior, explains new | Brief, focuses on what's new |
| Exercise steps | 10-15 granular steps | 6-10 moderate steps | 3-5 high-level steps |
| Hints in challenge | 3 hints, generous | 3 hints, behind `<details>` | 1-2 hints, behind `<details>` |
| Solutions | Full with explanation | Included with brief explanation | In `solution/` directory only |

## Samples in This Directory

1. **L1-M05** (PostgreSQL From Zero) — Loop 1, heavy scaffolding
2. **L2-M31** (The Strangler Fig) — Loop 2, medium scaffolding
3. **L3-M68** (The Ticket Rush Problem) — Loop 3, light scaffolding

## How to Convert Additional Modules

1. Read the source module file from `modules/loop-N/`
2. Split content into lesson (concepts) vs exercise (hands-on steps) vs challenge (open problems)
3. Create an episode.md from the module's header/goals
4. Adjust scaffolding level based on the loop
5. Maintain the "Nerdy Friend" voice throughout

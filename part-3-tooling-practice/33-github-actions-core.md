<!--
  CHAPTER: 33
  TITLE: GitHub Actions Core
  PART: III — Tooling & Practice
  PREREQS: Ch 7 (DevOps), Ch 15 (Codebase Organization), Ch 8 (Testing)
  KEY_TOPICS: GitHub Actions workflow syntax, reusable workflows, composite actions, matrix strategies, OIDC federation
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 33: GitHub Actions Core

> **Part III — Tooling & Practice** | Prerequisites: Ch 7 (DevOps), Ch 15, Ch 8 | Difficulty: Intermediate to Advanced

From basic YAML to production-grade CI/CD — reusable workflows, OIDC federation, self-hosted runners, monorepo patterns, custom actions, security hardening, and performance optimization that separates copy-paste pipelines from engineered delivery systems.

### In This Chapter
- Why a Dedicated Chapter on GitHub Actions
- Workflow Syntax Deep Dive
- Reusable Workflows
- Composite Actions
- Matrix Strategies
- OIDC Federation (The Modern Way)

### Related Chapters
- Chapter 33b — Advanced GitHub Actions: self-hosted runners, monorepo CI, custom actions, security, performance, and advanced patterns
- Chapter 7 — DevOps fundamentals and CI/CD concepts
- Chapter 8 — Testing strategies that CI enforces
- Chapter 15 — Codebase organization, linting, basic CI/CD pipeline setup
- Chapter 5 — Security principles (applied here to supply chain)
- Chapter 19 — AWS infrastructure (OIDC federation target)
- Chapter 12 — Git workflows and tooling

---

## 1. WHY A DEDICATED CHAPTER ON GITHUB ACTIONS

Here is a story. A team of eight engineers spent 45 minutes every week babysitting deployments. Not because the software was broken — because the CI pipeline was. Tests ran in random order. Secrets were stored as plaintext environment variables. The deploy job would silently succeed even when Docker push failed. One engineer's entire Friday was consumed by a workflow that had been copy-pasted twelve times across twelve microservices, and now needed updating in all twelve places.

Another 15 minutes had been shaved off one team's PR cycle by doing nothing more than adding `cancel-in-progress: true` to their concurrency group. That is not a dramatic story. That is Tuesday.

The difference between those two teams is not talent. It is whether anyone had stopped to treat CI/CD as engineering.

Chapter 15 §2 covers CI/CD pipeline basics — lint, test, build, deploy stages. That is enough to get a pipeline running. It is not enough to run one well.

**The gap between "works" and "mastery" is enormous.** A basic pipeline takes 15 minutes. A well-engineered one takes 3 minutes, costs 60% less, is immune to supply chain attacks, requires zero secret rotation, and scales across 50 repositories without copy-pasting a single YAML file.

GitHub Actions is the dominant CI/CD platform. Over 85% of open-source projects use it. The majority of startups and a growing share of enterprises run on it. If you write backend code professionally, you will maintain GitHub Actions workflows. The question is whether you maintain them well.

**What this chapter covers that Ch 15 does not:**
- Reusable workflows and composite actions (DRY across repos)
- OIDC federation (zero long-lived secrets)
- Matrix strategies for exhaustive testing
- Self-hosted runners for cost and performance
- Security hardening against supply chain attacks
- Monorepo-specific CI patterns
- Building custom actions
- Performance optimization at scale

**The thesis:** CI/CD is infrastructure. Treat it with the same rigor you apply to your application code — version it, test it, review it, optimize it, secure it. As Ch 7 established, DevOps is not a role; it is a practice. Your GitHub Actions workflows are where that practice lives day-to-day.

---

## 2. WORKFLOW SYNTAX DEEP DIVE

Every workflow is a YAML file sitting in `.github/workflows/`. GitHub reads it, interprets the triggers, and spins up runners to execute the jobs. That part is simple. What separates a great pipeline from a mediocre one is deep fluency with the syntax — knowing not just how things work, but when to use each option and why.

### 2.1 Triggers (The `on:` Block)

Every workflow starts with a trigger. Most engineers know `push` and `pull_request`. There are many more — and the right trigger for the wrong situation is a common source of both wasted runner minutes and subtle security holes.

```yaml
on:
  # Code changes
  push:
    branches: [main, release/*]
    tags: ['v*']
    paths: ['src/**', 'package.json']
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]  # Default types if omitted
    paths-ignore: ['docs/**', '*.md']

  # Manual triggers
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options: [staging, production]
      dry_run:
        description: 'Dry run (no actual deploy)'
        type: boolean
        default: false

  # Scheduled (cron syntax, UTC)
  schedule:
    - cron: '0 6 * * 1'    # Every Monday at 6 AM UTC
    - cron: '0 */4 * * *'  # Every 4 hours

  # Cross-repo triggers
  repository_dispatch:
    types: [deploy-backend, run-integration-tests]

  # Called by other workflows (reusable)
  workflow_call:
    inputs:
      node_version:
        type: string
        default: '22'
    secrets:
      NPM_TOKEN:
        required: true
```

**Key distinctions:**

| Trigger | Runs on | Use Case |
|---------|---------|----------|
| `push` | Commit SHA on target branch | Post-merge CI, deploys |
| `pull_request` | Merge commit (PR + base) | Pre-merge validation |
| `pull_request_target` | Base branch HEAD | Safe access to secrets for fork PRs |
| `workflow_dispatch` | Any ref (branch/tag) | Manual deploys, ad-hoc tasks |
| `schedule` | Default branch only | Dependency updates, cleanup |
| `repository_dispatch` | Default branch | Cross-repo orchestration |
| `workflow_call` | Caller's context | Reusable workflows |

**Critical detail:** `pull_request` events from forks do not have access to secrets. This is a security feature, not a bug. If you need secrets for fork PR validation (e.g., to post comments), use `pull_request_target` with extreme caution — it runs in the context of the base branch and has full secret access. Getting this wrong is how you hand a stranger the keys to your cloud account.

### 2.2 Event Filtering

Path filtering is the single most impactful optimization for monorepos — and it costs you nothing but a few lines of YAML.

```yaml
# Only run when these paths change (positive filter)
on:
  push:
    branches: [main]
    paths:
      - 'apps/api/**'
      - 'packages/shared/**'
      - 'package.json'
      - '.github/workflows/api-ci.yml'
```

```yaml
# Run on everything EXCEPT these paths (negative filter)
on:
  push:
    branches: [main]
    paths-ignore:
      - '**/*.md'
      - 'docs/**'
```

**Rules:**
- `paths` and `paths-ignore` **cannot** be combined in the same trigger — use one or the other.
- Patterns use `fnmatch` syntax. `**` matches any directory depth.
- If only `paths` is set, the workflow only runs when those paths change.
- Always include the workflow file itself in `paths` so changes to CI trigger CI.

Tag filtering for releases:

```yaml
on:
  push:
    tags:
      - 'v[0-9]+.[0-9]+.[0-9]+'      # v1.2.3
      - 'v[0-9]+.[0-9]+.[0-9]+-*'    # v1.2.3-beta.1
```

### 2.3 Context Objects

GitHub Actions exposes rich context objects that let your workflows make intelligent decisions based on who triggered them, what changed, and where they are running. Think of these as the sensor inputs for your automation assembly line.

```yaml
steps:
  - name: Context examples
    run: |
      echo "Event: ${{ github.event_name }}"           # push, pull_request, etc.
      echo "Ref: ${{ github.ref }}"                     # refs/heads/main, refs/tags/v1.0
      echo "SHA: ${{ github.sha }}"                     # Full commit SHA
      echo "Actor: ${{ github.actor }}"                 # Who triggered
      echo "Repo: ${{ github.repository }}"             # owner/repo
      echo "Run ID: ${{ github.run_id }}"               # Unique run identifier
      echo "Run number: ${{ github.run_number }}"       # Sequential per workflow
      echo "Server URL: ${{ github.server_url }}"       # https://github.com
      echo "API URL: ${{ github.api_url }}"             # https://api.github.com
      echo "Workspace: ${{ github.workspace }}"         # /home/runner/work/repo/repo
```

**Cross-step data passing:**

```yaml
steps:
  - name: Generate version
    id: version
    run: echo "tag=v$(date +%Y%m%d)-${{ github.run_number }}" >> "$GITHUB_OUTPUT"

  - name: Use version
    run: echo "Deploying ${{ steps.version.outputs.tag }}"
```

**Cross-job data passing (via outputs):**

```yaml
jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.tag }}
      should_deploy: ${{ steps.check.outputs.deploy }}
    steps:
      - id: version
        run: echo "tag=v1.2.3" >> "$GITHUB_OUTPUT"
      - id: check
        run: echo "deploy=true" >> "$GITHUB_OUTPUT"

  deploy:
    needs: setup
    if: needs.setup.outputs.should_deploy == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying ${{ needs.setup.outputs.version }}"
```

### 2.4 Expressions and Conditionals

The `${{ }}` expression syntax is where your pipelines get smart. This is the logic layer of your assembly line — routing work to the right station, skipping steps that do not apply, catching failures before they propagate.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Only on main
        if: github.ref == 'refs/heads/main'
        run: echo "On main branch"

      - name: Only on PRs to main
        if: github.event_name == 'pull_request' && github.base_ref == 'main'
        run: echo "PR targeting main"

      - name: Skip for bot commits
        if: "!contains(github.event.head_commit.message, '[skip ci]')"
        run: npm test

      - name: Run on failure of previous steps
        if: failure()
        run: echo "Something failed above"

      - name: Always run (even if cancelled)
        if: always()
        run: echo "Cleanup tasks"

      - name: Only if previous job succeeded
        if: success()
        run: echo "All good"
```

**Status check functions:**

| Function | When it runs |
|----------|-------------|
| `success()` | All previous steps succeeded (default if no `if:`) |
| `failure()` | Any previous step failed |
| `always()` | Always runs, even if workflow is cancelled |
| `cancelled()` | Workflow was cancelled |

**Type coercion gotcha:** Outputs are always strings. Comparing `steps.x.outputs.count > 0` compares strings lexicographically. Use `fromJSON()` to cast: `fromJSON(steps.x.outputs.count) > 0`. This one bites everyone at least once.

### 2.5 Permissions

Every workflow gets a `GITHUB_TOKEN` automatically. By default, it has broad permissions. The principle of least privilege from Ch 5 applies here just as much as it does to IAM roles — your CI token should only be able to do what it needs to do, and nothing more.

```yaml
# Top-level: restrict default permissions for all jobs
permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm test

  comment:
    runs-on: ubuntu-latest
    # Job-level: grant only what this job needs
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Post PR comment
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: 'Tests passed!'
            })
```

**Common permission scopes:**

| Scope | Typical need |
|-------|-------------|
| `contents: read` | Checkout code |
| `contents: write` | Push commits, create releases |
| `pull-requests: write` | Post PR comments, update status |
| `issues: write` | Create/update issues |
| `packages: write` | Publish to GitHub Packages |
| `id-token: write` | OIDC federation (see §6) |
| `actions: read` | List workflow runs |
| `security-events: write` | Upload SARIF (code scanning) |

**Rule:** Set `permissions: {}` at the top level (no permissions) and grant per-job. This is the principle of least privilege applied to CI. One compromised job should not give an attacker the ability to push to main.

### 2.6 Real-World Example: Monorepo Path Filtering

Here is what a properly constructed backend CI workflow looks like — the kind that is still fast and precise three years after you wrote it.

```yaml
name: Backend CI

on:
  pull_request:
    paths:
      - 'apps/api/**'
      - 'packages/shared/**'
      - 'packages/database/**'
      - '.github/workflows/backend-ci.yml'

permissions:
  contents: read
  pull-requests: write

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'

      - run: npm ci

      - name: Run migrations
        run: npx prisma migrate deploy
        working-directory: apps/api
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb

      - name: Run tests
        run: npm run test -- --filter=api
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
```

This workflow only triggers when backend-related files change. It spins up a real Postgres service container for integration tests. It caches npm dependencies. It runs in under 3 minutes for most changes. The frontend engineer who only touched a CSS file never waits for it.

---

## 3. REUSABLE WORKFLOWS

### 3.1 The Problem: The YAML Copy-Paste Trap

Picture this: you joined a company with 12 microservices. Each has its own `.github/workflows/ci.yml`. They all look identical — same Node setup, same lint step, same test runner, same deploy script. Because they were copy-pasted from one original workflow written in 2023.

Now the security team wants you to add Trivy container scanning to every pipeline. You spend two days opening 12 PRs, getting 12 rounds of review, merging 12 changes, and immediately forgetting about the two repos where the PR sat unreviewed for three weeks. Four months later, a vulnerability slips through one of those unscanned repos.

That is not a hypothetical. That is a pattern that plays out across companies of every size.

Reusable workflows are the solution. Write the pipeline once. Call it from everywhere. Update in one place.

### 3.2 Creating a Reusable Workflow

Reusable workflows live in a repository (often a dedicated `.github` repo) and are called via `workflow_call`:

```yaml
# .github/workflows/node-ci.yml in org/shared-workflows repo
name: Node.js CI (Reusable)

on:
  workflow_call:
    inputs:
      node_version:
        description: 'Node.js version'
        type: string
        default: '22'
      working_directory:
        description: 'Directory containing package.json'
        type: string
        default: '.'
      run_e2e:
        description: 'Run E2E tests'
        type: boolean
        default: false
      test_command:
        description: 'Test command to run'
        type: string
        default: 'npm test'
    secrets:
      NPM_TOKEN:
        required: false
      CODECOV_TOKEN:
        required: false
    outputs:
      coverage_percent:
        description: 'Test coverage percentage'
        value: ${{ jobs.test.outputs.coverage }}

jobs:
  lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ inputs.working_directory }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node_version }}
          cache: 'npm'
          cache-dependency-path: ${{ inputs.working_directory }}/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  test:
    runs-on: ubuntu-latest
    outputs:
      coverage: ${{ steps.coverage.outputs.percent }}
    defaults:
      run:
        working-directory: ${{ inputs.working_directory }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node_version }}
          cache: 'npm'
          cache-dependency-path: ${{ inputs.working_directory }}/package-lock.json
      - run: npm ci
      - name: Run tests
        run: ${{ inputs.test_command }} -- --coverage
      - name: Extract coverage
        id: coverage
        run: |
          PERCENT=$(jq '.total.lines.pct' coverage/coverage-summary.json)
          echo "percent=$PERCENT" >> "$GITHUB_OUTPUT"
      - name: Upload coverage
        if: inputs.run_e2e == false
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}

  e2e:
    if: inputs.run_e2e
    needs: [lint, test]
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ inputs.working_directory }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node_version }}
          cache: 'npm'
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npm run test:e2e
```

### 3.3 Calling a Reusable Workflow

From any repo in your organization, calling this reusable workflow is 12 lines:

```yaml
# .github/workflows/ci.yml in org/user-service repo
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  ci:
    uses: org/shared-workflows/.github/workflows/node-ci.yml@v1
    with:
      node_version: '22'
      working_directory: '.'
      run_e2e: true
      test_command: 'npm run test:unit'
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

Now when you need to add Trivy scanning to all 12 services, you edit one file. One PR. One review. Done.

**Key points:**
- Reference with `owner/repo/.github/workflows/file.yml@ref`
- `@ref` can be a branch, tag, or SHA. Use tags for stability (`@v1`), SHAs for security.
- `secrets: inherit` passes all secrets from the caller (convenient but less explicit).
- Reusable workflows can call other reusable workflows, up to 4 levels deep.

### 3.4 Reusable Workflows vs Composite Actions

Both solve code reuse. They solve different problems. Picking the wrong one is a common mistake.

| Aspect | Reusable Workflow | Composite Action |
|--------|------------------|-----------------|
| **Scope** | Entire workflow (multiple jobs) | Single set of steps within a job |
| **Trigger** | `workflow_call` | `uses:` in a step |
| **Can define jobs** | Yes | No (steps only) |
| **Can use services** | Yes | No |
| **Can use `secrets`** | Yes (explicit or inherit) | No (pass via inputs) |
| **Can define `strategy`** | Yes | No |
| **Caller visibility** | Shows as single job in UI | Steps visible inline |
| **Nesting limit** | 4 levels | Unlimited |
| **Best for** | Standardizing entire CI pipelines | Reusable setup/utility steps |

**Decision rule:** If you are standardizing what an entire pipeline looks like — the full sequence of lint, test, build, deploy — use a reusable workflow. If you are extracting common step sequences that appear inside jobs (checkout + setup + install), use a composite action. Think of reusable workflows as assembly line templates, and composite actions as reusable tool heads on each station.

---

## 4. COMPOSITE ACTIONS

### 4.1 Structure

A composite action lives in a directory with an `action.yml` file. It is the tool that every station on your assembly line can pick up and use.

```yaml
# .github/actions/setup-project/action.yml
name: 'Setup Project'
description: 'Checkout, setup Node, install dependencies with caching'

inputs:
  node_version:
    description: 'Node.js version'
    required: false
    default: '22'
  working_directory:
    description: 'Working directory'
    required: false
    default: '.'

outputs:
  cache_hit:
    description: 'Whether npm cache was hit'
    value: ${{ steps.cache.outputs.cache-hit }}

runs:
  using: 'composite'
  steps:
    - name: Checkout
      uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

    - name: Setup Node.js
      uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af  # v4.1.0
      with:
        node-version: ${{ inputs.node_version }}
        cache: 'npm'
        cache-dependency-path: ${{ inputs.working_directory }}/package-lock.json
      id: cache

    - name: Install dependencies
      shell: bash
      working-directory: ${{ inputs.working_directory }}
      run: npm ci

    - name: Verify installation
      shell: bash
      working-directory: ${{ inputs.working_directory }}
      run: |
        echo "Node $(node --version)"
        echo "npm $(npm --version)"
        echo "Dependencies installed: $(ls node_modules | wc -l) packages"
```

**Important:** Every `run:` step in a composite action **must** specify `shell:`. This is not optional — GitHub Actions cannot infer the shell when the action might be called from different operating systems.

### 4.2 Using Composite Actions

**From the same repo (monorepo pattern):**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/setup-project
        with:
          node_version: '22'
          working_directory: 'apps/api'

      - name: Run tests
        run: npm test
        working-directory: apps/api
```

**From another repo:**

```yaml
steps:
  - uses: org/shared-actions/setup-project@v1
    with:
      node_version: '22'
```

### 4.3 Monorepo Pattern: Local Composite Actions

In a monorepo (see Ch 15 §3 for the full codebase organization philosophy), composite actions become the DRY mechanism for step sequences that repeat across every package workflow. Put them in `.github/actions/`:

```
.github/
  actions/
    setup-project/
      action.yml
    setup-database/
      action.yml
    deploy-service/
      action.yml
  workflows/
    api-ci.yml
    web-ci.yml
    shared-tests.yml
```

**Database setup composite action:**

```yaml
# .github/actions/setup-database/action.yml
name: 'Setup Test Database'
description: 'Run migrations and seed test data'

inputs:
  database_url:
    description: 'PostgreSQL connection string'
    required: true
  working_directory:
    description: 'Directory with Prisma schema'
    required: false
    default: '.'

runs:
  using: 'composite'
  steps:
    - name: Wait for Postgres
      shell: bash
      run: |
        for i in {1..30}; do
          pg_isready -h localhost -p 5432 && break
          echo "Waiting for Postgres... ($i/30)"
          sleep 1
        done

    - name: Run migrations
      shell: bash
      working-directory: ${{ inputs.working_directory }}
      env:
        DATABASE_URL: ${{ inputs.database_url }}
      run: npx prisma migrate deploy

    - name: Seed test data
      shell: bash
      working-directory: ${{ inputs.working_directory }}
      env:
        DATABASE_URL: ${{ inputs.database_url }}
      run: npx prisma db seed
```

Every workflow in the monorepo that needs a test database calls this action. When the migration tooling changes, you update one file.

### 4.4 Publishing to the Marketplace

To publish a composite action:

1. The `action.yml` must be at the repo root (not in a subdirectory).
2. Add `branding:` to `action.yml`:

```yaml
branding:
  icon: 'package'
  color: 'blue'
```

3. Create a GitHub Release. The marketplace listing is auto-generated from the release and `action.yml`.

**Versioning convention:** Tag releases as `v1.0.0`. Maintain a floating major version tag (`v1`) that always points to the latest `v1.x.x`. Consumers reference `@v1` for automatic minor/patch updates.

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# Update floating tag
git tag -fa v1 -m "Update v1 to v1.2.0"
git push origin v1 --force
```

---

## 5. MATRIX STRATEGIES

### 5.1 The Assembly Line Goes Wide

Matrix strategies are where GitHub Actions starts to feel genuinely powerful. Instead of running tests once, you fan out across every combination of OS, runtime version, and database version you care about — simultaneously. It is the CI equivalent of spinning up a hundred workers on an assembly line instead of one.

### 5.2 Basic Matrix

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        node: [20, 22]
        # Creates 4 jobs: ubuntu/20, ubuntu/22, macos/20, macos/22
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
      - run: npm ci
      - run: npm test
```

### 5.3 Include and Exclude

Fine-tune the matrix without testing every combination. Not every axis of variation is worth crossing with every other:

```yaml
strategy:
  matrix:
    node: [20, 22]
    postgres: [15, 16]
    include:
      # Add a specific combination with extra variables
      - node: 22
        postgres: 16
        coverage: true        # Only collect coverage on latest versions
      # Add an entirely new combination
      - node: 23
        postgres: 17
        experimental: true
    exclude:
      # Skip this specific combination
      - node: 20
        postgres: 16
```

### 5.4 Dynamic Matrix

Generate the matrix from a previous job. This is where things get genuinely elegant for monorepos — the pipeline figures out what to test based on what changed, rather than you hardcoding it.

```yaml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      packages: ${{ steps.changes.outputs.packages }}
    steps:
      - uses: actions/checkout@v4
      - id: changes
        run: |
          # Detect which packages changed
          PACKAGES=$(ls packages/ | jq -R -s -c 'split("\n") | map(select(. != ""))')
          echo "packages=$PACKAGES" >> "$GITHUB_OUTPUT"

  test:
    needs: detect-changes
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package: ${{ fromJSON(needs.detect-changes.outputs.packages) }}
    steps:
      - uses: actions/checkout@v4
      - run: npm test --workspace=packages/${{ matrix.package }}
```

### 5.5 Fail-Fast and Parallelism

```yaml
strategy:
  fail-fast: false     # Don't cancel other jobs when one fails
  max-parallel: 4      # Limit concurrent jobs (useful for rate-limited APIs)
  matrix:
    shard: [1, 2, 3, 4, 5]
```

**Default behavior:** `fail-fast: true` — if any matrix job fails, all other running matrix jobs are cancelled. Set `false` when you want to see all failures (e.g., to know which Node version breaks, not just that one does). Fail-fast is useful when you only care whether something passes. Fail-slow is useful when you are diagnosing compatibility.

### 5.6 Test Sharding

Split a large test suite across matrix runners for parallelism. This is one of the highest-ROI techniques in this entire chapter.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
        total_shards: [4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'
      - run: npm ci

      # Jest sharding
      - name: Run tests (shard ${{ matrix.shard }}/${{ matrix.total_shards[0] }})
        run: npx jest --shard=${{ matrix.shard }}/${{ matrix.total_shards[0] }}

      # OR Vitest sharding
      # - run: npx vitest --shard=${{ matrix.shard }}/${{ matrix.total_shards[0] }}

      # OR Playwright sharding
      # - run: npx playwright test --shard=${{ matrix.shard }}/${{ matrix.total_shards[0] }}
```

**Performance impact:** A 12-minute test suite split across 4 shards runs in ~3 minutes. The overhead of 4 parallel runners is about 30 seconds of setup each. Net win: 9 minutes per PR. If your team opens 20 PRs per day, that is 3 hours of engineer waiting time you have just eliminated — every single day.

### 5.7 Real-World Matrix: Multi-DB, Multi-Runtime

Here is the kind of matrix that gives you real confidence in cross-version compatibility:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: [20, 22]
        postgres: [15, 16]
        include:
          - node: 22
            postgres: 16
            upload_coverage: true
    services:
      postgres:
        image: postgres:${{ matrix.postgres }}
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
          cache: 'npm'
      - run: npm ci
      - run: npm test
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
      - name: Upload coverage
        if: matrix.upload_coverage
        uses: codecov/codecov-action@v4
```

---

## 6. OIDC FEDERATION (THE MODERN WAY)

### 6.1 The Credential Graveyard

Every company has a `SECRETS_THAT_DEFINITELY_ROTATE` Notion doc that has not been updated since 2022. You know the one. Inside: AWS access keys for production, added by an engineer who left the company. Rotation policy: "TODO." Permissions: `AdministratorAccess`, because making narrow IAM policies was annoying and there was a deadline.

This is how breaches happen. Not dramatically. Just gradually, through accumulated laziness and the friction of doing the secure thing.

OIDC federation eliminates this entire class of problem. GitHub issues a short-lived JWT when your workflow runs. Your cloud provider validates it and issues temporary credentials. No secrets stored in GitHub. No rotation needed. Audit trail built in. When the job finishes, the credentials expire. An attacker who somehow steals the token gets credentials that stopped working 15 minutes ago.

### 6.2 How It Works

```
GitHub Actions Runner                     AWS / GCP / Azure
        |                                        |
        |-- 1. Request OIDC token -------------->|
        |   (JWT signed by GitHub)               |
        |                                        |
        |<-- 2. Validate JWT --------------------|
        |   (check issuer, audience, claims)     |
        |                                        |
        |<-- 3. Issue temporary credentials -----|
        |   (15-60 min TTL, scoped role)         |
        |                                        |
        |-- 4. Use temporary creds ------------->
        |   (deploy, push to ECR, etc.)          |
```

The JWT contains claims about the workflow: repository, branch, environment, actor, job ID. Your cloud provider's trust policy can restrict access based on any of these. A role that only works when called from `repo:my-org/my-repo:environment:production` cannot be triggered by a PR from a fork, a branch deploy, or anything else.

### 6.3 AWS OIDC Setup

**Step 1: Create the OIDC Identity Provider in AWS (one-time setup):**

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

**Step 2: Create IAM Role with trust policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:my-org/my-repo:*"
        }
      }
    }
  ]
}
```

**Step 3: Lock down by branch and environment:**

```json
{
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:my-org/my-repo:environment:production"
    }
  }
}
```

The `sub` claim format is `repo:OWNER/REPO:CONTEXT`. Context can be:
- `ref:refs/heads/main` — only main branch
- `environment:production` — only the production environment
- `pull_request` — any PR (avoid for production roles)
- `*` — any context (least restrictive)

**Step 4: Workflow configuration:**

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write    # Required for OIDC
      contents: read
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy
          aws-region: us-east-1
          role-session-name: gha-deploy-${{ github.run_id }}

      - name: Deploy
        run: |
          aws ecs update-service --cluster prod --service api --force-new-deployment
```

No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` anywhere. No secrets page entry to forget about. The credentials appear, do their job, and vanish.

### 6.4 GCP Workload Identity Federation

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'deploy@my-project.iam.gserviceaccount.com'

      - uses: google-github-actions/setup-gcloud@v2

      - run: gcloud run deploy api --source . --region us-central1
```

### 6.5 Azure Federated Credentials

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          # No client-secret needed — OIDC handles it

      - run: az webapp deploy --name my-app --src-path ./dist
```

### 6.6 Credential Strategy Comparison

| Strategy | Rotation | Scope | Audit | Setup Effort | Best For |
|----------|----------|-------|-------|-------------|----------|
| Encrypted secrets | Manual (never in practice) | Broad | Minimal | Low | Quick prototypes |
| OIDC federation | Automatic (per-job) | Fine-grained | Full | Medium | Production workloads |
| HashiCorp Vault | Automatic (configurable TTL) | Fine-grained | Full | High | Multi-cloud, compliance |
| AWS Secrets Manager | Configurable | Per-secret | Full | Medium | App-level secrets |

**Recommendation:** Use OIDC for all cloud provider authentication in CI/CD. There is no good reason to store cloud credentials as GitHub secrets in 2026. If you are still doing it, stop reading, go set up OIDC, then come back.

---

*Next: Chapter 33b covers advanced GitHub Actions patterns — self-hosted runners, monorepo CI, custom actions, security hardening, performance optimization, and building the 100x CI/CD pipeline.*

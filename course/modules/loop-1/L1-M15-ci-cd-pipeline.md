# L1-M15: CI/CD Pipeline

> **Loop 1 (Foundation)** | Section 1C: Building the API | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M14 (Your First Deployment)
>
> **Source:** Chapters 25, 5, 7, 8 of the 100x Engineer Guide

---

## The Goal

Right now, TicketPulse depends on developers remembering to run the linter, the type checker, and the tests before pushing. They will not always remember. Bugs will slip through.

A CI/CD pipeline automates all of that. Every push triggers: lint, type check, test, build Docker image. If any step fails, the pipeline fails, and the code cannot be merged. No exceptions.

By the end of this module, you will have a working pipeline that runs on every push to GitHub.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Make sure your TicketPulse repo is on GitHub. If it is not:

```bash
cd ticketpulse

# Initialize git if needed
git init
git add -A
git commit -m "Initial commit"

# Create a GitHub repo and push
gh repo create ticketpulse --private --source=. --push
```

Verify:

```bash
gh repo view --web
# This opens the GitHub repo in your browser
```

Good. Now let us add a pipeline.

---

## 1. What CI/CD Actually Means

Two concepts, often conflated:

**Continuous Integration (CI):** Every push is automatically built and tested. The whole team merges to the main branch frequently (at least daily). If a push breaks the build, it is caught immediately.

**Continuous Delivery (CD):** Every change that passes CI *can* be deployed to production. A human decides when. The deploy button is always green.

**Continuous Deployment:** Every change that passes CI *is* deployed automatically. No human approval. (We will not do this yet -- too risky for a first pipeline.)

For TicketPulse, our pipeline will do:
1. **On every push:** lint -> type check -> test -> build Docker image
2. **On merge to main:** all of the above, plus tag the image for deployment

---

## 2. Build: The Workflow YAML

<details>
<summary>💡 Hint 1: YAML Structure -- on, jobs, steps</summary>
A GitHub Actions workflow has three levels: `on:` (triggers -- push, pull_request), `jobs:` (parallel units of work), and `steps:` within each job. Each step is either `uses:` (a reusable action like `actions/checkout@v4`) or `run:` (a shell command like `npm ci`). Use `actions/setup-node@v4` with `cache: 'npm'` to cache node_modules between runs.
</details>

<details>
<summary>💡 Hint 2: Parallel Jobs and the needs Keyword</summary>
Jobs run in parallel by default. `lint`, `typecheck`, and `test` can all run simultaneously since they are independent. Use `needs: [lint, typecheck, test]` on the `build` job so it only runs if all three pass. This cuts wall-clock time while still gating the Docker build on all checks.
</details>

<details>
<summary>💡 Hint 3: Service Containers for Integration Tests</summary>
Under the `test` job, add a `services:` block to spin up Postgres and Redis as sidecar containers. Set health check options with `--health-cmd "pg_isready -U ticketpulse"`. The services are accessible at `localhost:5432` and `localhost:6379`. Pass `DATABASE_URL` and `REDIS_URL` as `env:` on the test step.
</details>

Create the workflow file:

```bash
mkdir -p .github/workflows
```

```yaml
# .github/workflows/ci.yml

name: CI

# When to run this pipeline
on:
  push:
    branches: [main, 'feature/**']
  pull_request:
    branches: [main]

# Cancel in-progress runs for the same branch
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # ===================================================
  # Job 1: Lint & Format
  # ===================================================
  lint:
    name: Lint & Format
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run ESLint
        run: npm run lint

      - name: Check formatting (Prettier)
        run: npx prettier --check "src/**/*.ts"

  # ===================================================
  # Job 2: Type Check
  # ===================================================
  typecheck:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run TypeScript compiler
        run: npx tsc --noEmit

  # ===================================================
  # Job 3: Test
  # ===================================================
  test:
    name: Test
    runs-on: ubuntu-latest

    # Spin up Postgres for integration tests
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: ticketpulse
          POSTGRES_PASSWORD: ticketpulse
          POSTGRES_DB: ticketpulse_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U ticketpulse"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run migrations
        run: npm run db:migrate
        env:
          DATABASE_URL: postgresql://ticketpulse:ticketpulse@localhost:5432/ticketpulse_test

      - name: Run tests
        run: npm test -- --coverage
        env:
          DATABASE_URL: postgresql://ticketpulse:ticketpulse@localhost:5432/ticketpulse_test
          REDIS_URL: redis://localhost:6379
          JWT_SECRET: test-secret
          NODE_ENV: test

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage/

  # ===================================================
  # Job 4: Build Docker Image
  # ===================================================
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test]  # Only build if all checks pass

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false  # Don't push yet -- just verify the build works
          tags: ticketpulse:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Verify image size
        run: |
          docker image ls ticketpulse
          # Fail if image is larger than 500MB
          SIZE=$(docker image inspect ticketpulse:${{ github.sha }} --format='{{.Size}}')
          MAX_SIZE=$((500 * 1024 * 1024))
          if [ "$SIZE" -gt "$MAX_SIZE" ]; then
            echo "ERROR: Image size ($SIZE bytes) exceeds 500MB limit"
            exit 1
          fi
          echo "Image size: $((SIZE / 1024 / 1024))MB -- within limits"
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Let us walk through the important parts:

### `concurrency` block
If you push three commits in quick succession, you do not need three pipeline runs. The `cancel-in-progress: true` setting cancels older runs for the same branch. This saves CI minutes and gives faster feedback.

### Parallel jobs
`lint`, `typecheck`, and `test` run in parallel. They do not depend on each other, so running them simultaneously cuts wall-clock time roughly in thirds.

### `needs: [lint, typecheck, test]`
The `build` job only runs if all three preceding jobs pass. If linting fails, we do not waste time building a Docker image.

### Service containers
GitHub Actions can spin up Postgres and Redis as service containers. The tests connect to them at `localhost:5432` and `localhost:6379` just like in development.

### Caching
`cache: 'npm'` in the Node.js setup action caches `node_modules` between runs. The Docker build uses GitHub Actions cache (`type=gha`) to cache layers. These two caches can reduce run time from 8 minutes to under 3 minutes.

---

## 3. Add the npm Scripts

Make sure your `package.json` has the scripts the pipeline needs:

```json
{
  "scripts": {
    "build": "tsc",
    "start": "node dist/server.js",
    "dev": "ts-node-dev --respawn src/server.ts",
    "lint": "eslint src/ --ext .ts",
    "lint:fix": "eslint src/ --ext .ts --fix",
    "test": "jest",
    "test:watch": "jest --watch",
    "db:migrate": "ts-node src/db/migrate.ts"
  }
}
```

If you do not have ESLint configured:

```bash
npm install -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin
```

```json
// .eslintrc.json
{
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint"],
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }]
  },
  "env": {
    "node": true,
    "jest": true
  }
}
```

---

## 4. Try It: Push and Watch the Pipeline

```bash
git add .github/workflows/ci.yml .eslintrc.json
git commit -m "Add CI pipeline with lint, typecheck, test, and Docker build"
git push
```

Now watch it run:

```bash
# Watch the pipeline in your terminal
gh run watch

# Or open it in the browser
gh run view --web
```

You should see four jobs appear: Lint & Format, Type Check, Test, and Build Docker Image. The first three start in parallel. Build waits for all three to finish.

---

## 5. Debug: Intentionally Break the Pipeline

<details>
<summary>💡 Hint 1: Trigger a Lint Failure</summary>
Add `const unusedVariable = 'test';` inside any function in a TypeScript file. The `@typescript-eslint/no-unused-vars` rule will flag it. Push to see the Lint job fail while Type Check and Test may still pass -- but the Build job will not run because of `needs`.
</details>

<details>
<summary>💡 Hint 2: Watch It in Real Time</summary>
Use `gh run watch` to stream pipeline progress in your terminal. Or `gh run view --web` to open the GitHub Actions UI. You will see the red X on the Lint job and the Build job skipped with "Skipped: depends on lint".
</details>

<details>
<summary>💡 Hint 3: Fix, Commit, Push, Verify Green</summary>
Remove the unused variable, commit with a fix message, and push again. The `concurrency: cancel-in-progress: true` setting will cancel the old failing run. Watch the new run go green. This fix-push-check cycle is the core feedback loop of CI.
</details>

Let us see what happens when the pipeline catches a problem.

### Break a lint rule

Open any TypeScript file and add an unused variable:

```typescript
// src/routes/events.ts -- add this anywhere inside a function
const unusedVariable = 'this will fail linting';
```

```bash
git add -A
git commit -m "Intentionally break linting to test CI"
git push
```

Watch the pipeline:

```bash
gh run watch
```

The Lint job should fail with something like:

```
error  'unusedVariable' is assigned a value but never used  @typescript-eslint/no-unused-vars
```

The Type Check and Test jobs may pass, but the Build job will not run because `needs: [lint, typecheck, test]` requires ALL dependencies to succeed.

### Fix it and push again

Remove the unused variable and push:

```bash
# Remove the line you added
git add -A
git commit -m "Fix lint error: remove unused variable"
git push
```

Watch it go green:

```bash
gh run watch
```

This is the core value of CI: the pipeline catches what developers forget to check. The fix-push-check cycle becomes second nature.

---

## 6. Branch Protection

Now that the pipeline exists, enforce it. Go to your GitHub repo settings:

1. Settings -> Branches -> Add rule
2. Branch name pattern: `main`
3. Enable:
   - **Require a pull request before merging** (no direct pushes to main)
   - **Require status checks to pass** (select the CI jobs)
   - **Require branches to be up to date before merging**

Or do it with the CLI:

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  -X PUT \
  -f required_status_checks='{"strict":true,"contexts":["Lint & Format","Type Check","Test","Build Docker Image"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1}'
```

Now nobody can merge to `main` unless all CI checks pass. This is the single most impactful process improvement you can make to a team's development workflow.

---

## 7. Caching: Show the Speed Improvement

Run the pipeline twice and compare:

```bash
# First run (no cache)
gh run list --limit 2 --json databaseId,conclusion,createdAt,updatedAt

# Check the duration of each run
gh run view <RUN_ID> --json jobs --jq '.jobs[] | {name, conclusion, duration: (.completedAt | sub(.startedAt))}'
```

Typical results:

| Run | npm install | Docker build | Total |
|-----|------------|-------------|-------|
| First (cold cache) | 45s | 120s | ~4 min |
| Second (warm cache) | 8s | 15s | ~1.5 min |

The `cache: 'npm'` directive and Docker layer caching (`type=gha`) save enormous time. On a real project with many dependencies, the difference can be 8 minutes vs 2 minutes.

---

## 8. Reflect: Pipeline Optimization

> Your pipeline takes 8 minutes. What would you optimize first?
>
> Consider:
> 1. Which job takes the longest? (Usually `test` or `build`)
> 2. Are there jobs that could run in parallel but currently don't?
> 3. Is the Docker build caching layers effectively?
> 4. Are you installing dependencies multiple times across jobs? (Could use a shared cache or a "setup" job)
> 5. Do all tests need to run on every push, or could you run a fast subset on push and the full suite on PR?
>
> Optimization priority:
> - **First**: cache dependencies (biggest bang for the buck)
> - **Second**: parallelize independent jobs
> - **Third**: split slow tests from fast tests
> - **Last**: optimize the Docker build (multi-stage + layer caching)

> **Insight:** Google runs 150 million test cases per day in their CI system. Their rule: the build must be green within 15 minutes of any commit. They achieve this through massive parallelism, hermetic builds (every build starts from a clean state), and aggressive caching. Your TicketPulse pipeline is the same philosophy at a smaller scale.

---

## 9. The Deploy Step (Placeholder)

We are not deploying to production yet, but here is what the deploy step will look like when we add it in Loop 2:

```yaml
  # ===================================================
  # Job 5: Deploy (only on merge to main)
  # ===================================================
  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [build]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # In Loop 2, this will push to a container registry and
      # trigger a deployment to your hosting platform
      - name: Deploy (placeholder)
        run: |
          echo "Would deploy ticketpulse:${{ github.sha }} to production"
          echo "Commit: ${{ github.sha }}"
          echo "Branch: ${{ github.ref_name }}"
          echo "Author: ${{ github.actor }}"
```

The `if: github.ref == 'refs/heads/main'` ensures deploys only happen on merges to main, never on feature branches.

---

## 10. Common Pipeline Patterns

### Running different checks on different triggers

```yaml
on:
  push:
    branches: [main]           # Full pipeline on main
  pull_request:
    branches: [main]           # Full pipeline on PRs to main
  schedule:
    - cron: '0 6 * * 1'       # Full pipeline every Monday at 6am (catch dependency issues)
```

### Failing fast

If lint fails, there is no point running tests. The `needs` keyword handles this for sequential jobs. For parallel jobs, GitHub Actions does not natively support "cancel all on first failure," but the `concurrency` block helps.

### Matrix builds (testing multiple versions)

```yaml
strategy:
  matrix:
    node-version: [18, 20, 22]
```

This runs the job three times -- once for each Node.js version. Useful for libraries, overkill for applications (you deploy on one version).

---

## 11. Checkpoint

After this module, TicketPulse should have:

- [ ] `.github/workflows/ci.yml` with four jobs: lint, typecheck, test, build
- [ ] Pipeline runs automatically on every push and PR
- [ ] Lint, typecheck, and test jobs run in parallel
- [ ] Build job only runs if all three checks pass
- [ ] npm dependency caching reduces install time
- [ ] Docker build caching reduces image build time
- [ ] You have watched the pipeline fail on a lint error and then pass after fixing it
- [ ] Branch protection requires CI to pass before merging to main

**Next up:** L1-M16 where we add a real test suite -- unit tests for business logic, integration tests with a real database, and the testing pyramid in practice.

---

## Glossary

| Term | Definition |
|------|-----------|
| **CI (Continuous Integration)** | Automatically building and testing every push. Catches problems early. |
| **CD (Continuous Delivery)** | Every passing change can be deployed. A human clicks the button. |
| **CD (Continuous Deployment)** | Every passing change is deployed automatically. No human in the loop. |
| **Pipeline** | The sequence of automated steps (lint, test, build, deploy) triggered by a code change. |
| **GitHub Actions** | GitHub's built-in CI/CD platform. Workflows are defined in YAML files in `.github/workflows/`. |
| **Service container** | A Docker container (like Postgres) that GitHub Actions spins up alongside your job for integration testing. |
| **Branch protection** | GitHub settings that prevent pushing directly to a branch. Require PR reviews and CI checks to pass. |
| **Concurrency** | Controls how multiple pipeline runs for the same branch are handled. `cancel-in-progress` stops older runs. |
| **Cache** | Saved state (node_modules, Docker layers) reused between pipeline runs to save time. |

> **Going deeper:** In Loop 2, **L2-M55a (GitHub Actions Mastery)** takes everything here to the next level: reusable workflows across multiple services, matrix strategies, OIDC federation (no more stored secrets), monorepo path filtering, and supply-chain security hardening.
---

## What's Next

In **Testing Fundamentals** (L1-M16), you'll build on what you learned here and take it further.

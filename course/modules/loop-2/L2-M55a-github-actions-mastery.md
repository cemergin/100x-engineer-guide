# L2-M55a: GitHub Actions Mastery

> **Loop 2 (Practice)** | Section 2D+: Delivery & Automation | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M15 (CI/CD Pipeline)
>
> **Source:** Chapter 33 of the 100x Engineer Guide

> **Before you continue:** Your CI pipeline runs tests and deploys. But what if you needed to run tests across Node 18, 20, and 22? Or deploy to staging first, wait for approval, then deploy to production? How would you model that workflow?

---

## What You'll Learn

- How to eliminate CI/CD duplication across microservices using reusable workflows
- How to use matrix strategies for multi-dimensional testing (Node versions, Postgres versions, services)
- How to replace long-lived AWS credentials with OIDC federation for zero-secret deployments
- How to use path filtering in a monorepo so only the changed service gets CI runs
- How to harden your GitHub Actions supply chain against dependency confusion and compromised actions

## Why This Matters

In L1-M15, TicketPulse was a single service with a single CI workflow. That was fine. But Loop 2 changed everything. You extracted event-service, payment-service, and user-service. You have a monorepo with three services, each needing its own CI pipeline. If you copy-paste the workflow YAML three times, you now have three files to keep in sync. When you add a fourth service, you copy-paste again. When you need to update the Node version, you update it in four places. This is the same DRY violation you would never tolerate in application code, but teams tolerate it in CI configuration every day.

Beyond duplication, there is a security problem. Your L1-M15 pipeline probably stores `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as repository secrets. Those credentials never expire. If they leak -- through a log, a fork, or a compromised dependency -- an attacker has persistent access to your AWS account. OIDC federation eliminates this entirely: GitHub proves its identity to AWS on every run, and AWS issues short-lived credentials that expire in minutes.

This module takes your working L1-M15 pipeline and transforms it into a production-grade CI/CD system. Every pattern here is used by teams shipping real software at scale. You will feel the pain of duplication, then eliminate it.

## Prereq Check

You should have completed L1-M15 (CI/CD Pipeline). Specifically, you need:

- A working `.github/workflows/ci.yml` that runs lint, type check, test, and build on every push
- TicketPulse pushed to a GitHub repository
- Basic familiarity with GitHub Actions syntax: `on`, `jobs`, `steps`, `uses`, `run`
- Docker image build step in your pipeline (from L1-M15)

If your L1-M15 pipeline is not working, go back and fix it before continuing. Everything in this module builds on top of it.

---

## Part 1: Reusable Workflows

### The Problem

After the Loop 2 microservice extraction, your repository looks like this:

```
ticketpulse/
  services/
    event-service/
      src/
      package.json
      Dockerfile
      tsconfig.json
    payment-service/
      src/
      package.json
      Dockerfile
      tsconfig.json
    user-service/
      src/
      package.json
      Dockerfile
      tsconfig.json
  .github/
    workflows/
      ci.yml          # The L1-M15 workflow -- covers... what exactly?
```

Teams solve this by creating `ci-event.yml`, `ci-payment.yml`, and `ci-user.yml`. Each is 80-100 lines. 90% of the content is identical. When someone adds a `pnpm audit` step to one workflow, the other two do not get it. Drift is inevitable.

### The Solution: `workflow_call`

A reusable workflow is a workflow that other workflows can call, like a function. You define the inputs and secrets it accepts, and callers provide them.

Create the template:

```yaml
# .github/workflows/ci-template.yml
name: CI Template

on:
  workflow_call:
    inputs:
      node-version:
        description: 'Node.js version to use'
        required: false
        type: string
        default: '22'
      working-directory:
        description: 'Path to the service directory'
        required: true
        type: string
      service-name:
        description: 'Name of the service (for Docker tagging)'
        required: true
        type: string
      run-e2e:
        description: 'Whether to run E2E tests'
        required: false
        type: boolean
        default: false
    secrets:
      inherit

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ inputs.working-directory }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: ${{ inputs.node-version }}
          cache: 'pnpm'
          cache-dependency-path: ${{ inputs.working-directory }}/pnpm-lock.yaml

      - run: pnpm install --frozen-lockfile

      - run: pnpm run lint

      - run: pnpm run typecheck

  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ inputs.working-directory }}
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: ticketpulse
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: ticketpulse_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd="pg_isready -U ticketpulse"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: ${{ inputs.node-version }}
          cache: 'pnpm'
          cache-dependency-path: ${{ inputs.working-directory }}/pnpm-lock.yaml

      - run: pnpm install --frozen-lockfile

      - run: pnpm run test
        env:
          DATABASE_URL: postgresql://ticketpulse:testpassword@localhost:5432/ticketpulse_test

  build:
    needs: [lint-and-typecheck, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: docker/setup-buildx-action@b5ca514318bd6ebac0fb2aedd5d36ec1b5c232a2 # v3.10.0

      - uses: docker/build-push-action@263435318d21b8e681c14492fe198e19c816612b # v6.18.0
        with:
          context: ${{ inputs.working-directory }}
          push: false
          tags: ticketpulse/${{ inputs.service-name }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

That is 90 lines, defined once. Now look at how each service calls it:

```yaml
# .github/workflows/ci-event-service.yml
name: CI - Event Service

on:
  push:
    branches: [main]
    paths: ['services/event-service/**']
  pull_request:
    paths: ['services/event-service/**']

jobs:
  ci:
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/event-service
      service-name: event-service
    secrets: inherit
```

```yaml
# .github/workflows/ci-payment-service.yml
name: CI - Payment Service

on:
  push:
    branches: [main]
    paths: ['services/payment-service/**']
  pull_request:
    paths: ['services/payment-service/**']

jobs:
  ci:
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/payment-service
      service-name: payment-service
    secrets: inherit
```

```yaml
# .github/workflows/ci-user-service.yml
name: CI - User Service

on:
  push:
    branches: [main]
    paths: ['services/user-service/**']
  pull_request:
    paths: ['services/user-service/**']

jobs:
  ci:
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/user-service
      service-name: user-service
      run-e2e: true
    secrets: inherit
```

Each caller is 15 lines. The template is 90 lines. Without reusable workflows, you would have 270 lines of duplicated YAML (3 x 90). With them, you have 90 + 45 = 135 lines total, and more importantly, exactly one place to update when your CI process changes.

### Key Rules for Reusable Workflows

1. The called workflow must be in `.github/workflows/` -- it cannot be in a subdirectory.
2. A reusable workflow can call another reusable workflow, but only one level deep (no chaining A -> B -> C).
3. `secrets: inherit` passes all the caller's secrets to the called workflow. You can also pass specific secrets if you want to be explicit.
4. The called workflow runs in the context of the caller -- it has access to the caller's repository, branch, and `GITHUB_TOKEN`.

---

## Part 2: Matrix Strategies for Multi-Service Testing

### Basic Matrix: Node and Postgres Versions

TicketPulse needs to work on both Node 20 (current LTS) and Node 22 (next LTS), and against Postgres 15 and 16 (your production upgrade is coming). A matrix strategy runs every combination:

```yaml
# .github/workflows/ci-template.yml (updated test job)
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node-version: ['20', '22']
        postgres-version: ['15', '16']
    defaults:
      run:
        working-directory: ${{ inputs.working-directory }}
    services:
      postgres:
        image: postgres:${{ matrix.postgres-version }}
        env:
          POSTGRES_USER: ticketpulse
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: ticketpulse_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd="pg_isready -U ticketpulse"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'pnpm'
          cache-dependency-path: ${{ inputs.working-directory }}/pnpm-lock.yaml

      - run: pnpm install --frozen-lockfile

      - run: pnpm run test
        env:
          DATABASE_URL: postgresql://ticketpulse:testpassword@localhost:5432/ticketpulse_test
```

This creates 4 jobs: Node 20 + PG 15, Node 20 + PG 16, Node 22 + PG 15, Node 22 + PG 16. They all run in parallel.

**Why `fail-fast: false`?** The default is `fail-fast: true`, which cancels all remaining matrix jobs as soon as one fails. That sounds efficient, but it hides information. If Node 22 + PG 16 fails, you want to know whether Node 22 + PG 15 also fails (it is a Node 22 issue) or only PG 16 combinations fail (it is a Postgres issue). Set `fail-fast: false` to see all failures.

### Dynamic Matrix: Detect Changed Services

In a monorepo, running the full matrix for all three services on every push wastes CI minutes. You can dynamically generate the matrix based on which services changed:

```yaml
# .github/workflows/ci-all.yml
name: CI - All Services

on:
  push:
    branches: [main]
  pull_request:

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      services: ${{ steps.changes.outputs.services }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          fetch-depth: 0

      - id: changes
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            BASE=${{ github.event.pull_request.base.sha }}
          else
            BASE=${{ github.event.before }}
          fi

          CHANGED_SERVICES=$(git diff --name-only $BASE ${{ github.sha }} \
            | grep '^services/' \
            | cut -d'/' -f2 \
            | sort -u \
            | jq -R -s -c 'split("\n") | map(select(length > 0))')

          echo "services=$CHANGED_SERVICES" >> "$GITHUB_OUTPUT"
          echo "Changed services: $CHANGED_SERVICES"

  ci:
    needs: detect-changes
    if: needs.detect-changes.outputs.services != '[]'
    strategy:
      fail-fast: false
      matrix:
        service: ${{ fromJson(needs.detect-changes.outputs.services) }}
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/${{ matrix.service }}
      service-name: ${{ matrix.service }}
    secrets: inherit
```

Push a change to `services/payment-service/src/handler.ts`. Only payment-service CI runs. Push a change to `services/event-service/` and `services/user-service/`. Both run in parallel, but payment-service is skipped.

### Test Sharding

TicketPulse's payment-service has 800 tests. Running them all sequentially takes 12 minutes. You can shard them across parallel runners:

```yaml
  test-sharded:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
        total-shards: [4]
    defaults:
      run:
        working-directory: ${{ inputs.working-directory }}
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: ticketpulse
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: ticketpulse_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd="pg_isready -U ticketpulse"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: '22'
          cache: 'pnpm'
          cache-dependency-path: ${{ inputs.working-directory }}/pnpm-lock.yaml

      - run: pnpm install --frozen-lockfile

      - run: pnpm run test --shard=${{ matrix.shard }}/${{ matrix.total-shards }}
        env:
          DATABASE_URL: postgresql://ticketpulse:testpassword@localhost:5432/ticketpulse_test
```

Vitest and Jest both support `--shard=X/Y` natively. 800 tests across 4 shards = ~200 tests per runner = ~3 minutes instead of 12. The wall-clock time drops by 75%.

---

## Part 3: OIDC Federation (No More AWS Secrets)

### The Problem with Long-Lived Credentials

In L1-M15, you probably stored AWS credentials like this:

```
Repository Settings -> Secrets -> AWS_ACCESS_KEY_ID = AKIA...
Repository Settings -> Secrets -> AWS_SECRET_ACCESS_KEY = wJalr...
```

These credentials have several problems:

1. **They never expire.** If they leak, the attacker has access until you manually rotate them.
2. **They are broadly scoped.** The IAM user often has more permissions than needed because "it works."
3. **They are shared.** The same credentials might be used across multiple repositories.
4. **Rotation is manual.** Someone has to remember to rotate them periodically, and they never do.

### The Solution: OIDC Federation

With OIDC (OpenID Connect), GitHub Actions proves its identity to AWS using a signed JWT token. AWS verifies the token and issues temporary credentials that expire in minutes. No secrets stored in GitHub at all.

**Step 1: Create an IAM OIDC Identity Provider in AWS**

```bash
# One-time setup per AWS account
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
```

**Step 2: Create an IAM Role with a Trust Policy**

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
          "token.actions.githubusercontent.com:sub": "repo:your-org/ticketpulse:*"
        }
      }
    }
  ]
}
```

The `Condition` block is critical. It restricts which repositories and branches can assume this role. You can be more specific:

- `repo:your-org/ticketpulse:ref:refs/heads/main` -- only the main branch
- `repo:your-org/ticketpulse:environment:production` -- only the production environment
- `repo:your-org/ticketpulse:pull_request` -- only pull requests

**Step 3: Create the role with ECR push permissions**

```bash
# Create the role
aws iam create-role \
  --role-name ticketpulse-github-actions \
  --assume-role-policy-document file://trust-policy.json

# Attach a policy that allows ECR push
aws iam put-role-policy \
  --role-name ticketpulse-github-actions \
  --policy-name ecr-push \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ],
        "Resource": "arn:aws:ecr:us-east-1:ACCOUNT_ID:repository/ticketpulse/*"
      },
      {
        "Effect": "Allow",
        "Action": "ecr:GetAuthorizationToken",
        "Resource": "*"
      }
    ]
  }'
```

**Step 4: Update the GitHub Actions Workflow**

```yaml
# .github/workflows/deploy.yml
name: Deploy to ECR

on:
  push:
    branches: [main]

permissions:
  id-token: write   # Required for OIDC
  contents: read     # Required for checkout

jobs:
  deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [event-service, payment-service, user-service]
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: aws-actions/configure-aws-credentials@ececac1a45f3b08a01d2dd070d28d111c5fe6722 # v4.1.0
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/ticketpulse-github-actions
          aws-region: us-east-1

      - uses: aws-actions/amazon-ecr-login@062b18b96a7aff071d4dc91bc00c4c1a7945b076 # v2.0.1
        id: ecr-login

      - uses: docker/build-push-action@263435318d21b8e681c14492fe198e19c816612b # v6.18.0
        with:
          context: services/${{ matrix.service }}
          push: true
          tags: |
            ${{ steps.ecr-login.outputs.registry }}/ticketpulse/${{ matrix.service }}:${{ github.sha }}
            ${{ steps.ecr-login.outputs.registry }}/ticketpulse/${{ matrix.service }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Notice what is missing: no `AWS_ACCESS_KEY_ID`, no `AWS_SECRET_ACCESS_KEY`. The `configure-aws-credentials` action handles the entire OIDC token exchange. The credentials it receives expire after the job finishes.

### Why This Is More Secure

| Aspect | Long-Lived Keys | OIDC Federation |
|--------|----------------|-----------------|
| Credential lifetime | Infinite (until manually rotated) | Minutes (automatic) |
| Stored in GitHub | Yes (as repository secrets) | No |
| Scope | Whatever the IAM user has | Whatever the IAM role allows |
| Rotation | Manual | Automatic (every run) |
| Blast radius if leaked | Full access until revoked | Token already expired |
| Audit trail | "IAM user X did Y" | "GitHub repo X, branch Y, workflow Z did W" |

---

## Part 4: Monorepo CI with Path Filtering

### The Problem

Without path filtering, every push to `ticketpulse` triggers CI for all three services. Edit a README? All three CI pipelines run. Fix a typo in event-service? Payment-service and user-service both run their full test suites. This wastes CI minutes and slows down feedback.

### Path Filtering with `dorny/paths-filter`

The `on.push.paths` trigger (shown in Part 1) works for simple cases. But it has a limitation: you cannot use it to conditionally run jobs within a single workflow. The `dorny/paths-filter` action gives you more control:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      event-service: ${{ steps.filter.outputs.event-service }}
      payment-service: ${{ steps.filter.outputs.payment-service }}
      user-service: ${{ steps.filter.outputs.user-service }}
      shared: ${{ steps.filter.outputs.shared }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: dorny/paths-filter@de90cc6fb38fc0963ad72b210f1f284cd68cea36 # v3.0.2
        id: filter
        with:
          filters: |
            event-service:
              - 'services/event-service/**'
              - 'packages/shared/**'
            payment-service:
              - 'services/payment-service/**'
              - 'packages/shared/**'
            user-service:
              - 'services/user-service/**'
              - 'packages/shared/**'
            shared:
              - 'packages/shared/**'

  ci-event-service:
    needs: changes
    if: needs.changes.outputs.event-service == 'true'
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/event-service
      service-name: event-service
    secrets: inherit

  ci-payment-service:
    needs: changes
    if: needs.changes.outputs.payment-service == 'true'
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/payment-service
      service-name: payment-service
    secrets: inherit

  ci-user-service:
    needs: changes
    if: needs.changes.outputs.user-service == 'true'
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/user-service
      service-name: user-service
    secrets: inherit
```

Key detail: each service filter includes `packages/shared/**`. If you change a shared library, all services that depend on it get tested. This prevents the silent breakage that happens when shared code changes but dependent services are not retested.

### What Happens on Each Push

| Changed files | Jobs that run |
|---------------|---------------|
| `services/payment-service/src/charge.ts` | `changes` + `ci-payment-service` |
| `services/event-service/src/handler.ts` + `services/user-service/src/auth.ts` | `changes` + `ci-event-service` + `ci-user-service` |
| `packages/shared/src/types.ts` | `changes` + all three service CIs |
| `README.md` | `changes` only (no service CIs triggered) |

---

## Part 5: Security Hardening

### Pin Actions by SHA, Not Tag

Most workflows use tags:

```yaml
# Dangerous: the tag can be moved to point at different code
- uses: actions/checkout@v4
```

Tags are mutable. A compromised action maintainer (or an attacker who gains access) can move the `v4` tag to point at malicious code. Every workflow using `@v4` would then run the attacker's code.

Pin by the full commit SHA:

```yaml
# Safe: this SHA is immutable
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

The comment at the end is for human readability. GitHub Actions ignores it. The SHA is what matters, and it is immutable -- no one can change what that SHA points to.

To find the SHA for a release:

```bash
# Look up the commit SHA for a given tag
gh api repos/actions/checkout/git/ref/tags/v4.2.2 --jq '.object.sha'
```

### Set Minimal `GITHUB_TOKEN` Permissions

By default, `GITHUB_TOKEN` has broad permissions. Restrict it at the workflow level:

```yaml
# At the top of every workflow
permissions:
  contents: read
  # Add only what you need:
  # pull-requests: write    # If you post PR comments
  # packages: write         # If you push to GHCR
  # id-token: write         # If you use OIDC
```

You can also set the default to restrictive at the repository or organization level:

```
Repository Settings -> Actions -> General -> Workflow permissions
-> "Read repository contents and packages permissions"
```

Then every workflow must explicitly request the permissions it needs. If a compromised action tries to push code or create a release, it will fail because the token does not have those permissions.

### Dependabot for Action Updates

Actions are dependencies, just like npm packages. Dependabot can automatically open PRs when new versions are available:

```yaml
# .github/dependabot.yml
version: 2
updates:
  # Keep actions up to date
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "ci"
    labels:
      - "dependencies"
      - "ci"
    reviewers:
      - "your-org/platform-team"

  # Also keep npm dependencies up to date (per service)
  - package-ecosystem: "npm"
    directory: "/services/event-service"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "deps(event-service)"

  - package-ecosystem: "npm"
    directory: "/services/payment-service"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "deps(payment-service)"

  - package-ecosystem: "npm"
    directory: "/services/user-service"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "deps(user-service)"
```

Dependabot will open a PR like: "ci: bump actions/checkout from v4.2.1 to v4.2.2" with the updated SHA. Review it, merge it, done.

### CODEOWNERS for `.github/`

Your CI configuration is infrastructure. Not everyone should be able to modify it. Use CODEOWNERS to require review from the platform team:

```
# .github/CODEOWNERS
# CI/CD configuration requires platform team review
.github/ @your-org/platform-team

# Dependabot config
.github/dependabot.yml @your-org/platform-team @your-org/security-team

# Service owners can modify their own service directories
services/event-service/ @your-org/events-team
services/payment-service/ @your-org/payments-team
services/user-service/ @your-org/identity-team
```

Any PR that modifies `.github/workflows/` will require approval from `@your-org/platform-team` before it can be merged. This prevents a well-meaning developer from accidentally weakening your CI security posture.

### Security Checklist Summary

| Practice | Why | How |
|----------|-----|-----|
| Pin by SHA | Prevents tag-swapping attacks | `actions/checkout@<sha> # v4.2.2` |
| Minimal permissions | Limits blast radius of compromised actions | `permissions:` block at workflow level |
| Dependabot for actions | Keeps actions up to date with security fixes | `.github/dependabot.yml` |
| CODEOWNERS | Prevents unauthorized CI changes | `.github/CODEOWNERS` |
| `secrets: inherit` (not hardcoded) | Centralizes secret management | In reusable workflow callers |
| OIDC over static keys | Eliminates long-lived credentials | See Part 3 |

---

## Try It

### 🛠️ Build Exercise 1: Refactor to Reusable Workflows

Take your L1-M15 `ci.yml` and split it into a reusable template plus per-service callers.

<details>
<summary>💡 Hint 1</summary>
Create `ci-template.yml` with `on: workflow_call:` and define inputs for `working-directory` (required, string), `service-name` (required, string), and `node-version` (optional, string, default '22'). Use `secrets: inherit` in the callers to pass all repository secrets without listing them individually.
</details>

<details>
<summary>💡 Hint 2</summary>
Each per-service caller is ~15 lines: trigger on `push/pull_request` with `paths: ['services/<name>/**']`, then a single job that calls `uses: ./.github/workflows/ci-template.yml` with the appropriate `working-directory` and `service-name`. Use `matrix` in the template's test job to run against Node 20 and 22 simultaneously.
</details>

<details>
<summary>💡 Hint 3</summary>
Validate your YAML before pushing: `python3 -c "import sys, yaml; yaml.safe_load(sys.stdin)" < .github/workflows/ci-template.yml`. After pushing, verify with `gh run list --limit 5` that only the expected workflows triggered. If a reusable workflow call fails with "not found," check that the template file is in `.github/workflows/` (not a subdirectory) and is on the same branch.
</details>

```bash
cd ticketpulse

# Create the template
mkdir -p .github/workflows
# Create ci-template.yml with the content from Part 1

# Create the per-service callers
# Create ci-event-service.yml, ci-payment-service.yml, ci-user-service.yml

# Verify YAML syntax before pushing
cat .github/workflows/ci-template.yml | python3 -c "import sys, yaml; yaml.safe_load(sys.stdin); print('Valid YAML')"

# Push and watch the workflows
git add .github/workflows/
git commit -m "refactor: extract reusable CI template"
git push

# Watch the workflow runs
gh run list --limit 5
gh run watch
```

### 🐛 Debug Exercise 2: Test Path Filtering

<details>
<summary>💡 Hint 1</summary>
When using `on.push.paths` with reusable workflows, the path filter applies to the caller workflow, not the template. If you change `packages/shared/src/types.ts`, only callers whose `paths` array includes `packages/shared/**` will trigger. Add `'packages/shared/**'` to every service caller's path filter.
</details>

<details>
<summary>💡 Hint 2</summary>
If all three CIs trigger when you only changed payment-service, check whether `dorny/paths-filter` is configured in a top-level workflow that conditionally calls per-service jobs. The `if: needs.changes.outputs.payment-service == 'true'` guard must match the exact output name from the filter step.
</details>

<details>
<summary>💡 Hint 3</summary>
To debug which paths were detected as changed, add a logging step in the `detect-changes` job: `echo "Changed files:" && git diff --name-only $BASE ${{ github.sha }}`. Compare this against your path filters. On PRs, `github.event.pull_request.base.sha` is the merge base; on pushes, `github.event.before` is the previous commit.
</details>

```bash
# Make a change to only payment-service
echo "// trigger CI" >> services/payment-service/src/index.ts
git add services/payment-service/src/index.ts
git commit -m "test: verify path filtering triggers only payment CI"
git push

# Check which workflows were triggered
gh run list --limit 5
# You should see only the payment-service CI running

# Now make a change to shared code
echo "// trigger all CIs" >> packages/shared/src/types.ts
git add packages/shared/src/types.ts
git commit -m "test: verify shared change triggers all service CIs"
git push

# All three service CIs should run
gh run list --limit 10
```

### 📐 Design Exercise 3: Set Up OIDC (or Understand It)

If you have an AWS account:

```bash
# Create the OIDC provider
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "1c58a3a8518e8759bf075b76b750d4f2df264fcd"

# Create the trust policy
cat > trust-policy.json << 'EOF'
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
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/ticketpulse:*"
        }
      }
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name ticketpulse-github-actions \
  --assume-role-policy-document file://trust-policy.json

# Verify: remove your AWS_ACCESS_KEY_ID secret from GitHub
gh secret delete AWS_ACCESS_KEY_ID
gh secret delete AWS_SECRET_ACCESS_KEY

# Push and verify the deploy workflow still works with OIDC
git push
gh run watch
```

If you do not have an AWS account, trace through the Part 3 YAML and answer: what would happen if you forgot `permissions: id-token: write`? (Answer: the `configure-aws-credentials` action would fail with "Error: Could not get ID token" because the GITHUB_TOKEN would not have permission to request an OIDC token from GitHub.)

---

## Debug

### Debug 1: Broken Reusable Workflow Input

Your colleague added a new input to the reusable workflow but used the wrong type. The workflow fails immediately.

Here is the broken caller:

```yaml
# .github/workflows/ci-event-service.yml
jobs:
  ci:
    uses: ./.github/workflows/ci-template.yml
    with:
      working-directory: services/event-service
      service-name: event-service
      node-version: 22  # <-- Bug: this is a number, but the input expects a string
    secrets: inherit
```

The error message will say something like:

```
Error: Invalid value for input 'node-version'. Expected type: string, actual type: number.
```

**The fix:** Quote the value. `node-version: '22'` instead of `node-version: 22`. YAML treats unquoted `22` as an integer. The reusable workflow declared `type: string`, so GitHub Actions enforces the type match.

**Lesson:** Always quote version numbers in GitHub Actions. `node-version: 22`, `postgres-version: 16`, and `python-version: 3.12` are all integers or floats in YAML. Quote them.

### Debug 2: Matrix Fail-Fast Behavior

Run a matrix build with `fail-fast: true` (the default):

```yaml
strategy:
  matrix:
    node-version: ['20', '22']
    postgres-version: ['15', '16']
```

Introduce a test that fails only on Postgres 16 (use a PG 16-specific syntax difference). Observe:

1. The PG 16 jobs fail.
2. The PG 15 jobs get cancelled -- even though they were passing.
3. You see 2 failures and 2 cancellations. You do NOT know whether the PG 15 jobs would have passed.

Now change to `fail-fast: false` and push again:

1. The PG 16 jobs fail.
2. The PG 15 jobs complete successfully.
3. You see 2 failures and 2 successes. You now know the issue is specific to PG 16.

**Lesson:** `fail-fast: false` costs more CI minutes but gives you more diagnostic information. Use it for compatibility matrices where you need to know exactly which combinations fail.

---

## Reflect

1. **Reusable workflows vs. composite actions.** Both reduce duplication. When should you use each? Consider: a reusable workflow replaces an entire workflow file. A composite action replaces a sequence of steps within a job. If you need different `runs-on`, different `services`, or different `permissions` per use case, you need a reusable workflow. If you just need to bundle a few steps (like "set up Node + install + cache"), a composite action is simpler.

2. **Cross-repository workflows.** TicketPulse is one monorepo. But what if you had 20 separate repositories, each needing the same CI template? You could publish the reusable workflow in a central `.github` repository and call it with `uses: your-org/.github/.github/workflows/ci-template.yml@main`. How would you handle versioning? How would you test changes to the template without breaking all 20 repos? Consider: use a release branch or tag, and have repos pin to `@v1` while you develop `@v2`.

3. **OIDC trust boundaries.** Your trust policy uses `repo:your-org/ticketpulse:*`, which allows any branch, any workflow, any environment. In a real production setup, what would you restrict the `sub` claim to? Why does it matter if someone can push a branch with a modified workflow?

---

> **What did you notice?** GitHub Actions workflows can model complex deployment pipelines with matrix builds and environment approvals. How does this compare to the CI/CD you set up in Loop 1? What new capabilities did you gain?

## Checkpoint

Before moving on, verify:

- [ ] Reusable CI workflow (`ci-template.yml`) created and called by at least 2 service workflows
- [ ] Matrix strategy configured to test across Node 20/22 and Postgres 15/16
- [ ] `fail-fast: false` set on the matrix so all failures are visible
- [ ] OIDC federation set up (or you can explain the setup) for AWS -- no long-lived credentials
- [ ] Path filtering ensures only changed services get CI runs (shared code triggers all)
- [ ] All actions pinned by full commit SHA with human-readable version comment
- [ ] `permissions` block set at workflow level with minimal required permissions
- [ ] `.github/dependabot.yml` configured for action version updates
- [ ] CODEOWNERS file protects `.github/` directory

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Reusable workflow** | A workflow triggered by `workflow_call` that other workflows can invoke like a function, accepting inputs and secrets |
| **`workflow_call`** | The event trigger that makes a workflow reusable -- it defines the inputs and secrets the workflow accepts |
| **Matrix strategy** | A GitHub Actions feature that runs a job multiple times with different variable combinations (e.g., Node versions, OS, services) |
| **`fail-fast`** | Matrix option that, when true (default), cancels remaining jobs when one fails; set to false to see all failures |
| **OIDC federation** | Authentication method where GitHub Actions proves its identity to a cloud provider using a signed JWT, receiving short-lived credentials in return |
| **Path filtering** | Triggering CI jobs only when specific file paths change, avoiding unnecessary builds in monorepos |
| **SHA pinning** | Referencing GitHub Actions by their immutable commit SHA instead of a mutable tag, preventing supply-chain attacks |
| **Composite action** | A reusable action defined in `action.yml` that bundles multiple steps; lighter-weight than a reusable workflow |
| **Test sharding** | Splitting a test suite across multiple parallel runners to reduce wall-clock execution time |
| **CODEOWNERS** | A GitHub file that defines which teams must review changes to specific directories or files |

---

---

## What's Next

In **Advanced Authentication** (L2-M56), you'll add OAuth 2.0, RBAC, and multi-factor authentication to TicketPulse's security model.

---

## Further Reading

- [GitHub Docs: Reusing Workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows) -- official reference for `workflow_call` syntax and limitations
- [GitHub Docs: Using a Matrix Strategy](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-a-matrix-for-your-jobs) -- matrix configuration and dynamic matrices
- [GitHub Docs: Configuring OIDC in AWS](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) -- step-by-step OIDC setup
- [GitHub Docs: Security Hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect) -- comprehensive security best practices
- [dorny/paths-filter](https://github.com/dorny/paths-filter) -- the path filtering action used in Part 4
- [GitHub Blog: GitHub Actions - Reducing duplication with reusable workflows](https://github.blog/changelog/2021-10-05-github-actions-dry-your-github-actions-configuration-by-reusing-workflows/) -- original announcement and motivation
- [StepSecurity: Secure GitHub Actions](https://app.stepsecurity.io/) -- automated tool to pin actions by SHA and set minimal permissions

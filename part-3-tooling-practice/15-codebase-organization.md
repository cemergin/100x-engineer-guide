<!--
  CHAPTER: 15
  TITLE: Codebase Organization & Engineering Standards at Scale
  PART: III — Tooling & Practice
  PREREQS: None
  KEY_TOPICS: ESLint, Prettier, Ruff, CI/CD pipelines, team organization (1 to 100+ people), monorepo patterns, Turborepo, Nx, architecture fitness functions, ADRs, dependency management
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 15: Codebase Organization & Engineering Standards at Scale

> **Part III — Tooling & Practice** | Prerequisites: None | Difficulty: Beginner to Advanced

Keeping code organized as teams grow — from linting setup for solo developers to monorepo governance for 100+ person organizations, with CI/CD pipelines that enforce standards automatically.

### In This Chapter
- Linting & Formatting (The Foundation)
- CI/CD Pipeline Architecture
- Solo Developer Organization (1 Person)
- Small Team Organization (2-10 People)
- Large Team Organization (10-100+ People)
- Repository Structure Patterns
- Keeping Things Organized Over Time
- Key Takeaways

### Related Chapters
- Chapter 12 — Git/tooling skills
- Chapter 7 — CI/CD concepts
- Chapter 9 — engineering leadership/ADRs
- Chapter 20 — dependency management

---

## 1. LINTING & FORMATTING (The Foundation)

### 1.1 Why This Matters

Automated formatting eliminates entire categories of code review friction. When formatting is enforced by tooling, you never see review comments like "add a space here" or "use single quotes." This frees human reviewers to focus on logic, architecture, and correctness.

**The rule:** No human should ever manually format code. Configure the tools once, enforce them in CI, and never think about it again.

### 1.2 JavaScript / TypeScript: ESLint + Prettier

**Install:**

```bash
# Core tools
npm install -D eslint prettier eslint-config-prettier

# TypeScript support
npm install -D @typescript-eslint/parser @typescript-eslint/eslint-plugin

# Framework-specific (pick what applies)
npm install -D eslint-plugin-react eslint-plugin-react-hooks  # React
npm install -D eslint-plugin-next @next/eslint-plugin-next     # Next.js
```

**ESLint configuration (`eslint.config.mjs` -- flat config, ESLint v9+):**

```javascript
import eslint from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";
import prettier from "eslint-config-prettier";

export default [
  eslint.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        project: "./tsconfig.json",
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      // Catch real bugs, not style
      "@typescript-eslint/no-floating-promises": "error",    // forgotten awaits
      "@typescript-eslint/no-misused-promises": "error",     // promises in wrong context
      "@typescript-eslint/strict-boolean-expressions": "warn",// if (undefined) traps
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
      }],
      "prefer-const": "error",
      "no-var": "error",
    },
  },
  prettier, // Must be last -- disables formatting rules that conflict with Prettier
];
```

**Prettier configuration (`.prettierrc`):**

```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

**Key insight:** ESLint catches bugs and enforces code quality rules. Prettier handles formatting. Do not use ESLint for formatting -- that is Prettier's job. `eslint-config-prettier` disables all ESLint rules that conflict with Prettier.

### 1.3 Python: Ruff + mypy

Ruff replaces flake8, black, isort, pyflakes, pycodestyle, and more. It is written in Rust and is 10-100x faster than the tools it replaces.

**Install:**

```bash
pip install ruff mypy
```

**Configuration (`pyproject.toml`):**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort (import sorting)
    "N",    # pep8-naming
    "UP",   # pyupgrade (modernize syntax)
    "B",    # flake8-bugbear (common bugs)
    "S",    # flake8-bandit (security)
    "A",    # flake8-builtins (shadowing built-ins)
    "C4",   # flake8-comprehensions
    "RUF",  # ruff-specific rules
]
ignore = [
    "E501",  # line length (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["myapp"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Usage:**

```bash
ruff check .              # Lint
ruff check --fix .        # Lint with auto-fix
ruff format .             # Format (replaces black)
mypy .                    # Type check
```

### 1.4 Go: gofmt + golangci-lint

Go has the strongest formatting culture: `gofmt` is the standard, and there is no debate about style.

```bash
# Format (built-in, no config needed)
gofmt -w .
goimports -w .   # gofmt + import organization

# Comprehensive linting
# Install: https://golangci-lint.run/welcome/install/
golangci-lint run
```

**Configuration (`.golangci.yml`):**

```yaml
linters:
  enable:
    - errcheck      # unchecked errors
    - gosimple      # simplification suggestions
    - govet         # suspicious constructs
    - ineffassign   # useless assignments
    - staticcheck   # advanced static analysis
    - unused        # unused code
    - gocritic      # opinionated checks
    - gosec         # security issues
    - prealloc      # suggest preallocating slices
    - misspell      # typos in comments/strings

linters-settings:
  errcheck:
    check-type-assertions: true
    check-blank: true

run:
  timeout: 5m
```

### 1.5 Rust: rustfmt + clippy

```bash
# Format
rustfmt --edition 2021 src/**/*.rs
# Or via cargo:
cargo fmt

# Lint (clippy is Rust's comprehensive linter)
cargo clippy -- -W clippy::all -W clippy::pedantic
```

**Configuration (`rustfmt.toml`):**

```toml
edition = "2021"
max_width = 100
tab_spaces = 4
use_field_init_shorthand = true
```

### 1.6 Java / Kotlin

```bash
# Kotlin: ktlint
ktlint --format "src/**/*.kt"

# Java: spotless (Gradle plugin)
# build.gradle.kts:
```

```kotlin
plugins {
    id("com.diffplug.spotless") version "6.25.0"
}

spotless {
    java {
        googleJavaFormat("1.19.2")
        removeUnusedImports()
    }
    kotlin {
        ktlint("1.1.1")
    }
}
```

```bash
./gradlew spotlessApply   # Format
./gradlew spotlessCheck   # Check (CI)
```

### 1.7 EditorConfig for Cross-Editor Consistency

Every project should have an `.editorconfig` file at the root. This ensures that regardless of whether developers use VS Code, IntelliJ, Vim, or Emacs, basic settings are consistent.

```ini
# .editorconfig
root = true

[*]
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

[*.{js,ts,tsx,jsx,json,yaml,yml,css,scss,html}]
indent_style = space
indent_size = 2

[*.{go,rs}]
indent_style = tab

[*.py]
indent_style = space
indent_size = 4

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

### 1.8 Pre-Commit Hooks: lint-staged + husky

Only lint files that are being committed. Linting the entire codebase on every commit is slow and discouraging.

**Setup:**

```bash
npm install -D husky lint-staged
npx husky init
```

**Configure husky (`.husky/pre-commit`):**

```bash
npx lint-staged
```

**Configure lint-staged (`package.json`):**

```json
{
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix --max-warnings=0",
      "prettier --write"
    ],
    "*.{json,md,yaml,yml}": [
      "prettier --write"
    ],
    "*.py": [
      "ruff check --fix",
      "ruff format"
    ]
  }
}
```

**The "format on save" rule:** Every developer on the team must configure their editor to format on save. This is non-negotiable. It means code is always formatted before it even reaches the pre-commit hook.

**VS Code settings (`.vscode/settings.json` -- commit this to the repo):**

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit",
    "source.organizeImports": "explicit"
  }
}
```

---

## 2. CI/CD PIPELINE ARCHITECTURE

> For advanced GitHub Actions patterns — reusable workflows, OIDC federation, matrix strategies, custom actions, monorepo CI, and security hardening — see **Chapter 33: GitHub Actions Mastery**.

### 2.1 Pipeline Stages (Optimal Order)

The principle: **fail fast, fail cheap.** Run the fastest and most likely-to-fail checks first.

```
lint (10s) → type-check (30s) → unit test (1-2m) → build (2-3m)
→ integration test (3-5m) → security scan (2m) → deploy
```

**Why this order:**

1. **Lint** catches syntax errors and formatting issues in seconds. If formatting is wrong, do not waste time running tests.
2. **Type-check** (`tsc --noEmit`) catches type errors in 30 seconds. Faster than running tests.
3. **Unit tests** run fast and catch logic errors. Run these before slow integration tests.
4. **Build** ensures the project actually compiles and bundles correctly.
5. **Integration tests** are slower and require services (DB, Redis). Run only if everything above passes.
6. **Security scan** runs in parallel with integration tests.
7. **Deploy** only if everything passes.

### 2.2 Example GitHub Actions Workflow (TypeScript Project)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancel stale runs on the same branch

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - name: Lint
        run: npx eslint . --max-warnings=0

      - name: Type Check
        run: npx tsc --noEmit

      - name: Format Check
        run: npx prettier --check .

  unit-test:
    runs-on: ubuntu-latest
    needs: lint-and-typecheck
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - name: Unit Tests
        run: npx vitest run --coverage --reporter=verbose

      - name: Upload Coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage/

  build:
    runs-on: ubuntu-latest
    needs: unit-test
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - name: Build
        run: npm run build

      - name: Upload Build Artifact
        uses: actions/upload-artifact@v4
        with:
          name: build
          path: .next/  # or dist/

  integration-test:
    runs-on: ubuntu-latest
    needs: build
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
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - name: Run Migrations
        run: npx prisma migrate deploy
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb

      - name: Integration Tests
        run: npx vitest run --config vitest.integration.config.ts
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379

  security-scan:
    runs-on: ubuntu-latest
    needs: lint-and-typecheck  # Can run in parallel with unit tests
    steps:
      - uses: actions/checkout@v4

      - name: Audit Dependencies
        run: npm audit --audit-level=high

      - name: CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          languages: javascript-typescript

  deploy:
    runs-on: ubuntu-latest
    needs: [integration-test, security-scan]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Vercel
        run: npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
```

### 2.3 Optimizing CI Speed

**Caching dependencies:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: "npm"  # Automatically caches ~/.npm
```

**Parallel test execution (Vitest):**

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    pool: "forks",         // Use forked processes for isolation
    poolOptions: {
      forks: {
        maxForks: 4,       // Parallel workers
      },
    },
  },
});
```

**Test sharding across CI runners:**

```yaml
# Run tests across 4 parallel runners
strategy:
  matrix:
    shard: [1/4, 2/4, 3/4, 4/4]

steps:
  - name: Run Tests
    run: npx vitest run --shard=${{ matrix.shard }}
```

**Only run affected tests (Turborepo):**

```bash
# Only test packages affected by changes since main
npx turbo run test --filter=...[main]
```

**Only run affected tests (Nx):**

```bash
npx nx affected --target=test --base=main
```

### 2.4 Branch Protection Rules

Configure in GitHub Settings > Branches > Branch protection rules:

```
Branch name pattern: main

[x] Require a pull request before merging
    [x] Require approvals: 1 (small team) or 2 (large team)
    [x] Dismiss stale pull request approvals when new commits are pushed
    [x] Require review from Code Owners

[x] Require status checks to pass before merging
    Required checks:
    - lint-and-typecheck
    - unit-test
    - integration-test
    - security-scan

[x] Require branches to be up to date before merging

[x] Require linear history (encourages rebase, prevents merge commits)

[ ] Do not allow bypassing the above settings (enforce for admins too)
```

### 2.5 Secrets Management in CI

**Hierarchy of secrets management (from simplest to most secure):**

1. **GitHub Encrypted Secrets** -- good enough for most teams. Set via Settings > Secrets.
2. **OIDC Tokens** -- for AWS/GCP/Azure, use OIDC instead of long-lived credentials:

```yaml
permissions:
  id-token: write  # Required for OIDC

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/github-actions
      aws-region: us-east-1
      # No secrets needed -- uses GitHub's OIDC token
```

3. **HashiCorp Vault / AWS Secrets Manager** -- for large organizations with rotation requirements.

**Rules:**
- Never echo secrets in CI logs
- Never commit `.env` files (add to `.gitignore`)
- Rotate secrets on a schedule
- Use environment-scoped secrets (prod secrets only available in prod deployment jobs)

### 2.6 Deployment Gates

```yaml
deploy-staging:
  needs: [integration-test]
  environment: staging  # Auto-deploy to staging

deploy-production:
  needs: [deploy-staging]
  environment:
    name: production
    url: https://app.example.com
  # Manual approval required (configure in GitHub Environment settings)
  steps:
    - name: Smoke Test Staging
      run: |
        curl -sf https://staging.example.com/api/health || exit 1

    - name: Deploy to Production
      run: npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }}

    - name: Post-Deploy Smoke Test
      run: |
        curl -sf https://app.example.com/api/health || exit 1
```

---

## 3. SOLO DEVELOPER ORGANIZATION (1 Person)

### 3.1 Minimal but Effective Setup

Even when you are the only developer, automated standards prevent "I'll clean it up later" technical debt from accumulating.

**Essential tools:**

```bash
# Initialize a project with standards from day one
npm init -y
npm install -D eslint prettier husky lint-staged @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-config-prettier

npx husky init
```

**Conventional Commits for meaningful git history:**

```
Format: <type>(<scope>): <description>

Types:
  feat:     New feature
  fix:      Bug fix
  refactor: Code change that neither fixes a bug nor adds a feature
  docs:     Documentation only
  test:     Adding missing tests
  chore:    Build process or tooling changes
  perf:     Performance improvement

Examples:
  feat(auth): add Google OAuth login
  fix(billing): handle Stripe webhook signature validation
  refactor(api): extract validation middleware from route handlers
  chore(deps): upgrade Next.js to 15.2
```

**Enforce with commitlint:**

```bash
npm install -D @commitlint/cli @commitlint/config-conventional
```

```javascript
// commitlint.config.js
export default { extends: ["@commitlint/config-conventional"] };
```

```bash
# .husky/commit-msg
npx --no -- commitlint --edit "$1"
```

### 3.2 Project Structure Conventions

Even for personal projects, consistent structure pays off when you return to the code after months.

```
my-project/
├── src/
│   ├── app/                  # Next.js app router pages
│   │   ├── (auth)/           # Route groups
│   │   ├── api/              # API routes
│   │   └── layout.tsx
│   ├── components/           # Shared UI components
│   │   ├── ui/               # Primitives (Button, Input)
│   │   └── features/         # Feature-specific components
│   ├── lib/                  # Shared utilities and helpers
│   │   ├── db.ts             # Database client
│   │   ├── auth.ts           # Auth helpers
│   │   └── utils.ts          # General utilities
│   ├── services/             # Business logic layer
│   │   ├── billing.ts
│   │   └── users.ts
│   └── types/                # Shared TypeScript types
├── tests/                    # Test files (or colocate with source)
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .husky/
├── .vscode/
│   └── settings.json
├── .editorconfig
├── .eslintrc.js
├── .prettierrc
├── .gitignore
├── .env.example              # Template for environment variables (committed)
├── .env.local                # Actual secrets (NOT committed)
├── package.json
├── tsconfig.json
└── README.md                 # Setup instructions, architecture notes
```

### 3.3 Self-Code-Review Habits

- **Diff before commit:** Always run `git diff --staged` and read every line before committing
- **Come back after a break:** If you wrote complex logic, review your own PR after stepping away for 30 minutes
- **Write the PR description as if someone else will read it** -- future you is that someone

### 3.4 Automate Anything You Do More Than Twice

```json
// package.json scripts
{
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "lint": "eslint . --max-warnings=0",
    "format": "prettier --write .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "db:migrate": "prisma migrate dev",
    "db:seed": "tsx prisma/seed.ts",
    "db:reset": "prisma migrate reset",
    "check": "npm run lint && npm run typecheck && npm run test"
  }
}
```

---

## 4. SMALL TEAM ORGANIZATION (2-10 People)

### 4.1 Shared Linting Configuration

Create a shared ESLint config package so all projects use the same rules.

```
packages/
  eslint-config/
    package.json
    index.mjs
```

```json
// packages/eslint-config/package.json
{
  "name": "@company/eslint-config",
  "version": "1.0.0",
  "type": "module",
  "main": "index.mjs",
  "peerDependencies": {
    "eslint": "^9.0.0"
  }
}
```

```javascript
// packages/eslint-config/index.mjs
import eslint from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import prettier from "eslint-config-prettier";

export default [
  eslint.configs.recommended,
  // ... your shared rules
  prettier,
];
```

**Consuming in projects:**

```javascript
// apps/web/eslint.config.mjs
import baseConfig from "@company/eslint-config";

export default [
  ...baseConfig,
  {
    // Project-specific overrides
    rules: {
      "no-console": "off", // Allow in this project
    },
  },
];
```

### 4.2 PR Template

Create `.github/pull_request_template.md`:

```markdown
## What does this PR do?
<!-- Brief description of the change -->

## Why?
<!-- Link to issue/ticket, explain the motivation -->

## How to test
<!-- Step-by-step instructions for reviewers -->

## Checklist
- [ ] Tests added/updated
- [ ] Types are correct (no `any` escape hatches)
- [ ] Error handling covers failure cases
- [ ] Database migrations are reversible
- [ ] No secrets or credentials in the diff
- [ ] Documentation updated (if user-facing change)

## Screenshots (if UI change)
<!-- Before/after screenshots -->
```

### 4.3 Branch Naming Conventions

```
feature/TICKET-123-add-billing-dashboard
fix/TICKET-456-webhook-timeout
chore/upgrade-nextjs-15
hotfix/fix-prod-crash-null-user
```

**Enforce with a Git hook (`.husky/pre-push` or CI check):**

```bash
#!/bin/sh
branch=$(git rev-parse --abbrev-ref HEAD)
pattern="^(feature|fix|chore|hotfix|refactor|test|docs)/"

if [[ ! "$branch" =~ $pattern ]] && [[ "$branch" != "main" ]] && [[ "$branch" != "develop" ]]; then
  echo "Branch name '$branch' does not match pattern: $pattern"
  echo "Examples: feature/add-billing, fix/null-pointer, chore/update-deps"
  exit 1
fi
```

### 4.4 Code Ownership (CODEOWNERS)

```
# .github/CODEOWNERS
# Default: require review from any team member
*                         @company/engineering

# Specific ownership
/apps/api/               @alice @bob
/apps/web/               @charlie @diana
/packages/shared/        @company/engineering    # Everyone reviews shared code
/prisma/                 @alice                   # Database changes need Alice
/.github/                @bob                     # CI changes need Bob
/terraform/              @bob
```

### 4.5 Monorepo vs. Polyrepo Decision

**At 2-10 people, monorepo is almost always better.** Here is why:

| Factor | Monorepo | Polyrepo |
|--------|----------|----------|
| **Code sharing** | Trivial -- import from `@company/shared` | Requires publishing packages, version management |
| **Atomic changes** | One PR changes API + frontend + shared types | Coordinated PRs across 3 repos |
| **CI complexity** | One pipeline, run affected tests | N pipelines, cross-repo trigger chains |
| **Onboarding** | Clone one repo, run one setup command | Clone N repos, configure each |
| **Dependency consistency** | One lockfile, one version of React | Version drift across repos |

**When polyrepo makes sense:** Genuinely independent services with different teams, different deploy cadences, and no shared code. At 2-10 people, this is rare.

### 4.6 Lightweight RFCs

For non-trivial changes (new service, database schema change, architecture shift), write a one-page RFC before coding.

```markdown
# RFC: Add Real-Time Notifications

## Status: Proposed
## Author: @alice
## Date: 2026-03-15

## Problem
Users have no way to know about task updates without refreshing the page.

## Proposed Solution
WebSocket connection via Socket.io, backed by Redis pub/sub.

## Alternatives Considered
1. **Polling (every 30s)** -- Simple but wasteful and not real-time
2. **Server-Sent Events** -- Simpler than WebSockets but unidirectional
3. **Third-party (Pusher/Ably)** -- Easy but adds vendor dependency and cost

## Decision Criteria
- Latency < 500ms for notifications
- Must work behind corporate proxies (rules out raw WebSockets without fallback)
- Budget: no additional vendor cost

## Plan
Phase 1: Socket.io server + Redis adapter (1 week)
Phase 2: Client integration + UI (1 week)
Phase 3: Load test and optimize (3 days)

## Open Questions
- Do we need message persistence (what if user is offline)?
- Rate limiting for high-activity orgs?
```

**The RFC is not bureaucracy.** It is a 30-minute investment that prevents a week of rework when someone says "wait, did we consider X?"

---

## 5. LARGE TEAM ORGANIZATION (10-100+ People)

### 5.1 Monorepo Tooling

At scale, you need build system intelligence. These tools understand the dependency graph and only rebuild/retest what changed.

**Turborepo (recommended for JavaScript/TypeScript):**

```json
// turbo.json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**"]
    },
    "test": {
      "dependsOn": ["^build"],
      "inputs": ["src/**", "tests/**"],
      "outputs": ["coverage/**"]
    },
    "lint": {
      "dependsOn": [],
      "outputs": []
    },
    "typecheck": {
      "dependsOn": ["^build"],
      "outputs": []
    }
  }
}
```

```bash
# Only run tests for packages affected by changes
npx turbo run test --filter=...[main]

# Run lint across all packages in parallel
npx turbo run lint

# Run the full pipeline for a specific app and its dependencies
npx turbo run build --filter=web...
```

**Nx (alternative, more features, steeper learning curve):**

```bash
npx nx affected --target=test --base=main
npx nx graph  # Visualize dependency graph
```

**Bazel (for very large, multi-language monorepos -- Google, Stripe scale):**

Bazel provides hermetic builds (every build is reproducible) and remote caching. It is significantly more complex to set up but scales to millions of lines of code.

### 5.2 Shared Packages

```
packages/
  @company/eslint-config/      # Shared lint rules
  @company/tsconfig/           # Shared TypeScript configs
  @company/ui/                 # Design system components
  @company/api-client/         # Generated API client from OpenAPI spec
  @company/auth/               # Shared auth utilities
  @company/testing/            # Shared test utilities, factories, mocks
  @company/logger/             # Structured logging wrapper
```

**Shared TypeScript config (`packages/tsconfig/base.json`):**

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "strict": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  }
}
```

**Consuming in apps:**

```json
// apps/web/tsconfig.json
{
  "extends": "@company/tsconfig/nextjs.json",
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "next-env.d.ts"],
  "exclude": ["node_modules"]
}
```

### 5.3 Architecture Fitness Functions

Fitness functions are automated checks that enforce architectural boundaries. They prevent the slow decay of architecture over time.

**dependency-cruiser (JavaScript/TypeScript):**

```bash
npm install -D dependency-cruiser
npx depcruise --init
```

```javascript
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      severity: "error",
      comment: "Circular dependencies cause bundling issues and indicate unclear boundaries",
      from: {},
      to: { circular: true },
    },
    {
      name: "no-ui-to-api",
      severity: "error",
      comment: "UI components must not import from API layer directly",
      from: { path: "^src/components/" },
      to: { path: "^src/app/api/" },
    },
    {
      name: "no-services-to-components",
      severity: "error",
      comment: "Business logic must not depend on UI components",
      from: { path: "^src/services/" },
      to: { path: "^src/components/" },
    },
    {
      name: "shared-packages-no-app-imports",
      severity: "error",
      comment: "Shared packages must not import from app-specific code",
      from: { path: "^packages/" },
      to: { path: "^apps/" },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
  },
};
```

```bash
# Add to CI
npx depcruise src --config .dependency-cruiser.cjs --output-type err
```

### 5.4 RFC Process for Cross-Team Changes

At 10+ people, RFCs become a critical coordination mechanism.

**RFC lifecycle:**

```
Draft → Proposed → In Review (1 week) → Accepted/Rejected → Implemented → Superseded
```

**RFC template (more structured than the small-team version):**

```markdown
# RFC-042: Migrate from REST to tRPC for Internal APIs

## Metadata
- **Status:** In Review
- **Author:** @alice
- **Reviewers:** @bob, @charlie, @platform-team
- **Created:** 2026-03-10
- **Decision deadline:** 2026-03-17

## Context
We have 47 REST endpoints across 3 services. Type safety between frontend
and backend is maintained manually, leading to ~2 type-related bugs per sprint.

## Proposal
Migrate internal APIs (not public-facing) to tRPC for end-to-end type safety.

## Impact Analysis
- **Teams affected:** Web, Mobile (API client), Platform
- **Migration effort:** ~3 sprints, can be done incrementally
- **Risk:** Learning curve for engineers unfamiliar with tRPC
- **Backward compatibility:** REST endpoints remain during migration

## Alternatives
[detailed comparison table]

## Decision Record
[filled in after review period]
```

**Store RFCs in the repo** (`docs/rfcs/`) so they are versioned, searchable, and linked to the code they describe.

### 5.5 Tech Radar

A tech radar categorizes technologies your organization uses into four rings:

- **Adopt:** Default choice for new projects. Well-understood, proven.
- **Trial:** Use in non-critical projects. Gathering experience.
- **Assess:** Worth exploring. Spike/prototype only.
- **Hold:** Do not start new projects with this. Migrate away over time.

**Example:**

| Technology | Ring | Notes |
|-----------|------|-------|
| Next.js 15 | Adopt | Default for all web frontends |
| tRPC | Trial | Using in billing service, evaluating |
| Bun | Assess | Promising but ecosystem gaps |
| Express.js | Hold | Migrate to Hono/Fastify for new services |
| Moment.js | Hold | Use date-fns or Temporal API |

**Update quarterly.** Make it a living document, not a one-time exercise.

### 5.6 Inner-Source Model

Allow teams to contribute to each other's services through a structured process:

1. **Service owners maintain a `CONTRIBUTING.md`** with setup instructions, architecture overview, and PR expectations
2. **External contributors** open an issue first describing the change
3. **Service owners** triage within 2 business days
4. **PRs from external contributors** require review from a service owner
5. **Shared packages** (`@company/*`) accept contributions from any team

### 5.7 API Contract Enforcement

For services communicating via HTTP, enforce contracts with OpenAPI specs:

```bash
# Generate types from OpenAPI spec
npx openapi-typescript api/openapi.yaml -o src/types/api.d.ts

# Validate API responses match the spec (in tests)
npm install -D openapi-response-validator
```

**Backward compatibility rule:** Never remove or rename a field in an API response. Add new fields, deprecate old ones, remove after all consumers have migrated.

### 5.8 Automated Dependency Updates

**Renovate (recommended over Dependabot for its flexibility):**

```json
// renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    ":automergeMinor",
    ":automergePatch",
    "group:allNonMajor"
  ],
  "packageRules": [
    {
      "matchPackagePatterns": ["eslint", "prettier", "@typescript-eslint"],
      "groupName": "linting tools",
      "automerge": true
    },
    {
      "matchPackagePatterns": ["vitest", "@testing-library"],
      "groupName": "testing tools",
      "automerge": true
    },
    {
      "matchUpdateTypes": ["major"],
      "automerge": false,
      "labels": ["dependency-major"]
    }
  ],
  "schedule": ["before 7am on Monday"]
}
```

**Key configuration choices:**
- Auto-merge minor/patch updates (if CI passes)
- Group related packages (all ESLint plugins update together)
- Major updates require manual review
- Run on a schedule (Monday mornings) to avoid constant PR noise

### 5.9 Platform Team and Golden Paths

A platform team provides "golden paths" -- opinionated, well-supported ways to build common things.

**What a golden path includes:**

- A project template (`create-company-app`) with all tooling pre-configured
- Shared CI pipeline templates
- Standard observability (logging, metrics, tracing) built into the template
- Database migration tooling
- Deployment workflow (push to main -> staging -> production with approvals)

```bash
# Create a new service using the company template
npx create-company-app my-new-service --template api

# What you get:
my-new-service/
├── src/
│   ├── index.ts           # Entry point with health check
│   ├── routes/            # API routes
│   └── middleware/         # Auth, logging, error handling
├── tests/
├── prisma/
├── Dockerfile             # Optimized multi-stage build
├── .github/
│   └── workflows/
│       └── ci.yml         # Pre-configured CI pipeline
├── turbo.json
├── package.json           # Pre-configured with company packages
└── README.md
```

### 5.10 Service Catalog (Backstage)

At 50+ services, you need a catalog. Backstage (by Spotify) or similar tools provide:

- **Service registry:** What services exist, who owns them, where they are deployed
- **API docs:** Auto-generated from OpenAPI specs
- **Dependency graph:** Which services call which
- **Runbooks:** Linked from the service entry
- **Scorecards:** Does this service have tests? Monitoring? Up-to-date dependencies?

```yaml
# catalog-info.yaml (in each service's repo root)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: billing-service
  description: Handles subscription billing and payment processing
  annotations:
    github.com/project-slug: company/billing-service
    backstage.io/techdocs-ref: dir:.
  tags:
    - typescript
    - grpc
spec:
  type: service
  lifecycle: production
  owner: team-billing
  dependsOn:
    - component:user-service
    - resource:billing-database
  providesApis:
    - billing-api
```

---

## 6. REPOSITORY STRUCTURE PATTERNS

### 6.1 Feature-Based vs. Layer-Based Organization

**Layer-based (organize by technical concern):**

```
src/
  controllers/
    userController.ts
    billingController.ts
    projectController.ts
  services/
    userService.ts
    billingService.ts
    projectService.ts
  repositories/
    userRepository.ts
    billingRepository.ts
    projectRepository.ts
  models/
    user.ts
    billing.ts
    project.ts
```

**Feature-based (organize by domain):**

```
src/
  features/
    users/
      userController.ts
      userService.ts
      userRepository.ts
      user.model.ts
      user.test.ts
    billing/
      billingController.ts
      billingService.ts
      billingRepository.ts
      billing.model.ts
      billing.test.ts
    projects/
      projectController.ts
      projectService.ts
      projectRepository.ts
      project.model.ts
      project.test.ts
  shared/
    middleware/
    utils/
    types/
```

**When to use each:**

- **Layer-based:** Small projects (< 10 files per layer), quick prototypes, when the domain model is simple
- **Feature-based:** Medium to large projects, when features have clear boundaries, when teams own features. This is almost always the better choice for production codebases because adding a new feature means adding a new folder, not modifying 5 existing folders.

### 6.2 Monorepo Layout

```
company-monorepo/
├── apps/
│   ├── web/                    # Next.js frontend
│   │   ├── src/
│   │   ├── public/
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── api/                    # Backend API service
│   │   ├── src/
│   │   ├── prisma/
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── mobile/                 # React Native app
│   │   ├── src/
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── admin/                  # Internal admin dashboard
│       ├── src/
│       ├── package.json
│       └── tsconfig.json
├── packages/
│   ├── ui/                     # Shared component library
│   │   ├── src/
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   └── index.ts        # Barrel export
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── shared/                 # Shared utilities, types, constants
│   │   ├── src/
│   │   │   ├── types.ts
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── config-eslint/          # Shared ESLint config
│   │   ├── index.mjs
│   │   └── package.json
│   ├── config-typescript/      # Shared TypeScript configs
│   │   ├── base.json
│   │   ├── nextjs.json
│   │   ├── react-library.json
│   │   └── package.json
│   └── api-client/             # Generated typed API client
│       ├── src/
│       ├── package.json
│       └── tsconfig.json
├── tools/                      # Build scripts, code generators
│   ├── generate-api-client.ts
│   └── seed-database.ts
├── docs/
│   ├── rfcs/
│   ├── adrs/
│   └── architecture.md
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── deploy.yml
│   ├── pull_request_template.md
│   └── CODEOWNERS
├── turbo.json
├── package.json                # Root workspace config
├── pnpm-workspace.yaml         # or npm workspaces in package.json
├── .editorconfig
├── .gitignore
└── README.md
```

**Workspace configuration (`pnpm-workspace.yaml`):**

```yaml
packages:
  - "apps/*"
  - "packages/*"
  - "tools/*"
```

### 6.3 Colocation Principle

**Tests next to source files:**

```
src/
  services/
    billing.ts
    billing.test.ts           # Unit test right next to the code
    billing.integration.test.ts
  components/
    InvoiceTable/
      InvoiceTable.tsx
      InvoiceTable.test.tsx
      InvoiceTable.stories.tsx  # Storybook story
      InvoiceTable.module.css   # Scoped styles
      index.ts                  # Re-export
```

**Why colocation is better than a separate `tests/` directory:**

- When you open a file, the test is right there -- you are more likely to update it
- When you delete a feature, the test goes with it -- no orphaned test files
- When you refactor, the test moves with the code
- File tree navigation is faster -- no jumping between `src/` and `tests/`

**Exception:** Integration tests and E2E tests that span multiple modules belong in a top-level `tests/` directory because they do not belong to any single module.

### 6.4 Barrel Files: When They Help vs. When They Hurt

**Barrel file (`index.ts`):**

```typescript
// packages/ui/src/index.ts
export { Button } from "./button";
export { Input } from "./input";
export { Modal } from "./modal";
export type { ButtonProps, InputProps, ModalProps } from "./types";
```

**When they help:**

- Package public API: clearly defines what consumers can import
- Simplifies imports: `import { Button, Input } from "@company/ui"` instead of `from "@company/ui/src/button"`

**When they hurt:**

- **Circular dependencies:** If `button.ts` imports from `utils.ts` which imports from `index.ts` which imports `button.ts`
- **Tree-shaking problems:** If you import one thing from a barrel, bundlers may pull in everything. Modern bundlers (webpack 5, Vite/Rollup) handle this better but it is not guaranteed.
- **IDE performance:** Large barrel files slow down TypeScript language server

**Best practice:** Use barrel files at package boundaries (the `index.ts` of `@company/ui`). Avoid barrel files within a package's internal directory structure.

---

## 7. KEEPING THINGS ORGANIZED OVER TIME

### 7.1 Technical Debt Tracking

Technical debt is inevitable. Untracked technical debt is dangerous.

**Debt register (simple approach):**

```markdown
<!-- docs/tech-debt.md -->
# Technical Debt Register

| ID | Description | Impact | Effort | Owner | Created | Target |
|----|-------------|--------|--------|-------|---------|--------|
| TD-001 | Billing service has no integration tests | High (breaks go undetected) | M (1 sprint) | @alice | 2026-01 | Q2 2026 |
| TD-002 | User model mixes auth and profile concerns | Medium (slows feature dev) | L (2 sprints) | @bob | 2026-02 | Q3 2026 |
| TD-003 | Legacy REST endpoints not migrated to tRPC | Low (working but inconsistent) | L | @charlie | 2026-03 | Q4 2026 |
```

**Automated tracking (SonarQube/SonarCloud):**

SonarQube provides "technical debt" estimates based on code smells, duplications, and complexity. Set quality gates:

```
Quality Gate: Sonar Way (customized)
- New code coverage > 80%
- No new bugs (severity: critical or higher)
- No new security vulnerabilities
- Technical debt ratio on new code < 5%
```

**The 20% rule:** Dedicate approximately 20% of each sprint to technical debt reduction. If you cannot justify 20%, negotiate 10% as a minimum. Zero percent leads to exponential decay.

### 7.2 Dependency Freshness

**Automated with Renovate (see Section 5.8) plus manual review cadence:**

```bash
# Check for outdated dependencies
npm outdated

# Check for known vulnerabilities
npm audit

# For a comprehensive view:
npx npm-check-updates
```

**Policy:**
- **Patch updates:** Auto-merge if CI passes
- **Minor updates:** Auto-merge for dev dependencies, review for production
- **Major updates:** Always review, test thoroughly, allocate sprint time

### 7.3 Dead Code Elimination

Dead code accumulates silently and slows down comprehension.

**Find unused exports (ts-prune):**

```bash
npx ts-prune
```

Output:

```
src/utils/legacyHelper.ts:15 - formatOldDate (unused)
src/services/deprecated.ts:1 - default (unused)
```

**Find unused files (knip -- comprehensive unused code detector):**

```bash
npx knip
```

Knip finds unused files, unused dependencies, unused exports, and missing dependencies. It is the single best tool for codebase hygiene in JavaScript/TypeScript projects.

```json
// knip.json
{
  "entry": ["src/index.ts", "src/app/**/*.ts"],
  "project": ["src/**/*.ts"],
  "ignore": ["**/*.test.ts", "**/*.d.ts"],
  "ignoreDependencies": ["@types/*"]
}
```

**Coverage-based detection:**

```bash
# Run tests with coverage, look for files with 0% coverage
npx vitest run --coverage
# Files with 0% coverage are candidates for deletion (verify they aren't
# used in non-tested paths first)
```

### 7.4 Architecture Decision Records (ADRs)

ADRs capture the "why" behind technical decisions. They are invaluable when someone (including future you) asks "why did we choose X over Y?"

**Format (Michael Nygard's template):**

```markdown
<!-- docs/adrs/005-use-trpc-for-internal-apis.md -->
# ADR-005: Use tRPC for Internal APIs

## Status
Accepted (2026-03-15)

## Context
We have 47 REST endpoints. Type mismatches between frontend and backend
cause ~2 bugs per sprint. Our frontend and backend are both TypeScript.

## Decision
Use tRPC for all new internal APIs. Existing REST endpoints will be
migrated incrementally.

## Consequences
### Positive
- End-to-end type safety eliminates type mismatch bugs
- No code generation step (unlike OpenAPI + codegen)
- Better developer experience (autocomplete for API calls)

### Negative
- Only works for TypeScript clients (mobile team uses Kotlin)
- Tight coupling between frontend and backend types
- Team needs to learn tRPC patterns

### Neutral
- Public API remains REST (for third-party consumers)

## Alternatives Considered
1. **GraphQL** -- More flexible but higher complexity, overkill for our use case
2. **OpenAPI codegen** -- Works across languages but adds build step and generation complexity
3. **Status quo (manual types)** -- Rejected due to ongoing bug rate
```

**Naming convention:** Number sequentially (`001-`, `002-`...). Titles should be decisions, not questions ("Use PostgreSQL for primary database", not "Which database should we use?").

**ADRs are immutable.** If a decision is reversed, create a new ADR that supersedes the old one. Never edit an accepted ADR -- the historical record of why the original decision was made remains valuable.

### 7.5 Periodic Architecture Reviews

**Quarterly review checklist:**

```markdown
## Architecture Review - Q1 2026

### Dependency Health
- [ ] All dependencies on supported versions?
- [ ] Any deprecated dependencies still in use?
- [ ] Security vulnerabilities addressed?

### Code Health
- [ ] Run knip -- any new dead code?
- [ ] Run dependency-cruiser -- any new boundary violations?
- [ ] Review SonarQube trends -- debt increasing or decreasing?

### Performance
- [ ] Review p50/p95/p99 latency trends
- [ ] Review error rate trends
- [ ] Any new N+1 query patterns?

### Architecture Fitness
- [ ] Are architectural boundaries holding?
- [ ] Any packages that have grown too large and should be split?
- [ ] Any new cross-cutting concerns that need shared solutions?

### Documentation
- [ ] Are ADRs up to date?
- [ ] Are READMEs accurate?
- [ ] Any tribal knowledge that should be documented?
```

### 7.6 The "Leave It Better Than You Found It" Culture

This is the single most powerful organizing principle for long-lived codebases:

**The Boy Scout Rule:** Every time you touch a file, leave it slightly better than you found it.

- Rename a confusing variable
- Add a missing type annotation
- Delete a commented-out block of code
- Add a missing test for an edge case you noticed
- Fix a lint warning

**This compounds.** If every engineer makes one small improvement per PR, a 10-person team makes 50+ improvements per sprint. Over a year, that is over a thousand incremental improvements -- without ever scheduling a "cleanup sprint."

**What this requires:**

- PR reviewers who do not reject "while I was here" improvements as scope creep
- A culture that values cleanliness as much as features
- Leading by example -- senior engineers who visibly clean up code in their PRs

---

## Key Takeaways

1. **Automate formatting and linting from day one.** The cost of setup is an hour. The cost of not having it is perpetual review friction and inconsistent code.

2. **CI pipelines should fail fast.** Lint before test, unit before integration. Optimize for developer feedback speed.

3. **Scale your process with your team size.** A solo developer needs a pre-commit hook and CI. A 10-person team needs shared configs and PR templates. A 100-person team needs architecture fitness functions, RFCs, and a platform team.

4. **Feature-based organization beats layer-based** for any non-trivial project. Colocate tests with source code.

5. **Track technical debt explicitly** and allocate time to address it. Untracked debt compounds until it halts progress.

6. **ADRs capture the "why."** Code shows what. Comments show how. ADRs show why. All three are necessary.

7. **The Boy Scout Rule is the only sustainable strategy** for long-term codebase health. Big rewrite projects fail. Incremental improvement works.

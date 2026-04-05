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

A well-organized codebase is a gift to your future self. This chapter covers the full spectrum: linting setup for the solo developer who wants to stop arguing with themselves about semicolons, all the way to monorepo governance for a 100-person engineering org that needs automated architectural boundaries to stay sane. These patterns are engineering hygiene — boring by design, compounding in value.

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
- Chapter 7 — CI/CD concepts (the pipeline theory behind Section 2)
- Chapter 12 — Git/tooling skills
- Chapter 9 — engineering leadership/ADRs
- Chapter 20 — dependency management
- Chapter 33 — GitHub Actions Mastery (advanced workflows that build on Section 2)

---

## 1. LINTING & FORMATTING (The Foundation)

### 1.1 Why This Matters

Here is a scenario you have probably lived through: you open a PR and half the comments are about formatting. Spaces vs. tabs. Missing semicolons. Inconsistent quote style. A trailing comma that someone finds aesthetically offensive. None of these comments are about logic, architecture, or correctness — they are pure noise that drains reviewer energy and delays the real conversation.

Now imagine a different world: every PR looks identical in style, regardless of who wrote it. Reviewers spend their attention on business logic and architectural decisions. Nobody argues about formatting because the formatter already ran. This is not a utopia — it is fifteen minutes of setup.

Automated formatting eliminates entire categories of code review friction. When formatting is enforced by tooling, those comments disappear entirely. You are left with reviews that actually matter.

**The rule:** No human should ever manually format code. Configure the tools once, enforce them in CI, and never think about it again.

This is also why linting is different from formatting, and why conflating them costs you twice. Linters like ESLint catch real bugs: forgotten `await` calls, promises in non-async callbacks, unreachable code. Formatters like Prettier handle the visual presentation. You need both. You want them to stay in their own lanes.

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

**Key insight:** ESLint catches bugs and enforces code quality rules. Prettier handles formatting. Do not use ESLint for formatting -- that is Prettier's job. `eslint-config-prettier` disables all ESLint rules that conflict with Prettier. This is the single most common misconfiguration — teams end up with ESLint and Prettier fighting each other, producing conflicts on every save. The `eslint-config-prettier` package ends that fight by making ESLint completely stand down on anything visual.

### 1.3 Python: Ruff + mypy

Ruff replaces flake8, black, isort, pyflakes, pycodestyle, and more. It is written in Rust and is 10-100x faster than the tools it replaces. If you are still running a chain of five Python linters that take 30 seconds each, Ruff is the upgrade you have been waiting for. It handles everything in a single pass, in milliseconds.

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

Do not skip mypy. Gradual typing is fine — start with `disallow_untyped_defs = false` and tighten it over time. But running without any type checking in a production Python codebase is how you end up debugging `AttributeError: 'NoneType' object has no attribute 'user_id'` at 2am.

### 1.4 Go: gofmt + golangci-lint

Go has the strongest formatting culture of any major language: `gofmt` is the standard, and there is essentially no debate about style. The Go team made an opinionated choice early, and the entire ecosystem has been reaping the benefits ever since. Every Go file, everywhere, looks the same. When you open someone else's Go code, you are not spending cognitive energy parsing unfamiliar formatting conventions.

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

Clippy is worth paying attention to — it catches genuinely problematic patterns, not just style issues. `clippy::pedantic` is aggressive, but going through its suggestions once teaches you a lot about idiomatic Rust.

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

Every project should have an `.editorconfig` file at the root. This is your lowest-common-denominator contract: regardless of whether developers use VS Code, IntelliJ, Vim, or Emacs, basic settings are consistent. It does not replace Prettier or gofmt — those go deeper. EditorConfig handles the basics so that, before any language-specific tooling runs, everyone starts from the same place.

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

Commit this file. Every repo gets it. Non-negotiable.

### 1.8 Pre-Commit Hooks: lint-staged + husky

Here is the moment where it all comes together locally. Pre-commit hooks run your linter before you even push — catching issues in seconds rather than waiting for CI to fail three minutes later. The key trick: only lint files that are being committed. Linting the entire codebase on every commit is slow and discouraging. lint-staged solves exactly this.

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

**The "format on save" rule:** Every developer on the team must configure their editor to format on save. This is non-negotiable. It means code is always formatted before it even reaches the pre-commit hook — the hook becomes a safety net, not the primary mechanism.

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

Committing `.vscode/settings.json` is one of those small things that saves every new team member from a half-hour of "why is my linting not working the same as yours?" conversations.

---

## 2. CI/CD PIPELINE ARCHITECTURE

> For advanced GitHub Actions patterns — reusable workflows, OIDC federation, matrix strategies, custom actions, monorepo CI, and security hardening — see **Chapter 33: GitHub Actions Mastery**. This section covers the pipeline design philosophy; Chapter 33 goes deep on the implementation mechanics.

> For foundational CI/CD concepts — the deployment models, environment promotion strategies, and rollback patterns that underpin everything in this section — see **Chapter 7: DevOps for Engineers**.

### 2.1 Pipeline Stages (Optimal Order)

Think of your CI pipeline as a funnel. Cheap checks go first, expensive checks go last. You want to fail as fast as possible when something is wrong, and you want the fast failures to be the most common ones.

The principle: **fail fast, fail cheap.** Run the fastest and most likely-to-fail checks first.

```
lint (10s) → type-check (30s) → unit test (1-2m) → build (2-3m)
→ integration test (3-5m) → security scan (2m) → deploy
```

**Why this order matters:**

1. **Lint** catches syntax errors and formatting issues in seconds. If formatting is wrong, do not waste time running tests.
2. **Type-check** (`tsc --noEmit`) catches type errors in 30 seconds. Faster than running tests and catches an entire class of bugs.
3. **Unit tests** run fast and catch logic errors. Run these before slow integration tests.
4. **Build** ensures the project actually compiles and bundles correctly. This should pass if lint and type-check pass, but bundle-level issues can surface here.
5. **Integration tests** are slower and require services (DB, Redis). Run only if everything above passes — there is no point spinning up Postgres if the code does not even type-check.
6. **Security scan** runs in parallel with integration tests. It does not need the build artifact.
7. **Deploy** only if everything passes.

A common mistake is running everything in parallel from the start. You will run integration tests on code that has a syntax error, burn 5 minutes of CI compute, and get a failure you could have caught in 10 seconds. Order matters.

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

For reusable workflow patterns, composite actions, and secrets federation with OIDC — all the things that make this scale across dozens of repositories — head to Chapter 33.

### 2.3 Optimizing CI Speed

Slow CI is one of the most corrosive forces in engineering productivity. When the feedback loop stretches past 15 minutes, developers switch context. Context switching is expensive. A 10-minute CI run that you watch is infinitely better than a 20-minute run you forget about. Optimize aggressively.

**Caching dependencies:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: "npm"  # Automatically caches ~/.npm
```

This single line shaves 2-3 minutes off most pipelines. The cache key is derived from your lockfile, so it invalidates automatically when dependencies change.

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

This is powerful when your test suite grows past 5 minutes. Four runners in parallel turns a 20-minute test run into 5.

**Only run affected tests (Turborepo):**

```bash
# Only test packages affected by changes since main
npx turbo run test --filter=...[main]
```

**Only run affected tests (Nx):**

```bash
npx nx affected --target=test --base=main
```

The Turborepo/Nx approach pays off enormously in monorepos. Why run 40 packages worth of tests when you touched one package? Section 5 covers this in detail.

### 2.4 Branch Protection Rules

Branch protection rules are the enforcement layer. All the tooling in the world does not matter if someone can bypass it. Configure in GitHub Settings > Branches > Branch protection rules:

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

That last checkbox — enforcing for admins — is important. A bypass escape hatch that exists will eventually be used, and it will always be at the worst possible time.

### 2.5 Secrets Management in CI

**Hierarchy of secrets management (from simplest to most secure):**

1. **GitHub Encrypted Secrets** -- good enough for most teams. Set via Settings > Secrets.
2. **OIDC Tokens** -- for AWS/GCP/Azure, use OIDC instead of long-lived credentials. This is the right approach for anything production:

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

3. **HashiCorp Vault / AWS Secrets Manager** -- for large organizations with rotation requirements and audit trails.

**Rules:**
- Never echo secrets in CI logs. GitHub masks them in output, but `echo $SECRET | base64` will bypass that masking.
- Never commit `.env` files (add to `.gitignore`)
- Rotate secrets on a schedule
- Use environment-scoped secrets (prod secrets only available in prod deployment jobs)

### 2.6 Deployment Gates

The deployment gate pattern is where engineering discipline meets business risk management. Staging gets automatic deployment; production requires both automated verification and human approval.

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

The post-deploy smoke test is not optional. It is the difference between "we deployed" and "we deployed and it works." See Chapter 7 for the full model of environment promotion, canary deployments, and rollback strategies.

---

## 3. SOLO DEVELOPER ORGANIZATION (1 Person)

### 3.1 The Solo Developer's Trap

Here is the lie you tell yourself when you are the only engineer: "I know where everything is. I wrote it. I do not need process."

Three months later, you open your own project and spend 20 minutes trying to remember why you made a particular architectural decision. Six months later, you want to extract a feature into a shared library but everything is tangled together. A year later, you bring on a second engineer and they spend a week just understanding the project structure.

The solo developer trap is assuming that "just you" means "never needs organization." The reality is that the most forgetful reviewer of your code is future you. Future you deserves the same respect you would give a colleague.

Even when you are the only developer, automated standards prevent "I'll clean it up later" technical debt from accumulating. Because "later" never comes.

**Essential tools to configure from day one:**

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

A conventional commit history is searchable. `git log --oneline --grep="fix(billing)"` pulls up every billing fix. `git log --oneline --grep="feat"` gives you a changelog draft. When you are debugging a regression six months from now, this is the difference between a five-minute `git bisect` and a two-hour archaeology expedition.

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

Even for personal projects, consistent structure pays off when you return to the code after months. The structure below is not arbitrary — it maps to mental models. When you need to find business logic, you look in `services/`. When you need a shared utility, you look in `lib/`. That predictability compounds.

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

Notice `.env.example`. This is the pattern that saves future-you (or a collaborator) from spending an hour figuring out what environment variables the project needs. Every variable in `.env.local` has a corresponding entry in `.env.example`, with a descriptive placeholder or a note about where to get the value. It is two minutes of work per variable. Do it every time.

### 3.3 Self-Code-Review Habits

The solo developer does not have someone to catch their mistakes in review. You have to be your own second set of eyes. These habits build that muscle:

- **Diff before commit:** Always run `git diff --staged` and read every line before committing. You will catch bugs you introduced five minutes ago that your brain is still too close to see.
- **Come back after a break:** If you wrote complex logic, review your own PR after stepping away for 30 minutes. A fresh pair of eyes catches what a tired pair misses — even when both pairs belong to you.
- **Write the PR description as if someone else will read it** -- future you is that someone. Describe the "why," not just the "what." Your future self will thank you when they are trying to understand a decision six months from now.

### 3.4 Automate Anything You Do More Than Twice

If you type the same command more than twice, it belongs in a script. The `package.json` scripts block is underutilized by most solo developers. Use it:

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

That `check` script is the one you run before opening a PR. It is also what CI runs. If they match, you never push a broken build.

---

## 4. SMALL TEAM ORGANIZATION (2-10 People)

### 4.1 The Phase Transition

The moment you add a second engineer, everything changes. Not because one person is untrustworthy, but because implicit knowledge becomes invisible. The mental model that lived in your head now needs to exist somewhere both of you can read.

Two engineers have different editor configurations. They have different opinions about code style (until the linter removes the opinion). They have different ideas about where new files should live. Without explicit conventions, these differences compound into a codebase that looks like it was written by committee — inconsistent, unpredictable, and hard to navigate.

The good news: the tooling from Section 1 and 2 handles most of this automatically. What you add at the 2-10 person stage is the coordination layer: shared configs, PR templates, branch conventions, and lightweight decision records.

### 4.2 Shared Linting Configuration

Create a shared ESLint config package so all projects in your organization use the same rules. The moment you have two repos with two different ESLint configs, you will have a drift problem within months.

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

The override mechanism is important. Shared config provides the baseline. Projects can diverge where they have legitimate reasons. But the baseline is the baseline — not a suggestion.

### 4.3 PR Template

A PR template is a forcing function for communication. Without one, PRs get descriptions like "fix bug" or "update things." With one, reviewers have context before they even open a diff.

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

The checklist items are load-bearing. They encode institutional knowledge about what tends to go wrong. Add items when you find new categories of mistakes. Remove items when they stop being relevant. Treat the template as a living document.

### 4.4 Branch Naming Conventions

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

The ticket reference (`TICKET-123`) in the branch name is optional but highly recommended. It links code to requirements, makes branch cleanup easier, and lets GitHub Actions automatically link PRs to your issue tracker.

### 4.5 Code Ownership (CODEOWNERS)

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

CODEOWNERS plugs into GitHub's branch protection rules. When a PR touches `prisma/`, Alice is automatically requested as a reviewer. No one has to remember. No database migration goes in without someone who understands the schema looking at it.

This is also a forcing function for reducing single points of failure. If only one person understands the database schema, that person is a bus factor risk. CODEOWNERS makes that risk visible.

### 4.6 Monorepo vs. Polyrepo Decision

**At 2-10 people, monorepo is almost always better.** Here is the reality:

| Factor | Monorepo | Polyrepo |
|--------|----------|----------|
| **Code sharing** | Trivial -- import from `@company/shared` | Requires publishing packages, version management |
| **Atomic changes** | One PR changes API + frontend + shared types | Coordinated PRs across 3 repos |
| **CI complexity** | One pipeline, run affected tests | N pipelines, cross-repo trigger chains |
| **Onboarding** | Clone one repo, run one setup command | Clone N repos, configure each |
| **Dependency consistency** | One lockfile, one version of React | Version drift across repos |

The cross-repo coordination cost is underestimated every single time. You have a type change in your API. You update the frontend. But the mobile app uses the old type. You need three coordinated PRs, a shared type library release, and a migration window. In a monorepo, that is one PR.

**When polyrepo makes sense:** Genuinely independent services with different teams, different deploy cadences, and no shared code. At 2-10 people, this is rare. If you find yourself arguing for polyrepo at this team size, the more likely problem is that your code boundaries are unclear, not that your repo structure is wrong.

### 4.7 Lightweight RFCs

For non-trivial changes — a new service, a database schema change, a significant architecture shift — write a one-page RFC before coding. This is not bureaucracy. It is a 30-minute investment that prevents a week of rework when someone says "wait, did we consider X?"

The RFC forces you to articulate your reasoning before you are emotionally invested in the implementation. It surfaces concerns from teammates who might not have time to review a 500-line PR but can read a one-pager in five minutes.

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

**The RFC is a conversation starter, not a final word.** The author is not looking for permission — they are looking for blind spots. Write it with that spirit and it will not feel like bureaucracy.

---

## 5. LARGE TEAM ORGANIZATION (10-100+ People)

### 5.1 When Informality Becomes Chaos

Let me tell you about a codebase I heard about — a startup that grew from 5 to 50 engineers over 18 months. In the early days, everyone knew the architecture. The tech lead knew every service. PRs were reviewed by whoever was available. Deploys happened when someone felt confident.

By month 18, nobody could tell you which team owned the payment service. The frontend imported directly from `../../services/auth/internal`, violating the API boundary everyone had implicitly agreed to but never enforced. Three different teams had three different logging patterns. Database migrations ran in any order because the migration runner was whoever remembered to do it. Onboarding took three weeks.

The problems were not hard engineering problems. They were coordination problems. At 10+ people, you need systems that enforce coordination automatically, because informal coordination does not scale.

That is what this section is about.

### 5.2 Monorepo Tooling

At scale, you need build system intelligence. These tools understand the dependency graph and only rebuild/retest what changed. Without them, you are either running CI on everything (slow) or running CI on nothing (risky).

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

The `^build` dependency declaration is the key insight. It tells Turborepo: "before building this package, build everything it depends on." This produces a topologically correct build order automatically, in parallel where possible. See Chapter 33 for how to integrate Turborepo's remote caching into GitHub Actions pipelines.

**Nx (alternative, more features, steeper learning curve):**

```bash
npx nx affected --target=test --base=main
npx nx graph  # Visualize dependency graph
```

Nx's `graph` command is genuinely useful during code review — seeing a visual dependency graph helps you understand the blast radius of a change.

**Bazel (for very large, multi-language monorepos -- Google, Stripe scale):**

Bazel provides hermetic builds (every build is reproducible) and remote caching. It is significantly more complex to set up but scales to millions of lines of code and dozens of languages in a single repo. The productivity investment is substantial; the payoff at truly massive scale is real.

### 5.3 Shared Packages

In a monorepo, shared packages are the economic engine. They let teams share code without the coordination overhead of independent package publishing. Build them early. Build them well.

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

The `@company/logger` package deserves special mention. When every service writes logs differently — some JSON, some not; some with request IDs, some without; some with stack traces, some losing them — debugging a distributed system becomes an archaeological dig. A shared logging wrapper ensures every service produces logs in the same format, with the same fields, parseable by the same tools.

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

### 5.4 Architecture Fitness Functions

This is the idea that saves large codebases from entropy. The term comes from evolutionary architecture: just as fitness functions in genetic algorithms determine whether a solution survives, architectural fitness functions automatically verify whether your codebase is staying within its intended boundaries.

Without fitness functions, architectural decisions degrade. Someone adds a `import { db } from '../../lib/db'` inside a UI component because it was faster. Someone adds a circular dependency because the alternative required a refactor. Someone imports an internal implementation detail from a package that was supposed to have a clean API. Nobody catches it. Six months later, the architecture is unrecognizable.

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

When this check runs in CI (see Chapter 33 for the workflow pattern), architectural violations fail the build. The architecture is enforced automatically, not through code review heroics.

### 5.5 RFC Process for Cross-Team Changes

At 10+ people, RFCs become a critical coordination mechanism. Without them, you get invisible decisions — one team makes a choice that affects three others, and nobody finds out until the other teams are already building against the old assumption.

The RFC process creates a paper trail of technical decisions. It forces cross-team notification before work starts. It gives people who are not in the room a structured way to participate.

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

**Store RFCs in the repo** (`docs/rfcs/`) so they are versioned, searchable, and linked to the code they describe. An RFC that lives in Confluence might as well not exist — nobody will find it when they need it. An RFC in the repo is findable with `git log`, `grep`, and code search.

### 5.6 Tech Radar

A tech radar categorizes technologies your organization uses into four rings. This is about managing cognitive load at scale: when 50 engineers can independently choose any technology, you end up with 30 different ways to do the same thing.

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

**Update quarterly.** Make it a living document, not a one-time exercise. The most dangerous state is a tech radar that was written 18 months ago and has not been touched since — it becomes a false authority that nobody trusts.

The tech radar is also a forcing function for having explicit opinions. "We have not decided" is not a position. "Assessing" is a position.

### 5.7 Inner-Source Model

Allow teams to contribute to each other's services through a structured process. Without structure, you get either "no contributions from outside the team" (silos) or "anyone can merge anything to any repo" (chaos). The inner-source model gives you the benefits of open source contribution patterns inside a company:

1. **Service owners maintain a `CONTRIBUTING.md`** with setup instructions, architecture overview, and PR expectations
2. **External contributors** open an issue first describing the change
3. **Service owners** triage within 2 business days
4. **PRs from external contributors** require review from a service owner
5. **Shared packages** (`@company/*`) accept contributions from any team

This model scales contribution without scaling coordination cost linearly.

### 5.8 API Contract Enforcement

For services communicating via HTTP, enforce contracts with OpenAPI specs. A verbal agreement about API shape is not an agreement — it is a future bug.

```bash
# Generate types from OpenAPI spec
npx openapi-typescript api/openapi.yaml -o src/types/api.d.ts

# Validate API responses match the spec (in tests)
npm install -D openapi-response-validator
```

**Backward compatibility rule:** Never remove or rename a field in an API response. Add new fields, deprecate old ones, remove after all consumers have migrated. This rule sounds obvious until the third time someone removes a field and breaks two consumers that nobody remembered were using it.

### 5.9 Automated Dependency Updates

Manual dependency updates do not happen. Everyone intends to do them, and then a quarter goes by and you have 60 pending minor updates and three major versions to jump. Automate it.

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
- Auto-merge minor/patch updates (if CI passes). If your CI is good enough to trust, trust it.
- Group related packages (all ESLint plugins update together) — one PR review for 6 lint package bumps instead of 6 separate ones.
- Major updates require manual review. This is where breaking changes live.
- Run on a schedule (Monday mornings) to avoid constant PR noise.

Renovate pays for itself the first time it auto-merges a security patch at 3am before you even wake up.

### 5.10 Platform Team and Golden Paths

When you have 10+ services, the invisible tax is setup cost. Every new service means making 50 decisions: Which test framework? What logging format? How does CI work? Where do secrets go? How do we do database migrations? How do we deploy?

A platform team eliminates this tax by providing "golden paths" — opinionated, well-supported ways to build common things. Engineers still have the freedom to deviate, but the default is fast, correct, and consistent.

**What a golden path includes:**

- A project template (`create-company-app`) with all tooling pre-configured
- Shared CI pipeline templates (see Chapter 33 for reusable workflows)
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

New service, day one: clone, `npm install`, you are already following every standard the company has. That is the goal.

### 5.11 Service Catalog (Backstage)

At 50+ services, you need a catalog. Without one, the answer to "what services exist and who owns them?" is "ask around." Backstage (by Spotify) turns institutional knowledge into structured data.

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

The `dependsOn` field is what makes this genuinely useful. When the user service has an incident, Backstage can tell you which other services depend on it. Incident response goes from "which team do we call?" to "here are the five affected services and their owners."

---

## 6. REPOSITORY STRUCTURE PATTERNS

### 6.1 Feature-Based vs. Layer-Based Organization

This is one of those decisions that seems minor until you are maintaining a 100,000-line codebase. The wrong choice does not kill you; it just makes every developer slightly slower, every day, forever.

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

- **Layer-based:** Small projects (< 10 files per layer), quick prototypes, when the domain model is simple. If you have five files total, do not overthink this.
- **Feature-based:** Medium to large projects, when features have clear boundaries, when teams own features. This is almost always the better choice for production codebases.

Here is why feature-based wins at scale: adding a new feature means adding a new folder. You create `src/features/notifications/` and everything you need is in one place. In a layer-based structure, adding notifications means touching `controllers/`, `services/`, `repositories/`, and `models/` — four separate directories, all for one logical feature.

Feature-based organization also makes ownership clearer. If the billing team owns `src/features/billing/`, CODEOWNERS can reflect that exactly. Layer-based ownership is murkier — who owns `services/`?

### 6.2 Monorepo Layout

This layout is the result of a lot of teams learning the same lessons. The `apps/` / `packages/` split is the critical structural decision — apps are deployable things, packages are shared libraries.

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

Tests belong next to the code they test. This is one of those opinions that sounds like preference but is actually engineering pragmatism.

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

**Why colocation beats a separate `tests/` directory:**

- When you open a file, the test is right there. The friction to update a test drops to zero. You are more likely to do it.
- When you delete a feature, the test goes with it automatically. No orphaned test files that test things that no longer exist.
- When you refactor, the test moves with the code. In a separate `tests/` directory, you have to remember to move both.
- Navigation is faster. No context-switching between `src/` and `tests/` to understand a feature.

**Exception:** Integration tests and E2E tests that span multiple modules belong in a top-level `tests/` directory because they do not belong to any single module. `tests/e2e/billing-flow.test.ts` tests user-visible behavior that crosses service boundaries — it lives at the top level, where it can reference anything.

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

- Package public API: clearly defines what consumers can import from your package. Everything not exported here is considered internal.
- Simplifies imports: `import { Button, Input } from "@company/ui"` instead of `from "@company/ui/src/button"`. Your public API is stable even as the internal structure evolves.

**When they hurt:**

- **Circular dependencies:** If `button.ts` imports from `utils.ts` which imports from `index.ts` which imports `button.ts`, you have a circular dependency that is invisible until the bundler blows up.
- **Tree-shaking problems:** If you import one thing from a barrel, bundlers may pull in everything. Modern bundlers (webpack 5, Vite/Rollup) handle this better with `"sideEffects": false` in `package.json`, but it requires intentional configuration.
- **IDE performance:** Large barrel files with 50+ re-exports slow down the TypeScript language server. You start to notice it in autocomplete latency.

**Best practice:** Use barrel files at package boundaries (the `index.ts` of `@company/ui`). Avoid barrel files within a package's internal directory structure. The rule of thumb: one level of barrel per package, not one per directory.

---

## 7. KEEPING THINGS ORGANIZED OVER TIME

### 7.1 The Compounding Nature of Disorganization

Here is the thing about codebases that go wrong: they do not collapse overnight. They degrade in increments. A file that is slightly too long. A service that has one responsibility too many. A dependency that gets upgraded on one project but not another. An ADR that was never written. A test that was skipped "just this once."

Each individual decision is defensible. Collectively, they produce a codebase that every engineer describes as "hard to work in" without being able to articulate a specific cause. The cause is the aggregate of a thousand small decisions that each went slightly the wrong way.

The practices in this section are about reversing that gradient. Not a big rewrite — those fail. Not a "cleanup sprint" — those are one-time events with no lasting effect. Incremental, systematic, continuous improvement.

### 7.2 Technical Debt Tracking

Technical debt is inevitable. Untracked technical debt is dangerous. The difference between manageable debt and paralyzing debt is visibility.

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

The owner and target date columns are load-bearing. Debt without an owner is a wish. Debt without a target date is a permanent fixture. Both columns force accountability.

**Automated tracking (SonarQube/SonarCloud):**

SonarQube provides "technical debt" estimates based on code smells, duplications, and complexity. Set quality gates:

```
Quality Gate: Sonar Way (customized)
- New code coverage > 80%
- No new bugs (severity: critical or higher)
- No new security vulnerabilities
- Technical debt ratio on new code < 5%
```

**The 20% rule:** Dedicate approximately 20% of each sprint to technical debt reduction. If you cannot justify 20%, negotiate 10% as a minimum. Zero percent leads to exponential decay. The codebase will eventually become the thing that slows every feature by 30%. When that happens, you do not get to ship features — you have a debt crisis.

### 7.3 Dependency Freshness

**Automated with Renovate (see Section 5.9) plus manual review cadence:**

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

The worst case is a dependency that has had an unnoticed breaking change in a minor version (technically a semver violation, but it happens). The second worst case is a critical security vulnerability in a package you have not updated in 18 months. Renovate hedges against both.

### 7.4 Dead Code Elimination

Dead code accumulates silently. Every file that used to do something important and now does nothing is a file the next engineer will spend time reading, understanding, and deciding whether to change. Multiply that across a large codebase and you are paying a significant cognitive tax.

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

Knip finds unused files, unused dependencies, unused exports, and missing dependencies. It is the single best tool for codebase hygiene in JavaScript/TypeScript projects. Run it quarterly. The first time you run it on an established codebase, the results will surprise you.

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

Coverage does not catch everything — some code paths are legitimately hard to test. But a file with 0% coverage in a well-tested codebase is a strong signal that nobody is using it.

### 7.5 Architecture Decision Records (ADRs)

ADRs capture the "why" behind technical decisions. They are invaluable when someone (including future you) asks "why did we choose X over Y?" — a question that comes up constantly in the context of onboarding new engineers, evaluating migration paths, and understanding system constraints.

Without ADRs, that knowledge lives in the memory of whoever made the original decision. When that person leaves, the knowledge leaves with them. You are left with a system full of choices that nobody can explain.

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

**Naming convention:** Number sequentially (`001-`, `002-`...). Titles should be decisions, not questions. "Use PostgreSQL for primary database" is a good ADR title. "Which database should we use?" is a question, not a decision — and once you have decided, the ADR should reflect what you decided.

**ADRs are immutable.** If a decision is reversed, create a new ADR that supersedes the old one. Never edit an accepted ADR. The historical record of why the original decision was made — including the constraints that were true at that time — remains valuable even when the decision has changed.

The context in which a decision was made often reveals things the current state of the codebase no longer communicates. "We chose Redis for sessions because we needed multi-region failover, but we were also cost-constrained and could not use a managed service" is information that cannot be recovered from looking at the code.

### 7.6 Periodic Architecture Reviews

Automated checks catch boundary violations. Quarterly reviews catch everything else — patterns that no automated tool has been configured to detect, trends that require human judgment, and the meta-question of whether the architecture is still fit for the product's current direction.

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

Schedule this as a recurring calendar event. "We should do an architecture review sometime" means it never happens.

### 7.7 The "Leave It Better Than You Found It" Culture

This is the single most powerful organizing principle for long-lived codebases. Not a big rewrite. Not a cleanup sprint. A culture of continuous, incremental improvement baked into every PR.

**The Boy Scout Rule:** Every time you touch a file, leave it slightly better than you found it.

Practically, this means:
- Rename a confusing variable while you are already in the file
- Add a missing type annotation to a function you are modifying
- Delete a commented-out block of code that has been sitting there for six months
- Add a missing test for an edge case you noticed while debugging
- Fix a lint warning in a file you are already editing

Each of these takes 30-60 seconds. None of them requires a separate PR.

**This compounds.** If every engineer makes one small improvement per PR, a 10-person team makes 50+ improvements per sprint. Over a year, that is over a thousand incremental improvements — without ever scheduling a "cleanup sprint."

The codebases that stay clean over years are not the ones that have quarterly rewrite projects. They are the ones where every engineer has internalized the habit of leaving things slightly better than they found them.

**What this requires:**

- PR reviewers who do not reject "while I was here" improvements as scope creep. A rename that improves clarity is never out of scope.
- A culture that values cleanliness as much as features. This has to come from the top — teams reflect the values of their senior engineers.
- Leading by example. Senior engineers who visibly clean up code in their PRs create permission for everyone else to do the same.

The inverse is also true: senior engineers who consistently skip cleanup, comment with "not in scope" when someone tries to improve something, or who treat any non-feature work as a distraction, produce codebases that degrade at scale.

---

## Key Takeaways

1. **Automate formatting and linting from day one.** The cost of setup is an hour. The cost of not having it is perpetual review friction and inconsistent code. This is the highest-return investment in codebase organization.

2. **CI pipelines should fail fast.** Lint before test, unit before integration. Optimize for developer feedback speed — slow CI destroys flow state and costs you more than the compute savings. See Chapter 7 for pipeline theory and Chapter 33 for advanced GitHub Actions patterns.

3. **Scale your process with your team size.** A solo developer needs a pre-commit hook and CI. A 10-person team needs shared configs, PR templates, and lightweight RFCs. A 100-person team needs architecture fitness functions, a formal RFC process, and a platform team.

4. **Feature-based organization beats layer-based** for any non-trivial project. Adding a feature means adding a folder. Colocate tests with source code — proximity reduces the friction to keep tests updated.

5. **Track technical debt explicitly** and allocate time to address it. Untracked debt compounds silently until it halts progress. The 20% rule — 20% of sprint capacity on debt reduction — is not idealistic, it is the minimum viable maintenance.

6. **ADRs capture the "why."** Code shows what. Comments show how. ADRs show why. All three are necessary for a codebase that remains comprehensible as teams turn over and requirements evolve.

7. **Architecture fitness functions make boundaries permanent.** Architectural decisions degrade without automated enforcement. dependency-cruiser in CI turns "we agreed not to import from the database layer in UI components" from a verbal agreement into a build failure.

8. **The Boy Scout Rule is the only sustainable strategy** for long-term codebase health. Big rewrite projects fail — they are too long, too risky, and always interrupted by product demands. Incremental improvement, applied consistently by every engineer every day, works. The codebase either improves or degrades. There is no stable equilibrium.

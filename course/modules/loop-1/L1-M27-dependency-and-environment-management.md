# L1-M27: Dependency & Environment Management

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M24 (Secrets Management)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

Right now, the TicketPulse team has a problem:

| | Developer A | Developer B | CI | Production |
|---|---|---|---|---|
| Node.js | 18.19.0 | 20.11.0 | 20.10.0 | 22.1.0 |
| npm | 9.8.1 | 10.2.4 | 10.1.0 | 10.3.0 |
| PostgreSQL | 16.1 (Homebrew) | 15.4 (Docker) | 16.2 (apt) | 16.2 (RDS) |

Developer A writes code that works on Node 18. Developer B's tests pass on Node 20. CI fails because it is on a different patch version. Production runs Node 22, which has a breaking change in the Buffer API.

Every difference is a production incident waiting to happen.

> 💡 **Chapter 20 of the 100x Engineer Guide** covers dependency management at depth: how dependency resolution algorithms work, why the left-pad incident happened, what supply chain attacks look like, and why lockfiles are a security mechanism as much as a reproducibility mechanism. This module is the applied companion: you will pin your environment, audit your lockfile, and understand what "reproducible" really means.

By the end of this module, every developer and every CI runner will use exactly the same Node version, install exactly the same dependencies, and load exactly the same environment variables — automatically, with zero manual steps.

**You will pin your Node version within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Check what Node version you are running:

```bash
node --version
# v20.11.0? v22.1.0? v18.19.0? It varies.
```

Now check what the CI pipeline uses:

```bash
# Look at the GitHub Actions workflow
cat .github/workflows/ci.yml | grep "node-version"
```

Are they the same? Probably not. Let us fix that.

---

## 1. The Left-Pad Incident: Why This Matters More Than You Think

Before we fix TicketPulse's environment, let us understand why dependency management is a reliability and security problem, not just a developer convenience problem.

### What Happened

On March 22, 2016, a developer named Azer Koçulu unpublished 273 npm packages because of a naming dispute with npm's legal team. One of those packages was `left-pad` — a 17-line utility that left-pads strings.

**The aftermath:**

```
left-pad was a dependency of:
  babel-runtime
    → which was a dependency of:
  babel-core
    → which was a dependency of:
  react, angular, ember, and thousands of other projects

Result: The entire JavaScript build ecosystem broke globally
for 2.5 hours. Thousands of CI pipelines failed. Hundreds
of production deployments were blocked.
```

**The 17-line function that broke the internet:**

```javascript
module.exports = leftpad;

function leftpad(str, len, ch) {
  str = String(str);
  var i = -1;
  if (!ch && ch !== 0) ch = ' ';
  len = len - str.length;
  while (++i < len) {
    str = ch + str;
  }
  return str;
}
```

### What Left-Pad Reveals

The left-pad incident is not a story about npm being unreliable. It is a story about:

1. **Shallow dependencies becoming deep risks.** Nobody depended directly on left-pad. They depended on babel, which depended on it. When you install 50 top-level packages, you are actually installing 500-2,000 transitive dependencies. Every one of them can be removed, modified, or compromised.

2. **The "it's just a utility" fallacy.** No package is "just a utility." If your build breaks without it, it is critical infrastructure.

3. **Lockfiles as survival mechanisms.** If every project had used `npm ci` (or the equivalent), the left-pad removal would not have broken existing builds — they would have used the locked version from the cache.

### 🤔 Reflect: TicketPulse's Exposure

```bash
# How many dependencies does TicketPulse actually have?
npm ls --all 2>/dev/null | wc -l

# How many are direct vs transitive?
cat package.json | jq '.dependencies | keys | length'  # Direct
npm ls --depth=0 2>/dev/null | wc -l                   # Direct (alt)
npm ls --all 2>/dev/null | wc -l                       # All (recursive)
```

For a typical Node.js application, the ratio is often 1:20 or worse — 50 direct dependencies with 1,000+ transitive dependencies. Every one of those 1,000 packages is a potential point of failure.

---

## 2. Build: Pin the Node Version

### 2.1 Create .nvmrc

The `.nvmrc` file declares which Node.js version this project requires. It is the single source of truth.

```bash
# Create .nvmrc in the project root
echo "20.11.0" > .nvmrc
```

If you use nvm:

```bash
# Install and use the pinned version
nvm install
nvm use
node --version
# v20.11.0 -- guaranteed
```

### 2.2 Add .tool-versions (for mise/asdf compatibility)

`.nvmrc` works with nvm. `.tool-versions` works with mise (formerly rtx) and asdf, which can manage Node, Python, Go, Rust, and 400+ other tools from a single file.

```bash
# .tool-versions -- in the project root
cat > .tool-versions << 'EOF'
nodejs 20.11.0
EOF
```

### 2.3 Update the CI Pipeline

```yaml
# .github/workflows/ci.yml -- use the same version everywhere
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'  # Read version from .nvmrc
      - run: node --version            # Verify: v20.11.0
      - run: npm ci
      - run: npm test
```

The `node-version-file: '.nvmrc'` line tells the CI to read the version from the same file developers use locally. One source of truth.

---

## 3. Try It: Install mise

mise (pronounced "meez") is the recommended tool for managing runtime versions. It replaces nvm, pyenv, rbenv, and dozens of other version managers with one tool.

### 3.1 Install mise

```bash
# macOS
brew install mise

# Linux
curl https://mise.run | sh
```

Add mise to your shell:

```bash
# For zsh (add to ~/.zshrc)
eval "$(mise activate zsh)"

# For bash (add to ~/.bashrc)
eval "$(mise activate bash)"
```

Restart your shell or source the config file.

### 3.2 Install the Pinned Node Version

```bash
cd ticketpulse

# mise reads .tool-versions (or .nvmrc) automatically
mise install

# Verify
node --version
# v20.11.0
```

### 3.3 See It Switch Automatically

```bash
# Leave the project
cd ~
node --version
# Whatever your system default is (e.g., v22.1.0)

# Enter the project
cd ~/ticketpulse
node --version
# v20.11.0 -- mise switched automatically
```

This is the magic: you never think about Node versions again. Enter the directory, get the right version. Leave the directory, go back to your default. No `nvm use`, no manual switching.

---

## 4. Lockfiles: The Deep Dive

### 4.1 The Problem

```bash
# Developer A runs this on Monday:
npm install
# package-lock.json is generated with express@4.18.2

# Developer B runs this on Friday:
npm install
# express@4.18.3 was released on Wednesday
# Developer B gets a different version than Developer A
```

Even though `package.json` says `"express": "^4.18.2"`, the `^` means "4.18.2 or higher." A new patch release changes what gets installed.

### 4.2 npm ci: The Reproducible Install

```bash
# BAD for CI/production -- may resolve different versions
npm install

# GOOD for CI/production -- installs exactly what is in the lockfile
npm ci
```

The differences:

| | `npm install` | `npm ci` |
|---|---|---|
| Reads | `package.json` (may resolve newer versions) | `package-lock.json` (exact versions) |
| Modifies lockfile | Yes (if newer versions exist) | Never |
| node_modules | Updates in-place | Deletes and recreates from scratch |
| Speed | Slower (compares existing) | Faster (clean install) |
| Use when | Adding/updating dependencies locally | CI, production, ensuring reproducibility |

### 4.3 Lockfile Analysis Exercise

Open TicketPulse's `package-lock.json`. It is verbose and hard to read — but it contains critical information. Let us decode it:

```json
{
  "name": "ticketpulse",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "ticketpulse",
      "version": "1.0.0",
      "dependencies": {
        "express": "^4.18.2"
      }
    },
    "node_modules/express": {
      "version": "4.18.2",       // ← Exact resolved version
      "resolved": "https://registry.npmjs.org/express/-/express-4.18.2.tgz",
      "integrity": "sha512-abc123...",  // ← SHA-512 hash of the package contents
      "dependencies": {
        "body-parser": "1.20.1", // ← Transitive dependencies, pinned exactly
        "cookie": "0.5.0",
        ...
      }
    }
  }
}
```

**What to look for in a lockfile audit:**

```bash
# 1. Check for packages with known vulnerabilities
npm audit

# 2. Find packages with multiple versions (often indicates version conflicts)
cat package-lock.json | jq '[.packages | keys[] | select(test("node_modules/.*/node_modules/"))] | length'
# A large number here means dependency conflicts -- packages pulled in at multiple versions

# 3. Verify integrity fields are present (they should be for all packages)
cat package-lock.json | jq '[.packages | to_entries[] | select(.value.integrity == null) | .key]'
# Any package without an integrity field is a potential security concern

# 4. Check for packages from non-standard registries
cat package-lock.json | jq '[.packages | to_entries[] | select(.value.resolved | startswith("https://registry.npmjs.org") | not) | .key]'
# Packages not from the official registry are worth scrutinizing
```

### 4.4 The Lockfile as a Security Mechanism

The `integrity` field in the lockfile is the critical security property. It is a SHA-512 hash of the package contents. When `npm ci` installs a package:

1. Downloads the package from the registry
2. Computes the SHA-512 hash of the downloaded content
3. Compares against the hash in the lockfile
4. **Fails the install if they do not match**

This means if an attacker:
- Modifies a package in the registry
- Publishes a malicious version under the same version number
- Compromises the registry itself

...`npm ci` with a committed lockfile will detect the tampering and fail. The lockfile is your last line of defense against supply chain attacks.

**The 2021 ua-parser-js incident:** The `ua-parser-js` npm package (downloaded 8 million times/week) was compromised. The attackers published a malicious version that installed cryptomining software. Projects using `npm ci` with a lockfile that did not include the malicious version were protected — `npm ci` would have installed the locked (safe) version, not the new (malicious) one.

### 4.5 Update the CI Pipeline

```yaml
# .github/workflows/ci.yml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-node@v4
    with:
      node-version-file: '.nvmrc'
  - run: npm ci                    # NOT npm install
  - run: npm test
```

### 4.6 The Rule

- **Locally:** Use `npm install` when adding or updating packages. Commit the updated `package-lock.json`.
- **CI and production:** Always use `npm ci`. If the lockfile is out of date, the build fails — which is what you want. It forces developers to commit their lockfile changes.

---

## 5. Build: direnv for Auto-Activation

In M24, you set up a `.env` file and learned about direnv for loading environment variables. Now we combine it with mise for the complete auto-activation experience.

### 5.1 Create .envrc

```bash
# .envrc -- in the project root
cat > .envrc << 'EOF'
# Load environment variables from .env
dotenv_if_exists .env

# Use mise to activate the correct Node version
# (This replaces "nvm use" -- happens automatically)
use mise

# Add local binaries to PATH
PATH_add node_modules/.bin

# Print confirmation
echo "TicketPulse dev environment loaded: Node $(node --version)"
EOF
```

Allow it:

```bash
direnv allow
```

### 5.2 Try It: The Full Experience

```bash
# Leave the project directory
cd ~

# Enter the project directory
cd ~/ticketpulse
# direnv: loading ~/ticketpulse/.envrc
# TicketPulse dev environment loaded: Node v20.11.0

# Everything is set:
echo $DATABASE_HOST      # localhost (from .env)
node --version           # v20.11.0 (from .tool-versions via mise)
which jest               # ./node_modules/.bin/jest (from PATH_add)
```

One `cd` command. Everything activates. No manual steps.

---

## 6. The Two-Command Onboarding

> **Reflect:** "A new developer joins the team. How many commands should they need to run to get TicketPulse working? Can we get it to two?"

### 6.1 The Current State (Too Many Steps)

A typical onboarding today looks like:

```bash
git clone https://github.com/100x-engineer/ticketpulse.git
cd ticketpulse
# Install nvm (if not installed)
# nvm install 20.11.0
# nvm use 20.11.0
# cp .env.example .env
# Edit .env with the right values
# npm install
# docker compose up -d postgres redis
# npm run db:migrate
# npm run db:seed
# npm run dev
```

That is 10+ commands, some of which require manual editing and tribal knowledge. A new developer can easily spend an hour getting set up.

### 6.2 The Gold Standard

```bash
git clone https://github.com/100x-engineer/ticketpulse.git
cd ticketpulse && make setup
```

Create a Makefile that automates everything:

```makefile
# Makefile

.PHONY: setup dev test clean

# One-command setup for new developers
setup:
	@echo "Setting up TicketPulse development environment..."
	@command -v mise >/dev/null 2>&1 || { echo "Please install mise: https://mise.jdx.dev"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "Please install Docker: https://docker.com"; exit 1; }
	@mise install
	@test -f .env || cp .env.example .env
	@echo ">>> Edit .env with your local values if needed"
	@npm ci
	@docker compose up -d postgres redis
	@echo "Waiting for Postgres to be ready..."
	@sleep 3
	@npm run db:migrate
	@npm run db:seed
	@echo ""
	@echo "============================================"
	@echo "  TicketPulse is ready!"
	@echo "  Run 'make dev' to start the server"
	@echo "============================================"

# Start development server
dev:
	docker compose up -d postgres redis
	npm run dev

# Run all tests
test:
	npm run test:unit
	DATABASE_URL=postgresql://ticketpulse:ticketpulse@localhost:5432/ticketpulse_test npm run test:integration

# Clean everything
clean:
	docker compose down -v
	rm -rf node_modules
	rm -rf coverage
```

### 6.3 Document It in the README

```markdown
## Quick Start

Prerequisites: [mise](https://mise.jdx.dev) and [Docker](https://docker.com)

\`\`\`bash
git clone https://github.com/100x-engineer/ticketpulse.git
cd ticketpulse
make setup   # Installs Node, dependencies, starts DB, runs migrations
make dev     # Starts the development server
\`\`\`
```

Two commands. Done. A new developer is shipping on day one instead of debugging their environment for three days.

### 📐 Exercise: Onboarding Time Trial

<details>
<summary>💡 Hint 1: Time the full clone-to-running sequence</summary>
Start a stopwatch from `git clone` and stop when `curl http://localhost:3000/api/health` returns `{"status":"ok"}`. Note every point where you had to stop and think or manually edit something — each pause is a gap in the Makefile automation.
</details>

<details>
<summary>💡 Hint 2: The Makefile should check prerequisites</summary>
Before running `npm ci`, the setup target should verify that `mise` and `docker` are installed. Use `@command -v mise >/dev/null 2>&1 || { echo "Please install mise"; exit 1; }`. Also check that `.env` exists; if not, copy from `.env.example`. Each missing prerequisite should produce a clear, actionable error.
</details>

<details>
<summary>💡 Hint 3: Target time is under 5 minutes, zero manual steps</summary>
The ideal flow: `git clone && cd ticketpulse && make setup` completes with no human intervention. `mise install` handles the Node version from `.nvmrc`. `npm ci` installs from the lockfile. `docker compose up -d` starts Postgres and Redis. `npm run db:migrate && npm run db:seed` initializes the database. If any step requires manual editing (other than `.env` secrets), automate it.
</details>


If you have access to a clean machine (or a colleague who just joined):

1. Clone the repo fresh (no existing node_modules or .env)
2. Run `make setup`
3. Time how long it takes to get to a running server
4. Note every manual step that was still required (every "I had to edit X" or "I had to install Y first")

**Target:** Under 15 minutes, zero manual steps (except editing .env for secrets). If it takes longer or requires manual steps, add those steps to the Makefile.

---

## 7. Dependency Security: Audit and Update

Your dependencies have dependencies, and those have dependencies. Any of them could have a security vulnerability.

```bash
# Check for known vulnerabilities
npm audit

# See the full audit report with fix suggestions
npm audit --json | jq '.vulnerabilities | to_entries[] | {
  name: .key,
  severity: .value.severity,
  via: .value.via,
  fixAvailable: .value.fixAvailable
}'

# See what is outdated
npm outdated

# Update to latest patch/minor versions (within semver range)
npm update

# Check for updates beyond your semver range
npx npm-check-updates
```

### 7.1 Triage Your Audit Results

Not all vulnerabilities are equal. When you run `npm audit`, triage the results:

```
npm audit triage framework:
──────────────────────────

CRITICAL / HIGH:
  Is the vulnerable code path reachable in production?
  Can an attacker actually exploit it given your architecture?
  - Yes → Fix immediately, treat as P0
  - No → Fix in the next sprint, document the reasoning

MODERATE:
  Is there a fix available?
  - Yes → Schedule for next dependency update cycle
  - No → Accept, document, monitor for fix

LOW:
  Accept and move on. Low vulnerabilities in dev dependencies
  especially. Not worth blocking releases for low-risk issues.
```

```bash
# Practical triage: identify fixable critical/high issues
npm audit --json | jq '[
  .vulnerabilities | to_entries[] |
  select(.value.severity == "critical" or .value.severity == "high") |
  select(.value.fixAvailable != false) |
  {
    name: .key,
    severity: .value.severity,
    fix: .value.fixAvailable
  }
]'
```

### 7.2 Automate It with Dependabot

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    reviewers:
      - "your-github-username"
    labels:
      - "dependencies"
    # Group minor and patch updates together to reduce PR noise
    groups:
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"
```

Dependabot automatically creates pull requests when dependency updates are available. Your CI pipeline tests the update. If tests pass, merge it. If they fail, the update broke something — investigate before merging.

### 7.3 The Lockfile Analysis Exercise: Find the Left-Pads in Your Tree

Run this analysis against TicketPulse's dependencies to understand your exposure:

```bash
# Find packages that are extremely small (< 5 files)
# and widely depended upon (the left-pad pattern)
npm ls --all --json 2>/dev/null | jq -r '
  .dependencies |
  to_entries[] |
  select(.value.dependencies | length < 3) |
  "\(.key)@\(.value.version)"
' | sort | uniq | head -20
```

For each result, ask:
- What does this package do?
- How many packages in my tree depend on it?
- Would my build break if it disappeared?
- Is there a way to eliminate this dependency or inline the logic?

The goal is not to eliminate all small packages — it is to be conscious of your dependency tree's fragility. The packages you cannot name are the ones that surprise you in production.

---

## 8. Reproducibility Checklist

Your project is reproducible if a new developer can answer "yes" to all of these:

- [ ] Can I clone the repo and be productive in under 15 minutes?
- [ ] Is the Node.js version pinned (`.nvmrc` or `.tool-versions`)?
- [ ] Does `npm ci` install the exact same dependencies everywhere?
- [ ] Are environment variables documented in `.env.example`?
- [ ] Does the app validate environment variables at startup?
- [ ] Does `docker compose up` start all infrastructure dependencies?
- [ ] Is there a single command to run the full test suite?
- [ ] Do the CI and local environments use the same Node version?
- [ ] Is the lockfile committed and up to date?
- [ ] Does `npm audit` report zero critical/high vulnerabilities?

If any answer is "no," you have an environment problem waiting to become a production incident.

---

## 9. Checkpoint

Before continuing to the next module, verify:

- [ ] `.nvmrc` exists and contains the pinned Node version
- [ ] `.tool-versions` exists for mise/asdf compatibility
- [ ] `mise install` in the project directory installs the correct Node version
- [ ] `npm ci` installs dependencies from the lockfile without modifying it
- [ ] `.envrc` auto-loads the environment when you `cd` into the project
- [ ] `make setup` takes a new developer from clone to running in one command
- [ ] The CI pipeline reads the Node version from `.nvmrc`
- [ ] You have run `npm audit` and triaged the results
- [ ] You have analyzed the lockfile for integrity fields and non-standard registries

```bash
# Verify the full experience
cd ~
cd ~/ticketpulse
# direnv: loading .envrc
# TicketPulse dev environment loaded: Node v20.11.0
node --version     # v20.11.0
echo $PORT         # 3000
which jest         # ./node_modules/.bin/jest
```

> **Reflect:** "Works on my machine" is not a defense. It is a confession. If your environment is not reproducible, every deployment is a gamble. The ten minutes you spend pinning versions and writing a Makefile saves hours of "but it works for me" debugging every month. And the lockfile you committed this week is the integrity check that protects you from the supply chain attack next month.

---

## What's Next

TicketPulse is written in TypeScript. But what if it was not? The next module shows the same API endpoint implemented in Go, Python, Rust, and TypeScript — side by side. You will run each, read each, and benchmark each.

## Key Terms

| Term | Definition |
|------|-----------|
| **Version manager** | A tool (such as nvm or asdf) that installs and switches between multiple versions of a language runtime. |
| **Lockfile** | A file that records the exact resolved versions of every dependency, ensuring reproducible installs. |
| **Reproducible build** | A build process that produces identical outputs given the same source code, dependencies, and environment. |
| **direnv** | A shell extension that automatically loads and unloads environment variables when you enter or leave a directory. |
| **.tool-versions** | A configuration file used by asdf to declare which runtime versions a project requires. |
| **Supply chain attack** | A cyberattack that targets the software supply chain — injecting malicious code into a dependency that is then installed by thousands of projects. |
| **Integrity hash** | A cryptographic hash (SHA-512) of a package's contents, stored in the lockfile to detect tampering. |
| **Transitive dependency** | A dependency of a dependency. If you depend on package A and A depends on B, then B is a transitive dependency. |
| **npm ci** | The npm command that installs packages strictly from the lockfile, never modifying it. Suitable for CI and production. |
| **Dependabot** | A GitHub tool that automatically creates pull requests when dependency updates are available. |

## Further Reading

- **"The left-pad incident"**: npm blog post-mortem from March 2016
- **Chapter 20 of the 100x Engineer Guide**: Dependency management — resolution algorithms, lockfiles, and supply chain security
- **"A post-mortem on the npm left-pad situation"** (David Haney, 2016) — a developer perspective on why this happened
- **ua-parser-js npm attack (2021)**: Bleeping Computer coverage — a real supply chain attack and how lockfiles protect against it
- **SLSA Framework (Supply-chain Levels for Software Artifacts)**: Google's framework for supply chain security — slsa.dev
- **mise documentation**: mise.jdx.dev — the modern replacement for nvm, pyenv, and friends

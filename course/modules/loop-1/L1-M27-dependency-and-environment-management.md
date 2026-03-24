# L1-M27: Dependency & Environment Management

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L1-M24 (Secrets Management)
>
> **What you'll build:** A fully reproducible development environment for TicketPulse -- pinned Node.js version via `.nvmrc`, automatic version switching with mise, lockfile discipline with `npm ci`, direnv for auto-activation, and a two-command onboarding workflow for new developers.

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

By the end of this module, every developer and every CI runner will use exactly the same Node version, install exactly the same dependencies, and load exactly the same environment variables -- automatically, with zero manual steps.

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

## 1. Build: Pin the Node Version

### 1.1 Create .nvmrc

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

### 1.2 Add .tool-versions (for mise/asdf compatibility)

`.nvmrc` works with nvm. `.tool-versions` works with mise (formerly rtx) and asdf, which can manage Node, Python, Go, Rust, and 400+ other tools from a single file.

```bash
# .tool-versions -- in the project root
cat > .tool-versions << 'EOF'
nodejs 20.11.0
EOF
```

### 1.3 Update the CI Pipeline

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

## 2. Try It: Install mise

mise (pronounced "meez") is the recommended tool for managing runtime versions. It replaces nvm, pyenv, rbenv, and dozens of other version managers with one tool.

### 2.1 Install mise

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

### 2.2 Install the Pinned Node Version

```bash
cd ticketpulse

# mise reads .tool-versions (or .nvmrc) automatically
mise install

# Verify
node --version
# v20.11.0
```

### 2.3 See It Switch Automatically

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

## 3. Lockfiles: npm ci vs npm install

### 3.1 The Problem

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

### 3.2 npm ci: The Reproducible Install

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

### 3.3 Try It: See the Difference

```bash
# 1. Clean install with npm ci
rm -rf node_modules
npm ci
ls node_modules/express/package.json | head -5
# Note the exact version

# 2. Now simulate a drift scenario
# Edit package-lock.json to change express's resolved version (for demonstration)
# Then:
npm ci
# npm ci will use the lockfile version, NOT resolve a new one
```

### 3.4 Update the CI Pipeline

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

### 3.5 The Rule

- **Locally:** Use `npm install` when adding or updating packages. Commit the updated `package-lock.json`.
- **CI and production:** Always use `npm ci`. If the lockfile is out of date, the build fails -- which is what you want. It forces developers to commit their lockfile changes.

---

## 4. Build: direnv for Auto-Activation

In M24, you set up a `.env` file and learned about direnv for loading environment variables. Now we combine it with mise for the complete auto-activation experience.

### 4.1 Create .envrc

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

### 4.2 Try It: The Full Experience

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

## 5. The Two-Command Onboarding

> **Reflect:** "A new developer joins the team. How many commands should they need to run to get TicketPulse working? Can we get it to two?"

### 5.1 The Current State (Too Many Steps)

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

### 5.2 The Gold Standard

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

### 5.3 Document It in the README

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

---

## 6. Dependency Security: Audit and Update

Your dependencies have dependencies, and those have dependencies. Any of them could have a security vulnerability.

```bash
# Check for known vulnerabilities
npm audit

# See what is outdated
npm outdated

# Update to latest patch/minor versions (within semver range)
npm update

# Check for updates beyond your semver range
npx npm-check-updates
```

### 6.1 Automate It with Dependabot

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
```

Dependabot automatically creates pull requests when dependency updates are available. Your CI pipeline tests the update. If tests pass, merge it. If they fail, the update broke something -- investigate before merging.

---

## 7. Reproducibility Checklist

Your project is reproducible if a new developer can answer "yes" to all of these:

- [ ] Can I clone the repo and be productive in under 15 minutes?
- [ ] Is the Node.js version pinned (`.nvmrc` or `.tool-versions`)?
- [ ] Does `npm ci` install the exact same dependencies everywhere?
- [ ] Are environment variables documented in `.env.example`?
- [ ] Does the app validate environment variables at startup?
- [ ] Does `docker compose up` start all infrastructure dependencies?
- [ ] Is there a single command to run the full test suite?
- [ ] Do the CI and local environments use the same Node version?

If any answer is "no," you have an environment problem waiting to become a production incident.

---

## 8. Checkpoint

Before continuing to the next module, verify:

- [ ] `.nvmrc` exists and contains the pinned Node version
- [ ] `.tool-versions` exists for mise/asdf compatibility
- [ ] `mise install` in the project directory installs the correct Node version
- [ ] `npm ci` installs dependencies from the lockfile without modifying it
- [ ] `.envrc` auto-loads the environment when you `cd` into the project
- [ ] `make setup` takes a new developer from clone to running in one command
- [ ] The CI pipeline reads the Node version from `.nvmrc`

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

> **Reflect:** "Works on my machine" is not a defense. It is a confession. If your environment is not reproducible, every deployment is a gamble. The ten minutes you spend pinning versions and writing a Makefile saves hours of "but it works for me" debugging every month.

---

## What's Next

TicketPulse is written in TypeScript. But what if it was not? The next module shows the same API endpoint implemented in Go, Python, Rust, and TypeScript -- side by side. You will run each, read each, and benchmark each.

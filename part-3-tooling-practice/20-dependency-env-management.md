<!--
  CHAPTER: 20
  TITLE: Dependency & Environment Management
  PART: III — Tooling & Practice
  PREREQS: Chapter 12 (basic tooling)
  KEY_TOPICS: Nix, NixOS, asdf, mise, nvm, pyenv, rustup, lockfiles, Python packaging (uv, Poetry), Docker dev environments, devcontainers, .env management, monorepo dependencies, reproducible builds
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 20: Dependency & Environment Management

> **Part III — Tooling & Practice** | Prerequisites: Chapter 12 (basic tooling) | Difficulty: Intermediate

Reproducibility as a superpower — from Nix flakes to version managers to lockfile discipline, ensuring "works on my machine" is never a problem and every build is deterministic.

### In This Chapter
- The Problem
- Nix & NixOS
- Version Managers
- Lockfiles & Deterministic Installs
- Python Environment Management
- Docker for Dev Environments
- Environment Variables & Secrets
- Monorepo Dependency Strategies
- Reproducible Builds
- Recommended Stack by Project Type

### Related Chapters
- Chapter 12 (Docker/tooling hands-on)
- Chapter 11 (language-specific package managers)
- Chapter 15 (monorepo dependency strategies)

---

## 1. THE PROBLEM

### 1.1 "Works on My Machine"

The phrase hides a combinatorial explosion of differences between environments:

- **OS differences**: macOS uses BSD utilities, Linux uses GNU. `sed -i` behaves differently. `readlink` flags differ. libc implementations vary (glibc vs musl).
- **Version differences**: Node 18 vs 20, Python 3.10 vs 3.12, OpenSSL 1.1 vs 3.0. Even patch versions can change behavior.
- **System dependencies**: One developer has libpq installed via Homebrew, another compiled from source, a third doesn't have it at all.
- **Environment variables**: Missing `DATABASE_URL`, different `NODE_ENV`, stale AWS credentials.
- **Implicit state**: Global npm packages, Python packages installed with `pip install --user`, stale caches, leftover Docker volumes.

### 1.2 Dependency Hell

```
Your app
├── library-A@2.0 (requires shared-lib@^3.0)
├── library-B@1.5 (requires shared-lib@^2.0)
└── 💥 shared-lib: needs to be both 3.x AND 2.x
```

- **Diamond dependencies**: Two libraries depend on incompatible versions of the same transitive dependency.
- **Phantom dependencies**: Your code imports a package that isn't in your package.json but happens to be installed because another dependency brought it along. Works locally, breaks in CI.
- **Transitive dependency drift**: You didn't change anything, but a transitive dependency published a broken patch release and your next `npm install` pulls it in.

### 1.3 Environment Drift

| | Dev | Staging | Production |
|---|---|---|---|
| Node version | 20.11.0 | 20.9.0 | 20.10.0 |
| PostgreSQL | 16.1 (Homebrew) | 15.4 (Docker) | 16.2 (RDS) |
| OS | macOS 14 | Ubuntu 22.04 | Amazon Linux 2023 |
| ENV vars | .env.local | Terraform | AWS Secrets Manager |

Every difference is a potential production incident waiting to happen.

### 1.4 The Cost of Non-Reproducibility

- **Debugging time**: "It works locally" adds hours to every bug investigation. You're debugging the environment, not the code.
- **Onboarding time**: New engineers spend 1-3 days setting up their dev environment instead of shipping on day one.
- **Production incidents**: A dependency that worked in dev but not in prod causes downtime. Post-mortems reveal "we didn't test with the same Node version."
- **CI flakes**: Tests pass locally but fail in CI because of subtle environment differences, eroding trust in the test suite.

---

## 2. NIX & NIXOS

### 2.1 What Nix Is

Nix is a **purely functional package manager**. Every package is built in isolation, identified by a cryptographic hash of all its inputs (source code, dependencies, build scripts, compiler flags). This means:

- **Immutable**: Once built, a package never changes. `/nix/store/abc123-nodejs-20.11.0/` is always exactly the same binary everywhere.
- **Content-addressed**: The path includes a hash of everything that went into building it. Different inputs produce different paths.
- **No global state**: No `/usr/local/lib` pollution. Multiple versions coexist without conflict.
- **Reproducible**: Same inputs always produce the same output, across machines, across time.

### 2.2 Key Concepts

```
Derivation          A build recipe: sources + dependencies + build script → output
Nix Store           /nix/store/ — immutable, content-addressed storage for all packages
nix-shell           Legacy command to enter a temporary shell with specific packages
nix develop         Modern (flakes) equivalent of nix-shell
Flakes              The modern Nix interface: reproducible, composable, with a lockfile
nixpkgs             The package repository — 100,000+ packages, one of the largest in existence
```

### 2.3 nix-shell for Per-Project Environments (Legacy)

```nix
# shell.nix — drop this in your project root
{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    nodejs_20
    nodePackages.pnpm
    postgresql_16
    redis
    jq
    awscli2
  ];

  shellHook = ''
    echo "Dev environment loaded: Node $(node -v), pnpm $(pnpm -v)"
    export DATABASE_URL="postgresql://localhost:5432/myapp_dev"
  '';
}
```

```bash
# Enter the environment
nix-shell              # Drops you into a shell with all packages available

# Run a single command without entering the shell
nix-shell --run "node --version"
```

### 2.4 Nix Flakes (The Modern Approach)

Flakes add reproducibility guarantees that legacy Nix lacks: a lockfile (`flake.lock`), a standard schema, and no reliance on mutable channels.

```nix
# flake.nix
{
  description = "My project dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_20
            nodePackages.pnpm
            python312
            uv
            postgresql_16
            redis
            docker-compose
            awscli2
            terraform
          ];

          shellHook = ''
            echo "🔧 Dev shell activated"
            export PRISMA_QUERY_ENGINE_LIBRARY="${pkgs.prisma-engines}/lib/libquery_engine.node"
          '';
        };
      }
    );
}
```

```bash
# Enter the dev shell
nix develop            # Uses flake.nix in current directory

# Update all inputs (like npm update, but for your entire toolchain)
nix flake update

# Update a single input
nix flake lock --update-input nixpkgs

# Pin to a specific nixpkgs commit for absolute reproducibility
# flake.lock does this automatically
```

### 2.5 direnv + Nix: Automatic Environment Activation

The killer combo. When you `cd` into a project directory, your shell automatically gets the right versions of everything.

```bash
# Install direnv
nix profile install nixpkgs#direnv
# Or: brew install direnv

# Add to your .zshrc / .bashrc
eval "$(direnv hook zsh)"    # or bash
```

```bash
# .envrc (in project root)
use flake                    # Automatically runs `nix develop` when you enter the directory

# Or for legacy nix-shell:
use nix
```

```bash
# Allow direnv for this directory (one-time)
direnv allow

# Now just cd into the project:
cd ~/projects/myapp
# direnv: loading .envrc
# direnv: using flake
# Dev shell activated
node --version   # v20.11.0 — guaranteed
```

### 2.6 Nix for CI

The same `flake.nix` that defines your local dev environment can define your CI environment:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - uses: DeterminateSystems/magic-nix-cache-action@main   # Caches /nix/store
      - run: nix develop --command bash -c "pnpm install && pnpm test"
```

Same Node version, same system libraries, same tools. Locally and in CI. Always.

### 2.7 NixOS

NixOS extends the Nix philosophy to the entire operating system. Your OS configuration is a single file:

```nix
# /etc/nixos/configuration.nix (simplified)
{
  services.postgresql.enable = true;
  services.postgresql.package = pkgs.postgresql_16;
  services.redis.servers."default".enable = true;

  environment.systemPackages = with pkgs; [ vim git curl ];

  # Atomic upgrades, instant rollbacks
  system.stateVersion = "24.05";
}
```

- **Atomic upgrades**: The entire system switches to a new configuration atomically. If something breaks, reboot and select the previous generation from the bootloader.
- **Declarative**: The configuration file IS the system. No imperative state drift.
- **Best for**: Servers, CI runners, developers who want full control.

### 2.8 When to Use Nix

**Use Nix when:**
- Your project has system-level dependencies (PostgreSQL, Redis, FFmpeg, ImageMagick, native libraries)
- You work across multiple languages (Node + Python + Go in the same project)
- You need CI/local parity guaranteed
- You're tired of "install Homebrew, then install X, then install Y, hope the versions work"

**Don't use Nix when:**
- Your project is a single-language app with no system dependencies (use mise or the language's version manager)
- Your team is small and Docker Compose handles everything
- Nobody on the team has Nix experience and you're shipping against a deadline

### 2.9 Trade-offs

| Advantage | Disadvantage |
|---|---|
| True reproducibility | Steep learning curve |
| Cross-platform (macOS + Linux) | Nix language is unusual (not quite functional, not quite JSON) |
| Enormous package repository (100k+) | Large disk usage (/nix/store grows) |
| Atomic upgrades and rollbacks | First build is slow (subsequent builds are cached) |
| One config for local + CI | macOS support is good but Linux-first |
| Community growing rapidly | Documentation has historically been rough (improving fast) |

### 2.10 Real-World Adoption

- **Shopify**: Uses Nix for dev environments across thousands of developers
- **Replit**: Entire platform built on Nix for package management
- **Cachix**: Binary cache service, makes Nix builds fast by sharing pre-built packages
- **Determinate Systems**: Building commercial tooling around Nix (FlakeHub, the Determinate Nix Installer)
- **European Space Agency**: Uses NixOS for mission-critical systems
- **Target, Hercules CI, Tweag**: Production Nix users

---

## 3. VERSION MANAGERS

### 3.1 Language-Specific Version Managers

#### nvm (Node.js)

```bash
# Install
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Usage
nvm install 20              # Install Node 20 (latest LTS minor)
nvm install 20.11.0         # Install specific version
nvm use 20                  # Switch to Node 20
nvm alias default 20        # Set default version for new shells

# Auto-switching: create .nvmrc in project root
echo "20.11.0" > .nvmrc
nvm use                     # Reads .nvmrc

# Auto-switching on cd (add to .zshrc):
autoload -U add-zsh-hook
load-nvmrc() {
  local nvmrc_path="$(nvm_find_nvmrc)"
  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")
    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$(nvm version)" ]; then
      nvm use
    fi
  fi
}
add-zsh-hook chpwd load-nvmrc
load-nvmrc
```

#### pyenv (Python)

```bash
# Install
brew install pyenv   # macOS
# Or: curl https://pyenv.run | bash

# Usage
pyenv install 3.12.2        # Install a Python version
pyenv global 3.12.2         # Set global default
pyenv local 3.12.2          # Set for current directory (creates .python-version file)
pyenv shell 3.12.2          # Set for current shell session

# Integration with virtualenv
pyenv virtualenv 3.12.2 myproject    # Create a named virtualenv
pyenv activate myproject             # Activate it
pyenv local myproject                # Auto-activate when entering directory

# .python-version file is respected by pyenv, mise, and many CI systems
cat .python-version
# 3.12.2
```

#### rbenv (Ruby)

```bash
# Same pattern as pyenv
rbenv install 3.3.0
rbenv local 3.3.0           # Creates .ruby-version
rbenv global 3.3.0
```

#### rustup (Rust)

```bash
# Install (the standard way to install Rust)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Toolchain management
rustup default stable                # Use stable channel
rustup default nightly               # Use nightly
rustup override set nightly          # Override for current directory
rustup update                        # Update all installed toolchains

# Components
rustup component add clippy          # Linter
rustup component add rustfmt         # Formatter
rustup component add rust-analyzer   # LSP server

# Cross-compilation targets
rustup target add wasm32-unknown-unknown      # WebAssembly
rustup target add aarch64-unknown-linux-gnu   # ARM Linux
rustup target add x86_64-unknown-linux-musl   # Static Linux binary

# rust-toolchain.toml (per-project, checked into git)
# Automatically used by rustup when you enter the directory
cat > rust-toolchain.toml << 'EOF'
[toolchain]
channel = "1.77.0"
components = ["rustfmt", "clippy", "rust-analyzer"]
targets = ["wasm32-unknown-unknown"]
EOF
```

#### sdkman (JVM Languages)

```bash
# Install
curl -s "https://get.sdkman.io" | bash

# Usage
sdk install java 21.0.2-tem     # Install Temurin JDK 21
sdk install kotlin 2.0.0
sdk install gradle 8.6
sdk install maven 3.9.6

sdk use java 21.0.2-tem         # Switch for current shell
sdk default java 21.0.2-tem     # Set default

# .sdkmanrc (per-project)
cat > .sdkmanrc << 'EOF'
java=21.0.2-tem
gradle=8.6
EOF
sdk env                          # Apply .sdkmanrc
```

#### Go Toolchain Management

```bash
# Go manages its own toolchain since Go 1.21+
# go.mod specifies the required version:
# go 1.22.0
# toolchain go1.22.2

# Go automatically downloads the required toolchain version
go mod tidy   # Downloads the right Go version if needed

# Or install specific versions manually:
go install golang.org/dl/go1.22.2@latest
go1.22.2 download
```

### 3.2 Universal Version Managers

#### asdf (Multi-Language)

```bash
# Install
brew install asdf    # macOS
# Or: git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.14.0

# Add plugins (one per language/tool)
asdf plugin add nodejs
asdf plugin add python
asdf plugin add ruby
asdf plugin add golang
asdf plugin add terraform
asdf plugin add kubectl

# Install versions
asdf install nodejs 20.11.0
asdf install python 3.12.2

# Set versions (per-project)
asdf local nodejs 20.11.0
asdf local python 3.12.2
# Creates .tool-versions file:
# nodejs 20.11.0
# python 3.12.2

# Set global defaults
asdf global nodejs 20.11.0
```

```bash
# .tool-versions — the universal config file
nodejs 20.11.0
python 3.12.2
ruby 3.3.0
golang 1.22.2
terraform 1.7.4
kubectl 1.29.2
```

How asdf works under the hood: It uses **shims**. When you install a tool, asdf creates a shim script in `~/.asdf/shims/` that intercepts the command, reads `.tool-versions`, and dispatches to the correct version.

#### mise (Formerly rtx) - The Modern Choice

mise is a Rust-based alternative to asdf that's faster, has better UX, and adds task running and environment variable management.

```bash
# Install
brew install mise    # macOS
# Or: curl https://mise.run | sh

# It's compatible with .tool-versions AND has its own .mise.toml
# Reads: .tool-versions, .nvmrc, .python-version, .ruby-version, .node-version

# Install and use tools
mise use node@20.11.0        # Install + set in .mise.toml
mise use python@3.12.2
mise use go@1.22.2

# Activate in your shell (.zshrc)
eval "$(mise activate zsh)"
```

```toml
# .mise.toml — the modern config file
[tools]
node = "20.11.0"
python = "3.12.2"
go = "1.22.2"
terraform = "1.7.4"
kubectl = "1.29.2"
"npm:turbo" = "2.0.0"       # Install npm packages as tools
"cargo:cargo-watch" = "8.5"  # Install Rust crates as tools

[env]
DATABASE_URL = "postgresql://localhost:5432/myapp_dev"
NODE_ENV = "development"

# Load .env files
[env]
_.file = ".env.local"

[tasks.dev]
description = "Start dev server"
run = "pnpm dev"

[tasks.test]
description = "Run tests"
run = "pnpm test"

[tasks.db-reset]
description = "Reset database"
run = """
dropdb myapp_dev --if-exists
createdb myapp_dev
pnpm prisma migrate dev
"""

[tasks.lint]
description = "Lint and typecheck"
depends = ["lint:eslint", "lint:tsc"]

[tasks."lint:eslint"]
run = "pnpm eslint ."

[tasks."lint:tsc"]
run = "pnpm tsc --noEmit"
```

```bash
# Run tasks
mise run dev
mise run test
mise run db-reset

# Or use the shorthand:
mise r dev
```

#### mise vs asdf

| Feature | mise | asdf |
|---|---|---|
| Speed | Fast (Rust) | Slower (shell scripts + shims) |
| Config format | .mise.toml (rich) + .tool-versions compat | .tool-versions only |
| Env vars | Built-in (.mise.toml [env] section) | Requires plugin or external tool |
| Task runner | Built-in | Not available |
| Shims | Optional (uses PATH manipulation by default) | Always uses shims |
| Plugin compat | Uses asdf plugins (plus its own backends) | asdf plugins |
| Community | Growing fast, active development | Established, large ecosystem |
| Maturity | Newer (2023+) | Established (2017+) |

### 3.3 Which to Choose

```
Single language project?
├── Node.js → nvm (or fnm for speed)
├── Python → pyenv
├── Rust → rustup (no alternative needed)
├── Go → Go's built-in toolchain management
└── JVM → sdkman

Multi-language project?
├── Want modern + fast + tasks + env vars → mise
└── Want established + maximum plugin ecosystem → asdf

Need system packages too (PostgreSQL, Redis, FFmpeg)?
└── Nix flakes + direnv
```

---

## 4. LOCKFILES & DETERMINISTIC INSTALLS

### 4.1 Why Lockfiles Exist

Your `package.json` says `"lodash": "^4.17.0"`. That matches 4.17.0, 4.17.1, ... 4.17.21. Without a lockfile, two developers running `npm install` a week apart could get different versions of every transitive dependency. A lockfile pins the **exact** resolved version of every package in your dependency tree.

### 4.2 Language-Specific Lockfiles

| Language | Manifest | Lockfile | Notes |
|---|---|---|---|
| Node.js (npm) | package.json | package-lock.json | Also stores integrity hashes |
| Node.js (pnpm) | package.json | pnpm-lock.yaml | Content-addressable store |
| Node.js (yarn) | package.json | yarn.lock | Yarn Berry uses a different format than Yarn Classic |
| Python (Poetry) | pyproject.toml | poetry.lock | Full dependency tree with hashes |
| Python (uv) | pyproject.toml | uv.lock | Cross-platform resolution |
| Python (pip-tools) | requirements.in | requirements.txt | Generated by `pip-compile` |
| Go | go.mod | go.sum | Checksums of module content |
| Rust | Cargo.toml | Cargo.lock | Commit for binaries, optional for libraries |
| Java (Gradle) | build.gradle | gradle.lockfile | Opt-in with `--write-locks` |
| Ruby | Gemfile | Gemfile.lock | Bundler standard |

### 4.3 ALWAYS Commit Lockfiles. Period.

```gitignore
# .gitignore — do NOT add lockfiles here

# These should be committed:
# package-lock.json   ← COMMIT
# pnpm-lock.yaml      ← COMMIT
# yarn.lock           ← COMMIT
# poetry.lock         ← COMMIT
# uv.lock             ← COMMIT
# go.sum              ← COMMIT
# Cargo.lock          ← COMMIT (for applications; optional for libraries)
# Gemfile.lock        ← COMMIT
```

If someone on your team has lockfiles in `.gitignore`, that is a bug. Fix it today.

### 4.4 `npm ci` vs `npm install`

```bash
# npm install (development)
# - Reads package.json
# - May update package-lock.json
# - Installs to existing node_modules (incremental)
# - Use during development when adding/updating packages
npm install

# npm ci (CI/production)
# - Reads package-lock.json EXACTLY
# - Deletes node_modules first (clean install)
# - Fails if package-lock.json is out of sync with package.json
# - Deterministic — same lockfile always produces same node_modules
# - Use in CI, Docker builds, production deploys
npm ci
```

### 4.5 Reproducible Install Commands by Package Manager

```bash
# Node.js
npm ci                                    # Exact lockfile install
pnpm install --frozen-lockfile           # Fail if lockfile would change
yarn install --immutable                  # Yarn Berry: fail if lockfile would change

# Python
uv sync                                   # Install from uv.lock exactly
poetry install --no-update               # Don't update poetry.lock
pip install -r requirements.txt --no-deps # Exact versions, no transitive resolution

# Go
go mod download                           # Download exact versions from go.sum
go mod verify                             # Verify checksums match

# Rust
cargo install --locked                    # Use Cargo.lock exactly

# Ruby
bundle install --frozen                   # Fail if Gemfile.lock would change
```

### 4.6 Dependency Resolution

Modern package managers use SAT solvers or purpose-built resolution algorithms:

- **npm**: Uses a tree-based resolution algorithm. Can produce deeply nested `node_modules` trees (deduplication improved in v7+).
- **pnpm**: Content-addressable store + symlinks. Each package is stored once on disk globally, linked into projects. Strict by default (no phantom dependencies).
- **yarn Berry (PnP)**: Plug'n'Play mode eliminates `node_modules` entirely. A `.pnp.cjs` file maps imports to zip archives in `.yarn/cache/`.
- **uv**: Written in Rust, uses a PubGrub-based resolver. Resolves Python dependencies 10-100x faster than pip.
- **Cargo**: Also uses a PubGrub variant. Known for high-quality dependency resolution.

---

## 5. PYTHON ENVIRONMENT MANAGEMENT

Python gets its own section because its packaging ecosystem is uniquely fragmented. The joke "there are 14 competing standards" applies literally here.

### 5.1 The Problem

```
Python packaging timeline:
2004: easy_install + eggs
2008: pip
2011: virtualenv becomes standard practice
2014: pip gets wheel support
2016: Pipenv (briefly "officially recommended," then abandoned)
2018: Poetry appears
2019: PEP 517/518 (build system abstraction)
2020: PEP 621 (pyproject.toml metadata standard)
2022: PDM, Hatch mature
2023: Rye appears
2024: uv appears and changes everything
```

The result: Five different tools that all manage virtual environments, three different lockfile formats, two different project metadata standards, and every tutorial you find uses a different one.

### 5.2 Virtual Environments (The Foundation)

```bash
# Built-in venv (Python 3.3+)
python -m venv .venv                # Create virtual environment
source .venv/bin/activate           # Activate (Unix)
.venv\Scripts\activate              # Activate (Windows)
deactivate                          # Deactivate

# Why virtual environments exist:
# Python has a single global site-packages directory.
# Without venvs, `pip install` contaminates your system Python.
# Project A needs Django 4.2, Project B needs Django 5.0 → conflict.
# venvs isolate each project's dependencies.
```

### 5.3 Modern Tooling Comparison

#### uv (The 2024-2026 Winner)

By Astral (the team behind Ruff). Written in Rust. 10-100x faster than pip.

```bash
# Install
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or: brew install uv

# Create a new project
uv init myproject
cd myproject

# Add dependencies
uv add fastapi uvicorn
uv add --dev pytest ruff mypy

# Install all dependencies (creates .venv automatically)
uv sync

# Run commands in the virtual environment (no manual activation needed)
uv run python main.py
uv run pytest
uv run ruff check .

# Pin Python version
uv python pin 3.12.2

# Lock dependencies
uv lock                 # Generates uv.lock

# Install in CI (exact lockfile)
uv sync --frozen
```

```toml
# pyproject.toml (uv project)
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn>=0.29.0",
    "sqlalchemy>=2.0",
    "pydantic>=2.7",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "ruff>=0.4.0",
    "mypy>=1.10",
    "pytest-asyncio>=0.23",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Why uv wins:
- **Speed**: `uv sync` is 10-100x faster than `pip install`. Not a typo.
- **All-in-one**: Replaces pip, pip-tools, virtualenv, pyenv (for Python version management), pipx.
- **Cross-platform lockfile**: `uv.lock` resolves for all platforms simultaneously.
- **Compatible**: Reads `requirements.txt`, `pyproject.toml`, `.python-version`.
- **No activation needed**: `uv run` executes in the right environment automatically.

#### Poetry (Established Alternative)

```bash
# Install
pipx install poetry

# Create project
poetry new myproject
cd myproject

# Add dependencies
poetry add fastapi uvicorn
poetry add --group dev pytest ruff

# Install
poetry install

# Run
poetry run python main.py
poetry run pytest

# Lock
poetry lock
```

Poetry is mature and well-documented but slower than uv and uses a non-standard lockfile format. It's still a fine choice for existing projects.

#### PDM

PEP 582 support (no virtualenv needed, uses `__pypackages__/`), modern resolver, PEP 621 compliant. Good tool, less adoption than Poetry or uv.

#### Hatch

PEP 621 compliant, built-in environment matrix (test across Python 3.10, 3.11, 3.12 easily), good for library authors. Used by many PyPA projects.

#### Rye

By Armin Ronacher (Flask creator). Wraps uv internally. Conceptually similar to uv's project management but predates it. Astral has stated uv is the successor.

### 5.4 Recommendation

**For new projects in 2025-2026: Use uv.** It's the fastest, most complete, and most actively developed tool. The entire Python packaging ecosystem is consolidating around it.

For existing projects: Migrate to uv when convenient. It reads `requirements.txt` and `pyproject.toml` natively, so migration is straightforward.

```bash
# Migrate from requirements.txt to uv
uv init
uv add $(cat requirements.txt | grep -v '^#' | grep -v '^$' | tr '\n' ' ')
uv lock
# Delete requirements.txt, use pyproject.toml + uv.lock going forward
```

---

## 6. DOCKER FOR DEV ENVIRONMENTS

### 6.1 Docker Compose for Services

Don't Dockerize your application code for development. DO Dockerize the services it depends on.

```yaml
# docker-compose.yml (or compose.yml — both work)
services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: myapp_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # Web UI

  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"   # All AWS services on one port
    environment:
      SERVICES: s3,sqs,sns,dynamodb,ses
      DEFAULT_REGION: us-east-1
    volumes:
      - localstackdata:/var/lib/localstack

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"   # S3-compatible API
      - "9001:9001"   # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  redisdata:
  localstackdata:
  miniodata:
```

```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d postgres redis

# View logs
docker compose logs -f postgres

# Reset everything
docker compose down -v    # -v removes volumes (data)
```

### 6.2 Dev Containers

Dev containers standardize the entire development environment inside a container. VS Code, GitHub Codespaces, and JetBrains Gateway all support them.

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "My Project",
  "image": "mcr.microsoft.com/devcontainers/typescript-node:20",

  // Or build from a Dockerfile:
  // "build": { "dockerfile": "Dockerfile" },

  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/github-cli:1": {},
    "ghcr.io/devcontainers/features/aws-cli:1": {},
    "ghcr.io/devcontainers-contrib/features/pnpm:2": {}
  },

  "forwardPorts": [3000, 5432, 6379],

  "postCreateCommand": "pnpm install",
  "postStartCommand": "docker compose up -d postgres redis",

  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "bradlc.vscode-tailwindcss",
        "prisma.prisma"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode"
      }
    }
  },

  "mounts": [
    "source=${localEnv:HOME}/.ssh,target=/home/node/.ssh,type=bind,readonly",
    "source=${localEnv:HOME}/.gitconfig,target=/home/node/.gitconfig,type=bind,readonly"
  ],

  "remoteUser": "node"
}
```

**When to use dev containers:**
- Onboarding (new engineer goes from clone to running in minutes)
- Cross-platform teams (Windows + macOS + Linux developers)
- Complex system dependencies (specific versions of native libraries)
- GitHub Codespaces (cloud-based development)

### 6.3 Trade-offs of Docker for Development

| Pro | Con |
|---|---|
| Consistent services (same PostgreSQL everywhere) | Overhead on macOS (Docker Desktop uses a VM) |
| Easy to spin up and tear down | Volume mount performance on macOS (especially node_modules) |
| Isolates services from your system | Adds complexity to debugging (container networking, logs) |
| Reproducible across the team | Docker Desktop license costs for large companies |

**macOS performance tip**: Use Docker volumes for data (databases), not bind mounts. If you must bind-mount code, use `:cached` or VirtioFS (Docker Desktop 4.15+).

---

## 7. ENVIRONMENT VARIABLES & SECRETS

### 7.1 .env Files and Dotenv

```bash
# .env.example — committed to git, documents required variables (no real values)
DATABASE_URL=postgresql://localhost:5432/myapp_dev
REDIS_URL=redis://localhost:6379
API_KEY=your-api-key-here
STRIPE_SECRET_KEY=sk_test_...
AWS_REGION=us-east-1
```

```bash
# .env.local — NOT committed, contains real values for local dev
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/myapp_dev
REDIS_URL=redis://localhost:6379
API_KEY=ak_dev_abc123
STRIPE_SECRET_KEY=sk_test_51ABC...
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### 7.2 Precedence Rules (Next.js Example)

```
Priority (highest to lowest):
1. Process environment (CLI: DATABASE_URL=x next dev)
2. .env.$(NODE_ENV).local    (.env.development.local)
3. .env.local                (NOT loaded in test environment)
4. .env.$(NODE_ENV)          (.env.development)
5. .env                      (base defaults)
```

Most frameworks follow a similar pattern. Vite, Remix, Rails, Laravel all have their own `.env` loading order.

### 7.3 .gitignore Rules

```gitignore
# .gitignore — ALWAYS include these
.env
.env.local
.env.*.local
.env.development.local
.env.test.local
.env.production.local

# DO commit these (they contain no secrets, just defaults/examples):
# .env.example
# .env.development
# .env.test
```

### 7.4 direnv for Per-Directory Env Vars

```bash
# Install
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# .envrc (in project root)
export DATABASE_URL="postgresql://localhost:5432/myapp_dev"
export REDIS_URL="redis://localhost:6379"
export AWS_PROFILE="myapp-dev"
export PATH="$PWD/node_modules/.bin:$PATH"

# Source a .env file
dotenv .env.local

# Combine with mise or Nix
use mise        # or: use flake
```

```bash
direnv allow    # Approve .envrc (required after any change)

# Now variables are automatically set when you cd into the directory
cd ~/projects/myapp
echo $DATABASE_URL   # postgresql://localhost:5432/myapp_dev

cd ~
echo $DATABASE_URL   # (empty — unset when you leave the directory)
```

### 7.5 Team Secret Sharing

**Never share secrets over Slack, email, or sticky notes.** Use a secrets manager:

```bash
# 1Password CLI (op)
eval $(op signin)
op read "op://Development/MyApp/DATABASE_URL"

# .envrc with 1Password
export DATABASE_URL=$(op read "op://Development/MyApp/DATABASE_URL")
export STRIPE_SECRET_KEY=$(op read "op://Development/MyApp/STRIPE_SECRET_KEY")
```

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id myapp/dev --query SecretString --output text | jq -r .

# HashiCorp Vault
vault kv get -field=password secret/myapp/database
```

```bash
# Vercel environment variables
vercel env pull .env.local      # Download env vars for current project
vercel env add SECRET_KEY       # Add a new secret
vercel env ls                   # List all env vars
```

### 7.6 Environment Variable Validation at Startup

Don't let your app silently fail because an env var is missing. Validate at startup.

```typescript
// env.ts (Node.js with zod)
import { z } from "zod";

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  API_KEY: z.string().min(1),
  STRIPE_SECRET_KEY: z.string().startsWith("sk_"),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().default(3000),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export const env = envSchema.parse(process.env);

// If DATABASE_URL is missing, the app crashes immediately with a clear error:
// ZodError: [
//   { code: 'invalid_type', expected: 'string', received: 'undefined', path: ['DATABASE_URL'] }
// ]
```

```typescript
// Alternative: envalid (Node.js)
import { cleanEnv, str, port, url } from "envalid";

export const env = cleanEnv(process.env, {
  DATABASE_URL: url(),
  REDIS_URL: url(),
  API_KEY: str(),
  PORT: port({ default: 3000 }),
});
```

```python
# Python with pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    api_key: str
    stripe_secret_key: str
    debug: bool = False
    port: int = 8000

    class Config:
        env_file = ".env.local"

settings = Settings()  # Raises ValidationError if required vars are missing
```

---

## 8. MONOREPO DEPENDENCY STRATEGIES

### 8.1 Hoisting (npm/yarn Workspaces)

```json
// package.json (root)
{
  "name": "myapp",
  "private": true,
  "workspaces": ["apps/*", "packages/*"]
}
```

```
myapp/
├── package.json
├── node_modules/           ← Shared dependencies hoisted here
├── apps/
│   ├── web/               ← Next.js app
│   │   └── package.json
│   └── api/               ← Express API
│       └── package.json
└── packages/
    ├── ui/                ← Shared React components
    │   └── package.json
    ├── db/                ← Prisma schema + client
    │   └── package.json
    └── config/            ← Shared ESLint, TypeScript configs
        └── package.json
```

The problem with hoisting: Dependencies are physically located at the root `node_modules/`, but your code might accidentally import packages that aren't in your `package.json` (phantom dependencies). This works locally but breaks when you deploy or publish the package.

### 8.2 pnpm Strict Mode (Recommended)

pnpm uses a content-addressable store and symlinks. Each package can only access its declared dependencies.

```yaml
# .npmrc
# pnpm settings
shamefully-hoist=false         # Don't hoist (strict mode — default in pnpm)
strict-peer-dependencies=true  # Error on peer dep mismatches
```

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
```

```bash
# Install dependencies
pnpm install

# Add a dependency to a specific package
pnpm --filter @myapp/web add next
pnpm --filter @myapp/api add express

# Add a workspace dependency
pnpm --filter @myapp/web add @myapp/ui --workspace

# Run a script in a specific package
pnpm --filter @myapp/web dev

# Run a script in all packages that have it
pnpm -r run build
```

Why pnpm is the monorepo standard:
- **No phantom dependencies**: If it's not in your package.json, you can't import it
- **Disk efficient**: Packages stored once globally, symlinked into projects
- **Fast**: Parallel installs, content-addressable cache
- **Strict**: Catches dependency issues that npm/yarn silently allow

### 8.3 Turborepo / Nx for Build Orchestration

```json
// turbo.json (Turborepo)
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],          // Build dependencies first
      "outputs": ["dist/**", ".next/**"]
    },
    "test": {
      "dependsOn": ["build"]
    },
    "lint": {},                          // No dependencies, can run in parallel
    "dev": {
      "cache": false,                    // Don't cache dev server
      "persistent": true                 // Long-running task
    }
  }
}
```

```bash
# Run build in all packages (with caching + parallelism)
turbo build

# Only run affected packages
turbo build --filter=...[HEAD~1]

# Remote caching (Vercel)
turbo build --remote-cache
```

### 8.4 Shared Packages

```json
// packages/config/package.json
{
  "name": "@myapp/eslint-config",
  "version": "1.0.0",
  "main": "index.js"
}
```

```json
// packages/tsconfig/package.json
{
  "name": "@myapp/tsconfig",
  "version": "1.0.0",
  "files": ["base.json", "nextjs.json", "react-library.json"]
}
```

```json
// apps/web/tsconfig.json
{
  "extends": "@myapp/tsconfig/nextjs.json",
  "compilerOptions": {
    "outDir": "dist"
  },
  "include": ["src"]
}
```

### 8.5 Versioning Strategies

**Fixed (recommended for most teams)**: All packages share the same version number. One version bump, one release. Simpler to reason about.

**Independent**: Each package has its own version. More flexible, more overhead. Use when packages have genuinely different release cadences.

### 8.6 Changesets for Versioning and Publishing

```bash
# Install
pnpm add -D -w @changesets/cli
pnpm changeset init
```

```bash
# When you make a change that should be released:
pnpm changeset
# Interactive prompt:
# Which packages? → @myapp/ui
# Bump type? → minor
# Summary? → Added new Button variant

# This creates .changeset/some-name.md:
# ---
# "@myapp/ui": minor
# ---
# Added new Button variant
```

```bash
# In CI, apply changesets and publish:
pnpm changeset version     # Updates package versions + CHANGELOG.md
pnpm -r publish            # Publish to npm
```

---

## 9. REPRODUCIBLE BUILDS

### 9.1 What Reproducibility Means

**Bit-for-bit reproducibility**: Given the same source code and build instructions, anyone can produce the exact same binary output. The hash of the output is identical, regardless of who built it, when, or where.

### 9.2 Why It Matters

- **Security**: You can verify that a binary was built from the claimed source code. No backdoors injected during build.
- **Debugging**: Reproduce the exact binary running in production. Match debug symbols perfectly.
- **Compliance**: Audit trails require provable builds. Supply chain security (SLSA framework) requires reproducibility.

### 9.3 Nix for Reproducible Builds

Nix achieves reproducibility by design: every input is explicit, every build is sandboxed, outputs are content-addressed.

```nix
# Build a production Docker image with Nix
{
  packages.x86_64-linux.docker = pkgs.dockerTools.buildImage {
    name = "myapp";
    tag = "latest";
    contents = [ myAppPackage ];
    config.Cmd = [ "${myAppPackage}/bin/myapp" ];
  };
}
```

### 9.4 Docker Multi-Stage Builds with Pinned Images

```dockerfile
# Pin by digest, not tag. Tags are mutable; digests are not.
FROM node:20.11.0-alpine@sha256:abc123... AS builder

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# Production image
FROM node:20.11.0-alpine@sha256:abc123... AS runner
WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

USER node
CMD ["node", "dist/server.js"]
```

### 9.5 Bazel for Hermetic Builds

Bazel (and its successor Bazel-compatible tools like Buck2, Pants) treat builds as pure functions:

- Every input file is declared explicitly
- Build actions are sandboxed (no network, no undeclared file access)
- Results are cached by input hash (local and remote)
- Same inputs always produce same outputs

Best for: Large monorepos (Google, Meta scale), multi-language projects, projects that need CI build times measured in seconds not minutes thanks to granular caching.

Trade-off: Significant setup cost. Not worth it for most projects under 100 engineers.

### 9.6 Go's Reproducible Builds

Go has first-class support for reproducible builds:

```bash
# go.mod pins exact dependency versions
# go.sum contains cryptographic checksums
# Go's build system is deterministic by default

# Verify that dependencies haven't been tampered with
go mod verify

# Build with CGO disabled for fully static, reproducible binary
CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o myapp ./cmd/myapp

# -trimpath: removes filesystem paths from the binary
# -ldflags="-s -w": strips debug info (smaller binary, but still reproducible)
```

---

## 10. RECOMMENDED STACK BY PROJECT TYPE

### Quick Reference Table

| Project Type | Version Manager | Package Manager | Dev Environment | Secrets |
|---|---|---|---|---|
| Node.js monorepo | mise + .nvmrc | pnpm | Docker Compose for services | direnv + .env.local |
| Python API | mise + .python-version | uv | venv + Docker Compose for DB | direnv + .env.local |
| Go microservice | mise | go modules | Docker Compose for deps | direnv + Vault |
| Rust CLI | rustup | cargo | None needed | direnv |
| Multi-language | Nix flakes | language-native | nix develop + direnv | 1Password CLI |
| Full-stack startup | mise | pnpm (FE) + uv (BE) | Docker Compose + devcontainer | Vercel env pull |
| Enterprise Java | sdkman | Gradle/Maven | Docker Compose | Vault / AWS Secrets Manager |

### 10.1 Starter: Node.js Monorepo

```
myapp/
├── .nvmrc                    # Node version
├── .mise.toml                # Tools + env vars
├── .envrc                    # direnv config
├── .env.example              # Documented env vars
├── .env.local                # Local secrets (gitignored)
├── .gitignore
├── docker-compose.yml        # PostgreSQL, Redis
├── pnpm-workspace.yaml
├── turbo.json
├── package.json
├── apps/
│   └── web/
└── packages/
    └── ui/
```

```
# .nvmrc
20.11.0
```

```toml
# .mise.toml
[tools]
node = "20.11.0"
"npm:turbo" = "2"

[env]
_.file = ".env.local"
```

```bash
# .envrc
use mise
```

### 10.2 Starter: Python API

```
myapi/
├── .python-version           # Python version
├── .mise.toml
├── .envrc
├── .env.example
├── .env.local
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── src/
    └── myapi/
```

```toml
# .mise.toml
[tools]
python = "3.12.2"

[env]
_.file = ".env.local"
```

```toml
# pyproject.toml
[project]
name = "myapi"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "pydantic-settings>=2.2",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.4.0",
    "mypy>=1.10",
]
```

### 10.3 Starter: Nix Flake (Multi-Language)

```nix
# flake.nix
{
  description = "Multi-language project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Node.js
            nodejs_20
            nodePackages.pnpm

            # Python
            python312
            uv

            # Go
            go_1_22

            # System dependencies
            postgresql_16
            redis
            docker-compose

            # Tools
            awscli2
            terraform
            jq
            direnv
          ];

          shellHook = ''
            export DATABASE_URL="postgresql://localhost:5432/myapp_dev"
            echo "Dev environment ready"
            echo "  Node: $(node -v)"
            echo "  Python: $(python --version)"
            echo "  Go: $(go version)"
          '';
        };
      }
    );
}
```

```bash
# .envrc (for Nix flake projects)
use flake
dotenv_if_exists .env.local
```

### 10.4 Starter: Dev Container

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "Full Stack Dev",
  "dockerComposeFile": ["../docker-compose.yml", "docker-compose.devcontainer.yml"],
  "service": "devcontainer",
  "workspaceFolder": "/workspace",

  "features": {
    "ghcr.io/devcontainers/features/node:1": { "version": "20" },
    "ghcr.io/devcontainers/features/python:1": { "version": "3.12" },
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },

  "forwardPorts": [3000, 5432, 6379],
  "postCreateCommand": "pnpm install && uv sync",

  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "ms-python.python",
        "charliermarsh.ruff"
      ]
    }
  }
}
```

```yaml
# .devcontainer/docker-compose.devcontainer.yml
services:
  devcontainer:
    image: mcr.microsoft.com/devcontainers/base:ubuntu
    volumes:
      - ..:/workspace:cached
    command: sleep infinity
```

---

## CHEAT SHEET

```
┌─────────────────────────────────────────────────────────┐
│              DEPENDENCY MANAGEMENT DECISION TREE         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Need system packages (pg, redis, ffmpeg)?              │
│  ├── YES → Nix flakes + direnv                         │
│  └── NO                                                 │
│       │                                                 │
│       ├── Single language?                              │
│       │   ├── Node → nvm/fnm + pnpm                    │
│       │   ├── Python → pyenv/mise + uv                  │
│       │   ├── Rust → rustup + cargo                     │
│       │   ├── Go → built-in + go modules                │
│       │   └── JVM → sdkman + gradle/maven               │
│       │                                                 │
│       └── Multi-language?                               │
│           ├── mise (modern, fast, built-in env/tasks)   │
│           └── asdf (established, huge plugin ecosystem) │
│                                                         │
│  Need services (DB, cache, queue)?                      │
│  └── Docker Compose (always)                            │
│                                                         │
│  Need reproducible builds?                              │
│  ├── Small project → Docker multi-stage + pinned images │
│  ├── Medium → Nix builds                                │
│  └── Large (100+ engineers) → Bazel                     │
│                                                         │
│  Secrets management?                                    │
│  ├── Solo/small team → direnv + .env.local              │
│  ├── Vercel project → vercel env pull                   │
│  └── Enterprise → 1Password CLI / Vault / AWS SM        │
│                                                         │
│  ALWAYS:                                                │
│  • Commit lockfiles                                     │
│  • Use --frozen-lockfile in CI                          │
│  • Validate env vars at startup                         │
│  • .gitignore .env files with secrets                   │
│  • Pin versions in .nvmrc / .python-version / etc.      │
│  • Document setup in README (or better: automate it)    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

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

"It works on my machine" is a war crime. This chapter is your Geneva Convention.

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
- Chapter 12 (Docker/tooling hands-on — where you first met these tools)
- Chapter 11 (language-specific package managers)
- Chapter 15 (monorepo dependency strategies)
- Chapter 7 (DevOps & deployment — the production side of what you manage here)

---

## 1. THE PROBLEM

Let me describe a scene you have almost certainly lived through.

It's 11 PM the day before a big demo. The feature works perfectly on your machine. You push to staging. Staging blows up with a cryptic error you have never seen before. You spend three hours chasing a ghost — it turns out staging was running Node 18.9 and you were on Node 20.11, and the behavior of `fs.promises.readFile` with a specific encoding edge-case changed between them. Three hours. For a version number.

Or picture your new hire's first day. They're smart, excited, ready to ship. Instead of writing code, they spend two days installing things, fighting Homebrew conflicts, getting told their Python version is wrong, discovering that the `DATABASE_URL` env var you forgot to document is required for the tests to run. They arrive on day three mildly demoralized. You could have prevented all of it.

This is the problem. It's boring, it's expensive, and it is entirely solvable.

### 1.1 "Works on My Machine"

The phrase hides a combinatorial explosion of differences between environments. Every one of these dimensions can bite you:

- **OS differences**: macOS uses BSD utilities, Linux uses GNU. `sed -i` behaves differently. `readlink` flags differ. libc implementations vary (glibc vs musl). Your shell script that works fine on your Mac fails silently in CI because CI runs on Linux. This happens more than anyone admits.
- **Version differences**: Node 18 vs 20, Python 3.10 vs 3.12, OpenSSL 1.1 vs 3.0. Even patch versions can change behavior. The bug isn't in your code. The bug is the assumption that everyone has the same Node version.
- **System dependencies**: One developer has libpq installed via Homebrew, another compiled from source, a third doesn't have it at all. Your app links against whatever happens to be on the machine.
- **Environment variables**: Missing `DATABASE_URL`, different `NODE_ENV`, stale AWS credentials. The code is correct; the environment is wrong. Good luck finding it in a stack trace.
- **Implicit state**: Global npm packages, Python packages installed with `pip install --user`, stale caches, leftover Docker volumes from a project you deleted six months ago. Your machine has accumulated years of invisible state. New machines don't have it. CI doesn't have it. Production definitely doesn't have it.

Each of these is a small chaos demon that hides in the gap between your machine and everyone else's.

### 1.2 Dependency Hell

```
Your app
├── library-A@2.0 (requires shared-lib@^3.0)
├── library-B@1.5 (requires shared-lib@^2.0)
└── 💥 shared-lib: needs to be both 3.x AND 2.x
```

This is the diamond dependency problem, and it has been making developers miserable since the dawn of package managers. But it gets worse:

- **Diamond dependencies**: Two libraries depend on incompatible versions of the same transitive dependency. You didn't cause this conflict; two library authors who have never met each other caused it. You get to deal with it.
- **Phantom dependencies**: Your code imports a package that isn't in your `package.json` but happens to be installed because another dependency brought it along. Works locally, breaks in CI. You add `axios` to your dependencies, and suddenly ten phantom imports you didn't know existed become visible when CI does a clean install. Fun!
- **Transitive dependency drift**: You didn't change anything. You didn't touch `package.json`. But a transitive dependency published a broken patch release, and your next `npm install` pulled it in because your lockfile was missing or ignored. Monday morning: everything is broken and `git blame` shows no changes.

### 1.3 The left-pad Incident (And Why It Matters)

On March 22, 2016, a developer named Azer Koçulu unpublished 273 npm packages after a dispute with npm over a package name. One of those packages was `left-pad` — eleven lines of code that pads a string on the left. Thousands of projects, including Babel and React, broke simultaneously across the entire JavaScript ecosystem. CI pipelines failed worldwide. Production deploys stopped. All because of eleven lines of code that left the registry.

The lesson wasn't "don't depend on tiny packages" (though that's good advice). The lesson was: **when you rely on things you don't control, and you don't pin exact versions with integrity hashes, you are one bad day away from everything breaking at once.** The ecosystem has gotten better — npm now has policies against unpublishing packages with dependents, and lockfiles with integrity hashes are standard — but the underlying fragility is still there.

Lockfiles exist because of moments like left-pad. Treat them accordingly.

### 1.4 Environment Drift

| | Dev | Staging | Production |
|---|---|---|---|
| Node version | 20.11.0 | 20.9.0 | 20.10.0 |
| PostgreSQL | 16.1 (Homebrew) | 15.4 (Docker) | 16.2 (RDS) |
| OS | macOS 14 | Ubuntu 22.04 | Amazon Linux 2023 |
| ENV vars | .env.local | Terraform | AWS Secrets Manager |

Every row in that table is a potential production incident. Every difference is a place where code can behave differently. As you scale from one developer to ten to a hundred, the number of possible environment combinations explodes. The only way to win is to make "environment" something you define explicitly and version control, not something that accumulates organically on each machine.

This is the thesis of the entire chapter. If you remember nothing else: **environment is configuration, configuration is code, code goes in git.**

### 1.5 The Cost of Non-Reproducibility

The costs are real and they compound:

- **Debugging time**: "It works locally" adds hours to every bug investigation. You're debugging the environment, not the code. You can't tell whether the fix you just made actually fixed the bug or whether it just happened to work on your machine. This erodes confidence in your entire process.
- **Onboarding time**: New engineers spend 1-3 days setting up their dev environment instead of shipping on day one. That's 2-6 weeks of lost productivity per year per new hire, conservatively. With a team of ten and two new hires a year, you've lost a developer-month to "install the right version of Node."
- **Production incidents**: A dependency that worked in dev but not in prod causes downtime. Post-mortems reveal "we didn't test with the same Node version" or "libssl was different on the production box." These are not interesting failures. They're avoidable failures.
- **CI flakes**: Tests pass locally but fail in CI because of subtle environment differences, eroding trust in the test suite. Once engineers start assuming CI is wrong when it fails, you've lost the CI. It becomes noise instead of signal.

The good news: you can solve all of this. Let's do it.

---

## 2. NIX & NIXOS

Nix is the extreme solution to the reproducibility problem, and it is glorious. If you've been burned enough times by environment chaos, Nix will feel like arriving home. If you haven't been burned enough yet, bookmark this section and come back to it after your next "it works on my machine" incident.

### 2.1 What Nix Is

Nix is a **purely functional package manager**. Every package is built in isolation, identified by a cryptographic hash of all its inputs (source code, dependencies, build scripts, compiler flags). This means:

- **Immutable**: Once built, a package never changes. `/nix/store/abc123-nodejs-20.11.0/` is always exactly the same binary everywhere. Always. On your machine, on your colleague's machine, in CI, on a server in a data center you've never visited.
- **Content-addressed**: The path includes a hash of everything that went into building it. Different inputs produce different paths. If two machines have the same path, they have the same binary. This is mathematically guaranteed, not hoped for.
- **No global state**: No `/usr/local/lib` pollution. Multiple versions coexist without conflict. Node 18 and Node 20 live side by side. Your Rails project from 2019 using Ruby 2.7 doesn't fight with your new project using Ruby 3.3.
- **Reproducible**: Same inputs always produce the same output, across machines, across time. Not "probably the same." The same. Provably.

This is not how any other package manager works. Homebrew installs into `/usr/local`. apt modifies global state. pip contaminates your system Python. Every conventional package manager assumes you want one version of everything, globally, and it will cheerfully destroy the old one when you install the new one.

Nix rejects this worldview entirely, and it is correct to do so.

### 2.2 Key Concepts

```
Derivation          A build recipe: sources + dependencies + build script → output
Nix Store           /nix/store/ — immutable, content-addressed storage for all packages
nix-shell           Legacy command to enter a temporary shell with specific packages
nix develop         Modern (flakes) equivalent of nix-shell
Flakes              The modern Nix interface: reproducible, composable, with a lockfile
nixpkgs             The package repository — 100,000+ packages, one of the largest in existence
```

The Nix store is the key insight. Every package lives in a path that includes a cryptographic hash of its inputs. `/nix/store/5hq8d8gp...nodejs-20.11.0/bin/node` is a specific binary built from specific source code with specific compiler flags. That hash is stable. That binary never changes. You can share it across a team, cache it, verify it, and trust it.

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

This is the old way. It still works, but it has a problem: the version of nixpkgs you get depends on your "channel," which is mutable. Two developers running `nix-shell` against the same `shell.nix` at different times might get slightly different package versions. The lockfile equivalent was missing. Flakes fix this.

### 2.4 Nix Flakes (The Modern Approach)

Flakes add reproducibility guarantees that legacy Nix lacks: a lockfile (`flake.lock`), a standard schema, and no reliance on mutable channels. When you commit a `flake.lock`, you've pinned the exact commit of nixpkgs — and therefore the exact versions of every package — that your project uses. Everyone on your team, including CI, gets the exact same binary toolchain.

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

Notice what just happened: you described your entire development environment — Node version, Python version, system-level services like PostgreSQL and Redis, CLI tools like AWS CLI and Terraform — in a single file, with a lockfile that pins exact versions. Your new hire clones the repo, runs `nix develop`, and has exactly the same tools you have. No "step 3: install PostgreSQL, but make sure it's version 16" in the README. No "you might need to install libpq if you're on Ubuntu 22.04." Just one command.

### 2.5 direnv + Nix: Automatic Environment Activation

The killer combo. When you `cd` into a project directory, your shell automatically gets the right versions of everything. No manual `nix develop`. No remembering to switch versions. You walk into the room and the lights turn on.

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

The first time direnv loads a flake, it might take a minute to build. After that, everything is cached in the Nix store and activation is instant. You will never think about it again. You will just `cd` and everything will work.

This is the goal. Invisible correctness.

### 2.6 Nix for CI

Here is where the investment pays off. The same `flake.nix` that defines your local dev environment can define your CI environment. Not "approximately the same." Literally the same:

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

Same Node version, same system libraries, same tools. Locally and in CI. Always. CI flakes that say "passed in CI, failed locally" or "passed locally, failed in CI" become a rarity. When the test suite is green, it's green everywhere, because everywhere is the same environment.

The magic-nix-cache-action is worth calling out: it caches built packages in the Nix store across CI runs, so you're not rebuilding Node from source every time. Subsequent runs are fast.

### 2.7 NixOS

NixOS extends the Nix philosophy to the entire operating system. Your OS configuration is a single declarative file that describes the entire system:

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

- **Atomic upgrades**: The entire system switches to a new configuration atomically. If something breaks, reboot and select the previous generation from the bootloader. This isn't like `apt upgrade` where partial failure leaves you with a half-upgraded system. It's all or nothing, and rollback is one reboot.
- **Declarative**: The configuration file IS the system. No imperative state drift. No "I added a cron job six months ago and forgot." No "someone SSH'd in and installed something." The system is what the file says it is.
- **Best for**: Servers where you need guaranteed reproducibility, CI runners, and developers who want to go all the way down the rabbit hole.

This connects directly to Chapter 7's coverage of immutable infrastructure — the same philosophy that says "never mutate a running server; replace it" applied to the operating system itself. NixOS is immutable infrastructure for your development machine.

### 2.8 When to Use Nix

**Use Nix when:**
- Your project has system-level dependencies (PostgreSQL, Redis, FFmpeg, ImageMagick, native libraries). Docker Compose handles the running services, but Nix handles the compilation environment and CLI tools consistently.
- You work across multiple languages (Node + Python + Go in the same project). One `flake.nix` manages everything.
- You need CI/local parity guaranteed. Not "pretty good." Guaranteed.
- Your team is spending meaningful time on "works on my machine" problems. One Nix setup pays for itself in a week.
- You're tired of "install Homebrew, then install X, then install Y, hope the versions work, and by the way these steps only apply to macOS, here's the Ubuntu version..."

**Don't use Nix when:**
- Your project is a simple single-language app with no system dependencies (use mise or the language's version manager — simpler is better here).
- Your team is small and Docker Compose handles everything.
- Nobody on the team has Nix experience and you're shipping against a deadline. Nix has a real learning curve. Pick your moment.
- You need to onboard team members quickly and can't budget time for the learning curve.

### 2.9 Trade-offs

| Advantage | Disadvantage |
|---|---|
| True reproducibility | Steep learning curve (the Nix language is unlike anything else) |
| Cross-platform (macOS + Linux) | Nix language is unusual (not quite functional, not quite JSON) |
| Enormous package repository (100k+) | Large disk usage (/nix/store grows) |
| Atomic upgrades and rollbacks | First build is slow (subsequent builds are cached) |
| One config for local + CI | macOS support is good but Linux-first |
| Community growing rapidly | Documentation has historically been rough (improving fast with nix.dev) |

The disk usage is real — `/nix/store` can grow to 50-100GB on an active machine. The `nix-collect-garbage` command cleans up unused packages, and `nix store optimise` deduplicates. Budget the disk space and it's fine.

The learning curve is also real. The Nix language is a purely functional expression language that takes time to internalize. The payoff is enormous, but don't expect to master it in a weekend.

### 2.10 Real-World Adoption

- **Shopify**: Uses Nix for dev environments across thousands of developers. When you have that many machines, manual environment management isn't a process; it's a prayer.
- **Replit**: Entire platform built on Nix for package management. Every Repl gets its own isolated, reproducible environment.
- **Cachix**: Binary cache service that makes Nix builds fast by sharing pre-built packages. The secret weapon that makes team Nix viable — you don't all build from source; you share.
- **Determinate Systems**: Building commercial tooling around Nix (FlakeHub, the Determinate Nix Installer). The Determinate Installer is now the recommended way to install Nix; it works reliably on macOS and adds an uninstaller.
- **European Space Agency**: Uses NixOS for mission-critical systems. When the stakes are high enough, reproducibility isn't optional.
- **Target, Hercules CI, Tweag**: Production Nix users with public case studies.

---

## 3. VERSION MANAGERS

If Nix is the maximal solution, version managers are the pragmatic middle ground. They solve the most common "works on my machine" problem — different language runtime versions — without requiring you to learn a new programming language or rethink your entire setup.

The rule is simple: **always pin your language version in a file that lives in the project repo.** `.nvmrc`, `.python-version`, `.ruby-version`, `.tool-versions`, `rust-toolchain.toml`. Any of these. The point is that the version is in git, not in someone's head, and it's enforced automatically when you enter the project directory.

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

nvm is slow to initialize (it's shell script), but it works reliably and has the largest community. If you want speed, use `fnm` instead — it's nvm-compatible (reads `.nvmrc`) but written in Rust, so it adds essentially zero overhead to shell startup.

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

One `.python-version` file in your repo root. Everyone who clones the project, if they're using pyenv or mise, gets the right Python. No more "wait, what Python version does this project use?" It's in the repo. Check it.

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

`rust-toolchain.toml` is a particularly elegant version pinning mechanism — rustup reads it automatically, downloads the specified toolchain if needed, and uses it. No manual switching. The toolchain specification — including components and cross-compilation targets — lives in the repo alongside the code that requires them.

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

Go has taken the sensible position that the toolchain version should be in `go.mod` alongside the module itself. Since Go 1.21, `go mod tidy` will download and use the right Go version automatically. This is the correct design decision, and it's one reason Go projects have fewer "which Go version do I need?" incidents than equivalent Node or Python projects.

### 3.2 Universal Version Managers

The language-specific tools work great when you're only dealing with one language. Once your project touches two or three languages — say a Node frontend, a Python API, and a Go service — you have a version manager management problem. You need a manager for your managers. Enter the universal version managers.

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

How asdf works under the hood: It uses **shims**. When you install a tool, asdf creates a shim script in `~/.asdf/shims/` that intercepts the command, reads `.tool-versions`, and dispatches to the correct version. It's clever, and it works across hundreds of plugins contributed by the community. The `.tool-versions` file is asdf's gift to the ecosystem — it's become a standard that other tools like mise respect.

#### mise (Formerly rtx) - The Modern Choice

mise is a Rust-based alternative to asdf that's faster, has better UX, and adds task running and environment variable management. It's what asdf would be if you rewrote it from scratch today, knowing what you know now.

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

The task runner is the killer feature that puts mise ahead. Instead of a `Makefile` that nobody understands or a collection of shell scripts in a `scripts/` directory that half the team doesn't know about, you have tasks defined right next to the tool versions they depend on. `mise run db-reset` is self-documenting, consistent across operating systems, and available to everyone who clones the repo.

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

The verdict: if you're starting fresh, use mise. If you have a team that's already on asdf with a bunch of custom plugins, the migration isn't urgent — asdf works fine. But mise is where the ecosystem is heading.

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

Whatever you choose, the cardinal rule is the same: **the version lives in a file in the repo, not in your head.**

---

## 4. LOCKFILES & DETERMINISTIC INSTALLS

If version managers solve "which runtime am I using," lockfiles solve "which exact package am I using." They are not optional. They are not best-practice suggestions. They are the minimum bar for responsible dependency management.

### 4.1 Why Lockfiles Exist

Your `package.json` says `"lodash": "^4.17.0"`. That caret means "any 4.x version at or above 4.17.0." Which includes 4.17.0, 4.17.1, and — critically — 4.17.21. Without a lockfile, two developers running `npm install` a week apart could get different versions of every transitive dependency. Their node_modules are different. Their builds are different. The bugs one of them sees, the other might not. And nobody knows why.

This isn't hypothetical. This happens constantly in teams without proper lockfile discipline. "I can't reproduce your bug" often translates to "our node_modules are different and we don't know it."

A lockfile pins the **exact** resolved version of every package in your dependency tree. Not just your direct dependencies — every transitive dependency too. With a lockfile and a frozen install command, two developers can get byte-for-byte identical node_modules from a cold start.

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

This is not a style preference. This is a correctness requirement.

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

If someone on your team has lockfiles in `.gitignore`, that is a bug. Not a preference, not a style thing — a bug. It means CI is not running the same packages as development. It means two developers running `npm install` at different times get different results. It means the left-pad scenario can happen to you. Fix it today.

The one exception: library authors sometimes don't commit `Cargo.lock` because they want downstream consumers to resolve against current versions. But for applications — services, servers, CLIs — commit the lockfile, every time, no exceptions.

### 4.4 `npm ci` vs `npm install`

This distinction matters more than most developers realize:

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

The name `npm ci` is not a coincidence — it stands for "continuous integration." It was specifically designed for the use case where you want the exact packages from your lockfile and nothing else. Use `npm install` when you're developing (adding or updating dependencies). Use `npm ci` everywhere else. Never use `npm install` in a Dockerfile or CI pipeline.

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

Set these in your CI config and forget about it. They run fast (everything is cached), they're deterministic, and they will catch lockfile drift immediately — when a developer runs `npm install` to add a package but forgets to commit the updated `package-lock.json`, the next CI run fails loudly instead of silently drifting.

### 4.6 Dependency Resolution

Modern package managers use SAT solvers or purpose-built resolution algorithms. It's worth understanding roughly how they work, because the resolution algorithm affects what breaks when:

- **npm**: Uses a tree-based resolution algorithm. Can produce deeply nested `node_modules` trees (deduplication improved in v7+). Multiple versions of the same package can coexist at different depths of the tree.
- **pnpm**: Content-addressable store + symlinks. Each package is stored once on disk globally, linked into projects. **Strict by default** — no phantom dependencies. If it's not in your `package.json`, you cannot import it. This catches an entire class of bugs that npm silently allows.
- **yarn Berry (PnP)**: Plug'n'Play mode eliminates `node_modules` entirely. A `.pnp.cjs` file maps imports to zip archives in `.yarn/cache/`. Fastest possible install (no file system tree to build), strictest possible dependency enforcement.
- **uv**: Written in Rust, uses a PubGrub-based resolver. Resolves Python dependencies 10-100x faster than pip. Generates a cross-platform lockfile that works on macOS, Linux, and Windows simultaneously.
- **Cargo**: Also uses a PubGrub variant. Known for high-quality dependency resolution and excellent error messages when resolution fails.

The resolution algorithm is why "just delete node_modules and npm install again" sometimes fixes things — you were in a state that the algorithm wouldn't produce from scratch, but accumulated through incremental installs. This is a sign you need `npm ci` in your workflow.

### 4.7 Integrity Verification

Lockfiles don't just record versions — they record cryptographic hashes of package contents:

```json
// package-lock.json (excerpt)
"lodash": {
  "version": "4.17.21",
  "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz",
  "integrity": "sha512-v2kDEe57lecTulaDIuNTPy3Ry4gLGJ6Z1O3vE1krgXZNrsQ+LFTGHVxVjcXPs17LhbZR/iIBSvRQ8+oa/fRT/=="
}
```

That `integrity` field is the SHA-512 hash of the package tarball. npm verifies this hash on every install. If the npm registry serves you a different tarball than what you locked — due to a supply chain attack, a registry compromise, or a package republish — the integrity check fails and the install is aborted. This is the post-left-pad safety mechanism. It works as long as you commit the lockfile.

---

## 5. PYTHON ENVIRONMENT MANAGEMENT

Python gets its own section because its packaging ecosystem is uniquely, spectacularly fragmented. The joke "there are 14 competing standards" isn't really a joke — at the peak, the Python packaging ecosystem had multiple incompatible build systems, two competing metadata standards, at least five different dependency management tools, and three different ways to manage virtual environments. It was the kind of chaos that made you appreciate boring.

The good news is that in 2024-2026, this has consolidated dramatically. There's a clear winner now. But let's walk through the history so you understand why the landscape looks the way it does.

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

The result: for nearly two decades, every tutorial you found used a different tool. "Just use pip" led to global package installation and conflicts. "Use virtualenv" was right but incomplete. "Use Pipenv" was officially recommended for a couple of years, then the maintainer went quiet and the community abandoned it. "Use Poetry" was the answer from 2018 until 2024, and it's still fine, but it's been lapped.

The churn isn't a sign that Python is bad. It's a sign that the community takes packaging seriously and keeps improving. But if you haven't worked in Python for a few years, the landscape looks unrecognizable.

### 5.2 Virtual Environments (The Foundation)

This foundational concept hasn't changed:

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

Virtual environments are the Python answer to the package isolation problem that Nix solves at the system level. Every Python project should have its own virtual environment. This is not optional. Running `pip install` into your system Python is the Python equivalent of `sudo apt install` — it might work today, but you're accumulating implicit state that will bite you eventually.

Modern tools handle virtual environment creation automatically, so you rarely need to think about it explicitly. But understanding that they exist and why they exist helps you reason about what's happening when things go wrong.

### 5.3 Modern Tooling Comparison

#### uv (The 2024-2026 Winner)

By Astral (the team behind Ruff). Written in Rust. 10-100x faster than pip. This is not marketing copy — benchmarks consistently show that `uv sync` completes in 1-3 seconds what `pip install -r requirements.txt` takes 30-90 seconds to do. On a project with hundreds of dependencies, this difference compounds: your CI installs go from a minute and a half to five seconds.

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
- **Speed**: `uv sync` is 10-100x faster than `pip install`. Not a typo. This matters at scale.
- **All-in-one**: Replaces pip, pip-tools, virtualenv, pyenv (for Python version management), and pipx. You don't need a version manager management problem for Python; uv handles Python version installation too.
- **Cross-platform lockfile**: `uv.lock` resolves for all platforms simultaneously — macOS, Linux, Windows. One lockfile, all platforms.
- **Compatible**: Reads `requirements.txt`, `pyproject.toml`, `.python-version`. Migration is usually drop-in.
- **No activation needed**: `uv run` executes in the right environment automatically. You don't need to remember to activate the virtualenv.

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

Poetry is mature, well-documented, and used by a huge number of existing Python projects. It introduced the concept of dependency groups, deterministic locking for Python, and a reasonable project structure to the ecosystem years before uv existed. If you're maintaining an existing Poetry project, there's no urgent reason to migrate. But for new projects, uv is the better choice.

#### PDM

PEP 582 support (no virtualenv needed, uses `__pypackages__/`), modern resolver, PEP 621 compliant. Good tool, less adoption than Poetry or uv. Worth knowing exists; probably not worth adopting for most projects.

#### Hatch

PEP 621 compliant, built-in environment matrix (test across Python 3.10, 3.11, 3.12 easily), good for library authors. Used by many PyPA projects (pip itself uses Hatch). If you're publishing a library that needs to test against multiple Python versions, Hatch's environment matrix is genuinely excellent.

#### Rye

By Armin Ronacher (Flask creator). Wraps uv internally. Conceptually similar to uv's project management but predates it. Astral has stated uv is the successor. You may encounter it in existing projects; new projects should use uv directly.

### 5.4 Recommendation

**For new projects in 2025-2026: Use uv.** The conversation is over. It's the fastest, most complete, and most actively developed tool. The entire Python packaging ecosystem is consolidating around it, and Astral has shown a strong commitment to stability and backwards compatibility.

For existing projects: Migrate to uv when convenient. It reads `requirements.txt` and `pyproject.toml` natively, so migration is usually a few commands:

```bash
# Migrate from requirements.txt to uv
uv init
uv add $(cat requirements.txt | grep -v '^#' | grep -v '^$' | tr '\n' ' ')
uv lock
# Delete requirements.txt, use pyproject.toml + uv.lock going forward
```

The speed difference alone will justify the migration in your first CI run.

---

## 6. DOCKER FOR DEV ENVIRONMENTS

Docker is often misapplied for development: people Dockerize their application code, then fight with hot reload not working, file permissions being wrong, and volume mount performance problems. This is the wrong use of Docker for development.

The right use: **Dockerize the services your application depends on, run your application code natively.** PostgreSQL, Redis, RabbitMQ, Elasticsearch, LocalStack — these are perfect Docker candidates for local development. Your Node or Python code is not.

This connects to Chapter 7's treatment of containers: containers are excellent for isolating services with specific version requirements and complex configuration, but they add friction when you need tight development loops with live reloading and debugger attachment.

### 6.1 Docker Compose for Services

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

This is a complete local infrastructure stack. PostgreSQL 16, Redis 7, a local SMTP server with a web UI, LocalStack for AWS services, and MinIO for S3-compatible object storage. It starts in under ten seconds. A new developer clones the repo, runs `docker compose up -d`, and has the exact same infrastructure as you do. No Homebrew services running in the background, no version conflicts, no "wait, what database are you running locally?"

Every service uses a named Docker volume, so data persists between restarts. `docker compose down -v` nukes everything and you're back to a clean slate. This is the local equivalent of the database wipe-and-restore you'd do in staging.

### 6.2 Dev Containers

Dev containers are for when you want to go further — not just the services, but the entire development environment inside a container. VS Code, GitHub Codespaces, and JetBrains Gateway all support them.

The use case: you have complex system dependencies (specific native libraries, platform-specific tools), a cross-platform team (Windows + macOS + Linux), or you want every developer to start from exactly the same base image with zero local setup.

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

The `features` system is particularly elegant: instead of writing a custom Dockerfile that installs Docker-in-Docker, the GitHub CLI, and AWS CLI, you declare the features you want. The container runtime assembles them. It's composable infrastructure for dev environments.

**When to use dev containers:**
- Onboarding (new engineer goes from clone to running in minutes — open VS Code, click "Reopen in Container," wait, done)
- Cross-platform teams (Windows + macOS + Linux developers — the container is Linux regardless of host OS)
- Complex system dependencies (specific versions of native libraries that are painful to install natively)
- GitHub Codespaces (cloud-based development for remote teams or open source projects with complex setup)

**When not to use dev containers:**
- Simple projects where native development is fast and your team is Mac-homogeneous
- When performance is critical — macOS → Docker VM → container adds overhead
- When you need tight debugger integration that containers complicate

### 6.3 Trade-offs of Docker for Development

| Pro | Con |
|---|---|
| Consistent services (same PostgreSQL everywhere) | Overhead on macOS (Docker Desktop uses a VM) |
| Easy to spin up and tear down | Volume mount performance on macOS (especially node_modules) |
| Isolates services from your system | Adds complexity to debugging (container networking, logs) |
| Reproducible across the team | Docker Desktop license costs for large companies |

**macOS performance tip**: Use Docker volumes for data (databases), not bind mounts. The performance difference is significant — a bind-mounted `node_modules` on macOS can be 3-10x slower than native. If you must bind-mount code, use `:cached` or VirtioFS (Docker Desktop 4.15+). For `node_modules` specifically, use a named volume and let Docker manage it.

---

## 7. ENVIRONMENT VARIABLES & SECRETS

Environment variables are how you configure an application without hardcoding configuration into its source. They're also the most common source of "why is staging broken but production is fine" incidents, because they're invisible and easy to get wrong.

The rules here are simple. Violating them is how credentials end up in git history and production goes down at 2 AM.

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

`.env.example` is the contract. It documents every environment variable the application needs. New developer clones the repo, copies `.env.example` to `.env.local`, fills in the values (ideally from a secrets manager — see section 7.5), and the app works. No hunting through code trying to figure out which env vars are required. No discovering that `PAYMENT_WEBHOOK_SECRET` is required only when you try to test the webhook flow.

Every time you add a new env var to the app, update `.env.example`. This is a discipline. Make it a team norm.

### 7.2 Precedence Rules (Next.js Example)

```
Priority (highest to lowest):
1. Process environment (CLI: DATABASE_URL=x next dev)
2. .env.$(NODE_ENV).local    (.env.development.local)
3. .env.local                (NOT loaded in test environment)
4. .env.$(NODE_ENV)          (.env.development)
5. .env                      (base defaults)
```

Most frameworks follow a similar pattern. Vite, Remix, Rails, Laravel all have their own `.env` loading order. Know your framework's rules — the precedence determines which value wins when the same variable is defined in multiple places.

The key nuance: `.env.local` is not loaded in the `test` environment. This is intentional — tests should use deterministic values defined in `.env.test`, not developer-local overrides that differ between machines.

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

If you have ever committed a `.env` file with real credentials to a public (or even private) repository, you should assume those credentials are compromised. Git history is forever — deleting the file in a subsequent commit doesn't remove it from history. The moment a secret touches git history, rotate it. No exceptions, no "but the repo is private" — private repos get breached, cloned, and moved to public without secrets being scrubbed.

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

This is the composable alternative to always activating environments manually. direnv + mise gives you automatic tool versions and automatic environment variables, scoped to the directory. direnv + Nix gives you automatic tool versions, automatic environment variables, and hermetically reproducible builds, scoped to the directory.

The security model is worth noting: direnv requires explicit `direnv allow` before running an `.envrc`. This prevents malicious repositories from automatically executing code when you clone them. After any change to `.envrc`, you must run `direnv allow` again. This is a feature, not a bug.

### 7.5 Team Secret Sharing

**Never share secrets over Slack, email, or sticky notes.** This cannot be emphasized enough. Slack messages can be leaked. Email can be forwarded. Sticky notes are on monitors visible in video calls. Secrets belong in a secrets manager:

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

The 1Password CLI approach is particularly elegant for teams: secrets live in a shared 1Password vault, access is managed through 1Password's permissions system, and the `.envrc` pulls secrets at shell activation time. New team member gets access to the vault, runs `direnv allow`, and has the right secrets. When you rotate a secret, update it in 1Password and everyone gets the new value on their next shell session.

Chapter 7 covers secrets management in production (AWS Secrets Manager, HashiCorp Vault, environment-specific configurations). This chapter covers the development-time side of the same problem. They're two halves of the same discipline.

### 7.6 Environment Variable Validation at Startup

The worst way to discover a missing environment variable is from a production error log at 3 AM. The second worst way is from a confusing error three layers deep in your application code. The right way is to crash immediately at startup with a clear error message listing exactly which variables are missing.

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

This pattern — validate env vars at startup, fail loud and fast — is the application-level equivalent of type checking. You're asserting your invariants at the boundary between your application and the environment. If those invariants aren't met, nothing should run. Better a hard crash at startup than a mysterious `null` deep in your business logic.

The zod approach has an added benefit: you can `import { env } from './env'` throughout your application and get typed access to all environment variables. Your editor knows the type of `env.PORT` (it's a number), and TypeScript will prevent you from using it as a string. Your environment configuration is now type-safe.

---

## 8. MONOREPO DEPENDENCY STRATEGIES

Monorepos are increasingly the standard for teams building multiple related services or packages. They simplify code sharing, make cross-cutting changes easier, and unify CI configuration. But they add complexity to dependency management — you have multiple packages, potentially with different dependency needs, that need to coexist.

If you're setting up a monorepo or evaluating tooling, Chapter 7 covers the CI/CD and deployment side (how you build and deploy individual apps in a monorepo), and Chapter 15 covers the repository organization strategy in depth. This section covers the dependency management layer.

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

Workspaces hoist shared dependencies to the root `node_modules/`. This is efficient — React is installed once even though five packages depend on it — but it creates a trap: **phantom dependencies**. Your `web` app might accidentally import a package that isn't in `apps/web/package.json` because it was hoisted from somewhere else. It works locally. It breaks when you deploy `web` as a standalone service, because the other packages aren't there to do the hoisting.

This is a class of bug that's very hard to catch without the right tooling.

### 8.2 pnpm Strict Mode (Recommended)

pnpm uses a content-addressable store and symlinks. Each package can only access its declared dependencies. This eliminates phantom dependencies entirely — if it's not in your `package.json`, the module resolver can't find it.

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
- **No phantom dependencies**: If it's not in your package.json, you can't import it. This catches dependency issues at `pnpm install` time, not at production deploy time.
- **Disk efficient**: Packages stored once globally, symlinked into projects. A global content-addressable store means you have one copy of React on your machine regardless of how many projects use it.
- **Fast**: Parallel installs, content-addressable cache. Fresh installs are fast; repeated installs with the same lockfile are nearly instant.
- **Strict**: Catches dependency issues that npm/yarn silently allow. Being strict here saves you production incidents.

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

Turborepo understands the dependency graph of your packages. When you run `turbo build`, it builds packages in the right order (dependencies before dependents), runs independent packages in parallel, and caches results by input hash. If the inputs to `packages/ui` haven't changed since the last build, `turbo build` skips it and uses the cached output. This turns monorepo CI from "build everything, always, slowly" to "build what changed, in parallel, with caching."

The `--filter=...[HEAD~1]` flag is particularly powerful in CI: only run tasks for packages that have changed relative to the previous commit. Instead of a 10-minute CI run that tests every package on every commit, you get targeted runs that test only what's affected.

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

Shared configuration packages are the highest-leverage monorepo pattern. One ESLint config, extended by all apps. One TypeScript base config, specialized per use case. One set of Prettier rules. When you need to update a rule, update it once. Every app in the monorepo picks it up when it rebuilds.

The alternative — copying config files into every app — sounds fine until you have twelve apps and discover that ten of them have diverged slightly, and you can't remember which version is "current."

### 8.5 Versioning Strategies

**Fixed (recommended for most teams)**: All packages share the same version number. One version bump, one release. Simpler to reason about, simpler to debug ("which version of @myapp/ui does production have?" — same answer as every other package).

**Independent**: Each package has its own version. More flexible, more overhead. Use when packages have genuinely different release cadences — when `packages/cli` needs to ship weekly but `packages/core` changes monthly, independent versioning makes sense.

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

Changesets solve the "who bumped what version and why" problem in monorepos. Instead of a single person manually updating versions and writing changelogs, every developer who makes a publishable change creates a changeset file describing what changed and at what semver level. CI collects these, bumps versions, generates changelogs, and publishes. The history of version bumps is in git, reviewable, and attributable.

---

## 9. REPRODUCIBLE BUILDS

We've talked about reproducible environments and deterministic installs. Now let's talk about the hardest version of the problem: reproducible builds, where the goal is that two independent builds of the same source code produce **byte-for-byte identical output**.

This is harder than it sounds. Build outputs routinely embed timestamps, random UUIDs, filesystem paths, and other non-deterministic data. Truly reproducible builds require eliminating all of this.

### 9.1 What Reproducibility Means

**Bit-for-bit reproducibility**: Given the same source code and build instructions, anyone can produce the exact same binary output. The hash of the output is identical, regardless of who built it, when, or where.

This is the strongest possible reproducibility guarantee. It means you can independently verify that a distributed binary was built from the claimed source code — no backdoors, no supply chain injection, no tampering between the repo and the artifact.

### 9.2 Why It Matters

- **Security**: You can verify that a binary was built from the claimed source code. No backdoors injected during build. The reproducible-builds.org project has found cases where distributed binaries differed from what the source code would produce. That's a supply chain attack.
- **Debugging**: Reproduce the exact binary running in production. Match debug symbols perfectly. "It only happens in production" often means "you're debugging a different binary than the one running."
- **Compliance**: Audit trails require provable builds. The SLSA (Supply-chain Levels for Software Artifacts) framework defines levels of supply chain security, with full reproducibility at the highest level.
- **Trust**: When your CI publishes a release and your users can independently rebuild and verify it, you've removed yourself as a trusted intermediary. This is increasingly important as supply chain attacks become more common.

### 9.3 Nix for Reproducible Builds

Nix achieves reproducibility by design: every input is explicit, every build is sandboxed, outputs are content-addressed. Sandboxing means builds run without network access and without access to undeclared inputs — so there's no way for a build to accidentally depend on your machine's local state.

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

A Docker image built with `pkgs.dockerTools.buildImage` produces a deterministic layer hash. The same image, built on any machine with the same Nix inputs, produces the same hash. You can distribute the hash as a verification artifact, and anyone can rebuild and check it.

### 9.4 Docker Multi-Stage Builds with Pinned Images

If you're not using Nix, pinned Docker image digests give you the next best thing:

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

The key insight: `node:20.11.0-alpine` is a mutable tag. Whoever publishes the Node.js Docker images can update it to fix a security vulnerability. Your build next week might use a different base image than your build today. `node:20.11.0-alpine@sha256:abc123...` is immutable — it refers to a specific manifest in the registry. Nobody can change what that digest points to.

Pin base images by digest in production Dockerfiles. Update the pins deliberately, test the update, merge it. This is the same discipline as lockfiles, applied to Docker images.

### 9.5 Bazel for Hermetic Builds

Bazel (and its successors like Buck2 and Pants) treat builds as pure functions: same inputs always produce the same outputs, guaranteed by hermetic sandboxing. Every input file is declared explicitly. Build actions can't access the network or undeclared files. Results are cached by input hash locally and remotely.

```python
# BUILD file (Bazel)
nodejs_binary(
    name = "server",
    srcs = ["server.js"],
    deps = [
        "@npm//express:express",
        "@npm//pg:pg",
    ],
)
```

Best for: Large monorepos (Google-scale, Meta-scale), multi-language projects, projects that need CI build times measured in seconds not minutes thanks to granular caching. If your CI builds take 30 minutes and half the time is rebuilding things that didn't change, Bazel's incremental builds will transform your workflow.

Trade-off: Significant setup cost. Bazel's build files are verbose. The learning curve is steep. Migration from an existing build system is non-trivial. Not worth it for most projects under 100 engineers, but transformative for large monorepos.

### 9.6 Go's Reproducible Builds

Go has first-class support for reproducible builds, and it's worth highlighting as a model for how language ecosystems should handle this:

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

The `-trimpath` flag is the key to reproducibility: without it, the Go binary embeds the absolute path of each source file (for debugging). This means a binary built on `/home/alice/projects/myapp` has different bytes than one built on `/Users/bob/code/myapp`. `-trimpath` replaces these with module-relative paths, making the binary identical regardless of where it was built. Go's reproducible builds story is one of the best in the ecosystem.

---

## 10. RECOMMENDED STACK BY PROJECT TYPE

All the principles in this chapter converge into a set of concrete recommendations. Use these as starting points, not as rigid rules — adapt based on your team, your project complexity, and your operational context.

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

This is the stack for a TypeScript full-stack team building a Next.js frontend and Node API backend with shared packages. It's opinionated and tuned for the workflow described in Chapter 12 (where you first saw this kind of project structure).

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

The combination of `.nvmrc` (for compatibility with tools that read it directly) and `.mise.toml` (for mise's richer feature set) means any developer using either nvm, fnm, or mise gets the right Node version automatically. The `_.file = ".env.local"` in `.mise.toml` means environment variables load automatically when you activate mise. Everything is in the repo. Nothing is in anyone's head.

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

New developer workflow: `git clone`, `direnv allow`, `uv sync`, `docker compose up -d`, `uv run uvicorn myapi.main:app --reload`. That's the entire setup. One command installs all Python dependencies with the exact versions from `uv.lock`. One command starts the database. One command starts the dev server. Twenty minutes of setup, tops — most of it is `git clone` and `docker compose pull`.

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

This is the setup for teams who need everything pinned and reproducible — system packages, multiple language runtimes, infrastructure tools. When you commit `flake.lock`, the entire toolchain is pinned. When a new developer joins, `nix develop` gives them everything. When CI runs, it uses the same environment.

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

Dev containers shine for cross-platform teams and complex setups. The VS Code extension handles everything: clone the repo, open it in VS Code, click "Reopen in Container," and the container builds, extensions install, dependencies sync, and you're coding. The entire environment — editor settings, extensions, tools, services — is defined in checked-in files.

---

## CHEAT SHEET

The whole chapter boils down to a few decisions and a set of invariants. Make the decisions once, enforce the invariants always.

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
│  • Never share secrets over Slack or email              │
│  • Update .env.example when you add new env vars        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

The goal is a world where "it works on my machine" is a phrase that no longer exists in your team's vocabulary. Where a new developer can go from `git clone` to a running development environment in under fifteen minutes. Where CI and local development use the same toolchain, the same dependency versions, the same environment configuration. Where "works in CI but not locally" is as rare as a unicorn.

This isn't a dream. It's a set of engineering decisions you can make today. Make them.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M27: Dependency & Environment Management](../course/modules/loop-1/L1-M27-dependency-and-environment-management.md)** — Lock TicketPulse's dependencies, pin its runtime versions, and make the dev environment reproducible from a single command
- **[L1-M02: Your Dev Environment](../course/modules/loop-1/L1-M02-your-dev-environment.md)** — Set up the foundational dev environment that TicketPulse builds on, covering toolchain management and container-based isolation

### Quick Exercises

1. **Run `npm audit`, `pip-audit`, `cargo audit`, or your ecosystem's equivalent and triage every vulnerability: for each finding, record whether it's reachable in your code, then fix or suppress with a documented reason.**
2. **Check if your lockfile is committed — if not, commit it now, then verify that `git clone` followed by the install command produces a bit-for-bit identical `node_modules` (or equivalent) on two different machines.**
3. **Create a `.tool-versions` (asdf), `flake.nix` (Nix), or `.mise.toml` (mise) for your project that pins every runtime version, then delete your local toolchain and verify you can restore the exact versions in under two minutes.**

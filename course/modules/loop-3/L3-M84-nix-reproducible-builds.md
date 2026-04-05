# L3-M84: Nix & Reproducible Builds

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 45 min | 🟡 Deep Dive | Prerequisites: L2-M42
>
> **Source:** Chapter 20 of the 100x Engineer Guide

## What You'll Learn

- Why "works on my machine" is an engineering failure mode, not a joke
- Nix as a purely functional package manager: immutable, content-addressed, reproducible
- Writing a `flake.nix` that defines TicketPulse's exact development environment
- direnv integration: auto-activating the environment when you enter the project directory
- Using the same Nix flake in CI for guaranteed dev/CI parity
- Trade-offs: when Nix is worth the learning curve and when simpler tools suffice

## Why This Matters

TicketPulse's CI builds occasionally fail for reasons that have nothing to do with the code. Last week, a build broke because the CI runner had Node 20.9.0 while the code was developed on 20.11.0 and relied on a feature introduced in 20.10. The week before, a native PostgreSQL client library was a different version on macOS vs the Ubuntu CI runner, causing a segfault in the test suite.

Every engineer on the team has a slightly different setup. One uses Homebrew, another uses nvm, a third installed Node from the website. The `README.md` says "Node 20+" but does not specify which 20. The Dockerfile pins the version, but the dev environment does not.

This is not a tooling inconvenience. It is a class of bug that wastes hours per incident, erodes trust in CI, and makes onboarding new engineers take days instead of minutes.

Nix solves this by making the entire development environment declarative, reproducible, and shareable. One file defines every tool, every version, every system dependency. The same file works on macOS, Linux, and CI. If it works for one person, it works for everyone.

---

## 1. The Nix Mental Model

### Purely Functional Package Management

Nix treats packages like pure functions treat values:

```
Traditional package manager:
  npm install node@20 → mutates /usr/local/bin/node
  brew install postgresql → mutates /usr/local/lib/libpq
  Two packages with conflicting deps → 💥

Nix:
  Every package → /nix/store/<hash>-<name>-<version>/
  node@20.11.0 → /nix/store/abc123-nodejs-20.11.0/bin/node
  node@20.9.0  → /nix/store/def456-nodejs-20.9.0/bin/node
  Both coexist. No conflicts. No mutation. Ever.
```

The hash in the path is computed from ALL inputs: source code, dependencies, build scripts, compiler flags. Change any input, get a different hash, get a different path. Same inputs always produce the same output.

### Key Concepts

| Concept | What It Is |
|---------|-----------|
| **Derivation** | A build recipe: sources + dependencies + build script = output |
| **Nix Store** | `/nix/store/` -- immutable, content-addressed storage for all packages |
| **Flake** | The modern Nix interface: reproducible, composable, with a lockfile |
| **nixpkgs** | The package repository -- 100,000+ packages, one of the largest in existence |
| **nix develop** | Enter a shell with all packages from a flake available |
| **flake.lock** | Pins exact versions of all inputs (like package-lock.json for your entire toolchain) |

---

## 2. Build: A Flake for TicketPulse

### The flake.nix

```nix
# flake.nix -- drop this in TicketPulse's project root
{
  description = "TicketPulse development environment";

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
            # JavaScript / Node.js
            nodejs_20           # Exact: Node.js 20.x from nixpkgs
            nodePackages.pnpm   # Package manager
            nodePackages.typescript

            # Database clients
            postgresql_16       # psql CLI + libpq (exact version)
            redis               # redis-cli

            # Infrastructure tools
            docker-compose
            awscli2
            terraform

            # Build tools
            protobuf            # Protocol Buffers compiler
            grpcurl             # gRPC testing tool
            jq                  # JSON processing

            # Testing
            k6                  # Load testing
          ];

          shellHook = ''
            echo "TicketPulse dev environment loaded"
            echo "  Node.js: $(node --version)"
            echo "  pnpm:    $(pnpm --version)"
            echo "  psql:    $(psql --version | head -1)"
            export PRISMA_QUERY_ENGINE_LIBRARY="${pkgs.prisma-engines}/lib/libquery_engine.node"
            export DATABASE_URL="postgresql://localhost:5432/ticketpulse_dev"
          '';
        };
      }
    );
}
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

### What This Gives You

Every engineer who runs `nix develop` in the TicketPulse directory gets:

- **Exactly** Node.js 20.x (the specific version pinned in `flake.lock`)
- **Exactly** PostgreSQL 16 client libraries (no more "my libpq is a different version")
- **Exactly** the same protobuf compiler (no more "my generated code differs from yours")
- All tools available immediately, no installation steps, no Homebrew, no manual downloads

### Try It

```bash
# First time: Nix downloads and builds everything (cached afterward)
nix develop

# You're now in a shell with all tools available
node --version    # v20.11.0 (or whatever nixpkgs pins)
psql --version    # psql (PostgreSQL) 16.x
protoc --version  # libprotoc 25.x
k6 version        # k6 v0.x.x

# Exit the shell
exit
```

### The Lockfile

Running `nix develop` the first time creates `flake.lock`:

```json
{
  "nodes": {
    "nixpkgs": {
      "locked": {
        "lastModified": 1710000000,
        "narHash": "sha256-abc123...",
        "owner": "NixOS",
        "repo": "nixpkgs",
        "rev": "a1b2c3d4e5f6...",
        "type": "github"
      }
    }
  }
}
```

This lockfile pins nixpkgs to an exact commit. Every engineer, every CI run, every machine that uses this lockfile gets the exact same package versions. Commit `flake.lock` to git.

### Updating Dependencies

```bash
# Update all inputs to their latest versions
nix flake update

# Update only nixpkgs
nix flake lock --update-input nixpkgs

# After updating, test everything, then commit the new flake.lock
pnpm test && git add flake.lock && git commit -m "Update Nix flake inputs"
```

---

## 3. direnv: Automatic Environment Activation

Typing `nix develop` every time you open a terminal is friction. direnv eliminates it.

### Setup

```bash
# Install direnv (one time)
# On macOS:
brew install direnv

# Add to your shell config (~/.zshrc or ~/.bashrc):
eval "$(direnv hook zsh)"    # or: eval "$(direnv hook bash)"
```

### Configure for TicketPulse

```bash
# .envrc (in TicketPulse project root)
use flake
```

```bash
# Allow direnv for this directory (one time, after creating .envrc)
cd ~/projects/ticketpulse
direnv allow
```

Now, every time you `cd` into the TicketPulse directory:

```
$ cd ~/projects/ticketpulse
direnv: loading .envrc
direnv: using flake
TicketPulse dev environment loaded
  Node.js: v20.11.0
  pnpm:    9.x.x
  psql:    psql (PostgreSQL) 16.x

$ cd ~
direnv: unloading   # Environment is cleaned up when you leave
```

No manual activation. No forgetting to switch Node versions. No "wait, which project am I in?"

---

## 4. Nix in CI: Same Environment, Every Time

### GitHub Actions with Nix

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Install Nix with flake support
      - uses: DeterminateSystems/nix-installer-action@main

      # Cache the Nix store between runs (huge speedup)
      - uses: DeterminateSystems/magic-nix-cache-action@main

      # Run tests inside the exact same environment as local dev
      - run: nix develop --command bash -c "pnpm install && pnpm test"

      # Run linting
      - run: nix develop --command bash -c "pnpm lint"

      # Run type checking
      - run: nix develop --command bash -c "pnpm tsc --noEmit"
```

The CI runner uses the same `flake.nix` and `flake.lock` as every developer. Same Node version. Same PostgreSQL client. Same protobuf compiler. If tests pass locally, they pass in CI. The "works on my machine" class of bugs is eliminated.

---

## 5. Build: Nix for Docker Images

### Reproducible Docker Builds with Nix

Nix can also build Docker images, eliminating a different class of reproducibility problem: "this Dockerfile builds a different image on different machines because of layer caching, apt-get install pulling newer packages, or different Docker daemon versions."

```nix
# In your flake.nix, add a package output for the Docker image:

packages.dockerImage = pkgs.dockerTools.buildLayeredImage {
  name = "ticketpulse-order-service";
  tag = "latest";

  contents = with pkgs; [
    nodejs_20
    # Only include what the app needs to run -- nothing else
    # No shell, no package manager, no build tools
  ];

  config = {
    Cmd = [ "${pkgs.nodejs_20}/bin/node" "dist/server.js" ];
    WorkingDir = "/app";
    ExposedPorts = { "3000/tcp" = {}; };
    Env = [
      "NODE_ENV=production"
    ];
    User = "1000:1000";
  };

  # Copy your built application
  extraCommands = ''
    mkdir -p app
    cp -r ${./dist}/* app/
    cp -r ${./node_modules} app/node_modules
  '';
};
```

```bash
# Build the Docker image
nix build .#dockerImage

# Load it into Docker
docker load < result

# Run it
docker run -p 3000:3000 ticketpulse-order-service:latest
```

**Why this matters**: The image built by Nix is bit-for-bit identical regardless of which machine builds it or when. No layer cache surprises. No "apt-get install pulled a newer version." The image is a deterministic function of its inputs.

### Nix vs Multi-Stage Docker Builds

| Aspect | Multi-Stage Dockerfile | Nix Docker Image |
|--------|----------------------|-------------------|
| Reproducibility | Good (if you pin base image digests) | Perfect (content-addressed) |
| Build speed | Fast (layer caching) | First build slow, then cached |
| Image size | Small (with careful multi-stage) | Small (only declared contents) |
| Debugging | Easy (familiar tooling) | Harder (Nix-specific) |
| Adoption | Universal | Requires Nix knowledge |

For most teams, multi-stage Dockerfiles with pinned base image digests are sufficient. Nix Docker builds are for teams that already use Nix and want the same reproducibility guarantees for their container images.

---

## 6. When Nix Is Worth It (and When It Is Not)

### Use Nix When

- **Cross-language projects**: TicketPulse has Node.js services, a Python ML pipeline, and Go infrastructure tools. Nix manages all of them in one file.
- **System-level dependencies**: PostgreSQL client, protobuf compiler, FFmpeg, ImageMagick -- anything that is not a npm/pip/go package.
- **CI reproducibility is critical**: You are tired of debugging "passes locally, fails in CI" issues.
- **Team onboarding**: New engineers should be productive on day one, not after two days of setup.

### Do Not Use Nix When

- **Single-language, no system deps**: A pure TypeScript project with no native dependencies? `mise` or `nvm` is enough.
- **Small team, Docker Compose works**: If your team is 3 people and Docker Compose handles everything, Nix adds complexity without clear benefit.
- **Deadline pressure, no Nix experience**: The learning curve is real. Do not adopt Nix the week before a launch.

### Trade-offs

| Advantage | Disadvantage |
|-----------|-------------|
| True reproducibility across all machines | Steep learning curve (Nix language is unusual) |
| 100,000+ packages available | Large disk usage (`/nix/store` grows over time) |
| One config for local + CI | First build is slow (subsequent builds are cached) |
| Multiple versions coexist without conflict | macOS support is good but Linux-first |
| Atomic updates with instant rollback | Documentation has historically been rough (improving) |

### Real-World Adoption

Nix is not fringe. Shopify uses it across thousands of developers. Replit built their entire platform on it. The European Space Agency uses NixOS for mission-critical systems. Determinate Systems is building commercial tooling to make Nix more accessible.

---

## 7. Lockfile Deep Dive: Reading and Auditing flake.lock

The `flake.lock` file is the single most important artifact Nix produces. Understanding how to read and audit it is a critical skill for maintaining reproducible builds over time.

### Anatomy of a Real flake.lock

```json
{
  "nodes": {
    "nixpkgs": {
      "locked": {
        "lastModified": 1710432000,
        "narHash": "sha256-abc123XYZ456...",
        "owner": "NixOS",
        "repo": "nixpkgs",
        "rev": "a1b2c3d4e5f67890abcdef1234567890abcdef12",
        "type": "github"
      },
      "original": {
        "owner": "NixOS",
        "ref": "nixos-unstable",
        "repo": "nixpkgs",
        "type": "github"
      }
    },
    "flake-utils": {
      "locked": {
        "lastModified": 1709126400,
        "narHash": "sha256-def456ABC789...",
        "owner": "numtide",
        "repo": "flake-utils",
        "rev": "b1b2b3b4b5b67890abcdef1234567890abcdef12",
        "type": "github"
      },
      "original": {
        "owner": "numtide",
        "repo": "flake-utils",
        "type": "github"
      }
    }
  },
  "root": {
    "inputs": {
      "nixpkgs": "nixpkgs",
      "flake-utils": "flake-utils"
    }
  },
  "version": 7
}
```

**What each field means:**

- `rev`: The exact git commit hash of the nixpkgs snapshot. This is what guarantees reproducibility — not a branch name, not a version tag, a specific commit.
- `narHash`: The cryptographic hash of the NAR (Nix Archive) of this input. If the content changes, the hash changes, and the build fails. This is the content-addressable guarantee.
- `lastModified`: Unix timestamp of when this commit was made. Useful for auditing how old your dependencies are.
- `original`: What you specified in `flake.nix`. In this case, `nixos-unstable` is a branch. The lockfile resolves that to a specific commit.

### Lockfile Audit Exercise (15 minutes)

After you have a working `flake.nix`, audit the lockfile by answering these questions:

```bash
# 1. How old is your nixpkgs snapshot?
python3 -c "import datetime; print(datetime.datetime.fromtimestamp(1710432000))"
# → 2024-03-14 (or whatever the timestamp resolves to)

# 2. What exact node version does this pin?
nix eval --raw .#devShells.x86_64-linux.default --apply 'x: x.buildInputs' 2>/dev/null | head -20
# OR: enter the shell and check
nix develop --command node --version

# 3. Are there any inputs that are more than 6 months old?
# Check lastModified timestamps in flake.lock against today's date
# If yes: nix flake update and run the full test suite

# 4. Do the narHashes match what you expect?
# Run: nix flake check
# This re-downloads and verifies all inputs against the hashes in flake.lock
nix flake check
```

**Signs your lockfile needs attention:**
- `lastModified` is more than 90 days in the past: security patches may be missing
- After `nix flake update`, your tests break: a dependency changed behavior and you need to pin more carefully
- The `narHash` in CI does not match your local lock: someone updated the lockfile without committing it

### Selective Pinning for Stability

Sometimes you want nixpkgs-unstable for most packages but need to pin a specific package to an older version:

```nix
{
  description = "TicketPulse — selectively pinned";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # Pin a stable channel for production-critical tools
    nixpkgs-stable.url = "github:NixOS/nixpkgs/nixos-23.11";
  };

  outputs = { self, nixpkgs, nixpkgs-stable }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      pkgs-stable = nixpkgs-stable.legacyPackages.${system};
    in {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          # Use unstable for most packages (latest features)
          pkgs.nodejs_20
          pkgs.nodePackages.pnpm

          # Use stable for production-critical infrastructure tooling
          pkgs-stable.postgresql_16  # Known-good version
          pkgs-stable.terraform      # Pinned to avoid breaking changes
        ];
      };
    };
}
```

This gives you the freshness of unstable for development tools and the stability of the LTS channel for infrastructure tooling.

---

## 8. Customizing Your Nix Shell

A bare `nix develop` shell is functional but generic. The real productivity gain comes from customizing the shell environment with project-specific tools, aliases, and configuration.

### Shell Customization Exercise

Extend your `flake.nix` shellHook with a complete developer experience:

```nix
shellHook = ''
  # ─── Project branding ─────────────────────────────────────────────
  echo ""
  echo "  TicketPulse development environment"
  echo "  ─────────────────────────────────────────"
  echo "  Node.js:    $(node --version)"
  echo "  pnpm:       $(pnpm --version)"
  echo "  PostgreSQL: $(psql --version | head -1)"
  echo "  Redis CLI:  $(redis-cli --version)"
  echo "  Terraform:  $(terraform --version | head -1)"
  echo "  k6:         $(k6 version)"
  echo "  ─────────────────────────────────────────"
  echo "  Aliases: tp-start, tp-test, tp-migrate, tp-reset-db"
  echo ""

  # ─── Environment variables ────────────────────────────────────────
  export DATABASE_URL="postgresql://ticketpulse:ticketpulse@localhost:5432/ticketpulse_dev"
  export REDIS_URL="redis://localhost:6379"
  export KAFKA_BROKERS="localhost:9092"
  export NODE_ENV="development"
  export LOG_LEVEL="debug"

  # Prisma: use the exact query engine from Nix (no binary downloads)
  export PRISMA_QUERY_ENGINE_LIBRARY="${pkgs.prisma-engines}/lib/libquery_engine.node"
  export PRISMA_SCHEMA_ENGINE_BINARY="${pkgs.prisma-engines}/bin/schema-engine"

  # ─── Helpful aliases ──────────────────────────────────────────────
  alias tp-start='docker compose up -d && pnpm dev'
  alias tp-test='docker compose up -d postgres redis && pnpm test'
  alias tp-migrate='pnpm prisma migrate dev'
  alias tp-reset-db='pnpm prisma migrate reset --force'
  alias tp-logs='docker compose logs -f'

  # ─── Git hooks ────────────────────────────────────────────────────
  # Install pre-commit hooks if not already installed
  if [ ! -f .git/hooks/pre-commit ]; then
    echo "Installing git hooks..."
    cp scripts/pre-commit.sh .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
  fi

  # ─── Check required services ──────────────────────────────────────
  if ! docker compose ps postgres 2>/dev/null | grep -q "running"; then
    echo "⚠  PostgreSQL is not running. Run: docker compose up -d postgres"
  fi
'';
```

### Per-User Overrides with .envrc.local

Some engineers need local overrides (different database names, debug ports, feature flags). Use direnv's local override mechanism:

```bash
# .envrc (committed to git)
use flake
source_env_if_present .envrc.local
```

```bash
# .envrc.local (in .gitignore — per-engineer customization)
export DATABASE_URL="postgresql://ticketpulse:ticketpulse@localhost:5433/ticketpulse_alice"
export LOG_LEVEL="trace"
export FEATURE_FLAG_EXPERIMENTAL_SEARCH="true"
```

Every engineer runs the same Nix environment but can layer personal customizations on top without polluting the shared configuration.

### Exercise: Add a Custom Tool Not in nixpkgs

Occasionally you need a tool that is not in nixpkgs. Nix can build it from source:

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;

      # Build a custom version of a tool not in nixpkgs
      # (or a version newer than what nixpkgs has)
      customTool = pkgs.buildGoModule {
        pname = "my-custom-cli";
        version = "1.2.3";
        src = pkgs.fetchFromGitHub {
          owner = "example";
          repo = "my-custom-cli";
          rev = "v1.2.3";
          hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        };
        vendorHash = "sha256-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=";
      };
    in {
      devShells.x86_64-linux.default = pkgs.mkShell {
        buildInputs = [
          pkgs.nodejs_20
          customTool  # your custom tool is available in the shell
        ];
      };
    };
}
```

To find the correct hashes, use:

```bash
# Step 1: Use a placeholder hash to let Nix compute the real one
# (The build will fail, but show you the correct hash)
hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";

# Run nix develop — it will error with the real hash
nix develop 2>&1 | grep "got:"
# got:    sha256-abc123RealHashHere...

# Step 2: Replace the placeholder with the real hash and try again
```

---

## 9. Reflect: Reproducibility Spectrum

### Stop and Think (5 minutes)

There is a spectrum of reproducibility tools, from lightweight to heavyweight:

```
nvm/pyenv       →  mise/asdf      →  Docker         →  Nix            →  NixOS
(one language)     (multi-lang)      (containerized)   (system-level)    (entire OS)
```

Where does TicketPulse fall on this spectrum? What about your current production project?

Consider:
- How many languages does the project use?
- Does it have system-level dependencies (native libraries, CLI tools)?
- How often do CI failures come from environment differences?
- How long does onboarding a new engineer take?

There is no universally right answer. The right tool is the simplest one that eliminates your reproducibility problems.

---

---

## Cross-References

- **Chapter 20** (Everything as Code): The philosophy behind treating environments, configurations, and infrastructure as versioned, auditable code. Nix is the purest expression of this principle.
- **L3-M83** (Observability and GitOps): Nix flakes complement GitOps workflows — your environment definition lives in git alongside your application code.
- **L2-M42** (Kubernetes Fundamentals): Nix Docker image builds integrate with Kubernetes deployment pipelines.

---

## Checkpoint: What You Built

You have:

- [x] Written a `flake.nix` defining TicketPulse's complete development environment
- [x] Set up direnv for automatic environment activation
- [x] Configured GitHub Actions to use the same Nix flake as local development
- [x] Audited a `flake.lock` file: reading timestamps, hashes, and pinned commits
- [x] Customized the shell environment with aliases, environment variables, and git hooks
- [x] Set up per-user `.envrc.local` overrides that do not pollute shared configuration
- [x] Understood when Nix is worth the investment and when simpler tools suffice

**Key insight**: Nix makes "works on my machine" impossible by making the machine irrelevant. The environment is defined in code, pinned by a lockfile, and identical everywhere. The trade-off is a real learning curve and an unusual language -- but for projects with cross-language dependencies and reproducibility requirements, it pays for itself quickly.

---

**Next module**: L3-M85 -- Open Source Your Work, where we prepare a TicketPulse component for public release and learn what makes open source projects actually get adopted.

## Key Terms

| Term | Definition |
|------|-----------|
| **Nix** | A purely functional package manager that builds software in isolated, reproducible environments. |
| **Flake** | A Nix feature that provides a standardized, hermetic way to define project inputs, outputs, and dependencies. |
| **Derivation** | The fundamental build unit in Nix; a description of how to build a package from its inputs. |
| **direnv** | A shell extension that automatically loads environment variables and Nix shells when entering a project directory. |
| **Reproducible** | The property that a build produces bit-for-bit identical output regardless of when or where it is executed. |
| **Content-addressed** | A storage model where artifacts are identified by the hash of their content rather than by name or version. |
| **narHash** | The cryptographic hash of a Nix Archive (NAR), used to verify that a downloaded input has not changed since the lockfile was created. |
| **shellHook** | A Nix attribute that runs shell commands when entering a `nix develop` shell, used to set environment variables and aliases. |
| **Selective pinning** | The practice of using different nixpkgs channels for different packages to balance freshness and stability. |
---

## What's Next

In **Open Source Your Work** (L3-M85), you'll build on what you learned here and take it further.

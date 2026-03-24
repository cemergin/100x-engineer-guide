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

## 6. Reflect: Reproducibility Spectrum

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

## Checkpoint: What You Built

You have:

- [x] Written a `flake.nix` defining TicketPulse's complete development environment
- [x] Set up direnv for automatic environment activation
- [x] Configured GitHub Actions to use the same Nix flake as local development
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

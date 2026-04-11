<!--
  CHAPTER: 12b
  TITLE: Git, Docker, Terraform & Kubernetes
  PART: III — Tooling & Practice
  PREREQS: None
  KEY_TOPICS: Git advanced, Docker, Terraform, kubectl, regex
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 12b: Git, Docker, Terraform & Kubernetes

> **Part III — Tooling & Practice** | Prerequisites: None | Difficulty: Beginner to Advanced

This chapter covers the infrastructure CLI tools that make you measurably faster — Git wizardry, Docker for local development and production, Terraform for infrastructure as code, Kubernetes CLI for container orchestration, and regex patterns you will use everywhere.

### In This Chapter
- Git Mastery
- Docker for Daily Use
- Terraform Essentials
- Kubernetes CLI (kubectl)
- Regex Mastery
- Quick Reference: The Commands You Will Use Daily

### Related Chapters
- Chapter 12 — Linux, Shell & Editors (foundational tools)
- Chapter 7 — infrastructure concepts behind Docker/Terraform/K8s
- Chapter 17 — Claude Code as your AI co-pilot in the terminal
- Chapter 20 — environment management
- Chapter 15 — Git workflows in teams
- Chapter 36 — Beast Mode toolchain setup (putting it all together)

---

## 5. GIT MASTERY

Here's the thing about Git: most people learn enough to `commit`, `push`, and `pull`, and then they stop. They treat Git like a save button. But Git is actually a time machine, a collaboration tool, a code review system, and a debugging assistant — all at once.

The commands in this section are the ones that separate developers who are *in control of their history* from developers who are afraid to touch it. Interactive rebase, bisect, reflog — these feel like superpowers once they're in your toolkit. And the `.gitconfig` section at the end will improve your daily workflow immediately, with zero learning curve.

### 5.1 Interactive Rebase (The Most Powerful Git Feature)

Interactive rebase lets you rewrite history before it becomes permanent (i.e., before you push). This is how you turn a messy sequence of "fix typo", "actually fix typo", "WIP", "more WIP" commits into a clean, logical sequence that tells a coherent story to the code reviewers.

Think of it as editing a document before you publish it. The final published version should read clearly even if the drafting process was chaotic.

```bash
# Rewrite the last 5 commits
git rebase -i HEAD~5

# The editor opens with:
# pick abc1234 Add user model
# pick def5678 Fix typo in user model
# pick ghi9012 Add user service
# pick jkl3456 WIP debugging
# pick mno7890 Add user controller

# Change 'pick' to:
# pick   = keep commit as-is
# squash = merge into previous commit (combine messages)
# fixup  = merge into previous commit (discard this message)
# reword = keep commit, edit message
# edit   = pause here to amend
# drop   = delete commit

# Common rewrite: clean up before PR
# pick abc1234 Add user model
# fixup def5678 Fix typo in user model    ← fold into previous
# pick ghi9012 Add user service
# drop jkl3456 WIP debugging              ← remove entirely
# pick mno7890 Add user controller

# Autosquash workflow (the pro way):
git commit --fixup=abc1234               # Create fixup commit targeting abc1234
git commit --fixup=abc1234               # Another fixup
git rebase -i --autosquash HEAD~5        # Fixups auto-arranged next to their targets
```

### 5.2 Essential Advanced Commands

```bash
# Cherry-pick: grab specific commits from other branches
git cherry-pick abc1234                  # Apply single commit
git cherry-pick abc1234..def5678         # Apply range
git cherry-pick -n abc1234              # Apply without committing (stage only)

# Bisect: binary search for the commit that introduced a bug
git bisect start
git bisect bad                           # Current commit is broken
git bisect good v1.0.0                   # This tag was working
# Git checks out middle commit — test it, then:
git bisect good                          # or: git bisect bad
# Repeat until git identifies the exact commit
git bisect reset                         # Return to original branch

# Automated bisect (provide a test script):
git bisect start HEAD v1.0.0
git bisect run npm test                  # Runs tests at each step automatically

# Reflog: your safety net (every HEAD change is recorded for 90 days)
git reflog                               # See history of HEAD positions
git checkout HEAD@{5}                    # Go back to 5 moves ago
git branch recover-branch HEAD@{5}      # Create branch from old state

# Undo almost anything:
git reset --hard HEAD@{1}               # Undo last reset/rebase/merge
# "I accidentally force-pushed / rebased / deleted a branch" → reflog saves you
```

### 5.3 Branching Strategies

Choosing a branching strategy is like choosing a deployment architecture — it shapes how your team works every single day. Pick the wrong one and you'll spend hours on merge conflicts and coordination overhead. Here's the opinionated take:

```
# Trunk-Based Development (recommended for most teams)
# - Everyone commits to main (or short-lived feature branches, < 2 days)
# - Feature flags for incomplete work
# - CI/CD deploys from main
# + Fast integration, less merge hell, encourages small PRs
# - Requires good CI, feature flags, and discipline

# GitHub Flow (good for open source, small teams)
# - main is always deployable
# - Feature branches → PR → review → merge to main
# - Deploy from main after merge
# + Simple, easy to understand
# - Can accumulate long-lived branches

# Git Flow (for versioned software releases)
# - main (production), develop (integration), feature/*, release/*, hotfix/*
# + Clear release process, good for versioned software
# - Complex, slow, merge conflicts between long-lived branches
# - Avoid unless you have explicit versioned releases

# Decision: Use trunk-based unless you have a specific reason not to.
```

### 5.4 Git Hooks with Husky + lint-staged

Git hooks run automatically at key moments in the git workflow. The pre-commit hook runs before every commit, making it the perfect place to run your linter and formatter. This way, bad code physically cannot enter your repository — the commit just fails. `lint-staged` ensures you only lint the files you changed, keeping the hook fast.

```bash
# Install
npm install -D husky lint-staged

# Initialize husky
npx husky init

# .husky/pre-commit
npx lint-staged

# .husky/commit-msg
npx commitlint --edit $1
```

```jsonc
// package.json
{
    "lint-staged": {
        "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
        "*.{json,md,yml}": ["prettier --write"],
        "*.py": ["black", "ruff check --fix"]
    }
}

// commitlint.config.js — enforce Conventional Commits
module.exports = {
    extends: ['@commitlint/config-conventional'],
    // Enforces: type(scope): description
    // Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build
};
```

### 5.5 Advanced Git Features

```bash
# Worktrees: multiple branches checked out simultaneously
git worktree add ../hotfix-branch hotfix/urgent-fix
cd ../hotfix-branch                      # Work on hotfix without stashing current work
git worktree remove ../hotfix-branch     # Clean up when done
git worktree list                        # See all worktrees

# Sparse checkout: only check out specific directories (huge monorepos)
git clone --sparse https://github.com/org/monorepo.git
cd monorepo
git sparse-checkout set packages/my-service shared/  # Only these directories

# Shallow clone: only recent history (faster CI)
git clone --depth 1 https://github.com/org/repo.git           # Latest commit only
git clone --depth 50 --single-branch https://github.com/org/repo.git  # 50 commits, one branch

# Partial clone: download objects on demand (huge repos)
git clone --filter=blob:none https://github.com/org/repo.git  # No file contents until needed

# Subtrees: embed another repo in a subdirectory (alternative to submodules)
git subtree add --prefix=lib/utils https://github.com/org/utils.git main --squash
git subtree pull --prefix=lib/utils https://github.com/org/utils.git main --squash
```

### 5.6 .gitconfig Optimizations

Your `.gitconfig` is worth spending an hour on. The options below aren't tweaks — they're significant quality-of-life improvements. `delta` as your diff pager makes code review a pleasure instead of a chore. `zdiff3` conflict style shows you the original code alongside both conflicting versions, so you actually understand what changed instead of guessing. `rerere` remembers how you resolved a conflict and reapplies that resolution automatically the next time the same conflict appears.

```ini
# ~/.gitconfig
[user]
    name = Your Name
    email = your@email.com

[core]
    editor = nvim
    pager = delta                           # Much better diff viewer (install: brew install git-delta)
    autocrlf = input                        # Normalize line endings
    excludesFile = ~/.gitignore_global

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    side-by-side = true
    line-numbers = true
    syntax-theme = Dracula

[merge]
    conflictStyle = zdiff3                  # Shows base version in conflicts (massive help)

[diff]
    algorithm = histogram                   # Better diff algorithm than default Myers
    colorMoved = default                    # Highlight moved lines differently

[pull]
    rebase = true                           # pull --rebase by default (cleaner history)

[push]
    default = current                       # Push current branch to same-named remote
    autoSetupRemote = true                  # Auto set upstream on first push

[fetch]
    prune = true                            # Remove stale remote tracking branches

[rebase]
    autoSquash = true                       # Auto-arrange fixup! commits
    autoStash = true                        # Stash before rebase, pop after

[rerere]
    enabled = true                          # Remember conflict resolutions (REuse REcorded REsolution)

[init]
    defaultBranch = main

[alias]
    s = status -sb
    co = checkout
    cb = checkout -b
    cm = commit -m
    ca = commit --amend --no-edit
    unstage = reset HEAD --
    last = log -1 HEAD --format="%H"
    lg = log --oneline --graph --decorate --all -20
    branches = branch -a --sort=-committerdate --format='%(HEAD) %(color:yellow)%(refname:short)%(color:reset) - %(contents:subject) %(color:green)(%(committerdate:relative))%(color:reset)'
    cleanup = "!git branch --merged | grep -v '\\*\\|main\\|master\\|develop' | xargs -n 1 git branch -d"
    who = shortlog -sn --no-merges
    changed = diff --name-only HEAD~1
    undo = reset --soft HEAD~1             # Undo last commit, keep changes staged
    wip = "!git add -A && git commit -m 'WIP [skip ci]'"
```

### 5.7 Conventional Commits

Conventional Commits aren't just about being tidy — they're the foundation of automated changelogs, semantic versioning, and CI/CD workflows that know whether a commit is a feature, a bug fix, or a breaking change. Once your team adopts this format, tools like `semantic-release` can automatically version and publish your package based on commit history alone.

```
# Format: <type>(<optional scope>): <description>
#
# Types:
# feat:     New feature (triggers MINOR version bump)
# fix:      Bug fix (triggers PATCH version bump)
# docs:     Documentation only
# style:    Formatting, semicolons, etc. (no code change)
# refactor: Code change that neither fixes nor adds feature
# perf:     Performance improvement
# test:     Adding/correcting tests
# chore:    Build process, deps, tooling
# ci:       CI/CD changes
# build:    Build system or external dependency changes
#
# Breaking changes:
# feat!: remove deprecated API    ← ! triggers MAJOR version bump
# Or add BREAKING CHANGE in footer

# Examples:
feat(auth): add OAuth2 PKCE flow
fix(api): handle null response from payment gateway
refactor(user): extract validation into shared module
perf(db): add composite index for user search query
docs(readme): add deployment instructions
chore(deps): upgrade express to 4.18.2
ci(github): add parallel test execution
feat(api)!: change response format for /users endpoint

BREAKING CHANGE: Response is now paginated. Clients must handle `next_cursor` field.
```

---

## 6. DOCKER FOR DAILY USE

Docker is the "it works on my machine" problem, solved. Instead of "I need you to install Node 18, the specific version of PostgreSQL we use, and Redis, and configure them all correctly," you say `docker compose up` and the entire environment materializes in thirty seconds, identical to what runs in production.

The commands in this section are your daily Docker toolkit — the ones you'll use for local development, debugging, and managing containers. The multi-stage Dockerfile at the end is production-grade: small images, non-root user, health checks. Use it as a template.

### 6.1 Essential Commands

```bash
# Build & Run
docker build -t myapp:latest .                         # Build image
docker build -t myapp:latest --no-cache .               # Build without cache
docker build --target builder -t myapp:builder .        # Build specific stage
docker run -d -p 3000:3000 --name myapp myapp:latest    # Run detached with port mapping
docker run -it --rm myapp:latest /bin/sh                 # Interactive, auto-remove on exit
docker run -d --env-file .env -v $(pwd):/app myapp      # With env file and volume mount

# Inspect & Debug
docker ps                                                # Running containers
docker ps -a                                             # All containers (including stopped)
docker logs myapp -f --tail 100                          # Follow logs, last 100 lines
docker logs myapp --since 30m                            # Logs from last 30 minutes
docker exec -it myapp /bin/sh                            # Shell into running container
docker exec myapp cat /app/config.yml                    # Run single command
docker inspect myapp | jq '.[0].NetworkSettings'         # Inspect (JSON, pipe to jq)
docker stats                                             # Live resource usage
docker top myapp                                         # Processes in container

# Lifecycle
docker stop myapp                                        # Graceful stop (SIGTERM)
docker kill myapp                                        # Force stop (SIGKILL)
docker rm myapp                                          # Remove stopped container
docker rmi myapp:latest                                  # Remove image

# Cleanup (reclaim disk space)
docker system prune -af --volumes                        # Nuclear option: remove everything unused
docker image prune -a                                    # Remove unused images
docker volume prune                                      # Remove unused volumes
docker builder prune                                     # Clear build cache
docker system df                                         # Show Docker disk usage
```

### 6.2 Docker Compose for Local Development

This is the compose file you actually want — not just a database, but the full stack: API with hot reload, database with health checks and seed data, Redis, and a background worker, all wired together and ready to go with `docker compose up`.

```yaml
# docker-compose.yml — typical backend development setup
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: development                   # Multi-stage: use dev target
    ports:
      - "3000:3000"
      - "9229:9229"                          # Node.js debug port
    volumes:
      - .:/app                               # Mount source code
      - /app/node_modules                    # Except node_modules (use container's)
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy           # Wait for DB to be ready
      redis:
        condition: service_healthy
    command: npm run dev                      # Override CMD for development

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: myapp
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # Seed data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redisdata:/data

  worker:
    build:
      context: .
      target: development
    volumes:
      - .:/app
      - /app/node_modules
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: npm run worker:dev

volumes:
  pgdata:                                     # Named volumes persist across restarts
  redisdata:
```

```bash
# Compose commands
docker compose up -d                          # Start all services (detached)
docker compose up -d --build                  # Rebuild images before starting
docker compose down                           # Stop and remove containers
docker compose down -v                        # Also remove volumes (reset data)
docker compose logs -f api                    # Follow specific service logs
docker compose exec api sh                    # Shell into a service
docker compose ps                             # Status of services
docker compose restart api                    # Restart single service
docker compose run --rm api npm test          # Run one-off command
```

### 6.3 Multi-Stage Builds & Layer Caching

Multi-stage builds solve the fundamental Docker tension: you need build tools to compile your app, but you don't want those build tools in your production image. The pattern: separate stages for deps, build, and production. The production image gets only the compiled output, not the compiler. This is the difference between a 1.2GB image and a 120MB image.

The layer caching trick matters too: always `COPY package.json` before `COPY . .` so the expensive `npm ci` step is cached unless your dependencies actually changed.

```dockerfile
# Dockerfile — production-optimized multi-stage build

# ── Stage 1: Dependencies ──
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production                  # Install production deps only

# ── Stage 2: Build ──
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci                                    # Install ALL deps (including devDependencies)
COPY . .
RUN npm run build                             # Compile TypeScript, etc.

# ── Stage 3: Development (used by docker-compose target: development) ──
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev"]

# ── Stage 4: Production ──
FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production

# Non-root user (security)
RUN addgroup -g 1001 -S appgroup && adduser -S appuser -u 1001
USER appuser

COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package.json .

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/main.js"]
```

```
# .dockerignore — keep build context small (faster builds)
node_modules
.git
.gitignore
*.md
.env*
.vscode
coverage
dist
.nyc_output
docker-compose*.yml
Dockerfile
```

### 6.4 Docker Networking

```bash
# Default networks
docker network ls                              # List networks

# Bridge (default): containers on same bridge can communicate by container name
docker network create mynet
docker run -d --name api --network mynet myapp
docker run -d --name db --network mynet postgres
# Inside api container: curl http://db:5432 works

# Host mode: container shares host's network stack (no port mapping needed)
docker run -d --network host myapp             # App on host's port directly

# Debugging networking
docker network inspect mynet                   # See connected containers + IPs
docker exec api ping db                        # Test connectivity
docker exec api nslookup db                    # DNS resolution check
docker exec api wget -qO- http://db:5432      # HTTP check

# Port mapping
docker run -p 8080:3000 myapp                  # Host 8080 → Container 3000
docker run -p 127.0.0.1:3000:3000 myapp        # Bind to localhost only (more secure)
```

---

## 7. TERRAFORM ESSENTIALS

Terraform is infrastructure as code in the most literal sense: your servers, databases, load balancers, DNS records — all described in text files, version-controlled, reviewable, and reproducible. Instead of clicking through the AWS console and hoping you remember every setting, you write it down once and can recreate the exact same environment in any region, any account, any time.

The learning curve is real, but the payoff is enormous. Onboarding a new environment goes from "two weeks of clicking" to `terraform apply`. Disaster recovery goes from "does anyone remember how we set this up?" to `git clone && terraform apply`.

### 7.1 Core Workflow

The four-command lifecycle is what you'll run every day. `plan` before `apply`, always — treat the plan output like a code review. Read it carefully. Infrastructure mistakes are expensive.

```bash
# The 4-command lifecycle
terraform init      # Download providers, initialize backend, install modules
terraform plan      # Preview changes (ALWAYS review before apply)
terraform apply     # Apply changes (type 'yes' to confirm, or -auto-approve for CI)
terraform destroy   # Tear down all resources

# Plan to file (for CI/CD — ensures apply matches what was reviewed)
terraform plan -out=tfplan
terraform apply tfplan

# Targeted operations (use sparingly)
terraform plan -target=aws_instance.web         # Plan only specific resource
terraform apply -target=module.vpc              # Apply only specific module

# Formatting and validation
terraform fmt -recursive                         # Format all .tf files
terraform validate                               # Syntax and type checking
```

### 7.2 State Management

Terraform's state is the source of truth about what infrastructure exists. The golden rule: never store state locally when working in a team. Put it in S3 (or equivalent) with DynamoDB locking. Without the lock, two engineers running `terraform apply` simultaneously can corrupt your infrastructure.

```hcl
# Remote backend (store state in S3 — never local in a team)
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "services/api/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"            # State locking (prevents concurrent applies)
    encrypt        = true
  }
}
```

```bash
# State operations
terraform state list                              # List all resources in state
terraform state show aws_instance.web             # Show details of a resource
terraform state mv aws_instance.web aws_instance.api  # Rename without destroy/recreate
terraform state rm aws_instance.legacy            # Remove from state (keeps real resource)

# Import existing resources into Terraform management
terraform import aws_instance.web i-1234567890abcdef0

# State troubleshooting
terraform state pull > state.json                 # Download state for inspection
terraform force-unlock <lock-id>                  # Break stuck lock (dangerous, coordinate with team)

# Refresh state from real infrastructure
terraform plan -refresh-only                      # See drift without changing anything
terraform apply -refresh-only                     # Update state to match reality
```

### 7.3 Modules

Modules are the functions of Terraform — reusable, parameterized, testable infrastructure components. A well-written VPC module means you write VPC configuration once and use it in dev, staging, and production by just passing different variables. The Terraform Registry has battle-tested community modules for most common infrastructure patterns.

```hcl
# modules/vpc/main.tf — reusable VPC module
variable "name" { type = string }
variable "cidr" { type = string }
variable "azs" { type = list(string) }

resource "aws_vpc" "main" {
  cidr_block           = var.cidr
  enable_dns_hostnames = true
  tags = { Name = var.name }
}

resource "aws_subnet" "public" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr, 8, count.index)
  availability_zone = var.azs[count.index]
  tags = { Name = "${var.name}-public-${var.azs[count.index]}" }
}

output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*.id] }
```

```hcl
# Using the module
module "vpc" {
  source = "./modules/vpc"        # Local module
  # source = "terraform-aws-modules/vpc/aws"   # Registry module
  # source = "git::https://github.com/org/modules.git//vpc?ref=v1.2.0"  # Git with version

  name = "production"
  cidr = "10.0.0.0/16"
  azs  = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# Reference module outputs
resource "aws_instance" "web" {
  subnet_id = module.vpc.public_subnet_ids[0]
}
```

### 7.4 Workspaces

```bash
# Workspaces: same config, different state (good for dev/staging/prod)
terraform workspace list
terraform workspace new staging
terraform workspace new production
terraform workspace select staging
terraform workspace show                          # Current workspace
```

```hcl
# Use workspace name in configuration
locals {
  env = terraform.workspace

  instance_type = {
    dev        = "t3.micro"
    staging    = "t3.small"
    production = "t3.medium"
  }

  min_instances = {
    dev        = 1
    staging    = 2
    production = 3
  }
}

resource "aws_instance" "web" {
  instance_type = local.instance_type[local.env]
  tags = { Environment = local.env }
}
```

### 7.5 Common Patterns

```hcl
# Data sources — reference existing infrastructure
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# count — create N identical resources
resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  tags = { Name = "web-${count.index}" }
}

# for_each — create resources from a map (preferred over count for non-identical resources)
variable "buckets" {
  default = {
    logs   = { versioning = true }
    assets = { versioning = false }
    backup = { versioning = true }
  }
}

resource "aws_s3_bucket" "this" {
  for_each = var.buckets
  bucket   = "${var.project}-${each.key}"
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = { for k, v in var.buckets : k => v if v.versioning }
  bucket   = aws_s3_bucket.this[each.key].id
  versioning_configuration { status = "Enabled" }
}

# dynamic blocks — generate repeated nested blocks
resource "aws_security_group" "web" {
  name = "web-sg"

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}

# depends_on — explicit dependency (when Terraform cannot infer it)
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  depends_on    = [aws_iam_role_policy_attachment.web]  # Ensure IAM is ready
}

# Lifecycle rules
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  lifecycle {
    create_before_destroy = true   # Zero-downtime replacement
    prevent_destroy       = true   # Safety net for critical resources
    ignore_changes        = [tags] # Don't revert external tag changes
  }
}
```

### 7.6 Debugging

```bash
# Enable debug logging
TF_LOG=DEBUG terraform plan               # Full debug output
TF_LOG=TRACE terraform plan 2> debug.log  # Trace level to file
TF_LOG_CORE=DEBUG terraform plan          # Core only (not provider)
TF_LOG_PROVIDER=DEBUG terraform plan      # Provider only

# Console — interactive expression evaluator
terraform console
> cidrsubnet("10.0.0.0/16", 8, 1)
"10.0.1.0/24"
> length(var.azs)
3
> [for s in var.subnets : s.cidr if s.public]

# Dependency graph
terraform graph | dot -Tpng > graph.png   # Visualize resource dependencies
terraform graph -type=plan                # Show what will change
```

---

## 8. KUBERNETES CLI (kubectl)

If Docker is "my app in a container," Kubernetes is "my app in a container, running on a cluster of machines, with automatic scaling, self-healing, rolling deployments, and service discovery." `kubectl` is the CLI that lets you talk to that cluster — inspect what's running, debug what's broken, scale what needs more capacity.

The first thing to internalize: everything in Kubernetes is a resource with a status and events. When something breaks, your debugging flow is almost always: `get` to see status, `describe` to see events, `logs` to see what the app says. That loop solves 90% of Kubernetes problems.

### 8.1 Essential Commands

```bash
# Get resources
kubectl get pods                               # List pods in current namespace
kubectl get pods -A                            # All namespaces
kubectl get pods -o wide                       # Show node, IP, etc.
kubectl get pods -o yaml                       # Full YAML output
kubectl get pods -l app=api                    # Filter by label
kubectl get pods --sort-by='.status.startTime' # Sort by field
kubectl get all                                # Pods, services, deployments, etc.
kubectl get svc,deploy,pods                    # Multiple resource types

# Describe (detailed info + events — first place to look when debugging)
kubectl describe pod api-7d8f9b6c5-x2j4k
kubectl describe node worker-1
kubectl describe svc api-service

# Logs
kubectl logs api-7d8f9b6c5-x2j4k             # Pod logs
kubectl logs api-7d8f9b6c5-x2j4k -c sidecar  # Specific container
kubectl logs -f api-7d8f9b6c5-x2j4k          # Follow (tail -f)
kubectl logs -f -l app=api --all-containers   # All pods with label, all containers
kubectl logs api-7d8f9b6c5-x2j4k --previous  # Logs from crashed/previous container
kubectl logs api-7d8f9b6c5-x2j4k --since=1h  # Last hour

# Execute commands in pods
kubectl exec -it api-7d8f9b6c5-x2j4k -- /bin/sh         # Shell into pod
kubectl exec api-7d8f9b6c5-x2j4k -- env                  # Check environment
kubectl exec api-7d8f9b6c5-x2j4k -- cat /app/config.yml  # Read file
kubectl exec -it api-pod -- curl http://other-service:8080 # Test connectivity

# Port forwarding (access services locally)
kubectl port-forward svc/api-service 3000:80              # Service port forward
kubectl port-forward pod/api-7d8f9b6c5-x2j4k 3000:3000   # Pod port forward
kubectl port-forward deploy/api 3000:3000                 # Deployment port forward

# Apply and delete
kubectl apply -f deployment.yaml              # Create/update from file
kubectl apply -f k8s/                         # Apply all files in directory
kubectl apply -f https://raw.githubusercontent.com/org/repo/main/deploy.yaml  # From URL
kubectl delete -f deployment.yaml             # Delete resources defined in file
kubectl delete pod api-7d8f9b6c5-x2j4k       # Delete specific pod (will be recreated by deployment)

# Quick operations
kubectl scale deploy api --replicas=5         # Scale deployment
kubectl rollout restart deploy api            # Rolling restart (picks up configmap changes, etc.)
kubectl rollout status deploy api             # Watch rollout progress
kubectl rollout undo deploy api               # Rollback to previous version
kubectl rollout history deploy api            # See revision history

# Resource usage
kubectl top pods                               # CPU/memory per pod
kubectl top nodes                              # CPU/memory per node
kubectl top pods --sort-by=memory              # Sort by memory usage
```

### 8.2 Context & Namespace Management

Context switching is where engineers lose time. `kubectx` and `kubens` turn multi-step commands into single words — and with `fzf` integration, they become interactive fuzzy pickers. Install these the first day you start working with Kubernetes and never look back.

```bash
# Without kubectx/kubens (built-in)
kubectl config get-contexts                    # List all contexts
kubectl config current-context                 # Show active context
kubectl config use-context production          # Switch context
kubectl config set-context --current --namespace=staging  # Set default namespace

# With kubectx/kubens (install: brew install kubectx)
kubectx                     # List contexts (interactive with fzf)
kubectx production          # Switch context
kubectx -                   # Switch to previous context

kubens                      # List namespaces (interactive with fzf)
kubens staging              # Switch namespace
kubens -                    # Switch to previous namespace
```

### 8.3 Debugging Pods

A systematic approach is worth more than memorizing commands. When a pod is broken, work through this checklist in order. The status alone tells you a lot — `CrashLoopBackOff`, `ImagePullBackOff`, `Pending` all have different causes and different fixes. Don't start guessing until you've read the events.

```bash
# Step 1: Check pod status
kubectl get pods -l app=api
# STATUS tells you a lot:
# CrashLoopBackOff  → App crashing on start (check logs)
# ImagePullBackOff  → Cannot pull image (check image name/registry auth)
# Pending           → Cannot be scheduled (check resources/node availability)
# Init:0/1          → Init container stuck (check init container logs)
# Running (but not ready) → Readiness probe failing

# Step 2: Describe the pod (look at Events section at bottom)
kubectl describe pod api-7d8f9b6c5-x2j4k
# Events show: scheduling, pulling image, starting, probe failures, OOM kills

# Step 3: Check logs
kubectl logs api-7d8f9b6c5-x2j4k
kubectl logs api-7d8f9b6c5-x2j4k --previous    # If it crashed and restarted

# Step 4: Shell in and investigate (if pod is running)
kubectl exec -it api-7d8f9b6c5-x2j4k -- /bin/sh
# Inside: check env vars, test DNS, test connectivity
env | grep DATABASE
nslookup other-service
wget -qO- http://other-service:8080/health

# Step 5: Check events across namespace
kubectl get events --sort-by='.lastTimestamp' | tail -20
kubectl get events --field-selector reason=FailedScheduling

# Step 6: Check resource constraints
kubectl describe node <node-name>              # Check capacity vs allocated
kubectl top pods                                # Actual usage vs limits
```

### 8.4 kubectl Plugins & Tools

`k9s` deserves special mention. It's a terminal UI for Kubernetes that makes navigating resources, reading logs, shelling into pods, and editing YAML feel natural and fast. Once you've used it, raw `kubectl` for anything interactive feels tedious. Install it immediately.

```bash
# krew — plugin manager for kubectl
kubectl krew install ctx ns neat stern         # Install plugins

# stern — multi-pod log tailing (essential for microservices)
brew install stern                              # Or: kubectl krew install stern
stern api                                       # Tail all pods matching "api"
stern api -n staging                            # In specific namespace
stern "api|worker" --since 5m                   # Multiple patterns, last 5 min
stern api -o json | jq                          # JSON output
stern api --exclude "health"                    # Exclude health check noise
stern api -c main                               # Specific container only

# k9s — terminal UI for Kubernetes (the best way to interact with k8s)
brew install k9s
k9s                                             # Launch TUI
k9s -n staging                                  # Start in specific namespace
k9s --context production                        # Start with specific context

# k9s shortcuts:
# :pods / :svc / :deploy / :ns     Navigate resource types
# / + pattern                      Filter
# d                                Describe
# l                                Logs
# s                                Shell into pod
# Ctrl+d                          Delete
# y                                YAML view

# kubectl neat — clean up verbose YAML output
kubectl get pod api-pod -o yaml | kubectl neat  # Remove managed fields, status, etc.

# Other useful plugins:
# kubectl tree                      Show resource ownership hierarchy
# kubectl images                    List all images in cluster
# kubectl sniff                     Start tcpdump on a pod
# kubectl who-can                   RBAC analysis
```

### 8.5 Quick Reference: Resource Shortnames

```bash
# Save keystrokes with short names
kubectl get po        # pods
kubectl get svc       # services
kubectl get deploy    # deployments
kubectl get rs        # replicasets
kubectl get ds        # daemonsets
kubectl get sts       # statefulsets
kubectl get cm        # configmaps
kubectl get secret    # secrets
kubectl get ns        # namespaces
kubectl get no        # nodes
kubectl get ing       # ingresses
kubectl get pv        # persistentvolumes
kubectl get pvc       # persistentvolumeclaims
kubectl get sa        # serviceaccounts
kubectl get ep        # endpoints
kubectl get hpa       # horizontalpodautoscalers
kubectl get cj        # cronjobs

# Custom output columns
kubectl get pods -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
NODE:.spec.nodeName,\
IP:.status.podIP,\
RESTARTS:.status.containerStatuses[0].restartCount

# JSONPath queries
kubectl get pods -o jsonpath='{.items[*].metadata.name}'
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.capacity.memory}{"\n"}{end}'
```

---

## 9. REGEX MASTERY

Regex is one of those skills where the activation energy to learn it is high, but the payoff lasts a career. It shows up everywhere: `grep`, `rg`, `sed`, VS Code search, log analysis, input validation, database queries, linting rules. Engineers who don't know regex reach for manual solutions to problems that should take three seconds. Engineers who do know it turn log analysis, refactoring, and data extraction into one-liners.

A surprisingly high-leverage skill. Master the syntax, know the gotchas, and bookmark regex101.com for the rest.

### Core Syntax Reference

```
LITERALS & METACHARACTERS
.           Any character (except newline)
\d          Digit [0-9]
\D          Non-digit
\w          Word character [a-zA-Z0-9_]
\W          Non-word character
\s          Whitespace (space, tab, newline)
\S          Non-whitespace
\b          Word boundary
^           Start of line
$           End of line

QUANTIFIERS
*           0 or more (greedy)
+           1 or more (greedy)
?           0 or 1 (optional)
{3}         Exactly 3
{2,5}       Between 2 and 5
{3,}        3 or more
*?  +?  ??  Lazy versions (match as few as possible)

GROUPS & ALTERNATION
(abc)       Capture group
(?:abc)     Non-capturing group
(?P<name>abc)  Named capture group
(a|b)       Alternation (a OR b)

LOOKAHEAD & LOOKBEHIND
(?=abc)     Positive lookahead (followed by abc)
(?!abc)     Negative lookahead (NOT followed by abc)
(?<=abc)    Positive lookbehind (preceded by abc)
(?<!abc)    Negative lookbehind (NOT preceded by abc)

CHARACTER CLASSES
[abc]       Any of a, b, c
[a-z]       Range
[^abc]      NOT a, b, or c
[a-zA-Z0-9]  Alphanumeric
```

### Practical Patterns Every Engineer Needs

```bash
# Email (simplified — don't use for validation, use a library)
[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}

# IPv4 address
\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b

# URL extraction
https?://[^\s<>"{}|\\^`\[\]]+

# ISO date (2024-01-15)
\d{4}-\d{2}-\d{2}

# ISO datetime (2024-01-15T10:30:00Z)
\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?

# UUID
[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}

# Semantic version (1.2.3, 1.0.0-beta.1)
\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?

# Extract function names from code
function\s+(\w+)\s*\(      # JavaScript
def\s+(\w+)\s*\(            # Python
func\s+(\w+)\s*\(           # Go

# Log level extraction
\b(DEBUG|INFO|WARN|ERROR|FATAL)\b

# JSON key-value extraction
"(\w+)"\s*:\s*"([^"]*)"

# Find TODO/FIXME comments
(TODO|FIXME|HACK|XXX|BUG)(\([^)]*\))?:?\s*(.*)
```

### Regex in Daily Tools

```bash
# ripgrep (rg) — search code
rg 'TODO\(.*\):' --type ts            # Find TODOs in TypeScript
rg 'console\.(log|warn|error)' src/   # Find console statements
rg 'password|secret|token' --type-not test  # Find potential secrets

# sed — find and replace
sed -E 's/oldFunc\(/newFunc(/g' file.ts          # Rename function
sed -E 's/([0-9]+)px/\1rem/g' styles.css         # px to rem (sort of)
sed -E '/^\s*\/\//d' file.ts                       # Remove comment lines

# grep in log analysis
grep -oP 'duration=\K[0-9.]+' access.log | sort -n | tail -20  # Top 20 slowest
grep -cP 'status=(4|5)\d\d' access.log            # Count 4xx/5xx errors

# VS Code search (supports regex)
# Ctrl+Shift+F → enable regex (.*) → search across project
# Find: import .* from ['"]\.\./
# → finds all relative imports

# PostgreSQL
SELECT * FROM logs WHERE message ~ 'error.*timeout';
SELECT regexp_matches(url, '/api/v(\d+)/(\w+)', 'g') FROM requests;
```

### Catastrophic Backtracking (The Regex That Kills Your Server)

This one is important enough to memorize. Catastrophic backtracking is not a theoretical concern — it caused the Cloudflare outage (Ch 26) that knocked a significant chunk of the internet offline. A single poorly-crafted regex in a hot path can take a server from 5% CPU to 100% with a single specific input string.

```
# DANGEROUS: nested quantifiers with overlapping matches
(a+)+$          # Exponential backtracking on "aaaaaaaaaaaaaaab"
(a|a)+$         # Same problem
(.*a){10}       # Terrible on strings without 'a'

# Why: the regex engine tries every possible way to match
# For "aaaaab" with (a+)+$: tries a+a+a+a+a, then a+a+a+aa, then a+a+aa+a, ...
# Each additional 'a' doubles the attempts

# SAFE alternatives:
a+$             # Remove nesting
[^a]*a          # Be specific about what you're matching
(?:a+)$         # Atomic group (if supported) prevents backtracking

# PROTECTION:
# - Use RE2 (Google's regex engine) — guarantees linear time, no backtracking
# - Set timeout on regex execution
# - Avoid user-supplied regex in production (or sandbox with RE2)
# - The Cloudflare outage (Ch 26) was caused by catastrophic backtracking
```

### Regex Debugging
- **regex101.com**: THE tool for building and testing regex (shows match groups, explains each part, tests against multiple inputs, supports multiple flavors)
- **VS Code regex search**: test patterns in real-time across your codebase
- Named capture groups make regex self-documenting:
  ```
  (?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})
  ```

### Common Gotchas
- Greedy vs lazy: `<.*>` matches `<b>bold</b>` as ONE match. Use `<.*?>` for shortest match.
- `^` and `$` in multiline: by default match start/end of STRING. Use `m` flag for line-by-line.
- Escape special characters in literals: `.` matches ANY char. Use `\.` for a literal dot.
- Different regex flavors: JavaScript, Python, Go (RE2), PCRE have different feature sets. Check what your tool supports.
- Don't use regex for HTML parsing. Use a proper parser (cheerio, Beautiful Soup). "You can't parse HTML with regex" is a famous Stack Overflow answer for a reason.

---

## QUICK REFERENCE: The Commands You Will Use Daily

| Task | Command |
|---|---|
| Find what is using a port | `lsof -i :3000` or `ss -tlnp \| grep 3000` |
| Search code fast | `rg "pattern" --type ts` |
| Find files | `fd "pattern"` |
| Fuzzy history search | `Ctrl+R` (with fzf installed) |
| Quick JSON formatting | `curl ... \| jq .` |
| Check disk space | `df -h` then `ncdu /` |
| Watch logs | `tail -f /var/log/app.log` or `journalctl -u app -f` |
| Docker cleanup | `docker system prune -af --volumes` |
| Git undo last commit | `git reset --soft HEAD~1` |
| Git find breaking commit | `git bisect start && git bisect bad && git bisect good v1.0` |
| K8s debug pod | `kubectl describe pod X` then `kubectl logs X --previous` |
| K8s multi-pod logs | `stern "api"` |
| SSH tunnel to DB | `ssh -L 5432:db.internal:5432 bastion` |
| Terraform preview | `terraform plan -out=tfplan` |
| Process tree | `ps auxf` or `htop` (F5 for tree) |

---

> **The meta-lesson:** Tools are multipliers. Spending 30 minutes learning a tool you use daily saves hundreds of hours per year. The commands in this chapter are not trivia — they are the difference between spending 10 minutes or 10 seconds on a task you do 20 times a day. Go set up your shell, configure your editor, tune your `.gitconfig`. Then pair all of this with Claude Code (Ch 17) running in your terminal and the full Beast Mode toolchain (Ch 36), and you'll have a development environment that most engineers have never experienced. Once you've worked that way, you can't go back.

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M01: Course Setup & TicketPulse Kickoff](../course/modules/loop-1/L1-M01-course-setup-ticketpulse-kickoff.md)** — Wire up the full local development environment from scratch, including shell, editor, and Docker
- **[L1-M02: Your Dev Environment](../course/modules/loop-1/L1-M02-your-dev-environment.md)** — Configure your terminal, dotfiles, and editor extensions for maximum leverage
- **[L1-M03: Git Beyond the Basics](../course/modules/loop-1/L1-M03-git-beyond-the-basics.md)** — Interactive rebase, bisect, worktrees, and the git workflows that senior engineers use daily

### Quick Exercises

1. **Time yourself finding a function definition with and without fzf/ripgrep** — pick any function in a codebase you know, find it with `grep -r`, then find it again with `rg` or `fzf`. Note the difference in keystrokes and seconds.
2. **Set up 3 git aliases that save you keystrokes daily** — candidates: `git st` for status, `git co` for checkout, `git lg` for a one-line log. Add them to your `.gitconfig` and commit to using them for a week.
3. **Learn 5 new Vim motions or VS Code shortcuts this week** — pick from the tables in this chapter, add them to a sticky note on your monitor, and practice until they're muscle memory.

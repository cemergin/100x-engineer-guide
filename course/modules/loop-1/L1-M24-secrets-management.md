# L1-M24: Secrets Management

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 45 min | 🟢 Core | Prerequisites: L1-M23 (OWASP Top 10)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

Right now, TicketPulse has secrets sprinkled throughout the codebase:

```typescript
// src/config/database.ts
const pool = new Pool({
  host: 'localhost',
  port: 5432,
  user: 'ticketpulse',
  password: 'tiger123',     // Hardcoded password in source code
  database: 'ticketpulse',
});
```

```typescript
// src/middleware/authenticate.ts
const decoded = jwt.verify(token, 'super-secret-jwt-key-12345');  // Hardcoded JWT secret
```

```typescript
// src/config/redis.ts
const redis = new Redis({
  host: 'localhost',
  port: 6379,
  password: 'redis-pass-2024',  // Hardcoded Redis password
});
```

If this code is pushed to a public GitHub repo -- or even a private repo that gets compromised -- every secret is exposed. An attacker gets your database password, your JWT signing key, your Redis credentials. Game over.

By the end of this module, zero secrets will live in source code. The application will validate its configuration at startup and crash immediately with a clear error message if anything is missing.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

First, let us see the damage. Search the codebase for hardcoded secrets:

```bash
cd ticketpulse

# Search for password-like strings in the source
grep -rn "password\|secret\|api_key\|apiKey\|token.*=.*'" src/ --include="*.ts"
```

Count how many hardcoded secrets you find. Write down the number. This is your "secret debt."

> **Insight:** In 2022, Toyota leaked 296,000 customer email addresses because an access key was accidentally committed to a public GitHub repository. The key had been exposed for five years. GitHub scans for secrets in public repos and finds millions every year.

---

## 1. Build: Extract Secrets to .env

### 1.1 Create the .env File

```bash
# Create .env in the project root (this file should NEVER be committed)
cat > .env << 'EOF'
# TicketPulse Environment Configuration
# Copy this to .env and fill in the values
# NEVER commit .env to version control

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=ticketpulse
DATABASE_PASSWORD=tiger123
DATABASE_NAME=ticketpulse

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis-pass-2024

# Authentication
JWT_SECRET=change-me-to-a-random-64-char-string
JWT_EXPIRY=15m
REFRESH_TOKEN_EXPIRY=7d

# Application
NODE_ENV=development
PORT=3000
LOG_LEVEL=debug

# CSRF
CSRF_SECRET=change-me-to-another-random-string

# External Services (add as needed)
# SENDGRID_API_KEY=
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
EOF
```

### 1.2 Create .env.example

This file documents what environment variables are required without revealing actual values. It IS committed to version control.

```bash
cat > .env.example << 'EOF'
# TicketPulse Environment Configuration
# Copy this file to .env and fill in actual values:
#   cp .env.example .env

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=ticketpulse
DATABASE_PASSWORD=         # Required. Your Postgres password.
DATABASE_NAME=ticketpulse

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=            # Required. Your Redis password.

# Authentication
JWT_SECRET=                # Required. Generate with: openssl rand -hex 32
JWT_EXPIRY=15m
REFRESH_TOKEN_EXPIRY=7d

# Application
NODE_ENV=development
PORT=3000
LOG_LEVEL=debug

# CSRF
CSRF_SECRET=               # Required. Generate with: openssl rand -hex 32

# External Services
# SENDGRID_API_KEY=        # Optional in dev. Required in production.
# STRIPE_SECRET_KEY=       # Optional in dev. Required in production.
# STRIPE_WEBHOOK_SECRET=   # Optional in dev. Required in production.
EOF
```

### 1.3 Add .env to .gitignore

```bash
# Check if .env is already in .gitignore
grep -q "^\.env$" .gitignore 2>/dev/null || echo ".env" >> .gitignore

# Also ignore other secret-containing files
cat >> .gitignore << 'EOF'

# Environment secrets
.env
.env.local
.env.production
.env.*.local

# Never commit these
*.pem
*.key
credentials.json
EOF
```

Verify it is ignored:

```bash
git status
# .env should NOT appear in untracked files
# .env.example SHOULD appear (it's safe to commit)
```

### 1.4 Update the Code to Use Environment Variables

Replace every hardcoded secret:

```typescript
// src/config/database.ts -- AFTER

import { env } from './environment';

const pool = new Pool({
  host: env.DATABASE_HOST,
  port: env.DATABASE_PORT,
  user: env.DATABASE_USER,
  password: env.DATABASE_PASSWORD,
  database: env.DATABASE_NAME,
});
```

```typescript
// src/middleware/authenticate.ts -- AFTER

import { env } from '../config/environment';

const decoded = jwt.verify(token, env.JWT_SECRET);
```

```typescript
// src/config/redis.ts -- AFTER

import { env } from './environment';

const redis = new Redis({
  host: env.REDIS_HOST,
  port: env.REDIS_PORT,
  password: env.REDIS_PASSWORD,
});
```

No more hardcoded secrets. Every secret comes from the environment.

---

## 2. Build: Startup Validation with Zod

The worst thing that can happen with environment variables is discovering they are missing at runtime -- halfway through a user's purchase, your app crashes because `JWT_SECRET` is undefined. That is a terrible user experience and a terrible debugging experience.

The solution: **validate all required environment variables at startup.** If anything is missing, the application refuses to start and tells you exactly what is wrong.

### 2.1 Install Zod

```bash
npm install zod dotenv
```

### 2.2 Create the Environment Validator

```typescript
// src/config/environment.ts

import { z } from 'zod';
import dotenv from 'dotenv';
import path from 'path';

// Load .env file in development
if (process.env.NODE_ENV !== 'production') {
  dotenv.config({ path: path.resolve(process.cwd(), '.env') });
}

// Define the schema for ALL required environment variables.
// This is the single source of truth for what your app needs to run.
const envSchema = z.object({
  // Database
  DATABASE_HOST: z.string().min(1, 'DATABASE_HOST is required'),
  DATABASE_PORT: z.coerce.number().int().positive().default(5432),
  DATABASE_USER: z.string().min(1, 'DATABASE_USER is required'),
  DATABASE_PASSWORD: z.string().min(1, 'DATABASE_PASSWORD is required'),
  DATABASE_NAME: z.string().min(1, 'DATABASE_NAME is required'),

  // Redis
  REDIS_HOST: z.string().min(1).default('localhost'),
  REDIS_PORT: z.coerce.number().int().positive().default(6379),
  REDIS_PASSWORD: z.string().min(1, 'REDIS_PASSWORD is required'),

  // Authentication
  JWT_SECRET: z
    .string()
    .min(32, 'JWT_SECRET must be at least 32 characters for security'),
  JWT_EXPIRY: z.string().default('15m'),
  REFRESH_TOKEN_EXPIRY: z.string().default('7d'),

  // Application
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().default(3000),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  // CSRF
  CSRF_SECRET: z.string().min(16, 'CSRF_SECRET must be at least 16 characters'),

  // External Services (optional in dev, required in production)
  SENDGRID_API_KEY: z.string().optional(),
  STRIPE_SECRET_KEY: z.string().optional(),
  STRIPE_WEBHOOK_SECRET: z.string().optional(),
});

// Parse and validate. This runs at import time (module load).
const parsed = envSchema.safeParse(process.env);

if (!parsed.success) {
  console.error('');
  console.error('========================================');
  console.error('  ENVIRONMENT VALIDATION FAILED');
  console.error('========================================');
  console.error('');
  console.error('The following environment variables are missing or invalid:');
  console.error('');

  for (const issue of parsed.error.issues) {
    console.error(`  ${issue.path.join('.')}: ${issue.message}`);
  }

  console.error('');
  console.error('Copy .env.example to .env and fill in the values:');
  console.error('  cp .env.example .env');
  console.error('');
  console.error('========================================');
  process.exit(1);
}

// Export the validated, typed environment object.
// Every property is guaranteed to exist and have the correct type.
export const env = parsed.data;

// TypeScript knows the exact shape:
// env.DATABASE_HOST  -> string (guaranteed non-empty)
// env.DATABASE_PORT  -> number (guaranteed positive integer)
// env.NODE_ENV       -> 'development' | 'test' | 'production'
```

### 2.3 How It Works

The critical line is `process.exit(1)`. If validation fails, the application **stops immediately** with a clear error message. It does not start the HTTP server. It does not accept connections. It does not half-work and then crash later when someone tries to authenticate.

This is the principle: **fail fast, fail loud.** A clear error at startup is infinitely better than a cryptic crash at 3 AM when a user tries to buy a ticket.

---

## 3. Try It: Remove a Required Variable

Let us see what happens when a variable is missing:

```bash
# Temporarily remove JWT_SECRET from .env
# (Save the original first)
cp .env .env.backup
grep -v "JWT_SECRET" .env > .env.tmp && mv .env.tmp .env

# Try to start the app
npm run dev
```

You should see:

```
========================================
  ENVIRONMENT VALIDATION FAILED
========================================

The following environment variables are missing or invalid:

  JWT_SECRET: JWT_SECRET must be at least 32 characters for security

Copy .env.example to .env and fill in the values:
  cp .env.example .env

========================================
```

The app refuses to start. No ambiguity. No guessing. Restore the backup:

```bash
mv .env.backup .env
npm run dev
# App starts normally
```

> **Reflect:** Without startup validation, what would happen if JWT_SECRET was missing? The app would start fine. Users could browse events. But the first person who tried to log in would get a cryptic `jwt.verify` error. You would not find out until a user complains -- or worse, you would find out from an error monitoring tool at 2 AM.

---

## 4. Build: Production-Specific Validation

Some variables are optional in development but required in production. Add conditional validation:

```typescript
// Add to src/config/environment.ts after the base validation

// Additional production checks
if (parsed.data.NODE_ENV === 'production') {
  const productionRequired = {
    SENDGRID_API_KEY: parsed.data.SENDGRID_API_KEY,
    STRIPE_SECRET_KEY: parsed.data.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET: parsed.data.STRIPE_WEBHOOK_SECRET,
  };

  const missing = Object.entries(productionRequired)
    .filter(([, value]) => !value)
    .map(([key]) => key);

  if (missing.length > 0) {
    console.error('');
    console.error('========================================');
    console.error('  PRODUCTION ENVIRONMENT INCOMPLETE');
    console.error('========================================');
    console.error('');
    console.error('The following variables are required in production:');
    missing.forEach((key) => console.error(`  - ${key}`));
    console.error('');
    console.error('========================================');
    process.exit(1);
  }

  // Warn about insecure defaults
  if (parsed.data.JWT_SECRET.includes('change-me') || parsed.data.JWT_SECRET.length < 64) {
    console.error('FATAL: JWT_SECRET appears to be a default/weak value. Generate a proper secret:');
    console.error('  openssl rand -hex 32');
    process.exit(1);
  }
}
```

---

## 5. direnv: Automatic Environment Activation

Typing `source .env` every time you open a terminal is tedious and error-prone. direnv automatically loads environment variables when you `cd` into a project directory.

### 5.1 Install direnv

```bash
# macOS
brew install direnv

# Linux
curl -sfL https://direnv.net/install.sh | bash
```

Add the hook to your shell:

```bash
# For zsh (add to ~/.zshrc)
eval "$(direnv hook zsh)"

# For bash (add to ~/.bashrc)
eval "$(direnv hook bash)"
```

Restart your shell or `source ~/.zshrc`.

### 5.2 Create .envrc

```bash
# .envrc -- in the project root
# This file IS committed to version control (it does not contain secrets)

# Load .env if it exists
dotenv_if_exists .env

# Set project-specific paths
export PATH="$PWD/node_modules/.bin:$PATH"

# Optional: use specific Node version (if using mise/nvm)
# use mise
# use nvm
```

Allow direnv for this directory:

```bash
direnv allow
```

### 5.3 Try It

```bash
# Leave the project directory
cd ~

# Check: the env vars should NOT be set
echo $DATABASE_HOST
# (empty)

# Enter the project directory
cd ~/ticketpulse
# direnv: loading ~/ticketpulse/.envrc
# direnv: export +DATABASE_HOST +DATABASE_PASSWORD +DATABASE_PORT ...

# Check: the env vars ARE now set
echo $DATABASE_HOST
# localhost
```

Environment variables load automatically when you enter the directory and unload when you leave. No manual sourcing. No forgetting.

---

## 6. Generating Strong Secrets

Never use passwords like `tiger123`. Generate cryptographically random secrets:

```bash
# Generate a 32-byte hex string (64 characters) -- good for JWT secrets
openssl rand -hex 32
# Example: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2

# Generate a base64 string -- good for API keys
openssl rand -base64 32
# Example: kR7zQ2xVnJmF5tG8hL3pWsY9cA0dBvE6iN1oMuP4qT=

# Generate a UUID -- good for CSRF secrets
uuidgen
# Example: 550e8400-e29b-41d4-a716-446655440000
```

Update your `.env` with real secrets:

```bash
# Generate and set all secrets at once
cat >> .env << EOF
JWT_SECRET=$(openssl rand -hex 32)
CSRF_SECRET=$(openssl rand -hex 16)
EOF
```

---

## 7. Docker Compose: Secrets in Containers

Update docker-compose.yml to pass environment variables to containers:

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    env_file:
      - .env              # Load all vars from .env
    environment:
      - NODE_ENV=development  # Override specific vars
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DATABASE_USER}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_DB: ${DATABASE_NAME}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

The `${VARIABLE}` syntax reads from the `.env` file in the same directory as `docker-compose.yml`. The secrets live in one place and are injected into each container at runtime.

---

## 8. The Secret Lifecycle

Here is how secrets should flow through your environments:

```
Development:    .env file (local, gitignored)
                ↓
CI/CD:          GitHub Secrets / GitLab CI Variables (encrypted at rest)
                ↓
Staging:        Cloud secret manager (AWS Secrets Manager, GCP Secret Manager)
                ↓
Production:     Cloud secret manager + automatic rotation
```

At no point in this chain does a secret exist in source code.

For production deployments (beyond this module but worth knowing):
- **AWS Secrets Manager**: Stores and auto-rotates secrets. Your app fetches them at startup.
- **HashiCorp Vault**: Self-hosted secret management. Dynamic credentials that expire automatically.
- **Kubernetes Secrets**: Base64-encoded (not encrypted by default). Use Sealed Secrets or External Secrets Operator for real security.

---

## 9. Checkpoint

Before continuing to the next module, verify:

- [ ] No hardcoded secrets remain in the TicketPulse source code (`grep` returns nothing)
- [ ] `.env` exists with all required variables and is in `.gitignore`
- [ ] `.env.example` exists with placeholder values and IS tracked in git
- [ ] Startup validation works -- removing a variable prevents the app from starting
- [ ] The error message clearly states which variable is missing
- [ ] direnv loads environment variables automatically when you `cd` into the project

```bash
# Final check: no secrets in source code
grep -rn "tiger123\|super-secret\|redis-pass" src/ --include="*.ts"
# Expected: no results

# Verify .env is gitignored
git status | grep ".env"
# .env should NOT appear in untracked files
```

> **Insight:** The rule is simple: if a value would be different between environments (dev vs staging vs production), it belongs in an environment variable. If a value would be dangerous in the wrong hands, it belongs in a secret manager. TicketPulse's database password is both.

---

## What's Next

TicketPulse currently uses `console.log` for everything. When something goes wrong in production, you have no way to trace a request through the system. The next module introduces structured logging and request tracing.

## Key Terms

| Term | Definition |
|------|-----------|
| **Environment variable** | A key-value pair set outside the application code that configures behavior at runtime. |
| **.env** | A file that stores environment variables locally for development, typically excluded from version control. |
| **Secret** | A sensitive value (such as an API key, password, or token) that must be protected from unauthorized access. |
| **Config** | Non-secret application settings (like feature flags or URLs) that vary between environments. |
| **dotenv** | A library that loads environment variables from a .env file into the application's runtime environment. |

<!--
  CHAPTER: 35
  TITLE: Everything as Code
  PART: IV — Cloud & Operations
  PREREQS: Chapter 7 (DevOps/IaC basics), Chapter 5 (security)
  KEY_TOPICS: policy-as-code, secrets management as code, database migrations as code, observability as code, compliance as code, configuration management, IaC testing, GitOps, environment promotion, platform abstractions, Crossplane, Backstage
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-31
-->

# Chapter 35: Everything as Code

> **Part IV — Cloud & Operations** | Prerequisites: Chapter 7, Chapter 5 | Difficulty: Intermediate → Advanced

Chapter 7 showed you the foundation: Terraform for infrastructure, GitHub Actions for CI/CD, containers for everything. That was the beginning. This chapter is the endgame — where you codify *everything* that affects production. Policies. Secrets. Database schemas. Alert thresholds. Compliance controls. The platforms that your entire organization builds on. If it's not in Git, it doesn't exist.

The thesis is simple and it's one you'll never be able to unlearn: **if a decision affects production, it belongs in a reviewed, versioned, tested file.** No exceptions. No "I'll document it later." No "it's just a quick change in the console."

### In This Chapter
- The "Everything as Code" Philosophy
- Policy as Code
- Secrets Management as Code
- Database Migrations as Code
- Observability as Code
- Compliance & Supply Chain as Code
- Configuration Management
- IaC Testing & Validation
- GitOps & Environment Promotion
- Platform Abstractions

### Related Chapters
- Chapter 7 (Terraform, containers, K8s, CI/CD — the foundation this chapter extends)
- Chapter 5 (security engineering — secrets, compliance)
- Chapter 18 (monitoring tools — this chapter codifies their configuration)
- Chapter 20 (dependency/env management — Nix, reproducible builds)
- Chapter 33 (GitHub Actions — CI/CD pipelines as code)
- Chapter 34 (spec-driven development — specs as code)

---

## 1. THE "EVERYTHING AS CODE" PHILOSOPHY

### Why Codify Everything?

Here is a story you have lived or will live. It is 2 AM. Something is broken in production. You are staring at a Grafana dashboard that was hand-crafted by a senior engineer who left six months ago. The alert that fired references a threshold of 150ms — why 150? Nobody knows. You open the Terraform state and discover that the database security group has an inbound rule allowing traffic from `0.0.0.0/0`. When was that added? Who approved it? The `git log` shows nothing, because it was clicked in the AWS console during "a quick fix" eleven months ago.

This is what invisible state costs you. Not just at 2 AM. Every day, in every planning meeting where someone says "we think the database has these columns," in every audit where a compliance officer asks for evidence of your access controls and you start screenshotting the AWS console. The invisible state accumulates until it becomes the biggest risk in your organization.

The "everything as code" philosophy eliminates invisible state:

| Without Code | With Code |
|---|---|
| "Someone configured the firewall rule last year" | `firewall.tf` reviewed in PR #342 |
| "The staging alert thresholds are different because..." | `alerts/staging.yaml` shows exactly why |
| "We think the database has these columns" | `migrations/V42__add_priority.sql` is the source of truth |
| "The compliance auditor needs screenshots" | `inspec/cis-benchmark.rb` runs continuously |
| "Only Sarah knows how to set up a new environment" | `terragrunt.hcl` + `make new-env` |

When you achieve everything-as-code, the answer to nearly every question about your production system is: `git log --all --grep="your question"`. That is engineering maturity.

### The Five Properties

Everything-as-code delivers five properties that no UI-driven workflow can match:

1. **Reviewable** — changes go through pull requests. A second pair of eyes catches "allow all traffic from 0.0.0.0/0." This is security-as-process: see Chapter 5 for why this matters at the policy layer.
2. **Auditable** — `git log` tells you who changed what, when, and why. Compliance teams love this. So do post-incident reviews.
3. **Reproducible** — the same code produces the same result. No "works in staging but not production." No snowflake servers with undocumented configuration.
4. **Testable** — you can validate configurations before they hit production (policy checks, linting, dry runs). If it is code, it can have tests.
5. **Recoverable** — rollback is `git revert`. Disaster recovery is `terraform apply` from a clean state. You rehearse recovery by running it in CI.

These five properties compound. Reviewability catches bugs before they reach production. Auditability means you can trace every bug back to its source. Reproducibility means your disaster recovery actually works when you need it. Together, they define the difference between a team that runs on luck and a team that runs on systems.

### The Spectrum

Not everything needs the same rigor. Here is a practical spectrum:

```
Must be code (day 1):
  ├── Infrastructure (Terraform, Pulumi, CDK)
  ├── CI/CD pipelines (GitHub Actions, etc.)
  ├── Database schema (migrations)
  └── Application config (env vars, feature flags)

Should be code (before you hit 10 engineers):
  ├── Monitoring & alerting rules
  ├── Security policies & firewall rules
  ├── Secret rotation config
  └── Deployment promotion rules

Nice to have as code (staff+ territory):
  ├── Compliance controls
  ├── Cost policies
  ├── Platform abstractions (golden paths)
  └── Incident response runbooks
```

The day-1 list is non-negotiable. A team of two deserves version-controlled infrastructure. The rest is a journey — but it is a journey with a clear destination. By the time you are reading the "staff+ territory" section and thinking "that sounds like exactly what we need," you are ready for it.

### The GitOps Transformation Story

There is a pattern you see again and again in engineering organizations. A team starts scrappy — clicking around in the AWS console, copy-pasting secrets into environment variables, editing Grafana dashboards live during incidents. It works, until it doesn't. The inflection point comes during a major incident or a failed audit or a compliance review where nobody can answer basic questions about the system's state. The team emerges from that moment with a mandate: codify everything.

Teams that go through this transformation describe it as a before/after moment. Before: three-hour AWS console sessions to onboard a new environment. After: `make new-env` and a coffee break. Before: "only Marcus knows how the staging database is configured." After: Marcus leaves and nobody panics because the knowledge lives in a Git repository, not in his head. Before: a compliance audit requires weeks of screenshot-gathering. After: `inspec exec cis-aws-foundations` and a generated report.

The transformation is not instant, and it is not free. But every team that completes it says the same thing: they wish they had started sooner.

---

## 2. POLICY AS CODE

Policy as code treats governance rules, security guardrails, and compliance requirements as version-controlled code that is evaluated automatically — at plan time, admission time, or in CI. This is where Chapter 5's security principles become operational. Instead of a security review that happens once a quarter, your security policies are running on every pull request, every deploy, every resource creation.

### The Layered Approach

The most effective organizations layer policy enforcement at four levels:

```
Layer 4: Cloud-Native Guardrails (SCPs, Azure Policy)
         Hardest controls. Cannot be bypassed by developers.
         Use for: region restrictions, disabling dangerous services,
         mandatory encryption.

Layer 3: Runtime Admission Control (OPA/Gatekeeper, Kyverno)
         Evaluates resources at deploy time in Kubernetes.
         Use for: pod security, resource limits, label requirements.

Layer 2: CI/CD Pipeline Scanning (Checkov, Trivy, conftest)
         Catches issues before they reach production.
         Use for: Terraform misconfigs, Docker vulnerabilities,
         compliance checks.

Layer 1: Developer Workstation (Trivy pre-commit, IDE plugins)
         Fastest feedback loop.
         Use for: immediate security feedback as you write code.
```

The goal is to catch policy violations at the **earliest possible layer**. A violation caught at layer 1, on the developer's laptop, costs two seconds. The same violation caught at layer 4 — if it somehow gets there — costs a production incident. Shift left is not just a slogan; it is an economics argument.

Each layer is codified. SCPs live as JSON files in your AWS Organizations module (see the Terraform example below). Kyverno policies are YAML files in your infrastructure repo. Checkov runs in your GitHub Actions workflow (see Chapter 33 for the workflow plumbing). Your security posture becomes a diff on a pull request.

### Open Policy Agent (OPA)

OPA is the general-purpose, open-source policy engine (CNCF Graduated). You write policies in **Rego** — a declarative query language designed for nested JSON/YAML — and OPA evaluates structured data against them.

**Core use cases:**
- Kubernetes admission control (via **Gatekeeper**)
- Terraform plan validation (via **conftest**)
- API authorization (as a sidecar or centralized service)

**Example: deny Kubernetes pods running as root:**

```rego
package kubernetes.admission

import rego.v1

deny contains msg if {
    input.request.kind.kind == "Pod"
    some container in input.request.object.spec.containers
    container.securityContext.runAsUser == 0
    msg := sprintf("Container '%s' must not run as root (UID 0)", [container.name])
}
```

This policy is not a one-time audit. It runs on every `kubectl apply`. Write a Deployment manifest that sets `runAsUser: 0` and the cluster refuses it. The security policy is now a hard constraint, not a guideline you hope developers remember.

**Example: require tags on Terraform resources (for conftest):**

```rego
package terraform.plan

import rego.v1

required_tags := {"Environment", "Owner", "CostCenter"}

deny contains msg if {
    some resource in input.resource_changes
    resource.type == "aws_instance"
    tags := object.get(resource.change.after, "tags", {})
    missing := required_tags - {key | some key, _ in tags}
    count(missing) > 0
    msg := sprintf("aws_instance '%s' missing required tags: %v",
                   [resource.name, missing])
}
```

**Running conftest against a Terraform plan:**

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
conftest test tfplan.json --policy policy/
```

Add this to your GitHub Actions workflow (the one you built in Chapter 33) and tagging compliance becomes automatic. No more manually auditing the AWS Cost Explorer trying to figure out who owns that mystery EC2 instance.

### Kyverno (Kubernetes-Native)

Unlike OPA (which requires learning Rego), Kyverno policies are pure YAML — Kubernetes custom resources. It can **validate**, **mutate**, and **generate** resources. That generate capability is where the magic is: Kyverno does not just block bad things, it creates good things automatically.

**Example: require labels on all pods:**

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: Enforce   # or Audit for gradual rollout
  rules:
    - name: require-team-label
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "The label 'team' is required."
        pattern:
          metadata:
            labels:
              team: "?*"
```

Start with `validationFailureAction: Audit` when rolling this out. You will probably discover that half your existing pods would fail the validation. Fix them progressively, then flip to `Enforce`. This is the gradual rollout pattern for policy-as-code — never YOLO a hard block into production without an audit phase first.

**Example: auto-generate NetworkPolicy for new namespaces:**

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: default-network-policy
spec:
  rules:
    - name: generate-default-deny
      match:
        any:
          - resources:
              kinds:
                - Namespace
      generate:
        apiVersion: networking.k8s.io/v1
        kind: NetworkPolicy
        name: default-deny-ingress
        namespace: "{{request.object.metadata.name}}"
        data:
          spec:
            podSelector: {}
            policyTypes:
              - Ingress
```

Every new namespace gets a default-deny NetworkPolicy automatically. This is security-by-default: you do not have to remember to create the NetworkPolicy, and you do not have to trust that every developer will. The policy generates the control. This is what policy-as-code enables at the infrastructure layer.

### Checkov (Multi-Framework Static Analysis)

Checkov scans Terraform, CloudFormation, Kubernetes manifests, Helm charts, and Dockerfiles against 1,000+ built-in policies (CIS, SOC2, HIPAA, PCI-DSS). It is the broadest pre-commit, pre-deploy net you can throw.

```bash
# Scan a Terraform directory
checkov -d ./terraform/

# Scan Terraform plan (catches dynamic values)
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
checkov -f tfplan.json

# Skip specific checks
checkov -d ./terraform/ --skip-check CKV_AWS_18,CKV_AWS_19

# Output for CI (JUnit XML)
checkov -d ./terraform/ -o junitxml > checkov-results.xml
```

**Custom policy (YAML — no Python needed):**

```yaml
metadata:
  id: "CKV2_CUSTOM_1"
  name: "Ensure RDS instances are not publicly accessible"
  category: "NETWORKING"
definition:
  cond_type: "attribute"
  resource_types:
    - "aws_db_instance"
  attribute: "publicly_accessible"
  operator: "is_false"
```

Custom policies let you encode your organization's specific requirements — things that CIS benchmarks do not cover, like your internal tagging convention or your VPC CIDR allocation scheme. Every custom policy you write is tribal knowledge extracted from human brains and put into a file that runs automatically.

### HashiCorp Sentinel

Sentinel is HashiCorp's proprietary policy framework embedded in Terraform Cloud/Enterprise. It evaluates policies between `terraform plan` and `terraform apply` with built-in enforcement levels.

```python
import "tfplan/v2" as tfplan

allowed_types = ["t3.micro", "t3.small", "t3.medium"]

ec2_instances = filter tfplan.resource_changes as _, rc {
    rc.type is "aws_instance" and
    (rc.change.actions contains "create" or rc.change.actions contains "update")
}

main = rule {
    all ec2_instances as _, instance {
        instance.change.after.instance_type in allowed_types
    }
}
```

Enforcement levels: `advisory` (warn), `soft-mandatory` (override with approval), `hard-mandatory` (cannot override).

The `hard-mandatory` level is the right default for security-critical policies. Nobody should be able to deploy a production instance type not on the approved list without a code change to the policy itself — which goes through a pull request, which is reviewable, which is auditable. The enforcement is the policy.

### Cloud-Native Policy: AWS SCPs

Service Control Policies define the **maximum permissions** for all IAM entities in an AWS account. They cascade down the Organizations hierarchy and cannot be overridden — not by administrators, not by root users in the target accounts. This is Chapter 5's principle of least privilege at the organizational level.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyOutsideApprovedRegions",
      "Effect": "Deny",
      "NotAction": ["iam:*", "sts:*", "organizations:*", "support:*"],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
        }
      }
    }
  ]
}
```

Manage SCPs as code with Terraform:

```hcl
resource "aws_organizations_policy" "restrict_regions" {
  name    = "restrict-regions"
  type    = "SERVICE_CONTROL_POLICY"
  content = file("${path.module}/policies/restrict-regions.json")
}

resource "aws_organizations_policy_attachment" "production_ou" {
  policy_id = aws_organizations_policy.restrict_regions.id
  target_id = aws_organizations_organizational_unit.production.id
}
```

When this SCP is in Terraform, changing your approved regions requires a pull request. That pull request will have a reviewer. That reviewer will ask "why are we adding ap-southeast-1?" and somebody will have to answer. This is exactly the friction you want for decisions with large security implications.

### Decision Matrix: Policy Tools

| Scenario | Best Tool |
|---|---|
| Kubernetes admission, simple policies | **Kyverno** (YAML, easy adoption) |
| Kubernetes admission, complex logic | **OPA / Gatekeeper** (Rego) |
| Terraform policy in TF Cloud | **Sentinel** (native) or **OPA** (portable) |
| Multi-IaC security scanning in CI | **Checkov** (broadest coverage) |
| Fast local Terraform linting | **Trivy** (Go binary, formerly tfsec) |
| AWS account-level guardrails | **SCPs** (non-negotiable for multi-account) |
| Azure subscription guardrails | **Azure Policy** (auto-remediation support) |

---

## 3. SECRETS MANAGEMENT AS CODE

Secrets — database passwords, API keys, TLS certificates — are the most dangerous form of invisible state. Hardcoded in source, pasted into UIs, shared in Slack: every shortcut becomes a future breach. Chapter 5 covers the security principles. This section covers the operational mechanics of making secrets management itself a code-driven, reviewable, auditable process.

Here is the pattern you should be terrified of: a developer creates an API key in the AWS console. They paste it into a GitHub Actions secret. They also paste it into their local `.env` file. That `.env` gets committed accidentally six months later, or the GitHub Actions secret rotates and nobody knows the procedure, or the developer leaves and the key is never revoked. The key lives forever, in how many places? Nobody knows. This is not a security horror story. This is Tuesday.

The hierarchy below is not theoretical. It describes a migration path. You can move up the levels as your team matures.

### The Hierarchy of Secrets Management

```
Level 0: Hardcoded in source code         ← breach waiting to happen
Level 1: .env files in .gitignore          ← better, but no rotation, no audit
Level 2: Cloud secret stores (AWS SM, GCP SM) ← good, but manual management
Level 3: Dynamic secrets (Vault)           ← best: short-lived, auto-rotated
Level 4: Workload identity (OIDC, IRSA)   ← no secrets at all
```

Level 4 is the endgame: your workload authenticates to AWS using its Kubernetes service account identity (IRSA) or GitHub Actions OIDC token (see Chapter 33). There are no credentials to rotate, no secrets to manage, no `.env` files to accidentally commit. The cloud provider verifies the identity claim cryptographically. You get there by building up through levels 2 and 3.

### HashiCorp Vault

Vault is the most comprehensive secrets management platform. Key concepts:

- **Secrets engines** generate or store secrets (KV, database, PKI, transit)
- **Auth methods** authenticate clients (Kubernetes, OIDC, AWS IAM, AppRole)
- **Policies** control access (HCL, path-based)
- **Dynamic secrets** are generated on-demand with automatic TTL and revocation

**Example: dynamic database credentials**

```hcl
# Configure the database secrets engine
resource "vault_database_secret_backend_connection" "postgres" {
  backend       = "database"
  name          = "ticketpulse"
  allowed_roles = ["app-readonly", "app-readwrite"]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@db:5432/ticketpulse"
  }
}

resource "vault_database_secret_backend_role" "app_readonly" {
  backend = "database"
  name    = "app-readonly"
  db_name = vault_database_secret_backend_connection.postgres.name

  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";"
  ]

  default_ttl = "1h"
  max_ttl     = "24h"
}
```

An application requests credentials from Vault, receives a username/password valid for 1 hour, and Vault automatically revokes them on expiry. No long-lived database passwords exist. A compromised credential is useless after an hour. Your blast radius for any secret compromise drops from "potentially forever" to "at most 60 minutes." This is the operational realization of the security principles in Chapter 5.

**Vault policy (HCL):**

```hcl
# Allow the ticket-service to read its own secrets
path "secret/data/ticketpulse/ticket-service/*" {
  capabilities = ["read"]
}

# Allow database credential generation
path "database/creds/app-readonly" {
  capabilities = ["read"]
}

# Deny everything else (implicit)
```

This policy is in your infrastructure repo, reviewed alongside the service it protects. When a new secret path is needed, it requires a pull request. That pull request shows exactly what access is being granted. Principle of least privilege, enforced through code review.

### SOPS (Secrets OPerationS)

SOPS encrypts secret files with cloud KMS keys (AWS KMS, GCP KMS) or age/PGP, allowing encrypted secrets to live **in Git**. Only the values are encrypted; keys remain readable for easy diffing.

**`.sops.yaml` configuration:**

```yaml
creation_rules:
  - path_regex: \.env\.production$
    kms: "arn:aws:kms:us-east-1:123456789:key/abc-123"
  - path_regex: \.env\.staging$
    kms: "arn:aws:kms:us-east-1:123456789:key/def-456"
  - path_regex: \.env\.dev$
    age: "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p"
```

**Workflow:**

```bash
# Encrypt a file (in-place)
sops -e -i .env.production

# The file in Git looks like:
# DATABASE_URL=ENC[AES256_GCM,data:abc123...,type:str]
# API_KEY=ENC[AES256_GCM,data:def456...,type:str]

# Decrypt for use
sops -d .env.production > .env.local

# Edit encrypted file (decrypts in $EDITOR, re-encrypts on save)
sops .env.production
```

**Why SOPS over Vault?** SOPS is simpler — no server to run, no auth to configure. It is ideal for small teams, static secrets, and GitOps workflows where secrets travel with the code. Vault is better when you need dynamic secrets, rotation, or centralized access control.

The key insight with SOPS: your secrets are now in Git, with all the review and audit properties that implies. Changing `DATABASE_URL` requires a commit. That commit is attributable. When the compliance auditor asks "who had access to the production database credentials and when did they change?" you run `git log`.

### Sealed Secrets (Kubernetes)

Bitnami's Sealed Secrets lets you commit encrypted Kubernetes Secrets to Git. A controller in the cluster decrypts them.

```bash
# Encrypt a Secret into a SealedSecret
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# The SealedSecret is safe to commit — only the cluster can decrypt it
git add sealed-secret.yaml && git commit -m "Add database credentials"
```

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: database-credentials
  namespace: ticketpulse
spec:
  encryptedData:
    password: AgBy3i4OJSWK+PiTySYZZA9rO... # only the in-cluster controller can decrypt
    username: AgBu7wIEKpYFC8fjl+Q3vA0...
```

Sealed Secrets is the "secrets in Git" pattern for Kubernetes-native workflows. Your GitOps tool (ArgoCD or Flux — see section 9) syncs the SealedSecret to the cluster. The controller decrypts it. The Kubernetes Secret is never in Git, but the encrypted form that produces it is. Full GitOps, full auditability.

### External Secrets Operator (ESO)

ESO syncs secrets from external stores (Vault, AWS Secrets Manager, GCP Secret Manager) into Kubernetes Secrets. The cluster never stores the master secret — it pulls on demand.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: database-credentials
  data:
    - secretKey: password
      remoteRef:
        key: ticketpulse/database
        property: password
    - secretKey: username
      remoteRef:
        key: ticketpulse/database
        property: username
```

ESO is the bridge between "we have secrets in AWS Secrets Manager" and "we want to use them in Kubernetes without committing them to Git." The ExternalSecret definition is in Git — it describes *which* secret to pull, not the secret itself. When the secret rotates in AWS, ESO picks up the new value within `refreshInterval`. Your application gets fresh credentials without a redeploy.

### Decision Matrix: Secrets Tools

| Scenario | Best Tool |
|---|---|
| Dynamic secrets, credential rotation | **Vault** |
| Small team, secrets in Git (encrypted) | **SOPS** |
| Kubernetes + GitOps, no external store | **Sealed Secrets** |
| Kubernetes + existing cloud secret store | **External Secrets Operator** |
| AWS-native, no K8s | **AWS Secrets Manager** (rotation) or **SSM Parameter Store** (simple) |
| Zero-secret deployments | **Workload identity** (OIDC federation, IRSA, GKE Workload Identity) |

---

## 4. DATABASE MIGRATIONS AS CODE

Your database schema is as much "infrastructure" as your servers. Maybe more so — servers are ephemeral, but databases are stateful. They accumulate schema changes over years. They hold data that is often irreplaceable. Without versioned migrations, schema changes are invisible, unreviewable, and irreversible.

### Why Migrations Matter

Without migrations:
- Someone runs `ALTER TABLE` in production during a Zoom call
- Staging and production schemas silently drift
- New team members spend a day reverse-engineering the current schema
- Rolling back a deployment doesn't roll back the schema — data corruption ensues

With migrations:
- Every schema change is a versioned file in Git, reviewed in a PR
- `migrate up` produces the same schema everywhere: dev, CI, staging, production
- Rollback is `migrate down` (if you wrote the down migration)
- The migration history IS the schema documentation

That last point deserves emphasis. When you have a complete migration history, you can answer questions that would otherwise require archaeology: "When did we add the `priority` column to the tickets table? Who asked for it? What was the business reason?" The commit message on `V42__add_priority.sql` tells you. The PR it was merged from has the discussion. The schema change is documented, reviewed, and attributable — just like any other code.

### Approaches: Versioned vs Declarative

**Versioned (imperative):** You write ordered migration files. Each file is a diff (what to change). The tool tracks which migrations have been applied. Examples: Flyway, Alembic, golang-migrate, Django migrations.

```
migrations/
├── V001__create_users.sql          # CREATE TABLE users (...)
├── V002__add_email_to_users.sql    # ALTER TABLE users ADD COLUMN email ...
├── V003__create_events.sql         # CREATE TABLE events (...)
└── V004__add_index_on_email.sql    # CREATE INDEX idx_users_email ON users(email)
```

**Declarative (desired state):** You define the desired schema. The tool computes the diff and generates the migration. Examples: Atlas, Prisma Migrate, Drizzle Kit.

```prisma
// schema.prisma — the desired state
model User {
  id    Int     @id @default(autoincrement())
  email String  @unique
  name  String?
}
```

```bash
# Prisma computes the diff and generates the SQL migration
npx prisma migrate dev --name add-user-email
```

The declarative approach is conceptually the same leap as moving from imperative configuration scripts to Terraform's desired-state model. You describe what you want; the tool figures out how to get there. The trade-off: less control over the generated SQL, which matters for complex zero-downtime migrations.

### Tool Comparison

| Tool | Language | Approach | Rollback | Best For |
|---|---|---|---|---|
| **Flyway** | Java (runs anywhere) | Versioned SQL | Manual (V + U files) | JVM projects, enterprise |
| **Liquibase** | Java | Versioned (XML/YAML/SQL) | Automatic | Complex rollback needs |
| **Alembic** | Python | Versioned + autogenerate | Automatic (down) | Python/SQLAlchemy projects |
| **Prisma Migrate** | TypeScript | Declarative schema → SQL | Not built-in | TypeScript/Node.js projects |
| **Drizzle Kit** | TypeScript | Declarative schema → SQL | Manual | TypeScript, lightweight |
| **Atlas** | Go | Declarative + versioned | Planned | Schema-as-code, drift detection |
| **golang-migrate** | Go | Versioned SQL | Automatic (down) | Go projects, lightweight |
| **Django** | Python | Model-first, autogenerate | Automatic | Django projects |

### Flyway

The industry standard for JVM ecosystems. Migrations are SQL files with a naming convention:

```
V1__create_events_table.sql        # Versioned: runs once, in order
V2__add_ticket_price_column.sql
R__refresh_event_statistics.sql    # Repeatable: re-runs when checksum changes
```

```sql
-- V1__create_events_table.sql
CREATE TABLE events (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    venue       VARCHAR(255),
    event_date  TIMESTAMP NOT NULL,
    capacity    INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_date ON events(event_date);
```

```bash
# Apply all pending migrations
flyway -url=jdbc:postgresql://localhost/ticketpulse migrate

# Show migration status
flyway info

# Validate applied migrations haven't been tampered with
flyway validate
```

The `flyway validate` command is underappreciated. It checks that the checksums of applied migrations match what is in your codebase. If someone edited an applied migration file (a cardinal sin of versioned migrations), validation will catch it. Add this to your CI pipeline on every deploy.

### Atlas (Declarative Schema Management)

Atlas by Ariga takes a declarative approach — you define the desired schema in HCL or SQL, and Atlas computes the migration.

```hcl
# schema.hcl — desired state
schema "public" {}

table "users" {
  schema = schema.public
  column "id" {
    type = bigserial
  }
  column "email" {
    type = varchar(255)
    null = false
  }
  column "name" {
    type = varchar(255)
    null = true
  }
  primary_key {
    columns = [column.id]
  }
  index "idx_users_email" {
    columns = [column.email]
    unique  = true
  }
}
```

```bash
# Inspect current database schema
atlas schema inspect -u "postgres://localhost/ticketpulse"

# Compute diff between desired and actual schema
atlas schema diff \
  --from "postgres://localhost/ticketpulse" \
  --to "file://schema.hcl"

# Apply (with review)
atlas schema apply \
  --url "postgres://localhost/ticketpulse" \
  --to "file://schema.hcl"

# Detect drift in production
atlas schema diff \
  --from "postgres://production-host/ticketpulse" \
  --to "file://schema.hcl"
```

The drift detection capability is the killer feature. Run this in a daily cron job in your CI system (see Chapter 33 for the scheduled workflow pattern). If production's schema has drifted from the declared `schema.hcl`, you get an alert. No more silent drift. No more discovering at 2 AM that someone ran `ALTER TABLE` directly on production six weeks ago.

### Migration Patterns

**Zero-downtime migrations** — the hardest problem in database evolution:

| Pattern | How | Example |
|---|---|---|
| **Expand-contract** | Add new, migrate data, remove old | Rename column: add new → copy data → update app → drop old |
| **Backward-compatible adds** | Only add columns/tables, never remove in the same deploy | Add `email_v2` alongside `email`, remove `email` next deploy |
| **Online DDL** | Use tools that avoid table locks | `pg_repack`, `gh-ost` (MySQL), `pt-online-schema-change` |
| **Feature flags** | App reads from old AND new schema, writes to both | Dual-write during migration window |

**Data migrations vs schema migrations:**

Schema migrations change structure (DDL: `CREATE`, `ALTER`, `DROP`). Data migrations change content (DML: `INSERT`, `UPDATE`, `DELETE`). Keep them separate:

```
V10__add_status_column.sql          # Schema: ALTER TABLE tickets ADD COLUMN status VARCHAR(20)
V11__backfill_status_column.sql     # Data: UPDATE tickets SET status = 'active' WHERE status IS NULL
V12__make_status_not_null.sql       # Schema: ALTER TABLE tickets ALTER COLUMN status SET NOT NULL
```

Never combine schema and data changes in one migration — if the data migration fails halfway, the schema change is already committed and the rollback is painful. Separate files let you reason about each change independently, and the three-step pattern above is the standard expand-contract approach for adding a NOT NULL column without downtime.

### CI Integration

```yaml
# GitHub Actions: validate migrations on every PR
- name: Validate migrations
  run: |
    # Start a clean database
    docker run -d --name test-db -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:16

    # Run all migrations
    flyway -url=jdbc:postgresql://localhost/test -user=postgres -password=test migrate

    # Validate no drift (expected schema matches migration output)
    atlas schema diff --from "postgres://localhost/test" --to "file://schema.hcl"
```

Every PR touches a migration file, CI spins up a real database, runs all migrations from scratch, and validates the result against the declared schema. A migration that would break a clean environment fails before it reaches production. This is the test pyramid applied to database schema evolution.

---

## 5. OBSERVABILITY AS CODE

Chapter 18 covers monitoring tools. This section covers managing their **configuration** as code — so dashboards, alerts, and SLOs are versioned, reviewed, and reproducible. Because there is nothing more demoralizing than spending three hours building the perfect Grafana dashboard during an incident, only to lose it when someone clicks "delete" or the Grafana instance is rebuilt from scratch.

### Why Observability as Code?

The "click around in Grafana" approach fails predictably:
- Dashboard created for an incident, never documented, creator leaves the company
- Alert thresholds changed at 3 AM during an incident, never reviewed
- Staging has different alert rules than production — nobody notices until a false negative in prod
- Disaster recovery requires recreating dozens of dashboards from memory

The last point is the killer. When you codify your observability setup — dashboards, alerts, SLOs, on-call schedules — disaster recovery goes from "spend a week reconstructing what we had" to "run `terraform apply` and wait five minutes." Your observability is as resilient as your code.

Beyond disaster recovery: when alert thresholds are in code, changing them requires a pull request. When a threshold change requires a pull request, there is a review. When there is a review, someone asks: "why are we changing the 99th percentile latency alert from 200ms to 500ms?" And the answer — whether it is "the upstream dependency got slower" or "we were getting too many false positives" — is in the PR description, permanently attributable to a decision.

### Grafana as Code

**Option 1: Provisioning (YAML)**

Grafana reads dashboards from files at startup:

```yaml
# provisioning/dashboards/dashboards.yaml
apiVersion: 1
providers:
  - name: TicketPulse
    folder: TicketPulse
    type: file
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

Dashboard JSON files live alongside your application code:

```
dashboards/
├── ticketpulse/
│   ├── overview.json
│   ├── api-latency.json
│   └── database-performance.json
└── infrastructure/
    ├── kubernetes-cluster.json
    └── node-resources.json
```

**Option 2: Terraform Grafana provider**

```hcl
resource "grafana_dashboard" "api_overview" {
  config_json = file("${path.module}/dashboards/api-overview.json")
  folder      = grafana_folder.ticketpulse.id
}

resource "grafana_alert_rule_group" "slo_alerts" {
  name             = "SLO Violations"
  folder_uid       = grafana_folder.ticketpulse.uid
  interval_seconds = 60

  rule {
    name      = "High Error Rate"
    condition = "C"

    data {
      ref_id = "A"
      relative_time_range {
        from = 300
        to   = 0
      }
      datasource_uid = grafana_data_source.prometheus.uid
      model = jsonencode({
        expr = "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) > 0.01"
      })
    }
  }
}
```

**Option 3: Grafonnet (Jsonnet library)**

For teams that manage many dashboards, Grafonnet provides a programmatic DSL. Instead of maintaining a thousand-line JSON blob, you write structured code with reusable components:

```jsonnet
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local prometheus = grafana.prometheus;
local graphPanel = grafana.graphPanel;

dashboard.new(
  'TicketPulse API Overview',
  tags=['ticketpulse', 'api'],
  time_from='now-1h',
)
.addPanel(
  graphPanel.new(
    'Request Rate',
    datasource='Prometheus',
  )
  .addTarget(
    prometheus.target(
      'sum(rate(http_requests_total{service="ticket-service"}[5m])) by (method, path)',
      legendFormat='{{method}} {{path}}',
    )
  ),
  gridPos={ x: 0, y: 0, w: 12, h: 8 },
)
```

Grafonnet shines when you have a standard panel template used across a dozen services. Define it once as a Jsonnet function, parameterize it per service, generate all twelve dashboards from the same library. Any change to the template propagates to all twelve. Consistency enforced through code.

### Terraform for Monitoring Platforms

**Datadog:**

```hcl
resource "datadog_monitor" "high_error_rate" {
  name    = "TicketPulse: High Error Rate"
  type    = "query alert"
  message = <<-EOT
    Error rate exceeded 1% for 5 minutes.
    @slack-ticketpulse-alerts @pagerduty-ticketpulse
  EOT

  query = "sum(last_5m):sum:http.requests{service:ticket-service,status_code_class:5xx}.as_rate() / sum:http.requests{service:ticket-service}.as_rate() > 0.01"

  monitor_thresholds {
    critical = 0.01
    warning  = 0.005
  }

  tags = ["service:ticket-service", "team:platform", "env:production"]
}

resource "datadog_dashboard_json" "api_overview" {
  dashboard = file("${path.module}/dashboards/api-overview.json")
}
```

**PagerDuty:**

```hcl
resource "pagerduty_service" "ticketpulse" {
  name              = "TicketPulse"
  escalation_policy = pagerduty_escalation_policy.platform_team.id
  alert_creation    = "create_alerts_and_incidents"

  incident_urgency_rule {
    type    = "constant"
    urgency = "high"
  }
}

resource "pagerduty_escalation_policy" "platform_team" {
  name      = "Platform Team Escalation"
  num_loops = 2

  rule {
    escalation_delay_in_minutes = 10
    target {
      type = "schedule_reference"
      id   = pagerduty_schedule.primary_oncall.id
    }
  }

  rule {
    escalation_delay_in_minutes = 15
    target {
      type = "user_reference"
      id   = pagerduty_user.engineering_manager.id
    }
  }
}
```

Your on-call schedule, escalation policies, and service routing are in Terraform. When someone rotates off on-call, it is a pull request. When the escalation policy changes (the manager no longer gets paged first), it is a pull request. The PagerDuty configuration is as reviewable as the code that triggers the alerts.

### Prometheus Rules as Code

Alerting and recording rules as Kubernetes custom resources:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ticketpulse-alerts
  labels:
    role: alert-rules
spec:
  groups:
    - name: ticketpulse.slos
      interval: 30s
      rules:
        # Recording rule: pre-compute error rate
        - record: ticketpulse:http_error_rate:5m
          expr: |
            sum(rate(http_requests_total{service="ticket-service", status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total{service="ticket-service"}[5m]))

        # Alert: error budget burn rate too high
        - alert: TicketPulseErrorBudgetBurn
          expr: ticketpulse:http_error_rate:5m > 14.4 * 0.001
          for: 5m
          labels:
            severity: critical
            team: platform
          annotations:
            summary: "TicketPulse error budget burning too fast"
            description: "Current error rate {{ $value | humanizePercentage }} exceeds 14.4x burn rate"
            runbook_url: "https://wiki.internal/runbooks/ticketpulse-error-budget"
```

The `PrometheusRule` lives in your Kubernetes manifests repo, alongside the Deployments it monitors. ArgoCD or Flux syncs it to the cluster. The kube-prometheus-stack picks it up and loads it into Prometheus automatically. New alerting rule: open a PR, merge it, it is live in minutes. No clicking. No manual Prometheus config reloads.

**Testing rules locally:**

```bash
# Lint rules
promtool check rules ticketpulse-alerts.yaml

# Unit test rules
promtool test rules tests/ticketpulse-alerts-test.yaml
```

Write unit tests for your alert rules. This sounds over-engineered until you ship an alert with a broken PromQL expression that silently never fires. `promtool test` catches this in CI, before the broken rule reaches production. Observability as code is testable. Test it.

### SLO as Code (OpenSLO / Sloth)

**Sloth** generates Prometheus recording rules and alerts from a simple SLO definition:

```yaml
# slo/ticketpulse-api.yaml
version: "prometheus/v1"
service: "ticketpulse-api"
labels:
  team: platform
slos:
  - name: "requests-availability"
    objective: 99.9
    description: "99.9% of API requests succeed"
    sli:
      events:
        error_query: sum(rate(http_requests_total{service="ticket-service",status=~"5.."}[{{.window}}]))
        total_query: sum(rate(http_requests_total{service="ticket-service"}[{{.window}}]))
    alerting:
      name: TicketPulseAvailability
      labels:
        team: platform
      annotations:
        runbook_url: "https://wiki.internal/runbooks/ticketpulse-availability"
      page_alert:
        labels:
          severity: critical
      ticket_alert:
        labels:
          severity: warning
```

```bash
# Generate Prometheus rules from SLO definition
sloth generate -i slo/ticketpulse-api.yaml -o rules/ticketpulse-slo.yaml
```

Sloth generates multi-window, multi-burn-rate alerts following Google's SRE workbook methodology — the same approach described in Chapter 4. The beauty of this pattern: your SLO (99.9% availability) lives in a YAML file. Changing the objective from 99.9% to 99.95% requires a pull request. That pull request triggers a conversation: "are we sure we can hit 99.95%? What would that require?" The code enforces the engineering discussion.

### OpenTelemetry Collector Config

The OTel Collector pipeline is declarative YAML:

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 8192
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
  attributes:
    actions:
      - key: environment
        value: production
        action: upsert

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
  otlp/datadog:
    endpoint: "https://trace.agent.datadoghq.com"
    headers:
      "DD-API-KEY": "${DD_API_KEY}"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, attributes]
      exporters: [otlp/jaeger, otlp/datadog]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

Your telemetry routing is code. Adding a new exporter — say, Honeycomb for distributed tracing — is a pull request to this config file. Removing the Jaeger export when you migrate fully to Datadog is a pull request. The observability pipeline is auditable, reviewable, and reproducible.

---

## 6. COMPLIANCE & SUPPLY CHAIN AS CODE

### Chef InSpec (Compliance Profiles)

InSpec defines compliance controls as executable Ruby code. CIS benchmarks, SOC 2 controls, and HIPAA requirements become automated tests — not checklists you fill out once a year, but code that runs continuously and fails loudly when something is wrong.

```ruby
# controls/cis-aws-foundations.rb

control 'cis-aws-1.1' do
  impact 1.0
  title 'Avoid the use of the root account'
  desc 'The root account has unrestricted access. Avoid using it for daily tasks.'

  describe aws_iam_root_user do
    it { should_not have_access_key }
    it { should have_mfa_enabled }
  end
end

control 'cis-aws-2.1' do
  impact 1.0
  title 'Ensure CloudTrail is enabled in all regions'

  describe aws_cloudtrail_trails do
    it { should exist }
  end

  aws_cloudtrail_trails.trail_arns.each do |trail_arn|
    describe aws_cloudtrail_trail(trail_arn) do
      it { should be_multi_region_trail }
      it { should be_logging }
      its('s3_bucket_name') { should_not be_nil }
    end
  end
end
```

```bash
# Run compliance profile against your AWS account
inspec exec cis-aws-foundations -t aws://us-east-1

# Run against a specific profile from Chef Supermarket
inspec exec supermarket://dev-sec/linux-baseline -t ssh://production-host
```

When compliance is code, your SOC 2 audit is not a three-month scramble gathering screenshots. It is a CI job that ran 90 times in the last quarter, and you have the reports to prove it. Auditors are increasingly familiar with this model — some explicitly prefer it because continuous automated evidence is more credible than periodic manual attestation.

### Cloud Custodian (Cloud Governance)

Cloud Custodian enforces policies against cloud resources with YAML rules. It can audit, notify, or take action (stop instances, delete untagged resources, enforce encryption).

```yaml
# policies/enforce-tagging.yaml
policies:
  - name: ec2-require-tags
    resource: ec2
    filters:
      - "tag:Environment": absent
    actions:
      - type: mark-for-op
        tag: custodian_cleanup
        op: stop
        days: 3
      - type: notify
        template: default
        subject: "EC2 instance missing required tags"
        to:
          - resource-owner
          - team-platform@company.com
        transport:
          type: sqs
          queue: https://sqs.us-east-1.amazonaws.com/123456789/custodian-mailer

  - name: s3-enforce-encryption
    resource: s3
    filters:
      - type: bucket-encryption
        state: false
    actions:
      - type: set-bucket-encryption
        crypto: AES256
```

```bash
# Dry run (audit mode)
custodian run -s output/ --dry-run policies/enforce-tagging.yaml

# Enforce
custodian run -s output/ policies/enforce-tagging.yaml
```

Always run in `--dry-run` first. The first time you run Cloud Custodian against a mature AWS account with "EC2 instances missing tags," you will typically find dozens of instances. Some of them might be critical. Audit first, understand the inventory, then enforce.

### Supply Chain Security as Code

**SLSA (Supply-chain Levels for Software Artifacts)** defines four levels of supply chain integrity. At its core: every artifact should have a provenance attestation — a signed record of what was built, from what source, by which builder.

This is where Chapter 5's security principles meet Chapter 33's CI/CD pipelines. The pipeline that builds your containers is also the pipeline that signs them and generates provenance attestations. The code that describes what gets built is also the code that proves how it was built.

**Sigstore/cosign** — sign and verify container images without managing keys:

```bash
# Sign an image (keyless — uses OIDC identity from CI)
cosign sign ghcr.io/company/ticketpulse:v1.2.3

# Verify an image
cosign verify ghcr.io/company/ticketpulse:v1.2.3 \
  --certificate-identity=https://github.com/company/ticketpulse/.github/workflows/build.yml@refs/heads/main \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

The keyless signing is the important detail here. Cosign uses the GitHub Actions OIDC token (the same workload identity mechanism from Chapter 33) to prove that the image was built by a specific workflow in a specific repository. No key management, no expiring certificates, no "who has the signing key?" conversations. The proof is the CI system identity.

**SBOM (Software Bill of Materials)** — list every dependency in your artifacts:

```bash
# Generate SBOM with Syft
syft ghcr.io/company/ticketpulse:v1.2.3 -o spdx-json > sbom.json

# Scan SBOM for vulnerabilities with Grype
grype sbom:sbom.json

# Attach SBOM to container image
cosign attach sbom --sbom sbom.json ghcr.io/company/ticketpulse:v1.2.3
```

Your SBOM is the manifest of what your artifact contains. When a new critical CVE drops, you query your SBOMs to find out which images are affected — without rebuilding anything. The SBOM is provenance: a versioned, signed record of the exact dependencies in every release.

---

## 7. CONFIGURATION MANAGEMENT

### Ansible: When You Still Need Config Management

Chapter 7 covered immutable infrastructure — build a new image, deploy it, terminate the old one. This eliminates configuration drift by design. So when does mutable configuration management still matter?

The answer is: more often than you might like. The world has not fully containerized. Real organizations have legacy systems, bare-metal servers, database hosts that predate Kubernetes, GPU clusters that are too expensive to treat as ephemeral. For all of these, Ansible is the right tool.

**Ansible is still relevant for:**
- Legacy systems that cannot be rebuilt as containers
- Bare-metal servers (database hosts, GPU clusters)
- One-time provisioning before immutable images take over
- Network equipment configuration
- Compliance hardening of base images

**Ansible is NOT the right tool for:**
- Anything that runs in containers (use Dockerfiles + K8s)
- Cloud infrastructure provisioning (use Terraform)
- Application deployment (use CI/CD pipelines)

### Ansible Basics

Ansible is **agentless** — it connects via SSH and executes tasks. Configuration is YAML (playbooks), and it uses an inventory of target hosts.

```yaml
# inventory/production.yaml
all:
  children:
    databases:
      hosts:
        db-primary:
          ansible_host: 10.0.1.10
        db-replica:
          ansible_host: 10.0.1.11
      vars:
        postgresql_version: "16"
    gpu_cluster:
      hosts:
        gpu-[01:04]:
          ansible_host: "10.0.2.{{ groups['gpu_cluster'].index(inventory_hostname) + 10 }}"
```

```yaml
# playbooks/harden-database.yaml
---
- name: Harden PostgreSQL servers
  hosts: databases
  become: true

  tasks:
    - name: Ensure PostgreSQL is installed
      apt:
        name: "postgresql-{{ postgresql_version }}"
        state: present

    - name: Configure pg_hba.conf
      template:
        src: templates/pg_hba.conf.j2
        dest: /etc/postgresql/{{ postgresql_version }}/main/pg_hba.conf
        owner: postgres
        mode: '0640'
      notify: Restart PostgreSQL

    - name: Set sysctl parameters for database
      sysctl:
        name: "{{ item.key }}"
        value: "{{ item.value }}"
        state: present
      loop:
        - { key: vm.swappiness, value: "1" }
        - { key: vm.overcommit_memory, value: "2" }
        - { key: net.core.somaxconn, value: "65535" }

  handlers:
    - name: Restart PostgreSQL
      systemd:
        name: postgresql
        state: restarted
```

```bash
# Run playbook (dry run first)
ansible-playbook -i inventory/production.yaml playbooks/harden-database.yaml --check --diff

# Apply
ansible-playbook -i inventory/production.yaml playbooks/harden-database.yaml
```

Always `--check --diff` first. Ansible's check mode shows you what it *would* change without changing anything. The `--diff` flag shows you the exact file changes. This is your review step — the equivalent of `terraform plan` before `terraform apply`. Never run `ansible-playbook` on production hosts without reviewing the diff first.

### The IaC / Config Management Boundary

| Concern | Tool | Why |
|---|---|---|
| Create VMs, networks, load balancers | **Terraform** | Declarative, state-tracked, cloud-agnostic |
| Install packages, configure OS, harden servers | **Ansible** | Agentless, idempotent, SSH-based |
| Build application images | **Dockerfiles** | Reproducible, layered, versioned |
| Deploy applications | **Kubernetes / CI/CD** | Orchestrated, self-healing |
| Configure the runtime platform (K8s itself) | **Helm / Kustomize** | Parameterized manifests |

The overlap zone is small: Ansible can provision cloud resources (but Terraform is better), and Terraform can run scripts (but Ansible is better). Use each for what it does best. The boundary is about choosing the tool that makes the desired state most explicit and the actual change most reviewable.

---

## 8. IAC TESTING & VALIDATION

Infrastructure code is code. It deserves the same testing discipline as application code. This is the statement that gets eye-rolls from developers who have not yet watched a Terraform change bring down production because the plan looked fine but the state was wrong. Test your infrastructure code. Seriously.

### The IaC Testing Pyramid

```
                    ┌─────────────┐
                    │  End-to-End  │  Real cloud, real resources
                    │   (slow)     │  Run: weekly or pre-release
                    ├─────────────┤
                 ┌──┤ Integration  │  LocalStack, kind, ephemeral envs
                 │  │  (minutes)   │  Run: nightly or on merge to main
                 ├──┼─────────────┤
              ┌──┤  │  Plan Tests  │  terraform plan → JSON → validate
              │  │  │  (seconds)   │  Run: every PR
              ├──┼──┼─────────────┤
           ┌──┤  │  │   Unit Tests │  terraform test, CDK assertions
           │  │  │  │  (seconds)   │  Run: every PR
           ├──┼──┼──┼─────────────┤
        ┌──┤  │  │  │ Static Scan  │  Checkov, Trivy, cfn-lint, kube-linter
        │  │  │  │  │ (seconds)    │  Run: every commit (pre-commit hook)
        └──┴──┴──┴──┴─────────────┘
```

The pyramid structure matters. Most tests should be fast and cheap — static analysis and unit tests that run in seconds on every commit. Fewer tests should be slow and expensive — real cloud integration tests that run nightly. This mirrors the application testing pyramid from Chapter 33's CI/CD patterns: test early, test fast, reserve expensive tests for high-confidence gates.

### Static Analysis

**Trivy** (formerly tfsec) — fast Go binary for Terraform security scanning:

```bash
# Scan Terraform directory
trivy config ./terraform/

# With severity filter
trivy config --severity HIGH,CRITICAL ./terraform/

# Output SARIF for GitHub Security tab
trivy config --format sarif -o results.sarif ./terraform/
```

**kube-linter** — Kubernetes manifest best practices:

```bash
kube-linter lint k8s-manifests/

# Common findings:
# - No resource requests/limits
# - Running as root
# - No readiness probe
# - Using :latest tag
```

`kube-linter` is the manifest equivalent of a linter for application code. You would not ship JavaScript without running ESLint. Do not ship Kubernetes manifests without running `kube-linter`. The findings it surfaces — no resource limits, running as root, no readiness probe — are exactly the class of misconfiguration that causes production incidents.

### Native Terraform Testing

Terraform's built-in `terraform test` framework (HCL):

```hcl
# tests/vpc.tftest.hcl
run "vpc_creates_correctly" {
  command = plan

  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR block should be 10.0.0.0/16"
  }

  assert {
    condition     = aws_vpc.main.enable_dns_hostnames == true
    error_message = "DNS hostnames should be enabled"
  }
}

run "subnets_spread_across_azs" {
  command = plan

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Should create 3 private subnets"
  }
}
```

```bash
terraform test
```

The `command = plan` variant runs assertions against the plan without provisioning real resources. Fast, cheap, catches logic errors in your Terraform modules. Write these as you build modules. The test file is the specification — it documents what the module is supposed to produce, which is exactly the kind of living documentation that does not go stale.

### Terratest (Integration Testing)

Terratest provisions real infrastructure in a test, validates it, then tears it down:

```go
package test

import (
    "testing"
    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
    http_helper "github.com/gruntwork-io/terratest/modules/http-helper"
)

func TestVpcModule(t *testing.T) {
    t.Parallel()

    terraformOptions := &terraform.Options{
        TerraformDir: "../modules/vpc",
        Vars: map[string]interface{}{
            "cidr_block":  "10.99.0.0/16",
            "environment": "test",
        },
    }

    // Clean up after test
    defer terraform.Destroy(t, terraformOptions)

    // Provision real infrastructure
    terraform.InitAndApply(t, terraformOptions)

    // Validate outputs
    vpcId := terraform.Output(t, terraformOptions, "vpc_id")
    assert.NotEmpty(t, vpcId)

    privateSubnets := terraform.OutputList(t, terraformOptions, "private_subnet_ids")
    assert.Len(t, privateSubnets, 3)
}
```

Terratest integration tests are expensive — they provision real cloud resources, which costs money and takes time. Run them on merge to main or nightly, not on every PR. The `defer terraform.Destroy` is critical: if the test panics, the resources still get cleaned up. Always use `t.Parallel()` if you have multiple Terratest suites — they can run concurrently, which cuts your CI time significantly.

### Cost Estimation: Infracost

Infracost estimates cloud costs from Terraform plans and posts them as PR comments:

```bash
# Generate cost breakdown
infracost breakdown --path ./terraform/

# Compare cost of a change (in CI)
infracost diff --path ./terraform/ --compare-to infracost-base.json

# Example output:
# ──────────────────────────────────
#  Monthly cost will increase by $142
#  ├── aws_instance.web (+$98)
#  │   └── t3.micro → t3.large
#  └── aws_rds_cluster.main (+$44)
#      └── Storage: 100GB → 200GB
# ──────────────────────────────────
```

Cost is a constraint, and constraints belong in code review. When a PR to upgrade your database instance type includes an Infracost comment saying "+$44/month," the reviewer has the information they need to have a real conversation. No more discovering surprise cloud bills at the end of the month wondering what changed.

### Drift Detection

```bash
# Terraform: detect drift between state and reality
terraform plan -detailed-exitcode
# Exit code 0 = no changes, 1 = error, 2 = changes detected

# Schedule in CI (daily cron)
# .github/workflows/drift-detection.yaml
# on:
#   schedule:
#     - cron: '0 6 * * *'  # 6 AM daily
```

Drift detection is your integrity check. Run it daily. When `terraform plan` reports changes on a codebase that nobody touched, someone changed something outside of Terraform. Find it, bring it back into code, open a post-mortem discussion about why it happened. Drift is a process failure. Detecting it early makes it cheap to fix.

---

## 9. GITOPS & ENVIRONMENT PROMOTION

### GitOps: Git as the Source of Truth

GitOps means the desired state of your infrastructure and applications is declared in Git. An agent continuously reconciles the actual state with the declared state. This is the culmination of the everything-as-code philosophy — not just declaring state in Git, but having automation continuously enforce that Git is the authority.

Two models:

| Model | How | Security | Example |
|---|---|---|---|
| **Push-based** | CI pushes changes to the cluster | CI needs cluster credentials | GitHub Actions → `kubectl apply` |
| **Pull-based** | Agent in cluster pulls from Git | Cluster pulls; no external access needed | ArgoCD, Flux |

Pull-based is more secure: the cluster reaches out to Git (read-only), rather than CI reaching into the cluster (write access). When your CI system does not have cluster credentials, your CI system cannot be compromised to deploy malicious code. The cluster controls its own state by continuously comparing it to Git.

### The GitOps Transformation: A Before/After Story

Before GitOps: your staging environment drifts from production because someone ran `kubectl edit deployment` to "quickly test something" and forgot to update the manifest. You discover the drift during a production incident when the staging reproduction steps don't match production behavior. The investigation takes two hours.

After GitOps: ArgoCD's `selfHeal: true` reverts the manual `kubectl edit` within 90 seconds. The developer gets a notification that their change was reverted. They open a pull request with the actual change. The change is reviewed, merged, and deployed to staging automatically. The diff between staging and production is exactly what is in the manifest files, always.

This is not just a convenience. It is a correctness guarantee. With GitOps, if you want to know what is running in production, you read the Git repository. Period. No checking the cluster, no reconciling what the Terraform state says versus what the AWS console shows. Git is the source of truth, and automation enforces it.

### ArgoCD

ArgoCD is the most popular GitOps tool for Kubernetes. It watches a Git repo and syncs Kubernetes manifests to a cluster.

**Application CRD:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ticketpulse
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/company/ticketpulse-infra.git
    targetRevision: main
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: ticketpulse
  syncPolicy:
    automated:
      prune: true        # Delete resources removed from Git
      selfHeal: true     # Revert manual changes (drift correction)
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

The `prune: true` setting is important and occasionally surprising to new ArgoCD users. If you remove a resource from Git, ArgoCD will delete it from the cluster. This is correct behavior — Git is the source of truth — but it means you cannot have resources that "exist in the cluster but not in Git." Everything must be declared. Everything must be code.

**ApplicationSet (multi-environment):**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: ticketpulse-envs
spec:
  generators:
    - list:
        elements:
          - env: staging
            cluster: https://staging.k8s.internal
            values_file: values-staging.yaml
          - env: production
            cluster: https://prod.k8s.internal
            values_file: values-production.yaml
  template:
    metadata:
      name: "ticketpulse-{{env}}"
    spec:
      source:
        repoURL: https://github.com/company/ticketpulse-infra.git
        path: k8s/helm
        helm:
          valueFiles:
            - "{{values_file}}"
      destination:
        server: "{{cluster}}"
        namespace: ticketpulse
```

ApplicationSet is how you manage multiple environments without duplicating Application definitions. Add a new environment by adding an entry to the `elements` list. Add a new service by creating a new ApplicationSet. The matrix of environments × services is managed declaratively, in code, reviewed in PRs.

### Flux CD

Flux takes a more Kubernetes-native approach — everything is a CRD, and it composes well with Kustomize and Helm.

```yaml
# GitRepository: where to pull from
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: ticketpulse
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/company/ticketpulse-infra.git
  ref:
    branch: main

---
# Kustomization: what to apply
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: ticketpulse
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: ticketpulse
  path: ./k8s/overlays/production
  prune: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: ticket-service
      namespace: ticketpulse
```

### ArgoCD vs Flux

| Aspect | ArgoCD | Flux |
|---|---|---|
| **UI** | Rich web UI with visual diff | No built-in UI (use Weave GitOps) |
| **Architecture** | Centralized server + Application CRDs | Distributed controllers + CRDs |
| **Multi-cluster** | Built-in (register external clusters) |Hub-spoke via CRDs |
| **Helm support** | Native | Via HelmRelease CRD |
| **RBAC** | Built-in, fine-grained | Delegates to Kubernetes RBAC |
| **Best for** | Teams wanting a UI, multi-cluster | Teams wanting Kubernetes-native, composable |

Both are excellent. The choice often comes down to whether your team wants a UI (ArgoCD wins) or wants everything to be CRDs that integrate naturally with other Kubernetes tooling (Flux wins). You will not go wrong with either — the important thing is committing to the GitOps model.

### Terragrunt (DRY Terraform)

Terragrunt wraps Terraform to eliminate repetition across environments:

```
infrastructure/
├── terragrunt.hcl              # Root: common config (backend, provider)
├── staging/
│   ├── terragrunt.hcl          # Environment: staging-specific vars
│   ├── vpc/
│   │   └── terragrunt.hcl      # Module instance
│   ├── database/
│   │   └── terragrunt.hcl
│   └── kubernetes/
│       └── terragrunt.hcl
└── production/
    ├── terragrunt.hcl
    ├── vpc/
    │   └── terragrunt.hcl
    ├── database/
    │   └── terragrunt.hcl
    └── kubernetes/
        └── terragrunt.hcl
```

```hcl
# infrastructure/terragrunt.hcl (root)
remote_state {
  backend = "s3"
  config = {
    bucket         = "company-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

# infrastructure/staging/vpc/terragrunt.hcl
terraform {
  source = "../../../modules/vpc"
}

include "root" {
  path = find_in_parent_folders()
}

inputs = {
  environment = "staging"
  cidr_block  = "10.1.0.0/16"
  az_count    = 2
}
```

Terragrunt's directory structure is itself documentation. Looking at the tree, you understand the environments, their modules, and their relationships. Adding a new environment is copying a directory and changing the `inputs`. Promoting a module version from staging to production is changing a single `source` line. The structure enforces the pattern.

### Atlantis (Terraform PR Automation)

Atlantis runs `terraform plan` automatically on PRs and posts the output as a comment. Team members review the plan and comment `atlantis apply` to apply.

```yaml
# atlantis.yaml (repo config)
version: 3
projects:
  - name: staging-vpc
    dir: infrastructure/staging/vpc
    autoplan:
      when_modified: ["*.tf", "*.tfvars"]
      enabled: true
  - name: production-vpc
    dir: infrastructure/production/vpc
    autoplan:
      when_modified: ["*.tf", "*.tfvars"]
      enabled: true
    apply_requirements: [approved, mergeable]   # Require PR approval before apply
```

The `apply_requirements: [approved, mergeable]` for production is the key control. Nobody can `atlantis apply` on production without a PR approval. The Terraform change goes through code review — the plan is visible in the PR, the reviewer can see exactly what will change, and only after approval does the apply happen. Chapter 33's GitHub Actions workflow handles the CI; Atlantis handles the Terraform-specific workflow of plan-review-apply.

### Environment Promotion Patterns

**Anti-pattern: branch-per-environment**

```
main → staging → production     # AVOID: cherry-pick hell, merge conflicts, drift
```

**Better: directory-per-environment with shared modules**

```
modules/                         # Shared, versioned modules
├── vpc/
├── database/
└── kubernetes/

environments/                    # Environment-specific configuration
├── staging/
│   └── main.tf                  # module "vpc" { source = "../../modules/vpc" }
└── production/
    └── main.tf                  # Same module, different vars
```

**Best: promote immutable artifacts**

```
1. PR merged → CI builds container image → tags: git-sha + "staging"
2. Staging deploy → smoke tests pass → image retagged "production"
3. Production deploy → same binary, different config (env vars)

The image that runs in production is byte-for-byte identical
to what was tested in staging.
```

The immutable artifact promotion pattern is the gold standard. The container image is a versioned, signed artifact. It does not change between staging and production — only the configuration changes (different environment variables, different secrets from Vault/ESO). This eliminates an entire class of "works in staging but not in production" bugs: the binary is identical. If it passes staging, it will behave the same way in production.

### Feature Flags as Config-as-Code

Feature flags decouple deployment from release. The **OpenFeature** standard provides a vendor-agnostic API:

```typescript
import { OpenFeature } from '@openfeature/server-sdk';

const client = OpenFeature.getClient();

// Flag evaluation — provider-agnostic
const showNewCheckout = await client.getBooleanValue('new-checkout-flow', false, {
  targetingKey: userId,
});

if (showNewCheckout) {
  return renderNewCheckoutFlow();
}
```

Flag definitions in version control (e.g., Flagsmith, Unleash):

```yaml
# flags/production.yaml
flags:
  new-checkout-flow:
    enabled: true
    rules:
      - segments: [beta-testers]
        percentage: 100
      - segments: [all-users]
        percentage: 5    # 5% canary rollout
  dark-mode:
    enabled: true
    default: false
```

Feature flags in version control mean that enabling a feature for 100% of users is a pull request. The PR description explains why the rollout is happening, what the success criteria are, and how to roll back. The flag change is reviewable, auditable, and revertible. This is the everything-as-code philosophy applied to product releases.

---

## 10. PLATFORM ABSTRACTIONS

### Crossplane: Kubernetes-Native Infrastructure

Crossplane extends Kubernetes to manage cloud infrastructure. Instead of Terraform HCL, you define infrastructure as Kubernetes custom resources — and the Kubernetes reconciliation loop keeps them in sync.

**Why Crossplane over Terraform?**
- GitOps-native: works with ArgoCD/Flux out of the box (it is just K8s resources)
- Continuous reconciliation: if someone deletes an S3 bucket manually, Crossplane recreates it
- Self-service: teams create infrastructure by applying K8s manifests — no Terraform expertise needed
- Composability: build platform APIs that abstract cloud complexity

Crossplane answers a question that Terraform cannot easily answer: what happens if someone manually deletes a resource that Terraform manages? Terraform detects it at the next `terraform plan`. Crossplane detects it and fixes it immediately, because reconciliation is continuous. This is the difference between eventually consistent (Terraform) and continuously consistent (Crossplane) infrastructure management.

**Managed Resource (raw cloud resource):**

```yaml
apiVersion: s3.aws.upbound.io/v1beta1
kind: Bucket
metadata:
  name: ticketpulse-uploads
spec:
  forProvider:
    region: us-east-1
    tags:
      Environment: production
      Team: platform
  providerConfigRef:
    name: aws-provider
```

**Composition (platform abstraction):**

Instead of exposing raw AWS resources, create a "Database" abstraction:

```yaml
# XRD: define the API
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xdatabases.platform.company.io
spec:
  group: platform.company.io
  names:
    kind: XDatabase
    plural: xdatabases
  claimNames:
    kind: Database
    plural: databases
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                size:
                  type: string
                  enum: [small, medium, large]
                engine:
                  type: string
                  enum: [postgres, mysql]
```

**Team usage (simple claim):**

```yaml
# A developer requests a database — no cloud expertise needed
apiVersion: platform.company.io/v1alpha1
kind: Database
metadata:
  name: ticketpulse-db
  namespace: ticketpulse
spec:
  size: medium
  engine: postgres
```

The Composition maps `size: medium` to an RDS instance with specific instance type, storage, and backup settings. The developer never sees the cloud-specific details. The platform team controls the actual implementation. This separation of concerns is the platform engineering model: the platform team builds the golden path, product teams walk it.

The developer experience is remarkable. To provision a database, you apply a 10-line YAML file. You do not need to know what RDS instance type `medium` maps to, or what the backup retention policy is, or how VPC security groups need to be configured. The platform team encoded that knowledge into the Composition. The developer's job is to describe what they need, not how to build it.

### Backstage (Internal Developer Portal)

Backstage (by Spotify, CNCF Incubating) is an internal developer portal that unifies service catalogs, documentation, and self-service infrastructure. If Crossplane is "infrastructure as a Kubernetes API," Backstage is "platform knowledge as a developer portal."

**Software Catalog** — register all services:

```yaml
# catalog-info.yaml (lives in each repo)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: ticket-service
  description: Handles ticket purchases and reservations
  annotations:
    github.com/project-slug: company/ticket-service
    pagerduty.com/service-id: P1234567
    grafana/dashboard-selector: "service=ticket-service"
  tags:
    - typescript
    - grpc
spec:
  type: service
  lifecycle: production
  owner: platform-team
  dependsOn:
    - component:default/events-service
    - resource:default/ticketpulse-db
  providesApis:
    - ticket-api
```

Every `catalog-info.yaml` is a `git add`. The software catalog grows as you add services. The dependency graph in Backstage — who depends on what — is derived from these files. When you need to assess the blast radius of taking the events-service offline, you query the catalog. The answer is in code, not in someone's head.

**Scaffolder Templates** — self-service new service creation:

```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: new-microservice
  title: Create a New Microservice
  description: Scaffold a production-ready microservice with CI/CD, monitoring, and K8s manifests
spec:
  owner: platform-team
  type: service
  parameters:
    - title: Service Details
      properties:
        name:
          title: Service Name
          type: string
          pattern: "^[a-z][a-z0-9-]*$"
        description:
          title: Description
          type: string
        owner:
          title: Owner Team
          type: string
          ui:field: OwnerPicker
  steps:
    - id: fetch
      name: Scaffold
      action: fetch:template
      input:
        url: ./skeleton
        values:
          name: ${{ parameters.name }}
          description: ${{ parameters.description }}
          owner: ${{ parameters.owner }}
    - id: publish
      name: Create Repository
      action: publish:github
      input:
        repoUrl: github.com?owner=company&repo=${{ parameters.name }}
    - id: register
      name: Register in Catalog
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps.publish.output.repoContentsUrl }}
        catalogInfoPath: /catalog-info.yaml
```

This template is the golden path as code. When a developer uses the Backstage Scaffolder to create a new microservice, they get: a GitHub repository, a CI/CD pipeline (from Chapter 33's workflow templates), a Kubernetes manifest directory, a Crossplane database claim, a Grafana dashboard, a Datadog monitor, and a PagerDuty service — all pre-configured, all reviewable, all in Git. The platform team invested in building the template once. Every new service benefits forever.

The Scaffolder template itself is a YAML file. Adding a new step to the template — say, automatically creating a JIRA project, or setting up a Slack channel — is a pull request to the template file. The golden path is version-controlled. Improving it is code review. This is the everything-as-code philosophy applied to platform engineering.

### The Platform Engineering Stack

```
┌──────────────────────────────────────────────────┐
│                Developer Portal                   │
│         (Backstage / Port / Cortex)               │
├──────────────────────────────────────────────────┤
│              Self-Service APIs                    │
│    (Crossplane Compositions / Terraform Modules)  │
├──────────────────────────────────────────────────┤
│            GitOps Reconciliation                  │
│            (ArgoCD / Flux)                        │
├──────────────────────────────────────────────────┤
│          Policy & Compliance Gates                │
│    (OPA / Kyverno / Checkov / Sentinel)           │
├──────────────────────────────────────────────────┤
│          Infrastructure Providers                 │
│    (AWS / GCP / Azure / Kubernetes)               │
└──────────────────────────────────────────────────┘
```

The golden path: a developer creates a service via Backstage → Scaffolder generates a repo with a Crossplane claim → ArgoCD syncs the claim to the cluster → Crossplane provisions cloud resources → Kyverno enforces policies → monitoring is auto-configured via Terraform/Grafana-as-code.

Every step is in code. Every step is reviewable. Every step is reproducible.

### The Endgame

Here is what everything-as-code looks like when you have reached full maturity. A new engineer joins the team. On day one, they clone two repositories: the application code and the infrastructure code. Everything they need to understand about the system is in those repositories. The infrastructure history is `git log`. The policy decisions are Rego files and Kyverno policies with explanatory comments. The database schema is the migration history — a story of how the schema evolved, one PR at a time. The alert thresholds have commit messages explaining why they were set at those values. The on-call schedule is in Terraform, with the reasoning in the PR that created it.

The new engineer can answer questions about the system by reading the code. They can make changes to the system through pull requests. They can run the system locally using the same automation that runs in production. They never have to ask "where is that configured?" because the answer is always the same: it is in Git.

If it is not in Git, it does not exist.

That is not a philosophy. That is a practice. Start today.

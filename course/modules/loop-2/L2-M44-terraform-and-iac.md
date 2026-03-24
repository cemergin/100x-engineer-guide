# L2-M44: Terraform & Infrastructure as Code

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M43
>
> **Source:** Chapter 7 of the 100x Engineer Guide

## What You'll Learn

- Why infrastructure as code matters and the difference between declarative and imperative IaC
- Writing Terraform HCL from scratch to define TicketPulse's infrastructure
- The core workflow: `terraform init` → `terraform plan` → `terraform apply`
- State management: what terraform.tfstate is, why it matters, how to use remote backends
- Creating reusable Terraform modules for TicketPulse services
- Detecting and handling infrastructure drift
- Importing existing resources into Terraform management
- When to choose Terraform vs Pulumi vs CDK

## Why This Matters

In L2-M43, you deployed TicketPulse to Kubernetes by running `kubectl apply` commands manually. That works for a single developer on a local cluster. But in production, you have multiple environments (staging, production), multiple team members, and dozens of resources (clusters, databases, caches, DNS records, load balancers). If someone sets up production by following a wiki page of commands, you get drift, inconsistency, and "it worked last time" failures. Infrastructure as Code means the infrastructure is defined in version-controlled files, reviewed in pull requests, and applied deterministically. The same code produces the same infrastructure every time.

## Prereq Check

You need Terraform installed and the kind cluster from L2-M43 running.

```bash
# Install Terraform
# macOS
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# Linux
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# Verify
terraform version
# Should show Terraform v1.x.x

# Verify your kind cluster is running
kubectl get nodes --context kind-ticketpulse
```

---

## 1. Infrastructure as Code: The Core Idea

Without IaC:
- You SSH into a server and run commands
- You click through a cloud console UI
- You follow a wiki page that says "create an RDS instance with these settings"
- Six months later, nobody knows why production has a different config than staging

With IaC:
- Infrastructure is defined in files, committed to Git
- Changes go through pull requests and code review
- `terraform plan` shows you exactly what will change before you apply
- Every environment is created from the same code
- Rollback = revert the commit

### Declarative vs Imperative

**Declarative (Terraform):** You describe the desired end state. The tool figures out how to get there.

```hcl
# "I want 3 servers" -- Terraform figures out: need to create 3
resource "aws_instance" "web" {
  count         = 3
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"
}
```

**Imperative (Pulumi/CDK):** You write code that describes the steps.

```typescript
// "Create 3 servers" -- you write the logic
for (let i = 0; i < 3; i++) {
  new aws.ec2.Instance(`web-${i}`, {
    ami: "ami-0abcdef1234567890",
    instanceType: "t3.micro",
  });
}
```

Both produce the same result. The difference matters when you change from 3 to 5: Terraform automatically figures out "create 2 more." Imperative code needs explicit diff logic.

---

## 2. Build: TicketPulse Infrastructure in Terraform

We will define TicketPulse's infrastructure for a local/simulated environment. The patterns translate directly to AWS, GCP, or Azure.

Create the Terraform project:

```bash
mkdir -p ticketpulse/terraform
cd ticketpulse/terraform
```

### 2a. Provider Configuration

Terraform uses "providers" to interact with infrastructure platforms. We will use the Kubernetes provider to manage our kind cluster.

```hcl
# main.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "kind-ticketpulse"
}

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = "kind-ticketpulse"
  }
}
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

### 2b. Variables

Variables make your Terraform code reusable across environments.

```hcl
# variables.tf

variable "namespace" {
  description = "Kubernetes namespace for TicketPulse"
  type        = string
  default     = "ticketpulse"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "api_replicas" {
  description = "Number of API gateway replicas"
  type        = number
  default     = 3
}

variable "event_service_replicas" {
  description = "Number of event service replicas"
  type        = number
  default     = 2
}

variable "payment_service_replicas" {
  description = "Number of payment service replicas"
  type        = number
  default     = 2
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true    # Never shown in logs or plan output
}

variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true
}

variable "api_image" {
  description = "Docker image for the API gateway"
  type        = string
  default     = "ticketpulse-api-gateway:latest"
}

variable "event_service_image" {
  description = "Docker image for the event service"
  type        = string
  default     = "ticketpulse-event-service:latest"
}

variable "payment_service_image" {
  description = "Docker image for the payment service"
  type        = string
  default     = "ticketpulse-payment-service:latest"
}
```

### 2c. Namespace and Config

```hcl
# namespace.tf

resource "kubernetes_namespace" "ticketpulse" {
  metadata {
    name = var.namespace

    labels = {
      environment = var.environment
      managed_by  = "terraform"
    }
  }
}
```

```hcl
# config.tf

resource "kubernetes_config_map" "api_config" {
  metadata {
    name      = "api-config"
    namespace = kubernetes_namespace.ticketpulse.metadata[0].name
  }

  data = {
    NODE_ENV              = var.environment == "production" ? "production" : "development"
    LOG_LEVEL             = var.environment == "production" ? "warn" : "info"
    EVENT_SERVICE_URL     = "http://event-service:3001"
    PAYMENT_SERVICE_URL   = "http://payment-service:3002"
    KAFKA_BROKERS         = "kafka:9092"
    ELASTICSEARCH_URL     = "http://elasticsearch:9200"
  }
}

resource "kubernetes_secret" "db_credentials" {
  metadata {
    name      = "db-credentials"
    namespace = kubernetes_namespace.ticketpulse.metadata[0].name
  }

  data = {
    POSTGRES_USER     = "ticketpulse"
    POSTGRES_PASSWORD = var.db_password
    DATABASE_URL      = "postgresql://ticketpulse:${var.db_password}@postgres:5432/ticketpulse"
    JWT_SECRET        = var.jwt_secret
  }

  type = "Opaque"
}
```

Notice the references: `kubernetes_namespace.ticketpulse.metadata[0].name` creates a dependency. Terraform knows to create the namespace before the ConfigMap. You never specify ordering -- Terraform builds a dependency graph automatically.

### 2d. API Gateway Deployment

```hcl
# api-gateway.tf

resource "kubernetes_deployment" "api_gateway" {
  metadata {
    name      = "api-gateway"
    namespace = kubernetes_namespace.ticketpulse.metadata[0].name

    labels = {
      app  = "api-gateway"
      tier = "frontend"
    }
  }

  spec {
    replicas = var.api_replicas

    selector {
      match_labels = {
        app = "api-gateway"
      }
    }

    strategy {
      type = "RollingUpdate"

      rolling_update {
        max_unavailable = "1"
        max_surge       = "1"
      }
    }

    template {
      metadata {
        labels = {
          app  = "api-gateway"
          tier = "frontend"
        }
      }

      spec {
        container {
          name              = "api-gateway"
          image             = var.api_image
          image_pull_policy = "Never"

          port {
            container_port = 3000
            name           = "http"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.api_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.db_credentials.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 3000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
            failure_threshold     = 3
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 3000
            }
            initial_delay_seconds = 15
            period_seconds        = 20
            failure_threshold     = 3
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "api_gateway" {
  metadata {
    name      = "api-gateway"
    namespace = kubernetes_namespace.ticketpulse.metadata[0].name
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "api-gateway"
    }

    port {
      name        = "http"
      port        = 80
      target_port = 3000
    }
  }
}
```

### 2e. Outputs

Outputs expose values after `terraform apply`, useful for other tools or for human reference.

```hcl
# outputs.tf

output "namespace" {
  description = "The Kubernetes namespace"
  value       = kubernetes_namespace.ticketpulse.metadata[0].name
}

output "api_gateway_service" {
  description = "API Gateway service name"
  value       = kubernetes_service.api_gateway.metadata[0].name
}

output "api_replicas" {
  description = "Number of API gateway replicas"
  value       = kubernetes_deployment.api_gateway.spec[0].replicas
}
```

### 2f. Variable Values

Create a `.tfvars` file for your local environment:

```hcl
# dev.tfvars

environment              = "dev"
api_replicas             = 3
event_service_replicas   = 2
payment_service_replicas = 2
db_password              = "local-dev-password"
jwt_secret               = "local-dev-jwt-secret"
```

> **Never commit `.tfvars` files with real secrets.** Add `*.tfvars` to `.gitignore` and use environment variables or a secret manager in CI/CD.

---

## 3. Try It: The Core Workflow

### Step 1: terraform init

```bash
cd ticketpulse/terraform

terraform init
```

This downloads the Kubernetes and Helm providers. You will see:

```
Initializing the backend...
Initializing provider plugins...
- Installing hashicorp/kubernetes v2.25.x...
- Installing hashicorp/helm v2.12.x...
Terraform has been successfully initialized!
```

A `.terraform` directory is created containing the provider binaries. Add `.terraform/` to `.gitignore`.

### Step 2: terraform plan

```bash
terraform plan -var-file=dev.tfvars
```

This is the most important command. It shows exactly what Terraform will do WITHOUT doing it.

```
Terraform will perform the following actions:

  # kubernetes_namespace.ticketpulse will be created
  + resource "kubernetes_namespace" "ticketpulse" {
      + id = (known after apply)
      + metadata {
          + name = "ticketpulse"
          + labels = {
              + "environment" = "dev"
              + "managed_by"  = "terraform"
            }
        }
    }

  # kubernetes_config_map.api_config will be created
  + resource "kubernetes_config_map" "api_config" { ... }

  # kubernetes_secret.db_credentials will be created
  + resource "kubernetes_secret" "db_credentials" { ... }

  # kubernetes_deployment.api_gateway will be created
  + resource "kubernetes_deployment" "api_gateway" { ... }

  # kubernetes_service.api_gateway will be created
  + resource "kubernetes_service" "api_gateway" { ... }

Plan: 5 to add, 0 to change, 0 to destroy.
```

Read every line. The `+` means "create." You will also see `~` for "modify in place" and `-` for "destroy." In production, you review this plan in a pull request before anyone runs `apply`.

### Step 3: terraform apply

```bash
terraform apply -var-file=dev.tfvars
```

Terraform shows the plan again and asks for confirmation:

```
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes
```

Type `yes`. Terraform creates the resources:

```
kubernetes_namespace.ticketpulse: Creating...
kubernetes_namespace.ticketpulse: Creation complete after 0s [id=ticketpulse]
kubernetes_config_map.api_config: Creating...
kubernetes_secret.db_credentials: Creating...
kubernetes_config_map.api_config: Creation complete after 0s
kubernetes_secret.db_credentials: Creation complete after 0s
kubernetes_deployment.api_gateway: Creating...
kubernetes_deployment.api_gateway: Creation complete after 5s
kubernetes_service.api_gateway: Creating...
kubernetes_service.api_gateway: Creation complete after 0s

Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:
  api_gateway_service = "api-gateway"
  api_replicas        = 3
  namespace           = "ticketpulse"
```

Verify:

```bash
kubectl get all -n ticketpulse
```

You should see the exact same resources as when you applied YAML manually in L2-M43 -- but now they are defined in code, version-controlled, and reproducible.

---

## 4. State Management

After `terraform apply`, a `terraform.tfstate` file appears. This is critical.

```bash
ls -la terraform.tfstate
# ~50KB JSON file
```

### What is the state file?

The state file maps your Terraform resources to real infrastructure. Without it, Terraform cannot know what already exists.

```bash
# Peek at the state (DO NOT edit manually)
terraform show
```

You will see every resource with its current attributes. Terraform uses this to compute diffs: "the config says 3 replicas, the state says 3 replicas, no change needed."

### Why it matters

- **Without state:** Terraform would try to create everything from scratch every time
- **Corrupted state:** Terraform loses track of resources. You have "orphaned" infrastructure
- **Stale state:** Terraform thinks resources exist that were already deleted (or vice versa)

### Remote backends

For team use, the state must be stored remotely with locking:

```hcl
# backend.tf (for production -- NOT needed for this local exercise)

terraform {
  backend "s3" {
    bucket         = "ticketpulse-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"    # Prevents concurrent modifications
    encrypt        = true                  # Encrypt state at rest
  }
}
```

**S3** stores the state file. **DynamoDB** provides locking so two engineers cannot run `terraform apply` simultaneously. **Encryption** is essential because the state contains all your secret values in plaintext.

> **Rule:** Never commit `terraform.tfstate` to Git. Add it to `.gitignore`. In CI/CD, always use a remote backend.

---

## 5. Build: A Reusable Terraform Module

You will write the same Deployment + Service pattern for every TicketPulse microservice. Instead of copying, create a module.

```bash
mkdir -p ticketpulse/terraform/modules/ticketpulse-service
```

```hcl
# modules/ticketpulse-service/variables.tf

variable "name" {
  description = "Service name"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "image" {
  description = "Docker image"
  type        = string
}

variable "port" {
  description = "Container port"
  type        = number
}

variable "replicas" {
  description = "Number of replicas"
  type        = number
  default     = 2
}

variable "cpu_request" {
  description = "CPU request"
  type        = string
  default     = "100m"
}

variable "memory_request" {
  description = "Memory request"
  type        = string
  default     = "128Mi"
}

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
  default     = "500m"
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
  default     = "512Mi"
}

variable "config_map_name" {
  description = "ConfigMap to attach"
  type        = string
}

variable "secret_name" {
  description = "Secret to attach"
  type        = string
}

variable "health_path" {
  description = "Health check endpoint path"
  type        = string
  default     = "/health"
}

variable "labels" {
  description = "Additional labels"
  type        = map(string)
  default     = {}
}
```

```hcl
# modules/ticketpulse-service/main.tf

resource "kubernetes_deployment" "service" {
  metadata {
    name      = var.name
    namespace = var.namespace

    labels = merge({
      app        = var.name
      managed_by = "terraform"
    }, var.labels)
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app = var.name
      }
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_unavailable = "1"
        max_surge       = "1"
      }
    }

    template {
      metadata {
        labels = merge({
          app = var.name
        }, var.labels)
      }

      spec {
        container {
          name              = var.name
          image             = var.image
          image_pull_policy = "Never"

          port {
            container_port = var.port
          }

          env_from {
            config_map_ref {
              name = var.config_map_name
            }
          }

          env_from {
            secret_ref {
              name = var.secret_name
            }
          }

          resources {
            requests = {
              cpu    = var.cpu_request
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit
              memory = var.memory_limit
            }
          }

          readiness_probe {
            http_get {
              path = var.health_path
              port = var.port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = var.health_path
              port = var.port
            }
            initial_delay_seconds = 15
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "service" {
  metadata {
    name      = var.name
    namespace = var.namespace
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = var.name
    }

    port {
      port        = var.port
      target_port = var.port
    }
  }
}
```

```hcl
# modules/ticketpulse-service/outputs.tf

output "service_name" {
  value = kubernetes_service.service.metadata[0].name
}

output "deployment_name" {
  value = kubernetes_deployment.service.metadata[0].name
}
```

Now use the module for all services:

```hcl
# services.tf (in the root terraform directory)

module "api_gateway" {
  source = "./modules/ticketpulse-service"

  name            = "api-gateway"
  namespace       = kubernetes_namespace.ticketpulse.metadata[0].name
  image           = var.api_image
  port            = 3000
  replicas        = var.api_replicas
  config_map_name = kubernetes_config_map.api_config.metadata[0].name
  secret_name     = kubernetes_secret.db_credentials.metadata[0].name

  labels = {
    tier = "frontend"
  }
}

module "event_service" {
  source = "./modules/ticketpulse-service"

  name            = "event-service"
  namespace       = kubernetes_namespace.ticketpulse.metadata[0].name
  image           = var.event_service_image
  port            = 3001
  replicas        = var.event_service_replicas
  config_map_name = kubernetes_config_map.api_config.metadata[0].name
  secret_name     = kubernetes_secret.db_credentials.metadata[0].name

  labels = {
    tier = "backend"
  }
}

module "payment_service" {
  source = "./modules/ticketpulse-service"

  name            = "payment-service"
  namespace       = kubernetes_namespace.ticketpulse.metadata[0].name
  image           = var.payment_service_image
  port            = 3002
  replicas        = var.payment_service_replicas
  config_map_name = kubernetes_config_map.api_config.metadata[0].name
  secret_name     = kubernetes_secret.db_credentials.metadata[0].name

  labels = {
    tier = "backend"
  }
}
```

```bash
# Reinitialize to pick up the module
terraform init

# Plan -- should show 3 deployments + 3 services
terraform plan -var-file=dev.tfvars
```

Three services, each with identical operational characteristics, defined in 15 lines of configuration each. Change the module once, all services update.

---

## 6. Debug: Infrastructure Drift

Drift happens when someone changes infrastructure outside of Terraform. Let us cause it.

```bash
# Manually scale the API gateway outside Terraform
kubectl scale deployment api-gateway -n ticketpulse --replicas=5
```

Now run plan:

```bash
terraform plan -var-file=dev.tfvars
```

Terraform detects the drift:

```
  # module.api_gateway.kubernetes_deployment.service will be updated in-place
  ~ resource "kubernetes_deployment" "service" {
      ~ spec {
          ~ replicas = 5 -> 3    # Terraform wants to change it back to 3
        }
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

Terraform sees: "The state says 3 replicas, the actual infrastructure has 5 replicas, the config says 3 replicas. I need to change the actual infrastructure back to 3."

This is the power of declarative IaC. The code is the source of truth. If you want 5 replicas, change the variable in code and go through the PR process.

```bash
# Apply to fix the drift
terraform apply -var-file=dev.tfvars
```

---

## 7. terraform import: Adopting Existing Resources

What if you already have resources created manually and want to bring them under Terraform management?

```bash
# First, create something manually
kubectl create namespace legacy-app

# Now write the Terraform config for it
```

Add to a file:

```hcl
# legacy.tf
resource "kubernetes_namespace" "legacy" {
  metadata {
    name = "legacy-app"
  }
}
```

If you run `terraform plan` now, it will try to CREATE the namespace (which already exists). Instead, import it:

```bash
terraform import kubernetes_namespace.legacy legacy-app
```

```
kubernetes_namespace.legacy: Importing from ID "legacy-app"...
kubernetes_namespace.legacy: Import successful!
```

Now `terraform plan` shows no changes -- Terraform knows about the existing resource and the config matches.

```bash
terraform plan -var-file=dev.tfvars
# No changes. Your infrastructure matches the configuration.
```

> **Tip:** `terraform import` only updates the state file. You still need to write the matching config in `.tf` files. If the config does not match the real resource, the next `plan` will show changes.

---

## 8. Terraform Workflow in a Team

The real-world workflow looks like this:

1. **Branch:** Create a feature branch
2. **Write:** Add or modify `.tf` files
3. **Plan:** Run `terraform plan` and paste the output in the PR
4. **Review:** Team reviews the plan (what will be created, changed, destroyed)
5. **Merge:** Approve and merge to main
6. **Apply:** CI/CD runs `terraform apply` from the main branch

Many teams use tools like Atlantis or Spacelift to automate this: when you open a PR, a bot runs `terraform plan` and comments with the output. When you merge, it runs `terraform apply`.

The key principle: **nobody runs `terraform apply` from their laptop in production.** All applies happen through CI/CD on the main branch.

---

## 9. Reflect

> **"What happens if the state file is deleted?"**
>
> Terraform forgets about all existing resources. Running `terraform apply` would try to create everything from scratch, which would fail because the resources already exist (name conflicts). Recovery: re-import every resource, or restore from a state backup. This is why remote backends with versioning are essential.

> **"Terraform vs Pulumi vs CDK -- when would you choose each?"**
>
> **Terraform:** Multi-cloud, massive ecosystem of providers, mature tooling. Best for most teams. The HCL DSL is limited but simple. Choose when you need multi-cloud or have complex module reuse.
>
> **Pulumi:** Write infrastructure in TypeScript, Python, or Go. Full language power (loops, conditionals, functions). Choose when your IaC has complex logic, or your team is allergic to learning a DSL.
>
> **AWS CDK:** TypeScript/Python that compiles to CloudFormation. Deep AWS integration, excellent constructs library. Choose when you are AWS-only and want tight integration with AWS services.

> **"We defined K8s resources in Terraform. Could we also define them in YAML and apply with kubectl? When would you do one vs the other?"**
>
> Both work. Terraform is better when K8s is one part of a larger infrastructure stack (you want the cluster, the database, the DNS record, AND the K8s resources in one workflow). kubectl + YAML (or Helm/Kustomize) is better when a separate team manages the cluster and you only manage your application manifests. Many teams use Terraform for infrastructure (clusters, databases, networking) and Helm/ArgoCD for application deployments.

---

## 10. Checkpoint

After this module, your TicketPulse Terraform setup should have:

- [ ] Terraform installed and initialized
- [ ] Provider configuration for Kubernetes and Helm
- [ ] Variables with types, descriptions, and defaults
- [ ] Namespace, ConfigMap, and Secret resources
- [ ] A reusable module for TicketPulse services (Deployment + Service)
- [ ] All three services (API gateway, event service, payment service) using the module
- [ ] `terraform plan` shows no changes (infrastructure matches config)
- [ ] You have detected and fixed infrastructure drift
- [ ] You have imported an existing resource with `terraform import`
- [ ] `.tfvars` file for local development (not committed to Git)
- [ ] Understanding of remote state backends (S3 + DynamoDB)

**Next up:** L2-M45 where we add Prometheus and Grafana to monitor everything we have deployed.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Infrastructure as Code (IaC)** | Managing infrastructure through version-controlled configuration files instead of manual processes or interactive tools. |
| **HCL** | HashiCorp Configuration Language. Terraform's declarative DSL for defining infrastructure. |
| **Provider** | A Terraform plugin that interacts with a specific platform (AWS, GCP, Kubernetes, etc.). |
| **Resource** | A single piece of infrastructure managed by Terraform (an instance, a database, a namespace). |
| **State** | Terraform's record of what infrastructure exists and how it maps to your configuration. Stored in `terraform.tfstate`. |
| **Plan** | A preview of what Terraform will do. Shows creates, updates, and destroys before any changes are made. |
| **Module** | A reusable package of Terraform configuration. Takes inputs (variables), produces outputs, encapsulates complexity. |
| **Drift** | When actual infrastructure differs from the Terraform configuration, usually from manual changes. |
| **Remote Backend** | Storing Terraform state in a shared location (S3, GCS, Terraform Cloud) with locking for team use. |
| **terraform import** | A command that brings existing infrastructure under Terraform management by adding it to the state file. |
| **Sensitive Variable** | A variable marked `sensitive = true`. Its value is redacted from plan output and logs. |

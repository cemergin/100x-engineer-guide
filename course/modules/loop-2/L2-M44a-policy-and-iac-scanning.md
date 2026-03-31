# L2-M44a: Policy & IaC Security Scanning

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide (Sections 2 & 8)

## What You'll Learn

- Why policy-as-code matters and where it fits in the deployment pipeline
- Running Checkov against TicketPulse's Terraform to catch misconfigurations before they reach production
- Writing custom Checkov policies for your team's standards
- Writing OPA/Rego policies and evaluating Terraform plans with conftest
- Deploying Kyverno policies to enforce security standards in your Kubernetes cluster
- The layered approach: static scanning → plan validation → admission control
- Debugging policy failures and understanding what happens when checks fail

## Why This Matters

In L2-M44, you wrote Terraform to define TicketPulse's infrastructure. Nothing in that workflow stops you from writing Terraform that deploys a container running as root, creates a Kubernetes Secret with no encryption, or defines a Deployment with no resource limits. The `terraform apply` succeeds. The cluster runs fine. Three months later, a container escape gives an attacker root on the node because your pod had `privileged: true`. Or your namespace has no ResourceQuota and a single runaway pod eats all the cluster memory, taking down every other service.

**Concrete scenario:** A junior developer on the TicketPulse team adds a new analytics service. They copy-paste a Deployment manifest, forget to set `runAsNonRoot`, skip resource limits (they are running locally and "it works"), and remove the `team` label because the linter complained and they did not know what value to use. The PR gets merged because the reviewer focused on the application code. In production, the analytics pod runs as root and consumes 8 GB of memory during a traffic spike, starving the payment service. Customers cannot complete purchases for 40 minutes.

Policy-as-code catches every one of those mistakes automatically. It turns security requirements into executable checks that run at three layers: on the developer's machine, in the CI pipeline, and at the Kubernetes admission layer. A bad configuration never makes it past a pull request.

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — tool versions, policy check IDs, and Kyverno API versions evolve frequently. The concepts and patterns remain the same regardless of version.

## Prereq Check

You need the Terraform project and kind cluster from L2-M44 running.

```bash
# Install scanning tools
# macOS
brew install checkov         # Multi-framework IaC scanner
brew install conftest        # OPA-based policy testing for structured data

# Linux (pip works on both)
pip install checkov
# conftest: download binary from https://github.com/open-policy-agent/conftest/releases

# Verify installations
checkov --version
# Checkov 3.x.x

conftest --version
# Conftest v0.x.x

# Verify your kind cluster and Terraform from L2-M44 are running
kubectl get nodes --context kind-ticketpulse
terraform version

# Install Kyverno in your cluster
kubectl create -f https://github.com/kyverno/kyverno/releases/latest/download/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kyverno -n kyverno --timeout=120s

# Verify Kyverno is running
kubectl get pods -n kyverno
# You should see kyverno-admission-controller, kyverno-background-controller, etc.
```

---

## 1. The Layered Approach to Policy

Before writing any policies, understand where each tool fits. The most effective organizations enforce policy at multiple layers, because no single layer catches everything:

```
Layer 4: Cloud-Native Guardrails (SCPs, Azure Policy)
         Hardest controls. Cannot be bypassed by developers.
         Use for: region restrictions, disabling dangerous services.

Layer 3: Runtime Admission Control (Kyverno, OPA/Gatekeeper)
         Evaluates resources at deploy time in Kubernetes.
         Use for: pod security, resource limits, label requirements.

Layer 2: CI/CD Pipeline Scanning (Checkov, conftest)
         Catches issues before they reach production.
         Use for: Terraform misconfigs, compliance checks, plan validation.

Layer 1: Developer Workstation (Checkov pre-commit, IDE plugins)
         Fastest feedback loop.
         Use for: immediate security feedback as you write code.
```

In this module, we build layers 1 through 3 for TicketPulse:

| Layer | Tool | What it checks | When it runs |
|-------|------|---------------|-------------|
| 1 & 2 | **Checkov** | Static Terraform/K8s misconfigurations | Pre-commit and CI |
| 2 | **conftest** | Terraform plan JSON against custom Rego rules | CI, after `terraform plan` |
| 3 | **Kyverno** | Live Kubernetes resources at admission time | Every `kubectl apply` / deploy |

Each layer catches different problems. Checkov finds issues in your `.tf` files before you ever run `plan`. conftest catches issues in the computed plan (dynamic values, interpolated strings). Kyverno catches issues at deploy time, including resources created by Helm charts, operators, or manual `kubectl` commands that never went through your CI pipeline.

---

## 2. Static Scanning with Checkov

Checkov scans Terraform, CloudFormation, Kubernetes manifests, Helm charts, and Dockerfiles against 1,000+ built-in policies covering CIS, SOC2, HIPAA, and PCI-DSS benchmarks.

### 2a. Run Checkov Against TicketPulse

Navigate to your Terraform directory from L2-M44 and run Checkov:

```bash
cd ticketpulse/terraform
checkov -d .
```

You will see output like this:

```
       _               _
   ___| |__   ___  ___| | _______   __
  / __| '_ \ / _ \/ __| |/ / _ \ \ / /
 | (__| | | |  __/ (__|   < (_) \ V /
  \___|_| |_|\___|\___|_|\_\___/ \_/

By Prisma Cloud | version: 3.2.x

terraform scan results:

Passed checks: 8, Failed checks: 12, Skipped checks: 0

Check: CKV_K8S_28: "Ensure that the --service-account-lookup argument is set to true"
        FAILED for resource: kubernetes_deployment.api_gateway
        File: /api-gateway.tf:3-62
        Guide: https://docs.prismacloud.io/en/enterprise-edition/policy-reference/...

Check: CKV_K8S_37: "Ensure that the pod containers are running with read-only root filesystem"
        FAILED for resource: kubernetes_deployment.api_gateway
        File: /api-gateway.tf:3-62

Check: CKV_K8S_22: "Ensure that the container is not running as root"
        FAILED for resource: kubernetes_deployment.api_gateway
        File: /api-gateway.tf:3-62

Check: CKV_K8S_40: "Ensure that the pod does not use the default service account"
        FAILED for resource: kubernetes_deployment.api_gateway
        File: /api-gateway.tf:3-62

Check: CKV_K8S_43: "Ensure that the Tiller (Helm v2) is not deployed"
        PASSED for resource: kubernetes_deployment.api_gateway

Check: CKV_K8S_8: "Ensure that the liveness probe is configured"
        PASSED for resource: kubernetes_deployment.api_gateway

Check: CKV_K8S_9: "Ensure that the readiness probe is configured"
        PASSED for resource: kubernetes_deployment.api_gateway
```

### 2b. Triage the Findings

Not every finding is a real risk for your setup. For each finding, you need to decide: **fix now**, **accept with reason**, or **skip (false positive)**.

Here is how to think about the TicketPulse findings:

| Check | Description | Verdict | Reasoning |
|-------|-------------|---------|-----------|
| CKV_K8S_22 | Container not running as root | **Fix now** | Real risk. A root container can escape to the host. |
| CKV_K8S_37 | Read-only root filesystem | **Fix now** | Prevents attackers from writing to the container filesystem. |
| CKV_K8S_40 | Default service account | **Fix now** | Default SA may have excessive permissions. |
| CKV_K8S_28 | Service account lookup | **Skip** | Not applicable to our kind cluster. |

### 2c. Fix Real Findings

Open your Terraform module from L2-M44 and add the security context. In `modules/ticketpulse-service/main.tf`, update the container spec:

```hcl
# modules/ticketpulse-service/main.tf
# Inside the template > spec block, add security_context before the container block:

    template {
      metadata {
        labels = merge({
          app = var.name
        }, var.labels)
      }

      spec {
        automount_service_account_token = false

        security_context {
          run_as_non_root = true
          run_as_user     = 1000
          run_as_group    = 1000
          fs_group        = 1000
        }

        container {
          name              = var.name
          image             = var.image
          image_pull_policy = "Never"

          security_context {
            read_only_root_filesystem = true
            allow_privilege_escalation = false
            capabilities {
              drop = ["ALL"]
            }
          }

          # ... rest of container spec (ports, env_from, resources, probes)
        }
      }
    }
```

Run Checkov again:

```bash
checkov -d .
```

You should see previously failing checks now pass:

```
Passed checks: 14, Failed checks: 6, Skipped checks: 0

Check: CKV_K8S_22: "Ensure that the container is not running as root"
        PASSED for resource: module.api_gateway.kubernetes_deployment.service

Check: CKV_K8S_37: "Ensure that the pod containers are running with read-only root filesystem"
        PASSED for resource: module.api_gateway.kubernetes_deployment.service
```

### 2d. Skip False Positives with Inline Comments

For checks that are genuinely not applicable, add skip comments in your Terraform files:

```hcl
resource "kubernetes_deployment" "service" {
  #checkov:skip=CKV_K8S_28:Service account lookup not applicable to local kind cluster
  metadata {
    name      = var.name
    namespace = var.namespace
  }
  # ...
}
```

Run Checkov and verify the skip:

```bash
checkov -d .
```

```
Passed checks: 14, Failed checks: 5, Skipped checks: 1

Check: CKV_K8S_28: "Ensure that the --service-account-lookup argument is set to true"
        SKIPPED for resource: module.api_gateway.kubernetes_deployment.service
        Suppress comment: Service account lookup not applicable to local kind cluster
```

### 2e. Write a Custom Checkov Policy

Checkov's built-in checks are generic. TicketPulse has its own standards: every Kubernetes Deployment must have a `team` label so on-call routing works, and every Deployment must have a `cost-center` label for billing attribution.

Create the custom policy directory and policy file:

```bash
mkdir -p policies/checkov/
```

```yaml
# policies/checkov/require-team-label.yaml
metadata:
  id: "CKV2_TICKETPULSE_1"
  name: "Ensure all TicketPulse deployments have a 'team' label"
  category: "GENERAL_SECURITY"
  severity: "HIGH"
definition:
  cond_type: "attribute"
  resource_types:
    - "kubernetes_deployment"
  attribute: "metadata.labels.team"
  operator: "exists"
```

```yaml
# policies/checkov/require-cost-center.yaml
metadata:
  id: "CKV2_TICKETPULSE_2"
  name: "Ensure all TicketPulse deployments have a 'cost-center' label"
  category: "GENERAL_SECURITY"
  severity: "MEDIUM"
definition:
  cond_type: "attribute"
  resource_types:
    - "kubernetes_deployment"
  attribute: "metadata.labels.cost-center"
  operator: "exists"
```

Run Checkov with the custom policies:

```bash
checkov -d . --external-checks-dir ./policies/checkov/
```

```
Check: CKV2_TICKETPULSE_1: "Ensure all TicketPulse deployments have a 'team' label"
        FAILED for resource: module.api_gateway.kubernetes_deployment.service
        File: /modules/ticketpulse-service/main.tf:3-78

Check: CKV2_TICKETPULSE_2: "Ensure all TicketPulse deployments have a 'cost-center' label"
        FAILED for resource: module.api_gateway.kubernetes_deployment.service
        File: /modules/ticketpulse-service/main.tf:3-78
```

Fix by adding the labels to your module. In `modules/ticketpulse-service/main.tf`:

```hcl
  metadata {
    name      = var.name
    namespace = var.namespace

    labels = merge({
      app         = var.name
      managed_by  = "terraform"
      team        = var.team
      cost-center = var.cost_center
    }, var.labels)
  }
```

Add the corresponding variables in `modules/ticketpulse-service/variables.tf`:

```hcl
variable "team" {
  description = "Team that owns this service (for on-call routing)"
  type        = string
}

variable "cost_center" {
  description = "Cost center for billing attribution"
  type        = string
}
```

Update `services.tf` to pass the new variables:

```hcl
module "api_gateway" {
  source = "./modules/ticketpulse-service"

  name            = "api-gateway"
  namespace       = kubernetes_namespace.ticketpulse.metadata[0].name
  image           = var.api_image
  port            = 3000
  replicas        = var.api_replicas
  config_map_name = kubernetes_config_map.api_config.metadata[0].name
  secret_name     = kubernetes_secret.db_credentials.metadata[0].name
  team            = "platform"
  cost_center     = "eng-platform"

  labels = {
    tier = "frontend"
  }
}
```

Run Checkov again to confirm the custom checks pass:

```bash
checkov -d . --external-checks-dir ./policies/checkov/
```

```
Check: CKV2_TICKETPULSE_1: "Ensure all TicketPulse deployments have a 'team' label"
        PASSED for resource: module.api_gateway.kubernetes_deployment.service

Check: CKV2_TICKETPULSE_2: "Ensure all TicketPulse deployments have a 'cost-center' label"
        PASSED for resource: module.api_gateway.kubernetes_deployment.service
```

### 2f. CI-Friendly Output

In your CI pipeline, you want machine-readable output and a non-zero exit code on failure:

```bash
# JUnit XML for CI systems (GitHub Actions, Jenkins)
checkov -d . --external-checks-dir ./policies/checkov/ -o junitxml > checkov-results.xml

# JSON output for custom processing
checkov -d . -o json > checkov-results.json

# Filter by severity in CI (fail only on HIGH and CRITICAL)
checkov -d . --check HIGH --check CRITICAL

# Compact output for pull request comments
checkov -d . --compact
```

---

## 3. Plan Validation with Conftest and OPA

Checkov scans your `.tf` files statically. But some issues only appear in the Terraform plan -- dynamic values, interpolated strings, computed attributes, and conditional resources. Conftest evaluates Terraform plan JSON against policies written in Rego, OPA's policy language.

### 3a. Generate the Plan JSON

```bash
cd ticketpulse/terraform

# Create the plan
terraform plan -var-file=dev.tfvars -out=tfplan

# Convert to JSON (conftest reads JSON, not the binary plan)
terraform show -json tfplan > tfplan.json
```

The JSON file contains every resource change Terraform will make, including computed values. This is what conftest evaluates.

### 3b. Write Your First Rego Policy

Create the policy directory:

```bash
mkdir -p policy/
```

Write a policy that ensures every TicketPulse namespace has a ResourceQuota (to prevent the runaway-pod scenario from the "Why This Matters" section):

```rego
# policy/terraform.rego
package main

import rego.v1

# Deny creating a namespace without a corresponding ResourceQuota
deny contains msg if {
    some resource in input.resource_changes
    resource.type == "kubernetes_namespace"
    resource.change.actions[_] == "create"
    ns_name := resource.change.after.metadata[0].name
    not has_quota_for(ns_name)
    msg := sprintf(
        "Namespace '%s' must have a ResourceQuota. Add a kubernetes_resource_quota resource for this namespace.",
        [ns_name]
    )
}

has_quota_for(ns_name) if {
    some resource in input.resource_changes
    resource.type == "kubernetes_resource_quota"
    resource.change.after.metadata[0].namespace == ns_name
}

# Deny deployments without resource limits
deny contains msg if {
    some resource in input.resource_changes
    resource.type == "kubernetes_deployment"
    resource.change.actions[_] == "create"
    name := resource.change.after.metadata[0].name

    some container in resource.change.after.spec[0].template[0].spec[0].container
    not container.resources[0].limits
    msg := sprintf(
        "Deployment '%s', container '%s': must have resource limits (CPU and memory).",
        [name, container.name]
    )
}

# Deny deployments with more than 10 replicas (cost guard)
deny contains msg if {
    some resource in input.resource_changes
    resource.type == "kubernetes_deployment"
    resource.change.actions[_] != "delete"
    replicas := resource.change.after.spec[0].replicas
    replicas > 10
    name := resource.change.after.metadata[0].name
    msg := sprintf(
        "Deployment '%s' requests %d replicas. Maximum allowed is 10. File a capacity request for more.",
        [name, replicas]
    )
}
```

### 3c. Run Conftest

```bash
conftest test tfplan.json --policy policy/
```

If your Terraform code has no ResourceQuota, you will see:

```
FAIL - tfplan.json - main - Namespace 'ticketpulse' must have a ResourceQuota. Add a kubernetes_resource_quota resource for this namespace.

1 test, 0 passed, 0 warnings, 1 failure
```

### 3d. Fix the Failure

Add a ResourceQuota to your Terraform configuration:

```hcl
# resource-quota.tf

resource "kubernetes_resource_quota" "ticketpulse" {
  metadata {
    name      = "ticketpulse-quota"
    namespace = kubernetes_namespace.ticketpulse.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = "4"
      "requests.memory" = "8Gi"
      "limits.cpu"      = "8"
      "limits.memory"   = "16Gi"
      "pods"            = "50"
    }
  }
}
```

Regenerate the plan and retest:

```bash
terraform plan -var-file=dev.tfvars -out=tfplan
terraform show -json tfplan > tfplan.json
conftest test tfplan.json --policy policy/
```

```
1 test, 1 passed, 0 warnings, 0 failures
```

### 3e. Add a Warning-Level Policy

Not every policy needs to block. Use `warn` for advisory policies:

```rego
# policy/terraform.rego (add to the same file)

# Warn if any deployment uses the :latest tag
warn contains msg if {
    some resource in input.resource_changes
    resource.type == "kubernetes_deployment"
    resource.change.actions[_] != "delete"
    name := resource.change.after.metadata[0].name

    some container in resource.change.after.spec[0].template[0].spec[0].container
    endswith(container.image, ":latest")
    msg := sprintf(
        "Deployment '%s', container '%s': uses ':latest' tag. Pin to a specific version for reproducibility.",
        [name, container.name]
    )
}
```

Run conftest again:

```bash
conftest test tfplan.json --policy policy/
```

```
WARN - tfplan.json - main - Deployment 'api-gateway', container 'api-gateway': uses ':latest' tag. Pin to a specific version for reproducibility.
WARN - tfplan.json - main - Deployment 'event-service', container 'event-service': uses ':latest' tag. Pin to a specific version for reproducibility.
WARN - tfplan.json - main - Deployment 'payment-service', container 'payment-service': uses ':latest' tag. Pin to a specific version for reproducibility.

1 test, 1 passed, 3 warnings, 0 failures
```

Warnings are visible but do not cause a non-zero exit code. Use them for gradual rollout of new policies: start as `warn`, promote to `deny` once the team has fixed existing violations.

### 3f. What Happens When conftest Fails in CI

In a GitHub Actions pipeline, conftest returns exit code 1 on any `deny` failure, which fails the workflow:

```yaml
# .github/workflows/terraform.yml (relevant job step)
- name: Validate Terraform plan
  run: |
    terraform plan -out=tfplan
    terraform show -json tfplan > tfplan.json
    conftest test tfplan.json --policy policy/ --all-namespaces
```

The developer sees the failure in the PR checks tab. They read the message, fix the Terraform code, push, and the check reruns. The merge button stays red until all `deny` rules pass.

---

## 4. Kubernetes Admission Control with Kyverno

Checkov and conftest catch issues in code and plans. But what about resources that bypass your CI pipeline? A developer running `kubectl apply` directly. A Helm chart creating pods. An operator generating resources. Kyverno is the last line of defense: it runs inside the Kubernetes cluster and evaluates every resource at admission time.

Unlike OPA/Gatekeeper (which requires Rego), Kyverno policies are pure YAML -- Kubernetes custom resources. It can **validate** (block bad resources), **mutate** (modify resources on the fly), and **generate** (create companion resources automatically).

### 4a. Policy 1: Require Labels

Every pod in the TicketPulse cluster must have `team` and `app` labels. Without them, you cannot route alerts to the right on-call team and your monitoring dashboards have blind spots.

```yaml
# kyverno/require-labels.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
  annotations:
    policies.kyverno.io/title: Require team and app labels
    policies.kyverno.io/description: >-
      All pods must have 'team' and 'app' labels for on-call routing
      and monitoring attribution.
    policies.kyverno.io/severity: high
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-team-and-app-labels
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: >-
          Pods must have 'team' and 'app' labels.
          Add them to your Deployment's pod template metadata.
          Example: team=platform, app=api-gateway
        pattern:
          metadata:
            labels:
              team: "?*"
              app: "?*"
```

Apply and verify:

```bash
kubectl apply -f kyverno/require-labels.yaml
```

```
clusterpolicy.kyverno.io/require-labels created
```

Test that it works -- try creating a pod without labels:

```bash
kubectl run test-no-labels --image=nginx -n ticketpulse
```

Kyverno blocks it:

```
Error from server: admission webhook "validate.kyverno.svc-fail" denied the request:

resource Pod/ticketpulse/test-no-labels was blocked due to the following policies:

require-labels:
  require-team-and-app-labels: >
    validation error: Pods must have 'team' and 'app' labels.
    Add them to your Deployment's pod template metadata.
    Example: team=platform, app=api-gateway
```

Now try with the required labels:

```bash
kubectl run test-with-labels --image=nginx -n ticketpulse \
  --labels="team=platform,app=test"
```

```
pod/test-with-labels created
```

Clean up:

```bash
kubectl delete pod test-with-labels -n ticketpulse
```

### 4b. Policy 2: Block Privileged Containers

A privileged container has full access to the host. It is the single most dangerous Kubernetes misconfiguration.

```yaml
# kyverno/block-privileged.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: block-privileged
  annotations:
    policies.kyverno.io/title: Block privileged containers
    policies.kyverno.io/description: >-
      Privileged containers have full host access. This policy denies
      any pod that sets privileged: true or adds dangerous capabilities.
    policies.kyverno.io/severity: critical
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: deny-privileged
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: >-
          Privileged containers are not allowed. Remove
          'securityContext.privileged: true' from your container spec.
        pattern:
          spec:
            containers:
              - securityContext:
                  privileged: "!true"
    - name: deny-privilege-escalation
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: >-
          Privilege escalation is not allowed. Set
          'securityContext.allowPrivilegeEscalation: false' on all containers.
        deny:
          conditions:
            any:
              - key: "{{ request.object.spec.containers[].securityContext.allowPrivilegeEscalation || `[false]` }}"
                operator: AnyIn
                value:
                  - true
```

Apply and test:

```bash
kubectl apply -f kyverno/block-privileged.yaml
```

Test with a privileged pod:

```bash
cat <<EOF | kubectl apply -n ticketpulse -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-privileged
  labels:
    team: platform
    app: test
spec:
  containers:
    - name: evil
      image: nginx
      securityContext:
        privileged: true
EOF
```

```
Error from server: error when creating "STDIN": admission webhook
"validate.kyverno.svc-fail" denied the request:

resource Pod/ticketpulse/test-privileged was blocked due to the following policies:

block-privileged:
  deny-privileged: >
    validation error: Privileged containers are not allowed. Remove
    'securityContext.privileged: true' from your container spec.
```

### 4c. Policy 3: Auto-Generate Default Deny NetworkPolicy

When a new namespace is created, Kyverno can automatically create a default-deny-ingress NetworkPolicy. This ensures no pod accepts traffic unless explicitly allowed -- a zero-trust starting point.

```yaml
# kyverno/default-deny-network.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: default-network-policy
  annotations:
    policies.kyverno.io/title: Generate default-deny NetworkPolicy
    policies.kyverno.io/description: >-
      Automatically creates a default-deny-ingress NetworkPolicy
      in every new namespace. Teams must explicitly create allow
      policies for their services.
spec:
  rules:
    - name: generate-default-deny
      match:
        any:
          - resources:
              kinds:
                - Namespace
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kube-public
                - kyverno
      generate:
        synchronize: true
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

Apply and test:

```bash
kubectl apply -f kyverno/default-deny-network.yaml
```

Create a test namespace and verify the NetworkPolicy was auto-generated:

```bash
kubectl create namespace test-kyverno-gen
```

Wait a few seconds, then check:

```bash
kubectl get networkpolicy -n test-kyverno-gen
```

```
NAME                   POD-SELECTOR   AGE
default-deny-ingress   <none>         5s
```

Kyverno created the NetworkPolicy automatically. Inspect it:

```bash
kubectl describe networkpolicy default-deny-ingress -n test-kyverno-gen
```

```
Name:         default-deny-ingress
Namespace:    test-kyverno-gen
Spec:
  PodSelector:     <none> (Coverage: all pods in the namespace)
  Allowing ingress traffic:
    <none> (Selected pods are isolated for ingress connectivity)
  Policy Types: Ingress
```

Clean up:

```bash
kubectl delete namespace test-kyverno-gen
```

### 4d. Policy 4: Mutate — Inject Default Resource Limits

Validation blocks bad resources. Mutation modifies resources to make them compliant. This policy adds default resource limits to any container that does not specify them:

```yaml
# kyverno/default-resources.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: default-resources
  annotations:
    policies.kyverno.io/title: Add default resource limits
    policies.kyverno.io/description: >-
      Injects default CPU and memory requests/limits into containers
      that do not specify them. Prevents runaway resource consumption.
spec:
  rules:
    - name: add-default-resources
      match:
        any:
          - resources:
              kinds:
                - Pod
      mutate:
        patchStrategicMerge:
          spec:
            containers:
              - (name): "*"
                resources:
                  requests:
                    memory: "64Mi"
                    cpu: "50m"
                  limits:
                    memory: "256Mi"
                    cpu: "250m"
```

Apply it:

```bash
kubectl apply -f kyverno/default-resources.yaml
```

Create a pod without resource limits and check what Kyverno does:

```bash
kubectl run test-no-resources --image=nginx -n ticketpulse \
  --labels="team=platform,app=test"

kubectl get pod test-no-resources -n ticketpulse -o jsonpath='{.spec.containers[0].resources}' | python3 -m json.tool
```

```json
{
    "limits": {
        "cpu": "250m",
        "memory": "256Mi"
    },
    "requests": {
        "cpu": "50m",
        "memory": "64Mi"
    }
}
```

Kyverno injected the default limits. The developer does not need to remember them. Clean up:

```bash
kubectl delete pod test-no-resources -n ticketpulse
```

### 4e. View All Policies and Their Status

```bash
# List all Kyverno policies
kubectl get clusterpolicy

# Check policy reports for existing resources
kubectl get policyreport -A

# Detailed status of a specific policy
kubectl describe clusterpolicy require-labels
```

---

## 5. Debugging Policy Failures

### What Happens When Checkov Fails in CI but Not Locally

**Symptom:** Checkov passes on your laptop but fails in CI with new findings.

**Common causes:**
1. **Different Checkov version.** Pin the version in CI: `pip install checkov==3.2.x`.
2. **Missing custom policy directory.** CI does not have the `--external-checks-dir` flag.
3. **Environment-specific `.tf` files.** CI scans files that you have in `.gitignore` locally.

**Debug steps:**

```bash
# Check your local version
checkov --version

# Run with verbose output to see which files are scanned
checkov -d . --list

# Run a specific check to isolate the problem
checkov -d . --check CKV_K8S_22
```

### What Happens When conftest Denies a Valid Plan

**Symptom:** conftest returns `FAIL` but you believe the plan is correct.

**Debug steps:**

```bash
# See what conftest is reading (the raw plan JSON)
cat tfplan.json | python3 -m json.tool | head -100

# Test a single policy file
conftest test tfplan.json --policy policy/terraform.rego

# Use the --trace flag to see Rego evaluation step by step
conftest test tfplan.json --policy policy/ --trace
```

The trace output shows exactly which Rego rules matched and why:

```
TRAC   Enter data.main.deny
TRAC   | Eval some resource in input.resource_changes
TRAC   | Eval resource.type == "kubernetes_namespace"
TRAC   | Eval resource.change.actions[_] == "create"
TRAC   | Eval ns_name := resource.change.after.metadata[0].name
TRAC   | Eval not has_quota_for(ns_name)
TRAC   | Eval has_quota_for("ticketpulse")
TRAC   | Fail has_quota_for("ticketpulse")    <-- This is where it failed
```

### What Happens When Kyverno Blocks a Deployment

**Symptom:** `kubectl apply` or `terraform apply` fails because Kyverno rejected a resource.

The error message tells you exactly which policy and rule failed:

```
Error from server: admission webhook "validate.kyverno.svc-fail"
denied the request:

resource Deployment/ticketpulse/analytics-service was blocked
due to the following policies:

require-labels:
  require-team-and-app-labels: validation error: Pods must have
  'team' and 'app' labels.
```

**Debug steps:**

```bash
# Check what policies exist
kubectl get clusterpolicy

# See detailed policy status and any errors
kubectl describe clusterpolicy require-labels

# Check Kyverno's own logs for policy evaluation details
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --tail=50

# Test a resource against policies without applying (dry-run)
kubectl apply -f my-deployment.yaml --dry-run=server
```

The `--dry-run=server` flag sends the resource to the API server (including admission webhooks) but does not persist it. Use this to test whether Kyverno will accept a resource before committing to the apply.

### What Happens When Kyverno is Down

If the Kyverno admission controller pods crash, the webhook becomes unavailable. Depending on the webhook's `failurePolicy`:

- **`Fail`** (default for Kyverno Enforce): All resource creation/modification is blocked. This is safe but causes an outage in your deployment pipeline.
- **`Ignore`**: Resources are admitted without policy evaluation. This is less safe -- misconfigurations slip through.

Check webhook configuration:

```bash
kubectl get validatingwebhookconfigurations
kubectl describe validatingwebhookconfigurations kyverno-resource-validating-webhook-cfg
```

If Kyverno is down and blocking deployments:

```bash
# Check Kyverno pod status
kubectl get pods -n kyverno

# Check Kyverno logs for crash reasons
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --previous

# Restart Kyverno (if the pods are in CrashLoopBackOff)
kubectl rollout restart deployment kyverno-admission-controller -n kyverno
```

---

## 6. Putting It All Together: The TicketPulse Policy Pipeline

Here is how the three layers work together for TicketPulse:

```
Developer writes Terraform code
         │
         ▼
    ┌─────────────┐
    │   Checkov    │  Layer 1: Static scan on developer's machine
    │  (pre-commit)│  Catches: missing labels, no security context,
    │              │  no resource limits, privileged containers
    └──────┬──────┘
           │ passes
           ▼
    Push to GitHub, open PR
         │
         ▼
    ┌─────────────┐
    │   Checkov    │  Layer 2a: CI scan on the PR
    │  (CI/CD)    │  Same checks + custom TicketPulse policies
    └──────┬──────┘
           │ passes
           ▼
    ┌─────────────┐
    │   conftest   │  Layer 2b: Plan validation in CI
    │  (on plan)  │  Catches: missing ResourceQuota, >10 replicas,
    │              │  :latest tags, computed value violations
    └──────┬──────┘
           │ passes
           ▼
    PR approved and merged
         │
         ▼
    terraform apply (or ArgoCD sync)
         │
         ▼
    ┌─────────────┐
    │   Kyverno    │  Layer 3: Admission control in the cluster
    │  (admission)│  Catches: anything that bypassed CI (manual
    │              │  kubectl, operators, Helm charts)
    │              │  Also: mutates pods to add default limits
    └──────┬──────┘
           │ admitted
           ▼
    Pod runs in TicketPulse cluster
```

Every misconfiguration has at least two chances to get caught. Most have three.

---

## 7. Reflect

> **"If Checkov already checks for resource limits and runAsNonRoot, why do we also need Kyverno to check the same things in the cluster?"**
>
> Checkov only scans code that goes through your CI pipeline. But not everything enters the cluster through CI. A developer might run `kubectl apply` directly during an incident. A Helm chart might template pods that Checkov never sees. An operator (like the Kafka operator) might create pods programmatically. Kyverno catches all of these because it sits at the Kubernetes API server admission layer -- every resource creation passes through it, regardless of origin.

> **"When should a policy be a `warn` versus a `deny`?"**
>
> Start every new policy as `warn` (Checkov skip, conftest `warn`, Kyverno `Audit`). Run it for one to two weeks and observe the volume of violations. If the violations are few and the fix is straightforward, promote to `deny`/`Enforce`. If there are hundreds of violations, the policy needs gradual rollout: fix the existing violations first, then enforce. Blocking half the team's deployments on the first day creates resentment and policy circumvention.

> **"What is the difference between conftest and Checkov scanning a Terraform plan?"**
>
> Checkov comes with 1,000+ built-in checks and a framework for scanning static files -- it is a scanner with a broad rule library. conftest is a generic policy evaluation tool -- it runs arbitrary Rego against arbitrary JSON. Use Checkov when built-in checks cover your needs. Use conftest when you need custom organizational policies that reason about relationships between resources (like "every namespace must have a ResourceQuota"). Many teams use both.

> **"What would you add next to TicketPulse's policy pipeline?"**
>
> Consider: (1) Trivy scanning of container images for CVEs before deployment, (2) a Kyverno policy that requires image signatures (cosign) to ensure only images built by your CI can run, (3) Sentinel or OPA policies in Terraform Cloud for cost controls, (4) AWS SCPs to restrict which regions and services TicketPulse can use.

---

## 8. Checkpoint

After this module, your TicketPulse setup should have:

- [ ] Checkov installed and running against your Terraform directory
- [ ] At least 2 real Checkov findings fixed (security context, read-only filesystem)
- [ ] False positives skipped with inline `#checkov:skip` comments
- [ ] Custom Checkov policies for `team` and `cost-center` labels
- [ ] A `policy/terraform.rego` file with deny rules for ResourceQuota and replica limits
- [ ] A warning rule for `:latest` image tags
- [ ] conftest passing against your Terraform plan JSON
- [ ] A ResourceQuota added to the TicketPulse namespace
- [ ] Kyverno installed and running in your kind cluster
- [ ] Four Kyverno policies applied: require-labels, block-privileged, default-deny-network, default-resources
- [ ] Verified that Kyverno blocks a pod without labels and a privileged pod
- [ ] Verified that Kyverno auto-generates a NetworkPolicy for new namespaces
- [ ] Understanding of how the three layers (Checkov → conftest → Kyverno) work together

**Next up:** L2-M45 where we add Prometheus and Grafana to monitor everything we have deployed.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Policy as Code** | Treating governance rules, security guardrails, and compliance requirements as version-controlled code evaluated automatically. |
| **Checkov** | An open-source static analysis tool that scans IaC files (Terraform, K8s, Docker) against 1,000+ built-in security and compliance policies. |
| **OPA (Open Policy Agent)** | A CNCF-graduated general-purpose policy engine. Policies are written in Rego and evaluated against structured data (JSON/YAML). |
| **Rego** | OPA's declarative query language, designed for evaluating nested structured data. Used by conftest and Gatekeeper. |
| **conftest** | A command-line tool that tests structured data (Terraform plans, K8s manifests, Dockerfiles) against OPA/Rego policies. |
| **Kyverno** | A Kubernetes-native policy engine. Policies are YAML custom resources that can validate, mutate, and generate K8s resources. |
| **Admission Control** | The Kubernetes mechanism that intercepts API requests after authentication but before persistence. Kyverno and Gatekeeper use admission webhooks. |
| **Validate** | A Kyverno rule type that checks whether a resource meets a condition and blocks it if not. |
| **Mutate** | A Kyverno rule type that modifies a resource on admission (e.g., injecting default values). |
| **Generate** | A Kyverno rule type that automatically creates companion resources (e.g., a NetworkPolicy when a Namespace is created). |
| **ResourceQuota** | A Kubernetes object that limits the total resource consumption (CPU, memory, pod count) within a namespace. |
| **Static Analysis** | Examining code without executing it. Checkov scans `.tf` files; it does not run `terraform plan`. |
| **Plan Validation** | Evaluating the output of `terraform plan` (which includes computed and dynamic values) against policies. |
| **`validationFailureAction`** | Kyverno setting: `Enforce` blocks non-compliant resources; `Audit` logs violations without blocking. |

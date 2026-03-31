# L2-M44a: Policy & IaC Security Scanning

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why policy-as-code matters and where it fits in the deployment pipeline
- Running Checkov and Trivy against TicketPulse's Terraform to catch misconfigurations before they reach production
- Writing Kyverno policies to enforce security standards in your Kubernetes cluster
- Testing Terraform plans against custom OPA/Rego policies using conftest
- The layered approach: static scanning → plan validation → admission control

## Why This Matters

In L2-M44, you wrote Terraform to define TicketPulse's infrastructure. But nothing stops you from writing Terraform that creates a publicly accessible database, an S3 bucket with no encryption, or a security group that allows all inbound traffic. The `terraform apply` succeeds — and the breach happens three months later.

Policy-as-code catches these mistakes automatically. It turns security requirements into executable checks that run in your CI pipeline and at your Kubernetes admission layer. The goal: a bad configuration should never make it past a pull request.

## Prereq Check

```bash
# Install scanning tools
brew install checkov         # Multi-framework IaC scanner
brew install trivy           # Fast Terraform + container scanner

# Verify your kind cluster and Terraform from L2-M44 are running
kubectl get nodes --context kind-ticketpulse
terraform version

# Install Kyverno in your cluster
kubectl create -f https://github.com/kyverno/kyverno/releases/latest/download/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kyverno -n kyverno --timeout=120s
```

---

## 1. Static Scanning with Checkov

Run Checkov against TicketPulse's Terraform directory from L2-M44:

```bash
checkov -d ./terraform/
```

You will see output like:

```
Passed checks: 12, Failed checks: 5, Skipped checks: 0

Check: CKV_K8S_28: "Ensure that the --service-account-lookup argument is set to true"
  FAILED for resource: kubernetes_deployment.ticket_service
  File: /main.tf:42-78
  Guide: https://docs.prismacloud.io/en/...
```

### Exercise 1: 🔍 Explore — Triage Checkov Findings

Run Checkov against your L2-M44 Terraform files. For each finding:
1. Read the check description and linked guide
2. Classify it: **fix now** (real risk), **accept** (not applicable), or **skip** (false positive)
3. Fix at least 2 real findings (e.g., add resource limits, set `runAsNonRoot`)
4. Skip false positives with inline comments: `#checkov:skip=CKV_K8S_28:Reason here`

### Exercise 2: 🛠️ Build — Custom Checkov Policy

Write a custom YAML-based Checkov policy that enforces your team's standards:

```yaml
# policies/custom/require-team-label.yaml
metadata:
  id: "CKV2_CUSTOM_TP_1"
  name: "Ensure all Kubernetes deployments have a 'team' label"
  category: "GENERAL_SECURITY"
definition:
  cond_type: "attribute"
  resource_types:
    - "kubernetes_deployment"
  attribute: "metadata.labels.team"
  operator: "exists"
```

Run Checkov with your custom policy directory:

```bash
checkov -d ./terraform/ --external-checks-dir ./policies/custom/
```

---

## 2. Plan Validation with Conftest

Conftest evaluates Terraform plan JSON against OPA/Rego policies. This catches issues that static scanning misses (dynamic values, computed attributes).

### Exercise 3: 🛠️ Build — OPA Policy for Terraform Plans

Create a Rego policy that ensures all TicketPulse Kubernetes namespaces have resource quotas:

```bash
mkdir -p policy/
```

Write `policy/terraform.rego`:

```rego
package main

import rego.v1

deny contains msg if {
    some resource in input.resource_changes
    resource.type == "kubernetes_namespace"
    resource.change.actions[_] == "create"
    # Check that a resource_quota exists for this namespace
    not has_quota_for(resource.change.after.metadata[0].name)
    msg := sprintf("Namespace '%s' must have a ResourceQuota",
                   [resource.change.after.metadata[0].name])
}

has_quota_for(ns_name) if {
    some resource in input.resource_changes
    resource.type == "kubernetes_resource_quota"
    resource.change.after.metadata[0].namespace == ns_name
}
```

Test it:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
conftest test tfplan.json --policy policy/
```

---

## 3. Kubernetes Admission Control with Kyverno

### Exercise 4: 🛠️ Build — Kyverno Policies for TicketPulse

Apply these three policies to your cluster and verify they work:

**Policy 1: Require labels**
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-team-and-app-labels
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "Pods must have 'team' and 'app' labels."
        pattern:
          metadata:
            labels:
              team: "?*"
              app: "?*"
```

**Policy 2: Block privileged containers**

Write a Kyverno policy that denies any Pod with `securityContext.privileged: true`.

**Policy 3: Auto-add default network policy**

Write a Kyverno generate policy that creates a default-deny-ingress NetworkPolicy whenever a new namespace is created.

**Verification:**

```bash
# This should be DENIED (no labels):
kubectl run test-no-labels --image=nginx

# This should SUCCEED:
kubectl run test-with-labels --image=nginx --labels="team=platform,app=test"

# Create a namespace and verify NetworkPolicy was auto-generated:
kubectl create namespace test-kyverno
kubectl get networkpolicy -n test-kyverno
```

---

## 4. Putting It All Together

### Exercise 5: 🤔 Reflect — Design Your Pipeline

Draw a diagram showing where each policy tool runs in TicketPulse's deployment pipeline:

```
Developer workstation → PR → CI Pipeline → Merge → Deploy → Cluster
        ↓                ↓        ↓                           ↓
     (Trivy           (Checkov  (conftest                  (Kyverno
      pre-commit)      + Trivy)  on plan)                   admission)
```

For each stage, write down:
- What gets checked
- What happens on failure (block PR? warning? reject pod?)
- Who is responsible for fixing the issue

Compare your design with the "Layered Approach" in Chapter 35 §2.

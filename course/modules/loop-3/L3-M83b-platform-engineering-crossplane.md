# L3-M83b: Platform Engineering & Crossplane

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 75 min | 🔴 Expert | Prerequisites: L3-M83, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why platform engineering matters: reducing cognitive load for application teams
- Crossplane: managing cloud infrastructure through Kubernetes CRDs instead of Terraform
- Building Crossplane Compositions that let developers self-service databases and storage
- Backstage: the internal developer portal that ties services, docs, and infrastructure together
- The golden path: from developer request to running infrastructure with no cloud expertise needed

## Why This Matters

TicketPulse has grown. The platform team manages Terraform for VPCs, databases, caches, and Kubernetes clusters. Application teams want to create their own databases and storage buckets, but they should not need to learn Terraform, understand IAM policies, or know which AWS region to use.

Platform engineering solves this by building abstractions — simple interfaces (like `kind: Database, size: medium`) that hide cloud complexity. Crossplane makes Kubernetes the control plane for ALL infrastructure, not just containers. Backstage makes the platform discoverable and self-service.

This is staff+ engineer territory: designing the platform that makes other engineers productive.

## Prereq Check

```bash
# Verify your kind cluster from L3-M83 is running
kubectl get nodes --context kind-ticketpulse

# Install Crossplane
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm repo update
helm install crossplane crossplane-stable/crossplane \
  --namespace crossplane-system --create-namespace
kubectl wait --for=condition=ready pod -l app=crossplane -n crossplane-system --timeout=120s

# Verify Crossplane is running
kubectl get pods -n crossplane-system
```

---

## 1. Crossplane Fundamentals

Crossplane extends Kubernetes with **Providers** (cloud API plugins) and **Managed Resources** (cloud resources as K8s objects).

### Exercise 1: 🔍 Explore — Crossplane Architecture

Install the Kubernetes provider (no cloud account needed — manages K8s-native resources):

```bash
cat <<EOF | kubectl apply -f -
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-kubernetes
spec:
  package: xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.14.1
EOF

kubectl wait --for=condition=healthy provider/provider-kubernetes --timeout=120s
```

Create a Managed Resource — a Kubernetes namespace managed by Crossplane:

```yaml
apiVersion: kubernetes.crossplane.io/v1alpha2
kind: Object
metadata:
  name: ticketpulse-staging
spec:
  forProvider:
    manifest:
      apiVersion: v1
      kind: Namespace
      metadata:
        name: ticketpulse-staging
        labels:
          managed-by: crossplane
          environment: staging
  providerConfigRef:
    name: kubernetes-provider
```

Apply it and observe: Crossplane creates the namespace AND continuously reconciles it. Try deleting the namespace with `kubectl delete namespace ticketpulse-staging` — Crossplane recreates it.

---

## 2. Building Platform APIs with Compositions

### Exercise 2: 📐 Design — The "Database" Abstraction

Design a platform API that lets application teams request databases without knowing cloud details. You will create:

1. **CompositeResourceDefinition (XRD)** — the API schema (what users can request)
2. **Composition** — what gets created behind the scenes

**Step 1: Define the API**

```yaml
# platform/xrd-database.yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xdatabases.platform.ticketpulse.io
spec:
  group: platform.ticketpulse.io
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
                  description: "Database size: small (256MB), medium (1GB), large (4GB)"
                  enum: [small, medium, large]
                  default: small
              required:
                - size
            status:
              type: object
              properties:
                connectionSecret:
                  type: string
                  description: "Name of the Secret containing connection details"
```

**Step 2: Define the Composition** (what `size: medium` actually creates)

Since we are working locally with kind, the Composition creates a PostgreSQL StatefulSet + Service + Secret inside the cluster:

```yaml
# platform/composition-database.yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: database-local
  labels:
    crossplane.io/xrd: xdatabases.platform.ticketpulse.io
spec:
  compositeTypeRef:
    apiVersion: platform.ticketpulse.io/v1alpha1
    kind: XDatabase
  resources:
    - name: namespace
      base:
        apiVersion: kubernetes.crossplane.io/v1alpha2
        kind: Object
        spec:
          forProvider:
            manifest:
              apiVersion: v1
              kind: Namespace
              metadata:
                name: "" # patched
    - name: postgresql
      base:
        apiVersion: kubernetes.crossplane.io/v1alpha2
        kind: Object
        spec:
          forProvider:
            manifest:
              apiVersion: apps/v1
              kind: StatefulSet
              metadata:
                name: postgresql
              spec:
                replicas: 1
                selector:
                  matchLabels:
                    app: postgresql
                template:
                  metadata:
                    labels:
                      app: postgresql
                  spec:
                    containers:
                      - name: postgresql
                        image: postgres:16
                        resources:
                          requests:
                            memory: "256Mi"  # patched based on size
                            cpu: "250m"
                        env:
                          - name: POSTGRES_PASSWORD
                            value: "changeme"  # in production, use External Secrets
                        ports:
                          - containerPort: 5432
```

Apply both and create a database claim:

```yaml
# teams/ticket-team/database.yaml
apiVersion: platform.ticketpulse.io/v1alpha1
kind: Database
metadata:
  name: ticket-db
  namespace: ticketpulse
spec:
  size: medium
```

```bash
kubectl apply -f platform/
kubectl apply -f teams/ticket-team/database.yaml

# Watch Crossplane create the resources
kubectl get database -n ticketpulse
kubectl get xdatabase
kubectl get managed
```

---

## 3. Backstage Service Catalog

### Exercise 3: 🛠️ Build — Catalog Entries for TicketPulse

Write `catalog-info.yaml` files for each TicketPulse service. These register services in an internal developer portal:

```yaml
# ticket-service/catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: ticket-service
  description: Handles ticket purchases and reservations for TicketPulse
  annotations:
    github.com/project-slug: company/ticket-service
    grafana/dashboard-selector: "service=ticket-service"
  tags:
    - typescript
    - grpc
    - postgresql
spec:
  type: service
  lifecycle: production
  owner: ticket-team
  dependsOn:
    - component:default/events-service
    - resource:default/ticket-db
  providesApis:
    - ticket-api
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: ticket-api
  description: REST API for ticket operations
spec:
  type: openapi
  lifecycle: production
  owner: ticket-team
  definition:
    $text: ./openapi.yaml
```

Write catalog entries for:
1. `events-service` (depends on events-db, provides events-api)
2. `payments-service` (depends on ticket-service, stripe integration)
3. `ticket-db` and `events-db` as `Resource` kinds

---

## 4. The Golden Path

### Exercise 4: 📐 Design — TicketPulse Platform Blueprint

Design the complete platform stack for TicketPulse on paper:

```
┌──────────────────────────────────────────────────┐
│              Developer Portal (Backstage)          │
│  "I need a new microservice with a database"       │
├──────────────────────────────────────────────────┤
│              Self-Service APIs (Crossplane)         │
│  XRD: Database, Cache, MessageQueue                │
│  Compositions: map to real cloud resources          │
├──────────────────────────────────────────────────┤
│              GitOps (ArgoCD from L3-M83a)          │
│  Watches infra repo, auto-syncs to cluster         │
├──────────────────────────────────────────────────┤
│              Policy Gates (Kyverno from L2-M44a)   │
│  Enforce labels, security, resource limits          │
├──────────────────────────────────────────────────┤
│              Infrastructure (kind / cloud)          │
└──────────────────────────────────────────────────┘
```

For each layer, answer:
1. What is the input? (developer request, Git commit, K8s manifest)
2. What is the output? (running resource, policy violation, sync status)
3. What happens on failure? (PR blocked, sync failed, alert fired)

### Exercise 5: 🤔 Reflect — Platform Trade-offs

Consider these questions:

1. **Crossplane vs Terraform**: when would you choose one over the other? (Hint: think about who manages the infra and how they want to interact with it.)
2. **Abstraction level**: your `Database` XRD hides cloud details. What happens when a team needs a feature your abstraction does not expose (e.g., read replicas)? How do you balance simplicity with escape hatches?
3. **Adoption**: you have built this platform. Half the teams love it, half still use raw Terraform. How do you drive adoption without mandating it? (Hint: Chapter 7 §6 on "Platform as a Product.")
4. **Operational overhead**: Crossplane, ArgoCD, Kyverno, Backstage — that is four systems to maintain. At what team/org size does this investment pay off?

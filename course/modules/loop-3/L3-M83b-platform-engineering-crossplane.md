# L3-M83b: Platform Engineering & Crossplane

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 75 min | 🔴 Expert | Prerequisites: L3-M83, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why platform engineering matters: reducing cognitive load for application teams
- Installing Crossplane on a kind cluster and configuring the Kubernetes provider
- Building a CompositeResourceDefinition (XRD) that defines a "Database" platform API
- Writing a Composition that maps size tiers (small/medium/large) to PostgreSQL StatefulSets
- Using Claims to let developers self-service databases without cloud expertise
- Tracing the full Crossplane resource chain: Claim -> XR -> Managed Resources
- Understanding the Crossplane deletion lifecycle
- Building a Backstage service catalog with catalog-info.yaml for TicketPulse services
- Writing a Backstage scaffolder template for new microservice creation
- Designing a complete platform engineering stack and evaluating Crossplane vs Terraform trade-offs

## Why This Matters

TicketPulse has grown. Three teams (ticket, events, payments) each need databases, caches, and message queues. The platform team manages Terraform for VPCs, databases, and Kubernetes clusters. Application teams want to create their own databases, but they should not need to learn Terraform, understand IAM policies, or know which AWS region to use.

Platform engineering solves this by building abstractions -- simple interfaces (like `kind: Database, size: medium`) that hide cloud complexity. Crossplane makes Kubernetes the control plane for ALL infrastructure, not just containers. Backstage makes the platform discoverable and self-service.

This is staff+ engineer territory: designing the platform that makes other engineers productive. In L2-M44 you learned Terraform from the operator's perspective. Here you learn how to wrap that complexity behind a developer-friendly API.

## Prereq Check

You need the kind cluster from L3-M83, Helm, and kubectl.

```bash
# Verify your kind cluster is running
kubectl get nodes --context kind-ticketpulse

# If not running, recreate it
kind create cluster --name ticketpulse

# Verify Helm is installed
helm version
# Should show v3.x.x

# Verify kubectl is installed
kubectl version --client
```

> **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases -- Crossplane Helm charts, provider images, and API versions evolve frequently. The concepts and patterns remain the same regardless of version. Check https://crossplane.io/docs for current versions.

---

## 1. Crossplane Installation and Provider Setup

Crossplane runs inside your Kubernetes cluster as a set of controllers. It watches for custom resources (like `Database`) and reconciles them into real infrastructure -- the same reconciliation loop that keeps your Deployments running.

### 1a. Install Crossplane via Helm

```bash
# Add the Crossplane Helm repository
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm repo update

# Install Crossplane into its own namespace
helm install crossplane crossplane-stable/crossplane \
  --namespace crossplane-system \
  --create-namespace \
  --set args='{"--enable-usages"}'

# Wait for Crossplane pods to be ready
kubectl wait --for=condition=ready pod \
  -l app=crossplane \
  -n crossplane-system \
  --timeout=120s

# Verify the installation
kubectl get pods -n crossplane-system
```

You should see two pods running: the Crossplane pod (the main controller) and the RBAC manager.

```
NAME                                       READY   STATUS    RESTARTS   AGE
crossplane-6d67f8c8b5-x2k9l              1/1     Running   0          45s
crossplane-rbac-manager-7b4c6d5f9-m3n7p  1/1     Running   0          45s
```

### 1b. Install the Kubernetes Provider

Crossplane uses Providers to talk to infrastructure APIs. AWS has a provider, GCP has a provider, and -- critically for local development -- Kubernetes itself has a provider. This lets us build and test Compositions without a cloud account.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-kubernetes
spec:
  package: xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.14.1
EOF

# Wait for the provider to become healthy
kubectl wait --for=condition=healthy provider/provider-kubernetes --timeout=120s

# Verify -- you should see INSTALLED: True, HEALTHY: True
kubectl get providers
```

Expected output:

```
NAME                    INSTALLED   HEALTHY   PACKAGE                                                          AGE
provider-kubernetes     True        True      xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.14.1  30s
```

### 1c. Configure the Provider

The provider needs credentials to talk to the Kubernetes API. For a local kind cluster, we give it the in-cluster service account:

```bash
# Create a ServiceAccount for the provider
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: provider-kubernetes
  namespace: crossplane-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: provider-kubernetes-admin
subjects:
  - kind: ServiceAccount
    name: provider-kubernetes
    namespace: crossplane-system
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: kubernetes.crossplane.io/v1alpha1
kind: ProviderConfig
metadata:
  name: kubernetes-provider
spec:
  credentials:
    source: InjectedIdentity
EOF

kubectl get providerconfig
```

> In production you would never use `cluster-admin`. You would scope the ClusterRole to only the resources the provider needs to manage. For local development this is fine.

### 1d. Verify: Create a Managed Resource

Test that the provider works by creating a namespace through Crossplane:

```bash
cat <<'EOF' | kubectl apply -f -
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
EOF

# Verify the namespace was created
kubectl get namespace ticketpulse-staging --show-labels
```

Now test continuous reconciliation -- the key difference from Terraform:

```bash
# Delete the namespace manually
kubectl delete namespace ticketpulse-staging

# Wait a few seconds, then check again
sleep 10
kubectl get namespace ticketpulse-staging
```

Crossplane recreates it. Terraform would not notice until you ran `terraform plan`. This continuous reconciliation is why Crossplane is called "Kubernetes-native" -- it uses the same control loop that keeps your Deployment replicas running.

```bash
# Clean up the test resource
kubectl delete object ticketpulse-staging
```

---

## 2. Building a Platform API: The Database Abstraction

Platform engineering is about building abstractions. You want the ticket team to say "I need a medium database" without knowing whether it runs on RDS, CloudSQL, or a StatefulSet. Crossplane achieves this with three resources:

1. **CompositeResourceDefinition (XRD)** -- defines the API schema (what developers can request)
2. **Composition** -- defines the implementation (what actually gets created)
3. **Claim** -- what developers actually apply (a namespaced request against the API)

### 2a. Define the XRD (the API)

The XRD defines what parameters developers can set. Think of it as the OpenAPI schema for your platform:

```bash
mkdir -p platform/crossplane
cat <<'EOF' > platform/crossplane/xrd-database.yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xdatabases.platform.ticketpulse.io
spec:
  group: platform.ticketpulse.io
  names:
    kind: XDatabase
    plural: xdatabases
  # claimNames makes this available as a namespaced resource
  # Developers use "Database" (the Claim), not "XDatabase" (the XR)
  claimNames:
    kind: Database
    plural: databases
  connectionSecretKeys:
    - host
    - port
    - username
    - password
    - database
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
                  description: "Database size: small (256Mi, 250m CPU), medium (1Gi, 500m CPU), large (4Gi, 1 CPU)"
                  enum:
                    - small
                    - medium
                    - large
                  default: small
                teamName:
                  type: string
                  description: "Team that owns this database (used for labeling and RBAC)"
              required:
                - size
                - teamName
            status:
              type: object
              properties:
                host:
                  type: string
                  description: "Hostname to connect to the database"
                port:
                  type: string
                  description: "Port to connect to the database"
                ready:
                  type: string
                  description: "Whether the database is ready to accept connections"
EOF
```

Key design decisions:
- `claimNames` makes `Database` available as a namespaced resource. Teams apply Claims in their own namespace. The cluster-scoped `XDatabase` is the platform team's view.
- `connectionSecretKeys` defines what connection details get exposed. The Composition must produce a Secret with these keys.
- The `size` enum is the entire public API. Developers do not set CPU, memory, storage class, or replication -- the platform team decides those in the Composition.
- `teamName` is required for labeling and cost attribution.

### 2b. Define the Composition (the Implementation)

The Composition maps the developer-facing API to actual Kubernetes resources. For local kind, we create a PostgreSQL StatefulSet, a Service, and a ConfigMap with connection details.

```bash
cat <<'EOF' > platform/crossplane/composition-database.yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: database-local
  labels:
    crossplane.io/xrd: xdatabases.platform.ticketpulse.io
    provider: local
spec:
  compositeTypeRef:
    apiVersion: platform.ticketpulse.io/v1alpha1
    kind: XDatabase
  mode: Pipeline
  pipeline:
    # --- Resource: PostgreSQL StatefulSet ---
    - step: postgresql-statefulset
      functionRef:
        name: function-patch-and-transform
      input:
        apiVersion: pt.fn.crossplane.io/v1beta1
        kind: Resources
        resources:
          - name: postgresql
            base:
              apiVersion: kubernetes.crossplane.io/v1alpha2
              kind: Object
              spec:
                providerConfigRef:
                  name: kubernetes-provider
                forProvider:
                  manifest:
                    apiVersion: apps/v1
                    kind: StatefulSet
                    metadata:
                      name: ""       # patched below
                      namespace: ""  # patched below
                      labels:
                        app.kubernetes.io/managed-by: crossplane
                    spec:
                      serviceName: ""  # patched below
                      replicas: 1
                      selector:
                        matchLabels:
                          app: postgresql
                          database-claim: ""  # patched below
                      template:
                        metadata:
                          labels:
                            app: postgresql
                            database-claim: ""  # patched below
                        spec:
                          containers:
                            - name: postgresql
                              image: postgres:16
                              ports:
                                - containerPort: 5432
                                  name: postgresql
                              env:
                                - name: POSTGRES_DB
                                  value: appdb
                                - name: POSTGRES_USER
                                  value: appuser
                                - name: POSTGRES_PASSWORD
                                  value: changeme-use-external-secrets
                              resources:
                                requests:
                                  memory: "256Mi"
                                  cpu: "250m"
                                limits:
                                  memory: "256Mi"
                                  cpu: "250m"
                              volumeMounts:
                                - name: data
                                  mountPath: /var/lib/postgresql/data
                                  subPath: pgdata
                      volumeClaimTemplates:
                        - metadata:
                            name: data
                          spec:
                            accessModes: ["ReadWriteOnce"]
                            resources:
                              requests:
                                storage: "1Gi"
            patches:
              # Set the StatefulSet name to match the claim name
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.metadata.name
                transforms:
                  - type: string
                    string:
                      type: Format
                      fmt: "pg-%s"
              # Set the namespace from the claim namespace
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-namespace"]
                toFieldPath: spec.forProvider.manifest.metadata.namespace
              # Set serviceName to match
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.spec.serviceName
                transforms:
                  - type: string
                    string:
                      type: Format
                      fmt: "pg-%s"
              # Label the pods with the claim name
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.spec.selector.matchLabels["database-claim"]
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.spec.template.metadata.labels["database-claim"]
              # Size tier: small
              - type: FromCompositeFieldPath
                fromFieldPath: spec.size
                toFieldPath: spec.forProvider.manifest.spec.template.spec.containers[0].resources.requests.memory
                transforms:
                  - type: map
                    map:
                      small: "256Mi"
                      medium: "1Gi"
                      large: "4Gi"
              - type: FromCompositeFieldPath
                fromFieldPath: spec.size
                toFieldPath: spec.forProvider.manifest.spec.template.spec.containers[0].resources.limits.memory
                transforms:
                  - type: map
                    map:
                      small: "256Mi"
                      medium: "1Gi"
                      large: "4Gi"
              - type: FromCompositeFieldPath
                fromFieldPath: spec.size
                toFieldPath: spec.forProvider.manifest.spec.template.spec.containers[0].resources.requests.cpu
                transforms:
                  - type: map
                    map:
                      small: "250m"
                      medium: "500m"
                      large: "1000m"
              - type: FromCompositeFieldPath
                fromFieldPath: spec.size
                toFieldPath: spec.forProvider.manifest.spec.template.spec.containers[0].resources.limits.cpu
                transforms:
                  - type: map
                    map:
                      small: "250m"
                      medium: "500m"
                      large: "1000m"
              # Storage tier
              - type: FromCompositeFieldPath
                fromFieldPath: spec.size
                toFieldPath: spec.forProvider.manifest.spec.volumeClaimTemplates[0].spec.resources.requests.storage
                transforms:
                  - type: map
                    map:
                      small: "1Gi"
                      medium: "5Gi"
                      large: "20Gi"

          # --- Resource: PostgreSQL Service ---
          - name: postgresql-service
            base:
              apiVersion: kubernetes.crossplane.io/v1alpha2
              kind: Object
              spec:
                providerConfigRef:
                  name: kubernetes-provider
                forProvider:
                  manifest:
                    apiVersion: v1
                    kind: Service
                    metadata:
                      name: ""       # patched
                      namespace: ""  # patched
                    spec:
                      type: ClusterIP
                      selector:
                        app: postgresql
                        database-claim: ""  # patched
                      ports:
                        - port: 5432
                          targetPort: 5432
                          protocol: TCP
                          name: postgresql
            patches:
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.metadata.name
                transforms:
                  - type: string
                    string:
                      type: Format
                      fmt: "pg-%s"
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-namespace"]
                toFieldPath: spec.forProvider.manifest.metadata.namespace
              - type: FromCompositeFieldPath
                fromFieldPath: metadata.labels["crossplane.io/claim-name"]
                toFieldPath: spec.forProvider.manifest.spec.selector["database-claim"]
EOF
```

This is a long file. Study the key patterns:

- **`transforms: map`** is how size tiers work. `small` maps to `256Mi` memory, `medium` to `1Gi`, `large` to `4Gi`. The developer says "medium" and the platform decides the resource allocation.
- **`FromCompositeFieldPath`** patches pull values from the XR (the composite resource) and inject them into the managed resources. The claim name becomes the StatefulSet name with a `pg-` prefix.
- **`providerConfigRef`** on every resource points to the ProviderConfig we created in section 1c.

### 2c. Install the Patch-and-Transform Function

The Composition above uses Pipeline mode with the `function-patch-and-transform` function. Install it:

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: pkg.crossplane.io/v1beta1
kind: Function
metadata:
  name: function-patch-and-transform
spec:
  package: xpkg.upbound.io/crossplane-contrib/function-patch-and-transform:v0.7.0
EOF

kubectl wait --for=condition=healthy function/function-patch-and-transform --timeout=120s
```

### 2d. Apply the XRD and Composition

```bash
kubectl apply -f platform/crossplane/xrd-database.yaml
kubectl apply -f platform/crossplane/composition-database.yaml

# Verify the XRD is established
kubectl get xrd
```

Expected output:

```
NAME                                       ESTABLISHED   OFFERED   AGE
xdatabases.platform.ticketpulse.io        True          True      10s
```

`OFFERED: True` means the Claim kind (`Database`) is available for developers to use.

```bash
# Verify the new API is registered
kubectl api-resources | grep ticketpulse
```

You should see both the cluster-scoped XR and the namespaced Claim:

```
databases           platform.ticketpulse.io/v1alpha1   true    Database
xdatabases          platform.ticketpulse.io/v1alpha1   false   XDatabase
```

---

## 3. Developer Self-Service: Creating a Database with a Claim

Now switch hats. You are a developer on the ticket team. You do not know Terraform. You do not know which PostgreSQL version the platform uses. You just need a database.

### 3a. Create the TicketPulse Namespace

```bash
kubectl create namespace ticketpulse --dry-run=client -o yaml | kubectl apply -f -
```

### 3b. Create a Database Claim

```bash
mkdir -p teams/ticket-team
cat <<'EOF' > teams/ticket-team/database.yaml
# As a ticket-team developer, I need a medium database.
# I do not need to know about StatefulSets, PVCs, or resource limits.
apiVersion: platform.ticketpulse.io/v1alpha1
kind: Database
metadata:
  name: ticket-db
  namespace: ticketpulse
spec:
  size: medium
  teamName: ticket-team
EOF

kubectl apply -f teams/ticket-team/database.yaml
```

### 3c. Watch the Resource Chain

This is the critical observation. One `Database` claim triggers a chain of resources:

```bash
# The Claim (namespaced -- what the developer sees)
kubectl get database -n ticketpulse
```

```
NAME        SYNCED   READY   CONNECTION-SECRET   AGE
ticket-db   True     True                        30s
```

```bash
# The XR (cluster-scoped -- what the platform team sees)
kubectl get xdatabase
```

```
NAME                   SYNCED   READY   COMPOSITION      AGE
ticket-db-abc12        True     True    database-local   30s
```

```bash
# The Managed Resources (the actual Kubernetes Objects that Crossplane created)
kubectl get object
```

```
NAME                              SYNCED   READY   AGE
ticket-db-abc12-postgresql        True     True    30s
ticket-db-abc12-postgresql-svc   True     True    30s
```

```bash
# The actual StatefulSet and Service in the ticketpulse namespace
kubectl get statefulset -n ticketpulse
kubectl get service -n ticketpulse
kubectl get pods -n ticketpulse
```

```
NAME           READY   AGE
pg-ticket-db   1/1     45s

NAME           TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
pg-ticket-db   ClusterIP   10.96.45.123   <none>        5432/TCP   45s

NAME               READY   STATUS    RESTARTS   AGE
pg-ticket-db-0     1/1     Running   0          45s
```

The full resource chain:

```
Database (Claim)          -- developer creates this
  └── XDatabase (XR)      -- Crossplane creates this (cluster-scoped composite)
       ├── Object          -- Managed Resource: wraps the StatefulSet
       │    └── StatefulSet  -- actual PostgreSQL pod
       │         └── Pod     -- pg-ticket-db-0
       └── Object          -- Managed Resource: wraps the Service
            └── Service     -- pg-ticket-db (ClusterIP on port 5432)
```

The developer applied 7 lines of YAML. The platform created a StatefulSet with correctly sized resources, a headless Service, and persistent storage -- all governed by the platform team's Composition.

---

## 4. What Happens When You Delete the Claim

Understanding the deletion lifecycle is essential for platform engineering. Crossplane uses Kubernetes owner references to cascade deletes.

### 4a. Walkthrough: Deletion Cascade

```bash
# Step 1: Delete the claim
kubectl delete database ticket-db -n ticketpulse

# Step 2: Watch the chain unwind (run this quickly after deleting)
kubectl get xdatabase
kubectl get object
kubectl get statefulset -n ticketpulse
kubectl get pods -n ticketpulse
```

What happens in order:

1. **Claim deleted** -- `kubectl delete database ticket-db -n ticketpulse`
2. **XR deleted** -- Crossplane sees the Claim is gone and deletes the XDatabase
3. **Managed Resources deleted** -- Crossplane sees the XR is gone and deletes the Object resources
4. **Underlying resources deleted** -- The Kubernetes provider sees the Object resources are gone and deletes the StatefulSet and Service
5. **Pods terminated** -- Kubernetes sees the StatefulSet is gone and terminates the pods
6. **PVCs remain** -- By default, StatefulSet PVCs are NOT deleted (data protection). You would need an explicit `reclaimPolicy` or manual cleanup.

```bash
# PVCs survive deletion by default -- data protection
kubectl get pvc -n ticketpulse
```

This is intentional. In production, you never want a `kubectl delete` to wipe a database. The platform team can configure Crossplane's `deletionPolicy` on the Composition:
- `deletionPolicy: Delete` -- delete cloud resources when the XR is deleted (default)
- `deletionPolicy: Orphan` -- leave cloud resources running even after the XR is deleted

### 4b. Recreate for the Next Section

```bash
kubectl apply -f teams/ticket-team/database.yaml
# Wait for it to be ready
kubectl wait --for=condition=ready database/ticket-db -n ticketpulse --timeout=120s
```

---

## 5. Backstage Service Catalog

Backstage (by Spotify, CNCF Incubating) is an internal developer portal. While Crossplane handles the "create infrastructure" part, Backstage handles "discover what exists, who owns it, and where the docs are."

### 5a. catalog-info.yaml for All TicketPulse Services

Each service repository contains a `catalog-info.yaml` that registers it in Backstage.

**Ticket Service:**

```yaml
# ticket-service/catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: ticket-service
  description: Handles ticket purchases, reservations, and seat assignments for TicketPulse
  annotations:
    github.com/project-slug: ticketpulse/ticket-service
    backstage.io/techdocs-ref: dir:.
    pagerduty.com/service-id: P_TICKET_SVC
    grafana/dashboard-selector: "service=ticket-service"
    argocd/app-name: ticket-service
  tags:
    - typescript
    - grpc
    - postgresql
  links:
    - url: https://grafana.internal/d/ticket-service
      title: Grafana Dashboard
      icon: dashboard
    - url: https://runbooks.internal/ticket-service
      title: Runbook
      icon: docs
spec:
  type: service
  lifecycle: production
  owner: team-tickets
  system: ticketpulse
  dependsOn:
    - component:default/events-service
    - resource:default/ticket-db
  providesApis:
    - ticket-api
  consumesApis:
    - events-api
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: ticket-api
  description: REST/gRPC API for ticket operations (purchase, reserve, cancel)
spec:
  type: openapi
  lifecycle: production
  owner: team-tickets
  system: ticketpulse
  definition:
    $text: ./openapi.yaml
---
apiVersion: backstage.io/v1alpha1
kind: Resource
metadata:
  name: ticket-db
  description: PostgreSQL database for ticket data (purchases, reservations, seat maps)
  annotations:
    crossplane.io/claim-name: ticket-db
    crossplane.io/claim-namespace: ticketpulse
spec:
  type: database
  lifecycle: production
  owner: team-tickets
  system: ticketpulse
  dependencyOf:
    - component:default/ticket-service
```

**Events Service:**

```yaml
# events-service/catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: events-service
  description: Manages concert events, venues, artist lineups, and scheduling for TicketPulse
  annotations:
    github.com/project-slug: ticketpulse/events-service
    backstage.io/techdocs-ref: dir:.
    pagerduty.com/service-id: P_EVENTS_SVC
    grafana/dashboard-selector: "service=events-service"
    argocd/app-name: events-service
  tags:
    - typescript
    - rest
    - postgresql
    - elasticsearch
spec:
  type: service
  lifecycle: production
  owner: team-events
  system: ticketpulse
  dependsOn:
    - resource:default/events-db
  providesApis:
    - events-api
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: events-api
  description: REST API for event management (CRUD events, search, venue management)
spec:
  type: openapi
  lifecycle: production
  owner: team-events
  system: ticketpulse
  definition:
    $text: ./openapi.yaml
---
apiVersion: backstage.io/v1alpha1
kind: Resource
metadata:
  name: events-db
  description: PostgreSQL database for event data (events, venues, schedules)
  annotations:
    crossplane.io/claim-name: events-db
    crossplane.io/claim-namespace: ticketpulse
spec:
  type: database
  lifecycle: production
  owner: team-events
  system: ticketpulse
  dependencyOf:
    - component:default/events-service
```

**Payments Service:**

```yaml
# payments-service/catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payments-service
  description: Processes payments, refunds, and Stripe integration for TicketPulse
  annotations:
    github.com/project-slug: ticketpulse/payments-service
    backstage.io/techdocs-ref: dir:.
    pagerduty.com/service-id: P_PAYMENTS_SVC
    grafana/dashboard-selector: "service=payments-service"
    argocd/app-name: payments-service
  tags:
    - typescript
    - rest
    - stripe
    - postgresql
spec:
  type: service
  lifecycle: production
  owner: team-payments
  system: ticketpulse
  dependsOn:
    - component:default/ticket-service
    - resource:default/payments-db
  providesApis:
    - payments-api
  consumesApis:
    - ticket-api
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: payments-api
  description: REST API for payment processing (charge, refund, payment status)
spec:
  type: openapi
  lifecycle: production
  owner: team-payments
  system: ticketpulse
  definition:
    $text: ./openapi.yaml
---
apiVersion: backstage.io/v1alpha1
kind: Resource
metadata:
  name: payments-db
  description: PostgreSQL database for payment records and transaction history
  annotations:
    crossplane.io/claim-name: payments-db
    crossplane.io/claim-namespace: ticketpulse
spec:
  type: database
  lifecycle: production
  owner: team-payments
  system: ticketpulse
  dependencyOf:
    - component:default/payments-service
```

**The TicketPulse System (ties everything together):**

```yaml
# system/catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: System
metadata:
  name: ticketpulse
  description: Concert ticketing platform -- buy tickets, manage events, process payments
  annotations:
    github.com/project-slug: ticketpulse
  tags:
    - concert
    - ticketing
    - platform
spec:
  owner: team-platform
  domain: entertainment
```

Notice the relationship graph: `ticket-service` depends on `events-service` and `ticket-db`. `payments-service` depends on `ticket-service` and `payments-db`. Backstage renders this as a visual dependency graph so anyone in the company can understand the architecture.

### 5b. Backstage Scaffolder Template

The scaffolder lets developers create new services through a web form. When they click "Create," Backstage generates a Git repository from a template, complete with CI/CD, Kubernetes manifests, and a Crossplane database claim.

```yaml
# backstage/templates/new-ticketpulse-service.yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: new-ticketpulse-service
  title: Create a New TicketPulse Microservice
  description: >
    Scaffold a production-ready microservice with CI/CD pipeline,
    Kubernetes manifests, Crossplane database claim, and Backstage catalog entry.
  tags:
    - typescript
    - microservice
    - recommended
spec:
  owner: team-platform
  type: service
  parameters:
    - title: Service Details
      required:
        - name
        - description
        - owner
      properties:
        name:
          title: Service Name
          type: string
          description: "Lowercase, hyphenated (e.g., notification-service)"
          pattern: "^[a-z][a-z0-9-]*$"
          ui:autofocus: true
        description:
          title: Description
          type: string
          description: "One sentence describing what the service does"
        owner:
          title: Owner Team
          type: string
          description: "The team that will own and maintain this service"
          ui:field: OwnerPicker
          ui:options:
            catalogFilter:
              kind: Group
    - title: Infrastructure
      properties:
        needsDatabase:
          title: Needs a Database?
          type: boolean
          default: true
        databaseSize:
          title: Database Size
          type: string
          enum:
            - small
            - medium
            - large
          default: small
          description: "small (256Mi), medium (1Gi), large (4Gi)"
          ui:widget: select
        needsCache:
          title: Needs a Redis Cache?
          type: boolean
          default: false
  steps:
    - id: fetch-skeleton
      name: Fetch Service Skeleton
      action: fetch:template
      input:
        url: ./skeleton
        values:
          name: ${{ parameters.name }}
          description: ${{ parameters.description }}
          owner: ${{ parameters.owner }}
          needsDatabase: ${{ parameters.needsDatabase }}
          databaseSize: ${{ parameters.databaseSize }}
          needsCache: ${{ parameters.needsCache }}
    - id: publish
      name: Create GitHub Repository
      action: publish:github
      input:
        repoUrl: github.com?owner=ticketpulse&repo=${{ parameters.name }}
        description: ${{ parameters.description }}
        defaultBranch: main
        protectDefaultBranch: true
        requireCodeOwnerReviews: true
    - id: create-argocd-app
      name: Register with ArgoCD
      action: argocd:create-resources
      input:
        appName: ${{ parameters.name }}
        argoInstance: production
        namespace: ticketpulse
        repoUrl: https://github.com/ticketpulse/${{ parameters.name }}
        path: k8s/
    - id: register
      name: Register in Backstage Catalog
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps.publish.output.repoContentsUrl }}
        catalogInfoPath: /catalog-info.yaml
  output:
    links:
      - title: Open Repository
        url: ${{ steps.publish.output.remoteUrl }}
      - title: View in Backstage
        url: /catalog/default/component/${{ parameters.name }}
```

When a developer fills in this form and clicks "Create," the golden path executes:

1. A GitHub repository is created from the skeleton template
2. If `needsDatabase` is true, the skeleton includes a Crossplane `Database` claim YAML
3. ArgoCD is configured to watch the new repository
4. The service is registered in Backstage's catalog
5. ArgoCD syncs the manifests, Crossplane provisions the database, and the service is running

No tickets. No waiting for the platform team. Self-service in minutes.

---

## 6. Platform Stack Diagram Exercise

### Exercise: Design the TicketPulse Platform Stack

Draw (on paper, a whiteboard, or ASCII) the complete platform stack for TicketPulse. Use this template and fill in the specifics for each layer:

```
┌───────────────────────────────────────────────────────────┐
│                   Developer Portal (Backstage)             │
│  "I need a new microservice with a database"               │
│                                                            │
│  Components: ticket-service, events-service, payments-svc  │
│  APIs: ticket-api, events-api, payments-api                │
│  Resources: ticket-db, events-db, payments-db              │
│  Templates: new-ticketpulse-service                        │
├───────────────────────────────────────────────────────────┤
│               Self-Service APIs (Crossplane)               │
│                                                            │
│  XRD: Database (small/medium/large)                        │
│  XRD: Cache (future)                                       │
│  XRD: MessageQueue (future)                                │
│  Composition: database-local (kind), database-aws (prod)   │
├───────────────────────────────────────────────────────────┤
│               GitOps Reconciliation (ArgoCD)               │
│                                                            │
│  Watches: teams/*/  directories in infra repo              │
│  Auto-syncs Claims, Deployments, Services to cluster       │
├───────────────────────────────────────────────────────────┤
│              Policy & Compliance Gates (Kyverno)           │
│                                                            │
│  Enforce: resource limits, labels, image registries        │
│  Audit: namespace isolation, network policies              │
├───────────────────────────────────────────────────────────┤
│              Infrastructure (kind / AWS / GCP)             │
│                                                            │
│  Local: kind cluster with Crossplane                       │
│  Prod: EKS + RDS + ElastiCache + S3                       │
└───────────────────────────────────────────────────────────┘
```

For each layer, answer these questions:

1. **Input**: What triggers this layer? (developer form submission, Git commit, K8s manifest, API call)
2. **Output**: What does this layer produce? (running resource, Git repository, policy decision, sync status)
3. **Failure mode**: What happens when this layer fails? (PR blocked, sync error in ArgoCD, Crossplane error event, pod crash)
4. **Who owns it**: Which team is responsible? (platform team, application team, security team)

The golden path through the stack:

```
Developer fills Backstage form
  → Backstage creates GitHub repo with Crossplane Claim
    → ArgoCD detects new manifests in Git
      → ArgoCD applies Claim to cluster
        → Crossplane reconciles Claim into XR
          → Composition creates StatefulSet + Service
            → Kyverno validates resources against policies
              → Pods start, database is ready
                → Developer connects at pg-<name>:5432
```

---

## 7. Reflection: Crossplane vs Terraform Trade-offs

### Exercise: Consider These Questions

Work through each question. Write your answers before reading the discussion below.

**1. When would you choose Crossplane over Terraform?**

Think about: who manages the infrastructure, how they want to interact with it, and what your existing stack looks like.

*Discussion:* Choose Crossplane when:
- You already run Kubernetes and want one control plane for everything
- You need continuous reconciliation (drift detection is real-time, not "when someone runs plan")
- You want to build self-service platform APIs for application teams
- Your infra changes flow through GitOps (ArgoCD/Flux)

Choose Terraform when:
- You are provisioning foundational infrastructure (VPCs, clusters, DNS zones) that changes rarely
- Your team already knows HCL and has years of modules
- You need to manage resources across many providers in a single plan
- You do not run Kubernetes (Crossplane requires a K8s cluster to run)

Many organizations use both: Terraform for the foundation (VPC, EKS cluster, IAM) and Crossplane for the application-level resources (databases, caches, queues) that teams self-service.

**2. Abstraction escape hatches**

Your `Database` XRD exposes only `size` and `teamName`. What happens when the events team needs read replicas, or the payments team needs a specific PostgreSQL extension?

*Discussion:* This is the core tension of platform engineering. Options:
- Add optional fields to the XRD (`readReplicas: 2`, `extensions: ["pg_trgm"]`) -- increases API surface, but keeps things in the platform
- Create a new Composition variant (`database-with-replicas`) selected by a label
- Provide an escape hatch: let teams drop down to raw Managed Resources for exceptional cases, with a policy that requires platform team review
- The worst option: say "no" and force everyone through the same abstraction. That drives shadow IT.

**3. Adoption without mandates**

You have built this platform. Half the teams love it, half still use raw Terraform. How do you drive adoption?

*Discussion:* Treat the platform as a product (Chapter 7 section 6):
- Measure the golden path: "new service from zero to production in 12 minutes" vs the manual process (3 days of tickets and waiting)
- Make it opt-in first. Teams that adopt it become your advocates.
- Run blameless post-mortems. When a non-platform team has an incident caused by manual infrastructure, use it as a case study (not a blame exercise).
- Ship features developers want: "need a database? One YAML file." Not features the platform team wants: "we migrated to Crossplane Functions."

**4. Operational overhead**

Crossplane, ArgoCD, Kyverno, Backstage -- that is four systems to maintain. At what team/org size does this investment pay off?

*Discussion:* Rules of thumb:
- 1-3 teams: overkill. Use Terraform modules and a shared wiki.
- 4-10 teams: Crossplane + ArgoCD start paying off. Self-service saves more time than it costs to maintain.
- 10+ teams: the full stack (including Backstage) becomes essential. Without a portal, teams cannot discover what exists.
- The investment is not just tools -- it is the platform team's time to build Compositions, maintain templates, and support users. Budget 2-4 engineers for a meaningful platform effort.

---

## Checklist

Before moving on, verify you can answer "yes" to each:

- [ ] Crossplane is installed and the Kubernetes provider is healthy (`kubectl get providers`)
- [ ] You created an XRD that defines a `Database` API with size tiers
- [ ] You created a Composition that maps sizes to PostgreSQL StatefulSets
- [ ] You created a Claim and traced the full resource chain (Claim -> XR -> Object -> StatefulSet)
- [ ] You deleted a Claim and understood the deletion cascade
- [ ] You wrote catalog-info.yaml entries for all three TicketPulse services
- [ ] You can explain when to choose Crossplane vs Terraform
- [ ] You can explain the golden path from Backstage template to running infrastructure

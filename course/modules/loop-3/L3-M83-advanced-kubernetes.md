# L3-M83: Advanced Kubernetes

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L2-M42
>
> **Source:** Chapter 7 of the 100x Engineer Guide

## What You'll Learn

- NetworkPolicies: restricting which pods can communicate with which, implementing a zero-trust network model
- RBAC: creating service accounts with minimum permissions for each TicketPulse service
- PodSecurityContext: running containers as non-root with read-only filesystems and dropped capabilities
- PodDisruptionBudgets: ensuring availability during node drains and cluster upgrades
- HPA with custom metrics: scaling based on Kafka consumer lag instead of just CPU
- Resource quotas per namespace: preventing one team's service from consuming the entire cluster

## Why This Matters

TicketPulse is running on Kubernetes. The Deployments are working, Services route traffic, and the pods are up. But the cluster is wide open. Every pod can talk to every other pod. The API gateway can talk directly to the database. The frontend service can reach the payment service. If an attacker compromises any single pod, they can reach everything.

Production Kubernetes requires hardening. The defaults are permissive because they make getting started easy. But running production workloads on those defaults is like leaving every door in a building unlocked because it is convenient for the first tenant.

This module takes TicketPulse's K8s deployment from "works" to "production-grade." You will implement defense in depth: restrict network access, enforce least-privilege permissions, harden container security, and ensure availability during operational events.

---

### 🤔 Prediction Prompt

Before reading about network policies, think: in your current Kubernetes cluster, which pod-to-pod communication paths are actually necessary? If you enforced "default deny," how many explicit allow rules would you need?

## 1. NetworkPolicies: Default Deny, Explicit Allow

### The Problem

By default in Kubernetes, every pod can communicate with every other pod across all namespaces. This means:

```
frontend pod → can reach → database pod (port 5432)       ❌ Should not be allowed
api-gateway  → can reach → payment-service internal API    ❌ Should go through service mesh
order-service → can reach → kube-system namespace          ❌ Should not be allowed
```

### The Architecture

TicketPulse's network policy should enforce:

```
Internet → Ingress → API Gateway → Backend Services → Databases
                                                    → Message Broker
                                                    → Cache
```

No shortcuts. No direct database access from the gateway. No cross-service communication that bypasses the intended architecture.

### Build: Default Deny All

<details>
<summary>💡 Hint 1: Do not forget the DNS egress rule</summary>
A default-deny egress policy will break DNS resolution for every pod in the namespace. Apply the CoreDNS egress allow (port 53 UDP/TCP to kube-system) immediately after the deny-all, or your pods will not resolve any service names.
</details>

Start by denying all ingress and egress traffic. Then explicitly allow what is needed.

```yaml
# network-policies/default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: ticketpulse
spec:
  podSelector: {}    # Applies to ALL pods in the namespace
  policyTypes:
    - Ingress
    - Egress
```

With this in place, nothing can talk to anything. Now open exactly the connections you need.

### Build: Allow API Gateway to Backend Services

```yaml
# network-policies/api-gateway-to-backends.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-to-backends
  namespace: ticketpulse
spec:
  podSelector:
    matchLabels:
      tier: backend           # Applies to all backend service pods
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway  # Only the API gateway can reach backends
      ports:
        - port: 3000
          protocol: TCP
```

### Build: Allow Backend Services to Databases

```yaml
# network-policies/backends-to-database.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backends-to-postgres
  namespace: ticketpulse
spec:
  podSelector:
    matchLabels:
      app: postgres
  ingress:
    - from:
        - podSelector:
            matchLabels:
              tier: backend     # Only backend services can reach Postgres
      ports:
        - port: 5432
          protocol: TCP
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backends-to-redis
  namespace: ticketpulse
spec:
  podSelector:
    matchLabels:
      app: redis
  ingress:
    - from:
        - podSelector:
            matchLabels:
              tier: backend
      ports:
        - port: 6379
          protocol: TCP
```

### Build: Allow DNS Resolution (Critical)

NetworkPolicies can accidentally break DNS resolution. All pods need to reach CoreDNS:

```yaml
# network-policies/allow-dns.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: ticketpulse
spec:
  podSelector: {}    # All pods
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
```

### Verification

```bash
# Test that allowed traffic works
kubectl exec -it deploy/api-gateway -- curl http://order-service:3000/health
# Should succeed

# Test that denied traffic is blocked
kubectl exec -it deploy/api-gateway -- curl http://postgres:5432
# Should timeout (gateway cannot reach database directly)

kubectl exec -it deploy/frontend -- curl http://order-service:3000/health
# Should timeout (frontend cannot reach backend directly)
```

---

## 2. RBAC: Least Privilege Per Service

### The Problem

Every pod runs with a service account. If no service account is specified, it uses the `default` service account, which may have more permissions than the pod needs. If the order-service pod is compromised, the attacker should not be able to list secrets or delete deployments.

### Build: Service Accounts Per Service

```yaml
# rbac/service-accounts.yaml

# Each TicketPulse service gets its own service account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service
  namespace: ticketpulse
automountServiceAccountToken: false   # Don't mount the token unless needed
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
  namespace: ticketpulse
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: payment-service
  namespace: ticketpulse
automountServiceAccountToken: false
```

### Build: Roles with Minimum Permissions

The order service needs to read ConfigMaps (for configuration) but nothing else:

```yaml
# rbac/order-service-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: order-service-role
  namespace: ticketpulse
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
    resourceNames: ["order-service-config"]  # Only its own config
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: order-service-binding
  namespace: ticketpulse
subjects:
  - kind: ServiceAccount
    name: order-service
    namespace: ticketpulse
roleRef:
  kind: Role
  name: order-service-role
  apiGroup: rbac.authorization.k8s.io
```

### Assign Service Accounts to Deployments

```yaml
# deployments/order-service.yaml (relevant section)
spec:
  template:
    spec:
      serviceAccountName: order-service
      automountServiceAccountToken: false
      containers:
        - name: order-service
          image: ticketpulse/order-service:v1.2.3
```

---

## 3. PodSecurityContext: Hardening Containers

### Build: Non-Root, Read-Only, Minimal Capabilities

```yaml
# deployments/order-service.yaml (security section)
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: order-service
          image: ticketpulse/order-service:v1.2.3
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp        # Writable tmp for the app
            - name: cache
              mountPath: /app/.cache # Writable cache if needed
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir:
            sizeLimit: 100Mi
```

What each setting does:

| Setting | Purpose |
|---------|---------|
| `runAsNonRoot: true` | Container must run as non-root. Fails to start otherwise. |
| `readOnlyRootFilesystem: true` | Prevents writing to the container filesystem (blocks malware persistence). |
| `capabilities.drop: ["ALL"]` | Drops all Linux capabilities (no raw sockets, no changing file ownership, etc.). |
| `allowPrivilegeEscalation: false` | Prevents gaining more privileges than the parent process. |
| `seccompProfile: RuntimeDefault` | Restricts system calls to a safe default set. |

The `emptyDir` volumes provide writable space where the application actually needs it (temp files, cache) without making the entire filesystem writable.

---

## 4. PodDisruptionBudgets: Availability During Disruptions

### The Problem

Kubernetes node drains (during upgrades, scaling, or maintenance) evict pods from the node being drained. Without a PDB, Kubernetes might evict all replicas of a service simultaneously, causing downtime.

### Build: PDBs for Critical Services

```yaml
# pdb/order-service-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service-pdb
  namespace: ticketpulse
spec:
  minAvailable: 2              # At least 2 pods must remain available
  selector:
    matchLabels:
      app: order-service
---
# pdb/api-gateway-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: ticketpulse
spec:
  maxUnavailable: 1            # At most 1 pod can be unavailable at a time
  selector:
    matchLabels:
      app: api-gateway
```

`minAvailable: 2` means Kubernetes will refuse to evict a pod if doing so would leave fewer than 2 replicas running. This requires you to have at least 3 replicas so that draining one node is always possible.

### Try It: Drain a Node

<details>
<summary>💡 Hint 1: Check your PDB math before draining</summary>
If your PDB says `minAvailable: 2` and you only have 2 replicas, the drain will block forever -- Kubernetes cannot evict a pod without violating the budget. You need at least N+1 replicas where N is your minAvailable value. Verify with `kubectl get pdb -n ticketpulse`.
</details>

```bash
# See which nodes your pods are on
kubectl get pods -n ticketpulse -o wide

# Drain a node (simulates maintenance)
kubectl drain node-2 --ignore-daemonsets --delete-emptydir-data

# Watch the drain process
# Kubernetes will:
# 1. Evict pods from node-2 one at a time
# 2. Check PDB before each eviction
# 3. Wait for replacement pods to be Ready before evicting more
# 4. Refuse to evict if PDB would be violated

# Uncordon the node when done
kubectl uncordon node-2
```

---

## 5. HPA with Custom Metrics: Scale on What Matters

### Beyond CPU: Scaling on Kafka Consumer Lag

CPU-based autoscaling misses the point for event-driven services. The order processor might have low CPU but a growing Kafka consumer lag, meaning it is falling behind on processing orders.

```yaml
# hpa/order-processor-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-processor-hpa
  namespace: ticketpulse
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-processor
  minReplicas: 2
  maxReplicas: 20
  metrics:
    # Primary: scale based on Kafka consumer lag
    - type: External
      external:
        metric:
          name: kafka_consumer_lag
          selector:
            matchLabels:
              topic: orders
              consumer_group: order-processor
        target:
          type: AverageValue
          averageValue: "1000"    # Target: max 1000 messages lag per pod
    # Secondary: CPU as a safety net
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30    # React quickly to spikes
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60             # Add up to 4 pods per minute
    scaleDown:
      stabilizationWindowSeconds: 300   # Wait 5 minutes before scaling down
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60             # Remove at most 2 pods per minute
```

This requires a metrics adapter (like Prometheus Adapter or KEDA) that exposes Kafka consumer lag as a Kubernetes metric.

---

## 6. Resource Quotas: Preventing Cluster Starvation

### Build: Per-Namespace Quotas

```yaml
# quotas/ticketpulse-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ticketpulse-quota
  namespace: ticketpulse
spec:
  hard:
    requests.cpu: "20"           # Max 20 CPU cores requested total
    requests.memory: "40Gi"      # Max 40 GiB memory requested total
    limits.cpu: "40"             # Max 40 CPU cores limit total
    limits.memory: "80Gi"        # Max 80 GiB memory limit total
    pods: "100"                  # Max 100 pods
    services: "20"               # Max 20 services
    persistentvolumeclaims: "10" # Max 10 PVCs
---
# Also set default requests/limits so pods that forget get sensible defaults
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: ticketpulse
spec:
  limits:
    - default:
        cpu: "500m"
        memory: "512Mi"
      defaultRequest:
        cpu: "100m"
        memory: "128Mi"
      type: Container
```

---

## 7. Design: GKE Autopilot Comparison

### Stop and Think (10 minutes)

If TicketPulse moved from self-managed Kubernetes to GKE Autopilot (Google's fully managed K8s), what would change?

| Dimension | Self-Managed K8s | GKE Autopilot |
|-----------|-----------------|---------------|
| Node management | You provision, patch, and scale nodes | Google manages nodes entirely |
| Pod security | You enforce SecurityContext | Enforced by default (Restricted) |
| Resource quotas | You set them | Billing-based — you pay per pod resource |
| NetworkPolicies | You write them | Still your responsibility |
| RBAC | Full control | Full control |
| Node access | SSH into nodes for debugging | No node access |
| DaemonSets | Full control | Limited (no custom DaemonSets) |
| GPU workloads | Configure GPU node pools | Request GPU in pod spec, Autopilot provisions |

**What gets easier**: No node patching, no capacity planning, security hardened by default, pay-per-pod pricing simplifies cost tracking.

**What gets harder**: No SSH to nodes for debugging, no custom DaemonSets (so log agents must be deployed differently), less control over scheduling and node types.

---

## Checkpoint: What You Built

You have:

- [x] Implemented default-deny NetworkPolicies with explicit allow rules
- [x] Created per-service RBAC with least-privilege roles
- [x] Hardened containers with non-root, read-only rootfs, and dropped capabilities
- [x] Set up PodDisruptionBudgets to maintain availability during drains
- [x] Configured HPA with custom Kafka consumer lag metrics
- [x] Added resource quotas and limit ranges to prevent cluster starvation

**Key insight**: Kubernetes defaults are designed for ease of getting started, not for production security. Production hardening is about changing every default to an explicit, restrictive configuration. Default deny for network. Least privilege for RBAC. Non-root for containers. Minimum availability for disruptions.

---

---

## 8. Walkthrough: Harden One Service End-to-End (20 min)

Reading policies is one thing. Walking through the complete hardening of a single service makes the concepts concrete. Let's fully harden the `payment-service` — the most security-sensitive component in TicketPulse.

### Step 1: Audit the Current State

```bash
# What does the payment-service deployment look like today?
kubectl get deployment payment-service -n ticketpulse -o yaml

# Check current security context (probably none)
kubectl get deployment payment-service -n ticketpulse -o jsonpath='{.spec.template.spec.securityContext}'
# If empty: {}  — that means running as root with full capabilities

# Check what service account it's using
kubectl get deployment payment-service -n ticketpulse -o jsonpath='{.spec.template.spec.serviceAccountName}'
# If "default": that's the shared default account — needs fixing

# Check what it can reach on the network
kubectl exec -it -n ticketpulse deployment/payment-service -- \
  wget -qO- --timeout=3 http://event-service:3000/health
# If this succeeds: payment-service can reach event-service — it should NOT need to
```

Document your findings before making any changes. This is your baseline.

### Step 2: Apply Hardening Layer by Layer

Apply each change, verify it works, then apply the next:

```bash
# Layer 1: Service account
kubectl apply -f rbac/payment-service-account.yaml
kubectl patch deployment payment-service -n ticketpulse \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/serviceAccountName", "value": "payment-service"}]'

# Verify: payment-service is still healthy
kubectl rollout status deployment/payment-service -n ticketpulse
curl http://localhost:3000/api/events/evt_1/purchase  # Should still work

# Layer 2: Security context
kubectl apply -f deployments/payment-service-secured.yaml  # The hardened deployment
kubectl rollout status deployment/payment-service -n ticketpulse

# Verify again: the security constraints did not break the app
kubectl exec -it -n ticketpulse deployment/payment-service -- id
# Should show: uid=1000 gid=1000 — not root

kubectl exec -it -n ticketpulse deployment/payment-service -- \
  sh -c "echo test > /app/test.txt"
# Should fail: Read-only file system

# Layer 3: Network policies
kubectl apply -f network-policies/payment-service-egress.yaml
kubectl rollout restart deployment/payment-service -n ticketpulse

# Verify: payment-service can still reach postgres and Stripe API
kubectl exec -it -n ticketpulse deployment/payment-service -- \
  wget -qO- http://postgres:5432  # Should fail (cannot reach DB on 5432 — goes through service)
  
kubectl exec -it -n ticketpulse deployment/payment-service -- \
  wget -qO- --timeout=5 https://api.stripe.com/v1  # Should succeed (egress to Stripe allowed)
```

### Step 3: Verify Denials Work

The most important test: confirm that your deny rules actually deny.

```bash
# Test 1: payment-service CANNOT reach event-service (should be blocked by NetworkPolicy)
kubectl exec -it -n ticketpulse deployment/payment-service -- \
  wget -qO- --timeout=3 http://event-service:3000/health
# Expected: Connection timed out (denied by NetworkPolicy)
# If this succeeds: your NetworkPolicy is wrong

# Test 2: frontend CANNOT reach payment-service directly (must go through API gateway)
kubectl exec -it -n ticketpulse deployment/frontend -- \
  wget -qO- --timeout=3 http://payment-service:3000/internal/process
# Expected: Connection timed out

# Test 3: payment-service CANNOT create a kubernetes secret (RBAC test)
kubectl exec -it -n ticketpulse deployment/payment-service -- \
  kubectl create secret generic test-secret --from-literal=key=value
# Expected: Error from server (Forbidden): ...
```

If all three denials work: your hardening is effective.

### Step 4: Create a Security Posture Scorecard

Document the hardened state for the payment service and use it as a template for other services:

```markdown
# payment-service Security Posture

## ✅ Hardening Applied
- [x] Dedicated service account (payment-service) — not default
- [x] automountServiceAccountToken: false
- [x] runAsNonRoot: true, runAsUser: 1000
- [x] readOnlyRootFilesystem: true
- [x] capabilities.drop: ["ALL"]
- [x] seccompProfile: RuntimeDefault
- [x] PodDisruptionBudget: minAvailable=2
- [x] NetworkPolicy: ingress only from api-gateway on port 3000
- [x] NetworkPolicy: egress only to postgres:5432, redis:6379, api.stripe.com:443, kube-dns:53

## ❌ Still TODO
- [ ] mTLS via service mesh (Istio or Linkerd) for encrypted service-to-service traffic
- [ ] OPA/Kyverno policy to enforce SecurityContext on all new deployments
- [ ] Secrets managed via external-secrets-operator (not plain K8s Secrets)
- [ ] Runtime threat detection (Falco) to alert on unexpected syscalls

## Blast Radius if payment-service is Compromised
- Can reach: postgres (orders DB), redis, Stripe API
- Cannot reach: event-service, user-service, kafka, kubernetes API
- Cannot write to: filesystem (read-only), other namespaces
- Cannot escalate to: root, cluster-admin, other service accounts
```

---

## 9. Reflection: Production Kubernetes Trade-offs (10 min)

Work through these questions. The goal is to develop judgment, not recall the "correct" answer.

### Question 1: The Rollout Chicken-and-Egg

You want to enforce `runAsNonRoot: true` on all deployments in the `ticketpulse` namespace using a Kyverno policy. But 3 of your 8 services currently run as root (because they were written before you thought about this). If you enforce the policy, those 3 services cannot deploy.

**Walk through the migration path.** Do not leave any service unable to deploy, even temporarily.

> **Guided approach**: 
> 1. Apply the policy in `audit` mode first — violations are logged but not blocked.
> 2. Fix the 3 non-compliant services (update Dockerfile USER instruction, test locally).
> 3. Apply the policy in `enforce` mode once all services are compliant.
> 4. Never apply an enforcing policy that would break existing deployments — that is a weekend-ruining mistake.

### Question 2: PDB Math

You have the `api-gateway` with `maxUnavailable: 1` and 3 replicas. You are draining a node that has 2 of those 3 replicas.

Will the drain succeed? How will Kubernetes handle it?

> **Guided answer**: The drain will succeed, but slowly. Kubernetes will evict the first replica (1 unavailable — allowed by PDB). It will then wait until that replica is scheduled and Ready on another node before evicting the second one. This can take 1-3 minutes per replica. With PDB properly configured, you never have zero api-gateway pods, but the drain is serialized. If your pods take 30 seconds to start, this drain takes 30-60 seconds total — acceptable.

### Question 3: Custom Metrics HPA — The Chicken-and-Egg

Your HPA scales the order-processor based on Kafka consumer lag. But if the Kafka exporter or Prometheus Adapter is down, the HPA cannot get the `kafka_consumer_lag` metric. What happens?

> **Guided answer**: By default, Kubernetes HPAs become "flapping" when the metric source is unavailable — they may scale down to minimum replicas or hold at current. Configure `behavior.scaleDown.stabilizationWindowSeconds: 3600` (1 hour hold before scale-down) to prevent dangerous scale-downs during monitoring outages. Also, keep CPU as a secondary metric — if Kafka lag is unavailable but CPU is spiking, the HPA can still scale up. Defense in depth.

---

> **Want the deep theory?** See Ch 7 of the 100x Engineer Guide: "Production Kubernetes Architecture" — covers advanced scheduling, admission controllers, service meshes, and the full Kubernetes security model.

---

**Next module**: L3-M84 — Nix & Reproducible Builds, where we eliminate "works on my machine" by defining TicketPulse's exact development environment in a single file.

### 🤔 Reflection Prompt

After hardening the cluster, which security control gave you the most "I can not believe this was not already in place" reaction? What is the single cheapest security improvement any Kubernetes deployment should have from day one?

## Key Terms

| Term | Definition |
|------|-----------|
| **NetworkPolicy** | A Kubernetes resource that controls which pods can communicate with each other and with external endpoints. |
| **RBAC** | Role-Based Access Control; a Kubernetes authorization model that grants permissions based on assigned roles. |
| **PDB** | PodDisruptionBudget; a Kubernetes resource that limits the number of pods that can be down simultaneously during disruptions. |
| **SecurityContext** | A Kubernetes setting that defines privilege and access-control options for a pod or container. |
| **HPA** | Horizontal Pod Autoscaler; a Kubernetes controller that automatically scales the number of pod replicas based on observed metrics. |
| **Resource quota** | A Kubernetes mechanism that limits the total amount of CPU, memory, or other resources a namespace can consume. |
---

## What's Next

In **Observability & GitOps as Code** (L3-M83a), you'll build on what you learned here and take it further.

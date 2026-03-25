<!--
  CHAPTER: 7
  TITLE: DevOps, Infrastructure & Deployment
  PART: II — Applied Engineering
  PREREQS: Chapter 3
  KEY_TOPICS: IaC, Terraform, containers, Kubernetes, CI/CD, 12-factor app, HTTP/2/3, DNS, CDN, service mesh, platform engineering
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 7: DevOps, Infrastructure & Deployment

> **Part II — Applied Engineering** | Prerequisites: Chapter 3 | Difficulty: Intermediate

The infrastructure layer — how code gets from a developer's machine to production, and the platforms that make it repeatable, scalable, and observable.

### In This Chapter
- Infrastructure as Code (IaC)
- Containers & Orchestration
- CI/CD Philosophies
- Cloud-Native: The 12-Factor App
- Networking for Backend Engineers
- Platform Engineering
- Kubernetes Deep Dive

### Related Chapters
- Chapter 3 (architecture deployed)
- Chapter 12 (Docker/Terraform/kubectl hands-on)
- Chapter 15 (CI/CD pipelines)
- Chapter 19 (AWS infrastructure)

---

## 1. INFRASTRUCTURE AS CODE (IaC)

### Declarative vs Imperative
- **Declarative (Terraform/HCL):** Describe desired end state. Engine computes the diff.
- **Imperative (Pulumi/CDK):** Describe steps in a real programming language. Full control.

### Tool Philosophies
- **Terraform:** HCL DSL, massive provider ecosystem, mature state management. BSL license concern.
- **Pulumi:** TypeScript/Python/Go. Full language power. Risk of "too clever" infrastructure code.
- **AWS CDK:** General-purpose languages → CloudFormation. Deep AWS integration, AWS-only.

### State Management
Remote state (S3 + DynamoDB lock) is essential for teams. State files contain secrets — encrypt at rest. Always enable versioning.

### Drift Detection
Periodic `terraform plan`, continuous reconciliation (GitOps), cloud-native tools (AWS Config).

### Immutable Infrastructure
Never modify deployed infra. Build new image → deploy → route → terminate old. Eliminates configuration drift.

### GitOps
Git = single source of truth. **Push-based:** CI pushes to cluster. **Pull-based:** Agent in cluster pulls from Git (Argo CD, Flux). Pull is more secure.

---

## 2. CONTAINERS & ORCHESTRATION

### Docker Best Practices
- Multi-stage builds (separate build from runtime)
- Pin base image digests, not just tags
- Order layers by change frequency (lockfile before source)
- One process per container, non-root user
- Scan images for CVEs (trivy, grype)

### Kubernetes Architecture

**Control Plane:** kube-apiserver → etcd → kube-scheduler → kube-controller-manager
**Node:** kubelet → kube-proxy → container runtime (containerd)

**Core Resources:**
| Resource | Purpose |
|---|---|
| **Pod** | Smallest deployable unit (1+ containers) |
| **Deployment** | Declarative updates, rolling deployments |
| **Service** | Stable network endpoint (ClusterIP, NodePort, LoadBalancer) |
| **StatefulSet** | Stable identity, ordered deployment (databases) |
| **DaemonSet** | One pod per node (log collectors, agents) |
| **Job / CronJob** | Batch and scheduled workloads |

### Service Mesh (Istio / Linkerd)
Sidecar proxy per pod. Handles mTLS, observability, traffic management, authorization policies.
**Justified when:** Many services, need consistent security/observability. **Premature when:** <10 services.

### Operators
Kubernetes controllers encoding domain-specific operational knowledge via CRDs. Automate complex lifecycle management (Postgres operator, Kafka operator).

---

## 3. CI/CD PHILOSOPHIES

> For hands-on GitHub Actions mastery — reusable workflows, OIDC, self-hosted runners, and more — see **Chapter 33: GitHub Actions Mastery**.

### Core Practices
- **CI:** Merge to mainline frequently (at least daily). Automated build + test on every commit.
- **Continuous Delivery:** Every change *can* be deployed. Human decides when.
- **Continuous Deployment:** Every passing change *is* deployed automatically.

### Trunk-Based Development
Single shared branch. Short-lived feature branches (1-2 days max). Feature flags decouple deployment from release.

### Deployment Strategies

| Strategy | Downtime | Infra Cost | Rollback | Risk |
|---|---|---|---|---|
| **Blue-Green** | Zero | 2x | Instant | Low |
| **Canary** | Zero | +small % | Fast | Lowest |
| **Rolling** | Zero | +1 instance | Slow | Medium |
| **Recreate** | Yes | 1x | Redeploy | Highest |

---

## 4. CLOUD-NATIVE: THE 12-FACTOR APP

| Factor | Principle |
|---|---|
| I. Codebase | One repo, many deploys |
| II. Dependencies | Explicitly declare and isolate |
| III. Config | Store in environment variables |
| IV. Backing Services | Treat as attached resources (swap via config) |
| V. Build, Release, Run | Strictly separate stages |
| VI. Processes | Stateless, share-nothing |
| VII. Port Binding | Self-contained, export via port |
| VIII. Concurrency | Scale out via process model |
| IX. Disposability | Fast startup, graceful shutdown |
| X. Dev/Prod Parity | Minimize gaps between environments |
| XI. Logs | Treat as event streams (stdout) |
| XII. Admin Processes | Run as one-off processes in same environment |

---

## 5. NETWORKING FOR BACKEND ENGINEERS

### HTTP/2 vs HTTP/3

| Feature | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
|---|---|---|---|
| Multiplexing | No | Yes (single TCP) | Yes (per-stream) |
| Head-of-line blocking | HTTP + TCP | TCP only | None |
| Header compression | None | HPACK | QPACK |
| Connection setup | 2-3 RTT | 1-2 RTT | 0-1 RTT |
| Transport | TCP | TCP | UDP (QUIC) |

### DNS
Resolution: Client cache → Recursive resolver → Root → TLD → Authoritative
Key records: A/AAAA (IP), CNAME (alias), SRV (service locator), TXT (verification)

### CDN Architecture
Edge locations cache content near users. Beyond caching: edge compute, DDoS protection, TLS termination, image optimization.

### Service Discovery
- **Client-side:** Client queries registry, selects instance (Eureka + Ribbon)
- **Server-side:** Client → load balancer → registry → backend (Kubernetes Services)
- **DNS-based:** Universal, but caching can serve stale records

### Load Balancing: L4 vs L7
- **L4:** Routes by IP/port. Fast. No application awareness.
- **L7:** Routes by HTTP path/headers/cookies. Flexible. More overhead.

---

## 6. PLATFORM ENGINEERING

### Internal Developer Platforms
Self-service infrastructure: service catalog, CI/CD templates, observability, secret management, ephemeral environments.

### Golden Paths
Recommended, well-supported way to accomplish tasks. Not mandated, but paved and well-lit. 80% of services should fit.

### Developer Experience (DevEx)
Three dimensions: **Feedback loops** (how fast you know if it works), **Cognitive load** (how much to hold in your head), **Flow state** (uninterrupted focus).

### Platform as a Product
Platform team = product team. Customers = developers. Measure: adoption rates, time-to-first-deploy, developer satisfaction.

---

## 7. KUBERNETES DEEP DIVE

Beyond kubectl — the knowledge needed to operate Kubernetes in production.

### Networking
- **Pod networking**: every pod gets its own IP, pods communicate directly (no NAT)
- **CNI (Container Network Interface)**: the plugin that implements pod networking (Calico, Cilium, Flannel, Weave)
- **Service networking**: ClusterIP (virtual IP + kube-proxy iptables/IPVS rules), NodePort (expose on every node), LoadBalancer (cloud LB provisioned automatically)
- **DNS**: CoreDNS resolves `service-name.namespace.svc.cluster.local`
- **Ingress**: HTTP routing rules → Ingress Controller (nginx, Traefik, Envoy/Contour, ALB Ingress)
- **NetworkPolicy**: firewall rules between pods (default: all pods can talk to all pods — you must restrict)
  ```yaml
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata:
    name: allow-api-to-db
  spec:
    podSelector:
      matchLabels:
        app: database
    ingress:
      - from:
          - podSelector:
              matchLabels:
                app: api
        ports:
          - port: 5432
  ```
- **Service mesh** (recap): Istio/Linkerd adds mTLS, traffic management, observability at L7

### RBAC (Role-Based Access Control)
- **ServiceAccount**: identity for pods (every pod gets one, default if not specified)
- **Role / ClusterRole**: defines permissions (which API verbs on which resources)
- **RoleBinding / ClusterRoleBinding**: assigns roles to users/groups/service accounts
  ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: Role
  metadata:
    namespace: production
    name: pod-reader
  rules:
    - apiGroups: [""]
      resources: ["pods", "pods/log"]
      verbs: ["get", "list", "watch"]
  ---
  apiVersion: rbac.authorization.k8s.io/v1
  kind: RoleBinding
  metadata:
    namespace: production
    name: read-pods
  subjects:
    - kind: ServiceAccount
      name: monitoring-agent
      namespace: production
  roleRef:
    kind: Role
    name: pod-reader
    apiGroup: rbac.authorization.k8s.io
  ```
- **Principle of least privilege**: don't use cluster-admin for apps, create specific roles
- **Common mistake**: granting `*` verbs on `*` resources — effectively admin access

### Helm Charts
- What Helm is: a package manager for Kubernetes (charts = parameterized manifests)
- Chart structure:
  ```
  my-app/
  ├── Chart.yaml          # Metadata (name, version, dependencies)
  ├── values.yaml         # Default configuration values
  ├── templates/
  │   ├── deployment.yaml # Go templates referencing {{ .Values.* }}
  │   ├── service.yaml
  │   ├── ingress.yaml
  │   ├── configmap.yaml
  │   ├── _helpers.tpl    # Reusable template functions
  │   └── NOTES.txt       # Post-install message
  └── charts/             # Subcharts (dependencies)
  ```
- Key commands: `helm install`, `helm upgrade`, `helm rollback`, `helm template` (render locally), `helm diff` (preview changes)
- `values.yaml` overrides: `-f production-values.yaml` or `--set image.tag=v1.2.3`
- Helm vs Kustomize:
  | Aspect | Helm | Kustomize |
  |--------|------|-----------|
  | Approach | Templating (Go templates) | Patching (overlays on base manifests) |
  | Complexity | Higher (template logic) | Lower (plain YAML) |
  | Ecosystem | Massive chart library | Built into kubectl |
  | Best for | Distributing apps, complex configs | Internal apps, simple overrides |
- **Recommendation**: Helm for third-party apps (nginx, cert-manager, Prometheus), Kustomize for your own apps

### Custom Resource Definitions (CRDs) & Operators
- **CRD**: extends the Kubernetes API with your own resource types
  ```yaml
  apiVersion: apiextensions.k8s.io/v1
  kind: CustomResourceDefinition
  metadata:
    name: databases.example.com
  spec:
    group: example.com
    versions:
      - name: v1
        served: true
        storage: true
        schema:
          openAPIV3Schema:
            type: object
            properties:
              spec:
                type: object
                properties:
                  engine: { type: string, enum: [postgres, mysql] }
                  version: { type: string }
                  storage: { type: string }
    scope: Namespaced
    names:
      plural: databases
      singular: database
      kind: Database
  ```
- **Operator**: a controller that watches CRDs and automates operations
- Operator Framework / Kubebuilder / controller-runtime for building operators
- Popular operators: cert-manager, Prometheus Operator, Postgres Operator (Zalando), Strimzi (Kafka)
- **Operator Maturity Model**: install → upgrade → lifecycle → deep insights → autopilot

### Resource Management
- **Requests**: minimum guaranteed resources (scheduler uses this for placement)
- **Limits**: maximum allowed resources (exceeded = OOMKilled for memory, throttled for CPU)
  ```yaml
  resources:
    requests:
      cpu: "250m"      # 0.25 CPU cores
      memory: "512Mi"  # 512 MiB
    limits:
      cpu: "1000m"     # 1 CPU core
      memory: "1Gi"    # 1 GiB
  ```
- **Best practices**: always set requests, set memory limits, consider NOT setting CPU limits (throttling is worse than sharing)
- **HPA (Horizontal Pod Autoscaler)**: scale pods based on CPU/memory/custom metrics
- **VPA (Vertical Pod Autoscaler)**: recommend or auto-adjust requests/limits
- **PDB (Pod Disruption Budget)**: minimum available pods during voluntary disruptions (upgrades, node drain)
- **LimitRange**: default requests/limits per namespace (safety net)
- **ResourceQuota**: cap total resources per namespace (prevent one team from consuming the cluster)

### Pod Security
- **SecurityContext**: run as non-root, read-only root filesystem, drop capabilities
  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    readOnlyRootFilesystem: true
    capabilities:
      drop: ["ALL"]
    allowPrivilegeEscalation: false
  ```
- **Pod Security Standards** (replaced PodSecurityPolicies): Privileged, Baseline, Restricted
- **Secrets management**: external-secrets-operator (sync from Vault/AWS SM/GCP SM), sealed-secrets (encrypted in git)

### Debugging in Kubernetes
```bash
# Pod not starting? Check events:
kubectl describe pod my-pod-xyz        # Events at the bottom tell you why

# Common reasons:
# - ImagePullBackOff → wrong image name/tag, missing imagePullSecret
# - CrashLoopBackOff → app crashes on startup, check logs
# - Pending → insufficient resources, node affinity/taint preventing scheduling
# - OOMKilled → memory limit too low

# Container logs:
kubectl logs my-pod-xyz                # Current logs
kubectl logs my-pod-xyz --previous     # Logs from crashed container
kubectl logs -l app=my-app --all-containers  # All pods matching label

# Interactive debugging:
kubectl exec -it my-pod-xyz -- /bin/sh  # Shell into container
kubectl debug my-pod-xyz --image=busybox --target=app  # Ephemeral debug container

# Network debugging:
kubectl run debug --image=nicolaka/netshoot -it --rm -- bash
# Inside: curl, dig, nslookup, tcpdump, ping all available

# Resource usage:
kubectl top pods                        # CPU/memory per pod
kubectl top nodes                       # CPU/memory per node
```

### Production Checklist
- [ ] Resource requests and limits set on all pods
- [ ] Liveness and readiness probes configured
- [ ] Pod Disruption Budgets for critical services
- [ ] NetworkPolicies restricting pod-to-pod traffic
- [ ] RBAC with least privilege (no cluster-admin for apps)
- [ ] Secrets in external secret manager (not plaintext in manifests)
- [ ] HPA configured for variable-traffic services
- [ ] Node anti-affinity for replicas (spread across nodes/AZs)
- [ ] Monitoring: Prometheus + Grafana dashboards per service
- [ ] Logging: centralized (Loki/ELK) with structured logs
- [ ] SecurityContext: non-root, read-only rootfs, dropped capabilities
- [ ] Image scanning in CI (trivy/grype)
- [ ] Rollback strategy tested (helm rollback / kubectl rollout undo)

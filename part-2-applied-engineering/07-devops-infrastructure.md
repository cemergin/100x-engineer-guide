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

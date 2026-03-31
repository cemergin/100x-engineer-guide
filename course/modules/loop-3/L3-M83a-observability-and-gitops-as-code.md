# L3-M83a: Observability & GitOps as Code

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M45, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why dashboards, alerts, and SLO definitions must live in Git — not just in the Grafana UI
- Provisioning Grafana dashboards from JSON files alongside your application code
- Defining Prometheus alerting rules as Kubernetes PrometheusRule CRDs
- Generating multi-window, multi-burn-rate SLO alerts with Sloth
- Setting up ArgoCD for GitOps deployment of TicketPulse
- The full loop: code change → Git push → ArgoCD sync → monitoring auto-updates

## Why This Matters

In L2-M45 you built Grafana dashboards and Prometheus alerts for TicketPulse by clicking through UIs. Those dashboards work — until someone accidentally deletes one, or staging's alert thresholds drift from production's, or the engineer who built the "Ticket Purchase Latency" dashboard leaves the company and nobody knows how to recreate it.

Observability-as-code means your dashboards, alerts, and SLOs are files in Git. They are reviewed in PRs, versioned, and reproducible. If you lose your entire monitoring stack, `kubectl apply -f monitoring/` rebuilds it in minutes.

GitOps extends this: instead of running `kubectl apply` manually, ArgoCD watches your Git repo and syncs automatically. The cluster's actual state always matches what is declared in Git.

## Prereq Check

```bash
# Verify Prometheus + Grafana from L2-M45 are running
kubectl get pods -n monitoring

# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=180s

# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Install Sloth (SLO generator)
brew install slok/sloth/sloth
```

---

## 1. Grafana Dashboards as Code

### Exercise 1: 🛠️ Build — Export and Version Dashboards

Export your L2-M45 Grafana dashboards to JSON and set up file-based provisioning:

```bash
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/provisioning
```

1. Export each dashboard from Grafana UI (Dashboard → Share → Export → Save to file)
2. Save them as `monitoring/grafana/dashboards/api-overview.json`, `monitoring/grafana/dashboards/database-performance.json`, etc.
3. Create the provisioning config:

```yaml
# monitoring/grafana/provisioning/dashboards.yaml
apiVersion: 1
providers:
  - name: TicketPulse
    folder: TicketPulse
    type: file
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

4. Update your Grafana Kubernetes deployment to mount these files
5. Restart Grafana and verify the dashboards load from files
6. Delete a dashboard in the UI, restart Grafana — it should reappear (provisioned dashboards are restored automatically)

---

## 2. Prometheus Alerting Rules as Code

### Exercise 2: 🛠️ Build — PrometheusRule CRDs

Convert your L2-M47 alerting rules into a Kubernetes PrometheusRule resource:

```yaml
# monitoring/prometheus/rules/ticketpulse-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ticketpulse-alerts
  namespace: monitoring
  labels:
    role: alert-rules
spec:
  groups:
    - name: ticketpulse.availability
      interval: 30s
      rules:
        # Recording rule: pre-compute error rate
        - record: ticketpulse:http_error_rate:5m
          expr: |
            sum(rate(http_requests_total{service="ticket-service",status=~"5.."}[5m]))
            / sum(rate(http_requests_total{service="ticket-service"}[5m]))

        # Alert: high error rate
        - alert: TicketPulseHighErrorRate
          expr: ticketpulse:http_error_rate:5m > 0.01
          for: 5m
          labels:
            severity: critical
            team: platform
          annotations:
            summary: "Error rate {{ $value | humanizePercentage }} exceeds 1%"
```

Apply and verify:

```bash
kubectl apply -f monitoring/prometheus/rules/ticketpulse-alerts.yaml

# Verify Prometheus loaded the rules
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Visit http://localhost:9090/rules — your rules should appear

# Lint rules
promtool check rules monitoring/prometheus/rules/ticketpulse-alerts.yaml
```

---

## 3. SLO as Code with Sloth

### Exercise 3: 🛠️ Build — Define TicketPulse SLOs

Write an SLO definition for TicketPulse's API availability:

```yaml
# monitoring/slos/ticketpulse-api.yaml
version: "prometheus/v1"
service: "ticketpulse-api"
labels:
  team: platform
slos:
  - name: "requests-availability"
    objective: 99.9
    description: "99.9% of API requests return non-5xx responses"
    sli:
      events:
        error_query: sum(rate(http_requests_total{service="ticket-service",status=~"5.."}[{{.window}}]))
        total_query: sum(rate(http_requests_total{service="ticket-service"}[{{.window}}]))
    alerting:
      name: TicketPulseAvailability
      labels:
        team: platform
      page_alert:
        labels:
          severity: critical
      ticket_alert:
        labels:
          severity: warning
```

Generate Prometheus rules:

```bash
sloth generate -i monitoring/slos/ticketpulse-api.yaml \
               -o monitoring/prometheus/rules/ticketpulse-slo-generated.yaml
```

Inspect the generated file — Sloth produces multi-window, multi-burn-rate alerts (1h, 6h, 3d windows at 14.4x, 6x, 3x, 1x burn rates). Apply it and check Prometheus loaded the rules.

Add a second SLO for latency:
- 99th percentile latency under 500ms for 99% of the time
- Use `histogram_quantile(0.99, ...)` in the SLI query

---

## 4. GitOps with ArgoCD

### Exercise 4: 🚀 Deploy — ArgoCD for TicketPulse

Create a Git repository structure for GitOps:

```
ticketpulse-infra/
├── base/
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── ticket-service-deployment.yaml
│   ├── ticket-service-service.yaml
│   └── events-service-deployment.yaml
├── overlays/
│   ├── staging/
│   │   └── kustomization.yaml    # replicas: 1, staging env vars
│   └── production/
│       └── kustomization.yaml    # replicas: 3, production env vars
└── monitoring/
    ├── grafana/
    ├── prometheus/
    └── slos/
```

Register it as an ArgoCD Application:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ticketpulse
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USER/ticketpulse-infra.git
    targetRevision: main
    path: overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: ticketpulse
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Apply and verify:

```bash
kubectl apply -f argocd-app.yaml
# Open ArgoCD UI and watch the sync
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

### Exercise 5: 🐛 Debug — Drift Detection

1. Manually scale a deployment: `kubectl scale deployment ticket-service --replicas=5 -n ticketpulse`
2. Watch ArgoCD detect the drift (UI shows "OutOfSync")
3. With `selfHeal: true`, ArgoCD should revert it back to the Git-declared replica count within seconds
4. Check the ArgoCD event log to see the reconciliation

---

## 5. The Full Loop

### Exercise 6: 🤔 Reflect — End-to-End GitOps

Make a code change and trace it through the entire pipeline:

1. Update a Grafana dashboard JSON file (add a new panel)
2. Update a PrometheusRule (lower the error threshold)
3. Update a deployment manifest (change the image tag)
4. Commit and push all three changes in one commit
5. Watch ArgoCD sync all three changes simultaneously

Answer: What is the maximum time between your `git push` and the changes being live in the cluster? What determines this latency? How would you handle a change that needs to be deployed to staging first and production second?

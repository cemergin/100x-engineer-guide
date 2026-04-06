# L3-M83a: Observability & GitOps as Code

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M45, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why dashboards, alerts, and SLO definitions must live in Git -- not just in the Grafana UI
- Exporting Grafana dashboards to JSON and provisioning them from files
- Defining Prometheus recording AND alerting rules as Kubernetes PrometheusRule CRDs
- Testing Prometheus rules locally with promtool before deploying
- Generating multi-window, multi-burn-rate SLO alerts with Sloth
- Installing and configuring ArgoCD for GitOps deployment of TicketPulse
- Structuring a GitOps repository with Kustomize base and overlays
- How ArgoCD detects and reverts drift automatically
- The full loop: code change in Git -> ArgoCD sync -> monitoring auto-updates

## Why This Matters

In L2-M45 you built Grafana dashboards and Prometheus alerts for TicketPulse by clicking through UIs. Those dashboards work -- until someone accidentally deletes one, or staging's alert thresholds drift from production's, or the engineer who built the "Ticket Purchase Latency" dashboard leaves the company and nobody knows how to recreate it. In L2-M44 you defined infrastructure in Terraform so it could be reviewed and versioned. But your monitoring configuration -- the dashboards, alerts, and SLOs -- still lives in a running Grafana instance and a Prometheus config that someone edited by hand.

Observability-as-code means your dashboards, alerts, and SLOs are files in Git. They are reviewed in PRs, versioned, and reproducible. If you lose your entire monitoring stack, `kubectl apply -f monitoring/` rebuilds it in minutes.

GitOps extends this further: instead of running `kubectl apply` manually, ArgoCD watches your Git repo and syncs automatically. The cluster's actual state always matches what is declared in Git. Manual `kubectl` changes get reverted. The only way to change production is through a reviewed, merged pull request.

> **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases -- Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

### 🤔 Prediction Prompt

Before reading further, think: if your Grafana instance disappeared right now, how long would it take to recreate your dashboards and alerts? If the answer is "hours" or "I don't know," that is exactly the problem observability-as-code solves.

## Prereq Check

You need the Prometheus operator and Grafana from L2-M45 running, plus ArgoCD and Sloth installed.

```bash
# Verify Prometheus + Grafana from L2-M45 are running
kubectl get pods -n monitoring
# You should see prometheus-*, grafana-*, and alertmanager-* pods

# Verify the Prometheus operator is running (needed for PrometheusRule CRDs)
kubectl get crd prometheusrules.monitoring.coreos.com
# Should return the CRD definition

# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.3/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server \
  -n argocd --timeout=180s

# Get ArgoCD admin password
ARGOCD_PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo "ArgoCD admin password: $ARGOCD_PASS"

# Install ArgoCD CLI
# macOS
brew install argocd
# Linux
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/v2.13.3/argocd-linux-amd64
chmod +x argocd && sudo mv argocd /usr/local/bin/

# Install Sloth (SLO generator)
# macOS
brew install slok/sloth/sloth
# Linux
curl -sSL -o sloth https://github.com/slok/sloth/releases/download/v0.11.0/sloth-linux-amd64
chmod +x sloth && sudo mv sloth /usr/local/bin/

# Install promtool (comes with Prometheus)
# macOS
brew install prometheus
# Linux -- promtool is bundled with prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.53.0/prometheus-2.53.0.linux-amd64.tar.gz
tar xzf prometheus-*.tar.gz
sudo cp prometheus-*/promtool /usr/local/bin/

# Verify tools
argocd version --client
sloth version
promtool --version
```

---

## 1. Grafana Dashboards as Code

Every Grafana dashboard is a JSON document. When you build a dashboard through the UI, that JSON lives in Grafana's internal database. If the pod restarts without persistent storage, or someone deletes the dashboard, it is gone. File-based provisioning solves this: Grafana reads dashboard JSON files from disk at startup and restores them automatically.

### 1a. Set Up the Directory Structure

```bash
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/provisioning/dashboards
```

### 1b. Create the Provisioning Config

This YAML file tells Grafana where to find dashboard JSON files:

```yaml
# monitoring/grafana/provisioning/dashboards/ticketpulse.yaml
apiVersion: 1
providers:
  - name: TicketPulse
    orgId: 1
    folder: TicketPulse
    type: file
    disableDeletion: true
    editable: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards/ticketpulse
      foldersFromFilesStructure: false
```

Key fields: `disableDeletion: true` prevents the UI from deleting provisioned dashboards. `editable: false` prevents UI edits that would be lost on restart (changes must go through Git). `updateIntervalSeconds: 30` means Grafana re-reads the files every 30 seconds.

### 1c. Export and Version a Dashboard

Export your L2-M45 API Overview dashboard from the Grafana UI: Dashboard -> Share -> Export -> Save to file. Save it as `monitoring/grafana/dashboards/ticketpulse-api-overview.json`.

Here is a minimal but complete dashboard JSON for the TicketPulse API overview, showing the structure you need:

```json
{
  "__inputs": [],
  "__requires": [
    { "type": "datasource", "id": "prometheus", "name": "Prometheus" }
  ],
  "id": null,
  "uid": "ticketpulse-api-overview",
  "title": "TicketPulse API Overview",
  "tags": ["ticketpulse", "api"],
  "timezone": "browser",
  "editable": false,
  "time": { "from": "now-1h", "to": "now" },
  "refresh": "30s",
  "templating": {
    "list": [
      {
        "name": "service",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(http_requests_total, service)",
        "refresh": 2,
        "current": { "text": "ticket-service", "value": "ticket-service" }
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "title": "Request Rate",
      "type": "timeseries",
      "gridPos": { "x": 0, "y": 0, "w": 12, "h": 8 },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{service=\"$service\"}[5m])) by (method, status)",
          "legendFormat": "{{method}} {{status}}",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "custom": { "drawStyle": "line", "fillOpacity": 10 }
        }
      }
    },
    {
      "id": 2,
      "title": "Error Rate (%)",
      "type": "stat",
      "gridPos": { "x": 12, "y": 0, "w": 6, "h": 4 },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{service=\"$service\",status=~\"5..\"}[5m])) / sum(rate(http_requests_total{service=\"$service\"}[5m])) * 100",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "thresholds": {
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 0.5 },
              { "color": "red", "value": 1.0 }
            ]
          }
        }
      }
    },
    {
      "id": 3,
      "title": "P99 Latency",
      "type": "timeseries",
      "gridPos": { "x": 12, "y": 4, "w": 6, "h": 4 },
      "targets": [
        {
          "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service=\"$service\"}[5m])) by (le))",
          "legendFormat": "p99",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": { "unit": "s" }
      }
    },
    {
      "id": 4,
      "title": "Active Connections",
      "type": "gauge",
      "gridPos": { "x": 18, "y": 0, "w": 6, "h": 8 },
      "targets": [
        {
          "expr": "sum(http_active_connections{service=\"$service\"})",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 500 },
              { "color": "red", "value": 1000 }
            ]
          }
        }
      }
    }
  ],
  "schemaVersion": 39,
  "version": 1
}
```

Notice the structure: `uid` is a stable identifier (not an auto-generated number), `templating` allows variable selection, and each panel has a PromQL query, grid position, and field configuration. When you export from the Grafana UI, the JSON will be more verbose but follow this same structure.

### 1d. Mount Dashboards in Kubernetes

Update your Grafana deployment to mount the provisioning config and dashboard files. The simplest approach uses ConfigMaps:

```yaml
# monitoring/grafana/grafana-dashboards-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards-provisioning
  namespace: monitoring
data:
  ticketpulse.yaml: |
    apiVersion: 1
    providers:
      - name: TicketPulse
        orgId: 1
        folder: TicketPulse
        type: file
        disableDeletion: true
        editable: false
        updateIntervalSeconds: 30
        options:
          path: /var/lib/grafana/dashboards/ticketpulse
          foldersFromFilesStructure: false
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboard-api-overview
  namespace: monitoring
data:
  ticketpulse-api-overview.json: |
    { ... }  # Paste the full dashboard JSON here
```

```yaml
# Add these volume mounts to your Grafana Deployment spec
# monitoring/grafana/grafana-deployment-patch.yaml
spec:
  template:
    spec:
      containers:
        - name: grafana
          volumeMounts:
            - name: dashboards-provisioning
              mountPath: /etc/grafana/provisioning/dashboards
            - name: dashboard-api-overview
              mountPath: /var/lib/grafana/dashboards/ticketpulse
      volumes:
        - name: dashboards-provisioning
          configMap:
            name: grafana-dashboards-provisioning
        - name: dashboard-api-overview
          configMap:
            name: grafana-dashboard-api-overview
```

Apply and verify:

```bash
kubectl apply -f monitoring/grafana/grafana-dashboards-configmap.yaml
kubectl rollout restart deployment grafana -n monitoring
kubectl rollout status deployment grafana -n monitoring

# Port-forward and check
kubectl port-forward -n monitoring svc/grafana 3000:3000
# Visit http://localhost:3000 -> Browse -> TicketPulse folder
# You should see the API Overview dashboard
```

### 1e. Test Provisioning Recovery

Delete the dashboard through the Grafana UI (if `disableDeletion` is false) or restart the pod:

```bash
kubectl delete pod -l app=grafana -n monitoring
kubectl wait --for=condition=ready pod -l app=grafana -n monitoring --timeout=60s

# Port-forward again and verify: the dashboard is back.
# Provisioned dashboards are restored automatically on startup.
```

This is the core value: your monitoring configuration survives pod restarts, cluster migrations, and accidental deletions because the source of truth is a file in Git, not a database row in Grafana.

---

## 2. Prometheus Rules as Code

The Prometheus Operator (installed in L2-M45) watches for PrometheusRule custom resources. When you create or update a PrometheusRule, the operator automatically reloads Prometheus with the new rules. No manual config editing, no Prometheus restarts.

### 2a. PrometheusRule CRD with Recording and Alerting Rules

Recording rules pre-compute expensive queries and store the result as a new time series. Alerting rules fire when conditions are met. Both belong in the same PrometheusRule resource:

```yaml
# monitoring/prometheus/rules/ticketpulse-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ticketpulse-rules
  namespace: monitoring
  labels:
    role: alert-rules
    app: ticketpulse
    prometheus: kube-prometheus
spec:
  groups:
    # ── Recording Rules ──────────────────────────────────────────
    - name: ticketpulse.recordings
      interval: 30s
      rules:
        # Pre-compute 5-minute error rate (used by multiple alerts)
        - record: ticketpulse:http_error_rate:5m
          expr: |
            sum(rate(http_requests_total{service="ticket-service", status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total{service="ticket-service"}[5m]))
          labels:
            team: platform

        # Pre-compute request rate per endpoint
        - record: ticketpulse:http_request_rate:5m
          expr: |
            sum(rate(http_requests_total{service="ticket-service"}[5m])) by (method, path)
          labels:
            team: platform

        # Pre-compute p99 latency
        - record: ticketpulse:http_latency_p99:5m
          expr: |
            histogram_quantile(0.99,
              sum(rate(http_request_duration_seconds_bucket{service="ticket-service"}[5m])) by (le)
            )
          labels:
            team: platform

        # Pre-compute ticket purchase success rate
        - record: ticketpulse:purchase_success_rate:5m
          expr: |
            sum(rate(ticket_purchases_total{status="success"}[5m]))
            /
            sum(rate(ticket_purchases_total[5m]))
          labels:
            team: platform

    # ── Alerting Rules ───────────────────────────────────────────
    - name: ticketpulse.alerts
      rules:
        # High error rate: >1% for 5 minutes
        - alert: TicketPulseHighErrorRate
          expr: ticketpulse:http_error_rate:5m > 0.01
          for: 5m
          labels:
            severity: critical
            team: platform
          annotations:
            summary: "TicketPulse error rate is {{ $value | humanizePercentage }}"
            description: "Error rate has exceeded 1% for more than 5 minutes."
            runbook_url: "https://wiki.internal/runbooks/ticketpulse-high-error-rate"

        # High latency: p99 > 500ms for 10 minutes
        - alert: TicketPulseHighLatency
          expr: ticketpulse:http_latency_p99:5m > 0.5
          for: 10m
          labels:
            severity: warning
            team: platform
          annotations:
            summary: "TicketPulse p99 latency is {{ $value | humanizeDuration }}"
            description: "P99 latency has exceeded 500ms for more than 10 minutes."
            runbook_url: "https://wiki.internal/runbooks/ticketpulse-high-latency"

        # Purchase failures: success rate drops below 95%
        - alert: TicketPulsePurchaseFailures
          expr: ticketpulse:purchase_success_rate:5m < 0.95
          for: 5m
          labels:
            severity: critical
            team: payments
          annotations:
            summary: "Ticket purchase success rate is {{ $value | humanizePercentage }}"
            description: "More than 5% of ticket purchases are failing."
            runbook_url: "https://wiki.internal/runbooks/ticketpulse-purchase-failures"

        # Pod restarts: more than 3 restarts in 15 minutes
        - alert: TicketPulsePodRestarting
          expr: |
            increase(kube_pod_container_status_restarts_total{namespace="ticketpulse"}[15m]) > 3
          for: 0m
          labels:
            severity: warning
            team: platform
          annotations:
            summary: "Pod {{ $labels.pod }} restarting frequently"
            description: "Pod {{ $labels.pod }} has restarted {{ $value }} times in 15 minutes."
```

Notice the pattern: recording rules use `record:` and produce a new metric name. Alerting rules use `alert:` and reference the pre-computed recording rules. This keeps alert expressions simple and avoids redundant computation when multiple alerts use the same base query.

### 2b. Apply and Verify

```bash
kubectl apply -f monitoring/prometheus/rules/ticketpulse-rules.yaml

# Verify the PrometheusRule was created
kubectl get prometheusrules -n monitoring
# NAME                AGE
# ticketpulse-rules   5s

# Verify Prometheus loaded the rules
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
# Visit http://localhost:9090/rules
# You should see the "ticketpulse.recordings" and "ticketpulse.alerts" groups

# Check for any rule evaluation errors
# Visit http://localhost:9090/rules and look for red error indicators
```

### 2c. Lint Rules with promtool

Before applying rules to a cluster, lint them locally. This catches syntax errors, invalid PromQL, and common mistakes before they reach Prometheus.

```bash
# promtool expects raw Prometheus rule format, not the CRD wrapper.
# Extract the spec.groups section into a standalone rules file:
cat > /tmp/ticketpulse-rules-extracted.yaml << 'EOF'
groups:
  - name: ticketpulse.recordings
    interval: 30s
    rules:
      - record: ticketpulse:http_error_rate:5m
        expr: |
          sum(rate(http_requests_total{service="ticket-service", status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total{service="ticket-service"}[5m]))
      - record: ticketpulse:http_request_rate:5m
        expr: |
          sum(rate(http_requests_total{service="ticket-service"}[5m])) by (method, path)
      - record: ticketpulse:http_latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket{service="ticket-service"}[5m])) by (le)
          )
      - record: ticketpulse:purchase_success_rate:5m
        expr: |
          sum(rate(ticket_purchases_total{status="success"}[5m]))
          /
          sum(rate(ticket_purchases_total[5m]))
  - name: ticketpulse.alerts
    rules:
      - alert: TicketPulseHighErrorRate
        expr: ticketpulse:http_error_rate:5m > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "TicketPulse error rate is {{ $value | humanizePercentage }}"
      - alert: TicketPulseHighLatency
        expr: ticketpulse:http_latency_p99:5m > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "TicketPulse p99 latency is {{ $value | humanizeDuration }}"
      - alert: TicketPulsePurchaseFailures
        expr: ticketpulse:purchase_success_rate:5m < 0.95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Purchase success rate is {{ $value | humanizePercentage }}"
      - alert: TicketPulsePodRestarting
        expr: increase(kube_pod_container_status_restarts_total{namespace="ticketpulse"}[15m]) > 3
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.pod }} restarting frequently"
EOF

promtool check rules /tmp/ticketpulse-rules-extracted.yaml
# Expected output:
# Checking /tmp/ticketpulse-rules-extracted.yaml
#   SUCCESS: 8 rules found
```

### 2d. Unit Test Rules with promtool

promtool supports unit tests that simulate time-series data and assert that alerts fire (or do not fire) at the right thresholds. This is how you test your alerting rules in CI before deploying them.

```yaml
# monitoring/prometheus/tests/ticketpulse-rules-test.yaml
rule_files:
  - /tmp/ticketpulse-rules-extracted.yaml

evaluation_interval: 30s

tests:
  # ── Test 1: High error rate triggers alert ─────────────────
  - interval: 1m
    input_series:
      # 20 requests/sec total, 1 error/sec = 5% error rate
      - series: 'http_requests_total{service="ticket-service", status="200"}'
        values: "0+19x30"       # +19 every minute for 30 minutes
      - series: 'http_requests_total{service="ticket-service", status="500"}'
        values: "0+1x30"        # +1 every minute for 30 minutes

    # Check that the recording rule computes correctly
    promql_expr_test:
      - expr: ticketpulse:http_error_rate:5m
        eval_time: 10m
        exp_samples:
          - labels: 'ticketpulse:http_error_rate:5m{team="platform"}'
            value: 0.05          # 1/20 = 5%

    # Check that the alert fires after 5 minutes
    alert_rule_test:
      - eval_time: 15m          # 10m for data + 5m for 'for' duration
        alertname: TicketPulseHighErrorRate
        exp_alerts:
          - exp_labels:
              severity: critical
              team: platform
            exp_annotations:
              summary: "TicketPulse error rate is 5%"

  # ── Test 2: Normal error rate does NOT trigger ─────────────
  - interval: 1m
    input_series:
      # 1000 requests/sec total, 5 errors/sec = 0.5% error rate
      - series: 'http_requests_total{service="ticket-service", status="200"}'
        values: "0+995x30"
      - series: 'http_requests_total{service="ticket-service", status="500"}'
        values: "0+5x30"

    alert_rule_test:
      - eval_time: 15m
        alertname: TicketPulseHighErrorRate
        exp_alerts: []          # No alerts expected

  # ── Test 3: Purchase failures trigger alert ────────────────
  - interval: 1m
    input_series:
      - series: 'ticket_purchases_total{status="success"}'
        values: "0+90x30"       # 90 successes/min
      - series: 'ticket_purchases_total{status="failed"}'
        values: "0+10x30"       # 10 failures/min = 10% failure rate

    alert_rule_test:
      - eval_time: 15m
        alertname: TicketPulsePurchaseFailures
        exp_alerts:
          - exp_labels:
              severity: critical
              team: payments
            exp_annotations:
              summary: "Purchase success rate is 90%"
```

Run the tests:

```bash
promtool test rules monitoring/prometheus/tests/ticketpulse-rules-test.yaml
# Expected output:
# Unit Testing: monitoring/prometheus/tests/ticketpulse-rules-test.yaml
#   SUCCESS
```

If a test fails, promtool shows exactly which assertion failed and the actual vs expected values. Add this to your CI pipeline so rule changes are tested before merge:

```bash
# In your CI pipeline (e.g., GitHub Actions)
- name: Test Prometheus rules
  run: |
    promtool check rules monitoring/prometheus/rules/*.yaml
    promtool test rules monitoring/prometheus/tests/*.yaml
```

---

## 3. SLO as Code with Sloth

Writing multi-window, multi-burn-rate alerts by hand is tedious and error-prone. Google's SRE Workbook defines the math: you need alerts at different burn rates (14.4x, 6x, 3x, 1x) over different windows (1h, 6h, 1d, 3d). Sloth generates all of this from a single SLO definition.

### 3a. Define the SLO

```yaml
# monitoring/slos/ticketpulse-api-availability.yaml
version: "prometheus/v1"
service: "ticketpulse-api"
labels:
  team: platform
  environment: production
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
      annotations:
        runbook_url: "https://wiki.internal/runbooks/ticketpulse-availability"
      page_alert:
        labels:
          severity: critical
      ticket_alert:
        labels:
          severity: warning
```

The key is `{{.window}}` -- Sloth replaces this placeholder with different time windows when generating rules.

### 3b. Generate Prometheus Rules

```bash
sloth generate \
  -i monitoring/slos/ticketpulse-api-availability.yaml \
  -o monitoring/prometheus/rules/ticketpulse-slo-generated.yaml

echo "--- Generated rules ---"
cat monitoring/prometheus/rules/ticketpulse-slo-generated.yaml
```

Inspect the output. Sloth generates three groups:

1. **SLI recording rules** -- compute the error ratio over multiple windows (5m, 30m, 1h, 2h, 6h, 1d, 3d, 30d):
   ```yaml
   - record: slo:sli_error:ratio_rate5m
     expr: (sum(rate(http_requests_total{service="ticket-service",status=~"5.."}[5m]))) / (sum(rate(http_requests_total{service="ticket-service"}[5m])))
   ```

2. **Metadata recording rules** -- store the SLO objective and error budget:
   ```yaml
   - record: slo:objective:ratio
     expr: "0.999"
   - record: slo:error_budget:ratio
     expr: "0.001"
   ```

3. **Multi-burn-rate alerts** -- page for fast burns, ticket for slow burns:
   ```yaml
   # Page alert: 14.4x burn over 1h AND 6x burn over 6h
   - alert: TicketPulseAvailability
     expr: (slo:sli_error:ratio_rate1h > (14.4 * 0.001)) and (slo:sli_error:ratio_rate6h > (6 * 0.001))
     labels:
       severity: critical
   ```

This is the math you would otherwise write by hand -- four burn-rate tiers, each checked over two windows to reduce false positives.

### 3c. Add a Latency SLO

```yaml
# monitoring/slos/ticketpulse-api-latency.yaml
version: "prometheus/v1"
service: "ticketpulse-api"
labels:
  team: platform
  environment: production
slos:
  - name: "requests-latency"
    objective: 99.0
    description: "99% of API requests complete within 500ms"
    sli:
      events:
        error_query: |
          (
            sum(rate(http_request_duration_seconds_count{service="ticket-service"}[{{.window}}]))
            -
            sum(rate(http_request_duration_seconds_bucket{service="ticket-service",le="0.5"}[{{.window}}]))
          )
        total_query: sum(rate(http_request_duration_seconds_count{service="ticket-service"}[{{.window}}]))
    alerting:
      name: TicketPulseLatency
      labels:
        team: platform
      annotations:
        runbook_url: "https://wiki.internal/runbooks/ticketpulse-latency"
      page_alert:
        labels:
          severity: critical
      ticket_alert:
        labels:
          severity: warning
```

The error query counts requests that took longer than 500ms (total requests minus those in the le="0.5" histogram bucket). Generate and apply:

```bash
sloth generate \
  -i monitoring/slos/ticketpulse-api-latency.yaml \
  -o monitoring/prometheus/rules/ticketpulse-latency-slo-generated.yaml

# Validate both generated files
promtool check rules monitoring/prometheus/rules/ticketpulse-slo-generated.yaml
promtool check rules monitoring/prometheus/rules/ticketpulse-latency-slo-generated.yaml

# Apply both
kubectl apply -f monitoring/prometheus/rules/ticketpulse-slo-generated.yaml
kubectl apply -f monitoring/prometheus/rules/ticketpulse-latency-slo-generated.yaml
```

### 3d. Why Sloth Over Hand-Written Rules?

Sloth gives you three things hand-written rules do not:

1. **Correctness.** The multi-window, multi-burn-rate math is tricky. Getting one window wrong means either too many false alarms or missed incidents.
2. **Consistency.** Every SLO in your organization follows the same alerting methodology.
3. **Maintainability.** To change the availability target from 99.9% to 99.95%, you change one line (`objective: 99.95`) and regenerate. With hand-written rules you would need to recalculate every burn-rate threshold.

---

## 4. GitOps with ArgoCD

Up to this point you have been running `kubectl apply` by hand. GitOps inverts this: you commit manifests to Git, and an agent running inside the cluster pulls those manifests and applies them automatically. The cluster's desired state is always whatever is declared in the main branch.

### 4a. Push vs Pull GitOps

| Model | How | Security | Example |
|-------|-----|----------|---------|
| **Push-based** | CI pushes changes to the cluster | CI needs cluster write credentials | GitHub Actions runs `kubectl apply` |
| **Pull-based** | Agent in cluster pulls from Git | Cluster pulls (read-only); no external write access needed | ArgoCD, Flux |

Pull-based is more secure: the cluster reaches out to Git (read-only access), rather than CI reaching into the cluster (write access). ArgoCD is the most widely adopted pull-based GitOps tool.

### 4b. GitOps Repository Structure

Create a repository (or directory) that contains all Kubernetes manifests for TicketPulse, organized with Kustomize:

```
ticketpulse-infra/
├── base/
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── ticket-service/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── event-service/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── payment-service/
│       ├── deployment.yaml
│       └── service.yaml
├── overlays/
│   ├── staging/
│   │   ├── kustomization.yaml
│   │   ├── replicas-patch.yaml
│   │   └── configmap.yaml
│   └── production/
│       ├── kustomization.yaml
│       ├── replicas-patch.yaml
│       └── configmap.yaml
└── monitoring/
    ├── grafana/
    │   ├── grafana-dashboards-configmap.yaml
    │   └── grafana-deployment-patch.yaml
    ├── prometheus/
    │   └── rules/
    │       ├── ticketpulse-rules.yaml
    │       ├── ticketpulse-slo-generated.yaml
    │       └── ticketpulse-latency-slo-generated.yaml
    └── slos/
        ├── ticketpulse-api-availability.yaml
        └── ticketpulse-api-latency.yaml
```

### 4c. Build the Base Manifests

The base contains the common configuration shared across all environments:

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  - ticket-service/deployment.yaml
  - ticket-service/service.yaml
  - event-service/deployment.yaml
  - event-service/service.yaml
  - payment-service/deployment.yaml
  - payment-service/service.yaml

commonLabels:
  app.kubernetes.io/part-of: ticketpulse
  app.kubernetes.io/managed-by: argocd
```

```yaml
# base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ticketpulse
```

```yaml
# base/ticket-service/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ticket-service
  namespace: ticketpulse
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ticket-service
  template:
    metadata:
      labels:
        app: ticket-service
    spec:
      containers:
        - name: ticket-service
          image: ticketpulse/ticket-service:v1.0.0
          ports:
            - containerPort: 3000
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

```yaml
# base/ticket-service/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ticket-service
  namespace: ticketpulse
spec:
  selector:
    app: ticket-service
  ports:
    - port: 80
      targetPort: 3000
```

### 4d. Build the Overlays

Overlays customize the base for each environment:

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: ticketpulse

patches:
  - path: replicas-patch.yaml
  - path: configmap.yaml

images:
  - name: ticketpulse/ticket-service
    newTag: staging-abc1234
```

```yaml
# overlays/staging/replicas-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ticket-service
spec:
  replicas: 1
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-service
spec:
  replicas: 1
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  replicas: 1
```

```yaml
# overlays/staging/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ticketpulse-config
  namespace: ticketpulse
data:
  NODE_ENV: "staging"
  LOG_LEVEL: "debug"
  FEATURE_WAITLIST: "true"
```

```yaml
# overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: ticketpulse

patches:
  - path: replicas-patch.yaml
  - path: configmap.yaml

images:
  - name: ticketpulse/ticket-service
    newTag: v1.2.3
```

```yaml
# overlays/production/replicas-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ticket-service
spec:
  replicas: 3
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-service
spec:
  replicas: 2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  replicas: 2
```

```yaml
# overlays/production/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ticketpulse-config
  namespace: ticketpulse
data:
  NODE_ENV: "production"
  LOG_LEVEL: "warn"
  FEATURE_WAITLIST: "false"
```

Verify the overlays render correctly before committing:

```bash
# Preview what staging produces
kustomize build overlays/staging

# Preview what production produces
kustomize build overlays/production

# Diff the two environments
diff <(kustomize build overlays/staging) <(kustomize build overlays/production)
```

### 4e. Create the ArgoCD Application

The Application CRD tells ArgoCD what to watch and where to deploy:

```yaml
# argocd/ticketpulse-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ticketpulse-staging
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
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
      prune: true          # Delete resources removed from Git
      selfHeal: true        # Revert manual changes (drift correction)
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

Key fields explained:
- `prune: true` -- if you remove a manifest from Git, ArgoCD deletes the resource from the cluster.
- `selfHeal: true` -- if someone runs `kubectl edit` or `kubectl scale` directly, ArgoCD reverts the change.
- `retry` -- ArgoCD retries failed syncs with exponential backoff, handling transient errors.
- `finalizers` -- ensures ArgoCD cleans up managed resources if you delete the Application.

### 4f. Deploy and Verify

```bash
# If using a local repo, initialize and commit first
cd ticketpulse-infra
git init
git add .
git commit -m "Initial TicketPulse GitOps repo"

# For a local kind cluster, register the repo with ArgoCD
# Port-forward the ArgoCD server
kubectl port-forward -n argocd svc/argocd-server 8080:443 &

# Login to ArgoCD CLI
argocd login localhost:8080 --username admin --password "$ARGOCD_PASS" --insecure

# If using a local Git repo, add it to ArgoCD
# (For GitHub repos, ArgoCD can access them directly if public,
# or you can add SSH keys for private repos)
argocd repo add https://github.com/YOUR_USER/ticketpulse-infra.git

# Apply the Application CRD
kubectl apply -f argocd/ticketpulse-app.yaml

# Watch the sync
argocd app get ticketpulse-staging
# Status should transition: Unknown -> Progressing -> Healthy/Synced

# Open the ArgoCD UI
echo "ArgoCD UI: https://localhost:8080"
echo "Username: admin"
echo "Password: $ARGOCD_PASS"
# The UI shows a visual dependency graph of all your resources
```

In the ArgoCD UI you will see a tree of resources: Namespace -> Deployments -> ReplicaSets -> Pods, plus Services, ConfigMaps, and any other resources. Green means healthy and synced. Yellow means progressing. Red means degraded or out of sync.

---

## 5. Drift Detection and Self-Healing

This is where GitOps proves its value. Without GitOps, manual changes to a cluster accumulate silently -- someone scales a deployment for a load test and forgets to scale it back, someone edits a ConfigMap to debug an issue and never reverts it. With `selfHeal: true`, ArgoCD continuously compares cluster state to Git and reverts any differences.

### Exercise: Break It and Watch ArgoCD Fix It

<details>
<summary>💡 Hint 1: selfHeal interval determines how fast the revert happens</summary>
ArgoCD's default self-heal check runs every ~5 seconds. If your manual `kubectl scale` is not reverted within 10-15 seconds, check that `selfHeal: true` is set in the Application's `syncPolicy.automated` block. Without it, ArgoCD detects drift but does not fix it.
</details>

**Step 1: Check the current state.**

```bash
kubectl get deployment ticket-service -n ticketpulse -o jsonpath='{.spec.replicas}'
# Should show: 1 (staging overlay sets replicas to 1)
```

**Step 2: Manually introduce drift.**

```bash
kubectl scale deployment ticket-service --replicas=5 -n ticketpulse
kubectl get deployment ticket-service -n ticketpulse
# NAME             READY   UP-TO-DATE   AVAILABLE   AGE
# ticket-service   5/5     5            5           10m
```

**Step 3: Watch ArgoCD detect and revert.**

```bash
# Check ArgoCD status -- it should show OutOfSync briefly
argocd app get ticketpulse-staging | grep -E "Status|Health"
# Health Status:   Healthy
# Sync Status:     OutOfSync  (briefly, then Synced)

# Watch the replicas revert (selfHeal triggers within ~5 seconds by default)
kubectl get deployment ticket-service -n ticketpulse -w
# NAME             READY   UP-TO-DATE   AVAILABLE   AGE
# ticket-service   5/5     5            5           10m
# ticket-service   1/1     1            1           10m   <-- ArgoCD reverted!
```

**Step 4: Check the ArgoCD event log.**

```bash
argocd app history ticketpulse-staging
# The history shows each sync event, including auto-syncs triggered by drift

# For more detail:
kubectl get events -n argocd --sort-by='.lastTimestamp' | grep ticketpulse
```

The point is clear: the only way to change the number of replicas in production is to commit a change to `overlays/production/replicas-patch.yaml`, get it reviewed, and merge it. Manual `kubectl` changes are undone automatically.

---

## 6. The Full Loop

This exercise ties together everything in this module: dashboards-as-code, alerting rules, SLOs, and GitOps. You will make three changes in one commit and watch them propagate through ArgoCD to both the application and the monitoring stack.

### Exercise: End-to-End GitOps

<details>
<summary>💡 Hint 1: Use an ArgoCD ApplicationSet if you manage multiple environments</summary>
Instead of duplicating Application manifests for staging and production, an ApplicationSet with a list generator produces one Application per environment from a single template. The `path` field uses `overlays/{{name}}` to select the right Kustomize overlay per cluster.
</details>

**Preparation:** Create an ArgoCD Application for the monitoring directory as well:

```yaml
# argocd/ticketpulse-monitoring-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ticketpulse-monitoring
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USER/ticketpulse-infra.git
    targetRevision: main
    path: monitoring
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

```bash
kubectl apply -f argocd/ticketpulse-monitoring-app.yaml
```

**Step 1: Update a Grafana dashboard.**

Edit `monitoring/grafana/dashboards/ticketpulse-api-overview.json` and add a new panel to track the SLO error budget remaining:

```json
{
  "id": 5,
  "title": "Error Budget Remaining (30d)",
  "type": "gauge",
  "gridPos": { "x": 0, "y": 8, "w": 8, "h": 6 },
  "targets": [
    {
      "expr": "1 - (slo:sli_error:ratio_rate30d{sloth_service=\"ticketpulse-api\"} / (1 - slo:objective:ratio{sloth_service=\"ticketpulse-api\"}))",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "percentunit",
      "min": 0,
      "max": 1,
      "thresholds": {
        "steps": [
          { "color": "red", "value": null },
          { "color": "yellow", "value": 0.25 },
          { "color": "green", "value": 0.5 }
        ]
      }
    }
  }
}
```

**Step 2: Lower an alert threshold.**

Edit `monitoring/prometheus/rules/ticketpulse-rules.yaml` and change the high-error-rate threshold from 1% to 0.5%:

```yaml
# Change this:
        - alert: TicketPulseHighErrorRate
          expr: ticketpulse:http_error_rate:5m > 0.01
# To this:
        - alert: TicketPulseHighErrorRate
          expr: ticketpulse:http_error_rate:5m > 0.005
```

**Step 3: Update an image tag.**

Edit `overlays/staging/kustomization.yaml` and update the image tag:

```yaml
images:
  - name: ticketpulse/ticket-service
    newTag: staging-def5678    # was staging-abc1234
```

**Step 4: Commit, push, and watch.**

```bash
git add -A
git commit -m "Add error budget panel, tighten alert threshold, deploy staging-def5678"
git push origin main

# Watch both ArgoCD applications sync
argocd app list
# NAME                     SYNC      HEALTH
# ticketpulse-staging      Synced    Healthy
# ticketpulse-monitoring   Synced    Healthy

# Verify the dashboard update loaded in Grafana
# Verify the new alert threshold in Prometheus (/rules)
# Verify the new image is running
kubectl get deployment ticket-service -n ticketpulse -o jsonpath='{.spec.template.spec.containers[0].image}'
# ticketpulse/ticket-service:staging-def5678
```

**Answer these questions:**

1. What is the maximum time between your `git push` and the changes being live in the cluster? (Hint: ArgoCD's default polling interval is 3 minutes, but webhooks can make it near-instant.)
2. If the new image tag fails to pull (does not exist in the registry), what happens? Does ArgoCD roll back? (No -- it stays OutOfSync/Degraded. ArgoCD does not automatically roll back failed syncs. You revert the commit in Git.)
3. How would you promote the staging-def5678 image to production? (Update `overlays/production/kustomization.yaml` with the new tag and merge to main.)

---

## 7. Reflect

> **"Why not just use Grafana's built-in dashboard save/versioning?"**
>
> Grafana does have internal versioning, but it only tracks changes made through the UI. It cannot be reviewed in a pull request, it is not visible to anyone who does not have Grafana access, and it does not work across environments (staging and production would each have their own version history). File-based provisioning makes dashboards part of the same Git workflow as the rest of your infrastructure.

> **"The Sloth-generated rules are complex. What if I need to customize one?"**
>
> Do not edit the generated file directly -- it will be overwritten on the next `sloth generate`. Instead, either adjust the Sloth input (objective, labels, annotations) or create a separate PrometheusRule with your custom rules. Treat generated files as build artifacts: the SLO YAML is the source, the generated rules are the output.

> **"selfHeal sounds dangerous. What if ArgoCD reverts a legitimate hotfix?"**
>
> This is the point. In a GitOps workflow, the "legitimate" way to hotfix is to push an emergency commit to Git (even to a fast-tracked PR with a single approval). If you bypass Git, you are creating invisible state that is not reproducible and not auditable. selfHeal enforces the discipline. Teams that are not ready for this can start with `selfHeal: false` and use ArgoCD's manual sync + diff to review drift before reverting.

> **"How does this work with secrets? I cannot commit database passwords to Git."**
>
> Correct. Secrets are handled separately through tools like Sealed Secrets (encrypts secrets in Git, decrypts in-cluster), External Secrets Operator (syncs from AWS Secrets Manager / Vault into K8s Secrets), or SOPS (encrypts specific YAML values). The secret references (e.g., the Secret name in a Deployment's env spec) live in Git; the actual secret values do not.

---

## 8. Checkpoint

After this module, you should have:

- [ ] Grafana dashboard JSON exported and provisioned from files (not UI-only)
- [ ] Provisioning config that restores dashboards automatically on pod restart
- [ ] PrometheusRule CRD with both recording rules and alerting rules applied
- [ ] promtool lint passing on your rules files
- [ ] promtool unit tests validating that alerts fire at correct thresholds
- [ ] Sloth SLO definition generating multi-burn-rate alerts for availability
- [ ] A second Sloth SLO for latency, generated and applied
- [ ] GitOps repo structure with Kustomize base and overlays (staging + production)
- [ ] ArgoCD Application CRD deployed and syncing from Git
- [ ] Drift detection verified: manual `kubectl scale` was reverted by ArgoCD
- [ ] End-to-end test: one commit updating dashboard + alert + image tag, all synced

**Next up:** Continue with Section 3D modules to explore further cutting-edge practices.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Observability as Code** | Managing monitoring configuration (dashboards, alerts, SLOs) as version-controlled files rather than UI-only settings. |
| **Grafana Provisioning** | A mechanism where Grafana reads dashboard and datasource configuration from YAML/JSON files on disk, restoring them automatically on startup. |
| **PrometheusRule** | A Kubernetes custom resource (CRD) used by the Prometheus Operator to define recording and alerting rules. |
| **Recording Rule** | A Prometheus rule that pre-computes an expression and stores the result as a new time series, reducing query-time computation. |
| **promtool** | The command-line tool bundled with Prometheus for linting rules, running unit tests, and validating configuration. |
| **Sloth** | An SLO-as-code tool that generates multi-window, multi-burn-rate Prometheus alerting rules from a simple SLO definition. |
| **Multi-Burn-Rate Alert** | An alerting strategy from Google's SRE Workbook that uses multiple time windows and burn rates to balance alert sensitivity with false-positive reduction. |
| **GitOps** | An operational model where the desired state of infrastructure and applications is declared in Git, and an agent continuously reconciles actual state to match. |
| **ArgoCD** | A Kubernetes-native GitOps controller that watches a Git repository and automatically syncs manifests to a cluster. |
| **Application CRD** | ArgoCD's custom resource that defines what Git repo/path to watch, where to deploy, and sync policies. |
| **Self-Heal** | An ArgoCD sync policy that automatically reverts manual changes to cluster resources, enforcing Git as the single source of truth. |
| **Kustomize** | A Kubernetes-native configuration management tool that uses base manifests and overlays to customize resources per environment without templating. |
| **Drift** | When the actual state of a system differs from the declared state in Git, usually caused by manual changes. |
| **Pull-Based GitOps** | A GitOps model where an in-cluster agent pulls changes from Git, rather than CI pushing to the cluster. More secure because the cluster does not need to expose write access. |

### 🤔 Reflection Prompt

After moving dashboards and alerts into Git, what changed about your confidence in the monitoring stack? How does "delete everything and re-apply from Git" change your disaster recovery posture?

---

## What's Next

In **Platform Engineering & Crossplane** (L3-M83b), you'll build on what you learned here and take it further.

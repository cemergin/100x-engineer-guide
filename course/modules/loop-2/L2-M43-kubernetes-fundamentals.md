# L2-M43: Kubernetes Fundamentals

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 90 min | 🟢 Core | Prerequisites: L1-M14, L2-M31
>
> **Source:** Chapter 7 of the 100x Engineer Guide

## What You'll Learn

- How Kubernetes works: control plane, nodes, pods, and the reconciliation loop
- Writing K8s manifests from scratch: Deployment, Service, Ingress, ConfigMap, Secret
- Deploying TicketPulse to a local Kubernetes cluster with kind
- Interacting with running pods: logs, exec, describe
- Diagnosing common failures: ImagePullBackOff, OOMKilled, CrashLoopBackOff
- Scaling deployments and performing zero-downtime rolling updates
- When Kubernetes makes sense and when docker compose is the better choice

## Why This Matters

TicketPulse is now a microservices system: API gateway, event service, payment service, notification consumer, Kafka, per-service databases, Elasticsearch, and Neo4j. Docker Compose got us this far, but it runs on a single machine with no self-healing, no rolling updates, and no real service discovery. Kubernetes is the industry-standard platform for running containers in production. By the end of this module, TicketPulse will be running on a local Kubernetes cluster with replicas, health checks, and automatic restarts -- the same primitives used to run services at Google, Spotify, and Airbnb.

## Prereq Check

You need Docker running (from L1-M14) and the TicketPulse microservices images built (from L2-M31).

```bash
# Verify Docker is running
docker version

# Verify you have TicketPulse images
docker image ls | grep ticketpulse
# You should see images for api-gateway, event-service, payment-service, etc.
```

If you do not have the images, build them from your docker-compose setup:

```bash
cd ticketpulse
docker compose build
```

---

## 1. Install kind (Kubernetes in Docker)

kind runs a full Kubernetes cluster inside Docker containers. It is the fastest way to get a real K8s environment locally.

```bash
# macOS
brew install kind kubectl

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Verify
kind version
kubectl version --client
```

Now create a cluster:

```bash
# Create a cluster named "ticketpulse"
kind create cluster --name ticketpulse

# Verify
kubectl cluster-info --context kind-ticketpulse
kubectl get nodes
```

You should see one node with status `Ready`. That node is actually a Docker container running the Kubernetes control plane and a kubelet.

```
NAME                        STATUS   ROLES           AGE   VERSION
ticketpulse-control-plane   Ready    control-plane   30s   v1.31.0
```

### What just happened?

kind created a Docker container that runs:
- **kube-apiserver**: the front door for all K8s operations (kubectl talks to this)
- **etcd**: the key-value store holding all cluster state
- **kube-scheduler**: decides which node runs each pod
- **kube-controller-manager**: runs the reconciliation loops (desired state vs actual state)
- **kubelet**: the agent on each node that actually starts/stops containers
- **containerd**: the container runtime (what actually runs your images)

This is the same architecture that runs in production clusters with hundreds of nodes.

---

## 2. Load TicketPulse Images into kind

kind runs its own container registry inside Docker. Your local images are not automatically available inside the cluster.

```bash
# Load your images into the kind cluster
kind load docker-image ticketpulse-api-gateway:latest --name ticketpulse
kind load docker-image ticketpulse-event-service:latest --name ticketpulse
kind load docker-image ticketpulse-payment-service:latest --name ticketpulse
kind load docker-image ticketpulse-notification-consumer:latest --name ticketpulse
```

This copies each image from your local Docker daemon into the kind node. Without this step, Kubernetes would try to pull from Docker Hub and fail (since these are local images).

---

## 3. Build: Kubernetes Manifests from Scratch

We will write every manifest by hand. No Helm charts, no generators. You need to understand what every line does.

Create a directory for your K8s manifests:

```bash
mkdir -p ticketpulse/k8s
```

### 3a. Namespace

Namespaces isolate resources. Think of them as folders for your K8s objects.

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ticketpulse
```

```bash
kubectl apply -f k8s/namespace.yaml
kubectl get namespaces
```

From now on, every resource goes in the `ticketpulse` namespace.

### 3b. ConfigMap (Non-Secret Configuration)

ConfigMaps hold configuration that is NOT sensitive. Environment-specific values, feature flags, URLs.

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: ticketpulse
data:
  NODE_ENV: "production"
  LOG_LEVEL: "info"
  EVENT_SERVICE_URL: "http://event-service:3001"
  PAYMENT_SERVICE_URL: "http://payment-service:3002"
  KAFKA_BROKERS: "kafka:9092"
  ELASTICSEARCH_URL: "http://elasticsearch:9200"
```

Notice the service URLs use Kubernetes DNS names. `event-service:3001` resolves to the ClusterIP of the event-service Service. Kubernetes handles the DNS automatically.

### 3c. Secret (Sensitive Configuration)

Secrets hold passwords, API keys, and other sensitive data. They are base64-encoded (NOT encrypted by default -- we will discuss this).

```bash
# Create secrets from literal values
# In production, these come from a secret manager (Vault, AWS Secrets Manager)
kubectl create secret generic db-credentials \
  --namespace=ticketpulse \
  --from-literal=POSTGRES_USER=ticketpulse \
  --from-literal=POSTGRES_PASSWORD=supersecretpassword \
  --from-literal=DATABASE_URL="postgresql://ticketpulse:supersecretpassword@postgres:5432/ticketpulse" \
  --from-literal=JWT_SECRET="k8s-jwt-secret-change-in-production"
```

Verify:

```bash
kubectl get secrets -n ticketpulse
kubectl describe secret db-credentials -n ticketpulse
# Notice: the values are NOT shown, just their sizes
```

> **Important:** Kubernetes Secrets are base64-encoded, not encrypted. Anyone with `kubectl get secret -o yaml` access can decode them. In production, use an external secret manager (HashiCorp Vault, AWS Secrets Manager) with something like external-secrets-operator to sync secrets into K8s.

### 3d. Deployment (The API Gateway)

A Deployment declares the desired state for your pods: which image, how many replicas, resource limits, health checks. Kubernetes continuously reconciles actual state toward this desired state.

```yaml
# k8s/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: ticketpulse
  labels:
    app: api-gateway
    tier: frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1      # At most 1 pod down during update
      maxSurge: 1             # At most 1 extra pod during update
  template:
    metadata:
      labels:
        app: api-gateway
        tier: frontend
    spec:
      containers:
        - name: api-gateway
          image: ticketpulse-api-gateway:latest
          imagePullPolicy: Never    # Use local image (loaded via kind)
          ports:
            - containerPort: 3000
              name: http
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: db-credentials
          resources:
            requests:
              cpu: "100m"           # 0.1 CPU cores (minimum guaranteed)
              memory: "128Mi"       # 128 MiB (minimum guaranteed)
            limits:
              cpu: "500m"           # 0.5 CPU cores (maximum allowed)
              memory: "512Mi"       # 512 MiB (exceeded = OOMKilled)
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 15
            periodSeconds: 20
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]
                # Give the load balancer time to drain connections
```

Let us break down every section:

**`replicas: 3`** -- Three instances of the API gateway run simultaneously. If one crashes, two remain while K8s restarts the third. This is the most basic form of high availability.

**`selector.matchLabels`** -- How the Deployment finds its pods. Labels are key-value pairs on every K8s object. The Deployment watches pods with `app: api-gateway`.

**`strategy.rollingUpdate`** -- During deploys, K8s replaces pods one at a time. With `maxUnavailable: 1` and `maxSurge: 1`, at worst we have 2 old pods + 1 new pod, then 1 old + 2 new, then 3 new. Zero downtime.

**`resources.requests`** -- The scheduler uses these to place pods on nodes. "This pod needs at least 100m CPU and 128Mi memory."

**`resources.limits`** -- Hard ceilings. If the container exceeds the memory limit, it gets OOMKilled. If it exceeds the CPU limit, it gets throttled (slowed down, not killed).

**`readinessProbe`** -- "Is this pod ready to receive traffic?" K8s removes unready pods from the Service load balancer. A pod starting up is not ready until it passes this check.

**`livenessProbe`** -- "Is this pod still alive?" If it fails, K8s restarts the container. Use this to recover from deadlocks or hung processes.

**`preStop` hook** -- When K8s decides to terminate a pod (during scaling or rolling update), it sends SIGTERM. The `sleep 5` gives the load balancer time to stop routing traffic to this pod before the app starts shutting down. This prevents dropped requests.

### 3e. Service (Internal Load Balancer)

A Service provides a stable network endpoint for a set of pods. Pods come and go (scaling, restarts, updates), but the Service IP never changes.

```yaml
# k8s/api-gateway-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: ticketpulse
  labels:
    app: api-gateway
spec:
  type: ClusterIP
  selector:
    app: api-gateway        # Routes to pods with this label
  ports:
    - name: http
      port: 80              # The port the Service listens on
      targetPort: 3000      # The port on the container
      protocol: TCP
```

**ClusterIP** means this Service is only accessible inside the cluster. Other services reach it at `api-gateway.ticketpulse.svc.cluster.local:80` (or just `api-gateway:80` from within the same namespace).

The Service load-balances across all pods matching `app: api-gateway` that pass their readiness probe.

### 3f. Ingress (External Access)

An Ingress routes external HTTP traffic into the cluster. It is like an nginx config managed by Kubernetes.

First, install the nginx Ingress controller in kind:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for it to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s
```

Now create the Ingress:

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ticketpulse-ingress
  namespace: ticketpulse
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: ticketpulse.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 80
```

Add the hostname to your `/etc/hosts`:

```bash
echo "127.0.0.1 ticketpulse.local" | sudo tee -a /etc/hosts
```

---

## 4. Build: Deploy to the Cluster

Now apply everything:

```bash
# Apply the manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/api-gateway-deployment.yaml
kubectl apply -f k8s/api-gateway-service.yaml
kubectl apply -f k8s/ingress.yaml
```

Watch the pods come up:

```bash
# Watch pods in real time
kubectl get pods -n ticketpulse -w
```

You should see three pods transition through these states:

```
NAME                          READY   STATUS              RESTARTS   AGE
api-gateway-7f8b9c5d6-abc12  0/1     ContainerCreating   0          2s
api-gateway-7f8b9c5d6-def34  0/1     ContainerCreating   0          2s
api-gateway-7f8b9c5d6-ghi56  0/1     ContainerCreating   0          2s
api-gateway-7f8b9c5d6-abc12  0/1     Running             0          5s
api-gateway-7f8b9c5d6-abc12  1/1     Running             0          15s
...
```

`0/1` means the readiness probe has not passed yet. `1/1` means the pod is ready and receiving traffic.

---

## 5. Try It: Interact with Running Pods

This is where Kubernetes becomes tangible. These commands are the ones you will use every day.

### Get pod status

```bash
# List all pods
kubectl get pods -n ticketpulse

# Show more detail (node, IP, status)
kubectl get pods -n ticketpulse -o wide

# Show all resources in the namespace
kubectl get all -n ticketpulse
```

### Read logs

```bash
# Logs from a specific pod
kubectl logs -n ticketpulse api-gateway-7f8b9c5d6-abc12

# Follow logs in real time (like tail -f)
kubectl logs -n ticketpulse api-gateway-7f8b9c5d6-abc12 -f

# Logs from ALL pods matching a label
kubectl logs -n ticketpulse -l app=api-gateway --all-containers

# Last 50 lines
kubectl logs -n ticketpulse api-gateway-7f8b9c5d6-abc12 --tail=50

# Logs from the last 5 minutes
kubectl logs -n ticketpulse api-gateway-7f8b9c5d6-abc12 --since=5m
```

### Shell into a running pod

```bash
# Open a shell inside a running container
kubectl exec -it -n ticketpulse api-gateway-7f8b9c5d6-abc12 -- /bin/sh

# Once inside, verify the environment:
env | grep DATABASE    # See the secret was injected
env | grep EVENT       # See the configmap was injected
wget -qO- http://localhost:3000/health   # Hit the health endpoint from inside
exit
```

### Describe a resource (detailed info + events)

```bash
# Detailed info about a pod
kubectl describe pod -n ticketpulse api-gateway-7f8b9c5d6-abc12

# This shows:
# - Container image, ports, environment variables
# - Resource requests and limits
# - Probe configuration
# - Events (scheduling, pulling image, starting, readiness)
# - Restart count and reason
```

The Events section at the bottom of `kubectl describe` is your primary debugging tool. It tells you exactly what happened and when.

### Port-forward to test locally

```bash
# Forward local port 3000 to the service
kubectl port-forward -n ticketpulse svc/api-gateway 3000:80

# In another terminal, test it
curl -s http://localhost:3000/health | jq .
```

---

## 6. Debug: Intentional Failures

You need to recognize common failures by sight. Let us cause them on purpose.

### Failure 1: ImagePullBackOff

```yaml
# Change the image to something that does not exist
kubectl set image deployment/api-gateway \
  -n ticketpulse \
  api-gateway=ticketpulse-api-gateway:v999-does-not-exist
```

Watch:

```bash
kubectl get pods -n ticketpulse -w
# You'll see: ErrImagePull → ImagePullBackOff

kubectl describe pod -n ticketpulse <pod-name>
# Events will show:
# Failed to pull image "ticketpulse-api-gateway:v999-does-not-exist": ...
```

**What you see:** `ImagePullBackOff` with exponentially increasing backoff delays.
**Root cause:** Wrong image name or tag, missing image in registry, missing imagePullSecret.
**Fix:** Correct the image tag.

```bash
# Fix it
kubectl set image deployment/api-gateway \
  -n ticketpulse \
  api-gateway=ticketpulse-api-gateway:latest
```

### Failure 2: OOMKilled

```bash
# Set an absurdly low memory limit
kubectl set resources deployment/api-gateway \
  -n ticketpulse \
  --limits=memory=10Mi
```

Watch:

```bash
kubectl get pods -n ticketpulse -w
# STATUS: OOMKilled → CrashLoopBackOff

kubectl describe pod -n ticketpulse <pod-name>
# Last State: Terminated
# Reason: OOMKilled
# Exit Code: 137
```

**What you see:** Container starts, immediately gets killed, restarts, gets killed again. The `CrashLoopBackOff` status means K8s is backing off on restarts.
**Root cause:** Memory limit too low for the application.
**Fix:** Increase the memory limit.

```bash
# Fix it
kubectl set resources deployment/api-gateway \
  -n ticketpulse \
  --limits=memory=512Mi --requests=memory=128Mi
```

### Failure 3: CrashLoopBackOff (Application Error)

```bash
# Set an environment variable that will break the app
kubectl set env deployment/api-gateway \
  -n ticketpulse \
  DATABASE_URL="postgresql://wrong:wrong@nonexistent:5432/nope"
```

```bash
kubectl get pods -n ticketpulse -w
# STATUS: Error → CrashLoopBackOff

# Check why it crashed
kubectl logs -n ticketpulse <pod-name> --previous
# Shows the app's crash log (connection refused, auth failed, etc.)
```

**What you see:** Pod starts, app crashes, K8s restarts it, it crashes again.
**Root cause:** Application startup failure (bad config, missing dependency, code bug).
**Fix:** Check logs with `--previous` to see the crash output, fix the underlying issue.

```bash
# Fix it -- remove the override to restore the secret value
kubectl set env deployment/api-gateway \
  -n ticketpulse \
  DATABASE_URL-
```

---

## 7. Scale It

```bash
# Scale to 5 replicas
kubectl scale deployment api-gateway -n ticketpulse --replicas=5

# Watch the new pods come up
kubectl get pods -n ticketpulse -w

# Verify all 5 are running
kubectl get pods -n ticketpulse
```

You should see 5 pods, all `1/1 Running`. Kubernetes scheduled them, pulled the image (already cached), started the containers, and waited for readiness probes to pass. In production, an HPA (Horizontal Pod Autoscaler) would do this automatically based on CPU or custom metrics.

```bash
# Scale back down
kubectl scale deployment api-gateway -n ticketpulse --replicas=3

# Watch pods terminate gracefully
kubectl get pods -n ticketpulse -w
# You'll see pods go through Terminating state
```

When scaling down, K8s picks pods to terminate, sends SIGTERM, waits for the `preStop` hook and graceful shutdown, then removes them. In-flight requests are not dropped.

---

## 8. Observe: Resource Usage

```bash
# Install metrics-server in kind
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch metrics-server to work with kind (self-signed certs)
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

# Wait for it to be ready (takes ~60 seconds)
kubectl wait --for=condition=ready pod \
  -l k8s-app=metrics-server \
  -n kube-system \
  --timeout=120s
```

Now check resource usage:

```bash
# CPU and memory per pod
kubectl top pods -n ticketpulse

# Example output:
# NAME                          CPU(cores)   MEMORY(bytes)
# api-gateway-7f8b9c5d6-abc12  3m           85Mi
# api-gateway-7f8b9c5d6-def34  2m           82Mi
# api-gateway-7f8b9c5d6-ghi56  4m           88Mi

# CPU and memory per node
kubectl top nodes
```

`3m` means 3 millicores (0.003 CPU cores). `85Mi` means 85 mebibytes. These are your baselines. If `MEMORY` is approaching `limits.memory` (512Mi), you risk OOMKilled.

---

## 9. Rolling Updates

The real power of Kubernetes: deploy new code with zero downtime.

```bash
# Simulate a new version by rebuilding the image with a tag
docker build -t ticketpulse-api-gateway:v2 .
kind load docker-image ticketpulse-api-gateway:v2 --name ticketpulse

# Update the deployment to use the new image
kubectl set image deployment/api-gateway \
  -n ticketpulse \
  api-gateway=ticketpulse-api-gateway:v2

# Watch the rolling update
kubectl rollout status deployment/api-gateway -n ticketpulse
```

What happens step by step:
1. K8s creates 1 new pod with the v2 image (`maxSurge: 1`)
2. Waits for the new pod's readiness probe to pass
3. Terminates 1 old pod (`maxUnavailable: 1`)
4. Creates another new pod
5. Repeat until all pods are running v2

At no point are fewer than 2 pods serving traffic.

```bash
# Check rollout history
kubectl rollout history deployment/api-gateway -n ticketpulse

# Rollback to previous version if something goes wrong
kubectl rollout undo deployment/api-gateway -n ticketpulse

# Rollback to a specific revision
kubectl rollout undo deployment/api-gateway -n ticketpulse --to-revision=1
```

---

## 10. Deploying the Event Service

Repeat the pattern for the event service. Notice how the structure is identical -- only the names, image, and port change.

```yaml
# k8s/event-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-service
  namespace: ticketpulse
  labels:
    app: event-service
    tier: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: event-service
  template:
    metadata:
      labels:
        app: event-service
        tier: backend
    spec:
      containers:
        - name: event-service
          image: ticketpulse-event-service:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 3001
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: db-credentials
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          readinessProbe:
            httpGet:
              path: /health
              port: 3001
            initialDelaySeconds: 5
            periodSeconds: 10
---
# k8s/event-service-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: event-service
  namespace: ticketpulse
spec:
  type: ClusterIP
  selector:
    app: event-service
  ports:
    - port: 3001
      targetPort: 3001
```

```bash
kubectl apply -f k8s/event-service-deployment.yaml
kubectl apply -f k8s/event-service-service.yaml
kubectl get pods -n ticketpulse
```

Now the API gateway can reach the event service at `http://event-service:3001` -- exactly what we put in the ConfigMap. Kubernetes DNS handles the resolution.

---

## 11. Reflect

Think about these questions before moving on:

> **"What does Kubernetes give us that docker compose does not?"**
>
> Self-healing (crashed containers restart automatically), rolling updates (zero-downtime deploys), scaling (add/remove replicas), service discovery (DNS-based), health checks (readiness and liveness probes), resource management (requests and limits prevent noisy neighbors), and declarative state (you describe what you want, K8s makes it happen).

> **"When is docker compose still the better choice?"**
>
> Local development (faster startup, simpler debugging), small projects with 1-3 services, when you do not need high availability, when your team is small and deploys manually. Docker compose is minutes to set up; Kubernetes is hours. Do not use K8s for a side project with 2 containers.

> **"We have 3 replicas of the API gateway. What happens if 2 of them crash at the same time?"**
>
> The remaining pod handles all traffic (possibly with degraded performance). K8s immediately starts 2 new pods. Once they pass readiness probes, they join the load balancer. Total recovery time: ~15-30 seconds. In production, you would set a Pod Disruption Budget to ensure at least 2 pods are always available during voluntary disruptions.

---

## 12. Checkpoint

After this module, your TicketPulse setup should have:

- [ ] A kind Kubernetes cluster running locally
- [ ] TicketPulse images loaded into the cluster
- [ ] A Namespace, ConfigMap, and Secret for configuration
- [ ] A Deployment with 3 replicas, resource limits, and health probes
- [ ] A ClusterIP Service for internal routing
- [ ] An Ingress for external HTTP access
- [ ] You have diagnosed ImagePullBackOff, OOMKilled, and CrashLoopBackOff
- [ ] You have scaled the deployment up and down
- [ ] You have performed a rolling update with zero downtime
- [ ] `kubectl top pods` shows CPU and memory usage
- [ ] The event service is deployed and reachable from the API gateway

**Next up:** L2-M44 where we define all of this infrastructure as code with Terraform -- so we never have to run `kubectl apply` manually again.

---

## Glossary

| Term | Definition |
|------|-----------|
| **kind** | Kubernetes IN Docker. Runs a full K8s cluster inside Docker containers for local development and CI. |
| **Pod** | The smallest deployable unit in Kubernetes. One or more containers sharing network and storage. |
| **Deployment** | A controller that manages a set of identical pods, handling scaling, updates, and self-healing. |
| **Service** | A stable network endpoint that load-balances traffic across a set of pods matched by label selectors. |
| **ClusterIP** | The default Service type. Accessible only within the cluster. |
| **Ingress** | An API object that manages external HTTP access to services, typically via an Ingress controller like nginx. |
| **ConfigMap** | Stores non-sensitive configuration data as key-value pairs, injected into pods as environment variables or files. |
| **Secret** | Stores sensitive data (passwords, tokens). Base64-encoded by default, not encrypted. |
| **Readiness Probe** | A check that determines if a pod is ready to receive traffic. Failed probes remove the pod from the Service. |
| **Liveness Probe** | A check that determines if a pod is still alive. Failed probes trigger a container restart. |
| **Rolling Update** | A deployment strategy that replaces pods incrementally, maintaining availability throughout. |
| **OOMKilled** | Out Of Memory Killed. The container exceeded its memory limit and was terminated by the kernel. |
| **ImagePullBackOff** | Kubernetes cannot pull the container image. Usually a wrong tag, missing registry credentials, or typo. |
| **CrashLoopBackOff** | The container keeps crashing on startup. K8s backs off on restart attempts exponentially. |

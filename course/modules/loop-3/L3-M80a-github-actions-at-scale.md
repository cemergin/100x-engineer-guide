# L3-M80a: GitHub Actions at Scale

> **Loop 3 (Mastery)** | Section 3C+: Platform Engineering | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M55a (GitHub Actions Mastery), L3-M80 (Building Your Platform)
>
> **Source:** Chapter 33 of the 100x Engineer Guide

## What You'll Learn

- How to build custom composite and JavaScript GitHub Actions that encapsulate your organization's deployment logic
- When and how to run self-hosted runners at scale using actions-runner-controller on Kubernetes
- How to design multi-environment deployment pipelines with protection rules, required reviewers, and regional rollouts
- How cross-repository workflows enable shared CI/CD across a platform with 10+ services
- How to measure CI/CD health with observability and connect it to DORA metrics

## Why This Matters

TicketPulse has grown. What was 3 services is now 12. The team went from 5 engineers to 25. The platform spans 3 regions: us-east-1, eu-west-1, and ap-southeast-1. There is a recommendation engine that needs GPU runners. There is a payment service that must build inside a private VPC. And every service has its own workflow file that is a copy-pasted variant of every other service's workflow file -- 12 files, each 200+ lines, each slightly different, each drifting further apart.

Last week, someone updated the Docker build step in the order-service workflow but forgot to update the other 11. The event-service deployed with the old base image and a known CVE. Nobody noticed for 3 days.

This is what happens when CI/CD does not scale with the platform. The workflow files that were "good enough" at 3 services become a liability at 12. The GitHub-hosted runners that were fast enough at 50 builds/day are now queuing at 300 builds/day. The manual deployment approvals that one person handled are now a bottleneck across 3 time zones.

> **Pro tip:** "Shopify has 400+ engineers committing to a monorepo with 40,000+ CI minutes per day. Their investment in custom actions, self-hosted runners, and CI observability is what makes that possible. You do not need to be Shopify to feel the pain -- it starts around 10 services and 100 builds/day."

---

### 🤔 Prediction Prompt

Before reading further, think about what happens when your team has 12 services each with their own CI workflow file. Where do you expect the drift, duplication, and operational pain to concentrate?

## Prereq Check

You should be comfortable with:

```
✅ Writing GitHub Actions workflows (triggers, jobs, steps, matrix)
✅ Docker multi-stage builds and container registries
✅ Kubernetes basics (pods, deployments, services)
✅ TicketPulse's multi-region architecture from L3-M61
✅ The platform concepts from L3-M80
```

If any of these are unfamiliar, revisit the prerequisite modules first.

---

## Part 1: Building Custom GitHub Actions

### The Problem: Copy-Paste Workflows

Every TicketPulse service deploys the same way:

```
1. Build Docker image
2. Push to ECR
3. Update ECS task definition
4. Deploy new task definition
5. Wait for health check
6. Notify Slack
```

But each service's workflow file implements this independently. When the ECR login step changed from v1 to v2, someone had to update 12 files. They missed 2. Those 2 services could not deploy for a day until someone noticed.

The fix: extract this into a **custom action** that lives in one place and is consumed everywhere.

### Action Types

```
GITHUB ACTION TYPES
════════════════════

Composite Action
  - Runs steps directly (like a reusable chunk of workflow YAML)
  - No build step required
  - Best for: orchestrating existing actions and shell commands

JavaScript Action
  - Runs Node.js code with access to @actions/core, @actions/github
  - Can interact with the GitHub API, parse outputs, handle errors
  - Best for: complex logic, API calls, conditional behavior

Docker Action
  - Runs inside a container you define
  - Best for: actions that need specific tools or OS-level dependencies
  - Slower (container pull on every run)
```

For TicketPulse's deploy-service action, we will use a **JavaScript action** because we need conditional logic (skip health check in staging), GitHub API integration (create deployment status), and clean error handling.

### The deploy-service Action

Directory structure:

```
.github/
  actions/
    deploy-service/
      action.yml
      index.js
      package.json
      node_modules/   (checked in -- required for JS actions)
```

**action.yml** -- the action's interface:

```yaml
# .github/actions/deploy-service/action.yml
name: 'Deploy Service'
description: 'Build, push, and deploy a TicketPulse service to ECS'

inputs:
  service-name:
    description: 'Name of the service (e.g., order-service)'
    required: true
  environment:
    description: 'Target environment (dev, staging, production)'
    required: true
  aws-region:
    description: 'AWS region to deploy to'
    required: true
    default: 'us-east-1'
  skip-health-check:
    description: 'Skip post-deploy health check'
    required: false
    default: 'false'
  image-tag:
    description: 'Docker image tag (defaults to SHA)'
    required: false
    default: ''

outputs:
  image-uri:
    description: 'Full ECR image URI that was deployed'
  task-definition-arn:
    description: 'ARN of the new task definition'
  deployment-id:
    description: 'ECS deployment ID'

runs:
  using: 'node20'
  main: 'index.js'
```

**index.js** -- the action's logic:

```javascript
// .github/actions/deploy-service/index.js
const core = require('@actions/core');
const exec = require('@actions/exec');
const github = require('@actions/github');

async function run() {
  try {
    const serviceName = core.getInput('service-name', { required: true });
    const environment = core.getInput('environment', { required: true });
    const awsRegion = core.getInput('aws-region');
    const skipHealthCheck = core.getInput('skip-health-check') === 'true';
    const imageTag = core.getInput('image-tag') || github.context.sha.substring(0, 8);

    const accountId = process.env.AWS_ACCOUNT_ID;
    const ecrUri = `${accountId}.dkr.ecr.${awsRegion}.amazonaws.com`;
    const imageUri = `${ecrUri}/ticketpulse-${serviceName}:${imageTag}`;

    // Step 1: Build Docker image
    core.startGroup('Building Docker image');
    await exec.exec('docker', [
      'build',
      '-t', imageUri,
      '-f', `services/${serviceName}/Dockerfile`,
      '--build-arg', `ENVIRONMENT=${environment}`,
      '--cache-from', `${ecrUri}/ticketpulse-${serviceName}:latest`,
      '.',
    ]);
    core.endGroup();

    // Step 2: Push to ECR
    core.startGroup('Pushing to ECR');
    await exec.exec('docker', ['push', imageUri]);
    // Also tag as latest for cache
    await exec.exec('docker', ['tag', imageUri,
      `${ecrUri}/ticketpulse-${serviceName}:latest`]);
    await exec.exec('docker', ['push',
      `${ecrUri}/ticketpulse-${serviceName}:latest`]);
    core.endGroup();

    // Step 3: Update ECS task definition
    core.startGroup('Updating ECS task definition');
    let taskDefOutput = '';
    await exec.exec('aws', [
      'ecs', 'describe-task-definition',
      '--task-definition', `ticketpulse-${serviceName}-${environment}`,
      '--region', awsRegion,
    ], {
      listeners: {
        stdout: (data) => { taskDefOutput += data.toString(); },
      },
    });

    const taskDef = JSON.parse(taskDefOutput).taskDefinition;
    taskDef.containerDefinitions[0].image = imageUri;

    // Remove fields that cannot be passed to register-task-definition
    delete taskDef.taskDefinitionArn;
    delete taskDef.revision;
    delete taskDef.status;
    delete taskDef.requiresAttributes;
    delete taskDef.compatibilities;
    delete taskDef.registeredAt;
    delete taskDef.registeredBy;

    const fs = require('fs');
    fs.writeFileSync('/tmp/task-def.json', JSON.stringify(taskDef));

    let registerOutput = '';
    await exec.exec('aws', [
      'ecs', 'register-task-definition',
      '--cli-input-json', 'file:///tmp/task-def.json',
      '--region', awsRegion,
    ], {
      listeners: {
        stdout: (data) => { registerOutput += data.toString(); },
      },
    });

    const newTaskDefArn = JSON.parse(registerOutput)
      .taskDefinition.taskDefinitionArn;
    core.endGroup();

    // Step 4: Deploy
    core.startGroup('Deploying to ECS');
    let deployOutput = '';
    await exec.exec('aws', [
      'ecs', 'update-service',
      '--cluster', `ticketpulse-${environment}`,
      '--service', `ticketpulse-${serviceName}`,
      '--task-definition', newTaskDefArn,
      '--region', awsRegion,
    ], {
      listeners: {
        stdout: (data) => { deployOutput += data.toString(); },
      },
    });

    const deploymentId = JSON.parse(deployOutput)
      .service.deployments[0].id;
    core.endGroup();

    // Step 5: Wait for health check
    if (!skipHealthCheck) {
      core.startGroup('Waiting for deployment to stabilize');
      await exec.exec('aws', [
        'ecs', 'wait', 'services-stable',
        '--cluster', `ticketpulse-${environment}`,
        '--services', `ticketpulse-${serviceName}`,
        '--region', awsRegion,
      ]);
      core.endGroup();
    } else {
      core.info('Skipping health check (skip-health-check=true)');
    }

    // Set outputs
    core.setOutput('image-uri', imageUri);
    core.setOutput('task-definition-arn', newTaskDefArn);
    core.setOutput('deployment-id', deploymentId);

    core.info(`Successfully deployed ${serviceName} to ${environment} in ${awsRegion}`);
  } catch (error) {
    core.setFailed(`Deploy failed: ${error.message}`);
  }
}

run();
```

### Consuming the Custom Action

Now every service workflow collapses to:

```yaml
# .github/workflows/deploy-order-service.yml
name: Deploy Order Service

on:
  push:
    branches: [main]
    paths: ['services/order-service/**']

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - uses: ./.github/actions/deploy-service
        with:
          service-name: order-service
          environment: staging
          aws-region: us-east-1
```

Twelve 200-line workflow files become twelve 30-line files. The deployment logic lives in one place. A CVE fix to the Docker build step is a single PR.

### Testing Custom Actions Locally

Use `act` to run actions locally before pushing:

```bash
# Install act
brew install act

# Run a specific workflow
act push -W .github/workflows/deploy-order-service.yml \
  --secret-file .env.ci \
  -P ubuntu-latest=catthehacker/ubuntu:act-latest

# Run with a specific event payload
act push -e test-event.json
```

Limitations of `act`: does not support all GitHub-hosted runner features, cannot test GitHub API calls that require a token, and self-hosted runner features are not available. Use it for smoke testing, not as a complete replacement for CI.

---

## Part 2: Self-Hosted Runners at Scale

### When GitHub-Hosted Runners Are Not Enough

```
WHEN TO CONSIDER SELF-HOSTED RUNNERS
══════════════════════════════════════

✅ VPC access required
   TicketPulse's integration tests hit a private RDS instance.
   GitHub-hosted runners cannot reach your VPC without a bastion
   or VPN, which adds latency and complexity.

✅ GPU workloads
   The recommendation engine (L3-M70) needs CUDA for model training
   and evaluation. GitHub-hosted runners have no GPU option.

✅ Cost at scale
   GitHub-hosted: $0.008/min (Linux). At 1,000 builds/day averaging
   10 min each: $0.008 × 10 × 1000 × 30 = $2,400/month.
   Self-hosted on reserved instances: ~$800/month for equivalent
   capacity. The break-even is around 300 builds/day.

✅ Custom hardware or software
   FPGA for hardware testing, macOS for iOS builds, specific
   OS versions for compliance testing.

❌ DO NOT self-host for:
   - Simple builds that run fine on GitHub-hosted
   - Teams without Kubernetes expertise to manage runners
   - Public repositories (CRITICAL SECURITY RISK — see below)
```

### actions-runner-controller (ARC) on Kubernetes

ARC is the standard way to run self-hosted runners on Kubernetes. It manages runner pods that scale with demand.

```yaml
# arc-values.yaml — Helm values for actions-runner-controller
# Install: helm install arc oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller

containerMode:
  type: "dind"  # Docker-in-Docker for building images

template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"

maxRunners: 20
minRunners: 2   # Keep 2 warm to avoid cold-start latency
```

### Runner Groups and Labels

TicketPulse needs different runner types for different workloads:

```yaml
# runner-scale-set for GPU workloads (recommendation engine)
apiVersion: actions.github.com/v1alpha1
kind: AutoscalingRunnerSet
metadata:
  name: ticketpulse-gpu-runners
spec:
  githubConfigUrl: "https://github.com/ticketpulse"
  githubConfigSecret: github-runner-secret
  maxRunners: 4
  minRunners: 0
  runnerGroup: "gpu"
  template:
    spec:
      nodeSelector:
        gpu: "true"
      containers:
        - name: runner
          image: ghcr.io/actions/actions-runner:latest
          resources:
            requests:
              nvidia.com/gpu: 1
            limits:
              nvidia.com/gpu: 1

---
# runner-scale-set for VPC-internal workloads (integration tests)
apiVersion: actions.github.com/v1alpha1
kind: AutoscalingRunnerSet
metadata:
  name: ticketpulse-vpc-runners
spec:
  githubConfigUrl: "https://github.com/ticketpulse"
  githubConfigSecret: github-runner-secret
  maxRunners: 10
  minRunners: 2
  runnerGroup: "vpc-internal"
  template:
    spec:
      containers:
        - name: runner
          image: ghcr.io/actions/actions-runner:latest
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
```

Consuming labeled runners in workflows:

```yaml
jobs:
  integration-tests:
    runs-on: [self-hosted, vpc-internal]
    steps:
      - run: psql $DATABASE_URL -c "SELECT 1"  # Can reach private RDS

  train-model:
    runs-on: [self-hosted, gpu]
    steps:
      - run: nvidia-smi  # GPU available
```

### Ephemeral Runners and Security

Every self-hosted runner should be **ephemeral**: it runs one job and then is destroyed. This prevents state leakage between jobs (credentials, build artifacts, malware from a compromised dependency).

ARC handles this automatically -- each job gets a fresh pod. But if you are running runners on bare metal or VMs, use the `--ephemeral` flag:

```bash
./config.sh --url https://github.com/ticketpulse \
  --token $RUNNER_TOKEN \
  --ephemeral \
  --disableupdate
```

**CRITICAL: Never use self-hosted runners on public repositories.** Anyone who can open a PR can run arbitrary code on your runner. A malicious PR could:

- Exfiltrate secrets from the runner environment
- Install a backdoor on the runner's network
- Mine cryptocurrency on your hardware
- Pivot to other systems on your network

This is not theoretical. It has happened. Public repos must use GitHub-hosted runners exclusively.

### Cost Analysis

```
COST COMPARISON: 1,000 BUILDS/DAY, 10 MIN AVG
═══════════════════════════════════════════════

GitHub-Hosted (Linux, 4-core):
  Per-minute cost:     $0.008
  Daily minutes:       10,000
  Monthly cost:        $2,400
  Includes:            Maintenance, updates, security

Self-Hosted (ARC on EKS, c5.2xlarge reserved):
  EC2 cost (4 nodes):  $600/mo (1yr reserved)
  EKS cluster:         $73/mo
  EBS storage:         $50/mo
  Engineer time:       ~4 hrs/mo × $100/hr = $400/mo
  Monthly cost:        $1,123
  Does NOT include:    Setup time (~40 hrs), incident response

Break-even:            ~300 builds/day
Below 300/day:         GitHub-hosted is cheaper (total cost of ownership)
Above 300/day:         Self-hosted saves money IF you have K8s expertise
```

---

## Part 3: Deployment Environments and Protection Rules

### TicketPulse's Deployment Pipeline

```
commit → lint/test → build → staging → smoke test → prod-us → prod-eu → prod-ap
                                                      ↑
                                               required review
                                               + wait timer
```

### GitHub Environments Configuration

Configure environments in GitHub: Settings → Environments.

```
ENVIRONMENT CONFIGURATION
═════════════════════════

staging:
  Protection rules: none (auto-deploy on merge to main)
  Secrets: AWS_ROLE_ARN (staging account), DATABASE_URL (staging)
  Variables: LOG_LEVEL=debug, FEATURE_FLAGS=all-enabled

production-us:
  Protection rules:
    - Required reviewers: 2 (from @ticketpulse/platform-team)
    - Wait timer: 0 minutes
    - Branch policy: main only
  Secrets: AWS_ROLE_ARN (prod-us account), DATABASE_URL (prod-us)
  Variables: LOG_LEVEL=warn, AWS_REGION=us-east-1

production-eu:
  Protection rules:
    - Required reviewers: 0 (auto-approve after prod-us succeeds)
    - Wait timer: 15 minutes (observe prod-us for errors)
    - Branch policy: main only
  Secrets: AWS_ROLE_ARN (prod-eu account), DATABASE_URL (prod-eu)
  Variables: LOG_LEVEL=warn, AWS_REGION=eu-west-1

production-ap:
  Protection rules:
    - Required reviewers: 0
    - Wait timer: 15 minutes (observe prod-eu for errors)
    - Branch policy: main only
  Secrets: AWS_ROLE_ARN (prod-ap account), DATABASE_URL (prod-ap)
  Variables: LOG_LEVEL=warn, AWS_REGION=ap-southeast-1
```

### Complete Multi-Region Deployment Workflow

```yaml
# .github/workflows/deploy-production.yml
name: Production Deployment Pipeline

on:
  push:
    branches: [main]

concurrency:
  group: production-deploy
  cancel-in-progress: false  # Never cancel an in-progress production deploy

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test -- --coverage

  build:
    needs: lint-and-test
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ticketpulse
          tags: type=sha,prefix=

      # Build and push all changed service images
      - uses: ./.github/actions/detect-changed-services
        id: changes
      - run: |
          for service in ${{ steps.changes.outputs.services }}; do
            docker build -t $ECR_URI/$service:${{ steps.meta.outputs.version }} \
              -f services/$service/Dockerfile .
            docker push $ECR_URI/$service:${{ steps.meta.outputs.version }}
          done

  deploy-staging:
    needs: build
    runs-on: [self-hosted, vpc-internal]
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/deploy-service
        with:
          service-name: ${{ needs.build.outputs.changed-services }}
          environment: staging
          image-tag: ${{ needs.build.outputs.image-tag }}

  smoke-test-staging:
    needs: deploy-staging
    runs-on: [self-hosted, vpc-internal]
    steps:
      - uses: actions/checkout@v4
      - run: |
          npm run test:smoke -- --env=staging
          # Hit critical paths: create event, purchase ticket, process payment
          # Verify: HTTP 200, response time < 500ms, no error logs

  # Production: US East (primary region, requires human approval)
  deploy-prod-us:
    needs: smoke-test-staging
    runs-on: [self-hosted, vpc-internal]
    environment: production-us
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/deploy-service
        with:
          service-name: ${{ needs.build.outputs.changed-services }}
          environment: production
          aws-region: us-east-1
          image-tag: ${{ needs.build.outputs.image-tag }}
      - uses: ./.github/actions/verify-deployment
        with:
          region: us-east-1
          canary-checks: 'true'

  # Production: EU West (auto-approve after prod-us, 15 min wait)
  deploy-prod-eu:
    needs: deploy-prod-us
    runs-on: [self-hosted, vpc-internal]
    environment: production-eu
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/deploy-service
        with:
          service-name: ${{ needs.build.outputs.changed-services }}
          environment: production
          aws-region: eu-west-1
          image-tag: ${{ needs.build.outputs.image-tag }}
      - uses: ./.github/actions/verify-deployment
        with:
          region: eu-west-1
          canary-checks: 'true'

  # Production: AP Southeast (auto-approve after prod-eu, 15 min wait)
  deploy-prod-ap:
    needs: deploy-prod-eu
    runs-on: [self-hosted, vpc-internal]
    environment: production-ap
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/deploy-service
        with:
          service-name: ${{ needs.build.outputs.changed-services }}
          environment: production
          aws-region: ap-southeast-1
          image-tag: ${{ needs.build.outputs.image-tag }}
      - uses: ./.github/actions/verify-deployment
        with:
          region: ap-southeast-1
          canary-checks: 'true'

  notify:
    needs: [deploy-prod-us, deploy-prod-eu, deploy-prod-ap]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "Deploy ${{ needs.build.outputs.image-tag }}: US=${{ needs.deploy-prod-us.result }}, EU=${{ needs.deploy-prod-eu.result }}, AP=${{ needs.deploy-prod-ap.result }}"
            }
```

The key design decisions:

- **`concurrency: cancel-in-progress: false`** -- never cancel a production deploy mid-flight. A half-deployed state is worse than waiting.
- **Sequential region rollout** -- if prod-us has errors, prod-eu and prod-ap never start. The blast radius is one region.
- **Environment-scoped secrets** -- the production-us job cannot access production-eu credentials. AWS account isolation is enforced by GitHub, not by convention.
- **Wait timers between regions** -- 15 minutes gives you time to observe error rates and roll back before the next region starts.

---

## Part 4: Cross-Repository Workflows

### The Multi-Repo Challenge

At scale, TicketPulse's code lives across multiple repositories:

```
TICKETPULSE REPOSITORY STRUCTURE
═════════════════════════════════

ticketpulse/platform-services     Main application services
ticketpulse/infrastructure        Terraform for AWS resources
ticketpulse/shared-libraries      @ticketpulse/sdk, @ticketpulse/types
ticketpulse/ml-models             Recommendation engine training
ticketpulse/deploy-configs        Kubernetes manifests, Helm charts
ticketpulse/.github               Shared workflows and actions
```

When shared-libraries publishes a new version, platform-services needs to update and rebuild. When infrastructure changes a database schema, services need integration tests rerun. These cross-repo dependencies need automated triggers.

### Repository Dispatch

Trigger a workflow in another repository when something happens:

```yaml
# In shared-libraries: .github/workflows/publish.yml
name: Publish Shared Libraries

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build && npm publish

      # Trigger downstream repos to test with the new version
      - uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.CROSS_REPO_PAT }}
          repository: ticketpulse/platform-services
          event-type: dependency-updated
          client-payload: |
            {
              "package": "@ticketpulse/sdk",
              "version": "${{ github.ref_name }}",
              "sha": "${{ github.sha }}"
            }
```

```yaml
# In platform-services: .github/workflows/on-dependency-update.yml
name: Test Dependency Update

on:
  repository_dispatch:
    types: [dependency-updated]

jobs:
  update-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          npm install ${{ github.event.client_payload.package }}@${{ github.event.client_payload.version }}
          npm test
      - if: success()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add package.json package-lock.json
          git commit -m "chore: update ${{ github.event.client_payload.package }} to ${{ github.event.client_payload.version }}"
          git push
```

### Workflow Dispatch with Custom Inputs

Enable manual deployments with parameters -- deploy any version to any region:

```yaml
# .github/workflows/manual-deploy.yml
name: Manual Deployment

on:
  workflow_dispatch:
    inputs:
      service:
        description: 'Service to deploy'
        required: true
        type: choice
        options:
          - order-service
          - event-service
          - payment-service
          - recommendation-engine
          - all
      region:
        description: 'Target region'
        required: true
        type: choice
        options:
          - us-east-1
          - eu-west-1
          - ap-southeast-1
          - all-regions
      image-tag:
        description: 'Image tag to deploy (e.g., abc1234f)'
        required: true
        type: string
      skip-approval:
        description: 'Skip manual approval (emergency only)'
        required: false
        type: boolean
        default: false

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Verify image exists
        run: |
          aws ecr describe-images \
            --repository-name ticketpulse-${{ inputs.service }} \
            --image-ids imageTag=${{ inputs.image-tag }} \
            --region us-east-1
          echo "Image verified: ${{ inputs.image-tag }}"

  deploy:
    needs: validate
    runs-on: [self-hosted, vpc-internal]
    environment: ${{ inputs.skip-approval && 'staging' || 'production-us' }}
    strategy:
      matrix:
        region: ${{ inputs.region == 'all-regions' && fromJson('["us-east-1","eu-west-1","ap-southeast-1"]') || fromJson(format('["{0}"]', inputs.region)) }}
      max-parallel: 1  # Deploy one region at a time
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/deploy-service
        with:
          service-name: ${{ inputs.service }}
          environment: production
          aws-region: ${{ matrix.region }}
          image-tag: ${{ inputs.image-tag }}
```

### Shared Workflow Repository

The most powerful pattern: a **shared workflow repository** that all repos reference. Place reusable workflows in `ticketpulse/.github`:

```yaml
# ticketpulse/.github/.github/workflows/reusable-deploy.yml
name: Reusable Deploy Pipeline

on:
  workflow_call:
    inputs:
      service-name:
        required: true
        type: string
      dockerfile-path:
        required: false
        type: string
        default: 'Dockerfile'
    secrets:
      AWS_ROLE_ARN:
        required: true

jobs:
  build-and-deploy:
    runs-on: [self-hosted, vpc-internal]
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1
      # ... full deploy pipeline
```

Consuming from any repo:

```yaml
# In any service repo
jobs:
  deploy:
    uses: ticketpulse/.github/.github/workflows/reusable-deploy.yml@main
    with:
      service-name: order-service
    secrets:
      AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}
```

One workflow definition. Twelve repos consuming it. A fix in one place propagates everywhere.

---

## Part 5: CI/CD Observability

### What to Measure

You cannot improve what you do not measure. CI/CD has the same observability needs as production systems.

```
CI/CD HEALTH METRICS
════════════════════

1. BUILD DURATION (p50, p95)
   Current:  p50 = 8 min, p95 = 22 min
   Target:   p50 < 5 min, p95 < 12 min
   Alert:    p95 > 20 min for 1 hour

2. QUEUE WAIT TIME
   Time from "workflow triggered" to "runner picks up job."
   Current:  p50 = 15s, p95 = 3 min
   Target:   p50 < 10s, p95 < 1 min
   Alert:    p95 > 5 min (scale up runners)

3. FLAKY TEST RATE
   Tests that pass on retry without code change.
   Current:  2.3% of test runs contain a flaky failure
   Target:   < 0.5%
   Alert:    > 3% over 24 hours

4. DEPLOYMENT FREQUENCY
   How often you deploy to production.
   Current:  4 deploys/day
   Target:   on every merge to main (continuous deployment)

5. CHANGE FAILURE RATE
   Percentage of deployments that cause a rollback or hotfix.
   Current:  8%
   Target:   < 5%
```

### Extracting CI Metrics via the GitHub API

```javascript
// scripts/ci-metrics.js
// Collect workflow run data for the past 7 days

const { Octokit } = require('@octokit/rest');
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

async function collectMetrics(owner, repo, days = 7) {
  const since = new Date(Date.now() - days * 86400000).toISOString();

  // Get all workflow runs
  const runs = await octokit.paginate(
    octokit.actions.listWorkflowRunsForRepo,
    { owner, repo, created: `>=${since}`, per_page: 100 }
  );

  const metrics = {
    totalRuns: runs.length,
    successRate: 0,
    durations: [],
    queueTimes: [],
    failuresByWorkflow: {},
  };

  for (const run of runs) {
    if (run.conclusion === 'success' || run.conclusion === 'failure') {
      const created = new Date(run.created_at);
      const started = new Date(run.run_started_at);
      const updated = new Date(run.updated_at);

      const queueTime = (started - created) / 1000;  // seconds
      const duration = (updated - started) / 1000;    // seconds

      metrics.durations.push(duration);
      metrics.queueTimes.push(queueTime);

      if (run.conclusion === 'failure') {
        const wf = run.name;
        metrics.failuresByWorkflow[wf] = (metrics.failuresByWorkflow[wf] || 0) + 1;
      }
    }
  }

  const successes = runs.filter(r => r.conclusion === 'success').length;
  const completed = runs.filter(r =>
    r.conclusion === 'success' || r.conclusion === 'failure'
  ).length;

  metrics.successRate = completed > 0
    ? ((successes / completed) * 100).toFixed(1)
    : 'N/A';

  metrics.p50Duration = percentile(metrics.durations, 50);
  metrics.p95Duration = percentile(metrics.durations, 95);
  metrics.p50QueueTime = percentile(metrics.queueTimes, 50);
  metrics.p95QueueTime = percentile(metrics.queueTimes, 95);

  return metrics;
}

function percentile(arr, p) {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[idx];
}

// Usage
collectMetrics('ticketpulse', 'platform-services').then(m => {
  console.log(`Success rate:     ${m.successRate}%`);
  console.log(`Build p50:        ${(m.p50Duration / 60).toFixed(1)} min`);
  console.log(`Build p95:        ${(m.p95Duration / 60).toFixed(1)} min`);
  console.log(`Queue p50:        ${m.p50QueueTime.toFixed(0)}s`);
  console.log(`Queue p95:        ${m.p95QueueTime.toFixed(0)}s`);
  console.log(`Failures:`, m.failuresByWorkflow);
});
```

### The DORA Metrics Connection

CI/CD observability feeds directly into the four DORA metrics (covered in depth in L3-M78):

```
DORA METRIC              CI/CD SIGNAL
═══════════════════════════════════════════════════════════
Deployment Frequency     Count of successful production deploys
                         → GitHub API: workflow runs with
                           environment=production, conclusion=success

Lead Time for Changes    Time from commit to production deploy
                         → commit.created_at → deployment.completed_at
                         TicketPulse target: < 1 hour

Change Failure Rate      Deploys followed by rollback or hotfix
                         → Track: did a deploy to prod get followed
                           by another deploy within 30 min?
                         TicketPulse target: < 5%

Mean Time to Recovery    Time from failure detection to fix deployed
                         → Alert fired → next successful deploy
                         TicketPulse target: < 30 minutes
```

The teams that track these metrics improve. The teams that do not track them do not know they are getting worse. Google's State of DevOps reports have shown this correlation for 10 consecutive years.

---

## Design Exercise: TicketPulse CI/CD at Scale (25 min)

Design the complete CI/CD pipeline for TicketPulse. Your design should handle 12 services, 3 regions, 25 engineers, and 300+ builds/day.

### Step 1: Draw the Pipeline

Complete this ASCII diagram with the missing details:

```
TICKETPULSE CI/CD PIPELINE
═══════════════════════════

Developer pushes to main
        │
        ▼
┌─────────────────┐
│   Detect Changes │ ← Which services changed? (path filters)
│   (< 30s)       │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ Lint   │ │ Type   │  ← Parallel. Fail fast.
│        │ │ Check  │
└───┬────┘ └───┬────┘
    └────┬─────┘
         ▼
┌─────────────────┐
│   Unit Tests    │ ← Matrix: run per changed service
│   (3-5 min)     │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Docker Build   │ ← Custom action. Push to ECR.
│  + Push to ECR  │   Cache layers from previous build.
│  (2-3 min)      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Deploy Staging  │ ← VPC runner. Auto-approve.
│ + Smoke Tests   │   Full integration test suite.
│ (5-8 min)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Deploy prod-us  │ ← 🔒 2 reviewers required
│ + Canary Check  │   Verify error rate < 0.1%
│ (5-10 min)      │
└────────┬────────┘
         │ 15 min wait + auto-approve
         ▼
┌─────────────────┐
│ Deploy prod-eu  │ ← Auto if prod-us healthy
│ + Canary Check  │
│ (5-10 min)      │
└────────┬────────┘
         │ 15 min wait + auto-approve
         ▼
┌─────────────────┐
│ Deploy prod-ap  │ ← Auto if prod-eu healthy
│ + Canary Check  │
│ (5-10 min)      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Notify + Record │ ← Slack, deployment log, DORA metrics
│                 │
└─────────────────┘

Total: commit → all regions: ~60-90 min
       (most of that is wait timers, not build time)
```

### Step 2: Answer These Design Questions

1. A deploy to prod-us succeeds but canary checks show elevated 5xx errors. prod-eu has not started yet. What is your automated response? What is the manual escalation path?

2. An engineer needs to deploy an emergency hotfix to prod-eu only (a region-specific bug). How does the pipeline support this without deploying to all regions?

3. The recommendation engine needs GPU runners for CI but only runs 10 builds/day. Do you self-host GPU runners or use a different approach?

4. Two engineers merge to main within 5 minutes of each other. Both trigger the pipeline. How do you prevent them from clobbering each other's deployments?

---

## Final Reflections

1. **At what team size does investing in custom actions pay for itself?** Consider the cost of building and maintaining the action versus the cost of copy-paste drift across N workflow files. Is the threshold 3 services? 5? 10?

2. **How would you handle a failed deployment to us-east-1 that succeeded in eu-west-1?** This is a real scenario: you have two regions running different versions. Users routed to one region see the bug, users routed to the other do not. What is the correct sequence of actions?

3. **What CI/CD metrics would you put on your team's engineering dashboard?** You have room for 5 numbers. The team sees them every morning. Which 5 tell you the most about engineering health?

4. **Why is CI/CD observability often neglected?** The pipeline is not "the product" -- it is the thing that ships the product. How do you justify investment in CI health to stakeholders who only care about feature delivery?

5. **Self-hosted runners introduce operational burden.** You now have infrastructure that must be patched, monitored, and scaled. At what point does that burden outweigh the cost savings? What is the minimum team size that should manage self-hosted runners?

---

## Checkpoint: What You Built

- [ ] Custom `deploy-service` action created with inputs, outputs, and error handling
- [ ] Understand self-hosted runner architecture: ARC, runner groups, ephemeral mode, and the security implications
- [ ] Multi-environment deployment pipeline with protection rules, required reviewers, and regional wait timers
- [ ] Cross-repository workflow triggering with repository dispatch and reusable workflows
- [ ] CI/CD observability: can name and measure at least 3 health metrics and connect them to DORA

**Key insight**: CI/CD at scale is not about writing more YAML. It is about building a deployment platform -- with the same rigor you apply to production systems. Custom actions are your libraries. Runners are your compute. Environments are your safety nets. Observability is your feedback loop.

---

**Next module**: L3-M81 -- Durable Execution, where we make TicketPulse's multi-step processes survive crashes by persisting workflow state.

## Key Terms

| Term | Definition |
|------|-----------|
| **Custom action** | A reusable unit of CI/CD logic packaged as a JavaScript, composite, or Docker action, consumed via `uses:` in workflows. |
| **Self-hosted runner** | A machine you manage that executes GitHub Actions jobs, providing VPC access, GPU support, or cost savings at scale. |
| **ARC** | Actions Runner Controller; a Kubernetes operator that manages self-hosted GitHub Actions runners as pods. |
| **Ephemeral runner** | A runner that processes exactly one job and is then destroyed, preventing state leakage between builds. |
| **Deployment environment** | A GitHub feature that associates jobs with named environments (staging, production) and enforces protection rules. |
| **Protection rules** | Constraints on a GitHub environment: required reviewers, wait timers, branch restrictions. |
| **Repository dispatch** | A GitHub event that allows one repository to trigger workflows in another repository via the API. |
| **Reusable workflow** | A workflow defined with `workflow_call` that can be invoked from other workflows, even across repositories. |
| **DORA metrics** | Four metrics (deployment frequency, lead time, change failure rate, MTTR) that measure software delivery performance. |

### 🤔 Reflection Prompt

After building reusable actions and cross-repo workflows, what was the biggest time savings you identified? How does centralizing CI/CD logic change the operational burden as you add new services?

## Further Reading

- **Chapter 33**: CI/CD at Scale -- the full theoretical foundation for this module
- **L3-M78**: DORA Metrics & Team Performance -- deep dive on measuring engineering effectiveness
- **GitHub Docs: Creating Actions**: docs.github.com/en/actions/creating-actions
- **actions-runner-controller**: github.com/actions/actions-runner-controller -- the official ARC project
- **"Accelerate" by Nicole Forsgren, Jez Humble, Gene Kim**: the research behind DORA metrics and high-performing teams
- **GitHub Blog: "How we use GitHub Actions at GitHub"**: engineering.github.com -- lessons from running Actions at massive scale
- **Shopify Engineering: "CI at Scale"**: how Shopify manages 40,000+ CI minutes/day with custom tooling
---

## What's Next

In **Durable Execution** (L3-M81), you'll build on what you learned here and take it further.

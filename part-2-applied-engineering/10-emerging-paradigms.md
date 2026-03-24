<!--
  CHAPTER: 10
  TITLE: Emerging & Advanced Engineering Paradigms
  PART: II — Applied Engineering
  PREREQS: Chapters 1-4
  KEY_TOPICS: AI-native engineering, RAG, agents, edge computing, real-time systems, CRDTs, durable execution, stream processing, FinOps, WebAssembly
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 10: Emerging & Advanced Engineering Paradigms

> **Part II — Applied Engineering** | Prerequisites: Chapters 1-4 (broad foundation) | Difficulty: Advanced

The frontier — emerging paradigms that are reshaping backend engineering in 2025-2026, from AI-native architectures to edge computing to WebAssembly on the server.

### In This Chapter
- AI-Native Engineering
- Edge Computing
- Real-Time Systems
- Modern Backend Patterns
- Data-Intensive Applications
- Sustainability & Efficiency
- WebAssembly & Portable Computing
- Mobile Backend Patterns
- ML Infrastructure for Backend Engineers
- Cross-Cutting Themes

### Related Chapters
- Chapter 14 (AI workflows in practice)
- Chapter 13 (cloud integration)
- Chapter 1 (distributed systems theory behind edge/real-time)

---

## 1. AI-NATIVE ENGINEERING

### LLM Integration Patterns

**RAG (Retrieval-Augmented Generation):** Ingest → chunk (256-1024 tokens with overlap) → embed → store in vector DB → at query time retrieve top-k → inject into prompt.
- Always try RAG before fine-tuning. RAG is for *what* the model knows; fine-tuning is for *how* it responds.
- **Hybrid search** (vector + BM25 keyword) with re-ranking is current best practice.

**Fine-tuning:** Adjust model weights on domain data. LoRA/QLoRA make it feasible. Use for consistent tone/format or domain-specific reasoning.

**Prompt Engineering:** Few-shot examples, chain-of-thought, system prompts, structured output (JSON mode, function calling).

### AI Agent Architectures
- **ReAct:** Observe → reason → act → observe. Simple, effective for tool use.
- **Plan-and-Execute:** Create plan first, then execute steps. Better for complex tasks.
- **Multi-Agent:** Orchestrator-worker, debate/critique, pipeline.
- **Trade-offs:** Non-deterministic, 5-15 LLM calls per request, novel failure modes (infinite loops, hallucinated tool calls). Always set max-iteration limits.

### AI Gateway Patterns
Sits between app and LLM providers. Rate limiting, fallback routing, semantic caching (30-60% cost reduction), observability, guardrails (PII redaction, content filtering).

### Vector Databases
Pinecone (managed), Weaviate, Qdrant, pgvector (use if you already have Postgres).
HNSW index is most common. pgvector is "good enough" for <10M vectors.

### AI Observability
Track: token usage/cost, latency breakdown, quality metrics (user feedback, LLM-as-judge evals), drift detection.
Tools: LangSmith, Langfuse, Arize Phoenix, Helicone.

---

## 2. EDGE COMPUTING

### Architecture Tiers
CDN edge (static/cached) → Edge compute (dynamic logic) → Regional compute (heavier workloads) → Origin (centralized DB).

### Edge Databases
- **Read replicas at edge:** Turso, Neon, PlanetScale. Writes → primary; reads → local.
- **CRDTs / eventual consistency:** Durable Objects, Electric SQL. Writes at any edge.
- **Edge caching + origin DB:** Simplest model for read-heavy workloads.

### Patterns
- **Stale-while-revalidate:** Serve cached immediately, refresh in background.
- **Edge-side personalization:** Cache page shell, inject user-specific content at edge.
- **Edge middleware:** Auth, bot detection, feature flags before reaching origin.

---

## 3. REAL-TIME SYSTEMS

### Transport Mechanisms
- **WebSockets:** Full-duplex, persistent TCP. High-frequency bidirectional (chat, games). Stateful, complicates horizontal scaling.
- **SSE (Server-Sent Events):** Unidirectional (server→client) over HTTP. Simpler. Auto-reconnects. Best for feeds, notifications, LLM streaming. **Use SSE unless you need client→server streaming.**
- **WebRTC:** Peer-to-peer, sub-100ms. For video calls, screen sharing.

### Collaborative Editing
- **OT (Operational Transformation):** Transforms concurrent operations. Requires central server. Used by Google Docs.
- **CRDTs:** Mathematically guaranteed convergence without coordination. Works offline/P2P. Libraries: Yjs, Automerge.

### Presence Systems
Heartbeat-based detection + fast ephemeral store (Redis) + pub/sub broadcast.

---

## 4. MODERN BACKEND PATTERNS

### Durable Execution (Temporal, Restate, Inngest)
Persists function execution state. Survives crashes, deployments, restarts. Looks like normal sequential code.
**Use for:** Multi-step processes, wait-then-do patterns, saga orchestration.
**Trade-off:** Workflow code must be deterministic. Side effects only through activities.

### Cell-Based Architecture
Independent, self-contained instances serving subsets of users. Failure isolated per cell.
**Real-world:** Slack (per-workspace cells), AWS internal services.

### Multi-Tenancy Patterns
1. **Shared everything** (tenant_id column) — cheapest, simplest
2. **Shared DB, separate schemas** — better isolation
3. **Separate databases** — full isolation, most expensive
4. **Hybrid** — small tenants share, large get dedicated

---

## 5. DATA-INTENSIVE APPLICATIONS

### Stream Processing
Kafka (backbone) + Kafka Streams (embedded, simple) or Flink (dedicated cluster, powerful).

### Time-Series Optimization
Columnar storage, downsampling/rollups, partitioning by time. TimescaleDB, ClickHouse.

### Full-Text Search
Inverted index + BM25 ranking. **Hybrid search** (BM25 + vector) is current best practice.
Tools: Elasticsearch, Meilisearch, Postgres tsvector + pgvector.

### Analytics Engineering (dbt)
SQL transforms in git, modular DAG, built-in testing, generated docs.
Layering: staging → intermediate → marts.

---

## 6. SUSTAINABILITY & EFFICIENCY

### Green Software Engineering
Use less energy, use it efficiently, use lower-carbon energy. Schedule flexible workloads when/where grid is cleanest.

### FinOps
Right-sizing (most instances over-provisioned), spot instances (60-90% discount), reserved capacity (30-60% discount), storage tiering, kill zombie resources.

### Resource Efficiency Metrics
Cost per request, cost per active user, cloud spend as % of revenue.

---

## 7. WEBASSEMBLY & PORTABLE COMPUTING

### Wasm on the Server
Portable, sandboxed, near-native-speed execution. WASI gives filesystem/network access via capability-based security.

### Component Model
Language-agnostic interfaces (WIT), composable modules, per-component sandboxing. Define in WIT, implement in Rust, consume from Python.

### Use Cases
Edge computing, plugin systems (Shopify, Envoy, Figma), embedded DB functions, polyglot microservices.
**Trade-off:** Ecosystem still maturing. Not for heavy threading/GPU. Near-native for compute; I/O less clear.

---

## 8. MOBILE BACKEND PATTERNS

### Push Notifications
- APNs (Apple Push Notification service) and FCM (Firebase Cloud Messaging) architecture
- Device token registration flow: app registers with OS → sends token to your server → server stores token → sends push via APNs/FCM
- Notification payload design (title, body, data payload, badge count, sound, category/actions)
- Silent/background notifications (wake the app to fetch data without showing a notification)
- Topic-based vs device-based targeting
- Delivery reliability: push is best-effort, NOT guaranteed. Always have a fallback (in-app inbox).
- Common problems: stale tokens (devices uninstall), rate limiting, payload size limits (4KB APNs, 4KB FCM)

### Offline-First & Data Sync
- Offline-first principle: the app works without network, syncs when connectivity returns
- Conflict resolution strategies: last-write-wins (simple), merge (complex), user-chooses (interactive)
- CRDTs for automatic merge (see Ch 1)
- Sync protocols: Firebase Realtime DB (automatic), custom (version vectors + delta sync)
- Optimistic UI: show the change immediately, sync in background, rollback on conflict
- Queue local mutations: store writes locally, replay when online (outbox pattern on mobile)

### API Design for Mobile
- Minimize round trips: batch endpoints, GraphQL, BFF (Backend for Frontend)
- Payload optimization: only return needed fields, compress responses (gzip/brotli)
- Image optimization: serve different sizes per device (srcset equivalent for APIs), WebP/AVIF
- Pagination: cursor-based (works with offline cache), not offset-based
- Versioning: mobile apps can't be force-updated instantly — support older API versions longer
- Deep linking: universal links (iOS), app links (Android), deferred deep links for install attribution

### Real-Time Features for Mobile
- WebSocket vs SSE vs long-polling on mobile (battery and data considerations)
- Presence systems: heartbeat-based, handle mobile app backgrounding
- Typing indicators, read receipts, live location sharing
- Battery optimization: reduce polling frequency when app is backgrounded, use push for wakeup

---

## 9. ML INFRASTRUCTURE FOR BACKEND ENGINEERS

### What Backend Engineers Need to Know
- You don't need to train models — but you need to serve, monitor, and scale them
- ML is a data problem before it's a model problem

### Feature Stores
- What they are: a centralized repository for ML features (computed values used as model inputs)
- Online store (low-latency serving for real-time inference) vs offline store (batch for training)
- Tools: Feast (open source), Tecton, SageMaker Feature Store
- Example: user features (avg order value, days since last login, total orders) stored once, used by multiple models

### Model Serving
- Batch inference: run model on a schedule, store predictions (simplest, good for recommendations)
- Real-time inference: model behind an API, responds per-request (needed for search ranking, fraud detection)
- Serving patterns: model-as-a-service (dedicated endpoint), model-in-application (embedded), sidecar model
- Tools: TensorFlow Serving, TorchServe, Triton, SageMaker Endpoints, BentoML
- GPU vs CPU inference: GPUs for large models (LLMs, image), CPU fine for small models (XGBoost, linear)
- Model versioning and A/B testing (canary rollout for models, shadow scoring)

### A/B Testing & Experimentation Platforms
- Experimentation as infrastructure (not ad-hoc)
- Components: randomization (hash user ID to assign variant), feature flags (control/treatment), metrics pipeline, statistical analysis
- Sample size and duration: don't peek early, use power analysis to determine required sample
- Guardrail metrics: metrics that must NOT degrade (latency, error rate, revenue)
- Tools: Statsig, LaunchDarkly, Eppo, Optimizely, GrowthBook (open source), custom on Kafka+ClickHouse
- Common mistakes: peeking at results too early, insufficient sample size, testing too many things at once, not accounting for novelty effect

### ML Pipelines
- Training pipelines: data extraction → feature engineering → training → evaluation → model registry
- Tools: Airflow, Kubeflow, MLflow, Metaflow, SageMaker Pipelines
- Model registry: version models, track lineage, promote to production
- Data versioning: DVC (Data Version Control) — git for data
- Reproducibility: pin data version + code version + environment = reproducible model

---

## Cross-Cutting Themes

1. **Composition over invention** — compose proven primitives
2. **Shift complexity to platforms** — your advantage is in business logic
3. **Observability is non-negotiable** — every new paradigm makes systems harder to reason about
4. **Design for the cost profile** — model cost at 10x traffic before committing
5. **Embrace the boring option** — Postgres with pgvector + tsvector + JSONB + RLS can replace 4-5 specialized databases

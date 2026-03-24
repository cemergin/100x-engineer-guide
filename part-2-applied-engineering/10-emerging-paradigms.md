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

## Cross-Cutting Themes

1. **Composition over invention** — compose proven primitives
2. **Shift complexity to platforms** — your advantage is in business logic
3. **Observability is non-negotiable** — every new paradigm makes systems harder to reason about
4. **Design for the cost profile** — model cost at 10x traffic before committing
5. **Embrace the boring option** — Postgres with pgvector + tsvector + JSONB + RLS can replace 4-5 specialized databases

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

### Evals: Your AI Test Suite

Traditional software is deterministic: same input → same output → unit tests work. LLM outputs are non-deterministic: same input → different output each time. You need **statistical testing** — evals.

**Why evals matter:**
- You cannot eyeball quality at scale. Manual spot-checking breaks at 100+ use cases.
- Evals catch regressions when you change prompts, swap models, or update retrieval logic.
- Without evals, every deploy is a guess. With evals, you have a confidence score.

**Golden datasets:** Curated sets of input/expected-output pairs that represent your use cases.
- Start small (50-100 examples), grow over time.
- Include edge cases, adversarial inputs, and domain-specific examples.
- Version them in git alongside your code.
- Sources: hand-crafted by domain experts, sampled from production logs, generated synthetically then human-verified.

**Automated scorers:**
- **Exact match:** Output must equal expected. Good for classification, structured extraction.
- **Fuzzy match:** Levenshtein distance, token overlap. Good for near-exact answers.
- **LLM-as-judge:** Use a strong model (GPT-4, Claude) to grade a weaker model's output against criteria. Surprisingly effective. Define rubrics explicitly.
- **Semantic similarity:** Embed both expected and actual output, compute cosine similarity. Good for open-ended generation where wording varies.
- **Custom scorers:** Domain-specific checks (e.g., "output contains valid SQL", "response includes citation", "no PII leaked").

**Eval suites in CI:**
- Run evals on every PR that touches prompts, retrieval, or model config.
- Set pass/fail thresholds (e.g., "accuracy must stay above 85%").
- Track scores over time — plot trends, catch gradual degradation.
- Fast evals (~50 examples) in CI, full suite (~500+) nightly.

**Example eval structure (YAML):**
```yaml
# evals/summarization.yaml
suite: summarization
model: gpt-4o
scorer: llm-as-judge
threshold: 0.85
cases:
  - input: "Summarize this 2000-word article about climate policy..."
    expected: "The article argues for carbon pricing as the most effective..."
    rubric: "Must mention carbon pricing, include key statistics, be under 100 words"
  - input: "Summarize this earnings call transcript..."
    expected: "Revenue grew 15% YoY driven by cloud services..."
    rubric: "Must include revenue figure, growth driver, and forward guidance"
```

**Key principle:** Evals are not a one-time setup. They are a living suite that grows with your product. Every bug report is a candidate for a new eval case.

### Context Engineering

Context engineering is the practice of curating exactly the right tokens for the model at inference time. If prompt engineering is *what you say*, context engineering is *what you include*.

**Why it matters:**
- Models have finite context windows (4K-2M tokens). Every token counts.
- Stuffing irrelevant context degrades output quality — models get confused by noise.
- The right 2K tokens of context beats 100K tokens of everything.

**Context window budget:**
```
System prompt          ~500-2000 tokens
Few-shot examples      ~500-1500 tokens
Retrieved documents    ~2000-8000 tokens (the dynamic part)
User input             ~100-2000 tokens
Tool results           ~500-4000 tokens
Reserved for output    ~1000-4000 tokens
─────────────────────────────────────
Total must fit within model's context window
```

**Strategies for managing context:**
- **Summarization:** Compress long documents before injecting. Use a smaller/cheaper model to summarize, then feed summaries to the main model.
- **Sliding window:** For conversations, keep recent messages in full, summarize older ones.
- **Priority ranking:** Score each context chunk by relevance, include top-N until budget is filled.
- **Token counting:** Always count tokens before sending. Libraries: `tiktoken` (OpenAI), model-specific tokenizers. Never guess — measure.
- **Metadata injection:** Instead of full documents, inject titles + summaries + key facts.

**Prompt engineering vs context engineering:**
| Prompt Engineering | Context Engineering |
|---|---|
| How you phrase the instruction | What information you include |
| System prompt wording | Which documents get retrieved |
| Few-shot example selection | How context is compressed/ranked |
| Output format specification | Token budget allocation |
| Static (changes with deploys) | Dynamic (changes per request) |

**Practical tip:** Build a context assembly pipeline — a function that takes a user query and returns the fully assembled prompt with all context, respecting token limits. Test this pipeline independently from the model.

### Advanced RAG Patterns

Basic RAG (retrieve → stuff into prompt → generate) works for simple cases. Production RAG needs more.

**Naive RAG vs Advanced RAG:**
- **Naive RAG:** Embed query → vector search → top-k chunks → prompt → answer. Breaks on complex queries, poor chunks, or ambiguous intent.
- **Advanced RAG:** Query transformation → hybrid retrieval → re-ranking → prompt assembly → answer → citation verification.

**Chunking strategies (garbage in, garbage out):**
- **Fixed-size:** Split every N tokens with overlap. Simple but splits mid-sentence/mid-thought.
- **Recursive/character:** Split on paragraphs, then sentences, then words. Respects natural boundaries.
- **Semantic chunking:** Embed consecutive sentences, split where similarity drops. Produces coherent chunks.
- **Document-aware:** Use document structure (headings, sections, tables) to create meaningful chunks. A table should never be split across chunks.
- **Parent-child:** Store small chunks for retrieval precision, but return the parent (larger) chunk for context. Best of both worlds.

**Query transformation (don't search with raw user queries):**
- **HyDE (Hypothetical Document Embeddings):** Generate a hypothetical answer, embed *that*, search for similar real documents. Works because answers are closer to documents than questions are.
- **Multi-query:** Rewrite the user query into 3-5 variations, retrieve for each, deduplicate results. Captures different phrasings of the same intent.
- **Step-back prompting:** Ask "what is the broader topic?" first, retrieve background context, then answer the specific question.
- **Query decomposition:** Break complex queries into sub-queries, retrieve for each, synthesize.

**Re-ranking (the secret weapon):**
- Vector search retrieves candidates (high recall, lower precision). Re-ranking sorts them by true relevance (high precision).
- **Cross-encoder re-rankers:** Score each (query, document) pair jointly. Much more accurate than bi-encoder similarity. Slower — only run on top 20-50 candidates.
- **Cohere Rerank:** Managed API, easy to integrate. Strong general-purpose re-ranker.
- **ColBERT:** Token-level interaction between query and document. Fast and accurate. Good self-hosted option.
- **LLM re-ranking:** Ask an LLM to rank documents by relevance. Expensive but effective for small candidate sets.

**RAG evaluation (measure or you're guessing):**
- **Retrieval metrics:** Precision@k (are retrieved docs relevant?), Recall@k (did we find all relevant docs?), MRR (is the best doc ranked first?).
- **Answer faithfulness:** Does the answer only use information from retrieved context? Detects hallucination.
- **Answer relevance:** Does the answer actually address the question?
- **Hallucination detection:** Compare claims in the answer against retrieved sources. Flag unsupported claims.
- **Tools:** RAGAS, DeepEval, LangSmith, custom eval suites.

### Multi-Agent Patterns (Beyond Basics)

Single-agent + tools handles 80% of use cases. Multi-agent is for the remaining 20% where tasks are genuinely decomposable and benefit from specialization.

**Observe-Predict-Update loop:**
- Research-backed pattern for agents that operate in changing environments.
- **Observe:** Gather current state from tools/APIs/environment.
- **Predict:** Form a hypothesis about what action will achieve the goal.
- **Update:** Execute, observe the result, update beliefs. Repeat.
- Works because it mirrors how humans solve problems — not one-shot, but iteratively.

**Multi-agent handoffs:**
- **Routing:** A lightweight classifier/LLM decides which specialist agent handles the request. Fast, cheap first pass.
- **Escalation:** Agent A attempts the task. If confidence is low or it hits a blocker, it escalates to Agent B (more capable, more expensive).
- **Structured handoff:** Agent A produces a handoff document (context, progress, remaining tasks) that Agent B consumes. Prevents context loss between agents.
- **Key rule:** Handoff overhead must be less than the benefit of specialization. If two agents spend more tokens coordinating than a single agent would spend solving, use one agent.

**Voting/consensus:**
- Run the same query through N agents (same or different models).
- Aggregate answers: majority vote (classification), union + dedup (extraction), LLM-as-judge picks best (generation).
- Increases reliability at the cost of N× latency and tokens.
- **When to use:** High-stakes decisions (medical, legal, financial) where correctness matters more than speed/cost.

**Supervisor pattern vs swarm pattern:**
- **Supervisor:** One orchestrator agent assigns tasks to worker agents, collects results, synthesizes. Clear control flow. Single point of failure.
- **Swarm:** Agents communicate peer-to-peer, self-organize around tasks. More resilient, harder to debug. Emergent behavior — sometimes good, sometimes chaotic.
- **Practical guidance:** Start with supervisor. Move to swarm only if you need resilience to individual agent failures and can tolerate unpredictability.

**When single agent + tools beats multi-agent:**
- Task is linear (step A → step B → step C). No benefit from parallelism.
- Context is shared — all steps need the same information. Handoff loses context.
- Latency matters — multi-agent adds coordination overhead.
- Debugging matters — single agent has one trace to follow.
- **Rule of thumb:** If you can describe the task as a single paragraph of instructions, use one agent. Multi-agent is for tasks that need a *document* of instructions with clearly separable sections.

### Production Agent Patterns

Getting an agent to work in a demo is easy. Getting it to work safely, reliably, and at scale in production is the real engineering challenge.

**Sandboxed code execution:**
- Agents that generate and run code need isolation. Never execute agent-generated code on your production host.
- **Containers (Docker):** Spin up per-request containers with resource limits (CPU, memory, network). Simple, well-understood. Cold start 1-5s.
- **Firecracker microVMs:** Sub-second cold start, strong isolation (used by AWS Lambda, Fly.io). Best for multi-tenant agent platforms.
- **V8 isolates (Cloudflare Workers, Deno):** Millisecond cold start, memory-isolated. Good for lightweight code execution. Limited to JS/TS/WASM.
- **gVisor / Sandbox2:** Kernel-level syscall filtering. Defense-in-depth when containers are not enough.
- **Practical rule:** The more capable the agent, the stronger the sandbox. An agent that can `pip install` and run arbitrary Python needs a VM, not just a container.

**Tool search (scaling beyond a handful of tools):**
- Agents with 5-10 tools can have all tool definitions in the system prompt. Agents with 50-500 tools cannot — it wastes context and confuses tool selection.
- **Embedding-based tool search:** Embed all tool descriptions. At runtime, embed the user query, retrieve top-k most relevant tools, include only those in the prompt.
- **Hierarchical tool selection:** Group tools into categories. First select the category, then select specific tools within it. Two-stage retrieval.
- **Tool popularity priors:** Weight tool search results by usage frequency. Commonly used tools should be easier to select.
- **Always include core tools:** Some tools (e.g., "ask user for clarification", "report error") should always be available regardless of query.

**Few-shot tool examples:**
- LLMs are much better at using tools when they see examples of correct usage in context.
- Include 2-3 examples of tool calls with realistic arguments and expected outputs.
- Show the reasoning trace: *why* the agent chose that tool, not just the tool call itself.
- Rotate examples based on the current task — use embedding similarity to select the most relevant examples from a library.

**Human-in-the-loop:**
- **Approval gates:** Agent proposes an action (e.g., "send email to customer", "execute SQL DELETE"), human approves or rejects before execution. Essential for irreversible actions.
- **Confidence thresholds:** If agent's confidence is below a threshold, escalate to human. Requires calibrated confidence — many LLMs are overconfident by default.
- **Escalation triggers:** Specific patterns that should always trigger human review: PII detected, financial transactions above threshold, conflicting information, user frustration signals.
- **Graceful degradation:** When the human is unavailable, the agent should queue the action or fall back to a safe default — never silently skip the approval.

**Streaming and generative UI:**
- **Token-by-token streaming:** Users see the response forming in real-time. Reduces perceived latency from 5-30s to instant. Use SSE (Server-Sent Events) or WebSockets.
- **Tool call status updates:** Show "Searching documents...", "Running code...", "Analyzing results..." as the agent works. Users tolerate longer waits when they see progress.
- **Generative UI:** Agent outputs structured data (charts, tables, forms, interactive elements) rather than just text. The frontend renders rich components based on tool outputs.
- **Partial results:** Stream intermediate results (e.g., first few search results) while the agent continues working. Users can start reading immediately.
- **Cancellation:** Allow users to cancel long-running agent tasks. The agent should checkpoint its progress so work is not lost.

### Production AI: Feedback Loops

Deploying an AI feature is the beginning, not the end. Production AI systems need continuous feedback loops to improve over time.

**User corrections as eval data:**
- When users edit, retry, or override AI outputs, that is signal.
- Log the original output, the user correction, and the input. This triple becomes a new eval case.
- Prioritize corrections on high-frequency queries — they represent the most impactful improvements.

**Thumbs up/down → golden dataset expansion:**
- Simple binary feedback is cheap to collect and surprisingly useful.
- Thumbs-up responses become positive examples in your golden dataset.
- Thumbs-down responses become regression test cases — the system must not produce this output.
- **Volume target:** Aim for 1-5% of interactions to get feedback. Design the UX to make it frictionless.

**A/B testing AI responses:**
- Route a percentage of traffic to a new model/prompt/pipeline.
- Measure: task completion rate, user satisfaction (thumbs up ratio), downstream business metrics.
- **Statistical rigor:** AI outputs have high variance. You need more samples than a typical A/B test. Run for longer, use larger groups.
- Watch for novelty effects — users may prefer "different" initially.

**Shadow mode (new model runs alongside old):**
- Both models process every request. Only the old model's output is shown to users.
- Compare outputs offline: quality scores, latency, cost, failure rate.
- Promote the new model when shadow metrics exceed the old model across the board.
- **Cost:** 2× inference cost during shadow period. Worth it for high-stakes systems.

**Continuous improvement flywheel:**
```
Deploy → Observe (logs, metrics, feedback)
  → Collect feedback (thumbs, corrections, escalations)
  → Update evals (add new cases from feedback)
  → Improve (better prompts, retrieval, model)
  → Deploy → ...
```
- **Key insight:** The flywheel accelerates. More users → more feedback → better evals → faster improvement → more users.
- Automate as much as possible: auto-ingest corrections into eval suite, auto-run evals on PRs, auto-alert on quality drops.
- Review golden dataset quarterly — remove stale cases, rebalance categories, add emerging use cases.

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

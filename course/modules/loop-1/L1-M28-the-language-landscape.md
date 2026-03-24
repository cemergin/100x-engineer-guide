# L1-M28: The Language Landscape

> **Loop 1 (Foundation)** | Section 1F: Language Exposure + Capstone | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M11 (REST API Design)
>
> **Source:** Chapters 11, 6 of the 100x Engineer Guide

---

## The Goal

TicketPulse is written in TypeScript. That was a choice -- a reasonable one for a full-stack web application. But it was not the only choice.

This module is not about finding the "best" language. There is no best language. There is best fit for a given context: team, problem domain, performance requirements, ecosystem needs, and hiring pool.

You will run each server, read each codebase, and benchmark each one. By the end, you will have hands-on experience with four major backend languages and an informed opinion about when to use each.

**You will have all four servers running within the first ten minutes.**

---

## 0. Quick Start (10 minutes)

The four implementations are provided in the `language-comparison/` directory. Each implements the same API:

```
GET /api/events         → Returns a list of events (JSON)
GET /api/events/:id     → Returns a single event (JSON)
GET /health             → Returns { "status": "ok" }
```

Same data. Same response format. Four different languages.

### 0.1 Start TypeScript (Already Running)

```bash
# TicketPulse is already running on port 3000
curl -s http://localhost:3000/api/events | jq '.[0]'
```

### 0.2 Start Go

```bash
cd ticketpulse/language-comparison/go

# If Go is not installed:
# brew install go   (macOS)
# mise use go@1.22  (with mise)

go run main.go &
# Listening on :3001

curl -s http://localhost:3001/api/events | jq '.[0]'
```

### 0.3 Start Python (FastAPI)

```bash
cd ticketpulse/language-comparison/python

# If Python 3.12+ is not installed:
# brew install python@3.12   (macOS)
# mise use python@3.12       (with mise)

python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn

uvicorn main:app --port 3002 &
# Uvicorn running on http://0.0.0.0:3002

curl -s http://localhost:3002/api/events | jq '.[0]'
```

### 0.4 Start Rust

```bash
cd ticketpulse/language-comparison/rust

# If Rust is not installed:
# curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# mise use rust@stable  (with mise)

cargo run &
# First build takes 30-60 seconds (Rust compiles everything ahead of time)
# Listening on :3003

curl -s http://localhost:3003/api/events | jq '.[0]'
```

All four should return the same JSON structure:

```json
{
  "id": 1,
  "title": "Summer Music Festival",
  "venue": "Central Park Amphitheater",
  "date": "2026-07-15T19:00:00Z",
  "totalTickets": 5000,
  "availableTickets": 3247,
  "priceInCents": 7500
}
```

---

## 1. Read the Code: Side by Side

### 1.1 Go: main.go

```go
// language-comparison/go/main.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"time"
)

type Event struct {
	ID               int       `json:"id"`
	Title            string    `json:"title"`
	Venue            string    `json:"venue"`
	Date             time.Time `json:"date"`
	TotalTickets     int       `json:"totalTickets"`
	AvailableTickets int       `json:"availableTickets"`
	PriceInCents     int       `json:"priceInCents"`
}

var events = []Event{
	{1, "Summer Music Festival", "Central Park Amphitheater",
		time.Date(2026, 7, 15, 19, 0, 0, 0, time.UTC), 5000, 3247, 7500},
	{2, "Jazz Night", "Blue Note Club",
		time.Date(2026, 8, 20, 20, 0, 0, 0, time.UTC), 200, 142, 12000},
	{3, "Rock Revival", "Madison Square Garden",
		time.Date(2026, 9, 10, 18, 0, 0, 0, time.UTC), 20000, 8421, 15000},
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /api/events", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(events)
	})

	mux.HandleFunc("GET /api/events/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := strconv.Atoi(r.PathValue("id"))
		if err != nil {
			http.Error(w, `{"error":"invalid id"}`, http.StatusBadRequest)
			return
		}
		for _, e := range events {
			if e.ID == id {
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(e)
				return
			}
		}
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
	})

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	log.Println("Go server listening on :3001")
	log.Fatal(http.ListenAndServe(":3001", mux))
}
```

**What stands out:**
- No external dependencies. The standard library includes HTTP server, JSON, routing.
- Explicit error handling (`if err != nil` -- you will see this on every other line in Go).
- Struct tags (`json:"id"`) control serialization.
- Types are declared, but inference exists (`id, err := strconv.Atoi(...)`)
- ~50 lines for a complete HTTP server.

### 1.2 Python (FastAPI): main.py

```python
# language-comparison/python/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class Event(BaseModel):
    id: int
    title: str
    venue: str
    date: datetime
    totalTickets: int
    availableTickets: int
    priceInCents: int

events = [
    Event(id=1, title="Summer Music Festival", venue="Central Park Amphitheater",
          date=datetime(2026, 7, 15, 19, 0), totalTickets=5000,
          availableTickets=3247, priceInCents=7500),
    Event(id=2, title="Jazz Night", venue="Blue Note Club",
          date=datetime(2026, 8, 20, 20, 0), totalTickets=200,
          availableTickets=142, priceInCents=12000),
    Event(id=3, title="Rock Revival", venue="Madison Square Garden",
          date=datetime(2026, 9, 10, 18, 0), totalTickets=20000,
          availableTickets=8421, priceInCents=15000),
]

@app.get("/api/events")
def list_events() -> list[Event]:
    return events

@app.get("/api/events/{event_id}")
def get_event(event_id: int) -> Event:
    for event in events:
        if event.id == event_id:
            return event
    raise HTTPException(status_code=404, detail="not found")

@app.get("/health")
def health():
    return {"status": "ok"}
```

**What stands out:**
- Dramatically fewer lines than any other language (~30 lines of business logic).
- Decorator-based routing (`@app.get`).
- Pydantic models provide validation AND serialization AND auto-generated API docs.
- Type hints (`event_id: int`) are enforced at runtime by FastAPI, not just by a type checker.
- Visit `http://localhost:3002/docs` to see auto-generated Swagger documentation.
- The trade-off: Python is slower at runtime. The developer experience is exceptional.

### 1.3 TypeScript (Express): Already Familiar

```typescript
// You already know this from TicketPulse:
router.get('/api/events', async (req, res) => {
  const events = await pool.query('SELECT * FROM events');
  res.json(events.rows);
});
```

**What stands out:**
- Familiar syntax if you know JavaScript.
- TypeScript adds type safety at compile time, but it is optional (you can always use `any`).
- The ecosystem is enormous -- npm has more packages than any other registry.
- Async/await feels natural for I/O-heavy work.

### 1.4 Rust (Axum): main.rs

```rust
// language-comparison/rust/src/main.rs
use axum::{extract::Path, http::StatusCode, routing::get, Json, Router};
use serde::Serialize;
use std::sync::Arc;

#[derive(Clone, Serialize)]
struct Event {
    id: u32,
    title: String,
    venue: String,
    date: String,
    total_tickets: u32,
    available_tickets: u32,
    price_in_cents: u32,
}

type Events = Arc<Vec<Event>>;

async fn list_events(events: axum::extract::State<Events>) -> Json<Vec<Event>> {
    Json(events.as_ref().clone())
}

async fn get_event(
    Path(id): Path<u32>,
    events: axum::extract::State<Events>,
) -> Result<Json<Event>, StatusCode> {
    events
        .iter()
        .find(|e| e.id == id)
        .cloned()
        .map(Json)
        .ok_or(StatusCode::NOT_FOUND)
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok"}))
}

#[tokio::main]
async fn main() {
    let events: Events = Arc::new(vec![
        Event {
            id: 1,
            title: "Summer Music Festival".into(),
            venue: "Central Park Amphitheater".into(),
            date: "2026-07-15T19:00:00Z".into(),
            total_tickets: 5000,
            available_tickets: 3247,
            price_in_cents: 7500,
        },
        Event {
            id: 2,
            title: "Jazz Night".into(),
            venue: "Blue Note Club".into(),
            date: "2026-08-20T20:00:00Z".into(),
            total_tickets: 200,
            available_tickets: 142,
            price_in_cents: 12000,
        },
        Event {
            id: 3,
            title: "Rock Revival".into(),
            venue: "Madison Square Garden".into(),
            date: "2026-09-10T18:00:00Z".into(),
            total_tickets: 20000,
            available_tickets: 8421,
            price_in_cents: 15000,
        },
    ]);

    let app = Router::new()
        .route("/api/events", get(list_events))
        .route("/api/events/{id}", get(get_event))
        .route("/health", get(health))
        .with_state(events);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3003")
        .await
        .unwrap();

    println!("Rust server listening on :3003");
    axum::serve(listener, app).await.unwrap();
}
```

**What stands out:**
- `Arc<Vec<Event>>` -- shared ownership with atomic reference counting. Rust makes you think about ownership.
- `Result<Json<Event>, StatusCode>` -- errors are values, not exceptions. The type system forces you to handle them.
- `.into()` converts `&str` to `String`. Rust distinguishes between borrowed and owned strings.
- The `#[derive(Clone, Serialize)]` macros auto-generate code at compile time.
- First compile is slow (30-60 seconds). Subsequent compiles are fast. Runtime is blazing.

---

## 2. Observe: Benchmark All Four

Install `wrk` (a modern HTTP benchmarking tool):

```bash
# macOS
brew install wrk

# Linux
sudo apt install wrk
```

Benchmark each server:

```bash
echo "=== TypeScript (Express) ==="
wrk -t2 -c100 -d10s http://localhost:3000/api/events
echo ""

echo "=== Go ==="
wrk -t2 -c100 -d10s http://localhost:3001/api/events
echo ""

echo "=== Python (FastAPI) ==="
wrk -t2 -c100 -d10s http://localhost:3002/api/events
echo ""

echo "=== Rust (Axum) ==="
wrk -t2 -c100 -d10s http://localhost:3003/api/events
echo ""
```

The flags: `-t2` = 2 threads, `-c100` = 100 concurrent connections, `-d10s` = 10 second duration.

### 2.1 Typical Results

Your numbers will vary, but the relative order is usually consistent:

| Language | Requests/sec | Avg Latency | Memory Usage |
|---|---|---|---|
| **Rust (Axum)** | ~150,000 | ~0.7ms | ~5 MB |
| **Go** | ~120,000 | ~0.9ms | ~12 MB |
| **TypeScript (Express)** | ~15,000 | ~6ms | ~80 MB |
| **Python (FastAPI)** | ~8,000 | ~12ms | ~50 MB |

Check memory usage while the benchmarks run:

```bash
# If running in Docker:
docker stats

# If running natively, use:
ps aux | grep -E "node|go|python|target/release" | awk '{print $11, $6/1024 "MB"}'
```

### 2.2 What the Numbers Tell You

- **Rust and Go** are 10-20x faster than TypeScript and Python for raw HTTP throughput on this simple benchmark.
- **Memory usage** differs by an order of magnitude. Rust uses almost nothing. Node.js uses ~80 MB before handling a single request (the V8 runtime).
- **But this is an in-memory benchmark.** The real TicketPulse hits a database, parses JSON, validates input, and does business logic. In a real application with real I/O, the gap narrows significantly because the bottleneck is usually the database, not the language runtime.

> **Reflect:** Which language felt most natural to read? Which had the most surprising performance? If you had to add a feature to one of these codebases right now, which would you be most productive in?

---

## 3. Comparing Patterns Across Languages

### 3.1 HTTP Routing

| Language | Routing Pattern |
|---|---|
| Go | `mux.HandleFunc("GET /api/events/{id}", handler)` |
| Python | `@app.get("/api/events/{event_id}")` |
| TypeScript | `router.get('/api/events/:id', handler)` |
| Rust | `.route("/api/events/{id}", get(handler))` |

All four use a similar concept (path with parameter placeholders) but different syntax. If you understand one, you can read the others.

### 3.2 JSON Serialization

| Language | How JSON Works |
|---|---|
| Go | Struct tags: `json:"id"`. `json.Encode` uses reflection. |
| Python | Pydantic models: `class Event(BaseModel)`. Automatic. |
| TypeScript | Objects are JSON-like natively. `res.json(data)` calls `JSON.stringify`. |
| Rust | `#[derive(Serialize)]` macro generates serialization code at compile time. Zero-cost. |

### 3.3 Error Handling

| Language | Error Pattern |
|---|---|
| Go | `if err != nil { return err }` -- explicit, verbose, impossible to ignore |
| Python | `raise HTTPException(status_code=404)` -- exceptions |
| TypeScript | `throw new Error()` or return error response -- exceptions or manual |
| Rust | `Result<T, E>` -- errors are return values, compiler forces handling |

---

## 4. When to Use Each

| Language | Best For | Avoid When |
|---|---|---|
| **Go** | Microservices, CLIs, DevOps tools, network services | Complex domain models, data science, rapid prototyping |
| **Python** | Data/ML, rapid prototyping, scripting, small APIs | High-throughput services, CPU-bound workloads |
| **TypeScript** | Full-stack web, existing JS ecosystem, large teams | Systems programming, performance-critical services |
| **Rust** | Infrastructure, performance-critical services, WebAssembly | MVPs, small teams, tight deadlines |

### 4.1 The Real Decision Framework

The language choice is less about performance and more about:

1. **Team:** What does your team know? A team that knows Python will ship 5x faster in Python than in Rust, even if Rust is 10x faster at runtime.
2. **Ecosystem:** Does the language have libraries for what you need? Python dominates ML. Go dominates DevOps. TypeScript dominates web.
3. **Hiring:** Can you hire engineers who know this language in your market?
4. **Maintenance:** Will the codebase be readable in 3 years by someone who did not write it?
5. **Performance requirements:** If you need <1ms latency at scale, Go or Rust. If you need 200ms and developer velocity, TypeScript or Python.

---

## 5. Checkpoint

Before continuing to the next module, verify:

- [ ] You ran all four servers and got the same JSON response from each
- [ ] You read the source code for all four implementations
- [ ] You ran `wrk` benchmarks and recorded the requests/sec for each
- [ ] You checked memory usage for each language runtime
- [ ] You can explain the error handling pattern for each language
- [ ] You have an opinion on which language felt most readable to you (there is no wrong answer)

```bash
# Quick verify: all four are running and returning the same data
for port in 3000 3001 3002 3003; do
  echo "Port $port: $(curl -s http://localhost:$port/api/events | jq '.[0].title')"
done
# All four should print: "Summer Music Festival"
```

> **The key takeaway:** There is no best language. There is best fit. A 100x engineer does not have a favorite language -- they have a framework for choosing the right tool for the job.

---

## What's Next

All four servers handled 100 concurrent connections fine. But what happens at 10,000? The next module pushes each language to its limits with heavy concurrency, revealing how event loops, goroutines, async runtimes, and thread pools handle the pressure differently.

## Key Terms

| Term | Definition |
|------|-----------|
| **Static typing** | A type system where variable types are checked at compile time, catching type errors before the code runs. |
| **Dynamic typing** | A type system where variable types are determined and checked at runtime rather than at compile time. |
| **Compiled** | A language whose source code is translated entirely into machine code before execution. |
| **Interpreted** | A language whose source code is executed line by line at runtime by an interpreter. |
| **Garbage collection** | An automatic memory management process that reclaims memory occupied by objects no longer in use. |

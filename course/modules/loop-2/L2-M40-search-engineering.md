# L2-M40: Search Engineering

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M31, L2-M34 (Kafka)
>
> **Source:** Chapters 24, 22 of the 100x Engineer Guide

## What You'll Learn
- How full-text search works (inverted indexes, tokenization, BM25 scoring)
- How to deploy Elasticsearch and index TicketPulse events
- How to build a search API with full-text search, filters, and sorting
- How to implement autocomplete with edge n-grams
- Strategies for keeping search in sync with your primary database
- When Postgres full-text search (tsvector) is good enough vs when you need Elasticsearch

## Why This Matters
TicketPulse users want to search: "jazz concerts in NYC this weekend." That's a query that combines full-text search ("jazz"), filtering ("NYC"), and date range ("this weekend"). A naive SQL `LIKE '%jazz%'` query on a large events table is a sequential scan nightmare. This module builds a real search system — the same architecture that powers search at companies from small startups to Spotify and GitHub.

## Prereq Check

Your TicketPulse microservices should be running with events in Postgres. You'll need Docker Compose available to add Elasticsearch.

```bash
docker compose ps
# Verify your services are running
```

---

## Part 1: Why SQL LIKE Isn't Enough (5 min)

### The Problem

```sql
-- The naive approach
SELECT * FROM events
WHERE name ILIKE '%jazz%' OR description ILIKE '%jazz%'
ORDER BY event_date;
```

This has three fundamental problems:

1. **Performance**: `ILIKE '%jazz%'` requires a sequential scan. No B-tree index can help with leading wildcards. On 1M events, this takes seconds.

2. **Relevance**: Which result should be first? An event named "Jazz at Lincoln Center" or one with "pizza jazz" in the description? SQL has no concept of relevance ranking.

3. **Flexibility**: Users search for "taylor swift nyc" — that's a multi-term query that needs to match across multiple fields. SQL can't handle this naturally.

### What Search Engines Do Differently

Search engines (Elasticsearch, Solr, Meilisearch) use **inverted indexes** — a data structure purpose-built for text search.

```
Forward index (what a database has):
  Doc 1: "Jazz at Lincoln Center"
  Doc 2: "Blues and Jazz Festival"
  Doc 3: "Lincoln Park Concert"

Inverted index (what a search engine builds):
  "jazz"     → [Doc 1, Doc 2]
  "lincoln"  → [Doc 1, Doc 3]
  "center"   → [Doc 1]
  "blues"    → [Doc 2]
  "festival" → [Doc 2]
  "park"     → [Doc 3]
  "concert"  → [Doc 3]
```

To find documents containing "jazz," the search engine looks up the single entry in the inverted index — O(1), not O(N).

---

> **Before you continue:** If you run `SELECT * FROM events WHERE name ILIKE '%jazz%'` on 1 million rows, what kind of scan does the database perform? Why can't a B-tree index help with leading wildcards?


## Part 2: Deploy Elasticsearch (10 min)

### 🚀 Deploy: Add Elasticsearch to Docker Compose

Add to your `docker-compose.yml`:

```yaml
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - es-data:/usr/share/elasticsearch/data
    healthcheck:
      test: curl -f http://localhost:9200/_cluster/health || exit 1
      interval: 10s
      timeout: 5s
      retries: 10

  kibana:
    image: docker.elastic.co/kibana/kibana:8.12.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

volumes:
  es-data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```bash
docker compose up -d elasticsearch kibana

# Wait for Elasticsearch to be healthy
docker compose logs elasticsearch --tail 5
# Look for: "started"

# Verify
curl http://localhost:9200
# Should return cluster info JSON
```

### 🔍 Try It: Explore Kibana

Open http://localhost:5601 in your browser. Navigate to Dev Tools (the wrench icon in the sidebar). This is where you can run Elasticsearch queries interactively.

---

## Part 3: Index TicketPulse Events (15 min)

### 🛠️ Build: Define the Index Mapping

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


A mapping defines the schema for your search index — which fields exist, their types, and how they should be analyzed.

```bash
# Create the events index with an explicit mapping
curl -X PUT "http://localhost:9200/ticketpulse-events" -H 'Content-Type: application/json' -d '
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "autocomplete_analyzer": {
          "type": "custom",
          "tokenizer": "autocomplete_tokenizer",
          "filter": ["lowercase"]
        },
        "autocomplete_search_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "autocomplete_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 20,
          "token_chars": ["letter", "digit"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "standard",
        "fields": {
          "autocomplete": {
            "type": "text",
            "analyzer": "autocomplete_analyzer",
            "search_analyzer": "autocomplete_search_analyzer"
          },
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "description": {
        "type": "text",
        "analyzer": "standard"
      },
      "category": {
        "type": "keyword"
      },
      "venue_name": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "city": {
        "type": "keyword"
      },
      "event_date": {
        "type": "date"
      },
      "price_min": {
        "type": "float"
      },
      "price_max": {
        "type": "float"
      },
      "tickets_available": {
        "type": "integer"
      }
    }
  }
}'
```

### Understanding Field Types

| Type | Behavior | Use For |
|------|----------|---------|
| `text` | Analyzed (tokenized, lowercased, stemmed). Supports full-text search. | Event names, descriptions — anything users search with natural language |
| `keyword` | NOT analyzed. Stored as-is. Supports exact match, aggregation, sorting. | Categories, cities, statuses — anything you filter or aggregate on |
| `date` | Parsed as dates. Supports range queries. | Event dates |
| `float`/`integer` | Numeric. Supports range queries, sorting, aggregation. | Prices, counts |

A field can have **multi-fields** (the `fields` block): `name` is analyzed as `text` for search, but `name.keyword` is stored as a keyword for exact match and sorting. `name.autocomplete` uses edge n-grams for search-as-you-type.

### 🛠️ Build: Bulk Index Events from Postgres

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


Create a script to sync events from Postgres to Elasticsearch:

```javascript
// scripts/index-events.js
const { Client } = require('@elastic/elasticsearch');
const { Pool } = require('pg');

const esClient = new Client({ node: 'http://localhost:9200' });
const pgPool = new Pool({
  connectionString: 'postgres://ticketpulse:ticketpulse@localhost:5432/tickets'
});

async function indexEvents() {
  // Fetch events with venue info and ticket stats from Postgres
  const { rows } = await pgPool.query(`
    SELECT
      e.id,
      e.name,
      e.category,
      e.event_date,
      v.name AS venue_name,
      v.city,
      MIN(t.price) AS price_min,
      MAX(t.price) AS price_max,
      COUNT(t.id) FILTER (WHERE t.status = 'available') AS tickets_available
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    LEFT JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name, e.category, e.event_date, v.name, v.city
  `);

  console.log(`Fetched ${rows.length} events from Postgres`);

  // Build bulk request body
  const body = rows.flatMap(event => [
    { index: { _index: 'ticketpulse-events', _id: event.id.toString() } },
    {
      name: event.name,
      category: event.category,
      event_date: event.event_date,
      venue_name: event.venue_name,
      city: event.city,
      price_min: parseFloat(event.price_min) || 0,
      price_max: parseFloat(event.price_max) || 0,
      tickets_available: parseInt(event.tickets_available) || 0
    }
  ]);

  // Bulk index
  const result = await esClient.bulk({ body });

  if (result.errors) {
    const errorItems = result.items.filter(item => item.index.error);
    console.error(`Errors indexing ${errorItems.length} events`);
    errorItems.slice(0, 3).forEach(item => console.error(item.index.error));
  } else {
    console.log(`Successfully indexed ${rows.length} events`);
  }

  // Refresh the index to make documents searchable immediately
  await esClient.indices.refresh({ index: 'ticketpulse-events' });

  await pgPool.end();
}

indexEvents().catch(console.error);
```

```bash
# Run the indexing script
node scripts/index-events.js

# Verify documents are indexed
curl "http://localhost:9200/ticketpulse-events/_count"
# Should show the count of indexed events
```

---

## Part 4: Build the Search API (15 min)

### 🛠️ Build: Full-Text Search with Filters

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


```javascript
// src/services/event-service/routes/search.js
const { Client } = require('@elastic/elasticsearch');
const esClient = new Client({ node: 'http://elasticsearch:9200' });

// GET /api/events/search?q=jazz&city=NYC&dateFrom=2024-03-20&dateTo=2024-03-24
router.get('/api/events/search', async (req, res) => {
  const { q, city, category, dateFrom, dateTo, priceMax, page = 1, size = 20 } = req.query;

  // Build the query
  const must = [];
  const filter = [];

  // Full-text search (if query provided)
  if (q) {
    must.push({
      multi_match: {
        query: q,
        fields: ['name^3', 'description', 'venue_name^2'],
        // ^3 means "name matches are 3x more important than description"
        type: 'best_fields',
        fuzziness: 'AUTO'  // Handles typos: "jaz" matches "jazz"
      }
    });
  }

  // Filters (exact match — no relevance scoring)
  if (city) {
    filter.push({ term: { city: city } });
  }
  if (category) {
    filter.push({ term: { category: category } });
  }
  if (dateFrom || dateTo) {
    const range = { event_date: {} };
    if (dateFrom) range.event_date.gte = dateFrom;
    if (dateTo) range.event_date.lte = dateTo;
    filter.push({ range });
  }
  if (priceMax) {
    filter.push({ range: { price_min: { lte: parseFloat(priceMax) } } });
  }

  // Only show events with available tickets
  filter.push({ range: { tickets_available: { gt: 0 } } });

  const result = await esClient.search({
    index: 'ticketpulse-events',
    body: {
      query: {
        bool: {
          must: must.length > 0 ? must : [{ match_all: {} }],
          filter: filter
        }
      },
      sort: q
        ? [{ _score: 'desc' }, { event_date: 'asc' }]  // If searching, sort by relevance first
        : [{ event_date: 'asc' }],                       // If browsing, sort by date
      from: (page - 1) * size,
      size: parseInt(size),
      highlight: {
        fields: {
          name: {},
          description: {}
        }
      }
    }
  });

  res.json({
    total: result.hits.total.value,
    page: parseInt(page),
    results: result.hits.hits.map(hit => ({
      id: hit._id,
      score: hit._score,
      ...hit._source,
      highlights: hit.highlight
    }))
  });
});
```

### 🔍 Try It: Search for Events

```bash
# Full-text search
curl "http://localhost:3000/api/events/search?q=jazz"

# Search with city filter
curl "http://localhost:3000/api/events/search?q=jazz&city=New%20York"

# Search with date range
curl "http://localhost:3000/api/events/search?q=concert&dateFrom=2024-03-20&dateTo=2024-03-24"

# Browse with filters only (no search query)
curl "http://localhost:3000/api/events/search?category=rock&city=Chicago"
```

### How BM25 Scoring Works

Elasticsearch uses **BM25** (Best Match 25) to rank search results. The simplified intuition:

```
Score = Relevance of term to document

Higher score when:
  - The term appears MORE OFTEN in this document (term frequency)
  - The term appears in FEWER documents overall (inverse document frequency)
  - The document is SHORTER (shorter documents get a boost — a match in a short title
    is more meaningful than a match in a long description)
```

The `^3` boost on `name` means a match in the event name is weighted 3x more than a match in the description. This is a tuning knob — adjust it based on user feedback.

### 🔍 Try It: See Relevance Scoring

```bash
# Use explain to see how scoring works
curl "http://localhost:9200/ticketpulse-events/_search" -H 'Content-Type: application/json' -d '
{
  "explain": true,
  "query": {
    "multi_match": {
      "query": "jazz",
      "fields": ["name^3", "description"]
    }
  },
  "size": 3
}'
```

The `_explanation` field in the response breaks down exactly why each document scored as it did.

---

## Part 5: Autocomplete — Search as You Type (10 min)

### 🛠️ Build: Suggest Endpoint with Edge N-Grams

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


We already configured the `autocomplete_analyzer` in our mapping. Here's how edge n-grams work:

```
Input: "Taylor Swift"

Edge n-grams (min=2, max=20):
  "ta", "tay", "tayl", "taylo", "taylor"
  "sw", "swi", "swif", "swift"

When user types "tay", it matches the "tay" n-gram → returns "Taylor Swift"
```

```javascript
// GET /api/events/suggest?q=tay
router.get('/api/events/suggest', async (req, res) => {
  const { q } = req.query;

  if (!q || q.length < 2) {
    return res.json({ suggestions: [] });
  }

  const result = await esClient.search({
    index: 'ticketpulse-events',
    body: {
      query: {
        bool: {
          should: [
            {
              match: {
                'name.autocomplete': {
                  query: q,
                  operator: 'and'
                }
              }
            },
            {
              match_phrase_prefix: {
                name: {
                  query: q,
                  boost: 2  // Exact prefix match gets higher score
                }
              }
            }
          ]
        }
      },
      _source: ['name', 'category', 'city', 'event_date'],
      size: 5
    }
  });

  res.json({
    suggestions: result.hits.hits.map(hit => ({
      id: hit._id,
      name: hit._source.name,
      category: hit._source.category,
      city: hit._source.city,
      date: hit._source.event_date
    }))
  });
});
```

### 🔍 Try It: Autocomplete in Action

```bash
curl "http://localhost:3000/api/events/suggest?q=ev"
# Returns events starting with "ev"

curl "http://localhost:3000/api/events/suggest?q=jazz"
# Returns events containing "jazz"
```

---

## Part 6: Keeping Search in Sync (10 min)

### The Dual-Write Problem

TicketPulse stores events in Postgres (source of truth) and Elasticsearch (search index). When an event is created or updated, both need to be updated. But how?

### Option A: Sync in the API Handler

```javascript
// Simple: update ES after DB write
async function updateEvent(id, data) {
  // 1. Update Postgres
  await db.query('UPDATE events SET name=$1, ... WHERE id=$2', [data.name, id]);

  // 2. Update Elasticsearch
  await esClient.update({
    index: 'ticketpulse-events',
    id: id.toString(),
    body: { doc: data }
  });
}
```

**Pros**: Simple, immediate consistency.
**Cons**: If ES update fails, your data is inconsistent. If the API crashes between step 1 and step 2, ES is stale. Adds latency to every write.

### Option B: CDC via Kafka (Recommended)

Use the Kafka infrastructure from L2-M34 to stream Postgres changes to an Elasticsearch consumer:

```
Postgres → Debezium CDC → Kafka (events.changes topic) → ES Consumer → Elasticsearch
```

```javascript
// kafka/consumers/es-sync-consumer.js
const { Kafka } = require('kafkajs');
const { Client } = require('@elastic/elasticsearch');

const kafka = new Kafka({ brokers: ['kafka:9092'] });
const consumer = kafka.consumer({ groupId: 'es-sync-group' });
const esClient = new Client({ node: 'http://elasticsearch:9200' });

async function start() {
  await consumer.connect();
  await consumer.subscribe({ topic: 'ticketpulse.public.events', fromBeginning: false });

  await consumer.run({
    eachMessage: async ({ message }) => {
      const change = JSON.parse(message.value.toString());

      if (change.op === 'd') {
        // Delete
        await esClient.delete({
          index: 'ticketpulse-events',
          id: change.before.id.toString(),
          refresh: true
        }).catch(() => {}); // Ignore if already deleted
      } else {
        // Create or Update
        const event = change.after;
        await esClient.index({
          index: 'ticketpulse-events',
          id: event.id.toString(),
          body: {
            name: event.name,
            category: event.category,
            event_date: event.event_date,
            // ... other fields
          },
          refresh: true
        });
      }

      console.log(`[es-sync] Processed ${change.op} for event ${(change.after || change.before).id}`);
    }
  });
}

start().catch(console.error);
```

**Pros**: Decoupled, reliable (Kafka guarantees delivery), works for any number of consumers.
**Cons**: Eventual consistency (events appear in search after a short delay), more infrastructure to manage.

### Which Approach for TicketPulse?

| Factor | Direct Sync (Option A) | CDC via Kafka (Option B) |
|--------|----------------------|--------------------------|
| Consistency | Immediate (but fragile) | Eventual (seconds) |
| Reliability | Single point of failure | Kafka retries on failure |
| Complexity | Simple | More infrastructure |
| Performance | Adds latency to writes | Async, no write latency |
| Scale | Gets complex with many consumers | Kafka handles fan-out |

For a startup with one search index, Option A is fine. As TicketPulse grows and adds more consumers (search, analytics, recommendations), Option B pays off.

### 📊 Observe: Elasticsearch Kibana UI

Open Kibana at http://localhost:5601 and explore:

1. **Dev Tools**: Run search queries interactively
2. **Index Management** (Stack Management > Index Management): See index size, document count, shard info
3. **Discover**: Browse and filter indexed documents
4. **Dashboard**: Build visualizations of search analytics (top queries, response times)

---

## Part 7: When to Use Postgres Full-Text Search Instead (5 min)

### 🤔 Reflect: Elasticsearch vs PostgreSQL tsvector

PostgreSQL has built-in full-text search using `tsvector` and `tsquery`:

```sql
-- Add a tsvector column and GIN index
ALTER TABLE events ADD COLUMN search_vector tsvector;
UPDATE events SET search_vector = to_tsvector('english', name || ' ' || COALESCE(description, ''));
CREATE INDEX idx_events_search ON events USING GIN (search_vector);

-- Search
SELECT name, ts_rank(search_vector, query) AS rank
FROM events, to_tsquery('english', 'jazz & new & york') AS query
WHERE search_vector @@ query
ORDER BY rank DESC;
```

### When Postgres FTS is Enough

| Use Postgres FTS When... | Use Elasticsearch When... |
|--------------------------|--------------------------|
| < 1M documents | > 1M documents or growing fast |
| Simple search (one or two fields) | Complex search (multi-field, boosting, facets) |
| You want zero additional infrastructure | You need autocomplete, fuzzy matching, "did you mean?" |
| Search is a secondary feature | Search is a primary user experience |
| Queries are simple (single terms, phrases) | Queries are complex (multi-term, cross-field, with typo tolerance) |
| You already have Postgres and don't want to add ES | You need search analytics, A/B testing of relevance |

For TicketPulse, where search is a core user experience with autocomplete, filtering, and relevance ranking, Elasticsearch is the right choice. But if you're building an admin panel with a simple "find event by name" feature, Postgres tsvector is perfectly adequate.

---

> **What did you notice?** An inverted index turns a full-table scan into an O(1) lookup. But now you have two data stores to keep in sync. When is the operational overhead of Elasticsearch worth it versus just using Postgres tsvector?

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Inverted index** | Maps terms to documents. O(1) lookup vs O(N) sequential scan. |
| **Mapping** | Define field types: `text` for full-text search, `keyword` for exact match/filters. |
| **BM25** | Relevance scoring based on term frequency, inverse document frequency, and document length. |
| **Multi-match** | Search across multiple fields with different boosts. |
| **Edge n-grams** | Pre-compute prefixes for autocomplete. "Taylor" -> "ta", "tay", "tayl"... |
| **Sync strategy** | Simple: dual-write in handler. Better: CDC via Kafka. |
| **Postgres FTS** | Good enough for simple search. Use `tsvector` + GIN index. |
| **Elasticsearch** | When search is a primary UX: autocomplete, fuzzy, relevance tuning. |

## What's Next

In **L2-M41: The N+1 Problem**, you'll discover that TicketPulse's events page is firing 201 database queries to load 100 events — and you'll fix it with a 16x performance improvement.

## Key Terms

| Term | Definition |
|------|-----------|
| **Inverted index** | A data structure mapping each unique term to the list of documents (or rows) that contain it. |
| **BM25** | A probabilistic ranking function used by search engines to score documents by relevance to a query. |
| **Elasticsearch** | A distributed search and analytics engine built on Apache Lucene, commonly used for full-text search. |
| **Analyzer** | A pipeline of character filters, a tokenizer, and token filters that transforms text into searchable terms. |
| **Autocomplete** | A search feature that suggests completions as the user types, typically implemented with edge n-grams or prefix queries. |
| **Facet** | A category or attribute used to filter and narrow search results (e.g., price range, brand). |

## 📚 Further Reading
- [Elasticsearch: The Definitive Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- Chapter 22 of the 100x Engineer Guide: Search Engineering section
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [BM25 Explained](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables)
- [Elasticsearch from the Ground Up (video)](https://www.youtube.com/watch?v=PpX7J-G2PEo)

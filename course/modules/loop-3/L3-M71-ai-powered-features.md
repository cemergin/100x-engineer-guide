# L3-M71: AI-Powered Features

> **Loop 3 (Mastery)** | Section 3B: Real-Time & Advanced Features | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L3-M70
>
> **Source:** Chapters 10, 25 of the 100x Engineer Guide

## What You'll Learn

- Adding AI to TicketPulse: natural language search, smart descriptions, and a chatbot
- Building RAG (Retrieval-Augmented Generation) for semantic event search
- Combining vector search with keyword filters for hybrid search
- Using LLMs to generate event marketing copy from basic event data
- Building a simple chatbot grounded in real TicketPulse data
- Managing cost and latency of LLM calls in production
- Implementing guardrails to prevent hallucination and misuse

## Why This Matters

A user types "find me something fun to do outdoors this weekend near downtown" into TicketPulse's search bar. A traditional keyword search returns nothing -- there is no event titled "something fun." But an AI-powered search understands the intent: outdoor events, this weekend, near the city center. It returns a rooftop jazz night, a food truck festival, and an outdoor comedy show.

AI features are not about adding chatbots because they are trendy. They are about solving real problems that traditional engineering cannot: understanding natural language queries, generating content at scale, and creating conversational interfaces where users express imprecise needs.

The challenge is doing this responsibly. LLM calls are expensive ($0.01-$0.10 per query), slow (500ms-3s), and nondeterministic. The model can hallucinate events that do not exist, generate offensive content, or give confidently wrong answers. Shipping AI features means building guardrails as carefully as you build the features themselves.

---

## 1. RAG for Natural Language Search

### The Problem

TicketPulse's search currently uses PostgreSQL full-text search:

```sql
SELECT * FROM events
WHERE to_tsvector('english', title || ' ' || description) @@ plainto_tsquery('english', 'jazz concert')
```

This works for "jazz concert" but fails for:
- "something chill for a date night" (no keyword match)
- "live music with good energy" (subjective, no exact match)
- "events similar to Coachella" (requires world knowledge)

### RAG Architecture

```
User query: "jazz concerts near me this weekend"
        │
        ▼
  Embed the query (text-embedding-3-small)
        │
        ▼
  Vector search in pgvector (semantic match)
        │
        ▼
  Combine with keyword filters (date, location)
        │
        ▼
  Return ranked results
```

RAG (Retrieval-Augmented Generation) means: retrieve relevant data first, then optionally use an LLM to synthesize a response. For search, we may not even need the LLM -- the retrieval step alone is powerful.

### Build: Semantic Search Endpoint

You already have event embeddings from L3-M70. Now expose them as a search endpoint:

```javascript
const { OpenAI } = require('openai');
const openai = new OpenAI();

async function semanticSearch(query, filters = {}, limit = 10) {
  // Step 1: Embed the user's query
  const queryEmbedding = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: query
  });
  const vector = queryEmbedding.data[0].embedding;

  // Step 2: Build the SQL query with both vector similarity AND keyword filters
  let sql = `
    SELECT
      e.id, e.title, e.description, e.genre, e.city,
      e.event_date, e.venue_name, e.price_range,
      1 - (e.embedding <=> $1::vector) AS similarity
    FROM events e
    WHERE e.embedding IS NOT NULL
      AND e.event_date >= CURRENT_DATE
  `;
  const params = [`[${vector.join(',')}]`];
  let paramIndex = 2;

  // Apply hard filters (date, location, price)
  if (filters.city) {
    sql += ` AND e.city = $${paramIndex}`;
    params.push(filters.city);
    paramIndex++;
  }
  if (filters.dateFrom) {
    sql += ` AND e.event_date >= $${paramIndex}`;
    params.push(filters.dateFrom);
    paramIndex++;
  }
  if (filters.dateTo) {
    sql += ` AND e.event_date <= $${paramIndex}`;
    params.push(filters.dateTo);
    paramIndex++;
  }
  if (filters.maxPrice) {
    sql += ` AND e.min_price <= $${paramIndex}`;
    params.push(filters.maxPrice);
    paramIndex++;
  }

  sql += ` ORDER BY e.embedding <=> $1::vector LIMIT $${paramIndex}`;
  params.push(limit);

  const results = await db.query(sql, params);
  return results.rows;
}
```

### Hybrid Search: Vector + Keyword

Pure vector search sometimes misses exact matches. A user searching for "Taylor Swift" should see Taylor Swift events even if the embedding similarity is not the highest. Combine vector search with traditional full-text search:

```javascript
async function hybridSearch(query, filters = {}, limit = 10) {
  const queryEmbedding = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: query
  });
  const vector = queryEmbedding.data[0].embedding;

  // Hybrid: combine vector similarity with BM25 text relevance
  const results = await db.query(
    `WITH vector_results AS (
       SELECT id, title, description, genre, city, event_date,
              1 - (embedding <=> $1::vector) AS vector_score,
              0 AS text_score
       FROM events
       WHERE embedding IS NOT NULL AND event_date >= CURRENT_DATE
       ORDER BY embedding <=> $1::vector
       LIMIT 50
     ),
     text_results AS (
       SELECT id, title, description, genre, city, event_date,
              0 AS vector_score,
              ts_rank(to_tsvector('english', title || ' ' || description),
                      plainto_tsquery('english', $2)) AS text_score
       FROM events
       WHERE to_tsvector('english', title || ' ' || description)
             @@ plainto_tsquery('english', $2)
         AND event_date >= CURRENT_DATE
       LIMIT 50
     ),
     combined AS (
       SELECT
         COALESCE(v.id, t.id) AS id,
         COALESCE(v.title, t.title) AS title,
         COALESCE(v.description, t.description) AS description,
         COALESCE(v.genre, t.genre) AS genre,
         COALESCE(v.city, t.city) AS city,
         COALESCE(v.event_date, t.event_date) AS event_date,
         COALESCE(v.vector_score, 0) * 0.7 +
         COALESCE(t.text_score, 0) * 0.3 AS combined_score
       FROM vector_results v
       FULL OUTER JOIN text_results t ON v.id = t.id
     )
     SELECT * FROM combined
     ORDER BY combined_score DESC
     LIMIT $3`,
    [`[${vector.join(',')}]`, query, limit]
  );

  return results.rows;
}
```

Vector gets 70% weight (semantic understanding), text gets 30% (exact keyword matching). This ensures "Taylor Swift" matches the right event while "chill date night vibes" still works.

### Try It

```javascript
// Test queries
const tests = [
  'jazz concerts this weekend',
  'something fun for a date night',
  'outdoor events near downtown',
  'Taylor Swift',
  'live music with good energy',
  'family friendly activities'
];

for (const query of tests) {
  const results = await hybridSearch(query, { city: 'San Francisco' }, 3);
  console.log(`\nQuery: "${query}"`);
  for (const r of results) {
    console.log(`  ${r.title} (${r.genre}) - score: ${r.combined_score.toFixed(3)}`);
  }
}
```

Evaluate: do the results make sense? Are there queries where vector search helps but keyword search would fail? Are there queries where keyword search is essential?

---

## 2. AI-Generated Event Descriptions

Event organizers submit basic information: artist name, genre, date, venue. Writing a compelling marketing description takes time. An LLM can generate a first draft.

### Build: Description Generator

```javascript
async function generateEventDescription(eventData) {
  const prompt = `Write a compelling event description for a ticketing platform.
Keep it to 2-3 short paragraphs. Be enthusiastic but not over the top.
Include practical details naturally.

Event details:
- Artist/Event: ${eventData.title}
- Genre: ${eventData.genre}
- Venue: ${eventData.venueName}, ${eventData.city}
- Date: ${eventData.date}
- Price range: ${eventData.priceRange}
${eventData.artistBio ? `- Artist bio: ${eventData.artistBio}` : ''}
${eventData.specialNotes ? `- Special notes: ${eventData.specialNotes}` : ''}

Write the description:`;

  const response = await openai.chat.completions.create({
    model: 'gpt-4o-mini',  // Cheaper model for content generation
    messages: [
      {
        role: 'system',
        content: 'You are a copywriter for TicketPulse, a live events platform. Write engaging event descriptions that make people want to buy tickets. Be concise and specific.'
      },
      { role: 'user', content: prompt }
    ],
    max_tokens: 300,
    temperature: 0.7  // Some creativity, not too wild
  });

  return response.choices[0].message.content.trim();
}

// Usage
const description = await generateEventDescription({
  title: 'Blue Note All-Stars',
  genre: 'Jazz',
  venueName: 'The Blue Note',
  city: 'New York',
  date: 'March 28, 2026',
  priceRange: '$45-$85',
  artistBio: 'A rotating ensemble of legendary jazz musicians',
  specialNotes: 'Two shows: 8pm and 10:30pm. Full dinner menu available.'
});

console.log(description);
```

### Cost Awareness

```
gpt-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
A description prompt: ~300 input tokens, ~200 output tokens
Cost per description: ~$0.00017

1000 events/month = $0.17/month -- negligible
```

Use `gpt-4o-mini` for content generation, not `gpt-4o`. The quality difference for marketing copy is minimal, and the cost difference is 10-20x.

### Human-in-the-Loop

Never publish AI-generated content without review:

```javascript
async function createEventWithAIDescription(eventData) {
  const aiDescription = await generateEventDescription(eventData);

  // Store as a draft, not the published description
  await db.query(
    `UPDATE events
     SET ai_generated_description = $1,
         description_status = 'draft'
     WHERE id = $2`,
    [aiDescription, eventData.id]
  );

  // Notify the event organizer to review
  await notifyOrganizer(eventData.organizerId, {
    message: 'We generated a description for your event. Please review and edit.',
    eventId: eventData.id,
    draftDescription: aiDescription
  });
}
```

---

## 3. Build: TicketPulse Chatbot

"Help me find something to do this weekend." A chatbot that understands natural language and responds with real TicketPulse events.

### Architecture

```
User: "What jazz events are happening this weekend?"
        │
        ▼
  Retrieve relevant events (RAG)
        │
        ▼
  Inject events into LLM prompt as context
        │
        ▼
  LLM generates a conversational response
        │
        ▼
  "Great news! There are 3 jazz events this weekend: ..."
```

This is RAG applied to conversation. The LLM never "makes up" events -- it only talks about events that were retrieved from the database.

### Build: Chat Endpoint

```javascript
async function chat(userId, message, conversationHistory = []) {
  // Step 1: Extract intent and filters from the user's message
  // (Use the LLM itself to parse the natural language)
  const extractionResponse = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      {
        role: 'system',
        content: `Extract search parameters from the user's message about finding events.
Return JSON with these optional fields:
- query: string (the core search intent)
- city: string (if a location is mentioned)
- dateFrom: string (ISO date, if a date range is mentioned)
- dateTo: string (ISO date)
- genre: string (if a specific genre is mentioned)
- maxPrice: number (if a budget is mentioned)

Today's date is ${new Date().toISOString().split('T')[0]}.
"This weekend" means the coming Saturday and Sunday.`
      },
      { role: 'user', content: message }
    ],
    response_format: { type: 'json_object' },
    max_tokens: 150
  });

  let filters = {};
  try {
    filters = JSON.parse(extractionResponse.choices[0].message.content);
  } catch (e) {
    filters = { query: message };
  }

  // Step 2: Search for relevant events using hybrid search
  const events = await hybridSearch(
    filters.query || message,
    {
      city: filters.city,
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
      maxPrice: filters.maxPrice
    },
    5
  );

  // Step 3: Generate a conversational response with the events as context
  const eventContext = events.length > 0
    ? events.map((e, i) =>
        `${i + 1}. "${e.title}" - ${e.genre} at ${e.city} on ${e.event_date}. ${e.description?.slice(0, 100)}...`
      ).join('\n')
    : 'No events found matching the search criteria.';

  const chatResponse = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      {
        role: 'system',
        content: `You are the TicketPulse assistant. Help users find events to attend.

RULES:
1. ONLY recommend events from the provided context. NEVER make up events.
2. If no events match, say so honestly and suggest broadening the search.
3. Be conversational and enthusiastic but concise.
4. Include event names, dates, and venues when recommending.
5. If the user asks about something unrelated to events, politely redirect.

Available events:
${eventContext}`
      },
      ...conversationHistory.slice(-6), // Keep last 3 exchanges for context
      { role: 'user', content: message }
    ],
    max_tokens: 400,
    temperature: 0.7
  });

  const assistantMessage = chatResponse.choices[0].message.content;

  return {
    message: assistantMessage,
    events: events.map(e => ({ id: e.id, title: e.title, date: e.event_date })),
    conversationHistory: [
      ...conversationHistory,
      { role: 'user', content: message },
      { role: 'assistant', content: assistantMessage }
    ]
  };
}
```

### Try It

```javascript
// Simulate a conversation
let history = [];

let result = await chat('user_123', 'What jazz events are happening this weekend?', history);
console.log('Bot:', result.message);
history = result.conversationHistory;

result = await chat('user_123', 'Which one is cheapest?', history);
console.log('Bot:', result.message);
history = result.conversationHistory;

result = await chat('user_123', 'Great, how do I buy tickets for that one?', history);
console.log('Bot:', result.message);
```

---

## 4. Cost and Latency Management

LLM calls are the most expensive and slowest operations in your stack. Manage them aggressively.

### Caching

```javascript
const Redis = require('ioredis');
const redis = new Redis();
const crypto = require('crypto');

async function cachedEmbedding(text) {
  const cacheKey = `embed:${crypto.createHash('md5').update(text).digest('hex')}`;

  // Check cache first
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  // Generate embedding
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text
  });
  const embedding = response.data[0].embedding;

  // Cache for 24 hours
  await redis.set(cacheKey, JSON.stringify(embedding), 'EX', 86400);

  return embedding;
}

// Cache search results for common queries
async function cachedSearch(query, filters, limit) {
  const cacheKey = `search:${crypto.createHash('md5')
    .update(JSON.stringify({ query, filters, limit }))
    .digest('hex')}`;

  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  const results = await hybridSearch(query, filters, limit);

  // Cache for 5 minutes (events change less frequently than searches happen)
  await redis.set(cacheKey, JSON.stringify(results), 'EX', 300);

  return results;
}
```

### Model Selection

Use the right model for the right task:

| Task | Model | Why | Cost per call |
|------|-------|-----|---------------|
| Embeddings | text-embedding-3-small | Cheap, fast, good enough | ~$0.00002 |
| Filter extraction | gpt-4o-mini | Structured output, cheap | ~$0.0001 |
| Description generation | gpt-4o-mini | Creative writing, cheap | ~$0.0002 |
| Chatbot response | gpt-4o-mini | Conversational, fast | ~$0.0003 |
| Complex reasoning | gpt-4o | Only if mini fails | ~$0.005 |

Do not use gpt-4o for everything. Reserve it for tasks where gpt-4o-mini produces noticeably worse results.

### Latency Budget

```
Search flow:
  Embed query:     100-200ms
  pgvector search: 10-50ms
  Total:           110-250ms  ← acceptable

Chat flow:
  Extract filters: 300-500ms  (LLM call)
  Embed + search:  150-250ms
  Generate reply:  500-1000ms (LLM call)
  Total:           950-1750ms ← acceptable for chat, not for search
```

For the search endpoint, skip the LLM filter extraction. Parse simple filters (date, city) with regex or a lightweight parser. Use the LLM only for the chatbot where the latency is expected.

---

## 5. Guardrails

### Preventing Hallucination

The biggest risk: the chatbot recommends an event that does not exist. A user tries to buy tickets for a hallucinated event and gets frustrated.

The system prompt already says "ONLY recommend events from the provided context." But LLMs do not always follow instructions. Add a verification layer:

```javascript
async function verifiedChat(userId, message, history) {
  const result = await chat(userId, message, history);

  // Verify: every event mentioned in the response exists in the retrieved events
  const retrievedIds = new Set(result.events.map(e => e.id));
  const mentionedEvents = extractEventMentions(result.message);

  for (const mentioned of mentionedEvents) {
    const match = result.events.find(e =>
      e.title.toLowerCase().includes(mentioned.toLowerCase())
    );
    if (!match) {
      // LLM mentioned an event that was not in the search results
      console.warn(`Potential hallucination detected: "${mentioned}"`);
      // Regenerate with stricter instructions, or remove the hallucinated mention
      return await regenerateWithStricterPrompt(userId, message, result.events, history);
    }
  }

  return result;
}
```

### Content Safety

```javascript
// Prevent misuse of the chatbot
const BLOCKED_TOPICS = [
  'how to hack', 'credit card', 'personal information',
  'competitor', 'refund policy'  // Route to support, not AI
];

function prefilterMessage(message) {
  const lower = message.toLowerCase();
  for (const topic of BLOCKED_TOPICS) {
    if (lower.includes(topic)) {
      return {
        blocked: true,
        response: 'I can help you find events! For account or payment questions, please contact our support team at support@ticketpulse.com.'
      };
    }
  }
  return { blocked: false };
}
```

### Rate Limiting AI Endpoints

LLM calls are expensive. Rate limit them separately from regular API endpoints:

```javascript
const rateLimit = require('express-rate-limit');

const aiRateLimit = rateLimit({
  windowMs: 60 * 1000,  // 1 minute
  max: 10,              // 10 AI requests per minute per user
  keyGenerator: (req) => req.user.id,
  message: { error: 'Too many AI requests. Please wait a moment.' }
});

app.post('/api/chat', aiRateLimit, async (req, res) => { /* ... */ });
app.get('/api/search/semantic', aiRateLimit, async (req, res) => { /* ... */ });
```

---

## 6. Reflect: When AI Adds Value

Take 5 minutes to think through this:

> Which AI features genuinely improve the user experience? Which are just AI for AI's sake?

Consider:
- **Semantic search**: high value. Solves a real problem (natural language queries) that traditional search cannot.
- **Generated descriptions**: medium value. Saves organizer time but requires human review. Not user-facing AI.
- **Chatbot**: debatable. Is it faster than a good search bar with filters? When does conversation add value over a form?
- **Recommendation embeddings** (from M70): high value. Captures nuance that genre tags miss.

The test: would the feature be better without AI? If a well-designed filter UI solves the same problem as the chatbot, the chatbot is unnecessary complexity. AI should be invisible infrastructure that makes existing features better, not a visible gimmick.

---

## 7. Checkpoint

Before moving on, verify:

- [ ] Semantic search embeds the user's query and finds similar events via pgvector
- [ ] Hybrid search combines vector similarity (70%) with keyword matching (30%)
- [ ] The chatbot uses RAG: retrieve events first, then generate a response grounded in real data
- [ ] LLM costs are managed with caching, model selection, and rate limiting
- [ ] Guardrails prevent hallucination (verify mentioned events exist) and misuse (content filtering)
- [ ] You can articulate which AI features add genuine value vs. unnecessary complexity

---

## Summary

AI features in TicketPulse solve real problems. Semantic search understands "chill date night vibes" in a way keyword search never could. Generated descriptions save organizer time. The chatbot provides a conversational interface for imprecise queries.

But AI is not free. Every LLM call costs money, adds latency, and introduces nondeterminism. The engineering discipline is: cache aggressively, use the cheapest model that works, ground every response in real data, and verify outputs before showing them to users.

The most important AI feature is the one the user never notices: embeddings powering better search and recommendations behind the scenes. The flashiest AI feature (the chatbot) is often the least valuable. Build for substance, not spectacle.

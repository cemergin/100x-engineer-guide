# L3-M70: Recommendation Engine

> **Loop 3 (Mastery)** | Section 3B: Real-Time & Advanced Features | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M40
>
> **Source:** Chapters 10, 25 of the 100x Engineer Guide

## What You'll Learn

- Designing a recommendation strategy for TicketPulse: "Events you might like"
- Implementing collaborative filtering with a co-occurrence matrix
- Building content-based recommendations using genre and artist similarity
- Using vector embeddings and pgvector for modern semantic recommendations
- Combining multiple strategies into a hybrid recommender
- Handling the cold start problem for new users
- Measuring recommendation quality with precision, recall, and click-through rate
- A/B testing recommendation algorithms in production

## Why This Matters

A user opens TicketPulse. The homepage shows a grid of events. Without recommendations, every user sees the same thing: the most popular events, sorted by date. The jazz fan sees the same homepage as the metal fan. The user who attended three comedy shows last month gets no comedy suggestions.

"Events you might like" is the feature that transforms a search tool into a discovery platform. Spotify's Discover Weekly drives 30% of all listening. Netflix attributes $1B per year in retained revenue to its recommendation engine. Amazon's "Customers who bought this also bought" generates 35% of all purchases.

For TicketPulse, recommendations drive ticket sales by surfacing events users would not find on their own. The engineering challenge is doing this well without a PhD in machine learning.

---

## 1. Design: Recommendation Strategy (10 minutes)

Before building, think through the approaches:

### Three Fundamental Strategies

1. **Collaborative filtering**: "Users who attended X also attended Y" -- uses behavior patterns across users
2. **Content-based**: "You like jazz, here are more jazz events" -- uses item attributes
3. **Embedding-based**: encode events and users as vectors in a shared space, find nearest neighbors

Each has strengths and weaknesses. Think:
- What data does each approach need?
- Which works for a brand-new user with no history?
- Which works for a brand-new event with no attendees?
- Which captures subtle preferences (a user who likes "intimate jazz venues" not just "jazz")?

### 🤔 Prediction Prompt

Before reading the implementations, think: which strategy works for a brand-new user with zero history? Which works for a brand-new event with zero attendees? Your answers determine which strategies you combine.

Write down your initial design, then continue.

---

## 2. Collaborative Filtering: Co-Occurrence

The simplest collaborative filter: for each pair of events, count how many users attended both. Events that frequently co-occur in users' histories are likely to appeal to similar audiences.

### Build: Co-Occurrence Matrix

```sql
-- User attendance history
CREATE TABLE user_attendance (
    user_id   BIGINT NOT NULL,
    event_id  VARCHAR(50) NOT NULL,
    attended_at TIMESTAMP,
    PRIMARY KEY (user_id, event_id)
);

-- Compute co-occurrence: for every pair of events,
-- how many users attended both?
CREATE MATERIALIZED VIEW event_cooccurrence AS
SELECT
    a.event_id AS event_a,
    b.event_id AS event_b,
    COUNT(*) AS shared_users
FROM user_attendance a
JOIN user_attendance b
  ON a.user_id = b.user_id
  AND a.event_id < b.event_id  -- avoid duplicates and self-pairs
GROUP BY a.event_id, b.event_id
HAVING COUNT(*) >= 3;  -- minimum threshold to reduce noise

CREATE INDEX idx_cooccurrence_a ON event_cooccurrence(event_a, shared_users DESC);
CREATE INDEX idx_cooccurrence_b ON event_cooccurrence(event_b, shared_users DESC);
```

### Querying Recommendations

```javascript
async function getCollaborativeRecommendations(userId, limit = 10) {
  // Step 1: Get the user's attended events
  const attended = await db.query(
    `SELECT event_id FROM user_attendance WHERE user_id = $1`,
    [userId]
  );
  const attendedIds = attended.rows.map(r => r.event_id);

  if (attendedIds.length === 0) return []; // Cold start -- no history

  // Step 2: Find events with highest co-occurrence with user's history
  // Exclude events the user already attended
  const recommendations = await db.query(
    `SELECT
       CASE
         WHEN event_a = ANY($1::varchar[]) THEN event_b
         ELSE event_a
       END AS recommended_event,
       SUM(shared_users) AS score
     FROM event_cooccurrence
     WHERE (event_a = ANY($1::varchar[]) OR event_b = ANY($1::varchar[]))
       AND NOT (event_a = ANY($1::varchar[]) AND event_b = ANY($1::varchar[]))
     GROUP BY recommended_event
     ORDER BY score DESC
     LIMIT $2`,
    [attendedIds, limit]
  );

  return recommendations.rows;
}
```

**How to read this**: if user attended events [A, B, C], and the co-occurrence table shows (A, D) = 15 shared users, (B, D) = 8 shared users, (A, E) = 3 shared users, then event D gets a score of 23 (15 + 8) and event E gets 3. D is the stronger recommendation.

### Refresh Strategy

The materialized view is expensive to compute. Refresh it on a schedule, not in real time:

```sql
-- Refresh nightly at 3 AM
REFRESH MATERIALIZED VIEW CONCURRENTLY event_cooccurrence;
```

`CONCURRENTLY` allows reads while the refresh is in progress. The old data is served until the new computation completes.

---

## 3. Content-Based: Genre and Artist Similarity

Collaborative filtering fails when an event is brand new (no attendance data). Content-based filtering works from day one because it uses the event's own attributes.

### Build: Similarity Scoring

```sql
-- Events with their attributes
CREATE TABLE events (
    id          VARCHAR(50) PRIMARY KEY,
    title       VARCHAR(255),
    description TEXT,
    genre       VARCHAR(50),
    subgenre    VARCHAR(50),
    artist_id   VARCHAR(50),
    venue_id    VARCHAR(50),
    city        VARCHAR(100),
    price_range VARCHAR(20),  -- 'budget', 'mid', 'premium'
    event_date  DATE
);

-- Genre affinity: how much does a user like each genre?
CREATE MATERIALIZED VIEW user_genre_affinity AS
SELECT
    ua.user_id,
    e.genre,
    COUNT(*) AS attendance_count,
    COUNT(*)::float / SUM(COUNT(*)) OVER (PARTITION BY ua.user_id) AS affinity_score
FROM user_attendance ua
JOIN events e ON ua.event_id = e.id
GROUP BY ua.user_id, e.genre;
```

```javascript
async function getContentBasedRecommendations(userId, limit = 10) {
  // Get user's genre affinity profile
  const affinities = await db.query(
    `SELECT genre, affinity_score
     FROM user_genre_affinity
     WHERE user_id = $1
     ORDER BY affinity_score DESC`,
    [userId]
  );

  if (affinities.rows.length === 0) return [];

  // Get user's attended event IDs (to exclude)
  const attended = await db.query(
    `SELECT event_id FROM user_attendance WHERE user_id = $1`,
    [userId]
  );
  const attendedIds = attended.rows.map(r => r.event_id);

  // Find upcoming events matching user's genre preferences
  // Weight by genre affinity
  const recommendations = await db.query(
    `SELECT
       e.id,
       e.title,
       e.genre,
       e.event_date,
       uga.affinity_score AS genre_match,
       CASE WHEN e.city = $3 THEN 0.2 ELSE 0 END AS location_bonus,
       uga.affinity_score + CASE WHEN e.city = $3 THEN 0.2 ELSE 0 END AS total_score
     FROM events e
     JOIN user_genre_affinity uga ON uga.genre = e.genre AND uga.user_id = $1
     WHERE e.id != ALL($2::varchar[])
       AND e.event_date >= CURRENT_DATE
     ORDER BY total_score DESC, e.event_date ASC
     LIMIT $4`,
    [userId, attendedIds, userCity, limit]
  );

  return recommendations.rows;
}
```

This is crude but effective. A user who attended 5 jazz events and 1 rock event gets an affinity of 0.83 for jazz and 0.17 for rock. Upcoming jazz events score higher.

---

## 4. Embedding-Based Recommendations (Modern Approach)

Genre tags are coarse. "Jazz" includes everything from Miles Davis tributes to smooth jazz brunches. Embeddings capture semantic nuance by representing events as points in a high-dimensional vector space. Events that are similar in meaning are close together, even if they do not share the same genre tag.

### Build: Generate Event Embeddings

```javascript
const { OpenAI } = require('openai');
const openai = new OpenAI();

async function generateEventEmbedding(event) {
  // Combine relevant fields into a single text representation
  const text = [
    event.title,
    event.description,
    `Genre: ${event.genre}`,
    event.subgenre ? `Subgenre: ${event.subgenre}` : '',
    `Venue: ${event.venueName} in ${event.city}`,
    `Price range: ${event.priceRange}`
  ].filter(Boolean).join('. ');

  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',  // 1536 dimensions, cheap
    input: text
  });

  return response.data[0].embedding; // Float array, length 1536
}
```

### Store in pgvector

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to events
ALTER TABLE events ADD COLUMN embedding vector(1536);

-- Create an index for fast similarity search
CREATE INDEX idx_events_embedding ON events
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
  -- lists = sqrt(number of rows) is a good starting point
```

```javascript
// Store the embedding
async function storeEventEmbedding(eventId, embedding) {
  await db.query(
    `UPDATE events SET embedding = $1 WHERE id = $2`,
    [`[${embedding.join(',')}]`, eventId]
  );
}

// Batch process: generate and store embeddings for all events
async function embedAllEvents() {
  const events = await db.query(
    `SELECT id, title, description, genre, subgenre, venue_id, city, price_range
     FROM events WHERE embedding IS NULL`
  );

  for (const event of events.rows) {
    const embedding = await generateEventEmbedding(event);
    await storeEventEmbedding(event.id, embedding);
    console.log(`Embedded: ${event.title}`);
  }
}
```

### Build: User Preference Vector

Represent the user as the average of their attended events' embeddings:

```javascript
async function getUserPreferenceVector(userId) {
  const result = await db.query(
    `SELECT AVG(e.embedding) AS preference_vector
     FROM user_attendance ua
     JOIN events e ON ua.event_id = e.id
     WHERE ua.user_id = $1
       AND e.embedding IS NOT NULL`,
    [userId]
  );

  return result.rows[0]?.preference_vector;
}
```

### Query: Find Similar Events

```javascript
async function getEmbeddingRecommendations(userId, limit = 10) {
  const preferenceVector = await getUserPreferenceVector(userId);
  if (!preferenceVector) return [];

  const attended = await db.query(
    `SELECT event_id FROM user_attendance WHERE user_id = $1`,
    [userId]
  );
  const attendedIds = attended.rows.map(r => r.event_id);

  // Find nearest events to the user's preference vector
  const recommendations = await db.query(
    `SELECT
       id, title, genre, event_date,
       1 - (embedding <=> $1::vector) AS similarity_score
     FROM events
     WHERE id != ALL($2::varchar[])
       AND event_date >= CURRENT_DATE
       AND embedding IS NOT NULL
     ORDER BY embedding <=> $1::vector  -- cosine distance
     LIMIT $3`,
    [preferenceVector, attendedIds, limit]
  );

  return recommendations.rows;
}
```

The `<=>` operator computes cosine distance. Lower distance = more similar. `1 - distance` gives a similarity score between 0 and 1.

### Try It

```javascript
// Test: get recommendations for a user
const recs = await getEmbeddingRecommendations('user_123', 5);
console.log('Recommendations:');
for (const rec of recs) {
  console.log(`  ${rec.title} (${rec.genre}) - similarity: ${rec.similarity_score.toFixed(3)}`);
}

// Example output:
//   Blue Note Jazz Festival (jazz) - similarity: 0.923
//   Late Night Jazz at The Cellar (jazz) - similarity: 0.891
//   Acoustic Sessions: Folk & Blues (folk) - similarity: 0.834
//   Summer Jazz Brunch (jazz) - similarity: 0.812
//   Indie Folk Night (folk) - similarity: 0.789
```

Notice how the embedding approach captures cross-genre similarity (a jazz fan might also like folk/blues) that pure genre matching would miss.

---

## 5. Hybrid: Combine All Three

No single strategy is best for all users and all events. Combine them:

```javascript
async function getHybridRecommendations(userId, limit = 10) {
  // Fetch from all three strategies (in parallel)
  const [collaborative, contentBased, embedding] = await Promise.all([
    getCollaborativeRecommendations(userId, limit * 2),
    getContentBasedRecommendations(userId, limit * 2),
    getEmbeddingRecommendations(userId, limit * 2)
  ]);

  // Normalize scores to 0-1 range for each strategy
  const normalize = (items, scoreField) => {
    if (items.length === 0) return [];
    const max = Math.max(...items.map(i => i[scoreField]));
    return items.map(i => ({
      ...i,
      normalizedScore: max > 0 ? i[scoreField] / max : 0
    }));
  };

  const collabNorm = normalize(collaborative, 'score');
  const contentNorm = normalize(contentBased, 'total_score');
  const embedNorm = normalize(embedding, 'similarity_score');

  // Merge scores with weights
  const WEIGHTS = {
    collaborative: 0.4,   // Strong signal -- real behavior
    contentBased: 0.25,   // Good for new events
    embedding: 0.35       // Captures nuance
  };

  const scoreMap = new Map(); // eventId → combined score

  for (const item of collabNorm) {
    const current = scoreMap.get(item.recommended_event) || 0;
    scoreMap.set(item.recommended_event, current + item.normalizedScore * WEIGHTS.collaborative);
  }
  for (const item of contentNorm) {
    const current = scoreMap.get(item.id) || 0;
    scoreMap.set(item.id, current + item.normalizedScore * WEIGHTS.contentBased);
  }
  for (const item of embedNorm) {
    const current = scoreMap.get(item.id) || 0;
    scoreMap.set(item.id, current + item.normalizedScore * WEIGHTS.embedding);
  }

  // Sort by combined score and return top N
  const ranked = Array.from(scoreMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);

  // Fetch full event details for the top recommendations
  const eventIds = ranked.map(([id]) => id);
  const events = await db.query(
    `SELECT * FROM events WHERE id = ANY($1::varchar[])`,
    [eventIds]
  );

  // Preserve ranking order
  return eventIds.map(id => ({
    ...events.rows.find(e => e.id === id),
    score: scoreMap.get(id)
  }));
}
```

The weights (0.4, 0.25, 0.35) are starting points. You tune them based on A/B testing results -- which you will set up later.

---

## 6. Cold Start Problem

A new user has no attendance history. All three strategies return empty results.

### Fallback Strategy

```javascript
async function getRecommendations(userId, limit = 10) {
  // Check if user has enough history for personalized recommendations
  const historyCount = await db.query(
    `SELECT COUNT(*) FROM user_attendance WHERE user_id = $1`,
    [userId]
  );

  if (historyCount.rows[0].count >= 3) {
    // Enough history -- use hybrid recommendations
    return getHybridRecommendations(userId, limit);
  }

  if (historyCount.rows[0].count >= 1) {
    // Some history -- use content-based + embedding (no collaborative)
    return getFallbackRecommendations(userId, limit);
  }

  // No history -- cold start fallback
  return getColdStartRecommendations(userId, limit);
}

async function getColdStartRecommendations(userId, limit) {
  // Use signals we DO have:
  // 1. User's location (from profile or IP geolocation)
  // 2. Popular events (social proof)
  // 3. Trending events (recent ticket velocity)
  // 4. Signup context (if they came from a specific event page)

  const userProfile = await getUserProfile(userId);

  const recommendations = await db.query(
    `SELECT
       e.*,
       ts.tickets_sold_last_24h,
       ts.tickets_sold_last_24h::float / NULLIF(e.capacity, 0) AS sell_rate
     FROM events e
     LEFT JOIN ticket_stats ts ON ts.event_id = e.id
     WHERE e.event_date >= CURRENT_DATE
       AND ($1::varchar IS NULL OR e.city = $1)
     ORDER BY
       ts.tickets_sold_last_24h DESC NULLS LAST,
       e.event_date ASC
     LIMIT $2`,
    [userProfile?.city, limit]
  );

  return recommendations.rows;
}
```

Cold start is unavoidable. The best you can do is use whatever signals you have (location, trending, popularity) and quickly build a preference profile as the user interacts.

---

## 7. Observe: Recommendation Quality Metrics

How do you know if the recommendations are good?

### Key Metrics

```javascript
// Track recommendation impressions and clicks
async function trackRecommendationImpression(userId, eventId, position, algorithm) {
  await db.query(
    `INSERT INTO recommendation_impressions
     (user_id, event_id, position, algorithm, shown_at)
     VALUES ($1, $2, $3, $4, NOW())`,
    [userId, eventId, position, algorithm]
  );
}

async function trackRecommendationClick(userId, eventId, algorithm) {
  await db.query(
    `UPDATE recommendation_impressions
     SET clicked_at = NOW()
     WHERE user_id = $1 AND event_id = $2 AND algorithm = $3 AND clicked_at IS NULL`,
    [userId, eventId, algorithm]
  );
}

// Calculate metrics
async function getRecommendationMetrics(algorithm, days = 7) {
  const result = await db.query(
    `SELECT
       COUNT(*) AS impressions,
       COUNT(clicked_at) AS clicks,
       COUNT(clicked_at)::float / NULLIF(COUNT(*), 0) AS click_through_rate,
       COUNT(DISTINCT CASE WHEN ua.event_id IS NOT NULL THEN ri.event_id END) AS conversions,
       COUNT(DISTINCT CASE WHEN ua.event_id IS NOT NULL THEN ri.event_id END)::float
         / NULLIF(COUNT(clicked_at), 0) AS conversion_rate
     FROM recommendation_impressions ri
     LEFT JOIN user_attendance ua
       ON ri.user_id = ua.user_id AND ri.event_id = ua.event_id
     WHERE ri.algorithm = $1
       AND ri.shown_at >= NOW() - INTERVAL '1 day' * $2`,
    [algorithm, days]
  );

  return result.rows[0];
}
```

| Metric | What It Measures | Good Target |
|--------|-----------------|-------------|
| Click-through rate (CTR) | % of shown recommendations that were clicked | 5-15% |
| Conversion rate | % of clicked recommendations that led to a ticket purchase | 2-5% |
| Coverage | % of all events that appear in recommendations | 30-70% |
| Diversity | How varied the recommendations are (not all same genre) | Depends on user |

---

## 8. A/B Testing Recommendations

You have a hybrid recommender. But are the weights (0.4, 0.25, 0.35) optimal? Only one way to find out.

```javascript
// Simple A/B test: assign users to a variant based on their ID
function getRecommendationVariant(userId) {
  // Deterministic hash -- same user always gets same variant
  const hash = userId.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return hash % 2 === 0 ? 'control' : 'treatment';
}

async function getRecommendations(userId, limit = 10) {
  const variant = getRecommendationVariant(userId);

  if (variant === 'control') {
    // Current weights
    return getHybridRecommendations(userId, limit, { collab: 0.4, content: 0.25, embed: 0.35 });
  } else {
    // Experiment: heavier weight on embeddings
    return getHybridRecommendations(userId, limit, { collab: 0.3, content: 0.2, embed: 0.5 });
  }
}
```

After two weeks, compare CTR and conversion rate between control and treatment. If the treatment is statistically significantly better (p < 0.05), ship it as the new default.

---

## 9. Reflect: Privacy and Ethics

> What data privacy concerns exist with recommendation systems? How does GDPR apply?

Think about:
- Recommendations reveal what the system "knows" about the user
- Collaborative filtering implicitly leaks information about other users' behavior
- Users should be able to understand why an event was recommended ("Because you attended Jazz Fest 2025")
- GDPR Article 22: users have the right not to be subject to solely automated decision-making
- The filter bubble: if you only show people what they already like, they never discover new genres

---

## 10. Checkpoint

Before moving on, verify:

- [ ] Collaborative filtering uses co-occurrence of user attendance patterns
- [ ] Content-based filtering matches event attributes to user preference profiles
- [ ] Embedding-based filtering captures semantic similarity via vector space proximity
- [ ] The hybrid approach normalizes and combines scores from all three strategies
- [ ] Cold start falls back to popularity + location for new users
- [ ] pgvector stores and queries embeddings efficiently
- [ ] You can measure recommendation quality (CTR, conversion rate, coverage)

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Summary

TicketPulse now has "Events you might like." Three strategies cover different scenarios: collaborative filtering leverages crowd wisdom, content-based filtering works for new events, and embedding-based filtering captures semantic nuance. The hybrid approach combines all three with tunable weights.

The cold start problem is handled with fallbacks. Quality is measured with click-through and conversion rates. A/B testing determines optimal weights.

The recommendation engine is a perfect example of "start simple, iterate with data." A co-occurrence matrix in SQL gets you 80% of the way. Embeddings add the remaining nuance. ### 🤔 Reflection Prompt

Did the "start simple, iterate with data" approach change how you think about building ML-adjacent features? Where in your own work have you over-engineered a solution that a simple SQL query would have handled?

The hardest part is not the algorithm -- it is building the feedback loop that tells you whether the recommendations are actually good.

## Key Terms

| Term | Definition |
|------|-----------|
| **Collaborative filtering** | A recommendation technique that suggests items based on the preferences of similar users. |
| **Content-based** | A recommendation technique that suggests items similar to those a user has previously liked, based on item attributes. |
| **Embedding** | A dense numerical vector representation of an item or user in a continuous space, capturing semantic similarity. |
| **Cold start** | The challenge of generating recommendations for new users or items with little or no interaction data. |
| **pgvector** | A PostgreSQL extension that adds vector data types and similarity-search indexes for embedding-based queries. |

---

## What's Next

Next up: **[L3-M71: AI-Powered Features](L3-M71-ai-powered-features.md)** -- you will integrate LLMs and AI capabilities into TicketPulse, from semantic search to natural-language event descriptions.

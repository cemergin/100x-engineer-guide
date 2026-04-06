# L2-M42: Graph Databases

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L2-M37, L2-M34 (Kafka)
>
> **Source:** Chapter 24 of the 100x Engineer Guide

## What You'll Learn
- When graph databases solve problems that relational databases can't handle well
- How to model TicketPulse's social features as a property graph
- Cypher query language fundamentals: creating nodes, relationships, and pattern matching
- How to build "friends attending this event" and recommendation queries
- The same queries in SQL vs Cypher — and when each is appropriate
- Hybrid architecture: Postgres for CRUD, Neo4j for relationships, Kafka CDC for sync

## Why This Matters
TicketPulse wants social features: "3 of your friends are attending this event," "events your friends are going to," and "artists similar to ones you've seen." These are all **relationship queries** — and relationships are exactly where relational databases (ironically) struggle. A "friends of friends who attended similar events" query requires 4+ self-JOINs in SQL, becoming both unreadable and slow. A graph database handles it with a single traversal pattern. This module teaches you when to reach for a graph database and how to integrate it alongside your existing Postgres.

## Prereq Check

You should have TicketPulse running with Postgres and Kafka from previous modules.

```bash
docker compose ps
# Verify postgres and kafka are running
```

---

> **Before you continue:** How many SQL JOINs would you need to find "friends-of-friends who attended the same events as me"? Write down your estimate before seeing the comparison.

## Part 1: Why Graphs? (5 min)

### The Relationship Problem

Consider this TicketPulse query: "Find friends of Alice who are attending the Taylor Swift concert, and also find friends-of-friends attending."

**In SQL:**
```sql
-- Friends attending (1 hop)
SELECT DISTINCT u2.name
FROM users u1
JOIN friendships f ON u1.id = f.user_id
JOIN users u2 ON f.friend_id = u2.id
JOIN ticket_purchases tp ON u2.id = tp.user_id
JOIN events e ON tp.event_id = e.id
WHERE u1.name = 'Alice'
  AND e.name = 'Taylor Swift NYC';

-- Friends-of-friends attending (2 hops)
SELECT DISTINCT u3.name
FROM users u1
JOIN friendships f1 ON u1.id = f1.user_id
JOIN users u2 ON f1.friend_id = u2.id
JOIN friendships f2 ON u2.id = f2.user_id
JOIN users u3 ON f2.friend_id = u3.id
JOIN ticket_purchases tp ON u3.id = tp.user_id
JOIN events e ON tp.event_id = e.id
WHERE u1.name = 'Alice'
  AND e.name = 'Taylor Swift NYC'
  AND u3.id != u1.id;
-- Already 7 JOINs for 2 hops. 3 hops? 10+ JOINs.
```

**In Cypher (Neo4j):**
```cypher
// Friends and friends-of-friends attending (1-2 hops — one query)
MATCH (alice:User {name: "Alice"})-[:FRIENDS*1..2]-(friend)-[:ATTENDING]->(event:Event {name: "Taylor Swift NYC"})
WHERE friend <> alice
RETURN DISTINCT friend.name, length(shortestPath((alice)-[:FRIENDS*]-(friend))) AS hops
```

The SQL version gets exponentially more complex with each hop. The Cypher version stays readable regardless of depth.

### Key Insight: Where the Cost Lives

In a relational database, the cost of a JOIN is proportional to **table sizes**. In a graph database, the cost of a traversal is proportional to the **local neighborhood** — it doesn't matter if you have 1 billion users if Alice only has 200 friends.

---

## Part 2: Deploy Neo4j (5 min)

### 🚀 Deploy: Add Neo4j to Docker Compose

Add to your `docker-compose.yml`:

```yaml
  neo4j:
    image: neo4j:5-community
    environment:
      - NEO4J_AUTH=neo4j/ticketpulse
      - NEO4J_PLUGINS=["apoc"]
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol
    volumes:
      - neo4j-data:/data

volumes:
  neo4j-data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

```bash
docker compose up -d neo4j

# Wait for it to start
docker compose logs -f neo4j
# Look for "Started."
```

### 🔍 Try It: Open the Neo4j Browser

Open http://localhost:7474 in your browser. Connect with:
- Username: `neo4j`
- Password: `ticketpulse`

You'll see an interactive query interface where you can write Cypher queries and see results as visual graphs. This is one of Neo4j's great strengths — you can literally see the relationships.

---

## Part 3: Model TicketPulse Social Data (15 min)

### 🛠️ Build: Create the Graph Schema

<details>
<summary>💡 Hint 1: Direction</summary>
Start with uniqueness constraints on node IDs (User.id, Event.id, Artist.id, Venue.id). These also create indexes for fast lookups.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Add indexes on properties you search by frequently (User.name, Event.name). Constraints prevent duplicate nodes if you accidentally run the creation script twice.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use CREATE CONSTRAINT ... IF NOT EXISTS for idempotency and CREATE INDEX ... IF NOT EXISTS for the name lookups. Create the schema before loading data.
</details>

In the Neo4j browser (or via `cypher-shell`), create TicketPulse's social graph:

```cypher
// Create constraints and indexes first
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT artist_id IF NOT EXISTS FOR (a:Artist) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT venue_id IF NOT EXISTS FOR (v:Venue) REQUIRE v.id IS UNIQUE;

CREATE INDEX user_name IF NOT EXISTS FOR (u:User) ON (u.name);
CREATE INDEX event_name IF NOT EXISTS FOR (e:Event) ON (e.name);
```


<details>
<summary>💡 Hint 1: Direction</summary>
A graph schema defines node labels (User, Event, Artist) and relationship types (FRIENDS, ATTENDING, PERFORMED_AT). Nodes have properties; relationships can too.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Create uniqueness constraints on node IDs first: `CREATE CONSTRAINT FOR (u:User) REQUIRE u.id IS UNIQUE`. This also creates an index for fast lookups.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use `MERGE` instead of `CREATE` when populating to avoid duplicates: `MERGE (u:User {id: 1}) SET u.name = 'Alice'`. Relationships use the same pattern: `MATCH (u1:User {id: 1}), (u2:User {id: 2}) MERGE (u1)-[:FRIENDS]-(u2)`.
</details>

### 🛠️ Build: Populate the Graph

<details>
<summary>💡 Hint 1: Direction</summary>
Use `CREATE` to build the initial dataset: Users, Venues, Artists, Events. Then add relationships: `(event)-[:AT]->(venue)`, `(event)-[:FEATURING]->(artist)`, `(user)-[:FRIENDS]->(user)`, `(user)-[:ATTENDING]->(event)`.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `MERGE` instead of `CREATE` when you might run the script twice -- MERGE is idempotent (creates only if the node does not exist). Relationships can carry properties too: `[:FRIENDS {since: date("2023-01-15")}]`.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Create enough data to make queries interesting: 8 users, 4 events, bidirectional friendships, and varied attendance. Include both `:ATTENDING` (future events) and `:ATTENDED` (past events) relationship types so recommendation queries have data to work with.
</details>


```cypher
// Create users
CREATE (alice:User {id: 1, name: "Alice", email: "alice@example.com"})
CREATE (bob:User {id: 2, name: "Bob", email: "bob@example.com"})
CREATE (carol:User {id: 3, name: "Carol", email: "carol@example.com"})
CREATE (dave:User {id: 4, name: "Dave", email: "dave@example.com"})
CREATE (eve:User {id: 5, name: "Eve", email: "eve@example.com"})
CREATE (frank:User {id: 6, name: "Frank", email: "frank@example.com"})
CREATE (grace:User {id: 7, name: "Grace", email: "grace@example.com"})
CREATE (henry:User {id: 8, name: "Henry", email: "henry@example.com"})

// Create venues
CREATE (msg:Venue {id: 1, name: "Madison Square Garden", city: "New York"})
CREATE (forum:Venue {id: 2, name: "The Forum", city: "Los Angeles"})
CREATE (redrocks:Venue {id: 3, name: "Red Rocks", city: "Denver"})

// Create artists
CREATE (taylor:Artist {id: 1, name: "Taylor Swift", genre: "pop"})
CREATE (kendrick:Artist {id: 2, name: "Kendrick Lamar", genre: "hip-hop"})
CREATE (norah:Artist {id: 3, name: "Norah Jones", genre: "jazz"})
CREATE (radiohead:Artist {id: 4, name: "Radiohead", genre: "rock"})

// Create events
CREATE (tsConcert:Event {id: 1, name: "Taylor Swift NYC", date: date("2024-06-15")})
CREATE (klConcert:Event {id: 2, name: "Kendrick Lamar LA", date: date("2024-07-20")})
CREATE (njConcert:Event {id: 3, name: "Norah Jones Denver", date: date("2024-08-10")})
CREATE (rhConcert:Event {id: 4, name: "Radiohead NYC", date: date("2024-09-05")})

// Link events to venues and artists
CREATE (tsConcert)-[:AT]->(msg)
CREATE (klConcert)-[:AT]->(forum)
CREATE (njConcert)-[:AT]->(redrocks)
CREATE (rhConcert)-[:AT]->(msg)

CREATE (tsConcert)-[:FEATURING]->(taylor)
CREATE (klConcert)-[:FEATURING]->(kendrick)
CREATE (njConcert)-[:FEATURING]->(norah)
CREATE (rhConcert)-[:FEATURING]->(radiohead)

// Create friendships (bidirectional)
CREATE (alice)-[:FRIENDS {since: date("2023-01-15")}]->(bob)
CREATE (alice)-[:FRIENDS {since: date("2023-03-20")}]->(carol)
CREATE (bob)-[:FRIENDS {since: date("2023-06-10")}]->(dave)
CREATE (carol)-[:FRIENDS {since: date("2023-02-28")}]->(eve)
CREATE (dave)-[:FRIENDS {since: date("2023-08-15")}]->(frank)
CREATE (eve)-[:FRIENDS {since: date("2023-04-01")}]->(grace)
CREATE (frank)-[:FRIENDS {since: date("2023-09-20")}]->(henry)
CREATE (bob)-[:FRIENDS {since: date("2023-07-05")}]->(carol)
CREATE (grace)-[:FRIENDS {since: date("2023-11-10")}]->(henry)

// Create event attendance
CREATE (alice)-[:ATTENDING {purchased_at: datetime("2024-05-01T10:30:00")}]->(tsConcert)
CREATE (bob)-[:ATTENDING {purchased_at: datetime("2024-05-02T14:15:00")}]->(tsConcert)
CREATE (carol)-[:ATTENDING {purchased_at: datetime("2024-06-01T09:00:00")}]->(klConcert)
CREATE (dave)-[:ATTENDING {purchased_at: datetime("2024-05-15T16:45:00")}]->(tsConcert)
CREATE (eve)-[:ATTENDING {purchased_at: datetime("2024-07-01T11:30:00")}]->(njConcert)
CREATE (frank)-[:ATTENDING {purchased_at: datetime("2024-06-10T08:00:00")}]->(klConcert)
CREATE (grace)-[:ATTENDING {purchased_at: datetime("2024-08-01T13:20:00")}]->(rhConcert)
CREATE (henry)-[:ATTENDING {purchased_at: datetime("2024-05-20T15:00:00")}]->(tsConcert)
CREATE (alice)-[:ATTENDING {purchased_at: datetime("2024-06-05T12:00:00")}]->(rhConcert)
CREATE (bob)-[:ATTENDING {purchased_at: datetime("2024-07-10T09:30:00")}]->(njConcert)

// Create past event attendance (for recommendations)
CREATE (alice)-[:ATTENDED]->(klConcert)
CREATE (bob)-[:ATTENDED]->(njConcert)
CREATE (carol)-[:ATTENDED]->(tsConcert)
CREATE (dave)-[:ATTENDED]->(klConcert)
```

### 🔍 Try It: Visualize the Graph

In the Neo4j browser, run:

```cypher
// See the entire graph
MATCH (n)-[r]->(m)
RETURN n, r, m
```

You should see a visual graph with nodes (circles) and relationships (arrows). Click on nodes and relationships to see their properties. Drag nodes around to explore the structure.

This visual representation is one of graph databases' superpowers — you can literally see the data model and how entities connect.

---

## Part 4: Build Social Features (20 min)

### 🛠️ Build: "Friends Attending This Event"

The most requested social feature: when a user views an event, show which of their friends are going.

<details>
<summary>💡 Hint 1: Direction</summary>
The Cypher pattern is: (me)-[:FRIENDS]-(friend)-[:ATTENDING]->(event). This traverses from a user through friendship to attendance at a specific event.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use pattern matching with properties to filter: {name: 'Alice'} for the user and {name: 'Taylor Swift NYC'} for the event.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The result shows direct friends only. For friends-of-friends, use variable-length paths: [:FRIENDS*1..2] and add WHERE friend <> alice to exclude self-matches.
</details>

```cypher
// Friends of Alice attending "Taylor Swift NYC"
MATCH (me:User {name: "Alice"})-[:FRIENDS]-(friend)-[:ATTENDING]->(event:Event {name: "Taylor Swift NYC"})
RETURN friend.name AS friend_name, event.name AS event_name
```

Run this in Neo4j browser. You should see Bob and Dave (Alice's direct friends who are attending).

### 🛠️ Build: "Events Your Friends Are Attending"

<details>
<summary>💡 Hint 1: Direction</summary>
The pattern is: `(me)-[:FRIENDS]-(friend)-[:ATTENDING]->(event)`. Add `WHERE NOT (me)-[:ATTENDING]->(event)` to exclude events Alice is already attending -- only show new recommendations.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `collect(friend.name)` to aggregate all friends going to each event into a list, and `count(friend)` to sort by social proof. An event with 3 friends attending ranks higher than one with 1.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
ORDER BY `friend_count DESC` to show the most socially compelling events first. This is a natural recommendation: "3 friends are going to Kendrick Lamar LA" is more compelling than a generic "popular event" ranking.
</details>


```cypher
// All events that Alice's friends are attending (that Alice is NOT attending)
MATCH (me:User {name: "Alice"})-[:FRIENDS]-(friend)-[:ATTENDING]->(event:Event)
WHERE NOT (me)-[:ATTENDING]->(event)
RETURN event.name AS event_name,
       event.date AS event_date,
       collect(friend.name) AS friends_going,
       count(friend) AS friend_count
ORDER BY friend_count DESC
```

This returns events ranked by how many of Alice's friends are attending. It's a natural recommendation: "2 friends are going to Kendrick Lamar LA" is more compelling than "1 friend is going to Norah Jones Denver."

### 🛠️ Build: "Artists Similar to Ones You've Seen"

<details>
<summary>💡 Hint 1: Direction</summary>
This is collaborative filtering via graph traversal: find users who attended the same events as Alice, then find what other events (and artists) those users attended. The overlap reveals "similar taste."
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Three MATCH clauses chained with WITH: (1) collect Alice's known artists, (2) find other users who share events with Alice, (3) find what those users attended that Alice has not. Use `WHERE NOT recArtist IN myArtists` to exclude artists Alice already knows.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Rank by `count(DISTINCT other)` -- the number of users with shared taste who also attended the recommended artist. This is the "shared audience count." Higher means stronger signal. Use `ATTENDING|ATTENDED` (pipe = OR) to match both future and past events in the traversal.
</details>


Recommendation via shared attendees: if people who went to Event A also went to Event B, the artists at those events are "similar."

```cypher
// Artists that Alice might like based on shared audience
MATCH (me:User {name: "Alice"})-[:ATTENDING|ATTENDED]->(myEvent:Event)-[:FEATURING]->(myArtist:Artist)
WITH me, collect(DISTINCT myArtist) AS myArtists

// Find other users who attended the same events as Alice
MATCH (me)-[:ATTENDING|ATTENDED]->(sharedEvent:Event)<-[:ATTENDING|ATTENDED]-(other:User)
WHERE other <> me

// Find what those users also attended
MATCH (other)-[:ATTENDING|ATTENDED]->(otherEvent:Event)-[:FEATURING]->(recArtist:Artist)
WHERE NOT recArtist IN myArtists  // Exclude artists Alice already knows

RETURN recArtist.name AS recommended_artist,
       recArtist.genre AS genre,
       count(DISTINCT other) AS shared_audience_count
ORDER BY shared_audience_count DESC
LIMIT 5
```

This is collaborative filtering via graph traversal — the same concept Spotify and Netflix use, but expressed as a graph pattern instead of a matrix factorization algorithm.

### 🔍 Try It: Run Each Query

Run all three queries in the Neo4j browser. Notice:
- The visual result shows the traversal paths
- You can click "Table" view to see structured results
- Query times are in the low milliseconds (even these toy examples)

### Integrate with TicketPulse's API

```javascript
// src/services/social-service/routes/friends.js
const neo4j = require('neo4j-driver');

const driver = neo4j.driver(
  'bolt://neo4j:7687',
  neo4j.auth.basic('neo4j', 'ticketpulse')
);

// GET /api/events/:eventId/friends-attending
router.get('/api/events/:eventId/friends-attending', async (req, res) => {
  const session = driver.session();

  try {
    const result = await session.run(
      `MATCH (me:User {id: $userId})-[:FRIENDS]-(friend)-[:ATTENDING]->(event:Event {id: $eventId})
       RETURN friend.name AS name, friend.id AS id`,
      {
        userId: neo4j.int(req.user.id),
        eventId: neo4j.int(parseInt(req.params.eventId))
      }
    );

    const friends = result.records.map(record => ({
      id: record.get('id').toNumber(),
      name: record.get('name')
    }));

    res.json({ friends_attending: friends, count: friends.length });
  } finally {
    await session.close();
  }
});

// GET /api/recommendations/events
router.get('/api/recommendations/events', async (req, res) => {
  const session = driver.session();

  try {
    const result = await session.run(
      `MATCH (me:User {id: $userId})-[:FRIENDS]-(friend)-[:ATTENDING]->(event:Event)
       WHERE NOT (me)-[:ATTENDING]->(event)
         AND event.date >= date()
       RETURN event.id AS eventId,
              event.name AS eventName,
              event.date AS eventDate,
              collect(friend.name) AS friendsGoing,
              count(friend) AS friendCount
       ORDER BY friendCount DESC
       LIMIT 10`,
      { userId: neo4j.int(req.user.id) }
    );

    const recommendations = result.records.map(record => ({
      event_id: record.get('eventId').toNumber(),
      event_name: record.get('eventName'),
      event_date: record.get('eventDate').toString(),
      friends_going: record.get('friendsGoing'),
      friend_count: record.get('friendCount').toNumber()
    }));

    res.json({ recommendations });
  } finally {
    await session.close();
  }
});
```

---

## Part 5: SQL vs Cypher Comparison (5 min)

### 🤔 Reflect: Compare the Same Query

"Find friends-of-friends who attended the same events as me, excluding direct friends."

**SQL (Postgres):**
```sql
SELECT DISTINCT u3.name AS fof_name, e.name AS shared_event
FROM users u1
-- My friends
JOIN friendships f1 ON u1.id = f1.user_id
JOIN users u2 ON f1.friend_id = u2.id
-- Friends of my friends
JOIN friendships f2 ON u2.id = f2.user_id
JOIN users u3 ON f2.friend_id = u3.id
-- Events they attended
JOIN ticket_purchases tp2 ON u3.id = tp2.user_id
JOIN events e ON tp2.event_id = e.id
-- Events I attended
JOIN ticket_purchases tp1 ON u1.id = tp1.user_id AND tp1.event_id = e.id
-- Exclude me and direct friends
WHERE u1.id = 1
  AND u3.id != u1.id
  AND u3.id NOT IN (SELECT friend_id FROM friendships WHERE user_id = u1.id)
ORDER BY u3.name;
```

**Cypher (Neo4j):**
```cypher
MATCH (me:User {id: 1})-[:FRIENDS*2]-(fof:User)-[:ATTENDED]->(event:Event)<-[:ATTENDED]-(me)
WHERE NOT (me)-[:FRIENDS]-(fof)
  AND fof <> me
RETURN DISTINCT fof.name AS fof_name, event.name AS shared_event
ORDER BY fof_name
```

Which is clearer to you? Which would be easier to modify if the requirements changed to "3 hops" instead of 2?

### When Each Shines

| Scenario | Better Choice | Why |
|----------|--------------|-----|
| CRUD operations (create event, buy ticket) | **Postgres** | ACID transactions, mature ecosystem |
| Aggregations (revenue by venue, daily stats) | **Postgres** | SQL is built for GROUP BY, SUM, AVG |
| "Friends attending this event" | **Neo4j** | 1-hop traversal, simple pattern |
| "Recommend events based on social network" | **Neo4j** | Multi-hop traversal, graph pattern matching |
| Full-text search | **Elasticsearch** | Inverted index, relevance scoring |
| Ticket inventory management | **Postgres** | Transactional integrity, strong consistency |

---

## Part 6: Design — What Goes Where? (5 min)

### 📐 Design: TicketPulse's Hybrid Architecture

<details>
<summary>💡 Hint 1: Direction</summary>
Not everything belongs in the graph. CRUD operations (creating events, buying tickets, processing payments) stay in Postgres where ACID transactions guarantee consistency. Only relationship-heavy queries go to Neo4j.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Postgres is the source of truth. Neo4j is a read-optimized projection. When a user buys a ticket in Postgres, a Kafka CDC consumer creates the `(user)-[:ATTENDING]->(event)` relationship in Neo4j. Accept eventual consistency -- social features can lag a few seconds.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The full architecture: Postgres (writes) -> Kafka CDC -> Neo4j consumer (creates/updates nodes and relationships). The API checks Neo4j for "friends attending" and "recommendations" but calls Postgres for ticket purchases, order creation, and revenue analytics (GROUP BY, SUM).
</details>


```
┌─────────────────────────────────────────────────────────────┐
│                     TicketPulse Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PostgreSQL (Source of Truth)    Neo4j (Graph Layer)          │
│  ├── events                     ├── (:User) nodes            │
│  ├── tickets                    ├── (:Event) nodes           │
│  ├── orders                     ├── (:Artist) nodes          │
│  ├── users                      ├── [:FRIENDS] relationships │
│  └── venues                     ├── [:ATTENDING] rels        │
│                                 └── [:FEATURING] rels        │
│                                                              │
│  Elasticsearch (Search)                                      │
│  └── ticketpulse-events index                               │
│                                                              │
│  Sync: Postgres → Kafka CDC → Neo4j Consumer                 │
│        Postgres → Kafka CDC → ES Consumer                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Which features belong where?

Think about this before revealing the answer:

| Feature | Where? | Why? |
|---------|--------|------|

<details>
<summary>Proposed Architecture</summary>

| Feature | Where? | Why? |
|---------|--------|------|
| Create/update events | Postgres | ACID, source of truth |
| Buy tickets | Postgres | Transactional integrity |
| Search events | Elasticsearch | Full-text, relevance, autocomplete |
| "Friends at this event" | Neo4j | Relationship traversal |
| Event recommendations | Neo4j | Collaborative filtering via graph |
| Revenue analytics | Postgres (mat view) | Aggregation, GROUP BY |
| "Artists like X" | Neo4j | Multi-hop graph traversal |
| User authentication | Postgres | Standard CRUD |
| Fraud detection (shared devices/emails) | Neo4j | Pattern detection across entities |

</details>


<details>
<summary>💡 Hint 1: Direction</summary>
Not everything belongs in the graph. CRUD operations (creating events, processing payments) stay in Postgres. Only relationship-heavy queries (recommendations, social features) use Neo4j.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Postgres is the source of truth. Neo4j is a read-optimized projection. Sync data from Postgres to Neo4j via Kafka CDC — when a user buys a ticket, a Kafka consumer creates the ATTENDING relationship in Neo4j.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The architecture is: Postgres (writes) -> Kafka CDC -> Neo4j consumer -> Neo4j (reads). The API checks Neo4j for "friends attending" and "recommendations" but calls Postgres for everything else. Accept eventual consistency — social features can be seconds behind.
</details>

### 🛠️ Build: Kafka CDC to Neo4j

<details>
<summary>💡 Hint 1: Direction</summary>
Subscribe to CDC topics: `ticketpulse.public.users`, `ticketpulse.public.events`, `ticketpulse.public.ticket_purchases`, `ticketpulse.public.friendships`. Each message contains `op` (c=create, u=update, d=delete) and `before`/`after` snapshots.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Use `MERGE` for creates/updates (idempotent -- safe to replay) and `MATCH ... DETACH DELETE` for deletes. For ticket purchases, `MATCH (u:User {id: $userId}), (e:Event {id: $eventId}) MERGE (u)-[:ATTENDING]->(e)` creates the attendance relationship.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Create a separate Kafka consumer group (`neo4j-sync-group`) so it tracks offsets independently. Use the `neo4j-driver` package with `driver.session()` per message. Always close the session in a `finally` block. Route messages to handler functions by inspecting the topic name.
</details>


Keep Neo4j in sync with Postgres changes via Kafka:

```javascript
// kafka/consumers/neo4j-sync-consumer.js
const { Kafka } = require('kafkajs');
const neo4j = require('neo4j-driver');

const kafka = new Kafka({ brokers: ['kafka:9092'] });
const consumer = kafka.consumer({ groupId: 'neo4j-sync-group' });

const driver = neo4j.driver(
  'bolt://neo4j:7687',
  neo4j.auth.basic('neo4j', 'ticketpulse')
);

async function start() {
  await consumer.connect();
  await consumer.subscribe({
    topics: [
      'ticketpulse.public.users',
      'ticketpulse.public.events',
      'ticketpulse.public.ticket_purchases',
      'ticketpulse.public.friendships'
    ],
    fromBeginning: false
  });

  await consumer.run({
    eachMessage: async ({ topic, message }) => {
      const change = JSON.parse(message.value.toString());
      const session = driver.session();

      try {
        if (topic.includes('users')) {
          await syncUser(session, change);
        } else if (topic.includes('events')) {
          await syncEvent(session, change);
        } else if (topic.includes('ticket_purchases')) {
          await syncAttendance(session, change);
        } else if (topic.includes('friendships')) {
          await syncFriendship(session, change);
        }
      } finally {
        await session.close();
      }
    }
  });
}

async function syncUser(session, change) {
  if (change.op === 'd') {
    await session.run('MATCH (u:User {id: $id}) DETACH DELETE u', {
      id: neo4j.int(change.before.id)
    });
  } else {
    const user = change.after;
    await session.run(
      `MERGE (u:User {id: $id})
       SET u.name = $name, u.email = $email`,
      { id: neo4j.int(user.id), name: user.name, email: user.email }
    );
  }
}

async function syncEvent(session, change) {
  if (change.op === 'd') {
    await session.run('MATCH (e:Event {id: $id}) DETACH DELETE e', {
      id: neo4j.int(change.before.id)
    });
  } else {
    const event = change.after;
    await session.run(
      `MERGE (e:Event {id: $id})
       SET e.name = $name, e.date = date($date)`,
      {
        id: neo4j.int(event.id),
        name: event.name,
        date: event.event_date.split('T')[0]
      }
    );
  }
}

async function syncAttendance(session, change) {
  if (change.op === 'c' || change.op === 'u') {
    const purchase = change.after;
    await session.run(
      `MATCH (u:User {id: $userId}), (e:Event {id: $eventId})
       MERGE (u)-[:ATTENDING {purchased_at: datetime()}]->(e)`,
      {
        userId: neo4j.int(purchase.user_id),
        eventId: neo4j.int(purchase.event_id)
      }
    );
  }
}

async function syncFriendship(session, change) {
  if (change.op === 'c') {
    const friendship = change.after;
    await session.run(
      `MATCH (u1:User {id: $userId}), (u2:User {id: $friendId})
       MERGE (u1)-[:FRIENDS {since: date()}]->(u2)`,
      {
        userId: neo4j.int(friendship.user_id),
        friendId: neo4j.int(friendship.friend_id)
      }
    );
  } else if (change.op === 'd') {
    const friendship = change.before;
    await session.run(
      `MATCH (u1:User {id: $userId})-[r:FRIENDS]-(u2:User {id: $friendId})
       DELETE r`,
      {
        userId: neo4j.int(friendship.user_id),
        friendId: neo4j.int(friendship.friend_id)
      }
    );
  }
}

start().catch(console.error);
```

This pattern — Postgres as source of truth, Kafka CDC for replication, Neo4j as a derived view — is how production systems add graph capabilities without replacing their primary database.

---

## Part 7: Performance Considerations (5 min)

### Graph Query Performance Tips

1. **Always constrain traversal depth**: Use `*1..5` not `*` (unbounded traversals can explore the entire graph)
2. **Index properties you search by**: Every MATCH pattern's starting node should be findable via index
3. **Profile your queries**: Use `PROFILE` to see the query plan

```cypher
// See the execution plan and actual costs
PROFILE
MATCH (me:User {name: "Alice"})-[:FRIENDS*1..2]-(friend)-[:ATTENDING]->(event:Event)
RETURN friend.name, event.name
```

4. **Beware of super-nodes**: A user with 1 million friends is a "super-node" that makes every traversal through it expensive. Strategies: partition relationships by time, use intermediate nodes, or filter early in the query.

5. **Batch writes**: For initial data load, use `UNWIND` instead of individual CREATE statements:

```cypher
// Batch create users from a list
UNWIND $users AS userData
CREATE (u:User {id: userData.id, name: userData.name, email: userData.email})
```

### When NOT to Use a Graph Database

- **Simple CRUD** with no relationship queries — Postgres is simpler and more mature
- **Heavy aggregations** (SUM, AVG, GROUP BY) — graph databases are weak at analytics
- **Time-series data** — use TimescaleDB, InfluxDB, or Clickhouse
- **Full-text search** — use Elasticsearch
- **If your queries are always "get entity by ID"** — a key-value store is simpler

---

## 🤔 Reflect: The Hybrid Decision

For each of these potential TicketPulse features, think about where you'd implement it:

1. **"People who bought tickets to Event A also bought tickets to Event B"** — Where?
2. **"Total revenue by venue for the last 30 days"** — Where?
3. **"Find events matching 'jazz in New York'"** — Where?
4. **"Suggest friends based on mutual event attendance"** — Where?
5. **"Update a ticket's status from 'reserved' to 'sold'"** — Where?

<details>
<summary>Discussion</summary>

1. **Neo4j** — This is collaborative filtering via graph traversal. `(buyer)-[:PURCHASED]->(eventA)<-[:PURCHASED]-(other)-[:PURCHASED]->(eventB)`. Classic graph query.
2. **Postgres** (materialized view) — Pure aggregation. `SUM(amount) GROUP BY venue_id`.
3. **Elasticsearch** — Full-text search with filtering. The inverted index handles "jazz" and the keyword field handles "New York."
4. **Neo4j** — Mutual attendance is a graph pattern: `(u1)-[:ATTENDED]->(event)<-[:ATTENDED]-(u2)` where the count of shared events determines suggestion strength.
5. **Postgres** — CRUD with ACID transactions. Ticket purchases need transactional guarantees.

</details>

---

> **What did you notice?** When you visualized the graph in Neo4j's browser, did the relationship patterns become more intuitive than looking at SQL tables? Did the Cypher queries feel easier to read than the equivalent multi-JOIN SQL?

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Property graph model** | Nodes (entities) + Relationships (connections) + Properties (key-value on both). |
| **Cypher** | Pattern matching language. `MATCH (a)-[:REL]->(b) RETURN b`. Reads like ASCII art. |
| **Graph vs SQL** | Graph: relationship traversal in constant time per hop. SQL: JOINs scale with table size. |
| **Friends at event** | One-hop traversal: `(me)-[:FRIENDS]-(friend)-[:ATTENDING]->(event)`. |
| **Recommendations** | Multi-hop: shared attendance patterns → collaborative filtering. |
| **Hybrid architecture** | Postgres for CRUD, Neo4j for relationships, ES for search, Kafka CDC for sync. |
| **When NOT to graph** | Simple CRUD, aggregations, time-series, full-text search. |

**The key insight**: You don't replace Postgres with Neo4j. You augment it. Each database does what it's best at, and Kafka CDC keeps them in sync.

## What's Next

Section 2B is complete. You've built a deep understanding of database performance — from Postgres internals and connection pooling, through advanced SQL analytics, search engineering, N+1 detection, and graph databases. In **Section 2C**, you'll tackle observability and reliability: distributed tracing, monitoring, and making TicketPulse production-ready.

## Key Terms

| Term | Definition |
|------|-----------|
| **Graph database** | A database optimized for storing and querying data modeled as nodes and edges (relationships). |
| **Node** | An entity in a graph database, representing a person, place, thing, or concept. |
| **Edge** | A relationship connecting two nodes in a graph database, often with a type and properties. |
| **Cypher** | A declarative query language for graph databases, used primarily with Neo4j. |
| **Neo4j** | A popular open-source graph database that uses the property graph model and the Cypher query language. |
| **Traversal** | The process of navigating from node to node along edges to answer a graph query. |

## 📚 Further Reading
- [Neo4j Getting Started](https://neo4j.com/docs/getting-started/)
- Chapter 24 of the 100x Engineer Guide: Section 10 — Graph Databases
- [Graph Databases (free O'Reilly book)](https://neo4j.com/graph-databases-book/)
- [Cypher Reference Card](https://neo4j.com/docs/cypher-refcard/current/)
- [Neo4j + Kafka Integration](https://neo4j.com/labs/kafka/)

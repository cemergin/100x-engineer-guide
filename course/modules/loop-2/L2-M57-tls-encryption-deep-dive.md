# L2-M57: TLS & Encryption Deep Dive

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L1-M04, L2-M56
>
> **Source:** Chapter 21 of the 100x Engineer Guide

## What You'll Learn

- The TLS 1.3 handshake, step by step -- what each message contains and why
- How to watch a real TLS handshake with `openssl s_client`
- How to generate self-signed certificates and configure HTTPS
- Mutual TLS (mTLS) for service-to-service communication
- Certificate chain validation, Let's Encrypt, and cert-manager in Kubernetes
- How to measure and optimize TLS handshake latency

## Why This Matters

Every TicketPulse service-to-service call carries sensitive data: user tokens, payment information, ticket inventory. If any of that traffic is unencrypted, anyone on the same network can read it. In cloud environments, "the same network" might include other tenants on the same physical host. TLS is not optional -- it is the baseline for production systems.

But TLS is also one of the most common sources of production outages. Certificate expiration, misconfigured certificate chains, missing intermediates, and mTLS misconfigurations cause real incidents. Understanding how TLS works -- not just that it works -- is what lets you debug these problems at 3 AM.

## Prereq Check

You need `openssl` installed (it ships with macOS and most Linux distributions):

```bash
openssl version
# Should output: OpenSSL 3.x.x or LibreSSL 3.x.x

# Verify curl is available with TLS support
curl --version | head -1
# Should mention OpenSSL or LibreSSL
```

---

## Part 1: Watching a TLS Handshake in Real Time

### 🔍 Try It: Connect to a Real Server

```bash
openssl s_client -connect api.github.com:443 -servername api.github.com
```

This opens a TLS connection and prints every detail of the handshake. Let's read the output section by section.

**Section 1: Connection Establishment**

```
CONNECTED(00000005)
```

TCP connection established. Now the TLS handshake begins.

**Section 2: Certificate Chain**

```
depth=2 C = US, O = DigiCert Inc, OU = www.digicert.com, CN = DigiCert Global Root G2
verify return:1
depth=1 C = US, O = DigiCert Inc, CN = DigiCert TLS Hybrid ECC SHA384 2020 CA1
verify return:1
depth=0 C = US, ST = California, L = San Francisco, O = "GitHub, Inc.", CN = github.com
verify return:1
```

Three certificates in the chain:
- **depth=0**: The leaf certificate for github.com (the one the server presents)
- **depth=1**: The intermediate CA that signed the leaf
- **depth=2**: The root CA in your trust store

`verify return:1` means each certificate verified successfully.

**Section 3: Server Certificate Details**

```
Server certificate
-----BEGIN CERTIFICATE-----
MIIE... (base64 encoded certificate)
-----END CERTIFICATE-----
subject=C = US, ST = California, L = San Francisco, O = "GitHub, Inc.", CN = github.com
issuer=C = US, O = DigiCert Inc, CN = DigiCert TLS Hybrid ECC SHA384 2020 CA1
```

**Section 4: TLS Session Parameters**

```
SSL-Session:
    Protocol  : TLSv1.3
    Cipher    : TLS_AES_128_GCM_SHA256
    Session-ID: ...
    ...
    Start Time: 1711316400
    Timeout   : 7200 (sec)
    Verify return code: 0 (ok)
```

This tells you:
- **Protocol**: TLS 1.3 was negotiated
- **Cipher**: AES-128-GCM with SHA-256 (fast, secure, hardware-accelerated on modern CPUs)
- **Verify return code: 0 (ok)**: The certificate chain is valid

### 🔍 Try It: Check Certificate Expiration

```bash
echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null \
  | openssl x509 -noout -dates

# Output:
# notBefore=Feb 14 00:00:00 2024 GMT
# notAfter=Mar 14 23:59:59 2025 GMT
```

This is how you check if a certificate is about to expire. Automate this check for your own services.

### 🔍 Try It: See the Subject Alternative Names

```bash
echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName

# Output:
# X509v3 Subject Alternative Name:
#     DNS:github.com, DNS:www.github.com
```

The SAN extension lists which domains this certificate is valid for. Your browser checks that the domain in the URL matches one of these names.

---

## Part 2: The TLS 1.3 Handshake, Step by Step

### The 1-RTT Handshake

TLS 1.3 completes the handshake in a single round trip. This is the key improvement over TLS 1.2, which required two round trips.

```
Client                                    Server
  |                                          |
  |  ClientHello                             |
  |  + supported_versions: [TLS 1.3]        |
  |  + key_share: X25519 public key (32B)   |
  |  + signature_algorithms: [ed25519, ...]  |
  |  + supported_groups: [x25519, secp256r1] |
  |  ---------------------------------------->|   t=0
  |                                          |
  |                          ServerHello     |
  |              + key_share: X25519 pub key |
  |                                          |
  |         {EncryptedExtensions}            |
  |         {Certificate}                    |
  |         {CertificateVerify}              |
  |         {Finished}                       |
  |<-----------------------------------------|   t=RTT/2
  |                                          |
  |  {Finished}                              |
  |  [Application Data]  ←── data flows here |
  |----------------------------------------->|   t=RTT
  |                                          |
  |               [Application Data]         |
  |<-----------------------------------------|
```

Items in `{}` are encrypted. Items in `[]` are application data.

Step by step:

**1. ClientHello** (client to server)

The client sends everything the server needs to negotiate the connection in a single message:

- **supported_versions**: "I support TLS 1.3" (and maybe 1.2 as fallback)
- **key_share**: The client's ephemeral public key for Diffie-Hellman key exchange. This is the optimization -- in TLS 1.2, the client waited for the server to choose a key exchange algorithm before sending its key. TLS 1.3 sends it preemptively.
- **signature_algorithms**: Which signature algorithms the client can verify
- **supported_groups**: Which elliptic curves / DH groups the client supports

**2. ServerHello** (server to client)

The server selects a cipher suite and sends its ephemeral public key. At this point, both sides can compute the shared secret using ECDHE (Elliptic Curve Diffie-Hellman Ephemeral). Everything after ServerHello is encrypted.

**3. Encrypted Server Messages**

- **EncryptedExtensions**: Additional parameters (e.g., ALPN protocol negotiation for HTTP/2)
- **Certificate**: The server's certificate chain
- **CertificateVerify**: A signature over the handshake transcript, proving the server owns the private key for the certificate
- **Finished**: A MAC over the entire handshake, confirming both sides agree on the derived keys

**4. Client Finished**

The client verifies the certificate chain, checks the CertificateVerify signature, and sends its own Finished message. Application data can be sent alongside this message -- the handshake is functionally complete after 1 RTT.

### TLS 1.3 vs TLS 1.2: What Changed

| Feature | TLS 1.2 | TLS 1.3 |
|---|---|---|
| Handshake RTTs | 2 RTT | 1 RTT (0-RTT for resumption) |
| Key exchange | RSA or ECDHE | ECDHE only (mandatory PFS) |
| Cipher suites | Many (some weak: RC4, CBC) | 5 suites, all AEAD |
| Static RSA key exchange | Supported | **Removed** (no forward secrecy) |
| Compression | Optional (CRIME attack vector) | **Removed** |
| Renegotiation | Supported | **Removed** |
| 0-RTT resumption | Not available | Available (with replay caveats) |

The most important change is **mandatory Perfect Forward Secrecy (PFS)**. In TLS 1.2 with RSA key exchange, if an attacker records encrypted traffic today and steals the server's private key next year, they can decrypt all the recorded traffic. TLS 1.3 eliminates this: every connection uses ephemeral keys that are discarded after the session ends.

### 0-RTT Resumption: Speed vs Security

If a client has connected to a server before, TLS 1.3 supports sending application data in the very first message (0-RTT), using a pre-shared key from the previous session:

```
Client → Server: ClientHello + key_share + PSK + early_data (0-RTT application data)
Server → Client: ServerHello + ... + Finished
```

Data flows before the handshake completes. But there is a catch:

> ⚠️ **0-RTT data is vulnerable to replay attacks.** An attacker who captures the ClientHello + early data can re-send it. The server may process the request again. This means 0-RTT should only be used for **idempotent requests** (GET). Never use 0-RTT for requests that create resources, transfer money, or have side effects.

---

## Part 3: Certificates for TicketPulse

### 🛠️ Build: Generate a Self-Signed Certificate

```bash
# Generate a self-signed certificate for local development
openssl req -x509 \
  -newkey rsa:4096 \
  -keyout ticketpulse-key.pem \
  -out ticketpulse-cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=California/L=San Francisco/O=TicketPulse/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:*.ticketpulse.local,IP:127.0.0.1"
```

Let's break down each flag:

| Flag | Purpose |
|---|---|
| `-x509` | Generate a self-signed certificate (not a certificate signing request) |
| `-newkey rsa:4096` | Generate a new 4096-bit RSA key pair |
| `-keyout` | Where to write the private key |
| `-out` | Where to write the certificate |
| `-days 365` | Certificate validity period |
| `-nodes` | Do not encrypt the private key (needed for automated use) |
| `-subj` | Certificate subject (who the cert is for) |
| `-addext` | Add Subject Alternative Names (the domains this cert covers) |

Verify the certificate:

```bash
# View certificate details
openssl x509 -in ticketpulse-cert.pem -noout -text | head -30

# Check the SANs
openssl x509 -in ticketpulse-cert.pem -noout -ext subjectAltName

# Check the key
openssl rsa -in ticketpulse-key.pem -check -noout
```

### 🛠️ Build: Configure HTTPS on the API Gateway

```typescript
// src/server.ts
import https from 'https';
import fs from 'fs';
import app from './app';

const PORT = parseInt(process.env.PORT || '3000');

if (process.env.NODE_ENV === 'production' || process.env.ENABLE_TLS === 'true') {
  const httpsOptions = {
    key: fs.readFileSync(process.env.TLS_KEY_PATH || './certs/ticketpulse-key.pem'),
    cert: fs.readFileSync(process.env.TLS_CERT_PATH || './certs/ticketpulse-cert.pem'),
    minVersion: 'TLSv1.2' as const,  // Reject anything older than TLS 1.2
  };

  https.createServer(httpsOptions, app).listen(PORT, () => {
    console.log(`HTTPS server running on port ${PORT}`);
  });
} else {
  // Plain HTTP for local development
  app.listen(PORT, () => {
    console.log(`HTTP server running on port ${PORT}`);
  });
}
```

### 🔍 Try It: See Your TLS Handshake

```bash
# Start the server with TLS enabled
ENABLE_TLS=true node dist/server.js

# Connect with curl verbose mode -- watch the handshake
curl -v --cacert ticketpulse-cert.pem https://localhost:3000/api/health

# You'll see:
# * TLSv1.3 (OUT), TLS handshake, Client hello (1):
# * TLSv1.3 (IN), TLS handshake, Server hello (2):
# * TLSv1.3 (IN), TLS handshake, Encrypted Extensions (8):
# * TLSv1.3 (IN), TLS handshake, Certificate (11):
# * TLSv1.3 (IN), TLS handshake, CERT verify (15):
# * TLSv1.3 (IN), TLS handshake, Finished (20):
# * TLSv1.3 (OUT), TLS handshake, Finished (20):
# * SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384

# Without --cacert, curl rejects the self-signed cert:
curl -v https://localhost:3000/api/health
# * SSL certificate problem: self-signed certificate
```

The `--cacert` flag tells curl to trust your self-signed certificate. In production, you would use a certificate signed by a real CA, and curl would trust it automatically.

---

## Part 4: Mutual TLS (mTLS)

### Why mTLS?

In standard TLS, only the server proves its identity. The client trusts the server's certificate, but the server has no idea who the client is (authentication happens at the application layer, e.g., with JWTs).

In mTLS, both sides present certificates:

```
Standard TLS:
  Client ──── verifies ────> Server certificate    ✓
  Client <─── no proof ───── Server               ✗

Mutual TLS:
  Client ──── verifies ────> Server certificate    ✓
  Client <─── verifies ───── Client certificate    ✓
```

This is used for:
- **Service-to-service communication** in microservices (Istio service mesh enables mTLS by default)
- **Kubernetes pod-to-pod** communication
- **Zero-trust networks** where network location does not grant trust
- **API authentication** where API keys are insufficient

### 🛠️ Build: Set Up mTLS for TicketPulse Services

First, create a Certificate Authority (CA) for TicketPulse:

```bash
# Step 1: Create the CA key and certificate
openssl req -x509 \
  -newkey rsa:4096 \
  -keyout ca-key.pem \
  -out ca-cert.pem \
  -days 3650 \
  -nodes \
  -subj "/C=US/O=TicketPulse/CN=TicketPulse Internal CA"

# Step 2: Generate a server certificate signed by the CA
# First, create a certificate signing request (CSR)
openssl req -new \
  -newkey rsa:4096 \
  -keyout server-key.pem \
  -out server.csr \
  -nodes \
  -subj "/C=US/O=TicketPulse/CN=event-service.ticketpulse.local"

# Sign the CSR with the CA
openssl x509 -req \
  -in server.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out server-cert.pem \
  -days 365 \
  -extfile <(echo "subjectAltName=DNS:event-service.ticketpulse.local,DNS:localhost")

# Step 3: Generate a client certificate (for the payment service)
openssl req -new \
  -newkey rsa:4096 \
  -keyout client-key.pem \
  -out client.csr \
  -nodes \
  -subj "/C=US/O=TicketPulse/CN=payment-service"

openssl x509 -req \
  -in client.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out client-cert.pem \
  -days 365
```

Configure the server to require client certificates:

```typescript
// event-service/src/server.ts
import https from 'https';
import fs from 'fs';

const httpsOptions = {
  key: fs.readFileSync('./certs/server-key.pem'),
  cert: fs.readFileSync('./certs/server-cert.pem'),
  ca: fs.readFileSync('./certs/ca-cert.pem'),       // Trust our internal CA
  requestCert: true,                                  // Ask clients for a certificate
  rejectUnauthorized: true,                           // Reject clients without a valid cert
};

const server = https.createServer(httpsOptions, app);
server.listen(3001, () => {
  console.log('Event service (mTLS) listening on port 3001');
});

// Middleware to extract client identity from the certificate
app.use((req, res, next) => {
  const cert = (req.socket as any).getPeerCertificate();
  if (cert && cert.subject) {
    req.clientService = cert.subject.CN; // e.g., "payment-service"
    console.log(`Request from service: ${req.clientService}`);
  }
  next();
});
```

Test mTLS:

```bash
# This fails -- no client certificate
curl --cacert ca-cert.pem https://localhost:3001/api/events
# Error: SSL peer certificate or SSH remote key was not OK

# This succeeds -- client presents its certificate
curl --cacert ca-cert.pem \
     --cert client-cert.pem \
     --key client-key.pem \
     https://localhost:3001/api/events
# → {"events": [...]}
```

### mTLS in Production: Service Meshes

In practice, you do not manually manage certificates for every service. A service mesh like Istio handles this:

1. **Automatic certificate issuance**: Each pod gets a certificate from Istio's CA (Citadel)
2. **Automatic rotation**: Certificates are rotated before expiration (default: every 24 hours)
3. **Transparent mTLS**: The sidecar proxy (Envoy) handles TLS termination and initiation -- your application code uses plain HTTP

```yaml
# Istio PeerAuthentication -- require mTLS for all services in the namespace
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: ticketpulse
spec:
  mtls:
    mode: STRICT  # Only allow mTLS connections
```

With this configuration, every service-to-service call within the `ticketpulse` namespace is automatically encrypted and authenticated with mTLS. No application code changes needed.

---

## Part 5: Certificate Management in Production

### Let's Encrypt and Automatic Renewal

For public-facing services, use Let's Encrypt for free, automated certificates:

```bash
# Using certbot
sudo certbot certonly --standalone -d api.ticketpulse.com

# Auto-renewal (certbot sets this up automatically)
sudo certbot renew --dry-run
```

### cert-manager in Kubernetes

For Kubernetes clusters, cert-manager automates certificate lifecycle:

```yaml
# Install cert-manager (Helm)
# helm install cert-manager jetstack/cert-manager --set installCRDs=true

# ClusterIssuer for Let's Encrypt
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform@ticketpulse.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx

---
# Certificate for the API gateway
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
  namespace: ticketpulse
spec:
  secretName: api-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.ticketpulse.com
    - www.ticketpulse.com

---
# Use the certificate in an Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: ticketpulse
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - api.ticketpulse.com
      secretName: api-tls-secret
  rules:
    - host: api.ticketpulse.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 80
```

cert-manager will:
1. Request a certificate from Let's Encrypt
2. Complete the HTTP-01 challenge automatically
3. Store the certificate in a Kubernetes Secret
4. Renew the certificate before it expires (default: 30 days before)
5. Update the Secret with the new certificate

---

## Part 6: Measuring TLS Performance

### 📊 Observe: TLS Handshake Timing

```bash
# Measure TLS handshake time
curl -w "DNS: %{time_namelookup}s\nTCP: %{time_connect}s\nTLS: %{time_appconnect}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s https://api.github.com

# Example output:
# DNS:   0.012s
# TCP:   0.045s    (RTT to server ≈ 33ms)
# TLS:   0.112s    (TLS handshake ≈ 67ms, about 2 RTTs for TLS 1.2)
# Total: 0.156s
```

Compare TLS 1.2 vs 1.3:

```bash
# Force TLS 1.2
curl -w "TLS: %{time_appconnect}s\n" --tls-max 1.2 -o /dev/null -s https://api.github.com

# Force TLS 1.3
curl -w "TLS: %{time_appconnect}s\n" --tlsv1.3 -o /dev/null -s https://api.github.com
```

You should see TLS 1.3 complete faster because it saves one round trip.

### 📊 Observe: Connection Reuse Savings

```bash
# Without connection reuse: every request pays DNS + TCP + TLS
for i in {1..5}; do
  curl -w "Total: %{time_total}s\n" -o /dev/null -s https://api.github.com/zen
done

# With connection reuse (HTTP/2 or keep-alive): only the first request pays TLS
curl -w "Req1: %{time_total}s\n" -o /dev/null -s \
     -w "Req2: %{time_total}s\n" -o /dev/null -s \
     https://api.github.com/zen https://api.github.com/zen
```

The cost model:

```
Without connection pooling: DNS (1 RTT) + TCP (1 RTT) + TLS (1-2 RTT) + Request (1 RTT) = 4-5 RTTs
With connection pooling:    Request (1 RTT)                                               = 1 RTT
```

For a server 50ms away, that is 200-250ms vs 50ms. Connection pooling is the single largest optimization for latency.

> 💡 **Insight**: "Cloudflare terminates TLS for roughly 30% of the internet's web traffic. Their TLS 1.3 implementation saved an average of 300ms per connection for users on slow networks. For TicketPulse, TLS 1.3 saves one round trip per new connection -- which adds up when you have thousands of users making their first request."

---

## Part 7: Common TLS Failures in Production

### The Certificate Chain Problem

The most common TLS issue: the server sends only the leaf certificate, missing the intermediate.

```bash
# This simulates the problem -- curl with a strict trust store
curl https://api.example.com
# curl: (60) SSL certificate problem: unable to get local issuer certificate

# Diagnosis: check the chain
openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | grep -E "depth|verify"
# If depth=0 is the only line, the intermediate is missing
```

Fix: configure your server to send the full chain (leaf + intermediate):

```bash
# Combine the certificates into a full chain file
cat server-cert.pem intermediate-cert.pem > fullchain.pem
```

### Certificate Expiration

Let's Encrypt certificates expire every 90 days. If auto-renewal breaks, you get an outage.

```bash
# Check expiration for all your domains
for domain in api.ticketpulse.com www.ticketpulse.com; do
  echo -n "$domain: "
  echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null \
    | openssl x509 -noout -enddate
done
```

Set up monitoring: alert if any certificate expires within 14 days.

### SNI Mismatch

If the client does not send SNI (Server Name Indication), the server may present the wrong certificate:

```bash
# Without SNI (old behavior)
openssl s_client -connect shared-host.example.com:443

# With SNI (correct)
openssl s_client -connect shared-host.example.com:443 -servername api.ticketpulse.com
```

---

## 🤔 Reflect

Answer these questions:

1. **Why did TLS 1.3 remove RSA key exchange?** What attack does this prevent?
2. **When should you NOT use 0-RTT resumption?** What is the specific risk?
3. **Why does mTLS matter in a Kubernetes cluster?** Isn't the cluster network already private?
4. **If you had to choose between mTLS and JWT-based service authentication, what are the trade-offs of each?**

---

## Checkpoint

Before moving on, verify:

- [ ] You watched a TLS handshake with `openssl s_client` and can explain each section
- [ ] You can explain the TLS 1.3 handshake (1-RTT) and why it is faster than TLS 1.2
- [ ] You generated a self-signed certificate for TicketPulse
- [ ] You configured HTTPS on the TicketPulse API gateway
- [ ] You verified TLS with `curl -v` and saw the handshake details
- [ ] You understand mTLS and when to use it (service-to-service authentication)
- [ ] You can measure TLS handshake time with `curl -w`
- [ ] You know how cert-manager automates certificate lifecycle in Kubernetes

---

## Key Terms

| Term | Definition |
|------|-----------|
| **TLS 1.3** | The latest version of TLS, offering improved security and a faster handshake compared to previous versions. |
| **Certificate** | A digital document that binds a public key to an identity, signed by a certificate authority. |
| **mTLS** | Mutual TLS; a variant where both client and server present certificates to authenticate each other. |
| **Handshake** | The initial negotiation between client and server that establishes encryption parameters for a TLS session. |
| **Cipher suite** | A named combination of algorithms for key exchange, encryption, and message authentication used in a TLS session. |
| **Let's Encrypt** | A free, automated certificate authority that issues TLS certificates trusted by major browsers. |

## Further Reading

- [RFC 8446: TLS 1.3](https://tools.ietf.org/html/rfc8446)
- Chapter 21 of the 100x Engineer Guide (Networking & Protocols) for the full TLS section
- [Let's Encrypt: How It Works](https://letsencrypt.org/how-it-works/)
- [cert-manager documentation](https://cert-manager.io/docs/)

> **Next up:** L2-M58 is THE module that separates senior from junior engineers -- debugging in production with only observability tools.

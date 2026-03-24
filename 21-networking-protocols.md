<!--
  CHAPTER: 21
  TITLE: Networking & Protocols Deep Dive
  PART: I — Foundations
  PREREQS: None
  KEY_TOPICS: TCP/IP, TLS, HTTP lifecycle, DNS, WebSocket, gRPC, protobuf, network debugging, tcpdump, Wireshark, mtr, latency
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 21: Networking & Protocols Deep Dive

> **Part I — Foundations** | Prerequisites: None | Difficulty: Intermediate → Advanced

Understanding the network is what separates engineers who can debug production from those who can't. This chapter covers every protocol layer from TCP segments to HTTP headers, with practical debugging techniques.

### In This Chapter
- TCP/IP Internals
- TLS & Encryption on the Wire
- HTTP Request Lifecycle (end-to-end)
- DNS Resolution Deep Dive
- WebSocket Protocol
- gRPC & Protocol Buffers
- Network Debugging & Troubleshooting

### Related Chapters
- Ch 4 (latency/performance engineering)
- Ch 7 (CDN, load balancing, service mesh)
- Ch 13 (cloud networking/VPC)
- Ch 18 (debugging with network tools)

---

## 1. TCP/IP Internals

### The TCP/IP Model vs the OSI Model

There are two reference models for network communication. The OSI model has seven layers; the TCP/IP model has four. In practice, virtually every system you will debug uses the TCP/IP model. The OSI model is useful as a teaching tool and as a shared vocabulary, but nobody ships software that cleanly separates the session, presentation, and application layers.

| TCP/IP Layer        | OSI Layers               | Protocols / Examples                        |
|---------------------|--------------------------|---------------------------------------------|
| Application         | Application (7), Presentation (6), Session (5) | HTTP, gRPC, DNS, TLS, SSH, SMTP  |
| Transport           | Transport (4)            | TCP, UDP, QUIC                              |
| Internet            | Network (3)              | IP (v4/v6), ICMP, ARP                       |
| Network Access      | Data Link (2), Physical (1) | Ethernet, Wi-Fi, PPP                     |

**Which matters in practice?** Layers 3 (IP) and 4 (TCP/UDP) are where 90% of production networking issues live. You need to understand IP routing to reason about VPCs, security groups, and network policies. You need to understand TCP to reason about connection state, latency, throughput, and reliability.

### TCP Three-Way Handshake

Every TCP connection begins with a three-way handshake. This establishes the connection and synchronizes sequence numbers between client and server.

```
Client                          Server
  |                                |
  |  ---- SYN (seq=x) --------->  |   t=0ms
  |                                |
  |  <--- SYN-ACK (seq=y, ack=x+1) |   t=RTT/2
  |                                |
  |  ---- ACK (seq=x+1, ack=y+1) ->|   t=RTT
  |                                |
  [Connection ESTABLISHED]           [Connection ESTABLISHED]
```

Step by step:

1. **SYN**: The client picks an initial sequence number (ISN) `x` and sends a SYN segment. The client enters the `SYN_SENT` state.
2. **SYN-ACK**: The server receives the SYN, picks its own ISN `y`, and responds with SYN-ACK acknowledging the client's sequence number (`ack=x+1`). The server enters `SYN_RCVD`.
3. **ACK**: The client acknowledges the server's sequence number (`ack=y+1`). Both sides enter `ESTABLISHED`.

The handshake costs one round-trip time (RTT). For a server 50ms away, that is 50ms before any data flows. This is why connection reuse matters enormously.

**SYN flood attacks** exploit this: an attacker sends millions of SYN packets with spoofed source IPs, filling the server's SYN queue. Defenses include SYN cookies (`net.ipv4.tcp_syncookies=1`), which encode the connection state in the SYN-ACK sequence number so the server does not need to allocate memory until the handshake completes.

### TCP Connection Teardown

TCP uses a four-way teardown (though it is often collapsed into three segments):

```
Client                          Server
  |                                |
  |  ---- FIN (seq=u) ---------->  |   Client says "I'm done sending"
  |                                |
  |  <--- ACK (ack=u+1) ---------  |   Server acknowledges
  |                                |
  |  <--- FIN (seq=v) -----------  |   Server says "I'm done sending too"
  |                                |
  |  ---- ACK (ack=v+1) -------->  |   Client acknowledges
  |                                |
  [Client enters TIME_WAIT]         [Server enters CLOSED]
```

**TIME_WAIT** is the most misunderstood state in TCP. After the side that initiates the close sends the final ACK, it enters TIME_WAIT for 2 * MSL (Maximum Segment Lifetime, typically 60 seconds on Linux). This exists for two reasons:

1. **Reliable termination**: If the final ACK is lost, the remote side will retransmit its FIN, and the TIME_WAIT state allows the local side to re-send the ACK.
2. **Preventing sequence number reuse**: Old packets from a previous connection on the same (src IP, src port, dst IP, dst port) tuple could be misinterpreted by a new connection. TIME_WAIT ensures those old segments expire.

### TCP Flow Control

TCP uses a **sliding window** mechanism to prevent a fast sender from overwhelming a slow receiver.

- Each side advertises a **receive window** (`rwnd`) in every ACK, indicating how many bytes it can buffer.
- The sender limits its unacknowledged (in-flight) data to `min(rwnd, cwnd)` where `cwnd` is the congestion window.
- **Window scaling** (RFC 7323) is negotiated during the handshake via the Window Scale option. The 16-bit window field in the TCP header maxes out at 65,535 bytes, which is far too small for high-bandwidth, high-latency links. Window scaling allows effective windows up to ~1 GB.

```bash
# Check current window sizes on Linux
ss -i | grep -A1 ESTAB
# Output includes: wscale:7,7 rto:204 rtt:1.5/0.75 cwnd:10 ssthresh:7
```

### TCP Congestion Control

Congestion control prevents TCP from overwhelming the network. The sender maintains a **congestion window** (`cwnd`) that limits how much data can be in flight.

**Slow Start**: When a connection is new (or after a timeout), `cwnd` starts at a small value (typically 10 segments, i.e., ~14KB) and doubles every RTT (exponential growth). This continues until `cwnd` reaches the slow-start threshold (`ssthresh`) or packet loss is detected.

**Congestion Avoidance**: Once `cwnd >= ssthresh`, growth becomes linear: `cwnd` increases by roughly 1 segment per RTT (additive increase).

**Fast Retransmit**: When the sender receives 3 duplicate ACKs (indicating a single lost segment rather than a total collapse), it retransmits the missing segment immediately without waiting for a timeout.

**Fast Recovery**: After fast retransmit, the sender halves `cwnd` (multiplicative decrease) and enters congestion avoidance rather than slow start. This avoids the penalty of starting over from scratch.

**Cubic vs BBR**:

- **Cubic** (Linux default since 2.6.19): Uses a cubic function of time since last congestion event to determine `cwnd`. Performs well on high-bandwidth, high-latency links. Loss-based: responds to packet loss.
- **BBR** (Bottleneck Bandwidth and Round-trip propagation time): Developed by Google. Model-based rather than loss-based: it estimates the actual bottleneck bandwidth and minimum RTT, then paces packets to match. Performs dramatically better on networks with shallow buffers or random packet loss (e.g., wireless). Can be unfair to Cubic flows.

```bash
# Check current congestion control algorithm
sysctl net.ipv4.tcp_congestion_control
# Switch to BBR (requires kernel 4.9+)
sysctl -w net.ipv4.tcp_congestion_control=bbr
```

### TCP vs UDP

| Property              | TCP                      | UDP                         |
|-----------------------|--------------------------|-----------------------------|
| Delivery guarantee    | Reliable, ordered        | Best-effort, unordered      |
| Connection setup      | Three-way handshake      | None (connectionless)       |
| Head-of-line blocking | Yes                      | No                          |
| Flow/congestion ctrl  | Built-in                 | None (app must implement)   |
| Header size           | 20-60 bytes              | 8 bytes                     |
| Use cases             | HTTP, databases, SSH     | DNS, video streaming, gaming, QUIC |

**When to use UDP:**
- **DNS queries**: Single request-response, no need for connection setup.
- **Real-time audio/video**: Late data is useless. Better to drop a frame than wait for retransmission.
- **Online gaming**: Player position updates at 60Hz — a lost packet is immediately superseded by the next.
- **QUIC** (HTTP/3): Builds reliability on top of UDP to avoid TCP's head-of-line blocking.

**When to use TCP:**
- Everything where data integrity matters and you do not want to re-implement reliability yourself. This is most things.

### Socket Programming Concepts

At the OS level, network communication happens through sockets — file descriptors that represent network endpoints.

**Server lifecycle:**
```
socket()  →  bind()  →  listen()  →  accept()  →  read()/write()  →  close()
```

**Client lifecycle:**
```
socket()  →  connect()  →  read()/write()  →  close()
```

- `listen(fd, backlog)`: The `backlog` parameter controls how many connections can be queued before `accept()` is called. On Linux, this is the size of the accept queue (completed handshakes waiting for the application to call `accept()`). A separate SYN queue holds in-progress handshakes.
- `accept()`: Returns a new file descriptor for each accepted connection. The original listening socket continues to accept more connections.
- **File descriptors**: Each socket is a file descriptor. The system-wide limit (`ulimit -n`, `fs.file-max`) can be a bottleneck under high connection counts.

**I/O multiplexing**: Handling thousands of connections requires non-blocking I/O:
- **`select`/`poll`**: O(n) per event — scales poorly.
- **`epoll`** (Linux): O(1) per event. The backbone of nginx, Node.js, and Go's runtime.
- **`kqueue`** (macOS/BSD): Similar to epoll. Used by the same high-performance servers on BSD-derived systems.

```bash
# See how many file descriptors a process is using
ls /proc/<pid>/fd | wc -l
# Check system-wide limits
sysctl fs.file-max
# Check per-process limits
ulimit -n
```

### TCP_NODELAY and Nagle's Algorithm

**Nagle's algorithm** buffers small writes and combines them into larger segments to reduce overhead. It waits to send data until either (a) there is enough to fill a segment, or (b) all previously sent data has been ACKed.

This is efficient for bulk transfers but disastrous for interactive/low-latency protocols. If you are sending small messages (e.g., a 50-byte RPC request), Nagle's algorithm may delay sending for up to 200ms waiting for the previous ACK.

**`TCP_NODELAY`** disables Nagle's algorithm, causing every `write()` to be sent immediately.

**When to set TCP_NODELAY:**
- RPC protocols (gRPC, Redis protocol, database wire protocols)
- Interactive sessions (SSH, telnet)
- Any protocol where latency matters more than bandwidth efficiency

Most modern HTTP libraries and database drivers set `TCP_NODELAY` by default.

### Keep-Alive vs Connection Pooling

**TCP keep-alive** is an OS-level mechanism that sends probe packets on idle connections to detect if the remote end has silently died. On Linux:

```bash
# Default: probe after 2 hours of inactivity
sysctl net.ipv4.tcp_keepalive_time      # 7200 seconds
sysctl net.ipv4.tcp_keepalive_intvl     # 75 seconds between probes
sysctl net.ipv4.tcp_keepalive_probes    # 9 probes before declaring dead
```

For services behind load balancers, the default 2-hour timeout is far too long. AWS NLB idle timeout is 350 seconds; if TCP keep-alive does not fire before that, the LB silently drops the connection and the next request gets a reset.

**Connection pooling** is an application-level pattern: maintain a pool of pre-established TCP connections to a server. When a request needs to be made, grab a connection from the pool; when done, return it. This avoids the overhead of the TCP handshake + TLS handshake on every request.

```
Without pooling: DNS + TCP (1 RTT) + TLS (1-2 RTT) + Request/Response = 3-4 RTTs
With pooling:    Request/Response = 1 RTT (connection already established)
```

### Common TCP Problems

**TIME_WAIT accumulation**: If your service makes many short-lived outbound connections (e.g., to a database or external API), each closed connection sits in TIME_WAIT for 60 seconds. At high rates, you can exhaust the ephemeral port range (typically 28,000 ports).

```bash
# Count TIME_WAIT connections
ss -s
# Or specifically
ss -ant | awk '{print $1}' | sort | uniq -c | sort -rn

# Mitigation on Linux:
sysctl -w net.ipv4.tcp_tw_reuse=1       # Allow reuse of TIME_WAIT sockets for new connections
                                          # (safe for outbound connections)
# DO NOT use tcp_tw_recycle — it is broken with NAT and removed in kernel 4.12
```

The real fix is connection pooling.

**Connection reset (RST)**: A RST packet abruptly terminates a connection. Common causes:
- Connecting to a port with no listener
- The application crashed without closing the socket
- A firewall or load balancer timing out and sending RST
- Sending data on a half-closed connection

**Half-open connections**: One side thinks the connection is open; the other side has crashed or lost network. The "open" side will not discover this until it tries to send data (gets RST or timeout) or TCP keep-alive detects it.

---

## 2. TLS & Encryption on the Wire

### TLS 1.3 Handshake

TLS 1.3 (RFC 8446) achieves a 1-RTT handshake by sending the key exchange in the first message:

```
Client                                    Server
  |                                          |
  |  ClientHello                             |
  |  + supported_versions (1.3)              |
  |  + key_share (e.g., X25519 public key)   |
  |  + signature_algorithms                  |
  |  + supported_groups                      |
  |  ---------------------------------------->|
  |                                          |
  |                          ServerHello     |
  |                + key_share (server pubkey)|
  |         {EncryptedExtensions}            |
  |         {Certificate}                    |
  |         {CertificateVerify}              |
  |         {Finished}                       |
  |<-----------------------------------------|
  |                                          |
  |  {Finished}                              |
  |  [Application Data]                      |
  |----------------------------------------->|
  |                                          |
  |               [Application Data]         |
  |<-----------------------------------------|
```

Step by step:

1. **ClientHello**: The client sends its supported TLS versions, cipher suites, a random nonce, and crucially a **key_share** — its half of the key exchange (typically an X25519 or P-256 ephemeral public key). This is the key optimization: the client guesses which key exchange the server will accept and sends its share preemptively.
2. **ServerHello**: The server selects a cipher suite, sends its key_share. At this point, both sides can derive the handshake keys using ECDHE. Everything after ServerHello is encrypted.
3. **Encrypted payload**: The server sends its certificate, a signature proving it owns the private key (CertificateVerify), and a Finished message (MAC over the handshake transcript).
4. **Client Finished**: The client verifies the certificate chain, checks the signature, and sends its own Finished message. Application data can be sent with this message.

**Result**: The handshake completes in 1 RTT. Application data flows after 1 RTT (the client can send data along with its Finished message).

### TLS 1.3 vs TLS 1.2

| Feature                     | TLS 1.2                          | TLS 1.3                         |
|-----------------------------|----------------------------------|----------------------------------|
| Handshake RTTs              | 2 RTT                            | 1 RTT (0-RTT for resumption)    |
| Key exchange                | RSA or ECDHE                     | ECDHE only (mandatory PFS)      |
| Cipher suites               | Many (some weak)                 | 5 suites, all AEAD              |
| Static RSA key exchange     | Supported                        | Removed (no PFS)                |
| Symmetric ciphers           | CBC, RC4, etc.                   | AES-GCM, ChaCha20-Poly1305 only |
| Compression                 | Optional (CRIME attack vector)   | Removed                         |
| Renegotiation               | Supported                        | Removed                         |
| 0-RTT resumption            | Not available                    | Available (with replay risks)    |

The most important change: **mandatory Perfect Forward Secrecy (PFS)**. In TLS 1.2 with RSA key exchange, if an attacker records ciphertext and later obtains the server's private key, they can decrypt all recorded traffic. TLS 1.3 eliminates this by requiring ephemeral key exchange — even if the long-term key is compromised, past sessions remain secure.

### 0-RTT Resumption

TLS 1.3 supports 0-RTT (early data): if a client has connected to a server before, it can send application data in the first flight (alongside ClientHello) using a pre-shared key (PSK) from the previous session.

```
Client                                    Server
  |                                          |
  |  ClientHello + key_share                 |
  |  + pre_shared_key                        |
  |  + early_data_indication                 |
  |  (Application Data — 0-RTT)              |
  |  ---------------------------------------->|
  |                                          |
  |  ServerHello + ... + Finished            |
  |<-----------------------------------------|
```

**Replay attack risk**: 0-RTT data is not protected against replay. An attacker who captures the ClientHello + early data can re-send it to the server. This means **0-RTT should only be used for idempotent requests** (e.g., GET). Do not use 0-RTT for POST requests that create resources or transfer money.

Servers can mitigate replay by maintaining a list of used tickets (at the cost of statefulness) or by limiting 0-RTT acceptance to a short time window.

### Certificate Chain Validation

When a server presents its certificate, the client validates a chain:

```
Root CA (e.g., DigiCert Global Root G2)
  └── Intermediate CA (e.g., DigiCert SHA2 Extended Validation Server CA)
        └── Leaf Certificate (e.g., CN=api.example.com)
```

Validation steps:
1. **Chain building**: The leaf cert's "Issuer" field must match the intermediate's "Subject." The intermediate's "Issuer" must match the root's "Subject."
2. **Signature verification**: Each certificate's signature is verified using the issuer's public key.
3. **Root trust**: The root CA must be in the client's trust store (OS/browser-managed).
4. **Validity period**: Each certificate must be within its `notBefore` and `notAfter` dates.
5. **Revocation check**: Verify the certificate has not been revoked (via OCSP or CRL).
6. **Name matching**: The leaf certificate's Subject Alternative Name (SAN) must match the requested hostname.

**Common production issue**: The server is configured with only the leaf certificate, not the intermediate. Modern browsers may cache intermediates and succeed, but API clients (curl, Python requests, Go HTTP client) will fail with "certificate verify failed." Always configure the full chain.

### Certificate Pinning

Certificate pinning hardcodes the expected certificate (or its public key hash) in the client, so the client will only trust that specific certificate rather than any certificate signed by a trusted CA.

**When to use it:**
- Mobile apps communicating with a known backend
- Service-to-service communication where you control both ends

**When NOT to use it:**
- Websites (browsers have deprecated HTTP Public Key Pinning / HPKP because misconfiguration can permanently lock users out)
- Any situation where you cannot guarantee timely client updates when certificates rotate

If you pin, **pin the public key hash of the intermediate CA** rather than the leaf. Leaf certificates rotate frequently; intermediate CAs rotate rarely. Pin at least two keys (primary + backup) to avoid lockout.

### SNI (Server Name Indication)

SNI is a TLS extension that allows the client to indicate which hostname it is connecting to during the ClientHello. This allows a single IP address to serve TLS certificates for multiple domains.

Without SNI, the server must present a certificate before knowing which domain the client wants. This means one IP per domain, which does not scale.

SNI is sent **in plaintext** in TLS 1.2 and 1.3. This leaks which hostname you are connecting to (even though the rest of the traffic is encrypted). **Encrypted Client Hello (ECH)**, part of the ESNI/ECH draft, encrypts the SNI extension to address this.

Almost all modern TLS clients send SNI. The notable exception is very old clients (Android 2.x, IE on Windows XP). If you are reading this in 2026, you can safely require SNI.

### mTLS (Mutual TLS)

In standard TLS, only the server presents a certificate. In mTLS, the client also presents a certificate, and the server verifies it. This provides strong authentication of both parties.

**Use cases:**
- Service-to-service authentication in microservices (Istio service mesh uses mTLS by default)
- API authentication where API keys are insufficient
- Zero-trust network architectures

**How it works:**
1. The server includes a `CertificateRequest` message in its handshake.
2. The client responds with its certificate and a `CertificateVerify` signature.
3. The server validates the client certificate against its trusted CA.

**Operational complexity**: You now need to manage certificates for every client. This is where tools like Vault PKI, cert-manager (Kubernetes), or SPIFFE/SPIRE become essential.

### OCSP Stapling vs CRL

When a certificate is revoked (e.g., private key compromised), clients need a way to discover this.

**CRL (Certificate Revocation List)**: The CA publishes a list of revoked certificate serial numbers. The client downloads the full list and checks if the server's certificate is on it. Problems: CRLs can be large, and clients do not always check them (soft-fail mode).

**OCSP (Online Certificate Status Protocol)**: The client sends the certificate serial number to the CA's OCSP responder and gets back a signed "good/revoked/unknown" response. Problems: adds latency (extra HTTP request to the CA), privacy concern (the CA sees which sites you visit), and OCSP responders can be slow or unreliable.

**OCSP Stapling**: The server periodically fetches the OCSP response from the CA and "staples" it to the TLS handshake. The client gets proof of non-revocation without contacting the CA. This is the best approach and should be enabled on every server.

```bash
# Check if a server supports OCSP stapling
openssl s_client -connect api.example.com:443 -status < /dev/null 2>&1 | grep -A5 "OCSP Response"
```

### Let's Encrypt and the ACME Protocol

Let's Encrypt provides free, automated TLS certificates using the ACME (Automatic Certificate Management Environment) protocol.

**How ACME works:**
1. The client (e.g., certbot, Caddy, Traefik) creates an account with the ACME server.
2. The client requests a certificate for a domain.
3. The ACME server issues challenges to prove domain ownership:
   - **HTTP-01**: Place a file at `http://<domain>/.well-known/acme-challenge/<token>`.
   - **DNS-01**: Create a TXT record at `_acme-challenge.<domain>`. Required for wildcard certificates.
   - **TLS-ALPN-01**: Respond to a TLS connection with a special self-signed certificate. Useful when port 80 is unavailable.
4. The client completes the challenge and the ACME server issues the certificate.

Let's Encrypt certificates are valid for 90 days, encouraging automation. Most ACME clients handle renewal automatically (certbot runs via systemd timer or cron).

### Debugging TLS

```bash
# Full TLS handshake details — shows protocol version, cipher suite, certificate chain
openssl s_client -connect api.example.com:443 -servername api.example.com

# Check certificate expiration
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | openssl x509 -noout -dates

# Check certificate SANs (Subject Alternative Names)
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName

# curl verbose shows TLS handshake details
curl -v https://api.example.com 2>&1 | grep -E '^\*'

# Test specific TLS version
openssl s_client -connect api.example.com:443 -tls1_3

# Test with a specific CA bundle (useful for debugging CA trust issues)
curl --cacert /path/to/ca-bundle.crt https://api.example.com
```

---

## 3. HTTP Request Lifecycle (End-to-End)

### What Happens When You Hit `https://api.example.com/users/123`

This is the single most important mental model for a backend engineer. Let us trace every step.

#### Step 1: DNS Resolution

The browser (or HTTP client) needs to resolve `api.example.com` to an IP address.

1. **Browser DNS cache**: Check if the domain was recently resolved. Chrome: `chrome://net-internals/#dns`.
2. **OS DNS cache**: Check the operating system's resolver cache. On Linux: `systemd-resolved` or `nscd`. On macOS: the mDNSResponder cache.
3. **Resolver (recursive DNS server)**: If not cached locally, the query goes to the configured recursive resolver (e.g., 8.8.8.8, 1.1.1.1, or your corporate DNS). The resolver has its own cache.
4. **Root nameservers**: If the resolver does not have the answer cached, it queries a root nameserver for the `.com` TLD.
5. **TLD nameservers**: The root points to the `.com` TLD nameservers. The resolver queries them for `example.com`.
6. **Authoritative nameserver**: The TLD points to the authoritative nameservers for `example.com` (e.g., `ns1.example.com`). The resolver queries them for `api.example.com` and gets back an IP (e.g., `93.184.216.34`).

Total time: 0ms (cached) to 200ms (cold cache, all steps required).

#### Step 2: TCP Connection

The client initiates a TCP connection to the resolved IP on port 443.

```
SYN  →  (network latency)  →  SYN-ACK  →  (network latency)  →  ACK
```

Cost: 1 RTT. If the server is 30ms away, this takes 30ms. With connection pooling, this cost is paid once and amortized over many requests.

#### Step 3: TLS Handshake

With TLS 1.3: 1 additional RTT. With TLS 1.2: 2 additional RTTs.

If the client has connected recently and has a session ticket: 0-RTT (TLS 1.3) or 1-RTT (TLS 1.2 session resumption).

#### Step 4: HTTP Request

The client sends the HTTP request over the encrypted connection:

```http
GET /users/123 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
User-Agent: MyApp/1.0
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

#### Step 5: Server Processing

The server receives the request, processes it (authentication, database query, business logic, serialization), and prepares a response. This is the part you control.

#### Step 6: HTTP Response

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: private, max-age=0
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
Content-Length: 127

{"id": 123, "name": "Alice", "email": "alice@example.com", "created_at": "2026-01-15T10:30:00Z"}
```

#### Step 7: Connection Handling

- **HTTP/1.1 Keep-Alive**: The connection stays open for subsequent requests (default behavior). But only one request can be in flight per connection.
- **HTTP/2 Multiplexing**: Multiple requests can be interleaved on a single connection using streams. No head-of-line blocking at the HTTP layer.
- **Connection: close**: The server or client indicates the connection should be closed after this response.

**Total latency for a cold request:**
```
DNS lookup:        ~50ms (uncached)
TCP handshake:     ~30ms (1 RTT)
TLS handshake:     ~30ms (1 RTT with TLS 1.3)
HTTP req/response: ~30ms (1 RTT) + server processing time
──────────────────────────────────
Total:             ~140ms + server processing
```

**With connection pooling and warm cache:**
```
HTTP req/response: ~30ms (1 RTT) + server processing
```

This is why connection pooling is not optional for production systems.

### HTTP/1.1 vs HTTP/2 vs HTTP/3

#### HTTP/1.1

- **One request per connection at a time**: To make concurrent requests, the client opens multiple TCP connections (browsers typically open 6 per host).
- **Text-based headers**: Headers are sent as plain text on every request, with no compression.
- **Chunked transfer encoding**: The server can stream response bodies of unknown size.
- **Pipelining**: Technically specified but never adopted in practice due to head-of-line blocking — responses must arrive in order.

#### HTTP/2 (RFC 7540)

- **Multiplexing**: Multiple requests and responses are interleaved on a single TCP connection using **streams**. Each stream has a unique ID.
- **Header compression (HPACK)**: Headers are compressed using a static table + dynamic table. Reduces header overhead from ~800 bytes to ~20 bytes for typical subsequent requests.
- **Server push**: The server can proactively send resources the client has not requested yet (e.g., pushing CSS when HTML is requested). Rarely used in practice due to complexity and cache issues; Chrome removed support in 2022.
- **Binary framing**: The protocol is binary, not text. Each frame has a fixed header format.
- **Stream prioritization**: Clients can indicate which streams are more important.

**The TCP head-of-line blocking problem**: HTTP/2 solves head-of-line blocking at the HTTP layer, but TCP still delivers bytes in order. If one TCP segment is lost, all streams stall until that segment is retransmitted. This is the fundamental limitation that motivated HTTP/3.

#### HTTP/3 (RFC 9114)

- **Built on QUIC**: QUIC is a transport protocol running over UDP that provides reliable, multiplexed streams. Each QUIC stream is independent — packet loss on one stream does not affect others.
- **No TCP head-of-line blocking**: Lost packets only stall the affected stream.
- **Faster connection establishment**: QUIC combines the transport handshake and TLS handshake into a single RTT. 0-RTT for resumed connections.
- **Connection migration**: QUIC connections are identified by a connection ID, not the IP/port tuple. If you switch from Wi-Fi to cellular, the connection survives.
- **QPACK**: Header compression adapted for QUIC (similar to HPACK but handles out-of-order delivery).

### HTTP Headers Every Backend Engineer Must Know

| Header | Direction | Purpose |
|--------|-----------|---------|
| `Content-Type` | Both | MIME type of the body (`application/json`, `text/html`, etc.) |
| `Content-Length` | Both | Size of the body in bytes |
| `Authorization` | Request | Authentication credentials (`Bearer <token>`, `Basic <base64>`) |
| `Cache-Control` | Both | Caching directives (`no-cache`, `max-age=3600`, `private`, `public`) |
| `ETag` | Response | Opaque identifier for a specific version of a resource |
| `If-None-Match` | Request | Conditional request — send the resource only if its ETag differs |
| `Vary` | Response | Tells caches which request headers affect the response (e.g., `Vary: Accept-Encoding`) |
| `X-Request-ID` | Both | Unique request identifier for distributed tracing |
| `Retry-After` | Response | How long to wait before retrying (with 429 or 503 responses) |
| `CORS headers` | Response | `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, etc. |
| `Transfer-Encoding` | Response | `chunked` — body is sent in chunks of unknown total size |
| `Connection` | Both | `keep-alive` (default in HTTP/1.1) or `close` |
| `Accept` | Request | Media types the client can handle (`application/json`, `text/html`) |

### HTTP Status Codes

**2xx — Success:**
- `200 OK`: Request succeeded.
- `201 Created`: Resource created (typically for POST). Should include `Location` header.
- `204 No Content`: Success, but no response body (typically for DELETE or PUT).

**3xx — Redirection:**
- `301 Moved Permanently`: Resource permanently at a new URL. Cacheable. Browsers change POST to GET.
- `302 Found`: Temporary redirect. Browsers change POST to GET (use 307 to preserve method).
- `304 Not Modified`: Conditional request — the cached version is still valid (used with `If-None-Match` / `If-Modified-Since`).

**4xx — Client Error:**
- `400 Bad Request`: Malformed request (invalid JSON, missing required field).
- `401 Unauthorized`: Authentication required or invalid. Should include `WWW-Authenticate` header.
- `403 Forbidden`: Authenticated but not authorized. Do not retry with the same credentials.
- `404 Not Found`: Resource does not exist.
- `409 Conflict`: Request conflicts with current state (e.g., duplicate email on user creation).
- `429 Too Many Requests`: Rate limit exceeded. Check `Retry-After` header.

**5xx — Server Error:**
- `500 Internal Server Error`: Unhandled exception on the server.
- `502 Bad Gateway`: The server acting as a reverse proxy received an invalid response from the upstream. Often means the upstream crashed or timed out.
- `503 Service Unavailable`: Server is temporarily overloaded or in maintenance. Should include `Retry-After`.
- `504 Gateway Timeout`: The reverse proxy timed out waiting for the upstream.

**Debugging heuristic**: 502 usually means the upstream process is dead or returned garbage. 504 usually means the upstream is alive but too slow. Both indicate the problem is upstream of whatever returned the error.

### Connection Pooling

Creating a new TCP connection per request is catastrophic for performance:

```
Without pooling (per-request connection):
  DNS + TCP + TLS + Request + Response + Close = ~200ms overhead per request

With pooling (reused connection):
  Request + Response = ~30ms overhead per request
```

Every production HTTP client must use connection pooling. Most do by default:

- **Go**: `http.Client` uses `http.Transport` which pools connections by default (`MaxIdleConnsPerHost`, default 2 — increase this for high-throughput services).
- **Python requests**: Use a `Session` object to enable connection pooling.
- **Node.js**: `http.Agent` pools connections. Set `keepAlive: true` (default since Node 19).
- **Java**: `HttpClient` pools connections by default.

```bash
# Monitor connection pool behavior — look for connection reuse vs new connections
curl -v https://api.example.com/users/1 https://api.example.com/users/2 2>&1 | grep -E 'Connected|Re-using'
```

---

## 4. DNS Resolution Deep Dive

### Full Resolution Path

```
Browser cache → OS cache → Recursive resolver cache → Root (.) → TLD (.com) → Authoritative (example.com)
```

A recursive resolver (e.g., Cloudflare 1.1.1.1, Google 8.8.8.8, your ISP's resolver) does the heavy lifting. When it receives a query it cannot answer from cache:

1. Query a **root nameserver** (13 root server clusters, anycast addresses, e.g., `a.root-servers.net`).
2. The root returns a referral to the **TLD nameserver** for `.com`.
3. Query the TLD nameserver. It returns a referral to the **authoritative nameserver** for `example.com`.
4. Query the authoritative nameserver. It returns the A/AAAA record for `api.example.com`.
5. The resolver caches the result according to the TTL and returns it to the client.

### DNS Record Types

| Record | Purpose | Example |
|--------|---------|---------|
| **A** | Maps hostname to IPv4 address | `api.example.com. 300 IN A 93.184.216.34` |
| **AAAA** | Maps hostname to IPv6 address | `api.example.com. 300 IN AAAA 2606:2800:220:1:...` |
| **CNAME** | Alias — points to another hostname | `www.example.com. 300 IN CNAME example.com.` |
| **MX** | Mail exchange server + priority | `example.com. 300 IN MX 10 mail.example.com.` |
| **TXT** | Arbitrary text (SPF, DKIM, domain verification) | `example.com. 300 IN TXT "v=spf1 include:_spf.google.com ~all"` |
| **SRV** | Service discovery (host + port + priority + weight) | `_grpc._tcp.example.com. 300 IN SRV 10 60 5060 server1.example.com.` |
| **NS** | Nameserver delegation | `example.com. 86400 IN NS ns1.example.com.` |
| **SOA** | Start of Authority — zone metadata | Contains serial number, refresh interval, etc. |
| **CAA** | Certificate Authority Authorization — which CAs can issue certs | `example.com. 300 IN CAA 0 issue "letsencrypt.org"` |

### TTL and Caching Behavior

The **TTL** (Time to Live) on a DNS record tells resolvers how long to cache the result.

- **Low TTL (30-60 seconds)**: Enables fast failover and changes. But generates more queries to the authoritative server, and some resolvers enforce a minimum TTL (e.g., some ISP resolvers have a 300-second floor).
- **High TTL (3600+ seconds)**: Reduces query load and improves reliability (clients can survive authoritative server outages). But changes propagate slowly.

**Negative caching**: If a query returns NXDOMAIN (the record does not exist), resolvers cache this too, based on the SOA record's minimum TTL. This means if you create a new DNS record, clients that recently got an NXDOMAIN may not see it for a while.

**Practical advice**: Use a TTL of 300 seconds (5 minutes) for most records. Reduce to 60 seconds before a migration, wait for the old TTL to expire, then do the migration.

### DNS Propagation

"DNS takes 24-48 hours to propagate" is largely a myth from the era when people set TTLs to 86400 seconds (24 hours). In reality:

- If the old TTL was 3600s and you change the record, every resolver will have the new value within 3600s.
- If you reduce the TTL to 60s first, wait 3600s (for the old TTL to expire), then change the record, every resolver will have the new value within 60s.
- Some resolvers ignore low TTLs or have minimum floors. This can cause pockets of stale resolution, but these are uncommon with major resolvers.

The "propagation" delay is really just caching. There is no propagation mechanism — resolvers simply hold onto the old answer until the TTL expires.

### DNS-Based Load Balancing

- **Round-robin**: Return multiple A records. The client (typically) tries them in order. Simple but offers no health checking.
- **Weighted**: Return records with different frequencies to distribute traffic proportionally.
- **Latency-based**: Route to the region with the lowest measured latency from the resolver's location (e.g., AWS Route 53 latency routing).
- **Geolocation**: Route based on the resolver's geographic location. Useful for regulatory compliance (data residency) or serving localized content.
- **Failover**: Return the primary IP normally; return the secondary only when health checks detect the primary is down.

All of these are implemented at the authoritative nameserver level and are features of managed DNS services (Route 53, Cloudflare DNS, Google Cloud DNS).

### DNS over HTTPS (DoH) and DNS over TLS (DoT)

Traditional DNS uses unencrypted UDP on port 53. This allows anyone on the network path (ISPs, Wi-Fi operators) to observe and modify DNS queries.

- **DoT (DNS over TLS, RFC 7858)**: Wraps DNS queries in TLS on port 853. Encrypts the query content but the port is distinctive, making it easy to block.
- **DoH (DNS over HTTPS, RFC 8484)**: Sends DNS queries as HTTPS POST/GET requests to a standard HTTPS endpoint. Encrypted and indistinguishable from normal HTTPS traffic.

Both are widely deployed. Major browsers support DoH. Operating systems are adding native DoT/DoH support.

### Common DNS Problems

**Stale cache**: A resolver is returning an old IP after you changed the record. Wait for the TTL to expire. If urgent, flush specific caches:

```bash
# Flush macOS DNS cache
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Flush systemd-resolved cache (Linux)
sudo systemd-resolve --flush-caches
```

**TTL too low → query storms**: If your TTL is 5 seconds and you have 10,000 servers, each server queries the authoritative nameserver every 5 seconds. That is 2,000 queries/second to your DNS server. Solution: use a local caching resolver (e.g., systemd-resolved, dnsmasq, unbound) on each host.

**TTL too high → slow failover**: If your TTL is 3600s and your primary server dies, clients will keep trying the dead IP for up to an hour.

**CNAME at zone apex**: You cannot have a CNAME at the root of your domain (`example.com`), only at subdomains (`www.example.com`). This is because CNAME cannot coexist with other records (like MX, TXT) at the same name, and the zone apex always has SOA and NS records. Solutions: use ALIAS/ANAME records (provider-specific) or simply use A records.

### Debugging DNS

```bash
# Basic lookup
dig api.example.com

# Full trace — shows every step of resolution
dig +trace api.example.com

# Query a specific nameserver
dig @8.8.8.8 api.example.com

# Show all record types
dig api.example.com ANY

# Specific record type
dig api.example.com AAAA
dig example.com MX
dig example.com TXT

# Short output (just the answer)
dig +short api.example.com

# Check the TTL remaining on a cached record
dig api.example.com | grep -E "^api"
# The number in the second column is the remaining TTL

# nslookup (simpler, less detailed)
nslookup api.example.com
nslookup -type=MX example.com

# Check what DNS server your system is using
cat /etc/resolv.conf            # Linux
scutil --dns | head -20         # macOS
```

---

## 5. WebSocket Protocol

### The WebSocket Handshake

WebSocket starts as an HTTP/1.1 request with an `Upgrade` header. This is the only part that uses HTTP — after the handshake, the protocol switches to WebSocket's binary frame format.

**Client request:**
```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: chat, superchat
```

**Server response:**
```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: chat
```

The `Sec-WebSocket-Accept` is a hash of the client's `Sec-WebSocket-Key` concatenated with a magic GUID (`258EAFA5-E914-47DA-95CA-5AB5DC11CE56`), then base64-encoded. This proves the server understands WebSocket (not just blindly proxying).

After the 101 response, both sides communicate using WebSocket frames over the same TCP connection.

### Frame Format

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+-------------------------------+
|                 Masking key (if MASK set)                      |
+-------------------------------+-------------------------------+
|                         Payload Data                          |
+---------------------------------------------------------------+
```

- **FIN bit**: 1 = this is the final fragment of a message. 0 = more fragments follow.
- **Opcode**: 0x1 = text frame, 0x2 = binary frame, 0x8 = close, 0x9 = ping, 0xA = pong, 0x0 = continuation.
- **MASK bit**: Client-to-server frames MUST be masked. Server-to-client frames MUST NOT be masked. The masking key is a random 32-bit value.
- **Payload length**: 7 bits for lengths 0-125. If 126, the next 2 bytes are the length. If 127, the next 8 bytes are the length.

### Ping/Pong Heartbeats

WebSocket defines ping (opcode 0x9) and pong (opcode 0xA) control frames for connection health monitoring:

- Either side can send a ping. The other side MUST respond with a pong containing the same payload.
- The payload is limited to 125 bytes.
- If a pong is not received within a timeout, the connection is considered dead.

**Why this matters:** TCP keep-alive operates at the OS level with coarse timeouts (minutes to hours). WebSocket ping/pong operates at the application level with fine-grained control (seconds). For real-time applications, ping/pong every 30 seconds is common.

### Close Handshake

Either side can initiate a close:

1. Send a close frame (opcode 0x8) with an optional status code and reason string.
2. The other side responds with its own close frame.
3. Both sides close the TCP connection.

**Close status codes:**
- `1000`: Normal closure.
- `1001`: Going away (server shutting down, browser navigating away).
- `1006`: Abnormal closure (connection lost without a close frame — generated locally, never sent on the wire).
- `1008`: Policy violation.
- `1009`: Message too big.
- `1011`: Unexpected server error.

### When to Use WebSocket vs Alternatives

| Feature | WebSocket | SSE (Server-Sent Events) | Long Polling | Short Polling |
|---------|-----------|--------------------------|--------------|---------------|
| Direction | Bidirectional | Server → Client only | Server → Client (with request per update) | Client → Server (periodic) |
| Connection | Persistent | Persistent | Held open, reconnects per message | New request each poll |
| Protocol | Custom binary frames | Plain HTTP (text/event-stream) | Plain HTTP | Plain HTTP |
| Browser support | Universal | Universal (except old IE) | Universal | Universal |
| Proxy/CDN friendly | Problematic | Yes (just HTTP) | Yes | Yes |
| Complexity | High | Low | Medium | Low |

**Use WebSocket when:**
- You need bidirectional real-time communication (chat, collaborative editing, multiplayer games).
- You need very low latency (sub-100ms) server-to-client updates.
- You need high-frequency updates (more than 1 per second).

**Use SSE when:**
- You only need server-to-client streaming (live feeds, notifications, progress updates).
- You want automatic reconnection (SSE has it built in, WebSocket does not).
- You need to work easily with existing HTTP infrastructure.

**Use polling when:**
- Update frequency is low (every 30-60 seconds).
- Simplicity matters more than efficiency.

### Scaling WebSockets Horizontally

WebSocket connections are stateful — a client is connected to a specific server instance. This creates challenges for horizontal scaling:

**Problem**: If you have 4 servers behind a load balancer and Client A is connected to Server 1, a message from Client B (on Server 2) intended for Client A will not reach it.

**Solutions:**

1. **Sticky sessions**: Route each client to the same server based on a cookie or IP hash. Simple but limits scaling (one server failure drops all its connections) and creates uneven load.

2. **Pub/sub backbone**: All servers subscribe to a shared message bus (Redis Pub/Sub, NATS, Kafka). When a message needs to be broadcast, it goes to the bus, and every server forwards it to its connected clients.

```
Client A ←→ Server 1 ←→ Redis Pub/Sub ←→ Server 2 ←→ Client B
                              ↕
                          Server 3 ←→ Client C
```

3. **Dedicated WebSocket service**: Use a service like Ably, Pusher, or AWS API Gateway WebSocket to offload connection management entirely.

### Common WebSocket Issues

**Proxy/load balancer timeout on idle connections**: Many load balancers (ALB, nginx) have idle timeouts (default 60 seconds on ALB). If no data flows for 60 seconds, the LB kills the connection. Solution: configure ping/pong at an interval shorter than the LB timeout.

```nginx
# nginx — increase WebSocket timeout
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;    # 1 hour
    proxy_send_timeout 3600s;
}
```

**Reconnection strategy**: WebSocket does not auto-reconnect. Implement exponential backoff with jitter:

```javascript
function connect() {
  const ws = new WebSocket('wss://api.example.com/ws');
  let retryDelay = 1000;

  ws.onclose = () => {
    const jitter = Math.random() * 1000;
    setTimeout(() => {
      retryDelay = Math.min(retryDelay * 2, 30000);  // Cap at 30 seconds
      connect();
    }, retryDelay + jitter);
  };

  ws.onopen = () => {
    retryDelay = 1000;  // Reset on successful connection
  };
}
```

**Backpressure**: If the server sends messages faster than the client can process them, the TCP send buffer fills up. The server should monitor the buffered amount and either slow down or drop messages for slow clients.

---

## 6. gRPC & Protocol Buffers

### Protobuf Wire Format

Protocol Buffers encode data as a sequence of (field_number, wire_type, value) tuples. This is what makes protobuf compact and fast.

**Wire types:**

| Wire Type | Meaning | Used For |
|-----------|---------|----------|
| 0 | Varint | int32, int64, uint32, uint64, sint32, sint64, bool, enum |
| 1 | 64-bit | fixed64, sfixed64, double |
| 2 | Length-delimited | string, bytes, embedded messages, repeated fields (packed) |
| 5 | 32-bit | fixed32, sfixed32, float |

**Varint encoding**: Protobuf uses variable-length integers where small values use fewer bytes. Each byte uses 7 bits for data and 1 bit (MSB) to indicate if more bytes follow. The value `1` uses 1 byte; the value `300` uses 2 bytes.

**Field numbers**: The `.proto` file assigns a number to each field. This number (not the field name) appears in the wire format. This is why field numbers should never be reused — they are the permanent identity of a field.

```protobuf
message User {
  int32 id = 1;           // field number 1
  string name = 2;        // field number 2
  string email = 3;       // field number 3
  repeated string tags = 4; // field number 4
}
```

The encoded message `{id: 150, name: "Alice"}` looks like:

```
08 96 01        → field 1, varint, value 150
12 05 41 6c 69 63 65  → field 2, length-delimited, length 5, "Alice"
```

Total: 12 bytes for what JSON would encode as `{"id":150,"name":"Alice"}` (30 bytes).

### gRPC over HTTP/2

gRPC uses HTTP/2 as its transport layer. Each RPC call maps to an HTTP/2 stream:

```
Client                                          Server
  |                                                |
  |  HEADERS (POST /UserService/GetUser)           |
  |  + content-type: application/grpc              |
  |  + grpc-timeout: 5S                            |
  |  DATA (protobuf-encoded request)               |
  |  END_STREAM                                    |
  |  --------------------------------------------->|
  |                                                |
  |  HEADERS (status: 200, content-type: grpc)     |
  |  DATA (protobuf-encoded response)              |
  |  HEADERS (trailers: grpc-status: 0)            |
  |  END_STREAM                                    |
  |<-----------------------------------------------|
```

Key observations:
- The RPC method name is the HTTP path: `/package.ServiceName/MethodName`.
- The request and response bodies are protobuf-encoded (prefixed with a 5-byte header: 1 byte compression flag + 4 bytes message length).
- gRPC uses **HTTP trailers** to send the `grpc-status` code after the response body. This is critical — the HTTP status code is always 200, and the actual success/failure is in the trailer.

### gRPC Call Types

```protobuf
service ChatService {
  // Unary: one request, one response
  rpc GetUser (GetUserRequest) returns (User);

  // Server streaming: one request, stream of responses
  rpc ListMessages (ListMessagesRequest) returns (stream Message);

  // Client streaming: stream of requests, one response
  rpc UploadChunks (stream Chunk) returns (UploadResult);

  // Bidirectional streaming: stream of requests, stream of responses
  rpc Chat (stream ChatMessage) returns (stream ChatMessage);
}
```

**Unary**: The most common. One request, one response. Equivalent to a REST API call.

**Server streaming**: The server sends multiple messages back. Useful for large datasets, real-time feeds, or paginated results where you want to stream rather than buffer.

**Client streaming**: The client sends multiple messages. Useful for file upload (send chunks), batch processing, or aggregation.

**Bidirectional streaming**: Both sides send a stream of messages independently. The streams are independent — the server does not need to wait for the client to finish. Useful for chat, real-time collaboration, or any bidirectional data flow.

### gRPC Metadata

gRPC metadata is the equivalent of HTTP headers. It consists of key-value pairs sent at the start (headers) and end (trailers) of an RPC.

- **Headers**: Sent before the first message. Used for authentication tokens, request IDs, tracing context.
- **Trailers**: Sent after the last message. Contains `grpc-status` and `grpc-message`. Can also carry custom metadata.

```go
// Go example — setting and reading metadata
import "google.golang.org/grpc/metadata"

// Client: send metadata
md := metadata.New(map[string]string{
    "authorization": "Bearer <token>",
    "x-request-id":  "abc-123",
})
ctx := metadata.NewOutgoingContext(ctx, md)
resp, err := client.GetUser(ctx, req)

// Server: read metadata
md, ok := metadata.FromIncomingContext(ctx)
if ok {
    token := md.Get("authorization")
}
```

### gRPC Status Codes

gRPC defines its own status codes (separate from HTTP status codes):

| Code | Name | Meaning |
|------|------|---------|
| 0 | OK | Success |
| 1 | CANCELLED | Operation cancelled by the caller |
| 2 | UNKNOWN | Unknown error (often a catch-all) |
| 3 | INVALID_ARGUMENT | Client sent invalid data (equivalent to HTTP 400) |
| 4 | DEADLINE_EXCEEDED | Operation timed out (equivalent to HTTP 504) |
| 5 | NOT_FOUND | Resource not found (equivalent to HTTP 404) |
| 7 | PERMISSION_DENIED | Caller lacks permission (equivalent to HTTP 403) |
| 8 | RESOURCE_EXHAUSTED | Rate limit or quota exceeded (equivalent to HTTP 429) |
| 12 | UNIMPLEMENTED | Method not implemented (equivalent to HTTP 501) |
| 13 | INTERNAL | Internal server error (equivalent to HTTP 500) |
| 14 | UNAVAILABLE | Service temporarily unavailable — retry (equivalent to HTTP 503) |
| 16 | UNAUTHENTICATED | Missing or invalid auth (equivalent to HTTP 401) |

**Important**: Only codes 14 (UNAVAILABLE) should generally be retried automatically. DEADLINE_EXCEEDED may be retried depending on whether the operation is idempotent.

### gRPC Interceptors

Interceptors are gRPC's middleware pattern. They wrap RPC calls to add cross-cutting concerns:

```go
// Unary server interceptor — logging example
func loggingInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    start := time.Now()
    resp, err := handler(ctx, req)
    log.Printf("method=%s duration=%s error=%v",
        info.FullMethod, time.Since(start), err)
    return resp, err
}

// Register interceptor
server := grpc.NewServer(
    grpc.UnaryInterceptor(loggingInterceptor),
)
```

Common interceptor use cases: logging, metrics, authentication, tracing, rate limiting, error recovery.

### gRPC-Web

Browsers cannot use gRPC directly because they lack control over HTTP/2 framing and trailers. **gRPC-Web** is a protocol adaptation:

- Uses HTTP/1.1 or HTTP/2 (without requiring trailer support).
- Encodes trailers in the response body instead of HTTP trailers.
- Requires a proxy (Envoy, grpc-web-proxy) between the browser and the gRPC server.

```
Browser → [gRPC-Web request over HTTP/1.1] → Envoy proxy → [native gRPC over HTTP/2] → gRPC server
```

Alternatively, **Connect** (from Buf) provides a gRPC-compatible protocol that works natively in browsers without a proxy, using standard HTTP POST with JSON or protobuf bodies.

### Protobuf Schema Evolution

Protobuf is designed for backward and forward compatible schema changes. The rules:

**Safe changes:**
- **Add a new field** with a new field number. Old code ignores unknown fields. New code uses the default value for missing fields.
- **Remove a field** (but **reserve** its number so it is never reused).
- **Rename a field** — field names are not part of the wire format.

**Unsafe changes:**
- **Change a field number** — breaks all existing encoded data.
- **Change a field type** (e.g., `int32` → `string`) — the decoder will misinterpret the bytes.
- **Reuse a field number** — old data with that number will be decoded as the new field type.

```protobuf
message User {
  int32 id = 1;
  string name = 2;
  // email was removed — reserve the number to prevent accidental reuse
  reserved 3;
  reserved "email";
  string phone = 4;  // newly added
}
```

### gRPC vs REST Decision Framework

| Factor | Choose gRPC | Choose REST |
|--------|-------------|-------------|
| Client types | Internal services, mobile apps | Browsers, third-party consumers, public APIs |
| Performance | High throughput, low latency required | Adequate for most web workloads |
| Streaming | Need bidirectional or server streaming | Server-Sent Events sufficient |
| Schema | Strong typing with protobuf, contract-first | Flexible, JSON-based |
| Tooling | protoc, buf, grpcurl | curl, Postman, browser |
| Human readability | Binary (need tools to inspect) | JSON/text (human-readable) |
| Ecosystem | Growing (gRPC-Web, Connect) | Universal |
| API evolution | Excellent (protobuf field numbering) | Versioned URLs or headers |

**General rule**: Use gRPC for internal service-to-service communication where performance matters. Use REST for public APIs and browser-facing endpoints.

### Debugging gRPC

```bash
# grpcurl — curl for gRPC
# List services
grpcurl -plaintext localhost:50051 list

# Describe a service
grpcurl -plaintext localhost:50051 describe mypackage.UserService

# Make a unary call
grpcurl -plaintext -d '{"id": 123}' localhost:50051 mypackage.UserService/GetUser

# With TLS
grpcurl -cacert ca.pem -cert client.pem -key client-key.pem \
  api.example.com:443 mypackage.UserService/GetUser

# Server reflection must be enabled for grpcurl to discover services:
# Go: import "google.golang.org/grpc/reflection"; reflection.Register(server)
```

**Bloom RPC** (now succeeded by **Kreya** and **Postman gRPC**): GUI tools for testing gRPC services, similar to Postman for REST.

**grpc-web-devtools**: A Chrome extension that shows gRPC-Web requests in the DevTools Network tab.

---

## 7. Network Debugging & Troubleshooting

This is the section you read at 3 AM when production is down and you do not know why.

### curl — The Swiss Army Knife

curl is the single most important debugging tool for HTTP-based services.

```bash
# Basic request with verbose output — shows DNS, TCP, TLS, HTTP details
curl -v https://api.example.com/users/123

# Timing breakdown — where is the latency?
curl -o /dev/null -s -w "\
    DNS lookup:     %{time_namelookup}s\n\
    TCP connect:    %{time_connect}s\n\
    TLS handshake:  %{time_appconnect}s\n\
    TTFB:           %{time_starttransfer}s\n\
    Total:          %{time_total}s\n\
    HTTP status:    %{http_code}\n\
    Size download:  %{size_download} bytes\n" \
    https://api.example.com/users/123

# Output example:
#   DNS lookup:     0.012s
#   TCP connect:    0.045s     (TCP handshake completed 33ms after DNS)
#   TLS handshake:  0.095s     (TLS completed 50ms after TCP)
#   TTFB:           0.250s     (first byte 155ms after TLS — this is server processing time)
#   Total:          0.260s
#   HTTP status:    200
#   Size download:  1234 bytes

# Test against a specific IP (bypass DNS — useful for testing before DNS cutover)
curl --resolve api.example.com:443:10.0.1.50 https://api.example.com/users/123

# Send custom headers
curl -H "Authorization: Bearer <token>" \
     -H "X-Request-ID: debug-$(date +%s)" \
     https://api.example.com/users/123

# POST with JSON body
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice", "email": "alice@example.com"}' \
     https://api.example.com/users

# Follow redirects
curl -L https://example.com

# Show response headers only
curl -I https://api.example.com/health

# Test with specific TLS version
curl --tlsv1.3 https://api.example.com

# Test with client certificate (mTLS)
curl --cert client.pem --key client-key.pem --cacert ca.pem \
     https://internal-api.example.com/data

# Send request and show the full HTTP exchange (headers + body for both request and response)
curl -v --trace-ascii /dev/stdout https://api.example.com/health
```

**Interpreting the timing breakdown:**

```
DNS lookup:     0.012s     ← DNS resolution took 12ms
TCP connect:    0.045s     ← TCP handshake completed at 45ms (so TCP handshake = 45 - 12 = 33ms)
TLS handshake:  0.095s     ← TLS completed at 95ms (so TLS handshake = 95 - 45 = 50ms)
TTFB:           0.250s     ← First byte at 250ms (so server processing = 250 - 95 = 155ms)
Total:          0.260s     ← Done at 260ms (so transfer = 260 - 250 = 10ms)
```

If DNS is slow → check resolver, consider caching.
If TCP connect is slow → network latency or packet loss.
If TLS is slow → consider session resumption, or the server is CPU-bound on crypto.
If TTFB minus TLS is slow → the server is slow (database query, computation, upstream dependency).
If Total minus TTFB is large → the response body is large, or bandwidth is constrained.

### tcpdump

tcpdump captures packets on a network interface. It is available on virtually every Linux/Unix system.

```bash
# Capture all traffic on the default interface
sudo tcpdump -i any

# Capture traffic to/from a specific host
sudo tcpdump -i any host api.example.com

# Capture only TCP traffic on port 443
sudo tcpdump -i any tcp port 443

# Capture traffic from a specific source
sudo tcpdump -i any src 10.0.1.50

# Capture and save to a file for later analysis (e.g., in Wireshark)
sudo tcpdump -i any -w /tmp/capture.pcap port 443

# Read a capture file
sudo tcpdump -r /tmp/capture.pcap

# Show TCP flags (SYN, ACK, FIN, RST) and sequence numbers
sudo tcpdump -i any -S tcp port 8080

# Capture only SYN packets (new connections)
sudo tcpdump -i any 'tcp[tcpflags] & tcp-syn != 0'

# Capture only RST packets (connection resets — useful for debugging unexpected disconnects)
sudo tcpdump -i any 'tcp[tcpflags] & tcp-rst != 0'

# Show packet contents in hex and ASCII
sudo tcpdump -i any -X port 80

# Limit capture to first 200 bytes of each packet
sudo tcpdump -i any -s 200 port 443

# Capture HTTP traffic (unencrypted) and show request/response
sudo tcpdump -i any -A port 80 | grep -E "^(GET|POST|HTTP|Host|Content)"
```

**Common tcpdump patterns for debugging:**

```bash
# Are SYN packets being sent? (Is the client trying to connect?)
sudo tcpdump -i any 'tcp[tcpflags] == tcp-syn' and host api.example.com

# Are SYN-ACKs coming back? (Is the server responding?)
sudo tcpdump -i any 'tcp[tcpflags] == (tcp-syn|tcp-ack)' and host api.example.com

# Are there retransmissions? (Packet loss or congestion)
sudo tcpdump -i any tcp and host api.example.com | grep retransmit
# (Better: analyze in Wireshark which detects retransmissions automatically)
```

### Wireshark

Wireshark provides a GUI for deep packet analysis. While tcpdump captures, Wireshark analyzes.

**Capture filters** (BPF syntax, applied during capture):
```
host 10.0.1.50
port 443
tcp port 8080 and host 10.0.1.50
```

**Display filters** (applied after capture, much richer):
```
# Show only HTTP traffic
http

# Show only TLS handshake messages
tls.handshake

# Show only TCP retransmissions
tcp.analysis.retransmission

# Show only RST packets
tcp.flags.reset == 1

# Show traffic to a specific IP
ip.dst == 10.0.1.50

# Show slow responses (time since request > 1 second)
http.time > 1

# Show only gRPC traffic
http2.header.name == "content-type" && http2.header.value contains "grpc"
```

**Following a TCP stream**: Right-click any packet → "Follow" → "TCP Stream." This reassembles the full conversation (all data sent in both directions) in a single view. Invaluable for debugging HTTP issues.

**Expert Info**: Analyze → Expert Information shows a summary of problems Wireshark detected: retransmissions, duplicate ACKs, window full events, RST packets.

### mtr — Network Path Analysis

mtr combines traceroute and ping into a single tool, continuously updating latency and packet loss for each hop.

```bash
# Basic usage — shows every hop between you and the destination
mtr api.example.com

# Non-interactive (send 100 packets, print report)
mtr --report --report-cycles 100 api.example.com

# Example output:
# HOST                  Loss%   Snt   Last   Avg  Best  Wrst StDev
# 1. gateway.local       0.0%   100    0.5   0.6   0.3   2.1   0.3
# 2. isp-router.net      0.0%   100    5.2   5.1   4.8   6.3   0.4
# 3. core-router.isp     0.0%   100   12.1  12.0  11.5  14.2   0.6
# 4. peering-point.net   2.0%   100   15.3  15.5  14.8  25.1   2.1  ← packet loss here
# 5. cdn-edge.example    0.0%   100   15.1  15.2  14.9  16.0   0.3
# 6. api.example.com     0.0%   100   15.0  15.1  14.8  15.9   0.3

# Use TCP instead of ICMP (some routers block ICMP)
mtr --tcp --port 443 api.example.com
```

**Interpreting mtr output:**
- **Loss% increasing at a hop and staying high for all subsequent hops**: Real packet loss at that hop. The network is dropping packets.
- **Loss% at one hop but 0% at subsequent hops**: The router is deprioritizing ICMP (traceroute) packets. This is not actual packet loss — ignore it.
- **Latency jump at a hop**: A long link (e.g., crossing an ocean). Expected. If the jump is unexpected (e.g., +100ms between two hops in the same datacenter), investigate.

### ss / netstat

`ss` (socket statistics) is the modern replacement for `netstat`. It reads from the kernel directly rather than parsing `/proc/net/tcp`.

```bash
# Show all TCP connections with state
ss -ant

# Count connections by state
ss -ant | awk '{print $1}' | sort | uniq -c | sort -rn
#  4521 ESTAB
#   892 TIME-WAIT
#    23 CLOSE-WAIT
#     5 SYN-SENT

# Show connections to a specific port
ss -ant dst :5432    # PostgreSQL connections
ss -ant dst :6379    # Redis connections

# Show which process owns each connection
ss -antp

# Show listening sockets (what ports are open)
ss -tlnp
# Output:
# LISTEN  0  4096  *:8080  *:*  users:(("myapp",pid=1234,fd=7))
# The '4096' is the backlog (listen queue size)

# Show socket memory usage and TCP window sizes
ss -antm

# Show TCP internal info (congestion control, RTT, cwnd)
ss -anti
# Output includes:
#   cubic wscale:7,7 rto:204 rtt:1.516/0.751 ato:40 mss:1448 pmtu:1500
#   rcvmss:1448 advmss:1448 cwnd:10 ssthresh:7 bytes_sent:1234
#   bytes_acked:1234 segs_out:50 segs_in:45 data_segs_out:25
```

**Key things to watch:**
- **High TIME-WAIT count**: You are opening and closing too many connections. Implement connection pooling.
- **CLOSE-WAIT accumulation**: Your application is not closing connections after the remote side sent FIN. This is a bug in your code — you are leaking file descriptors.
- **SYN-SENT stuck**: Your outbound connection attempts are not getting responses. Firewall, security group, or the remote server is down.
- **Large listen backlog overflow**: Check `ss -tlnp` — if the backlog is full, new connections are dropped silently.

### dig +trace

```bash
# Full DNS resolution trace — shows every query from root to authoritative
dig +trace api.example.com

# Example output:
# .                       518400  IN  NS  a.root-servers.net.
# com.                    172800  IN  NS  a.gtld-servers.net.
# example.com.            172800  IN  NS  ns1.example.com.
# api.example.com.        300     IN  A   93.184.216.34

# This tells you:
# 1. Which root server was queried
# 2. Which TLD server was queried
# 3. Which authoritative server answered
# 4. The actual record and its TTL
```

### openssl s_client

```bash
# Full TLS connection details
openssl s_client -connect api.example.com:443 -servername api.example.com

# Key things to look for in output:
# - Certificate chain (verify return:1 means OK)
# - Protocol: TLSv1.3
# - Cipher: TLS_AES_256_GCM_SHA384
# - Server certificate subject and SANs
# - Certificate validity dates

# Check if a certificate is about to expire
echo | openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -enddate
# notAfter=Jun 15 12:00:00 2026 GMT

# Show the full certificate chain
openssl s_client -connect api.example.com:443 -showcerts

# Test a specific TLS version
openssl s_client -connect api.example.com:443 -tls1_2
openssl s_client -connect api.example.com:443 -tls1_3

# Test STARTTLS for email servers
openssl s_client -connect mail.example.com:587 -starttls smtp
```

### Network Latency Debugging Workflow

When a request is slow, systematically determine where the time is spent:

```
Step 1: Is it DNS?
─────────────────
$ dig api.example.com
;; Query time: 150 msec    ← Slow! Normal is <10ms for cached, <50ms for uncached.

Fix: Check resolver, consider local caching (systemd-resolved, dnsmasq).


Step 2: Is it TCP?
──────────────────
$ curl -o /dev/null -s -w "TCP connect: %{time_connect}s\n" https://api.example.com
TCP connect: 0.350s    ← 350ms for TCP handshake? Check for packet loss.

$ mtr --report --report-cycles 30 api.example.com
Look for loss% > 0 or unexpected latency jumps.


Step 3: Is it TLS?
──────────────────
$ curl -o /dev/null -s -w "TLS: %{time_appconnect}s  TCP: %{time_connect}s\n" https://api.example.com
TLS: 0.800s  TCP: 0.350s    ← TLS took 450ms on top of TCP.

Check: certificate chain too long? Missing intermediate? OCSP lookup slow?
Fix: Enable OCSP stapling, ensure full chain is configured, enable TLS session resumption.


Step 4: Is it the server?
─────────────────────────
$ curl -o /dev/null -s -w "TTFB: %{time_starttransfer}s  TLS: %{time_appconnect}s\n" https://api.example.com
TTFB: 2.100s  TLS: 0.095s    ← Server took 2 seconds to respond.

The problem is backend processing: slow database query, slow upstream dependency, CPU-bound computation.
Add logging, check database query plans, check upstream latency.


Step 5: Is it the network (transfer)?
──────────────────────────────────────
$ curl -o /dev/null -s -w "Total: %{time_total}s  TTFB: %{time_starttransfer}s\n" https://api.example.com
Total: 5.000s  TTFB: 0.250s    ← 4.75 seconds transferring data.

Response body is large or bandwidth is constrained.
Fix: Compress response (gzip/br), paginate, reduce payload size.
```

### Common Network Issues — Symptoms and Diagnosis

#### High TIME_WAIT → Connection Pool Exhaustion

**Symptoms**: "Cannot assign requested address" errors, connections failing intermittently, `ss -s` shows thousands of TIME_WAIT sockets.

```bash
# Diagnose
ss -s | grep TIME-WAIT
# TCP: 28342 (estab 156, closed 27891, orphaned 0, timewait 27891)

# The ephemeral port range (default ~28,000 ports) is nearly exhausted
cat /proc/sys/net/ipv4/ip_local_port_range
# 32768   60999

# Fix: Enable connection pooling in your application (the real fix)
# Temporary mitigation:
sysctl -w net.ipv4.tcp_tw_reuse=1
```

#### TCP Retransmissions → Packet Loss or Congestion

**Symptoms**: Requests intermittently slow, latency spikes, throughput lower than expected.

```bash
# Check retransmission stats
ss -anti | grep retrans
# Or system-wide:
cat /proc/net/snmp | grep -E "Tcp.*Retrans"
# Tcp: ... RetransSegs 45231

# Use mtr to find where packet loss is happening
mtr --report --report-cycles 100 api.example.com
```

#### TLS Handshake Failures

**Symptoms**: "SSL: CERTIFICATE_VERIFY_FAILED", "handshake failure", "no common cipher suites".

```bash
# Check the certificate chain
openssl s_client -connect api.example.com:443 -servername api.example.com 2>&1 | grep -E "verify|subject|issuer"

# Common causes:
# 1. Certificate expired
echo | openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -dates

# 2. Missing intermediate certificate — server only sends leaf
openssl s_client -connect api.example.com:443 2>&1 | grep "verify error"
# verify error:num=21:unable to verify the first certificate

# 3. SNI mismatch — server returns wrong certificate because SNI is missing
openssl s_client -connect 10.0.1.50:443       # No SNI → might get wrong cert
openssl s_client -connect 10.0.1.50:443 -servername api.example.com  # With SNI → correct cert

# 4. Cipher suite incompatibility
openssl s_client -connect api.example.com:443 -cipher 'ECDHE-RSA-AES128-GCM-SHA256'
```

#### DNS NXDOMAIN → Misconfigured Records

**Symptoms**: "Could not resolve host", NXDOMAIN in dig output.

```bash
# Verify the record exists at the authoritative nameserver
dig +trace api.example.com

# If the authoritative server returns NXDOMAIN, the record does not exist there
# Check if the record was recently changed (negative caching)
dig api.example.com SOA  # The minimum TTL field controls negative cache duration
```

#### 502 Bad Gateway → Upstream Crash or Invalid Response

**Symptoms**: Intermittent 502 errors from the load balancer or reverse proxy.

```bash
# Check if the upstream is running
curl -v http://localhost:8080/health

# Check upstream logs for crashes or panics
journalctl -u myapp --since "5 minutes ago"

# Check if the upstream is listening
ss -tlnp | grep 8080

# Check if the LB/proxy can reach the upstream
# (from the LB host)
curl -v http://upstream-host:8080/health
```

#### 504 Gateway Timeout → Upstream Too Slow

**Symptoms**: Consistent 504 errors after exactly N seconds (the proxy's timeout).

```bash
# Check proxy timeout configuration
# nginx: proxy_read_timeout (default 60s)
# ALB: idle timeout (default 60s)
# Envoy: route timeout (default 15s)

# Verify the upstream is indeed slow
curl -o /dev/null -s -w "TTFB: %{time_starttransfer}s\n" http://upstream:8080/slow-endpoint

# Fix: optimize the slow endpoint, or increase the timeout if the slowness is expected
```

#### Connection Refused → Nothing Listening

**Symptoms**: "Connection refused" immediately (no timeout).

```bash
# Verify the service is listening on the expected port
ss -tlnp | grep <port>

# If it's not listed:
# - The service is not running
# - The service is running but listening on a different port
# - The service is listening on localhost (127.0.0.1) but you're connecting from another host

# Check if a firewall is blocking the port
iptables -L -n | grep <port>          # Linux iptables
ufw status                             # UFW
firewall-cmd --list-all                # firewalld

# For cloud: check security group and network ACL rules in the AWS/GCP console
```

### Emergency Debugging Cheat Sheet

When production is on fire and you need answers fast:

```bash
# 1. Is the service up?
curl -s -o /dev/null -w "%{http_code}" https://api.example.com/health

# 2. Where is the latency?
curl -o /dev/null -s -w "dns:%{time_namelookup} tcp:%{time_connect} tls:%{time_appconnect} ttfb:%{time_starttransfer} total:%{time_total}\n" https://api.example.com/health

# 3. How many connections in each state?
ss -ant | awk '{print $1}' | sort | uniq -c | sort -rn

# 4. Is there packet loss on the path?
mtr --report --report-cycles 20 api.example.com

# 5. Is the certificate OK?
echo | openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -dates -subject

# 6. What does DNS return?
dig +short api.example.com

# 7. Are there TCP retransmissions? (system-wide)
cat /proc/net/snmp | grep Tcp | head -2

# 8. What is the process doing?
strace -p <pid> -e trace=network -f    # What network syscalls is it making?
lsof -p <pid> -i                       # What network connections does it have?

# 9. Is the disk (or something else) blocking the process?
cat /proc/<pid>/status | grep -E "State|voluntary"
# voluntary_ctxt_switches: high = waiting on I/O
# nonvoluntary_ctxt_switches: high = CPU contention
```

---

## Summary

The network is not a black box. Every production issue — slow requests, intermittent failures, mysterious timeouts — has a root cause in one of the layers covered in this chapter. The key mental model:

1. **DNS**: Is the name resolving correctly and quickly?
2. **TCP**: Is the connection establishing, and is data flowing without loss?
3. **TLS**: Is the handshake succeeding, and are certificates valid?
4. **HTTP**: Are the right headers set, and is the server returning the expected status?
5. **Application**: Is the server processing the request efficiently?

When debugging, work from the bottom up. Use the timing breakdown from `curl -w` to identify which layer is slow. Then use the layer-specific tools (dig for DNS, ss/tcpdump for TCP, openssl s_client for TLS, application logs for HTTP/app) to pinpoint the issue.

The engineers who get paged at 3 AM and actually fix things are the ones who understand these layers. Now you are one of them.
